"""Optional Blockscout enrichment; never used as the real-time trade source."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from types import TracebackType
from urllib.parse import urlsplit

import httpx

from memeradar_application.provider_contracts import (
    OnChainPort,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import Chain, Observation, Provenance, QualityState, normalize_chain
from memeradar_domain.common import ensure_utc, require_text
from memeradar_domain.identities import require_evm_address

from .transport import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
)

Clock = Callable[[], datetime]
BLOCKSCOUT_PARSER_VERSION = "blockscout-v2"


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


class BlockscoutAdapter(OnChainPort):
    """Bounded v2 explorer reads for metadata, transactions and token transfers."""

    capabilities = frozenset(
        {"contract_metadata", "transaction_history", "token_transfers", "on_chain"}
    )

    def __init__(
        self,
        chain: Chain | str,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        normalized_chain = normalize_chain(chain)
        if not normalized_chain.is_evm:
            raise ValueError("Blockscout requires an EVM chain")
        normalized_url = require_text(base_url, "base_url", max_length=512).rstrip("/")
        parsed = urlsplit(normalized_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("base_url must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("base_url must not contain credentials or fragments")
        self.chain = normalized_chain
        self.provider_name = f"blockscout:{normalized_chain.value}"
        self._base_url = normalized_url
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=self.provider_name)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def __aenter__(self) -> BlockscoutAdapter:
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

    def _timeout_for(self, context: ProviderRequestContext) -> float:
        if context.deadline_at is None:
            return self._transport.timeouts.overall_seconds
        remaining = (
            ensure_utc(context.deadline_at, "deadline_at") - ensure_utc(self._clock(), "now")
        ).total_seconds()
        if remaining <= 0:
            raise ProviderTimeoutError("provider request deadline expired")
        return min(remaining, self._transport.timeouts.overall_seconds)

    async def _get(
        self,
        path: str,
        *,
        params: Mapping[str, object] | None,
        context: ProviderRequestContext,
    ) -> Mapping[str, object]:
        headers = {"accept": "application/json", "x-correlation-id": context.correlation_id}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        async def operation() -> object:
            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=(
                        None
                        if params is None
                        else {key: str(value) for key, value in params.items()}
                    ),
                    headers=headers,
                    timeout=self._transport.timeouts.overall_seconds,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError("provider request timed out") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError("provider transport failed") from exc
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                raise ProviderRateLimitedError()
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            if not isinstance(payload, Mapping):
                raise ProviderSchemaError("Blockscout response must be an object")
            return dict(payload)

        raw = await self._transport.execute(operation, timeout_seconds=self._timeout_for(context))
        if not isinstance(raw, Mapping):
            raise ProviderSchemaError("Blockscout response was invalid")
        return raw

    async def fetch_contract_metadata(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> Mapping[str, object]:
        normalized = require_evm_address(address, "address")
        return await self._get(f"/api/v2/addresses/{normalized}", params=None, context=context)

    async def fetch_transactions(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> Mapping[str, object]:
        normalized = require_evm_address(address, "address")
        return await self._get(
            f"/api/v2/addresses/{normalized}/transactions",
            params=None,
            context=context,
        )

    async def fetch_token_transfers(
        self,
        address: str,
        *,
        context: ProviderRequestContext,
    ) -> Mapping[str, object]:
        normalized = require_evm_address(address, "address")
        return await self._get(
            "/api",
            params={"module": "account", "action": "tokentx", "address": normalized},
            context=context,
        )

    async def enrich(self, request: OnChainRequest) -> Sequence[Observation]:
        if not isinstance(request, OnChainRequest):
            raise TypeError("request must be an OnChainRequest")
        if normalize_chain(request.chain or self.chain) is not self.chain:
            raise ValueError("request chain must match Blockscout chain")
        address = request.address or (request.token.address if request.token is not None else None)
        if address is None:
            raise ValueError("address or token is required")
        metadata = await self.fetch_contract_metadata(address, context=request.context)
        observed_at = ensure_utc(self._clock(), "observed_at")
        return (
            Observation(
                kind="onchain.blockscout_metadata",
                provenance=Provenance(
                    provider=self.provider_name,
                    source_id=f"address:{address}",
                    observed_at=observed_at,
                    parser_version=BLOCKSCOUT_PARSER_VERSION,
                    raw_payload_hash=_payload_hash(metadata),
                ),
                occurred_at=None,
                observed_at=observed_at,
                ingested_at=observed_at,
                quality_state=QualityState.FRESH,
                normalized_payload={
                    "chain": self.chain.value,
                    "address": address,
                    "source": "blockscout",
                    "verified_source": metadata.get("is_verified"),
                    "creator_address": metadata.get("creator_address_hash"),
                    "creation_transaction": metadata.get("creation_transaction_hash"),
                    "metadata": dict(metadata),
                    "collection_mode": "ENRICHMENT",
                },
            ),
        )


__all__ = ["BLOCKSCOUT_PARSER_VERSION", "BlockscoutAdapter"]
