"""TDD contracts for the bounded organic momentum evidence projection."""

from decimal import Decimal

from memeradar_application.organic_momentum import OrganicMomentumProjection
from memeradar_domain import QualityState


def test_independent_growth_and_liquidity_outscore_manipulated_flow() -> None:
    organic = OrganicMomentumProjection.from_metrics(
        {
            "buyer_acceleration": Decimal("0.8"),
            "unique_buyer_growth": Decimal("12"),
            "liquidity_acceleration": Decimal("0.6"),
            "independent_smart_wallet_count": 3,
            "fresh_wallet_ratio": Decimal("0.4"),
            "buy_sell_volume_ratio": Decimal("1.5"),
        }
    )
    manipulated = OrganicMomentumProjection.from_metrics(
        {
            "buyer_acceleration": Decimal("0.8"),
            "unique_buyer_growth": Decimal("1"),
            "liquidity_acceleration": Decimal("0"),
            "independent_smart_wallet_count": 0,
            "shared_funder_ratio": Decimal("0.9"),
            "wash_evidence": True,
            "circular_flow_ratio": Decimal("0.8"),
            "creator_linked_buyer_ratio": Decimal("0.7"),
            "bundle_risk": Decimal("0.9"),
        }
    )

    assert organic.score is not None
    assert manipulated.score is not None
    assert organic.score > manipulated.score
    assert organic.quality_state is QualityState.FRESH


def test_missing_evidence_remains_unknown() -> None:
    result = OrganicMomentumProjection.from_metrics({})

    assert result.score is None
    assert result.quality_state is QualityState.UNKNOWN
    assert "ORGANIC_MOMENTUM_EVIDENCE_MISSING" in result.reason_code_values
