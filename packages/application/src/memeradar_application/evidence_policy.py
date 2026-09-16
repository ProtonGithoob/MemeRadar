"""Provider-neutral eligibility rules for persisted evidence projections."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from memeradar_domain import Observation

PRODUCTION_COLLECTION_MODE = "PRODUCTION"
LIVE_SHADOW_COLLECTION_MODE = "LIVE_SHADOW"
RECOGNIZED_COLLECTION_MODES = frozenset(
    {
        PRODUCTION_COLLECTION_MODE,
        LIVE_SHADOW_COLLECTION_MODE,
        "RESEARCH",
        "REPLAY",
        "FIXTURE",
        "MOCK",
        "SYNTHETIC",
        "DEMO",
        "REDACTED",
    }
)
LEGACY_MISSING_COLLECTION_MODE_CUTOFF = datetime(2026, 9, 15, tzinfo=UTC)


def _legacy_unclassified_observation(observation: Observation) -> bool:
    """Keep pre-boundary canonical rows usable only without trust claims."""

    if observation.ingested_at >= LEGACY_MISSING_COLLECTION_MODE_CUTOFF:
        return False

    payload = observation.normalized_payload
    return not any(
        key in payload
        for key in (
            "evidence_origin",
            "evidence_class",
            "live_shadow",
            "evidence_promotion_state",
        )
    )


def is_production_evidence_eligible(observation: Observation) -> bool:
    """Return whether one observation may feed an unpromoted decision path."""

    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    raw_mode = observation.normalized_payload.get("collection_mode")
    if raw_mode is None:
        return _legacy_unclassified_observation(observation)
    if not isinstance(raw_mode, str):
        return False
    normalized_mode = raw_mode.strip().upper()
    if normalized_mode not in RECOGNIZED_COLLECTION_MODES:
        return False
    return normalized_mode == PRODUCTION_COLLECTION_MODE


def production_observations(
    observations: Sequence[object],
    *,
    include_shadow: bool = False,
) -> tuple[Observation, ...]:
    """Validate and filter raw evidence for production-facing projections.

    Research/replay callers opt in explicitly with ``include_shadow=True``;
    persisted observations are never removed by this projection.
    """

    if not isinstance(include_shadow, bool):
        raise TypeError("include_shadow must be a boolean")
    if isinstance(observations, str | bytes | bytearray):
        raise TypeError("observations must be a sequence")
    normalized = tuple(observations)
    if any(not isinstance(value, Observation) for value in normalized):
        raise TypeError("observations must contain Observation values")
    validated = tuple(value for value in normalized if isinstance(value, Observation))
    if include_shadow:
        return validated
    return tuple(value for value in validated if is_production_evidence_eligible(value))


__all__ = [
    "PRODUCTION_COLLECTION_MODE",
    "LIVE_SHADOW_COLLECTION_MODE",
    "LEGACY_MISSING_COLLECTION_MODE_CUTOFF",
    "RECOGNIZED_COLLECTION_MODES",
    "is_production_evidence_eligible",
    "production_observations",
]
