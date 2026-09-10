"""Provider-neutral launch lifecycle and post-graduation route evidence."""

from __future__ import annotations

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
    BONDING = "BONDING"
    GRADUATED = "GRADUATED"


class RouteState(str, Enum):
    UNKNOWN = "UNKNOWN"
    BONDING = "BONDING"
    FOUND = "FOUND"
    NO_ROUTE = "NO_ROUTE"


@dataclass(frozen=True, slots=True)
class LaunchLifecyclePolicy:
    evidence_ttl: timedelta = timedelta(minutes=5)
    version: str = "launch-lifecycle-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class LaunchLifecycleSnapshot:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    lifecycle_state: LaunchLifecycleState | str
    route_state: RouteState | str
    pool_address: str | None
    venue: str | None
    bonding_curve_progress_bps: int | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "launch-lifecycle-v1"

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
        if self.pool_address is not None:
            object.__setattr__(
                self,
                "pool_address",
                require_chain_address(self.pool_address, self.token.chain, "pool_address"),
            )
        if self.venue is not None:
            object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=128))
        if self.bonding_curve_progress_bps is not None and (
            isinstance(self.bonding_curve_progress_bps, bool)
            or not isinstance(self.bonding_curve_progress_bps, int)
            or not 0 <= self.bonding_curve_progress_bps <= 10_000
        ):
            raise ValueError("bonding_curve_progress_bps must be between 0 and 10000")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(require_text(value, "evidence_ref") for value in self.evidence_refs),
        )
        reasons = tuple(
            value if isinstance(value, ReasonCode) else ReasonCode(str(value))
            for value in self.reason_codes
        )
        object.__setattr__(self, "reason_codes", reasons)
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
        if self.route_state is RouteState.FOUND:
            return True
        if self.route_state is RouteState.NO_ROUTE:
            return False
        return None

    def as_mapping(self) -> Mapping[str, object]:
        return {
            "lifecycle_state": LaunchLifecycleState(self.lifecycle_state).value,
            "route_state": RouteState(self.route_state).value,
            "route_available": self.route_available,
            "pool_address": self.pool_address,
            "venue": self.venue,
            "bonding_curve_progress_bps": self.bonding_curve_progress_bps,
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


_LIFECYCLE_KINDS = frozenset({"chain.launchpad", "protocol.lifecycle"})
_BONDING_EVENTS = frozenset(
    {
        "bonding",
        "bonding_curve",
        "bonding_curve_progress",
        "launch",
        "token_created",
        "launchpad_launch",
    }
)
_GRADUATED_EVENTS = frozenset(
    {
        "graduation",
        "graduated",
        "launchpad_graduation",
        "migration",
        "pool_created",
        "route_found",
    }
)
_ROUTE_KINDS = frozenset(
    {"market.snapshot", "market.pair", "market.quote", "protocol.lifecycle", "chain.launchpad"}
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
        try:
            return LaunchLifecycleState(str(raw_state).upper())
        except ValueError:
            return None
    raw_event = payload.get("event_type")
    if raw_event is None:
        return None
    event = str(raw_event).strip().lower()
    if event in _BONDING_EVENTS:
        return LaunchLifecycleState.BONDING
    if event in _GRADUATED_EVENTS:
        return LaunchLifecycleState.GRADUATED
    return None


def _progress(payload: Mapping[str, object]) -> int | None:
    value = payload.get("bonding_curve_progress_bps")
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            raise ValueError("bonding curve progress was invalid")
        parsed = int(str(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("bonding curve progress was invalid") from exc
    if not 0 <= parsed <= 10_000:
        raise ValueError("bonding curve progress was invalid")
    return parsed


def _route_signal(
    payload: Mapping[str, object],
    lifecycle: LaunchLifecycleState | None,
    chain: Chain | str,
) -> tuple[RouteState | None, str | None, str | None, int | None]:
    progress = _progress(payload)
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
    coverage = str(payload.get("coverage_state", "")).upper()
    discovery_complete = payload.get("route_discovery_complete") is True
    route_value = None if raw_route is None else str(raw_route).upper()
    if lifecycle is LaunchLifecycleState.BONDING:
        return RouteState.BONDING, pool, venue, progress
    if pool is not None and (
        route_value == RouteState.FOUND.value
        or coverage == "FOUND"
        or lifecycle is LaunchLifecycleState.GRADUATED
    ):
        return RouteState.FOUND, pool, venue, progress
    if (
        route_value == RouteState.NO_ROUTE.value
        and discovery_complete
    ):
        return RouteState.NO_ROUTE, None, venue, progress
    if raw_route is not None or coverage:
        return RouteState.UNKNOWN, None, venue, progress
    return None, pool, venue, progress


def _quality(observations: Sequence[Observation]) -> QualityState:
    if not observations:
        return QualityState.UNKNOWN
    return max((item.quality_state for item in observations), key=_QUALITY_ORDER.__getitem__)


class GraduationAwareRouteAnalyzer:
    """Combine launch lifecycle evidence with an explicit DEX route signal."""

    def __init__(self, policy: LaunchLifecyclePolicy | None = None) -> None:
        self.policy = policy or LaunchLifecyclePolicy()

    def snapshot(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
    ) -> LaunchLifecycleSnapshot:
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

        lifecycle_rows: list[tuple[Observation, LaunchLifecycleState]] = []
        route_rows: list[tuple[Observation, RouteState, str | None, str | None, int | None]] = []
        for observation in matched:
            try:
                lifecycle = _lifecycle_signal(observation.normalized_payload)
                row_route, route_pool, route_venue, route_progress = _route_signal(
                    observation.normalized_payload, lifecycle, token.chain
                )
            except (TypeError, ValueError, OverflowError):
                invalid = True
                continue
            if lifecycle is not None:
                lifecycle_rows.append((observation, lifecycle))
            if row_route is not None:
                route_rows.append(
                    (observation, row_route, route_pool, route_venue, route_progress)
                )

        selected: list[Observation] = []
        reasons: list[ReasonCode] = []
        lifecycle = LaunchLifecycleState.UNKNOWN
        if lifecycle_rows:
            latest_at = max(_event_at(row[0]) for row in lifecycle_rows)
            latest_lifecycle = [
                row for row in lifecycle_rows if _event_at(row[0]) == latest_at
            ]
            lifecycle_values = {row[1] for row in latest_lifecycle}
            selected.extend(row[0] for row in latest_lifecycle)
            if len(lifecycle_values) > 1:
                reasons.append(ReasonCode("PROVIDER_DISAGREEMENT"))
            else:
                lifecycle = next(iter(lifecycle_values))

        route = RouteState.UNKNOWN
        pool: str | None = None
        venue: str | None = None
        progress: int | None = None
        if route_rows:
            latest_at = max(_event_at(row[0]) for row in route_rows)
            latest_route = [row for row in route_rows if _event_at(row[0]) == latest_at]
            route_values = {row[1] for row in latest_route}
            pools = {row[2] for row in latest_route if row[2] is not None}
            selected.extend(row[0] for row in latest_route)
            if len(route_values) > 1 or len(pools) > 1:
                reasons.append(ReasonCode("PROVIDER_DISAGREEMENT"))
            else:
                route = next(iter(route_values))
                chosen_route = latest_route[-1]
                pool, venue, progress = (
                    chosen_route[2],
                    chosen_route[3],
                    chosen_route[4],
                )

        if lifecycle is LaunchLifecycleState.BONDING:
            route = RouteState.BONDING
            reasons.append(ReasonCode("BONDING_ROUTE_NOT_NO_ROUTE"))
        elif lifecycle is LaunchLifecycleState.UNKNOWN and route is RouteState.BONDING:
            lifecycle = LaunchLifecycleState.BONDING

        if invalid:
            reasons.append(ReasonCode("ROUTE_EVIDENCE_INVALID"))
        if not matched:
            reasons.append(ReasonCode("LAUNCH_LIFECYCLE_EVIDENCE_MISSING"))
        elif lifecycle is LaunchLifecycleState.GRADUATED and route is RouteState.UNKNOWN:
            reasons.append(ReasonCode("ROUTE_DISCOVERY_INCOMPLETE"))
        elif route is RouteState.FOUND:
            reasons.append(ReasonCode("GRADUATION_ROUTE_FOUND"))
        elif route is RouteState.NO_ROUTE:
            reasons.append(ReasonCode("ROUTE_DISCOVERY_COMPLETE_NO_ROUTE"))

        unique_selected_values: list[Observation] = []
        selected_keys: set[tuple[str, str]] = set()
        for item in sorted(
            selected, key=lambda value: (_event_at(value), value.provenance.source_id)
        ):
            key = (item.provenance.provider, item.provenance.source_id)
            if key not in selected_keys:
                selected_keys.add(key)
                unique_selected_values.append(item)
        unique_selected = tuple(unique_selected_values)
        quality = _quality(unique_selected)
        if len({reason.code for reason in reasons} & {"PROVIDER_DISAGREEMENT"}):
            quality = QualityState.CONFLICTED
            lifecycle = LaunchLifecycleState.UNKNOWN
            route = RouteState.UNKNOWN
            pool = None
            venue = None
            progress = None
        elif invalid:
            quality = QualityState.INVALID
        elif unique_selected and quality is QualityState.FRESH:
            latest_selected = max(_event_at(item) for item in unique_selected)
            if checked_at >= latest_selected + self.policy.evidence_ttl:
                quality = QualityState.STALE

        as_of = max((_event_at(item) for item in unique_selected), default=checked_at)
        provenance = tuple(item.provenance for item in unique_selected)
        evidence_refs = tuple(item.provenance.source_id for item in unique_selected)
        confidence = Decimal("0") if quality is not QualityState.FRESH else Decimal("1")
        return LaunchLifecycleSnapshot(
            token=token,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            lifecycle_state=lifecycle,
            route_state=route,
            pool_address=pool,
            venue=venue,
            bonding_curve_progress_bps=progress,
            provenance=provenance,
            evidence_refs=evidence_refs,
            reason_codes=tuple(dict.fromkeys(reasons)),
            confidence=confidence,
            config_hash=normalized_config,
            quality_state=quality,
            version=self.policy.version,
        )


__all__ = [
    "GraduationAwareRouteAnalyzer",
    "LaunchLifecyclePolicy",
    "LaunchLifecycleSnapshot",
    "LaunchLifecycleState",
    "RouteState",
]
