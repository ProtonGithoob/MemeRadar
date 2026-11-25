#!/usr/bin/env python3
"""M1: collect one bounded finalized Pump.fun launch window from two sources.

Usage:
    python scripts/launch_inventory.py --rpc-url URL [--slots 120] [--tip-margin 40]
        [--from-slot N --to-slot M] [--output-dir artifacts/research/<id>]

Writes primary/independent inventories, the coverage ledger and the cohort
manifest (with its logical digest) to the output directory.  Read-only; the
RPC URL is never written to the artifacts.  Exit code 0 when a manifest was
produced (any status), 2 when the window could not be determined.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _package in ("domain", "application", "providers", "telemetry"):
    sys.path.insert(0, str(ROOT / "packages" / _package / "src"))

from memeradar_application.launch_inventory import (
    InventoryWindow,
    build_cohort,
    window_from_records,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.pump_fun_inventory import (
    address_index_inventory,
    block_scan_inventory,
)
from memeradar_providers.solana_rpc import SolanaRpcAdapter


def _window_payload(window: InventoryWindow) -> dict[str, object]:
    return {
        "cutoff": window.cutoff.isoformat(),
        "source": window.source,
        "source_revision": window.source_revision,
        "data_rights": window.data_rights.value,
        "window": [window.from_slot, window.to_slot],
        "digest": window.digest(),
        "slot_states": {str(k): v.value for k, v in sorted(window.slot_states.items())},
        "unresolved_reasons": {str(k): v for k, v in sorted(window.unresolved_reasons.items())},
        "launches": [launch.canonical() for launch in window.launches],
        "rejected": [list(item) for item in window.rejected],
    }


async def _run(args: argparse.Namespace) -> int:
    rpc = SolanaRpcAdapter(args.rpc_url)
    try:
        if args.from_slot is not None and args.to_slot is not None:
            from_slot, to_slot = args.from_slot, args.to_slot
        else:
            now = datetime.now(UTC)
            tip = await rpc.fetch_finalized_slot(
                context=ProviderRequestContext(
                    "launch-inventory:tip", now, deadline_at=now + timedelta(seconds=20)
                )
            )
            to_slot = tip - args.tip_margin
            from_slot = to_slot - args.slots + 1
        if to_slot - from_slot + 1 > 500:
            print("WINDOW_TOO_LARGE (max 500 slots)")
            return 2
        cutoff = datetime.now(UTC)
        started = datetime.now(UTC)
        primary = await block_scan_inventory(
            rpc, from_slot=from_slot, to_slot=to_slot, cutoff=cutoff
        )
        independent = await address_index_inventory(
            rpc, from_slot=from_slot, to_slot=to_slot, cutoff=cutoff
        )
        finished = datetime.now(UTC)
    finally:
        await rpc.aclose()
    manifest = build_cohort(primary, independent)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "inventory-primary.json").write_text(
        json.dumps(_window_payload(primary), indent=1, default=str)
    )
    (out / "inventory-independent.json").write_text(
        json.dumps(_window_payload(independent), indent=1, default=str)
    )
    (out / "coverage-ledger.json").write_text(
        json.dumps(manifest.ledger.to_payload(), indent=1, default=str)
    )
    (out / "cohort-manifest.json").write_text(
        json.dumps(
            {
                **manifest.logical_payload(),
                "logical_digest": manifest.digest,
                "run": {
                    "started_at": started.isoformat(),
                    "finished_at": finished.isoformat(),
                    "cutoff": cutoff.isoformat(),
                    "rpc_host_class": args.rpc_label,
                },
            },
            indent=1,
            default=str,
        )
    )
    summary = {
        "window": [from_slot, to_slot],
        "status": manifest.status,
        "cohort_size": len(manifest.entries),
        "logical_digest": manifest.digest,
        **{k: v for k, v in manifest.ledger.to_payload().items()
           if k in {"matched_count", "primary_only", "independent_only",
                    "jointly_resolved_slots", "primary_recall", "reason_codes"}},
        "unresolved": {k: len(v) for k, v in manifest.ledger.unresolved_slots.items()},
    }
    print(json.dumps(summary, indent=1))
    return 0


def _load_window(path: Path) -> InventoryWindow:
    data = json.loads(path.read_text())
    states = data["slot_states"]
    return window_from_records(
        source=data["source"],
        from_slot=data["window"][0],
        to_slot=data["window"][1],
        cutoff=datetime.fromisoformat(data["cutoff"]),
        scanned=[int(k) for k, v in states.items() if v == "SCANNED"],
        skipped=[int(k) for k, v in states.items() if v == "SKIPPED"],
        unresolved={int(k): v for k, v in data["unresolved_reasons"].items()},
        records=[
            {**item, "block_time": datetime.fromisoformat(item["block_time"])}
            for item in data["launches"]
        ],
        source_revision=data["source_revision"],
        data_rights=data["data_rights"],
    )


def rebuild(directory: Path) -> int:
    """Rebuild the manifest from saved inventories and compare digests."""

    primary = _load_window(directory / "inventory-primary.json")
    independent = _load_window(directory / "inventory-independent.json")
    rebuilt = build_cohort(primary, independent).digest
    recorded = json.loads((directory / "cohort-manifest.json").read_text())["logical_digest"]
    print(json.dumps({"recorded": recorded, "rebuilt": rebuilt, "match": recorded == rebuilt}))
    return 0 if recorded == rebuilt else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--rebuild":
        return rebuild(Path(sys.argv[2]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--rpc-label", default="public-keyless")
    parser.add_argument("--slots", type=int, default=120)
    parser.add_argument("--tip-margin", type=int, default=40)
    parser.add_argument("--from-slot", type=int)
    parser.add_argument("--to-slot", type=int)
    parser.add_argument("--output-dir", required=True)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
