"""Pump.fun TradeEvent log decoding against verified mainnet fixtures."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from memeradar_providers.pump_fun_events import (
    PUMP_FUN_TRADE_EVENT_DISCRIMINATOR,
    decode_pump_fun_trade_event,
    extract_pump_fun_trade_events,
)
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.transport import ProviderSchemaError

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "providers"
    / "pump_fun_trade_events_mainnet.json"
)
FOREIGN_PROGRAM = "11111111111111111111111111111111"


def _transactions() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["transactions"]


def _trade_data_line(transaction: dict[str, object]) -> str:
    logs = transaction["log_messages"]
    assert isinstance(logs, list)
    return next(
        line
        for line in logs
        if line.startswith("Program data: ")
        and base64.b64decode(line[14:])[:8] == PUMP_FUN_TRADE_EVENT_DISCRIMINATOR
    )


def test_discriminator_is_the_anchor_trade_event_hash() -> None:
    assert PUMP_FUN_TRADE_EVENT_DISCRIMINATOR.hex() == "bddb7fd34ee661ee"


@pytest.mark.parametrize("index", range(3))
def test_mainnet_trade_events_decode_to_verified_balance_and_time_values(index: int) -> None:
    transaction = _transactions()[index]
    expected = transaction["expected"]
    assert isinstance(expected, dict)

    extraction = extract_pump_fun_trade_events(transaction["log_messages"])  # type: ignore[arg-type]

    assert extraction.logs_truncated is False
    assert len(extraction.events) == 1
    event = extraction.events[0]
    assert event.mint == expected["mint"]
    assert event.user == expected["user"]
    assert event.is_buy is expected["is_buy"]
    assert event.token_amount_raw == expected["token_amount"]
    assert event.sol_amount_lamports == expected["sol_amount"]
    assert event.occurred_at == datetime.fromtimestamp(transaction["block_time"], UTC)  # type: ignore[arg-type]
    assert event.ix_name == expected["ix_name"]
    payload = event.to_payload()
    assert payload["side"] == ("buy" if expected["is_buy"] else "sell")
    # Executed and market reference prices are separate fields and both near
    # the curve price for an ordinary bonding-curve trade.
    executed = event.executed_price
    reference = event.market_reference_price
    assert executed is not None and reference is not None
    assert payload["executed_price_lamports_per_raw_token"] != (
        payload["market_reference_price_lamports_per_raw_token"]
    )
    assert reference / 2 < executed < reference * 2


def test_trade_event_logged_by_another_program_is_ignored() -> None:
    data_line = _trade_data_line(_transactions()[0])
    forged = [
        f"Program {FOREIGN_PROGRAM} invoke [1]",
        data_line,
        f"Program {FOREIGN_PROGRAM} success",
    ]
    nested = [
        f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]",
        f"Program {FOREIGN_PROGRAM} invoke [2]",
        data_line,
        f"Program {FOREIGN_PROGRAM} success",
        f"Program {PUMP_FUN_PROGRAM_ID} success",
    ]

    assert extract_pump_fun_trade_events(forged).events == ()
    assert extract_pump_fun_trade_events(nested).events == ()


def test_trade_event_after_nested_call_returns_is_attributed_to_pump() -> None:
    data_line = _trade_data_line(_transactions()[0])
    logs = [
        f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]",
        f"Program {FOREIGN_PROGRAM} invoke [2]",
        f"Program {FOREIGN_PROGRAM} success",
        data_line,
        f"Program {PUMP_FUN_PROGRAM_ID} success",
    ]

    assert len(extract_pump_fun_trade_events(logs).events) == 1


def test_truncated_logs_are_reported_incomplete() -> None:
    logs = [f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]", "Log truncated"]

    extraction = extract_pump_fun_trade_events(logs)

    assert extraction.events == ()
    assert extraction.logs_truncated is True


def test_short_or_malformed_pump_trade_event_fails_closed() -> None:
    raw = base64.b64decode(_trade_data_line(_transactions()[0])[14:])

    with pytest.raises(ProviderSchemaError):
        decode_pump_fun_trade_event(raw[:100])
    corrupted = bytearray(raw)
    corrupted[56] = 7
    with pytest.raises(ProviderSchemaError, match="is_buy"):
        decode_pump_fun_trade_event(bytes(corrupted))
    logs = [
        f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]",
        "Program data: " + base64.b64encode(raw[:100]).decode(),
        f"Program {PUMP_FUN_PROGRAM_ID} success",
    ]
    with pytest.raises(ProviderSchemaError):
        extract_pump_fun_trade_events(logs)
