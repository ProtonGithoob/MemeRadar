"""Post-launch lifecycle watch: tiered tracking, revival detection and outcome labels.

The early radar evaluates a Pump.fun launch only during its first fifteen
minutes.  Most large moves observed in practice happen later: on the bonding
curve while it races toward graduation, right after migration to an AMM, or in
a second wave hours later.  This module keeps watching launches for a bounded
horizon with a polling budget that follows activity (hot/warm/cold tiers), and
turns aggregated market samples into two deterministic products:

* ``RevivalAssessment`` -- a sustained, tape-corroborated acceleration on a
  token older than the early window.  It is watch-level evidence only: it can
  request an operator notification but never ``ENTRY_READY`` or execution.
* ``LifecycleOutcome`` -- a no-lookahead outcome label per horizon (peak and
  final multiple, graduation, collapse) so thresholds can later be calibrated
  against what actually happened instead of guessed.

All thresholds are versioned hypotheses (``LifecyclePolicy.config_hash``).
Missing fields are UNKNOWN and never satisfy a criterion.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain.common import ensure_utc, require_text

LIFECYCLE_WATCH_VERSION = "lifecycle-watch-v1"
_ZERO = Decimal("0")


class Venue(str, Enum):
    """Normalized trading venue; providers spell these several ways."""

    PUMPFUN_CURVE = "PUMPFUN_CURVE"
    PUMPSWAP = "PUMPSWAP"
    RAYDIUM = "RAYDIUM"
    METEORA = "METEORA"
    ORCA = "ORCA"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


def normalize_venue(dex_id: str | None) -> Venue:
    """Map provider DEX identifiers onto one venue vocabulary."""

    if not dex_id:
        return Venue.UNKNOWN
    value = dex_id.strip().lower().replace(".", "").replace("-", "").replace("_", "")
    if value in {"pumpfun", "pump", "pumpfuncurve", "pumpfunbondingcurve"}:
        return Venue.PUMPFUN_CURVE
    if value in {"pumpswap", "pumpamm", "pumpfunamm"}:
        return Venue.PUMPSWAP
    if value.startswith("raydium"):
        return Venue.RAYDIUM
    if value.startswith("meteora"):
        return Venue.METEORA
    if value.startswith("orca"):
        return Venue.ORCA
    return Venue.OTHER


class Tier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    RETIRED = "RETIRED"


class RevivalSignal(str, Enum):
    REVIVAL = "REVIVAL"
    PENDING = "PENDING"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class LifecycleSample:
    """One aggregated market observation of a mint's primary pair."""

    mint: str
    observed_at: datetime
    venue: Venue
    source: str
    source_id: str
    pair_address: str | None = None
    price_usd: Decimal | None = None
    market_cap_usd: Decimal | None = None
    liquidity_usd: Decimal | None = None
    volume_m5_usd: Decimal | None = None
    volume_h1_usd: Decimal | None = None
    volume_h6_usd: Decimal | None = None
    buys_m5: int | None = None
    sells_m5: int | None = None
    buys_h1: int | None = None
    sells_h1: int | None = None
    price_change_m5_pct: Decimal | None = None
    price_change_h1_pct: Decimal | None = None
    pair_created_at: datetime | None = None
    symbol: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mint", require_text(self.mint, "mint", max_length=64))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "venue", Venue(self.venue))
        if self.pair_created_at is not None:
            object.__setattr__(
                self, "pair_created_at", ensure_utc(self.pair_created_at, "pair_created_at")
            )

    @property
    def graduated(self) -> bool:
        return self.venue not in {Venue.PUMPFUN_CURVE, Venue.UNKNOWN}

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["venue"] = self.venue.value
        payload["graduated"] = self.graduated
        return {key: _json_value(value) for key, value in payload.items()}


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    """Versioned hypotheses. None of these values is calibrated yet."""

    horizon: timedelta = timedelta(hours=72)
    hot_interval: timedelta = timedelta(seconds=60)
    warm_interval: timedelta = timedelta(minutes=5)
    cold_interval: timedelta = timedelta(minutes=30)
    hot_market_cap_usd: Decimal = Decimal("20000")
    warm_market_cap_usd: Decimal = Decimal("6000")
    hot_volume_m5_usd: Decimal = Decimal("2000")
    retire_cold_after: timedelta = timedelta(hours=6)
    retire_after_missing_samples: int = 3
    revival_min_age: timedelta = timedelta(minutes=30)
    revival_min_market_cap_usd: Decimal = Decimal("15000")
    revival_max_market_cap_usd: Decimal = Decimal("5000000")
    revival_min_liquidity_usd: Decimal = Decimal("5000")
    revival_min_volume_m5_usd: Decimal = Decimal("3000")
    revival_min_acceleration: Decimal = Decimal("3")
    revival_min_buys_m5: int = 20
    revival_min_buy_sell_ratio: Decimal = Decimal("1.2")
    sustained_samples: int = 2
    sustained_min_span: timedelta = timedelta(seconds=60)
    alert_cooldown: timedelta = timedelta(hours=6)
    collapse_drawdown: Decimal = Decimal("0.9")
    coarse_gap: timedelta = timedelta(minutes=5)
    outcome_horizons: tuple[tuple[str, timedelta], ...] = (
        ("1h", timedelta(hours=1)),
        ("6h", timedelta(hours=6)),
        ("24h", timedelta(hours=24)),
        ("72h", timedelta(hours=72)),
    )
    version: str = LIFECYCLE_WATCH_VERSION

    def __post_init__(self) -> None:
        for name in (
            "horizon",
            "hot_interval",
            "warm_interval",
            "cold_interval",
            "retire_cold_after",
            "revival_min_age",
            "sustained_min_span",
            "alert_cooldown",
            "coarse_gap",
        ):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value < timedelta(0):
                raise ValueError(f"{name} must be a non-negative duration")
        if not self.hot_interval <= self.warm_interval <= self.cold_interval:
            raise ValueError("poll intervals must be ordered hot <= warm <= cold")
        if self.sustained_samples < 1 or self.retire_after_missing_samples < 1:
            raise ValueError("sample counts must be positive")
        if not _ZERO < self.collapse_drawdown < 1:
            raise ValueError("collapse_drawdown must be between zero and one")
        previous = timedelta(0)
        for label, duration in self.outcome_horizons:
            require_text(label, "outcome horizon label", max_length=16)
            if duration <= previous or duration > self.horizon:
                raise ValueError("outcome horizons must increase and fit the watch horizon")
            previous = duration

    @property
    def config_hash(self) -> str:
        material = {
            key: _json_value(value) for key, value in asdict(self).items()
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
        return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class MintLifecycle:
    """Mutable per-mint tracking state owned by one worker loop."""

    mint: str
    discovered_at: datetime
    symbol: str | None = None
    first_sample: LifecycleSample | None = None
    last_sample: LifecycleSample | None = None
    peak_market_cap_usd: Decimal | None = None
    peak_at: datetime | None = None
    graduated_at: datetime | None = None
    migration_seen_at: datetime | None = None
    sample_count: int = 0
    max_gap_seconds: float = 0.0
    missing_samples: int = 0
    revival_streak: list[datetime] = field(default_factory=list)
    last_alert_at: datetime | None = None
    outcomes_recorded: set[str] = field(default_factory=set)
    tier: Tier = Tier.HOT
    next_due_at: datetime | None = None

    def __post_init__(self) -> None:
        self.discovered_at = ensure_utc(self.discovered_at, "discovered_at")
        if self.next_due_at is None:
            self.next_due_at = self.discovered_at

    def age(self, now: datetime) -> timedelta:
        return ensure_utc(now, "now") - self.discovered_at


@dataclass(frozen=True, slots=True)
class RevivalAssessment:
    mint: str
    as_of: datetime
    signal: RevivalSignal
    reason_codes: tuple[str, ...]
    metrics: Mapping[str, object]
    should_alert: bool
    config_hash: str
    version: str = LIFECYCLE_WATCH_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "mint": self.mint,
            "as_of": self.as_of.isoformat(),
            "signal": self.signal.value,
            "reason_codes": list(self.reason_codes),
            "metrics": {key: _json_value(value) for key, value in self.metrics.items()},
            "should_alert": self.should_alert,
            "config_hash": self.config_hash,
            "version": self.version,
            "authority": "WATCH_EVIDENCE_ONLY",
        }


