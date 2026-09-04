#!/usr/bin/env python3
"""Shadow status & daily report generator for MemeRadar live read-only validation.

Queries API / database telemetry to report uptime, observed candidates, paper entries,
provider health, stream gaps, and active alerts, tagged with full evidence provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
):
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)

from memeradar_application.config import Settings  # noqa: E402


def compute_config_hash(settings: Settings) -> str:
    payload = (
        f"{settings.analysis_only}:{settings.paper_trading}:"
        f"{settings.manual_execution}:{settings.auto_execution}:{settings.app_env}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def get_git_sha() -> str:
    env_sha = os.getenv("MEMERADAR_GIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def fetch_all_paginated_items(
    client: httpx.Client,
    api_url: str,
    path: str,
    params: dict[str, Any] | None = None,
    max_pages: int = 50,
) -> tuple[list[dict[str, Any]], bool]:
    """Safely page through API using next_cursor without assuming a total field."""
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    page_count = 0
    is_truncated = False

    while page_count < max_pages:
        req_params = dict(params) if params else {}
        if cursor:
            req_params["cursor"] = cursor
        req_params.setdefault("limit", 50)

        try:
            resp = client.get(f"{api_url}{path}", params=req_params)
            if resp.status_code != 200:
                break
            data = resp.json()
            page_items = data.get("items", [])
            if isinstance(page_items, list):
                items.extend(page_items)
            else:
                break

            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
            if not has_more or not next_cursor:
                break

            cursor = str(next_cursor)
            page_count += 1
            if page_count >= max_pages:
                is_truncated = True

        except Exception:
            break

    return items, is_truncated


def read_current_run_identity() -> dict[str, Any]:
    run_file = ROOT / "artifacts" / "research" / "live-shadow" / "current_run.json"
    if run_file.exists():
        try:
            with open(run_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_shadow_status(api_url: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    settings = Settings.from_env()
    run_identity = read_current_run_identity()

    modes = {
        "analysis_only": settings.analysis_only,
        "paper_trading": settings.paper_trading,
        "manual_execution": settings.manual_execution,
        "auto_execution": settings.auto_execution,
    }

    # Run collection window metadata
    run_id = run_identity.get("run_id", "NOT_AVAILABLE")
    run_started_at = run_identity.get("run_started_at", "NOT_AVAILABLE")

    # API Telemetry Collections
    api_available = False
    candidates: list[dict[str, Any]] = []
    early_radar: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    audit_events: list[dict[str, Any]] = []
    provider_health_items: list[dict[str, Any]] = []
    config_versions: list[dict[str, Any]] = []

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{api_url}/health/live")
            if resp.status_code == 200:
                api_available = True

            if api_available:
                candidates, _ = fetch_all_paginated_items(client, api_url, "/v1/candidates")
                early_radar, _ = fetch_all_paginated_items(client, api_url, "/v1/early-radar")
                positions, _ = fetch_all_paginated_items(client, api_url, "/v1/positions")
                audit_events, _ = fetch_all_paginated_items(client, api_url, "/v1/audit/events")
                provider_health_items, _ = fetch_all_paginated_items(
                    client, api_url, "/v1/providers/health"
                )
                config_versions, _ = fetch_all_paginated_items(
                    client, api_url, "/v1/config/versions"
                )

    except Exception:
        api_available = False

    # Measured Telemetry Aggregations
    candidates_count: int | None = len(candidates) if api_available else None
    early_radar_count: int | None = len(early_radar) if api_available else None
    positions_count: int | None = len(positions) if api_available else None
    audit_events_count: int | None = len(audit_events) if api_available else None

    # Decision Band Breakdown
    band_counts: dict[str, int] | None = None
    if api_available and early_radar:
        band_counts = {
            "WATCH": 0,
            "EARLY_WATCH": 0,
            "STRONG_SETUP": 0,
            "HIGH_CONFLUENCE": 0,
            "ENTRY_READY": 0,
        }
        for item in early_radar:
            st = item.get("state")
            if st in band_counts:
                band_counts[st] += 1

    # Paper Trading Execution Metrics
    paper_kpis: dict[str, Any] | None = None
    if api_available and positions is not None:
        open_pos = [p for p in positions if p.get("state") in ("PENDING", "OPEN")]
        closed_pos = [p for p in positions if p.get("state") == "CLOSED"]

        realized_pnl = 0.0
        for p in closed_pos:
            perf = p.get("performance") or {}
            val = perf.get("realized_pnl_usd")
            if val is not None:
                try:
                    realized_pnl += float(val)
                except (ValueError, TypeError):
                    realized_pnl += 0.0

        unrealized_pnl = 0.0
        for p in open_pos:
            perf = p.get("performance") or {}
            val = perf.get("unrealized_pnl_usd")
            if val is not None:
                try:
                    unrealized_pnl += float(val)
                except (ValueError, TypeError):
                    unrealized_pnl += 0.0

        paper_kpis = {
            "total_positions": len(positions),
            "open_positions": len(open_pos),
            "closed_positions": len(closed_pos),
            "realized_pnl_usd": realized_pnl if closed_pos else 0.0,
            "unrealized_pnl_usd": unrealized_pnl if open_pos else 0.0,
            "max_drawdown_pct": None,  # Not measured unless position risk view exposes it
        }

    # Provider Health & Readiness Summaries
    provider_health_summary: dict[str, str] = {}
    if provider_health_items:
        for item in provider_health_items:
            pname = item.get("provider", "unknown")
            pstate = str(item.get("state", "UNKNOWN"))
            provider_health_summary[pname] = pstate

    helius_state = provider_health_summary.get("helius", "UNKNOWN")
    birdeye_state = provider_health_summary.get("birdeye", "UNKNOWN")

    if not api_available:
        stack_status = "STACK_OFFLINE"
        provider_readiness = "NOT_AVAILABLE"
        live_shadow_collection = "NOT_ACTIVE"
    elif helius_state == "FRESH" and birdeye_state == "FRESH":
        stack_status = "STACK_READY"
        provider_readiness = "PROVIDERS_READY"
        live_shadow_collection = "LIVE_SHADOW_COLLECTION_ACTIVE"
    elif helius_state in ("FRESH", "DEGRADED") or birdeye_state in ("FRESH", "DEGRADED"):
        stack_status = "STACK_READY"
        provider_readiness = "DEGRADED"
        live_shadow_collection = "LIVE_SHADOW_COLLECTION_ACTIVE"
    else:
        stack_status = "STACK_READY"
        provider_readiness = "BLOCKED_EXTERNAL"
        live_shadow_collection = "NOT_ACTIVE"

    # Derive Evidence Class (Task 7)
    evidence_class = "NOT_AVAILABLE"
    if not api_available:
        evidence_class = "NOT_AVAILABLE"
    elif candidates_count == 0 and positions_count == 0:
        evidence_class = "INSUFFICIENT_SAMPLES"
    else:
        # Check if items carry live provider provenance
        has_live_provenance = False
        has_synthetic_provenance = False

        sample_items = (candidates or []) + (positions or [])
        for item in sample_items:
            prov = item.get("provenance") or {}
            source_type = prov.get("source_type") or prov.get("source") or ""
            provider_name = prov.get("provider") or ""

            if source_type in ("LIVE_STREAM", "LIVE_RPC") or provider_name in (
                "helius",
                "birdeye",
                "dexscreener",
                "raydium",
            ):
                has_live_provenance = True
            elif source_type in ("SYNTHETIC_FIXTURE", "FIXTURE") or provider_name == "fixture":
                has_synthetic_provenance = True

        if has_live_provenance and live_shadow_collection == "LIVE_SHADOW_COLLECTION_ACTIVE":
            evidence_class = "LIVE_SHADOW"
        elif has_synthetic_provenance:
            evidence_class = "SYNTHETIC_FIXTURE"
        else:
            evidence_class = "INSUFFICIENT_SAMPLES"

    # Canonical Strategy & Parser Versions
    strategy_version = "NOT_CONFIGURED"
    parser_version = "NOT_AVAILABLE"

    if config_versions:
        for cv in config_versions:
            name = cv.get("component") or cv.get("name") or ""
            ver = cv.get("version") or ""
            if "strategy" in name.lower():
                strategy_version = ver
            if "parser" in name.lower():
                parser_version = ver

    provenance = {
        "evidence_class": evidence_class,
        "run_id": run_id,
        "run_started_at": run_started_at,
        "report_generated_at": now.isoformat(),
        "collection_window": {
            "start": run_started_at,
            "end": now.isoformat(),
        },
        "git_commit_sha": get_git_sha(),
        "config_hash": compute_config_hash(settings),
        "operating_modes": modes,
        "strategy_version": strategy_version,
        "parser_version": parser_version,
        "provider_versions": provider_health_summary or "NOT_AVAILABLE",
    }

    summary = {
        "stack_status": stack_status,
        "provider_readiness": provider_readiness,
        "live_shadow_collection": live_shadow_collection,
        "api_url": api_url,
        "candidates_observed": candidates_count,
        "early_radar_signals": early_radar_count,
        "decision_bands": band_counts,
        "paper_kpis": paper_kpis,
        "provider_health": provider_health_summary or "NOT_AVAILABLE",
        "stream_gaps_detected": None,  # UNKNOWN / NOT_AVAILABLE (no fake zero!)
        "stream_recovery_failures": None,  # UNKNOWN / NOT_AVAILABLE
        "alerts_dispatched": audit_events_count,
        "matured_outcomes_count": None,  # UNKNOWN / NOT_AVAILABLE
    }

    return {
        "service": "memeradar-shadow-status",
        "timestamp": now.isoformat(),
        "provenance": provenance,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MemeRadar Shadow Status & Daily Report")
    parser.add_argument(
        "--api-url",
        type=str,
        default=os.getenv("MEMERADAR_API_URL", "http://localhost:18000"),
        help="API base URL",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON report path",
    )
    args = parser.parse_args()

    report = get_shadow_status(args.api_url)

    def _fmt(val: Any) -> str:
        if val is None:
            return "UNKNOWN (NOT_AVAILABLE)"
        return str(val)

    print("==========================================================")
    print("        MemeRadar Live Read-Only Shadow Status Report      ")
    print("==========================================================")
    print(f"Timestamp:             {report['timestamp']}")
    print(f"Run ID:                {report['provenance']['run_id']}")
    print(f"Run Started At:        {report['provenance']['run_started_at']}")
    print(f"Stack Status:          {report['summary']['stack_status']}")
    print(f"Provider Readiness:    {report['summary']['provider_readiness']}")
    print(f"Shadow Collection:     {report['summary']['live_shadow_collection']}")
    print(f"Evidence Class:        {report['provenance']['evidence_class']}")
    print(f"Strategy Version:      {report['provenance']['strategy_version']}")
    print(f"Parser Version:        {report['provenance']['parser_version']}")
    print(f"Git Commit SHA:        {report['provenance']['git_commit_sha']}")
    print(f"Config Hash:           {report['provenance']['config_hash']}")
    print("Operating Modes:")
    for k, v in report['provenance']['operating_modes'].items():
        print(f"  - {k}: {v}")
    print("Telemetry Summary:")
    print(f"  - Candidates Observed: {_fmt(report['summary']['candidates_observed'])}")
    print(f"  - Early Radar Signals: {_fmt(report['summary']['early_radar_signals'])}")
    if report['summary']['decision_bands']:
        print("  - Decision Bands:")
        for b, c in report['summary']['decision_bands'].items():
            print(f"      * {b}: {c}")
    if report['summary']['paper_kpis']:
        print("  - Paper Trading KPIs:")
        for k, v in report['summary']['paper_kpis'].items():
            print(f"      * {k}: {_fmt(v)}")
    print("Provider Health:")
    if isinstance(report['summary']['provider_health'], dict):
        for p, s in report['summary']['provider_health'].items():
            print(f"  - {p}: {s}")
    else:
        print(f"  - Status: {_fmt(report['summary']['provider_health'])}")
    print("Stream & Outcome Telemetry:")
    print(f"  - Stream Gaps Detected:     {_fmt(report['summary']['stream_gaps_detected'])}")
    print(f"  - Stream Recovery Failures: {_fmt(report['summary']['stream_recovery_failures'])}")
    print(f"  - Alerts Dispatched:        {_fmt(report['summary']['alerts_dispatched'])}")
    print(f"  - Matured Outcomes Count:   {_fmt(report['summary']['matured_outcomes_count'])}")
    print("==========================================================")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Report written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
