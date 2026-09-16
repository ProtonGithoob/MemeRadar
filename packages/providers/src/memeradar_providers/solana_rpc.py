"""Provider-independent standard Solana JSON-RPC adapter.

This module deliberately implements only standard Solana RPC methods. Helius
DAS/enhanced methods belong to the Helius adapter and are never inferred from
an account or transaction response here.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from urllib.parse import parse_qsl, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    OnChainPort,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, Provenance, QualityState
from memeradar_domain.common import ensure_utc, require_text
from memeradar_domain.identities import require_solana_address

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

SOLANA_RPC_PROVIDER = "solana-public-rpc"
SOLANA_RPC_PARSER_VERSION = "solana-rpc-v1"
SOLANA_CHAIN = "solana"
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "token",
}
_MISSING = object()


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"provider {field} response was invalid")
    return value


def _nonnegative_int(value: object, field: str) -> int | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderSchemaError(f"invalid {field} value")
    return value


def _timestamp(value: object, field: str) -> datetime | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ProviderSchemaError(f"invalid {field} value")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ProviderSchemaError(f"invalid {field} value")
    try:
        return datetime.fromtimestamp(numeric, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ProviderSchemaError(f"invalid {field} value") from exc


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"


def _address_keys(value: object) -> tuple[str, ...]:
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError("transaction account keys were invalid")
    keys: list[str] = []
    for item in value[:256]:
        candidate = item.get("pubkey", _MISSING) if isinstance(item, Mapping) else item
        if not isinstance(candidate, str):
            raise ProviderSchemaError("transaction account key was invalid")
        try:
            keys.append(require_solana_address(candidate, "account_key"))
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("transaction account key was invalid") from exc
    return tuple(keys)


class SolanaRpcAdapter(OnChainPort):
    """Read-only standard Solana JSON-RPC with bounded transport policy."""

    provider_name = SOLANA_RPC_PROVIDER
    capabilities = frozenset({"chain_rpc", "on_chain", "transaction_history"})

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = SOLANA_RPC_PARSER_VERSION,
        max_concurrency: int = 4,
    ) -> None:
        self._endpoint = self._validate_endpoint(endpoint)
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")
        if not 1 <= max_concurrency <= 32:
            raise ValueError("max_concurrency must be between 1 and 32")
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=SOLANA_RPC_PROVIDER)
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
            f"SolanaRpcAdapter(endpoint={self._endpoint!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> SolanaRpcAdapter:
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
        """Return safe rate-limit metadata from the latest response."""

        return self._last_rate_limit

    def _now_pair(self) -> tuple[datetime, datetime]:
        now = ensure_utc(self._clock(), "observed_at")
        return now, now

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
    def _header_float(headers: httpx.Headers, name: str) -> float | None:
        value = headers.get(name)
        if value is None:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) and parsed >= 0 else None

    @classmethod
    def _rate_limit_snapshot(cls, headers: httpx.Headers) -> RateLimitSnapshot | None:
        def nonnegative_int(name: str) -> int | None:
            value = headers.get(name)
            if value is None:
                return None
            try:
                parsed = int(value)
            except ValueError:
                return None
            return parsed if parsed >= 0 else None

        limit = nonnegative_int("x-ratelimit-limit")
        remaining = nonnegative_int("x-ratelimit-remaining")
        reset_epoch = cls._header_float(headers, "x-ratelimit-reset")
        reset_at: datetime | None = None
        if reset_epoch is not None:
            try:
                reset_at = datetime.fromtimestamp(reset_epoch, UTC)
            except (OverflowError, OSError, ValueError):
                reset_at = None
        retry_after = cls._header_float(headers, "retry-after")
        if retry_after is not None and retry_after > 86_400:
            retry_after = None
        if limit is None and remaining is None and reset_at is None and retry_after is None:
            return None
        if limit is not None and remaining is not None and remaining > limit:
            remaining = limit
        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
        )

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
                raise ProviderRateLimitedError(self._header_float(response.headers, "retry-after"))
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
            provider=SOLANA_RPC_PROVIDER,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=self._parser_version,
            raw_payload_hash=_payload_hash(result),
        )

    async def check_health(self, *, context: ProviderRequestContext) -> str:
        result = await self._rpc("getHealth", (), context=context)
        if not isinstance(result, str) or result.strip().lower() != "ok":
            raise ProviderSchemaError("provider health response was invalid")
        return "ok"

    async def fetch_account(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> Observation:
        normalized_address = require_solana_address(address, "address")
        result = await self._rpc(
            "getAccountInfo",
            (normalized_address, {"encoding": "jsonParsed"}),
            context=context,
        )
        observed_at, ingested_at = self._now_pair()
        result_mapping = _mapping(result, "account")
        value = result_mapping.get("value")
        quality = QualityState.UNKNOWN
        owner: str | None = None
        lamports: int | None = None
        executable: bool | None = None
        rent_epoch: int | None = None
        data: object = None
        if value is not None:
            value_mapping = _mapping(value, "account value")
            owner_value = value_mapping.get("owner")
            if owner_value is not None:
                if not isinstance(owner_value, str):
                    raise ProviderSchemaError("account owner was invalid")
                try:
                    owner = require_solana_address(owner_value, "account owner")
                except (TypeError, ValueError) as exc:
                    raise ProviderSchemaError("account owner was invalid") from exc
            lamports = _nonnegative_int(value_mapping.get("lamports", _MISSING), "lamports")
            executable_value = value_mapping.get("executable", _MISSING)
            if executable_value is not _MISSING and not isinstance(executable_value, bool):
                raise ProviderSchemaError("account executable flag was invalid")
            executable = None if executable_value is _MISSING else cast(bool, executable_value)
            rent_epoch = _nonnegative_int(value_mapping.get("rentEpoch", _MISSING), "rentEpoch")
            data = value_mapping.get("data")
            quality = (
                QualityState.FRESH
                if owner is not None and lamports is not None
                else QualityState.UNKNOWN
            )
        provenance = self._provenance(
            f"getAccountInfo:{normalized_address}",
            observed_at,
            result,
        )
        return Observation(
            kind="onchain.account_info",
            provenance=provenance,
            occurred_at=None,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=quality,
            normalized_payload={
                "address": normalized_address,
                "owner": owner,
                "lamports": lamports,
                "executable": executable,
                "rent_epoch": rent_epoch,
                "data": data,
                "collection_mode": "PRODUCTION",
            },
        )

    async def fetch_transaction(
        self,
        signature: str,
        *,
        context: ProviderRequestContext,
    ) -> Observation:
        normalized_signature = require_text(signature, "signature", max_length=128)
        result = await self._rpc(
            "getTransaction",
            (
                normalized_signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
            ),
            context=context,
        )
        observed_at, ingested_at = self._now_pair()
        if result is None:
            return Observation(
                kind="onchain.transaction",
                provenance=self._provenance(
                    f"getTransaction:{normalized_signature}",
                    observed_at,
                    result,
                ),
                occurred_at=None,
                observed_at=observed_at,
                ingested_at=ingested_at,
                quality_state=QualityState.UNKNOWN,
                normalized_payload={
                    "signature": normalized_signature,
                    "slot": None,
                    "block_time": None,
                    "success": None,
                    "account_keys": (),
                    "collection_mode": "PRODUCTION",
                },
            )
        result_mapping = _mapping(result, "transaction")
        slot = _nonnegative_int(result_mapping.get("slot", _MISSING), "slot")
        block_time = _timestamp(result_mapping.get("blockTime", _MISSING), "blockTime")
        transaction = _mapping(result_mapping.get("transaction", _MISSING), "transaction")
        message = _mapping(transaction.get("message", _MISSING), "transaction message")
        account_keys = _address_keys(message.get("accountKeys", _MISSING))
        meta = result_mapping.get("meta")
        success: bool | None = None
        if meta is not None:
            meta_mapping = _mapping(meta, "transaction metadata")
            if "err" in meta_mapping:
                success = meta_mapping["err"] is None
        quality = (
            QualityState.FRESH
            if slot is not None and block_time is not None and account_keys
            else QualityState.UNKNOWN
        )
        provenance = self._provenance(
            f"getTransaction:{normalized_signature}",
            observed_at,
            result,
        )
        return Observation(
            kind="onchain.transaction",
            provenance=provenance,
            occurred_at=block_time,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=quality,
            normalized_payload={
                "signature": normalized_signature,
                "slot": slot,
                "block_time": None if block_time is None else block_time.isoformat(),
                "success": success,
                "account_keys": account_keys,
                "collection_mode": "PRODUCTION",
            },
        )

    async def fetch_signatures_for_address(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
        limit: int = 100,
    ) -> Observation:
        normalized_address = require_solana_address(address, "address")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        result = await self._rpc(
            "getSignaturesForAddress",
            (normalized_address, {"limit": limit, "commitment": "finalized"}),
            context=context,
        )
        if not isinstance(result, Sequence) or isinstance(result, str | bytes | bytearray):
            raise ProviderSchemaError("address signatures response was invalid")
        entries: list[dict[str, object]] = []
        for item in result[:1000]:
            mapping = _mapping(item, "address signature")
            signature = mapping.get("signature")
            if not isinstance(signature, str) or not signature.strip():
                raise ProviderSchemaError("address signature identity was invalid")
            entries.append(
                {
                    "signature": signature,
                    "slot": _nonnegative_int(mapping.get("slot", _MISSING), "slot"),
                    "block_time": _timestamp(mapping.get("blockTime", _MISSING), "blockTime"),
                    "confirmation_status": mapping.get("confirmationStatus"),
                    "err": mapping.get("err"),
                }
            )
        observed_at, ingested_at = self._now_pair()
        return Observation(
            kind="onchain.address_signatures",
            provenance=self._provenance(
                f"getSignaturesForAddress:{normalized_address}",
                observed_at,
                result,
            ),
            occurred_at=None,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "address": normalized_address,
                "signatures": tuple(entries),
                "collection_mode": "PRODUCTION",
            },
        )

    async def fetch_blocks(
        self,
        start_slot: int,
        end_slot: int,
        *,
        context: ProviderRequestContext,
    ) -> Observation:
        if (
            not isinstance(start_slot, int)
            or isinstance(start_slot, bool)
            or not isinstance(end_slot, int)
            or isinstance(end_slot, bool)
            or start_slot < 0
            or end_slot < start_slot
            or end_slot - start_slot > 500
        ):
            raise ValueError("block range must be ordered and contain at most 501 slots")
        result = await self._rpc(
            "getBlocks",
            (start_slot, end_slot, {"commitment": "finalized"}),
            context=context,
        )
        if not isinstance(result, Sequence) or isinstance(result, str | bytes | bytearray):
            raise ProviderSchemaError("blocks response was invalid")
        slots = tuple(_nonnegative_int(value, "slot") for value in result)
        if any(value is None for value in slots):
            raise ProviderSchemaError("blocks response contained an invalid slot")
        observed_at, ingested_at = self._now_pair()
        return Observation(
            kind="onchain.blocks",
            provenance=self._provenance(f"getBlocks:{start_slot}:{end_slot}", observed_at, result),
            occurred_at=None,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "start_slot": start_slot,
                "end_slot": end_slot,
                "slots": tuple(value for value in slots if value is not None),
                "collection_mode": "PRODUCTION",
            },
        )

    async def fetch_block(
        self,
        slot: int,
        *,
        context: ProviderRequestContext,
    ) -> Observation:
        if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
            raise ValueError("slot must be a non-negative integer")
        result = await self._rpc(
            "getBlock",
            (
                slot,
                {
                    "commitment": "finalized",
                    "encoding": "jsonParsed",
                    "transactionDetails": "signatures",
                    "rewards": False,
                    "maxSupportedTransactionVersion": 0,
                },
            ),
            context=context,
        )
        observed_at, ingested_at = self._now_pair()
        if result is None:
            return Observation(
                kind="onchain.block",
                provenance=self._provenance(f"getBlock:{slot}", observed_at, result),
                occurred_at=None,
                observed_at=observed_at,
                ingested_at=ingested_at,
                quality_state=QualityState.UNKNOWN,
                normalized_payload={
                    "slot": slot,
                    "blockhash": None,
                    "previous_blockhash": None,
                    "block_time": None,
                    "signatures": (),
                    "collection_mode": "PRODUCTION",
                },
            )
        result_mapping = _mapping(result, "block")
        block_time = _timestamp(result_mapping.get("blockTime", _MISSING), "blockTime")
        return Observation(
            kind="onchain.block",
            provenance=self._provenance(f"getBlock:{slot}", observed_at, result),
            occurred_at=block_time,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=QualityState.FRESH if block_time is not None else QualityState.UNKNOWN,
            normalized_payload={
                "slot": slot,
                "blockhash": result_mapping.get("blockhash"),
                "previous_blockhash": result_mapping.get("previousBlockhash"),
                "block_time": None if block_time is None else block_time.isoformat(),
                "signatures": result_mapping.get("signatures", ()),
                "collection_mode": "PRODUCTION",
            },
        )

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        if request.token is not None:
            raise CapabilityUnavailableError(
                "standard Solana RPC does not provide enhanced asset metadata"
            )
        if request.signature is not None:
            return (await self.fetch_transaction(request.signature, context=request.context),)
        if request.address is not None:
            return (await self.fetch_account(request.address, context=request.context),)
        raise ValueError("OnChainRequest has no supported standard RPC read target")


__all__ = [
    "SOLANA_CHAIN",
    "SOLANA_RPC_PARSER_VERSION",
    "SOLANA_RPC_PROVIDER",
    "SolanaRpcAdapter",
]
