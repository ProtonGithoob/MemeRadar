"""Pump.fun trade tape wiring: registry routing, live tracking and features."""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from memeradar_application.early_features import EarlyFeatureEngine
from memeradar_domain import CommitmentState, Observation, Provenance, QualityState
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
from memeradar_providers.pump_fun_events import (
    PUMP_FUN_TRADE_EVENT_DISCRIMINATOR,
    extract_pump_fun_trade_events,
    trade_events_to_raw_transactions,
)
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID
from memeradar_providers.solana_raw_stream import (
    SolanaLogsNotification,
    SolanaRawTransactionSource,
)
from memeradar_providers.solana_rpc import SolanaRpcAdapter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "providers"
    / "pump_fun_trade_events_mainnet.json"
)


def _fixture(index: int = 0) -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["transactions"][index]


def _raw_trades(index: int = 0):
    transaction = _fixture(index)
    extraction = extract_pump_fun_trade_events(transaction["log_messages"])  # type: ignore[arg-type]
    block_time = datetime.fromtimestamp(transaction["block_time"], UTC)  # type: ignore[arg-type]
    return trade_events_to_raw_transactions(
        extraction.events,
        signature=str(transaction["signature"]),
        slot=int(transaction["slot"]),  # type: ignore[arg-type]
        observed_at=block_time + timedelta(seconds=1),
        ingested_at=block_time + timedelta(seconds=2),
        commitment=CommitmentState.CONFIRMED,
        transport="fixture-live",
    )


def test_registry_routes_trade_events_by_program_and_event_discriminator() -> None:
    (raw,) = _raw_trades()

    event = CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY).decode_live(raw)

    assert event.event_type == "trade_event"
    assert event.program_id == PUMP_FUN_PROGRAM_ID
    assert event.discriminator_or_tag == PUMP_FUN_TRADE_EVENT_DISCRIMINATOR.hex()
    assert event.token_id is not None
    assert event.normalized_payload["protocol_identity_verified"] is True
    assert event.normalized_payload["side"] in {"buy", "sell"}
    assert event.normalized_payload["market_price"] is not None


def _notification(transaction: dict[str, object]) -> SolanaLogsNotification:
    return SolanaLogsNotification(
        slot=int(transaction["slot"]),  # type: ignore[arg-type]
        signature=str(transaction["signature"]),
        error=None,
        logs=tuple(transaction["log_messages"]),  # type: ignore[arg-type]
        commitment=CommitmentState.CONFIRMED,
        observed_at=datetime.fromtimestamp(transaction["block_time"], UTC),  # type: ignore[arg-type]
    )


def test_live_source_emits_trades_only_for_recently_launched_tracked_mints() -> None:
    transaction = _fixture()
    mint = transaction["expected"]["mint"]  # type: ignore[index]
    seen_at = datetime.fromtimestamp(transaction["block_time"], UTC)  # type: ignore[arg-type]
    source = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=asyncio.Event(),
        trade_tracking_window=timedelta(minutes=5),
        max_trades_per_mint=1,
    )
    notification = _notification(transaction)

    untracked = source._tracked_trade_events(
        notification.logs, notification, observed_at=seen_at, reconnect_reason=None
    )
    source._track_mint(mint, seen_at)
    tracked = source._tracked_trade_events(
        notification.logs, notification, observed_at=seen_at, reconnect_reason=None
    )
    capped = source._tracked_trade_events(
        notification.logs, notification, observed_at=seen_at, reconnect_reason=None
    )
    expired = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=asyncio.Event(),
        trade_tracking_window=timedelta(minutes=5),
    )
    expired._track_mint(mint, seen_at - timedelta(minutes=10))
    late = expired._tracked_trade_events(
        notification.logs, notification, observed_at=seen_at, reconnect_reason=None
    )

    assert untracked == ()
    assert len(tracked) == 1
    assert tracked[0].discriminator_or_tag == PUMP_FUN_TRADE_EVENT_DISCRIMINATOR.hex()
    assert capped == ()
    assert source.metrics["trade_events_capped"] == 1
    assert late == ()


