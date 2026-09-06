"""Canonical caller/social identity contracts for Alpha Caller Intelligence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    CrossChainIdentityEvidence,
    IdentityEvidenceType,
    IdentityLinkState,
    Provenance,
    QualityState,
    SocialCallObservation,
    TokenIdentity,
    WalletIdentity,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SOLANA_MINT = "So11111111111111111111111111111111111111112"
EVM_ADDRESS = "0x" + "AB" * 20


def provenance(source_id: str = "message-1") -> Provenance:
    return Provenance(
        provider="fixture.social",
        source_id=source_id,
        observed_at=NOW + timedelta(minutes=2),
        parser_version="caller-contract-fixture-v1",
    )


def caller() -> CallerIdentity:
    return CallerIdentity(platform="telegram", author_id="channel-42", handle="alpha_calls")


def observation(**overrides: object) -> SocialCallObservation:
    values: dict[str, object] = {
        "source": "telegram",
        "message_id": "message-1",
        "caller_identity": caller(),
        "published_at": NOW,
        "observed_at": NOW + timedelta(minutes=2),
        "ingested_at": NOW + timedelta(minutes=3),
        "asset": TokenIdentity(mint_address=SOLANA_MINT),
        "intent": CallIntent.BULLISH,
        "confidence": Decimal("0.80"),
        "provenance": (provenance(),),
    }
    values.update(overrides)
    return SocialCallObservation(**values)  # type: ignore[arg-type]


def test_ticker_only_reference_is_evidence_and_never_a_canonical_asset() -> None:
    result = observation(asset=None, unresolved_references=("$MEME", "Meme Coin"))

    assert result.asset is None
    assert result.canonical_asset_id is None
    assert result.unresolved_references == ("$MEME", "Meme Coin")


def test_solana_and_evm_assets_and_wallets_use_chain_qualified_identity() -> None:
    solana = observation(asset=TokenIdentity(mint_address=SOLANA_MINT, chain="solana"))
    bnb = observation(
        chain="bnb",
        asset=TokenIdentity(mint_address=EVM_ADDRESS, chain="bnb", token_program="bep20"),
    )
    robinhood_wallet = WalletIdentity(address=EVM_ADDRESS, chain="robinhood")

    assert solana.canonical_asset_id == f"solana:{SOLANA_MINT}"
    assert bnb.canonical_asset_id == f"bnb:{EVM_ADDRESS.lower()}"
    assert robinhood_wallet.canonical_id == f"robinhood:{EVM_ADDRESS.lower()}"
    assert bnb.canonical_asset_id != f"robinhood:{EVM_ADDRESS.lower()}"


def test_ambiguous_wallet_linkage_remains_evidence_not_a_hard_identity_link() -> None:
    evidence = CrossChainIdentityEvidence(
        caller_identity=caller(),
        wallet=WalletIdentity(address=EVM_ADDRESS, chain="bnb"),
        evidence_type=IdentityEvidenceType.TEMPORAL_CORRELATION,
        link_state=IdentityLinkState.AMBIGUOUS,
        confidence=Decimal("0.42"),
        observed_at=NOW + timedelta(minutes=4),
        provenance=(provenance("link-1"),),
        evidence_refs=("flow:before-call",),
    )

    assert evidence.wallet.canonical_id == f"bnb:{EVM_ADDRESS.lower()}"
    assert evidence.link_state is IdentityLinkState.AMBIGUOUS
    assert evidence.is_hard_link is False
    assert evidence.execution_eligible(NOW) is False


def test_published_observed_and_ingested_times_are_distinct_and_ordered() -> None:
    result = observation()

    assert result.published_at == NOW
    assert result.observed_at == NOW + timedelta(minutes=2)
    assert result.ingested_at == NOW + timedelta(minutes=3)
    assert result.published_at < result.observed_at < result.ingested_at

    with pytest.raises(ValueError, match="occurred_at"):
        observation(published_at=NOW + timedelta(minutes=4))


def test_unknown_unresolved_call_is_explicit_and_fail_closed() -> None:
    result = observation(
        asset=None,
        unresolved_references=("$UNKNOWN",),
        intent=CallIntent.UNKNOWN,
        confidence=Decimal("0"),
        quality_state=QualityState.UNKNOWN,
    )

    assert result.quality_state is QualityState.UNKNOWN
    assert result.intent is CallIntent.UNKNOWN
    assert result.confidence == Decimal("0")
    assert result.execution_eligible(NOW) is False
