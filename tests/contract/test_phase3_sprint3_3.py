"""Keyless replay contract for Phase 3 Sprint 3.3 flow analysis."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from memeradar_application.flow_analysis import FlowAnalyzer
from memeradar_application.provider_contracts import QuoteSnapshot
from memeradar_domain import Freshness, Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
QUOTE = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MAKER_A = "11111111111111111111111111111112"
MAKER_B = "11111111111111111111111111111113"
MAKER_C = "11111111111111111111111111111114"
MAKER_D = "11111111111111111111111111111115"


def load_fixture(name: str) -> dict[str, object]:
    path = ROOT / "fixtures" / "providers" / "flow_analysis" / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def observation(
    token: TokenIdentity,
    *,
    kind: str,
    payload: dict[str, object],
    source_id: str,
    observed_at: datetime,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider="flow-analysis-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="flow-analysis-fixture-v1",
        ),
        occurred_at=None,
        observed_at=observed_at,
        ingested_at=observed_at + timedelta(seconds=1),
        quality_state=QualityState.FRESH,
        normalized_payload={"mint_address": token.mint_address, **payload},
        token_id=token.id,
    )


def market_observations(
    token: TokenIdentity,
    payload: dict[str, object],
) -> tuple[Observation, ...]:
    records = payload["observations"]
    assert isinstance(records, list)
    return tuple(
        observation(
            token,
            kind="market.market_data",
            payload={"liquidity": record["liquidity"], "depth": record["depth"]},
            source_id=str(record["source_id"]),
            observed_at=datetime.fromisoformat(str(record["observed_at"])),
        )
        for record in records
        if isinstance(record, dict)
    )


def trade_observations(
    token: TokenIdentity,
    payload: dict[str, object],
) -> tuple[Observation, ...]:
    records = payload["events"]
    assert isinstance(records, list)
    return tuple(
        observation(
            token,
            kind="market.trade",
            payload={
                "maker": record["maker"],
                "side": record["side"],
                "amount": record["amount"],
                "buyer": record["buyer"],
                "seller": record["seller"],
            },
            source_id=str(record["source_id"]),
            observed_at=datetime.fromisoformat(str(record["observed_at"])),
        )
        for record in records
        if isinstance(record, dict)
    )


def quote_from_fixture(
    token: TokenIdentity,
    payload: dict[str, object],
    *,
    index: int,
) -> QuoteSnapshot:
    records = payload["quotes"]
    assert isinstance(records, list)
    record = records[index]
    assert isinstance(record, dict)
    as_of = datetime.fromisoformat(str(record["observed_at"]))
    return QuoteSnapshot(
        provenance=Provenance(
            provider="flow-analysis-fixture",
            source_id=str(record["source_id"]),
            observed_at=as_of,
            parser_version="flow-analysis-fixture-v1",
        ),
        input_mint=token.mint_address,
        output_mint=str(record["output_mint"]),
        input_amount=Decimal(str(record["input_amount"])),
        output_amount=Decimal(str(record["output_amount"])),
        price_impact_bps=Decimal(str(record["price_impact_bps"])),
        route=tuple(str(value) for value in record["route"]),
        freshness=Freshness(as_of=as_of, expires_at=NOW + timedelta(minutes=4)),
    )


def test_safe_and_suspicious_flow_fixtures_replay_deterministically() -> None:
    market_safe = load_fixture("market_safe.json")
    market_suspicious = load_fixture("market_suspicious.json")
    trades_safe = load_fixture("trades_safe.json")
    trades_suspicious = load_fixture("trades_suspicious.json")
    quotes = load_fixture("quotes.json")
    for fixture in (
        market_safe,
        market_suspicious,
        trades_safe,
        trades_suspicious,
        quotes,
    ):
        assert_credential_free(fixture)

    token = TokenIdentity(mint_address=MINT, id=uuid4())
    safe_observations = (
        *market_observations(token, market_safe),
        *trade_observations(token, trades_safe),
    )
    suspicious_observations = (
        *market_observations(token, market_suspicious),
        *trade_observations(token, trades_suspicious),
    )
    analyzer = FlowAnalyzer()
    safe = analyzer.analyze(
        token,
        safe_observations,
        now=NOW,
        config_hash="phase3-sprint3-3-fixture",
        quotes=(quote_from_fixture(token, quotes, index=0),),
    )
    suspicious = analyzer.analyze(
        token,
        suspicious_observations,
        now=NOW,
        config_hash="phase3-sprint3-3-fixture",
        quotes=(quote_from_fixture(token, quotes, index=1),),
    )

    assert safe.quality_state is QualityState.FRESH
    assert safe.score == Decimal("100")
    assert safe.metrics.unique_makers == 4
    assert safe.metrics.repeated_size_ratio == Decimal("0")
    assert safe.metrics.circular_flow_ratio == Decimal("0")
    assert safe.metrics.rapid_round_trip_ratio == Decimal("0")
    assert safe.metrics.quote_quality_state is QualityState.FRESH
    assert safe.execution_eligible(NOW) is False
    safe_replay = analyzer.analyze(
        token,
        safe_observations,
        now=NOW,
        config_hash="phase3-sprint3-3-fixture",
        quotes=(quote_from_fixture(token, quotes, index=0),),
    )
    assert safe_replay == safe

    suspicious_reasons = {reason.code for reason in suspicious.reason_codes}
    assert suspicious.quality_state is QualityState.FRESH
    assert suspicious.score == Decimal("0")
    assert suspicious.metrics.transaction_maker_ratio == Decimal("2")
    assert suspicious.metrics.repeated_size_ratio == Decimal("1")
    assert suspicious.metrics.circular_flow_ratio == Decimal("1")
    assert suspicious.metrics.rapid_round_trip_ratio == Decimal("1")
    assert suspicious.metrics.price_impact_bps == Decimal("250")
    assert {
        "LIQUIDITY_LOW",
        "LIQUIDITY_DEPTH_LOW",
        "LIQUIDITY_DECAY",
        "PRICE_IMPACT_HIGH",
        "TRANSACTION_MAKER_CONCENTRATION",
        "REPEATED_TRADE_SIZE",
        "CIRCULAR_FLOW_DETECTED",
        "RAPID_ROUND_TRIP",
    } <= suspicious_reasons
    assert suspicious.execution_eligible(NOW) is False


def test_flow_analysis_fixture_contract_has_no_live_execution_surface() -> None:
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "flow_analysis.py"
    ).read_text()
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign" not in source.lower()
    assert "submit" not in source.lower()
