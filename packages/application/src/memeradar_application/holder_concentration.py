"""Holder concentration from the largest token accounts, pool/curve excluded.

A meme token whose top wallets hold most of the circulating supply can be
dumped on late buyers at any moment.  This module turns an RPC holder
snapshot into deterministic evidence.  Accounts owned by the trading pool or
bonding curve are liquidity, not holders, and are excluded.  A missing
snapshot is UNKNOWN, never "distributed".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

HOLDER_CONCENTRATION_VERSION = "holder-concentration-v1"
_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class TokenAccountBalance:
    token_account: str
    owner: str | None
    amount_raw: int


@dataclass(frozen=True, slots=True)
class HolderSnapshot:
    mint: str
    supply_raw: int
    largest: tuple[TokenAccountBalance, ...]
    source: str


class ConcentrationRisk(str, Enum):
    LOW = "LOW"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class HolderConcentration:
    mint: str
    risk: ConcentrationRisk
    top1_pct: Decimal | None
    top10_pct: Decimal | None
    holders_considered: int
    excluded_liquidity_accounts: int
    unknown_owner_accounts: int
    reason_codes: tuple[str, ...]
    source: str | None
    version: str = HOLDER_CONCENTRATION_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "mint": self.mint,
            "risk": self.risk.value,
            "top1_pct": None if self.top1_pct is None else str(self.top1_pct),
            "top10_pct": None if self.top10_pct is None else str(self.top10_pct),
            "holders_considered": self.holders_considered,
            "excluded_liquidity_accounts": self.excluded_liquidity_accounts,
            "unknown_owner_accounts": self.unknown_owner_accounts,
            "reason_codes": list(self.reason_codes),
            "source": self.source,
            "version": self.version,
        }


def unknown_concentration(mint: str, reason: str) -> HolderConcentration:
    return HolderConcentration(
        mint=mint,
        risk=ConcentrationRisk.UNKNOWN,
        top1_pct=None,
        top10_pct=None,
        holders_considered=0,
        excluded_liquidity_accounts=0,
        unknown_owner_accounts=0,
        reason_codes=(reason,),
        source=None,
    )


def assess_concentration(
    snapshot: HolderSnapshot,
    *,
    liquidity_owners: Iterable[str],
    elevated_top10_pct: Decimal = Decimal("30"),
    high_top10_pct: Decimal = Decimal("50"),
    high_top1_pct: Decimal = Decimal("15"),
) -> HolderConcentration:
    """Aggregate by owner, drop pool/curve accounts, and classify (hypotheses)."""

    excluded = {owner for owner in liquidity_owners if owner}
    if snapshot.supply_raw <= 0 or not snapshot.largest:
        return unknown_concentration(snapshot.mint, "HOLDER_SNAPSHOT_EMPTY")
    by_owner: dict[str, int] = {}
    excluded_count = 0
    unknown_owner = 0
    for balance in snapshot.largest:
        if balance.amount_raw <= 0:
            continue
        if balance.owner is None:
            # Without the owner we cannot tell a holder from the pool vault;
            # count it as a holder (conservative: concentration never drops).
            unknown_owner += 1
            key = f"account:{balance.token_account}"
        elif balance.owner in excluded:
            excluded_count += 1
            continue
        else:
            key = balance.owner
        by_owner[key] = by_owner.get(key, 0) + balance.amount_raw
    reasons: list[str] = []
    if excluded_count == 0:
        reasons.append("HOLDER_POOL_ACCOUNT_NOT_IDENTIFIED")
    ranked: Sequence[int] = sorted(by_owner.values(), reverse=True)
    supply = Decimal(snapshot.supply_raw)
    top1 = (Decimal(ranked[0]) * _HUNDRED / supply).quantize(Decimal("0.01")) if ranked else None
    top10 = (Decimal(sum(ranked[:10])) * _HUNDRED / supply).quantize(Decimal("0.01"))
    if top10 >= high_top10_pct or (top1 is not None and top1 >= high_top1_pct):
        risk = ConcentrationRisk.HIGH
        reasons.append("HOLDER_CONCENTRATION_HIGH")
    elif top10 >= elevated_top10_pct:
        risk = ConcentrationRisk.ELEVATED
        reasons.append("HOLDER_CONCENTRATION_ELEVATED")
    else:
        risk = ConcentrationRisk.LOW
        reasons.append("HOLDER_CONCENTRATION_LOW")
    return HolderConcentration(
        mint=snapshot.mint,
        risk=risk,
        top1_pct=top1,
        top10_pct=top10,
        holders_considered=len(ranked),
        excluded_liquidity_accounts=excluded_count,
        unknown_owner_accounts=unknown_owner,
        reason_codes=tuple(reasons),
        source=snapshot.source,
    )


__all__ = [
    "HOLDER_CONCENTRATION_VERSION",
    "ConcentrationRisk",
    "HolderConcentration",
    "HolderSnapshot",
    "TokenAccountBalance",
    "assess_concentration",
    "unknown_concentration",
]
