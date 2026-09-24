"""Small, event-time-safe age/liquidity cohort percentile projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

AGE_COHORTS: tuple[tuple[str, int, int | None], ...] = (
    ("0-2m", 0, 120),
    ("2-5m", 120, 300),
    ("5-10m", 300, 600),
    ("10-20m", 600, 1200),
    ("20-30m", 1200, 1800),
    ("30-60m", 1800, 3600),
    ("1-3h", 3600, 10800),
    ("3-6h", 10800, 21600),
    ("6-12h", 21600, 43200),
    ("12-24h", 43200, 86400),
)
AGE_COHORT_LABELS = tuple(name for name, _, _ in AGE_COHORTS)
COHORT_METRICS = (
    "volume",
    "turnover",
    "buyer_velocity",
    "holder_velocity",
    "liquidity_growth",
    "trade_velocity",
)
INSUFFICIENT_COHORT_DATA = "INSUFFICIENT_COHORT_DATA"


def age_cohort(age_seconds: Decimal | int | float | str) -> str | None:
    age = Decimal(str(age_seconds))
    if age < 0:
        return None
    for label, lower, upper in AGE_COHORTS:
        if age >= lower and (upper is None or age < upper):
            return label
    return None


def liquidity_cohort(liquidity: Decimal | int | float | str | None) -> str:
    if liquidity is None:
        return "UNKNOWN"
    value = Decimal(str(liquidity))
    if value < 10_000:
        return "<10K"
    if value < 50_000:
        return "10-50K"
    if value < 100_000:
        return "50-100K"
    return "100K+"


def _text(value: object) -> str:
    return "UNKNOWN" if value is None else str(value).strip().lower() or "UNKNOWN"


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None


def _field(sample: Mapping[str, object], name: str) -> object:
    value = sample.get(name)
    if value is not None:
        return value
    features = sample.get("features")
    if isinstance(features, Mapping):
        return features.get(name)
    return None


def _percentile(values: Sequence[Decimal], target: Decimal) -> Decimal | None:
    ordered = sorted(values)
    if len(ordered) < 2:
        return None
    positions = [index for index, value in enumerate(ordered) if value == target]
    if not positions:
        return None
    return Decimal(str(sum(positions, 0) / len(positions))) / Decimal(len(ordered) - 1)


@dataclass(frozen=True, slots=True)
class AgeCohortNormalization:
    candidate_id: str
    age_cohort: str | None
    liquidity_cohort: str
    sample_count: int
    status: str
    normalization_scope: tuple[str, ...]
    percentiles: Mapping[str, Decimal | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "percentiles", MappingProxyType(dict(self.percentiles)))

    def to_mapping(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "age_cohort": self.age_cohort,
            "liquidity_cohort": self.liquidity_cohort,
            "sample_count": self.sample_count,
            "status": self.status,
            "normalization_scope": self.normalization_scope,
            "percentiles": self.percentiles,
        }


class AgeCohortNormalizer:
    """Normalize only against a sufficiently populated comparable cohort."""

    def __init__(self, *, minimum_samples: int = 20) -> None:
        if minimum_samples < 2:
            raise ValueError("minimum_samples must be at least 2")
        self.minimum_samples = minimum_samples

    def normalize(
        self,
        candidate: Mapping[str, object],
        samples: Sequence[Mapping[str, object]],
    ) -> AgeCohortNormalization:
        candidate_key = str(candidate.get("candidate_id", candidate.get("id", "unknown")))
        candidate_age = _decimal(candidate.get("age_seconds"))
        cohort = None if candidate_age is None else age_cohort(candidate_age)
        candidate_liquidity = _decimal(candidate.get("liquidity"))
        liq_cohort = liquidity_cohort(candidate_liquidity)
        empty = {metric: None for metric in COHORT_METRICS}
        if cohort is None:
            return AgeCohortNormalization(
                candidate_key,
                cohort,
                liq_cohort,
                0,
                INSUFFICIENT_COHORT_DATA,
                (),
                empty,
            )

        dimensions = (
            ("chain", _text(candidate.get("chain"))),
            ("launchpad", _text(candidate.get("launchpad"))),
            ("age_cohort", cohort),
            ("liquidity_cohort", liq_cohort),
        )
        scopes = (
            dimensions,
            tuple(item for item in dimensions if item[0] != "liquidity_cohort"),
            tuple(item for item in dimensions if item[0] in {"chain", "age_cohort"}),
            (("age_cohort", cohort),),
        )
        selected: list[Mapping[str, object]] = []
        selected_scope: tuple[str, ...] = ()
        for scope in scopes:
            selected = [
                sample
                for sample in samples
                if self._matches(sample, dimensions, scope)
            ]
            if len(selected) >= self.minimum_samples:
                selected_scope = tuple(name for name, _ in scope)
                break
        if not selected_scope:
            return AgeCohortNormalization(
                candidate_key,
                cohort,
                liq_cohort,
                len(selected),
                INSUFFICIENT_COHORT_DATA,
                (),
                empty,
            )

        percentiles: dict[str, Decimal | None] = {}
        for metric in COHORT_METRICS:
            target = _decimal(_field(candidate, metric))
            values = [
                value
                for sample in selected
                if (value := _decimal(_field(sample, metric))) is not None
            ]
            percentiles[f"{metric}_percentile"] = (
                None if target is None else _percentile(values, target)
            )
        return AgeCohortNormalization(
            candidate_key,
            cohort,
            liq_cohort,
            len(selected),
            "NORMALIZED",
            selected_scope,
            percentiles,
        )

    @staticmethod
    def _matches(
        sample: Mapping[str, object],
        dimensions: Sequence[tuple[str, str]],
        scope: Sequence[tuple[str, str]],
    ) -> bool:
        scope_names = {name for name, _ in scope}
        scope_values = dict(scope)
        for name, _value in dimensions:
            if name == "age_cohort":
                sample_age = _decimal(sample.get("age_seconds"))
                sample_value = None if sample_age is None else age_cohort(sample_age)
            elif name == "liquidity_cohort":
                sample_value = liquidity_cohort(_decimal(sample.get("liquidity")))
            else:
                sample_value = _text(sample.get(name))
            if name in scope_names and sample_value != scope_values[name]:
                return False
        return True


__all__ = [
    "AGE_COHORTS",
    "AGE_COHORT_LABELS",
    "COHORT_METRICS",
    "INSUFFICIENT_COHORT_DATA",
    "AgeCohortNormalization",
    "AgeCohortNormalizer",
    "age_cohort",
    "liquidity_cohort",
]
