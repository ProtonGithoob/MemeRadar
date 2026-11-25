"""Reverse wallet intelligence, part 2: point-in-time profiles and categories.

Leakage rule (goal M3): a profile ``as_of`` T uses only events with
``block_time <= T`` and only token outcomes whose horizon closed by T.  A
wallet that bought a token which later went 100x is not "successful" until
that outcome was observable.

Cost basis: lots received by transfer or inside an undecoded venue carry an
UNKNOWN cost; selling them produces UNKNOWN PnL, never zero.  Quote amounts
come from verified trade events; fees are an explicit assumption
(``fee_bps``), recorded in the profile.

Categories are heuristic, evidence-listing classifications, not proof.
Manipulation-related categories are risk evidence only: a wallet carrying any
of them can never be an ``EARLY_SMART_MONEY_CANDIDATE`` and must not seed a
copy or entry signal.  Shared funding or synchronized buying never asserts
common ownership.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from statistics import median

from memeradar_domain.common import ensure_utc

from .onchain_wallet_events import (
    LAMPORTS_PER_SOL,
    PUMP_FUN_TOTAL_SUPPLY_RAW,
    ActivityKind,
    OnChainWalletEvent,
    OutcomeClass,
    Reconciliation,
    RegistryRecord,
    deduplicate,
)

WALLET_PROFILE_VERSION = "wallet-profile-v1"
_EXTREME = {OutcomeClass.X10, OutcomeClass.X20, OutcomeClass.X50, OutcomeClass.X100}
_AT_LEAST_5X = _EXTREME | {OutcomeClass.X5}


class WalletCategory(str, Enum):
    EARLY_SMART_MONEY_CANDIDATE = "EARLY_SMART_MONEY_CANDIDATE"
    MOMENTUM_TRADER = "MOMENTUM_TRADER"
    CREATOR_LINKED = "CREATOR_LINKED"
    POTENTIAL_INSIDER = "POTENTIAL_INSIDER"
    POTENTIAL_WASH_TRADER = "POTENTIAL_WASH_TRADER"
    POTENTIAL_MANIPULATION_CLUSTER = "POTENTIAL_MANIPULATION_CLUSTER"
    MARKET_MAKER = "MARKET_MAKER"
    LOW_EVIDENCE = "LOW_EVIDENCE"
    UNKNOWN = "UNKNOWN"


RISK_CATEGORIES = frozenset(
    {
        WalletCategory.CREATOR_LINKED,
        WalletCategory.POTENTIAL_INSIDER,
        WalletCategory.POTENTIAL_WASH_TRADER,
        WalletCategory.POTENTIAL_MANIPULATION_CLUSTER,
    }
)


@dataclass(frozen=True, slots=True)
class ProfilePolicy:
    """Versioned hypotheses, not calibrated parameters."""

    outcome_horizon: str = "24h"
    fee_bps: int = 125  # assumption: Pump.fun protocol+creator fee per side
    min_observable_tokens: int = 3
    early_entry_max_multiple_of_initial: Decimal = Decimal("3")
    momentum_min_multiple_of_initial: Decimal = Decimal("5")
    insider_max_slots_after_create: int = 2
    wash_max_round_trip_seconds: int = 60
    wash_min_round_trips: int = 3
    market_maker_min_trades: int = 50
    market_maker_min_tokens: int = 10
    smart_min_win_rate: Decimal = Decimal("0.5")
    smart_min_early_5x_tokens: int = 2
    version: str = WALLET_PROFILE_VERSION


@dataclass(frozen=True, slots=True)
class WalletProfile:
    wallet: str
    as_of: datetime
    tokens_traded: int
    verified_trades: int
    observable_outcome_tokens: int
    realized_pnl_sol: Decimal  # known-cost portion only, net of assumed fees
    realized_unknown_events: int  # sells or exits whose cost basis is UNKNOWN
    unrealized_pnl_sol: Decimal | None  # mark at latest curve state <= as_of
    closed_positions: int
    win_rate: Decimal | None
    extreme_participation: Decimal | None  # of observable tokens, share >= 10x
    early_5x_tokens: int  # observable >=5x tokens entered early
    failed_token_exposure: Decimal | None  # of observable tokens, share NO_MOVE
    median_entry_multiple_of_initial: Decimal | None
    median_entry_delay_seconds: float | None
    median_holding_seconds: float | None
    reconciliation_completeness: Decimal | None
    categories: tuple[WalletCategory, ...]
    evidence: tuple[str, ...]
    policy_version: str = WALLET_PROFILE_VERSION

    @property
    def risk_only(self) -> bool:
        return any(category in RISK_CATEGORIES for category in self.categories)

    def to_payload(self) -> dict[str, object]:
        def text(value: object) -> object:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, tuple):
                return [text(v) for v in value]
            if isinstance(value, Enum):
                return value.value
            return value

        payload = {key: text(getattr(self, key)) for key in self.__slots__}
        payload["risk_only"] = self.risk_only
        payload["semantics"] = "HEURISTIC_CLASSIFICATION_NOT_CALIBRATED"
        return payload


@dataclass(slots=True)
class _Lot:
    tokens: int
    cost_lamports: int | None  # None = UNKNOWN basis
    opened_at: datetime


@dataclass(slots=True)
class _Position:
    lots: list[_Lot] = field(default_factory=list)
    realized_lamports: int = 0
    unknown_exits: int = 0
    first_buy_at: datetime | None = None
    first_buy_reference: Decimal | None = None
    closed_at: datetime | None = None
    had_known_sell: bool = False


def _consume(position: _Position, tokens: int) -> tuple[int | None, int]:
    """Remove ``tokens`` FIFO; return (known cost removed or None, tokens left)."""

    remaining = tokens
    known_cost = 0
    unknown = False
    while remaining > 0 and position.lots:
        lot = position.lots[0]
        take = min(lot.tokens, remaining)
        if lot.cost_lamports is None:
            unknown = True
        else:
            known_cost += lot.cost_lamports * take // lot.tokens
            lot.cost_lamports -= lot.cost_lamports * take // lot.tokens
        lot.tokens -= take
        remaining -= take
        if lot.tokens == 0:
            position.lots.pop(0)
    if remaining > 0:
        unknown = True  # sold more than we saw acquired: basis unknown
    return (None if unknown else known_cost), remaining


def _outcome_at(
    record: RegistryRecord | None, horizon: str, as_of: datetime
) -> OutcomeClass | None:
    """The outcome class only if it was observable at ``as_of``."""

    if record is None:
        return None
    for outcome in record.outcomes:
        if outcome.horizon == horizon:
            if outcome.horizon_end > as_of or outcome.outcome in {
                OutcomeClass.PENDING,
                OutcomeClass.CENSORED,
            }:
                return None
            return outcome.outcome
    return None


def build_profiles(
    events: Iterable[OnChainWalletEvent],
    registry: Mapping[str, RegistryRecord],
    *,
    as_of: datetime,
    policy: ProfilePolicy | None = None,
    cluster_members: Mapping[str, str] | None = None,
) -> dict[str, WalletProfile]:
    active = policy or ProfilePolicy()
    cutoff = ensure_utc(as_of, "as_of")
    visible = [e for e in deduplicate(events) if e.block_time <= cutoff]
    latest_reference: dict[str, Decimal] = {}
    create_slot: dict[str, int] = {}
    creators: dict[str, str] = {}
    for event in visible:
        if event.kind is ActivityKind.CREATE:
            create_slot[event.mint] = event.slot
            creators[event.mint] = event.wallet
        reference = event.reference_price
        if reference is not None:
            latest_reference[event.mint] = reference
    for mint, registered in registry.items():
        if registered.creator and mint not in creators and registered.launch_at <= cutoff:
            creators[mint] = registered.creator

    positions: dict[str, dict[str, _Position]] = defaultdict(lambda: defaultdict(_Position))
    per_wallet_swaps: dict[str, list[OnChainWalletEvent]] = defaultdict(list)
    for event in visible:
        if event.kind in {ActivityKind.CREATE, ActivityKind.FAILED,
                          ActivityKind.LIQUIDITY_MIGRATION}:
            continue
        position = positions[event.wallet][event.mint]
        if event.kind is ActivityKind.SWAP_BUY:
            per_wallet_swaps[event.wallet].append(event)
            paid = -(event.quote_delta_lamports or 0)
            cost = paid * (10_000 + active.fee_bps) // 10_000
            position.lots.append(_Lot(event.token_delta_raw, cost, event.block_time))
            if position.first_buy_at is None:
                position.first_buy_at = event.block_time
                position.first_buy_reference = event.reference_price
        elif event.kind is ActivityKind.SWAP_SELL:
            per_wallet_swaps[event.wallet].append(event)
            received = (event.quote_delta_lamports or 0) * (10_000 - active.fee_bps) // 10_000
            known_cost, _ = _consume(position, -event.token_delta_raw)
            if known_cost is None:
                position.unknown_exits += 1
            else:
                position.realized_lamports += received - known_cost
                position.had_known_sell = True
            if not position.lots:
                position.closed_at = event.block_time
        elif event.token_delta_raw > 0:  # TRANSFER_IN / UNVERIFIED_VENUE inflow
            position.lots.append(_Lot(event.token_delta_raw, None, event.block_time))
        elif event.token_delta_raw < 0:  # outflow without proceeds
            _consume(position, -event.token_delta_raw)
            position.unknown_exits += 1
            if not position.lots:
                position.closed_at = event.block_time

    profiles: dict[str, WalletProfile] = {}
    clusters = dict(cluster_members or {})
    for wallet, by_mint in positions.items():
        swaps = per_wallet_swaps.get(wallet, [])
        if not swaps:
            continue
        realized = sum(p.realized_lamports for p in by_mint.values())
        unknown_exits = sum(p.unknown_exits for p in by_mint.values())
        unrealized = 0
        unrealized_known = True
        for mint, position in by_mint.items():
            price = latest_reference.get(mint)
            for lot in position.lots:
                if lot.cost_lamports is None or price is None:
                    unrealized_known = False
                    continue
                value = int(Decimal(lot.tokens) * price) * (10_000 - active.fee_bps) // 10_000
                unrealized += value - lot.cost_lamports
        closed = [
            p for p in by_mint.values()
            if p.closed_at is not None and p.had_known_sell and p.unknown_exits == 0
        ]
        wins = sum(1 for p in closed if p.realized_lamports > 0)
        observable: dict[str, OutcomeClass] = {}
        early_5x = 0
        entry_multiples: list[Decimal] = []
        entry_delays: list[float] = []
        holds: list[float] = []
        for mint, position in by_mint.items():
            record = registry.get(mint)
            if position.first_buy_at is None:
                continue
            entry_multiple: Decimal | None = None
            reference = position.first_buy_reference
            if record is not None and record.initial_market_cap_sol and reference:
                entry_cap = reference * PUMP_FUN_TOTAL_SUPPLY_RAW / LAMPORTS_PER_SOL
                entry_multiple = (entry_cap / record.initial_market_cap_sol).quantize(
                    Decimal("0.01")
                )
                entry_multiples.append(entry_multiple)
            if record is not None:
                entry_delays.append((position.first_buy_at - record.launch_at).total_seconds())
            if position.closed_at is not None:
                holds.append((position.closed_at - position.first_buy_at).total_seconds())
            outcome = _outcome_at(record, active.outcome_horizon, cutoff)
            if outcome is not None:
                observable[mint] = outcome
                early = (
                    entry_multiple is not None
                    and entry_multiple <= active.early_entry_max_multiple_of_initial
                )
                if outcome in _AT_LEAST_5X and early:
                    early_5x += 1
        matched = sum(1 for e in swaps if e.reconciliation is Reconciliation.MATCHED)
        categories, evidence = _categorize(
            wallet,
            swaps=swaps,
            by_mint=by_mint,
            creators=creators,
            create_slot=create_slot,
            observable=observable,
            early_5x=early_5x,
            win_rate=(Decimal(wins) / Decimal(len(closed))) if closed else None,
            realized=realized,
            entry_multiples=entry_multiples,
            holds=holds,
            in_cluster=clusters.get(wallet),
            policy=active,
        )
        profiles[wallet] = WalletProfile(
            wallet=wallet,
            as_of=cutoff,
            tokens_traded=sum(1 for p in by_mint.values() if p.first_buy_at is not None),
            verified_trades=len(swaps),
            observable_outcome_tokens=len(observable),
            realized_pnl_sol=(Decimal(realized) / LAMPORTS_PER_SOL).quantize(Decimal("0.000001")),
            realized_unknown_events=unknown_exits,
            unrealized_pnl_sol=(
                (Decimal(unrealized) / LAMPORTS_PER_SOL).quantize(Decimal("0.000001"))
                if unrealized_known else None
            ),
            closed_positions=len(closed),
            win_rate=(
                (Decimal(wins) / Decimal(len(closed))).quantize(Decimal("0.0001"))
                if closed else None
            ),
            extreme_participation=_share(observable, _EXTREME),
            early_5x_tokens=early_5x,
            failed_token_exposure=_share(observable, {OutcomeClass.NO_MOVE}),
            median_entry_multiple_of_initial=(
                Decimal(str(median(entry_multiples))) if entry_multiples else None
            ),
            median_entry_delay_seconds=median(entry_delays) if entry_delays else None,
            median_holding_seconds=median(holds) if holds else None,
            reconciliation_completeness=(
                (Decimal(matched) / Decimal(len(swaps))).quantize(Decimal("0.0001"))
            ),
            categories=categories,
            evidence=evidence,
            policy_version=active.version,
        )
    return profiles


def _share(observable: Mapping[str, OutcomeClass], classes: set[OutcomeClass]) -> Decimal | None:
    if not observable:
        return None
    hits = sum(1 for value in observable.values() if value in classes)
    return (Decimal(hits) / Decimal(len(observable))).quantize(Decimal("0.0001"))


def _categorize(
    wallet: str,
    *,
    swaps: Sequence[OnChainWalletEvent],
    by_mint: Mapping[str, _Position],
    creators: Mapping[str, str],
    create_slot: Mapping[str, int],
    observable: Mapping[str, OutcomeClass],
    early_5x: int,
    win_rate: Decimal | None,
    realized: int,
    entry_multiples: Sequence[Decimal],
    holds: Sequence[float],
    in_cluster: str | None,
    policy: ProfilePolicy,
) -> tuple[tuple[WalletCategory, ...], tuple[str, ...]]:
    categories: list[WalletCategory] = []
    evidence: list[str] = []
    created = sorted(mint for mint, creator in creators.items() if creator == wallet)
    traded_created = [mint for mint in created if mint in by_mint]
    if traded_created:
        categories.append(WalletCategory.CREATOR_LINKED)
        evidence.append(f"traded own launches: {len(traded_created)}")
    near_create = sorted(
        {
            e.mint
            for e in swaps
            if e.kind is ActivityKind.SWAP_BUY
            and e.mint in create_slot
            and creators.get(e.mint) != wallet
            and e.slot - create_slot[e.mint] <= policy.insider_max_slots_after_create
        }
    )
    if len(near_create) >= 2:
        categories.append(WalletCategory.POTENTIAL_INSIDER)
        evidence.append(
            f"bought within {policy.insider_max_slots_after_create} slots of create "
            f"on {len(near_create)} tokens (bundle/sniper footprint; not proof)"
        )
    round_trips_by_mint: dict[str, int] = defaultdict(int)
    by_mint_swaps: dict[str, list[OnChainWalletEvent]] = defaultdict(list)
    for event in swaps:
        by_mint_swaps[event.mint].append(event)
    for mint, events in by_mint_swaps.items():
        last_buy: OnChainWalletEvent | None = None
        for event in events:
            if event.kind is ActivityKind.SWAP_BUY:
                last_buy = event
            elif last_buy is not None and (
                event.block_time - last_buy.block_time
            ) <= timedelta(seconds=policy.wash_max_round_trip_seconds):
                round_trips_by_mint[mint] += 1
                last_buy = None
    rapid = sum(round_trips_by_mint.values())
    if rapid >= policy.wash_min_round_trips and len(round_trips_by_mint) >= 1 and (
        len(round_trips_by_mint) >= 2 or rapid >= 2 * policy.wash_min_round_trips
    ):
        categories.append(WalletCategory.POTENTIAL_WASH_TRADER)
        evidence.append(
            f"{rapid} buy->sell round trips within {policy.wash_max_round_trip_seconds}s "
            f"across {len(round_trips_by_mint)} tokens"
        )
    if in_cluster is not None:
        categories.append(WalletCategory.POTENTIAL_MANIPULATION_CLUSTER)
        evidence.append(f"synchronized co-buying cluster {in_cluster} (not common ownership)")
    buys = sum(1 for e in swaps if e.kind is ActivityKind.SWAP_BUY)
    sells = len(swaps) - buys
    balanced = buys and sells and Decimal("0.8") <= Decimal(buys) / Decimal(sells) <= Decimal(
        "1.25"
    )
    if (
        len(swaps) >= policy.market_maker_min_trades
        and len(by_mint) >= policy.market_maker_min_tokens
        and balanced
        and holds
        and median(holds) < 120
    ):
        categories.append(WalletCategory.MARKET_MAKER)
        evidence.append(f"{len(swaps)} two-sided trades across {len(by_mint)} tokens")
    if entry_multiples and median(entry_multiples) >= policy.momentum_min_multiple_of_initial:
        categories.append(WalletCategory.MOMENTUM_TRADER)
        evidence.append(f"median entry at {median(entry_multiples)}x the first observable cap")
    risk = any(category in RISK_CATEGORIES for category in categories)
    if len(observable) < policy.min_observable_tokens:
        categories.append(WalletCategory.LOW_EVIDENCE)
        evidence.append(
            f"{len(observable)} tokens with observable {policy.outcome_horizon} outcome "
            f"< {policy.min_observable_tokens}"
        )
    elif (
        not risk
        and early_5x >= policy.smart_min_early_5x_tokens
        and win_rate is not None
        and win_rate >= policy.smart_min_win_rate
        and realized > 0
    ):
        categories.append(WalletCategory.EARLY_SMART_MONEY_CANDIDATE)
        evidence.append(
            f"{early_5x} early entries into observable >=5x tokens; win rate {win_rate}; "
            "positive known realized PnL (candidate, not validated)"
        )
    if not categories:
        categories.append(WalletCategory.UNKNOWN)
    return tuple(categories), tuple(evidence)


def co_buy_clusters(
    events: Iterable[OnChainWalletEvent],
    *,
    as_of: datetime,
    min_shared_tokens: int = 2,
    min_cluster_size: int = 3,
    exclude: Iterable[str] = (),
) -> dict[str, str]:
    """Wallets that repeatedly buy the same tokens in the same slot.

    An edge needs same-slot buys on at least ``min_shared_tokens`` different
    mints; components of at least ``min_cluster_size`` wallets are reported.
    This is coordination *evidence*; it does not establish common ownership.
    """

    cutoff = ensure_utc(as_of, "as_of")
    skip = set(exclude)
    slot_buyers: dict[tuple[str, int], set[str]] = defaultdict(set)
    for event in deduplicate(events):
        if (
            event.kind is ActivityKind.SWAP_BUY
            and event.block_time <= cutoff
            and event.wallet not in skip
        ):
            slot_buyers[(event.mint, event.slot)].add(event.wallet)
    shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (mint, _slot), wallets in slot_buyers.items():
        ordered = sorted(wallets)
        if len(ordered) > 25:  # a busy slot is not coordination evidence
            continue
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                shared[(left, right)].add(mint)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for (left, right), mints in shared.items():
        if len(mints) >= min_shared_tokens:
            adjacency[left].add(right)
            adjacency[right].add(left)
    seen: set[str] = set()
    clusters: dict[str, str] = {}
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack, component = [start], []
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            component.append(node)
            stack.extend(adjacency[node] - seen)
        if len(component) >= min_cluster_size:
            cluster_id = f"cobuy:{min(component)[:8]}:{len(component)}"
            for wallet in component:
                clusters[wallet] = cluster_id
    return clusters


def wallet_signal_features(
    profiles: Mapping[str, WalletProfile], buyers: Iterable[str]
) -> dict[str, object]:
    """Feature mapping for the existing scorer/safety path (``confluence``).

    ``raw_smart_wallet_count`` counts buyers whose *point-in-time* profile is
    an EARLY_SMART_MONEY_CANDIDATE; ``independent_smart_wallet_count`` drops
    candidates that share a co-buy cluster with another counted candidate.
    Risk-category buyers are reported separately and never counted.
    """

    return signal_features_from_categories(
        {wallet: tuple(c.value for c in p.categories) for wallet, p in profiles.items()},
        buyers,
    )


def signal_features_from_categories(
    categories_by_wallet: Mapping[str, Sequence[str]],
    buyers: Iterable[str],
    *,
    min_coverage: Decimal = Decimal("0.5"),
) -> dict[str, object]:
    """Same features from stored categories, with an explicit coverage gate.

    When fewer than ``min_coverage`` of the buyers have a profile, the counts
    are omitted (UNKNOWN) instead of reported as zero.
    """

    ordered = list(dict.fromkeys(buyers))
    risk = {c.value for c in RISK_CATEGORIES}
    profiled = [w for w in ordered if w in categories_by_wallet]
    candidates = [
        w for w in profiled
        if WalletCategory.EARLY_SMART_MONEY_CANDIDATE.value in categories_by_wallet[w]
        and not risk & set(categories_by_wallet[w])
    ]
    risk_buyers = [w for w in profiled if risk & set(categories_by_wallet[w])]
    coverage = (
        (Decimal(len(profiled)) / Decimal(len(ordered))).quantize(Decimal("0.0001"))
        if ordered else Decimal("0")
    )
    features: dict[str, object] = {
        "wallet_profile_coverage": str(coverage),
        "wallet_buyers_seen": len(ordered),
        "wallet_buyers_profiled": len(profiled),
        "risk_category_buyer_count": len(risk_buyers),
        "wallet_feature_semantics": "HEURISTIC_POINT_IN_TIME_NOT_CALIBRATED",
        "wallet_profile_version": WALLET_PROFILE_VERSION,
    }
    if ordered and coverage >= min_coverage:
        features["raw_smart_wallet_count"] = len(candidates)
        features["independent_smart_wallet_count"] = len(candidates)
    return features


__all__ = [
    "RISK_CATEGORIES",
    "WALLET_PROFILE_VERSION",
    "ProfilePolicy",
    "WalletCategory",
    "WalletProfile",
    "build_profiles",
    "co_buy_clusters",
    "signal_features_from_categories",
    "wallet_signal_features",
]
