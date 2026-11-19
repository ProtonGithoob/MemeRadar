"""Operator Telegram commands: parsing, chat authorization and position records."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from memeradar_application.manual_positions import CommandError, CommandKind, parse_command
from memeradar_application.provider_contracts import NotificationRequest, ProviderRequestContext
from memeradar_persistence import ObservationRow
from memeradar_persistence.models import Base
from memeradar_providers.telegram import TelegramInboundMessage, TelegramNotificationAdapter
from memeradar_worker.telegram_commands import TelegramCommandWorker

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
NOW = datetime(2026, 11, 19, 9, tzinfo=UTC)
OPERATOR = "424242"


def test_parse_commands() -> None:
    bought = parse_command(f"/bought {MINT} 0.00012 75")
    assert bought is not None and bought.kind is CommandKind.BOUGHT
    assert bought.entry_price_usd == Decimal("0.00012") and bought.size_usd == Decimal("75")
    default = parse_command(f"/bought@MemeRadarBot {MINT}")
    assert default is not None and default.size_usd == Decimal("50")
    assert default.entry_price_usd is None
    sold = parse_command(f"/sold {MINT}")
    assert sold is not None and sold.kind is CommandKind.SOLD
    assert parse_command("/positions").kind is CommandKind.POSITIONS  # type: ignore[union-attr]
    assert parse_command("gm") is None
    assert parse_command("/unknown") is None
    for bad in ("/bought", "/bought notamint", f"/bought {MINT} -1", f"/bought {MINT} abc"):
        with pytest.raises(CommandError):
            parse_command(bad)


class FakeTransport:
    def __init__(self, batches: list[list[TelegramInboundMessage]]) -> None:
        self.batches = batches
        self.offsets: list[int | None] = []
        self.sent: list[NotificationRequest] = []

    async def fetch_commands(
        self, *, offset: int | None, context: ProviderRequestContext, limit: int = 50
    ) -> tuple[tuple[TelegramInboundMessage, ...], int | None]:
        self.offsets.append(offset)
        batch = self.batches.pop(0) if self.batches else []
        next_offset = max((m.update_id for m in batch), default=None)
        return tuple(batch), (None if next_offset is None else next_offset + 1)

    async def send(self, request: NotificationRequest) -> object:
        self.sent.append(request)
        return None


def _message(update_id: int, text: str, chat: str = OPERATOR) -> TelegramInboundMessage:
    return TelegramInboundMessage(update_id=update_id, chat_id=chat, text=text, sent_at=NOW)


def test_worker_records_positions_only_for_the_operator_chat() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            transport = FakeTransport(
                [
                    [
                        _message(10, f"/bought {MINT} 0.0001", chat="999"),
                        _message(11, f"/bought {MINT} 0.0001"),
                        _message(12, f"/bought {MINT}"),
                        _message(13, "/positions"),
                    ],
                    [_message(14, f"/sold {MINT}")],
                ]
            )
            worker = TelegramCommandWorker(engine, transport, operator_chat_id=OPERATOR)
            assert await worker.poll_once(now=NOW) == 3
            assert await worker.poll_once(now=NOW + timedelta(minutes=1)) == 1
            assert transport.offsets == [None, 14]
            replies = [request.payload["text"] for request in transport.sent]
            assert len(replies) == 4  # the unauthorized chat gets no reply
            assert "Recorded manual buy" in replies[0]
            assert "already open" in replies[1]
            assert "Open manual positions" in replies[2]
            assert "Closed 1 position" in replies[3]
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                rows = list(
                    (
                        await session.scalars(
                            select(ObservationRow).where(ObservationRow.kind == "manual.position")
                        )
                    ).all()
                )
                commands = list(
                    (
                        await session.scalars(
                            select(ObservationRow).where(ObservationRow.kind == "telegram.command")
                        )
                    ).all()
                )
            assert sorted(row.normalized_payload["event"] for row in rows) == ["CLOSE", "OPEN"]
            assert {row.normalized_payload["status"] for row in commands} >= {
                "UNAUTHORIZED_CHAT",
                "HANDLED",
            }
            assert all("text" not in row.normalized_payload for row in commands)
            restarted = TelegramCommandWorker(engine, FakeTransport([]), operator_chat_id=OPERATOR)
            await restarted.poll_once(now=NOW + timedelta(minutes=2))
            assert restarted.transport.offsets == [15]  # type: ignore[attr-defined]
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_adapter_fetch_commands_normalizes_updates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/getUpdates")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 7,
                        "message": {
                            "message_id": 1,
                            "date": int(NOW.timestamp()),
                            "chat": {"id": 424242},
                            "text": "/positions",
                        },
                    },
                    {"update_id": 8, "edited_message": {"chat": {"id": 1}, "text": "x"}},
                ],
            },
        )

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = TelegramNotificationAdapter(
            "https://api.telegram.org", bot_token="123456:" + "A" * 35, client=client
        )
        context = ProviderRequestContext(
            correlation_id="t", requested_at=NOW, deadline_at=None
        )
        messages, offset = await adapter.fetch_commands(offset=None, context=context)
        await client.aclose()
        assert offset == 9
        assert [(m.update_id, m.chat_id, m.text) for m in messages] == [(7, "424242", "/positions")]

    asyncio.run(scenario())
