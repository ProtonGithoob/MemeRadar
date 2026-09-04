"""Unit tests for live-shadow validation tooling and operational correctness.

Verifies primary provider readiness semantics, start-shadow status classification,
durable shadow-run lifecycle states, provider states vs versions separation, alerts metric,
PnL UNKNOWN handling, completeness-aware pagination, and environment propagation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import shadow_status  # noqa: E402


# 1. Primary provider readiness 7-state combination tests (Task 1)
def test_evaluate_primary_provider_readiness_both_fresh() -> None:
    health = {"helius": "FRESH", "birdeye": "FRESH"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "PROVIDERS_READY"
    assert active == "LIVE_SHADOW_COLLECTION_ACTIVE"


def test_evaluate_primary_provider_readiness_fresh_and_degraded() -> None:
    health = {"helius": "FRESH", "birdeye": "DEGRADED"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "DEGRADED"
    assert active == "LIVE_SHADOW_COLLECTION_ACTIVE"


def test_evaluate_primary_provider_readiness_both_degraded() -> None:
    health = {"helius": "DEGRADED", "birdeye": "DEGRADED"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "DEGRADED"
    assert active == "LIVE_SHADOW_COLLECTION_ACTIVE"


def test_evaluate_primary_provider_readiness_fresh_and_unknown() -> None:
    health = {"helius": "FRESH", "birdeye": "UNKNOWN"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "BLOCKED_EXTERNAL"
    assert active == "NOT_ACTIVE"


def test_evaluate_primary_provider_readiness_degraded_and_unknown() -> None:
    health = {"helius": "DEGRADED", "birdeye": "UNKNOWN"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "BLOCKED_EXTERNAL"
    assert active == "NOT_ACTIVE"


def test_evaluate_primary_provider_readiness_missing_helius() -> None:
    health = {"birdeye": "FRESH"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "BLOCKED_EXTERNAL"
    assert active == "NOT_ACTIVE"


def test_evaluate_primary_provider_readiness_missing_birdeye() -> None:
    health = {"helius": "FRESH"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    assert readiness == "BLOCKED_EXTERNAL"
    assert active == "NOT_ACTIVE"


def test_free_stack_readiness_ignores_absent_optional_helius_and_birdeye() -> None:
    health = {"solana-public-rpc": "FRESH", "dexscreener": "FRESH"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    tiers = shadow_status.evaluate_readiness_tiers(health)

    assert readiness == "PROVIDERS_READY"
    assert active == "LIVE_SHADOW_COLLECTION_ACTIVE"
    assert tiers == {
        "CORE_FREE_READINESS": "READY_FOR_FREE_READ_ONLY_SHADOW",
        "OPTIONAL_ENRICHMENT_READINESS": "OPTIONAL_UNCONFIGURED",
        "FULL_PROVIDER_READINESS": "OPTIONAL_UNCONFIGURED",
    }


def test_free_stack_degrades_without_claiming_full_provider_readiness() -> None:
    health = {"solana-public-rpc": "DEGRADED", "dexscreener": "FRESH"}
    readiness, active = shadow_status.evaluate_primary_provider_readiness(health)
    tiers = shadow_status.evaluate_readiness_tiers(health)

    assert readiness == "DEGRADED"
    assert active == "LIVE_SHADOW_COLLECTION_ACTIVE"
    assert tiers["CORE_FREE_READINESS"] == "READY_FOR_FREE_READ_ONLY_SHADOW"
    assert tiers["FULL_PROVIDER_READINESS"] == "OPTIONAL_UNCONFIGURED"


def test_free_stack_unknown_core_provider_blocks_shadow_readiness() -> None:
    tiers = shadow_status.evaluate_readiness_tiers(
        {"solana-public-rpc": "FRESH", "dexscreener": "UNKNOWN"}
    )

    assert tiers["CORE_FREE_READINESS"] == "BLOCKED_EXTERNAL"


# 2. Final Status Output Classifications (Task 2)
def test_shadow_status_final_verdicts() -> None:
    # Stack Offline
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        rep_off = shadow_status.get_shadow_status("http://localhost:18000")
        assert rep_off["verdict"] == "STACK_OFFLINE"
        assert rep_off["summary"]["stack_status"] == "STACK_OFFLINE"

    # Stack Ready + Blocked External
    def mock_blocked(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            m.json.return_value = {
                "items": [{"provider": "helius", "state": "BLOCKED_EXTERNAL"}],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_blocked):
        rep_blk = shadow_status.get_shadow_status("http://localhost:18000")
        assert rep_blk["verdict"] == "STACK_READY / BLOCKED_EXTERNAL"

    # Stack Ready + Degraded
    def mock_degraded(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            m.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "DEGRADED"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_degraded):
        rep_deg = shadow_status.get_shadow_status("http://localhost:18000")
        assert rep_deg["verdict"] == "STACK_READY / DEGRADED"

    # Stack Ready + Active
    def mock_active(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            m.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "FRESH"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_active):
        rep_act = shadow_status.get_shadow_status("http://localhost:18000")
        assert rep_act["verdict"] == "STACK_READY / LIVE_SHADOW_COLLECTION_ACTIVE"


# 3. Durable Shadow Run Lifecycle States (Task 3)
def test_shadow_run_lifecycle_states() -> None:
    # Init run in PENDING state
    run_info = shadow_status.init_run_identity()
    assert run_info["state"] == "PENDING"
    assert shadow_status.read_current_run_identity()["state"] == "PENDING"

    # Update run state to ACTIVE
    upd = shadow_status.update_run_identity("ACTIVE")
    assert upd["state"] == "ACTIVE"
    assert shadow_status.read_current_run_identity()["state"] == "ACTIVE"

    # Update run state to START_FAILED
    upd2 = shadow_status.update_run_identity("START_FAILED")
    assert upd2["state"] == "START_FAILED"
    assert shadow_status.read_current_run_identity()["state"] == "START_FAILED"


# 4. Provider States vs Versions Separation (Task 4)
def test_provider_states_vs_versions_separation() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/v1/providers/health" in url:
            m.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH", "version": "1.2.0"},
                    {"provider": "birdeye", "state": "FRESH"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        # States mapping
        assert report["provenance"]["provider_states"] == {"helius": "FRESH", "birdeye": "FRESH"}
        # Versions mapping (NOT health states!)
        assert report["provenance"]["provider_versions"]["helius"] == "1.2.0"
        assert report["provenance"]["provider_versions"]["birdeye"] == "UNKNOWN"


# 5. Alerts Metric Fix (Task 5)
def test_alerts_metric_not_substituted_with_audit_count() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/audit/events" in url:
            m.json.return_value = {
                "items": [{"id": "evt1"}, {"id": "evt2"}],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["audit_events_logged"] == 2
        # alerts_dispatched must be None (UNKNOWN/NOT_AVAILABLE), NOT audit_events count!
        assert report["summary"]["alerts_dispatched"] is None


# 6. PnL UNKNOWN Handling & Coverage (Task 6)
def test_pnl_unknown_handling_and_coverage() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/positions" in url:
            # Position without PnL metrics
            m.json.return_value = {
                "items": [{"id": "p1", "state": "OPEN", "performance": {}}],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        kpis = report["summary"]["paper_kpis"]
        assert kpis["total_positions"] == 1
        assert kpis["positions_with_unrealized_pnl"] == 0
        assert kpis["unrealized_pnl_usd"] is None  # UNKNOWN, not 0.0!

    # Position with explicit zero PnL
    def mock_get_zero(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        m = MagicMock()
        m.status_code = 200
        if "/health/live" in url:
            m.json.return_value = {"status": "live"}
        elif "/v1/positions" in url:
            m.json.return_value = {
                "items": [
                    {
                        "id": "p1",
                        "state": "CLOSED",
                        "performance": {"realized_pnl_usd": 0.0},
                    }
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            m.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return m

    with patch("httpx.Client.get", side_effect=mock_get_zero):
        report_z = shadow_status.get_shadow_status("http://localhost:18000")
        kpis_z = report_z["summary"]["paper_kpis"]
        assert kpis_z["positions_with_realized_pnl"] == 1
        assert kpis_z["realized_pnl_usd"] == 0.0  # Measured zero!


# 7. Completeness-Aware Pagination (Task 7)
def test_completeness_aware_pagination_truncation() -> None:
    mock_client = MagicMock()

    resp_p1 = MagicMock()
    resp_p1.status_code = 200
    resp_p1.json.return_value = {
        "items": [{"id": "1"}, {"id": "2"}],
        "limit": 2,
        "has_more": True,
        "next_cursor": "cur2",
    }

    mock_client.get.return_value = resp_p1

    res = shadow_status.fetch_all_paginated_items(
        mock_client, "http://localhost:18000", "/v1/candidates", max_pages=1
    )
    assert res.is_truncated is True
    assert res.completeness == "PARTIAL_TRUNCATED"
    assert len(res.items) == 2


# 8. Environment Validation & Propagation
def test_start_shadow_env_validation_safe() -> None:
    script_path = SCRIPTS_DIR / "start-shadow.sh"
    assert script_path.exists()
    res = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert res.returncode == 0, f"Bash syntax check failed: {res.stderr}"


def test_start_shadow_env_validation_unsafe() -> None:
    script_path = SCRIPTS_DIR / "start-shadow.sh"

    env = os.environ.copy()
    env["MANUAL_EXECUTION"] = "true"
    res = subprocess.run(["bash", str(script_path)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "MANUAL_EXECUTION must be false" in res.stderr


# 9. Status JSON Output
def test_shadow_status_json_output() -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        def mock_active(url: str, params: dict[str, Any] | None = None) -> MagicMock:
            m = MagicMock()
            m.status_code = 200
            if "/health/live" in url:
                m.json.return_value = {"status": "live"}
            elif "/v1/providers/health" in url:
                m.json.return_value = {
                    "items": [
                        {"provider": "helius", "state": "FRESH"},
                        {"provider": "birdeye", "state": "FRESH"},
                    ],
                    "limit": 50,
                    "has_more": False,
                }
            else:
                m.json.return_value = {"items": [], "limit": 50, "has_more": False}
            return m

        with (
            patch("httpx.Client.get", side_effect=mock_active),
            patch("sys.argv", ["shadow_status.py", "--output", str(tmp_path)]),
        ):
            exit_code = shadow_status.main()
            assert exit_code == 0

        assert tmp_path.exists()
        data = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert data["service"] == "memeradar-shadow-status"
        assert "provenance" in data
        assert "summary" in data
        assert data["real_world_alpha"] == "REAL_WORLD_ALPHA_NOT_YET_PROVEN"
        assert data["verdict"] == "STACK_READY / LIVE_SHADOW_COLLECTION_ACTIVE"

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