@dataclass(frozen=True, slots=True)
class LifecycleOutcome:
    """Outcome label computed only from samples observed before the horizon end."""

    mint: str
    horizon: str
    horizon_end: datetime
    discovered_at: datetime
    baseline_market_cap_usd: Decimal | None
    baseline_observed_at: datetime | None
    peak_market_cap_usd: Decimal | None
    peak_at: datetime | None
    last_market_cap_usd: Decimal | None
    last_observed_at: datetime | None
    graduated: bool
    collapsed: bool
    sample_count: int
    max_gap_seconds: float
    resolution: str
    config_hash: str
    version: str = LIFECYCLE_WATCH_VERSION

    @property
    def peak_multiple(self) -> Decimal | None:
        return _ratio(self.peak_market_cap_usd, self.baseline_market_cap_usd)

    @property
    def last_multiple(self) -> Decimal | None:
        return _ratio(self.last_market_cap_usd, self.baseline_market_cap_usd)

    @property
    def label(self) -> str:
        peak = self.peak_multiple
        if peak is None:
            return "UNKNOWN"
        if self.collapsed and peak < 2:
            return "COLLAPSED"
        if peak >= 100:
            return "PEAK_100X"
        if peak >= 10:
            return "PEAK_10X"
        if peak >= 2:
            return "PEAK_2X"
        return "COLLAPSED" if self.collapsed else "FLAT"

    def to_payload(self) -> dict[str, object]:
        payload = {key: _json_value(value) for key, value in asdict(self).items()}
        payload["peak_multiple"] = _json_value(self.peak_multiple)
        payload["last_multiple"] = _json_value(self.last_multiple)
        payload["label"] = self.label
        # Market-cap marks only: a chart multiple, not a sellable peak and not
        # a realized fill.  Sellable/realized outcomes need size-aware quotes.
        payload["outcome_semantics"] = "MARK_MARKET_CAP"
        payload["sellable_peak_multiple"] = None
        payload["realized_multiple"] = None
        return payload


