"""M5: a verified mainnet launch -> migrate -> PumpSwap case decodes canonically."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from memeradar_domain import CommitmentState
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.solana_raw_stream import (
    PUMP_FUN_MIGRATE_TAG,
    SolanaLogsNotification,
    map_transaction_to_raw_events,
)

CASE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures/providers/pump_fun_migration_case_mainnet.json"
    ).read_text(encoding="utf-8")
)


def _events():
    transaction = CASE["transaction"]
    notification = SolanaLogsNotification(
        slot=transaction["slot"],
        signature=CASE["migration"]["signature"],
        error=transaction["meta"]["err"],
        logs=tuple(transaction["meta"]["logMessages"]),
        commitment=CommitmentState.FINALIZED,
        observed_at=datetime.fromtimestamp(transaction["blockTime"], UTC),
    )
    return map_transaction_to_raw_events(
        transaction,
        notification,
        ingested_at=datetime.fromtimestamp(transaction["blockTime"] + 1, UTC),
        transport="solana-rpc-backfill",
        fail_on_unknown_create=True,
    )


def test_migrate_is_routed_by_program_and_discriminator_with_the_launch_mint() -> None:
    migrates = [e for e in _events() if e.payload.get("instruction_type") == "migrate"]
    assert len(migrates) == 1
    event = migrates[0]
    assert event.program_id == PUMP_FUN_PROGRAM_ID
    assert event.discriminator_or_tag == PUMP_FUN_MIGRATE_TAG.hex()
    assert event.payload["mint_address"] == CASE["launch"]["mint"]
    assert event.commitment is CommitmentState.FINALIZED
    assert event.slot > CASE["launch"]["slot"]


def test_migration_hands_off_to_the_pumpswap_pool_seen_on_the_dex() -> None:
    message = CASE["transaction"]["transaction"]["message"]
    keys = [key["pubkey"] if isinstance(key, dict) else key for key in message["accountKeys"]]
    programs = {ix.get("programId") for ix in message["instructions"]} | {
        ix.get("programId")
        for group in CASE["transaction"]["meta"].get("innerInstructions", [])
        for ix in group["instructions"]
    }
    assert CASE["pumpswap"]["program_id"] in programs
    assert CASE["pumpswap"]["pool"] in keys
