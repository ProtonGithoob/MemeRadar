"""Reverse wallet intelligence, part 1: verified on-chain wallet events and registry.

Relation to existing code: ``wallet_tracking.WalletActivity``/``WalletRoundTrip``
model already-classified BUY/SELL trades of pre-registered wallets.  This
module sits *before* them: it decides from a confirmed transaction whether an
event is a verified swap at all (versus transfer, failed, migration or an
undecoded venue) and keeps the evidence needed for reconciliation.

Two rules from the goal are enforced structurally here:

* **Never infer a BUY from a token receipt.**  A ``SWAP_BUY``/``SWAP_SELL``
  exists only when a program-verified trade event names the wallet (Pump.fun
  ``TradeEvent``, decoded from Pump-context logs).  A token balance change with
  no such event is a ``TRANSFER_IN``/``TRANSFER_OUT`` (or an unverified other-venue
  movement), with unknown cost basis.  A failed transaction has no position
  effect.  Each swap is reconciled against the wallet's token balance delta.
* **Winners are not the population.**  The registry record is built for every
  token from its own verified tape, including tokens that never moved, died
  or rugged; classification is per horizon and fails to ``CENSORED`` when the
  observable path ends (for example after migration to an AMM whose trades are
  not decoded yet).

Price semantics: ``reference_price`` is the bonding curve's virtual-reserve
ratio after a trade (market semantics, lamports per raw token).  Market cap
uses Pump.fun's fixed supply.  Executable fills for a hypothetical size are
computed from the same reserves with the constant-product curve, never from a
later peak.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain.common import ensure_utc, require_text

WALLET_ACTIVITY_VERSION = "wallet-activity-v1"
REGISTRY_VERSION = "extreme-winner-registry-v1"
PUMP_FUN_TOTAL_SUPPLY_RAW = 1_000_000_000 * 10**6  # 1e9 tokens, 6 decimals
LAMPORTS_PER_SOL = Decimal(1_000_000_000)
THRESHOLDS: tuple[int, ...] = (2, 5, 10, 20, 50, 100)
REGISTRY_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1h", timedelta(hours=1)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
    ("7d", timedelta(days=7)),
    ("30d", timedelta(days=30)),
)


class ActivityKind(str, Enum):
    SWAP_BUY = "SWAP_BUY"
    SWAP_SELL = "SWAP_SELL"
    TRANSFER_IN = "TRANSFER_IN"  # received tokens without a verified swap
    TRANSFER_OUT = "TRANSFER_OUT"
    UNVERIFIED_VENUE = "UNVERIFIED_VENUE"  # balance moved inside an undecoded program
    LIQUIDITY_MIGRATION = "LIQUIDITY_MIGRATION"
    CREATE = "CREATE"
    FAILED = "FAILED"


class Reconciliation(str, Enum):
    MATCHED = "MATCHED"  # event amount equals the wallet's balance delta
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"  # balance entries unavailable for the wallet
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class OnChainWalletEvent:
    wallet: str
    mint: str
    signature: str
    slot: int
    event_index: int
    block_time: datetime
    kind: ActivityKind
    token_delta_raw: int  # signed, from the wallet's perspective
    quote_delta_lamports: int | None  # signed SOL for swaps; None when unknown
    reconciliation: Reconciliation
    venue: str = "UNKNOWN"
    virtual_sol_reserves: int | None = None  # curve state after the trade
    virtual_token_reserves: int | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "wallet", require_text(self.wallet, "wallet", max_length=64))
        object.__setattr__(self, "mint", require_text(self.mint, "mint", max_length=64))
        object.__setattr__(self, "block_time", ensure_utc(self.block_time, "block_time"))
        object.__setattr__(self, "kind", ActivityKind(self.kind))
        object.__setattr__(self, "reconciliation", Reconciliation(self.reconciliation))
        if self.kind in {ActivityKind.SWAP_BUY, ActivityKind.SWAP_SELL}:
            if self.quote_delta_lamports is None:
                raise ValueError("a verified swap must carry its quote amount")
            if (self.kind is ActivityKind.SWAP_BUY) != (self.token_delta_raw > 0):
                raise ValueError("swap direction disagrees with token delta sign")

    @property
    def identity(self) -> tuple[str, int, str, str]:
        """Canonical dedup key: one event per (tx, index, wallet, mint)."""

        return (self.signature, self.event_index, self.wallet, self.mint)

    @property
    def is_verified_swap(self) -> bool:
        return self.kind in {ActivityKind.SWAP_BUY, ActivityKind.SWAP_SELL}

    @property
    def reference_price(self) -> Decimal | None:
        if not self.virtual_sol_reserves or not self.virtual_token_reserves:
            return None
        return Decimal(self.virtual_sol_reserves) / Decimal(self.virtual_token_reserves)

    def market_cap_sol(self) -> Decimal | None:
        price = self.reference_price
        if price is None:
            return None
        return price * PUMP_FUN_TOTAL_SUPPLY_RAW / LAMPORTS_PER_SOL


def encode_event(event: OnChainWalletEvent) -> dict[str, object]:
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


def _evidence_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def decode_event(row: Mapping[str, object]) -> OnChainWalletEvent:
    def optional_int(value: object) -> int | None:
        return None if value is None else int(str(value))

    return OnChainWalletEvent(
        wallet=str(row["wallet"]), mint=str(row["mint"]), signature=str(row["signature"]),
        slot=int(str(row["slot"])), event_index=int(str(row["event_index"])),
        block_time=datetime.fromisoformat(str(row["block_time"])),
        kind=ActivityKind(str(row["kind"])), token_delta_raw=int(str(row["token_delta_raw"])),
        quote_delta_lamports=optional_int(row.get("quote_delta_lamports")),
        reconciliation=Reconciliation(str(row["reconciliation"])),
        venue=str(row.get("venue") or "UNKNOWN"),
        virtual_sol_reserves=optional_int(row.get("virtual_sol_reserves")),
        virtual_token_reserves=optional_int(row.get("virtual_token_reserves")),
        evidence=_evidence_tuple(row.get("evidence")),
    )


def deduplicate(activities: Iterable[OnChainWalletEvent]) -> tuple[OnChainWalletEvent, ...]:
    """Provider overlap and replays must not double-count a trade."""

    seen: dict[tuple[str, int, str, str], OnChainWalletEvent] = {}
    for activity in activities:
        seen.setdefault(activity.identity, activity)
    return tuple(
        sorted(seen.values(), key=lambda a: (a.slot, a.signature, a.event_index, a.wallet))
    )


# ---------------------------------------------------------------- curve math
@dataclass(frozen=True, slots=True)
class CurveState:
    """Constant-product bonding curve state (virtual reserves, raw units)."""

    virtual_sol: int
    virtual_token: int

    def buy(self, lamports_in: int, fee_bps: int) -> tuple[int, CurveState]:
        """Tokens received for ``lamports_in`` (fee taken from the input)."""

        if lamports_in <= 0:
            return 0, self
        net = lamports_in * (10_000 - fee_bps) // 10_000
        k = self.virtual_sol * self.virtual_token
        new_sol = self.virtual_sol + net
        new_token = -(-k // new_sol)  # ceil: the curve never gives away rounding
        return self.virtual_token - new_token, CurveState(new_sol, new_token)

    def sell(self, tokens_in: int, fee_bps: int) -> tuple[int, CurveState]:
        """Lamports received for ``tokens_in`` (fee taken from the output)."""

        if tokens_in <= 0:
            return 0, self
        k = self.virtual_sol * self.virtual_token
        new_token = self.virtual_token + tokens_in
        new_sol = -(-k // new_token)
        gross = self.virtual_sol - new_sol
        return gross * (10_000 - fee_bps) // 10_000, CurveState(new_sol, new_token)


def curve_state_before(
    trades: Sequence[OnChainWalletEvent], at: datetime
) -> CurveState | None:
    """Latest curve state strictly before ``at`` (point-in-time, no lookahead)."""

    cutoff = ensure_utc(at, "at")
    state: CurveState | None = None
    for trade in trades:
        if trade.block_time >= cutoff:
            break
        if trade.is_verified_swap and trade.virtual_sol_reserves and trade.virtual_token_reserves:
            state = CurveState(trade.virtual_sol_reserves, trade.virtual_token_reserves)
    return state


# ------------------------------------------------------------- the registry
class OutcomeClass(str, Enum):
    NO_MOVE = "NO_MOVE"  # observed but < 2x
    X2 = "2x"
    X5 = "5x"
    X10 = "10x"
    X20 = "20x"
    X50 = "50x"
    X100 = "100x+"
    CENSORED = "CENSORED"
    PENDING = "PENDING"


def _class_for(multiple: Decimal) -> OutcomeClass:
    for threshold, cls in (
        (100, OutcomeClass.X100),
        (50, OutcomeClass.X50),
        (20, OutcomeClass.X20),
        (10, OutcomeClass.X10),
        (5, OutcomeClass.X5),
        (2, OutcomeClass.X2),
    ):
        if multiple >= threshold:
            return cls
    return OutcomeClass.NO_MOVE


@dataclass(frozen=True, slots=True)
class HorizonOutcome:
    horizon: str
    horizon_end: datetime
    outcome: OutcomeClass
    peak_multiple: Decimal | None
    time_to_peak_seconds: int | None
    drawdown_from_peak: Decimal | None
    censor_reason: str | None


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    chain: str
    mint: str
    creator: str | None
    launch_at: datetime
    launch_signature: str | None
    initial_market_cap_sol: Decimal | None
    observed_until: datetime | None
    migrated_at: datetime | None
    trade_count: int
    unique_buyers: int
    unique_sellers: int
    buy_volume_sol: Decimal
    sell_volume_sol: Decimal
    peak_market_cap_sol: Decimal | None
    last_market_cap_sol: Decimal | None
    outcomes: tuple[HorizonOutcome, ...]
    data_completeness: Mapping[str, object] = field(default_factory=dict)
    price_semantics: str = "CURVE_VIRTUAL_RESERVE_REFERENCE"
    version: str = REGISTRY_VERSION

    def to_payload(self) -> dict[str, object]:
        def text(value: object) -> object:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            return value

        return {
            "chain": self.chain,
            "mint": self.mint,
            "creator": self.creator,
            "launch_at": text(self.launch_at),
            "launch_signature": self.launch_signature,
            "initial_market_cap_sol": text(self.initial_market_cap_sol),
            "observed_until": text(self.observed_until),
            "migrated_at": text(self.migrated_at),
            "trade_count": self.trade_count,
            "unique_buyers": self.unique_buyers,
            "unique_sellers": self.unique_sellers,
            "buy_volume_sol": text(self.buy_volume_sol),
            "sell_volume_sol": text(self.sell_volume_sol),
            "peak_market_cap_sol": text(self.peak_market_cap_sol),
            "last_market_cap_sol": text(self.last_market_cap_sol),
            "outcomes": [
                {key: text(getattr(outcome, key)) for key in outcome.__slots__}
                for outcome in self.outcomes
            ],
            "data_completeness": dict(self.data_completeness),
            "price_semantics": self.price_semantics,
            "version": self.version,
        }


def build_registry_record(
    *,
    mint: str,
    launch_at: datetime,
    activities: Sequence[OnChainWalletEvent],
    now: datetime,
    creator: str | None = None,
    launch_signature: str | None = None,
    migrated_at: datetime | None = None,
    history_complete: bool,
    horizons: Sequence[tuple[str, timedelta]] = REGISTRY_HORIZONS,
    chain: str = "solana",
) -> RegistryRecord:
    """One token's outcome per horizon from its own verified curve tape.

    The anchor is the first verified trade's reference market cap (the
    earliest observable price).  The observable path ends at migration (AMM
    trades are not decoded yet) or at the last fetched trade; a horizon that
    extends past that end is CENSORED, never assumed flat or zero.  A horizon
    that has not elapsed yet is PENDING.
    """

    launch = ensure_utc(launch_at, "launch_at")
    checked_at = ensure_utc(now, "now")
    tape = [a for a in deduplicate(activities) if a.mint == mint and a.is_verified_swap]
    priced = [(a.block_time, a.market_cap_sol()) for a in tape if a.market_cap_sol()]
    buyers = {a.wallet for a in tape if a.kind is ActivityKind.SWAP_BUY}
    sellers = {a.wallet for a in tape if a.kind is ActivityKind.SWAP_SELL}
    buy_volume = sum(
        (Decimal(a.quote_delta_lamports or 0).copy_abs() for a in tape
         if a.kind is ActivityKind.SWAP_BUY),
        Decimal("0"),
    ) / LAMPORTS_PER_SOL
    sell_volume = sum(
        (Decimal(a.quote_delta_lamports or 0).copy_abs() for a in tape
         if a.kind is ActivityKind.SWAP_SELL),
        Decimal("0"),
    ) / LAMPORTS_PER_SOL
    initial = priced[0][1] if priced else None
    path_end = priced[-1][0] if priced else None
    amm_decoded = any(a.venue == "PUMPSWAP" for a in tape)
    if migrated_at is not None and not amm_decoded:
        # Without decoded AMM trades the observable path ends at migration.
        migrated = ensure_utc(migrated_at, "migrated_at")
        path_end = migrated if path_end is None else min(path_end, migrated)
    observable_until = (
        checked_at if history_complete and (migrated_at is None or amm_decoded) else path_end
    )
    outcomes: list[HorizonOutcome] = []
    for name, duration in horizons:
        end = launch + duration
        window = [(t, cap) for t, cap in priced if t <= end]
        path_cut = migrated_at is not None and not amm_decoded and ensure_utc(
            migrated_at, "migrated_at"
        ) <= checked_at
        if checked_at < end and not path_cut:
            outcomes.append(HorizonOutcome(name, end, OutcomeClass.PENDING, None, None, None,
                                           "HORIZON_NOT_MATURE"))
            continue
        if initial is None or not window:
            outcomes.append(HorizonOutcome(name, end, OutcomeClass.CENSORED, None, None, None,
                                           "NO_VERIFIED_PRICED_TRADE"))
            continue
        peak_time, peak_cap = max(window, key=lambda item: item[1])  # type: ignore[arg-type,return-value]
        assert peak_cap is not None
        after_peak = [cap for t, cap in window if t >= peak_time and cap is not None]
        trough = min(after_peak) if after_peak else peak_cap
        multiple = (peak_cap / initial).quantize(Decimal("0.0001"))
        censor: str | None = None
        outcome = _class_for(multiple)
        if observable_until is None or observable_until < end:
            # The path ends early: a class reached so far is a lower bound;
            # a non-move can't be confirmed.
            if outcome is OutcomeClass.NO_MOVE:
                outcome = OutcomeClass.CENSORED
            censor = (
                "PATH_ENDS_AT_MIGRATION" if migrated_at and not amm_decoded
                else "HISTORY_INCOMPLETE"
            )
        outcomes.append(
            HorizonOutcome(
                horizon=name,
                horizon_end=end,
                outcome=outcome,
                peak_multiple=multiple,
                time_to_peak_seconds=int((peak_time - launch).total_seconds()),
                drawdown_from_peak=((peak_cap - trough) / peak_cap).quantize(Decimal("0.0001")),
                censor_reason=censor,
            )
        )
    return RegistryRecord(
        chain=chain,
        mint=mint,
        creator=creator,
        launch_at=launch,
        launch_signature=launch_signature,
        initial_market_cap_sol=None if initial is None else initial.quantize(Decimal("0.0001")),
        observed_until=observable_until,
        migrated_at=None if migrated_at is None else ensure_utc(migrated_at, "migrated_at"),
        trade_count=len(tape),
        unique_buyers=len(buyers),
        unique_sellers=len(sellers),
        buy_volume_sol=buy_volume.quantize(Decimal("0.000001")),
        sell_volume_sol=sell_volume.quantize(Decimal("0.000001")),
        peak_market_cap_sol=(
            None if not priced else max(cap for _, cap in priced if cap is not None)
            .quantize(Decimal("0.0001"))
        ),
        last_market_cap_sol=None if not priced else priced[-1][1].quantize(Decimal("0.0001")),  # type: ignore[union-attr]
        outcomes=tuple(outcomes),
        data_completeness={
            "history_complete": history_complete,
            "verified_swaps": len(tape),
            "unreconciled_swaps": sum(
                1 for a in tape if a.reconciliation is not Reconciliation.MATCHED
            ),
            "amm_trades_decoded": amm_decoded,
        },
    )


def assumption_hash(material: Mapping[str, object]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "LAMPORTS_PER_SOL",
    "PUMP_FUN_TOTAL_SUPPLY_RAW",
    "REGISTRY_HORIZONS",
    "REGISTRY_VERSION",
    "THRESHOLDS",
    "WALLET_ACTIVITY_VERSION",
    "ActivityKind",
    "CurveState",
    "HorizonOutcome",
    "OutcomeClass",
    "Reconciliation",
    "RegistryRecord",
    "OnChainWalletEvent",
    "assumption_hash",
    "build_registry_record",
    "curve_state_before",
    "decode_event",
    "deduplicate",
    "encode_event",
]
