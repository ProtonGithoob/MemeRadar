#!/usr/bin/env python3
"""Reverse wallet research over an M1 cohort manifest (read-only, resumable).

Usage:
    python scripts/reverse_wallet_research.py --cohort artifacts/research/<m1-run>
        --output-dir artifacts/research/<run> [--rpc-url URL] [--max-tx-per-mint 3000]
        [--outcome-horizon 1h] [--collect-only | --analyze-only]

1. For every cohort mint (winners and non-winners alike) page the finalized
   address history oldest-first and fetch each transaction.
2. Classify wallet events (verified swaps vs transfers, failed, migration,
   undecoded venue) with balance reconciliation; cache them per mint.
3. Build registry records, point-in-time profiles, co-buy clusters and a
   chronological copyability backtest with baselines.

Every artifact states its evidence class; nothing here is a calibrated result.
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

from memeradar_application.onchain_wallet_events import (
    ActivityKind,
    OnChainWalletEvent,
    Reconciliation,
    build_registry_record,
    deduplicate,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_application.wallet_copyability import CopyPolicy, backtest
from memeradar_application.wallet_intelligence import (
    ProfilePolicy,
    WalletCategory,
    build_profiles,
    co_buy_clusters,
)
from memeradar_providers.pump_fun_wallet_activity import wallet_activities
from memeradar_providers.solana_rpc import SolanaRpcAdapter


def _ctx(label: str) -> ProviderRequestContext:
    now = datetime.now(UTC)
    return ProviderRequestContext(
        f"reverse-wallet:{label}", now, deadline_at=now + timedelta(seconds=45)
    )


def _encode(event: OnChainWalletEvent) -> dict[str, object]:
    return {
        "wallet": event.wallet, "mint": event.mint, "signature": event.signature,
        "slot": event.slot, "event_index": event.event_index,
        "block_time": event.block_time.isoformat(), "kind": event.kind.value,
        "token_delta_raw": event.token_delta_raw,
        "quote_delta_lamports": event.quote_delta_lamports,
        "reconciliation": event.reconciliation.value, "venue": event.venue,
        "virtual_sol_reserves": event.virtual_sol_reserves,
        "virtual_token_reserves": event.virtual_token_reserves,
        "evidence": list(event.evidence),
    }


def _decode(row: dict[str, object]) -> OnChainWalletEvent:
    return OnChainWalletEvent(
        wallet=str(row["wallet"]), mint=str(row["mint"]), signature=str(row["signature"]),
        slot=int(row["slot"]), event_index=int(row["event_index"]),  # type: ignore[arg-type]
        block_time=datetime.fromisoformat(str(row["block_time"])),
        kind=ActivityKind(row["kind"]), token_delta_raw=int(row["token_delta_raw"]),  # type: ignore[arg-type]
        quote_delta_lamports=row["quote_delta_lamports"],  # type: ignore[arg-type]
        reconciliation=Reconciliation(row["reconciliation"]), venue=str(row["venue"]),
        virtual_sol_reserves=row["virtual_sol_reserves"],  # type: ignore[arg-type]
        virtual_token_reserves=row["virtual_token_reserves"],  # type: ignore[arg-type]
        evidence=tuple(row.get("evidence") or ()),  # type: ignore[arg-type]
    )


async def _collect_mint(
    rpc: SolanaRpcAdapter, mint: str, launch_signature: str, max_tx: int, out: Path
) -> dict[str, object]:
    cache = out / f"{mint}.events.jsonl"
    meta_path = out / f"{mint}.meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    signatures: list[dict[str, object]] = []
    before: str | None = None
    reached_launch = False
    for _page in range(max(1, max_tx // 1000) + 2):
        page = None
        for attempt in range(4):
            try:
                page = await rpc.fetch_signatures_for_address(
                    mint, context=_ctx("sigs"), limit=1000, before=before
                )
                break
            except Exception:  # noqa: BLE001 - retried, then recorded
                await asyncio.sleep(2 * (attempt + 1))
        if page is None:
            break
        entries = list(page.normalized_payload.get("signatures") or ())
        if not entries:
            reached_launch = True
            break
        signatures.extend(entries)
        if any(entry["signature"] == launch_signature for entry in entries):
            reached_launch = True
            break
        before = str(entries[-1]["signature"])
        if len(signatures) >= max_tx:
            break
        await asyncio.sleep(0.4)
    ordered = sorted(signatures, key=lambda e: (int(e["slot"]), str(e["signature"])))[-max_tx:]
    if len(signatures) > max_tx:
        reached_launch = False
    events: list[OnChainWalletEvent] = []
    missing = 0
    for entry in ordered:
        signature = str(entry["signature"])
        transaction = None
        for attempt in range(4):
            try:
                transaction = await rpc.fetch_transaction_payload(
                    signature, context=_ctx("tx"), commitment="finalized"
                )
                if transaction is not None:
                    break
            except Exception:  # noqa: BLE001 - retried, then counted missing
                pass
            await asyncio.sleep(1.5 * (attempt + 1))
        if transaction is None:
            missing += 1
            continue
        events.extend(wallet_activities(transaction, mint=mint, signature=signature))
        await asyncio.sleep(0.12)
    with cache.open("w") as handle:
        for event in events:
            handle.write(json.dumps(_encode(event)) + "\n")
    meta = {
        "mint": mint,
        "signatures": len(ordered),
        "transactions_missing": missing,
        "reached_launch_signature": reached_launch,
        "history_complete": reached_launch and missing == 0,
        "events": len(events),
    }
    meta_path.write_text(json.dumps(meta))
    return meta


async def collect(args: argparse.Namespace, cohort: dict[str, object], out: Path) -> None:
    rpc = SolanaRpcAdapter(args.rpc_url)
    try:
        for index, entry in enumerate(cohort["entries"]):  # type: ignore[arg-type]
            meta = await _collect_mint(
                rpc, entry["mint"], entry["signature"], args.max_tx_per_mint, out
            )
            print(f"[{index + 1}/{len(cohort['entries'])}] {entry['mint'][:10]} "  # type: ignore[arg-type]
                  f"tx={meta['signatures']} events={meta['events']} "
                  f"complete={meta['history_complete']}", flush=True)
    finally:
        await rpc.aclose()


def analyze(args: argparse.Namespace, cohort: dict[str, object], out: Path) -> dict[str, object]:
    now = datetime.now(UTC)
    events: list[OnChainWalletEvent] = []
    metas: dict[str, dict[str, object]] = {}
    launches: dict[str, dict[str, object]] = {}
    for entry in cohort["entries"]:  # type: ignore[union-attr]
        mint = entry["mint"]
        meta_path = out / f"{mint}.meta.json"
        if not meta_path.exists():
            continue
        metas[mint] = json.loads(meta_path.read_text())
        launches[mint] = entry
        for line in (out / f"{mint}.events.jsonl").read_text().splitlines():
            events.append(_decode(json.loads(line)))
    events = list(deduplicate(events))
    migrations = {
        e.mint: e.block_time for e in events if e.kind is ActivityKind.LIQUIDITY_MIGRATION
    }
    creators = {e.mint: e.wallet for e in events if e.kind is ActivityKind.CREATE}
    registry = {}
    for mint, entry in launches.items():
        create = next((e for e in events if e.mint == mint and e.kind is ActivityKind.CREATE), None)
        first = next((e for e in events if e.mint == mint), None)
        launch_at = create.block_time if create else (first.block_time if first else now)
        registry[mint] = build_registry_record(
            mint=mint, launch_at=launch_at, activities=[e for e in events if e.mint == mint],
            now=now, creator=creators.get(mint) or entry.get("creator"),
            launch_signature=entry["signature"], migrated_at=migrations.get(mint),
            history_complete=bool(metas[mint]["history_complete"]),
        )
    policy = ProfilePolicy(outcome_horizon=args.outcome_horizon)
    clusters = co_buy_clusters(events, as_of=now, exclude=set(creators.values()))
    profiles = build_profiles(events, registry, as_of=now, policy=policy, cluster_members=clusters)

    cache: dict[datetime, frozenset[str]] = {}

    def tracked_at(at: datetime) -> frozenset[str]:
        bucket = at.replace(minute=(at.minute // 10) * 10, second=0, microsecond=0)
        if bucket not in cache:
            past = build_profiles(
                events, registry, as_of=bucket, policy=policy,
                cluster_members=co_buy_clusters(events, as_of=bucket,
                                                exclude=set(creators.values())),
            )
            cache[bucket] = frozenset(
                w for w, p in past.items()
                if WalletCategory.EARLY_SMART_MONEY_CANDIDATE in p.categories
            )
        return cache[bucket]

    data_end = max((e.block_time for e in events), default=now)
    reports = backtest(
        events, tracked_at=tracked_at, migrations=migrations, data_end=data_end,
        policy=CopyPolicy(hold_horizon=timedelta(minutes=30)),
        evidence_class="HISTORICAL_REAL_PILOT_SMALL_SAMPLE",
    )
    category_counts: dict[str, int] = {}
    for profile in profiles.values():
        for category in profile.categories:
            category_counts[category.value] = category_counts.get(category.value, 0) + 1
    outcome_counts: dict[str, dict[str, int]] = {}
    for record in registry.values():
        for outcome in record.outcomes:
            row = outcome_counts.setdefault(outcome.horizon, {})
            row[outcome.outcome.value] = row.get(outcome.outcome.value, 0) + 1
    swaps = [e for e in events if e.is_verified_swap]
    summary = {
        "evidence_class": "HISTORICAL_REAL_PILOT_SMALL_SAMPLE",
        "generated_at": now.isoformat(),
        "cohort_digest": cohort.get("logical_digest"),
        "tokens": len(registry),
        "tokens_history_complete": sum(1 for m in metas.values() if m["history_complete"]),
        "migrated_tokens": len(migrations),
        "events": len(events),
        "verified_swaps": len(swaps),
        "swap_reconciliation": {
            r.value: sum(1 for e in swaps if e.reconciliation is r) for r in Reconciliation
        },
        "event_kinds": {k.value: sum(1 for e in events if e.kind is k) for k in ActivityKind},
        "registry_outcomes_by_horizon": outcome_counts,
        "wallets_profiled": len(profiles),
        "wallet_categories": category_counts,
        "co_buy_cluster_wallets": len(clusters),
        "profile_policy_outcome_horizon": args.outcome_horizon,
        "copyability": {name: report.to_payload() for name, report in reports.items()},
    }
    (out / "registry.json").write_text(
        json.dumps([r.to_payload() for r in registry.values()], indent=1, default=str)
    )
    (out / "profiles.json").write_text(
        json.dumps([p.to_payload() for p in profiles.values()], indent=1, default=str)
    )
    (out / "clusters.json").write_text(json.dumps(clusters, indent=1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--rpc-url", default="https://solana-rpc.publicnode.com")
    parser.add_argument("--max-tx-per-mint", type=int, default=3000)
    parser.add_argument("--outcome-horizon", default="24h")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    cohort = json.loads((Path(args.cohort) / "cohort-manifest.json").read_text())
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not args.analyze_only:
        asyncio.run(collect(args, cohort, out))
    if not args.collect_only:
        print(json.dumps(analyze(args, cohort, out), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
