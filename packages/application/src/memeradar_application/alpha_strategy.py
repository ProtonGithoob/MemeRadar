"""Provider-independent, versioned AlphaScore strategy contracts.

The strategy layer consumes immutable feature and risk snapshots only.  It
suggests a score for ranking and replay, while hard risk gates remain outside
the strategy and every result remains permanently ineligible for execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

from memeradar_domain import (
    FeatureSnapshot,
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
)
from memeradar_domain.events import normalize_reason_codes

from .evidence_helpers import (
    append_unique as _append_provenance,
)
from .evidence_helpers import (
    append_unique as _append_unique,
)

ALPHA_SCORE_V1_VERSION = "alpha-score-v1"
ALPHA_SCORE_V1_STRATEGY_NAME = "alpha-score"
# EarlyScore is a separate launch-stage strategy. AlphaScore remains the
# downstream primary strategy after the configured early-stage handoff.
EARLY_SCORE_V1_VERSION = "early-score-v1"

ALPHA_SCORE_V1_WEIGHTS: Mapping[str, Decimal] = MappingProxyType(
    {
        "SmartMoney": Decimal("0.25"),
        "OnChainSafety": Decimal("0.20"),
        "LiquidityQuality": Decimal("0.15"),
        "OrganicFlow": Decimal("0.15"),
        "SocialVelocity": Decimal("0.10"),
        "HolderQuality": Decimal("0.10"),
        "Momentum": Decimal("0.05"),
    }
)

_COMPONENT_NAMES = tuple(ALPHA_SCORE_V1_WEIGHTS)
_COMPONENT_ALIASES = {
    "smartmoney": "SmartMoney",
    "smartmoneyscore": "SmartMoney",
    "smartmoneycomponent": "SmartMoney",
    "onchainsafety": "OnChainSafety",
    "onchainsafetyscore": "OnChainSafety",
    "tokensafety": "OnChainSafety",
    "tokensecurity": "OnChainSafety",
    "tokensecurityscore": "OnChainSafety",
    "liquidityquality": "LiquidityQuality",
    "liquidityqualityscore": "LiquidityQuality",
    "liquidity": "LiquidityQuality",
    "liquidityscore": "LiquidityQuality",
    "organicflow": "OrganicFlow",
    "organicflowscore": "OrganicFlow",
    "flowquality": "OrganicFlow",
    "socialvelocity": "SocialVelocity",
    "socialvelocityscore": "SocialVelocity",
    "social": "SocialVelocity",
    "holderquality": "HolderQuality",
    "holderqualityscore": "HolderQuality",
    "holder": "HolderQuality",
    "momentum": "Momentum",
    "momentumscore": "Momentum",
}
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_QUALITY_FACTOR = {
    QualityState.FRESH: Decimal("1"),
    QualityState.STALE: Decimal("0"),
    QualityState.UNKNOWN: Decimal("0"),
    QualityState.CONFLICTED: Decimal("0"),
    QualityState.INVALID: Decimal("0"),
}
_MISSING = object()


def _canonical_component_key(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = "".join(character for character in value.strip().lower() if character.isalnum())
    return _COMPONENT_ALIASES.get(normalized)


def _combined_quality(*states: QualityState) -> QualityState:
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _append_reason(
    reasons: list[ReasonCode],
    code: str,
    *,
    detail: str | None = None,
    evidence_refs: tuple[str, ...] = (),
) -> None:
    if code not in {reason.code for reason in reasons}:
        reasons.append(ReasonCode(code, detail=detail, evidence_refs=evidence_refs))


def _feature_evidence_refs(feature: FeatureSnapshot) -> tuple[str, ...]:
    references: list[str] = []
    for source in sorted(feature.provenance, key=lambda item: (item.provider, item.source_id)):
        reference = f"{source.provider}:{source.source_id}"
        if reference not in references:
            references.append(reference)
    return tuple(references)


@dataclass(frozen=True, slots=True)
class StrategyPolicy:
    """Bounded, mode-safe configuration shared by deterministic strategies."""

    weights: Mapping[str, Decimal] = ALPHA_SCORE_V1_WEIGHTS
    missing_component_value: Decimal = Decimal("50")
    missing_component_confidence_penalty: Decimal = Decimal("0.10")
    evidence_ttl: timedelta = timedelta(minutes=5)
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    version: str = ALPHA_SCORE_V1_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.weights, Mapping):
            raise TypeError("weights must be a mapping")
        normalized_weights: dict[str, Decimal] = {}
        for key, raw_value in self.weights.items():
            component = _canonical_component_key(key)
            if component is None:
                raise ValueError(f"weights contains unknown component: {key}")
            if component in normalized_weights:
                raise ValueError(f"weights contains duplicate component: {component}")
            weight = bounded_decimal(raw_value, f"weight {component}", Decimal("0"), Decimal("1"))
            if weight <= 0:
                raise ValueError(f"weight {component} must be positive")
            normalized_weights[component] = weight
        if tuple(normalized_weights) != _COMPONENT_NAMES:
            if set(normalized_weights) != set(_COMPONENT_NAMES):
                raise ValueError("weights must define all AlphaScore components")
            normalized_weights = {name: normalized_weights[name] for name in _COMPONENT_NAMES}
        if sum(normalized_weights.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("weights must sum to 1")
        object.__setattr__(self, "weights", MappingProxyType(normalized_weights))
        object.__setattr__(
            self,
            "missing_component_value",
            bounded_decimal(
                self.missing_component_value,
                "missing_component_value",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "missing_component_confidence_penalty",
            bounded_decimal(
                self.missing_component_confidence_penalty,
                "missing_component_confidence_penalty",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} is a protected operating mode")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class StrategyInput:
    """Immutable strategy input bundle for callers that pass policy explicitly."""

    feature_snapshot: FeatureSnapshot
    risk_assessment: RiskAssessment
    policy: StrategyPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.feature_snapshot, FeatureSnapshot):
            raise TypeError("feature_snapshot must be a FeatureSnapshot")
        if not isinstance(self.risk_assessment, RiskAssessment):
            raise TypeError("risk_assessment must be a RiskAssessment")
        if not isinstance(self.policy, StrategyPolicy):
            raise TypeError("policy must be a StrategyPolicy")
        if self.feature_snapshot.candidate_id != self.risk_assessment.candidate_id:
            raise ValueError("feature_snapshot and risk_assessment candidate_id must match")


AlphaStrategyInput = StrategyInput


@dataclass(frozen=True, slots=True)
class StrategySnapshot:
    """Immutable, explainable and permanently advisory strategy output."""

    strategy_name: str
    strategy_version: str
    candidate_id: UUID
    as_of: datetime
    expires_at: datetime
    raw_score: Decimal
    suggested_score: Decimal
    components: Mapping[str, Decimal]
    weighted_components: Mapping[str, Decimal]
    penalties: Mapping[str, Decimal]
    confidence: Decimal
    confidence_adjustment: Decimal
    risk_disposition: RiskDisposition | str
    hard_blocks: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    evidence_refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    feature_snapshot_id: UUID
    risk_assessment_id: UUID
    config_hash: str
    quality_state: QualityState
    advisory: bool = True
    is_production: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_name", require_text(self.strategy_name, "strategy_name"))
        object.__setattr__(
            self,
            "strategy_version",
            require_text(self.strategy_version, "strategy_version", max_length=64),
        )
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if not isinstance(self.feature_snapshot_id, UUID):
            raise TypeError("feature_snapshot_id must be a UUID")
        if not isinstance(self.risk_assessment_id, UUID):
            raise TypeError("risk_assessment_id must be a UUID")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in ("raw_score", "suggested_score"):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name), field_name, Decimal("0"), Decimal("100")
                ),
            )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "confidence_adjustment",
            bounded_decimal(
                self.confidence_adjustment,
                "confidence_adjustment",
                Decimal("-1"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "hard_blocks", normalize_texts(self.hard_blocks, "hard_blocks"))
        object.__setattr__(
            self,
            "components",
            MappingProxyType(self._bounded_mapping(self.components, "component", Decimal("100"))),
        )
        object.__setattr__(
            self,
            "weighted_components",
            MappingProxyType(
                self._bounded_mapping(
                    self.weighted_components,
                    "weighted component",
                    Decimal("100"),
                )
            ),
        )
        object.__setattr__(
            self,
            "penalties",
            MappingProxyType(self._bounded_mapping(self.penalties, "penalty", Decimal("100"))),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.advisory, bool) or not self.advisory:
            raise ValueError("strategy snapshots are always advisory")
        if not isinstance(self.is_production, bool):
            raise TypeError("is_production must be a boolean")

    @staticmethod
    def _bounded_mapping(
        values: Mapping[str, object],
        label: str,
        upper: Decimal,
    ) -> dict[str, Decimal]:
        if not isinstance(values, Mapping):
            raise TypeError(f"{label}s must be a mapping")
        normalized: dict[str, Decimal] = {}
        for raw_key in sorted(values, key=str):
            key = require_text(str(raw_key), f"{label} key")
            normalized[key] = bounded_decimal(
                values[raw_key],
                f"{label} {key}",
                Decimal("0"),
                upper,
            )
        return normalized

    @property
    def alpha_score(self) -> Decimal:
        """Compatibility alias for the post-penalty score suggestion."""

        return self.suggested_score

    @property
    def score(self) -> Decimal:
        return self.suggested_score

    @property
    def penalty_total(self) -> Decimal:
        return sum(self.penalties.values(), Decimal("0"))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def blocked_by_risk(self) -> bool:
        return bool(self.hard_blocks) or self.risk_disposition is not RiskDisposition.PASS

    def execution_eligible(self, at: datetime) -> bool:
        """Strategy output can never authorize execution."""

        del at
        return False

    def to_score_snapshot(self) -> ScoreSnapshot:
        """Project this advisory result into the existing score persistence model."""

        return ScoreSnapshot(
            candidate_id=self.candidate_id,
            as_of=self.as_of,
            model_version=self.strategy_version,
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            alpha_score=self.suggested_score,
            confidence=self.confidence,
            components=self.components,
            penalties=self.penalties,
            reason_codes=normalize_reason_codes(self.reason_codes, required=True),
            feature_snapshot_id=self.feature_snapshot_id,
            risk_assessment_id=self.risk_assessment_id,
            expires_at=self.expires_at,
            config_hash=self.config_hash,
            quality_state=self.quality_state,
        )


@runtime_checkable
class AlphaStrategy(Protocol):
    """Application-facing strategy protocol with no provider dependencies."""

    strategy_name: str
    strategy_version: str

    def evaluate(
        self,
        feature_snapshot: FeatureSnapshot,
        risk_assessment: RiskAssessment,
        *,
        now: datetime,
        config_hash: str,
    ) -> StrategySnapshot:
        """Evaluate immutable evidence and return an advisory snapshot."""


@dataclass(frozen=True, slots=True)
class _EvaluationContext:
    feature: FeatureSnapshot
    risk: RiskAssessment
    now: datetime
    config_hash: str
    feature_state: QualityState
    risk_state: QualityState
    quality_state: QualityState
    base_confidence: Decimal
    expires_at: datetime
    evidence_refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    reasons: tuple[ReasonCode, ...]


def _validate_input(
    feature_snapshot: FeatureSnapshot,
    risk_assessment: RiskAssessment,
    *,
    now: datetime,
    config_hash: str,
) -> tuple[FeatureSnapshot, RiskAssessment, datetime, str]:
    if not isinstance(feature_snapshot, FeatureSnapshot):
        raise TypeError("feature_snapshot must be a FeatureSnapshot")
    if not isinstance(risk_assessment, RiskAssessment):
        raise TypeError("risk_assessment must be a RiskAssessment")
    if feature_snapshot.candidate_id != risk_assessment.candidate_id:
        raise ValueError("feature_snapshot and risk_assessment candidate_id must match")
    checked_at = ensure_utc(now, "now")
    if checked_at < feature_snapshot.as_of:
        raise ValueError("strategy evaluation is before feature snapshot")
    if checked_at < risk_assessment.as_of:
        raise ValueError("strategy evaluation is before risk assessment")
    return (
        feature_snapshot,
        risk_assessment,
        checked_at,
        require_text(config_hash, "config_hash"),
    )


def _build_context(
    feature_snapshot: FeatureSnapshot,
    risk_assessment: RiskAssessment,
    *,
    now: datetime,
    config_hash: str,
) -> _EvaluationContext:
    feature, risk, checked_at, normalized_config_hash = _validate_input(
        feature_snapshot,
        risk_assessment,
        now=now,
        config_hash=config_hash,
    )
    feature_state = feature.freshness.state_at(checked_at)
    risk_state = risk.freshness.state_at(checked_at)
    quality_state = _combined_quality(feature_state, risk_state)
    base_confidence = feature.confidence * risk.confidence
    evidence_refs_list: list[str] = []
    _append_unique(evidence_refs_list, risk.evidence_refs)
    _append_unique(evidence_refs_list, _feature_evidence_refs(feature))
    provenance_list: list[Provenance] = []
    _append_provenance(provenance_list, feature.provenance)
    reasons: list[ReasonCode] = []
    _append_reason(reasons, "STRATEGY_EVALUATED")
    _append_reason(reasons, "STRATEGY_SCORE_COMPUTED")
    if risk.disposition is RiskDisposition.PASS:
        _append_reason(reasons, "STRATEGY_RISK_PASS", evidence_refs=tuple(evidence_refs_list))
    else:
        _append_reason(
            reasons,
            "STRATEGY_RISK_NOT_PASS",
            detail=risk.disposition.value,
            evidence_refs=tuple(evidence_refs_list),
        )
    if risk.hard_blocks:
        _append_reason(
            reasons,
            "STRATEGY_HARD_RISK_BLOCK",
            evidence_refs=tuple(evidence_refs_list),
        )
    if risk.warnings:
        _append_reason(
            reasons,
            "STRATEGY_RISK_WARNINGS",
            evidence_refs=tuple(evidence_refs_list),
        )
    if feature_state is not QualityState.FRESH or risk_state is not QualityState.FRESH:
        _append_reason(
            reasons,
            f"STRATEGY_EVIDENCE_{_combined_quality(feature_state, risk_state).value}",
            evidence_refs=tuple(evidence_refs_list),
        )
    if feature.config_hash != normalized_config_hash or risk.config_hash != normalized_config_hash:
        quality_state = _combined_quality(quality_state, QualityState.CONFLICTED)
        _append_reason(
            reasons,
            "STRATEGY_INPUT_CONFIG_MISMATCH",
            evidence_refs=tuple(evidence_refs_list),
        )
    expires_at = min(feature.expires_at, risk.expires_at)
    if expires_at <= checked_at:
        expires_at = checked_at + timedelta(microseconds=1)
    return _EvaluationContext(
        feature=feature,
        risk=risk,
        now=checked_at,
        config_hash=normalized_config_hash,
        feature_state=feature_state,
        risk_state=risk_state,
        quality_state=quality_state,
        base_confidence=base_confidence,
        expires_at=expires_at,
        evidence_refs=tuple(evidence_refs_list),
        provenance=tuple(provenance_list),
        reasons=tuple(reasons),
    )


def _extract_components(
    values: Mapping[str, object],
    *,
    neutral: Decimal,
) -> tuple[dict[str, Decimal], tuple[str, ...], tuple[str, ...]]:
    """Extract canonical components and return missing/invalid names.

    Feature snapshots are intentionally generic JSON-shaped records.  Unknown
    feature keys are ignored; recognized aliases that disagree fail closed.
    """

    if not isinstance(values, Mapping):
        return (
            {name: neutral for name in _COMPONENT_NAMES},
            (),
            _COMPONENT_NAMES,
        )
    candidates: dict[str, list[object]] = {name: [] for name in _COMPONENT_NAMES}
    nested = values.get("components", _MISSING)
    mappings: list[Mapping[object, object]] = [cast(Mapping[object, object], values)]
    if isinstance(nested, Mapping):
        mappings.append(cast(Mapping[object, object], nested))
    for source in mappings:
        for key, value in source.items():
            component = _canonical_component_key(key)
            if component is not None:
                candidates[component].append(value)

    components: dict[str, Decimal] = {}
    missing: list[str] = []
    invalid: list[str] = []
    for name in _COMPONENT_NAMES:
        raw_values = candidates[name]
        if not raw_values or all(value is None for value in raw_values):
            components[name] = neutral
            missing.append(name)
            continue
        parsed_values: list[Decimal] = []
        is_invalid = False
        for raw_value in raw_values:
            if raw_value is None:
                continue
            try:
                parsed = bounded_decimal(
                    raw_value,
                    f"component {name}",
                    Decimal("0"),
                    Decimal("100"),
                )
            except (TypeError, ValueError):
                is_invalid = True
                break
            parsed_values.append(parsed)
        if is_invalid or not parsed_values:
            components[name] = neutral
            invalid.append(name)
            continue
        if any(value != parsed_values[0] for value in parsed_values[1:]):
            components[name] = neutral
            invalid.append(name)
            continue
        components[name] = parsed_values[0]
    return components, tuple(missing), tuple(invalid)


def _strategy_quality(
    context: _EvaluationContext,
    *,
    missing: tuple[str, ...],
    invalid: tuple[str, ...],
) -> QualityState:
    quality_state = context.quality_state
    if missing and quality_state is QualityState.FRESH:
        quality_state = QualityState.UNKNOWN
    if invalid:
        quality_state = _combined_quality(quality_state, QualityState.INVALID)
    return quality_state


@dataclass(frozen=True, slots=True)
class AlphaScoreV1Strategy:
    """Deterministic implementation of the initial configured AlphaScore."""

    policy: StrategyPolicy = field(default_factory=StrategyPolicy)
    strategy_name: str = ALPHA_SCORE_V1_STRATEGY_NAME
    strategy_version: str = ALPHA_SCORE_V1_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.policy, StrategyPolicy):
            raise TypeError("policy must be a StrategyPolicy")
        object.__setattr__(self, "strategy_name", require_text(self.strategy_name, "strategy_name"))
        object.__setattr__(
            self,
            "strategy_version",
            require_text(self.strategy_version, "strategy_version", max_length=64),
        )

    def evaluate(
        self,
        feature_snapshot: FeatureSnapshot,
        risk_assessment: RiskAssessment,
        *,
        now: datetime,
        config_hash: str,
    ) -> StrategySnapshot:
        context = _build_context(
            feature_snapshot,
            risk_assessment,
            now=now,
            config_hash=config_hash,
        )
        components, missing, invalid = _extract_components(
            context.feature.values,
            neutral=self.policy.missing_component_value,
        )
        reasons = list(context.reasons)
        if missing:
            _append_reason(
                reasons,
                "STRATEGY_COMPONENT_MISSING",
                detail=",".join(missing),
                evidence_refs=context.evidence_refs,
            )
        if invalid:
            _append_reason(
                reasons,
                "STRATEGY_COMPONENT_INVALID",
                detail=",".join(invalid),
                evidence_refs=context.evidence_refs,
            )
        weighted_components = {
            name: components[name] * self.policy.weights[name] for name in _COMPONENT_NAMES
        }
        raw_score = sum(weighted_components.values(), Decimal("0"))
        penalties = {
            key: bounded_decimal(
                context.risk.penalties[key],
                f"penalty {key}",
                Decimal("0"),
                Decimal("100"),
            )
            for key in sorted(context.risk.penalties)
        }
        suggested_score = max(
            Decimal("0"),
            min(Decimal("100"), raw_score - sum(penalties.values(), Decimal("0"))),
        )
        quality_state = _strategy_quality(context, missing=missing, invalid=invalid)
        confidence_factor = _QUALITY_FACTOR[context.feature_state]
        confidence_factor *= _QUALITY_FACTOR[context.risk_state]
        if context.risk.disposition is RiskDisposition.UNKNOWN:
            confidence_factor = Decimal("0")
        if (
            context.config_hash != context.feature.config_hash
            or context.config_hash != context.risk.config_hash
        ):
            confidence_factor = Decimal("0")
        confidence_factor *= max(
            Decimal("0"),
            Decimal("1") - self.policy.missing_component_confidence_penalty * len(missing),
        )
        if invalid:
            confidence_factor = Decimal("0")
        confidence = context.base_confidence * confidence_factor
        confidence_adjustment = confidence - context.base_confidence
        return StrategySnapshot(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            candidate_id=context.feature.candidate_id,
            as_of=context.now,
            expires_at=context.expires_at,
            raw_score=raw_score,
            suggested_score=suggested_score,
            components=components,
            weighted_components=weighted_components,
            penalties=penalties,
            confidence=confidence,
            confidence_adjustment=confidence_adjustment,
            risk_disposition=context.risk.disposition,
            hard_blocks=context.risk.hard_blocks,
            reason_codes=tuple(reasons),
            evidence_refs=context.evidence_refs,
            provenance=context.provenance,
            feature_snapshot_id=context.feature.id,
            risk_assessment_id=context.risk.id,
            config_hash=context.config_hash,
            quality_state=quality_state,
            is_production=True,
        )


@dataclass(frozen=True, slots=True)
class ReferenceStrategy:
    """Neutral framework strategy used only by protocol/replay tests."""

    policy: StrategyPolicy = field(default_factory=StrategyPolicy)
    strategy_name: str = "reference-neutral"
    strategy_version: str = "reference-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.policy, StrategyPolicy):
            raise TypeError("policy must be a StrategyPolicy")
        object.__setattr__(self, "strategy_name", require_text(self.strategy_name, "strategy_name"))
        object.__setattr__(
            self,
            "strategy_version",
            require_text(self.strategy_version, "strategy_version", max_length=64),
        )

    def evaluate(
        self,
        feature_snapshot: FeatureSnapshot,
        risk_assessment: RiskAssessment,
        *,
        now: datetime,
        config_hash: str,
    ) -> StrategySnapshot:
        context = _build_context(
            feature_snapshot,
            risk_assessment,
            now=now,
            config_hash=config_hash,
        )
        reasons = list(context.reasons)
        _append_reason(reasons, "REFERENCE_STRATEGY_ONLY", evidence_refs=context.evidence_refs)
        components = {name: Decimal("50") for name in _COMPONENT_NAMES}
        weighted_components = {
            name: components[name] * self.policy.weights[name] for name in _COMPONENT_NAMES
        }
        confidence = context.base_confidence * _QUALITY_FACTOR[context.feature_state]
        confidence *= _QUALITY_FACTOR[context.risk_state]
        if context.risk.disposition is RiskDisposition.UNKNOWN:
            confidence = Decimal("0")
        if (
            context.config_hash != context.feature.config_hash
            or context.config_hash != context.risk.config_hash
        ):
            confidence = Decimal("0")
        return StrategySnapshot(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            candidate_id=context.feature.candidate_id,
            as_of=context.now,
            expires_at=context.expires_at,
            raw_score=Decimal("50"),
            suggested_score=Decimal("50"),
            components=components,
            weighted_components=weighted_components,
            penalties={},
            confidence=confidence,
            confidence_adjustment=confidence - context.base_confidence,
            risk_disposition=context.risk.disposition,
            hard_blocks=context.risk.hard_blocks,
            reason_codes=tuple(reasons),
            evidence_refs=context.evidence_refs,
            provenance=context.provenance,
            feature_snapshot_id=context.feature.id,
            risk_assessment_id=context.risk.id,
            config_hash=context.config_hash,
            quality_state=context.quality_state,
            is_production=False,
        )


__all__ = [
    "ALPHA_SCORE_V1_STRATEGY_NAME",
    "ALPHA_SCORE_V1_VERSION",
    "ALPHA_SCORE_V1_WEIGHTS",
    "EARLY_SCORE_V1_VERSION",
    "AlphaScoreV1Strategy",
    "AlphaStrategy",
    "AlphaStrategyInput",
    "ReferenceStrategy",
    "StrategyInput",
    "StrategyPolicy",
    "StrategySnapshot",
]