def test_forged_trade_line_from_another_program_is_not_emitted() -> None:
    transaction = _fixture()
    mint = transaction["expected"]["mint"]  # type: ignore[index]
    data_line = next(
        line
        for line in transaction["log_messages"]  # type: ignore[union-attr]
        if line.startswith("Program data: ")
        and base64.b64decode(line[14:])[:8] == PUMP_FUN_TRADE_EVENT_DISCRIMINATOR
    )
    forged = dict(transaction)
    forged["log_messages"] = [
        "Program 11111111111111111111111111111111 invoke [1]",
        data_line,
        "Program 11111111111111111111111111111111 success",
    ]
    seen_at = datetime.fromtimestamp(transaction["block_time"], UTC)  # type: ignore[arg-type]
    source = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=asyncio.Event(),
    )
    source._track_mint(mint, seen_at)
    notification = _notification(forged)

    assert source._tracked_trade_events(
        notification.logs, notification, observed_at=seen_at, reconnect_reason=None
    ) == ()


def test_trade_tape_payload_is_counted_as_trades_by_the_feature_engine() -> None:
    observations = []
    token_id = None
    for index in range(1):
        (raw,) = _raw_trades(index)
        event = CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY).decode_live(raw)
        payload = dict(event.normalized_payload)
        payload["collection_mode"] = "PRODUCTION"
        token_id = event.token_id
        observations.append(
            Observation(
                kind="chain.event",
                provenance=Provenance(
                    provider="fixture-live",
                    source_id=event.signature,
                    observed_at=event.occurred_at,
                    parser_version=event.parser_version,
                ),
                occurred_at=event.occurred_at,
                observed_at=event.occurred_at,
                ingested_at=event.occurred_at,
                quality_state=QualityState.FRESH,
                normalized_payload=payload,
                token_id=event.token_id,
            )
        )
    assert token_id is not None
    checkpoint = max(item.occurred_at for item in observations if item.occurred_at)

    snapshot = EarlyFeatureEngine().compute(token_id, checkpoint, tuple(observations))

    largest = max(
        snapshot.windows.values(), key=lambda window: window.metrics.get("trade_count") or 0
    )
    assert largest.metrics["trade_count"] >= 1
    assert (largest.metrics.get("buy_count") or 0) + (largest.metrics.get("sell_count") or 0) >= 1


def test_backfill_recovers_trade_events_through_the_same_log_decoder() -> None:
    from types import SimpleNamespace

    from memeradar_application.stream_integrity import BackfillRequest
    from memeradar_providers.solana_raw_stream import SolanaRpcBackfillAdapter

    fixture = _fixture()
    slot = int(fixture["slot"])  # type: ignore[arg-type]
    block_time = datetime.fromtimestamp(fixture["block_time"], UTC)  # type: ignore[arg-type]
    transaction = {
        "transaction": {
            "signatures": [fixture["signature"]],
            "message": {"accountKeys": [PUMP_FUN_PROGRAM_ID], "instructions": []},
        },
        "meta": {"err": None, "logMessages": fixture["log_messages"], "innerInstructions": []},
    }
    rpc = SolanaRpcAdapter("https://fixture.solana.example")

    async def finalized(*_args: object, **_kwargs: object) -> int:
        return slot + 100

    async def fetch_blocks(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(normalized_payload={"slots": (slot,)}, observed_at=block_time)

    async def fetch_block(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            normalized_payload={"slot": slot, "transactions": (transaction,)},
            observed_at=block_time,
            occurred_at=block_time,
        )

    rpc.fetch_finalized_slot = finalized  # type: ignore[method-assign]
    rpc.fetch_blocks = fetch_blocks  # type: ignore[method-assign]
    rpc.fetch_block = fetch_block  # type: ignore[method-assign]

    result = asyncio.run(
        SolanaRpcBackfillAdapter(rpc).fetch(
            BackfillRequest(chain="solana", stream_id="fixture", from_slot=slot, to_slot=slot)
        )
    )

    trades = [
        item
        for item in result.transactions
        if item.discriminator_or_tag == PUMP_FUN_TRADE_EVENT_DISCRIMINATOR.hex()
    ]
    assert len(trades) == 1
    (live,) = _raw_trades()
    assert trades[0].event_index == live.event_index
    assert trades[0].payload["mint_address"] == live.payload["mint_address"]
    assert trades[0].payload["token_amount_raw"] == live.payload["token_amount_raw"]
