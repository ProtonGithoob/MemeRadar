"""Exit advisories for positions the operator bought manually.

MemeRadar never trades here.  The operator registers a manual buy; this module
turns subsequent market samples into deterministic, de-duplicated advisories:

* a take-profit ladder (recover principal at 2x, then scale out into strength),
* a trailing stop once a runner exists,
* a hard stop while the principal is still at risk,
* rug/exit-liquidity warnings (pool liquidity collapse, sell-pressure dumps),
* a stale-data warning so silence is never mistaken for safety.

Price semantics are explicit: the entry price is the operator's executed fill
(``OPERATOR_EXECUTED``) or, when they did not provide one, the market reference
at registration (``MARKET_REFERENCE_AT_REGISTRATION``).  The multiple is always
the *market reference* price over that entry; an actual sell executes at a
worse price after slippage and fees, and every advisory says so.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain.common import ensure_utc, require_text

from .lifecycle_watch import LifecycleSample

MANUAL_EXIT_VERSION = "manual-exit-advisor-v1"
_ONE = Decimal("1")


class EntryPriceSemantics(str, Enum):
    OPERATOR_EXECUTED = "OPERATOR_EXECUTED"
    MARKET_REFERENCE_AT_REGISTRATION = "MARKET_REFERENCE_AT_REGISTRATION"


class ExitAction(str, Enum):
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"
    WARN = "WARN"


@dataclass(frozen=True, slots=True)
class ManualPosition:
    position_id: str
    mint: str
    opened_at: datetime
    size_usd: Decimal
    entry_price_usd: Decimal
    entry_semantics: EntryPriceSemantics
    symbol: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position_id", require_text(self.position_id, "position_id", max_length=128)
        )
        object.__setattr__(self, "mint", require_text(self.mint, "mint", max_length=64))
        object.__setattr__(self, "opened_at", ensure_utc(self.opened_at, "opened_at"))
        object.__setattr__(self, "entry_semantics", EntryPriceSemantics(self.entry_semantics))
        if self.size_usd <= 0 or self.entry_price_usd <= 0:
            raise ValueError("size_usd and entry_price_usd must be positive")


@dataclass(frozen=True, slots=True)
class ExitPolicy:
    """Versioned hypotheses; fractions are of the position still held."""

    ladder: tuple[tuple[Decimal, Decimal], ...] = (
        (Decimal("2"), Decimal("0.5")),
        (Decimal("5"), Decimal("0.25")),
        (Decimal("10"), Decimal("0.25")),
        (Decimal("25"), Decimal("0.25")),
        (Decimal("50"), Decimal("0.5")),
        (Decimal("100"), Decimal("1")),
    )
    trailing_activation_multiple: Decimal = Decimal("3")
    trailing_drawdown: Decimal = Decimal("0.35")
    hard_stop_multiple: Decimal = Decimal("0.5")
    liquidity_drop: Decimal = Decimal("0.5")
    sell_pressure_ratio: Decimal = Decimal("2")
    sell_pressure_price_m5_pct: Decimal = Decimal("-20")
    stale_after: timedelta = timedelta(minutes=3)
    version: str = MANUAL_EXIT_VERSION

    def __post_init__(self) -> None:
        previous = _ONE
        for multiple, fraction in self.ladder:
            if multiple <= previous or not Decimal("0") < fraction <= _ONE:
                raise ValueError("ladder multiples must increase and fractions be in (0, 1]")
            previous = multiple
        for name in ("trailing_drawdown", "liquidity_drop"):
            if not Decimal("0") < getattr(self, name) < _ONE:
                raise ValueError(f"{name} must be between zero and one")
        if not Decimal("0") < self.hard_stop_multiple < _ONE:
            raise ValueError("hard_stop_multiple must be between zero and one")

    @property
    def config_hash(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, default=str, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ExitAdvisorState:
    peak_price_usd: Decimal | None = None
    peak_liquidity_usd: Decimal | None = None
    fired: set[str] = field(default_factory=set)
    last_observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExitAdvice:
    position_id: str
    mint: str
    key: str
    action: ExitAction
    sell_fraction_of_remaining: Decimal | None
    mark_multiple: Decimal | None
    peak_multiple: Decimal | None
    reason_codes: tuple[str, ...]
    severity: str
    as_of: datetime
    entry_semantics: EntryPriceSemantics
    config_hash: str
    version: str = MANUAL_EXIT_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "position_id": self.position_id,
            "mint": self.mint,
            "advice_key": self.key,
            "action": self.action.value,
            "sell_fraction_of_remaining": _text(self.sell_fraction_of_remaining),
            "mark_multiple": _text(self.mark_multiple),
            "peak_multiple": _text(self.peak_multiple),
            "reason_codes": list(self.reason_codes),
            "severity": self.severity,
            "as_of": self.as_of.isoformat(),
            "entry_price_semantics": self.entry_semantics.value,
            "price_semantics": "MARKET_REFERENCE_OVER_ENTRY; executed exit will be worse",
            "authority": "ADVISORY_ONLY_MANUAL_EXECUTION",
            "config_hash": self.config_hash,
            "version": self.version,
        }


def advise(
    position: ManualPosition,
    state: ExitAdvisorState,
    sample: LifecycleSample | None,
    *,
    now: datetime,
    policy: ExitPolicy | None = None,
) -> tuple[ExitAdvice, ...]:
    """Return new advisories for this sample; each key fires at most once."""

    active = policy or ExitPolicy()
    checked_at = ensure_utc(now, "now")
    advices: list[ExitAdvice] = []

    def emit(
        key: str,
        action: ExitAction,
        reasons: tuple[str, ...],
        *,
        fraction: Decimal | None = None,
        severity: str = "WARNING",
        mark: Decimal | None = None,
        peak: Decimal | None = None,
    ) -> None:
        if key in state.fired:
            return
        state.fired.add(key)
        advices.append(
            ExitAdvice(
                position_id=position.position_id,
                mint=position.mint,
                key=key,
                action=action,
                sell_fraction_of_remaining=fraction,
                mark_multiple=mark,
                peak_multiple=peak,
                reason_codes=reasons,
                severity=severity,
                as_of=checked_at,
                entry_semantics=position.entry_semantics,
                config_hash=active.config_hash,
            )
        )

    fresh = (
        sample is not None
        and sample.mint == position.mint
        and sample.price_usd is not None
        and checked_at - sample.observed_at <= active.stale_after
    )
    if not fresh:
        emit("stale", ExitAction.WARN, ("MANUAL_EXIT_MARKET_DATA_STALE",))
        return tuple(advices)
    state.fired.discard("stale")
    assert sample is not None and sample.price_usd is not None
    if state.last_observed_at is not None and sample.observed_at <= state.last_observed_at:
        return tuple(advices)
    state.last_observed_at = sample.observed_at

    price = sample.price_usd
    if state.peak_price_usd is None or price > state.peak_price_usd:
        state.peak_price_usd = price
    mark = (price / position.entry_price_usd).quantize(Decimal("0.0001"))
    peak = (state.peak_price_usd / position.entry_price_usd).quantize(Decimal("0.0001"))

    # Pool collapse is the classic rug; check it before taking profit.
    liquidity = sample.liquidity_usd
    if liquidity is not None:
        if state.peak_liquidity_usd is not None and liquidity <= state.peak_liquidity_usd * (
            _ONE - active.liquidity_drop
        ):
            emit(
                "liquidity_drop",
                ExitAction.CLOSE,
                ("MANUAL_EXIT_LIQUIDITY_COLLAPSE",),
                severity="CRITICAL",
                mark=mark,
                peak=peak,
            )
        if state.peak_liquidity_usd is None or liquidity > state.peak_liquidity_usd:
            state.peak_liquidity_usd = liquidity

    if (
        sample.buys_m5 is not None
        and sample.sells_m5 is not None
        and sample.price_change_m5_pct is not None
        and Decimal(sample.sells_m5) >= active.sell_pressure_ratio * max(sample.buys_m5, 1)
        and sample.price_change_m5_pct <= active.sell_pressure_price_m5_pct
    ):
        emit(
            "sell_pressure",
            ExitAction.REDUCE,
            ("MANUAL_EXIT_DISTRIBUTION_SELL_PRESSURE",),
            fraction=Decimal("0.5"),
            severity="CRITICAL",
            mark=mark,
            peak=peak,
        )
    else:
        state.fired.discard("sell_pressure")

    crossed = [
        (multiple, fraction)
        for multiple, fraction in active.ladder
        if mark >= multiple and f"tp:{multiple}" not in state.fired
    ]
    if crossed:
        remaining = _ONE
        for multiple, fraction in crossed:
            remaining *= _ONE - fraction
            state.fired.add(f"tp:{multiple}")
        top = crossed[-1][0]
        state.fired.discard(f"tp:{top}")
        emit(
            f"tp:{top}",
            ExitAction.CLOSE if remaining == 0 else ExitAction.REDUCE,
            (
                "MANUAL_EXIT_RECOVER_PRINCIPAL"
                if top == active.ladder[0][0]
                else "MANUAL_EXIT_TAKE_PROFIT_LADDER",
            ),
            fraction=(_ONE - remaining).quantize(Decimal("0.0001")),
            severity="INFO",
            mark=mark,
            peak=peak,
        )

    if peak >= active.trailing_activation_multiple and price <= state.peak_price_usd * (
        _ONE - active.trailing_drawdown
    ):
        emit(
            "trailing_stop",
            ExitAction.CLOSE,
            ("MANUAL_EXIT_TRAILING_STOP",),
            severity="CRITICAL",
            mark=mark,
            peak=peak,
        )

    principal_recovered = f"tp:{active.ladder[0][0]}" in state.fired
    if not principal_recovered and mark <= active.hard_stop_multiple:
        emit(
            "hard_stop",
            ExitAction.CLOSE,
            ("MANUAL_EXIT_HARD_STOP",),
            severity="CRITICAL",
            mark=mark,
            peak=peak,
        )
    return tuple(advices)


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


__all__ = [
    "MANUAL_EXIT_VERSION",
    "EntryPriceSemantics",
    "ExitAction",
    "ExitAdvice",
    "ExitAdvisorState",
    "ExitPolicy",
    "ManualPosition",
    "advise",
]
