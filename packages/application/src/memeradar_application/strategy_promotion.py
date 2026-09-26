"""Out-of-Sample Strategy Promotion Gate (E10.6).

Enforces strict out-of-sample promotion criteria before any strategy candidate,
threshold, weight, or exit policy can become production configuration.
No candidate is automatically promoted into production without deterministic
replay evidence, sample adequacy, out-of-sample test expectancy lift, and human review.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import normalize_texts, require_text


@dataclass(frozen=True)
class PromotionCandidate:
    strategy_version: str
    config_hash: str
    train_expectancy: Decimal
    val_expectancy: Decimal
    test_expectancy: Decimal
    baseline_test_expectancy: Decimal
    sample_count_test: int
    rug_rate_test: Decimal
    baseline_rug_rate: Decimal
    has_train_val_test_split: bool = True
    is_deterministic_replay: bool = True
    no_lookahead_verified: bool = True
    execution_feasible: bool = True


@dataclass(frozen=True)
class StrategyPromotionRecord:
    strategy_version: str
    config_hash: str
    evaluated_at: datetime
    is_approved_for_promotion: bool
    human_reviewer: str | None
    review_notes: str | None
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]


@dataclass(frozen=True, slots=True)
class StrategyFailureModeMetadata:
    """Research metadata; it is intentionally outside score calculation."""

    strategy_name: str
    hypothesis: str
    required_evidence: tuple[str, ...]
    known_failure_modes: tuple[str, ...]
    minimum_data_quality: str
    hard_blocks: tuple[str, ...]
    validation_status: str

    def __post_init__(self) -> None:
        for field_name in (
            "strategy_name",
            "hypothesis",
            "minimum_data_quality",
            "validation_status",
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=512),
            )
        for field_name in ("required_evidence", "known_failure_modes", "hard_blocks"):
            object.__setattr__(
                self,
                field_name,
                normalize_texts(getattr(self, field_name), field_name, max_item_length=512),
            )


class StrategyFailureModeRegistry:
    """Bounded registry used by research reports, never by the live score."""

    def __init__(self, entries: Sequence[StrategyFailureModeMetadata] = ()) -> None:
        self._entries: dict[str, StrategyFailureModeMetadata] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: StrategyFailureModeMetadata) -> StrategyFailureModeMetadata:
        if not isinstance(entry, StrategyFailureModeMetadata):
            raise TypeError("entry must be StrategyFailureModeMetadata")
        key = entry.strategy_name.lower()
        current = self._entries.get(key)
        if current is not None and current != entry:
            raise ValueError(f"conflicting strategy failure metadata: {entry.strategy_name}")
        if current is None and len(self._entries) >= 1_000:
            raise ValueError("strategy failure-mode registry exceeded bound")
        self._entries[key] = entry
        return entry

    def get(self, strategy_name: str) -> StrategyFailureModeMetadata | None:
        return self._entries.get(require_text(strategy_name, "strategy_name").lower())

    @property
    def entries(self) -> tuple[StrategyFailureModeMetadata, ...]:
        return tuple(self._entries.values())


class StrategyPromotionGate:
    """Evaluates candidate strategy configs for promotion eligibility."""

    def __init__(self, min_test_samples: int = 30) -> None:
        self.min_test_samples = min_test_samples

    def evaluate(
        self,
        candidate: PromotionCandidate,
        human_reviewer: str | None = None,
        review_notes: str | None = None,
    ) -> StrategyPromotionRecord:
        now = datetime.now(UTC)
        reasons: list[ReasonCode] = []

        is_approved = True

        if not candidate.is_deterministic_replay or not candidate.no_lookahead_verified:
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REJECTED_LOOKAHEAD_OR_NON_DETERMINISTIC"))

        if not candidate.has_train_val_test_split:
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REJECTED_NO_SPLIT"))

        if candidate.sample_count_test < self.min_test_samples:
            is_approved = False
            reasons.append(ReasonCode("INSUFFICIENT_SAMPLES"))

        if candidate.test_expectancy <= candidate.baseline_test_expectancy:
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REJECTED_NO_OUT_OF_SAMPLE_IMPROVEMENT"))

        if candidate.rug_rate_test > candidate.baseline_rug_rate:
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REJECTED_EXCESSIVE_RUG_RISK"))

        if not candidate.execution_feasible:
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REJECTED_EXECUTION_INFEASIBLE"))

        if human_reviewer is None or not human_reviewer.strip():
            is_approved = False
            reasons.append(ReasonCode("PROMOTION_REQUIRES_HUMAN_REVIEW"))

        if is_approved:
            reasons.append(ReasonCode("STRATEGY_PROMOTION_APPROVED"))

        return StrategyPromotionRecord(
            strategy_version=candidate.strategy_version,
            config_hash=candidate.config_hash,
            evaluated_at=now,
            is_approved_for_promotion=is_approved,
            human_reviewer=human_reviewer,
            review_notes=review_notes,
            quality_state=QualityState.FRESH if is_approved else QualityState.UNKNOWN,
            reason_codes=tuple(sorted(set(reasons), key=str)),
        )
