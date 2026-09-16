"""Contracts for the bounded production-like reliability matrix."""

from pathlib import Path

from scripts.reliability_benchmark import run_production_soak

ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_failure_matrix_remains_explicitly_synthetic() -> None:
    report = run_production_soak(iterations=8, expected_rate_per_second=1)

    assert report["schema_version"] == "production-soak-v1"
    assert report["measurement_method"] == "synthetic_local_failure_matrix"
    assert report["iterations"] == 8
    assert report["expected_rate_per_second"] == 1.0
    assert report["measured_rate_per_second"] > 0
    assert report["headroom_ratio"] > 0
    assert report["external_acceptance"] == "BLOCKED_EXTERNAL"
    assert report["external_network"] == "not_run"
    assert report["resource_assumptions"] == {
        "processes": 1,
        "provider_access": "synthetic",
        "database": "not_connected",
        "redis": "not_connected",
        "telegram": "fixture_only",
    }
    assert set(report["scenarios"]) == {
        "provider_timeout_retry_recovery",
        "provider_rate_limit_recovery",
        "redis_restart_recovery",
        "database_interruption_recovery",
        "duplicate_delayed_out_of_order_events",
        "stale_quote_fail_closed",
        "stream_gap_recovery",
        "telegram_outage_retry_dedupe",
    }
    assert all(item["status"] == "PASS" for item in report["scenarios"].values())
    assert all(
        item["live_acceptance"] == "BLOCKED_EXTERNAL"
        for item in report["scenarios"].values()
    )
    assert report["counters"]["provider_timeouts"] == 1
    assert report["counters"]["redis_connection_failures"] == 1
    assert report["counters"]["db_connection_failures"] == 1
    assert report["counters"]["telegram_delivery_failures"] == 1


def test_production_soak_rejects_unbounded_inputs_and_documents_make_target() -> None:
    for kwargs in (
        {"iterations": 0},
        {"iterations": 8, "expected_rate_per_second": 0},
    ):
        try:
            run_production_soak(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid soak input was accepted")

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "production-soak:" in makefile
    assert "production_stack_soak.py" in makefile
    assert "reliability_benchmark.py --production-soak" not in makefile
