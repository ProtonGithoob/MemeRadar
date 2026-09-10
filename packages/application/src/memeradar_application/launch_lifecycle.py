"""Provider-neutral launch lifecycle and post-graduation route evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain import (
    Chain,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import bounded_decimal, ensure_utc, require_text


class LaunchLifecycleState(str, Enum):
    UNKNOWN = "UNKNOWN"
    CREATED = "CREATED"
    BONDING = "BONDING"
    GRADUATING = "GRADUATING"
    DEX_LIVE = "DEX_LIVE"
    # Compatibility alias for the earlier local checkpoint vocabulary.
    GRADUATED = "GRADUATING"


class RouteState(str, Enum):
    BONDING_ROUTE = "BONDING_ROUTE"
    DEX_ROUTE = "DEX_ROUTE"
    NO_ROUTE = "NO_ROUTE"
    UNKNOWN = "UNKNOWN"
    # Compatibility aliases for the earlier local checkpoint vocabulary.
    BONDING = "BONDING_ROUTE"
    FOUND = "DEX_ROUTE"


@dataclass(frozen=True, slots=True)
class LaunchLifecyclePolicy:
    evidence_ttl: timedelta = timedelta(minutes=5)
    version: str = "launch-lifecycle-v2"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class LaunchLifecycleEvidence:
    """A bounded, replayable lifecycle and route projection for one token."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    lifecycle_state: LaunchLifecycleState | str
    route_state: RouteState | str
    launchpad: str | None = None
    creator_address: str | None = None
    bonding_curve_progress_bps: int | None = None
    quote_asset: str | None = None
    graduation_threshold_bps: int | None = None
    graduated_at: datetime | None = None
    first_verified_dex_liquidity_at: datetime | None = None
    first_verified_swap_at: datetime | None = None
    liquidity_lock_state: str | None = None
    pool_address: str | None = None
    venue: str | None = None
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    confidence: Decimal = Decimal("0")
    config_hash: str = "launch-lifecycle-v2"
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "launch-lifecycle-v2"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        lifecycle = LaunchLifecycleState(self.lifecycle_state)
        route = RouteState(self.route_state)
        if lifecycle is LaunchLifecycleState.BONDING and route is RouteState.NO_ROUTE:
            raise ValueError("bonding lifecycle cannot have a NO_ROUTE state")
        object.__setattr__(self, "lifecycle_state", lifecycle)
        object.__setattr__(self, "route_state", route)
        for field_name in (
            "graduated_at",
            "first_verified_dex_liquidity_at",
            "first_verified_swap_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.creator_address is not None:
            object.__setattr__(
                self,
                "creator_address",
                require_chain_address(self.creator_address, self.token.chain, "creator_address"),
            )
        if self.pool_address is not None:
            object.__setattr__(
                self,
                "pool_address",
                require_chain_address(self.pool_address, self.token.chain, "pool_address"),
            )
        for field_name in ("launchpad", "quote_asset", "liquidity_lock_state", "venue"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self, field_name, require_text(value, field_name, max_length=128)
                )
        for field_name in ("bonding_curve_progress_bps", "graduation_threshold_bps"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000
            ):
                raise ValueError(f"{field_name} must be between 0 and 10000")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(require_text(value, "evidence_ref") for value in self.evidence_refs),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                value if isinstance(value, ReasonCode) else ReasonCode(str(value))
                for value in self.reason_codes
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def route_available(self) -> bool | None:
        if self.route_state is RouteState.DEX_ROUTE:
            return True
        if self.route_state is RouteState.NO_ROUTE:
            return False
        return None

    def as_mapping(self) -> Mapping[str, object]:
        return {
            "lifecycle_state": LaunchLifecycleState(self.lifecycle_state).value,
            "route_state": RouteState(self.route_state).value,
            "route_available": self.route_available,
            "launchpad": self.launchpad,
            "creator_address": self.creator_address,
            "bonding_curve_progress_bps": self.bonding_curve_progress_bps,
            "quote_asset": self.quote_asset,
            "graduation_threshold_bps": self.graduation_threshold_bps,
            "graduated_at": (
                None if self.graduated_at is None else self.graduated_at.isoformat()
            ),
            "first_verified_dex_liquidity_at": (
                None
                if self.first_verified_dex_liquidity_at is None
                else self.first_verified_dex_liquidity_at.isoformat()
            ),
            "first_verified_swap_at": (
                None
                if self.first_verified_swap_at is None
                else self.first_verified_swap_at.isoformat()
            ),
            "liquidity_lock_state": self.liquidity_lock_state,
            "pool_address": self.pool_address,
            "venue": self.venue,
            "as_of": self.as_of.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "quality_state": self.quality_state.value,
            "confidence": self.confidence,
            "config_hash": self.config_hash,
            "version": self.version,
            "evidence_refs": self.evidence_refs,
            "reason_codes": tuple(reason.code for reason in self.reason_codes),
            "provenance": tuple(
                {
                    "provider": item.provider,
                    "source_id": item.source_id,
                    "observed_at": item.observed_at.isoformat(),
                    "parser_version": item.parser_version,
                }
                for item in self.provenance
            ),
        }


# The first local checkpoint exposed this name; keep it as a read-only alias.
LaunchLifecycleSnapshot = LaunchLifecycleEvidence

_LIFECYCLE_KINDS = frozenset({"chain.launchpad", "protocol.lifecycle"})
_ROUTE_KINDS = frozenset(
    {"market.snapshot", "market.pair", "market.quote", "protocol.lifecycle", "chain.launchpad"}
)
_CREATED_EVENTS = frozenset({"created", "launch", "token_created", "launchpad_launch"})
_BONDING_EVENTS = frozenset(
    {"bonding", "bonding_curve", "bonding_curve_progress", "bonding_started"}
)
_GRADUATING_EVENTS = frozenset(
    {
        "graduation",
        "graduated",
        "graduating",
        "graduation_started",
        "graduation_threshold_reached",
        "launchpad_graduation",
        "migration",
    }
)
_DEX_EVENTS = frozenset(
    {
        "dex_live",
        "first_liquidity",
        "first_verified_liquidity",
        "first_verified_swap",
        "pool_created",
        "route_found",
    }
)
_QUALITY_ORDER = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


def _event_at(observation: Observation) -> datetime:
    return ensure_utc(observation.occurred_at or observation.observed_at, "event_at")


def _token_matches(observation: Observation, token: TokenIdentity) -> bool:
    payload = observation.normalized_payload
    raw_chain = payload.get("chain")
    if raw_chain is not None:
        try:
            if normalize_chain(str(raw_chain)) is not token.chain:
                return False
        except ValueError:
            return False
    raw_address = next(
        (
            payload.get(key)
            for key in ("token_address", "mint_address", "token", "asset_address")
            if payload.get(key) is not None
        ),
        None,
    )
    if raw_address is not None:
        return str(raw_address).lower() == token.mint_address.lower()
    return observation.token_id == token.id


def _lifecycle_signal(payload: Mapping[str, object]) -> LaunchLifecycleState | None:
    raw_state = payload.get("lifecycle_state")
    if raw_state is not None:
        state = str(raw_state).upper()
        if state == "GRADUATED":
            state = LaunchLifecycleState.GRADUATING.value
        try:
            return LaunchLifecycleState(state)
        except ValueError:
            return None
    raw_event = payload.get("event_type")
    if raw_event is None:
        return None
    event = str(raw_event).strip().lower()
    if event in _CREATED_EVENTS:
        return LaunchLifecycleState.CREATED
    if event in _BONDING_EVENTS:
        return LaunchLifecycleState.BONDING
    if event in _GRADUATING_EVENTS:
        return LaunchLifecycleState.GRADUATING
    if event in _DEX_EVENTS:
        return LaunchLifecycleState.DEX_LIVE
    return None


def _bounded_bps(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} was invalid")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} was invalid") from exc
    if not 0 <= parsed <= 10_000:
        raise ValueError(f"{key} was invalid")
    return parsed


