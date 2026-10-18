from datetime import UTC, datetime, timedelta

from memeradar_application.pumpfun_forward import (
    DEX_FIRST_OBSERVATION_OFFSETS_SECONDS,
    EARLY_REEVALUATION_OFFSETS_SECONDS,
    MARKET_SNAPSHOT_OFFSETS_SECONDS,
    early_reevaluation_source_id,
    forward_observation_source_id,
    lead_seconds,
    offset_label,
    poll_is_due,
)


def test_forward_schedule_is_bounded_and_contains_required_milestones() -> None:
    assert DEX_FIRST_OBSERVATION_OFFSETS_SECONDS == (
        0,
        5,
        10,
        20,
        30,
        60,
        120,
        300,
        600,
        1200,
        1800,
        3600,
    )
    assert MARKET_SNAPSHOT_OFFSETS_SECONDS == (
        0,
        30,
        60,
        120,
        300,
        600,
        1800,
        3600,
        21600,
        86400,
        259200,
        604800,
    )
    assert offset_label(0) == "T0"
    assert offset_label(30) == "30s"
    assert offset_label(3600) == "1h"
    assert len(set(DEX_FIRST_OBSERVATION_OFFSETS_SECONDS)) == 12
    assert EARLY_REEVALUATION_OFFSETS_SECONDS == (30, 60, 120, 300, 600, 900)


def test_due_poll_and_lead_use_memeradar_observation_time() -> None:
    discovered = datetime(2026, 9, 21, 7, 0, tzinfo=UTC)
    assert poll_is_due(discovered, 5, discovered + timedelta(seconds=5))
    assert not poll_is_due(discovered, 5, discovered + timedelta(seconds=4.999))
    assert lead_seconds(discovered, discovered + timedelta(seconds=12.5)) == 12.5
    assert lead_seconds(discovered, discovered - timedelta(seconds=1)) is None
    assert lead_seconds(discovered, None) is None


def test_source_identity_is_deterministic_per_mint_and_offset() -> None:
    mint = "9vRzjUmVLv894UwsBkCtmbFFLUPwUC3p8bU7RgL7pump"
    assert forward_observation_source_id(mint, 30) == (
        "pumpfun-forward:dexscreener:9vRzjUmVLv894UwsBkCtmbFFLUPwUC3p8bU7RgL7pump:30"
    )
    assert forward_observation_source_id(mint, 30) == forward_observation_source_id(mint, 30)
    assert forward_observation_source_id(mint, 30) != forward_observation_source_id(mint, 60)
    assert early_reevaluation_source_id(mint, 60) == (
        "pumpfun-forward:early-reevaluation:9vRzjUmVLv894UwsBkCtmbFFLUPwUC3p8bU7RgL7pump:60"
    )


def test_forward_policy_helpers_retain_legacy_imports_and_market_fallback() -> None:
    from memeradar_application import pumpfun_forward
    from memeradar_worker import forward_evidence

    for name in (
        "metric",
        "market_metrics",
        "valid_market_record",
        "horizon_matured",
        "endpoint_record",
        "multiple_at_endpoint",
        "initial_market_values",
        "flag",
        "outcome_flags",
    ):
        assert getattr(forward_evidence, f"_{name}") is getattr(pumpfun_forward, name)
    values = pumpfun_forward.initial_market_values(
        (), datetime(2026, 10, 18, tzinfo=UTC), ({"state": "DISCOVERED", "price_usd": "2"},)
    )
    assert values["price"] == "2"
    assert values["liquidity"] is None
