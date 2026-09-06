"""Deterministic caller-linked wallet conduct evidence contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.correlation import (
    CallerMarketConductAnalyzer,
    CallerMarketConductClassification,
)
from memeradar_application.wallet_tracking import WalletAction, WalletActivity
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
SOLANA_TOKEN = "So11111111111111111111111111111111111111112"
SOLANA_WALLET = "11111111111111111111111111111112"
OTHER_SOLANA_WALLET = "11111111111111111111111111111113"
EVM_TOKEN = "0x" + "11" * 20
EVM_WALLET = "0x" + "22" * 20


def provenance(source_id: str, *, observed_at: datetime = NOW) -> Provenance:
    return Provenance(
        provider="conduct-fixture",
        source_id=source_id,
        observed_at=observed_at,
        parser_version="caller-conduct-fixture-v1",
    )


def caller(author_id: str = "alpha") -> CallerIdentity:
    return CallerIdentity(platform="telegram", author_id=author_id, handle=author_id)


def call(
    token: TokenIdentity,
    *,
    author_id: str = "alpha",
    called_at: datetime = NOW - timedelta(minutes=30),
    source_id: str = "call-alpha",
) -> SocialCallObservation:
    return SocialCallObservation(
        source="telegram",
        message_id=source_id,
        caller_identity=caller(author_id),
        published_at=called_at,
        observed_at=NOW,
        ingested_at=NOW,
        provenance=(provenance(source_id),),
        asset=token,
        intent=CallIntent.BULLISH,
        confidence=Decimal("0.90"),
        quality_state=QualityState.FRESH,
    )


def linkage(
    token: TokenIdentity,
    *,
    address: str,
    author_id: str = "alpha",
    confidence: str = "0.90",
    state: IdentityLinkState = IdentityLinkState.SUPPORTED,
) -> CrossChainIdentityEvidence:
    return CrossChainIdentityEvidence(
        caller_identity=caller(author_id),
        wallet=WalletIdentity(address=address, chain=token.chain),
        evidence_type=IdentityEvidenceType.EXPLICIT_PUBLIC_LINK,
        link_state=state,
        confidence=Decimal(confidence),
        observed_at=NOW,
        provenance=(provenance(f"link-{author_id}-{address}"),),
        quality_state=QualityState.FRESH,
    )


def activity(
    token: TokenIdentity,
    *,
    source_id: str,
    address: str,
    action: WalletAction,
    occurred_at: datetime,
    quote_amount: str = "100",
    observed_at: datetime = NOW,
) -> WalletActivity:
    return WalletActivity(
        token=token,
        wallet_address=address,
        action=action,
        quantity=Decimal("10"),
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        provenance=provenance(source_id, observed_at=observed_at),
        quote_amount=Decimal(quote_amount),
    )


def test_temporal_conduct_is_bounded_and_keeps_smart_money_and_cluster_evidence() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    primary = call(token)
    result = CallerMarketConductAnalyzer().analyze(
        primary,
        (linkage(token, address=SOLANA_WALLET),),
        (
            activity(
                token,
                source_id="buy-before-call",
                address=SOLANA_WALLET,
                action=WalletAction.BUY,
                occurred_at=primary.published_at - timedelta(minutes=10),
            ),
            activity(
                token,
                source_id="sell-after-call",
                address=SOLANA_WALLET,
                action=WalletAction.SELL,
                occurred_at=primary.published_at + timedelta(minutes=20),
                quote_amount="40",
            ),
        ),
        related_calls=(call(token, author_id="beta", source_id="call-beta"),),
        smart_money_wallets=(SOLANA_WALLET,),
        now=NOW,
        config_hash="conduct-test-v1",
    )

    assert CallerMarketConductClassification.PRE_POSITIONING_CORRELATION in result.classifications
    assert CallerMarketConductClassification.POST_CALL_DISTRIBUTION in result.classifications
    assert CallerMarketConductClassification.COORDINATED_CALL_CLUSTER in result.classifications
    assert (
        CallerMarketConductClassification.CALLER_SMART_MONEY_CONFIRMATION
        in result.classifications
    )
    assert result.pre_call_net_flow == Decimal("100")
    assert result.post_call_net_flow == Decimal("-40")
    assert result.pre_call_seconds == Decimal("600")
    assert result.distribution_seconds == Decimal("1200")
    assert result.wallet_link_confidence == Decimal("0.90")
    assert result.execution_eligible(NOW) is False


def test_unrelated_wallet_activity_does_not_create_conduct_evidence() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    primary = call(token)
    result = CallerMarketConductAnalyzer().analyze(
        primary,
        (linkage(token, address=SOLANA_WALLET),),
        (
            activity(
                token,
                source_id="unrelated-buy",
                address=OTHER_SOLANA_WALLET,
                action=WalletAction.BUY,
                occurred_at=primary.published_at - timedelta(minutes=5),
            ),
        ),
        now=NOW,
        config_hash="conduct-test-v1",
    )

    assert result.classifications == (CallerMarketConductClassification.INSUFFICIENT_EVIDENCE,)
    assert result.confidence == Decimal("0")
    assert "CALLER_WALLET_ACTIVITY_MISSING" in {str(reason) for reason in result.reason_codes}


def test_weak_wallet_linkage_never_becomes_identity_or_misconduct() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    primary = call(token)
    result = CallerMarketConductAnalyzer().analyze(
        primary,
        (
            linkage(
                token,
                address=SOLANA_WALLET,
                confidence="0.42",
                state=IdentityLinkState.AMBIGUOUS,
            ),
        ),
        (
            activity(
                token,
                source_id="weak-link-buy",
                address=SOLANA_WALLET,
                action=WalletAction.BUY,
                occurred_at=primary.published_at - timedelta(minutes=5),
            ),
        ),
        now=NOW,
        config_hash="conduct-test-v1",
    )

    assert result.classifications == (CallerMarketConductClassification.INSUFFICIENT_EVIDENCE,)
    assert result.linked_wallet_ids == ()
    assert result.wallet_link_confidence == Decimal("0")
    assert "CALLER_WALLET_LINK_NOT_HARD" in {str(reason) for reason in result.reason_codes}


def test_missing_flow_evidence_is_explicitly_unknown() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    result = CallerMarketConductAnalyzer().analyze(
        call(token),
        (),
        (),
        now=NOW,
        config_hash="conduct-test-v1",
    )

    assert result.classifications == (CallerMarketConductClassification.INSUFFICIENT_EVIDENCE,)
    assert result.quality_state is QualityState.UNKNOWN
    assert result.no_lookahead_verified is True
    assert "CALLER_FLOW_EVIDENCE_MISSING" in {str(reason) for reason in result.reason_codes}


def test_evm_wallet_activity_reuses_chain_neutral_token_identity() -> None:
    for chain in ("bnb", "robinhood"):
        token = TokenIdentity(mint_address=EVM_TOKEN, chain=chain, token_program="erc20")
        primary = call(token)
        result = CallerMarketConductAnalyzer().analyze(
            primary,
            (linkage(token, address=EVM_WALLET),),
            (
                activity(
                    token,
                    source_id=f"{chain}-buy",
                    address=EVM_WALLET,
                    action=WalletAction.BUY,
                    occurred_at=primary.published_at - timedelta(minutes=5),
                ),
            ),
            now=NOW,
            config_hash="conduct-test-v1",
        )

        assert (
            CallerMarketConductClassification.PRE_POSITIONING_CORRELATION
            in result.classifications
        )


def test_future_wallet_flow_is_excluded_and_invalidates_the_projection() -> None:
    token = TokenIdentity(mint_address=SOLANA_TOKEN)
    primary = call(token)
    future = activity(
        token,
        source_id="future-buy",
        address=SOLANA_WALLET,
        action=WalletAction.BUY,
        occurred_at=NOW + timedelta(minutes=1),
        observed_at=NOW + timedelta(minutes=1),
    )

    result = CallerMarketConductAnalyzer().analyze(
        primary,
        (linkage(token, address=SOLANA_WALLET),),
        (future,),
        now=NOW,
        config_hash="conduct-test-v1",
    )

    assert result.classifications == (CallerMarketConductClassification.INSUFFICIENT_EVIDENCE,)
    assert result.quality_state is QualityState.INVALID
    assert result.no_lookahead_verified is False
