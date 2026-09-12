"""Unit tests for Extension E6.4 Pre-Mine / Insider Allocation Suspicion."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from memeradar_application.holder_graph import (
    HolderBalance,
    HolderConcentrationSnapshot,
    InsiderAllocationAnalyzer,
    InsiderAllocationSuspicionState,
)
from memeradar_domain import Observation, Provenance, QualityState, ReasonCode, TokenIdentity

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT, id=uuid4())


def provenance(source_id: str) -> Provenance:
    return Provenance(
        provider="helius",
        source_id=source_id,
        observed_at=NOW,
        parser_version="insider-test-v1",
    )


def test_insider_allocation_safety_rule_exempts_valid_dex_buys() -> None:
    tok = token()
    snapshot = HolderConcentrationSnapshot(
        token=tok,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        total_holder_count=10,
        top1=Decimal("0.05"),
        top5=Decimal("0.10"),
        top10=Decimal("0.15"),
        clustered_top=Decimal("0.10"),
        holders=(
            HolderBalance(
                address="11111111111111111111111111111118",
                amount=Decimal("50000"),
                percentage=Decimal("0.05"),
                rank=1,
            ),
        ),
        excluded_addresses=(),
        provenance=(provenance("snap-1"),),
        evidence_refs=("ref-1",),
        reason_codes=(ReasonCode("TEST_CONCENTRATION"),),
        confidence=Decimal("0.90"),
        config_hash="sha256:test",
    )

    obs = [
        Observation(
            kind="wallet.activity",
            provenance=provenance("obs-1"),
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "wallet_address": "11111111111111111111111111111118",
                "native_sol": "0.02",
                "has_valid_buy_history": True,
                "acquisition_source": "buy",
            },
            token_id=tok.id,
        )
    ]

    analyzer = InsiderAllocationAnalyzer()
    res = analyzer.evaluate(tok, snapshot, observations=obs, as_of=NOW)
    assert res.state is InsiderAllocationSuspicionState.LOW_EVIDENCE
    assert res.suspicious_holder_count == 0
    assert res.execution_eligible() is False


def test_fresh_wallet_large_transfer_is_high_suspicion() -> None:
    tok = token()
    snapshot = HolderConcentrationSnapshot(
        token=tok,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        total_holder_count=10,
        top1=Decimal("0.10"),
        top5=Decimal("0.15"),
        top10=Decimal("0.20"),
        clustered_top=Decimal("0.15"),
        holders=(
            HolderBalance(
                address="11111111111111111111111111111113",
                amount=Decimal("100000"),
                percentage=Decimal("0.10"),
                rank=1,
            ),
        ),
        excluded_addresses=(),
        provenance=(provenance("snap-2"),),
        evidence_refs=("ref-2",),
        reason_codes=(ReasonCode("TEST_CONCENTRATION"),),
        confidence=Decimal("0.90"),
        config_hash="sha256:test",
    )

    obs = [
        Observation(
            kind="wallet.activity",
            provenance=provenance("obs-2"),
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "wallet_address": "11111111111111111111111111111113",
                "native_sol": "0.01",
                "acquisition_source": "transfer",
                "has_valid_buy_history": False,
                "is_fresh_wallet": True,
            },
            token_id=tok.id,
        )
    ]

    analyzer = InsiderAllocationAnalyzer()
    res = analyzer.evaluate(tok, snapshot, observations=obs, as_of=NOW)
    assert res.state is InsiderAllocationSuspicionState.HIGH_SUSPICION
    codes = [r.code for r in res.reason_codes]
    assert "LARGE_ALLOCATION_LOW_NATIVE_SOL" in codes
    assert "FRESH_WALLET_LARGE_ALLOCATION" in codes
    assert "TRANSFER_DOMINATED_ALLOCATION" in codes
    assert res.execution_eligible() is False


def test_low_native_sol_and_large_share_alone_is_supporting_evidence_only() -> None:
    tok = token()
    snapshot = HolderConcentrationSnapshot(
        token=tok,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        total_holder_count=10,
        top1=Decimal("0.05"),
        top5=None,
        top10=None,
        clustered_top=None,
        holders=(
            HolderBalance(
                address="11111111111111111111111111111118",
                amount=Decimal("50000"),
                percentage=Decimal("0.05"),
                rank=1,
            ),
        ),
        excluded_addresses=(),
        provenance=(provenance("snap-supporting"),),
        evidence_refs=("ref-supporting",),
        reason_codes=(ReasonCode("TEST_CONCENTRATION"),),
        confidence=Decimal("0.50"),
        config_hash="sha256:test",
    )
    obs = [
        Observation(
            kind="wallet.activity",
            provenance=provenance("obs-supporting"),
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "wallet_address": "11111111111111111111111111111118",
                "native_sol": "0.01",
            },
            token_id=tok.id,
        )
    ]

    result = InsiderAllocationAnalyzer().evaluate(tok, snapshot, observations=obs, as_of=NOW)

    assert result.state is InsiderAllocationSuspicionState.LOW_EVIDENCE
    assert result.suspicious_holder_count == 0
    assert result.suspicious_supply_pct == Decimal("0")
    assert "LARGE_ALLOCATION_LOW_NATIVE_SOL" in {item.code for item in result.reason_codes}

    unknown = InsiderAllocationAnalyzer().evaluate(tok, snapshot, observations=(), as_of=NOW)
    assert unknown.state is InsiderAllocationSuspicionState.UNKNOWN
    assert unknown.suspicious_holder_count == 0


def test_holder_flags_exclude_lp_burn_program_and_system_accounts() -> None:
    from memeradar_application.holder_graph import HolderGraphAnalyzer

    tok = token()
    observation = Observation(
        kind="market.holder_data",
        provenance=provenance("holders-flags"),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "holder_count": 4,
            "holders": [
                {"address": "11111111111111111111111111111113", "share": "0.40", "is_pool": True},
                {"address": "11111111111111111111111111111114", "share": "0.30", "is_burn": True},
                {
                    "address": "11111111111111111111111111111115",
                    "share": "0.20",
                    "is_program": True,
                },
                {"address": "11111111111111111111111111111116", "share": "0.10", "is_system": True},
            ],
        },
        token_id=tok.id,
    )

    result = HolderGraphAnalyzer().snapshot_holders(
        tok,
        (observation,),
        now=NOW,
        config_hash="holder-flags-v1",
    )

    assert result.holders == ()
    assert len(result.excluded_addresses) == 4
