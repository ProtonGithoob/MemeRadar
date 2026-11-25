"""Reverse wallet intelligence on PostgreSQL: idempotent profile persistence,
point-in-time lookup, read API and restart (new engine) recovery."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.read_wallets import WalletQuery
from memeradar_application.wallet_intelligence import WalletCategory, WalletProfile
from memeradar_persistence import create_database_engine
from memeradar_persistence.read_queries import SqlAlchemyReadQueryService
from memeradar_worker.wallet_profile_store import load_profile_categories, persist_profiles

pytestmark = pytest.mark.integration
T0 = datetime(2026, 11, 25, 12, tzinfo=UTC)


def _base58(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return encoded


def _profile(wallet: str, as_of: datetime, category: WalletCategory) -> WalletProfile:
    return WalletProfile(
        wallet=wallet, as_of=as_of, tokens_traded=4, verified_trades=8,
        observable_outcome_tokens=4, realized_pnl_sol=Decimal("0.5"),
        realized_unknown_events=1, unrealized_pnl_sol=None, closed_positions=3,
        win_rate=Decimal("0.6667"), extreme_participation=Decimal("0.25"), early_5x_tokens=2,
        failed_token_exposure=Decimal("0.5"), median_entry_multiple_of_initial=Decimal("1.2"),
        median_entry_delay_seconds=12.0, median_holding_seconds=300.0,
        reconciliation_completeness=Decimal("1"), categories=(category,), evidence=("fixture",),
    )


def test_wallet_profiles_round_trip_point_in_time_and_survive_restart() -> None:
    database_url = os.environ.get("MEMERADAR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MEMERADAR_TEST_DATABASE_URL is not configured")
    wallet = _base58(uuid4().bytes + uuid4().bytes)

    async def scenario() -> None:
        engine = create_database_engine(database_url)
        try:
            early = _profile(wallet, T0, WalletCategory.LOW_EVIDENCE)
            late = _profile(wallet, T0 + timedelta(days=1),
                            WalletCategory.EARLY_SMART_MONEY_CANDIDATE)
            await persist_profiles(engine, [early, late])
            await persist_profiles(engine, [early])  # duplicate delivery is idempotent
        finally:
            await engine.dispose()
        restarted = create_database_engine(database_url)
        try:
            before = await load_profile_categories(
                restarted, [wallet], as_of=T0 + timedelta(hours=2)
            )
            after = await load_profile_categories(
                restarted, [wallet], as_of=T0 + timedelta(days=2)
            )
            assert before == {wallet: ("LOW_EVIDENCE",)}
            assert after == {wallet: ("EARLY_SMART_MONEY_CANDIDATE",)}
            service = SqlAlchemyReadQueryService(
                restarted, clock=lambda: T0 + timedelta(days=1, hours=1)
            )
            view = await service.get_wallet(wallet)
            assert view is not None and view.score is None
            assert view.known_outcome_count == 4
            page = await service.list_wallets(WalletQuery(limit=100))
            assert wallet in {item.address for item in page.items}
        finally:
            await restarted.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=60))
