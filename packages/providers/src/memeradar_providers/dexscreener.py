"""Keyless DexScreener market, reference-quote and social-metadata adapter.

DexScreener is intentionally kept at the market boundary.  This adapter does
not expose Solana transaction history, wallet history, holder data, security
audits, websocket streams, DAS/enhanced asset metadata or social analytics.
Those capabilities remain owned by their existing provider or local ports.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

import httpx

from memeradar_application.provider_contracts import (
    MarketDataPort,
    MarketDataRequest,
    ProviderRequestContext,
    QuoteMarketContext,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
    SocialMetadata,
    SocialMetadataPort,
)
from memeradar_domain import (
    Chain,
    Freshness,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
    TokenIdentity,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import ensure_utc, require_text, to_decimal

from .transport import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RateLimitSnapshot,
)

Clock = Callable[[], datetime]

DEXSCREENER_PROVIDER = "dexscreener"
DEXSCREENER_PARSER_VERSION = "dexscreener-market-v1"
DEXSCREENER_CHAIN = "solana"
DEXSCREENER_TOKEN_PAIRS_PATH = "/token-pairs/v1/solana"
DEXSCREENER_CHAIN_BY_DOMAIN: Mapping[Chain, str] = {
    Chain.SOLANA: "solana",
    Chain.BNB: "bsc",
    Chain.ROBINHOOD: "robinhood",
}
_DEXSCREENER_CHAIN_ALIASES: Mapping[Chain, frozenset[str]] = {
    Chain.SOLANA: frozenset({"solana"}),
    Chain.BNB: frozenset({"bnb", "bsc", "binance-smart-chain"}),
    Chain.ROBINHOOD: frozenset({"robinhood", "robinhood-chain"}),
}
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "token",
}
_MISSING = object()

# Public Solana quote assets.  These are used only for deterministic pair
# ranking and for choosing the correct DexScreener price field.
SOLANA_NATIVE_MINT = "So11111111111111111111111111111111111111112"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
_STABLE_QUOTE_MINTS = frozenset({SOLANA_USDC_MINT, SOLANA_USDT_MINT})
_QUOTE_ASSET_ORDER = {
    SOLANA_USDC_MINT: 0,
    SOLANA_USDT_MINT: 1,
    SOLANA_NATIVE_MINT: 2,
}
_STABLE_QUOTE_SYMBOLS = frozenset({"usdc", "usdt", "busd", "dai", "usde"})
_NATIVE_QUOTE_SYMBOLS = frozenset({"sol", "wsol", "bnb", "wbnb", "eth", "weth"})


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        if name in payload:
            return payload[name]
    return _MISSING


def _mapping(value: object, field: str) -> Mapping[str, object] | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"provider {field} was invalid")
    return value


def _text(value: object, field: str, *, max_length: int = 256) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ProviderSchemaError(f"provider {field} was invalid")
    try:
        return require_text(value, field, max_length=max_length)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"provider {field} was invalid") from exc


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, field)
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 0 else None


def _optional_nonnegative_int(value: object, field: str) -> int | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value


def _optional_timestamp(value: object, field: str, *, observed_at: datetime) -> datetime | None:
    if value is _MISSING or value is None:
        return None
    try:
        normalized = to_decimal(value, field)
    except (TypeError, ValueError):
        return None
    if normalized < 0:
        return None
    # DexScreener documents pairCreatedAt as Unix milliseconds.  Accepting
    # seconds as a compatibility convenience keeps fixture/replay inputs
    # useful without changing the normalized timestamp semantics.
    seconds = float(normalized)
    if seconds >= 10_000_000_000:
        seconds /= 1000
    if not math.isfinite(seconds):
        return None
    try:
        timestamp = datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return timestamp if timestamp <= observed_at else None


def _safe_address(value: object, field: str, chain: Chain = Chain.SOLANA) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return require_chain_address(value, chain, field)
    except (TypeError, ValueError):
        return None


def _nested_mapping(payload: Mapping[str, object], field: str) -> Mapping[str, object] | None:
    value = payload.get(field, _MISSING)
    return _mapping(value, field)


def _nested_decimal(payload: Mapping[str, object], field: str, *names: str) -> Decimal | None:
    nested = _nested_mapping(payload, field)
    if nested is None:
        return None
    return _optional_decimal(_field(nested, *names), f"{field}.{names[0]}")


def _nested_int(payload: Mapping[str, object], field: str, *names: str) -> int | None:
    nested = _nested_mapping(payload, field)
    if nested is None:
        return None
    return _optional_nonnegative_int(_field(nested, *names), f"{field}.{names[0]}")


def _link(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        normalized = require_text(value, "link", max_length=1024)
    except (TypeError, ValueError):
        return None
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        return None
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
            return None
    return normalized


@dataclass(frozen=True, slots=True)
class DexScreenerPair:
    """Provider-normalized pair record retained inside the adapter boundary."""

    chain: str
    dex_id: str
    pair_address: str
    base_mint: str
    base_symbol: str | None
    quote_mint: str
    quote_symbol: str | None
    price_usd: Decimal | None
    price_native: Decimal | None
    liquidity_usd: Decimal | None
    fdv: Decimal | None
    market_cap: Decimal | None
    pair_created_at: datetime | None
    volume_5m: Decimal | None
    volume_1h: Decimal | None
    volume_6h: Decimal | None
    volume_24h: Decimal | None
    transactions: Mapping[str, Mapping[str, int | None]]
    price_change: Mapping[str, Decimal | None]
    websites: tuple[str, ...]
    socials: Mapping[str, str]
    raw: Mapping[str, object]


def _parse_transactions(value: object) -> Mapping[str, Mapping[str, int | None]]:
    if value is _MISSING or value is None:
        return {}
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Mapping[str, int | None]] = {}
    for window in ("m5", "h1", "h6", "h24"):
        nested = value.get(window)
        if not isinstance(nested, Mapping):
            continue
        result[window] = {
            "buys": _optional_nonnegative_int(nested.get("buys", _MISSING), f"txns.{window}.buys"),
            "sells": _optional_nonnegative_int(
                nested.get("sells", _MISSING), f"txns.{window}.sells"
            ),
        }
    return result


def _parse_price_change(value: object) -> Mapping[str, Decimal | None]:
    if value is _MISSING or value is None or not isinstance(value, Mapping):
        return {}
    return {
        window: _optional_decimal(value.get(window, _MISSING), f"priceChange.{window}")
        for window in ("m5", "h1", "h6", "h24")
        if window in value
    }


def _parse_links(info: Mapping[str, object] | None) -> tuple[tuple[str, ...], Mapping[str, str]]:
    if info is None:
        return (), {}
    websites: list[str] = []
    raw_websites = info.get("websites", ())
    if isinstance(raw_websites, Sequence) and not isinstance(raw_websites, str | bytes | bytearray):
        for item in raw_websites[:32]:
            item_mapping = item if isinstance(item, Mapping) else {}
            link = _link(item_mapping.get("url", _MISSING))
            if link is not None and link not in websites:
                websites.append(link)
    socials: dict[str, str] = {}
    raw_socials = info.get("socials", ())
    if isinstance(raw_socials, Sequence) and not isinstance(raw_socials, str | bytes | bytearray):
        for item in raw_socials[:32]:
            item_mapping = item if isinstance(item, Mapping) else {}
            kind = item_mapping.get("type", _MISSING)
            link = _link(item_mapping.get("url", _MISSING))
            if not isinstance(kind, str) or link is None:
                continue
            try:
                key = require_text(kind, "social type", max_length=64).lower()
            except (TypeError, ValueError):
                continue
            socials.setdefault(key, link)
    return tuple(websites), socials


def _parse_pair(
    value: object,
    *,
    observed_at: datetime,
    chain: Chain = Chain.SOLANA,
) -> DexScreenerPair | None:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError("provider pair item was invalid")
    normalized_chain = normalize_chain(chain)
    provider_chain = _text(
        _field(value, "chainId", "chain_id", "chain"),
        "chain_id",
        max_length=32,
    )
    if (
        provider_chain is None
        or provider_chain.lower() not in _DEXSCREENER_CHAIN_ALIASES[normalized_chain]
    ):
        return None
    pair_address = _safe_address(
        value.get("pairAddress", _MISSING),
        "pair_address",
        normalized_chain,
    )
    base = _mapping(value.get("baseToken", _MISSING), "baseToken")
    quote = _mapping(value.get("quoteToken", _MISSING), "quoteToken")
    if pair_address is None or base is None or quote is None:
        return None
    base_mint = _safe_address(
        base.get("address", _MISSING),
        "base_mint",
        normalized_chain,
    )
    quote_mint = _safe_address(
        quote.get("address", _MISSING),
        "quote_mint",
        normalized_chain,
    )
    if base_mint is None or quote_mint is None or base_mint == quote_mint:
        return None
    websites, socials = _parse_links(_mapping(value.get("info", _MISSING), "info"))
    return DexScreenerPair(
        chain=normalized_chain.value,
        dex_id=_text(value.get("dexId", _MISSING), "dex_id", max_length=64) or "unknown",
        pair_address=pair_address,
        base_mint=base_mint,
        base_symbol=_text(base.get("symbol", _MISSING), "base_symbol", max_length=64),
        quote_mint=quote_mint,
        quote_symbol=_text(quote.get("symbol", _MISSING), "quote_symbol", max_length=64),
        price_usd=_optional_decimal(value.get("priceUsd", _MISSING), "price_usd"),
        price_native=_optional_decimal(value.get("priceNative", _MISSING), "price_native"),
        liquidity_usd=_nested_decimal(value, "liquidity", "usd"),
        fdv=_optional_decimal(value.get("fdv", _MISSING), "fdv"),
        market_cap=_optional_decimal(value.get("marketCap", _MISSING), "market_cap"),
        pair_created_at=_optional_timestamp(
            value.get("pairCreatedAt", _MISSING),
            "pair_created_at",
            observed_at=observed_at,
        ),
        volume_5m=_nested_decimal(value, "volume", "m5"),
        volume_1h=_nested_decimal(value, "volume", "h1"),
        volume_6h=_nested_decimal(value, "volume", "h6"),
        volume_24h=_nested_decimal(value, "volume", "h24"),
        transactions=_parse_transactions(value.get("txns", _MISSING)),
        price_change=_parse_price_change(value.get("priceChange", _MISSING)),
        websites=websites,
        socials=socials,
        raw=dict(value),
    )


def _parse_pairs(
    value: object,
    *,
    observed_at: datetime,
    chain: Chain = Chain.SOLANA,
) -> tuple[DexScreenerPair, ...]:
    raw_pairs: object = (
        value.get("pairs", _MISSING) if isinstance(value, Mapping) else value
    )
    if not isinstance(raw_pairs, Sequence) or isinstance(raw_pairs, str | bytes | bytearray):
        raise ProviderSchemaError("provider token-pairs response was invalid")
    pairs_by_address: dict[str, DexScreenerPair] = {}
    for item in raw_pairs[:500]:
        pair = _parse_pair(item, observed_at=observed_at, chain=chain)
        if pair is not None:
            previous = pairs_by_address.get(pair.pair_address)
            if previous is None or _duplicate_pair_rank(pair) < _duplicate_pair_rank(previous):
                pairs_by_address[pair.pair_address] = pair
    return tuple(pairs_by_address[address] for address in sorted(pairs_by_address))


def _duplicate_pair_rank(pair: DexScreenerPair) -> tuple[object, ...]:
    """Choose one deterministic record when an upstream response repeats a pair."""

    liquidity = pair.liquidity_usd or Decimal("0")
    created = pair.pair_created_at.timestamp() if pair.pair_created_at is not None else 0.0
    return (
        0 if liquidity > 0 else 1,
        -liquidity,
        -created,
        pair.dex_id,
        _payload_hash(pair.raw),
    )


def _asset_kind(
    mint: str,
    symbol: str | None,
    chain: Chain,
) -> str | None:
    if chain is Chain.SOLANA:
        if mint in _STABLE_QUOTE_MINTS:
            return "stable"
        if mint == SOLANA_NATIVE_MINT:
            return "native"
    normalized_symbol = symbol.strip().lower() if symbol is not None else ""
    if normalized_symbol in _STABLE_QUOTE_SYMBOLS:
        return "stable"
    if normalized_symbol in _NATIVE_QUOTE_SYMBOLS:
        return "native"
    return None


def _quote_asset_rank(
    pair: DexScreenerPair,
    token_mint: str,
    chain: Chain = Chain.SOLANA,
) -> int:
    quote_mint = pair.quote_mint if pair.base_mint == token_mint else pair.base_mint
    quote_symbol = pair.quote_symbol if pair.base_mint == token_mint else pair.base_symbol
    if quote_mint in _QUOTE_ASSET_ORDER:
        return _QUOTE_ASSET_ORDER[quote_mint]
    kind = _asset_kind(quote_mint, quote_symbol, chain)
    return 0 if kind == "stable" else 2 if kind == "native" else 3


def _pair_rank(
    pair: DexScreenerPair,
    *,
    token_mint: str,
    chain: Chain = Chain.SOLANA,
) -> tuple[object, ...]:
    liquidity = pair.liquidity_usd
    created = pair.pair_created_at.timestamp() if pair.pair_created_at is not None else 0.0
    return (
        0 if liquidity is not None and liquidity > 0 else 1,
        _quote_asset_rank(pair, token_mint, chain),
        -(liquidity or Decimal("0")),
        -created,
        pair.pair_address,
        pair.dex_id,
    )


def _market_price_usd(
    pair: DexScreenerPair,
    token_mint: str,
    chain: Chain = Chain.SOLANA,
) -> Decimal | None:
    if pair.base_mint == token_mint:
        return pair.price_usd if pair.price_usd is not None and pair.price_usd > 0 else None
    if pair.quote_mint == token_mint:
        if chain is Chain.SOLANA and token_mint != SOLANA_NATIVE_MINT:
            return None
        if (
            _asset_kind(pair.base_mint, pair.base_symbol, chain) is not None
            and pair.price_usd is not None
            and pair.price_usd > 0
            and pair.price_native is not None
            and pair.price_native > 0
        ):
            return pair.price_usd / pair.price_native
    return None


def _quote_rate(
    pair: DexScreenerPair,
    input_mint: str,
    output_mint: str,
    chain: Chain = Chain.SOLANA,
) -> Decimal | None:
    if pair.base_mint == input_mint and pair.quote_mint == output_mint:
        kind = _asset_kind(pair.quote_mint, pair.quote_symbol, chain)
        if kind == "stable":
            return pair.price_usd if pair.price_usd is not None and pair.price_usd > 0 else None
        if kind == "native":
            return (
                pair.price_native
                if pair.price_native is not None and pair.price_native > 0
                else None
            )
        return None
    if pair.quote_mint == input_mint and pair.base_mint == output_mint:
        kind = _asset_kind(pair.quote_mint, pair.quote_symbol, chain)
        if kind == "stable":
            rate = pair.price_usd
        elif kind == "native":
            rate = pair.price_native
        else:
            return None
        if rate is None or rate <= 0:
            return None
        return Decimal("1") / rate
    return None


def _raw_links(pairs: Sequence[DexScreenerPair]) -> tuple[tuple[str, ...], Mapping[str, str]]:
    websites: list[str] = []
    socials: dict[str, str] = {}
    for pair in pairs:
        for website in pair.websites:
            if website not in websites:
                websites.append(website)
        for key, link in pair.socials.items():
            socials.setdefault(key, link)
    return tuple(websites), socials


@dataclass(frozen=True, slots=True)
class _MetadataCacheEntry:
    pairs: tuple[DexScreenerPair, ...]
    expires_at: datetime


class DexScreenerAdapter(MarketDataPort, QuotePort, SocialMetadataPort):
    """Read-only DexScreener adapter with deterministic pair selection."""

    provider_name = DEXSCREENER_PROVIDER
    capabilities = frozenset(
        {
            "market_snapshot",
            "market_data",
            "market_quote",
            "quote",
            "pair_discovery",
            "social_metadata",
        }
    )

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        token_registry: Mapping[UUID, TokenIdentity] | None = None,
        parser_version: str = DEXSCREENER_PARSER_VERSION,
        quote_ttl_seconds: float = 30.0,
        metadata_ttl_seconds: float = 300.0,
        max_concurrency: int = 2,
        max_metadata_cache_entries: int = 512,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=DEXSCREENER_PROVIDER)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._quote_ttl = self._duration(quote_ttl_seconds, "quote_ttl_seconds", maximum=3600.0)
        self._metadata_ttl = self._duration(
            metadata_ttl_seconds,
            "metadata_ttl_seconds",
            maximum=86_400.0,
        )
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool):
            raise TypeError("max_concurrency must be an integer")
        if not 1 <= max_concurrency <= 16:
            raise ValueError("max_concurrency must be between 1 and 16")
        if (
            not isinstance(max_metadata_cache_entries, int)
            or isinstance(max_metadata_cache_entries, bool)
            or not 1 <= max_metadata_cache_entries <= 10_000
        ):
            raise ValueError("max_metadata_cache_entries must be between 1 and 10000")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._token_registry = dict(token_registry or {})
        self._metadata_cache: dict[tuple[str, str], _MetadataCacheEntry] = {}
        self._max_metadata_cache_entries = max_metadata_cache_entries
        self._last_rate_limit: RateLimitSnapshot | None = None
        self.metadata_cache_hits = 0

    @staticmethod
    def _duration(value: float, field: str, *, maximum: float) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{field} must be a number")
        normalized = float(value)
        if not math.isfinite(normalized) or not 0 < normalized <= maximum:
            raise ValueError(f"{field} must be finite and between 0 and {maximum}")
        return normalized

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        normalized = require_text(base_url, "base_url", max_length=512)
        parsed = urlsplit(normalized)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("base_url must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("base_url must not contain credentials or a fragment")
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
                raise ValueError("base_url must not contain credential query parameters")
        return normalized.rstrip("/")

    def __repr__(self) -> str:
        return (
            f"DexScreenerAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> DexScreenerAdapter:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def last_rate_limit(self) -> RateLimitSnapshot | None:
        return self._last_rate_limit

    def register_token(self, token: TokenIdentity) -> None:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        self._token_registry[token.id] = token

    def _now_pair(self) -> tuple[datetime, datetime]:
        now = ensure_utc(self._clock(), "observed_at")
        return now, now

    def _timeout_for(self, context: ProviderRequestContext) -> float:
        if context.deadline_at is None:
            return self._transport.timeouts.overall_seconds
        remaining = (
            ensure_utc(context.deadline_at, "deadline_at") - ensure_utc(self._clock(), "now")
        ).total_seconds()
        if remaining <= 0:
            raise ProviderTimeoutError("provider request deadline expired")
        return min(remaining, self._transport.timeouts.overall_seconds)

    @staticmethod
    def _header_float(headers: httpx.Headers, name: str) -> float | None:
        value = headers.get(name)
        if value is None:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) and parsed >= 0 else None

    @classmethod
    def _rate_limit_snapshot(cls, headers: httpx.Headers) -> RateLimitSnapshot | None:
        def nonnegative_int(name: str) -> int | None:
            value = headers.get(name)
            if value is None:
                return None
            try:
                parsed = int(value)
            except ValueError:
                return None
            return parsed if parsed >= 0 else None

        limit = nonnegative_int("x-ratelimit-limit")
        remaining = nonnegative_int("x-ratelimit-remaining")
        if limit is not None and remaining is not None and remaining > limit:
            remaining = limit
        reset_at: datetime | None = None
        reset_epoch = cls._header_float(headers, "x-ratelimit-reset")
        if reset_epoch is not None:
            try:
                reset_at = datetime.fromtimestamp(reset_epoch, UTC)
            except (OverflowError, OSError, ValueError):
                reset_at = None
        retry_after = cls._header_float(headers, "retry-after")
        if retry_after is not None and retry_after > 86_400:
            retry_after = None
        if limit is None and remaining is None and reset_at is None and retry_after is None:
            return None
        return RateLimitSnapshot(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
        )

    async def _get_pairs(
        self,
        mint: str,
        *,
        context: ProviderRequestContext,
        chain: Chain = Chain.SOLANA,
        use_metadata_cache: bool = False,
    ) -> tuple[DexScreenerPair, ...]:
        normalized_chain = normalize_chain(chain)
        normalized_mint = require_chain_address(mint, normalized_chain, "mint")
        cache_key = (normalized_chain.value, normalized_mint)
        now = ensure_utc(self._clock(), "observed_at")
        cached = self._metadata_cache.get(cache_key)
        if use_metadata_cache and cached is not None and now < cached.expires_at:
            self.metadata_cache_hits += 1
            return cached.pairs
        path = (
            f"/token-pairs/v1/{DEXSCREENER_CHAIN_BY_DOMAIN[normalized_chain]}"
            f"/{normalized_mint}"
        )
        url = f"{self._base_url}{path}"
        headers = {
            "accept": "application/json",
            "x-correlation-id": context.correlation_id,
        }
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        async def operation() -> object:
            try:
                response = await self._client.get(
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(
                        self._transport.timeouts.overall_seconds,
                        connect=self._transport.timeouts.connect_seconds,
                        read=self._transport.timeouts.read_seconds,
                        write=self._transport.timeouts.write_seconds,
                        pool=self._transport.timeouts.connect_seconds,
                    ),
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError("provider request timed out") from exc
            except httpx.TransportError as exc:
                raise ProviderUnavailableError("provider transport failed") from exc
            snapshot = self._rate_limit_snapshot(response.headers)
            if snapshot is not None:
                self._last_rate_limit = snapshot
                self._transport.rate_limiter.update(snapshot)
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                raise ProviderRateLimitedError(self._header_float(response.headers, "retry-after"))
            if response.status_code == 408:
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderSchemaError("provider response was not valid JSON") from exc

        async with self._semaphore:
            raw = await self._transport.execute(
                operation,
                timeout_seconds=self._timeout_for(context),
            )
        observed_at = ensure_utc(self._clock(), "observed_at")
        pairs = _parse_pairs(raw, observed_at=observed_at, chain=normalized_chain)
        if use_metadata_cache:
            if len(self._metadata_cache) >= self._max_metadata_cache_entries:
                oldest = min(
                    self._metadata_cache,
                    key=lambda key: self._metadata_cache[key].expires_at,
                )
                del self._metadata_cache[oldest]
            self._metadata_cache[cache_key] = _MetadataCacheEntry(
                pairs=pairs,
                expires_at=observed_at + timedelta(seconds=self._metadata_ttl),
            )
        return pairs

    def _provenance(self, source_id: str, observed_at: datetime, raw: object) -> Provenance:
        return Provenance(
            provider=DEXSCREENER_PROVIDER,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=self._parser_version,
            raw_payload_hash=_payload_hash(raw),
        )

    @staticmethod
    def _select_market_pair(
        pairs: Sequence[DexScreenerPair],
        token_mint: str,
        chain: Chain = Chain.SOLANA,
    ) -> DexScreenerPair:
        eligible = [
            pair
            for pair in pairs
            if (pair.base_mint == token_mint or pair.quote_mint == token_mint)
            and _market_price_usd(pair, token_mint, chain) is not None
        ]
        if not eligible:
            raise ProviderSchemaError("provider returned no eligible market pair")
        return min(
            eligible,
            key=lambda pair: _pair_rank(pair, token_mint=token_mint, chain=chain),
        )

    @staticmethod
    def _select_quote_pair(
        pairs: Sequence[DexScreenerPair],
        input_mint: str,
        output_mint: str,
        chain: Chain = Chain.SOLANA,
    ) -> tuple[DexScreenerPair, Decimal]:
        eligible: list[tuple[DexScreenerPair, Decimal]] = []
        for pair in pairs:
            if pair.liquidity_usd is None or pair.liquidity_usd <= 0:
                continue
            rate = _quote_rate(pair, input_mint, output_mint, chain)
            if rate is not None and rate > 0:
                eligible.append((pair, rate))
        if not eligible:
            raise ProviderSchemaError("provider returned no eligible Solana quote pair")
        pair, rate = min(
            eligible,
            key=lambda item: _pair_rank(item[0], token_mint=output_mint, chain=chain),
        )
        return pair, rate

    @staticmethod
    def _market_payload(pair: DexScreenerPair, token_mint: str) -> dict[str, object]:
        price_usd = _market_price_usd(pair, token_mint, normalize_chain(pair.chain))
        assert price_usd is not None
        transactions = {
            window: dict(values) for window, values in pair.transactions.items()
        }
        return {
            "address": token_mint,
            "mint_address": token_mint,
            "chain": pair.chain,
            "pair_address": pair.pair_address,
            "venue": pair.dex_id,
            "dex_id": pair.dex_id,
            "base_mint": pair.base_mint,
            "base_symbol": pair.base_symbol,
            "quote_mint": pair.quote_mint,
            "quote_symbol": pair.quote_symbol,
            "price": price_usd,
            "price_usd": price_usd,
            "price_native": pair.price_native,
            "liquidity": pair.liquidity_usd,
            "liquidity_usd": pair.liquidity_usd,
            "volume_5m_usd": pair.volume_5m,
            "volume_1h_usd": pair.volume_1h,
            "volume_6h_usd": pair.volume_6h,
            "volume_24h": pair.volume_24h,
            "volume_24h_usd": pair.volume_24h,
            "transactions": transactions,
            "price_change": dict(pair.price_change),
            "fdv": pair.fdv,
            "market_cap": pair.market_cap,
            "pair_created_at": (
                None
                if pair.pair_created_at is None
                else pair.pair_created_at.isoformat()
            ),
            "websites": pair.websites,
            "socials": dict(pair.socials),
        }

    async def snapshot(self, request: MarketDataRequest) -> Sequence[Observation]:
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be a MarketDataRequest")
        if request.pool_ids:
            raise ValueError("DexScreener resolves token pairs, not opaque pool UUIDs")
        observations: list[Observation] = []
        for token_id in request.token_ids:
            token = self._token_registry.get(token_id)
            if token is None:
                raise ValueError(f"token registry has no token for {token_id}")
            observed_at, ingested_at = self._now_pair()
            chain = normalize_chain(token.chain)
            pairs = await self._get_pairs(
                token.address,
                context=request.context,
                chain=chain,
            )
            try:
                pair = self._select_market_pair(pairs, token.address, chain)
            except ProviderSchemaError:
                if chain is Chain.SOLANA:
                    raise
                observations.append(
                    Observation(
                        kind="market.market_snapshot",
                        provenance=self._provenance(
                            f"/token-pairs/v1/{DEXSCREENER_CHAIN_BY_DOMAIN[chain]}"
                            f"/{token.address}",
                            observed_at,
                            {"pair_count": len(pairs)},
                        ),
                        occurred_at=None,
                        observed_at=observed_at,
                        ingested_at=ingested_at,
                        quality_state=QualityState.UNKNOWN,
                        normalized_payload={
                            "address": token.address,
                            "mint_address": token.address,
                            "chain": chain.value,
                            "coverage_state": "UNKNOWN",
                            "collection_mode": "PRODUCTION",
                            "pair_address": None,
                            "liquidity_usd": None,
                            "price_usd": None,
                        },
                        token_id=token.id,
                    )
                )
                continue
            quality = (
                QualityState.FRESH
                if pair.liquidity_usd is not None and pair.liquidity_usd > 0
                else QualityState.UNKNOWN
            )
            observations.append(
                Observation(
                    kind="market.market_snapshot",
                    provenance=self._provenance(
                        f"/token-pairs/v1/{DEXSCREENER_CHAIN_BY_DOMAIN[chain]}"
                        f"/{token.address}:{pair.pair_address}",
                        observed_at,
                        pair.raw,
                    ),
                    occurred_at=pair.pair_created_at,
                    observed_at=observed_at,
                    ingested_at=ingested_at,
                    quality_state=quality,
                    normalized_payload={
                        **self._market_payload(pair, token.address),
                        "collection_mode": "PRODUCTION",
                        "event_time_quality": (
                            "EXACT" if pair.pair_created_at is not None else "UNKNOWN"
                        ),
                    },
                    token_id=token.id,
                )
            )
        return tuple(observations)

    async def quote(self, request: QuoteRequest) -> QuoteSnapshot:
        if not isinstance(request, QuoteRequest):
            raise TypeError("request must be a QuoteRequest")
        chain = normalize_chain(request.chain)
        primary_mint = (
            request.output_mint
            if chain is Chain.SOLANA and request.input_mint in _QUOTE_ASSET_ORDER
            else request.input_mint
        )
        pairs = await self._get_pairs(
            primary_mint,
            context=request.context,
            chain=chain,
        )
        try:
            pair, rate = self._select_quote_pair(
                pairs,
                request.input_mint,
                request.output_mint,
                chain,
            )
        except ProviderSchemaError:
            alternate_mint = (
                request.input_mint
                if primary_mint == request.output_mint
                else request.output_mint
            )
            if alternate_mint == primary_mint:
                raise
            pairs = await self._get_pairs(
                alternate_mint,
                context=request.context,
                chain=chain,
            )
            pair, rate = self._select_quote_pair(
                pairs,
                request.input_mint,
                request.output_mint,
                chain,
            )
        observed_at, _ = self._now_pair()
        input_amount = to_decimal(request.amount, "amount")
        output_amount = input_amount * rate
        pair_created_at = pair.pair_created_at
        assert pair.liquidity_usd is not None
        context = QuoteMarketContext(
            chain=chain,
            pair_address=pair.pair_address,
            base_mint=pair.base_mint,
            quote_mint=pair.quote_mint,
            liquidity_usd=pair.liquidity_usd,
            pair_created_at=pair_created_at,
        )
        return QuoteSnapshot(
            provenance=self._provenance(
                f"{DEXSCREENER_TOKEN_PAIRS_PATH}/{primary_mint}:{pair.pair_address}",
                observed_at,
                pair.raw,
            ),
            input_mint=request.input_mint,
            output_mint=request.output_mint,
            input_amount=request.amount,
            output_amount=output_amount,
            price_impact_bps=Decimal("0"),
            route=(DEXSCREENER_PROVIDER, "market_reference", pair.dex_id, pair.pair_address),
            freshness=Freshness(
                as_of=observed_at,
                expires_at=observed_at + timedelta(seconds=self._quote_ttl),
            ),
            price_semantics=PriceSemantics.MARKET_REFERENCE,
            market_context=context,
            chain=chain,
        )

    async def metadata(
        self,
        token: TokenIdentity,
        *,
        context: ProviderRequestContext,
    ) -> SocialMetadata:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        pairs = await self._get_pairs(
            token.address,
            context=context,
            chain=normalize_chain(token.chain),
            use_metadata_cache=True,
        )
        matching = [
            pair
            for pair in pairs
            if pair.base_mint == token.address or pair.quote_mint == token.address
        ]
        chain = normalize_chain(token.chain)
        matching.sort(key=lambda pair: _pair_rank(pair, token_mint=token.address, chain=chain))
        websites, socials = _raw_links(matching)
        observed_at, ingested_at = self._now_pair()
        raw = tuple(pair.raw for pair in matching)
        return SocialMetadata(
            token=token,
            websites=websites,
            socials=socials,
            observed_at=observed_at,
            ingested_at=ingested_at,
            quality_state=QualityState.FRESH if websites or socials else QualityState.UNKNOWN,
            provenance=self._provenance(
                f"/token-pairs/v1/{DEXSCREENER_CHAIN_BY_DOMAIN[chain]}/{token.address}",
                observed_at,
                raw,
            ),
        )


__all__ = [
    "DEXSCREENER_CHAIN",
    "DEXSCREENER_CHAIN_BY_DOMAIN",
    "DEXSCREENER_PARSER_VERSION",
    "DEXSCREENER_PROVIDER",
    "DEXSCREENER_TOKEN_PAIRS_PATH",
    "DexScreenerAdapter",
    "DexScreenerPair",
    "SOLANA_NATIVE_MINT",
    "SOLANA_USDC_MINT",
    "SOLANA_USDT_MINT",
]
