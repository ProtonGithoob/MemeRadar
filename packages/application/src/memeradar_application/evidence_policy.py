"""Provider-neutral eligibility rules for persisted evidence projections."""

from __future__ import annotations

from collections.abc import Sequence

from memeradar_domain import Observation

LIVE_SHADOW_COLLECTION_MODE = "LIVE_SHADOW"
PROMOTED_EVIDENCE_STATE = "PROMOTED"


def is_production_evidence_eligible(observation: Observation) -> bool:
    """Return whether one observation may feed an unpromoted decision path."""

    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation")
    raw_mode = observation.normalized_payload.get("collection_mode")
    if raw_mode is None:
        return True
    if not isinstance(raw_mode, str):
        return False
    if raw_mode.strip().upper() != LIVE_SHADOW_COLLECTION_MODE:
        return True
    promotion = observation.normalized_payload.get("evidence_promotion_state", "UNPROMOTED")
    return isinstance(promotion, str) and promotion.strip().upper() == PROMOTED_EVIDENCE_STATE


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
    "LIVE_SHADOW_COLLECTION_MODE",
    "PROMOTED_EVIDENCE_STATE",
    "is_production_evidence_eligible",
    "production_observations",
]
