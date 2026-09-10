"""Robinhood Chain low-latency read-only seams."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Observation, Provenance, QualityState, require_evm_address
from memeradar_domain.common import ensure_utc, require_text

from .smart_money_stream import (
    ExternalWalletEventStreamAdapter,
    ExternalWalletStreamPolicy,
    SourceFactory,
)
from .transport import ProviderSchemaError

ROBINHOOD_CHAIN_ID = 4663
ROBINHOOD_SEQUENCER_URL = "wss://feed.mainnet.chain.robinhood.com"


class RobinhoodReceiptRpc(Protocol):
    async def fetch_transaction_receipt(
        self,
        transaction_hash: str,
        *,
        context: ProviderRequestContext,
    ) -> Mapping[str, object] | None: ...


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
            require_text(value, "selector", max_length=128).lower() for value in self.selectors
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

    @staticmethod
    def _transaction_hash(message: Mapping[str, object]) -> object:
        return message.get("tx_hash", message.get("transaction_hash"))

    @staticmethod
    def _selector(message: Mapping[str, object]) -> object:
        return message.get("selector", message.get("topic0", message.get("topic")))

    @staticmethod
    def _receipt_reconciliation(
        message: Mapping[str, object],
        receipt: Mapping[str, object],
        *,
        contract: str,
        selector: str,
    ) -> tuple[bool, str, str]:
        tx_hash = RobinhoodLaunchpadDecoder._transaction_hash(message)
        receipt_hash = receipt.get("transactionHash", receipt.get("tx_hash"))
        if not isinstance(tx_hash, str) or not isinstance(receipt_hash, str):
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        if tx_hash.lower() != receipt_hash.lower():
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        chain_id = receipt.get("chainId", receipt.get("chain_id"))
        if chain_id is None:
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        try:
            parsed_chain_id = int(
                str(chain_id), 16 if str(chain_id).lower().startswith("0x") else 10
            )
        except (TypeError, ValueError):
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        if parsed_chain_id != ROBINHOOD_CHAIN_ID:
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        status = str(receipt.get("status", "")).lower()
        if status not in {"0x1", "1", "success"}:
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        logs = receipt.get("logs")
        if not isinstance(logs, Sequence) or isinstance(logs, str | bytes | bytearray):
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        matched_log = False
        for item in logs:
            if not isinstance(item, Mapping):
                continue
            raw_address = item.get("address", item.get("contract_address"))
            if not isinstance(raw_address, str) or raw_address.lower() != contract.lower():
                continue
            raw_selector = item.get("selector")
            topics = item.get("topics")
            topic_selector = (
                topics[0]
                if isinstance(topics, Sequence)
                and not isinstance(topics, str | bytes | bytearray)
                and topics
                else None
            )
            if (
                isinstance(raw_selector, str)
                and raw_selector.lower() == selector
                or isinstance(topic_selector, str)
                and topic_selector.lower() == selector
            ):
                matched_log = True
                break
        if not matched_log:
            return False, "UNKNOWN", "RPC_RECONCILIATION_FAILED"
        raw_finality = receipt.get("finality", receipt.get("commitment"))
        if raw_finality is None:
            return False, "UNKNOWN", "RPC_FINALITY_UNKNOWN"
        finality = str(raw_finality).upper()
        if finality != "FINALIZED":
            return False, finality, "RPC_FINALITY_UNKNOWN"
        return True, finality, ""

    @staticmethod
    def _event_time(
        message: Mapping[str, object], observed: datetime
    ) -> tuple[datetime | None, str]:
        raw = message.get("occurred_at", message.get("event_timestamp"))
        if raw is None:
            return None, "UNKNOWN"
        try:
            if isinstance(raw, datetime):
                occurred = ensure_utc(raw, "occurred_at")
            elif isinstance(raw, int | float) and not isinstance(raw, bool):
                occurred = datetime.fromtimestamp(raw, UTC)
            elif isinstance(raw, str):
                occurred = ensure_utc(
                    datetime.fromisoformat(raw.replace("Z", "+00:00")), "occurred_at"
                )
            else:
                return None, "UNKNOWN"
        except (TypeError, ValueError, OverflowError):
            return None, "UNKNOWN"
        if occurred > observed:
            return None, "UNKNOWN"
        return occurred, "EXACT"

    @staticmethod
    def _canonical_event_id(message: Mapping[str, object], source: str) -> str:
        tx_hash = RobinhoodLaunchpadDecoder._transaction_hash(message)
        if isinstance(tx_hash, str) and tx_hash:
            parts = [tx_hash.lower()]
            has_log_identity = False
            for key in ("log_index", "event_index"):
                if message.get(key) is not None:
                    parts.append(f"{key}={message[key]}")
                    has_log_identity = True
            topic = message.get("topic0", message.get("topic"))
            if topic is not None:
                parts.append(f"topic={str(topic).lower()}")
                has_log_identity = True
            if not has_log_identity:
                event_id = message.get("event_id")
                parts.append(
                    f"event={event_id}"
                    if event_id is not None
                    else f"source={source}"
                )
            return ":".join(parts)
        stable = message.get("canonical_event_id")
        return str(stable) if stable is not None else source

    def decode(
        self,
        message: object,
        context: ProviderRequestContext,
        *,
        canonical_receipt: Mapping[str, object] | None = None,
    ) -> Observation:
        if not isinstance(message, Mapping):
            raise ValueError("launchpad message must be a mapping")
        observed = ensure_utc(context.requested_at, "observed_at")
        occurred, event_time_quality = self._event_time(message, observed)
        contract = require_evm_address(str(message.get("contract_address", "")), "contract_address")
        selector = require_text(
            str(self._selector(message) or ""), "selector", max_length=128
        ).lower()
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
            str(message.get("event_id") or self._transaction_hash(message) or ""),
            "event_id",
            max_length=256,
        )
        source_layer = "RPC_RECONCILIATION" if canonical_receipt is not None else "SEQUENCER"
        payload = {
            "chain": "robinhood",
            "contract_address": contract,
            "selector": selector,
            "event_type": message.get("event_type", "launch"),
            "token_address": message.get("token_address"),
            "creator_address": message.get("creator_address"),
            "event_id": message.get("event_id"),
            "tx_hash": self._transaction_hash(message),
            "canonical_event_id": self._canonical_event_id(message, source),
            "log_index": message.get("log_index"),
            "event_index": message.get("event_index"),
            "topic0": message.get("topic0", message.get("topic")),
            "event_time_quality": event_time_quality,
            "pool_address": message.get("pool_address", message.get("pair_address")),
            "quote_asset": message.get("quote_asset", message.get("quote_mint")),
            "bonding_curve_progress_bps": message.get("bonding_curve_progress_bps"),
            "graduation_threshold_bps": message.get("graduation_threshold_bps"),
            "liquidity_lock_state": message.get("liquidity_lock_state"),
            "source_id": f"robinhood:{source}",
            "source_layer": source_layer,
            "authoritative": False,
            "rpc_reconciled": False,
            "commitment": "UNKNOWN",
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
            if canonical_receipt is None:
                quality = QualityState.UNKNOWN
                payload["reason_codes"] = ("RPC_RECONCILIATION_REQUIRED",)
            else:
                reconciled, commitment, reason = self._receipt_reconciliation(
                    message,
                    canonical_receipt,
                    contract=contract,
                    selector=selector,
                )
                payload["rpc_reconciled"] = reconciled
                payload["commitment"] = commitment
                if reason:
                    quality = QualityState.UNKNOWN
                    payload["reason_codes"] = (reason,)
                else:
                    quality = QualityState.FRESH
                    payload["source_layer"] = "RPC_RECONCILIATION"
                    payload["authoritative"] = True
        if occurred is None:
            payload["time_quality"] = "UNKNOWN"
        return Observation(
            kind="chain.launchpad",
            provenance=Provenance(
                provider=(
                    "evm-public-rpc:robinhood"
                    if canonical_receipt is not None
                    else "robinhood-sequencer"
                ),
                source_id=f"robinhood:{source}",
                observed_at=observed,
                parser_version=parser_version,
                raw_payload_hash=self._hash(dict(message)),
            ),
            occurred_at=occurred,
            observed_at=observed,
            ingested_at=ensure_utc(context.requested_at, "ingested_at"),
            quality_state=quality,
            normalized_payload=payload,
        )


class RobinhoodLaunchpadReconciler:
    """Bounded sequencer-to-canonical-RPC reconciliation for launch evidence."""

    def __init__(self, decoder: RobinhoodLaunchpadDecoder, rpc: RobinhoodReceiptRpc) -> None:
        if not isinstance(decoder, RobinhoodLaunchpadDecoder):
            raise TypeError("decoder must be a RobinhoodLaunchpadDecoder")
        if not callable(getattr(rpc, "fetch_transaction_receipt", None)):
            raise TypeError("rpc must expose fetch_transaction_receipt")
        self.decoder = decoder
        self.rpc: RobinhoodReceiptRpc = rpc

    async def reconcile(
        self,
        message: object,
        context: ProviderRequestContext,
    ) -> Observation:
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        pending = self.decoder.decode(message, context)
        tx_hash = pending.normalized_payload.get("tx_hash")
        if not isinstance(tx_hash, str) or not tx_hash:
            return pending
        reason_codes = pending.normalized_payload.get("reason_codes", ())
        if (
            isinstance(reason_codes, Sequence)
            and not isinstance(reason_codes, str | bytes | bytearray)
            and "UNVERIFIED_LAUNCHPAD_IDENTITY" in reason_codes
        ):
            return pending
        receipt = await self.rpc.fetch_transaction_receipt(tx_hash, context=context)
        if receipt is None:
            return pending
        if not isinstance(receipt, Mapping):
            return self.decoder.decode(message, context, canonical_receipt={})
        verify_chain_id = getattr(self.rpc, "verify_chain_id", None)
        if callable(verify_chain_id):
            try:
                chain_id = await verify_chain_id(context=context)
            except ProviderSchemaError:
                return self.decoder.decode(
                    message,
                    context,
                    canonical_receipt={"transactionHash": tx_hash, "chainId": 0},
                )
            receipt = {**receipt, "chainId": chain_id}
        if receipt.get("finality", receipt.get("commitment")) is None:
            fetch_finality = getattr(self.rpc, "fetch_transaction_finality", None)
            if callable(fetch_finality):
                finality = await fetch_finality(receipt, context=context)
                if finality is not None:
                    receipt = {**receipt, "finality": finality}
        return self.decoder.decode(message, context, canonical_receipt=receipt)

    async def reconcile_and_persist(
        self,
        message: object,
        context: ProviderRequestContext,
        persist: Callable[[Observation], Awaitable[object]],
    ) -> Observation:
        """Reconcile once, then hand the canonical observation to the existing UoW."""

        if not callable(persist):
            raise TypeError("persist must be callable")
        observation = await self.reconcile(message, context)
        await persist(observation)
        return observation


__all__ = [
    "ROBINHOOD_CHAIN_ID",
    "ROBINHOOD_SEQUENCER_URL",
    "ROBINHOOD_VERIFIED_LAUNCHPADS",
    "RobinhoodLaunchpadDecoder",
    "RobinhoodLaunchpadReconciler",
    "RobinhoodSequencerAdapter",
    "VerifiedLaunchpadContract",
]
