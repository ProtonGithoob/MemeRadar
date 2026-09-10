"""Small provider composition root for the free-first runtime.

The application owns ports and routing policy; this module owns construction of
HTTP adapters and a bounded, ordered fallback seam.  It intentionally does not
turn providers into interchangeable feature claims: a fallback is attempted
only for a concrete adapter failure, while an explicitly unavailable
capability remains unavailable.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from memeradar_application.config import Settings
from memeradar_application.external_wallet import ExternalWalletIntelligencePort
from memeradar_application.provider_contracts import (
    MarketDataPort,
    NarrativePort,
    OnChainPort,
    ProviderRequestContext,
    QuotePort,
    RiskDataPort,
    SocialDataPort,
    SocialMetadataPort,
)
from memeradar_application.provider_routing import (
    FreeFirstRoutePlan,
    build_free_first_route_plan,
)
from memeradar_domain import Chain, TokenIdentity

from .birdeye import BirdeyeRestAdapter
from .dexscreener import DexScreenerAdapter
from .evm_rpc import EvmRpcAdapter
from .helius import HeliusRpcAdapter
from .narrative import (
    DisabledNarrativeAdapter,
    NarrativeRestAdapter,
    OllamaNarrativeAdapter,
)
from .robinhood import (
    ROBINHOOD_VERIFIED_LAUNCHPADS,
    RobinhoodLaunchpadDecoder,
    RobinhoodLaunchpadReconciler,
)
from .rugcheck import RugCheckRestAdapter
from .social import SocialRestAdapter
from .solana_rpc import SolanaRpcAdapter
from .telegram import TelegramCallAdapter
from .transport import CapabilityUnavailableError, ProviderError, ProviderTransport

LOGGER = logging.getLogger(__name__)


def _provider_name(value: object) -> str:
    name = getattr(value, "provider_name", None)
    if not isinstance(name, str) or not name.strip():
        raise TypeError("provider must expose a non-empty provider_name")
    return name.strip().lower()


class _BoundedFallback:
    """Ordered fallback state shared by concrete port wrappers."""

    def __init__(
        self,
        providers: Sequence[object],
        *,
        fallback_on_capability: bool = False,
    ) -> None:
        if isinstance(providers, str | bytes | bytearray):
            raise TypeError("providers must be a sequence")
        normalized = tuple(providers)
        if not normalized:
            raise ValueError("at least one provider is required")
        for provider in normalized:
            _provider_name(provider)
        self._providers = normalized
        self._fallback_on_capability = fallback_on_capability
        self.provider_name = "fallback:" + ",".join(_provider_name(item) for item in normalized)
        self.last_provider: str | None = None
        self.fallback_count = 0
        self.last_failures: tuple[tuple[str, str], ...] = ()

    async def _call(self, method_name: str, *args: object, **kwargs: object) -> object:
        failures: list[tuple[str, str]] = []
        self.last_provider = None
        self.fallback_count = 0
        for index, provider in enumerate(self._providers):
            operation = getattr(provider, method_name, None)
            if not callable(operation):
                raise TypeError(f"provider {_provider_name(provider)} lacks {method_name}")
            provider_name = _provider_name(provider)
            try:
                result = await operation(*args, **kwargs)
            except CapabilityUnavailableError as exc:
                failures.append((provider_name, type(exc).__name__))
                if not self._fallback_on_capability:
                    self.last_failures = tuple(failures)
                    raise
                if index == len(self._providers) - 1:
                    self.last_failures = tuple(failures)
                    raise
                self.fallback_count += 1
                LOGGER.info(
                    "provider_capability_unavailable",
                    extra={
                        "provider": provider_name,
                        "fallback_provider": _provider_name(self._providers[index + 1]),
                        "operation": method_name,
                    },
                )
            except ProviderError as exc:
                failures.append((provider_name, type(exc).__name__))
                if index == len(self._providers) - 1:
                    self.last_failures = tuple(failures)
                    raise
                self.fallback_count += 1
                LOGGER.info(
                    "provider_fallback",
                    extra={
                        "provider": provider_name,
                        "fallback_provider": _provider_name(self._providers[index + 1]),
                        "operation": method_name,
                        "error_class": type(exc).__name__,
                    },
                )
            else:
                self.last_provider = provider_name
                self.last_failures = tuple(failures)
                return result
        raise AssertionError("bounded provider fallback exhausted without a result")


class BoundedOnChainFallback(_BoundedFallback, OnChainPort):
    """At-most-once ordered fallback for standard on-chain reads."""

    async def enrich(self, request: Any) -> Sequence[Any]:
        return cast(Sequence[Any], await self._call("enrich", request))


class BoundedMarketDataFallback(_BoundedFallback, MarketDataPort):
    """At-most-once ordered fallback for normalized market snapshots."""

    async def snapshot(self, request: Any) -> Sequence[Any]:
        return cast(Sequence[Any], await self._call("snapshot", request))


class BoundedQuoteFallback(_BoundedFallback, QuotePort):
    """At-most-once ordered fallback for normalized reference quotes."""

    async def quote(self, request: Any) -> Any:
        return await self._call("quote", request)


class _UnavailableQuotePort(QuotePort):
    """Explicitly unavailable normalized quote seam for an unconfigured selector."""

    provider_name = "custom-unavailable"
    capabilities: frozenset[str] = frozenset()

    async def quote(self, request: Any) -> Any:
        del request
        raise CapabilityUnavailableError("selected custom quote provider is unavailable")


class BoundedSocialMetadataFallback(_BoundedFallback, SocialMetadataPort):
    """At-most-once ordered fallback for declared project links."""

    async def metadata(
        self,
        token: TokenIdentity,
        *,
        context: ProviderRequestContext,
    ) -> Any:
        return await self._call("metadata", token, context=context)


class BoundedNarrativeFallback(_BoundedFallback, NarrativePort):
    """Advisory narrative fallback; no result can authorize execution."""

    def __init__(self, providers: Sequence[object]) -> None:
        super().__init__(providers, fallback_on_capability=True)

    async def summarize(self, request: Any) -> Any:
        return await self._call("summarize", request)

    async def aclose(self) -> None:
        """Close narrative clients created behind this bounded fallback."""

        seen: set[int] = set()
        for provider in self._providers:
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            close = getattr(provider, "aclose", None)
            if callable(close):
                await close()


def _configured(value: str | None) -> bool:
    return value is not None and bool(value.strip())


@dataclass(slots=True)
class ProviderBundle:
    """Concrete provider graph created at the infrastructure composition root."""

    settings: Settings
    route_plan: FreeFirstRoutePlan
    solana_rpc: SolanaRpcAdapter
    bnb_rpc: EvmRpcAdapter | None
    robinhood_rpc: EvmRpcAdapter | None
    robinhood_launchpad_reconciler: RobinhoodLaunchpadReconciler | None
    chain: OnChainPort
    chain_routes: Mapping[str, OnChainPort]
    helius: HeliusRpcAdapter | None
    enhanced_asset_metadata: HeliusRpcAdapter | None
    dexscreener: DexScreenerAdapter
    market_data: MarketDataPort
    quote: QuotePort
    birdeye: BirdeyeRestAdapter | None
    rugcheck: RiskDataPort | None
    social_metadata: SocialMetadataPort | None
    social_analytics: SocialDataPort | None
    external_wallet: ExternalWalletIntelligencePort | None
    narrative: NarrativePort
    telegram: Any | None
    telegram_chat_id: str | None
    optional: Mapping[str, str] = field(default_factory=dict)
    _closed: bool = False

    @property
    def market(self) -> MarketDataPort:
        """Compatibility alias for callers that use the shorter port name."""

        return self.market_data

    def register_token(self, token: TokenIdentity) -> None:
        """Register an application token with adapters that resolve UUIDs locally."""

        self.dexscreener.register_token(token)
        if self.birdeye is not None:
            self.birdeye.register_token(token)

    def provenance_defaults(self) -> Mapping[str, str]:
        """Return safe route provenance labels for status/readiness surfaces."""

        return {
            "chain_rpc": _provider_name(self.chain),
            "market_data": _provider_name(self.market_data),
            "paper_quote": _provider_name(self.quote),
            "social_metadata": (
                "unavailable"
                if self.social_metadata is None
                else _provider_name(self.social_metadata)
            ),
            "wallet_intelligence": "local",
            "narrative": _provider_name(self.narrative),
        }

    async def aclose(self) -> None:
        """Close only clients owned by this bundle; safe to call repeatedly."""

        if self._closed:
            return
        self._closed = True
        seen: set[int] = set()
        for provider in (
            self.solana_rpc,
            self.bnb_rpc,
            self.robinhood_rpc,
            self.helius,
            self.dexscreener,
            self.birdeye,
            self.rugcheck,
            self.social_metadata,
            self.social_analytics,
            self.narrative,
            self.telegram,
        ):
            if provider is None or id(provider) in seen:
                continue
            seen.add(id(provider))
            close = getattr(provider, "aclose", None)
            if callable(close):
                await close()


def build_provider_bundle(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    transport: ProviderTransport | None = None,
    clock: Any | None = None,
    token_registry: Mapping[Any, TokenIdentity] | None = None,
    custom_quote_port: QuotePort | None = None,
    external_wallet_port: ExternalWalletIntelligencePort | None = None,
) -> ProviderBundle:
    """Construct the bounded free-first provider graph without making requests.

    Legacy/custom quote and external-wallet seams accept already-normalized
    application ports only.  A URL or API key by itself never creates an
    unreviewed HTTP adapter or bypasses the provider boundary.
    """

    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")
    helius_configured = _configured(settings.helius_rpc_url) and _configured(
        settings.helius_api_key
    )
    helius_stream_configured = helius_configured and (
        _configured(settings.helius_stream_url) or _configured(settings.solana_stream_url)
    )
    birdeye_configured = _configured(settings.birdeye_api_url) and _configured(
        settings.birdeye_api_key
    )
    rugcheck_configured = _configured(settings.rugcheck_api_url)
    external_social_configured = _configured(settings.social_api_url) and _configured(
        settings.social_api_key
    )
    external_narrative_configured = (
        settings.narrative_provider == "external"
        and _configured(settings.narrative_api_url)
        and urlsplit(settings.narrative_api_url).scheme.lower() == "https"
    )
    external_wallet_configured = external_wallet_port is not None
    custom_quote_configured = custom_quote_port is not None
    telegram_configured = (
        _configured(settings.telegram_api_url)
        and _configured(settings.telegram_bot_token)
        and _configured(settings.telegram_chat_id)
    )
    route_plan = build_free_first_route_plan(
        helius_configured=helius_configured,
        helius_stream_configured=helius_stream_configured,
        birdeye_configured=birdeye_configured,
        rugcheck_configured=rugcheck_configured,
        external_social_configured=external_social_configured,
        external_narrative_configured=external_narrative_configured,
        external_wallet_configured=external_wallet_configured,
        custom_quote_configured=custom_quote_configured,
        telegram_configured=telegram_configured,
        market_data_provider=settings.market_data_provider,
        paper_quote_provider=settings.paper_quote_provider,
        wallet_intelligence_provider=settings.wallet_intelligence_provider,
        social_metadata_provider=settings.social_metadata_provider,
        narrative_provider=settings.narrative_provider,
    )

    solana_rpc = SolanaRpcAdapter(
        settings.solana_rpc_url,
        api_key=None,
        client=client,
        transport=transport,
        clock=clock,
    )
    bnb_rpc = (
        EvmRpcAdapter(
            Chain.BNB,
            cast(str, settings.bnb_rpc_url),
            expected_chain_id=settings.bnb_chain_id,
            client=client,
            transport=transport,
            clock=clock,
        )
        if Chain.BNB.value in settings.enabled_chains and _configured(settings.bnb_rpc_url)
        else None
    )
    robinhood_rpc = (
        EvmRpcAdapter(
            Chain.ROBINHOOD,
            settings.robinhood_rpc_url,
            expected_chain_id=settings.robinhood_chain_id,
            client=client,
            transport=transport,
            clock=clock,
        )
        if Chain.ROBINHOOD.value in settings.enabled_chains
        and _configured(settings.robinhood_rpc_url)
        else None
    )
    helius = (
        HeliusRpcAdapter(
            cast(str, settings.helius_rpc_url),
            api_key=cast(str, settings.helius_api_key),
            client=client,
            transport=transport,
            clock=clock,
        )
        if helius_configured
        else None
    )
    chain_providers: list[OnChainPort] = []
    if helius is not None:
        chain_providers.append(helius)
    chain_providers.append(solana_rpc)
    chain: OnChainPort = (
        chain_providers[0]
        if len(chain_providers) == 1
        else BoundedOnChainFallback(chain_providers)
    )
    chain_routes: dict[str, OnChainPort] = {Chain.SOLANA.value: chain}
    if bnb_rpc is not None:
        chain_routes[Chain.BNB.value] = bnb_rpc
    if robinhood_rpc is not None:
        chain_routes[Chain.ROBINHOOD.value] = robinhood_rpc

    dexscreener = DexScreenerAdapter(
        settings.dexscreener_api_url,
        api_key=settings.dexscreener_api_key,
        client=client,
        transport=transport,
        clock=clock,
        token_registry=token_registry,
    )
    birdeye = (
        BirdeyeRestAdapter(
            cast(str, settings.birdeye_api_url),
            api_key=cast(str, settings.birdeye_api_key),
            client=client,
            transport=transport,
            clock=clock,
            token_registry=token_registry,
        )
        if birdeye_configured
        else None
    )
    market_providers: list[MarketDataPort] = []
    if settings.market_data_provider == "birdeye" and birdeye is not None:
        market_providers.append(birdeye)
    market_providers.append(dexscreener)
    if settings.market_data_provider != "birdeye" and birdeye is not None:
        market_providers.append(birdeye)
    market_data: MarketDataPort = (
        market_providers[0]
        if len(market_providers) == 1
        else BoundedMarketDataFallback(market_providers)
    )

    # The existing Birdeye adapter is intentionally not cast to QuotePort: it
    # exposes market snapshots, while DexScreener is the normalized reference
    # quote implementation. Legacy URL/key variables remain available for a
    # reviewed adapter, but never cause raw HTTP from paper logic.
    quote_providers: list[QuotePort] = []
    if settings.paper_quote_provider == "custom":
        if custom_quote_port is not None:
            quote_providers.append(custom_quote_port)
        else:
            quote_providers.append(_UnavailableQuotePort())
    else:
        quote_providers.append(dexscreener)
        if custom_quote_port is not None:
            quote_providers.append(custom_quote_port)
    quote: QuotePort = (
        quote_providers[0]
        if len(quote_providers) == 1
        else BoundedQuoteFallback(quote_providers)
    )

    rugcheck = (
        RugCheckRestAdapter(
            cast(str, settings.rugcheck_api_url),
            api_key=settings.rugcheck_api_key,
            client=client,
            transport=transport,
            clock=clock,
        )
        if rugcheck_configured
        else None
    )
    social_metadata: SocialMetadataPort | None = (
        dexscreener if settings.social_metadata_provider == "dexscreener" else None
    )
    social_analytics: SocialDataPort | None = (
        SocialRestAdapter(
            cast(str, settings.social_api_url),
            api_key=cast(str, settings.social_api_key),
            client=client,
            transport=transport,
            clock=clock,
        )
        if external_social_configured
        else None
    )

    if settings.narrative_provider == "disabled":
        narrative: NarrativePort = DisabledNarrativeAdapter()
    elif settings.narrative_provider == "external":
        if external_narrative_configured:
            external = NarrativeRestAdapter(
                settings.narrative_api_url,
                api_key=settings.narrative_api_key,
                client=client,
                transport=transport,
                clock=clock,
            )
            narrative = BoundedNarrativeFallback((external, DisabledNarrativeAdapter()))
        else:
            narrative = DisabledNarrativeAdapter()
    else:
        ollama = OllamaNarrativeAdapter(
            settings.narrative_api_url,
            model=settings.narrative_model,
            api_key=settings.narrative_api_key,
            client=client,
            transport=transport,
            clock=clock,
        )
        narrative = BoundedNarrativeFallback((ollama, DisabledNarrativeAdapter()))

    telegram = (
        TelegramCallAdapter(
            cast(str, settings.telegram_api_url),
            bot_token=cast(str, settings.telegram_bot_token),
            client=client,
            transport=transport,
            clock=clock,
        )
        if telegram_configured
        else None
    )

    optional_statuses = {
        "bnb_rpc": "CONFIGURED" if bnb_rpc is not None else "UNCONFIGURED_OPTIONAL",
        "robinhood_rpc": (
            "CONFIGURED" if robinhood_rpc is not None else "UNCONFIGURED_OPTIONAL"
        ),
        "helius": "CONFIGURED" if helius is not None else "UNCONFIGURED_OPTIONAL",
        "birdeye": "CONFIGURED" if birdeye is not None else "UNCONFIGURED_OPTIONAL",
        "rugcheck": "CONFIGURED" if rugcheck is not None else "UNCONFIGURED_OPTIONAL",
        "social_analytics": (
            "CONFIGURED" if social_analytics is not None else "UNCONFIGURED_OPTIONAL"
        ),
        "external_wallet": (
            "CONFIGURED" if external_wallet_port is not None else "UNCONFIGURED_OPTIONAL"
        ),
        "ollama": (
            "DISABLED"
            if settings.narrative_provider == "disabled"
            else "CONFIGURED"
            if settings.narrative_provider == "ollama" and settings.narrative_model
            else "OPTIONAL_UNAVAILABLE"
            if settings.narrative_provider == "ollama"
            else "UNCONFIGURED_OPTIONAL"
        ),
        "narrative": (
            "CONFIGURED"
            if settings.narrative_provider == "external" and external_narrative_configured
            else "UNCONFIGURED_OPTIONAL"
            if settings.narrative_provider == "external"
            else "DISABLED"
            if settings.narrative_provider == "disabled"
            else "UNCONFIGURED_OPTIONAL"
        ),
        "telegram": "CONFIGURED" if telegram is not None else "UNCONFIGURED_OPTIONAL",
    }

    return ProviderBundle(
        settings=settings,
        route_plan=route_plan,
        solana_rpc=solana_rpc,
        bnb_rpc=bnb_rpc,
        robinhood_rpc=robinhood_rpc,
        robinhood_launchpad_reconciler=(
            None
            if robinhood_rpc is None
            else RobinhoodLaunchpadReconciler(
                RobinhoodLaunchpadDecoder(ROBINHOOD_VERIFIED_LAUNCHPADS), robinhood_rpc
            )
        ),
        chain=chain,
        chain_routes=chain_routes,
        helius=helius,
        enhanced_asset_metadata=helius,
        dexscreener=dexscreener,
        market_data=market_data,
        quote=quote,
        birdeye=birdeye,
        rugcheck=rugcheck,
        social_metadata=social_metadata,
        social_analytics=social_analytics,
        external_wallet=external_wallet_port,
        narrative=narrative,
        telegram=telegram,
        telegram_chat_id=settings.telegram_chat_id if telegram is not None else None,
        optional=optional_statuses,
    )


def build_free_first_provider_bundle(
    settings: Settings,
    **kwargs: Any,
) -> ProviderBundle:
    """Compatibility name for the explicit free-first composition entrypoint."""

    return build_provider_bundle(settings, **kwargs)


FreeFirstProviderBundle = ProviderBundle


__all__ = [
    "BoundedMarketDataFallback",
    "BoundedNarrativeFallback",
    "BoundedOnChainFallback",
    "BoundedQuoteFallback",
    "BoundedSocialMetadataFallback",
    "ProviderBundle",
    "FreeFirstProviderBundle",
    "build_free_first_provider_bundle",
    "build_provider_bundle",
]
