"""Measurement-only Solana KOL/side-wallet cluster evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from memeradar_domain import (
    Freshness,
    Observation,
    Provenance,
    QualityState,
    TokenIdentity,
    normalize_chain,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)

KOL_BUNDLE_VERSION = "kol-bundle-cluster-v1"


def _value(payload: Mapping[str, object], *names: str) -> object | None:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value
    return None


def _decimal(value: object | None, field: str) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = to_decimal(value, field)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _text(value: object | None) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _bool(value: object | None) -> bool:
    return value is True or (isinstance(value, str) and value.lower() in {"true", "1", "yes"})


def _worst(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    order = {
        QualityState.FRESH: 0,
        QualityState.STALE: 1,
        QualityState.UNKNOWN: 2,
        QualityState.CONFLICTED: 3,
        QualityState.INVALID: 4,
    }
    return max(states, key=order.__getitem__)


@dataclass(frozen=True, slots=True)
class KOLBundleClusterEvidence:
    """Correlated caller/cluster evidence; it never asserts wallet ownership."""

    token: TokenIdentity
    caller_wallet: str
    as_of: datetime
    expires_at: datetime
    visible_caller_position: Decimal | None
    cluster_adjusted_accumulation: Decimal | None
    probable_related_side_wallet_count: int | None
    related_side_wallets: tuple[str, ...]
    bundle_count: int | None
    temporal_proximity_seconds: Decimal | None
    confidence: Decimal
    quality_state: QualityState
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    config_hash: str
    ownership_asserted: bool = False
    version: str = KOL_BUNDLE_VERSION

    def __post_init__(self) -> None:
        if (
            not isinstance(self.token, TokenIdentity)
            or normalize_chain(self.token.chain).value != "solana"
        ):
            raise TypeError("token must be a Solana TokenIdentity")
        object.__setattr__(
            self, "caller_wallet", require_solana_address(self.caller_wallet, "caller_wallet")
        )
        as_of, expires_at = (
            ensure_utc(self.as_of, "as_of"),
            ensure_utc(self.expires_at, "expires_at"),
        )
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field in (
            "visible_caller_position",
            "cluster_adjusted_accumulation",
            "temporal_proximity_seconds",
        ):
            value = getattr(self, field)
            if value is not None:
                value = to_decimal(value, field)
                if value < 0:
                    raise ValueError(f"{field} must not be negative")
                object.__setattr__(self, field, value)
        if self.probable_related_side_wallet_count is not None and (
            not isinstance(self.probable_related_side_wallet_count, int)
            or self.probable_related_side_wallet_count < 0
        ):
            raise ValueError("probable_related_side_wallet_count must be non-negative or None")
        object.__setattr__(
            self,
            "related_side_wallets",
            tuple(
                sorted(
                    {
                        require_solana_address(value, "side wallet")
                        for value in self.related_side_wallets
                    }
                )
            ),
        )
        if not isinstance(self.bundle_count, int | type(None)) or (
            self.bundle_count is not None and self.bundle_count < 0
        ):
            raise ValueError("bundle_count must be non-negative or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if any(not isinstance(value, Provenance) for value in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if self.ownership_asserted:
            raise ValueError("correlation evidence cannot assert wallet ownership")

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return self.reason_codes

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


class KOLBundleClusterAnalyzer:
    """Join explicit bundle, adjacency, funding and same-token evidence."""

    def __init__(self, *, evidence_ttl: timedelta = timedelta(minutes=5)) -> None:
        if evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        self._ttl = evidence_ttl

    def analyze(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        caller_wallet: str,
        now: datetime,
        config_hash: str,
    ) -> KOLBundleClusterEvidence:
        if not isinstance(token, TokenIdentity) or normalize_chain(token.chain).value != "solana":
            raise TypeError("token must be a Solana TokenIdentity")
        caller = require_solana_address(caller_wallet, "caller_wallet")
        checked_at = ensure_utc(now, "now")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        matched: list[Observation] = []
        seen: set[str] = set()
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if observation.provenance.source_id in seen or observation.occurred_at is None:
                continue
            payload = observation.normalized_payload
            address = _text(_value(payload, "mint_address", "token_address", "mint", "token"))
            wallet = _text(_value(payload, "wallet_address", "wallet", "trader", "maker"))
            if address != token.address or wallet is None:
                continue
            try:
                require_solana_address(wallet, "wallet_address")
            except ValueError:
                continue
            if observation.occurred_at > checked_at or observation.observed_at > checked_at:
                continue
            seen.add(observation.provenance.source_id)
            matched.append(observation)

        caller_rows = [
            item
            for item in matched
            if _text(_value(item.normalized_payload, "wallet_address", "wallet", "trader", "maker"))
            == caller
        ]
        caller_at = caller_rows[0].occurred_at if caller_rows else None
        caller_bundles = {
            _text(_value(item.normalized_payload, "bundle_id", "bundle", "jito_bundle_id"))
            for item in caller_rows
        }
        caller_slots = {
            _value(item.normalized_payload, "slot", "block_number", "block") for item in caller_rows
        }
        caller_funders = {
            _text(_value(item.normalized_payload, "funder", "funding_wallet", "source_wallet"))
            for item in caller_rows
        }
        related: set[str] = set()
        accumulation = Decimal("0")
        caller_position = Decimal("0")
        temporal_deltas: list[Decimal] = []
        bundles: set[str] = set()
        reasons: list[str] = ["KOL_BUNDLE_CLUSTER_EVALUATED"]
        dimensions: set[str] = set()
        for item in matched:
            payload = item.normalized_payload
            wallet = _text(_value(payload, "wallet_address", "wallet", "trader", "maker"))
            quantity = _decimal(
                _value(payload, "quantity", "amount", "token_amount", "base_amount"), "quantity"
            ) or Decimal("0")
            action = (_text(_value(payload, "action", "side", "type")) or "buy").lower()
            signed = quantity if action not in {"sell", "sold"} else -quantity
            if wallet == caller:
                caller_position += signed
            bundle = _text(_value(payload, "bundle_id", "bundle", "jito_bundle_id"))
            if bundle is not None:
                bundles.add(bundle)
            jito = _bool(_value(payload, "jito_bundle", "jito", "bundle_member"))
            slot = _value(payload, "slot", "block_number", "block")
            adjacent = _bool(_value(payload, "adjacent", "block_adjacent", "transaction_adjacent"))
            funder = _text(_value(payload, "funder", "funding_wallet", "source_wallet"))
            graph = _bool(_value(payload, "graph_related", "funding_related", "same_funder"))
            same_bundle = bundle is not None and bundle in caller_bundles
            same_slot = slot is not None and slot in caller_slots
            if (
                wallet != caller
                and wallet is not None
                and (
                    jito
                    or same_bundle
                    or same_slot
                    or adjacent
                    or graph
                    or (funder is not None and funder in caller_funders)
                )
            ):
                related.add(wallet)
                accumulation += signed
                if item.occurred_at is not None and caller_at is not None:
                    temporal_deltas.append(
                        abs(Decimal(str((item.occurred_at - caller_at).total_seconds())))
                    )
            if jito:
                dimensions.add("jito")
            if same_slot or adjacent:
                dimensions.add("adjacency")
            if graph or (funder is not None and funder in caller_funders):
                dimensions.add("funding")
        if caller_rows:
            accumulation += caller_position
            dimensions.add("caller_position")
        if related:
            dimensions.add("side_wallet")
        if bundles:
            dimensions.add("bundle")
            reasons.append(
                "JITO_BUNDLE_EVIDENCE" if "jito" in dimensions else "BUNDLE_MEMBERSHIP_EVIDENCE"
            )
        if "adjacency" in dimensions:
            reasons.append("TRANSACTION_BLOCK_ADJACENCY_EVIDENCE")
        if "funding" in dimensions:
            reasons.append("FUNDING_GRAPH_EVIDENCE")
        if related:
            reasons.append("RELATED_SIDE_WALLETS_CORRELATED")
        if not matched:
            reasons.append("KOL_BUNDLE_EVIDENCE_MISSING")
        quality = _worst(tuple(item.quality_state for item in matched))
        if matched and not dimensions.intersection(
            {"bundle", "adjacency", "funding", "side_wallet"}
        ):
            quality = QualityState.UNKNOWN
            reasons.append("WEAK_CORRELATION_ONLY")
        confidence = (
            Decimal("0")
            if not matched
            else min(Decimal("0.95"), Decimal("0.10") * Decimal(len(dimensions)))
        )
        if quality is not QualityState.FRESH:
            confidence = Decimal("0")
        return KOLBundleClusterEvidence(
            token=token,
            caller_wallet=caller,
            as_of=checked_at,
            expires_at=checked_at + self._ttl,
            visible_caller_position=max(caller_position, Decimal("0")) if caller_rows else None,
            cluster_adjusted_accumulation=max(accumulation, Decimal("0")) if matched else None,
            probable_related_side_wallet_count=len(related) if matched else None,
            related_side_wallets=tuple(related),
            bundle_count=len(bundles) if matched else None,
            temporal_proximity_seconds=min(temporal_deltas) if temporal_deltas else None,
            confidence=confidence,
            quality_state=quality,
            provenance=tuple(item.provenance for item in matched),
            evidence_refs=tuple(item.provenance.source_id for item in matched),
            reason_codes=tuple(dict.fromkeys(reasons)),
            config_hash=config_hash,
        )


__all__ = ["KOL_BUNDLE_VERSION", "KOLBundleClusterEvidence", "KOLBundleClusterAnalyzer"]
