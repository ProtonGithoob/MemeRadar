"""Reverse wallet intelligence: classification, registry, leakage, categories, copyability.

All fixtures are synthetic but internally consistent: every trade's reserves
come from the same constant-product curve.  Results here are FIXTURE-only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.onchain_wallet_events import (
    ActivityKind,
    CurveState,
    OnChainWalletEvent,
    OutcomeClass,
    Reconciliation,
    build_registry_record,
    curve_state_before,
    deduplicate,
)
from memeradar_application.wallet_copyability import CopyPolicy, FillStatus, backtest
from memeradar_application.wallet_intelligence import (
    WalletCategory,
    build_profiles,
    co_buy_clusters,
    wallet_signal_features,
)

T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)
START = CurveState(30_000_000_000, 1_073_000_000_000_000)


class Tape:
    """Builds a mint's trades along one curve so reserves stay consistent."""

    def __init__(self, mint: str, creator: str = "Creator") -> None:
        self.mint = mint
        self.state = START
        self.events: list[OnChainWalletEvent] = [
            OnChainWalletEvent(
                wallet=creator, mint=mint, signature=f"{mint}-create", slot=1000, event_index=0,
                block_time=T0, kind=ActivityKind.CREATE, token_delta_raw=0,
                quote_delta_lamports=None, reconciliation=Reconciliation.NOT_APPLICABLE,
            )
        ]
        self.n = 0

    def buy(self, wallet: str, sol: float, seconds: float, slot: int | None = None):
        lamports = int(sol * 1e9)
        tokens, self.state = self.state.buy(lamports, 0)
        return self._add(wallet, ActivityKind.SWAP_BUY, tokens, -lamports, seconds, slot)

    def sell(self, wallet: str, tokens: int, seconds: float, slot: int | None = None):
        lamports, self.state = self.state.sell(tokens, 0)
        return self._add(wallet, ActivityKind.SWAP_SELL, -tokens, lamports, seconds, slot)

    def _add(self, wallet, kind, tokens, quote, seconds, slot):
        self.n += 1
        event = OnChainWalletEvent(
            wallet=wallet, mint=self.mint, signature=f"{self.mint}-{self.n}",
            slot=slot if slot is not None else 1000 + int(seconds / 0.4), event_index=0,
            block_time=T0 + timedelta(seconds=seconds), kind=kind, token_delta_raw=tokens,
            quote_delta_lamports=quote, reconciliation=Reconciliation.MATCHED,
            venue="PUMPFUN_CURVE", virtual_sol_reserves=self.state.virtual_sol,
            virtual_token_reserves=self.state.virtual_token,
        )
        self.events.append(event)
        return event


def _registry(tapes, now):
    return {
        t.mint: build_registry_record(
            mint=t.mint, launch_at=T0, activities=t.events, now=now, creator="Creator",
            history_complete=True,
        )
        for t in tapes
    }


# ------------------------------------------------------------ classification
def test_receiving_tokens_is_never_a_buy() -> None:
    with pytest.raises(ValueError):
        OnChainWalletEvent(
            wallet="W", mint="M", signature="s", slot=1, event_index=0, block_time=T0,
            kind=ActivityKind.SWAP_BUY, token_delta_raw=100, quote_delta_lamports=None,
            reconciliation=Reconciliation.UNKNOWN,
        )
    transfer = OnChainWalletEvent(
        wallet="W", mint="M", signature="s", slot=1, event_index=0, block_time=T0,
        kind=ActivityKind.TRANSFER_IN, token_delta_raw=100, quote_delta_lamports=None,
        reconciliation=Reconciliation.NOT_APPLICABLE,
    )
    assert transfer.is_verified_swap is False


def test_duplicate_trades_from_overlapping_sources_count_once() -> None:
    tape = Tape("M1")
    event = tape.buy("W", 1, 10)
    assert len(deduplicate([event, event, *tape.events])) == len(tape.events)


def test_curve_math_round_trip_loses_only_fees_and_is_point_in_time() -> None:
    tokens, after = START.buy(1_000_000_000, 100)
    back, _ = after.sell(tokens, 100)
    assert 0.97e9 < back < 1e9
    tape = Tape("M1")
    tape.buy("A", 5, 10)
    tape.buy("B", 5, 20)
    early = curve_state_before(tape.events, T0 + timedelta(seconds=15))
    assert early is not None and early.virtual_sol == 35_000_000_000


