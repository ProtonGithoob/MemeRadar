"""Wallet activity extraction on real finalized mainnet transactions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from memeradar_application.onchain_wallet_events import ActivityKind, Reconciliation
from memeradar_providers.pump_fun_wallet_activity import wallet_activities

ROOT = Path(__file__).resolve().parents[2] / "fixtures/providers"
TRADES = json.loads((ROOT / "pump_fun_wallet_trades_mainnet.json").read_text())
MIGRATION = json.loads((ROOT / "pump_fun_migration_case_mainnet.json").read_text())
MINT = TRADES["mint"]


def _run(name: str, transaction=None):
    item = TRADES["transactions"][name]
    return wallet_activities(
        transaction or item["transaction"], mint=MINT, signature=item["signature"]
    )


def test_real_buy_and_sell_are_verified_swaps_reconciled_to_balances() -> None:
    (buy,) = _run("buy")
    (sell,) = _run("sell")
    assert buy.kind is ActivityKind.SWAP_BUY and buy.token_delta_raw > 0
    assert buy.quote_delta_lamports is not None and buy.quote_delta_lamports < 0
    assert sell.kind is ActivityKind.SWAP_SELL and sell.token_delta_raw < 0
    assert {buy.reconciliation, sell.reconciliation} == {Reconciliation.MATCHED}
    assert buy.reference_price is not None


def test_balance_disagreement_is_flagged_not_trusted() -> None:
    tampered = copy.deepcopy(TRADES["transactions"]["buy"]["transaction"])
    for entry in tampered["meta"]["postTokenBalances"]:
        if entry.get("mint") == MINT and entry.get("owner"):
            amount = int(entry["uiTokenAmount"]["amount"])
            entry["uiTokenAmount"]["amount"] = str(amount + 12345)
    reconciliations = {a.reconciliation for a in _run("buy", tampered) if a.is_verified_swap}
    assert Reconciliation.MISMATCH in reconciliations


def test_failed_transaction_has_no_position_effect() -> None:
    failed = copy.deepcopy(TRADES["transactions"]["buy"]["transaction"])
    failed["meta"]["err"] = {"InstructionError": [3, {"Custom": 6001}]}
    (only,) = _run("buy", failed)
    assert only.kind is ActivityKind.FAILED and only.token_delta_raw == 0


def test_migration_moves_liquidity_without_creating_buys() -> None:
    activities = wallet_activities(
        MIGRATION["transaction"],
        mint=MIGRATION["launch"]["mint"],
        signature=MIGRATION["migration"]["signature"],
    )
    kinds = {a.kind for a in activities}
    assert ActivityKind.LIQUIDITY_MIGRATION in kinds
    assert ActivityKind.SWAP_BUY not in kinds and ActivityKind.SWAP_SELL not in kinds
    moved = [a for a in activities if a.token_delta_raw]
    assert moved and all(a.kind is ActivityKind.UNVERIFIED_VENUE for a in moved)