def tier_for(state: MintLifecycle, policy: LifecyclePolicy, now: datetime) -> Tier:
    """Spend polling budget where activity is, retire dead or expired mints."""

    age = state.age(now)
    if age > policy.horizon or state.missing_samples >= policy.retire_after_missing_samples:
        return Tier.RETIRED
    if state.migration_seen_at is not None and now - state.migration_seen_at < timedelta(hours=1):
        # Graduation is the PumpSwap handoff; watch it closely even before the
        # provider has indexed the new pool.
        return Tier.HOT
    sample = state.last_sample
    if sample is None:
        return Tier.HOT if age < policy.revival_min_age else Tier.WARM
    market_cap = sample.market_cap_usd
    volume = sample.volume_m5_usd
    if (
        (market_cap is not None and market_cap >= policy.hot_market_cap_usd)
        or (volume is not None and volume >= policy.hot_volume_m5_usd)
        or state.revival_streak
        or (
            state.migration_seen_at is not None
            and now - state.migration_seen_at < timedelta(hours=1)
        )
    ):
        return Tier.HOT
    if market_cap is not None and market_cap >= policy.warm_market_cap_usd:
        return Tier.WARM
    if age > policy.retire_cold_after:
        return Tier.RETIRED
    return Tier.COLD


def schedule_next(state: MintLifecycle, policy: LifecyclePolicy, now: datetime) -> Tier:
    tier = tier_for(state, policy, now)
    state.tier = tier
    interval = {
        Tier.HOT: policy.hot_interval,
        Tier.WARM: policy.warm_interval,
        Tier.COLD: policy.cold_interval,
        Tier.RETIRED: policy.horizon,
    }[tier]
    state.next_due_at = ensure_utc(now, "now") + interval
    return tier


