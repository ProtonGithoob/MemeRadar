"""TDD contracts for launch-age micro-feature windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.early_features import EARLY_WINDOW_LABELS, EarlyFeatureEngine
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TOKEN_ID = UUID("22222222-2222-2222-2222-222222222222")


def trade(
    seconds: int,
    *,
    side: str = "buy",
    amount: str = "1",
    wallet: str = "wallet-a",
    price: str | None = "2",
    liquidity: str | None = "1000",
    event_id: str | None = None,
    quality: QualityState = QualityState.FRESH,
) -> Observation:
    occurred = NOW + timedelta(seconds=seconds)
    payload: dict[str, object] = {
        "side": side,
        "quote_amount": amount,
        "amount": amount,
        "buyer_wallet": wallet if side == "buy" else None,
        "seller_wallet": wallet if side == "sell" else None,
    }
    if price is not None:
        payload["price"] = price
    if liquidity is not None:
        payload["liquidity"] = liquidity
    return Observation(
        id=uuid5(NAMESPACE_URL, f"early-feature:{event_id or seconds}:{side}:{wallet}"),
        kind="market.trade",
        provenance=Provenance(
            provider="fixture",
            source_id=event_id or f"trade-{seconds}-{wallet}",
            observed_at=occurred,
            parser_version="fixture-v1",
        ),
        occurred_at=occurred,
        observed_at=occurred,
        ingested_at=occurred,
        quality_state=quality,
        normalized_payload=payload,
        token_id=TOKEN_ID,
    )


def test_windows_use_half_open_event_time_boundaries_and_exclude_future_data() -> None:
    observations = (
        trade(-5, event_id="start-5"),
        trade(-4, event_id="inside-5"),
        trade(0, event_id="at-as-of"),
        trade(1, amount="100", event_id="future"),
    )

    snapshot = EarlyFeatureEngine().compute(TOKEN_ID, NOW, observations)

    assert tuple(snapshot.windows) == EARLY_WINDOW_LABELS
    assert snapshot.windows["5s"].metrics["trade_count"] == 2
    assert snapshot.windows["5s"].metrics["buy_count"] == 2
    assert snapshot.windows["5s"].metrics["quote_inflow_per_second"] == Decimal("0.4")
    assert snapshot.windows["5s"].metrics["future_observations_excluded"] == 1
    assert snapshot.windows["5s"].metrics["quote_inflow"] == Decimal("2")
    assert snapshot.windows["5s"].metrics["quote_inflow"] != Decimal("102")


def test_required_metrics_are_exact_and_missing_rows_remain_nullable() -> None:
    observations = (
        trade(-2, amount="1.1", wallet="wallet-a", price="10", liquidity="100"),
        trade(-1, amount="2.2", wallet="wallet-b", price="11", liquidity="110"),
    )

    window = EarlyFeatureEngine().compute(TOKEN_ID, NOW, observations).windows["5s"]

    assert window.metrics["buys_per_second"] == Decimal("0.4")
    assert window.metrics["quote_inflow_per_second"] == Decimal("0.66")
    assert window.metrics["return"] == Decimal("0.1")
    assert window.metrics["liquidity_change"] == Decimal("10")
    assert window.metrics["unique_buyers"] == 2
    assert window.metrics["maker_diversity"] == Decimal("1")
    assert window.metrics["buy_sell_ratio"] is None
    assert "SELL_EVIDENCE_MISSING" in window.reason_code_values


def test_acceleration_requires_a_valid_prior_adjacent_window() -> None:
    observations = (
        trade(-9, event_id="old"),
        trade(-4, event_id="recent-1"),
        trade(-3, event_id="recent-2"),
        trade(-2, event_id="recent-3"),
    )

    window = EarlyFeatureEngine().compute(TOKEN_ID, NOW, observations).windows["5s"]

    assert window.metrics["buys_per_second"] == Decimal("0.6")
    assert window.metrics["previous_buys_per_second"] == Decimal("0.2")
    assert window.metrics["buy_acceleration_per_second"] == Decimal("0.4")


def test_all_configured_windows_are_present_and_unknown_input_is_fail_closed() -> None:
    snapshot = EarlyFeatureEngine().compute(TOKEN_ID, NOW, ())

    assert tuple(snapshot.windows) == ("1s", "5s", "15s", "30s", "60s", "3m", "5m")
    assert all(window.quality_state is QualityState.UNKNOWN for window in snapshot.windows.values())
    assert all(window.metrics["buys_per_second"] is None for window in snapshot.windows.values())
    assert snapshot.execution_eligible() is False
