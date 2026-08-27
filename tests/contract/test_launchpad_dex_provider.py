"""Keyless contracts for the synthetic launchpad and DEX event fixtures."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.launchpad_dex import (
    CanonicalDuplicateDetector,
    MeteoraAdapter,
    PumpFunAdapter,
    PumpSwapAdapter,
    RaydiumAdapter,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "launchpad_dex"
NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="launchpad-dex-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


@pytest.mark.parametrize(
    ("name", "adapter", "pool_expected"),
    (
        ("pump_fun_create.json", PumpFunAdapter(), False),
        ("pumpswap_pool_created.json", PumpSwapAdapter(), True),
        ("raydium_pool_created.json", RaydiumAdapter(), True),
        ("meteora_pool_created.json", MeteoraAdapter(), True),
    ),
)
def test_protocol_fixtures_map_to_deterministic_canonical_candidates(
    name: str,
    adapter: object,
    pool_expected: bool,
) -> None:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    payload = fixture(name)

    assert "api_key" not in raw.lower()
    assert "authorization" not in raw.lower()
    assert "private_key" not in raw.lower()
    candidate = adapter.normalize(payload, context())  # type: ignore[attr-defined]
    replay = adapter.normalize(payload, context())  # type: ignore[attr-defined]

    assert candidate.token.mint_address == "So11111111111111111111111111111111111111112"
    assert candidate.token.id == replay.token.id
    assert candidate.source_id == replay.source_id
    assert candidate.provenance.provider in {"pump.fun", "pumpswap", "raydium", "meteora"}
    assert candidate.provenance.parser_version == "launchpad-dex-v1"
    assert (candidate.pool is not None) is pool_expected
    if candidate.pool is not None:
        assert candidate.pool.token_id == candidate.token.id
        assert candidate.pool.id == replay.pool.id if replay.pool is not None else False


def test_fixtures_retain_safe_event_payloads_only() -> None:
    for path in FIXTURE_DIR.glob("*.json"):
        payload = fixture(path.name)
        data = payload.get("data")
        assert isinstance(data, Mapping)
        serialized = json.dumps(data, sort_keys=True)
        assert "api_key" not in serialized.lower()
        assert "authorization" not in serialized.lower()
        assert "private_key" not in serialized.lower()


def test_cross_protocol_duplicate_detection_preserves_all_source_ids() -> None:
    detector = CanonicalDuplicateDetector()
    candidates = (
        PumpFunAdapter().normalize(fixture("pump_fun_create.json"), context()),
        PumpSwapAdapter().normalize(fixture("pumpswap_pool_created.json"), context()),
        RaydiumAdapter().normalize(fixture("raydium_pool_created.json"), context()),
    )

    assert detector.record(candidates[0]).is_duplicate is False
    second = detector.record(candidates[1])
    third = detector.record(candidates[2])

    assert second.is_duplicate is True
    assert third.is_duplicate is True
    assert second.duplicate_keys == (f"token:{candidates[0].token.mint_address}",)
    assert third.prior_source_ids == (candidates[0].source_id, candidates[1].source_id)