# ------------------------------------------------------------------ registry
def test_registry_includes_non_movers_and_censors_after_migration() -> None:
    flat = Tape("FLAT")
    flat.buy("A", 0.1, 5)
    winner = Tape("WIN")
    winner.buy("A", 0.1, 5)
    for i in range(20):
        winner.buy(f"B{i}", 2, 60 + i)
    now = T0 + timedelta(days=2)
    flat_record = build_registry_record(mint="FLAT", launch_at=T0, activities=flat.events,
                                        now=now, history_complete=True)
    win_record = build_registry_record(mint="WIN", launch_at=T0, activities=winner.events,
                                       now=now, history_complete=True,
                                       migrated_at=T0 + timedelta(minutes=10))
    flat_1h = next(o for o in flat_record.outcomes if o.horizon == "1h")
    assert flat_1h.outcome is OutcomeClass.NO_MOVE
    win_1h = next(o for o in win_record.outcomes if o.horizon == "1h")
    assert win_1h.outcome in {OutcomeClass.X2, OutcomeClass.X5, OutcomeClass.X10}
    assert win_1h.censor_reason == "PATH_ENDS_AT_MIGRATION"  # a lower bound, not a final
    # The observable path already ended, so even the unfinished 7d horizon is
    # a censored lower bound rather than PENDING; a non-migrated flat token
    # still waits for its 7d horizon.
    assert next(o for o in win_record.outcomes if o.horizon == "7d").censor_reason == (
        "PATH_ENDS_AT_MIGRATION"
    )
    assert next(o for o in flat_record.outcomes if o.horizon == "7d").outcome is (
        OutcomeClass.PENDING
    )


# ------------------------------------------------ profiles and leakage
def test_cost_basis_from_transfers_stays_unknown() -> None:
    tape = Tape("M1")
    tape.buy("A", 1, 10)
    tape.events.append(
        OnChainWalletEvent(
            wallet="W", mint="M1", signature="xfer", slot=1100, event_index=0,
            block_time=T0 + timedelta(seconds=30), kind=ActivityKind.TRANSFER_IN,
            token_delta_raw=10_000_000_000, quote_delta_lamports=None,
            reconciliation=Reconciliation.NOT_APPLICABLE,
        )
    )
    tape.sell("W", 10_000_000_000, 40)
    profile = build_profiles(tape.events, {}, as_of=T0 + timedelta(hours=1))["W"]
    assert profile.realized_unknown_events == 1
    assert profile.realized_pnl_sol == Decimal("0")  # nothing known, not "zero profit"
    assert profile.closed_positions == 0


def test_future_outcomes_do_not_leak_into_past_profiles() -> None:
    tapes = []
    for name in ("A1", "A2", "A3"):
        tape = Tape(name)
        bought = tape.buy("Smart", 0.5, 3)
        for i in range(30):
            tape.buy(f"{name}-crowd{i}", 3, 30 + i)
        tape.sell("Smart", bought.token_delta_raw, 200)
        tapes.append(tape)
    events = [e for t in tapes for e in t.events]
    now = T0 + timedelta(days=2)
    registry = _registry(tapes, now)
    before = build_profiles(events, registry, as_of=T0 + timedelta(hours=1))["Smart"]
    after = build_profiles(events, registry, as_of=T0 + timedelta(hours=25))["Smart"]
    # At 1h the 24h outcomes are not observable yet: no success claim.
    assert before.observable_outcome_tokens == 0
    assert WalletCategory.EARLY_SMART_MONEY_CANDIDATE not in before.categories
    assert WalletCategory.LOW_EVIDENCE in before.categories
    assert after.observable_outcome_tokens == 3
    assert WalletCategory.EARLY_SMART_MONEY_CANDIDATE in after.categories
    assert after.realized_pnl_sol > 0


