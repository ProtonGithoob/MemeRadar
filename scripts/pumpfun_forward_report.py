#!/usr/bin/env python3
"""Generate the reproducible Pump.fun forward-evidence report."""

from __future__ import annotations

# The repository's package roots are intentionally not installed by the bare
# script runner; imports follow the explicit local roots below.
# ruff: noqa: E402
import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    ROOT / "packages" / "application" / "src",
    ROOT / "packages" / "domain" / "src",
    ROOT / "packages" / "persistence" / "src",
):
    sys.path.insert(0, str(source_root))

from memeradar_application.pumpfun_forward_report import build_forward_report
from memeradar_persistence import AlertRow, ObservationRow, create_database_engine

RESEARCH_KINDS = (
    "chain.event",
    "early.stage_snapshot",
    "research.dex_forward",
    "research.outcome",
    "research.false_positive",
    "research.funnel_transition",
    "research.early_reevaluation",
    "provider.ingestion_health",
)


async def _load_rows(engine: AsyncEngine) -> list[dict[str, object]]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.scalars(
            select(ObservationRow).where(ObservationRow.kind.in_(RESEARCH_KINDS))
        )
        rows: list[dict[str, object]] = []
        for row in result:
            payload = dict(row.normalized_payload)
            payload.update(
                {
                    "kind": row.kind,
                    "provider": row.provider,
                    "source_id": row.source_id,
                    "event_type": row.event_type,
                    "signature": row.signature,
                    "slot": row.slot,
                    "mint": payload.get("mint", payload.get("mint_address")),
                }
            )
            rows.append(payload)
        alerts = await session.scalars(select(AlertRow))
        for alert in alerts:
            timing = alert.payload.get("alert_timing", {})
            if not isinstance(timing, Mapping):
                timing = {}
            rows.append(
                {
                    "kind": "research.telegram_delivery",
                    "decision_at": timing.get("decision_at"),
                    "outbox_at": timing.get("telegram_queued_at", alert.requested_at.isoformat()),
                    "telegram_sent_at": timing.get(
                        "telegram_sent_at",
                        None if alert.delivered_at is None else alert.delivered_at.isoformat(),
                    ),
                    "delivery_state": alert.state,
                }
            )
        return rows


async def _report(database_url: str) -> dict[str, object]:
    engine = create_database_engine(database_url)
    try:
        rows = await _load_rows(engine)
        return build_forward_report(rows)
    finally:
        await engine.dispose()


def _markdown(report: Mapping[str, object]) -> str:
    return "\n".join(
        (
            "# MemeRadar Pump.fun forward evidence",
            "",
            "All counts are persisted launch-denominated evidence. UNKNOWN is not a "
            "zero-value substitute.",
            "",
            "```json",
            json.dumps(report, indent=2, sort_keys=True),
            "```",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("MEMERADAR_DATABASE_URL"))
    parser.add_argument("--input", type=Path, help="offline JSON array of normalized report rows")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "research" / "pumpfun-forward",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    rows: Sequence[Mapping[str, object]] = ()
    if args.input is not None:
        loaded: Any = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(loaded, list) or not all(isinstance(row, Mapping) for row in loaded):
            raise ValueError("input must be a JSON array of objects")
        rows = loaded
        report = build_forward_report(rows)
    elif args.database_url:
        report = asyncio.run(_report(args.database_url))
    else:
        report = build_forward_report(())
        report["status"] = "DATABASE_NOT_CONFIGURED"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
