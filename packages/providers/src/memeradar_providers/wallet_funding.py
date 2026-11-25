"""Bounded funding lookup: the earliest observed inbound SOL transfer to a wallet.

Pages a wallet's finalized address index (newest first, a few pages at most)
and inspects its earliest observed transactions for a System Program
``transfer`` whose destination is the wallet.  The result is a
``wallet.funding`` payload in the shape the existing relationship analyzer
reads (``from_address`` -> ``to_address``).

Coverage is explicit: when paging did not reach the wallet's first
transaction, the funding found (or not found) is ``PARTIAL``.  A shared funder
is coordination evidence only; it never asserts common ownership.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

from memeradar_application.provider_contracts import ProviderRequestContext

from .solana_rpc import SolanaRpcAdapter

SYSTEM_PROGRAM = "11111111111111111111111111111111"


def _context() -> ProviderRequestContext:
    now = datetime.now(UTC)
    return ProviderRequestContext("wallet-funding", now, deadline_at=now + timedelta(seconds=45))


def inbound_sol_transfers(
    transaction: Mapping[str, object], wallet: str
) -> list[dict[str, object]]:
    """System transfers into ``wallet`` from a jsonParsed transaction."""

    found: list[dict[str, object]] = []
    meta = transaction.get("meta")
    if isinstance(meta, Mapping) and meta.get("err") is not None:
        return found
    body = transaction.get("transaction")
    message = body.get("message") if isinstance(body, Mapping) else None
    instructions: list[object] = []
    if isinstance(message, Mapping) and isinstance(message.get("instructions"), list):
        instructions.extend(message["instructions"])
    inner = meta.get("innerInstructions") if isinstance(meta, Mapping) else None
    if isinstance(inner, list):
        for group in inner:
            if isinstance(group, Mapping) and isinstance(group.get("instructions"), list):
                instructions.extend(group["instructions"])
    for instruction in instructions:
        if not isinstance(instruction, Mapping) or instruction.get("programId") != SYSTEM_PROGRAM:
            continue
        parsed = instruction.get("parsed")
        if not isinstance(parsed, Mapping) or parsed.get("type") not in {
            "transfer",
            "transferWithSeed",
            "createAccount",
        }:
            continue
        info = parsed.get("info")
        if not isinstance(info, Mapping):
            continue
        destination = info.get("destination") or info.get("newAccount")
        source = info.get("source")
        lamports = info.get("lamports")
        if destination == wallet and isinstance(source, str) and source != wallet:
            found.append({"source": source, "lamports": lamports})
    return found


async def earliest_funding(
    rpc: SolanaRpcAdapter,
    wallet: str,
    *,
    max_pages: int = 3,
    inspect: int = 5,
    pause_seconds: float = 0.3,
) -> dict[str, object]:
    signatures: list[Mapping[str, object]] = []
    before: str | None = None
    reached_first = False
    for _page in range(max_pages):
        try:
            page = await rpc.fetch_signatures_for_address(
                wallet, context=_context(), limit=1000, before=before
            )
        except Exception:  # noqa: BLE001 - coverage recorded as partial
            break
        raw = page.normalized_payload.get("signatures")
        entries: Sequence[Mapping[str, object]] = (
            [e for e in raw if isinstance(e, Mapping)] if isinstance(raw, list | tuple) else []
        )
        signatures.extend(entries)
        if len(entries) < 1000:
            reached_first = True
            break
        before = str(entries[-1]["signature"])
        await asyncio.sleep(pause_seconds)
    oldest = sorted(signatures, key=lambda e: (int(str(e["slot"])), str(e["signature"])))
    for entry in oldest[:inspect]:
        if entry.get("err") is not None:
            continue
        try:
            transaction = await rpc.fetch_transaction_payload(
                str(entry["signature"]), context=_context(), commitment="finalized"
            )
        except Exception:  # noqa: BLE001 - skip, coverage stays explicit
            transaction = None
        await asyncio.sleep(pause_seconds)
        if transaction is None:
            continue
        transfers = inbound_sol_transfers(transaction, wallet)
        if transfers:
            first = transfers[0]
            block_time = transaction.get("blockTime")
            return {
                "chain": "solana",
                "from_address": first["source"],
                "to_address": wallet,
                "lamports": first["lamports"],
                "signature": str(entry["signature"]),
                "block_time": (
                    datetime.fromtimestamp(block_time, UTC).isoformat()
                    if isinstance(block_time, int) else None
                ),
                "coverage": "FIRST_TRANSACTIONS" if reached_first else "PARTIAL",
                "evidence": "EARLIEST_OBSERVED_INBOUND_SOL_TRANSFER",
                "ownership_asserted": False,
            }
    return {
        "chain": "solana",
        "to_address": wallet,
        "from_address": None,
        "coverage": "FIRST_TRANSACTIONS" if reached_first else "PARTIAL",
        "evidence": "NO_INBOUND_SOL_TRANSFER_IN_INSPECTED_WINDOW",
        "ownership_asserted": False,
    }


def shared_funder_clusters(
    fundings: Sequence[Mapping[str, object]], *, min_wallets: int = 3, hub_cutoff: int = 50
) -> dict[str, str]:
    """Wallets funded by the same source; very high-degree sources are hubs.

    A source that funded more than ``hub_cutoff`` observed wallets is treated
    as an exchange/router hub and produces no cluster.
    """

    by_source: dict[str, set[str]] = {}
    for funding in fundings:
        source, target = funding.get("from_address"), funding.get("to_address")
        if isinstance(source, str) and isinstance(target, str):
            by_source.setdefault(source, set()).add(target)
    clusters: dict[str, str] = {}
    for source, wallets in sorted(by_source.items()):
        if min_wallets <= len(wallets) <= hub_cutoff:
            for wallet in wallets:
                clusters.setdefault(wallet, f"funder:{source[:8]}:{len(wallets)}")
    return clusters


__all__ = ["earliest_funding", "inbound_sol_transfers", "shared_funder_clusters"]
