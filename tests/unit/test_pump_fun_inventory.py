"""Independent address-index launch extraction and backfill null-log handling."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from memeradar_providers.pump_fun_idl import PUMP_FUN_MINT_AUTHORITY, PUMP_FUN_PROGRAM_ID
from memeradar_providers.pump_fun_inventory import launch_from_index_transaction
from memeradar_providers.solana_raw_stream import _references_program

FIXTURE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures/providers/pump_fun_create_v2_index_mainnet.json"
    ).read_text(encoding="utf-8")
)


def test_index_rule_recovers_the_canonical_launch_from_a_real_create() -> None:
    expected = FIXTURE["expected"]
    record = launch_from_index_transaction(
        FIXTURE["transaction"], signature=expected["signature"], slot=expected["slot"]
    )
    assert record is not None
    assert record["mint"] == expected["mint"]
    assert record["instruction"] == expected["instruction"]
    assert record["transaction_failed"] is False


def test_index_rule_requires_both_logged_create_and_mint_authority() -> None:
    expected = FIXTURE["expected"]
    no_logs = copy.deepcopy(FIXTURE["transaction"])
    no_logs["meta"]["logMessages"] = [
        line for line in no_logs["meta"]["logMessages"] if "Instruction: Create" not in line
    ]
    assert launch_from_index_transaction(no_logs, signature="x", slot=expected["slot"]) is None
    other_authority = copy.deepcopy(FIXTURE["transaction"])
    groups = [other_authority["transaction"]["message"]["instructions"]] + [
        group.get("instructions", []) for group in other_authority["meta"]["innerInstructions"]
    ]
    for instructions in groups:
        for instruction in instructions:
            accounts = instruction.get("accounts") or []
            if instruction.get("programId") == PUMP_FUN_PROGRAM_ID and len(accounts) > 1:
                accounts[1] = "11111111111111111111111111111111"
    assert (
        launch_from_index_transaction(other_authority, signature="x", slot=expected["slot"])
        is None
    )


def test_failed_create_is_marked_failed() -> None:
    failed = copy.deepcopy(FIXTURE["transaction"])
    failed["meta"]["err"] = {"InstructionError": [2, {"Custom": 6000}]}
    record = launch_from_index_transaction(failed, signature="x", slot=1)
    assert record is not None and record["transaction_failed"] is True


def test_mint_authority_is_referenced_by_the_fixture_create() -> None:
    keys = [
        key["pubkey"] if isinstance(key, dict) else key
        for key in FIXTURE["transaction"]["transaction"]["message"]["accountKeys"]
    ]
    assert PUMP_FUN_MINT_AUTHORITY in keys


def test_null_logs_skip_only_transactions_that_cannot_touch_pump() -> None:
    vote = "Vote111111111111111111111111111111111111111"
    unrelated = {"transaction": {"message": {"accountKeys": [{"pubkey": vote}]}}, "meta": {}}
    pump = {
        "transaction": {"message": {"accountKeys": [{"pubkey": PUMP_FUN_PROGRAM_ID}]}},
        "meta": {},
    }
    via_lookup = {
        "transaction": {"message": {"accountKeys": []}},
        "meta": {"loadedAddresses": {"writable": [], "readonly": [PUMP_FUN_PROGRAM_ID]}},
    }
    malformed = {"transaction": {}}
    assert _references_program(unrelated, PUMP_FUN_PROGRAM_ID) is False
    assert _references_program(pump, PUMP_FUN_PROGRAM_ID) is True
    assert _references_program(via_lookup, PUMP_FUN_PROGRAM_ID) is True
    assert _references_program(malformed, PUMP_FUN_PROGRAM_ID) is True  # fail closed