def test_manipulation_evidence_blocks_smart_money_status_and_signal_counts() -> None:
    tapes = []
    for name in ("B1", "B2", "B3"):
        tape = Tape(name)
        bought = tape.buy("Sniper", 0.5, 0.4, slot=1001)  # one slot after create
        for i in range(30):
            tape.buy(f"{name}-crowd{i}", 3, 30 + i)
        tape.sell("Sniper", bought.token_delta_raw, 200)
        tapes.append(tape)
    events = [e for t in tapes for e in t.events]
    registry = _registry(tapes, T0 + timedelta(days=2))
    profile = build_profiles(events, registry, as_of=T0 + timedelta(hours=25))["Sniper"]
    assert WalletCategory.POTENTIAL_INSIDER in profile.categories
    assert WalletCategory.EARLY_SMART_MONEY_CANDIDATE not in profile.categories
    assert profile.risk_only is True
    features = wallet_signal_features({"Sniper": profile}, ["Sniper"])
    assert features["raw_smart_wallet_count"] == 0
    assert features["risk_category_buyer_count"] == 1


def test_creator_trading_own_launch_is_creator_linked() -> None:
    tape = Tape("C1", creator="Dev")
    bought = tape.buy("Dev", 1, 1)
    tape.sell("Dev", bought.token_delta_raw, 50)
    profile = build_profiles(tape.events, {}, as_of=T0 + timedelta(hours=1))["Dev"]
    assert WalletCategory.CREATOR_LINKED in profile.categories


# ------------------------------------------------------------- clusters
def test_synchronized_co_buying_forms_a_cluster_but_one_shared_slot_does_not() -> None:
    events = []
    for index, name in enumerate(("K1", "K2")):
        tape = Tape(name)
        for wallet in ("X", "Y", "Z"):
            tape.buy(wallet, 0.2, 10 + index, slot=2000 + index)
        events += tape.events
    lone = Tape("K3")
    for wallet in ("P", "Q", "R"):
        lone.buy(wallet, 0.2, 10, slot=3000)
    events += lone.events
    clusters = co_buy_clusters(events, as_of=T0 + timedelta(hours=1))
    assert set(clusters) == {"X", "Y", "Z"}
    assert len(set(clusters.values())) == 1


# ---------------------------------------------------------- copyability
def test_copy_entry_happens_after_the_delay_and_never_at_the_wallet_price() -> None:
    tape = Tape("D1")
    signal = tape.buy("Leader", 0.5, 5)
    for i in range(10):
        tape.buy(f"crowd{i}", 2, 10 + i)  # price runs up during our delay
    tape.sell("Leader", signal.token_delta_raw, 300)
    reports = backtest(
        tape.events, tracked_at=lambda _t: frozenset({"Leader"}),
        data_end=T0 + timedelta(hours=3), policy=CopyPolicy(),
    )
    trade = reports["tracked_wallets"].trades[0]
    assert trade.status is FillStatus.FILLED
    assert trade.entry_at == signal.block_time + timedelta(seconds=17)
    # Our tokens are bought at the run-up curve state, so fewer than the leader's.
    assert trade.tokens < signal.token_delta_raw * 333 // 500
    assert trade.exit_reason == "FOLLOW_WALLET_SELL"


def test_untracked_wallets_produce_no_tracked_signal_and_migration_is_censored() -> None:
    tape = Tape("D2")
    tape.buy("Leader", 0.5, 5)
    tape.buy("x", 1, 30)
    reports = backtest(
        tape.events, tracked_at=lambda _t: frozenset(),
        migrations={"D2": T0 + timedelta(minutes=5)},
        data_end=T0 + timedelta(hours=3), policy=CopyPolicy(),
    )
    assert reports["tracked_wallets"].signals == 0
    copy_all = reports["copy_all_buyers"].trades[0]
    assert copy_all.status is FillStatus.UNPRICED_MIGRATION
    assert copy_all.net_multiple is None


def test_dead_token_after_entry_is_a_real_loss_not_a_skip() -> None:
    tape = Tape("D3")
    leader = tape.buy("Leader", 0.5, 5)
    big = tape.buy("Whale", 20, 10)
    tape.sell("Whale", big.token_delta_raw, 40)  # dump inside our hold window
    tape.sell("Leader", leader.token_delta_raw, 41)
    reports = backtest(
        tape.events, tracked_at=lambda _t: frozenset({"Leader"}),
        data_end=T0 + timedelta(hours=3), policy=CopyPolicy(exit_on_wallet_sell=False),
    )
    trade = reports["tracked_wallets"].trades[0]
    assert trade.status is FillStatus.FILLED
    assert trade.net_multiple is not None and trade.net_multiple < Decimal("0.5")
