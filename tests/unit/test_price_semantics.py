"""Deterministic contracts for execution/effective versus market prices."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from memeradar_application.price_semantics import (
    PRICE_SEMANTICS_VERSION,
    PriceSemantics,
    resolve_price_evidence,
)
from memeradar_domain import Observation, Provenance, QualityState

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def provenance(source_id: str = "price-1") -> Provenance:
    return Provenance(
        provider="fixture-market",
        source_id=source_id,
        observed_at=NOW,
        parser_version="fixture-v1",
    )


def test_market_snapshot_price_is_market_reference_and_execution_price_is_not_reused() -> None:
    market = resolve_price_evidence(
        {"price_usd": "1.25", "execution_price": "1.20"},
        kind="market.market_data",
        observed_at=NOW,
        provenance=(provenance(),),
        now=NOW,
    )

    assert market.price == Decimal("1.25")
    assert market.semantics is PriceSemantics.MARKET_REFERENCE
    assert market.source_field == "price_usd"
    assert market.quality_state is QualityState.FRESH
    assert market.version == PRICE_SEMANTICS_VERSION


def test_trade_price_is_execution_effective_and_generic_price_never_becomes_market_mark() -> None:
    trade = resolve_price_evidence(
        {"price": "1.20", "side": "buy"},
        kind="market.trade",
        observed_at=NOW,
        provenance=(provenance("trade-1"),),
        now=NOW,
    )
    assert trade.price == Decimal("1.20")
    assert trade.semantics is PriceSemantics.EXECUTION_EFFECTIVE

    ambiguous = resolve_price_evidence(
        {"price": "1.20"},
        kind="market.observation",
        observed_at=NOW,
        provenance=(provenance("ambiguous-1"),),
        now=NOW,
    )
    assert ambiguous.price is None
    assert ambiguous.semantics is PriceSemantics.UNKNOWN
    assert ambiguous.quality_state is QualityState.UNKNOWN


def test_missing_or_stale_price_is_unknown_and_never_zero() -> None:
    missing = resolve_price_evidence(
        {"market_price": None},
        kind="market.market_data",
        observed_at=NOW,
        provenance=(provenance("missing-1"),),
        now=NOW,
    )
    stale = resolve_price_evidence(
        {"market_price": "2"},
        kind="market.market_data",
        observed_at=NOW - timedelta(minutes=6),
        provenance=(
            Provenance(
                provider="fixture-market",
                source_id="stale-1",
                observed_at=NOW - timedelta(minutes=6),
                parser_version="fixture-v1",
            ),
        ),
        now=NOW,
    )
    assert missing.price is None
    assert missing.quality_state is QualityState.UNKNOWN
    assert stale.price == Decimal("2")
    assert stale.quality_state is QualityState.STALE


def test_future_price_is_invalid_and_observation_helper_preserves_provenance() -> None:
    future = resolve_price_evidence(
        {"market_price": "3"},
        kind="market.market_data",
        observed_at=NOW + timedelta(seconds=1),
        provenance=(provenance("future-1"),),
        now=NOW,
    )
    assert future.quality_state is QualityState.INVALID
    assert future.price is None

    observation = Observation(
        id=uuid5(NAMESPACE_URL, "price-observation"),
        kind="market.market_data",
        provenance=provenance("observation-1"),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": MINT, "market_price": "4"},
    )
    evidence = resolve_price_evidence(observation, now=NOW)
    assert evidence.price == Decimal("4")
    assert evidence.provenance == (observation.provenance,)


def test_invalid_price_does_not_get_coerced_to_zero() -> None:
    with pytest.raises(ValueError, match="price"):
        resolve_price_evidence(
            {"market_price": "0"},
            kind="market.market_data",
            observed_at=NOW,
            provenance=(provenance("zero-1"),),
            now=NOW,
        )
