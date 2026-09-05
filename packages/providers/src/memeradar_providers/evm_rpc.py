"""Shared read-only EVM JSON-RPC adapter for BNB and Robinhood Chain."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    OnChainPort,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import (
    Chain,
    Observation,
    Provenance,
    QualityState,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import ensure_utc, require_text

from .transport import (
    CapabilityUnavailableError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RateLimitSnapshot,
)

Clock = Callable[[], datetime]
EVM_RPC_PARSER_VERSION = "evm-rpc-v1"
EVM_CHAIN_IDS: Mapping[Chain, int] = {Chain.BNB: 56, Chain.ROBINHOOD: 4663}
EVM_CHAIN_ID_BY_NAME = {chain.value: value for chain, value in EVM_CHAIN_IDS.items()}
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "token",
}
_EVM_HEX_INT = re.compile(r"^0x[0-9a-fA-F]+$")


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _hex_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ProviderSchemaError(f"provider {field} was invalid")
    if isinstance(value, int):
        if value < 0:
            raise ProviderSchemaError(f"provider {field} was invalid")
        return value
    if not isinstance(value, str) or not value.strip():
        raise ProviderSchemaError(f"provider {field} was invalid")
    normalized = value.strip()
    try:
        return int(normalized, 16 if _EVM_HEX_INT.fullmatch(normalized) else 10)
    except ValueError as exc:
        raise ProviderSchemaError(f"provider {field} was invalid") from exc


class EvmRpcHealthStatus(str, Enum):
    """Safe readiness result for one EVM RPC endpoint."""

    PASS = "PASS"
    DEGRADED = "DEGRADED"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"


class EvmRpcAdapter(OnChainPort):
    """Read-only standard JSON-RPC for any supported EVM chain."""

    capabilities = frozenset({"chain_rpc", "on_chain"})

    def __init__(
        self,
        chain: Chain | str,
        endpoint: str,
        *,
        api_key: str | None = None,
        expected_chain_id: int | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = EVM_RPC_PARSER_VERSION,
        max_concurrency: int = 4,
    ) -> None:
        normalized_chain = normalize_chain(chain)
        if normalized_chain not in EVM_CHAIN_IDS:
            raise ValueError("EvmRpcAdapter requires an EVM chain")
        configured_id = EVM_CHAIN_IDS[normalized_chain]
        if expected_chain_id is not None and expected_chain_id != configured_id:
            raise ValueError(
                f"expected_chain_id must be {configured_id} for {normalized_chain.value}"
            )
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")
        if not 1 <= max_concurrency <= 32:
            raise ValueError("max_concurrency must be between 1 and 32")
        self.chain = normalized_chain
        self.provider_name = f"evm-public-rpc:{normalized_chain.value}"
        self._endpoint = self._validate_endpoint(endpoint)
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._expected_chain_id = configured_id
        self.chain_id: int | None = None
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=self.provider_name)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._last_rate_limit: RateLimitSnapshot | None = None

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        normalized = require_text(endpoint, "endpoint", max_length=512)
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("endpoint must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("endpoint must not contain credentials or a fragment")
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
                raise ValueError("endpoint must not contain credential query parameters")
        return normalized.rstrip("/")

    def __repr__(self) -> str:
        return (
            f"EvmRpcAdapter(chain={self.chain.value!r}, endpoint={self._endpoint!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> EvmRpcAdapter:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def last_rate_limit(self) -> RateLimitSnapshot | None:
        return self._last_rate_limit

    def _timeout_for(self, context: ProviderRequestContext) -> float | None:
        if context.deadline_at is None:
            return None
        remaining = (
            ensure_utc(context.deadline_at, "deadline_at") - ensure_utc(self._clock(), "now")
        ).total_seconds()
        if remaining <= 0:
            raise ProviderTimeoutError("provider request deadline expired")
        return min(remaining, self._transport.timeouts.overall_seconds)

    @staticmethod
    def _rate_limit_snapshot(headers: httpx.Headers) -> RateLimitSnapshot | None:
        raw_retry_after = headers.get("retry-after")
        if raw_retry_after is None:
            return None
        try:
            retry_after = float(raw_retry_after)
        except ValueError:
            return None
        if not math.isfinite(retry_after) or not 0 <= retry_after <= 86_400:
            return None
        return RateLimitSnapshot(retry_after_seconds=retry_after)

    async def _rpc(
        self,
        method: str,
        params: Sequence[object],
        *,
        context: ProviderRequestContext,
    ) -> object:
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-correlation-id": context.correlation_id,
        }
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        async def operation() -> object:
            try:
                response = await self._client.post(
                    self._endpoint,
                    json=body,
                    headers=headers,
                    timeout=httpx.Timeout(
                        self._transport.timeouts.overall_seconds,
                        connect=self._transport.timeouts.connect_seconds,
                        read=self._transport.timeouts.read_seconds,
                        write=self._transport.timeouts.write_seconds,
                        pool=self._transport.timeouts.connect_seconds,
                    ),
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError("provider request timed out") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError("provider transport failed") from exc
            snapshot = self._rate_limit_snapshot(response.headers)
            if snapshot is not None:
                self._last_rate_limit = snapshot
                self._transport.rate_limiter.update(snapshot)
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                retry_after = snapshot.retry_after_seconds if snapshot is not None else None
                raise ProviderRateLimitedError(retry_after)
            if response.status_code == 408:
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            if not isinstance(payload, Mapping) or payload.get("jsonrpc") != "2.0":
                raise ProviderSchemaError("provider response envelope was invalid")
            if "error" in payload:
                error = payload["error"]
                code = error.get("code") if isinstance(error, Mapping) else None
                if code == -32005:
                    raise ProviderRateLimitedError()
                raise ProviderError("provider JSON-RPC request failed")
            if "result" not in payload:
                raise ProviderSchemaError("provider response result was missing")
            return payload["result"]

        async with self._semaphore:
            return await self._transport.execute(
                operation,
                timeout_seconds=self._timeout_for(context),
            )

    def _provenance(self, source_id: str, observed_at: datetime, result: object) -> Provenance:
        return Provenance(
            provider=self.provider_name,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=self._parser_version,
            raw_payload_hash=_payload_hash(result),
        )

    async def verify_chain_id(self, *, context: ProviderRequestContext) -> int:
        result = await self._rpc("eth_chainId", (), context=context)
        chain_id = _hex_int(result, "chain_id")
        if chain_id != self._expected_chain_id:
            raise ProviderSchemaError(
                f"provider returned chain id {chain_id}; expected chain id "
                f"{self._expected_chain_id}"
            )
        self.chain_id = chain_id
        return chain_id

    async def check_health(self, *, context: ProviderRequestContext) -> str:
        await self.verify_chain_id(context=context)
        return "ok"

    async def probe_health(self, *, context: ProviderRequestContext) -> Mapping[str, object]:
        status = EvmRpcHealthStatus.PASS
        error_class: str | None = None
        try:
            chain_id = await self.verify_chain_id(context=context)
        except ProviderRateLimitedError as exc:
            chain_id = None
            status = EvmRpcHealthStatus.RATE_LIMITED
            error_class = type(exc).__name__
        except ProviderAuthenticationError as exc:
            chain_id = None
            status = EvmRpcHealthStatus.AUTH_FAILED
            error_class = type(exc).__name__
        except (ProviderTimeoutError, ProviderUnavailableError) as exc:
            chain_id = None
            status = EvmRpcHealthStatus.BLOCKED_EXTERNAL
            error_class = type(exc).__name__
        except ProviderError as exc:
            chain_id = None
            status = EvmRpcHealthStatus.DEGRADED
            error_class = type(exc).__name__
        return {
            "chain": self.chain.value,
            "provider": self.provider_name,
            "chain_id": chain_id,
            "expected_chain_id": self._expected_chain_id,
            "status": status.value,
            "error_class": error_class,
        }

    async def fetch_balance(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> Observation:
        normalized_address = require_chain_address(address, self.chain, "address")
        result = await self._rpc(
            "eth_getBalance",
            (normalized_address, "latest"),
            context=context,
        )
        balance_wei = _hex_int(result, "balance")
        observed_at = ensure_utc(self._clock(), "observed_at")
        return Observation(
            kind="onchain.evm_balance",
            provenance=self._provenance(
                f"eth_getBalance:{normalized_address}", observed_at, result
            ),
            occurred_at=None,
            observed_at=observed_at,
            ingested_at=observed_at,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "chain": self.chain.value,
                "address": normalized_address,
                "balance_wei": balance_wei,
            },
        )

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        request_chain = normalize_chain(request.chain or self.chain)
        if request_chain is not self.chain:
            raise ValueError("request must use the same chain")
        if request.token is not None and normalize_chain(request.token.chain) is not self.chain:
            raise ValueError("token and provider must use the same chain")
        if request.signature is not None:
            raise CapabilityUnavailableError(
                "EVM standard adapter exposes account reads only; transaction history "
                "is not configured"
            )
        address = request.address or (
            request.token.address if request.token is not None else None
        )
        if address is None:
            raise ValueError("token or address is required")
        return (await self.fetch_balance(address, context=request.context),)


__all__ = [
    "EVM_CHAIN_IDS",
    "EVM_CHAIN_ID_BY_NAME",
    "EVM_RPC_PARSER_VERSION",
    "EvmRpcAdapter",
    "EvmRpcHealthStatus",
]
