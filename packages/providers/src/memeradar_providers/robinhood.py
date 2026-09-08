"""Robinhood Chain low-latency read-only seams."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Observation, Provenance, QualityState, require_evm_address
from memeradar_domain.common import ensure_utc, require_text

from .smart_money_stream import (
    ExternalWalletEventStreamAdapter,
    ExternalWalletStreamPolicy,
    SourceFactory,
)

ROBINHOOD_CHAIN_ID = 4663
ROBINHOOD_SEQUENCER_URL = "wss://feed.mainnet.chain.robinhood.com"


class RobinhoodSequencerAdapter(ExternalWalletEventStreamAdapter):
    """Use the sequencer feed for wallet events and retain bounded RPC fallback."""

    def __init__(
        self,
        source_factory: SourceFactory,
        *,
        fallback: Callable[[ProviderRequestContext], Sequence[object] | Awaitable[Sequence[object]]]
        | None = None,
        policy: ExternalWalletStreamPolicy | None = None,
        sleeper: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if sleeper is None:
            super().__init__(
                "robinhood-sequencer",
                "robinhood",
                source_factory,
                fallback=fallback,
                policy=policy,
                source_layer="SEQUENCER",
            )
        else:
            super().__init__(
                "robinhood-sequencer",
                "robinhood",
                source_factory,
                fallback=fallback,
                policy=policy,
                sleeper=sleeper,
                source_layer="SEQUENCER",
            )


@dataclass(frozen=True, slots=True)
class VerifiedLaunchpadContract:
    name: str
    contract_address: str
    selectors: tuple[str, ...]
    verification_source: str
    verified_at: datetime
    parser_version: str = "robinhood-launchpad-v1"
    chain_id: int = ROBINHOOD_CHAIN_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, "name", max_length=64).lower())
        object.__setattr__(
            self, "contract_address", require_evm_address(self.contract_address, "contract_address")
        )
        selectors = tuple(
            require_text(value, "selector", max_length=16).lower() for value in self.selectors
        )
        if not selectors:
            raise ValueError("selectors must not be empty")
        object.__setattr__(self, "selectors", selectors)
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )
        object.__setattr__(
            self,
            "verification_source",
            require_text(self.verification_source, "verification_source", max_length=512),
        )
        if self.chain_id != ROBINHOOD_CHAIN_ID:
            raise ValueError("verified launchpad contract must use Robinhood chain id 4663")
        object.__setattr__(self, "verified_at", ensure_utc(self.verified_at, "verified_at"))


# No NOXA/Odyssey entry is included without independently verified metadata.
ROBINHOOD_VERIFIED_LAUNCHPADS: tuple[VerifiedLaunchpadContract, ...] = ()


class RobinhoodLaunchpadDecoder:
    """Decode only identities supplied from independently verified contracts."""

    def __init__(self, contracts: Sequence[VerifiedLaunchpadContract] = ()) -> None:
        self._contracts = tuple(contracts)

    @staticmethod
    def _hash(value: Mapping[str, object]) -> str:
        return (
            "sha256:"
            + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
        )

    def decode(self, message: object, context: ProviderRequestContext) -> Observation:
        if not isinstance(message, Mapping):
            raise ValueError("launchpad message must be a mapping")
        observed = ensure_utc(context.requested_at, "observed_at")
        contract = require_evm_address(str(message.get("contract_address", "")), "contract_address")
        selector = require_text(str(message.get("selector", "")), "selector", max_length=16).lower()
        identity = next(
            (
                item
                for item in self._contracts
                if item.chain_id == ROBINHOOD_CHAIN_ID
                and item.contract_address == contract
                and selector in item.selectors
            ),
            None,
        )
        source = require_text(
            str(message.get("event_id", message.get("tx_hash", ""))), "event_id", max_length=256
        )
        payload = {
            "chain": "robinhood",
            "contract_address": contract,
            "selector": selector,
            "event_type": message.get("event_type", "launch"),
            "token_address": message.get("token_address"),
            "creator_address": message.get("creator_address"),
            "source_id": f"robinhood:{source}",
        }
        quality = QualityState.FRESH if identity is not None else QualityState.UNKNOWN
        if identity is None:
            payload["reason_codes"] = ("UNVERIFIED_LAUNCHPAD_IDENTITY",)
            parser_version = "robinhood-launchpad-unknown-v1"
        else:
            payload["launchpad"] = identity.name
            payload["verification_source"] = identity.verification_source
            payload["verified_at"] = identity.verified_at.isoformat()
            payload["chain_id"] = identity.chain_id
            parser_version = identity.parser_version
        return Observation(
            kind="chain.launchpad",
            provenance=Provenance(
                provider="robinhood-sequencer",
                source_id=f"robinhood:{source}",
                observed_at=observed,
                parser_version=parser_version,
                raw_payload_hash=self._hash(dict(message)),
            ),
            occurred_at=observed,
            observed_at=observed,
            ingested_at=observed,
            quality_state=quality,
            normalized_payload=payload,
        )


__all__ = [
    "ROBINHOOD_CHAIN_ID",
    "ROBINHOOD_SEQUENCER_URL",
    "ROBINHOOD_VERIFIED_LAUNCHPADS",
    "RobinhoodLaunchpadDecoder",
    "RobinhoodSequencerAdapter",
    "VerifiedLaunchpadContract",
]
