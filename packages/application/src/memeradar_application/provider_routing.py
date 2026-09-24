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
from .provider_contracts import ProviderCapability

PROVIDER_ROUTING_VERSION = "provider-routing-v1"
FREE_FIRST_ROUTING_VERSION = "free-first-routing-v1"


class ProviderRouteState(str, Enum):
    """Safe result state for one capability comparison."""

    SELECTED = "SELECTED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CapabilityRoute:
    """Ordered provider names for one capability, without provider imports."""

    capability: ProviderCapability | str
    providers: tuple[str, ...]
    optional: bool = True

    def __post_init__(self) -> None:
        capability = (
            self.capability.value
            if isinstance(self.capability, ProviderCapability)
            else require_text(self.capability, "capability", max_length=128)
        )
        object.__setattr__(self, "capability", capability)
        object.__setattr__(
            self,
            "providers",
            normalize_texts(self.providers, "providers", max_item_length=128),
        )
        if not isinstance(self.optional, bool):
            raise TypeError("optional must be a boolean")


@dataclass(frozen=True, slots=True)
class FreeFirstRoutePlan:
    """Provider-neutral route order for the free-first composition layer."""

    chain: CapabilityRoute
    enhanced_asset_metadata: CapabilityRoute
    transaction_history: CapabilityRoute
    realtime_stream: CapabilityRoute
    market: CapabilityRoute
    quote: CapabilityRoute
    pair_discovery: CapabilityRoute
    social_metadata: CapabilityRoute
    social_analytics: CapabilityRoute
    risk: CapabilityRoute
    wallet: CapabilityRoute
    narrative: CapabilityRoute
    alerts: CapabilityRoute
    version: str = FREE_FIRST_ROUTING_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "chain",
            "enhanced_asset_metadata",
            "transaction_history",
            "realtime_stream",
            "market",
            "quote",
            "pair_discovery",
            "social_metadata",
            "social_analytics",
            "risk",
            "wallet",
            "narrative",
            "alerts",
        ):
            if not isinstance(getattr(self, field_name), CapabilityRoute):
                raise TypeError(f"{field_name} must be a CapabilityRoute")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