def _is_verified_route(payload: Mapping[str, object], provider: str) -> bool:
    return (
        payload.get("route_verified") is True
        or payload.get("adapter_verified") is True
        or payload.get("verified_adapter") is True
        or payload.get("rpc_reconciled") is True
        and (payload.get("authoritative") is True or provider.startswith("evm-public-rpc:"))
    )


def _route_signal(
    payload: Mapping[str, object],
    lifecycle: LaunchLifecycleState | None,
    chain: Chain | str,
    *,
    provider: str,
) -> tuple[RouteState | None, str | None, str | None, int | None, bool]:
    progress = _bounded_bps(payload, "bonding_curve_progress_bps")
    raw_pool = next(
        (
            payload.get(key)
            for key in ("pool_address", "pool", "pair_address")
            if payload.get(key) is not None
        ),
        None,
    )
    pool = None if raw_pool is None else require_chain_address(str(raw_pool), chain, "pool_address")
    venue_raw = payload.get("venue", payload.get("dex_id"))
    venue = None if venue_raw is None else require_text(str(venue_raw), "venue", max_length=128)
    raw_route = payload.get("route_state")
    route_value = None if raw_route is None else str(raw_route).upper()
    if route_value is not None:
        route_value = {
            "BONDING": RouteState.BONDING_ROUTE.value,
            "FOUND": RouteState.DEX_ROUTE.value,
        }.get(route_value, route_value)
    coverage = str(payload.get("coverage_state", "")).upper()
    discovery_complete = payload.get("route_discovery_complete") is True
    verified = _is_verified_route(payload, provider)
    if lifecycle is LaunchLifecycleState.BONDING:
        return RouteState.BONDING_ROUTE, pool, venue, progress, verified
    if pool is not None and verified and (
        route_value == RouteState.DEX_ROUTE.value
        or coverage == "FOUND"
        or lifecycle in {LaunchLifecycleState.GRADUATING, LaunchLifecycleState.DEX_LIVE}
    ):
        return RouteState.DEX_ROUTE, pool, venue, progress, True
    if route_value == RouteState.NO_ROUTE.value and discovery_complete and verified:
        return RouteState.NO_ROUTE, None, venue, progress, verified
    if route_value is not None or coverage:
        return RouteState.UNKNOWN, None, venue, progress, verified
    return None, pool, venue, progress, verified


