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

EARLY_WINDOW_LABELS = tuple(name for name, _ in ULTRA_EARLY_CORRELATION_WINDOWS)
EARLY_WINDOW_DURATIONS: Mapping[str, timedelta] = MappingProxyType(
    dict(ULTRA_EARLY_CORRELATION_WINDOWS)
)
EARLY_FEATURE_VERSION = "early-features-v1"

_QUALITY_SEVERITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_BUY_SIDES = frozenset({"buy", "b", "bid", "in", "purchase"})
_SELL_SIDES = frozenset({"sell", "s", "ask", "out", "sale"})
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
    return observation.occurred_at or observation.observed_at


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
            ("liquidity", "liquidity_usd", "liquidity_quote", "pool_liquidity"),
        ),
        "liquidity",
    )


def _wallet(observation: Observation, names: Sequence[str]) -> str | None:
    value = _payload_value(observation.normalized_payload, names)
    if value is _MISSING:
        return None
    return str(value).strip() or None


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

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID")
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        normalized_windows = dict(self.windows)
        if tuple(normalized_windows) != EARLY_WINDOW_LABELS:
            raise ValueError("windows must contain the canonical early window set in order")
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

    def compute(
        self,
        token_id: UUID,
        as_of: datetime,
        observations: Sequence[Observation],
    ) -> EarlyFeatureSnapshot:
        if not isinstance(token_id, UUID):
            raise TypeError("token_id must be a UUID")
        checkpoint = ensure_utc(as_of, "as_of")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        normalized = tuple(observations)
        if any(not isinstance(observation, Observation) for observation in normalized):
            raise TypeError("observations must contain Observation values")
        matching = tuple(
            sorted(
                (
                    observation
                    for observation in normalized
                    if observation.token_id in {None, token_id}
                ),
                key=lambda observation: (_event_time(observation), str(observation.id)),
            )
        )
        future_count = sum(_event_time(observation) > checkpoint for observation in matching)
        bounded = tuple(
            observation for observation in matching if _event_time(observation) <= checkpoint
        )
        windows: dict[str, EarlyFeatureWindow] = {}
        all_reasons: list[ReasonCode] = []
        all_refs: list[str] = []
        for label in EARLY_WINDOW_LABELS:
            duration = EARLY_WINDOW_DURATIONS[label]
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
        progress = tuple(
            value for observation in current if (value := _progress(observation)) is not None
        )
        buyers = tuple(
            wallet
            for observation in buys
            if (wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet")))
            is not None
        )
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
        metrics: dict[str, object] = {
            "trade_count": len(current),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "buys_per_second": _per_second(Decimal(len(buys)) if buys else None, duration),
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
            "future_observations_excluded": future_count,
        }
        previous_buys = tuple(
            observation for observation in previous if _side(observation) == "buy"
        )
        previous_amounts = tuple(
            amount for observation in previous_buys if (amount := _amount(observation)) is not None
        )
        previous_rate = _per_second(
            Decimal(len(previous_buys)) if previous_buys else None,
            duration,
        )
        current_rate = metrics["buys_per_second"]
        metrics["previous_buys_per_second"] = previous_rate
        metrics["buy_acceleration_per_second"] = (
            current_rate - previous_rate
            if isinstance(current_rate, Decimal) and isinstance(previous_rate, Decimal)
            else None
        )
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
        previous_buyers = tuple(
            wallet
            for observation in previous_buys
            if (wallet := _wallet(observation, ("buyer_wallet", "buyer", "trader", "wallet")))
            is not None
        )
        metrics["unique_buyer_growth"] = (
            len(set(buyers)) - len(set(previous_buyers)) if buyers and previous_buyers else None
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
    "EARLY_WINDOW_DURATIONS",
    "EARLY_WINDOW_LABELS",
    "EarlyFeatureEngine",
    "EarlyFeatureSnapshot",
    "EarlyFeatureWindow",
]
