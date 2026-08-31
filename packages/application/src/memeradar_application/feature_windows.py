"""Provider-independent rolling feature-snapshot aggregation.

The correlation builder owns event-time membership.  This module consumes its
immutable output together with already-normalized application evidence and
projects the required ``1m``, ``5m`` and ``15m`` windows into the domain
``FeatureSnapshot`` contract.  It deliberately has no provider, persistence,
network, signer or decision-state dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    FeatureSnapshot,
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    StreamGap,
    TokenIdentity,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .confluence import TokenSmartMoneyScore
from .correlation import (
    CorrelationSnapshot,
    CorrelationWindowFeatures,
)
from .external_wallet import ExternalWalletReconciliationSnapshot
from .flow_analysis import LiquiditySnapshot, OrganicFlowScore
from .holder_graph import HolderConcentrationSnapshot
from .social_intelligence import SocialVelocityScore
from .stream_integrity import StreamQualityImpact

FEATURE_WINDOWS_VERSION = "feature-windows-v1"
FEATURE_WINDOW_NAMES: tuple[str, ...] = ("1m", "5m", "15m")
DEFAULT_FEATURE_WINDOWS: tuple[tuple[str, timedelta], ...] = (
    ("1m", timedelta(minutes=1)),
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
)

_FEATURE_FAMILY_NAMES: tuple[str, ...] = (
    "market",
    "liquidity",
    "holder",
    "wallet",
    "social",
    "momentum",
    "on_chain_safety",
)
_ALPHA_COMPONENT_NAMES: tuple[str, ...] = (
    "SmartMoney",
    "OnChainSafety",
    "LiquidityQuality",
    "OrganicFlow",
    "SocialVelocity",
    "HolderQuality",
    "Momentum",
)
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


def _clamp(value: Decimal, lower: Decimal = Decimal("0"), upper: Decimal = Decimal("1")) -> Decimal:
    return max(lower, min(upper, value))


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


def _normalise_count(value: int, cap: int) -> Decimal:
    return _clamp(Decimal(value) / Decimal(cap))


def _ratio_score(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    parsed = to_decimal(value, "ratio")
    if parsed < 0:
        return None
    return _clamp(parsed / (Decimal("1") + parsed))


def _signed_score(
    value: Decimal | int | float | str | None,
    scale: Decimal,
) -> Decimal | None:
    if value is None or scale <= 0:
        return None
    parsed = to_decimal(value, "signed value")
    return Decimal("0.5") + _clamp(parsed / scale, Decimal("-1"), Decimal("1")) / Decimal("2")


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    return to_decimal(value, field)


def _freeze_value(value: object) -> object:
    """Recursively freeze builder-owned values before putting them in a snapshot."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_value(item) for item in value)
    return value


def _input_state(value: object, boundary: datetime) -> tuple[QualityState, bool]:
    """Resolve freshness and report evidence that is in the future of a snapshot."""

    as_of = getattr(value, "as_of", None)
    if not isinstance(as_of, datetime):
        return QualityState.INVALID, False
    if as_of > boundary:
        return QualityState.INVALID, True
    provenance = getattr(value, "provenance", ())
    if any(source.observed_at > boundary for source in provenance):
        return QualityState.INVALID, True
    expires_at = getattr(value, "expires_at", None)
    if not isinstance(expires_at, datetime):
        return QualityState.INVALID, False
    raw_quality_state = getattr(value, "quality_state", None)
    if raw_quality_state is None:
        raw_quality_state = getattr(value, "critical_evidence_state", QualityState.UNKNOWN)
    state = Freshness(
        as_of,
        expires_at,
        QualityState(cast(QualityState | str, raw_quality_state)),
    ).state_at(boundary)
    return state, False


def _stable_snapshot_id(
    candidate_id: UUID,
    window_name: str,
    as_of: datetime,
    version: str,
    config_hash: str,
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"memeradar:feature:{candidate_id}:{window_name}:{as_of.isoformat()}:{version}:{config_hash}",
    )