def record_missing(state: MintLifecycle, policy: LifecyclePolicy, now: datetime) -> None:
    """Count a provider miss; a brand-new mint is often not indexed yet."""

    if state.sample_count > 0 or state.age(now) >= policy.revival_min_age:
        state.missing_samples += 1


def record_migration(state: MintLifecycle, seen_at: datetime) -> None:
    """A verified chain migration promotes the mint to the hot tier immediately."""

    seen = ensure_utc(seen_at, "seen_at")
    state.migration_seen_at = seen
    state.graduated_at = state.graduated_at or seen
    state.next_due_at = seen


def apply_sample(
    state: MintLifecycle,
    sample: LifecycleSample,
    policy: LifecyclePolicy,
) -> tuple[LifecycleOutcome, ...]:
    """Fold one sample into the state; return horizons it closed (no lookahead).

    A horizon is labelled from the state *before* the first sample observed
    after that horizon ends, so the label never sees post-horizon prices.
    """

    if sample.mint != state.mint:
        raise ValueError("sample mint does not match lifecycle state")
    closed = _close_horizons(state, policy, before=sample.observed_at)
    if state.last_sample is not None:
        if sample.observed_at <= state.last_sample.observed_at:
            return closed
        gap = (sample.observed_at - state.last_sample.observed_at).total_seconds()
        state.max_gap_seconds = max(state.max_gap_seconds, gap)
    state.missing_samples = 0
    state.sample_count += 1
    state.symbol = state.symbol or sample.symbol
    if state.first_sample is None and sample.market_cap_usd is not None:
        state.first_sample = sample
    if sample.market_cap_usd is not None and (
        state.peak_market_cap_usd is None or sample.market_cap_usd > state.peak_market_cap_usd
    ):
        state.peak_market_cap_usd = sample.market_cap_usd
        state.peak_at = sample.observed_at
    if sample.graduated and state.graduated_at is None:
        state.graduated_at = sample.observed_at
    state.last_sample = sample
    return closed


def finalize(
    state: MintLifecycle, policy: LifecyclePolicy, now: datetime
) -> tuple[LifecycleOutcome, ...]:
    """Close every elapsed horizon when a mint retires or the watch ends."""

    return _close_horizons(state, policy, before=ensure_utc(now, "now"))


def _close_horizons(
    state: MintLifecycle, policy: LifecyclePolicy, *, before: datetime
) -> tuple[LifecycleOutcome, ...]:
    closed: list[LifecycleOutcome] = []
    for label, duration in policy.outcome_horizons:
        end = state.discovered_at + duration
        if label in state.outcomes_recorded or before <= end:
            continue
        state.outcomes_recorded.add(label)
        closed.append(_outcome(state, policy, label, end))
    return tuple(closed)


def _outcome(
    state: MintLifecycle, policy: LifecyclePolicy, label: str, end: datetime
) -> LifecycleOutcome:
    baseline = state.first_sample
    last = state.last_sample
    peak = state.peak_market_cap_usd
    last_cap = None if last is None else last.market_cap_usd
    collapsed = bool(
        peak is not None
        and last_cap is not None
        and peak > 0
        and last_cap <= peak * (1 - policy.collapse_drawdown)
    )
    coarse = state.sample_count < 2 or state.max_gap_seconds > policy.coarse_gap.total_seconds()
    return LifecycleOutcome(
        mint=state.mint,
        horizon=label,
        horizon_end=end,
        discovered_at=state.discovered_at,
        baseline_market_cap_usd=None if baseline is None else baseline.market_cap_usd,
        baseline_observed_at=None if baseline is None else baseline.observed_at,
        peak_market_cap_usd=peak,
        peak_at=state.peak_at,
        last_market_cap_usd=last_cap,
        last_observed_at=None if last is None else last.observed_at,
        graduated=state.graduated_at is not None and state.graduated_at <= end,
        collapsed=collapsed,
        sample_count=state.sample_count,
        max_gap_seconds=state.max_gap_seconds,
        resolution="COARSE" if coarse else "FINE",
        config_hash=policy.config_hash,
    )