def _canonical_key(observation: Observation) -> tuple[str, str, str]:
    payload = observation.normalized_payload
    identity = next(
        (
            str(payload[key])
            for key in ("canonical_event_id", "tx_hash", "signature", "event_id")
            if payload.get(key) is not None
        ),
        observation.provenance.source_id,
    )
    event_type = str(payload.get("event_type", payload.get("lifecycle_state", ""))).lower()
    return (str(payload.get("chain", "")), identity.lower(), event_type)


def _collapse(
    rows: Sequence[tuple[Observation, object]],
) -> tuple[tuple[tuple[Observation, object], ...], bool, bool]:
    groups: dict[tuple[str, str, str], list[tuple[Observation, object]]] = defaultdict(list)
    for row in rows:
        groups[_canonical_key(row[0])].append(row)
    representatives: list[tuple[Observation, object]] = []
    conflict = False
    deduped = False
    for group in groups.values():
        if len({repr(row[1]) for row in group}) > 1:
            conflict = True
        representative = min(
            group,
            key=lambda row: (
                _QUALITY_ORDER[row[0].quality_state],
                -_event_at(row[0]).timestamp(),
                row[0].provenance.source_id,
            ),
        )
        representatives.append(representative)
        deduped = deduped or len(group) > 1
    return tuple(representatives), conflict, deduped


def _quality(observations: Sequence[Observation]) -> QualityState:
    if not observations:
        return QualityState.UNKNOWN
    return max((item.quality_state for item in observations), key=_QUALITY_ORDER.__getitem__)


def _latest_value(
    observations: Sequence[Observation], keys: Sequence[str]
) -> object | None:
    for observation in sorted(observations, key=_event_at, reverse=True):
        for key in keys:
            value = observation.normalized_payload.get(key)
            if value is not None:
                return value
    return None


def _first_event_time(
    observations: Sequence[Observation], event_names: frozenset[str], *, verified_only: bool = False
) -> datetime | None:
    values: list[datetime] = []
    for observation in observations:
        event = str(observation.normalized_payload.get("event_type", "")).lower()
        if event not in event_names:
            continue
        if verified_only and not (
            observation.normalized_payload.get("route_verified") is True
            or observation.normalized_payload.get("adapter_verified") is True
            or observation.normalized_payload.get("rpc_reconciled") is True
        ):
            continue
        values.append(_event_at(observation))
    return min(values) if values else None


