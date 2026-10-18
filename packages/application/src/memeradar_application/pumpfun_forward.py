"""Small, bounded scheduling helpers for Pump.fun forward evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_domain import QualityState
from memeradar_domain.common import ensure_utc, require_text

from .replay_harness import ReplayEventRecord

PUMPFUN_FORWARD_VERSION = "pumpfun-forward-evidence-v1"

DEX_FIRST_OBSERVATION_OFFSETS_SECONDS = (
    0,
    5,
    10,
    20,
    30,
    60,
    120,
    300,
    600,
    1200,
    1800,
    3600,
)
MARKET_SNAPSHOT_OFFSETS_SECONDS = (
    0,
    30,
    60,
    120,
    300,
    600,
    1800,
    3600,
    21600,
    86400,
    259200,
    604800,
)
EARLY_REEVALUATION_OFFSETS_SECONDS = (30, 60, 120, 300, 600, 900)


def offset_label(offset_seconds: int) -> str:
    """Use stable human-readable labels without hiding the numeric offset."""

    if offset_seconds == 0:
        return "T0"
    if offset_seconds % 86400 == 0:
        return f"{offset_seconds // 86400}d"
    if offset_seconds % 3600 == 0:
        return f"{offset_seconds // 3600}h"
    if offset_seconds % 60 == 0:
        return f"{offset_seconds // 60}m"
    return f"{offset_seconds}s"


def poll_is_due(discovered_at: datetime, offset_seconds: int, now: datetime) -> bool:
    """Return whether a bounded poll milestone has become due."""

    if offset_seconds < 0:
        raise ValueError("offset_seconds must be non-negative")
    return ensure_utc(now, "now") >= ensure_utc(discovered_at, "discovered_at") + timedelta(
        seconds=offset_seconds
    )


def lead_seconds(
    discovered_at: datetime,
    dex_api_first_observed_at: datetime | None,
) -> float | None:
    """Measure MemeRadar-to-Dex API observation lead, never Dex listing latency."""

    if dex_api_first_observed_at is None:
        return None
    discovered = ensure_utc(discovered_at, "discovered_at")
    observed = ensure_utc(dex_api_first_observed_at, "dex_api_first_observed_at")
    if observed < discovered:
        return None
    return (observed - discovered).total_seconds()


def forward_observation_source_id(mint: str, offset_seconds: int) -> str:
    """Return the idempotency key for one exact-mint DexScreener poll."""

    if offset_seconds < 0:
        raise ValueError("offset_seconds must be non-negative")
    return f"pumpfun-forward:dexscreener:{require_text(mint, 'mint')}:{offset_seconds}"


def dex_horizon_source_id(mint: str) -> str:
    """Return the durable terminal identity for an exhausted exact-mint poll horizon."""

    return f"pumpfun-forward:dexscreener:{require_text(mint, 'mint')}:terminal"


def early_reevaluation_source_id(mint: str, offset_seconds: int) -> str:
    """Return the durable idempotency key for one bounded lifecycle reevaluation."""

    if offset_seconds < 0:
        raise ValueError("offset_seconds must be non-negative")
    return f"pumpfun-forward:early-reevaluation:{require_text(mint, 'mint')}:{offset_seconds}"


def utc_now() -> datetime:
    """Patchable clock seam for small worker tests."""

    return datetime.now(UTC)


__all__ = [
    "DEX_FIRST_OBSERVATION_OFFSETS_SECONDS",
    "EARLY_REEVALUATION_OFFSETS_SECONDS",
    "MARKET_SNAPSHOT_OFFSETS_SECONDS",
    "PUMPFUN_FORWARD_VERSION",
    "dex_horizon_source_id",
    "early_reevaluation_source_id",
    "forward_observation_source_id",
    "lead_seconds",
    "offset_label",
    "poll_is_due",
    "utc_now",
]


def metric(payload: Mapping[str, object], *names: str) -> Decimal | None:
    for name in names:
        value = payload.get(name)
        if value is not None:
            try:
                parsed = Decimal(str(value))
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
    for nested_name in ("values", "metrics", "snapshot", "data"):
        nested = payload.get(nested_name)
        if isinstance(nested, Mapping):
            value = metric(nested, *names)
            if value is not None:
                return value
    return None


def market_metrics(record: ReplayEventRecord) -> dict[str, Decimal | None]:
    payload = record.observation.normalized_payload
    return {
        "price": metric(payload, "price_usd", "market_price", "price"),
        "liquidity": metric(
            payload,
            "effective_executable_liquidity",
            "executable_liquidity",
            "effective_liquidity",
            "liquidity_usd",
            "liquidity",
            "pool_liquidity",
        ),
        "market_cap": metric(
            payload,
            "market_cap_usd",
            "market_cap",
            "marketCapUsd",
            "market_capitalization",
            "fdv",
        ),
    }


def valid_market_record(record: ReplayEventRecord) -> bool:
    if record.observation.kind != "market.market_snapshot":
        return False
    if record.observation.quality_state is not QualityState.FRESH:
        return False
    if record.observation.normalized_payload.get("pair_found") is False:
        return False
    return any(value is not None for value in market_metrics(record).values())


def horizon_matured(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    duration: timedelta,
) -> bool:
    target = signal_at + duration
    return any(valid_market_record(record) and record.event_at >= target for record in records)


def endpoint_record(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    duration: timedelta,
) -> ReplayEventRecord | None:
    end = signal_at + duration
    bounded = [
        record
        for record in records
        if valid_market_record(record) and signal_at < record.event_at <= end
    ]
    if bounded:
        return max(bounded, key=lambda record: record.event_at)
    after = [record for record in records if valid_market_record(record) and record.event_at > end]
    return min(after, key=lambda record: record.event_at) if after else None


def multiple_at_endpoint(
    record: ReplayEventRecord | None,
    *,
    baseline_price: Decimal | None,
    baseline_market_cap: Decimal | None,
) -> Decimal | None:
    if record is None:
        return None
    values = market_metrics(record)
    if values["price"] is not None and baseline_price is not None and baseline_price > 0:
        return values["price"] / baseline_price
    if (
        values["market_cap"] is not None
        and baseline_market_cap is not None
        and baseline_market_cap > 0
    ):
        return values["market_cap"] / baseline_market_cap
    return None


def initial_market_values(
    records: Sequence[ReplayEventRecord],
    signal_at: datetime,
    stage_payloads: Sequence[Mapping[str, object]],
) -> dict[str, str | None]:
    candidates = [
        record for record in records if valid_market_record(record) and record.event_at >= signal_at
    ]
    first = min(candidates, key=lambda record: record.event_at) if candidates else None
    values = market_metrics(first) if first is not None else {}
    stage = next(
        (
            payload
            for payload in sorted(
                stage_payloads,
                key=lambda value: str(value.get("occurred_at", value.get("discovered_at", ""))),
            )
            if str(payload.get("state", payload.get("stage", ""))).upper() == "DISCOVERED"
        ),
        {},
    )
    names = {
        "price": ("price_at_detection", "price_usd", "market_price", "price"),
        "liquidity": (
            "liquidity_at_detection",
            "effective_executable_liquidity",
            "executable_liquidity",
            "liquidity_usd",
            "liquidity",
        ),
        "market_cap": (
            "market_cap_at_detection",
            "market_cap_usd",
            "market_cap",
            "fdv",
        ),
    }
    result: dict[str, str | None] = {}
    for key, payload_names in names.items():
        metric_value = values.get(key)
        if metric_value is None:
            metric_value = metric(stage, *payload_names)
        result[key] = None if metric_value is None else str(metric_value)
    return result


def flag(payload: Mapping[str, object], *names: str) -> bool:
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, str) and value.strip().lower() in {
            "true",
            "yes",
            "1",
            "detected",
            "removed",
            "failed",
            "honeypot",
        }:
            return True
    return False


def outcome_flags(
    records: Sequence[ReplayEventRecord],
    stage_payloads: Sequence[Mapping[str, object]],
    *,
    signal_at: datetime,
    initial_liquidity: Decimal | None,
) -> dict[str, bool]:
    payloads = [record.observation.normalized_payload for record in records] + list(stage_payloads)
    rug_detected = any(
        record.observation.kind in {"risk.rug_event", "risk.token_outcome", "security.rug"}
        for record in records
    ) or any(flag(payload, "rug_detected", "rug", "rugged") for payload in payloads)
    honeypot = any(
        flag(payload, "honeypot_detected", "honeypot", "is_honeypot") for payload in payloads
    )
    migration_completed = any(
        flag(payload, "migration_completed", "graduated", "dex_active", "liquidity_added")
        or str(payload.get("migration_state", payload.get("lifecycle_state", ""))).upper()
        in {"COMPLETED", "GRADUATED", "DEX_ACTIVE", "LIQUIDITY_ADDED"}
        for payload in payloads
    )
    liquidities = [
        market_metrics(record)["liquidity"]
        for record in records
        if record.event_at > signal_at and valid_market_record(record)
    ]
    liquidity_removed = any(
        flag(payload, "liquidity_removed", "liquidity_rug", "liquidity_collapse")
        for payload in payloads
    )
    if initial_liquidity is not None and initial_liquidity > 0:
        liquidity_removed = liquidity_removed or any(
            liquidity is not None and liquidity <= initial_liquidity * Decimal("0.10")
            for liquidity in liquidities
        )
    return {
        "rug_detected": rug_detected,
        "honeypot_detected": honeypot,
        "liquidity_removed": liquidity_removed,
        "migration_completed": migration_completed,
    }
