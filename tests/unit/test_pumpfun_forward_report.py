from memeradar_application.pumpfun_forward_report import build_forward_report


def test_forward_report_has_requested_counts_and_no_denominator_free_rates() -> None:
    rows = [
        {
            "kind": "chain.event",
            "mint": "mint-a",
            "event_type": "launch",
            "instruction_type": "create_v2",
            "discovered_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "kind": "research.dex_forward",
            "mint": "mint-a",
            "pair_found": True,
            "dex_api_first_observed_at": "2026-01-01T00:00:12+00:00",
            "memeradar_discovered_at": "2026-01-01T00:00:00+00:00",
        },
        {"kind": "early.stage_snapshot", "mint": "mint-a", "stage": "EARLY_WATCH"},
        {"kind": "early.stage_snapshot", "mint": "mint-a", "stage": "STRONG_SETUP"},
        {
            "kind": "research.outcome",
            "mint": "mint-a",
            "horizon": "1h",
            "matured": True,
            "hit_10x": True,
            "hit_20x": False,
            "executable_peak_multiple": 10,
            "missed_winner": True,
            "stage": "STRONG_SETUP",
        },
        {"kind": "chain.event", "mint": "trade-mint", "event_type": "buy_v2"},
        {"kind": "early.stage_snapshot", "mint": "trade-mint", "stage": "WATCH"},
    ]

    report = build_forward_report(rows, generated_at="2026-01-02T00:00:00+00:00")

    assert report["TOTAL_LAUNCHES_OBSERVED"] == 1
    assert report["CREATE_COUNT"] == 0
    assert report["CREATE_V2_COUNT"] == 1
    assert report["DEX_FIRST_OBSERVATION_COUNT"] == 1
    assert report["DEX_BEFORE_MEMERADAR_COUNT"] == 0
    assert report["MEMERADAR_BEFORE_DEX_COUNT"] == 1
    assert report["MEMERADAR_DEX_LEAD"] == {
        "N": 1,
        "median": 12.0,
        "p90": 12.0,
        "p95": 12.0,
        "max": 12.0,
    }
    assert report["DISCOVERED_COUNT"] == 1
    assert report["WATCH_COUNT"] == 0
    assert report["EARLY_WATCH_COUNT"] == 1
    assert report["STRONG_SETUP_COUNT"] == 1
    assert report["MATURED_1H"] == 1
    assert report["2X_COUNT"] == 1
    assert report["10X_COUNT"] == 1
    assert report["MISSED_10X"] == 1
    assert report["FALSE_POSITIVE_COUNTS_BY_STAGE"] == {}
    assert report["STATISTICAL_SAMPLE_SUFFICIENT"] == "NO"


def test_unknown_dex_and_unmatured_outcomes_stay_explicit() -> None:
    report = build_forward_report(
        [
            {
                "kind": "chain.event",
                "mint": "mint-a",
                "event_type": "launch",
                "instruction_type": "create",
            },
            {
                "kind": "research.dex_forward",
                "mint": "mint-a",
                "pair_found": False,
                "dex_api_first_observed_at": None,
            },
        ]
    )
    assert report["TOTAL_LAUNCHES_OBSERVED"] == 1
    assert report["DEX_FIRST_OBSERVATION_COUNT"] == 0
    assert report["MEMERADAR_DEX_LEAD"]["N"] == 0
    assert report["MEMERADAR_DEX_LEAD"]["median"] == "UNKNOWN"
    assert report["MATURED_1H"] == 0
    assert report["2X_COUNT"] == 0
    assert report["MISSED_10X"] == 0
    assert report["OUTCOME_STATUS"] == "INSUFFICIENT_SAMPLES"


def test_report_surfaces_stream_gaps_as_degraded_shadow_operation() -> None:
    report = build_forward_report(
        [
            {
                "kind": "provider.ingestion_health",
                "events_received": 0,
                "raw_events_emitted": 0,
                "stream_gaps": 3,
                "stream_errors": 0,
            }
        ]
    )
    assert report["LIVE_SHADOW_OPERATIONAL"] == "DEGRADED"


def test_report_uses_persisted_discovered_snapshot_for_lead_time() -> None:
    report = build_forward_report(
        [
            {
                "kind": "chain.event",
                "mint": "mint-a",
                "event_type": "launch",
                "instruction_type": "create_v2",
            },
            {
                "kind": "early.stage_snapshot",
                "mint": "mint-a",
                "state": "DISCOVERED",
                "discovered_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "kind": "research.dex_forward",
                "mint": "mint-a",
                "pair_found": True,
                "dex_api_first_observed_at": "2026-01-01T00:00:05+00:00",
            },
        ]
    )
    assert report["MEMERADAR_DEX_LEAD"]["N"] == 1
    assert report["MEMERADAR_DEX_LEAD"]["median"] == 5.0
