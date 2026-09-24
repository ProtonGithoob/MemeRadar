"""Read-only EVM sellability and tax evidence through eth_call."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Protocol

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Chain, Freshness, Provenance, QualityState, normalize_chain
from memeradar_domain.common import bounded_decimal, ensure_utc, to_decimal
from memeradar_domain.identities import require_evm_address

from .transport import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class EvmCallPort(Protocol):
    chain: Chain
    provider_name: str

    async def call_contract(
        self,
        address: str,
        data: str,
        *,
        context: ProviderRequestContext,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class EvmSellSimulationRequest:
    chain: Chain | str
    token_address: str
    target_address: str
    sell_call_data: str
    context: ProviderRequestContext

    def __post_init__(self) -> None:
        chain = normalize_chain(self.chain)
        if not chain.is_evm:
            raise ValueError("sell simulation requires an EVM chain")
        object.__setattr__(self, "chain", chain)
        object.__setattr__(
            self,
            "token_address",
            require_evm_address(self.token_address, "token_address"),
        )
        object.__setattr__(
            self,
            "target_address",
            require_evm_address(self.target_address, "target_address"),
        )
        if not isinstance(self.sell_call_data, str) or not self.sell_call_data.startswith("0x"):
            raise ValueError("sell_call_data must be hexadecimal calldata")
        if not isinstance(self.context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")


@dataclass(frozen=True, slots=True)
class EvmSellabilityResult:
    chain: Chain
    token_address: str
    sellable: bool | None
    route_available: bool | None
    buy_tax_bps: Decimal | None
    sell_tax_bps: Decimal | None
    price_impact_bps: Decimal | None
    blacklist_observed: bool | None
    quality_state: QualityState
    reason_codes: tuple[str, ...]
    provenance: Provenance
    freshness: Freshness


def _optional_bps(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    return bounded_decimal(to_decimal(value, field), field, Decimal("0"), Decimal("10000"))


class EvmSellabilityAdapter:
    """Use the existing RPC eth_call seam; never signs or submits a transaction."""

    capabilities = frozenset({"sell_simulation", "route_check"})

    def __init__(self, rpc: EvmCallPort, *, ttl_seconds: float = 15.0) -> None:
        if not callable(getattr(rpc, "call_contract", None)):
            raise TypeError("rpc must expose call_contract")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.rpc = rpc
        self.provider_name = f"evm-sell-simulation:{rpc.chain.value}"
        self._ttl_seconds = float(ttl_seconds)

    async def simulate(self, request: EvmSellSimulationRequest) -> EvmSellabilityResult:
        if not isinstance(request, EvmSellSimulationRequest):
            raise TypeError("request must be an EvmSellSimulationRequest")
        chain = normalize_chain(request.chain)
        if chain is not self.rpc.chain:
            raise ValueError("request chain must match the RPC chain")
        observed_at = ensure_utc(request.context.requested_at, "observed_at")
        raw: object = None
        quality = QualityState.FRESH
        sellable: bool | None = True
        route_available: bool | None = True
        reason_codes = ("ETH_CALL_SUCCEEDED",)
        try:
            raw = await self.rpc.call_contract(
                request.target_address,
                request.sell_call_data,
                context=request.context,
            )
        except (
            ProviderTimeoutError,
            ProviderUnavailableError,
            ProviderRateLimitedError,
            ProviderAuthenticationError,
        ):
            quality = QualityState.UNKNOWN
            sellable = None
            route_available = None
            reason_codes = ("SELL_SIMULATION_UNAVAILABLE",)
        except ProviderError:
            quality = QualityState.INVALID
            sellable = False
            route_available = False
            reason_codes = ("ETH_CALL_REVERTED",)
        payload = raw if isinstance(raw, Mapping) else {}
        blacklist_observed = payload.get("blacklist_observed")
        if not isinstance(blacklist_observed, bool):
            blacklist_observed = None
        return EvmSellabilityResult(
            chain=chain,
            token_address=request.token_address,
            sellable=sellable,
            route_available=route_available,
            buy_tax_bps=_optional_bps(payload.get("buy_tax_bps"), "buy_tax_bps"),
            sell_tax_bps=_optional_bps(payload.get("sell_tax_bps"), "sell_tax_bps"),
            price_impact_bps=_optional_bps(
                payload.get("price_impact_bps"), "price_impact_bps"
            ),
            blacklist_observed=blacklist_observed,
            quality_state=quality,
            reason_codes=reason_codes,
            provenance=Provenance(
                provider=self.provider_name,
                source_id=f"eth_call:{request.target_address}",
                observed_at=observed_at,
                parser_version="evm-sellability-v1",
            ),
            freshness=Freshness(
                as_of=observed_at,
                expires_at=observed_at + timedelta(seconds=self._ttl_seconds),
                quality_state=quality,
            ),
        )


__all__ = [
    "EvmCallPort",
    "EvmSellabilityAdapter",
    "EvmSellabilityResult",
    "EvmSellSimulationRequest",
]
