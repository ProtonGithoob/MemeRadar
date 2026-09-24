"""Event-time bounded ultra-early micro-feature calculations.

The engine is intentionally a projection over the existing normalized
``Observation`` stream.  It never asks a provider for missing data and never
uses an observation after the requested ``as_of`` checkpoint.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from memeradar_domain import Observation, Provenance, QualityState, ReasonCode
from memeradar_domain.common import (
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .correlation import ULTRA_EARLY_CORRELATION_WINDOWS
from .event_time import exact_event_time
from .evidence_policy import production_observations

EARLY_WINDOW_LABELS = tuple(name for name, _ in ULTRA_EARLY_CORRELATION_WINDOWS)
EARLY_WINDOW_DURATIONS: Mapping[str, timedelta] = MappingProxyType(
    dict(ULTRA_EARLY_CORRELATION_WINDOWS)
)
EARLY_FEATURE_VERSION = "early-features-v1"
EARLY_RUNTIME_WINDOW_DURATIONS: tuple[tuple[str, timedelta], ...] = (
    ("30s", timedelta(seconds=30)),
    ("1m", timedelta(minutes=1)),
    ("2m", timedelta(minutes=2)),
    ("5m", timedelta(minutes=5)),
    ("10m", timedelta(minutes=10)),
    ("15m", timedelta(minutes=15)),
)

_QUALITY_SEVERITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_BUY_SIDES = frozenset({"buy", "b", "bid", "in", "purchase"})
_SELL_SIDES = frozenset({"sell", "s", "ask", "out", "sale"})
_EFFECTIVE_LIQUIDITY_KEYS = (
    "effective_executable_liquidity",
    "executable_liquidity",
    "effective_liquidity",
    "route_liquidity",
)
_MISSING = object()


def _reason(code: str, *, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code, detail=detail)


def _decimal(value: object, field_name: str) -> Decimal | None:
    if value is None or value is _MISSING or isinstance(value, bool):
        return None
    try:
        return to_decimal(value, field_name)
    except (TypeError, ValueError):
        return None


def _payload_value(payload: Mapping[str, object], names: Sequence[str]) -> object:
    for name in names:
        if name in payload and payload[name] is not None:
            return payload[name]
    return _MISSING


def _side(observation: Observation) -> str | None:
    value = _payload_value(
        observation.normalized_payload,
        ("side", "action", "trade_side", "direction"),
    )
    if not isinstance(value, str):
        event_type = str(observation.normalized_payload.get("event_type", "")).lower()
        value = event_type
    normalized = str(value).strip().lower()
    if normalized in _BUY_SIDES or "buy" in normalized:
        return "buy"
    if normalized in _SELL_SIDES or "sell" in normalized:
        return "sell"
    return None


def _event_time(observation: Observation) -> datetime:
    occurred_at = exact_event_time(observation)
    if occurred_at is None:
        raise ValueError("early feature calculations require exact occurred_at")
    return occurred_at


def _amount(observation: Observation) -> Decimal | None:
    return _decimal(
        _payload_value(
            observation.normalized_payload,
            (
                "quote_amount",
                "sol_amount",
                "quote_volume",
                "volume_sol",
                "amount_quote",
                "amount_in",
                "volume",
                "amount",
            ),
        ),
        "quote_amount",
    )


def _price(observation: Observation) -> Decimal | None:
    return _decimal(
        _payload_value(
            observation.normalized_payload,
            ("market_price", "price", "price_usd", "mark_price"),
        ),
        "price",
    )


def _liquidity(observation: Observation) -> Decimal | None:
    return _decimal(
        _payload_value(
            observation.normalized_payload,
            (
                *_EFFECTIVE_LIQUIDITY_KEYS,
                "liquidity",
                "liquidity_usd",
                "liquidity_quote",
                "pool_liquidity",
            ),
        ),
        "liquidity",
    )


def _liquidity_source(observation: Observation) -> str:
    payload = observation.normalized_payload
    if any(payload.get(key) is not None for key in _EFFECTIVE_LIQUIDITY_KEYS):
        return "EFFECTIVE_EXECUTABLE_LIQUIDITY"
    if any(
        payload.get(key) is not None
        for key in ("liquidity", "liquidity_usd", "liquidity_quote", "pool_liquidity")
    ):
        return "REPORTED_LIQUIDITY"
    return "UNKNOWN"


def _market_cap(observation: Observation) -> Decimal | None:
    return _decimal(
        _payload_value(
            observation.normalized_payload,
            ("market_cap_usd", "market_cap", "marketCapUsd", "fdv"),
        ),
        "market_cap",
    )


def _wallet(observation: Observation, names: Sequence[str]) -> str | None:
    value = _payload_value(observation.normalized_payload, names)
    if value is _MISSING:
        return None
    return str(value).strip() or None


def _explicit_boolean(observation: Observation, names: Sequence[str]) -> bool | None:
    value = _payload_value(observation.normalized_payload, names)
    if value is _MISSING:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _trade_wallets(observations: Sequence[Observation], side: str) -> tuple[str, ...]:
    names = (
        ("buyer_wallet", "buyer", "trader", "wallet")
        if side == "buy"
        else ("seller_wallet", "seller", "trader", "wallet")
    )
    return tuple(
        wallet
        for observation in observations
        if (wallet := _wallet(observation, names)) is not None
    )


def _progress(observation: Observation) -> Decimal | None:
    return _decimal(
        _payload_value(
            observation.normalized_payload,
            ("bonding_curve_progress_bps", "bonding_curve_progress", "curve_progress_bps"),
        ),
        "bonding_curve_progress_bps",
    )


def _per_second(total: Decimal | None, duration: timedelta) -> Decimal | None:
    if total is None:
        return None
    seconds = Decimal(str(duration.total_seconds()))
    return total / seconds


def bounded_acceleration(
    current: Decimal | int | float | str | None,
    previous: Decimal | int | float | str | None,
    *,
    denominator_floor: Decimal | int | float | str = Decimal("1"),
) -> Decimal | None:
    """Return bounded signed log acceleration without a tiny-denominator spike."""

    if current is None or previous is None:
        return None
    current_value = to_decimal(current, "current acceleration value")
    previous_value = to_decimal(previous, "previous acceleration value")
    floor = to_decimal(denominator_floor, "denominator_floor")
    if current_value < 0 or previous_value < 0:
        raise ValueError("acceleration values must be non-negative")
    if floor <= 0:
        raise ValueError("denominator_floor must be positive")
    if current_value == previous_value:
        return Decimal("0")
    logarithm = ((current_value + floor) / (previous_value + floor)).ln()
    bounded = logarithm / (Decimal("1") + abs(logarithm))
    return max(Decimal("-1"), min(Decimal("1"), bounded))


def _percentile(values: Sequence[Decimal], fraction: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = Decimal(len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _quality(observations: Sequence[Observation]) -> QualityState:
    if not observations:
        return QualityState.UNKNOWN
    return max(
        (QualityState(observation.quality_state) for observation in observations),
        key=lambda value: _QUALITY_SEVERITY[value],
    )


@dataclass(frozen=True, slots=True)
class EarlyFeatureWindow:
    """One half-open event-time micro-feature window."""

    label: str
    duration: timedelta
    as_of: datetime
    metrics: Mapping[str, object]
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", require_text(self.label, "label", max_length=16))
        if self.duration <= timedelta(0):
            raise ValueError("duration must be positive")
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "metrics", freeze_mapping(self.metrics, "metrics"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)


@dataclass(frozen=True, slots=True)
class EarlyFeatureSnapshot:
    """All launch-age windows projected at one event-time checkpoint."""

    token_id: UUID
    as_of: datetime
    windows: Mapping[str, EarlyFeatureWindow]
    quality_state: QualityState
    launch_age_seconds: Decimal | None = None
    version: str = EARLY_FEATURE_VERSION
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    window_labels: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID")
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        normalized_windows = dict(self.windows)
        labels = (
            EARLY_WINDOW_LABELS
            if self.window_labels is None
            else tuple(
                require_text(value, "window label", max_length=16)
                for value in self.window_labels
            )
        )
        object.__setattr__(self, "window_labels", labels)
        if tuple(normalized_windows) != labels:
            raise ValueError("windows must contain the configured early window set in order")
        if any(
            not isinstance(label, str) or not isinstance(window, EarlyFeatureWindow)
            for label, window in normalized_windows.items()
        ):
            raise TypeError("windows must contain EarlyFeatureWindow values")
        object.__setattr__(self, "windows", MappingProxyType(normalized_windows))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.launch_age_seconds is not None:
            age = to_decimal(self.launch_age_seconds, "launch_age_seconds")
            if age < 0:
                raise ValueError("launch_age_seconds must be non-negative")
            object.__setattr__(self, "launch_age_seconds", age)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    def window(self, label: str) -> EarlyFeatureWindow:
        return self.windows[require_text(label, "label", max_length=16)]

    def execution_eligible(self) -> bool:
        """Feature evidence is never execution permission."""

        return False


class EarlyFeatureEngine:
    """Compute deterministic launch-time metrics without lookahead."""

    def __init__(
        self,
        *,
        window_durations: Sequence[tuple[str, timedelta]] | None = None,
    ) -> None:
        configured = (
            tuple(ULTRA_EARLY_CORRELATION_WINDOWS)
            if window_durations is None
            else tuple(window_durations)
        )
        normalized: list[tuple[str, timedelta]] = []
        previous = timedelta(0)
        for label, duration in configured:
            name = require_text(label, "window label", max_length=16)
            if any(existing == name for existing, _ in normalized):
                raise ValueError("window labels must be unique")
            if not isinstance(duration, timedelta) or duration <= previous:
                raise ValueError("window durations must be strictly increasing")
            normalized.append((name, duration))
            previous = duration
        if not normalized:
            raise ValueError("at least one window is required")
        self._window_durations = tuple(normalized)

    def compute(
        self,
        token_id: UUID,
        as_of: datetime,
        observations: Sequence[Observation],
        *,
        include_shadow: bool = False,
    ) -> EarlyFeatureSnapshot:
        if not isinstance(token_id, UUID):
            raise TypeError("token_id must be a UUID")
        checkpoint = ensure_utc(as_of, "as_of")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        normalized = production_observations(observations, include_shadow=include_shadow)
        candidates = tuple(
            observation
            for observation in normalized
            if observation.token_id in {None, token_id}
        )
        future_count = sum(
            observation.observed_at > checkpoint
            or observation.ingested_at > checkpoint
            or (
                observation.occurred_at is not None
                and observation.occurred_at > checkpoint
            )
            for observation in candidates
        )
        matching = tuple(
            sorted(
                (
                    observation
                    for observation in candidates
                    if exact_event_time(observation) is not None
                ),
                key=lambda observation: (_event_time(observation), str(observation.id)),
            )
        )
        bounded = tuple(
            observation for observation in matching if _event_time(observation) <= checkpoint
        )
        windows: dict[str, EarlyFeatureWindow] = {}
        all_reasons: list[ReasonCode] = []
        all_refs: list[str] = []
        for label, duration in self._window_durations:
            current = tuple(
                observation
                for observation in bounded
                if checkpoint - duration < _event_time(observation) <= checkpoint
            )
            previous = tuple(
                observation
                for observation in bounded
                if checkpoint - (duration * 2) < _event_time(observation) <= checkpoint - duration
            )
            window = self._window(
                label,
                duration,
                checkpoint,
                current,
                previous,
                future_count,
            )
            windows[label] = window
            all_reasons.extend(window.reason_codes)
            all_refs.extend(window.evidence_refs)
        launch_times = [_event_time(observation) for observation in bounded]
        launch_age = None
        if launch_times:
            launch_age = Decimal(str((checkpoint - min(launch_times)).total_seconds()))
        quality = _quality(bounded)
        if future_count and quality is QualityState.FRESH:
            all_reasons.append(_reason("FUTURE_OBSERVATIONS_EXCLUDED", detail=str(future_count)))
        if not bounded:
            all_reasons.append(_reason("NO_EARLY_OBSERVATIONS"))
        return EarlyFeatureSnapshot(
            token_id=token_id,
            as_of=checkpoint,
            windows=windows,
            quality_state=quality,
            launch_age_seconds=launch_age,
            version=EARLY_FEATURE_VERSION,
            reason_codes=tuple(all_reasons),
            evidence_refs=tuple(all_refs),
            window_labels=tuple(label for label, _ in self._window_durations),
        )

    def _window(
        self,
        label: str,
        duration: timedelta,
        as_of: datetime,
        current: Sequence[Observation],
        previous: Sequence[Observation],
        future_count: int,
    ) -> EarlyFeatureWindow:
        buys = tuple(observation for observation in current if _side(observation) == "buy")
        sells = tuple(observation for observation in current if _side(observation) == "sell")
        buy_amounts = tuple(
            amount for observation in buys if (amount := _amount(observation)) is not None
        )
        sell_amounts = tuple(
            amount for observation in sells if (amount := _amount(observation)) is not None
        )
        total_inflow = sum(buy_amounts, Decimal("0")) if buy_amounts else None
        total_outflow = sum(sell_amounts, Decimal("0")) if sell_amounts else None
        prices = tuple(
            price for observation in current if (price := _price(observation)) is not None
        )
        liquidities = tuple(
            liquidity
            for observation in current
            if (liquidity := _liquidity(observation)) is not None
        )
        liquidity_sources = tuple(
            _liquidity_source(observation)
            for observation in current
            if _liquidity(observation) is not None
        )
        market_caps = tuple(
            market_cap
            for observation in current
            if (market_cap := _market_cap(observation)) is not None
        )
        progress = tuple(
            value for observation in current if (value := _progress(observation)) is not None
        )
        buyers = tuple(
            wallet
            for observation in buys
            if (wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet")))
            is not None
        )
        sellers = _trade_wallets(current, "sell")
        makers = tuple(
            wallet
            for observation in current
            if (
                wallet := _wallet(
                    observation,
                    ("maker", "trader", "wallet", "buyer_wallet", "seller_wallet"),
                )
            )
            is not None
        )
        all_amounts = tuple(
            amount for observation in current if (amount := _amount(observation)) is not None
        )
        fresh_flags = tuple(
            fresh_flag
            for observation in buys
            if (
                fresh_flag := _explicit_boolean(
                    observation, ("fresh_wallet", "is_fresh_wallet")
                )
            )
            is not None
        )
        smart_wallets = {
            wallet
            for observation in buys
            if (
                wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet"))
            ) is not None
            and _explicit_boolean(observation, ("smart_wallet", "is_smart_wallet")) is True
        }
        independent_smart_wallets = {
            wallet
            for observation in buys
            if (
                wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet"))
            ) is not None
            and _explicit_boolean(
                observation,
                ("independent_smart_wallet", "is_independent_smart_wallet"),
            )
            is True
        }
        funders = tuple(
            str(funder)
            for observation in buys
            if (
                funder := _payload_value(
                    observation.normalized_payload,
                    ("shared_funder", "funder", "funding_wallet"),
                )
            )
            is not _MISSING
            and funder is not None
        )
        shared_funder_ratio = None
        if funders:
            funding_counts = Counter(funders)
            shared_count = sum(count for count in funding_counts.values() if count > 1)
            shared_funder_ratio = Decimal(shared_count) / Decimal(len(funders))
        creator_flags = tuple(
            creator_flag
            for observation in buys
            if (
                creator_flag := _explicit_boolean(
                    observation, ("creator_linked", "creator_related")
                )
            )
            is not None
        )
        fresh_wallet_ratio = (
            Decimal(sum(fresh_flags)) / Decimal(len(fresh_flags)) if fresh_flags else None
        )
        top10_values = tuple(
            value
            for observation in current
            if (value := _decimal(
                _payload_value(
                    observation.normalized_payload,
                    ("top10_holder_pct", "top10_holder_percent", "top10"),
                ),
                "top10_holder_pct",
            ))
            is not None
        )
        wash_flags = tuple(
            wash_flag
            for observation in current
            if (
                wash_flag := _explicit_boolean(observation, ("wash_trade", "wash", "bot_trade"))
            )
            is not None
        )
        circular_values = tuple(
            value
            for observation in current
            if (value := _decimal(
                _payload_value(observation.normalized_payload, ("circular_flow_ratio",)),
                "circular_flow_ratio",
            ))
            is not None
        )

        def latest_delta(values: Sequence[Decimal]) -> Decimal | None:
            return values[-1] - values[0] if len(values) >= 2 else None

        metrics: dict[str, object] = {
            "trade_count": len(current),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "unique_sellers": len(set(sellers)) if sellers else None,
            "buys_per_second": _per_second(Decimal(len(buys)) if buys else None, duration),
            "new_buyers_per_minute": (
                Decimal(len(set(buyers))) / (Decimal(str(duration.total_seconds())) / Decimal("60"))
                if buyers
                else None
            ),
            "new_sellers_per_minute": (
                Decimal(len(set(sellers)))
                / (Decimal(str(duration.total_seconds())) / Decimal("60"))
                if sellers
                else None
            ),
            "buy_volume": total_inflow,
            "sell_volume": total_outflow,
            "buy_sell_count_ratio": (
                Decimal(len(buys)) / Decimal(len(sells)) if buys and sells else None
            ),
            "buy_sell_volume_ratio": (
                total_inflow / total_outflow
                if total_inflow is not None
                and total_outflow is not None
                and total_outflow != Decimal("0")
                else None
            ),
            "net_buy_flow": (
                None
                if total_inflow is None and total_outflow is None
                else (total_inflow or Decimal("0")) - (total_outflow or Decimal("0"))
            ),
            "quote_inflow": total_inflow,
            "quote_inflow_per_second": _per_second(total_inflow, duration),
            "quote_outflow": total_outflow,
            "quote_outflow_per_second": _per_second(total_outflow, duration),
            "net_quote_flow_per_second": _per_second(
                (
                    None
                    if total_inflow is None and total_outflow is None
                    else (total_inflow or Decimal("0")) - (total_outflow or Decimal("0"))
                ),
                duration,
            ),
            "return": None if len(prices) < 2 else prices[-1] / prices[0] - Decimal("1"),
            "liquidity_change": None if len(liquidities) < 2 else liquidities[-1] - liquidities[0],
            "liquidity": liquidities[-1] if liquidities else None,
            "market_cap": market_caps[-1] if market_caps else None,
            "market_cap_change": latest_delta(market_caps) if len(market_caps) >= 2 else None,
            "price": prices[-1] if prices else None,
            "median_trade_size": _percentile(all_amounts, Decimal("0.5")),
            "p90_trade_size": _percentile(all_amounts, Decimal("0.9")),
            "bonding_curve_velocity": self._velocity(progress, current),
            "migration_state": self._migration_state(current),
            "unique_buyers": len(set(buyers)) if buyers else None,
            "repeat_buyer_ratio": self._repeat_ratio(buyers),
            "buy_sell_ratio": (
                Decimal(len(buys)) / Decimal(len(sells)) if buys and sells else None
            ),
            "buyer_concentration": self._concentration(buyers),
            "maker_diversity": (
                None if not makers else Decimal(len(set(makers))) / Decimal(len(makers))
            ),
            "fresh_wallet_ratio": fresh_wallet_ratio,
            "raw_smart_wallet_count": len(smart_wallets) if smart_wallets else None,
            "independent_smart_wallet_count": (
                len(independent_smart_wallets) if independent_smart_wallets else None
            ),
            "shared_funder_ratio": shared_funder_ratio,
            "creator_linked_buyer_ratio": (
                Decimal(sum(creator_flags)) / Decimal(len(creator_flags))
                if creator_flags
                else None
            ),
            "top10_holder_delta": (
                top10_values[-1] - top10_values[0] if len(top10_values) >= 2 else None
            ),
            "top_holder_accumulation": _decimal(
                _payload_value(
                    current[-1].normalized_payload if current else {},
                    ("top_holder_accumulation", "top_holder_accumulation_pct"),
                ),
                "top_holder_accumulation",
            ),
            "top_holder_distribution": _decimal(
                _payload_value(
                    current[-1].normalized_payload if current else {},
                    ("top_holder_distribution", "top_holder_distribution_pct"),
                ),
                "top_holder_distribution",
            ),
            "repeated_size_ratio": self._repeat_ratio(tuple(str(value) for value in all_amounts)),
            "circular_flow_ratio": max(circular_values) if circular_values else None,
            "wash_evidence": any(wash_flags),
            "future_observations_excluded": future_count,
        }
        previous_buys = tuple(
            observation for observation in previous if _side(observation) == "buy"
        )
        previous_amounts = tuple(
            amount for observation in previous_buys if (amount := _amount(observation)) is not None
        )
        previous_sells = tuple(
            observation for observation in previous if _side(observation) == "sell"
        )
        previous_trade_amounts = tuple(
            amount
            for observation in (*previous_buys, *previous_sells)
            if (amount := _amount(observation)) is not None
        )
        previous_liquidities = tuple(
            liquidity
            for observation in previous
            if (liquidity := _liquidity(observation)) is not None
        )
        traded_volume = (
            sum((*buy_amounts, *sell_amounts), Decimal("0"))
            if buy_amounts or sell_amounts
            else None
        )
        effective_liquidity = liquidities[-1] if liquidities else None
        turnover = (
            traded_volume / effective_liquidity
            if traded_volume is not None
            and effective_liquidity is not None
            and effective_liquidity != Decimal("0")
            else None
        )
        previous_liquidity = (
            previous_liquidities[-1] if previous_liquidities else None
        )
        previous_traded_volume = (
            sum(previous_trade_amounts, Decimal("0")) if previous_trade_amounts else None
        )
        previous_turnover = (
            previous_traded_volume / previous_liquidity
            if previous_traded_volume is not None
            and previous_liquidity is not None
            and previous_liquidity != Decimal("0")
            else None
        )
        turnover_velocity = _per_second(turnover, duration)
        previous_turnover_velocity = _per_second(previous_turnover, duration)
        previous_rate = _per_second(
            Decimal(len(previous_buys)) if previous_buys else None,
            duration,
        )
        raw_current_rate = metrics["buys_per_second"]
        current_rate = raw_current_rate if isinstance(raw_current_rate, Decimal) else None
        metrics["previous_buys_per_second"] = previous_rate
        metrics["buy_acceleration_per_second"] = (
            current_rate - previous_rate
            if isinstance(current_rate, Decimal) and isinstance(previous_rate, Decimal)
            else None
        )
        metrics["buyer_acceleration"] = bounded_acceleration(current_rate, previous_rate)
        current_volume = _per_second(total_inflow, duration)
        previous_volume = _per_second(
            sum(previous_amounts, Decimal("0")) if previous_amounts else None,
            duration,
        )
        metrics["previous_quote_inflow_per_second"] = previous_volume
        metrics["volume_acceleration_per_second"] = (
            current_volume - previous_volume
            if isinstance(current_volume, Decimal) and isinstance(previous_volume, Decimal)
            else None
        )
        metrics["volume_acceleration"] = bounded_acceleration(current_volume, previous_volume)
        metrics["traded_volume"] = traded_volume
        metrics["effective_executable_liquidity"] = effective_liquidity
        metrics["turnover"] = turnover
        metrics[f"turnover_{label}"] = turnover
        metrics["turnover_velocity"] = turnover_velocity
        metrics["previous_turnover_velocity"] = previous_turnover_velocity
        metrics["turnover_acceleration"] = bounded_acceleration(
            turnover_velocity,
            previous_turnover_velocity,
        )
        metrics["turnover_liquidity_source"] = (
            liquidity_sources[-1] if liquidity_sources else "UNKNOWN"
        )
        metrics["turnover_provider_provenance"] = tuple(
            f"{observation.provenance.provider}:{observation.provenance.source_id}"
            for observation in current
        )
        previous_buyers = tuple(
            wallet
            for observation in previous_buys
            if (wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet")))
            is not None
        )
        metrics["unique_buyer_growth"] = (
            len(set(buyers)) - len(set(previous_buyers)) if buyers and previous_buyers else None
        )
        previous_sellers = _trade_wallets(previous, "sell")
        metrics["buyer_growth_rate"] = (
            Decimal(len(set(buyers)) - len(set(previous_buyers)))
            / (Decimal(str(duration.total_seconds())) / Decimal("60"))
            if buyers and previous_buyers
            else None
        )
        metrics["seller_growth_rate"] = (
            Decimal(len(set(sellers)) - len(set(previous_sellers)))
            / (Decimal(str(duration.total_seconds())) / Decimal("60"))
            if sellers and previous_sellers
            else None
        )
        current_liquidity = liquidities[-1] if liquidities else None
        previous_liquidity = previous_liquidities[-1] if previous_liquidities else None
        metrics["liquidity_velocity"] = self._velocity(
            liquidities,
            tuple(observation for observation in current if _liquidity(observation) is not None),
        )
        metrics["liquidity_acceleration"] = bounded_acceleration(
            current_liquidity, previous_liquidity
        )
        current_market_cap = market_caps[-1] if market_caps else None
        previous_market_caps = tuple(
            market_cap
            for observation in previous
            if (market_cap := _market_cap(observation)) is not None
        )
        previous_market_cap = previous_market_caps[-1] if previous_market_caps else None
        metrics["market_cap_velocity"] = self._velocity(
            market_caps,
            tuple(observation for observation in current if _market_cap(observation) is not None),
        )
        metrics["market_cap_acceleration"] = bounded_acceleration(
            current_market_cap, previous_market_cap
        )
        previous_prices = tuple(
            price for observation in previous if (price := _price(observation)) is not None
        )
        metrics["price_velocity"] = self._velocity(
            prices,
            tuple(observation for observation in current if _price(observation) is not None),
        )
        metrics["price_acceleration"] = bounded_acceleration(
            prices[-1] if prices else None,
            previous_prices[-1] if previous_prices else None,
        )
        reasons: list[ReasonCode] = []
        if future_count:
            reasons.append(_reason("FUTURE_OBSERVATIONS_EXCLUDED", detail=str(future_count)))
        if buys and not sells:
            reasons.append(_reason("SELL_EVIDENCE_MISSING"))
        if current and not buy_amounts:
            reasons.append(_reason("QUOTE_INFLOW_EVIDENCE_MISSING"))
        if not current:
            reasons.append(_reason("WINDOW_EVIDENCE_MISSING", detail=label))
        refs = tuple(f"observation:{observation.id}" for observation in current)
        return EarlyFeatureWindow(
            label=label,
            duration=duration,
            as_of=as_of,
            metrics=metrics,
            quality_state=_quality(current),
            reason_codes=tuple(reasons),
            evidence_refs=refs,
            provenance=tuple(observation.provenance for observation in current),
        )

    @staticmethod
    def _velocity(values: Sequence[Decimal], observations: Sequence[Observation]) -> Decimal | None:
        if len(values) < 2 or len(observations) < 2:
            return None
        times = [_event_time(observation) for observation in observations]
        elapsed = Decimal(str((times[-1] - times[0]).total_seconds()))
        if elapsed <= 0:
            return None
        return (values[-1] - values[0]) / elapsed

    @staticmethod
    def _migration_state(observations: Sequence[Observation]) -> str | None:
        for observation in reversed(observations):
            payload = observation.normalized_payload
            state = _payload_value(payload, ("migration_state", "migration", "migrated"))
            if state is not _MISSING:
                return str(state).upper()
            event_type = str(
                payload.get("event_type", payload.get("protocol_event_type", ""))
            ).lower()
            if "migrat" in event_type or "graduat" in event_type:
                return event_type.upper()
        return None

    @staticmethod
    def _repeat_ratio(wallets: Sequence[str]) -> Decimal | None:
        if not wallets:
            return None
        counts = Counter(wallets)
        repeats = sum(count - 1 for count in counts.values() if count > 1)
        return Decimal(repeats) / Decimal(len(wallets))

    @staticmethod
    def _concentration(wallets: Sequence[str]) -> Decimal | None:
        if not wallets:
            return None
        counts = Counter(wallets)
        return Decimal(max(counts.values())) / Decimal(len(wallets))


__all__ = [
    "EARLY_FEATURE_VERSION",
    "EARLY_RUNTIME_WINDOW_DURATIONS",
    "EARLY_WINDOW_DURATIONS",
    "EARLY_WINDOW_LABELS",
    "EarlyFeatureEngine",
    "EarlyFeatureSnapshot",
    "EarlyFeatureWindow",
    "bounded_acceleration",
]
