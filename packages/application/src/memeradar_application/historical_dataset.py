"""Validation metadata for the canonical, event-time research dataset.

This module wraps existing ``OpportunityResearchSample`` values.  It does not
replay events or infer outcomes; it only records whether the supplied matured
evidence is adequate for research gates.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from memeradar_domain.common import require_text

from .opportunity_research import OpportunityResearchAnalyzer, OpportunityResearchSample

HISTORICAL_DATASET_SCHEMA_VERSION = 1
HISTORICAL_DATASET_VERSION = "historical-real-dataset-v1"
HISTORICAL_REAL_EVIDENCE_CLASS = "HISTORICAL_REAL"
HISTORICAL_PARTITION_STRATEGY = "CHRONOLOGICAL_50_25_25"
DEFAULT_REQUIRED_COHORTS: tuple[str, ...] = (
    "EXTREME_WINNER",
    "MODERATE_WINNER",
    "ORDINARY_WINNER",
    "FLAT_NO_REPRICING",
    "SEVERE_LOSER",
    "RUG_HONEYPOT_NON_SELLABLE",
    "HIGH_ATTENTION_FALSE_POSITIVE",
    "LATE_CALLER",
    "FAILED_CALL",
    "EDITED_DELETED_CALL",
)
_PARTITIONS = ("TRAIN", "VALIDATION", "TEST")


@dataclass(frozen=True, slots=True)
class HistoricalDatasetRecord:
    """One event-time sample plus explicit maturity/discovery metadata."""

    sample: OpportunityResearchSample
    caller_id: str | None
    discovery_source: str = "TOKEN_DISCOVERED"
    matured_call: bool = False
    matured_token_outcome: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sample, OpportunityResearchSample):
            raise TypeError("sample must be an OpportunityResearchSample")
        if self.caller_id is not None:
            object.__setattr__(self, "caller_id", require_text(self.caller_id, "caller_id"))
        source = require_text(self.discovery_source, "discovery_source", max_length=32).upper()
        if source not in {"CALLER_DISCOVERED", "TOKEN_DISCOVERED", "BOTH", "UNKNOWN"}:
            raise ValueError("unsupported discovery_source")
        if source in {"CALLER_DISCOVERED", "BOTH"} and self.caller_id is None:
            raise ValueError("caller-discovered records require caller_id")
        object.__setattr__(self, "discovery_source", source)
        for field_name in ("matured_call", "matured_token_outcome"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be boolean")


@dataclass(frozen=True, slots=True)
class HistoricalDatasetConfig:
    """Versioned adequacy guardrails; these are not profitability claims."""

    dataset_version: str = HISTORICAL_DATASET_VERSION
    minimum_matured_calls: int = 1000
    minimum_callers: int = 50
    minimum_matured_token_outcomes: int = 500
    minimum_negative_control_ratio: Decimal = Decimal("0.40")
    max_test_caller_share: Decimal = Decimal("0.10")
    required_cohorts: tuple[str, ...] = DEFAULT_REQUIRED_COHORTS
    required_evidence_class: str = HISTORICAL_REAL_EVIDENCE_CLASS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dataset_version",
            require_text(self.dataset_version, "dataset_version"),
        )
        for field_name in (
            "minimum_matured_calls",
            "minimum_callers",
            "minimum_matured_token_outcomes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        for field_name in ("minimum_negative_control_ratio", "max_test_caller_share"):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal) or not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be a Decimal between zero and one")
        cohorts = tuple(
            require_text(value, "required_cohort", max_length=64).upper()
            for value in self.required_cohorts
        )
        if len(set(cohorts)) != len(cohorts):
            raise ValueError("required_cohorts must not contain duplicates")
        object.__setattr__(self, "required_cohorts", cohorts)
        object.__setattr__(
            self,
            "required_evidence_class",
            require_text(
                self.required_evidence_class,
                "required_evidence_class",
                max_length=64,
            ).upper(),
        )


@dataclass(frozen=True, slots=True)
class HistoricalDatasetValidation:
    """Reproducible adequacy result without any future target fields."""

    status: str
    reason_codes: tuple[str, ...]
    dataset_version: str
    sample_count: int
    matured_call_count: int
    caller_identity_count: int
    matured_token_outcome_count: int
    negative_control_count: int
    negative_control_ratio: Decimal
    partition_strategy: str
    partition_counts: Mapping[str, int]
    partition_event_time_bounds: Mapping[str, Mapping[str, str | None]]
    test_caller_counts: Mapping[str, int]
    test_caller_share: Decimal | None
    cohort_counts: Mapping[str, int]
    chain_counts: Mapping[str, int]
    archetype_counts: Mapping[str, int]
    market_regime_counts: Mapping[str, int]
    no_lookahead_verified: bool
    evidence_classes: tuple[str, ...]
    schema_version: int = HISTORICAL_DATASET_SCHEMA_VERSION

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_version": self.dataset_version,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "sample_count": self.sample_count,
            "matured_call_count": self.matured_call_count,
            "caller_identity_count": self.caller_identity_count,
            "matured_token_outcome_count": self.matured_token_outcome_count,
            "negative_control_count": self.negative_control_count,
            "negative_control_ratio": str(self.negative_control_ratio),
            "partition_strategy": self.partition_strategy,
            "partition_counts": dict(self.partition_counts),
            "partition_event_time_bounds": {
                key: dict(value) for key, value in self.partition_event_time_bounds.items()
            },
            "test_caller_counts": dict(self.test_caller_counts),
            "test_caller_share": (
                None if self.test_caller_share is None else str(self.test_caller_share)
            ),
            "cohort_counts": dict(self.cohort_counts),
            "chain_counts": dict(self.chain_counts),
            "archetype_counts": dict(self.archetype_counts),
            "market_regime_counts": dict(self.market_regime_counts),
            "no_lookahead_verified": self.no_lookahead_verified,
            "evidence_classes": list(self.evidence_classes),
        }


class HistoricalDatasetValidator:
    """Apply versioned sample and partition guardrails to existing samples."""

    def __init__(self, *, config: HistoricalDatasetConfig | None = None) -> None:
        self.config = config or HistoricalDatasetConfig()

    def validate(self, records: Sequence[HistoricalDatasetRecord]) -> HistoricalDatasetValidation:
        if isinstance(records, str | bytes | bytearray):
            raise TypeError("records must be a sequence")
        normalized = tuple(records)
        if any(not isinstance(value, HistoricalDatasetRecord) for value in normalized):
            raise TypeError("records must contain HistoricalDatasetRecord values")
        if len({value.sample.sample_id for value in normalized}) != len(normalized):
            raise ValueError("historical dataset contains duplicate sample IDs")

        samples = tuple(value.sample for value in normalized)
        partitions = dict(
            zip(_PARTITIONS, OpportunityResearchAnalyzer().split_samples(samples), strict=True)
        )
        by_sample_id = {value.sample.sample_id: value for value in normalized}
        partition_records = {
            key: tuple(by_sample_id[sample.sample_id] for sample in values)
            for key, values in partitions.items()
        }
        matured_calls = sum(value.matured_call for value in normalized)
        matured_outcomes = sum(value.matured_token_outcome for value in normalized)
        caller_ids = {
            value.caller_id
            for value in normalized
            if value.matured_call and value.caller_id is not None
        }
        negative_controls = sum(
            value.matured_token_outcome and not value.sample.is_winner for value in normalized
        )
        negative_ratio = (
            Decimal(negative_controls) / Decimal(matured_outcomes)
            if matured_outcomes
            else Decimal("0")
        )
        test_callers = {
            value.caller_id
            for value in partition_records["TEST"]
            if value.matured_call and value.caller_id is not None
        }
        test_caller_counts = {
            caller_id: sum(
                value.matured_call and value.caller_id == caller_id
                for value in partition_records["TEST"]
            )
            for caller_id in sorted(test_callers)
        }
        test_call_count = sum(test_caller_counts.values())
        test_caller_share = (
            max(test_caller_counts.values()) / Decimal(test_call_count)
            if test_caller_counts and test_call_count
            else None
        )
        reasons: list[str] = []
        if not all(value.sample.no_lookahead_verified for value in normalized):
            reasons.append("NO_LOOKAHEAD_UNVERIFIED")
        if matured_calls < self.config.minimum_matured_calls:
            reasons.append("MATURED_CALLS_REQUIRED")
        if len(caller_ids) < self.config.minimum_callers:
            reasons.append("CALLER_IDENTITIES_REQUIRED")
        if matured_outcomes < self.config.minimum_matured_token_outcomes:
            reasons.append("MATURED_TOKEN_OUTCOMES_REQUIRED")
        if negative_ratio < self.config.minimum_negative_control_ratio:
            reasons.append("NEGATIVE_CONTROLS_REQUIRED")
        missing_cohorts = set(self.config.required_cohorts) - {
            value.sample.cohort for value in normalized
        }
        if missing_cohorts:
            reasons.append("REQUIRED_COHORTS_MISSING")
        if test_caller_share is not None and test_caller_share > self.config.max_test_caller_share:
            reasons.append("TEST_CALLER_CAP_EXCEEDED")
        evidence_classes = tuple(sorted({value.sample.evidence_class for value in normalized}))
        if self.config.required_evidence_class not in evidence_classes:
            reasons.append("HISTORICAL_REAL_EVIDENCE_REQUIRED")

        return HistoricalDatasetValidation(
            status=(
                "INVALID"
                if "NO_LOOKAHEAD_UNVERIFIED" in reasons
                else "INSUFFICIENT_SAMPLES"
                if reasons
                else "VALID"
            ),
            reason_codes=tuple(reasons),
            dataset_version=self.config.dataset_version,
            sample_count=len(normalized),
            matured_call_count=matured_calls,
            caller_identity_count=len(caller_ids),
            matured_token_outcome_count=matured_outcomes,
            negative_control_count=negative_controls,
            negative_control_ratio=negative_ratio,
            partition_strategy=HISTORICAL_PARTITION_STRATEGY,
            partition_counts=MappingProxyType(
                {key: len(value) for key, value in partitions.items()}
            ),
            partition_event_time_bounds=MappingProxyType(
                {key: MappingProxyType(_time_bounds(value)) for key, value in partitions.items()}
            ),
            test_caller_counts=MappingProxyType(test_caller_counts),
            test_caller_share=test_caller_share,
            cohort_counts=MappingProxyType(_counts(value.sample.cohort for value in normalized)),
            chain_counts=MappingProxyType(_counts(value.sample.chain for value in normalized)),
            archetype_counts=MappingProxyType(
                _counts(value.sample.archetype for value in normalized)
            ),
            market_regime_counts=MappingProxyType(
                _counts(value.sample.market_regime for value in normalized)
            ),
            no_lookahead_verified=not any(
                not value.sample.no_lookahead_verified for value in normalized
            ),
            evidence_classes=evidence_classes,
        )


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _time_bounds(records: Sequence[OpportunityResearchSample]) -> dict[str, str | None]:
    if not records:
        return {"first": None, "last": None}
    ordered = sorted(record.event_time for record in records)
    return {"first": ordered[0].isoformat(), "last": ordered[-1].isoformat()}


__all__ = [
    "DEFAULT_REQUIRED_COHORTS",
    "HISTORICAL_DATASET_SCHEMA_VERSION",
    "HISTORICAL_DATASET_VERSION",
    "HistoricalDatasetConfig",
    "HistoricalDatasetRecord",
    "HistoricalDatasetValidation",
    "HistoricalDatasetValidator",
]
