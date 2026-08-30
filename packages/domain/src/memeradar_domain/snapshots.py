"""Explainable feature, risk and AlphaScore snapshot models."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from .common import bounded_decimal, ensure_utc, freeze_mapping, normalize_texts, require_text
from .events import ReasonCode, normalize_reason_codes
from .evidence import Freshness, Provenance, QualityState


def _normalize_mapping(values: Mapping[str, object], field: str) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in values.items():
        normalized[require_text(key, f"{field} key")] = value
    return normalized


def _normalize_penalties(values: Mapping[str, object]) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for key, value in values.items():
        normalized[require_text(key, "penalty key")] = bounded_decimal(
            value,
            f"penalty {key}",
            Decimal("0"),
            Decimal("100"),
        )
    return normalized


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """Versioned derived features with completeness and source provenance."""

    candidate_id: UUID
    as_of: datetime
    expires_at: datetime
    feature_version: str
    completeness: Decimal
    confidence: Decimal
    values: Mapping[str, object]
    provenance: tuple[Provenance, ...]
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "feature_version",
            require_text(self.feature_version, "feature_version"),
        )
        object.__setattr__(
            self,
            "completeness",
            bounded_decimal(self.completeness, "completeness", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        normalized_values = _normalize_mapping(self.values, "values")
        if not normalized_values:
            raise ValueError("values must contain at least one feature")
        object.__setattr__(self, "values", freeze_mapping(normalized_values, "values"))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if any(not isinstance(source, Provenance) for source in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    @property
    def freshness(self) -> Freshness:
        return Freshness(
            as_of=self.as_of,
            expires_at=self.expires_at,
            quality_state=self.quality_state,
        )


class RiskDisposition(str, Enum):
    """Risk gate output; UNKNOWN never means PASS."""

    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Versioned hard-gate and penalty decision with fail-closed freshness."""

    candidate_id: UUID
    as_of: datetime
    expires_at: datetime
    risk_version: str
    disposition: RiskDisposition
    hard_blocks: tuple[str, ...]
    warnings: tuple[str, ...]
    penalties: Mapping[str, object]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    critical_evidence_state: QualityState = QualityState.UNKNOWN
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "risk_version", require_text(self.risk_version, "risk_version"))
        object.__setattr__(self, "disposition", RiskDisposition(self.disposition))
        object.__setattr__(self, "hard_blocks", normalize_texts(self.hard_blocks, "hard_blocks"))
        object.__setattr__(self, "warnings", normalize_texts(self.warnings, "warnings"))
        object.__setattr__(
            self,
            "penalties",
            freeze_mapping(_normalize_penalties(self.penalties), "penalties"),
        )
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
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(
            self,
            "critical_evidence_state",
            QualityState(self.critical_evidence_state),
        )
        if self.disposition is RiskDisposition.BLOCK and not self.hard_blocks:
            raise ValueError("BLOCK risk assessments require at least one hard block")

    @property
    def freshness(self) -> Freshness:
        return Freshness(
            as_of=self.as_of,
            expires_at=self.expires_at,
            quality_state=self.critical_evidence_state,
        )

    def execution_eligible(self, at: datetime) -> bool:
        """Return true only when a fresh, explicit PASS has no hard block."""

        return (
            self.disposition is RiskDisposition.PASS
            and not self.hard_blocks
            and bool(self.evidence_refs)
            and self.confidence > 0
            and self.critical_evidence_state is QualityState.FRESH
            and self.freshness.is_fresh(at)
        )


@dataclass(frozen=True, slots=True)
class ScoreSnapshot:
    """Versioned AlphaScore result with all material decision references."""

    candidate_id: UUID
    as_of: datetime
    model_version: str
    alpha_score: Decimal
    confidence: Decimal
    components: Mapping[str, object]
    penalties: Mapping[str, object]
    reason_codes: tuple[ReasonCode, ...]
    feature_snapshot_id: UUID
    risk_assessment_id: UUID
    expires_at: datetime
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    strategy_name: str = "legacy"
    strategy_version: str = "legacy"
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at, "expires_at"))
        if self.expires_at <= self.as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "model_version", require_text(self.model_version, "model_version"))
        object.__setattr__(
            self,
            "alpha_score",
            bounded_decimal(self.alpha_score, "alpha_score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        normalized_components = _normalize_mapping(self.components, "components")
        if not normalized_components:
            raise ValueError("components must contain at least one component")
        for key, value in normalized_components.items():
            normalized_components[key] = bounded_decimal(
                value,
                f"component {key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(
            self,
            "components",
            freeze_mapping(normalized_components, "components"),
        )
        object.__setattr__(
            self,
            "penalties",
            freeze_mapping(_normalize_penalties(self.penalties), "penalties"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "strategy_name", require_text(self.strategy_name, "strategy_name"))
        object.__setattr__(
            self,
            "strategy_version",
            require_text(self.strategy_version, "strategy_version", max_length=64),
        )

    @property
    def freshness(self) -> Freshness:
        return Freshness(
            as_of=self.as_of,
            expires_at=self.expires_at,
            quality_state=self.quality_state,
        )
