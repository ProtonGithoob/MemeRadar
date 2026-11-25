"""Two independent collectors of finalized Pump.fun launches for one slot window.

* ``block_scan_inventory`` -- the canonical path: finalized blocks through
  ``SolanaRpcBackfillAdapter`` (the same decoder as live ingestion and
  recovery), in small chunks so one failed fetch marks only its own slots
  UNRESOLVED instead of discarding the window.
* ``address_index_inventory`` -- a different retrieval path: the RPC address
  index of the global mint-authority PDA, which every create/create_v2 must
  reference.  It shares the IDL account order (mint at index 0) but not the
  block fetch or the instruction routing, so a block-scan loss shows up as a
  disagreement in the coverage ledger.

Read-only.  Rate limits and fetch errors become UNRESOLVED slots with reasons.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

from memeradar_application.launch_inventory import InventoryWindow, window_from_records
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_application.stream_integrity import BackfillRequest

from .pump_fun_events import pump_fun_logged_instructions
from .pump_fun_idl import PUMP_FUN_MINT_AUTHORITY, PUMP_FUN_PROGRAM_ID
from .solana_raw_stream import SolanaRpcBackfillAdapter
from .solana_rpc import SolanaRpcAdapter

BLOCK_SCAN_SOURCE = "solana-rpc-block-scan"
ADDRESS_INDEX_SOURCE = "solana-rpc-mint-authority-index"
_LOGGED_CREATE = {"Create": "create", "CreateV2": "create_v2"}


def _context(label: str, seconds: float = 60.0) -> ProviderRequestContext:
    now = datetime.now(UTC)
    return ProviderRequestContext(
        correlation_id=f"launch-inventory:{label}",
        requested_at=now,
        deadline_at=now + timedelta(seconds=seconds),
    )


async def block_scan_inventory(
    rpc: SolanaRpcAdapter,
    *,
    from_slot: int,
    to_slot: int,
    cutoff: datetime,
    chunk_size: int = 10,
    retries: int = 2,
    pause_seconds: float = 1.0,
) -> InventoryWindow:
    backfill = SolanaRpcBackfillAdapter(rpc)
    scanned: list[int] = []
    skipped: list[int] = []
    unresolved: dict[int, str] = {}
    records: list[dict[str, object]] = []
    for start in range(from_slot, to_slot + 1, chunk_size):
        end = min(start + chunk_size - 1, to_slot)
        last_error = "UNKNOWN"
        for attempt in range(retries + 1):
            try:
                result = await backfill.fetch(
                    BackfillRequest(
                        chain="solana",
                        stream_id="m1-launch-inventory",
                        from_slot=start,
                        to_slot=end,
                        timeout_seconds=60,
                        max_concurrency=4,
                    )
                )
            except Exception as error:  # noqa: BLE001 - recorded as UNRESOLVED
                last_error = f"{type(error).__name__}:{str(error)[:80]}"
                await asyncio.sleep(pause_seconds * (attempt + 1))
                continue
            for block in result.blocks:
                (scanned if block.produced else skipped).append(block.slot)
                for event in block.transactions:
                    payload = event.payload
                    name = payload.get("instruction_type") or payload.get("event_type")
                    if name not in {"create", "create_v2"}:
                        continue
                    records.append(
                        {
                            "mint": payload.get("mint_address") or payload.get("mint"),
                            "signature": event.signature,
                            "slot": event.slot,
                            "block_time": event.occurred_at,
                            "instruction": name,
                            "creator": payload.get("creator") or payload.get("user"),
                            "transaction_failed": payload.get("transaction_error") is not None,
                        }
                    )
            break
        else:
            for slot in range(start, end + 1):
                unresolved[slot] = last_error
        await asyncio.sleep(pause_seconds)
    return window_from_records(
        source=BLOCK_SCAN_SOURCE,
        from_slot=from_slot,
        to_slot=to_slot,
        cutoff=cutoff,
        scanned=scanned,
        skipped=skipped,
        unresolved=unresolved,
        records=records,
        source_revision="SolanaRpcBackfillAdapter+canonical-decoder",
    )


def _account_keys(transaction: Mapping[str, object]) -> list[str]:
    body = transaction.get("transaction")
    message = body.get("message") if isinstance(body, Mapping) else None
    raw = message.get("accountKeys") if isinstance(message, Mapping) else None
    keys: list[str] = []
    if isinstance(raw, Sequence):
        for key in raw:
            value = key.get("pubkey") if isinstance(key, Mapping) else key
            if isinstance(value, str):
                keys.append(value)
    return keys


def _instructions(transaction: Mapping[str, object]) -> list[Mapping[str, object]]:
    body = transaction.get("transaction")
    message = body.get("message") if isinstance(body, Mapping) else None
    raw = message.get("instructions") if isinstance(message, Mapping) else None
    found = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
    meta = transaction.get("meta")
    inner = meta.get("innerInstructions") if isinstance(meta, Mapping) else None
    if isinstance(inner, list):
        for group in inner:
            values = group.get("instructions") if isinstance(group, Mapping) else None
            if isinstance(values, list):
                found.extend(item for item in values if isinstance(item, Mapping))
    return found


def launch_from_index_transaction(
    transaction: Mapping[str, object], *, signature: str, slot: int
) -> dict[str, object] | None:
    """Extract a launch record without the canonical router (independent rule)."""

    meta = transaction.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    logs = meta.get("logMessages")
    logged = pump_fun_logged_instructions(logs) if isinstance(logs, list) else ()
    names = [_LOGGED_CREATE[name] for name in logged if name in _LOGGED_CREATE]
    mint: str | None = None
    for instruction in _instructions(transaction):
        if instruction.get("programId") != PUMP_FUN_PROGRAM_ID:
            continue
        accounts = instruction.get("accounts")
        if (
            isinstance(accounts, list)
            and len(accounts) > 1
            and accounts[1] == PUMP_FUN_MINT_AUTHORITY
            and isinstance(accounts[0], str)
        ):
            mint = accounts[0]
            break
    if mint is None or not names:
        return None
    block_time = transaction.get("blockTime")
    keys = _account_keys(transaction)
    return {
        "mint": mint,
        "signature": signature,
        "slot": slot,
        "block_time": (
            datetime.fromtimestamp(block_time, UTC) if isinstance(block_time, int) else None
        ),
        "instruction": names[0],
        "creator": keys[0] if keys else None,  # fee payer, a weak creator proxy
        "transaction_failed": meta.get("err") is not None,
    }


async def address_index_inventory(
    rpc: SolanaRpcAdapter,
    *,
    from_slot: int,
    to_slot: int,
    cutoff: datetime,
    max_pages: int = 20,
    retries: int = 3,
    pause_seconds: float = 0.4,
) -> InventoryWindow:
    in_window: list[tuple[str, int]] = []
    before: str | None = None
    reached_floor = False
    index_error: str | None = None
    for _page in range(max_pages):
        page = None
        for attempt in range(retries + 1):
            try:
                page = await rpc.fetch_signatures_for_address(
                    PUMP_FUN_MINT_AUTHORITY, context=_context("index"), limit=1000, before=before
                )
                break
            except Exception as error:  # noqa: BLE001 - recorded as UNRESOLVED
                index_error = f"{type(error).__name__}"
                await asyncio.sleep(pause_seconds * 3 * (attempt + 1))
        if page is None:
            break
        raw_entries = page.normalized_payload.get("signatures") or ()
        entries: list[Mapping[str, object]] = (
            [item for item in raw_entries if isinstance(item, Mapping)]
            if isinstance(raw_entries, Sequence)
            else []
        )
        if not entries:
            reached_floor = True
            break
        for entry in entries:
            slot = int(str(entry["slot"]))
            if from_slot <= slot <= to_slot:
                in_window.append((str(entry["signature"]), slot))
        oldest = int(str(entries[-1]["slot"]))
        before = str(entries[-1]["signature"])
        if oldest < from_slot:
            reached_floor = True
            break
        await asyncio.sleep(pause_seconds)
    unresolved: dict[int, str] = {}
    if not reached_floor:
        for slot in range(from_slot, to_slot + 1):
            unresolved[slot] = f"ADDRESS_INDEX_INCOMPLETE:{index_error or 'PAGE_LIMIT'}"
    records: list[dict[str, object]] = []
    for signature, slot in sorted(set(in_window), key=lambda item: (item[1], item[0])):
        transaction = None
        for attempt in range(retries + 1):
            try:
                transaction = await rpc.fetch_transaction_payload(
                    signature, context=_context("tx"), commitment="finalized"
                )
                if transaction is not None:
                    break
            except Exception:  # noqa: BLE001 - recorded as UNRESOLVED below
                pass
            await asyncio.sleep(pause_seconds * 3 * (attempt + 1))
        if transaction is None:
            unresolved[slot] = "ADDRESS_INDEX_TRANSACTION_UNAVAILABLE"
            continue
        record = launch_from_index_transaction(transaction, signature=signature, slot=slot)
        if record is not None:
            records.append(record)
        await asyncio.sleep(pause_seconds)
    return window_from_records(
        source=ADDRESS_INDEX_SOURCE,
        from_slot=from_slot,
        to_slot=to_slot,
        cutoff=cutoff,
        # The address index covers every slot once paging passed the window.
        scanned=[s for s in range(from_slot, to_slot + 1) if s not in unresolved],
        unresolved=unresolved,
        records=records,
        source_revision=f"getSignaturesForAddress:{PUMP_FUN_MINT_AUTHORITY}",
    )


__all__ = [
    "ADDRESS_INDEX_SOURCE",
    "BLOCK_SCAN_SOURCE",
    "address_index_inventory",
    "block_scan_inventory",
    "launch_from_index_transaction",
]
