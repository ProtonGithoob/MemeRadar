"""Keyless replay contracts for research extension E5.4."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import yaml

from memeradar_application.call_performance import (
    CallPerformanceAnalyzer,
    CallPerformancePolicy,
    OutcomeHorizonState,
    SocialCall,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "call_performance"
NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)


def load_fixture() -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / "replay.json").read_text(encoding="utf-8"))
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
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def build_tokens(payload: dict[str, object]) -> dict[str, TokenIdentity]:
    raw_tokens = payload["tokens"]
    assert isinstance(raw_tokens, dict)
    result: dict[str, TokenIdentity] = {}
    for key, raw_token in raw_tokens.items():
        assert isinstance(raw_token, dict)
        mint = str(raw_token["mint_address"])
        result[key] = TokenIdentity(mint_address=mint, id=uuid5(NAMESPACE_URL, mint))
    return result


def provenance(source_id: str, observed_at: datetime) -> Provenance:
    return Provenance(
        provider="call-performance-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="call-performance-fixture-v1",
    )


def build_calls(
    payload: dict[str, object],
    tokens: Mapping[str, TokenIdentity],
) -> tuple[SocialCall, ...]:
    raw_calls = payload["calls"]
    assert isinstance(raw_calls, list)
    result: list[SocialCall] = []
    for row in raw_calls:
        assert isinstance(row, dict)
        called_at = datetime.fromisoformat(str(row["called_at"]))
        observed_at = datetime.fromisoformat(str(row["observed_at"]))
        source_post_ids = tuple(str(value) for value in row["source_post_ids"])
        result.append(
            SocialCall(
                provenance=provenance(source_post_ids[0], observed_at),
                author_id=str(row["author_id"]),
                token_id=tokens[str(row["mint_key"])].id,
                referenced_mint=tokens[str(row["mint_key"])].mint_address,
                called_at=called_at,
                observed_at=observed_at,
                ingested_at=datetime.fromisoformat(str(row["ingested_at"])),
                source_post_ids=source_post_ids,
            )
        )
    return tuple(result)


def build_observations(
    payload: dict[str, object],
    tokens: Mapping[str, TokenIdentity],
    *,
    field: str,
    kind: str,
) -> tuple[Observation, ...]:
    raw_observations = payload[field]
    assert isinstance(raw_observations, list)
    result: list[Observation] = []
    for row in raw_observations:
        assert isinstance(row, dict)
        event_at = datetime.fromisoformat(str(row["occurred_at"]))
        observed_at = event_at + timedelta(seconds=1)
        raw_payload: dict[str, object] = {
            "mint_address": tokens[str(row["mint_key"])].mint_address,
        }
        if "price" in row:
            raw_payload["price"] = str(row["price"])
        for key in ("rugged", "liquidity_collapsed"):
            if key in row:
                raw_payload[key] = row[key]
        result.append(
            Observation(
                kind=kind,
                provenance=provenance(str(row["source_id"]), observed_at),
                occurred_at=event_at,
                observed_at=observed_at,
                ingested_at=observed_at + timedelta(seconds=1),
                quality_state=QualityState.FRESH,
                normalized_payload=raw_payload,
                token_id=tokens[str(row["mint_key"])].id,
            )
        )
    return tuple(result)


def test_call_performance_fixture_replays_deterministically_and_preserves_unknowns() -> None:
    payload = load_fixture()
    assert_credential_free(payload)
    tokens = build_tokens(payload)
    calls = build_calls(payload, tokens)
    markets = build_observations(
        payload,
        tokens,
        field="market_observations",
        kind="market.market_data",
    )
    risks = build_observations(
        payload,
        tokens,
        field="risk_observations",
        kind="risk.token_outcome",
    )
    raw_tokens = payload["tokens"]
    assert isinstance(raw_tokens, dict)
    token_created_at = {
        tokens[key].mint_address: datetime.fromisoformat(str(row["created_at"]))
        for key, row in raw_tokens.items()
        if isinstance(row, dict)
    }
    analyzer = CallPerformanceAnalyzer(
        policy=CallPerformancePolicy(
            horizons=(
                ("5m", timedelta(minutes=5)),
                ("15m", timedelta(minutes=15)),
                ("1h", timedelta(hours=1)),
            ),
            reference_horizon="1h",
            minimum_sample_count=2,
            minimum_confidence=Decimal("0.50"),
        )
    )
    outcomes = analyzer.reconstruct_outcomes(
        calls,
        markets,
        risk_observations=risks,
        token_created_at=token_created_at,
        now=NOW,
        config_hash="extension-e5-4-fixture",
    )
    replay_outcomes = analyzer.reconstruct_outcomes(
        tuple(reversed(calls)),
        tuple(reversed(markets)),
        risk_observations=tuple(reversed(risks)),
        token_created_at=token_created_at,
        now=NOW,
        config_hash="extension-e5-4-fixture",
    )
    snapshots = analyzer.aggregate(
        outcomes,
        now=NOW,
        config_hash="extension-e5-4-fixture",
    )
    replay_snapshots = analyzer.aggregate(
        tuple(reversed(replay_outcomes)),
        now=NOW,
        config_hash="extension-e5-4-fixture",
    )
    by_author = {snapshot.author_id: snapshot for snapshot in snapshots}

    assert outcomes == replay_outcomes
    assert snapshots == replay_snapshots
    assert by_author["caller-good"].sample_count == 2
    assert by_author["caller-good"].hit_rate == Decimal("1")
    assert by_author["caller-good"].median_token_age_at_call_seconds is not None
    assert by_author["caller-good"].score > by_author["caller-poor"].score
    assert by_author["caller-rug"].rug_avoidance_rate == Decimal("0")
    assert by_author["caller-rug"].score < by_author["caller-good"].score
    assert by_author["caller-duplicate"].sample_count == 1
    assert "DUPLICATE_CALL_DEDUPED" in {
        reason.code for reason in by_author["caller-duplicate"].reason_codes
    }
    assert by_author["caller-insufficient"].score == Decimal("50")
    assert "MINIMUM_SAMPLE_NOT_MET" in {
        reason.code for reason in by_author["caller-insufficient"].reason_codes
    }
    assert all(snapshot.execution_eligible(NOW) is False for snapshot in snapshots)
    assert all(
        OutcomeHorizonState.COMPLETE in outcome.horizon_states.values()
        for outcome in outcomes
        if outcome.call.author_id != "caller-insufficient"
    )


def test_call_performance_contract_preserves_safe_modes_and_provider_independence() -> None:
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "call_performance.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
