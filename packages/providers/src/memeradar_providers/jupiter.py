"""Jupiter Swap API V2 read-only quote and unsigned-order adapter."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from urllib.parse import parse_qsl, urlsplit

import httpx

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
)
from memeradar_domain import Chain, Freshness, PriceSemantics, Provenance, normalize_chain
from memeradar_domain.common import bounded_decimal, ensure_utc, require_text, to_decimal
from memeradar_domain.identities import require_solana_address

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
JUPITER_PROVIDER = "jupiter-swap-v2"
JUPITER_PARSER_VERSION = "jupiter-swap-v2"
_CREDENTIAL_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "token",
}


class JupiterNoRouteError(ProviderError):
    """Jupiter explicitly reported that no route exists for the pair."""


@dataclass(frozen=True, slots=True)
class JupiterOrder:
    request_id: str
    input_mint: str
    output_mint: str
    input_amount: Decimal
    output_amount: Decimal
    minimum_output_amount: Decimal
    price_impact_bps: Decimal
    route: tuple[str, ...]
    transaction: str | None
    raw_router: str | None
    provenance: Provenance


def _payload_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def _amount(value: object, field: str = "amount") -> str:
    normalized = to_decimal(value, field)
    if normalized <= 0 or normalized != normalized.to_integral_value():
        raise ValueError(f"{field} must be a positive integer smallest-unit amount")
    return str(int(normalized))


def _impact_bps(value: object, field: str) -> Decimal:
    parsed = to_decimal(value, field)
    if parsed < 0:
        raise ProviderSchemaError(f"{field} must not be negative")
    return bounded_decimal(
        parsed * Decimal("10000"),
        f"{field}_bps",
        Decimal("0"),
        Decimal("1000000"),
    )


def _route(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes | bytearray):
        raise ProviderSchemaError("Jupiter routePlan was invalid")
    values: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ProviderSchemaError("Jupiter routePlan item was invalid")
        info = item.get("swapInfo", item)
        if not isinstance(info, Mapping):
            raise ProviderSchemaError("Jupiter swapInfo was invalid")
        for key in ("label", "ammKey"):
            value = info.get(key)
            if value is not None:
                values.append(require_text(str(value), f"route_{key}", max_length=256))
    return tuple(values)


class JupiterAdapter(QuotePort):
    """Bounded HTTP adapter for Jupiter V2 quote/order reads; no execution API."""

    provider_name = JUPITER_PROVIDER
    capabilities = frozenset({"quote", "market_quote", "sell_route_check", "order_read"})

    def __init__(
        self,
        base_url: str = "https://api.jup.ag/swap/v2",
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        quote_ttl_seconds: float = 15.0,
    ) -> None:
        normalized = require_text(base_url, "base_url", max_length=512).rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("base_url must be an HTTPS URL")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("base_url must not contain credentials or fragments")
        if any(
            key.lower().replace("-", "_") in _CREDENTIAL_QUERY_KEYS
            for key, _ in parse_qsl(parsed.query)
        ):
            raise ValueError("base_url must not contain credential query parameters")
        self._base_url = normalized
        self._api_key = (
            None if api_key is None else require_text(api_key, "api_key", max_length=512)
        )
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None
        self._transport = transport or ProviderTransport(provider_name=JUPITER_PROVIDER)
        self._clock = clock or (lambda: datetime.now(UTC))
        if isinstance(quote_ttl_seconds, bool) or not isinstance(quote_ttl_seconds, int | float):
            raise TypeError("quote_ttl_seconds must be numeric")
        if not math.isfinite(float(quote_ttl_seconds)) or float(quote_ttl_seconds) <= 0:
            raise ValueError("quote_ttl_seconds must be positive")
        self._quote_ttl_seconds = float(quote_ttl_seconds)
        self._last_rate_limit: RateLimitSnapshot | None = None

    def __repr__(self) -> str:
        return (
            f"JupiterAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None})"
        )

    async def __aenter__(self) -> JupiterAdapter:
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

    def _timeout_for(self, context: ProviderRequestContext) -> float:
        if context.deadline_at is None:
            return self._transport.timeouts.overall_seconds
        remaining = (
            ensure_utc(context.deadline_at, "deadline_at") - ensure_utc(self._clock(), "now")
        ).total_seconds()
        if remaining <= 0:
            raise ProviderTimeoutError("provider request deadline expired")
        return min(remaining, self._transport.timeouts.overall_seconds)

    def _provenance(self, source_id: str, observed_at: datetime, raw: object) -> Provenance:
        return Provenance(
            provider=JUPITER_PROVIDER,
            source_id=source_id,
            observed_at=observed_at,
            parser_version=JUPITER_PARSER_VERSION,
            raw_payload_hash=_payload_hash(raw),
        )

    async def _request_json(
        self,
        path: str,
        params: Mapping[str, object],
        *,
        context: ProviderRequestContext,
    ) -> Mapping[str, object]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"accept": "application/json", "x-correlation-id": context.correlation_id}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        async def operation() -> object:
            try:
                response = await self._client.get(
                    url,
                    params={key: str(value) for key, value in params.items()},
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
            retry_after: float | None = None
            if response.headers.get("retry-after") is not None:
                try:
                    retry_after = float(response.headers["retry-after"])
                except ValueError:
                    retry_after = None
            if retry_after is not None and 0 <= retry_after <= 86_400:
                self._last_rate_limit = RateLimitSnapshot(retry_after_seconds=retry_after)
                self._transport.rate_limiter.update(self._last_rate_limit)
            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("provider authentication failed")
            if response.status_code == 429:
                raise ProviderRateLimitedError(retry_after)
            if response.status_code == 408:
                raise ProviderTimeoutError("provider request timed out")
            if response.status_code == 400:
                raise JupiterNoRouteError("Jupiter reported no usable route")
            if response.status_code >= 500:
                raise ProviderUnavailableError("provider service unavailable")
            if response.status_code >= 400:
                raise ProviderError("provider request rejected")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderSchemaError("provider response was not valid JSON") from exc
            if not isinstance(payload, Mapping):
                raise ProviderSchemaError("Jupiter response must be an object")
            return dict(payload)

        raw = await self._transport.execute(operation, timeout_seconds=self._timeout_for(context))
        if not isinstance(raw, Mapping):
            raise ProviderSchemaError("Jupiter response was invalid")
        return raw

    @staticmethod
    def _quote_params(request: QuoteRequest) -> dict[str, object]:
        if normalize_chain(request.chain) is not Chain.SOLANA:
            raise ValueError("Jupiter is a Solana-only adapter")
        return {
            "inputMint": require_solana_address(request.input_mint, "input_mint"),
            "outputMint": require_solana_address(request.output_mint, "output_mint"),
            "amount": _amount(request.amount),
            "slippageBps": request.slippage_bps,
        }

    def _snapshot(self, raw: Mapping[str, object], request: QuoteRequest) -> QuoteSnapshot:
        input_mint = require_solana_address(
            str(raw.get("inputMint", request.input_mint)), "input_mint"
        )
        output_mint = require_solana_address(
            str(raw.get("outputMint", request.output_mint)), "output_mint"
        )
        in_amount = _amount(raw.get("inAmount"), "inAmount")
        out_amount = _amount(raw.get("outAmount"), "outAmount")
        minimum = _amount(raw.get("otherAmountThreshold", out_amount), "otherAmountThreshold")
        impact = _impact_bps(raw.get("priceImpactPct", "0"), "priceImpactPct")
        route = _route(raw.get("routePlan"))
        if not route:
            raise JupiterNoRouteError("Jupiter returned an empty route")
        observed_at = ensure_utc(self._clock(), "observed_at")
        slippage_bps = to_decimal(raw.get("slippageBps", 0), "slippageBps")
        return QuoteSnapshot(
            provenance=self._provenance("/swap/v2/quote", observed_at, raw),
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=in_amount,
            output_amount=out_amount,
            minimum_output_amount=minimum,
            slippage_bps=slippage_bps,
            price_impact_bps=impact,
            route=route,
            freshness=Freshness(
                as_of=observed_at,
                expires_at=observed_at + timedelta(seconds=self._quote_ttl_seconds),
            ),
            price_semantics=PriceSemantics.EXECUTION_QUOTE,
            chain="solana",
        )

    async def quote(self, request: QuoteRequest) -> QuoteSnapshot:
        if not isinstance(request, QuoteRequest):
            raise TypeError("request must be a QuoteRequest")
        raw = await self._request_json(
            "quote",
            self._quote_params(request),
            context=request.context,
        )
        return self._snapshot(raw, request)

    async def sell_route_exists(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: object,
        context: ProviderRequestContext,
        slippage_bps: int = 100,
    ) -> bool | None:
        request = QuoteRequest(
            context=context,
            input_mint=require_solana_address(input_mint, "input_mint"),
            output_mint=require_solana_address(output_mint, "output_mint"),
            amount=_amount(amount),
            slippage_bps=slippage_bps,
        )
        try:
            await self.quote(request)
        except JupiterNoRouteError:
            return False
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderRateLimitedError):
            return None
        return True

    async def order(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: object,
        taker: str,
        slippage_bps: int,
        context: ProviderRequestContext,
    ) -> JupiterOrder:
        normalized_input = require_solana_address(input_mint, "input_mint")
        normalized_output = require_solana_address(output_mint, "output_mint")
        normalized_taker = require_solana_address(taker, "taker")
        raw = await self._request_json(
            "order",
            {
                "inputMint": normalized_input,
                "outputMint": normalized_output,
                "amount": _amount(amount),
                "taker": normalized_taker,
                "slippageBps": slippage_bps,
            },
            context=context,
        )
        request_id = require_text(str(raw.get("requestId", "")), "requestId", max_length=256)
        observed_at = ensure_utc(self._clock(), "observed_at")
        return JupiterOrder(
            request_id=request_id,
            input_mint=normalized_input,
            output_mint=normalized_output,
            input_amount=to_decimal(raw.get("inAmount"), "inAmount"),
            output_amount=to_decimal(raw.get("outAmount"), "outAmount"),
            minimum_output_amount=to_decimal(
                raw.get("otherAmountThreshold"), "otherAmountThreshold"
            ),
            price_impact_bps=_impact_bps(raw.get("priceImpact", "0"), "priceImpact"),
            route=_route(raw.get("routePlan")),
            transaction=(
                None
                if raw.get("transaction") is None
                else require_text(str(raw["transaction"]), "transaction", max_length=2_000_000)
            ),
            raw_router=(None if raw.get("router") is None else str(raw["router"])),
            provenance=self._provenance("/swap/v2/order", observed_at, raw),
        )


__all__ = [
    "JUPITER_PARSER_VERSION",
    "JUPITER_PROVIDER",
    "JupiterAdapter",
    "JupiterNoRouteError",
    "JupiterOrder",
]
