from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scripts.production_stack_soak import HttpResult, run_stack_soak

ROOT = Path(__file__).resolve().parents[2]


def test_stack_soak_reports_real_http_stack_and_protected_modes() -> None:
    started = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

    def request(url: str, headers: dict[str, str]) -> HttpResult:
        assert headers == ({"Authorization": "Bearer viewer-test-token"} if "/v1/" in url else {})
        if url.endswith("/health/live"):
            return HttpResult(200, {"status": "alive"}, 1.0)
        if url.endswith("/health/ready"):
            return HttpResult(
                200,
                {
                    "status": "ready",
                    "dependencies": {
                        "database": {"required": True, "state": "reachable"},
                        "redis": {"required": True, "state": "reachable"},
                    },
                },
                2.0,
            )
        if "/v1/readiness" in url:
            return HttpResult(
                200,
                {
                    "gmgn_alpha_validation": {"real_observation_count": 7},
                    "protected_modes": {
                        "analysis_only": True,
                        "paper_trading": True,
                        "manual_execution": False,
                        "auto_execution": False,
                    },
                },
                3.0,
            )
        if "/v1/operations/overview" in url:
            return HttpResult(
                200,
                {
                    "modes": {
                        "analysis_only": True,
                        "paper_trading": True,
                        "manual_execution": False,
                        "auto_execution": False,
                    },
                    "execution_eligible": False,
                },
                4.0,
            )
        assert "/v1/providers/health" in url
        return HttpResult(200, {"items": []}, 5.0)

    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=2,
        interval_seconds=0,
        request=request,
        clock=lambda: started,
    )

    assert report["schema_version"] == "production-stack-soak-v1"
    assert report["measurement_method"] == "production_like_http_stack"
    assert report["request_count"] == 10
    assert report["error_count"] == 0
    assert report["readiness_failures"] == 0
    assert report["persistence"] == {
        "initial_real_observation_count": 7,
        "final_real_observation_count": 7,
        "real_observation_delta": 0,
    }
    assert report["duration_seconds"] == 0.0
    assert report["protected_modes"] == {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }
    assert report["execution_eligible"] is False
    assert report["status"] == "PASS"
    assert str(report["artifact_digest"]).startswith("sha256:")


def test_stack_soak_missing_token_is_external_blocker_and_not_success() -> None:
    report = run_stack_soak(
        "http://api.example",
        None,
        iterations=1,
        interval_seconds=0,
        request=lambda _url, _headers: HttpResult(200, {}, 1.0),
        clock=lambda: datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )

    assert report["status"] == "BLOCKED_EXTERNAL"
    assert report["request_count"] == 0
    assert report["error_count"] == 0


def test_stack_soak_accounts_for_duplicates_and_container_runtime() -> None:
    snapshots = iter(
        (
            {
                "api": {"status": "running", "restart_count": 0, "memory_usage_bytes": 100},
                "worker": {"status": "running", "restart_count": 1, "memory_usage_bytes": 200},
            },
            {
                "api": {"status": "running", "restart_count": 0, "memory_usage_bytes": 125},
                "worker": {"status": "running", "restart_count": 1, "memory_usage_bytes": 260},
            },
        )
    )

    def request(url: str, _headers: dict[str, str]) -> HttpResult:
        if url.endswith("/health/live"):
            return HttpResult(200, {}, 1.0)
        if url.endswith("/health/ready"):
            return HttpResult(200, {"dependencies": {}}, 1.0)
        if "/v1/readiness" in url:
            return HttpResult(
                200,
                {
                    "protected_modes": {
                        "analysis_only": True,
                        "paper_trading": True,
                        "manual_execution": False,
                        "auto_execution": False,
                    },
                    "real_observation_count": 0,
                },
                1.0,
            )
        if "/v1/operations/overview" in url:
            return HttpResult(
                200,
                {
                    "execution_eligible": False,
                    "metrics": {
                        "counters": {
                            "duplicate_events": 2,
                            "api_errors": 0,
                            "worker_restarts": 1,
                        }
                    },
                },
                1.0,
            )
        return HttpResult(200, {}, 1.0)

    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=1,
        interval_seconds=0,
        request=request,
        container_names=("api", "worker"),
        container_snapshot=lambda names: next(snapshots),
    )

    assert report["duplicate_accounting"] == {
        "initial_duplicate_events": 2,
        "final_duplicate_events": 2,
        "duplicate_event_delta": 0,
        "duplicate_rate_per_request": 0.0,
    }
    assert report["container_runtime"] == {
        "measurement_method": "docker_inspect_and_stats",
        "services": {
            "api": {"status": "running", "restart_count": 0},
            "worker": {"status": "running", "restart_count": 1},
        },
        "worker_liveness": "PASS",
        "process_container_restarts": {
            "api": 0,
            "worker": 0,
        },
        "memory_usage_bytes": {
            "api": {"initial": 100, "final": 125, "growth": 25},
            "worker": {"initial": 200, "final": 260, "growth": 60},
        },
    }
    assert report["status"] == "PASS"


