"""TDD contracts for launch-specific bundle/sniper/creator risk."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.launch_risk import LaunchRiskAnalyzer
from memeradar_domain import Observation, Provenance, QualityState, RiskDisposition

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TOKEN_ID = UUID("22222222-2222-2222-2222-222222222222")


def wallet_observation(
    wallet: str,
    *,
    bundle: str | None = None,
    funder: str | None = None,
    creator: bool = False,
    fresh: bool | None = False,
    slot: int = 100,
    quality: QualityState = QualityState.FRESH,
    occurred_at: datetime = NOW,
) -> Observation:
    payload: dict[str, object] = {
        "wallet": wallet,
        "slot": slot,
        "creator_related": creator,
    }
    if bundle is not None:
        payload["bundle_id"] = bundle
    if funder is not None:
        payload["funder"] = funder
    if fresh is not None:
        payload["fresh_wallet"] = fresh
    return Observation(
        id=uuid5(NAMESPACE_URL, f"launch-risk:{wallet}:{slot}:{bundle}"),
        kind="wallet.activity",
        provenance=Provenance(
            provider="fixture",
            source_id=f"risk-{wallet}-{slot}",
            observed_at=occurred_at,
            parser_version="fixture-v1",
        ),
        occurred_at=occurred_at,
        observed_at=occurred_at,
        ingested_at=occurred_at,
        quality_state=quality,
        normalized_payload=payload,
        token_id=TOKEN_ID,
    )


def test_clean_launch_requires_complete_graph_evidence_and_passes_control() -> None:
    observations = tuple(
        wallet_observation(
            f"wallet-{index}",
            bundle=f"bundle-{index}",
            funder=f"funder-{index}",
            slot=100 + index,
        )
        for index in range(4)
    )

    snapshot = LaunchRiskAnalyzer().evaluate(observations, as_of=NOW)

    assert snapshot.bundle_concentration == Decimal("0.25")
    assert snapshot.first_block_concentration == Decimal("0.25")
    assert snapshot.creator_related_ratio == Decimal("0")
    assert snapshot.shared_funder_ratio == Decimal("0")
    assert snapshot.fresh_wallet_ratio == Decimal("0")
    assert snapshot.risk_disposition is RiskDisposition.PASS
    assert snapshot.hard_blocks == ()
    assert snapshot.execution_eligible() is False


def test_bundle_and_creator_concentration_create_explicit_hard_block_candidates() -> None:
    observations = (
        wallet_observation("wallet-a", bundle="bundle-1", funder="funder-1", creator=True),
        wallet_observation("wallet-b", bundle="bundle-1", funder="funder-1", creator=True),
        wallet_observation("wallet-c", bundle="bundle-1", funder="funder-2"),
        wallet_observation("wallet-d", bundle="bundle-2", funder="funder-3"),
    )

    snapshot = LaunchRiskAnalyzer().evaluate(observations, as_of=NOW)

    assert snapshot.bundle_concentration == Decimal("0.75")
    assert snapshot.creator_related_ratio == Decimal("0.5")
    assert snapshot.risk_disposition is RiskDisposition.BLOCK
    assert "BUNDLE_CONCENTRATION" in snapshot.hard_blocks
    assert "CREATOR_RELATED_BUYING" in snapshot.hard_blocks


def test_missing_graph_evidence_is_unknown_not_a_clean_pass() -> None:
    snapshot = LaunchRiskAnalyzer().evaluate((), as_of=NOW)

    assert snapshot.quality_state is QualityState.UNKNOWN
    assert snapshot.risk_disposition is RiskDisposition.UNKNOWN
    assert snapshot.confidence == Decimal("0")
    assert "LAUNCH_RISK_EVIDENCE_UNKNOWN" in snapshot.reason_code_values


def test_stale_or_reverted_first_block_evidence_cannot_improve_risk() -> None:
    stale = wallet_observation(
        "wallet-a",
        bundle="bundle-1",
        funder="funder-1",
        quality=QualityState.STALE,
        occurred_at=NOW - timedelta(minutes=10),
    )
    reverted = wallet_observation(
        "wallet-b",
        bundle="bundle-1",
        funder="funder-1",
        quality=QualityState.CONFLICTED,
    )

    snapshot = LaunchRiskAnalyzer().evaluate((stale, reverted), as_of=NOW)

    assert snapshot.quality_state in {QualityState.STALE, QualityState.CONFLICTED}
    assert snapshot.risk_disposition is RiskDisposition.UNKNOWN
    assert snapshot.execution_eligible() is False
