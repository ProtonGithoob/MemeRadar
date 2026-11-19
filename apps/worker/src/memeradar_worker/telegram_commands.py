"""Operator Telegram commands: register manual buys/sells for exit monitoring.

Only messages from the configured operator chat are honoured.  Commands only
append ``manual.position`` records; nothing is signed, routed or executed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.manual_positions import (
    HELP_TEXT,
    MANUAL_POSITION_KIND,
    CommandError,
    CommandKind,
    OperatorCommand,
    parse_command,
    position_id_for,
    position_observation,
)
from memeradar_application.provider_contracts import (
    NotificationRequest,
    ProviderRequestContext,
)
from memeradar_domain import Observation, Provenance, QualityState
from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork
from memeradar_providers.telegram import TelegramInboundMessage
from memeradar_providers.transport import ProviderError

LOGGER = logging.getLogger(__name__)
COMMAND_KIND = "telegram.command"
MARK_KIND = "manual.position_mark"
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class CommandTransport(Protocol):
    async def fetch_commands(
        self, *, offset: int | None, context: ProviderRequestContext, limit: int = 50
    ) -> tuple[tuple[TelegramInboundMessage, ...], int | None]: ...

    async def send(self, request: NotificationRequest) -> object: ...


def _command_observation(
    message: TelegramInboundMessage, *, at: datetime, status: str, command: str | None
) -> Observation:
    source_id = f"telegram:update:{message.update_id}"
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:{COMMAND_KIND}:{source_id}"),
        kind=COMMAND_KIND,
        provenance=Provenance(
            provider="memeradar.operator",
            source_id=source_id,
            observed_at=at,
            parser_version="telegram-command-v1",
        ),
        occurred_at=message.sent_at,
        observed_at=at,
        ingested_at=at,
        quality_state=QualityState.FRESH,
        # The raw text is not retained: only the parsed verb and outcome.
        normalized_payload={
            "update_id": message.update_id,
            "status": status,
            "command": command,
        },
    )


class TelegramCommandWorker:
    def __init__(
        self,
        engine: AsyncEngine,
        transport: CommandTransport,
        *,
        operator_chat_id: str,
        clock: Clock | None = None,
    ) -> None:
        self.engine = engine
        self.transport = transport
        self.operator_chat_id = str(operator_chat_id)
        self.clock = clock or (lambda: datetime.now(UTC))
        self._offset: int | None = None
        self._bootstrapped = False
        self._factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _bootstrap(self) -> None:
        async with self._factory() as session:
            rows = await session.scalars(
                select(ObservationRow.normalized_payload).where(
                    ObservationRow.kind == COMMAND_KIND
                )
            )
            ids = [
                payload.get("update_id")
                for payload in rows.all()
                if isinstance(payload.get("update_id"), int)
            ]
        self._offset = max(ids) + 1 if ids else None
        self._bootstrapped = True

    async def _open_positions(self) -> dict[str, Mapping[str, object]]:
        async with self._factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ObservationRow)
                        .where(ObservationRow.kind == MANUAL_POSITION_KIND)
                        .order_by(ObservationRow.observed_at, ObservationRow.id)
                    )
                ).all()
            )
        positions: dict[str, Mapping[str, object]] = {}
        for row in rows:
            payload = row.normalized_payload
            position_id = payload.get("position_id")
            if not isinstance(position_id, str):
                continue
            if payload.get("event") == "OPEN":
                positions[position_id] = payload
            elif payload.get("event") == "CLOSE":
                positions.pop(position_id, None)
        return positions

    async def _latest_mark(self, position_id: str) -> Mapping[str, object] | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(ObservationRow)
                .where(
                    ObservationRow.kind == MARK_KIND,
                    ObservationRow.normalized_payload["position_id"].as_string() == position_id,
                )
                .order_by(ObservationRow.observed_at.desc())
                .limit(1)
            )
        return None if row is None else row.normalized_payload

    async def _handle(
        self, command: OperatorCommand, now: datetime, observations: list[Observation]
    ) -> str:
        if command.kind is CommandKind.HELP:
            return HELP_TEXT
        positions = await self._open_positions()
        if command.kind is CommandKind.POSITIONS:
            if not positions:
                return "No open manual positions."
            lines = ["Open manual positions:"]
            for position_id, payload in positions.items():
                mark = await self._latest_mark(position_id)
                entry = payload.get("entry_price_usd")
                price = None if mark is None else mark.get("price_usd")
                multiple = "UNKNOWN"
                if entry and price:
                    multiple = f"x{Decimal(str(price)) / Decimal(str(entry)):.2f}"
                lines.append(
                    f"{payload.get('mint')} size ${payload.get('size_usd')} "
                    f"entry {entry or 'market-ref'} mark {multiple}"
                )
            return "\n".join(lines)
        assert command.mint is not None
        if command.kind is CommandKind.SOLD:
            matching = [pid for pid, p in positions.items() if p.get("mint") == command.mint]
            if not matching:
                return f"No open position for {command.mint}."
            for position_id in matching:
                observations.append(
                    position_observation(
                        event="CLOSE",
                        position_id=position_id,
                        mint=command.mint,
                        at=now,
                        source="telegram",
                    )
                )
            return f"Closed {len(matching)} position(s) for {command.mint}. Exit alerts stop."
        if any(p.get("mint") == command.mint for p in positions.values()):
            return f"A position for {command.mint} is already open. Use /sold first."
        position_id = position_id_for(command.mint, now)
        observations.append(
            position_observation(
                event="OPEN",
                position_id=position_id,
                mint=command.mint,
                at=now,
                source="telegram",
                entry_price_usd=command.entry_price_usd,
                size_usd=command.size_usd,
            )
        )
        entry = (
            f"entry {command.entry_price_usd} USD (your fill)"
            if command.entry_price_usd is not None
            else "entry = market price at next sample (send your fill price for accuracy)"
        )
        return (
            f"Recorded manual buy {position_id}: ${command.size_usd}, {entry}.\n"
            "Exit alerts: 2x principal, 5x/10x/25x ladder, trailing stop, hard stop, "
            "rug warnings. Nothing is traded by MemeRadar."
        )

    async def poll_once(self, *, now: datetime | None = None) -> int:
        checked_at = now or self.clock()
        if not self._bootstrapped:
            await self._bootstrap()
        context = ProviderRequestContext(
            correlation_id=f"telegram-commands:{int(checked_at.timestamp())}",
            requested_at=checked_at,
            deadline_at=checked_at + timedelta(seconds=15),
        )
        messages, next_offset = await self.transport.fetch_commands(
            offset=self._offset, context=context
        )
        handled = 0
        for message in messages:
            observations: list[Observation] = []
            reply: str | None = None
            status = "IGNORED"
            verb: str | None = None
            if message.chat_id != self.operator_chat_id:
                status = "UNAUTHORIZED_CHAT"
            else:
                try:
                    command = parse_command(message.text)
                except CommandError as error:
                    status, reply = "REJECTED", f"Command rejected: {error}"
                else:
                    if command is not None:
                        verb = command.kind.value
                        reply = await self._handle(command, checked_at, observations)
                        status = "HANDLED"
            observations.append(
                _command_observation(message, at=checked_at, status=status, command=verb)
            )
            async with SqlAlchemyUnitOfWork(self.engine) as unit_of_work:
                for observation in observations:
                    await unit_of_work.observations.add(observation)
                await unit_of_work.commit()
            handled += status == "HANDLED"
            if reply is not None:
                await self._reply(message, reply, context)
        if next_offset is not None:
            self._offset = next_offset
        return handled

    async def _reply(
        self, message: TelegramInboundMessage, text: str, context: ProviderRequestContext
    ) -> None:
        try:
            await self.transport.send(
                NotificationRequest(
                    context=context,
                    type="operator_reply",
                    dedupe_key=f"telegram-reply:{message.update_id}",
                    payload={"chat_id": message.chat_id, "text": text[:3500]},
                )
            )
        except Exception as error:  # noqa: BLE001 - a lost reply must not stop intake.
            LOGGER.warning(
                "telegram_command_reply_failed", extra={"error_class": type(error).__name__}
            )

    async def run(
        self,
        stop_event: asyncio.Event,
        *,
        poll_interval_seconds: float = 5.0,
        sleeper: Sleep = asyncio.sleep,
    ) -> None:
        while not stop_event.is_set():
            try:
                await self.poll_once()
            except (ProviderError, ValueError) as error:
                LOGGER.warning(
                    "telegram_command_poll_failed", extra={"error_class": type(error).__name__}
                )
            except Exception as error:  # noqa: BLE001 - intake must not stop the worker.
                LOGGER.warning(
                    "telegram_command_cycle_failed", extra={"error_class": type(error).__name__}
                )
            if not stop_event.is_set():
                await sleeper(poll_interval_seconds)


__all__ = ["COMMAND_KIND", "CommandTransport", "TelegramCommandWorker"]


