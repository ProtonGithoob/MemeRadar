"""Pump.fun → successor-venue wallet position, cost-basis and realized-PnL continuity."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from json import dumps

from memeradar_domain import Observation, Provenance, QualityState, ReasonCode, TokenIdentity
from memeradar_domain.common import ensure_utc, require_text, to_decimal
from memeradar_domain.events import normalize_reason_codes

from .event_time import exact_event_time
from .wallet_tracking import (
    TrackedWalletRegistry,
    WalletAction,
    WalletActivity,
    WalletTrackingAnalyzer,
    WalletTrackingPolicy,
    WalletTrackingSnapshot,
)

_MISSING = object()
_LIFECYCLE_KINDS = frozenset({"protocol.lifecycle", "launchpad.lifecycle"})
_MIGRATION_TYPES = frozenset(
    {
        "graduation",
        "graduated",
        "complete",
        "migration",
        "migrate",
        "pool_migrated",
    }
)
_REVERT_STATES = frozenset({"reverted", "retracted", "rollback", "rolled_back"})
_SOURCE_VENUE = "pump.fun"
_SUCCESSOR_VENUE = "pumpswap"


class ContinuityQuality(str, Enum):
    """Cross-venue stitch quality; missing evidence is never treated as verified."""

    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"


def _field(payload: object, *names: str) -> object:
    if not isinstance(payload, dict):
        return _MISSING
    for name in names:
        if name in payload:
            return payload[name]
    return _MISSING


def _optional_text(value: object, field: str) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return require_text(value, field, max_length=128).lower()


def _optional_address(value: object, field: str) -> str | None:
    text = _optional_text(value, field)
    return None if text is None else text


def _event_type(payload: object) -> str:
    raw = _field(payload, "protocol_event_type", "event_type", "type")
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def _is_reverted(observation: Observation) -> bool:
    payload = observation.normalized_payload
    reverted_flag = _field(payload, "reverted", "reorg", "rollback")
    recovery = _optional_text(_field(payload, "recovery_state", "commitment_state"), "recovery")
    return reverted_flag is True or (recovery is not None and recovery in _REVERT_STATES)


def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
    mint = _field(observation.normalized_payload, "mint_address", "token_mint", "mint")
    if mint is not _MISSING and mint != token.mint_address:
        return False
    if observation.token_id is not None:
        return observation.token_id == token.id
    return mint == token.mint_address


def _trade_key(activity: WalletActivity) -> str:
    if activity.canonical_trade_id is not None:
        return f"id:{activity.canonical_trade_id}"
    quote = "" if activity.quote_amount is None else format(activity.quote_amount, "f")
    action_val = (
        activity.action.value if hasattr(activity.action, "value") else str(activity.action)
    )
    return (
        f"econ:{activity.wallet_address}:{action_val}:"
        f"{format(activity.quantity, 'f')}:{quote}:{activity.occurred_at.isoformat()}"
    )


def _continuity_hash(material: dict[str, object]) -> str:
    encoded = dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{sha256(encoded.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class VenueMigrationBoundary:
    """Canonical same-mint venue handoff; migration itself is not a trade."""

    token: TokenIdentity
    source_venue: str
    successor_venue: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    source_pool: str | None
    successor_pool: str | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    quality_state: QualityState
    parser_version: str
    schema_version: int
    config_hash: str
    reason_codes: tuple[ReasonCode | str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(
            self, "source_venue", require_text(self.source_venue, "source_venue").lower()
        )
        object.__setattr__(
            self,
            "successor_venue",
            require_text(self.successor_venue, "successor_venue").lower(),
        )
        occurred = ensure_utc(self.occurred_at, "occurred_at")
        observed = ensure_utc(self.observed_at, "observed_at")
        ingested = ensure_utc(self.ingested_at, "ingested_at")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        if self.source_pool is not None:
            object.__setattr__(self, "source_pool", require_text(self.source_pool, "source_pool"))
        if self.successor_pool is not None:
            object.__setattr__(
                self, "successor_pool", require_text(self.successor_pool, "successor_pool")
            )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version", max_length=64),
        )
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise TypeError("schema_version must be an integer")
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "provenance", tuple(self.provenance))


@dataclass(frozen=True, slots=True)
class CrossVenueWalletContinuity:
    """Continuous FIFO reconstruction across a verified same-mint venue migration."""

    token: TokenIdentity
    wallet_address: str
    quality: ContinuityQuality | str
    snapshot: WalletTrackingSnapshot
    pre_migration_quantity: Decimal | None
    pre_migration_cost_basis: Decimal | None
    post_migration_quantity: Decimal | None
    migration: VenueMigrationBoundary | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    version: str
    config_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if not isinstance(self.snapshot, WalletTrackingSnapshot):
            raise TypeError("snapshot must be a WalletTrackingSnapshot")
        object.__setattr__(self, "quality", ContinuityQuality(self.quality))
        if self.pre_migration_quantity is not None:
            object.__setattr__(
                self,
                "pre_migration_quantity",
                to_decimal(self.pre_migration_quantity, "pre_migration_quantity"),
            )
        if self.pre_migration_cost_basis is not None:
            object.__setattr__(
                self,
                "pre_migration_cost_basis",
                to_decimal(self.pre_migration_cost_basis, "pre_migration_cost_basis"),
            )
        if self.post_migration_quantity is not None:
            object.__setattr__(
                self,
                "post_migration_quantity",
                to_decimal(self.post_migration_quantity, "post_migration_quantity"),
            )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))

    @property
    def feeds_smart_wallet_score(self) -> bool:
        """Only verified continuous histories may enter SmartWalletScore outcomes."""

        return self.quality is ContinuityQuality.VERIFIED and self.snapshot.realized_pnl is not None

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


@dataclass(frozen=True, slots=True)
class CrossVenueContinuityPolicy:
    """Versioned continuity policy; it never grants execution authority."""

    version: str = "cross-venue-continuity-v1"
    source_venue: str = _SOURCE_VENUE
    successor_venue: str = _SUCCESSOR_VENUE

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(
            self, "source_venue", require_text(self.source_venue, "source_venue").lower()
        )
        object.__setattr__(
            self,
            "successor_venue",
            require_text(self.successor_venue, "successor_venue").lower(),
        )


class CrossVenuePositionContinuity:
    """Keep wallet quantity/cost-basis/PnL continuous across mapped venue migrations."""

    def __init__(
        self,
        *,
        policy: CrossVenueContinuityPolicy | None = None,
        tracker: WalletTrackingAnalyzer | None = None,
    ) -> None:
        self.policy = policy or CrossVenueContinuityPolicy()
        self.tracker = tracker or WalletTrackingAnalyzer(policy=WalletTrackingPolicy())

    def reconstruct(
        self,
        token: TokenIdentity,
        activities: Sequence[WalletActivity],
        registry: TrackedWalletRegistry,
        *,
        lifecycle_observations: Sequence[Observation] = (),
        now: datetime,
        config_hash: str,
        token_created_at: datetime | None = None,
        rug_observations: Sequence[Observation] = (),
    ) -> tuple[CrossVenueWalletContinuity, ...]:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_hash = require_text(config_hash, "config_hash")
        boundary, boundary_quality, boundary_reasons, reverted = self._resolve_boundary(
            token,
            lifecycle_observations,
            config_hash=normalized_hash,
        )
        canonical_activities = self.canonicalize_activities(activities, boundary)
        snapshots = self.tracker.reconstruct_positions(
            token,
            canonical_activities,
            registry,
            now=checked_at,
            config_hash=normalized_hash,
            token_created_at=token_created_at,
            rug_observations=rug_observations,
        )
        return tuple(
            self._continuity_for_snapshot(
                token,
                snapshot,
                tuple(
                    item
                    for item in canonical_activities
                    if item.wallet_address == snapshot.wallet_address
                ),
                boundary,
                boundary_quality=boundary_quality,
                boundary_reasons=boundary_reasons,
                reverted=reverted,
                config_hash=normalized_hash,
            )
            for snapshot in snapshots
        )

    def canonicalize_activities(
        self,
        activities: Sequence[WalletActivity],
        boundary: VenueMigrationBoundary | None,
    ) -> tuple[WalletActivity, ...]:
        if isinstance(activities, str | bytes | bytearray):
            raise TypeError("activities must be a sequence")
        chosen: dict[str, WalletActivity] = {}
        for activity in activities:
            if not isinstance(activity, WalletActivity):
                raise TypeError("activities must contain WalletActivity values")
            key = _trade_key(activity)
            prior = chosen.get(key)
            if prior is None or prior == activity:
                chosen[key] = activity if prior is None else prior
                continue
            chosen[key] = self._preferred_duplicate(prior, activity, boundary)
        return tuple(
            sorted(
                chosen.values(),
                key=lambda item: (item.occurred_at, item.observed_at, item.source_id),
            )
        )

    def _preferred_duplicate(
        self,
        left: WalletActivity,
        right: WalletActivity,
        boundary: VenueMigrationBoundary | None,
    ) -> WalletActivity:
        expected = self._expected_venue(left.occurred_at, boundary)
        if expected is None:
            return left if left.source_id <= right.source_id else right
        if left.venue == expected and right.venue != expected:
            return left
        if right.venue == expected and left.venue != expected:
            return right
        return left if left.source_id <= right.source_id else right

    def _expected_venue(
        self,
        occurred_at: datetime,
        boundary: VenueMigrationBoundary | None,
    ) -> str | None:
        if boundary is None:
            return None
        if occurred_at <= boundary.occurred_at:
            return boundary.source_venue
        return boundary.successor_venue

    def _resolve_boundary(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        config_hash: str,
    ) -> tuple[VenueMigrationBoundary | None, ContinuityQuality, tuple[str, ...], bool]:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("lifecycle_observations must be a sequence")
        candidates: list[Observation] = []
        reverted_seen = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("lifecycle_observations must contain Observation values")
            if observation.kind not in _LIFECYCLE_KINDS or not _observation_matches(
                observation, token
            ):
                continue
            if _event_type(observation.normalized_payload) not in _MIGRATION_TYPES:
                continue
            if _is_reverted(observation):
                reverted_seen = True
                continue
            if observation.quality_state in {QualityState.CONFLICTED, QualityState.INVALID}:
                quality = (
                    ContinuityQuality.CONFLICTED
                    if observation.quality_state is QualityState.CONFLICTED
                    else ContinuityQuality.INVALID
                )
                return None, quality, ("MIGRATION_EVIDENCE_UNSAFE",), False
            if exact_event_time(observation) is None:
                continue
            candidates.append(observation)
        if reverted_seen and not candidates:
            return None, ContinuityQuality.UNKNOWN, ("MIGRATION_REVERTED",), True
        if not candidates:
            return None, ContinuityQuality.UNKNOWN, ("MIGRATION_EVIDENCE_MISSING",), False

        ordered = sorted(
            candidates,
            key=lambda item: (
                exact_event_time(item),
                item.observed_at,
                item.provenance.source_id,
            ),
        )
        first = ordered[0]
        successor_pools = {
            _optional_address(
                _field(
                    item.normalized_payload, "successor_pool", "destination_pool", "pool_address"
                ),
                "successor_pool",
            )
            for item in ordered
        }
        successor_venues = {
            _optional_text(
                _field(item.normalized_payload, "successor_venue", "destination_venue"),
                "successor_venue",
            )
            or self.policy.successor_venue
            for item in ordered
        }
        known_pools = {pool for pool in successor_pools if pool is not None}
        if len(known_pools) > 1 or len(successor_venues) > 1:
            return None, ContinuityQuality.CONFLICTED, ("MIGRATION_SUCCESSOR_CONFLICTED",), False

        first_time = exact_event_time(first)
        assert first_time is not None
        for item in ordered[1:]:
            later = exact_event_time(item)
            assert later is not None
            if abs((later - first_time).total_seconds()) > 5:
                return (
                    None,
                    ContinuityQuality.CONFLICTED,
                    ("MIGRATION_SUCCESSOR_CONFLICTED",),
                    False,
                )

        payload = first.normalized_payload
        source_venue = (
            _optional_text(_field(payload, "source_venue", "venue"), "source_venue")
            or self.policy.source_venue
        )
        successor_venue = next(iter(successor_venues))
        successor_pool = next((pool for pool in successor_pools if pool is not None), None)
        source_pool = _optional_address(
            _field(payload, "source_pool", "bonding_curve"), "source_pool"
        )
        schema_raw = _field(payload, "schema_version")
        schema_version = (
            schema_raw if isinstance(schema_raw, int) and not isinstance(schema_raw, bool) else 2
        )
        boundary = VenueMigrationBoundary(
            token=token,
            source_venue=source_venue,
            successor_venue=successor_venue,
            occurred_at=first_time,
            observed_at=first.observed_at,
            ingested_at=first.ingested_at,
            source_pool=source_pool,
            successor_pool=successor_pool,
            provenance=tuple(item.provenance for item in ordered),
            evidence_refs=tuple(item.provenance.source_id for item in ordered),
            quality_state=QualityState.FRESH,
            parser_version=first.provenance.parser_version,
            schema_version=schema_version,
            config_hash=_continuity_hash(
                {
                    "source_venue": source_venue,
                    "successor_venue": successor_venue,
                    "successor_pool": successor_pool,
                    "occurred_at": first_time.isoformat(),
                    "config_hash": config_hash,
                    "version": self.policy.version,
                }
            ),
            reason_codes=("MIGRATION_BOUNDARY_VERIFIED", "MIGRATION_NOT_TRADE"),
        )
        return (
            boundary,
            ContinuityQuality.VERIFIED,
            ("MIGRATION_BOUNDARY_VERIFIED", "MIGRATION_NOT_TRADE"),
            False,
        )

    def _continuity_for_snapshot(
        self,
        token: TokenIdentity,
        snapshot: WalletTrackingSnapshot,
        activities: Sequence[WalletActivity],
        boundary: VenueMigrationBoundary | None,
        *,
        boundary_quality: ContinuityQuality,
        boundary_reasons: Sequence[str],
        reverted: bool,
        config_hash: str,
    ) -> CrossVenueWalletContinuity:
        reasons = list(boundary_reasons)
        pre_quantity: Decimal | None = None
        pre_cost: Decimal | None = None
        quality = boundary_quality
        if boundary is not None:
            pre_quantity, pre_cost = self._pre_migration_open(activities, boundary)
            if pre_quantity is None:
                quality = ContinuityQuality.UNKNOWN
                reasons.append("PRE_MIGRATION_STATE_MISSING")
            elif snapshot.unmatched_sell_quantity > 0:
                quality = ContinuityQuality.PARTIAL
                reasons.append("PRE_MIGRATION_STATE_PARTIAL")
            else:
                reasons.append("CROSS_VENUE_FIFO_CONTINUOUS")
        elif reverted:
            quality = ContinuityQuality.UNKNOWN
        elif not activities:
            quality = ContinuityQuality.UNKNOWN
            reasons.append("WALLET_ACTIVITY_MISSING")

        if boundary_quality is ContinuityQuality.CONFLICTED:
            quality = ContinuityQuality.CONFLICTED
        if boundary_quality is ContinuityQuality.INVALID:
            quality = ContinuityQuality.INVALID

        evidence_refs = list(snapshot.evidence_refs)
        provenance = list(snapshot.provenance)
        if boundary is not None:
            evidence_refs.extend(ref for ref in boundary.evidence_refs if ref not in evidence_refs)
            provenance.extend(item for item in boundary.provenance if item not in provenance)

        snapshot_reasons = tuple(
            code.code if isinstance(code, ReasonCode) else str(code)
            for code in snapshot.reason_codes
        )
        return CrossVenueWalletContinuity(
            token=token,
            wallet_address=snapshot.wallet_address,
            quality=quality,
            snapshot=snapshot,
            pre_migration_quantity=pre_quantity,
            pre_migration_cost_basis=pre_cost,
            post_migration_quantity=snapshot.open_quantity,
            migration=None if quality is ContinuityQuality.CONFLICTED else boundary,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(dict.fromkeys((*reasons, *snapshot_reasons))),
            version=self.policy.version,
            config_hash=config_hash,
        )

    def _pre_migration_open(
        self,
        activities: Sequence[WalletActivity],
        boundary: VenueMigrationBoundary,
    ) -> tuple[Decimal | None, Decimal | None]:
        pre = [item for item in activities if item.occurred_at <= boundary.occurred_at]
        if not any(item.action is WalletAction.BUY for item in pre):
            return None, None
        open_cost = Decimal("0")
        cost_known = True
        lots: list[tuple[Decimal, Decimal | None]] = []
        for item in pre:
            if item.action is WalletAction.BUY:
                lots.append((item.quantity, item.effective_price))
                continue
            remaining = item.quantity
            while remaining > 0 and lots:
                qty, unit = lots[0]
                matched = min(remaining, qty)
                remaining -= matched
                leftover = qty - matched
                if leftover == 0:
                    lots.pop(0)
                else:
                    lots[0] = (leftover, unit)
        open_quantity = sum((qty for qty, _unit in lots), Decimal("0"))
        for qty, unit in lots:
            if unit is None:
                cost_known = False
            else:
                open_cost += qty * unit
        return open_quantity, open_cost if cost_known else None


__all__ = [
    "ContinuityQuality",
    "CrossVenueContinuityPolicy",
    "CrossVenuePositionContinuity",
    "CrossVenueWalletContinuity",
    "VenueMigrationBoundary",
]