class GraduationAwareRouteAnalyzer:
    """Combine lifecycle observations with explicit, verified route evidence."""

    def __init__(self, policy: LaunchLifecyclePolicy | None = None) -> None:
        self.policy = policy or LaunchLifecyclePolicy()

    def snapshot(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
    ) -> LaunchLifecycleEvidence:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config = require_text(config_hash, "config_hash")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")

        matched: list[Observation] = []
        invalid = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if observation.kind not in _LIFECYCLE_KINDS and observation.kind not in _ROUTE_KINDS:
                continue
            if not _token_matches(observation, token):
                continue
            if observation.observed_at > checked_at or _event_at(observation) > checked_at:
                continue
            matched.append(observation)

        lifecycle_rows: list[tuple[Observation, object]] = []
        route_rows: list[tuple[Observation, object]] = []
        route_details: dict[str, tuple[str | None, str | None, int | None]] = {}
        for observation in matched:
            try:
                row_lifecycle = _lifecycle_signal(observation.normalized_payload)
                row_route, row_pool, row_venue, row_progress, _ = _route_signal(
                    observation.normalized_payload,
                    row_lifecycle,
                    token.chain,
                    provider=observation.provenance.provider,
                )
            except (TypeError, ValueError, OverflowError):
                invalid = True
                continue
            if row_lifecycle is not None:
                lifecycle_rows.append((observation, row_lifecycle))
            if row_route is not None:
                route_rows.append((observation, row_route))
                route_details[observation.provenance.source_id] = (
                    row_pool,
                    row_venue,
                    row_progress,
                )

        collapsed_lifecycle_rows, lifecycle_conflict, lifecycle_deduped = _collapse(
            lifecycle_rows
        )
        collapsed_route_rows, route_conflict, route_deduped = _collapse(route_rows)
        selected: list[Observation] = []
        reasons: list[ReasonCode] = []
        lifecycle = LaunchLifecycleState.UNKNOWN
        if collapsed_lifecycle_rows:
            latest_at = max(_event_at(row[0]) for row in collapsed_lifecycle_rows)
            latest_lifecycle = [
                row for row in collapsed_lifecycle_rows if _event_at(row[0]) == latest_at
            ]
            lifecycle_values = {row[1] for row in latest_lifecycle}
            selected.extend(row[0] for row in latest_lifecycle)
            lifecycle_latest_conflict = len(lifecycle_values) > 1
            if not lifecycle_latest_conflict:
                lifecycle = LaunchLifecycleState(next(iter(lifecycle_values)))
        else:
            lifecycle_latest_conflict = False

        route = RouteState.UNKNOWN
        pool: str | None = None
        venue: str | None = None
        progress: int | None = None
        if collapsed_route_rows:
            latest_at = max(_event_at(row[0]) for row in collapsed_route_rows)
            latest_route = [
                row for row in collapsed_route_rows if _event_at(row[0]) == latest_at
            ]
            route_values = {row[1] for row in latest_route}
            selected.extend(row[0] for row in latest_route)
            route_latest_conflict = len(route_values) > 1
            if not route_latest_conflict:
                route = RouteState(next(iter(route_values)))
                details = route_details.get(latest_route[-1][0].provenance.source_id)
                if details is not None:
                    pool, venue, progress = details
        else:
            route_latest_conflict = False

        if lifecycle is LaunchLifecycleState.BONDING:
            route = RouteState.BONDING_ROUTE
            reasons.append(ReasonCode("BONDING_ROUTE_NOT_NO_ROUTE"))
        elif lifecycle is LaunchLifecycleState.GRADUATING and route is RouteState.BONDING_ROUTE:
            route = RouteState.UNKNOWN
        elif route is RouteState.DEX_ROUTE:
            lifecycle = LaunchLifecycleState.DEX_LIVE

        if (
            lifecycle_conflict
            or lifecycle_latest_conflict
            or route_conflict
            or route_latest_conflict
        ):
            reasons.append(ReasonCode("PROVIDER_DISAGREEMENT"))
        if lifecycle_deduped or route_deduped:
            reasons.append(ReasonCode("DUPLICATE_CANONICAL_EVENT_DEDUPED"))
        if invalid:
            reasons.append(ReasonCode("ROUTE_EVIDENCE_INVALID"))
        if not matched:
            reasons.append(ReasonCode("LAUNCH_LIFECYCLE_EVIDENCE_MISSING"))
        elif lifecycle is LaunchLifecycleState.GRADUATING and route is RouteState.UNKNOWN:
            reasons.append(ReasonCode("ROUTE_DISCOVERY_INCOMPLETE"))
        elif route is RouteState.DEX_ROUTE:
            reasons.append(ReasonCode("GRADUATION_ROUTE_FOUND"))
        elif route is RouteState.NO_ROUTE:
            reasons.append(ReasonCode("ROUTE_DISCOVERY_COMPLETE_NO_ROUTE"))

        unique_selected: list[Observation] = []
        selected_keys: set[tuple[str, str]] = set()
        for item in sorted(
            selected, key=lambda value: (_event_at(value), value.provenance.source_id)
        ):
            key = (item.provenance.provider, item.provenance.source_id)
            if key not in selected_keys:
                selected_keys.add(key)
                unique_selected.append(item)
        selected_tuple = tuple(unique_selected)
        supporting_values: list[Observation] = []
        supporting_keys: set[tuple[str, str]] = set()
        for item in sorted(
            (row[0] for row in (*collapsed_lifecycle_rows, *collapsed_route_rows)),
            key=lambda value: (_event_at(value), value.provenance.source_id),
        ):
            key = (item.provenance.provider, item.provenance.source_id)
            if key not in supporting_keys:
                supporting_keys.add(key)
                supporting_values.append(item)
        supporting_tuple = tuple(supporting_values or matched)
        quality = _quality(selected_tuple)
        if "PROVIDER_DISAGREEMENT" in {reason.code for reason in reasons}:
            quality = QualityState.CONFLICTED
            lifecycle = LaunchLifecycleState.UNKNOWN
            route = RouteState.UNKNOWN
            pool = None
            venue = None
            progress = None
        elif invalid:
            quality = QualityState.INVALID
        elif selected_tuple and quality is QualityState.FRESH:
            latest_selected = max(_event_at(item) for item in selected_tuple)
            if checked_at >= latest_selected + self.policy.evidence_ttl:
                quality = QualityState.STALE

        as_of = max((_event_at(item) for item in selected_tuple), default=checked_at)
        creator_value = _latest_value(matched, ("creator_address", "creator"))
        pool_value = pool
        if pool_value is None and route is RouteState.DEX_ROUTE:
            pool_raw = _latest_value(matched, ("pool_address", "pool", "pair_address"))
            pool_value = None if pool_raw is None else str(pool_raw)
        if venue is None and route is RouteState.DEX_ROUTE:
            venue_raw = _latest_value(matched, ("venue", "dex_id"))
            venue = None if venue_raw is None else str(venue_raw)
        lock_value = _latest_value(
            matched, ("liquidity_lock_state", "lock_state", "permanent_liquidity")
        )
        if isinstance(lock_value, bool):
            lock_value = "PERMANENT" if lock_value else "NOT_PERMANENT"

        return LaunchLifecycleEvidence(
            token=token,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            lifecycle_state=lifecycle,
            route_state=route,
            launchpad=(
                None
                if (launchpad := _latest_value(matched, ("launchpad", "protocol"))) is None
                else str(launchpad)
            ),
            creator_address=None if creator_value is None else str(creator_value),
            bonding_curve_progress_bps=(
                progress
                if progress is not None
                else _bounded_bps(
                    {"bonding_curve_progress_bps": _latest_value(
                        matched, ("bonding_curve_progress_bps",)
                    )},
                    "bonding_curve_progress_bps",
                )
            ),
            quote_asset=(
                None
                if (quote := _latest_value(matched, ("quote_asset", "quote_mint", "quote"))) is None
                else str(quote)
            ),
            graduation_threshold_bps=(
                None
                if (threshold := _latest_value(
                    matched, ("graduation_threshold_bps", "graduation_threshold")
                )) is None
                else _bounded_bps(
                    {"graduation_threshold_bps": threshold}, "graduation_threshold_bps"
                )
            ),
            graduated_at=_first_event_time(matched, _GRADUATING_EVENTS),
            first_verified_dex_liquidity_at=_first_event_time(
                matched,
                frozenset({"first_liquidity", "first_verified_liquidity", "pool_created"}),
                verified_only=True,
            ),
            first_verified_swap_at=_first_event_time(
                matched, frozenset({"first_verified_swap"}), verified_only=True
            ),
            liquidity_lock_state=None if lock_value is None else str(lock_value),
            pool_address=pool_value,
            venue=venue,
            provenance=tuple(item.provenance for item in supporting_tuple),
            evidence_refs=tuple(item.provenance.source_id for item in supporting_tuple),
            reason_codes=tuple(dict.fromkeys(reasons)),
            confidence=Decimal("1") if quality is QualityState.FRESH else Decimal("0"),
            config_hash=normalized_config,
            quality_state=quality,
            version=self.policy.version,
        )


__all__ = [
    "GraduationAwareRouteAnalyzer",
    "LaunchLifecycleEvidence",
    "LaunchLifecyclePolicy",
    "LaunchLifecycleSnapshot",
    "LaunchLifecycleState",
    "RouteState",
]
