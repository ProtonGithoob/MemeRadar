"""Evidence-only wallet labels shared by wallet projections."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from memeradar_domain import Chain, normalize_chain, require_chain_address
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
)


class WalletLabelCategory(str, Enum):
    CEX = "CEX"
    DEX_ROUTER = "DEX_ROUTER"
    BRIDGE = "BRIDGE"
    LAUNCHPAD = "LAUNCHPAD"
    MEV = "MEV"
    MARKET_MAKER = "MARKET_MAKER"
    PROTOCOL_TREASURY = "PROTOCOL_TREASURY"
    KNOWN_WHALE = "KNOWN_WHALE"
    KNOWN_KOL = "KNOWN_KOL"
    CREATOR = "CREATOR"
    DEPLOYER = "DEPLOYER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class WalletLabel:
    """One sourced label; it is corroborating evidence, never authority."""

    chain: Chain | str
    address: str
    category: WalletLabelCategory | str
    source: str
    confidence: Decimal
    last_verified_at: datetime
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(
            self,
            "address",
            require_chain_address(self.address, chain, "wallet address"),
        )
        object.__setattr__(self, "category", WalletLabelCategory(self.category))
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(
            self,
            "last_verified_at",
            ensure_utc(self.last_verified_at, "last_verified_at"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    @property
    def identity(self) -> tuple[Chain, str, WalletLabelCategory, str]:
        return (
            normalize_chain(self.chain),
            self.address,
            WalletLabelCategory(self.category),
            self.source,
        )


class WalletLabelRegistry:
    """Bounded, idempotent registry for multi-source wallet label evidence."""

    def __init__(self, *, max_labels: int = 10_000) -> None:
        if (
            not isinstance(max_labels, int)
            or isinstance(max_labels, bool)
            or not 1 <= max_labels <= 100_000
        ):
            raise ValueError("max_labels must be between 1 and 100000")
        self.max_labels = max_labels
        self._labels: dict[tuple[Chain, str, WalletLabelCategory, str], WalletLabel] = {}

    def add(self, label: WalletLabel) -> WalletLabel:
        if not isinstance(label, WalletLabel):
            raise TypeError("label must be a WalletLabel")
        current = self._labels.get(label.identity)
        if current is not None and current.last_verified_at > label.last_verified_at:
            return current
        if current is None and len(self._labels) >= self.max_labels:
            raise ValueError("wallet-label registry exceeded bound")
        self._labels[label.identity] = label
        return label

    def add_many(self, labels: Sequence[WalletLabel]) -> tuple[WalletLabel, ...]:
        if isinstance(labels, str | bytes | bytearray):
            raise TypeError("labels must be a sequence")
        return tuple(self.add(label) for label in labels)

    def get(self, address: str, chain: Chain | str) -> tuple[WalletLabel, ...]:
        normalized_chain = normalize_chain(chain)
        normalized_address = require_chain_address(address, normalized_chain, "wallet address")
        return tuple(
            sorted(
                (
                    label
                    for label in self._labels.values()
                    if label.chain is normalized_chain and label.address == normalized_address
                ),
                key=lambda label: (
                    -label.confidence,
                    WalletLabelCategory(label.category).value,
                    label.source,
                ),
            )
        )

    @property
    def entries(self) -> tuple[WalletLabel, ...]:
        return tuple(self._labels.values())

    def __len__(self) -> int:
        return len(self._labels)


__all__ = ["WalletLabel", "WalletLabelCategory", "WalletLabelRegistry"]
