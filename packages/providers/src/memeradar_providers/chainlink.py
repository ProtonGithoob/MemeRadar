"""Read-only Chainlink AggregatorV3 evidence for verified Robinhood feeds."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.price_integrity import ReferencePriceEvidence, compare_reference_price
from memeradar_application.provider_contracts import ReferencePricePort, ReferencePriceRequest
from memeradar_domain import Chain, Provenance, normalize_chain, require_chain_address
from memeradar_domain.common import ensure_utc, require_text

from .evm_rpc import EvmRpcAdapter
from .transport import ProviderError

CHAINLINK_ROBINHOOD_VERSION = "chainlink-robinhood-v1"


@dataclass(frozen=True, slots=True)
class ChainlinkFeedConfig:
    feed_address: str
    asset_address: str
    verification_source: str
    verified_at: datetime
    parser_version: str = CHAINLINK_ROBINHOOD_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feed_address",
            require_chain_address(self.feed_address, Chain.ROBINHOOD, "feed_address"),
        )
        object.__setattr__(
            self,
            "asset_address",
            require_chain_address(self.asset_address, Chain.ROBINHOOD, "asset_address"),
        )
        object.__setattr__(
            self,
            "verification_source",
            require_text(self.verification_source, "verification_source", max_length=512),
        )
        object.__setattr__(self, "verified_at", ensure_utc(self.verified_at, "verified_at"))
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )


# Deliberately empty until feed proxy addresses are independently verified.
ROBINHOOD_CHAINLINK_FEEDS: tuple[ChainlinkFeedConfig, ...] = ()


def _hash(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
    )


def _words(value: object) -> tuple[bytes, ...]:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("oracle result was not hexadecimal")
    raw = bytes.fromhex(value[2:])
    if len(raw) < 160 or len(raw) % 32:
        raise ValueError("oracle result had an invalid word count")
    return tuple(raw[index : index + 32] for index in range(0, len(raw), 32))


class ChainlinkReferencePriceAdapter(ReferencePricePort):
    def __init__(
        self,
        rpc: EvmRpcAdapter,
        config: ChainlinkFeedConfig | None,
        *,
        max_oracle_age: timedelta = timedelta(minutes=5),
        deviation_threshold_bps: Decimal = Decimal("500"),
    ) -> None:
        if rpc.chain is not Chain.ROBINHOOD:
            raise ValueError("Chainlink Robinhood adapter requires Robinhood RPC")
        self._rpc = rpc
        self._config = config
        self._max_oracle_age = max_oracle_age
        self._deviation_threshold_bps = deviation_threshold_bps

    def _unknown(self, request: ReferencePriceRequest, reason: str) -> ReferencePriceEvidence:
        now = request.now or request.context.requested_at
        provider = "chainlink-robinhood"
        source_id = f"{provider}:{request.asset_address}:unknown"
        provenance = Provenance(
            provider=provider,
            source_id=source_id,
            observed_at=now,
            parser_version=CHAINLINK_ROBINHOOD_VERSION,
        )
        evidence = compare_reference_price(
            normalize_chain(request.chain).value,
            request.asset_address,
            None,
            request.quote_price,
            now,
            now,
            provenance=(provenance,),
            config_hash=CHAINLINK_ROBINHOOD_VERSION,
            max_oracle_age=self._max_oracle_age,
            deviation_threshold_bps=self._deviation_threshold_bps,
        )
        return replace(evidence, reason_codes=(reason,))

    async def fetch(self, request: ReferencePriceRequest) -> ReferencePriceEvidence:
        if not isinstance(request, ReferencePriceRequest):
            raise TypeError("request must be a ReferencePriceRequest")
        config = self._config
        if config is None or config.asset_address != request.asset_address:
            return self._unknown(request, "REFERENCE_FEED_UNAVAILABLE")
        try:
            decimals_result = await self._rpc.call_contract(
                config.feed_address, "0x313ce567", context=request.context
            )
            decimals = int(str(decimals_result), 16)
            if not 0 <= decimals <= 36:
                raise ValueError("oracle decimals were invalid")
            round_result = await self._rpc.call_contract(
                config.feed_address, "0xfeaf968c", context=request.context
            )
            words = _words(round_result)
            round_id = int.from_bytes(words[0], "big")
            answer = int.from_bytes(words[1], "big", signed=True)
            updated_at = int.from_bytes(words[3], "big")
            answered_in_round = int.from_bytes(words[4], "big")
            if answer <= 0:
                return self._unknown(request, "ORACLE_NON_POSITIVE")
            if updated_at <= 0 or answered_in_round < round_id:
                return self._unknown(request, "ORACLE_ROUND_INVALID")
            oracle_at = datetime.fromtimestamp(updated_at, UTC)
            provenance = Provenance(
                provider="chainlink-robinhood",
                source_id=f"chainlink:{config.feed_address}:round:{round_id}",
                observed_at=request.now or request.context.requested_at,
                parser_version=config.parser_version,
                raw_payload_hash=_hash({"decimals": decimals, "round": round_result}),
            )
            return compare_reference_price(
                normalize_chain(request.chain).value,
                request.asset_address,
                Decimal(answer) / (Decimal(10) ** decimals),
                request.quote_price,
                oracle_at,
                request.now or request.context.requested_at,
                provenance=(provenance,),
                config_hash=CHAINLINK_ROBINHOOD_VERSION,
                max_oracle_age=self._max_oracle_age,
                deviation_threshold_bps=self._deviation_threshold_bps,
            )
        except (ProviderError, TypeError, ValueError, OverflowError):
            return self._unknown(request, "REFERENCE_PROVIDER_FAILURE")


__all__ = [
    "CHAINLINK_ROBINHOOD_VERSION",
    "ChainlinkFeedConfig",
    "ChainlinkReferencePriceAdapter",
    "ROBINHOOD_CHAINLINK_FEEDS",
]
