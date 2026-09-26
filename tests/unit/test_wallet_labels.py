"""Evidence-only wallet-label registry contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.wallet_labels import (
    WalletLabel,
    WalletLabelCategory,
    WalletLabelRegistry,
)
from memeradar_domain import Chain

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
SOLANA_WALLET = "11111111111111111111111111111112"
EVM_WALLET = "0x1111111111111111111111111111111111111111"


def test_registry_keeps_multiple_sources_and_rejects_stale_replacement() -> None:
    registry = WalletLabelRegistry()
    first = WalletLabel(
        chain=Chain.SOLANA,
        address=SOLANA_WALLET,
        category=WalletLabelCategory.KNOWN_KOL,
        source="curated",
        confidence=Decimal("0.8"),
        last_verified_at=NOW,
        evidence_refs=("source:1",),
    )
    newer = WalletLabel(
        chain=Chain.SOLANA,
        address=SOLANA_WALLET,
        category=WalletLabelCategory.KNOWN_KOL,
        source="curated",
        confidence=Decimal("0.9"),
        last_verified_at=NOW + timedelta(minutes=1),
    )
    registry.add(first)
    registry.add(
        WalletLabel(
            chain=Chain.SOLANA,
            address=SOLANA_WALLET,
            category=WalletLabelCategory.MEV,
            source="heuristic",
            confidence=Decimal("0.6"),
            last_verified_at=NOW,
        )
    )
    registry.add(newer)
    registry.add(first)

    labels = registry.get(SOLANA_WALLET, Chain.SOLANA)
    assert len(labels) == 2
    assert labels[0].confidence == Decimal("0.9")
    assert labels[0].category is WalletLabelCategory.KNOWN_KOL


def test_registry_keys_evm_labels_by_address_not_ticker_like_metadata() -> None:
    registry = WalletLabelRegistry()
    registry.add(
        WalletLabel(
            chain=Chain.BASE,
            address=EVM_WALLET,
            category=WalletLabelCategory.CEX,
            source="explorer",
            confidence=Decimal("0.7"),
            last_verified_at=NOW,
        )
    )
    assert registry.get(EVM_WALLET, Chain.BASE)[0].chain is Chain.BASE
    assert registry.get(EVM_WALLET, Chain.BNB) == ()