def build_free_first_route_plan(
    *,
    helius_configured: bool = False,
    helius_stream_configured: bool = False,
    birdeye_configured: bool = False,
    rugcheck_configured: bool = False,
    external_social_configured: bool = False,
    external_narrative_configured: bool = False,
    external_wallet_configured: bool = False,
    custom_quote_configured: bool = False,
    jupiter_configured: bool = False,
    telegram_configured: bool = False,
    market_data_provider: str = "dexscreener",
    paper_quote_provider: str = "dexscreener",
    wallet_intelligence_provider: str = "local",
    social_metadata_provider: str = "dexscreener",
    narrative_provider: str = "ollama",
) -> FreeFirstRoutePlan:
    """Build deterministic capability routes from safe configuration presence."""

    for name, value in (
        ("helius_configured", helius_configured),
        ("helius_stream_configured", helius_stream_configured),
        ("birdeye_configured", birdeye_configured),
        ("rugcheck_configured", rugcheck_configured),
        ("external_social_configured", external_social_configured),
        ("external_narrative_configured", external_narrative_configured),
        ("external_wallet_configured", external_wallet_configured),
        ("custom_quote_configured", custom_quote_configured),
        ("jupiter_configured", jupiter_configured),
        ("telegram_configured", telegram_configured),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean")

    def choice(value: str, name: str, allowed: frozenset[str]) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        normalized = value.strip().lower()
        if normalized not in allowed:
            choices = ", ".join(sorted(allowed))
            raise ValueError(f"{name} must be one of: {choices}")
        return normalized

    selected_market = choice(
        market_data_provider,
        "market_data_provider",
        frozenset({"birdeye", "dexscreener"}),
    )
    selected_quote = choice(
        paper_quote_provider,
        "paper_quote_provider",
        frozenset({"custom", "dexscreener", "birdeye", "jupiter"}),
    )
    choice(
        wallet_intelligence_provider,
        "wallet_intelligence_provider",
        frozenset({"external", "local"}),
    )
    selected_metadata = choice(
        social_metadata_provider,
        "social_metadata_provider",
        frozenset({"dexscreener", "disabled"}),
    )
    selected_narrative = choice(
        narrative_provider,
        "narrative_provider",
        frozenset({"disabled", "external", "ollama"}),
    )

    chain_providers = ("helius", "solana-public-rpc") if helius_configured else (
        "solana-public-rpc",
    )
    market_providers: tuple[str, ...] = (
        ("birdeye", "dexscreener")
        if selected_market == "birdeye" and birdeye_configured
        else ("dexscreener", "birdeye")
        if birdeye_configured
        else ("dexscreener",)
    )
    social_analytics = ("social",) if external_social_configured else ()
    if selected_metadata == "disabled":
        metadata_providers: tuple[str, ...] = ()
    else:
        metadata_providers = ("dexscreener",)
    quote_providers: tuple[str, ...]
    if selected_quote == "custom":
        quote_providers = ("custom", "dexscreener") if custom_quote_configured else ("custom",)
    elif selected_quote == "jupiter":
        quote_providers = ("jupiter", "dexscreener")
    elif selected_quote == "birdeye" and birdeye_configured:
        # Birdeye's existing adapter is market-data only; it is not treated as
        # a QuotePort until a dedicated normalized quote adapter exists.
        quote_providers = ("dexscreener",)
    else:
        quote_providers = ("dexscreener",)
    wallet_providers: tuple[str, ...] = ("local",)
    if external_wallet_configured:
        wallet_providers = ("local", "external-wallet")
    narrative_providers: tuple[str, ...]
    if selected_narrative == "disabled":
        narrative_providers = ("disabled",)
    elif selected_narrative == "external":
        narrative_providers = ("narrative", "disabled")
    else:
        narrative_providers = ("ollama", "disabled")

    return FreeFirstRoutePlan(
        chain=CapabilityRoute(ProviderCapability.CHAIN_RPC, chain_providers, optional=False),
        enhanced_asset_metadata=CapabilityRoute(
            ProviderCapability.ENHANCED_ASSET_METADATA,
            ("helius",),
        ),
        transaction_history=CapabilityRoute(
            ProviderCapability.TRANSACTION_HISTORY,
            chain_providers,
            optional=False,
        ),
        realtime_stream=CapabilityRoute(
            ProviderCapability.REALTIME_STREAM,
            ("helius-stream",) if helius_stream_configured else (),
        ),
        market=CapabilityRoute(
            ProviderCapability.MARKET_SNAPSHOT,
            market_providers,
            optional=False,
        ),
        quote=CapabilityRoute(ProviderCapability.MARKET_QUOTE, quote_providers, optional=False),
        pair_discovery=CapabilityRoute(
            ProviderCapability.PAIR_DISCOVERY,
            market_providers,
            optional=False,
        ),
        social_metadata=CapabilityRoute(
            ProviderCapability.SOCIAL_METADATA,
            metadata_providers,
        ),
        social_analytics=CapabilityRoute(
            ProviderCapability.SOCIAL_ANALYTICS,
            social_analytics,
        ),
        risk=CapabilityRoute(
            ProviderCapability.RISK_SUMMARY,
            ("local", "rugcheck") if rugcheck_configured else ("local",),
            optional=False,
        ),
        wallet=CapabilityRoute(
            ProviderCapability.WALLET_ENRICHMENT,
            wallet_providers,
        ),
        narrative=CapabilityRoute(ProviderCapability.NARRATIVE, narrative_providers),
        alerts=CapabilityRoute(
            ProviderCapability.ALERT_DELIVERY,
            ("telegram",) if telegram_configured else (),
        ),
    )


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
    "FREE_FIRST_ROUTING_VERSION",
    "PROVIDER_ROUTING_VERSION",
    "CapabilityRoute",
    "FreeFirstRoutePlan",
    "build_free_first_route_plan",
    "ProviderHealthRouter",
    "ProviderRouteCandidate",
    "ProviderRouteDecision",
    "ProviderRouteState",
]
