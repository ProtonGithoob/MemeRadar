"""Provider-independent health comparison and safe routing selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import inf

from memeradar_domain import QualityState
from memeradar_domain.common import ensure_utc, normalize_texts, require_text

from .observability import OperationalState, ProviderOperationalInput

PROVIDER_ROUTING_VERSION = "provider-routing-v1"


class ProviderRouteState(str, Enum):
    """Safe result state for one capability comparison."""

    SELECTED = "SELECTED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ProviderRouteCandidate:
    """A normalized provider health record with deterministic preference."""

    health: ProviderOperationalInput
    priority: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.health, ProviderOperationalInput):
            raise TypeError("health must be a ProviderOperationalInput")
        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, int)
            or not 0 <= self.priority <= 10_000
        ):
            raise ValueError("priority must be an integer between 0 and 10000")


@dataclass(frozen=True, slots=True)
class ProviderRouteDecision:
    """Explainable health comparison with no business or execution authority."""

    capability: str
    as_of: datetime
    state: ProviderRouteState
    selected_provider: str | None
    provider_order: tuple[str, ...]
    healthy_providers: tuple[str, ...]
    degraded_providers: tuple[str, ...]
    unknown_providers: tuple[str, ...]
    conflicted_providers: tuple[str, ...]
    unavailable_providers: tuple[str, ...]
    reason_codes: tuple[str, ...]
    policy_version: str = PROVIDER_ROUTING_VERSION
    execution_eligible: bool = False
    schema_version: str = "provider-route-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", require_text(self.capability, "capability"))
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "state", ProviderRouteState(self.state))
        for field_name in (
            "provider_order",
            "healthy_providers",
            "degraded_providers",
            "unknown_providers",
            "conflicted_providers",
            "unavailable_providers",
        ):
            values = normalize_texts(getattr(self, field_name), field_name, max_item_length=128)
            object.__setattr__(self, field_name, values)
        all_providers = set(self.provider_order)
        categories = (
            self.healthy_providers,
            self.degraded_providers,
            self.unknown_providers,
            self.conflicted_providers,
            self.unavailable_providers,
        )
        if sum(len(values) for values in categories) != len(all_providers):
            raise ValueError("provider route categories must cover each provider once")
        if any(provider not in all_providers for values in categories for provider in values):
            raise ValueError("provider route category contains an unknown provider")
        if self.selected_provider is not None:
            object.__setattr__(
                self,
                "selected_provider",
                require_text(self.selected_provider, "selected_provider", max_length=128),
            )
        if self.state is ProviderRouteState.SELECTED:
            if self.selected_provider not in self.healthy_providers:
                raise ValueError("selected route must select a healthy provider")
        elif self.selected_provider is not None:
            raise ValueError("non-selected route cannot include a selected provider")
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version", max_length=64),
        )
        if self.execution_eligible is not False:
            raise ValueError("provider routing cannot authorize execution")
        if self.schema_version != "provider-route-v1":
            raise ValueError("unsupported provider route schema version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "capability": self.capability,
            "as_of": self.as_of.isoformat(),
            "state": self.state.value,
            "selected_provider": self.selected_provider,
            "provider_order": list(self.provider_order),
            "healthy_providers": list(self.healthy_providers),
            "degraded_providers": list(self.degraded_providers),
            "unknown_providers": list(self.unknown_providers),
            "conflicted_providers": list(self.conflicted_providers),
            "unavailable_providers": list(self.unavailable_providers),
            "reason_codes": list(self.reason_codes),
            "execution_eligible": False,
        }


class ProviderHealthRouter:
    """Select only fresh healthy providers and preserve unsafe alternatives."""

    version = PROVIDER_ROUTING_VERSION

    def select(
        self,
        capability: str,
        candidates: Sequence[ProviderRouteCandidate],
        *,
        as_of: datetime,
    ) -> ProviderRouteDecision:
        normalized_capability = require_text(capability, "capability", max_length=128)
        normalized_as_of = ensure_utc(as_of, "as_of")
        normalized_candidates = tuple(candidates)
        if any(not isinstance(value, ProviderRouteCandidate) for value in normalized_candidates):
            raise TypeError("candidates must contain ProviderRouteCandidate values")
        if any(value.health.capability != normalized_capability for value in normalized_candidates):
            raise ValueError("provider candidates must use the requested capability")
        providers = [value.health.provider for value in normalized_candidates]
        if len(providers) != len(set(providers)):
            raise ValueError("provider candidates must not contain duplicate providers")
        ordered = tuple(
            sorted(
                normalized_candidates,
                key=lambda value: (
                    value.priority,
                    value.health.latency_ms if value.health.latency_ms is not None else inf,
                    value.health.provider,
                ),
            )
        )
        categories: dict[str, list[str]] = {
            "healthy": [],
            "degraded": [],
            "unknown": [],
            "conflicted": [],
            "unavailable": [],
        }
        for candidate in ordered:
            categories[self._category(candidate, normalized_as_of)].append(
                candidate.health.provider
            )
        reasons: tuple[str, ...]
        if categories["conflicted"]:
            state = ProviderRouteState.CONFLICTED
            selected = None
            reasons = ("ROUTE_CONFLICTED",)
        elif categories["healthy"]:
            state = ProviderRouteState.SELECTED
            selected = categories["healthy"][0]
            reasons = ("HEALTHY_PROVIDER_SELECTED",)
        elif categories["unknown"]:
            state = ProviderRouteState.UNKNOWN
            selected = None
            reasons = ("ROUTE_HEALTH_UNKNOWN", "NO_HEALTHY_PROVIDER")
        elif categories["degraded"]:
            state = ProviderRouteState.DEGRADED
            selected = None
            reasons = ("ROUTE_DEGRADED_ONLY", "NO_HEALTHY_PROVIDER")
        else:
            state = ProviderRouteState.UNAVAILABLE
            selected = None
            reasons = ("ALL_PROVIDERS_UNAVAILABLE", "NO_HEALTHY_PROVIDER")
        return ProviderRouteDecision(
            capability=normalized_capability,
            as_of=normalized_as_of,
            state=state,
            selected_provider=selected,
            provider_order=tuple(value.health.provider for value in ordered),
            healthy_providers=tuple(categories["healthy"]),
            degraded_providers=tuple(categories["degraded"]),
            unknown_providers=tuple(categories["unknown"]),
            conflicted_providers=tuple(categories["conflicted"]),
            unavailable_providers=tuple(categories["unavailable"]),
            reason_codes=reasons,
        )

    @staticmethod
    def _category(candidate: ProviderRouteCandidate, as_of: datetime) -> str:
        health = candidate.health
        if health.checked_at > as_of:
            return "unknown"
        reasons = {value.upper() for value in health.reason_codes}
        if health.freshness_state is QualityState.CONFLICTED or any(
            "CONFLICT" in value or "DISAGREEMENT" in value for value in reasons
        ):
            return "conflicted"
        if health.state is OperationalState.DOWN:
            return "unavailable"
        if health.state is OperationalState.UNKNOWN:
            return "unknown"
        if health.state is OperationalState.DEGRADED:
            return "degraded"
        if health.freshness_state is None:
            return "unknown"
        if health.freshness_state in {QualityState.UNKNOWN, QualityState.INVALID}:
            return "unknown"
        if health.freshness_state is QualityState.STALE:
            return "degraded"
        return "healthy"


__all__ = [
    "PROVIDER_ROUTING_VERSION",
    "ProviderHealthRouter",
    "ProviderRouteCandidate",
    "ProviderRouteDecision",
    "ProviderRouteState",
]
