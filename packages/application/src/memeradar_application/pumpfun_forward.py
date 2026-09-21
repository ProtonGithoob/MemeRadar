"""Small, bounded scheduling helpers for Pump.fun forward evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from memeradar_domain.common import ensure_utc, require_text

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


def utc_now() -> datetime:
    """Patchable clock seam for small worker tests."""

    return datetime.now(UTC)


__all__ = [
    "DEX_FIRST_OBSERVATION_OFFSETS_SECONDS",
    "MARKET_SNAPSHOT_OFFSETS_SECONDS",
    "PUMPFUN_FORWARD_VERSION",
    "forward_observation_source_id",
    "lead_seconds",
    "offset_label",
    "poll_is_due",
    "utc_now",
]
