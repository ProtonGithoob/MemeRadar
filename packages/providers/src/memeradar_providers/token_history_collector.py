"""Collect one token's finalized on-chain history as classified wallet events.

Shared by ``scripts/reverse_wallet_research.py`` and the wallet research
worker.  Pages the address index back to the launch signature (the earliest
trades identify early buyers), fetches the oldest ``max_tx`` transactions and
reports how complete the history is.  Read-only; provider errors are retried
and then counted, never turned into empty success.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from memeradar_application.onchain_wallet_events import OnChainWalletEvent
from memeradar_application.provider_contracts import ProviderRequestContext

from .pump_fun_wallet_activity import wallet_activities
from .solana_rpc import SolanaRpcAdapter


@dataclass(frozen=True, slots=True)
class TokenHistory:
    mint: str
    events: tuple[OnChainWalletEvent, ...]
    signatures_total: int
    signatures_fetched: int
    transactions_missing: int
    reached_launch_signature: bool
    truncated_after_cap: bool

    @property
    def history_complete(self) -> bool:
        return (
            self.reached_launch_signature
            and self.transactions_missing == 0
            and not self.truncated_after_cap
        )

    def meta(self) -> dict[str, object]:
        return {
            "mint": self.mint,
            "signatures_total": self.signatures_total,
            "signatures": self.signatures_fetched,
            "truncated_after_cap": self.truncated_after_cap,
            "transactions_missing": self.transactions_missing,
            "reached_launch_signature": self.reached_launch_signature,
            "history_complete": self.history_complete,
            "events": len(self.events),
        }


def _context(label: str) -> ProviderRequestContext:
    now = datetime.now(UTC)
    return ProviderRequestContext(
        f"token-history:{label}", now, deadline_at=now + timedelta(seconds=45)
    )


async def collect_token_history(
    rpc: SolanaRpcAdapter,
    mint: str,
    *,
    launch_signature: str | None,
    max_tx: int = 1500,
    max_pages: int = 60,
    pause_seconds: float = 0.12,
) -> TokenHistory:
    signatures: list[dict[str, object]] = []
    before: str | None = None
    reached_launch = False
    for _page in range(max_pages):
        page = None
        for attempt in range(4):
            try:
                page = await rpc.fetch_signatures_for_address(
                    mint, context=_context("sigs"), limit=1000, before=before
                )
                break
            except Exception:  # noqa: BLE001 - retried, then the history is partial
                await asyncio.sleep(2 * (attempt + 1))
        if page is None:
            break
        raw_entries = page.normalized_payload.get("signatures")
        entries = (
            [e for e in raw_entries if isinstance(e, dict)]
            if isinstance(raw_entries, list | tuple) else []
        )
        if not entries:
            reached_launch = launch_signature is None
            break
        signatures.extend(entries)
        if launch_signature is not None and any(
            entry.get("signature") == launch_signature for entry in entries
        ):
            reached_launch = True
            break
        before = str(entries[-1]["signature"])
        await asyncio.sleep(pause_seconds * 3)
    full = sorted(signatures, key=lambda e: (int(str(e["slot"])), str(e["signature"])))
    ordered = full[:max_tx]
    events: list[OnChainWalletEvent] = []
    missing = 0
    for entry in ordered:
        signature = str(entry["signature"])
        transaction = None
        for attempt in range(4):
            try:
                transaction = await rpc.fetch_transaction_payload(
                    signature, context=_context("tx"), commitment="finalized"
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
        await asyncio.sleep(pause_seconds)
    return TokenHistory(
        mint=mint,
        events=tuple(events),
        signatures_total=len(full),
        signatures_fetched=len(ordered),
        transactions_missing=missing,
        reached_launch_signature=reached_launch,
        truncated_after_cap=len(full) > len(ordered),
    )


__all__ = ["TokenHistory", "collect_token_history"]
