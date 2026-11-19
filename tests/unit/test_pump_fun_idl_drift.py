"""Pump.fun official IDL drift: every new instruction is accounted for, and
v3 trades still land in the TradeEvent tape (finalized mainnet fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memeradar_providers.pump_fun_events import (
    extract_pump_fun_trade_events,
    pump_fun_logged_instructions,
)
from memeradar_providers.pump_fun_idl import (
    PUMP_FUN_LATEST_IDL_REVISION,
    PUMP_FUN_LATEST_IDL_SHA256,
    PUMP_FUN_UNROUTED_INSTRUCTIONS,
)

FIXTURE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures/providers/pump_fun_v3_trades_mainnet.json"
    ).read_text(encoding="utf-8")
)
PINNED_ROUTED_OR_KNOWN = 47


def test_every_instruction_new_in_the_official_idl_is_classified() -> None:
    assert FIXTURE["official_idl_revision"] == PUMP_FUN_LATEST_IDL_REVISION
    assert FIXTURE["official_idl_sha256"] == PUMP_FUN_LATEST_IDL_SHA256
    official = FIXTURE["official_idl_instructions"]
    assert len(official) == PINNED_ROUTED_OR_KNOWN + len(PUMP_FUN_UNROUTED_INSTRUCTIONS)
    for name, (discriminator, status) in PUMP_FUN_UNROUTED_INSTRUCTIONS.items():
        assert official[name] == discriminator, name
        assert "ROUTING" in status or status.endswith(("NOT_TRADE", "TODO_VERIFY"))


def test_trade_event_layout_only_grew_after_the_decoded_prefix() -> None:
    fields = FIXTURE["trade_event_fields"]
    # The decoder reads the fixed prefix through ix_name; later fields are
    # appended (creator_fee_unclaimed is new) and must not shift it.
    assert fields.index("ix_name") == 21
    assert fields[-1] == "creator_fee_unclaimed"


@pytest.mark.parametrize("index", range(3))
def test_v3_trades_produce_one_trade_event_per_logged_trade(index: int) -> None:
    transaction = FIXTURE["transactions"][index]
    logs = transaction["log_messages"]
    logged = [name for name in pump_fun_logged_instructions(logs)
              if name.lower().startswith(("buy", "sell"))]
    assert any(name.endswith("V3") for name in logged)
    events = extract_pump_fun_trade_events(logs).events
    assert len(events) == len(logged)
    for name, event in zip(logged, events, strict=True):
        assert event.is_buy is name.lower().startswith("buy")
        assert event.sol_amount_lamports > 0
