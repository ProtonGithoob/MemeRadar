"""Turn one confirmed (jsonParsed) transaction into verified wallet activities.

For a given mint:

* Pump.fun ``TradeEvent`` logs (Pump execution context only) are the only
  source of ``SWAP_BUY``/``SWAP_SELL``.  Each is reconciled against the
  wallet's own token balance delta from ``pre/postTokenBalances``.
* Remaining balance changes for the mint are classified without inventing a
  trade: the bonding curve's counter-movement is attributed and dropped;
  movement inside another program (e.g. an AMM whose events are not decoded)
  is ``UNVERIFIED_VENUE``; anything else is ``TRANSFER_IN``/``TRANSFER_OUT``.
* A failed transaction yields a single ``FAILED`` record and no position
  effect.  Creates and migrations are recorded as their own kinds.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from memeradar_application.onchain_wallet_events import (
    ActivityKind,
    OnChainWalletEvent,
    Reconciliation,
)

from .pump_fun_events import extract_pump_fun_trade_events, pump_fun_logged_instructions
from .pump_fun_idl import (
    PUMP_FUN_CREATE_ACCOUNT_NAMES,
    PUMP_FUN_CREATE_V2_ACCOUNT_NAMES,
    PUMP_FUN_PROGRAM_ID,
)
from .pump_swap_events import extract_pump_swap_events

_WSOL = "So11111111111111111111111111111111111111112"
_BENIGN_PROGRAMS = frozenset(
    {
        "11111111111111111111111111111111",
        "ComputeBudget111111111111111111111111111111",
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
        "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
        "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
    }
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
    found = [i for i in raw if isinstance(i, Mapping)] if isinstance(raw, list) else []
    meta = transaction.get("meta")
    inner = meta.get("innerInstructions") if isinstance(meta, Mapping) else None
    if isinstance(inner, list):
        for group in inner:
            values = group.get("instructions") if isinstance(group, Mapping) else None
            if isinstance(values, list):
                found.extend(i for i in values if isinstance(i, Mapping))
    return found


def _pool_owners(meta: Mapping[str, object], mint: str) -> set[str]:
    """Owners holding both ``mint`` and WSOL in this transaction (AMM pools)."""

    owners: dict[str, set[str]] = defaultdict(set)
    for key in ("preTokenBalances", "postTokenBalances"):
        entries = meta.get(key)
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, Mapping) and isinstance(entry.get("owner"), str):
                    owners[str(entry["owner"])].add(str(entry.get("mint")))
    return {owner for owner, mints in owners.items() if mint in mints and _WSOL in mints}


def _owner_deltas(meta: Mapping[str, object], mint: str) -> dict[str, int] | None:
    """Raw token delta per owner for ``mint``; None when balances are absent."""

    pre = meta.get("preTokenBalances")
    post = meta.get("postTokenBalances")
    if not isinstance(pre, list) or not isinstance(post, list):
        return None

    def amounts(entries: list[object]) -> dict[str, int]:
        totals: dict[str, int] = defaultdict(int)
        for entry in entries:
            if not isinstance(entry, Mapping) or entry.get("mint") != mint:
                continue
            owner = entry.get("owner")
            ui = entry.get("uiTokenAmount")
            amount = ui.get("amount") if isinstance(ui, Mapping) else None
            if isinstance(owner, str) and isinstance(amount, str) and amount.isdigit():
                totals[owner] += int(amount)
        return totals

    before, after = amounts(pre), amounts(post)
    return {
        owner: after.get(owner, 0) - before.get(owner, 0)
        for owner in set(before) | set(after)
        if after.get(owner, 0) != before.get(owner, 0)
    }


def wallet_activities(
    transaction: Mapping[str, object],
    *,
    mint: str,
    signature: str,
) -> tuple[OnChainWalletEvent, ...]:
    slot = transaction.get("slot")
    block_time = transaction.get("blockTime")
    meta = transaction.get("meta")
    if not (isinstance(slot, int) and isinstance(block_time, int) and isinstance(meta, Mapping)):
        return ()
    at = datetime.fromtimestamp(block_time, UTC)
    keys = _account_keys(transaction)
    fee_payer = keys[0] if keys else "UNKNOWN_FEE_PAYER"
    if meta.get("err") is not None:
        return (
            OnChainWalletEvent(
                wallet=fee_payer, mint=mint, signature=signature, slot=slot, event_index=0,
                block_time=at, kind=ActivityKind.FAILED, token_delta_raw=0,
                quote_delta_lamports=None, reconciliation=Reconciliation.NOT_APPLICABLE,
                evidence=("TRANSACTION_FAILED",),
            ),
        )
    logs = meta.get("logMessages")
    logs = [line for line in logs if isinstance(line, str)] if isinstance(logs, list) else []
    logged = pump_fun_logged_instructions(logs)
    activities: list[OnChainWalletEvent] = []
    index = 0

    for instruction in _instructions(transaction):
        if instruction.get("programId") != PUMP_FUN_PROGRAM_ID:
            continue
        accounts = instruction.get("accounts")
        if not isinstance(accounts, list) or not accounts or accounts[0] != mint:
            continue
        names = PUMP_FUN_CREATE_V2_ACCOUNT_NAMES if "CreateV2" in logged else (
            PUMP_FUN_CREATE_ACCOUNT_NAMES if "Create" in logged else None
        )
        if names is not None and len(accounts) > names.index("user"):
            activities.append(
                OnChainWalletEvent(
                    wallet=str(accounts[names.index("user")]), mint=mint, signature=signature,
                    slot=slot, event_index=index, block_time=at, kind=ActivityKind.CREATE,
                    token_delta_raw=0, quote_delta_lamports=None,
                    reconciliation=Reconciliation.NOT_APPLICABLE, venue="PUMPFUN_CURVE",
                    evidence=("PUMP_CREATE_LOGGED",),
                )
            )
            index += 1
            break
    if "Migrate" in logged:
        activities.append(
            OnChainWalletEvent(
                wallet=fee_payer, mint=mint, signature=signature, slot=slot, event_index=index,
                block_time=at, kind=ActivityKind.LIQUIDITY_MIGRATION, token_delta_raw=0,
                quote_delta_lamports=None, reconciliation=Reconciliation.NOT_APPLICABLE,
                venue="PUMPFUN_TO_PUMPSWAP", evidence=("PUMP_MIGRATE_LOGGED",),
            )
        )
        index += 1

    deltas = _owner_deltas(meta, mint)
    events = [e for e in extract_pump_fun_trade_events(logs).events if e.mint == mint]
    expected: dict[str, int] = defaultdict(int)
    for event in events:
        expected[event.user] += event.token_amount_raw if event.is_buy else -event.token_amount_raw
    for event in events:
        if deltas is None or event.user not in deltas and expected[event.user] != 0:
            reconciliation = (
                Reconciliation.UNKNOWN if deltas is None else Reconciliation.MISMATCH
            )
        else:
            reconciliation = (
                Reconciliation.MATCHED
                if deltas.get(event.user, 0) == expected[event.user]
                else Reconciliation.MISMATCH
            )
        signed_tokens = event.token_amount_raw if event.is_buy else -event.token_amount_raw
        activities.append(
            OnChainWalletEvent(
                wallet=event.user, mint=mint, signature=signature, slot=slot,
                event_index=index, block_time=at,
                kind=ActivityKind.SWAP_BUY if event.is_buy else ActivityKind.SWAP_SELL,
                token_delta_raw=signed_tokens,
                quote_delta_lamports=(
                    -event.sol_amount_lamports if event.is_buy else event.sol_amount_lamports
                ),
                reconciliation=reconciliation, venue="PUMPFUN_CURVE",
                virtual_sol_reserves=event.virtual_sol_reserves,
                virtual_token_reserves=event.virtual_token_reserves,
                evidence=(f"PUMP_TRADE_EVENT:{event.ix_name}",),
            )
        )
        index += 1

    # PumpSwap (post-graduation AMM) trades: only for a pool that holds this
    # mint and a WSOL quote, both proven by the transaction's own balances.
    pools = _pool_owners(meta, mint)
    swaps = [s for s in extract_pump_swap_events(logs) if s.pool in pools]
    # Aggregate first: several swaps by one user in a transaction reconcile
    # against the user's total delta, like the curve trades above.
    for swap in swaps:
        expected[swap.user] += swap.base_amount if swap.is_buy else -swap.base_amount
    for swap in swaps:
        signed = swap.base_amount if swap.is_buy else -swap.base_amount
        user_delta = None if deltas is None else deltas.get(swap.user, 0)
        reconciliation = (
            Reconciliation.UNKNOWN if user_delta is None
            else Reconciliation.MATCHED if user_delta == expected[swap.user]
            else Reconciliation.MISMATCH
        )
        base_after, quote_after = swap.post_trade_reserves
        activities.append(
            OnChainWalletEvent(
                wallet=swap.user, mint=mint, signature=signature, slot=slot,
                event_index=index, block_time=at,
                kind=ActivityKind.SWAP_BUY if swap.is_buy else ActivityKind.SWAP_SELL,
                token_delta_raw=signed,
                quote_delta_lamports=-swap.quote_amount if swap.is_buy else swap.quote_amount,
                reconciliation=reconciliation, venue="PUMPSWAP",
                virtual_sol_reserves=quote_after, virtual_token_reserves=base_after,
                evidence=(f"PUMPSWAP_TRADE_EVENT:pool={swap.pool}",),
            )
        )
        # The pool's own token movement mirrors the trade.
        expected.setdefault(swap.pool, 0)
        index += 1

    if deltas:
        explained = set(expected)
        residual = {owner: d for owner, d in deltas.items() if owner not in explained}
        # The curve's associated account mirrors the swaps; drop that owner
        # when its delta exactly offsets the verified trades.
        offset = -sum(expected.values())
        if events and offset:
            for owner, delta in list(residual.items()):
                if delta == offset:
                    residual.pop(owner)
                    break
        foreign = {
            str(instruction.get("programId"))
            for instruction in _instructions(transaction)
            if instruction.get("programId") not in _BENIGN_PROGRAMS
            and instruction.get("programId") != PUMP_FUN_PROGRAM_ID
        }
        for owner, delta in sorted(residual.items()):
            if foreign:
                kind = ActivityKind.UNVERIFIED_VENUE
                evidence = ("BALANCE_MOVED_IN_UNDECODED_PROGRAM", *sorted(foreign)[:3])
            else:
                kind = ActivityKind.TRANSFER_IN if delta > 0 else ActivityKind.TRANSFER_OUT
                evidence = ("TOKEN_BALANCE_CHANGE_WITHOUT_SWAP_EVENT",)
            activities.append(
                OnChainWalletEvent(
                    wallet=owner, mint=mint, signature=signature, slot=slot,
                    event_index=index, block_time=at, kind=kind, token_delta_raw=delta,
                    quote_delta_lamports=None, reconciliation=Reconciliation.NOT_APPLICABLE,
                    evidence=evidence,
                )
            )
            index += 1
    return tuple(activities)


__all__ = ["wallet_activities"]
