"""Provider-independent rolling SmartWalletScore calculation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from memeradar_domain import Freshness, Provenance, QualityState, ReasonCode, require_solana_address
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .wallet_tracking import WalletRoundTrip, WalletTier, WalletTrackingSnapshot

_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_QUALITY_CONFIDENCE = {
    QualityState.FRESH: Decimal("1"),
    QualityState.STALE: Decimal("0.5"),
    QualityState.UNKNOWN: Decimal("0.25"),
    QualityState.CONFLICTED: Decimal("0.1"),
    QualityState.INVALID: Decimal("0"),
}


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], values: Sequence[Provenance]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


def _shrink(value: Decimal | None, *, neutral: Decimal, sample_confidence: Decimal) -> Decimal:
    if value is None:
        return neutral
    return neutral + sample_confidence * (value - neutral)


class SmartWalletTier(str, Enum):
    """Reserved alias for callers that want to name score recommendations."""

    CANDIDATE = WalletTier.CANDIDATE.value
    TIER_A = WalletTier.TIER_A.value
    TIER_B = WalletTier.TIER_B.value
    BLOCKED = WalletTier.BLOCKED.value


@dataclass(frozen=True, slots=True)
class SmartWalletScoringPolicy:
    """Versioned bounded policy for rolling wallet-score aggregation."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    rolling_window: timedelta = timedelta(days=30)
    early_entry_max_age: timedelta = timedelta(minutes=10)
    minimum_sample_count: int = 5
    minimum_confidence: Decimal = Decimal("0.70")
    tier_a_minimum_sample_count: int = 20
    tier_a_minimum_confidence: Decimal = Decimal("0.85")
    tier_b_minimum_sample_count: int = 5
    tier_b_minimum_confidence: Decimal = Decimal("0.60")
    prior_sample_count: int = 1
    maximum_manipulation_penalty: Decimal = Decimal("40")
    win_rate_weight: Decimal = Decimal("0.20")
    realized_pnl_weight: Decimal = Decimal("0.20")
    median_return_weight: Decimal = Decimal("0.20")
    early_entry_weight: Decimal = Decimal("0.20")
    rug_avoidance_weight: Decimal = Decimal("0.20")
    version: str = "smart-wallet-v1"

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "rolling_window", "early_entry_max_age"):
            value = getattr(self, field_name)
            if value <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        for field_name, maximum in (
            ("minimum_sample_count", 100_000),
            ("tier_a_minimum_sample_count", 100_000),
            ("tier_b_minimum_sample_count", 100_000),
            ("prior_sample_count", 100_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        for field_name in (
            "minimum_confidence",
            "tier_a_minimum_confidence",
            "tier_b_minimum_confidence",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        penalty = bounded_decimal(
            self.maximum_manipulation_penalty,
            "maximum_manipulation_penalty",
            Decimal("0"),
            Decimal("100"),
        )
        object.__setattr__(self, "maximum_manipulation_penalty", penalty)
        weights = (
            "win_rate_weight",
            "realized_pnl_weight",
            "median_return_weight",
            "early_entry_weight",
            "rug_avoidance_weight",
        )
        normalized_weights = [
            bounded_decimal(
                getattr(self, field_name),
                field_name,
                Decimal("0"),
                Decimal("1"),
            )
            for field_name in weights
        ]
        if sum(normalized_weights, Decimal("0")) != Decimal("1"):
            raise ValueError("score component weights must sum to 1")
        for field_name, value in zip(weights, normalized_weights, strict=True):
            object.__setattr__(self, field_name, value)
        if self.tier_b_minimum_sample_count < self.minimum_sample_count:
            raise ValueError("tier_b_minimum_sample_count must meet minimum_sample_count")
        if self.tier_a_minimum_sample_count < self.tier_b_minimum_sample_count:
            raise ValueError("tier_a_minimum_sample_count must meet tier_b_minimum_sample_count")
        if self.tier_a_minimum_confidence < self.tier_b_minimum_confidence:
            raise ValueError("tier_a_minimum_confidence must meet tier_b_minimum_confidence")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class SmartWalletScore:
    """Explainable wallet score with a non-authorizing execution boundary."""

    wallet_address: str
    label: str
    registry_tier: WalletTier | str
    recommended_tier: WalletTier | str
    as_of: datetime
    expires_at: datetime
    score: Decimal
    confidence: Decimal
    sample_count: int
    known_outcome_count: int
    win_rate: Decimal | None
    realized_pnl: Decimal | None
    median_return: Decimal | None
    early_entry_rate: Decimal | None
    rug_avoidance_rate: Decimal | None
    manipulation_penalty: Decimal
    components: Mapping[str, Decimal]
    penalties: Mapping[str, Decimal]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "smart-wallet-v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "wallet_address",
            require_solana_address(self.wallet_address, "wallet address"),
        )
        object.__setattr__(self, "label", require_text(self.label, "wallet label", max_length=128))
        object.__setattr__(self, "registry_tier", WalletTier(self.registry_tier))
        object.__setattr__(self, "recommended_tier", WalletTier(self.recommended_tier))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        for field_name in ("sample_count", "known_outcome_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.known_outcome_count > self.sample_count:
            raise ValueError("known_outcome_count cannot exceed sample_count")
        for field_name in (
            "win_rate",
            "early_entry_rate",
            "rug_avoidance_rate",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in ("realized_pnl", "median_return"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        object.__setattr__(
            self,
            "manipulation_penalty",
            bounded_decimal(
                self.manipulation_penalty,
                "manipulation_penalty",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        normalized_components: dict[str, Decimal] = {}
        for key, value in self.components.items():
            normalized_key = require_text(key, "component key")
            normalized_components[normalized_key] = bounded_decimal(
                value,
                f"component {normalized_key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(self, "components", MappingProxyType(normalized_components))
        normalized_penalties: dict[str, Decimal] = {}
        for key, value in self.penalties.items():
            normalized_key = require_text(key, "penalty key")
            normalized_penalties[normalized_key] = bounded_decimal(
                value,
                f"penalty {normalized_key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(self, "penalties", MappingProxyType(normalized_penalties))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def tier(self) -> WalletTier:
        return WalletTier(self.recommended_tier)

    @property
    def score_tier(self) -> WalletTier:
        return WalletTier(self.recommended_tier)

    def execution_eligible(self, at: datetime) -> bool:
        """Smart-wallet intelligence never authorizes execution."""

        del at
        return False


@dataclass(slots=True)
class _WalletAggregate:
    snapshots: list[WalletTrackingSnapshot]
    outcomes: list[WalletRoundTrip]
    states: list[QualityState]
    snapshot_confidences: list[Decimal]
    evidence_refs: list[str]
    provenance: list[Provenance]
    future_outcome_excluded: bool = False
    outside_window_excluded: bool = False
    duplicate_outcome_deduped: bool = False
    metadata_conflict: bool = False


class SmartWalletScorer:
    """Aggregate completed wallet round trips without provider coupling."""

    def __init__(self, *, policy: SmartWalletScoringPolicy | None = None) -> None:
        self.policy = policy or SmartWalletScoringPolicy()

    def score(
        self,
        snapshots: Sequence[WalletTrackingSnapshot],
        *,
        now: datetime,
        config_hash: str,
        manipulation_penalties: Mapping[str, Decimal]
        | Sequence[tuple[str, Decimal]] = (),
    ) -> tuple[SmartWalletScore, ...]:
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(snapshots, str | bytes | bytearray):
            raise TypeError("snapshots must be a sequence")
        if len(snapshots) > 10_000:
            raise ValueError("wallet score snapshots exceeded the configured bound")
        penalties = self._normalize_penalties(manipulation_penalties)
        groups: dict[str, _WalletAggregate] = {}
        for snapshot in snapshots:
            if not isinstance(snapshot, WalletTrackingSnapshot):
                raise TypeError("snapshots must contain WalletTrackingSnapshot values")
            group = groups.get(snapshot.wallet_address)
            if group is None:
                group = _WalletAggregate(
                    snapshots=[],
                    outcomes=[],
                    states=[],
                    snapshot_confidences=[],
                    evidence_refs=[],
                    provenance=[],
                )
                groups[snapshot.wallet_address] = group
            group.snapshots.append(snapshot)
            snapshot_state = self._snapshot_state(snapshot, checked_at)
            group.states.append(snapshot_state)
            group.snapshot_confidences.append(snapshot.confidence)
            _append_unique(group.evidence_refs, snapshot.evidence_refs)
            _append_provenance(group.provenance, snapshot.provenance)
            if any(
                existing.label != snapshot.label or existing.tier != snapshot.tier
                for existing in group.snapshots[:-1]
            ):
                group.metadata_conflict = True
            self._add_outcomes(group, snapshot, checked_at)
        return tuple(
            self._score_group(
                wallet_address,
                group,
                penalties.get(wallet_address, Decimal("0")),
                checked_at=checked_at,
                config_hash=normalized_config_hash,
            )
            for wallet_address, group in sorted(groups.items())
        )

    def _add_outcomes(
        self,
        group: _WalletAggregate,
        snapshot: WalletTrackingSnapshot,
        now: datetime,
    ) -> None:
        window_start = now - self.policy.rolling_window
        existing_keys = {self._outcome_key(outcome) for outcome in group.outcomes}
        for outcome in snapshot.round_trips:
            if outcome.buy_at > now or outcome.sell_at > now:
                group.future_outcome_excluded = True
                group.states.append(QualityState.INVALID)
                continue
            if outcome.sell_at < window_start:
                group.outside_window_excluded = True
                continue
            key = self._outcome_key(outcome)
            if key in existing_keys:
                group.duplicate_outcome_deduped = True
                continue
            group.outcomes.append(outcome)
            existing_keys.add(key)
            _append_unique(group.evidence_refs, outcome.evidence_refs)
            _append_provenance(group.provenance, outcome.provenance)

    @staticmethod
    def _outcome_key(outcome: WalletRoundTrip) -> tuple[object, ...]:
        return (
            outcome.token.id,
            outcome.wallet_address,
            outcome.buy_at,
            outcome.sell_at,
            outcome.quantity,
            outcome.evidence_refs,
        )

    def _score_group(
        self,
        wallet_address: str,
        group: _WalletAggregate,
        manipulation_penalty: Decimal,
        *,
        checked_at: datetime,
        config_hash: str,
    ) -> SmartWalletScore:
        ordered_snapshots = sorted(group.snapshots, key=lambda item: (item.as_of, item.label))
        first_snapshot = ordered_snapshots[0]
        registry_tier = WalletTier(first_snapshot.tier)
        label = first_snapshot.label
        if group.metadata_conflict:
            metadata_snapshots = sorted(
                group.snapshots,
                key=lambda item: (item.label, WalletTier(item.tier).value),
            )
            label = metadata_snapshots[0].label
            registry_tier = WalletTier(metadata_snapshots[0].tier)
        penalty = to_decimal(manipulation_penalty, "manipulation penalty")
        if penalty < 0 or penalty > self.policy.maximum_manipulation_penalty:
            raise ValueError("manipulation penalty exceeds the configured policy")
        quality_state = _combined_quality(group.states)
        sample_count = len(group.outcomes)
        known_returns: list[Decimal] = []
        known_pnl: list[Decimal] = []
        early_values: list[bool] = []
        rug_values: list[bool] = []
        all_financial_known = True
        all_early_known = True
        all_rug_known = True
        total_cost = Decimal("0")
        for outcome in group.outcomes:
            if outcome.realized_pnl is None:
                all_financial_known = False
            else:
                known_pnl.append(outcome.realized_pnl)
            if outcome.cost_basis is None or outcome.cost_basis <= 0:
                all_financial_known = False
            else:
                total_cost += outcome.cost_basis
                if outcome.realized_pnl is not None:
                    known_returns.append(outcome.realized_pnl / outcome.cost_basis)
            if outcome.token_age_at_entry_seconds is None:
                all_early_known = False
            else:
                early_values.append(
                    outcome.token_age_at_entry_seconds
                    <= Decimal(str(self.policy.early_entry_max_age.total_seconds()))
                )
            if outcome.rug_exposure is None:
                all_rug_known = False
            else:
                rug_values.append(not outcome.rug_exposure)
        known_outcome_count = len(known_returns)
        win_rate = (
            None
            if not known_returns or not all_financial_known
            else Decimal(sum(value > 0 for value in known_returns)) / Decimal(sample_count)
        )
        realized_pnl = (
            None
            if not group.outcomes or not all_financial_known
            else sum(known_pnl, Decimal("0"))
        )
        median_return = (
            None
            if not known_returns or not all_financial_known
            else self._median(sorted(known_returns))
        )
        early_entry_rate = (
            None
            if not early_values or not all_early_known
            else Decimal(sum(early_values)) / Decimal(sample_count)
        )
        rug_avoidance_rate = (
            None
            if not rug_values or not all_rug_known
            else Decimal(sum(rug_values)) / Decimal(sample_count)
        )
        sample_confidence = (
            Decimal("0")
            if sample_count == 0
            else Decimal(sample_count)
            / Decimal(sample_count + self.policy.prior_sample_count)
        )
        evidence_confidence = min(group.snapshot_confidences, default=Decimal("0"))
        confidence = bounded_decimal(
            sample_confidence
            * evidence_confidence
            * _QUALITY_CONFIDENCE[quality_state],
            "confidence",
            Decimal("0"),
            Decimal("1"),
        )
        aggregate_return = (
            None
            if not group.outcomes or not all_financial_known or total_cost <= 0
            else sum(known_pnl, Decimal("0")) / total_cost
        )
        component_values = {
            "win_rate": _shrink(
                None if win_rate is None else win_rate * Decimal("100"),
                neutral=Decimal("50"),
                sample_confidence=sample_confidence,
            ),
            "realized_pnl": self._return_component(aggregate_return, sample_confidence),
            "median_return": self._return_component(median_return, sample_confidence),
            "early_entry_rate": _shrink(
                None if early_entry_rate is None else early_entry_rate * Decimal("100"),
                neutral=Decimal("50"),
                sample_confidence=sample_confidence,
            ),
            "rug_avoidance_rate": _shrink(
                None if rug_avoidance_rate is None else rug_avoidance_rate * Decimal("100"),
                neutral=Decimal("50"),
                sample_confidence=sample_confidence,
            ),
        }
        raw_score = sum(
            (
                component_values["win_rate"] * self.policy.win_rate_weight,
                component_values["realized_pnl"] * self.policy.realized_pnl_weight,
                component_values["median_return"] * self.policy.median_return_weight,
                component_values["early_entry_rate"] * self.policy.early_entry_weight,
                component_values["rug_avoidance_rate"] * self.policy.rug_avoidance_weight,
            ),
            Decimal("0"),
        )
        score = _clamp(
            Decimal("50") + sample_confidence * (raw_score - Decimal("50")) - penalty,
            Decimal("0"),
            Decimal("100"),
        )
        reasons: list[str | ReasonCode] = ["SMART_WALLET_SCORE_CALCULATED"]
        if group.duplicate_outcome_deduped:
            reasons.append("DUPLICATE_OUTCOME_DEDUPED")
        if group.outside_window_excluded:
            reasons.append("OUTCOME_OUTSIDE_WINDOW")
        if group.future_outcome_excluded:
            reasons.append("FUTURE_OUTCOME_EXCLUDED")
        if group.metadata_conflict:
            reasons.append("WALLET_METADATA_CONFLICT")
        if sample_count < self.policy.minimum_sample_count:
            reasons.append("MINIMUM_SAMPLE_NOT_MET")
        if confidence < self.policy.minimum_confidence:
            reasons.append("MINIMUM_CONFIDENCE_NOT_MET")
        if sample_count < self.policy.tier_a_minimum_sample_count:
            reasons.append("TIER_A_SAMPLE_GATE")
        if confidence < self.policy.tier_a_minimum_confidence:
            reasons.append("TIER_A_CONFIDENCE_GATE")
        if penalty > 0:
            reasons.append("MANIPULATION_PENALTY_APPLIED")
        if win_rate is None:
            reasons.append("WIN_RATE_UNKNOWN")
        if realized_pnl is None:
            reasons.append("REALIZED_PNL_UNKNOWN")
        if median_return is None:
            reasons.append("MEDIAN_RETURN_UNKNOWN")
        if early_entry_rate is None:
            reasons.append("EARLY_ENTRY_RATE_UNKNOWN")
        if rug_avoidance_rate is None:
            reasons.append("RUG_AVOIDANCE_UNKNOWN")
        if quality_state is not QualityState.FRESH:
            reasons.append(f"SMART_WALLET_EVIDENCE_{quality_state.value}")
        recommended_tier = self._recommend_tier(
            registry_tier,
            sample_count=sample_count,
            confidence=confidence,
            quality_state=quality_state,
        )
        as_of = max((snapshot.as_of for snapshot in group.snapshots), default=checked_at)
        if as_of > checked_at:
            as_of = checked_at
        return SmartWalletScore(
            wallet_address=wallet_address,
            label=label,
            registry_tier=registry_tier,
            recommended_tier=recommended_tier,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            score=score,
            confidence=confidence,
            sample_count=sample_count,
            known_outcome_count=known_outcome_count,
            win_rate=win_rate,
            realized_pnl=realized_pnl,
            median_return=median_return,
            early_entry_rate=early_entry_rate,
            rug_avoidance_rate=rug_avoidance_rate,
            manipulation_penalty=penalty,
            components=component_values,
            penalties={"manipulation": penalty} if penalty else {},
            provenance=tuple(group.provenance),
            evidence_refs=tuple(group.evidence_refs),
            reason_codes=tuple(reasons),
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def _recommend_tier(
        self,
        registry_tier: WalletTier,
        *,
        sample_count: int,
        confidence: Decimal,
        quality_state: QualityState,
    ) -> WalletTier:
        if registry_tier is WalletTier.BLOCKED:
            return WalletTier.BLOCKED
        if (
            sample_count >= self.policy.tier_a_minimum_sample_count
            and confidence >= self.policy.tier_a_minimum_confidence
            and quality_state is QualityState.FRESH
        ):
            return WalletTier.TIER_A
        if (
            sample_count >= self.policy.tier_b_minimum_sample_count
            and confidence >= self.policy.tier_b_minimum_confidence
            and quality_state is QualityState.FRESH
        ):
            return WalletTier.TIER_B
        return WalletTier.CANDIDATE

    @staticmethod
    def _return_component(value: Decimal | None, sample_confidence: Decimal) -> Decimal:
        if value is None:
            return Decimal("50")
        normalized = _clamp(value, Decimal("-1"), Decimal("1"))
        return _shrink(
            Decimal("50") + normalized * Decimal("50"),
            neutral=Decimal("50"),
            sample_confidence=sample_confidence,
        )

    @staticmethod
    def _median(values: Sequence[Decimal]) -> Decimal | None:
        if not values:
            return None
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle]) / Decimal("2")

    @staticmethod
    def _snapshot_state(snapshot: WalletTrackingSnapshot, now: datetime) -> QualityState:
        if snapshot.as_of > now:
            return QualityState.INVALID
        return snapshot.freshness.state_at(now)

    @staticmethod
    def _normalize_penalties(
        values: Mapping[str, Decimal] | Sequence[tuple[str, Decimal]],
    ) -> dict[str, Decimal]:
        if isinstance(values, str | bytes | bytearray):
            raise TypeError("manipulation_penalties must be a mapping or sequence")
        items = values.items() if isinstance(values, Mapping) else values
        normalized: dict[str, Decimal] = {}
        for address, value in items:
            if not isinstance(address, str):
                raise TypeError("manipulation penalty wallet address must be a string")
            normalized_address = require_solana_address(address, "wallet address")
            if normalized_address in normalized:
                raise ValueError(f"duplicate manipulation penalty for {normalized_address}")
            normalized[normalized_address] = to_decimal(value, "manipulation penalty")
        return normalized


__all__ = ["SmartWalletScore", "SmartWalletScorer", "SmartWalletScoringPolicy", "SmartWalletTier"]
