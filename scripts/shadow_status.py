#!/usr/bin/env python3
"""Shadow status & daily report generator for MemeRadar live read-only validation.

Queries API / database telemetry to report uptime, observed candidates, paper entries,
provider health, stream gaps, and active alerts, tagged with full evidence provenance.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
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

PRIMARY_PROVIDERS = ("helius", "birdeye")
RUN_FILE = ROOT / "artifacts" / "research" / "live-shadow" / "current_run.json"
RUNS_DIR = ROOT / "artifacts" / "research" / "live-shadow" / "runs"


@dataclass
class PaginatedResult:
    items: list[dict[str, Any]]
    pages_read: int
    is_truncated: bool
    completeness: str  # "EXACT" | "PARTIAL_TRUNCATED" | "FAILED"
    error: str | None = None


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
) -> PaginatedResult:
    """Completeness-aware pagination helper using next_cursor without total field assumption."""
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    page_count = 0
    is_truncated = False
    error_msg: str | None = None

    while page_count < max_pages:
        req_params = dict(params) if params else {}
        if cursor:
            req_params["cursor"] = cursor
        req_params.setdefault("limit", 50)

        try:
            resp = client.get(f"{api_url}{path}", params=req_params)
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}"
                break
            data = resp.json()
            page_items = data.get("items", [])
            if isinstance(page_items, list):
                items.extend(page_items)
            else:
                break

            page_count += 1
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
            if not has_more or not next_cursor:
                break

            cursor = str(next_cursor)
            if page_count >= max_pages and has_more:
                is_truncated = True
                break

        except Exception as exc:
            error_msg = str(exc)
            break

    if is_truncated:
        completeness = "PARTIAL_TRUNCATED"
    elif error_msg:
        completeness = "PARTIAL_TRUNCATED" if items else "FAILED"
    else:
        completeness = "EXACT"

    return PaginatedResult(
        items=items,
        pages_read=page_count,
        is_truncated=is_truncated,
        completeness=completeness,
        error=error_msg,
    )


def read_current_run_identity() -> dict[str, Any]:
    if RUN_FILE.exists():
        try:
            with open(RUN_FILE, encoding="utf-8") as f:
                val = json.load(f)
                if isinstance(val, dict):
                    return val
        except Exception:
            pass
    return {}


def init_run_identity() -> dict[str, Any]:
    RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    if RUN_FILE.exists():
        try:
            prev = json.loads(RUN_FILE.read_text(encoding="utf-8"))
            prev_id = prev.get("run_id", "prev_run")
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            archived = RUNS_DIR / f"run_{prev_id}_{ts}.json"
            archived.write_text(json.dumps(prev, indent=2), encoding="utf-8")
        except Exception:
            pass

    now_iso = datetime.now(UTC).isoformat()
    settings = Settings.from_env()
    run_id = f"shadow_run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

    run_data = {
        "run_id": run_id,
        "run_started_at": now_iso,
        "updated_at": now_iso,
        "state": "PENDING",
        "git_commit_sha": get_git_sha(),
        "config_hash": compute_config_hash(settings),
        "operating_modes": {
            "analysis_only": settings.analysis_only,
            "paper_trading": settings.paper_trading,
            "manual_execution": settings.manual_execution,
            "auto_execution": settings.auto_execution,
        },
    }

    RUN_FILE.write_text(json.dumps(run_data, indent=2), encoding="utf-8")
    return run_data


def update_run_identity(state: str) -> dict[str, Any]:
    data = read_current_run_identity()
    if not data:
        data = init_run_identity()
    data["state"] = state
    data["updated_at"] = datetime.now(UTC).isoformat()
    RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def evaluate_primary_provider_readiness(
    provider_health_summary: dict[str, str],
) -> tuple[str, str]:
    """Canonical readiness function requiring BOTH primary providers to be acceptable."""
    helius_state = provider_health_summary.get("helius", "UNKNOWN")
    birdeye_state = provider_health_summary.get("birdeye", "UNKNOWN")

    acceptable_states = ("FRESH", "DEGRADED")

    if helius_state not in acceptable_states or birdeye_state not in acceptable_states:
        return "BLOCKED_EXTERNAL", "NOT_ACTIVE"

    if helius_state == "FRESH" and birdeye_state == "FRESH":
        return "PROVIDERS_READY", "LIVE_SHADOW_COLLECTION_ACTIVE"

    return "DEGRADED", "LIVE_SHADOW_COLLECTION_ACTIVE"


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

    run_id = run_identity.get("run_id", "NOT_AVAILABLE")
    run_started_at = run_identity.get("run_started_at", "NOT_AVAILABLE")
    run_state = run_identity.get("state", "UNKNOWN")

    # API Telemetry Collections
    api_available = False
    candidates_res = PaginatedResult([], 0, False, "NOT_RUN")
    early_radar_res = PaginatedResult([], 0, False, "NOT_RUN")
    positions_res = PaginatedResult([], 0, False, "NOT_RUN")
    audit_events_res = PaginatedResult([], 0, False, "NOT_RUN")
    provider_health_res = PaginatedResult([], 0, False, "NOT_RUN")
    config_versions_res = PaginatedResult([], 0, False, "NOT_RUN")

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{api_url}/health/live")
            if resp.status_code == 200:
                api_available = True

            if api_available:
                candidates_res = fetch_all_paginated_items(client, api_url, "/v1/candidates")
                early_radar_res = fetch_all_paginated_items(client, api_url, "/v1/early-radar")
                positions_res = fetch_all_paginated_items(client, api_url, "/v1/positions")
                audit_events_res = fetch_all_paginated_items(client, api_url, "/v1/audit/events")
                provider_health_res = fetch_all_paginated_items(
                    client, api_url, "/v1/providers/health"
                )
                config_versions_res = fetch_all_paginated_items(
                    client, api_url, "/v1/config/versions"
                )

    except Exception:
        api_available = False

    # Candidates & Signals
    candidates = candidates_res.items
    early_radar = early_radar_res.items
    positions = positions_res.items

    candidates_count: int | None = len(candidates) if api_available else None
    early_radar_count: int | None = len(early_radar) if api_available else None

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

    # Paper Trading KPIs with UNKNOWN / None handling & coverage tracking
    paper_kpis: dict[str, Any] | None = None
    if api_available and positions is not None:
        open_pos = [p for p in positions if p.get("state") in ("PENDING", "OPEN")]
        closed_pos = [p for p in positions if p.get("state") == "CLOSED"]

        realized_pnl_values: list[float] = []
        for p in closed_pos:
            perf = p.get("performance") or {}
            val = perf.get("realized_pnl_usd")
            if val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    realized_pnl_values.append(float(val))

        unrealized_pnl_values: list[float] = []
        for p in open_pos:
            perf = p.get("performance") or {}
            val = perf.get("unrealized_pnl_usd")
            if val is not None:
                with contextlib.suppress(ValueError, TypeError):
                    unrealized_pnl_values.append(float(val))

        realized_pnl_usd = sum(realized_pnl_values) if realized_pnl_values else None
        unrealized_pnl_usd = sum(unrealized_pnl_values) if unrealized_pnl_values else None

        paper_kpis = {
            "total_positions": len(positions),
            "open_positions": len(open_pos),
            "closed_positions": len(closed_pos),
            "positions_with_realized_pnl": len(realized_pnl_values),
            "positions_with_unrealized_pnl": len(unrealized_pnl_values),
            "realized_pnl_usd": realized_pnl_usd,
            "unrealized_pnl_usd": unrealized_pnl_usd,
            "max_drawdown_pct": None,
        }

    # Provider States vs Versions separation (Task 4)
    provider_states_summary: dict[str, str] = {}
    provider_versions_summary: dict[str, str] = {}

    if provider_health_res.items:
        for item in provider_health_res.items:
            pname = str(item.get("provider", "unknown"))
            pstate = str(item.get("state", "UNKNOWN"))
            pver = item.get("version") or item.get("adapter_version") or "UNKNOWN"
            provider_states_summary[pname] = pstate
            provider_versions_summary[pname] = str(pver)

    # Evaluate Provider Readiness via Canonical Function
    if not api_available:
        stack_status = "STACK_OFFLINE"
        provider_readiness = "NOT_AVAILABLE"
        live_shadow_collection = "NOT_ACTIVE"
        verdict = "STACK_OFFLINE"
    else:
        stack_status = "STACK_READY"
        provider_readiness, live_shadow_collection = evaluate_primary_provider_readiness(
            provider_health_states := provider_states_summary
        )

        if provider_readiness == "BLOCKED_EXTERNAL":
            verdict = "STACK_READY / BLOCKED_EXTERNAL"
        elif provider_readiness == "DEGRADED":
            verdict = "STACK_READY / DEGRADED"
        else:
            verdict = "STACK_READY / LIVE_SHADOW_COLLECTION_ACTIVE"

    # Evidence Class Classification
    evidence_class = "NOT_AVAILABLE"
    if not api_available or run_state not in ("ACTIVE", "PENDING"):
        evidence_class = "NOT_AVAILABLE"
    elif candidates_count == 0 and (paper_kpis is None or paper_kpis["total_positions"] == 0):
        evidence_class = "INSUFFICIENT_SAMPLES"
    else:
        has_live_provenance = False
        has_synthetic_provenance = False

        sample_items = (candidates or []) + (positions or [])
        for item in sample_items:
            prov = item.get("provenance") or {}
            source_type = str(prov.get("source_type") or prov.get("source") or "")
            provider_name = str(prov.get("provider") or "")

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

    # Strategy & Parser Versions
    strategy_version = "NOT_CONFIGURED"
    parser_version = "NOT_AVAILABLE"

    if config_versions_res.items:
        for cv in config_versions_res.items:
            name = str(cv.get("component") or cv.get("name") or "")
            ver = str(cv.get("version") or "")
            if "strategy" in name.lower():
                strategy_version = ver
            if "parser" in name.lower():
                parser_version = ver

    provenance = {
        "evidence_class": evidence_class,
        "run_id": run_id,
        "run_started_at": run_started_at,
        "run_state": run_state,
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
        "provider_states": provider_states_summary or "NOT_AVAILABLE",
        "provider_versions": provider_versions_summary or "UNKNOWN",
    }

    pagination_completeness = {
        "candidates": {
            "completeness": candidates_res.completeness,
            "pages_read": candidates_res.pages_read,
            "is_truncated": candidates_res.is_truncated,
        },
        "early_radar": {
            "completeness": early_radar_res.completeness,
            "pages_read": early_radar_res.pages_read,
            "is_truncated": early_radar_res.is_truncated,
        },
        "positions": {
            "completeness": positions_res.completeness,
            "pages_read": positions_res.pages_read,
            "is_truncated": positions_res.is_truncated,
        },
    }

    summary = {
        "verdict": verdict,
        "real_world_alpha": "REAL_WORLD_ALPHA_NOT_YET_PROVEN",
        "stack_status": stack_status,
        "provider_readiness": provider_readiness,
        "live_shadow_collection": live_shadow_collection,
        "api_url": api_url,
        "candidates_observed": candidates_count,
        "early_radar_signals": early_radar_count,
        "decision_bands": band_counts,
        "paper_kpis": paper_kpis,
        "provider_states": provider_states_summary or "NOT_AVAILABLE",
        "stream_gaps_detected": None,  # UNKNOWN / NOT_AVAILABLE
        "stream_recovery_failures": None,  # UNKNOWN / NOT_AVAILABLE
        "alerts_dispatched": None,  # UNKNOWN / NOT_AVAILABLE (raw audit events not substituted)
        "audit_events_logged": len(audit_events_res.items) if api_available else None,
        "matured_outcomes_count": None,  # UNKNOWN / NOT_AVAILABLE
        "pagination_completeness": pagination_completeness,
    }

    return {
        "service": "memeradar-shadow-status",
        "timestamp": now.isoformat(),
        "verdict": verdict,
        "real_world_alpha": "REAL_WORLD_ALPHA_NOT_YET_PROVEN",
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
    parser.add_argument(
        "--init-run",
        action="store_true",
        help="Initialize durable shadow run identity in PENDING state",
    )
    parser.add_argument(
        "--update-run-state",
        type=str,
        default=None,
        help="Update shadow run state (e.g. ACTIVE, BLOCKED_EXTERNAL, START_FAILED, CLOSED)",
    )
    parser.add_argument(
        "--evaluate-readiness",
        action="store_true",
        help="Evaluate stack & provider readiness, update run state, and output verdict",
    )
    args = parser.parse_args()

    if args.init_run:
        run_data = init_run_identity()
        print(f"Run initialized: {run_data['run_id']} (State: {run_data['state']})")
        return 0

    if args.update_run_state:
        run_data = update_run_identity(args.update_run_state)
        print(f"Run state updated: {run_data['run_id']} -> {run_data['state']}")
        return 0

    report = get_shadow_status(args.api_url)

    if args.evaluate_readiness:
        # Update run state based on readiness evaluation
        verdict = report["summary"]["verdict"]
        if verdict == "STACK_OFFLINE":
            update_run_identity("START_FAILED")
        elif "BLOCKED_EXTERNAL" in verdict:
            update_run_identity("BLOCKED_EXTERNAL")
        elif "LIVE_SHADOW_COLLECTION_ACTIVE" in verdict or "DEGRADED" in verdict:
            update_run_identity("ACTIVE")

        print(f"Verdict: {verdict}")
        print("Real-World Alpha: REAL_WORLD_ALPHA_NOT_YET_PROVEN")
        return 0 if report["summary"]["stack_status"] == "STACK_READY" else 1

    def _fmt(val: Any) -> str:
        if val is None:
            return "UNKNOWN (NOT_AVAILABLE)"
        return str(val)

    print("==========================================================")
    print("        MemeRadar Live Read-Only Shadow Status Report      ")
    print("==========================================================")
    print(f"Timestamp:             {report['timestamp']}")
    print(f"Verdict:               {report['verdict']}")
    print(f"Real-World Alpha:      {report['real_world_alpha']}")
    print(f"Run ID:                {report['provenance']['run_id']}")
    print(f"Run State:             {report['provenance']['run_state']}")
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
    print("Provider States:")
    if isinstance(report['summary']['provider_states'], dict):
        for p, s in report['summary']['provider_states'].items():
            print(f"  - {p}: {s}")
    else:
        print(f"  - Status: {_fmt(report['summary']['provider_states'])}")
    print("Stream & Outcome Telemetry:")
    print(f"  - Stream Gaps Detected:     {_fmt(report['summary']['stream_gaps_detected'])}")
    print(f"  - Stream Recovery Failures: {_fmt(report['summary']['stream_recovery_failures'])}")
    print(f"  - Alerts Dispatched:        {_fmt(report['summary']['alerts_dispatched'])}")
    print(f"  - Audit Events Logged:      {_fmt(report['summary']['audit_events_logged'])}")
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
