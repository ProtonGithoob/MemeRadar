"""Deterministic external-wallet corroboration and safety tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_application.confluence import TokenSmartMoneyScore
from memeradar_application.external_wallet import (
    ExternalWalletCrossValidationPolicy,
    ExternalWalletLabel,
    ExternalWalletReconciler,
    ExternalWalletTokenSignal,
)
from memeradar_application.holder_graph import WalletGraphEdge, WalletGraphSnapshot
from memeradar_application.wallet_scoring import SmartWalletScore
from memeradar_application.wallet_tracking import WalletTier
from memeradar_domain import Provenance, QualityState, ReasonCode, TokenIdentity

NOW = datetime(2026, 8, 30, 20, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111112"
WALLET_B = "11111111111111111111111111111113"
FUNDER = "11111111111111111111111111111114"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def provenance(source_id: str, *, source: str = "external-fixture") -> Provenance:
    return Provenance(
        provider=source,
        source_id=source_id,
        observed_at=NOW - timedelta(seconds=30),
        parser_version="external-wallet-fixture-v1",
    )


def label(
    wallet: str = WALLET_A,
    *,
    value: str = "SMART_MONEY",
    source_id: str = "label:a",
    source: str = "external-fixture",
    observed_at: datetime = NOW - timedelta(seconds=30),
    expires_at: datetime = NOW + timedelta(minutes=4),
    confidence: str = "0.90",
) -> ExternalWalletLabel:
    source_provenance = Provenance(
        provider=source,
        source_id=source_id,
        observed_at=min(observed_at, NOW),
        parser_version="external-wallet-fixture-v1",
    )
    return ExternalWalletLabel(
        wallet_address=wallet,
        label=value,
        source=source,
        source_confidence=Decimal(confidence),
        observed_at=observed_at,
        expires_at=expires_at,
        raw_source_id=source_id,
        provenance=source_provenance,
        evidence_refs=(source_id,),
    )


def signal(
    token_value: TokenIdentity,
    *,
    wallet: str | None = WALLET_A,
    source_id: str = "signal:a",
    tracked_supply: str | None = "0.25",
    bundle: str | None = "0.70",
    side_wallet: str | None = "0.80",
    security_flags: tuple[str, ...] = ("RUG_WARNING",),
) -> ExternalWalletTokenSignal:
    return ExternalWalletTokenSignal(
        token=token_value,
        wallet_address=wallet,
        signal_type="TOKEN_INTELLIGENCE",
        source="external-fixture",
        source_confidence=Decimal("0.80"),
        observed_at=NOW - timedelta(seconds=20),
        expires_at=NOW + timedelta(minutes=4),
        raw_source_id=source_id,
        provenance=provenance(source_id),
        tracked_supply_pct=(None if tracked_supply is None else Decimal(tracked_supply)),
        bundle_confidence=None if bundle is None else Decimal(bundle),
        side_wallet_cluster_confidence=(
            None if side_wallet is None else Decimal(side_wallet)
        ),
        security_flags=security_flags,
        evidence_refs=(source_id,),
    )


def smart_score(wallet: str, *, score: str = "80", confidence: str = "0.90") -> SmartWalletScore:
    return SmartWalletScore(
        wallet_address=wallet,
        label="internal smart wallet",
        registry_tier=WalletTier.TIER_B,
        recommended_tier=WalletTier.TIER_B,
        as_of=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=4),
        score=Decimal(score),
        confidence=Decimal(confidence),
        sample_count=10,
        known_outcome_count=10,
        win_rate=Decimal("0.8"),
        realized_pnl=Decimal("10"),
        median_return=Decimal("0.2"),
        early_entry_rate=Decimal("0.8"),
        rug_avoidance_rate=Decimal("1"),
        manipulation_penalty=Decimal("0"),
        components={"win_rate": Decimal("80")},
        penalties={},
        provenance=(provenance(f"internal:{wallet}"),),
        evidence_refs=(f"internal:{wallet}",),
        reason_codes=("SMART_WALLET_SCORE_CALCULATED",),
        config_hash="external-wallet-test",
        quality_state=QualityState.FRESH,
    )


def graph(token_value: TokenIdentity) -> WalletGraphSnapshot:
    edge = WalletGraphEdge(
        from_address=WALLET_A,
        to_address=FUNDER,
        relation_type="funded_by",
        weight=Decimal("1"),
        transfer_count=1,
        first_seen_at=NOW - timedelta(hours=1),
        last_seen_at=NOW - timedelta(minutes=1),
        confidence=Decimal("0.9"),
        evidence_refs=("graph:a",),
        reason_codes=(ReasonCode("SHARED_FUNDER_CLUSTER"),),
    )
    second_edge = replace(edge, from_address=WALLET_B, evidence_refs=("graph:b",))
    return WalletGraphSnapshot(
        token=token_value,
        as_of=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=4),
        seed_addresses=(WALLET_A, WALLET_B),
        nodes=(WALLET_A, WALLET_B, FUNDER),
        edges=(edge, second_edge),
        provenance=(provenance("graph:wallets"),),
        evidence_refs=("graph:wallets",),
        reason_codes=(ReasonCode("WALLET_GRAPH_BUILT"),),
        confidence=Decimal("0.9"),
        config_hash="external-wallet-test",
    )


def test_contracts_normalize_and_remain_immutable() -> None:
    token_value = token()
    item = label(value=" smart-money ")
    token_signal = signal(token_value)

    assert item.label == "SMART_MONEY"
    assert item.confidence == Decimal("0.90")
    assert item.source_id == "label:a"
    assert item.freshness.is_fresh(NOW)
    assert token_signal.tracked_supply_pct == Decimal("0.25")
    assert token_signal.risk_flags == ("RUG_WARNING",)
    with pytest.raises((TypeError, AttributeError)):
        item.evidence_refs += ("another",)  # type: ignore[misc]


def test_agreement_uses_internal_score_and_collapses_graph_clusters() -> None:
    token_value = token()
    result = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(label(WALLET_A), label(WALLET_B, source_id="label:b")),
        token_signals=(signal(token_value),),
        internal_scores=(smart_score(WALLET_A), smart_score(WALLET_B)),
        wallet_graph=graph(token_value),
        now=NOW,
        config_hash="external-wallet-test",
    )

    assert result.external_label_confidence == Decimal("0.90")
    assert result.confidence_bonus > Decimal("0")
    assert result.independent_external_wallet_clusters == 1
    assert result.agreement_count == 2
    assert result.disagreement_count == 0
    assert result.tracked_supply_pct == Decimal("0.25")
    assert result.bundle_confidence == Decimal("0.70")
    assert result.side_wallet_cluster_confidence == Decimal("0.80")
    assert result.corroborating_security_flags == ("RUG_WARNING",)
    assert result.execution_eligible(NOW) is False


def test_stale_and_disagreeing_labels_never_add_positive_confidence() -> None:
    token_value = token()
    stale = label(
        observed_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=1),
    )
    stale_result = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(stale,),
        internal_scores=(smart_score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-test",
    )
    assert stale_result.external_label_confidence == Decimal("0")
    assert stale_result.confidence_bonus == Decimal("0")
    assert "EXTERNAL_LABEL_STALE" in {reason.code for reason in stale_result.reason_codes}

    disagreeing = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(label(value="RUGGER"),),
        internal_scores=(smart_score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-test",
    )
    assert disagreeing.confidence_bonus == Decimal("0")
    assert disagreeing.quality_state is QualityState.CONFLICTED
    assert "CONFLICTED_EXTERNAL_WALLET_LABEL" in {
        reason.code for reason in disagreeing.reason_codes
    }


def test_future_and_conflicting_source_evidence_fail_closed() -> None:
    token_value = token()
    future = label(
        observed_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    future_result = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(future,),
        internal_scores=(smart_score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-test",
    )
    assert future_result.quality_state is QualityState.INVALID
    assert future_result.confidence_bonus == Decimal("0")

    conflicting = label(value="KOL", source_id="label:a")
    conflict_result = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(label(), conflicting),
        internal_scores=(smart_score(WALLET_A),),
        now=NOW,
        config_hash="external-wallet-test",
    )
    assert conflict_result.quality_state is QualityState.CONFLICTED
    assert conflict_result.external_label_confidence == Decimal("0")
    assert conflict_result.confidence_bonus == Decimal("0")


def test_external_evidence_does_not_mutate_internal_score_or_risk_types() -> None:
    token_value = token()
    internal = smart_score(WALLET_A)
    before = internal
    result = ExternalWalletReconciler().reconcile(
        token_value,
        labels=(label(),),
        internal_scores=(internal,),
        now=NOW,
        config_hash="external-wallet-test",
    )

    assert internal == before
    assert result.internal_score_refs == ("internal:" + WALLET_A,)
    assert result.execution_eligible(NOW) is False
    assert not isinstance(result, TokenSmartMoneyScore)


def test_policy_keeps_bonus_bounded_and_modes_protected() -> None:
    policy = ExternalWalletCrossValidationPolicy()
    assert policy.maximum_confidence_bonus <= Decimal("0.20")
    assert policy.analysis_only is True
    assert policy.paper_trading is True
    assert policy.manual_execution is False
    assert policy.auto_execution is False

    with pytest.raises(ValueError, match="analysis_only"):
        ExternalWalletCrossValidationPolicy(analysis_only=False)


def test_contract_rejects_invalid_signal_ranges_and_missing_provenance() -> None:
    token_value = token()
    with pytest.raises(ValueError, match="tracked_supply_pct"):
        replace(signal(token_value), tracked_supply_pct=Decimal("1.1"))
    with pytest.raises(ValueError, match="provenance source_id"):
        ExternalWalletLabel(
            wallet_address=WALLET_A,
            label="SMART_MONEY",
            source="external-fixture",
            source_confidence=Decimal("0.9"),
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            raw_source_id="raw-id",
            provenance=provenance("different-id"),
        )