def test_stack_soak_rejects_unbounded_parameters_and_documents_make_targets() -> None:
    for iterations, interval in ((0, 0), (100_001, 0), (1, -1)):
        try:
            run_stack_soak(
                "http://api.example",
                "viewer",
                iterations=iterations,
                interval_seconds=interval,
                request=lambda _url, _headers: HttpResult(200, {}, 1.0),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid stack-soak input was accepted")

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "production-stack-smoke:" in makefile
    assert "production-stack-acceptance:" in makefile
    assert "--strict-acceptance" in makefile
    assert "production-soak:" in makefile
    assert "production_stack_soak.py" in makefile
    assert "synthetic-reliability-benchmark:" in makefile


def _strict_request(
    *, modes: dict[str, bool] | None = None, execution_eligible: bool | None = False
):
    protected_modes = {
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    } if modes is None else modes

    def request(url: str, _headers: dict[str, str]) -> HttpResult:
        if url.endswith("/health/live"):
            return HttpResult(200, {"status": "alive"}, 1.0)
        if url.endswith("/health/ready"):
            return HttpResult(
                200,
                {
                    "dependencies": {
                        "database": {"required": True, "state": "reachable"},
                        "redis": {"required": True, "state": "reachable"},
                    }
                },
                1.0,
            )
        if "/v1/readiness" in url:
            body: dict[str, object] = {
                "gmgn_alpha_validation": {"real_observation_count": 0},
                "protected_modes": protected_modes,
            }
            if execution_eligible is not None:
                body["live_money"] = {"execution_eligible": execution_eligible}
            return HttpResult(200, body, 1.0)
        if "/v1/operations/overview" in url:
            body = {"modes": protected_modes}
            if execution_eligible is not None:
                body["execution_eligible"] = execution_eligible
            body["metrics"] = {"counters": {"duplicate_events": 0}}
            return HttpResult(200, body, 1.0)
        return HttpResult(200, {"items": []}, 1.0)

    return request


def _measured_snapshots():
    snapshots = iter(
        (
            {
                "api": {"status": "running", "restart_count": 0, "memory_usage_bytes": 100},
                "worker": {
                    "status": "running",
                    "restart_count": 0,
                    "memory_usage_bytes": 200,
                },
            },
            {
                "api": {"status": "running", "restart_count": 0, "memory_usage_bytes": 110},
                "worker": {
                    "status": "running",
                    "restart_count": 0,
                    "memory_usage_bytes": 210,
                },
            },
        )
    )
    return lambda _names: next(snapshots)


def test_strict_stack_acceptance_rejects_missing_container_measurement() -> None:
    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=1,
        interval_seconds=0,
        request=_strict_request(),
        strict_acceptance=True,
    )

    assert report["status"] != "PASS"
    assert "container_runtime" in report["strict_failures"]


def test_strict_stack_acceptance_rejects_missing_protected_modes() -> None:
    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=1,
        interval_seconds=0,
        request=_strict_request(modes={}),
        container_names=("api", "worker"),
        container_snapshot=_measured_snapshots(),
        strict_acceptance=True,
    )

    assert report["status"] != "PASS"
    assert "protected_modes" in report["strict_failures"]


def test_strict_stack_acceptance_rejects_unknown_execution_eligibility() -> None:
    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=1,
        interval_seconds=0,
        request=_strict_request(execution_eligible=None),
        container_names=("api", "worker"),
        container_snapshot=_measured_snapshots(),
        strict_acceptance=True,
    )

    assert report["status"] != "PASS"
    assert "execution_eligible" in report["strict_failures"]


def test_strict_stack_acceptance_passes_with_measured_safe_stack() -> None:
    report = run_stack_soak(
        "http://api.example",
        "viewer-test-token",
        iterations=1,
        interval_seconds=0,
        request=_strict_request(),
        container_names=("api", "worker"),
        container_snapshot=_measured_snapshots(),
        strict_acceptance=True,
    )

    assert report["strict_acceptance"] is True
    assert report["strict_failures"] == []
    assert report["dependency_readiness"] == {
        "database": "reachable",
        "redis": "reachable",
    }
    assert report["status"] == "PASS"
