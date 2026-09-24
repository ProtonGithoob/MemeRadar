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
    assert report["OUTCOME_STATUS"] == "INSUFFICIENT_EVIDENCE"
    assert report["ELIGIBLE_MATURED_COUNT"] == 0
    assert report["OUTCOME_EVIDENCE_AVAILABLE_COUNT"] == 0
    assert report["OUTCOME_EVIDENCE_UNKNOWN_COUNT"] == 0


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


def test_report_distinguishes_terminal_dex_polling_and_unknown_outcomes() -> None:
    report = build_forward_report(
        [
            {
                "kind": "chain.event",
                "mint": "mint-a",
                "event_type": "launch",
                "discovered_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "kind": "chain.event",
                "mint": "mint-b",
                "event_type": "launch",
                "discovered_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "kind": "research.dex_forward",
                "mint": "mint-a",
                "pair_found": False,
                "poll_terminal": True,
                "poll_status": "HORIZON_EXHAUSTED",
            },
            {
                "kind": "research.outcome",
                "mint": "mint-a",
                "horizon": "1h",
                "matured": True,
                "quality_state": "UNKNOWN",
            },
            {
                "kind": "research.outcome",
                "mint": "mint-b",
                "horizon": "1h",
                "matured": True,
                "quality_state": "FRESH",
                "executable_peak_multiple": 2,
            },
        ],
        generated_at="2026-01-02T00:00:00+00:00",
    )

    assert report["DEX_TRACKER_STATUS_COUNTS"] == {
        "HORIZON_EXHAUSTED": 1,
        "NOT_SCHEDULED": 1,
    }
    assert report["OUTCOME_STATUS"] == "MEASURED"
    assert report["ELIGIBLE_MATURED_COUNT"] == 2
    assert report["OUTCOME_EVIDENCE_AVAILABLE_COUNT"] == 1
    assert report["OUTCOME_EVIDENCE_UNKNOWN_COUNT"] == 1
    assert report["OUTCOME_MULTIPLE_STATS"]["2X"] == {
        "hit_count": 1,
        "eligible_count": 2,
        "unknown_count": 1,
    }


def test_report_reads_durable_alert_timing_and_computes_latency_percentiles() -> None:
    report = build_forward_report(
        [
            {
                "kind": "alert.new_watch",
                "normalized_payload": {
                    "alert_timing": {
                        "signal_created_at": "2026-01-01T00:00:00+00:00",
                        "decision_at": "2026-01-01T00:00:01+00:00",
                        "telegram_enqueued_at": "2026-01-01T00:00:02+00:00",
                        "telegram_sent_at": "2026-01-01T00:00:04+00:00",
                        "alert_latency_ms": 3000,
                    }
                },
            },
        ]
    )

    assert report["TELEGRAM_DELIVERY"]["signal_created_at_count"] == 1
    assert report["TELEGRAM_DELIVERY"]["telegram_sent_at_count"] == 1
    assert report["TELEGRAM_DELIVERY"]["latency_ms"] == {
        "N": 1,
        "p50": 3000.0,
        "p95": 3000.0,
        "p99": 3000.0,
        "unknown_count": 0,
    }


def test_report_labels_matured_shadow_tokens_and_calculates_early_recall() -> None:
    rows = [
        {
            "kind": "chain.event",
            "mint": "winner",
            "event_type": "launch",
            "instruction_type": "create_v2",
            "discovered_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "kind": "early.stage_snapshot",
            "mint": "winner",
            "state": "DISCOVERED",
            "state_at": "2026-01-01T00:00:00+00:00",
            "token_age_seconds": 30,
            "liquidity": 20_000,
            "chain": "solana",
            "venue": "pump.fun",
        },
        {
            "kind": "early.stage_snapshot",
            "mint": "winner",
            "state": "EARLY_WATCH",
            "state_at": "2026-01-01T00:00:00.030000+00:00",
            "token_age_seconds": 30,
            "liquidity": 20_000,
            "chain": "solana",
            "venue": "pump.fun",
        },
        {
            "kind": "market.market_snapshot",
            "mint": "winner",
            "occurred_at": "2026-01-01T00:00:00+00:00",
            "pair_found": True,
            "quality_state": "FRESH",
            "price_usd": 1,
        },
        {
            "kind": "market.market_snapshot",
            "mint": "winner",
            "occurred_at": "2026-01-01T00:01:00+00:00",
            "pair_found": True,
            "quality_state": "FRESH",
            "price_usd": 1.2,
        },
        {
            "kind": "research.outcome",
            "mint": "winner",
            "horizon": "24h",
            "horizon_seconds": 86400,
            "signal_at": "2026-01-01T00:00:00+00:00",
            "matured": True,
            "outcome_label": "WINNER_2X",
            "price_at_detection": 1,
            "observed_peak_multiple": 2,
            "executable_peak_multiple": 2,
            "hit_2x": True,
        },
    ]

    report = build_forward_report(rows)

    assert report["FORWARD_SHADOW_MATURATION"]["winner_count"] == 1
    assert report["OUTCOME_LABEL_COUNTS"] == {"WINNER_2X": 1}
    recall = report["EARLY_WINNER_RECALL"]["thresholds"]["2X"]
    assert recall["status"] == "IMPLEMENTED"
    assert recall["before_20_pct"]["recall"] == 1.0
