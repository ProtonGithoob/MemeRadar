"""Composed candidate-to-outbox-to-mocked-Telegram persistence contract."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from memeradar_api.operations_store import PersistedStreamOperations
from memeradar_application.alert_pipeline import (
    AlertDeliveryService,
    AlertDeliveryStatus,
    AlertPolicy,
)
from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor
from memeradar_application.provider_contracts import (
    DeliveryReceipt,
    NotificationRequest,
    ProviderRequestContext,
)
from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertType,
    Observation,
    Provenance,
    QualityState,
)
from memeradar_persistence import (
    AlertRow,
    OutboxRow,
    SqlAlchemyAlertStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.telegram import TelegramNotificationAdapter
from memeradar_worker.operations_jobs import _handle_alert_event

pytestmark = pytest.mark.integration


def _mint() -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    raw = uuid4().bytes + uuid4().bytes
    value = int.from_bytes(raw, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + encoded


def test_candidate_outbox_delivers_once_through_mocked_telegram() -> None:
    url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def exercise() -> None:
        engine = create_database_engine(url)
        now = datetime.now(UTC)
        async with engine.connect() as connection:
            earliest = await connection.scalar(
                select(func.min(OutboxRow.available_at)).where(
                    OutboxRow.side_effect_kind == "notification",
                    OutboxRow.delivered_at.is_(None),
                    OutboxRow.dead_lettered_at.is_(None),
                )
            )
        if earliest is not None:
            now = min(now, earliest - timedelta(minutes=1))
        mint = _mint()
        source = Observation(
            kind="launch.trade",
            provenance=Provenance(
                provider="fixture",
                source_id=f"telegram-e2e:{mint}",
                observed_at=now,
                parser_version="telegram-test-v1",
            ),
            occurred_at=now,
            observed_at=now,
            ingested_at=now,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "chain": "solana",
                "mint_address": mint,
                "event_type": "launch",
                "protocol_identity_verified": True,
                "side": "buy",
                "buyer_wallet": "fixture-wallet",
                "quote_amount": "1200",
                "market_cap_usd": "47000",
                "liquidity_usd": "18000",
            },
        )
        safety = {
            "protocol_identity_verified": True,
            "quote_semantics": "EXECUTION_QUOTE",
            "mint_authority_safe": True,
            "freeze_authority_safe": True,
            "liquidity": Decimal("25000"),
            "sellability": True,
            "buy_impact_bps": Decimal("120"),
            "sell_impact_bps": Decimal("140"),
        }
        scores = dict.fromkeys(
            (
                "OrganicFlowAcceleration",
                "WalletQuality",
                "OnChainSafety",
                "LiquidityAndSellability",
                "LaunchMomentum",
                "SmartMoneyConfluence",
            ),
            Decimal("70"),
        )
        sent: list[httpx.Request] = []

        async def telegram(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 17}})

        client = httpx.AsyncClient(transport=httpx.MockTransport(telegram))
        adapter = TelegramNotificationAdapter(
            "https://telegram.example",
            bot_token="12345:telegram-test-fixture",
            client=client,
            clock=lambda: now + timedelta(seconds=1),
        )
        try:
            async with SqlAlchemyUnitOfWork(engine) as uow:
                service = EarlyRuntimeService(
                    observation_store=uow.observations,
                    candidate_store=uow.candidates,
                    feature_store=uow.features,
                    risk_store=uow.risks,
                    score_store=uow.scores,
                    outbox_store=uow.outbox,
                )
                result = await service.process(
                    source,
                    observations=(source,),
                    safety_evidence=safety,
                    score_components=scores,
                )
                assert result.lifecycle_event is not None
                assert result.lifecycle_event.payload["notification_eligible"] is True
                await uow.commit()
            delivery = AlertDeliveryService(
                SqlAlchemyAlertStore(engine),
                adapter,
                destination="-100123",
                policy=AlertPolicy(enabled_types=frozenset({AlertType.EARLY_WATCH})),
                clock=lambda: now + timedelta(seconds=1),
            )

            async def handle(event):
                await _handle_alert_event(event, delivery, now=now + timedelta(seconds=1))

            processor = OutboxProcessor(
                SqlAlchemyOutboxStore(engine),
                EventDispatcher({"CandidateStateChanged": handle}),
                side_effect_kind="notification",
                clock=lambda: now + timedelta(seconds=1),
            )
            first = await processor.process_once(now=now + timedelta(seconds=1))
            restarted = OutboxProcessor(
                SqlAlchemyOutboxStore(engine),
                EventDispatcher({"CandidateStateChanged": handle}),
                side_effect_kind="notification",
                clock=lambda: now + timedelta(seconds=2),
            )
            second = await restarted.process_once(now=now + timedelta(seconds=2))
            assert first.delivered == 1
            assert second.claimed == 0
            assert len(sent) == 1
            async with engine.connect() as connection:
                outbox = await connection.scalar(
                    select(OutboxRow.status).where(
                        OutboxRow.event_id == result.lifecycle_event.id,
                        OutboxRow.side_effect_kind == "notification",
                    )
                )
                state = await connection.scalar(
                    select(AlertRow.state).where(
                        AlertRow.candidate_id == result.candidate.id,
                    )
                )
                assert outbox == "DELIVERED"
                assert state == "DELIVERED"
        finally:
            await client.aclose()
            await engine.dispose()

    asyncio.run(exercise())


def test_ambiguous_telegram_attempt_survives_service_restart() -> None:
    url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")

    async def exercise() -> None:
        engine = create_database_engine(url)
        now = datetime.now(UTC)
        request_context = ProviderRequestContext(
            correlation_id="telegram-restart-test",
            requested_at=now,
        )

        class InterruptedNotification:
            provider_name = "fixture-telegram"
            calls = 0

            async def send(self, _request: NotificationRequest) -> DeliveryReceipt:
                self.calls += 1
                raise asyncio.CancelledError

        notification = InterruptedNotification()
        alert = Alert(
            type=AlertType.EARLY_WATCH,
            severity=AlertSeverity.INFO,
            payload={"mint": _mint(), "state": "EARLY_WATCH", "score": "70"},
            dedupe_key=f"telegram-restart:{uuid4()}",
            requested_at=now,
        )
        try:
            service = AlertDeliveryService(
                SqlAlchemyAlertStore(engine),
                notification,
                destination="-100123",
                policy=AlertPolicy(enabled_types=frozenset({AlertType.EARLY_WATCH})),
                clock=lambda: now,
            )
            with pytest.raises(asyncio.CancelledError):
                await service.deliver(alert, context=request_context)

            resumed = AlertDeliveryService(
                SqlAlchemyAlertStore(engine),
                notification,
                destination="-100123",
                policy=AlertPolicy(enabled_types=frozenset({AlertType.EARLY_WATCH})),
                clock=lambda: now,
            )
            result = await resumed.deliver(alert, context=request_context)
            assert result.status is AlertDeliveryStatus.DELIVERY_UNKNOWN
            assert notification.calls == 1
            async with engine.connect() as connection:
                state = await connection.scalar(
                    select(AlertRow.state).where(AlertRow.dedupe_key == alert.dedupe_key)
                )
            assert state == "DELIVERY_UNKNOWN"
            overview = await PersistedStreamOperations(engine).get_operations_overview(
                now + timedelta(seconds=1)
            )
            assert overview.metrics["notification_delivery"]["delivery_unknown"] >= 1
        finally:
            await engine.dispose()

    asyncio.run(exercise())
