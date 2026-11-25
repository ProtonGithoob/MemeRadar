"""PumpSwap (pump_amm) trade events: identity, layout and reconciliation."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from memeradar_application.onchain_wallet_events import ActivityKind, Reconciliation
from memeradar_providers.pump_fun_wallet_activity import wallet_activities
from memeradar_providers.pump_swap_events import (
    PUMP_SWAP_PROGRAM_ID,
    decode_pump_swap_event,
    extract_pump_swap_events,
)
from memeradar_providers.transport import ProviderSchemaError

CASE = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/providers/pump_swap_trades_mainnet.json")
    .read_text()
)
MINT = CASE["mint"]


def _tx(side: str):
    return CASE["transactions"][side]["transaction"], CASE["transactions"][side]["signature"]


def _balance(tx, key: str, owner: str) -> int:
    return sum(
        int(entry["uiTokenAmount"]["amount"])
        for entry in tx["meta"][key]
        if entry.get("owner") == owner and entry["mint"] == MINT
    )


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_event_amounts_and_reserves_match_on_chain_balances(side: str) -> None:
    tx, _ = _tx(side)
    (event,) = extract_pump_swap_events(tx["meta"]["logMessages"])
    assert event.is_buy is (side == "buy")
    assert event.pool == CASE["pool"]
    user_delta = _balance(tx, "postTokenBalances", event.user) - _balance(
        tx, "preTokenBalances", event.user
    )
    assert user_delta == (event.base_amount if event.is_buy else -event.base_amount)
    base_after, _quote_after = event.post_trade_reserves
    assert base_after == _balance(tx, "postTokenBalances", event.pool)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_amm_trades_become_reconciled_swaps_with_pool_reference_price(side: str) -> None:
    tx, signature = _tx(side)
    swaps = [a for a in wallet_activities(tx, mint=MINT, signature=signature)
             if a.venue == "PUMPSWAP"]
    assert len(swaps) == 1
    swap = swaps[0]
    assert swap.kind is (ActivityKind.SWAP_BUY if side == "buy" else ActivityKind.SWAP_SELL)
    assert swap.reconciliation is Reconciliation.MATCHED
    assert swap.reference_price is not None and swap.reference_price > 0
    assert not [a for a in wallet_activities(tx, mint=MINT, signature=signature)
                if a.kind is ActivityKind.UNVERIFIED_VENUE and a.wallet == swap.wallet]


def test_event_logged_outside_pump_amm_context_is_ignored() -> None:
    tx, _ = _tx("buy")
    data = next(line for line in tx["meta"]["logMessages"]
                if line.startswith("Program data: ")
                and base64.b64decode(line[14:])[:8].hex() == "67f4521f2cf57777")
    forged = ["Program 11111111111111111111111111111111 invoke [1]", data,
              "Program 11111111111111111111111111111111 success"]
    assert extract_pump_swap_events(forged) == ()
    real = [f"Program {PUMP_SWAP_PROGRAM_ID} invoke [1]", data,
            f"Program {PUMP_SWAP_PROGRAM_ID} success"]
    assert len(extract_pump_swap_events(real)) == 1


def test_truncated_or_foreign_payload_fails_closed() -> None:
    tx, _ = _tx("buy")
    data = next(line for line in tx["meta"]["logMessages"]
                if line.startswith("Program data: ")
                and base64.b64decode(line[14:])[:8].hex() == "67f4521f2cf57777")
    raw = base64.b64decode(data[14:])
    with pytest.raises(ProviderSchemaError):
        decode_pump_swap_event(raw[:100])
    with pytest.raises(ProviderSchemaError):
        decode_pump_swap_event(b"\x00" * 300)


def test_two_swaps_by_one_user_reconcile_against_the_total_delta() -> None:
    import copy

    tx, signature = _tx("buy")
    tx = copy.deepcopy(tx)
    (event,) = extract_pump_swap_events(tx["meta"]["logMessages"])
    logs = tx["meta"]["logMessages"]
    data_index = next(
        i for i, line in enumerate(logs)
        if line.startswith("Program data: ")
        and base64.b64decode(line[len("Program data: "):])[:8]
        == bytes.fromhex("67f4521f2cf57777")
    )
    logs.insert(data_index + 1, logs[data_index])  # same AMM frame, second BuyEvent
    for entry in tx["meta"]["postTokenBalances"]:
        if entry.get("mint") != MINT:
            continue
        amount = int(entry["uiTokenAmount"]["amount"])
        if entry.get("owner") == event.user:
            entry["uiTokenAmount"]["amount"] = str(amount + event.base_amount)
        elif entry.get("owner") == event.pool:
            entry["uiTokenAmount"]["amount"] = str(amount - event.base_amount)
    swaps = [a for a in wallet_activities(tx, mint=MINT, signature=signature)
             if a.venue == "PUMPSWAP"]
    assert len(swaps) == 2
    assert {s.reconciliation for s in swaps} == {Reconciliation.MATCHED}
