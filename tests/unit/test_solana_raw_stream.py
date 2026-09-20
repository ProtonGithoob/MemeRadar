"""Contract tests for the keyless Solana logs-to-raw-transaction seam."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import CommitmentState
from memeradar_providers import solana_raw_stream
from memeradar_providers.solana_raw_stream import (
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_PROGRAM_ID,
    SolanaRawTransactionSource,
    map_transaction_to_raw_events,
    parse_logs_notification,
)
from memeradar_providers.solana_rpc import SolanaRpcAdapter
from memeradar_providers.transport import ProviderSchemaError

NOW = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)
SIGNATURE = "5" * 88
MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
USER = "2J2rtMBRLxAbFkSLgrsuSNN8N5KMTJVaRTdnGfbZ5Vjw"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + (encoded or "")


def _notification() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "method": "logsNotification",
        "params": {
            "subscription": 7,
            "result": {
                "context": {"slot": 448780651},
                "value": {
                    "signature": SIGNATURE,
                    "err": None,
                    "logs": [
                        f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]",
                        "Program log: Instruction: CreateV2",
                    ],
                },
            },
        },
    }


def _transaction() -> dict[str, object]:
    accounts = [MINT]
    for _ in range(4):
        accounts.append("So11111111111111111111111111111111111111112")
    accounts.extend([USER, "11111111111111111111111111111111", TOKEN_2022])
    for _ in range(8):
        accounts.append("So11111111111111111111111111111111111111112")
    return {
        "slot": 448780651,
        "blockTime": 1789920360,
        "version": 0,
        "transaction": {
            "message": {
                "accountKeys": [{"pubkey": value} for value in accounts],
                "instructions": [
                    {
                        "programId": PUMP_FUN_PROGRAM_ID,
                        "accounts": accounts,
                        "data": _base58_encode(PUMP_FUN_CREATE_V2_TAG + b"\x00" * 32),
                    }
                ],
            }
        },
        "meta": {
            "err": None,
            "innerInstructions": [],
            "logMessages": ["Program log: Instruction: CreateV2"],
        },
    }


def test_logs_notification_parses_signature_slot_logs_and_commitment() -> None:
    notification = parse_logs_notification(
        _notification(),
        observed_at=NOW,
        commitment=CommitmentState.CONFIRMED,
    )

    assert notification.slot == 448780651
    assert notification.signature == SIGNATURE
    assert notification.logs[-1].endswith("CreateV2")
    assert notification.commitment is CommitmentState.CONFIRMED
    assert notification.observed_at == NOW


def test_transaction_mapping_produces_raw_pump_launch_event() -> None:
    notification = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )

    events = map_transaction_to_raw_events(
        _transaction(),
        notification,
        ingested_at=NOW,
    )

    assert len(events) == 1
    event = events[0]
    assert event.program_id == PUMP_FUN_PROGRAM_ID
    assert event.discriminator_or_tag == PUMP_FUN_CREATE_V2_TAG.hex()
    assert event.payload["event_type"] == "create_v2"
    assert event.payload["mint_address"] == MINT
    assert event.payload["user"] == USER
    assert event.payload["signature"] == SIGNATURE
    assert event.payload["slot"] == 448780651
    assert "creator" not in event.payload
    assert event.occurred_at == datetime.fromtimestamp(1789920360, UTC)
    assert event.commitment is CommitmentState.CONFIRMED


def test_transaction_mapping_resolves_versioned_lookup_table_accounts() -> None:
    notification = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )
    transaction = _transaction()
    message = transaction["transaction"]["message"]  # type: ignore[index]
    message["accountKeys"] = [MINT, USER]  # type: ignore[index]
    message["instructions"] = [  # type: ignore[index]
        {
            "programIdIndex": 2,
            "accounts": [0, 1],
            "data": _base58_encode(PUMP_FUN_CREATE_V2_TAG + b"\0" * 32),
        }
    ]
    transaction["meta"]["loadedAddresses"] = {  # type: ignore[index]
        "writable": [],
        "readonly": [PUMP_FUN_PROGRAM_ID],
    }

    events = map_transaction_to_raw_events(transaction, notification, ingested_at=NOW)

    assert len(events) == 1
    assert events[0].payload["mint_address"] == MINT


def test_transaction_mapping_ignores_other_programs_and_unknown_instruction_data() -> None:
    notification = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )
    transaction = _transaction()
    message = transaction["transaction"]["message"]  # type: ignore[index]
    message["instructions"] = [  # type: ignore[index]
        {
            "programId": "11111111111111111111111111111111",
            "accounts": [],
            "data": "11111111",
        }
    ]

    assert map_transaction_to_raw_events(transaction, notification, ingested_at=NOW) == ()


def test_transaction_mapping_rejects_missing_chain_time_instead_of_fabricating_receipt_time(
) -> None:
    notification = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )
    transaction = _transaction()
    transaction["blockTime"] = None

    with pytest.raises(ProviderSchemaError, match="blockTime"):
        map_transaction_to_raw_events(transaction, notification, ingested_at=NOW)


def test_malformed_logs_notification_fails_closed() -> None:
    with pytest.raises(ProviderSchemaError, match="logsNotification"):
        parse_logs_notification({"method": "accountNotification"}, observed_at=NOW)

    malformed = _notification()
    malformed["params"]["result"]["value"]["logs"] = [None]  # type: ignore[index]
    with pytest.raises(ProviderSchemaError, match="non-text"):
        parse_logs_notification(malformed, observed_at=NOW)


def test_transaction_mapping_rejects_signature_mismatch() -> None:
    notification = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )
    transaction = _transaction()
    transaction["transaction"]["signatures"] = ["6" * 88]  # type: ignore[index]

    with pytest.raises(ProviderSchemaError, match="signatures differed"):
        map_transaction_to_raw_events(transaction, notification, ingested_at=NOW)


def test_source_fetches_only_launch_shaped_notifications() -> None:
    source = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=__import__("asyncio").Event(),
    )
    create = parse_logs_notification(
        _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
    )
    buy = parse_logs_notification(
        {
            **_notification(),
            "params": {
                "result": {
                    "context": {"slot": 448780651},
                    "value": {
                        "signature": SIGNATURE,
                        "err": None,
                        "logs": [
                            f"Program {PUMP_FUN_PROGRAM_ID} invoke [1]",
                            "Program log: Instruction: BuyV2",
                        ],
                    },
                }
            },
        },
        observed_at=NOW,
        commitment=CommitmentState.CONFIRMED,
    )

    assert source._is_launch_notification(create) is True
    assert source._is_launch_notification(buy) is False


def test_source_retries_transaction_not_yet_available(monkeypatch) -> None:
    source = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=__import__("asyncio").Event(),
    )
    responses = [None, None, {"slot": 1, "transaction": {}, "meta": {}}]
    calls = 0

    async def fetch(*_args: object, **_kwargs: object):
        nonlocal calls
        calls += 1
        return responses.pop(0)

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(source.rpc, "fetch_transaction_payload", fetch)
    monkeypatch.setattr(solana_raw_stream.asyncio, "sleep", no_wait)

    async def scenario() -> object:
        return await source._fetch_transaction_with_retry(
            SIGNATURE,
            context=ProviderRequestContext(
                    "raw-source-test",
                    NOW,
                    deadline_at=NOW + timedelta(seconds=1),
            ),
        )

    result = __import__("asyncio").run(scenario())
    assert result == {"slot": 1, "transaction": {}, "meta": {}}
    assert calls == 3


def test_source_reconnects_restores_subscription_and_emits_raw_event(monkeypatch) -> None:
    class Session:
        def __init__(self, messages: list[str]) -> None:
            self.messages = messages
            self.sent: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def send(self, value: str) -> None:
            self.sent.append(value)

        async def recv(self) -> str:
            if self.messages:
                return self.messages.pop(0)
            raise ConnectionError("fixture websocket closed")

    notification = json.dumps(_notification())
    sessions: list[Session] = []
    fetch_commitments: list[str] = []

    class Connections:
        calls = 0

        def connect(self, *_args: object, **_kwargs: object) -> Session:
            self.calls += 1
            messages = [json.dumps({"jsonrpc": "2.0", "result": self.calls, "id": 1})]
            if self.calls == 2:
                messages.append(notification)
            session = Session(messages)
            sessions.append(session)
            return session

    connections = Connections()
    monkeypatch.setattr(solana_raw_stream.websockets, "connect", connections.connect)

    source = SolanaRawTransactionSource(
        SolanaRpcAdapter("https://fixture.solana.example"),
        stop_event=asyncio.Event(),
    )

    async def fetch(*_args: object, **_kwargs: object):
        fetch_commitments.append(_kwargs["commitment"])
        return _transaction()

    async def scenario() -> None:
        source.rpc.fetch_transaction_payload = fetch  # type: ignore[method-assign]
        event = await source.__anext__()
        assert event.payload["event_type"] == "create_v2"
        assert source.metrics["stream_reconnects"] >= 2
        assert connections.calls == 2
        assert fetch_commitments == ["confirmed"]
        assert len(sessions[0].sent) == 1
        assert len(sessions[1].sent) == 1
        await source.aclose()

    asyncio.run(scenario())


def test_mapping_is_async_safe_for_worker_contracts() -> None:
    async def scenario() -> None:
        notification = parse_logs_notification(
            _notification(), observed_at=NOW, commitment=CommitmentState.CONFIRMED
        )
        assert map_transaction_to_raw_events(_transaction(), notification, ingested_at=NOW)

    asyncio.run(scenario())
