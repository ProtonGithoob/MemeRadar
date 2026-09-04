"""Versioned EarlyScore v1, separate from the established AlphaScore strategy."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar
from uuid import UUID, uuid4

from memeradar_domain import EarlyDecisionState, QualityState, ReasonCode, RiskDisposition
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

EARLY_SCORE_V1_VERSION = "early-score-v1"
EARLY_SCORE_COMPONENT_WEIGHTS: Mapping[str, Decimal] = MappingProxyType(
    {
        "OrganicFlowAcceleration": Decimal("0.25"),
        "WalletQuality": Decimal("0.20"),
        "OnChainSafety": Decimal("0.20"),
        "LiquidityAndSellability": Decimal("0.15"),
        "LaunchMomentum": Decimal("0.10"),
        "SmartMoneyConfluence": Decimal("0.05"),
        "SocialCorroboration": Decimal("0.05"),
    }
)


def _reason(code: str, *, detail: str | None = None, refs: tuple[str, ...] = ()) -> ReasonCode:
    return ReasonCode(code, detail=detail, evidence_refs=refs)


def _source_value(source: object, name: str) -> object | None:
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _decimal_score(value: object | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return bounded_decimal(value, "score component", Decimal("0"), Decimal("100"))
    except (TypeError, ValueError):
        return None


def _quality(source: object, *names: str) -> QualityState | None:
    for name in names:
        value = _source_value(source, name)
        if value is not None:
            try:
                return QualityState(value)
            except (TypeError, ValueError):
                return QualityState.UNKNOWN
    return None


def _disposition(source: object) -> RiskDisposition:
    value = _source_value(source, "risk_disposition")
    if value is None:
        value = _source_value(source, "disposition")
    if value is None:
        return RiskDisposition.UNKNOWN
    try:
        return RiskDisposition(value)
    except (TypeError, ValueError):
        return RiskDisposition.UNKNOWN


def _refs(source: object) -> tuple[str, ...]:
    value = _source_value(source, "evidence_refs")
    if value is None:
        return ()
    if isinstance(value, str):
        return (require_text(value, "evidence_ref"),)
    if not isinstance(value, Sequence):
        return ()
    return normalize_texts(tuple(str(item) for item in value), "evidence_refs")


def _reasons(source: object) -> tuple[ReasonCode, ...]:
    value = _source_value(source, "reason_codes")
    if value is None:
        return ()
    if isinstance(value, str | ReasonCode):
        return normalize_reason_codes((value,))
    if not isinstance(value, Sequence):
        return ()
    return normalize_reason_codes(tuple(value))


@dataclass(frozen=True, slots=True)
class EarlyScorePolicy:
    """Configuration for the launch-stage score and its protected modes."""

    weights: Mapping[str, Decimal] = field(
        default_factory=lambda: dict(EARLY_SCORE_COMPONENT_WEIGHTS)
    )
    minimum_confidence: Decimal = Decimal("0.60")
    entry_ready_threshold: Decimal = Decimal("85")
    alpha_handoff_age_seconds: Decimal = Decimal("300")
    unknown_risk_penalty: Decimal = Decimal("100")
    warning_risk_penalty: Decimal = Decimal("15")
    incomplete_evidence_penalty: Decimal = Decimal("10")
    version: str = EARLY_SCORE_V1_VERSION
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    config_hash: str = field(init=False)

    component_names: ClassVar[tuple[str, ...]] = tuple(EARLY_SCORE_COMPONENT_WEIGHTS)

    def __post_init__(self) -> None:
        normalized: dict[str, Decimal] = {}
        for name in self.component_names:
            if name not in self.weights:
                raise ValueError(f"weights missing {name}")
            normalized[name] = bounded_decimal(
                self.weights[name],
                f"weight {name}",
                Decimal("0"),
                Decimal("1"),
            )
        if sum(normalized.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("EarlyScore weights must sum to one")
        object.__setattr__(self, "weights", MappingProxyType(normalized))
        object.__setattr__(
            self,
            "minimum_confidence",
            bounded_decimal(
                self.minimum_confidence,
                "minimum_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        for field_name in (
            "entry_ready_threshold",
            "alpha_handoff_age_seconds",
            "unknown_risk_penalty",
            "warning_risk_penalty",
            "incomplete_evidence_penalty",
        ):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0 or (field_name == "entry_ready_threshold" and value > 100):
                raise ValueError(f"{field_name} is outside its allowed range")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")
        material = {
            "weights": {key: str(value) for key, value in self.weights.items()},
            "minimum_confidence": str(self.minimum_confidence),
            "entry_ready_threshold": str(self.entry_ready_threshold),
            "alpha_handoff_age_seconds": str(self.alpha_handoff_age_seconds),
            "unknown_risk_penalty": str(self.unknown_risk_penalty),
            "warning_risk_penalty": str(self.warning_risk_penalty),
            "incomplete_evidence_penalty": str(self.incomplete_evidence_penalty),
            "version": self.version,
            "analysis_only": self.analysis_only,
            "paper_trading": self.paper_trading,
            "manual_execution": self.manual_execution,
            "auto_execution": self.auto_execution,
        }
        object.__setattr__(
            self,
            "config_hash",
            f"sha256:{hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}",
        )


@dataclass(frozen=True, slots=True)
class EarlyScoreSnapshot:
    """Explainable EarlyScore projection with hard-risk state kept separate."""

    score: Decimal
    confidence: Decimal
    components: Mapping[str, Decimal | None]
    penalties: Mapping[str, Decimal]
    state: EarlyDecisionState
    risk_disposition: RiskDisposition
    risk_quality_state: QualityState
    hard_risk_blocked: bool
    handoff_to_alpha: bool
    version: str
    config_hash: str
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    as_of: datetime | None = None
    launch_age_seconds: Decimal | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
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
        normalized_components = {
            require_text(key, "component key"): (
                None
                if value is None
                else bounded_decimal(value, "component", Decimal("0"), Decimal("100"))
            )
            for key, value in self.components.items()
        }
        object.__setattr__(self, "components", MappingProxyType(normalized_components))
        object.__setattr__(
            self,
            "penalties",
            MappingProxyType(
                {
                    require_text(key, "penalty key"): bounded_decimal(
                        value,
                        "penalty",
                        Decimal("0"),
                        Decimal("100"),
                    )
                    for key, value in self.penalties.items()
                }
            ),
        )
        object.__setattr__(self, "state", EarlyDecisionState(self.state))
        object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if self.as_of is not None:
            object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        if self.launch_age_seconds is not None:
            age = to_decimal(self.launch_age_seconds, "launch_age_seconds")
            if age < 0:
                raise ValueError("launch_age_seconds must be non-negative")
            object.__setattr__(self, "launch_age_seconds", age)
        if not isinstance(self.hard_risk_blocked, bool) or not isinstance(
            self.handoff_to_alpha, bool
        ):
            raise TypeError("hard_risk_blocked and handoff_to_alpha must be booleans")
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def early_score(self) -> Decimal:
        return self.score

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "score": self.score,
                "early_score": self.score,
                "confidence": self.confidence,
                "components": self.components,
                "penalties": self.penalties,
                "state": self.state.value,
                "risk_disposition": self.risk_disposition.value,
                "risk_quality_state": self.risk_quality_state.value,
                "hard_risk_blocked": self.hard_risk_blocked,
                "handoff_to_alpha": self.handoff_to_alpha,
                "version": self.version,
                "config_hash": self.config_hash,
                "reason_codes": tuple(reason.code for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "execution_eligible": False,
            },
            "early_score",
        )


class EarlyScorer:
    """Score early evidence while leaving risk and execution authority separate."""

    def score(
        self,
        snapshot: object,
        risk: object,
        confluence: object | None = None,
        social: object | None = None,
        policy: EarlyScorePolicy | None = None,
    ) -> EarlyScoreSnapshot:
        scoring_policy = policy or EarlyScorePolicy()
        explicit = _source_value(snapshot, "components")
        if isinstance(explicit, Mapping):
            raw_components = dict(explicit)
        elif isinstance(snapshot, Mapping):
            raw_components = dict(snapshot)
        else:
            raw_components = {}
        derived = self._derived_components(snapshot, risk, confluence, social)
        components: dict[str, Decimal | None] = {}
        reasons: list[ReasonCode] = list(_reasons(snapshot)) + list(_reasons(risk))
        refs = list(_refs(snapshot)) + list(_refs(risk))
        if confluence is not None:
            reasons.extend(_reasons(confluence))
            refs.extend(_refs(confluence))
        if social is not None:
            reasons.extend(_reasons(social))
            refs.extend(_refs(social))
        for name in scoring_policy.component_names:
            value = _decimal_score(raw_components.get(name))
            if value is None:
                value = derived.get(name)
            components[name] = value
            if value is None:
                code = (
                    "SOCIAL_EVIDENCE_MISSING"
                    if name == "SocialCorroboration"
                    else f"{name.upper()}_EVIDENCE_MISSING"
                )
                reasons.append(_reason(code))
        base_score = sum(
            (value or Decimal("0")) * scoring_policy.weights[name]
            for name, value in components.items()
        )
        penalties: dict[str, Decimal] = {}
        raw_penalties = _source_value(risk, "penalties")
        if isinstance(raw_penalties, Mapping):
            for key, value in raw_penalties.items():
                parsed = bounded_decimal(value, "risk penalty", Decimal("0"), Decimal("100"))
                penalties[str(key)] = parsed
        disposition = _disposition(risk)
        quality = _quality(risk, "quality_state", "critical_evidence_state") or QualityState.UNKNOWN
        hard_blocks = _source_value(risk, "hard_blocks")
        hard_risk_blocked = disposition is RiskDisposition.BLOCK or bool(hard_blocks)
        if hard_risk_blocked:
            penalties["HARD_RISK_GATE"] = scoring_policy.unknown_risk_penalty
            reasons.append(_reason("EARLY_SCORE_HARD_RISK_BLOCK", refs=_refs(risk)))
        elif disposition is RiskDisposition.UNKNOWN or quality is not QualityState.FRESH:
            penalties["RISK_EVIDENCE_UNKNOWN"] = scoring_policy.unknown_risk_penalty
            reasons.append(_reason("EARLY_SCORE_RISK_EVIDENCE_UNKNOWN"))
        elif disposition is RiskDisposition.WARN:
            penalties["RISK_WARNING"] = scoring_policy.warning_risk_penalty
            reasons.append(_reason("EARLY_SCORE_RISK_WARNING"))
        missing_components = {
            name for name, value in components.items() if value is None
        }
        if missing_components - {"SocialCorroboration"}:
            penalties["INCOMPLETE_EVIDENCE"] = scoring_policy.incomplete_evidence_penalty
        total_penalty = min(sum(penalties.values(), Decimal("0")), Decimal("100"))
        score = max(Decimal("0"), min(Decimal("100"), base_score - total_penalty))
        confidence = self._confidence(snapshot, risk, confluence, social, components)
        age = _source_value(snapshot, "launch_age_seconds")
        launch_age = None if age is None else to_decimal(age, "launch_age_seconds")
        handoff = launch_age is not None and launch_age >= scoring_policy.alpha_handoff_age_seconds
        if hard_risk_blocked or score < Decimal("40"):
            state = EarlyDecisionState.REJECT_LOW
        elif score < Decimal("60"):
            state = EarlyDecisionState.WATCH
        elif score < Decimal("75"):
            state = EarlyDecisionState.EARLY_WATCH
        elif score < Decimal("85"):
            state = EarlyDecisionState.STRONG_SETUP
        else:
            state = EarlyDecisionState.HIGH_CONFLUENCE
        snapshot_as_of = _source_value(snapshot, "as_of")
        return EarlyScoreSnapshot(
            score=score,
            confidence=confidence,
            components=components,
            penalties=penalties,
            state=state,
            risk_disposition=disposition,
            risk_quality_state=quality,
            hard_risk_blocked=hard_risk_blocked,
            handoff_to_alpha=handoff,
            version=scoring_policy.version,
            config_hash=scoring_policy.config_hash,
            reason_codes=tuple(reasons),
            evidence_refs=tuple(dict.fromkeys(refs)),
            as_of=snapshot_as_of if isinstance(snapshot_as_of, datetime) else None,
            launch_age_seconds=launch_age,
        )

    @staticmethod
    def _derived_components(
        snapshot: object,
        risk: object,
        confluence: object | None,
        social: object | None,
    ) -> dict[str, Decimal | None]:
        metrics: Mapping[str, object] = {}
        windows = _source_value(snapshot, "windows")
        if isinstance(windows, Mapping):
            candidate = windows.get("5s") or windows.get("1s")
            candidate_metrics = (
                _source_value(candidate, "metrics") if candidate is not None else None
            )
            if isinstance(candidate_metrics, Mapping):
                metrics = candidate_metrics
        acceleration = _decimal_score(metrics.get("buy_acceleration_per_second"))
        inflow = _decimal_score(metrics.get("quote_inflow_per_second"))
        organic = None
        if acceleration is not None or inflow is not None:
            organic = min(
                Decimal("100"),
                (acceleration or Decimal("0")) * Decimal("25")
                + (inflow or Decimal("0")) * Decimal("10"),
            )
        liquidity = _decimal_score(metrics.get("liquidity_change"))
        momentum = _decimal_score(metrics.get("return"))
        risk_disposition = _disposition(risk)
        safety = Decimal("100") if risk_disposition is RiskDisposition.PASS else None
        bundle = _decimal_score(_source_value(risk, "bundle_concentration"))
        wallet_quality = (
            None
            if bundle is None
            else max(Decimal("0"), Decimal("100") - bundle * Decimal("100"))
        )
        return {
            "OrganicFlowAcceleration": organic,
            "WalletQuality": wallet_quality,
            "OnChainSafety": safety,
            "LiquidityAndSellability": liquidity,
            "LaunchMomentum": momentum,
            "SmartMoneyConfluence": _decimal_score(
                _source_value(confluence, "score") if confluence is not None else None
            ),
            "SocialCorroboration": _decimal_score(
                _source_value(social, "score") if social is not None else None
            ),
        }

    @staticmethod
    def _confidence(
        snapshot: object,
        risk: object,
        confluence: object | None,
        social: object | None,
        components: Mapping[str, Decimal | None],
    ) -> Decimal:
        values: list[Decimal] = []
        for source in (snapshot, risk, confluence, social):
            if source is None:
                continue
            value = _source_value(source, "confidence")
            if value is not None:
                try:
                    values.append(bounded_decimal(value, "confidence", Decimal("0"), Decimal("1")))
                except (TypeError, ValueError):
                    values.append(Decimal("0"))
        source_confidence = min(values) if values else Decimal("1")
        coverage = Decimal(sum(value is not None for value in components.values())) / Decimal(
            len(components)
        )
        quality = _quality(risk, "quality_state", "critical_evidence_state")
        if quality is not None and quality is not QualityState.FRESH:
            return Decimal("0")
        return source_confidence * coverage


@dataclass(frozen=True, slots=True)
class AsymmetricAlphaProjection:
    """Measurement-only upside candidate projection (E6.5).

    Derived from EarlyScore/AlphaStrategy without emitting guaranteed predictions.
    """

    early_quality_score: Decimal
    upside_evidence_score: Decimal
    rug_dump_risk: Decimal
    execution_quality: Decimal
    evidence_confidence: Decimal
    launch_age_ms: int | None = None
    market_cap_at_decision: Decimal | None = None
    reason_codes: tuple[ReasonCode, ...] = ()
    strategy_version: str = "asymmetric-alpha-v1"
    config_hash: str = "asymmetric-alpha-hash"

    def __post_init__(self) -> None:
        eq_bounded = bounded_decimal(
            self.early_quality_score, "early_quality_score", Decimal("0"), Decimal("100")
        )
        object.__setattr__(self, "early_quality_score", eq_bounded)

        ue_bounded = bounded_decimal(
            self.upside_evidence_score, "upside_evidence_score", Decimal("0"), Decimal("100")
        )
        object.__setattr__(self, "upside_evidence_score", ue_bounded)

        rd_bounded = bounded_decimal(
            self.rug_dump_risk, "rug_dump_risk", Decimal("0"), Decimal("100")
        )
        object.__setattr__(self, "rug_dump_risk", rd_bounded)

        ex_bounded = bounded_decimal(
            self.execution_quality, "execution_quality", Decimal("0"), Decimal("100")
        )
        object.__setattr__(self, "execution_quality", ex_bounded)

        ec_bounded = bounded_decimal(
            self.evidence_confidence, "evidence_confidence", Decimal("0"), Decimal("1")
        )
        object.__setattr__(self, "evidence_confidence", ec_bounded)


def build_asymmetric_alpha_projection(
    snapshot: EarlyScoreSnapshot,
    market_cap_at_decision: Decimal | None = None,
    launch_age_ms: int | None = None,
) -> AsymmetricAlphaProjection:
    components = snapshot.components
    flow = components.get("OrganicFlowAcceleration") or Decimal("50")
    wallet = components.get("WalletQuality") or Decimal("50")
    momentum = components.get("LaunchMomentum") or Decimal("50")
    upside_score = (
        (flow * Decimal("0.40")) + (wallet * Decimal("0.35")) + (momentum * Decimal("0.25"))
    )

    safety = components.get("OnChainSafety") or Decimal("50")
    rug_risk = max(Decimal("0"), Decimal("100") - safety)
    if snapshot.hard_risk_blocked or snapshot.risk_disposition == RiskDisposition.BLOCK:
        rug_risk = Decimal("100")

    exec_quality = components.get("LiquidityAndSellability") or Decimal("50")

    reasons = list(snapshot.reason_codes) + [ReasonCode("ASYMMETRIC_ALPHA_PROJECTED")]

    return AsymmetricAlphaProjection(
        early_quality_score=snapshot.score,
        upside_evidence_score=bounded_decimal(
            upside_score, "upside_score", Decimal("0"), Decimal("100")
        ),
        rug_dump_risk=bounded_decimal(rug_risk, "rug_risk", Decimal("0"), Decimal("100")),
        execution_quality=exec_quality,
        evidence_confidence=snapshot.confidence,
        launch_age_ms=launch_age_ms,
        market_cap_at_decision=market_cap_at_decision,
        reason_codes=tuple(sorted(set(reasons), key=str)),
        config_hash=snapshot.config_hash,
    )


__all__ = [
    "EARLY_SCORE_COMPONENT_WEIGHTS",
    "EARLY_SCORE_V1_VERSION",
    "AsymmetricAlphaProjection",
    "EarlyScorePolicy",
    "EarlyScoreSnapshot",
    "EarlyScorer",
    "build_asymmetric_alpha_projection",
]
