"""M8 wiring: point-in-time profile lookup, coverage gate and shadow default."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from memeradar_application.config import Settings
from memeradar_application.wallet_intelligence import (
    WalletCategory,
    WalletProfile,
    signal_features_from_categories,
)
from memeradar_persistence.models import Base
from memeradar_worker.wallet_profile_store import load_profile_categories, persist_profiles

T0 = datetime(2026, 11, 25, 12, tzinfo=UTC)


def _profile(wallet: str, as_of: datetime, *categories: WalletCategory) -> WalletProfile:
    return WalletProfile(
        wallet=wallet, as_of=as_of, tokens_traded=3, verified_trades=6,
        observable_outcome_tokens=3, realized_pnl_sol=Decimal("1"), realized_unknown_events=0,
        unrealized_pnl_sol=None, closed_positions=3, win_rate=Decimal("1"),
        extreme_participation=None, early_5x_tokens=2, failed_token_exposure=None,
        median_entry_multiple_of_initial=None, median_entry_delay_seconds=None,
        median_holding_seconds=None, reconciliation_completeness=Decimal("1"),
        categories=categories, evidence=(),
    )


def test_coverage_gate_reports_unknown_instead_of_zero() -> None:
    smart = WalletCategory.EARLY_SMART_MONEY_CANDIDATE.value
    low = signal_features_from_categories({"A": (smart,)}, ["A", "B", "C"])
    assert "raw_smart_wallet_count" not in low  # 1/3 profiled: UNKNOWN
    high = signal_features_from_categories(
        {"A": (smart,), "B": (WalletCategory.POTENTIAL_INSIDER.value,)}, ["A", "B"]
    )
    assert high["raw_smart_wallet_count"] == 1
    assert high["risk_category_buyer_count"] == 1
    tainted = signal_features_from_categories(
        {"A": (smart, WalletCategory.CREATOR_LINKED.value)}, ["A"]
    )
    assert tainted["raw_smart_wallet_count"] == 0


def test_live_lookup_never_reads_a_profile_computed_after_the_decision() -> None:
    pytest.importorskip("aiosqlite")

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await persist_profiles(
                engine,
                [
                    _profile("W", T0, WalletCategory.LOW_EVIDENCE),
                    _profile("W", T0 + timedelta(days=1),
                             WalletCategory.EARLY_SMART_MONEY_CANDIDATE),
                ],
            )
            early = await load_profile_categories(engine, ["W"], as_of=T0 + timedelta(hours=1))
            late = await load_profile_categories(engine, ["W"], as_of=T0 + timedelta(days=2))
            assert early == {"W": ("LOW_EVIDENCE",)}
            assert late == {"W": ("EARLY_SMART_MONEY_CANDIDATE",)}
            assert await load_profile_categories(engine, ["W"], as_of=T0 - timedelta(1)) == {}
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_wallet_features_do_not_reach_scoring_unless_enabled() -> None:
    assert Settings.from_env({}).wallet_intelligence_scoring_enabled is False
    enabled = Settings.from_env({"WALLET_INTELLIGENCE_SCORING_ENABLED": "true"})
    assert enabled.wallet_intelligence_scoring_enabled is True


def test_wallet_read_api_serves_persisted_profiles_with_risk_blocked_and_no_score() -> None:
    pytest.importorskip("aiosqlite")
    from memeradar_application.read_wallets import WalletQuery
    from memeradar_persistence.read_queries import SqlAlchemyReadQueryService

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            smart = "So11111111111111111111111111111111111111112"
            insider = "Vote111111111111111111111111111111111111111"
            await persist_profiles(
                engine,
                [
                    _profile(smart, T0, WalletCategory.EARLY_SMART_MONEY_CANDIDATE),
                    _profile(insider, T0, WalletCategory.POTENTIAL_INSIDER),
                ],
            )
            service = SqlAlchemyReadQueryService(engine, clock=lambda: T0 + timedelta(hours=1))
            page = await service.list_wallets(WalletQuery())
            views = {view.address: view for view in page.items}
            assert set(views) == {smart, insider}
            assert views[insider].recommended_tier == "BLOCKED"
            assert views[smart].score is None
            assert "HEURISTIC_CLASSIFICATION_NOT_CALIBRATED" in views[smart].reason_codes
            assert views[smart].execution_eligible is False
            single = await service.get_wallet(smart)
            assert single is not None and single.known_outcome_count == 3
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
