"""Unit tests for live-shadow validation tooling and operational correctness.

Verifies scripts/start-shadow.sh, scripts/shadow_status.py, environment propagation,
pagination without `total`, UNKNOWN vs ZERO telemetry, durable run identity, provider readiness,
and evidence class classification.
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


# 1. Safe shadow startup and environment validation
def test_start_shadow_env_validation_safe(tmp_path: Path) -> None:
    script_path = SCRIPTS_DIR / "start-shadow.sh"
    assert script_path.exists()

    env = os.environ.copy()
    env["ANALYSIS_ONLY"] = "true"
    env["PAPER_TRADING"] = "true"
    env["MANUAL_EXECUTION"] = "false"
    env["AUTO_EXECUTION"] = "false"

    # Run bash -n syntax check
    res = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert res.returncode == 0, f"Bash syntax check failed: {res.stderr}"


# 2. Unsafe mode rejection
def test_start_shadow_env_validation_unsafe() -> None:
    script_path = SCRIPTS_DIR / "start-shadow.sh"

    # Test unsafe MANUAL_EXECUTION
    env = os.environ.copy()
    env["MANUAL_EXECUTION"] = "true"
    res = subprocess.run(["bash", str(script_path)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "MANUAL_EXECUTION must be false" in res.stderr

    # Test unsafe AUTO_EXECUTION
    env = os.environ.copy()
    env["AUTO_EXECUTION"] = "true"
    res = subprocess.run(["bash", str(script_path)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "AUTO_EXECUTION must be false" in res.stderr

    # Test unsafe ANALYSIS_ONLY
    env = os.environ.copy()
    env["ANALYSIS_ONLY"] = "false"
    res = subprocess.run(["bash", str(script_path)], env=env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "ANALYSIS_ONLY must be true" in res.stderr


# 3. Protected mode propagation into child environment
def test_start_shadow_exports_protection_invariants() -> None:
    script_content = (SCRIPTS_DIR / "start-shadow.sh").read_text(encoding="utf-8")
    assert "export ANALYSIS_ONLY=true" in script_content
    assert "export PAPER_TRADING=true" in script_content
    assert "export MANUAL_EXECUTION=false" in script_content
    assert "export AUTO_EXECUTION=false" in script_content


# 4. API health success
def test_shadow_status_api_health_success() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "FRESH"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["stack_status"] == "STACK_READY"


# 5. Provider BLOCKED_EXTERNAL
def test_shadow_status_provider_blocked_external() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "BLOCKED_EXTERNAL"},
                    {"provider": "birdeye", "state": "BLOCKED_EXTERNAL"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["provider_readiness"] == "BLOCKED_EXTERNAL"
        assert report["summary"]["live_shadow_collection"] == "NOT_ACTIVE"


# 6. Provider DEGRADED
def test_shadow_status_provider_degraded() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "DEGRADED"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["provider_readiness"] == "DEGRADED"
        assert report["summary"]["live_shadow_collection"] == "LIVE_SHADOW_COLLECTION_ACTIVE"


# 7. Real provider-ready state
def test_shadow_status_providers_ready() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "FRESH"},
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["provider_readiness"] == "PROVIDERS_READY"
        assert report["summary"]["live_shadow_collection"] == "LIVE_SHADOW_COLLECTION_ACTIVE"


# 8. Paginated candidate count (multi-page traversal)
def test_fetch_all_paginated_items_multi_page() -> None:
    mock_client = MagicMock()

    resp_p1 = MagicMock()
    resp_p1.status_code = 200
    resp_p1.json.return_value = {
        "items": [{"id": "item1"}, {"id": "item2"}],
        "limit": 2,
        "has_more": True,
        "next_cursor": "cursor_page2",
    }

    resp_p2 = MagicMock()
    resp_p2.status_code = 200
    resp_p2.json.return_value = {
        "items": [{"id": "item3"}],
        "limit": 2,
        "has_more": False,
        "next_cursor": None,
    }

    mock_client.get.side_effect = [resp_p1, resp_p2]

    items, is_truncated = shadow_status.fetch_all_paginated_items(
        mock_client, "http://localhost:18000", "/v1/candidates"
    )
    assert len(items) == 3
    assert items[0]["id"] == "item1"
    assert items[2]["id"] == "item3"
    assert not is_truncated


# 9. No `total` field assumption
def test_shadow_status_no_total_field_assumption() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/candidates" in url:
            # Notice NO "total" field!
            mock_resp.json.return_value = {
                "items": [{"id": "cand_1"}, {"id": "cand_2"}],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["summary"]["candidates_observed"] == 2


# 10. Telemetry UNKNOWN vs ZERO
def test_shadow_status_unknown_vs_zero() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        # Stream telemetry fields must be None (UNKNOWN/NOT_AVAILABLE), NOT hardcoded 0!
        assert report["summary"]["stream_gaps_detected"] is None
        assert report["summary"]["stream_recovery_failures"] is None
        assert report["summary"]["matured_outcomes_count"] is None
        # Observed candidate items count must be 0 (measured)
        assert report["summary"]["candidates_observed"] == 0


# 11. Real run collection window
def test_shadow_status_real_run_collection_window() -> None:
    mock_run = {
        "run_id": "test_shadow_run_12345",
        "run_started_at": "2026-09-04T12:00:00Z",
    }

    with (
        patch("shadow_status.read_current_run_identity", return_value=mock_run),
        patch("httpx.Client.get") as mock_get,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        mock_get.return_value = mock_resp

        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["provenance"]["run_id"] == "test_shadow_run_12345"
        assert report["provenance"]["run_started_at"] == "2026-09-04T12:00:00Z"
        assert report["provenance"]["collection_window"]["start"] == "2026-09-04T12:00:00Z"


# 12. No hard-coded provider version
def test_shadow_status_no_hardcoded_provider_versions() -> None:
    def mock_get(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [{"provider": "helius", "state": "FRESH"}],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["provenance"]["provider_versions"] == {"helius": "FRESH"}


# 13. No hard-coded synthetic strategy
def test_shadow_status_no_hardcoded_synthetic_strategy() -> None:
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        mock_get.return_value = mock_resp

        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["provenance"]["strategy_version"] == "NOT_CONFIGURED"


# 14. Provenance evidence class classification
def test_shadow_status_evidence_class_classification() -> None:
    # Scenario A: Live provider provenance + active collection -> LIVE_SHADOW
    def mock_get_live(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/providers/health" in url:
            mock_resp.json.return_value = {
                "items": [
                    {"provider": "helius", "state": "FRESH"},
                    {"provider": "birdeye", "state": "FRESH"},
                ],
                "limit": 50,
                "has_more": False,
            }
        elif "/v1/candidates" in url:
            mock_resp.json.return_value = {
                "items": [
                    {
                        "id": "c1",
                        "provenance": {"source_type": "LIVE_STREAM", "provider": "helius"},
                    }
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get_live):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["provenance"]["evidence_class"] == "LIVE_SHADOW"

    # Scenario B: Synthetic fixture provenance -> SYNTHETIC_FIXTURE
    def mock_get_fixture(url: str, params: dict[str, Any] | None = None) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "/health/live" in url:
            mock_resp.json.return_value = {"status": "live"}
        elif "/v1/candidates" in url:
            mock_resp.json.return_value = {
                "items": [
                    {
                        "id": "c1",
                        "provenance": {"source_type": "SYNTHETIC_FIXTURE", "provider": "fixture"},
                    }
                ],
                "limit": 50,
                "has_more": False,
            }
        else:
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get_fixture):
        report = shadow_status.get_shadow_status("http://localhost:18000")
        assert report["provenance"]["evidence_class"] == "SYNTHETIC_FIXTURE"


# 15. Status JSON output
def test_shadow_status_json_output() -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"items": [], "limit": 50, "has_more": False}
            mock_get.return_value = mock_resp

            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "shadow_status.py"), "--output", str(tmp_path)],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0
            assert tmp_path.exists()

            data = json.loads(tmp_path.read_text(encoding="utf-8"))
            assert data["service"] == "memeradar-shadow-status"
            assert "provenance" in data
            assert "summary" in data
            assert data["summary"]["stack_status"] == "STACK_READY"

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
