"""Provider-neutral ultra-early detection timing and decision contracts.

These values deliberately contain observations and derived timing only.  They
do not carry a signer, an execution port, or an authority to change an
execution mode.  Unknown launch time is represented as ``None`` rather than
being guessed from provider arrival time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from .common import ensure_utc, freeze_mapping, normalize_texts, require_text, to_decimal
from .events import ReasonCode, normalize_reason_codes
from .evidence import Provenance, QualityState


class EarlyDecisionState(str, Enum):
    """Deterministic early-stage bands before the separate entry gate."""

    REJECT_LOW = "REJECT/LOW"
    LOW = "REJECT/LOW"
    WATCH = "WATCH"
    EARLY_WATCH = "EARLY_WATCH"
    STRONG_SETUP = "STRONG_SETUP"
    HIGH_CONFLUENCE = "HIGH_CONFLUENCE"
    ENTRY_READY = "ENTRY_READY"


def _optional_utc(value: datetime | None, field_name: str) -> datetime | None:
    return None if value is None else ensure_utc(value, field_name)


def _duration_ms(start: datetime | None, end: datetime | None, field_name: str) -> Decimal | None:
    if start is None or end is None:
        return None
    duration = to_decimal(str((end - start).total_seconds()), field_name) * Decimal("1000")
    if duration < 0:
        raise ValueError(f"{field_name} must be non-negative; end is before start")
    return duration


def _validate_stage_pair(
    start: datetime | None,
    end: datetime | None,
    field_name: str,
) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError(f"{field_name} end is before start")


@dataclass(frozen=True, slots=True)
class EarlyCandidateTiming:
    """First trustworthy lifecycle timestamps for one detected candidate."""

    candidate_id: UUID
    first_observed_at: datetime
    first_ingested_at: datetime
    source_id: str
    token_id: UUID | None = None
    launch_at: datetime | None = None
    quality_state: QualityState = QualityState.FRESH
    slot: int | None = None
    signature: str | None = None
    transport: str | None = None
    parser_version: str | None = None
    registry_version: str | None = None
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if self.token_id is not None and not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID or None")
        launch_at = _optional_utc(self.launch_at, "launch_at")
        first_observed_at = ensure_utc(self.first_observed_at, "first_observed_at")
        first_ingested_at = ensure_utc(self.first_ingested_at, "first_ingested_at")
        _validate_stage_pair(launch_at, first_observed_at, "launch_to_first_observed")
        _validate_stage_pair(
            first_observed_at,
            first_ingested_at,
            "first_observed_to_ingested",
        )
        object.__setattr__(self, "launch_at", launch_at)
        object.__setattr__(self, "first_observed_at", first_observed_at)
        object.__setattr__(self, "first_ingested_at", first_ingested_at)
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.slot is not None and (
            not isinstance(self.slot, int) or isinstance(self.slot, bool) or self.slot < 0
        ):
            raise ValueError("slot must be a non-negative integer or None")
        for field_name in ("signature", "transport", "parser_version", "registry_version"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, "metadata"))

    @property
    def launch_to_first_observed_ms(self) -> Decimal | None:
        return _duration_ms(self.launch_at, self.first_observed_at, "launch_to_first_observed_ms")

    @property
    def first_observed_to_ingested_ms(self) -> Decimal:
        result = _duration_ms(
            self.first_observed_at,
            self.first_ingested_at,
            "first_observed_to_ingested_ms",
        )
        assert result is not None
        return result

    @property
    def first_seen_at(self) -> datetime:
        """Compatibility name used by read projections."""

        return self.first_observed_at


@dataclass(frozen=True, slots=True)
class EarlyLatencySnapshot:
    """Stage timestamps and derived latency measurements for one candidate."""

    candidate_id: UUID
    first_observed_at: datetime
    launch_at: datetime | None = None
    first_ingested_at: datetime | None = None
    normalized_at: datetime | None = None
    risk_complete_at: datetime | None = None
    features_complete_at: datetime | None = None
    score_at: datetime | None = None
    decision_at: datetime | None = None
    entry_ready_at: datetime | None = None
    shadow_quote_at: datetime | None = None
    shadow_fill_at: datetime | None = None
    launch_to_first_observed_ms: Decimal | int | float | str | None = None
    first_observed_to_ingested_ms: Decimal | int | float | str | None = None
    ingested_to_normalized_ms: Decimal | int | float | str | None = None
    normalized_to_risk_complete_ms: Decimal | int | float | str | None = None
    normalized_to_features_complete_ms: Decimal | int | float | str | None = None
    features_to_score_ms: Decimal | int | float | str | None = None
    first_observed_to_decision_ms: Decimal | int | float | str | None = None
    first_observed_to_entry_ready_ms: Decimal | int | float | str | None = None
    entry_ready_to_shadow_quote_ms: Decimal | int | float | str | None = None
    entry_ready_to_shadow_fill_ms: Decimal | int | float | str | None = None
    quality_state: QualityState = QualityState.FRESH
    reason_codes: tuple[ReasonCode | str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        timestamps = (
            "launch_at",
            "first_observed_at",
            "first_ingested_at",
            "normalized_at",
            "risk_complete_at",
            "features_complete_at",
            "score_at",
            "decision_at",
            "entry_ready_at",
            "shadow_quote_at",
            "shadow_fill_at",
        )
        for field_name in timestamps:
            normalized = _optional_utc(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, normalized)
        if self.first_observed_at is None:  # pragma: no cover - required by the type
            raise ValueError("first_observed_at is required")
        _validate_stage_pair(self.launch_at, self.first_observed_at, "launch_to_first_observed")
        _validate_stage_pair(
            self.first_observed_at,
            self.first_ingested_at,
            "first_observed_to_ingested",
        )
        _validate_stage_pair(
            self.first_ingested_at,
            self.normalized_at,
            "ingested_to_normalized",
        )
        _validate_stage_pair(
            self.normalized_at,
            self.risk_complete_at,
            "normalized_to_risk_complete",
        )
        _validate_stage_pair(
            self.normalized_at,
            self.features_complete_at,
            "normalized_to_features_complete",
        )
        _validate_stage_pair(self.features_complete_at, self.score_at, "features_to_score")
        _validate_stage_pair(self.first_observed_at, self.decision_at, "first_observed_to_decision")
        _validate_stage_pair(
            self.first_observed_at,
            self.entry_ready_at,
            "first_observed_to_entry_ready",
        )
        _validate_stage_pair(
            self.entry_ready_at,
            self.shadow_quote_at,
            "entry_ready_to_shadow_quote",
        )
        _validate_stage_pair(
            self.entry_ready_at,
            self.shadow_fill_at,
            "entry_ready_to_shadow_fill",
        )
        duration_fields = (
            "launch_to_first_observed_ms",
            "first_observed_to_ingested_ms",
            "ingested_to_normalized_ms",
            "normalized_to_risk_complete_ms",
            "normalized_to_features_complete_ms",
            "features_to_score_ms",
            "first_observed_to_decision_ms",
            "first_observed_to_entry_ready_ms",
            "entry_ready_to_shadow_quote_ms",
            "entry_ready_to_shadow_fill_ms",
        )
        for field_name in duration_fields:
            raw_duration = getattr(self, field_name)
            if raw_duration is None:
                continue
            duration_value = to_decimal(raw_duration, field_name)
            if duration_value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, duration_value)
        computed: dict[str, Decimal | None] = {
            "launch_to_first_observed_ms": _duration_ms(
                self.launch_at,
                self.first_observed_at,
                "launch_to_first_observed_ms",
            ),
            "first_observed_to_ingested_ms": _duration_ms(
                self.first_observed_at,
                self.first_ingested_at,
                "first_observed_to_ingested_ms",
            ),
            "ingested_to_normalized_ms": _duration_ms(
                self.first_ingested_at,
                self.normalized_at,
                "ingested_to_normalized_ms",
            ),
            "normalized_to_risk_complete_ms": _duration_ms(
                self.normalized_at,
                self.risk_complete_at,
                "normalized_to_risk_complete_ms",
            ),
            "normalized_to_features_complete_ms": _duration_ms(
                self.normalized_at,
                self.features_complete_at,
                "normalized_to_features_complete_ms",
            ),
            "features_to_score_ms": _duration_ms(
                self.features_complete_at,
                self.score_at,
                "features_to_score_ms",
            ),
            "first_observed_to_decision_ms": _duration_ms(
                self.first_observed_at,
                self.decision_at,
                "first_observed_to_decision_ms",
            ),
            "first_observed_to_entry_ready_ms": _duration_ms(
                self.first_observed_at,
                self.entry_ready_at,
                "first_observed_to_entry_ready_ms",
            ),
            "entry_ready_to_shadow_quote_ms": _duration_ms(
                self.entry_ready_at,
                self.shadow_quote_at,
                "entry_ready_to_shadow_quote_ms",
            ),
            "entry_ready_to_shadow_fill_ms": _duration_ms(
                self.entry_ready_at,
                self.shadow_fill_at,
                "entry_ready_to_shadow_fill_ms",
            ),
        }
        for field_name, computed_value in computed.items():
            if computed_value is not None and getattr(self, field_name) is None:
                object.__setattr__(self, field_name, computed_value)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes),
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


@dataclass(frozen=True, slots=True)
class ExternalCallBenchmark:
    """Measurement-only comparison against an externally reported call."""

    candidate_id: UUID
    memeradar_first_seen_at: datetime
    external_call_at: datetime | None
    source_id: str
    memeradar_first_watch_at: datetime | None = None
    memeradar_entry_ready_at: datetime | None = None
    quality_state: QualityState = QualityState.UNKNOWN
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        first_seen = ensure_utc(self.memeradar_first_seen_at, "memeradar_first_seen_at")
        external = _optional_utc(self.external_call_at, "external_call_at")
        watch = _optional_utc(self.memeradar_first_watch_at, "memeradar_first_watch_at")
        entry_ready = _optional_utc(self.memeradar_entry_ready_at, "memeradar_entry_ready_at")
        _validate_stage_pair(first_seen, watch, "first_seen_to_watch")
        _validate_stage_pair(first_seen, entry_ready, "first_seen_to_entry_ready")
        if external is not None and external < first_seen:
            raise ValueError("external call is before first seen")
        object.__setattr__(self, "memeradar_first_seen_at", first_seen)
        object.__setattr__(self, "external_call_at", external)
        object.__setattr__(self, "memeradar_first_watch_at", watch)
        object.__setattr__(self, "memeradar_entry_ready_at", entry_ready)
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, "metadata"))

    @property
    def lead_time_to_external_call_ms(self) -> Decimal | None:
        return _duration_ms(
            self.memeradar_first_seen_at,
            self.external_call_at,
            "lead_time_to_external_call_ms",
        )

    @property
    def measurement_only(self) -> bool:
        return True

    @property
    def can_authorize_execution(self) -> bool:
        return False


__all__ = [
    "EarlyCandidateTiming",
    "EarlyDecisionState",
    "EarlyLatencySnapshot",
    "ExternalCallBenchmark",
]
