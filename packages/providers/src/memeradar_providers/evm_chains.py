"""Named read-only EVM chain adapters over the shared JSON-RPC owner."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from memeradar_application.provider_contracts import DiscoveryCandidate, DiscoveryRequest
from memeradar_domain import Chain

from .evm_rpc import EVM_CHAIN_IDS, EvmRpcAdapter


@dataclass(frozen=True, slots=True)
class EvmChainDescriptor:
    """Identity and activation metadata for one EVM network."""

    chain: Chain
    chain_id: int
    enabled_by_default: bool = False

    def __post_init__(self) -> None:
        if not self.chain.is_evm:
            raise ValueError("EVM descriptors require an EVM chain")
        if EVM_CHAIN_IDS.get(self.chain) != self.chain_id:
            raise ValueError("descriptor chain_id must match the shared EVM identity map")


EVM_CHAIN_DESCRIPTORS = {
    chain: EvmChainDescriptor(chain, chain_id)
    for chain, chain_id in EVM_CHAIN_IDS.items()
}


class EvmChainAdapter(EvmRpcAdapter):
    """Generic read-only chain adapter; it intentionally exposes no write method."""

    descriptor: EvmChainDescriptor

    def __init__(self, chain: Chain | str, endpoint: str, **kwargs: Any) -> None:
        normalized = Chain(chain)
        self.descriptor = EVM_CHAIN_DESCRIPTORS[normalized]
        super().__init__(normalized, endpoint, expected_chain_id=self.descriptor.chain_id, **kwargs)


class BnbChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.BNB, endpoint, **kwargs)


class RobinhoodChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.ROBINHOOD, endpoint, **kwargs)


class BaseChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.BASE, endpoint, **kwargs)


class EthereumChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.ETHEREUM, endpoint, **kwargs)


class ArbitrumChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.ARBITRUM, endpoint, **kwargs)


class AvalancheChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.AVALANCHE, endpoint, **kwargs)


class PolygonChainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.POLYGON, endpoint, **kwargs)


class UnichainAdapter(EvmChainAdapter):
    def __init__(self, endpoint: str, **kwargs: Any) -> None:
        super().__init__(Chain.UNICHAIN, endpoint, **kwargs)


class SuiChainAdapter(Protocol):
    """Unimplemented non-EVM seam; Sui must not be forced through EVM ports."""

    provider_name: str
    chain: Chain
    capabilities: frozenset[str]

    async def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]: ...


__all__ = [
    "ArbitrumChainAdapter",
    "AvalancheChainAdapter",
    "BaseChainAdapter",
    "BnbChainAdapter",
    "EthereumChainAdapter",
    "EVM_CHAIN_DESCRIPTORS",
    "EvmChainAdapter",
    "EvmChainDescriptor",
    "PolygonChainAdapter",
    "RobinhoodChainAdapter",
    "SuiChainAdapter",
    "UnichainAdapter",
]
