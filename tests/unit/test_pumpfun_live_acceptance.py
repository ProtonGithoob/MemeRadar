"""Offline contracts for the bounded Pump.fun live acceptance runner."""

from datetime import UTC, datetime

import pytest
from scripts.pumpfun_live_acceptance import (
    EXPECTED_PROTECTED_MODES,
    build_acceptance_record,
    validate_protected_modes,
)

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
CREATOR = "11111111111111111111111111111111"


def test_acceptance_runner_requires_the_protected_modes() -> None:
    validate_protected_modes(EXPECTED_PROTECTED_MODES)
    with pytest.raises(ValueError, match="ANALYSIS_ONLY"):
        validate_protected_modes({**EXPECTED_PROTECTED_MODES, "ANALYSIS_ONLY": False})


def test_acceptance_record_contains_first_launch_proof_and_benchmark_times() -> None:
    raw = {
        "signature": "5" * 88,
        "slot": 123,
        "program_id": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "discriminator_or_tag": "d6904cec5f8b31b4",
        "payload": {
            "instruction_type": "create_v2",
            "mint_address": MINT,
            "creator": CREATOR,
            "user": CREATOR,
            "name": "Live",
            "symbol": "LIVE",
            "provider_observed_at": NOW.isoformat(),
            "memeradar_ingested_at": NOW.isoformat(),
        },
    }

    record = build_acceptance_record(
        raw_event=raw,
        canonical_decode="PASS",
        normalized_launch="PASS",
        discovered_persisted="PASS",
        discovered_at=NOW,
        dex_first_observation_at=NOW,
        dex_lookup_status="PASS",
    )

    assert record["RawChainTransaction"] == "PASS"
    assert record["canonical_decode"] == "PASS"
    assert record["normalized_launch"] == "PASS"
    assert record["DISCOVERED_PERSISTED"] == "PASS"
    assert record["instruction_type"] == "create_v2"
    assert record["mint"] == MINT
    assert record["MemeRadar_discovered_at"] == NOW.isoformat()
    assert record["DexScreener_first_successful_observation_at"] == NOW.isoformat()
    assert record["REAL_WORLD_ALPHA_VALIDATED"] == "NO"


def test_acceptance_record_keeps_unknown_dex_visibility_explicit() -> None:
    record = build_acceptance_record(
        raw_event=None,
        canonical_decode="UNKNOWN",
        normalized_launch="UNKNOWN",
        discovered_persisted="UNKNOWN",
        discovered_at=None,
        dex_first_observation_at=None,
        dex_lookup_status="UNKNOWN",
    )

    assert record["DexScreener_first_successful_observation_at"] is None
    assert record["dexscreener_status"] == "UNKNOWN"
    assert record["REAL_WORLD_ALPHA_VALIDATED"] == "NO"