def assess_revival(
    state: MintLifecycle,
    sample: LifecycleSample,
    policy: LifecyclePolicy,
) -> RevivalAssessment:
    """Detect a sustained, buyer-corroborated acceleration after the early window.

    Price movement alone never qualifies: volume acceleration, buy count and
    buy/sell balance must all be present and pass.  Any missing input makes
    the assessment UNKNOWN and resets the sustain streak (fail closed).
    """

    now = sample.observed_at
    age = state.age(now)
    reasons: list[str] = []
    metrics: dict[str, object] = {
        "age_seconds": int(age.total_seconds()),
        "venue": sample.venue.value,
        "graduated": sample.graduated,
        "market_cap_usd": sample.market_cap_usd,
        "liquidity_usd": sample.liquidity_usd,
        "volume_m5_usd": sample.volume_m5_usd,
        "buys_m5": sample.buys_m5,
        "sells_m5": sample.sells_m5,
        "price_change_m5_pct": sample.price_change_m5_pct,
        "price_change_h1_pct": sample.price_change_h1_pct,
        "peak_market_cap_usd": state.peak_market_cap_usd,
    }

    def result(signal: RevivalSignal, *, alert: bool = False) -> RevivalAssessment:
        return RevivalAssessment(
            mint=state.mint,
            as_of=now,
            signal=signal,
            reason_codes=tuple(reasons) or ("LIFECYCLE_NO_REVIVAL",),
            metrics=metrics,
            should_alert=alert,
            config_hash=policy.config_hash,
        )

    if age < policy.revival_min_age:
        state.revival_streak.clear()
        reasons.append("LIFECYCLE_INSIDE_EARLY_WINDOW")
        return result(RevivalSignal.NONE)

    required = {
        "market_cap_usd": sample.market_cap_usd,
        "volume_m5_usd": sample.volume_m5_usd,
        "buys_m5": sample.buys_m5,
        "sells_m5": sample.sells_m5,
        "price_change_m5_pct": sample.price_change_m5_pct,
        "price_change_h1_pct": sample.price_change_h1_pct,
    }
    missing = sorted(name for name, value in required.items() if value is None)
    baseline_hourly = _baseline_hourly_volume(sample)
    if baseline_hourly is None:
        missing.append("volume_baseline")
    liquidity_basis = "POOL"
    if sample.venue is Venue.PUMPFUN_CURVE:
        # The bonding curve itself is the counterparty; providers report no pool
        # liquidity for it.  Depth is implied by market cap, not assumed safe.
        liquidity_basis = "BONDING_CURVE"
    elif sample.liquidity_usd is None:
        missing.append("liquidity_usd")
    metrics["liquidity_basis"] = liquidity_basis
    if missing:
        state.revival_streak.clear()
        reasons.extend(f"LIFECYCLE_{name.upper()}_UNKNOWN" for name in missing)
        return result(RevivalSignal.UNKNOWN)

    assert sample.market_cap_usd is not None and sample.volume_m5_usd is not None
    assert sample.buys_m5 is not None and sample.sells_m5 is not None
    assert sample.price_change_m5_pct is not None and sample.price_change_h1_pct is not None
    assert baseline_hourly is not None
    acceleration = (
        Decimal("999")
        if baseline_hourly == 0
        else (sample.volume_m5_usd * 12 / baseline_hourly).quantize(Decimal("0.01"))
    )
    buy_sell_ratio = (
        Decimal("999")
        if sample.sells_m5 == 0
        else (Decimal(sample.buys_m5) / Decimal(sample.sells_m5)).quantize(Decimal("0.01"))
    )
    metrics["volume_acceleration"] = acceleration
    metrics["buy_sell_ratio_m5"] = buy_sell_ratio
    checks = (
        (
            sample.market_cap_usd >= policy.revival_min_market_cap_usd,
            "LIFECYCLE_MARKET_CAP_BELOW_MINIMUM",
        ),
        (
            sample.market_cap_usd <= policy.revival_max_market_cap_usd,
            "LIFECYCLE_MARKET_CAP_ABOVE_MAXIMUM",
        ),
        (
            liquidity_basis == "BONDING_CURVE"
            or (
                sample.liquidity_usd is not None
                and sample.liquidity_usd >= policy.revival_min_liquidity_usd
            ),
            "LIFECYCLE_LIQUIDITY_BELOW_MINIMUM",
        ),
        (
            sample.volume_m5_usd >= policy.revival_min_volume_m5_usd,
            "LIFECYCLE_VOLUME_BELOW_MINIMUM",
        ),
        (acceleration >= policy.revival_min_acceleration, "LIFECYCLE_NO_VOLUME_ACCELERATION"),
        (sample.buys_m5 >= policy.revival_min_buys_m5, "LIFECYCLE_TOO_FEW_BUYS"),
        (buy_sell_ratio >= policy.revival_min_buy_sell_ratio, "LIFECYCLE_SELL_PRESSURE"),
        (sample.price_change_m5_pct > 0, "LIFECYCLE_PRICE_NOT_RISING_M5"),
        (sample.price_change_h1_pct > 0, "LIFECYCLE_PRICE_NOT_RISING_H1"),
    )
    failed = [code for passed, code in checks if not passed]
    if failed:
        state.revival_streak.clear()
        reasons.extend(failed)
        return result(RevivalSignal.NONE)

    state.revival_streak.append(now)
    span = now - state.revival_streak[0]
    metrics["sustained_samples"] = len(state.revival_streak)
    metrics["sustained_seconds"] = int(span.total_seconds())
    if len(state.revival_streak) < policy.sustained_samples or span < policy.sustained_min_span:
        reasons.append("LIFECYCLE_REVIVAL_NOT_YET_SUSTAINED")
        return result(RevivalSignal.PENDING)
    reasons.append("LIFECYCLE_SUSTAINED_REVIVAL")
    if sample.graduated:
        reasons.append("LIFECYCLE_POST_GRADUATION")
    else:
        reasons.append("LIFECYCLE_ON_BONDING_CURVE")
    cooled = state.last_alert_at is None or now - state.last_alert_at >= policy.alert_cooldown
    if not cooled:
        reasons.append("LIFECYCLE_ALERT_COOLDOWN")
    return result(RevivalSignal.REVIVAL, alert=cooled)


def mark_alerted(state: MintLifecycle, at: datetime) -> None:
    state.last_alert_at = ensure_utc(at, "at")


def _baseline_hourly_volume(sample: LifecycleSample) -> Decimal | None:
    """Hourly baseline from the longer windows; the 5m window is the numerator."""

    candidates = []
    if sample.volume_h1_usd is not None:
        candidates.append(sample.volume_h1_usd)
    if sample.volume_h6_usd is not None:
        candidates.append(sample.volume_h6_usd / 6)
    return max(candidates) if candidates else None


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator).quantize(Decimal("0.0001"))


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)  # type: ignore[type-var]
    return value


__all__ = [
    "LIFECYCLE_WATCH_VERSION",
    "LifecycleOutcome",
    "LifecyclePolicy",
    "LifecycleSample",
    "MintLifecycle",
    "RevivalAssessment",
    "RevivalSignal",
    "Tier",
    "Venue",
    "apply_sample",
    "assess_revival",
    "finalize",
    "mark_alerted",
    "normalize_venue",
    "record_migration",
    "record_missing",
    "schedule_next",
    "tier_for",
]
