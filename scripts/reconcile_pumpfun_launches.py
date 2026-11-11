#!/usr/bin/env python3
"""Read-only inventory of launch identity and linked research eligibility."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for root in ("domain", "application", "persistence", "providers"):
    sys.path.insert(0, str(ROOT / "packages" / root / "src"))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from memeradar_domain import require_solana_address
from memeradar_persistence import ObservationRow, create_database_engine
from memeradar_providers.protocol_registry import (
    DEFAULT_PROTOCOL_REGISTRY,
    UnsupportedProtocolInput,
)
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID

VERSION = "pumpfun-launch-reconciliation-v1"
CLASSES = (
    "VERIFIED_VALID_LAUNCH",
    "VERIFIED_FOREIGN_PROGRAM",
    "VERIFIED_NON_CREATE_INSTRUCTION",
    "AMBIGUOUS_IDENTITY",
    "MISSING_SOURCE_EVIDENCE",
    "REQUIRES_REEVALUATION",
)
DERIVED_KINDS = (
    "early.stage_snapshot",
    "research.dex_forward",
    "research.outcome",
    "research.false_positive",
    "research.missed_winner",
    "research.early_reevaluation",
)


def _classify(row: Mapping[str, object]) -> str:
    payload = row.get("normalized_payload")
    payload = payload if isinstance(payload, Mapping) else {}
    program = row.get("program_id")
    payload_program = payload.get("program_id")
    if program and payload_program and program != payload_program:
        return "AMBIGUOUS_IDENTITY"
    program = program or payload_program
    if not isinstance(program, str) or not program:
        return "MISSING_SOURCE_EVIDENCE"
    try:
        require_solana_address(program, "program_id")
    except (TypeError, ValueError):
        return "AMBIGUOUS_IDENTITY"
    if program != PUMP_FUN_PROGRAM_ID:
        return "VERIFIED_FOREIGN_PROGRAM"
    tag = row.get("discriminator_or_tag")
    payload_tag = payload.get("discriminator_or_tag")
    if tag and payload_tag and tag != payload_tag:
        return "AMBIGUOUS_IDENTITY"
    tag = tag or payload_tag
    if not isinstance(tag, str) or not tag:
        return "MISSING_SOURCE_EVIDENCE"
    try:
        entry = DEFAULT_PROTOCOL_REGISTRY.route(program, tag)
    except (UnsupportedProtocolInput, ValueError, TypeError):
        return "AMBIGUOUS_IDENTITY"
    instruction = payload.get("instruction_type")
    if instruction is not None and (
        not isinstance(instruction, str) or instruction.lower() != entry.instruction_name
    ):
        return "AMBIGUOUS_IDENTITY"
    if entry.instruction_name not in {"create", "create_v2"}:
        return "VERIFIED_NON_CREATE_INSTRUCTION"
    if not row.get("signature") or row.get("event_index") is None:
        return "MISSING_SOURCE_EVIDENCE"
    mint = payload.get("mint_address", payload.get("mint"))
    if not isinstance(mint, str) or not mint:
        return "REQUIRES_REEVALUATION"
    try:
        require_solana_address(mint, "mint")
    except (TypeError, ValueError):
        return "REQUIRES_REEVALUATION"
    return "VERIFIED_VALID_LAUNCH"


def build_inventory(
    sources: Sequence[Mapping[str, object]], derived: Sequence[Mapping[str, object]]
) -> dict[str, Any]:
    """Classify immutable source rows; linked derived rows inherit conservative eligibility."""
    records = []
    by_token: dict[str, set[str]] = defaultdict(set)
    by_candidate: dict[str, set[str]] = defaultdict(set)
    for row in sources:
        category = _classify(row)
        for field, index in (("token_id", by_token), ("candidate_id", by_candidate)):
            if row.get(field) is not None:
                index[str(row[field])].add(category)
        records.append(
            {
                "id": str(row.get("id")),
                "provider": row.get("provider"),
                "source_id": row.get("source_id"),
                "classification": category,
                "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") else None,
                "token_id": str(row["token_id"]) if row.get("token_id") else None,
            }
        )
    records.sort(key=lambda value: (str(value["provider"]), str(value["source_id"]), value["id"]))
    counts = Counter(item["classification"] for item in records)
    derived_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in derived:
        kind = str(row.get("kind"))
        categories: set[str] = set()
        if row.get("token_id") is not None:
            categories.update(by_token.get(str(row["token_id"]), set()))
        if row.get("candidate_id") is not None:
            categories.update(by_candidate.get(str(row["candidate_id"]), set()))
        state = (
            "unlinked"
            if not categories
            else "eligible"
            if "VERIFIED_VALID_LAUNCH" in categories
            and categories <= {"VERIFIED_VALID_LAUNCH", "VERIFIED_NON_CREATE_INSTRUCTION"}
            else "excluded"
        )
        derived_counts[kind][state] += 1
    return {
        "version": VERSION,
        "registry_version": DEFAULT_PROTOCOL_REGISTRY.version,
        "total_source_records": len(records),
        "counts": {name: counts[name] for name in CLASSES},
        "records": records,
        "derived": {
            kind: {
                state: derived_counts[kind][state] for state in ("eligible", "excluded", "unlinked")
            }
            for kind in sorted(derived_counts)
        },
        "coverage": "PERSISTED_OBSERVATIONS_ONLY",
        "eligibility_semantics": "VERIFIED_LAUNCH_IDENTITY_ONLY_NOT_OUTCOME_VALIDATION",
    }


def _row(row: ObservationRow) -> dict[str, object]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "kind",
            "provider",
            "source_id",
            "candidate_id",
            "token_id",
            "program_id",
            "discriminator_or_tag",
            "signature",
            "event_index",
            "normalized_payload",
        )
    }


async def inventory_database(database_url: str, *, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= 1_000_000:
        raise ValueError("limit must be between 1 and 1000000")
    engine = create_database_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            if engine.dialect.name == "postgresql":
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
            source_rows = (
                await session.scalars(
                    select(ObservationRow)
                    .where(ObservationRow.kind == "chain.event")
                    .order_by(ObservationRow.id)
                    .limit(limit + 1)
                )
            ).all()
            derived_rows = (
                await session.scalars(
                    select(ObservationRow)
                    .where(ObservationRow.kind.in_(DERIVED_KINDS))
                    .order_by(ObservationRow.id)
                    .limit(limit + 1)
                )
            ).all()
            if len(source_rows) > limit or len(derived_rows) > limit:
                raise ValueError("inventory exceeds limit; no partial results produced")
            return build_inventory(
                [_row(row) for row in source_rows], [_row(row) for row in derived_rows]
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100_000)
    args = parser.parse_args()
    database_url = os.environ.get("MEMERADAR_DATABASE_URL")
    if not database_url:
        parser.error("MEMERADAR_DATABASE_URL must identify the database to inventory")
    report = asyncio.run(inventory_database(database_url, limit=args.limit))
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["content_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
