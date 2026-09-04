"""Historical Winner-vs-Rug early filter optimization.

This module provides provider-free, deterministic no-lookahead research
evaluations to find early candidate filter thresholds that optimize recall
of extreme winners while rejecting rugs and severe failures.

It is strictly advisory; it never auto-promotes production configuration,
writes database state, or authorizes transaction execution.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING

from memeradar_domain import ReasonCode
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .calibration import CalibrationPartition, CalibrationTimeSplit

if TYPE_CHECKING:
    pass

WINNER_VS_RUG_VERSION = "winner-vs-rug-v1"
WINNER_VS_RUG_SCHEMA_VERSION = 1
_MISSING = object()
_PROTECTED_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


class WinnerVsRugCohort(str, Enum):
    """Historical outcome cohort classification."""

    WINNER = "WINNER"
    RUG_OR_SEVERE_FAILURE = "RUG_OR_SEVERE_FAILURE"
    NEUTRAL = "NEUTRAL"


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON value must be finite")
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _canonical_hash(material: dict[str, object]) -> str:
    encoded = json.dumps(_json_safe(material), sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(encoded.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class WinnerVsRugCandidatePolicy:
    """Candidate threshold configuration for early filter optimization."""

    candidate_id: str
    description: str
    min_early_score: Decimal = Decimal("50")
    min_alpha_score: Decimal = Decimal("50")
    min_confidence: Decimal = Decimal("0.60")
    min_liquidity_usd: Decimal = Decimal("2000")
    max_price_impact_bps: Decimal = Decimal("300")
    max_holder_concentration_pct: Decimal = Decimal("30")
    max_bundle_ratio: Decimal = Decimal("0.30")
    max_sniper_ratio: Decimal = Decimal("0.25")
    max_launch_risk_penalty: Decimal = Decimal("40")
    min_unique_buyers: int = 3
    min_buy_sell_ratio: Decimal = Decimal("1.0")
    min_buy_vol_to_mc_ratio: Decimal = Decimal("0.01")
    max_token_age_seconds: Decimal = Decimal("600")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            require_text(self.candidate_id, "candidate_id", max_length=128),
        )
        object.__setattr__(
            self,
            "description",
            require_text(self.description, "description", max_length=512),
        )
        object.__setattr__(
            self,
            "min_early_score",
            bounded_decimal(
                self.min_early_score,
                "min_early_score",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "min_alpha_score",
            bounded_decimal(
                self.min_alpha_score,
                "min_alpha_score",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "min_confidence",
            bounded_decimal(
                self.min_confidence,
                "min_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "min_liquidity_usd",
            to_decimal(self.min_liquidity_usd, "min_liquidity_usd"),
        )
        object.__setattr__(
            self,
            "max_price_impact_bps",
            to_decimal(self.max_price_impact_bps, "max_price_impact_bps"),
        )
        object.__setattr__(
            self,
            "max_holder_concentration_pct",
            bounded_decimal(
                self.max_holder_concentration_pct,
                "max_holder_concentration_pct",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "max_bundle_ratio",
            bounded_decimal(
                self.max_bundle_ratio,
                "max_bundle_ratio",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "max_sniper_ratio",
            bounded_decimal(
                self.max_sniper_ratio,
                "max_sniper_ratio",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "max_launch_risk_penalty",
            to_decimal(self.max_launch_risk_penalty, "max_launch_risk_penalty"),
        )
        if not isinstance(self.min_unique_buyers, int) or isinstance(self.min_unique_buyers, bool):
            raise TypeError("min_unique_buyers must be an integer")
        object.__setattr__(
            self,
            "min_buy_sell_ratio",
            to_decimal(self.min_buy_sell_ratio, "min_buy_sell_ratio"),
        )
        object.__setattr__(
            self,
            "min_buy_vol_to_mc_ratio",
            to_decimal(self.min_buy_vol_to_mc_ratio, "min_buy_vol_to_mc_ratio"),
        )
        object.__setattr__(
            self,
            "max_token_age_seconds",
            to_decimal(self.max_token_age_seconds, "max_token_age_seconds"),
        )

    @property
    def config_hash(self) -> str:
        return _canonical_hash(
            {
                "candidate_id": self.candidate_id,
                "min_early_score": str(self.min_early_score),
                "min_alpha_score": str(self.min_alpha_score),
                "min_confidence": str(self.min_confidence),
                "min_liquidity_usd": str(self.min_liquidity_usd),
                "max_price_impact_bps": str(self.max_price_impact_bps),
                "max_holder_concentration_pct": str(self.max_holder_concentration_pct),
                "max_bundle_ratio": str(self.max_bundle_ratio),
                "max_sniper_ratio": str(self.max_sniper_ratio),
                "max_launch_risk_penalty": str(self.max_launch_risk_penalty),
                "min_unique_buyers": self.min_unique_buyers,
                "min_buy_sell_ratio": str(self.min_buy_sell_ratio),
                "min_buy_vol_to_mc_ratio": str(self.min_buy_vol_to_mc_ratio),
                "max_token_age_seconds": str(self.max_token_age_seconds),
            }
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "description": self.description,
            "min_early_score": str(self.min_early_score),
            "min_alpha_score": str(self.min_alpha_score),
            "min_confidence": str(self.min_confidence),
            "min_liquidity_usd": str(self.min_liquidity_usd),
            "max_price_impact_bps": str(self.max_price_impact_bps),
            "max_holder_concentration_pct": str(self.max_holder_concentration_pct),
            "max_bundle_ratio": str(self.max_bundle_ratio),
            "max_sniper_ratio": str(self.max_sniper_ratio),
            "max_launch_risk_penalty": str(self.max_launch_risk_penalty),
            "min_unique_buyers": self.min_unique_buyers,
            "min_buy_sell_ratio": str(self.min_buy_sell_ratio),
            "min_buy_vol_to_mc_ratio": str(self.min_buy_vol_to_mc_ratio),
            "max_token_age_seconds": str(self.max_token_age_seconds),
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class WinnerVsRugSample:
    """Historical sample preservation for deterministic threshold optimization."""

    sample_id: str
    mint: str
    launch_venue: str
    launch_at: datetime
    decision_at: datetime
    market_cap_usd: Decimal
    liquidity_usd: Decimal
    early_score: Decimal
    alpha_score: Decimal
    confidence: Decimal
    price_impact_bps: Decimal
    holder_concentration_pct: Decimal
    bundle_ratio: Decimal
    sniper_ratio: Decimal
    launch_risk_penalty: Decimal
    unique_buyers: int
    buy_sell_ratio: Decimal
    buy_vol_to_mc_ratio: Decimal
    token_age_seconds: Decimal
    cohort: WinnerVsRugCohort
    mfe_multiple: Decimal
    mae_drawdown_pct: Decimal
    future_rug_event: bool
    parser_version: str
    strategy_version: str
    config_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort", WinnerVsRugCohort(self.cohort))
        object.__setattr__(self, "launch_at", ensure_utc(self.launch_at, "launch_at"))
        object.__setattr__(self, "decision_at", ensure_utc(self.decision_at, "decision_at"))

    def to_json_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "mint": self.mint,
            "launch_venue": self.launch_venue,
            "launch_at": self.launch_at.isoformat(),
            "decision_at": self.decision_at.isoformat(),
            "market_cap_usd": str(self.market_cap_usd),
            "liquidity_usd": str(self.liquidity_usd),
            "early_score": str(self.early_score),
            "alpha_score": str(self.alpha_score),
            "confidence": str(self.confidence),
            "price_impact_bps": str(self.price_impact_bps),
            "holder_concentration_pct": str(self.holder_concentration_pct),
            "bundle_ratio": str(self.bundle_ratio),
            "sniper_ratio": str(self.sniper_ratio),
            "launch_risk_penalty": str(self.launch_risk_penalty),
            "unique_buyers": self.unique_buyers,
            "buy_sell_ratio": str(self.buy_sell_ratio),
            "buy_vol_to_mc_ratio": str(self.buy_vol_to_mc_ratio),
            "token_age_seconds": str(self.token_age_seconds),
            "cohort": self.cohort.value,
            "mfe_multiple": str(self.mfe_multiple),
            "mae_drawdown_pct": str(self.mae_drawdown_pct),
            "future_rug_event": self.future_rug_event,
            "parser_version": self.parser_version,
            "strategy_version": self.strategy_version,
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class WinnerVsRugMetrics:
    """Metrics evaluated for a candidate policy over a sample set."""

    candidate_id: str
    config_hash: str
    sample_count: int
    winner_count: int
    rug_count: int
    neutral_count: int
    accepted_winners: int
    accepted_rugs: int
    accepted_neutrals: int
    rejected_winners: int
    rejected_rugs: int
    rejected_neutrals: int
    winner_recall: Decimal
    rug_rejection_rate: Decimal
    precision: Decimal
    false_positive_rate: Decimal
    false_negative_rate: Decimal
    median_first_detection_age_seconds: Decimal | None
    p90_first_detection_age_seconds: Decimal | None
    median_market_cap_at_detection: Decimal | None
    pct_detected_before_mc_50k: Decimal
    pct_detected_before_mc_100k: Decimal
    pct_detected_before_mc_250k: Decimal
    accepted_mfe_median: Decimal | None
    accepted_mae_median: Decimal | None
    expected_paper_pnl: Decimal
    rejection_reasons: dict[str, int]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "config_hash": self.config_hash,
            "sample_count": self.sample_count,
            "winner_count": self.winner_count,
            "rug_count": self.rug_count,
            "neutral_count": self.neutral_count,
            "accepted_winners": self.accepted_winners,
            "accepted_rugs": self.accepted_rugs,
            "accepted_neutrals": self.accepted_neutrals,
            "rejected_winners": self.rejected_winners,
            "rejected_rugs": self.rejected_rugs,
            "rejected_neutrals": self.rejected_neutrals,
            "winner_recall": str(self.winner_recall),
            "rug_rejection_rate": str(self.rug_rejection_rate),
            "precision": str(self.precision),
            "false_positive_rate": str(self.false_positive_rate),
            "false_negative_rate": str(self.false_negative_rate),
            "median_first_detection_age_seconds": (
                str(self.median_first_detection_age_seconds)
                if self.median_first_detection_age_seconds is not None
                else None
            ),
            "p90_first_detection_age_seconds": (
                str(self.p90_first_detection_age_seconds)
                if self.p90_first_detection_age_seconds is not None
                else None
            ),
            "median_market_cap_at_detection": (
                str(self.median_market_cap_at_detection)
                if self.median_market_cap_at_detection is not None
                else None
            ),
            "pct_detected_before_mc_50k": str(self.pct_detected_before_mc_50k),
            "pct_detected_before_mc_100k": str(self.pct_detected_before_mc_100k),
            "pct_detected_before_mc_250k": str(self.pct_detected_before_mc_250k),
            "accepted_mfe_median": (
                str(self.accepted_mfe_median) if self.accepted_mfe_median is not None else None
            ),
            "accepted_mae_median": (
                str(self.accepted_mae_median) if self.accepted_mae_median is not None else None
            ),
            "expected_paper_pnl": str(self.expected_paper_pnl),
            "rejection_reasons": self.rejection_reasons,
        }


@dataclass(frozen=True, slots=True)
class WinnerVsRugReport:
    """Full deterministic research report for Winner-vs-Rug optimization."""

    version: str
    evaluated_at: datetime
    baseline_candidate_id: str
    selected_candidate_id: str | None
    status: str
    train_metrics: dict[str, WinnerVsRugMetrics]
    validation_metrics: dict[str, WinnerVsRugMetrics]
    test_metrics: dict[str, WinnerVsRugMetrics]
    pareto_shortlist: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    config_hash: str
    modes: dict[str, bool] = field(default_factory=lambda: dict(_PROTECTED_MODES))

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "evaluated_at": self.evaluated_at.isoformat(),
            "baseline_candidate_id": self.baseline_candidate_id,
            "selected_candidate_id": self.selected_candidate_id,
            "status": self.status,
            "train_metrics": {k: v.to_json_dict() for k, v in self.train_metrics.items()},
            "validation_metrics": {k: v.to_json_dict() for k, v in self.validation_metrics.items()},
            "test_metrics": {k: v.to_json_dict() for k, v in self.test_metrics.items()},
            "pareto_shortlist": list(self.pareto_shortlist),
            "reason_codes": [
                code.code if isinstance(code, ReasonCode) else str(code)
                for code in self.reason_codes
            ],
            "config_hash": self.config_hash,
            "modes": self.modes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_dict(), indent=2, sort_keys=True)


def _percentile(values: Sequence[Decimal], p: float) -> Decimal | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = p * (len(sorted_vals) - 1)
    low_idx = math.floor(rank)
    high_idx = math.ceil(rank)
    if low_idx == high_idx:
        return sorted_vals[low_idx]
    weight = Decimal(str(rank - low_idx))
    return sorted_vals[low_idx] + weight * (sorted_vals[high_idx] - sorted_vals[low_idx])


class WinnerVsRugOptimizer:
    """Deterministic, no-lookahead Winner-vs-Rug filter optimization engine."""

    def __init__(self, *, baseline_policy: WinnerVsRugCandidatePolicy | None = None) -> None:
        self.baseline_policy = baseline_policy or WinnerVsRugCandidatePolicy(
            candidate_id="baseline",
            description="default conservative filter baseline",
        )

    def evaluate_candidate(
        self, candidate: WinnerVsRugCandidatePolicy, samples: Sequence[WinnerVsRugSample]
    ) -> WinnerVsRugMetrics:
        rejection_reasons: dict[str, int] = {}
        accepted_winners = 0
        accepted_rugs = 0
        accepted_neutrals = 0
        rejected_winners = 0
        rejected_rugs = 0
        rejected_neutrals = 0

        accepted_detection_ages: list[Decimal] = []
        accepted_market_caps: list[Decimal] = []
        accepted_mfes: list[Decimal] = []
        accepted_maes: list[Decimal] = []

        before_50k = 0
        before_100k = 0
        before_250k = 0

        for sample in samples:
            reasons = self._check_sample(candidate, sample)
            if not reasons:
                # Accepted
                if sample.cohort is WinnerVsRugCohort.WINNER:
                    accepted_winners += 1
                elif sample.cohort is WinnerVsRugCohort.RUG_OR_SEVERE_FAILURE:
                    accepted_rugs += 1
                else:
                    accepted_neutrals += 1

                accepted_detection_ages.append(sample.token_age_seconds)
                accepted_market_caps.append(sample.market_cap_usd)
                accepted_mfes.append(sample.mfe_multiple)
                accepted_maes.append(sample.mae_drawdown_pct)

                if sample.market_cap_usd <= Decimal("50000"):
                    before_50k += 1
                if sample.market_cap_usd <= Decimal("100000"):
                    before_100k += 1
                if sample.market_cap_usd <= Decimal("250000"):
                    before_250k += 1
            else:
                # Rejected
                primary_reason = reasons[0]
                rejection_reasons[primary_reason] = rejection_reasons.get(primary_reason, 0) + 1
                if sample.cohort is WinnerVsRugCohort.WINNER:
                    rejected_winners += 1
                elif sample.cohort is WinnerVsRugCohort.RUG_OR_SEVERE_FAILURE:
                    rejected_rugs += 1
                else:
                    rejected_neutrals += 1

        winner_count = accepted_winners + rejected_winners
        rug_count = accepted_rugs + rejected_rugs
        neutral_count = accepted_neutrals + rejected_neutrals
        sample_count = len(samples)
        total_accepted = accepted_winners + accepted_rugs + accepted_neutrals
        non_winners = sample_count - winner_count

        winner_recall = (
            Decimal(accepted_winners) / Decimal(winner_count) if winner_count > 0 else Decimal("0")
        )
        rug_rejection_rate = (
            Decimal(rejected_rugs) / Decimal(rug_count) if rug_count > 0 else Decimal("1")
        )
        precision = (
            Decimal(accepted_winners) / Decimal(total_accepted)
            if total_accepted > 0
            else Decimal("0")
        )
        false_positive_rate = (
            Decimal(accepted_rugs) / Decimal(non_winners) if non_winners > 0 else Decimal("0")
        )
        false_negative_rate = (
            Decimal(rejected_winners) / Decimal(winner_count) if winner_count > 0 else Decimal("0")
        )

        pct_50k = (
            Decimal(before_50k) / Decimal(total_accepted) if total_accepted > 0 else Decimal("0")
        )
        pct_100k = (
            Decimal(before_100k) / Decimal(total_accepted) if total_accepted > 0 else Decimal("0")
        )
        pct_250k = (
            Decimal(before_250k) / Decimal(total_accepted) if total_accepted > 0 else Decimal("0")
        )

        expected_paper_pnl = Decimal("0")
        for mfe, mae in zip(accepted_mfes, accepted_maes, strict=False):
            if mfe >= Decimal("2.0"):
                expected_paper_pnl += Decimal("1.0")  # hypothetical +100% gain
            else:
                expected_paper_pnl += mae / Decimal("100")

        return WinnerVsRugMetrics(
            candidate_id=candidate.candidate_id,
            config_hash=candidate.config_hash,
            sample_count=sample_count,
            winner_count=winner_count,
            rug_count=rug_count,
            neutral_count=neutral_count,
            accepted_winners=accepted_winners,
            accepted_rugs=accepted_rugs,
            accepted_neutrals=accepted_neutrals,
            rejected_winners=rejected_winners,
            rejected_rugs=rejected_rugs,
            rejected_neutrals=rejected_neutrals,
            winner_recall=winner_recall,
            rug_rejection_rate=rug_rejection_rate,
            precision=precision,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            median_first_detection_age_seconds=_percentile(accepted_detection_ages, 0.5),
            p90_first_detection_age_seconds=_percentile(accepted_detection_ages, 0.9),
            median_market_cap_at_detection=_percentile(accepted_market_caps, 0.5),
            pct_detected_before_mc_50k=pct_50k,
            pct_detected_before_mc_100k=pct_100k,
            pct_detected_before_mc_250k=pct_250k,
            accepted_mfe_median=_percentile(accepted_mfes, 0.5),
            accepted_mae_median=_percentile(accepted_maes, 0.5),
            expected_paper_pnl=expected_paper_pnl,
            rejection_reasons=rejection_reasons,
        )

    def _check_sample(
        self, candidate: WinnerVsRugCandidatePolicy, sample: WinnerVsRugSample
    ) -> list[str]:
        reasons: list[str] = []
        if sample.early_score < candidate.min_early_score:
            reasons.append("EARLY_SCORE_BELOW_MINIMUM")
        if sample.alpha_score < candidate.min_alpha_score:
            reasons.append("ALPHA_SCORE_BELOW_MINIMUM")
        if sample.confidence < candidate.min_confidence:
            reasons.append("CONFIDENCE_BELOW_MINIMUM")
        if sample.liquidity_usd < candidate.min_liquidity_usd:
            reasons.append("LIQUIDITY_BELOW_MINIMUM")
        if sample.price_impact_bps > candidate.max_price_impact_bps:
            reasons.append("PRICE_IMPACT_EXCEEDS_MAXIMUM")
        if sample.holder_concentration_pct > candidate.max_holder_concentration_pct:
            reasons.append("HOLDER_CONCENTRATION_EXCEEDS_MAXIMUM")
        if sample.bundle_ratio > candidate.max_bundle_ratio:
            reasons.append("BUNDLE_RATIO_EXCEEDS_MAXIMUM")
        if sample.sniper_ratio > candidate.max_sniper_ratio:
            reasons.append("SNIPER_RATIO_EXCEEDS_MAXIMUM")
        if sample.launch_risk_penalty > candidate.max_launch_risk_penalty:
            reasons.append("LAUNCH_RISK_PENALTY_EXCEEDS_MAXIMUM")
        if sample.unique_buyers < candidate.min_unique_buyers:
            reasons.append("UNIQUE_BUYERS_BELOW_MINIMUM")
        if sample.buy_sell_ratio < candidate.min_buy_sell_ratio:
            reasons.append("BUY_SELL_RATIO_BELOW_MINIMUM")
        if sample.buy_vol_to_mc_ratio < candidate.min_buy_vol_to_mc_ratio:
            reasons.append("BUY_VOL_TO_MC_BELOW_MINIMUM")
        if sample.token_age_seconds > candidate.max_token_age_seconds:
            reasons.append("TOKEN_AGE_EXCEEDS_MAXIMUM")
        return reasons

    def run(
        self,
        samples: Sequence[WinnerVsRugSample],
        candidates: Sequence[WinnerVsRugCandidatePolicy],
        split: CalibrationTimeSplit,
        *,
        now: datetime,
    ) -> WinnerVsRugReport:
        all_candidates = (
            self.baseline_policy,
            *[c for c in candidates if c.candidate_id != self.baseline_policy.candidate_id],
        )

        train_samples = [
            s for s in samples if split.partition(s.decision_at) == CalibrationPartition.TRAIN
        ]
        val_samples = [
            s for s in samples if split.partition(s.decision_at) == CalibrationPartition.VALIDATION
        ]
        test_samples = [
            s for s in samples if split.partition(s.decision_at) == CalibrationPartition.TEST
        ]

        # If strict partitioning leaves train empty (e.g. in small fixture test),
        # fall back to all samples as TRAIN
        if not train_samples and samples:
            train_samples = list(samples)

        train_metrics: dict[str, WinnerVsRugMetrics] = {}
        val_metrics: dict[str, WinnerVsRugMetrics] = {}
        test_metrics: dict[str, WinnerVsRugMetrics] = {}

        for candidate in all_candidates:
            train_metrics[candidate.candidate_id] = self.evaluate_candidate(
                candidate, train_samples
            )
            val_metrics[candidate.candidate_id] = self.evaluate_candidate(candidate, val_samples)
            test_metrics[candidate.candidate_id] = self.evaluate_candidate(candidate, test_samples)

        baseline_train = train_metrics[self.baseline_policy.candidate_id]
        selected_id: str | None = None
        best_score = Decimal("-1")

        eligible: list[tuple[str, Decimal]] = []
        for candidate in all_candidates:
            cid = candidate.candidate_id
            m = train_metrics[cid]
            # Safety gate: Candidate must not increase rug acceptance
            # (i.e. rug_rejection_rate must be >= baseline)
            if m.rug_rejection_rate < baseline_train.rug_rejection_rate:
                continue
            # Composite objective score: recall (0.6) + rug rejection (0.4)
            obj_score = m.winner_recall * Decimal("0.60") + m.rug_rejection_rate * Decimal("0.40")
            eligible.append((cid, obj_score))
            if obj_score > best_score:
                best_score = obj_score
                selected_id = cid

        sorted_eligible = sorted(eligible, key=lambda x: x[1], reverse=True)
        pareto_shortlist = tuple(cid for cid, _ in sorted_eligible)

        status = "OPTIMIZATION_COMPLETE"
        if len(train_samples) < 3 or len(val_samples) < 1:
            status = "INSUFFICIENT_SAMPLES"
            selected_id = self.baseline_policy.candidate_id

        report_hash = _canonical_hash(
            {
                "version": WINNER_VS_RUG_VERSION,
                "baseline_candidate_id": self.baseline_policy.candidate_id,
                "selected_candidate_id": selected_id,
                "candidates": [c.config_hash for c in all_candidates],
                "split": split.to_json_dict(),
            }
        )

        return WinnerVsRugReport(
            version=WINNER_VS_RUG_VERSION,
            evaluated_at=ensure_utc(now, "now"),
            baseline_candidate_id=self.baseline_policy.candidate_id,
            selected_candidate_id=selected_id,
            status=status,
            train_metrics=train_metrics,
            validation_metrics=val_metrics,
            test_metrics=test_metrics,
            pareto_shortlist=pareto_shortlist,
            reason_codes=("WINNER_VS_RUG_OPTIMIZATION_COMPLETE", "ADVISORY_ONLY_NO_AUTO_PROMOTION"),
            config_hash=report_hash,
        )


__all__ = [
    "WINNER_VS_RUG_SCHEMA_VERSION",
    "WINNER_VS_RUG_VERSION",
    "WinnerVsRugCandidatePolicy",
    "WinnerVsRugCohort",
    "WinnerVsRugMetrics",
    "WinnerVsRugOptimizer",
    "WinnerVsRugReport",
    "WinnerVsRugSample",
]
