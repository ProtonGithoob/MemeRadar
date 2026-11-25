"""Reverse wallet intelligence, part 3: chronological copyability backtest.

For each signal (a tracked wallet's first verified buy of a token) the
simulated follower:

1. learns of it only at ``signal_time + provider_latency``;
2. decides after ``decision_delay``;
3. buys ``size_lamports`` into the bonding curve state that existed just
   before that moment (constant-product math, assumed fee), or records a
   NO_FILL when no curve state exists or the token already migrated;
4. exits by policy: when the copied wallet's next sell becomes observable
   (same delays) or at the hold horizon, again into the curve state that
   existed at that time.  An exit after migration is UNPRICED_MIGRATION
   (censored), because AMM trades are not decoded yet.

No future peak is ever used: entry and exit prices come from states at or
before the simulated action time.  Whether a wallet is "tracked" at signal
time is decided by a caller-supplied selector that must itself use only data
up to that time (walk-forward), e.g. ``build_profiles(as_of=signal_time)``.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from statistics import median

from .onchain_wallet_events import (
    ActivityKind,
    OnChainWalletEvent,
    assumption_hash,
    curve_state_before,
    deduplicate,
)

COPYABILITY_VERSION = "wallet-copyability-v1"


class FillStatus(str, Enum):
    FILLED = "FILLED"
    NO_FILL_NO_CURVE_STATE = "NO_FILL_NO_CURVE_STATE"
    NO_FILL_MIGRATED = "NO_FILL_MIGRATED"
    UNPRICED_MIGRATION = "UNPRICED_MIGRATION"
    OPEN_AT_DATA_END = "OPEN_AT_DATA_END"


@dataclass(frozen=True, slots=True)
class CopyPolicy:
    size_lamports: int = 333_000_000  # ~USD 50 at USD 150/SOL; recorded assumption
    provider_latency: timedelta = timedelta(seconds=2)
    decision_delay: timedelta = timedelta(seconds=15)
    fee_bps: int = 125  # assumption per side
    slippage_bps: int = 100  # extra adverse execution vs the curve state
    hold_horizon: timedelta = timedelta(hours=1)
    exit_on_wallet_sell: bool = True
    version: str = COPYABILITY_VERSION

    @property
    def assumption_hash(self) -> str:
        return assumption_hash(
            {
                "size_lamports": self.size_lamports,
                "provider_latency_s": self.provider_latency.total_seconds(),
                "decision_delay_s": self.decision_delay.total_seconds(),
                "fee_bps": self.fee_bps,
                "slippage_bps": self.slippage_bps,
                "hold_horizon_s": self.hold_horizon.total_seconds(),
                "exit_on_wallet_sell": self.exit_on_wallet_sell,
                "version": self.version,
            }
        )


@dataclass(frozen=True, slots=True)
class CopyTrade:
    strategy: str
    source: str  # copied wallet or baseline label
    mint: str
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime | None
    status: FillStatus
    tokens: int
    cost_lamports: int
    proceeds_lamports: int | None
    exit_reason: str | None

    @property
    def net_multiple(self) -> Decimal | None:
        if self.proceeds_lamports is None or self.cost_lamports <= 0:
            return None
        return (Decimal(self.proceeds_lamports) / Decimal(self.cost_lamports)).quantize(
            Decimal("0.0001")
        )


@dataclass(frozen=True, slots=True)
class StrategyReport:
    strategy: str
    signals: int
    filled: int
    no_fill: int
    censored: int
    priced: int
    mean_net_multiple: Decimal | None
    median_net_multiple: Decimal | None
    share_at_least_2x: Decimal | None
    share_total_loss: Decimal | None  # proceeds < 10 % of cost
    net_pnl_lamports: int
    assumption_hash: str
    evidence_class: str
    trades: tuple[CopyTrade, ...] = field(default=(), repr=False)

    def to_payload(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "signals": self.signals,
            "filled": self.filled,
            "no_fill": self.no_fill,
            "censored": self.censored,
            "priced": self.priced,
            "mean_net_multiple": _text(self.mean_net_multiple),
            "median_net_multiple": _text(self.median_net_multiple),
            "share_at_least_2x": _text(self.share_at_least_2x),
            "share_total_loss": _text(self.share_total_loss),
            "net_pnl_sol": str(Decimal(self.net_pnl_lamports) / Decimal(10**9)),
            "assumption_hash": self.assumption_hash,
            "evidence_class": self.evidence_class,
        }


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _simulate(
    *,
    strategy: str,
    source: str,
    mint: str,
    signal_at: datetime,
    tape: Sequence[OnChainWalletEvent],
    migrated_at: datetime | None,
    exit_signal_at: datetime | None,
    data_end: datetime,
    policy: CopyPolicy,
) -> CopyTrade:
    delay = policy.provider_latency + policy.decision_delay
    entry_at = signal_at + delay
    if migrated_at is not None and entry_at >= migrated_at:
        return CopyTrade(strategy, source, mint, signal_at, entry_at, None,
                         FillStatus.NO_FILL_MIGRATED, 0, 0, None, None)
    state = curve_state_before(tape, entry_at)
    if state is None:
        return CopyTrade(strategy, source, mint, signal_at, entry_at, None,
                         FillStatus.NO_FILL_NO_CURVE_STATE, 0, 0, None, None)
    tokens, _ = state.buy(policy.size_lamports, policy.fee_bps + policy.slippage_bps)
    exit_at = entry_at + policy.hold_horizon
    reason = "HOLD_HORIZON"
    if policy.exit_on_wallet_sell and exit_signal_at is not None:
        wallet_exit = exit_signal_at + delay
        if wallet_exit < exit_at:
            exit_at = max(wallet_exit, entry_at + timedelta(seconds=1))
            reason = "FOLLOW_WALLET_SELL"
    if migrated_at is not None and exit_at >= migrated_at:
        return CopyTrade(strategy, source, mint, signal_at, entry_at, exit_at,
                         FillStatus.UNPRICED_MIGRATION, tokens, policy.size_lamports, None,
                         "EXIT_AFTER_MIGRATION_AMM_UNDECODED")
    if exit_at > data_end:
        return CopyTrade(strategy, source, mint, signal_at, entry_at, exit_at,
                         FillStatus.OPEN_AT_DATA_END, tokens, policy.size_lamports, None,
                         "HORIZON_BEYOND_OBSERVED_DATA")
    exit_state = curve_state_before(tape, exit_at) or state
    # The follower's own buy moved the curve; apply it before selling only if
    # nothing traded in between is unknowable here, so use the observed state.
    proceeds, _ = exit_state.sell(tokens, policy.fee_bps + policy.slippage_bps)
    return CopyTrade(strategy, source, mint, signal_at, entry_at, exit_at,
                     FillStatus.FILLED, tokens, policy.size_lamports, proceeds, reason)


def _report(
    strategy: str, trades: Sequence[CopyTrade], policy: CopyPolicy, evidence_class: str
) -> StrategyReport:
    priced = [t for t in trades if t.net_multiple is not None]
    multiples = [t.net_multiple for t in priced if t.net_multiple is not None]
    no_fill = sum(
        1 for t in trades
        if t.status in {FillStatus.NO_FILL_NO_CURVE_STATE, FillStatus.NO_FILL_MIGRATED}
    )
    censored = sum(
        1 for t in trades
        if t.status in {FillStatus.UNPRICED_MIGRATION, FillStatus.OPEN_AT_DATA_END}
    )
    return StrategyReport(
        strategy=strategy,
        signals=len(trades),
        filled=sum(1 for t in trades if t.tokens > 0),
        no_fill=no_fill,
        censored=censored,
        priced=len(priced),
        mean_net_multiple=(
            (sum(multiples, Decimal("0")) / len(multiples)).quantize(Decimal("0.0001"))
            if multiples else None
        ),
        median_net_multiple=Decimal(str(median(multiples))) if multiples else None,
        share_at_least_2x=(
            (Decimal(sum(1 for m in multiples if m >= 2)) / len(multiples)).quantize(
                Decimal("0.0001")
            ) if multiples else None
        ),
        share_total_loss=(
            (Decimal(sum(1 for m in multiples if m < Decimal("0.1"))) / len(multiples)).quantize(
                Decimal("0.0001")
            ) if multiples else None
        ),
        net_pnl_lamports=sum((t.proceeds_lamports or 0) - t.cost_lamports for t in priced),
        assumption_hash=policy.assumption_hash,
        evidence_class=evidence_class,
        trades=tuple(trades),
    )


def backtest(
    events: Iterable[OnChainWalletEvent],
    *,
    tracked_at: Callable[[datetime], frozenset[str]],
    migrations: Mapping[str, datetime] | None = None,
    data_end: datetime,
    policy: CopyPolicy | None = None,
    momentum_buys: int = 10,
    momentum_window: timedelta = timedelta(seconds=60),
    random_seed: int = 7,
    evidence_class: str = "FIXTURE",
) -> dict[str, StrategyReport]:
    """Walk forward over signals; compare against copy-all, random and momentum.

    ``tracked_at(t)`` must return the wallets considered validated using only
    information available at ``t``.
    """

    active = policy or CopyPolicy()
    migrated = dict(migrations or {})
    ordered = deduplicate(events)
    tapes: dict[str, list[OnChainWalletEvent]] = defaultdict(list)
    for event in ordered:
        tapes[event.mint].append(event)
    first_buys: list[OnChainWalletEvent] = []
    seen: set[tuple[str, str]] = set()
    next_sell: dict[tuple[str, str, datetime], datetime] = {}
    for event in ordered:
        key = (event.wallet, event.mint)
        if event.kind is ActivityKind.SWAP_BUY and key not in seen:
            seen.add(key)
            first_buys.append(event)
    for buy in first_buys:
        for event in tapes[buy.mint]:
            if (
                event.wallet == buy.wallet
                and event.kind is ActivityKind.SWAP_SELL
                and event.block_time > buy.block_time
            ):
                next_sell[(buy.wallet, buy.mint, buy.block_time)] = event.block_time
                break

    Signal = tuple[str, str, datetime, datetime | None]

    def run(strategy: str, signals: Sequence[Signal]) -> StrategyReport:
        trades = [
            _simulate(
                strategy=strategy, source=source, mint=mint, signal_at=at,
                tape=tapes[mint], migrated_at=migrated.get(mint), exit_signal_at=exit_at,
                data_end=data_end, policy=active,
            )
            for source, mint, at, exit_at in signals
        ]
        return _report(strategy, trades, active, evidence_class)

    # One copy per (strategy, mint): the first qualifying signal only.
    def first_per_mint(rows: Iterable[Signal]) -> list[Signal]:
        used: set[str] = set()
        out: list[Signal] = []
        for row in rows:
            if row[1] not in used:
                used.add(row[1])
                out.append(row)
        return out

    tracked_signals = first_per_mint(
        (b.wallet, b.mint, b.block_time, next_sell.get((b.wallet, b.mint, b.block_time)))
        for b in first_buys
        if b.wallet in tracked_at(b.block_time)
    )
    creators = {e.mint: e.wallet for e in ordered if e.kind is ActivityKind.CREATE}
    # Naive baseline: the first non-creator buyer of each token.  Copying the
    # creator's own dev buy would be following a manipulation-risk actor.
    copy_all = first_per_mint(
        (b.wallet, b.mint, b.block_time, next_sell.get((b.wallet, b.mint, b.block_time)))
        for b in first_buys
        if creators.get(b.mint) != b.wallet
    )
    rng = random.Random(random_seed)
    mints = sorted(tapes)
    random_signals: list[Signal] = []
    # Random picks happen at the same moments as the strategy under test, or
    # at the naive baseline's moments when nothing was tracked.
    for _source, _mint, at, _exit in tracked_signals or copy_all:
        live = [m for m in mints if tapes[m] and tapes[m][0].block_time <= at
                and (migrated.get(m) is None or migrated[m] > at)]
        if live:
            random_signals.append(("random", rng.choice(live), at, None))
    momentum_signals: list[Signal] = []
    for mint, tape in sorted(tapes.items()):
        buys = [e for e in tape if e.kind is ActivityKind.SWAP_BUY]
        for i in range(len(buys)):
            window = [
                b for b in buys[: i + 1] if buys[i].block_time - b.block_time <= momentum_window
            ]
            if len(window) >= momentum_buys:
                momentum_signals.append(("momentum", mint, buys[i].block_time, None))
                break
    return {
        "tracked_wallets": run("tracked_wallets", tracked_signals),
        "copy_first_non_creator_buyer": run("copy_first_non_creator_buyer", copy_all),
        "random_same_time": run("random_same_time", random_signals),
        "momentum": run("momentum", momentum_signals),
    }


__all__ = [
    "COPYABILITY_VERSION",
    "CopyPolicy",
    "CopyTrade",
    "FillStatus",
    "StrategyReport",
    "backtest",
]
