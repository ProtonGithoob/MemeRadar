"""Provider-free, deterministic backtesting over normalized replay artifacts.

The backtester is intentionally downstream of ``replay_harness``.  It consumes
immutable strategy and future-outcome projections, reuses the paper fill model
for fee/slippage arithmetic, and emits research metrics only.  It has no
provider, persistence, signing or transaction-submission authority.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    FeatureSnapshot,
    Freshness,
    PaperOrderSide,
    Provenance,
    QualityState,
    ReasonCode,
    RiskDisposition,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .paper_execution import PaperExecutionRejected, PaperFillModel
from .provider_contracts import QuoteSnapshot
from .replay_harness import (
    OutcomeHorizonLabel,
    ReplayCheckpointResult,
    ResearchReplayManifest,
    ResearchReplayResult,
)

BACKTESTING_VERSION = "research-backtest-v1"
BACKTEST_SCHEMA_VERSION = 1
_QUOTE_MINT = "So11111111111111111111111111111111111111112"
_FALLBACK_QUOTE_MINT = "11111111111111111111111111111111"
_DEFAULT_HORIZON_SECONDS: Mapping[str, Decimal] = MappingProxyType(
    {
        "1m": Decimal("60"),
        "5m": Decimal("300"),
        "15m": Decimal("900"),
        "1h": Decimal("3600"),
        "6h": Decimal("21600"),
        "24h": Decimal("86400"),
    }
)
_SCORE_BUCKETS = ("0-25", "25-50", "50-75", "75-100")
_SECRET_KEY_PARTS = frozenset(
    {
        "apikey",
        "accesskey",
        "secret",
        "private" + "key",
        "seed" + "phrase",
        "password",
        "cookie",
        "authorization",
        "bottoken",
        "sessiontoken",
    }
)
_NO_EXIT_ACTIONS = frozenset({"HOLD", "NONE", "NO_EXIT", "NOEXIT"})


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonical(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, ReasonCode):
        return {
            "code": value.code,
            "detail": value.detail,
            "evidence_refs": list(value.evidence_refs),
        }
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("backtest artifacts cannot contain non-finite numbers")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


def _is_sensitive_field(value: object) -> bool:
    normalized = "".join(character for character in str(value).lower() if character.isalnum())
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _assert_safe_mapping(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_sensitive_field(key):
                raise ValueError("backtest artifact contains a secret-shaped field")
            _assert_safe_mapping(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _assert_safe_mapping(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("backtest artifact cannot contain non-finite numbers")


def _positive(value: object, field_name: str) -> Decimal:
    normalized = to_decimal(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _non_negative(value: object, field_name: str) -> Decimal:
    normalized = to_decimal(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must not be negative")
    return normalized


def _optional_positive(value: object | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _positive(value, field_name)


def _horizon_key(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return f"{rendered}x"


def _score_bucket(value: Decimal) -> str:
    if value < Decimal("25"):
        return "0-25"
    if value < Decimal("50"):
        return "25-50"
    if value < Decimal("75"):
        return "50-75"
    return "75-100"


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    return None if not values else sum(values, Decimal("0")) / Decimal(len(values))


def _early_outcome_json(item: ReplayCheckpointResult) -> Mapping[str, object] | None:
    if item.early_outcome is None:
        return None
    return item.early_outcome.to_json_dict()


def _seconds_to_delta(seconds: Decimal) -> timedelta:
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    microseconds = int(seconds * Decimal("1000000"))
    if microseconds <= 0:
        return timedelta(0)
    return timedelta(microseconds=microseconds)


@dataclass(frozen=True, slots=True)
class BacktestPolicy:
    """Versioned entry, exit and paper-fill assumptions for one research run."""

    entry_score_threshold: Decimal = Decimal("50")
    min_confidence: Decimal = Decimal("0.60")
    outcome_horizon: str = "24h"
    take_profit_multiple: Decimal | None = Decimal("1.5")
    stop_loss_fraction: Decimal | None = Decimal("0.5")
    allow_horizon_exit: bool = True
    exit_on_rug: bool = False
    exit_on_liquidity_collapse: bool = False
    exit_on_creator_dump: bool = False
    exit_on_paper_exit: bool = False
    position_notional: Decimal = Decimal("100")
    initial_capital: Decimal = Decimal("10000")
    fee_bps: Decimal = Decimal("30")
    slippage_bps: Decimal = Decimal("25")
    entry_fill_ratio: Decimal = Decimal("1")
    max_liquidity_fraction: Decimal | None = Decimal("0.01")
    horizon_duration_seconds: Decimal | None = None
    fee_currency: str = "USD"
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False
    version: str = "backtest-policy-v1"
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entry_score_threshold",
            bounded_decimal(
                self.entry_score_threshold,
                "entry_score_threshold",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(
            self,
            "min_confidence",
            bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "outcome_horizon",
            require_text(self.outcome_horizon, "outcome_horizon", max_length=16),
        )
        target = _optional_positive(self.take_profit_multiple, "take_profit_multiple")
        if target is not None and target <= Decimal("1"):
            raise ValueError("take_profit_multiple must be greater than one")
        object.__setattr__(self, "take_profit_multiple", target)
        stop = _optional_positive(self.stop_loss_fraction, "stop_loss_fraction")
        if stop is not None and stop >= Decimal("1"):
            raise ValueError("stop_loss_fraction must be below one")
        object.__setattr__(self, "stop_loss_fraction", stop)
        for field_name in (
            "allow_horizon_exit",
            "exit_on_rug",
            "exit_on_liquidity_collapse",
            "exit_on_creator_dump",
            "exit_on_paper_exit",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        object.__setattr__(
            self,
            "position_notional",
            _positive(self.position_notional, "position_notional"),
        )
        object.__setattr__(
            self,
            "initial_capital",
            _positive(self.initial_capital, "initial_capital"),
        )
        for field_name in ("fee_bps", "slippage_bps"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0 or value >= Decimal("10000"):
                raise ValueError(f"{field_name} must be between 0 and 10000")
            object.__setattr__(self, field_name, value)
        fill_ratio = bounded_decimal(
            self.entry_fill_ratio,
            "entry_fill_ratio",
            Decimal("0"),
            Decimal("1"),
        )
        if fill_ratio == 0:
            raise ValueError("entry_fill_ratio must be positive")
        object.__setattr__(self, "entry_fill_ratio", fill_ratio)
        liquidity_fraction = self.max_liquidity_fraction
        if liquidity_fraction is not None:
            liquidity_fraction = bounded_decimal(
                liquidity_fraction,
                "max_liquidity_fraction",
                Decimal("0"),
                Decimal("1"),
            )
            if liquidity_fraction == 0:
                raise ValueError("max_liquidity_fraction must be positive when configured")
        object.__setattr__(self, "max_liquidity_fraction", liquidity_fraction)
        object.__setattr__(
            self,
            "horizon_duration_seconds",
            _optional_positive(self.horizon_duration_seconds, "horizon_duration_seconds"),
        )
        object.__setattr__(self, "fee_currency", require_text(self.fee_currency, "fee_currency"))
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} must remain at its protected value")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "config_hash", _digest(self._config_dict()))

    def _config_dict(self) -> dict[str, object]:
        return {
            "entry_score_threshold": self.entry_score_threshold,
            "min_confidence": self.min_confidence,
            "outcome_horizon": self.outcome_horizon,
            "take_profit_multiple": self.take_profit_multiple,
            "stop_loss_fraction": self.stop_loss_fraction,
            "allow_horizon_exit": self.allow_horizon_exit,
            "exit_on_rug": self.exit_on_rug,
            "exit_on_liquidity_collapse": self.exit_on_liquidity_collapse,
            "exit_on_creator_dump": self.exit_on_creator_dump,
            "exit_on_paper_exit": self.exit_on_paper_exit,
            "position_notional": self.position_notional,
            "initial_capital": self.initial_capital,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "entry_fill_ratio": self.entry_fill_ratio,
            "max_liquidity_fraction": self.max_liquidity_fraction,
            "horizon_duration_seconds": self.horizon_duration_seconds,
            "fee_currency": self.fee_currency,
            "analysis_only": self.analysis_only,
            "paper_trading": self.paper_trading,
            "manual_execution": self.manual_execution,
            "auto_execution": self.auto_execution,
            "version": self.version,
        }

    def to_json_dict(self) -> dict[str, object]:
        result = self._config_dict()
        result["config_hash"] = self.config_hash
        return result

    def execution_eligible(self, at: datetime) -> bool:
        """Backtest policies never authorize execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class BacktestManifest:
    """Pinned replay and backtest identities carried by every report."""

    replay_manifest: ResearchReplayManifest
    dataset_digest: str
    policy_version: str
    policy_config_hash: str
    fill_model_version: str
    schema_version: int = BACKTEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.replay_manifest, ResearchReplayManifest):
            raise TypeError("replay_manifest must be a ResearchReplayManifest")
        object.__setattr__(
            self,
            "dataset_digest",
            require_text(self.dataset_digest, "dataset_digest"),
        )
        if (
            self.replay_manifest.dataset_digest is not None
            and self.replay_manifest.dataset_digest != self.dataset_digest
        ):
            raise ValueError("replay manifest dataset_digest does not match backtest dataset")
        for field_name in ("policy_version", "policy_config_hash", "fill_model_version"):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=128),
            )
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version != BACKTEST_SCHEMA_VERSION
        ):
            raise ValueError("unsupported backtest manifest schema version")

    @property
    def dataset_id(self) -> str:
        return self.replay_manifest.dataset_id

    @property
    def dataset_version(self) -> str:
        return self.replay_manifest.dataset_version

    @property
    def strategy_name(self) -> str:
        return self.replay_manifest.strategy_name

    @property
    def strategy_version(self) -> str:
        return self.replay_manifest.strategy_version

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "dataset_digest": self.dataset_digest,
            "replay_manifest": self.replay_manifest.to_json_dict(),
            "policy_version": self.policy_version,
            "policy_config_hash": self.policy_config_hash,
            "fill_model_version": self.fill_model_version,
        }