@dataclass(frozen=True, slots=True)
class FeatureWindowPolicy:
    """Bounded configuration for the canonical feature windows."""

    window_durations: tuple[tuple[str, timedelta], ...] = DEFAULT_FEATURE_WINDOWS
    evidence_ttl: timedelta = timedelta(minutes=5)
    market_event_cap: int = 100
    actor_cap: int = 50
    social_mention_cap: int = 75
    liquidity_target: Decimal = Decimal("100000")
    momentum_acceleration_cap: Decimal = Decimal("1000")
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    version: str = FEATURE_WINDOWS_VERSION

    def __post_init__(self) -> None:
        if self.window_durations != DEFAULT_FEATURE_WINDOWS:
            raise ValueError("feature windows must be exactly 1m, 5m and 15m")
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name in ("market_event_cap", "actor_cap", "social_mention_cap"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100_000:
                raise ValueError(f"{field_name} must be between 1 and 100000")
        for field_name in ("liquidity_target", "momentum_acceleration_cap"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} is a protected operating mode")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def window_names(self) -> tuple[str, ...]:
        return FEATURE_WINDOW_NAMES

    def duration_for(self, name: str) -> timedelta:
        normalized = require_text(name, "window name", max_length=16)
        for candidate, duration in self.window_durations:
            if candidate == normalized:
                return duration
        raise KeyError(normalized)


class FeatureWindowAggregator:
    """Build deterministic, explainable feature snapshots from normalized evidence."""

    def __init__(self, *, policy: FeatureWindowPolicy | None = None) -> None:
        self.policy = policy or FeatureWindowPolicy()

    @staticmethod
    def _validate_optional_inputs(
        token: TokenIdentity,
        candidate_id: UUID,
        *,
        risk_assessment: RiskAssessment | None,
        holder_snapshot: HolderConcentrationSnapshot | None,
        smart_money_score: TokenSmartMoneyScore | None,
        social_velocity: SocialVelocityScore | None,
        external_wallet: ExternalWalletReconciliationSnapshot | None,
        liquidity_snapshot: LiquiditySnapshot | None,
        organic_flow_score: OrganicFlowScore | None,
    ) -> None:
        values: tuple[tuple[str, object | None, type[object]], ...] = (
            ("risk_assessment", risk_assessment, RiskAssessment),
            ("holder_snapshot", holder_snapshot, HolderConcentrationSnapshot),
            ("smart_money_score", smart_money_score, TokenSmartMoneyScore),
            ("social_velocity", social_velocity, SocialVelocityScore),
            ("external_wallet", external_wallet, ExternalWalletReconciliationSnapshot),
            ("liquidity_snapshot", liquidity_snapshot, LiquiditySnapshot),
            ("organic_flow_score", organic_flow_score, OrganicFlowScore),
        )
        for field_name, value, expected in values:
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"{field_name} must be a {expected.__name__}")
        for field_name, value in (
            ("holder_snapshot", holder_snapshot),
            ("smart_money_score", smart_money_score),
            ("external_wallet", external_wallet),
            ("liquidity_snapshot", liquidity_snapshot),
            ("organic_flow_score", organic_flow_score),
        ):
            if value is not None and value.token != token:
                raise ValueError(f"{field_name} token does not match correlation token")
        if risk_assessment is not None and risk_assessment.candidate_id != candidate_id:
            raise ValueError("risk_assessment candidate_id does not match feature candidate")
        if social_velocity is not None:
            if social_velocity.token_id is not None and social_velocity.token_id != token.id:
                raise ValueError("social_velocity token_id does not match correlation token")
            if (
                social_velocity.referenced_mint is not None
                and social_velocity.referenced_mint != token.mint_address
            ):
                raise ValueError("social_velocity referenced_mint does not match correlation token")

    def _invalid_snapshots(
        self,
        candidate_id: UUID,
        correlation: CorrelationSnapshot,
        *,
        config_hash: str,
        reasons: Sequence[ReasonCode | str],
        provenance: Sequence[Provenance] = (),
        evidence_refs: Sequence[str] = (),
    ) -> tuple[FeatureSnapshot, ...]:
        normalized_reasons = normalize_reason_codes(reasons, required=True)
        normalized_provenance = tuple(
            sorted(
                set(provenance),
                key=lambda value: (value.provider, value.source_id, value.observed_at),
            )
        )
        normalized_refs = tuple(sorted(set(evidence_refs)))
        return tuple(
            self._snapshot(
                candidate_id,
                correlation.as_of,
                name,
                config_hash=config_hash,
                completeness=Decimal("0"),
                confidence=Decimal("0"),
                values={
                    "window": name,
                    "families": {},
                    "reason_codes": tuple(reason.code for reason in normalized_reasons),
                    "evidence_refs": normalized_refs,
                    "execution_eligible": False,
                },
                provenance=normalized_provenance,
                quality_state=QualityState.INVALID,
            )
            for name in self.policy.window_names
        )

    def _snapshot(
        self,
        candidate_id: UUID,
        as_of: datetime,
        window_name: str,
        *,
        config_hash: str,
        completeness: Decimal,
        confidence: Decimal,
        values: Mapping[str, object],
        provenance: Sequence[Provenance],
        quality_state: QualityState,
    ) -> FeatureSnapshot:
        return FeatureSnapshot(
            id=_stable_snapshot_id(
                candidate_id,
                window_name,
                as_of,
                self.policy.version,
                config_hash,
            ),
            candidate_id=candidate_id,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            feature_version=self.policy.version,
            completeness=completeness,
            confidence=confidence,
            values=cast(Mapping[str, object], _freeze_value(values)),
            provenance=tuple(provenance),
            config_hash=config_hash,
            quality_state=quality_state,
        )

    def _market_family(
        self,
        feature: CorrelationWindowFeatures,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        state = feature.quality_state
        available = state is QualityState.FRESH and feature.event_count > 0
        activity = _normalise_count(feature.event_count, self.policy.market_event_cap)
        buyers = _normalise_count(feature.unique_buyers, self.policy.actor_cap)
        sellers = _normalise_count(feature.unique_sellers, self.policy.actor_cap)
        makers = _normalise_count(feature.unique_makers, self.policy.actor_cap)
        score = (activity + buyers + sellers + makers) / Decimal("4") * Decimal("100")
        if not available:
            score_value: Decimal | None = None
        else:
            score_value = bounded_decimal(score, "market_score", Decimal("0"), Decimal("100"))
        return (
            {
                "available": available,
                "quality_state": state.value,
                "confidence": feature.confidence if available else Decimal("0"),
                "event_count": feature.event_count,
                "protocol_event_count": feature.protocol_event_count,
                "market_observation_count": feature.market_observation_count,
                "unique_buyers": feature.unique_buyers,
                "unique_sellers": feature.unique_sellers,
                "unique_makers": feature.unique_makers,
                "buyer_arrival_rate": feature.buyer_arrival_rate,
                "market_score": score_value,
            },
            score_value,
        )

    def _liquidity_family(
        self,
        feature: CorrelationWindowFeatures,
        *,
        liquidity_snapshot: LiquiditySnapshot | None,
        liquidity_state: QualityState,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        liquidity = _optional_decimal(feature.liquidity, "liquidity")
        depth: Decimal | None = None
        previous_liquidity: Decimal | None = None
        change_ratio: Decimal | None = None
        if liquidity_snapshot is not None and liquidity_state is QualityState.FRESH:
            liquidity = liquidity_snapshot.liquidity
            previous_liquidity = _optional_decimal(
                liquidity_snapshot.previous_liquidity,
                "previous_liquidity",
            )
            change_ratio = _optional_decimal(
                liquidity_snapshot.liquidity_change_ratio,
                "liquidity_change_ratio",
            )
            depth = _optional_decimal(liquidity_snapshot.depth, "depth")
        level = None if liquidity is None else _clamp(liquidity / self.policy.liquidity_target)
        liquidity_delta = _optional_decimal(feature.liquidity_delta, "liquidity_delta")
        if change_ratio is None and liquidity is not None and liquidity_delta is not None:
            change_ratio = liquidity_delta / liquidity if liquidity else None
        change_score = _signed_score(change_ratio, Decimal("1"))
        parts = [value for value in (level, change_score) if value is not None]
        state = liquidity_state if liquidity_snapshot is not None else feature.quality_state
        available = state is QualityState.FRESH and level is not None
        score = (
            None
            if not parts or not available
            else bounded_decimal(
                sum(parts, Decimal("0")) / Decimal(len(parts)) * Decimal("100"),
                "liquidity_score",
                Decimal("0"),
                Decimal("100"),
            )
        )
        return (
            {
                "available": available,
                "quality_state": state.value,
                "confidence": (
                    min(feature.confidence, liquidity_snapshot.confidence)
                    if available and liquidity_snapshot is not None
                    else feature.confidence
                    if available
                    else Decimal("0")
                ),
                "liquidity": liquidity,
                "depth": depth,
                "previous_liquidity": previous_liquidity,
                "liquidity_delta": liquidity_delta,
                "liquidity_acceleration": _optional_decimal(
                    feature.liquidity_acceleration,
                    "liquidity_acceleration",
                ),
                "liquidity_change_ratio": change_ratio,
                "liquidity_score": score,
            },
            score,
        )

    def _holder_family(
        self,
        holder_snapshot: HolderConcentrationSnapshot | None,
        *,
        state: QualityState,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        if holder_snapshot is None:
            return (
                {
                    "available": False,
                    "quality_state": QualityState.UNKNOWN.value,
                    "confidence": Decimal("0"),
                    "top1": None,
                    "top5": None,
                    "top10": None,
                    "clustered_top": None,
                    "holder_score": None,
                },
                None,
            )
        concentration = next(
            (
                value
                for value in (
                    holder_snapshot.clustered_top,
                    holder_snapshot.top10,
                    holder_snapshot.top5,
                    holder_snapshot.top1,
                )
                if value is not None
            ),
            None,
        )
        available = state is QualityState.FRESH and concentration is not None
        if not available:
            score = None
        else:
            assert concentration is not None
            score = (Decimal("1") - concentration) * Decimal("100")
        return (
            {
                "available": available,
                "quality_state": state.value,
                "confidence": holder_snapshot.confidence if available else Decimal("0"),
                "total_holder_count": holder_snapshot.total_holder_count,
                "top1": holder_snapshot.top1,
                "top5": holder_snapshot.top5,
                "top10": holder_snapshot.top10,
                "clustered_top": holder_snapshot.clustered_top,
                "holder_score": score,
            },
            score,
        )

    def _wallet_family(
        self,
        feature: CorrelationWindowFeatures,
        *,
        smart_money_score: TokenSmartMoneyScore | None,
        smart_money_state: QualityState,
        external_wallet: ExternalWalletReconciliationSnapshot | None,
        external_state: QualityState,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        score: Decimal | None = None
        feature_confidence = to_decimal(feature.confidence, "feature confidence")
        source_confidence = feature_confidence
        state = feature.quality_state
        if smart_money_score is not None and smart_money_state is QualityState.FRESH:
            score = smart_money_score.score
            source_confidence = min(source_confidence, smart_money_score.confidence)
            state = smart_money_state
        elif feature.quality_state is QualityState.FRESH:
            if feature.weighted_entry_quality is not None:
                score = _optional_decimal(
                    feature.weighted_entry_quality,
                    "weighted_entry_quality",
                )
            elif feature.independent_entry_clusters > 0:
                score = _normalise_count(
                    feature.independent_entry_clusters, self.policy.actor_cap
                ) * Decimal("100")
        available = state is QualityState.FRESH and score is not None
        external_values: Mapping[str, object]
        if external_wallet is None:
            external_values = {
                "available": False,
                "quality_state": QualityState.UNKNOWN.value,
                "confidence": Decimal("0"),
                "external_label_confidence": Decimal("0"),
                "confidence_bonus": Decimal("0"),
                "independent_wallet_clusters": 0,
                "security_flags": (),
                "execution_eligible": False,
            }
        else:
            external_values = {
                "available": external_state is QualityState.FRESH,
                "quality_state": external_state.value,
                "confidence": external_wallet.confidence_bonus
                if external_state is QualityState.FRESH
                else Decimal("0"),
                "external_label_confidence": external_wallet.external_label_confidence,
                "confidence_bonus": external_wallet.confidence_bonus
                if external_state is QualityState.FRESH
                else Decimal("0"),
                "independent_wallet_clusters": external_wallet.independent_external_wallet_clusters,
                "security_flags": external_wallet.corroborating_security_flags,
                "execution_eligible": False,
            }
        family = {
            "available": available,
            "quality_state": state.value,
            "confidence": source_confidence if available else Decimal("0"),
            "internal_score": score,
            "independent_entry_clusters": feature.independent_entry_clusters,
            "weighted_entry_quality": feature.weighted_entry_quality,
            "creator_related_sell_pressure": feature.creator_related_sell_pressure,
            "external_wallet": external_values,
        }
        return family, score

    def _social_family(
        self,
        feature: CorrelationWindowFeatures,
        *,
        social_velocity: SocialVelocityScore | None,
        social_state: QualityState,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        score: Decimal | None = None
        confidence = feature.confidence
        state = feature.quality_state
        window_counts: Mapping[str, int] = {}
        unique_author_counts: Mapping[str, int] = {}
        duplicate_ratio: Decimal | None = None
        spam_ratio: Decimal | None = None
        coordination_ratio: Decimal | None = None
        if social_velocity is not None and social_state is QualityState.FRESH:
            score = social_velocity.score
            confidence = min(confidence, social_velocity.confidence)
            state = social_state
            window_counts = social_velocity.window_counts
            unique_author_counts = social_velocity.unique_author_counts
            duplicate_ratio = social_velocity.duplicate_ratio
            spam_ratio = social_velocity.spam_ratio
            coordination_ratio = social_velocity.coordination_ratio
        elif feature.quality_state is QualityState.FRESH and feature.social_mention_count > 0:
            score = _normalise_count(
                feature.social_mention_count, self.policy.social_mention_cap
            ) * Decimal("100")
        available = state is QualityState.FRESH and score is not None
        return (
            {
                "available": available,
                "quality_state": state.value,
                "confidence": confidence if available else Decimal("0"),
                "mention_count": feature.social_mention_count,
                "window_counts": window_counts,
                "unique_author_counts": unique_author_counts,
                "duplicate_ratio": duplicate_ratio,
                "spam_ratio": spam_ratio,
                "coordination_ratio": coordination_ratio,
                "social_score": score,
            },
            score,
        )

    def _momentum_family(
        self,
        feature: CorrelationWindowFeatures,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        parts: list[Decimal] = []
        ratio_score = _ratio_score(_optional_decimal(feature.buy_sell_ratio, "buy_sell_ratio"))
        acceleration_score = _signed_score(
            _optional_decimal(feature.net_flow_acceleration, "net_flow_acceleration"),
            self.policy.momentum_acceleration_cap,
        )
        buyer_arrival_rate = _optional_decimal(
            feature.buyer_arrival_rate,
            "buyer_arrival_rate",
        )
        arrival_score = (
            None if buyer_arrival_rate is None else _clamp(buyer_arrival_rate / Decimal("1"))
        )
        for value in (ratio_score, acceleration_score, arrival_score):
            if value is not None:
                parts.append(value)
        available = feature.quality_state is QualityState.FRESH and bool(parts)
        score = (
            None
            if not available
            else bounded_decimal(
                sum(parts, Decimal("0")) / Decimal(len(parts)) * Decimal("100"),
                "momentum_score",
                Decimal("0"),
                Decimal("100"),
            )
        )
        return (
            {
                "available": available,
                "quality_state": feature.quality_state.value,
                "confidence": feature.confidence if available else Decimal("0"),
                "buy_sell_ratio": _optional_decimal(feature.buy_sell_ratio, "buy_sell_ratio"),
                "net_flow": _optional_decimal(feature.net_flow, "net_flow"),
                "net_flow_acceleration": _optional_decimal(
                    feature.net_flow_acceleration,
                    "net_flow_acceleration",
                ),
                "buyer_arrival_rate": buyer_arrival_rate,
                "momentum_score": score,
            },
            score,
        )

    @staticmethod
    def _on_chain_family(
        risk_assessment: RiskAssessment | None,
        *,
        state: QualityState,
    ) -> tuple[Mapping[str, object], Decimal | None]:
        if risk_assessment is None:
            return (
                {
                    "available": False,
                    "quality_state": QualityState.UNKNOWN.value,
                    "confidence": Decimal("0"),
                    "disposition": None,
                    "hard_blocks": (),
                    "warnings": (),
                    "safety_score": None,
                },
                None,
            )
        score_by_disposition = {
            RiskDisposition.PASS: Decimal("100"),
            RiskDisposition.WARN: Decimal("70"),
            RiskDisposition.BLOCK: Decimal("0"),
            RiskDisposition.UNKNOWN: None,
        }
        score = score_by_disposition[risk_assessment.disposition]
        available = state is QualityState.FRESH and score is not None
        return (
            {
                "available": available,
                "quality_state": state.value,
                "confidence": risk_assessment.confidence if available else Decimal("0"),
                "disposition": risk_assessment.disposition.value,
                "hard_blocks": risk_assessment.hard_blocks,
                "warnings": risk_assessment.warnings,
                "safety_score": score,
            },
            score,
        )

    def _organic_score(
        self,
        feature: CorrelationWindowFeatures,
        *,
        market_score: Decimal | None,
        liquidity_score: Decimal | None,
        organic_flow_score: OrganicFlowScore | None,
        organic_state: QualityState,
    ) -> Decimal | None:
        if organic_flow_score is not None and organic_state is QualityState.FRESH:
            return organic_flow_score.score
        if feature.quality_state is not QualityState.FRESH or market_score is None:
            return None
        maker_breadth = _normalise_count(feature.unique_makers, self.policy.actor_cap)
        actor_breadth = _normalise_count(
            feature.unique_buyers + feature.unique_sellers,
            self.policy.actor_cap * 2,
        )
        flow = _ratio_score(_optional_decimal(feature.buy_sell_ratio, "buy_sell_ratio")) or Decimal(
            "0.5"
        )
        wash_values: list[Decimal] = []
        for value, field_name in (
            (feature.repeated_size_ratio, "repeated_size_ratio"),
            (feature.circular_flow_ratio, "circular_flow_ratio"),
            (feature.rapid_round_trip_ratio, "rapid_round_trip_ratio"),
        ):
            if value is not None:
                parsed_value = _optional_decimal(value, field_name)
                if parsed_value is not None:
                    wash_values.append(parsed_value)
        wash_penalty = (
            sum(wash_values, Decimal("0")) / Decimal(len(wash_values))
            if wash_values
            else Decimal("0")
        )
        liquidity_support = (
            liquidity_score / Decimal("100") if liquidity_score is not None else Decimal("0.5")
        )
        score = (
            Decimal("0.35") * maker_breadth
            + Decimal("0.25") * actor_breadth
            + Decimal("0.25") * flow
            + Decimal("0.15") * liquidity_support
            - Decimal("0.50") * wash_penalty
        ) * Decimal("100")
        return bounded_decimal(score, "organic_flow_score", Decimal("0"), Decimal("100"))

    def build(
        self,
        candidate_id: UUID,
        correlation: CorrelationSnapshot,
        *,
        now: datetime,
        config_hash: str,
        risk_assessment: RiskAssessment | None = None,
        holder_snapshot: HolderConcentrationSnapshot | None = None,
        smart_money_score: TokenSmartMoneyScore | None = None,
        social_velocity: SocialVelocityScore | None = None,
        external_wallet: ExternalWalletReconciliationSnapshot | None = None,
        liquidity_snapshot: LiquiditySnapshot | None = None,
        organic_flow_score: OrganicFlowScore | None = None,
        stream_gaps: Sequence[StreamGap] = (),
    ) -> tuple[FeatureSnapshot, ...]:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if not isinstance(correlation, CorrelationSnapshot):
            raise TypeError("correlation must be a CorrelationSnapshot")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        self._validate_optional_inputs(
            correlation.token,
            candidate_id,
            risk_assessment=risk_assessment,
            holder_snapshot=holder_snapshot,
            smart_money_score=smart_money_score,
            social_velocity=social_velocity,
            external_wallet=external_wallet,
            liquidity_snapshot=liquidity_snapshot,
            organic_flow_score=organic_flow_score,
        )
        if isinstance(stream_gaps, str | bytes | bytearray):
            raise TypeError("stream_gaps must be a sequence")
        if any(not isinstance(gap, StreamGap) for gap in stream_gaps):
            raise TypeError("stream_gaps must contain StreamGap values")
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        _append_provenance(provenance, correlation.provenance)
        _append_unique(evidence_refs, correlation.evidence_refs)
        optional_inputs = (
            risk_assessment,
            holder_snapshot,
            smart_money_score,
            social_velocity,
            external_wallet,
            liquidity_snapshot,
            organic_flow_score,
        )
        future_evidence = False
        input_states: dict[str, QualityState] = {}
        for value in optional_inputs:
            if value is None:
                continue
            state, is_future = _input_state(value, correlation.as_of)
            input_states[type(value).__name__] = state
            future_evidence = future_evidence or is_future
            _append_provenance(provenance, getattr(value, "provenance", ()))
            _append_unique(evidence_refs, getattr(value, "evidence_refs", ()))
        correlation_state, correlation_future = _input_state(correlation, correlation.as_of)
        future_evidence = future_evidence or correlation_future
        if checked_at < correlation.as_of:
            return self._invalid_snapshots(
                candidate_id,
                correlation,
                config_hash=normalized_config_hash,
                reasons=("FEATURE_EVALUATION_BEFORE_AS_OF",),
                provenance=provenance,
                evidence_refs=evidence_refs,
            )
        if future_evidence:
            return self._invalid_snapshots(
                candidate_id,
                correlation,
                config_hash=normalized_config_hash,
                reasons=("FEATURE_FUTURE_EVIDENCE",),
                provenance=provenance,
                evidence_refs=evidence_refs,
            )
        missing_windows = [
            name for name in self.policy.window_names if name not in correlation.windows
        ]
        if missing_windows:
            return self._invalid_snapshots(
                candidate_id,
                correlation,
                config_hash=normalized_config_hash,
                reasons=(ReasonCode("FEATURE_WINDOWS_MISSING", detail=",".join(missing_windows)),),
                provenance=provenance,
                evidence_refs=evidence_refs,
            )
        for name in self.policy.window_names:
            feature = correlation.window(name)
            expected_start = correlation.as_of - self.policy.duration_for(name)
            if feature.end_at != correlation.as_of or feature.start_at != expected_start:
                return self._invalid_snapshots(
                    candidate_id,
                    correlation,
                    config_hash=normalized_config_hash,
                    reasons=("FEATURE_WINDOW_BOUNDARY_MISMATCH",),
                    provenance=provenance,
                    evidence_refs=evidence_refs,
                )

        risk_state = input_states.get("RiskAssessment", QualityState.UNKNOWN)
        holder_state = input_states.get("HolderConcentrationSnapshot", QualityState.UNKNOWN)
        smart_state = input_states.get("TokenSmartMoneyScore", QualityState.UNKNOWN)
        social_state = input_states.get("SocialVelocityScore", QualityState.UNKNOWN)
        external_state = input_states.get(
            "ExternalWalletReconciliationSnapshot", QualityState.UNKNOWN
        )
        liquidity_state = input_states.get("LiquiditySnapshot", QualityState.UNKNOWN)
        organic_state = input_states.get("OrganicFlowScore", QualityState.UNKNOWN)

        snapshots: list[FeatureSnapshot] = []
        for name in self.policy.window_names:
            feature = correlation.window(name)
            family_states: list[QualityState] = [correlation_state]
            families: dict[str, Mapping[str, object]] = {}
            components: dict[str, Decimal] = {}
            stream_impact = StreamQualityImpact.from_range(
                gaps=stream_gaps,
                window_start=feature.start_at,
                window_end=feature.end_at,
                as_of=correlation.as_of,
            )
            family_states.append(stream_impact.quality_state)
            reasons: list[ReasonCode] = [
                ReasonCode("FEATURE_SNAPSHOT_BUILT"),
                ReasonCode("FEATURE_WINDOW_AGGREGATED", detail=name),
            ]
            for reason_code in stream_impact.reason_codes:
                reasons.append(ReasonCode(reason_code))

            market_family, market_score = self._market_family(feature)
            liquidity_family, liquidity_score = self._liquidity_family(
                feature,
                liquidity_snapshot=liquidity_snapshot,
                liquidity_state=liquidity_state,
            )
            holder_family, holder_score = self._holder_family(
                holder_snapshot,
                state=holder_state,
            )
            wallet_family, smart_score = self._wallet_family(
                feature,
                smart_money_score=smart_money_score,
                smart_money_state=smart_state,
                external_wallet=external_wallet,
                external_state=external_state,
            )
            social_family, social_score = self._social_family(
                feature,
                social_velocity=social_velocity,
                social_state=social_state,
            )
            momentum_family, momentum_score = self._momentum_family(feature)
            on_chain_family, on_chain_score = self._on_chain_family(
                risk_assessment,
                state=risk_state,
            )
            for family_name, family in (
                ("market", market_family),
                ("liquidity", liquidity_family),
                ("holder", holder_family),
                ("wallet", wallet_family),
                ("social", social_family),
                ("momentum", momentum_family),
                ("on_chain_safety", on_chain_family),
            ):
                families[family_name] = family
                family_states.append(QualityState(str(family["quality_state"])))
                if not bool(family["available"]):
                    reasons.append(ReasonCode("FEATURE_FAMILY_MISSING", detail=family_name))
            for component_name, component_value in (
                ("SmartMoney", smart_score),
                ("OnChainSafety", on_chain_score),
                ("LiquidityQuality", liquidity_score),
                (
                    "OrganicFlow",
                    self._organic_score(
                        feature,
                        market_score=market_score,
                        liquidity_score=liquidity_score,
                        organic_flow_score=organic_flow_score,
                        organic_state=organic_state,
                    ),
                ),
                ("SocialVelocity", social_score),
                ("HolderQuality", holder_score),
                ("Momentum", momentum_score),
            ):
                if component_value is not None:
                    components[component_name] = bounded_decimal(
                        component_value,
                        f"component {component_name}",
                        Decimal("0"),
                        Decimal("100"),
                    )
            quality_state = _combined_quality(family_states)
            if quality_state is QualityState.FRESH and len(components) != len(
                _ALPHA_COMPONENT_NAMES
            ):
                quality_state = QualityState.UNKNOWN
            if quality_state is not QualityState.FRESH:
                confidence = Decimal("0")
            else:
                confidence_values = [
                    to_decimal(correlation.confidence, "correlation confidence"),
                    *(
                        Decimal(str(family["confidence"]))
                        for family in families.values()
                        if bool(family["available"])
                    ),
                ]
                confidence = _clamp(min(confidence_values))
            completeness = Decimal(len(families))
            completeness = sum(
                (Decimal("1") for family in families.values() if bool(family["available"])),
                Decimal("0"),
            ) / Decimal("7")
            completeness = Decimal(str(stream_impact.apply_completeness(completeness)))
            confidence = Decimal(str(stream_impact.apply_confidence(confidence)))
            if quality_state is not QualityState.FRESH:
                missing_names = tuple(
                    name_value
                    for name_value in _FEATURE_FAMILY_NAMES
                    if not bool(families[name_value]["available"])
                )
                if missing_names:
                    reasons.append(
                        ReasonCode(
                            "FEATURE_FAMILIES_INCOMPLETE",
                            detail=",".join(missing_names),
                        )
                    )
            if correlation_state is not QualityState.FRESH:
                reasons.append(ReasonCode(f"FEATURE_CORRELATION_{correlation_state.value}"))
            if external_wallet is not None:
                reasons.append(ReasonCode("FEATURE_EXTERNAL_WALLET_CORROBORATION"))
            normalized_reasons = normalize_reason_codes(reasons, required=True)
            values: dict[str, object] = {
                "window": name,
                "window_start": feature.start_at,
                "window_end": feature.end_at,
                "families": families,
                "components": components,
                "external_wallet": wallet_family["external_wallet"],
                "reason_codes": tuple(reason.code for reason in normalized_reasons),
                "evidence_refs": tuple(sorted(set(evidence_refs))),
                "stream_integrity": {
                    "quality_state": stream_impact.quality_state.value,
                    "completeness_multiplier": stream_impact.completeness_multiplier,
                    "confidence_multiplier": stream_impact.confidence_multiplier,
                    "reason_codes": stream_impact.reason_codes,
                    "score_adjustment": stream_impact.score_adjustment,
                },
                "execution_eligible": False,
            }
            values.update(components)
            snapshots.append(
                self._snapshot(
                    candidate_id,
                    correlation.as_of,
                    name,
                    config_hash=normalized_config_hash,
                    completeness=completeness,
                    confidence=confidence,
                    values=values,
                    provenance=tuple(
                        sorted(
                            provenance,
                            key=lambda value: (
                                value.provider,
                                value.source_id,
                                value.observed_at,
                                value.parser_version,
                            ),
                        )
                    ),
                    quality_state=quality_state,
                )
            )
        return tuple(snapshots)

    aggregate = build
    build_snapshots = build


FeatureSnapshotAggregator = FeatureWindowAggregator


__all__ = [
    "DEFAULT_FEATURE_WINDOWS",
    "FEATURE_WINDOW_NAMES",
    "FEATURE_WINDOWS_VERSION",
    "FeatureSnapshotAggregator",
    "FeatureWindowAggregator",
    "FeatureWindowPolicy",
]