@dataclass(frozen=True, slots=True)
class BacktestSegmentKey:
    """Stable research dimensions for one backtest projection."""

    launch_venue: str
    liquidity_band: str
    token_age_band: str
    market_regime: str
    social_velocity_band: str
    smart_wallet_confluence: str

    def __post_init__(self) -> None:
        for field_name in (
            "launch_venue",
            "liquidity_band",
            "token_age_band",
            "market_regime",
            "social_velocity_band",
            "smart_wallet_confluence",
        ):
            value = require_text(getattr(self, field_name), field_name, max_length=64).lower()
            object.__setattr__(self, field_name, value)

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.launch_venue,
                self.liquidity_band,
                self.token_age_band,
                self.market_regime,
                self.social_velocity_band,
                self.smart_wallet_confluence,
            )
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "launch_venue": self.launch_venue,
            "liquidity_band": self.liquidity_band,
            "token_age_band": self.token_age_band,
            "market_regime": self.market_regime,
            "social_velocity_band": self.social_velocity_band,
            "smart_wallet_confluence": self.smart_wallet_confluence,
        }


@dataclass(frozen=True, slots=True)
class BacktestSkippedSignal:
    """Auditable entry rejection or safely unpriced eligible signal."""

    checkpoint_id: UUID
    token_id: UUID
    signal_at: datetime
    stage: str
    score: Decimal | None
    confidence: Decimal | None
    segment_key: BacktestSegmentKey
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...] = ()
    early_outcome: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("checkpoint_id and token_id must be UUID values")
        object.__setattr__(self, "signal_at", ensure_utc(self.signal_at, "signal_at"))
        stage = require_text(self.stage, "stage", max_length=16).upper()
        if stage not in {"ENTRY", "EXIT"}:
            raise ValueError("stage must be ENTRY or EXIT")
        object.__setattr__(self, "stage", stage)
        if self.score is not None:
            object.__setattr__(
                self,
                "score",
                bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
            )
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
            )
        if not isinstance(self.segment_key, BacktestSegmentKey):
            raise TypeError("segment_key must be a BacktestSegmentKey")
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
        if self.early_outcome is not None:
            if not isinstance(self.early_outcome, Mapping):
                raise TypeError("early_outcome must be a mapping or None")
            object.__setattr__(self, "early_outcome", MappingProxyType(dict(self.early_outcome)))

    def to_json_dict(self) -> dict[str, object]:
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "token_id": str(self.token_id),
            "signal_at": self.signal_at.isoformat(),
            "stage": self.stage,
            "score": None if self.score is None else str(self.score),
            "confidence": None if self.confidence is None else str(self.confidence),
            "segment": self.segment_key.to_json_dict(),
            "reason_codes": _canonical(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
            "early_outcome": _canonical(self.early_outcome),
        }


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    """One fully priced fixed-notional paper trade in a research report."""

    id: UUID
    checkpoint_id: UUID
    token_id: UUID
    signal_at: datetime
    exit_at: datetime
    outcome_horizon: str
    exit_reason: str
    score: Decimal
    confidence: Decimal
    segment_key: BacktestSegmentKey
    baseline_price: Decimal
    exit_multiple: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_quantity: Decimal
    entry_cash: Decimal
    exit_cash: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    total_fees: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    gross_return: Decimal
    net_return: Decimal
    slippage_bps: Decimal
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    early_outcome: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "checkpoint_id", "token_id"):
            if not isinstance(getattr(self, field_name), UUID):
                raise TypeError(f"{field_name} must be a UUID")
        signal_at = ensure_utc(self.signal_at, "signal_at")
        exit_at = ensure_utc(self.exit_at, "exit_at")
        if exit_at < signal_at:
            raise ValueError("exit_at must not precede signal_at")
        object.__setattr__(self, "signal_at", signal_at)
        object.__setattr__(self, "exit_at", exit_at)
        object.__setattr__(
            self,
            "outcome_horizon",
            require_text(self.outcome_horizon, "outcome_horizon", max_length=16),
        )
        object.__setattr__(self, "exit_reason", require_text(self.exit_reason, "exit_reason"))
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
        if not isinstance(self.segment_key, BacktestSegmentKey):
            raise TypeError("segment_key must be a BacktestSegmentKey")
        for field_name in (
            "baseline_price",
            "exit_multiple",
            "entry_price",
            "exit_price",
            "entry_quantity",
            "entry_cash",
            "exit_cash",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive(getattr(self, field_name), field_name),
            )
        for field_name in ("entry_fee", "exit_fee", "total_fees"):
            object.__setattr__(
                self,
                field_name,
                _non_negative(getattr(self, field_name), field_name),
            )
        if self.total_fees != self.entry_fee + self.exit_fee:
            raise ValueError("total_fees must equal entry_fee plus exit_fee")
        for field_name in ("gross_pnl", "net_pnl", "gross_return", "net_return"):
            object.__setattr__(self, field_name, to_decimal(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "slippage_bps",
            to_decimal(self.slippage_bps, "slippage_bps"),
        )
        if self.slippage_bps < 0 or self.slippage_bps >= Decimal("10000"):
            raise ValueError("slippage_bps must be between 0 and 10000")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
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
        if self.early_outcome is not None:
            if not isinstance(self.early_outcome, Mapping):
                raise TypeError("early_outcome must be a mapping or None")
            object.__setattr__(self, "early_outcome", MappingProxyType(dict(self.early_outcome)))

    @property
    def trade_id(self) -> UUID:
        return self.id

    def to_json_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "checkpoint_id": str(self.checkpoint_id),
            "token_id": str(self.token_id),
            "signal_at": self.signal_at.isoformat(),
            "exit_at": self.exit_at.isoformat(),
            "outcome_horizon": self.outcome_horizon,
            "exit_reason": self.exit_reason,
            "score": str(self.score),
            "confidence": str(self.confidence),
            "segment": self.segment_key.to_json_dict(),
            "baseline_price": str(self.baseline_price),
            "exit_multiple": str(self.exit_multiple),
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "entry_quantity": str(self.entry_quantity),
            "entry_cash": str(self.entry_cash),
            "exit_cash": str(self.exit_cash),
            "entry_fee": str(self.entry_fee),
            "exit_fee": str(self.exit_fee),
            "total_fees": str(self.total_fees),
            "gross_pnl": str(self.gross_pnl),
            "net_pnl": str(self.net_pnl),
            "gross_return": str(self.gross_return),
            "net_return": str(self.net_return),
            "slippage_bps": str(self.slippage_bps),
            "quality_state": self.quality_state.value,
            "reason_codes": _canonical(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
            "early_outcome": _canonical(self.early_outcome),
        }


@dataclass(frozen=True, slots=True)
class BacktestScoreBucket:
    """Calibration metrics for one deterministic AlphaScore bucket."""

    bucket: str
    signal_count: int
    executed_trade_count: int
    skipped_signal_count: int
    win_count: int
    precision: Decimal | None
    hit_rate: Decimal | None
    mean_score: Decimal | None
    mean_net_return: Decimal | None
    expectancy: Decimal | None

    def __post_init__(self) -> None:
        if self.bucket not in _SCORE_BUCKETS:
            raise ValueError("unsupported score bucket")
        for field_name in (
            "signal_count",
            "executed_trade_count",
            "skipped_signal_count",
            "win_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.executed_trade_count + self.skipped_signal_count != self.signal_count:
            raise ValueError("score bucket counts must balance")
        if self.win_count > self.executed_trade_count:
            raise ValueError("win_count must not exceed executed_trade_count")
        for field_name in ("precision", "hit_rate"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in ("mean_score", "mean_net_return", "expectancy"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))

    def to_json_dict(self) -> dict[str, object]:
        return {
            "bucket": self.bucket,
            "signal_count": self.signal_count,
            "executed_trade_count": self.executed_trade_count,
            "skipped_signal_count": self.skipped_signal_count,
            "win_count": self.win_count,
            "precision": None if self.precision is None else str(self.precision),
            "hit_rate": None if self.hit_rate is None else str(self.hit_rate),
            "mean_score": None if self.mean_score is None else str(self.mean_score),
            "mean_net_return": None
            if self.mean_net_return is None
            else str(self.mean_net_return),
            "expectancy": None if self.expectancy is None else str(self.expectancy),
        }


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Aggregate backtest performance metrics with explicit empty-sample state."""

    checkpoint_count: int
    entry_rejected_count: int
    signal_count: int
    executed_trade_count: int
    skipped_signal_count: int
    win_count: int
    loss_count: int
    precision: Decimal | None
    hit_rate: Decimal | None
    total_net_pnl: Decimal
    average_net_pnl: Decimal | None
    total_net_return: Decimal
    average_net_return: Decimal | None
    expectancy: Decimal | None
    expectancy_pnl: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    max_drawdown_amount: Decimal
    score_buckets: tuple[BacktestScoreBucket, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "checkpoint_count",
            "entry_rejected_count",
            "signal_count",
            "executed_trade_count",
            "skipped_signal_count",
            "win_count",
            "loss_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.win_count + self.loss_count != self.executed_trade_count:
            raise ValueError("win/loss counts must balance executed trades")
        if self.executed_trade_count + self.skipped_signal_count != self.signal_count:
            raise ValueError("trade/skip counts must balance signals")
        for field_name in ("precision", "hit_rate"):
            value = getattr(self, field_name)
            if value is not None:
                bounded = bounded_decimal(value, field_name, Decimal("0"), Decimal("1"))
                object.__setattr__(self, field_name, bounded)
        max_drawdown = _non_negative(self.max_drawdown, "max_drawdown")
        object.__setattr__(self, "max_drawdown", max_drawdown)
        for field_name in (
            "total_net_pnl",
            "total_net_return",
            "gross_profit",
            "gross_loss",
            "max_drawdown_amount",
        ):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0 and field_name in {"gross_profit", "gross_loss", "max_drawdown_amount"}:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "average_net_pnl",
            "average_net_return",
            "expectancy",
            "expectancy_pnl",
            "profit_factor",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        buckets = tuple(self.score_buckets)
        if any(not isinstance(value, BacktestScoreBucket) for value in buckets):
            raise TypeError("score_buckets must contain BacktestScoreBucket values")
        if tuple(sorted(buckets, key=lambda value: _SCORE_BUCKETS.index(value.bucket))) != buckets:
            raise ValueError("score_buckets must be sorted")
        object.__setattr__(self, "score_buckets", buckets)

    @property
    def trade_count(self) -> int:
        return self.executed_trade_count

    @property
    def calibration_by_score_bucket(self) -> tuple[BacktestScoreBucket, ...]:
        return self.score_buckets

    def to_json_dict(self) -> dict[str, object]:
        return {
            "checkpoint_count": self.checkpoint_count,
            "entry_rejected_count": self.entry_rejected_count,
            "signal_count": self.signal_count,
            "executed_trade_count": self.executed_trade_count,
            "skipped_signal_count": self.skipped_signal_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "precision": None if self.precision is None else str(self.precision),
            "hit_rate": None if self.hit_rate is None else str(self.hit_rate),
            "total_net_pnl": str(self.total_net_pnl),
            "average_net_pnl": None
            if self.average_net_pnl is None
            else str(self.average_net_pnl),
            "total_net_return": str(self.total_net_return),
            "average_net_return": None
            if self.average_net_return is None
            else str(self.average_net_return),
            "expectancy": None if self.expectancy is None else str(self.expectancy),
            "expectancy_pnl": None
            if self.expectancy_pnl is None
            else str(self.expectancy_pnl),
            "gross_profit": str(self.gross_profit),
            "gross_loss": str(self.gross_loss),
            "profit_factor": None if self.profit_factor is None else str(self.profit_factor),
            "max_drawdown": str(self.max_drawdown),
            "max_drawdown_amount": str(self.max_drawdown_amount),
            "score_buckets": [value.to_json_dict() for value in self.score_buckets],
        }


@dataclass(frozen=True, slots=True)
class BacktestSegment:
    """Metrics for one launch/liquidity/age/regime/social/wallet segment."""

    key: BacktestSegmentKey
    metrics: BacktestMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.key, BacktestSegmentKey):
            raise TypeError("key must be a BacktestSegmentKey")
        if not isinstance(self.metrics, BacktestMetrics):
            raise TypeError("metrics must be BacktestMetrics")

    def to_json_dict(self) -> dict[str, object]:
        return {"key": self.key.to_json_dict(), "metrics": self.metrics.to_json_dict()}


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Deterministic, redacted backtest artifact; never an execution command."""

    manifest: BacktestManifest
    policy: BacktestPolicy
    metrics: BacktestMetrics
    trades: tuple[BacktestTrade, ...]
    skips: tuple[BacktestSkippedSignal, ...]
    segments: tuple[BacktestSegment, ...]
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, BacktestManifest):
            raise TypeError("manifest must be a BacktestManifest")
        if not isinstance(self.policy, BacktestPolicy):
            raise TypeError("policy must be a BacktestPolicy")
        if not isinstance(self.metrics, BacktestMetrics):
            raise TypeError("metrics must be BacktestMetrics")
        trades = tuple(self.trades)
        if any(not isinstance(value, BacktestTrade) for value in trades):
            raise TypeError("trades must contain BacktestTrade values")
        if tuple(sorted(trades, key=lambda value: (value.signal_at, str(value.id)))) != trades:
            raise ValueError("trades must be ordered by signal time and ID")
        skips = tuple(self.skips)
        if any(not isinstance(value, BacktestSkippedSignal) for value in skips):
            raise TypeError("skips must contain BacktestSkippedSignal values")
        if tuple(
            sorted(
                skips,
                key=lambda value: (value.signal_at, value.stage, str(value.checkpoint_id)),
            )
        ) != skips:
            raise ValueError("skips must be ordered deterministically")
        segments = tuple(self.segments)
        if any(not isinstance(value, BacktestSegment) for value in segments):
            raise TypeError("segments must contain BacktestSegment values")
        if tuple(sorted(segments, key=lambda value: value.key.key)) != segments:
            raise ValueError("segments must be sorted by key")
        object.__setattr__(self, "trades", trades)
        object.__setattr__(self, "skips", skips)
        object.__setattr__(self, "segments", segments)
        material = {
            "schema": BACKTESTING_VERSION,
            "manifest": self.manifest.to_json_dict(),
            "policy": self.policy.to_json_dict(),
            "metrics": self.metrics.to_json_dict(),
            "trades": [value.to_json_dict() for value in trades],
            "skips": [value.to_json_dict() for value in skips],
            "segments": [value.to_json_dict() for value in segments],
        }
        _assert_safe_mapping(material)
        object.__setattr__(self, "artifact_digest", _digest(material))

    def execution_eligible(self, at: datetime) -> bool:
        """Reports are research evidence and can never authorize execution."""

        del at
        return False

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema": BACKTESTING_VERSION,
            "artifact_digest": self.artifact_digest,
            "manifest": self.manifest.to_json_dict(),
            "policy": self.policy.to_json_dict(),
            "modes": {
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            "metrics": self.metrics.to_json_dict(),
            "trades": [value.to_json_dict() for value in self.trades],
            "skips": [value.to_json_dict() for value in self.skips],
            "segments": [value.to_json_dict() for value in self.segments],
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_json_dict())

    def to_csv(self) -> str:
        """Return one deterministic flat row per trade or skipped signal."""

        fieldnames = (
            "dataset_digest",
            "policy_version",
            "policy_config_hash",
            "row_type",
            "stage",
            "checkpoint_id",
            "token_id",
            "signal_at",
            "exit_at",
            "outcome_horizon",
            "exit_reason",
            "score",
            "confidence",
            "segment_key",
            "net_pnl",
            "net_return",
            "early_outcome",
            "reason_codes",
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for trade in self.trades:
            writer.writerow(
                {
                    "dataset_digest": self.manifest.dataset_digest,
                    "policy_version": self.manifest.policy_version,
                    "policy_config_hash": self.manifest.policy_config_hash,
                    "row_type": "TRADE",
                    "stage": None,
                    "checkpoint_id": str(trade.checkpoint_id),
                    "token_id": str(trade.token_id),
                    "signal_at": trade.signal_at.isoformat(),
                    "exit_at": trade.exit_at.isoformat(),
                    "outcome_horizon": trade.outcome_horizon,
                    "exit_reason": trade.exit_reason,
                    "score": str(trade.score),
                    "confidence": str(trade.confidence),
                    "segment_key": trade.segment_key.key,
                    "net_pnl": str(trade.net_pnl),
                    "net_return": str(trade.net_return),
                    "early_outcome": (
                        _canonical_json(trade.early_outcome)
                        if trade.early_outcome is not None
                        else None
                    ),
                    "reason_codes": ";".join(reason.code for reason in trade.reason_codes),
                }
            )
        for skip in self.skips:
            writer.writerow(
                {
                    "dataset_digest": self.manifest.dataset_digest,
                    "policy_version": self.manifest.policy_version,
                    "policy_config_hash": self.manifest.policy_config_hash,
                    "row_type": "SKIP",
                    "stage": skip.stage,
                    "checkpoint_id": str(skip.checkpoint_id),
                    "token_id": str(skip.token_id),
                    "signal_at": skip.signal_at.isoformat(),
                    "exit_at": None,
                    "outcome_horizon": self.policy.outcome_horizon,
                    "exit_reason": None,
                    "score": None if skip.score is None else str(skip.score),
                    "confidence": None if skip.confidence is None else str(skip.confidence),
                    "segment_key": skip.segment_key.key,
                    "net_pnl": None,
                    "net_return": None,
                    "early_outcome": (
                        _canonical_json(skip.early_outcome)
                        if skip.early_outcome is not None
                        else None
                    ),
                    "reason_codes": ";".join(reason.code for reason in skip.reason_codes),
                }
            )
        return output.getvalue()


@dataclass(frozen=True, slots=True)
class _ExitPlan:
    exit_reason: str
    exit_at: datetime
    exit_multiple: Decimal
    evidence_refs: tuple[str, ...]


class BacktestHarness:
    """Apply a deterministic backtest policy to one replay result."""

    def __init__(self, *, fill_model: PaperFillModel | None = None) -> None:
        self.fill_model = fill_model or PaperFillModel()
        if not isinstance(self.fill_model, PaperFillModel):
            raise TypeError("fill_model must be a PaperFillModel")

    def run(
        self,
        replay: ResearchReplayResult,
        *,
        policy: BacktestPolicy | None = None,
    ) -> BacktestReport:
        if not isinstance(replay, ResearchReplayResult):
            raise TypeError("replay must be a ResearchReplayResult")
        selected_policy = policy or BacktestPolicy()
        if not isinstance(selected_policy, BacktestPolicy):
            raise TypeError("policy must be a BacktestPolicy")
        if (
            replay.manifest.dataset_digest is not None
            and replay.manifest.dataset_digest != replay.dataset_digest
        ):
            raise ValueError("replay manifest dataset_digest does not match replay result")

        ordered = tuple(
            sorted(
                replay.checkpoints,
                key=lambda value: (value.checkpoint.as_of, str(value.checkpoint.id)),
            )
        )
        trades: list[BacktestTrade] = []
        skips: list[BacktestSkippedSignal] = []
        segment_checkpoints: dict[str, tuple[BacktestSegmentKey, int]] = {}
        for item in ordered:
            self._validate_checkpoint(item, replay.manifest)
            segment = self._segment_key(item, replay.manifest)
            existing = segment_checkpoints.get(segment.key)
            segment_checkpoints[segment.key] = (
                segment,
                1 if existing is None else existing[1] + 1,
            )
            entry_errors = self._entry_errors(item, replay.manifest, selected_policy)
            snapshot = item.strategy_snapshot
            if entry_errors:
                skips.append(
                    BacktestSkippedSignal(
                        checkpoint_id=item.checkpoint.id,
                        token_id=item.checkpoint.token_id,
                        signal_at=item.checkpoint.as_of,
                        stage="ENTRY",
                        score=None if snapshot is None else snapshot.suggested_score,
                        confidence=None if snapshot is None else snapshot.confidence,
                        segment_key=segment,
                        reason_codes=entry_errors,
                        evidence_refs=()
                        if snapshot is None
                        else snapshot.evidence_refs,
                        early_outcome=_early_outcome_json(item),
                    )
                )
                continue
            assert snapshot is not None
            horizon = next(
                (
                    value
                    for value in item.outcome.horizons
                    if value.horizon == selected_policy.outcome_horizon
                ),
                None,
            )
            exit_plan, exit_errors = self._exit_plan(
                item,
                horizon,
                selected_policy,
            )
            if exit_errors:
                skips.append(
                    BacktestSkippedSignal(
                        checkpoint_id=item.checkpoint.id,
                        token_id=item.checkpoint.token_id,
                        signal_at=item.checkpoint.as_of,
                        stage="EXIT",
                        score=snapshot.suggested_score,
                        confidence=snapshot.confidence,
                        segment_key=segment,
                        reason_codes=exit_errors,
                        evidence_refs=item.outcome.evidence_refs,
                        early_outcome=_early_outcome_json(item),
                    )
                )
                continue
            assert exit_plan is not None
            try:
                trades.append(
                    self._simulate_trade(
                        replay=replay,
                        item=item,
                        horizon=horizon,
                        exit_plan=exit_plan,
                        policy=selected_policy,
                        segment=segment,
                    )
                )
            except (PaperExecutionRejected, ValueError) as exc:
                skips.append(
                    BacktestSkippedSignal(
                        checkpoint_id=item.checkpoint.id,
                        token_id=item.checkpoint.token_id,
                        signal_at=item.checkpoint.as_of,
                        stage="EXIT",
                        score=snapshot.suggested_score,
                        confidence=snapshot.confidence,
                        segment_key=segment,
                        reason_codes=(ReasonCode("BACKTEST_FILL_UNUSABLE", detail=str(exc)),),
                        evidence_refs=item.outcome.evidence_refs,
                        early_outcome=_early_outcome_json(item),
                    )
                )

        ordered_trades = tuple(sorted(trades, key=lambda value: (value.signal_at, str(value.id))))
        ordered_skips = tuple(
            sorted(
                skips,
                key=lambda value: (value.signal_at, value.stage, str(value.checkpoint_id)),
            )
        )
        metrics = _build_metrics(
            checkpoint_count=len(ordered),
            trades=ordered_trades,
            skips=ordered_skips,
            policy=selected_policy,
        )
        segments = tuple(
            BacktestSegment(
                key=segment,
                metrics=_build_metrics(
                    checkpoint_count=count,
                    trades=tuple(value for value in ordered_trades if value.segment_key == segment),
                    skips=tuple(value for value in ordered_skips if value.segment_key == segment),
                    policy=selected_policy,
                ),
            )
            for segment, count in sorted(
                segment_checkpoints.values(), key=lambda value: value[0].key
            )
        )
        manifest = BacktestManifest(
            replay_manifest=replay.manifest,
            dataset_digest=replay.dataset_digest,
            policy_version=selected_policy.version,
            policy_config_hash=selected_policy.config_hash,
            fill_model_version=self.fill_model.version,
        )
        return BacktestReport(
            manifest=manifest,
            policy=selected_policy,
            metrics=metrics,
            trades=ordered_trades,
            skips=ordered_skips,
            segments=segments,
        )

    def _validate_checkpoint(
        self,
        item: ReplayCheckpointResult,
        manifest: ResearchReplayManifest,
    ) -> None:
        checkpoint = item.checkpoint
        if checkpoint.as_of > manifest.as_of:
            raise ValueError("backtest checkpoint is outside replay event-time boundary")
        outcome = item.outcome
        if outcome.checkpoint_id != checkpoint.id:
            raise ValueError("outcome checkpoint_id does not match replay checkpoint")
        if outcome.token_id != checkpoint.token_id:
            raise ValueError("outcome token_id does not match replay checkpoint")
        if outcome.signal_at != checkpoint.as_of:
            raise ValueError("outcome signal_at does not match replay checkpoint")
        if set(item.included_event_ids).intersection(item.excluded_future_event_ids):
            raise ValueError("replay event cannot be both included and future-excluded")

    def _entry_errors(
        self,
        item: ReplayCheckpointResult,
        manifest: ResearchReplayManifest,
        policy: BacktestPolicy,
    ) -> tuple[ReasonCode, ...]:
        snapshot = item.strategy_snapshot
        reasons: list[ReasonCode] = []
        if snapshot is None:
            reasons.append(ReasonCode("STRATEGY_SNAPSHOT_MISSING"))
            return tuple(reasons)
        if not snapshot.advisory:
            reasons.append(ReasonCode("STRATEGY_NOT_ADVISORY"))
        if (
            snapshot.strategy_name != manifest.strategy_name
            or snapshot.strategy_version != manifest.strategy_version
        ):
            reasons.append(ReasonCode("STRATEGY_IDENTITY_MISMATCH"))
        if snapshot.candidate_id != item.checkpoint.candidate_id:
            reasons.append(ReasonCode("STRATEGY_CANDIDATE_MISMATCH"))
        if snapshot.as_of > item.checkpoint.as_of:
            reasons.append(ReasonCode("STRATEGY_FUTURE_EVIDENCE"))
        if not snapshot.freshness.is_fresh(item.checkpoint.as_of):
            reasons.append(ReasonCode("STRATEGY_NOT_FRESH"))
        if snapshot.suggested_score < policy.entry_score_threshold:
            reasons.append(ReasonCode("ENTRY_SCORE_BELOW_THRESHOLD"))
        if snapshot.confidence < policy.min_confidence:
            reasons.append(ReasonCode("ENTRY_CONFIDENCE_BELOW_THRESHOLD"))
        if snapshot.risk_disposition is not RiskDisposition.PASS:
            reasons.append(ReasonCode("RISK_NOT_PASS"))
        if snapshot.hard_blocks:
            reasons.append(ReasonCode("RISK_HARD_BLOCK"))
        if snapshot.config_hash != manifest.config_hash:
            reasons.append(ReasonCode("STRATEGY_CONFIG_MISMATCH"))
        feature = self._feature_snapshot(item, manifest.feature_window)
        if feature is None:
            reasons.append(ReasonCode("FEATURE_SNAPSHOT_MISSING"))
        else:
            if feature.candidate_id != item.checkpoint.candidate_id:
                reasons.append(ReasonCode("FEATURE_CANDIDATE_MISMATCH"))
            if feature.as_of > item.checkpoint.as_of:
                reasons.append(ReasonCode("FEATURE_FUTURE_EVIDENCE"))
            if not feature.freshness.is_fresh(item.checkpoint.as_of):
                reasons.append(ReasonCode("FEATURE_NOT_FRESH"))
            if feature.config_hash != manifest.config_hash:
                reasons.append(ReasonCode("FEATURE_CONFIG_MISMATCH"))
        risk = item.checkpoint.risk_assessment
        if risk is not None:
            if risk.id != snapshot.risk_assessment_id:
                reasons.append(ReasonCode("RISK_SNAPSHOT_MISMATCH"))
            if not risk.execution_eligible(item.checkpoint.as_of):
                reasons.append(ReasonCode("RISK_EVIDENCE_NOT_FRESH"))
        liquidity_fraction = policy.max_liquidity_fraction
        if liquidity_fraction is not None:
            liquidity = self._liquidity(item, manifest.feature_window)
            if liquidity is None:
                reasons.append(ReasonCode("LIQUIDITY_UNKNOWN"))
            elif policy.position_notional > liquidity * liquidity_fraction:
                reasons.append(ReasonCode("LIQUIDITY_CONSTRAINT"))
        return normalize_reason_codes(reasons)

    @staticmethod
    def _feature_snapshot(item: ReplayCheckpointResult, window: str) -> FeatureSnapshot | None:
        return next(
            (value for value in item.feature_snapshots if value.values.get("window") == window),
            None,
        )

    def _liquidity(self, item: ReplayCheckpointResult, window: str) -> Decimal | None:
        feature = self._feature_snapshot(item, window)
        if feature is not None:
            families = feature.values.get("families")
            if isinstance(families, Mapping):
                liquidity_family = families.get("liquidity")
                if isinstance(liquidity_family, Mapping):
                    for key in ("liquidity", "liquidity_usd", "liquidityUsd"):
                        raw = liquidity_family.get(key)
                        if raw is not None:
                            try:
                                value = to_decimal(raw, "liquidity")
                            except (TypeError, ValueError):
                                return None
                            return value if value > 0 else None
        correlation_window = item.correlation.windows.get(window)
        if correlation_window is None or correlation_window.liquidity is None:
            return None
        value = to_decimal(correlation_window.liquidity, "liquidity")
        return value if value > 0 else None

    @staticmethod
    def _segment_key(
        item: ReplayCheckpointResult,
        manifest: ResearchReplayManifest,
    ) -> BacktestSegmentKey:
        cohort = item.cohort
        window = item.correlation.windows.get(manifest.feature_window)
        regime = "unknown"
        if (
            window is not None
            and window.quality_state is QualityState.FRESH
            and window.net_flow is not None
        ):
            flow = to_decimal(window.net_flow, "market net flow")
            regime = "positive" if flow > 0 else "negative" if flow < 0 else "flat"
        return BacktestSegmentKey(
            launch_venue=item.checkpoint.venue if cohort is None else cohort.launch_venue,
            liquidity_band="unknown" if cohort is None else cohort.liquidity_band,
            token_age_band="unknown" if cohort is None else cohort.token_age_band,
            market_regime=regime,
            social_velocity_band="unknown" if cohort is None else cohort.social_velocity_band,
            smart_wallet_confluence="unknown"
            if cohort is None
            else cohort.smart_wallet_confluence,
        )

    def _exit_plan(
        self,
        item: ReplayCheckpointResult,
        horizon: OutcomeHorizonLabel | None,
        policy: BacktestPolicy,
    ) -> tuple[_ExitPlan | None, tuple[ReasonCode, ...]]:
        outcome = item.outcome
        if outcome.quality_state is not QualityState.FRESH:
            return None, (ReasonCode("OUTCOME_NOT_FRESH"),)
        if horizon is None:
            return None, (ReasonCode("OUTCOME_HORIZON_MISSING"),)
        if horizon.quality_state is not QualityState.FRESH:
            return None, (ReasonCode("OUTCOME_HORIZON_NOT_FRESH"),)
        baseline = outcome.baseline_price
        if baseline is None or baseline <= 0:
            return None, (ReasonCode("OUTCOME_BASELINE_PRICE_MISSING"),)

        safety_fields = (
            ("rugged", policy.exit_on_rug, "RUG_HORIZON"),
            (
                "liquidity_collapsed",
                policy.exit_on_liquidity_collapse,
                "LIQUIDITY_COLLAPSE_HORIZON",
            ),
            ("creator_dump", policy.exit_on_creator_dump, "CREATOR_DUMP_HORIZON"),
        )
        for field_name, enabled, reason in safety_fields:
            if not enabled:
                continue
            value = getattr(horizon, field_name)
            if value is None:
                return None, (ReasonCode("SAFETY_LABEL_UNKNOWN", detail=field_name),)
            if value is True:
                return self._horizon_exit(item, horizon, policy, reason)
        if policy.exit_on_paper_exit:
            action = horizon.paper_exit_action
            if action is None:
                return None, (ReasonCode("SAFETY_LABEL_UNKNOWN", detail="paper_exit_action"),)
            if action not in _NO_EXIT_ACTIONS:
                return self._horizon_exit(item, horizon, policy, "PAPER_EXIT_HORIZON")

        candidates: list[tuple[datetime, int, str, Decimal]] = []
        if policy.take_profit_multiple is not None:
            target = policy.take_profit_multiple
            assert target is not None
            target_key = _horizon_key(target)
            if target_key not in horizon.time_to_multiple:
                return None, (ReasonCode("TARGET_LABEL_MISSING", detail=target_key),)
            target_time = horizon.time_to_multiple[target_key]
            if target_time is not None:
                candidates.append(
                    (
                        item.checkpoint.as_of + _seconds_to_delta(target_time),
                        1,
                        "TAKE_PROFIT",
                        target,
                    )
                )
        if policy.stop_loss_fraction is not None and horizon.time_to_drawdown is not None:
            stop = policy.stop_loss_fraction
            assert stop is not None
            candidates.append(
                (
                    item.checkpoint.as_of + _seconds_to_delta(horizon.time_to_drawdown),
                    0,
                    "STOP_LOSS",
                    Decimal("1") - stop,
                )
            )
        if candidates:
            exit_at, _, reason, multiple = min(candidates, key=lambda value: (value[0], value[1]))
            return (
                _ExitPlan(
                    exit_reason=reason,
                    exit_at=exit_at,
                    exit_multiple=multiple,
                    evidence_refs=horizon.evidence_refs,
                ),
                (),
            )
        if not policy.allow_horizon_exit:
            return None, (ReasonCode("NO_EXIT_EVENT"),)
        return self._horizon_exit(item, horizon, policy, "HORIZON_CLOSE")

    def _horizon_exit(
        self,
        item: ReplayCheckpointResult,
        horizon: OutcomeHorizonLabel,
        policy: BacktestPolicy,
        reason: str,
    ) -> tuple[_ExitPlan | None, tuple[ReasonCode, ...]]:
        if horizon.forward_return is None:
            return None, (ReasonCode("FORWARD_PRICE_MISSING"),)
        multiple = Decimal("1") + horizon.forward_return
        if multiple <= 0:
            return None, (ReasonCode("FORWARD_PRICE_NON_POSITIVE"),)
        seconds = policy.horizon_duration_seconds
        if seconds is None:
            seconds = _DEFAULT_HORIZON_SECONDS.get(horizon.horizon)
        if seconds is None:
            return None, (ReasonCode("HORIZON_DURATION_UNKNOWN"),)
        return (
            _ExitPlan(
                exit_reason=reason,
                exit_at=item.checkpoint.as_of + _seconds_to_delta(seconds),
                exit_multiple=multiple,
                evidence_refs=horizon.evidence_refs,
            ),
            (),
        )

    def _simulate_trade(
        self,
        *,
        replay: ResearchReplayResult,
        item: ReplayCheckpointResult,
        horizon: OutcomeHorizonLabel | None,
        exit_plan: _ExitPlan,
        policy: BacktestPolicy,
        segment: BacktestSegmentKey,
    ) -> BacktestTrade:
        if horizon is None or item.outcome.baseline_price is None:
            raise PaperExecutionRejected("backtest price inputs are missing")
        baseline = item.outcome.baseline_price
        exit_price = baseline * exit_plan.exit_multiple
        if exit_price <= 0:
            raise PaperExecutionRejected("exit price is not positive")
        token = item.correlation.token
        quote_mint = _FALLBACK_QUOTE_MINT if token.mint_address == _QUOTE_MINT else _QUOTE_MINT
        entry_order_id = uuid5(
            NAMESPACE_URL,
            f"memeradar/backtest/{replay.dataset_digest}/{item.checkpoint.id}/{policy.config_hash}/entry",
        )
        exit_order_id = uuid5(
            NAMESPACE_URL,
            f"memeradar/backtest/{replay.dataset_digest}/{item.checkpoint.id}/{policy.config_hash}/exit",
        )
        entry_fill_id = uuid5(NAMESPACE_URL, f"{entry_order_id}/fill")
        exit_fill_id = uuid5(NAMESPACE_URL, f"{exit_order_id}/fill")
        entry_quote = self._quote(
            token_mint=token.mint_address,
            quote_mint=quote_mint,
            input_amount=policy.position_notional,
            output_amount=policy.position_notional / baseline,
            at=item.checkpoint.as_of,
            parser_version=replay.manifest.parser_version,
            source_id=f"{item.checkpoint.id}:entry",
        )
        entry_fill = self.fill_model.simulate(
            order_id=entry_order_id,
            side=PaperOrderSide.BUY,
            input_amount=policy.position_notional,
            quote=entry_quote,
            occurred_at=item.checkpoint.as_of,
            fee_bps=policy.fee_bps,
            slippage_bps=policy.slippage_bps,
            fill_ratio=policy.entry_fill_ratio,
            fee_currency=policy.fee_currency,
            fill_id=entry_fill_id,
        )
        exit_quote = self._quote(
            token_mint=token.mint_address,
            quote_mint=quote_mint,
            input_amount=entry_fill.quantity,
            output_amount=entry_fill.quantity * exit_price,
            at=exit_plan.exit_at,
            parser_version=replay.manifest.parser_version,
            source_id=f"{item.checkpoint.id}:exit",
        )
        exit_fill = self.fill_model.simulate(
            order_id=exit_order_id,
            side=PaperOrderSide.SELL,
            input_amount=entry_fill.quantity,
            quote=exit_quote,
            occurred_at=exit_plan.exit_at,
            fee_bps=policy.fee_bps,
            slippage_bps=policy.slippage_bps,
            fill_ratio=Decimal("1"),
            fee_currency=policy.fee_currency,
            fill_id=exit_fill_id,
        )
        entry_cash = -entry_fill.cash_delta
        exit_cash = exit_fill.cash_delta
        gross_pnl = exit_fill.gross_cash_amount - entry_fill.gross_cash_amount
        net_pnl = entry_fill.cash_delta + exit_fill.cash_delta
        strategy_refs = (
            ()
            if item.strategy_snapshot is None
            else item.strategy_snapshot.evidence_refs
        )
        evidence_refs = normalize_texts(
            (*strategy_refs, *item.outcome.evidence_refs, *horizon.evidence_refs),
            "evidence_refs",
        )
        return BacktestTrade(
            id=uuid5(
                NAMESPACE_URL,
                f"memeradar/backtest/{replay.dataset_digest}/{item.checkpoint.id}/{policy.config_hash}/trade",
            ),
            checkpoint_id=item.checkpoint.id,
            token_id=item.checkpoint.token_id,
            signal_at=item.checkpoint.as_of,
            exit_at=exit_plan.exit_at,
            outcome_horizon=horizon.horizon,
            exit_reason=exit_plan.exit_reason,
            score=item.strategy_snapshot.suggested_score
            if item.strategy_snapshot is not None
            else Decimal("0"),
            confidence=item.strategy_snapshot.confidence
            if item.strategy_snapshot is not None
            else Decimal("0"),
            segment_key=segment,
            baseline_price=baseline,
            exit_multiple=exit_plan.exit_multiple,
            entry_price=entry_fill.price,
            exit_price=exit_fill.price,
            entry_quantity=entry_fill.quantity,
            entry_cash=entry_cash,
            exit_cash=exit_cash,
            entry_fee=entry_fill.fee_amount,
            exit_fee=exit_fill.fee_amount,
            total_fees=entry_fill.fee_amount + exit_fill.fee_amount,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            gross_return=gross_pnl / entry_fill.gross_cash_amount,
            net_return=net_pnl / entry_cash,
            slippage_bps=policy.slippage_bps,
            quality_state=QualityState.FRESH,
            reason_codes=(
                ReasonCode("BACKTEST_TRADE_SIMULATED"),
                ReasonCode(exit_plan.exit_reason),
            ),
            evidence_refs=evidence_refs,
            early_outcome=_early_outcome_json(item),
        )

    @staticmethod
    def _quote(
        *,
        token_mint: str,
        quote_mint: str,
        input_amount: Decimal,
        output_amount: Decimal,
        at: datetime,
        parser_version: str,
        source_id: str,
    ) -> QuoteSnapshot:
        provenance = Provenance(
            provider="replay-backtest",
            source_id=source_id,
            observed_at=at,
            parser_version=parser_version,
        )
        return QuoteSnapshot(
            provenance=provenance,
            input_mint=quote_mint,
            output_mint=token_mint,
            input_amount=input_amount,
            output_amount=output_amount,
            price_impact_bps=Decimal("0"),
            route=("replay",),
            freshness=Freshness(
                as_of=at,
                expires_at=at + timedelta(microseconds=1),
                quality_state=QualityState.FRESH,
            ),
        )


def _build_score_buckets(
    trades: Sequence[BacktestTrade],
    skips: Sequence[BacktestSkippedSignal],
) -> tuple[BacktestScoreBucket, ...]:
    grouped_trades: dict[str, list[BacktestTrade]] = {key: [] for key in _SCORE_BUCKETS}
    grouped_skips: dict[str, list[BacktestSkippedSignal]] = {key: [] for key in _SCORE_BUCKETS}
    for trade in trades:
        grouped_trades[_score_bucket(trade.score)].append(trade)
    for skip in skips:
        if skip.stage == "EXIT" and skip.score is not None:
            grouped_skips[_score_bucket(skip.score)].append(skip)
    buckets: list[BacktestScoreBucket] = []
    for key in _SCORE_BUCKETS:
        bucket_trades = grouped_trades[key]
        bucket_skips = grouped_skips[key]
        signals = len(bucket_trades) + len(bucket_skips)
        wins = sum(value.net_pnl > 0 for value in bucket_trades)
        buckets.append(
            BacktestScoreBucket(
                bucket=key,
                signal_count=signals,
                executed_trade_count=len(bucket_trades),
                skipped_signal_count=len(bucket_skips),
                win_count=wins,
                precision=(
                    None
                    if not bucket_trades
                    else Decimal(wins) / Decimal(len(bucket_trades))
                ),
                hit_rate=None if not signals else Decimal(wins) / Decimal(signals),
                mean_score=_mean(
                    [value.score for value in bucket_trades]
                    + [value.score for value in bucket_skips if value.score is not None]
                ),
                mean_net_return=_mean([value.net_return for value in bucket_trades]),
                expectancy=_mean([value.net_return for value in bucket_trades]),
            )
        )
    return tuple(value for value in buckets if value.signal_count > 0)


def _build_metrics(
    *,
    checkpoint_count: int,
    trades: Sequence[BacktestTrade],
    skips: Sequence[BacktestSkippedSignal],
    policy: BacktestPolicy,
) -> BacktestMetrics:
    exit_skips = tuple(value for value in skips if value.stage == "EXIT")
    entry_rejected = sum(value.stage == "ENTRY" for value in skips)
    signal_count = len(trades) + len(exit_skips)
    win_count = sum(value.net_pnl > 0 for value in trades)
    loss_count = len(trades) - win_count
    net_pnls = [value.net_pnl for value in trades]
    net_returns = [value.net_return for value in trades]
    total_net_pnl = sum(net_pnls, Decimal("0"))
    total_net_return = sum(net_returns, Decimal("0"))
    gross_profit = sum((max(value.net_pnl, Decimal("0")) for value in trades), Decimal("0"))
    gross_loss = sum((max(-value.net_pnl, Decimal("0")) for value in trades), Decimal("0"))
    balance = policy.initial_capital
    peak = balance
    max_drawdown_amount = Decimal("0")
    for trade in sorted(trades, key=lambda value: (value.exit_at, str(value.id))):
        balance += trade.net_pnl
        peak = max(peak, balance)
        max_drawdown_amount = max(max_drawdown_amount, peak - balance)
    return BacktestMetrics(
        checkpoint_count=checkpoint_count,
        entry_rejected_count=entry_rejected,
        signal_count=signal_count,
        executed_trade_count=len(trades),
        skipped_signal_count=len(exit_skips),
        win_count=win_count,
        loss_count=loss_count,
        precision=None if not trades else Decimal(win_count) / Decimal(len(trades)),
        hit_rate=None if not signal_count else Decimal(win_count) / Decimal(signal_count),
        total_net_pnl=total_net_pnl,
        average_net_pnl=_mean(net_pnls),
        total_net_return=total_net_return,
        average_net_return=_mean(net_returns),
        expectancy=_mean(net_returns),
        expectancy_pnl=_mean(net_pnls),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=None if gross_loss == 0 else gross_profit / gross_loss,
        max_drawdown=max_drawdown_amount / policy.initial_capital,
        max_drawdown_amount=max_drawdown_amount,
        score_buckets=_build_score_buckets(trades, exit_skips),
    )


__all__ = [
    "BACKTESTING_VERSION",
    "BacktestHarness",
    "BacktestManifest",
    "BacktestMetrics",
    "BacktestPolicy",
    "BacktestReport",
    "BacktestScoreBucket",
    "BacktestSegment",
    "BacktestSegmentKey",
    "BacktestSkippedSignal",
    "BacktestTrade",
]
