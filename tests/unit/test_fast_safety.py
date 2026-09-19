"""TDD contracts for the bounded fast launch safety gate."""

from decimal import Decimal

from memeradar_application.fast_safety import FastSafetyGate, FastSafetyStatus

BASE_EVIDENCE = {
    "mint_authority_safe": True,
    "freeze_authority_safe": True,
    "liquidity": Decimal("25000"),
    "sellability": True,
    "buy_impact_bps": Decimal("100"),
    "sell_impact_bps": Decimal("150"),
    "raw_smart_wallet_count": 3,
    "independent_smart_wallet_count": 3,
    "shared_funder_ratio": Decimal("0"),
}


def test_fast_safety_passes_complete_tradeable_evidence() -> None:
    result = FastSafetyGate().evaluate(BASE_EVIDENCE)

    assert result.status is FastSafetyStatus.PASS
    assert result.critical_unknowns == ()
    assert result.sellability is True
    assert result.latency_ms >= 0


def test_optional_social_unknown_is_noncritical_caution() -> None:
    result = FastSafetyGate().evaluate({**BASE_EVIDENCE, "social_quality_state": "UNKNOWN"})

    assert result.status is FastSafetyStatus.CAUTION
    assert result.critical_unknowns == ()
    assert "SOCIAL_EVIDENCE_UNKNOWN" in result.noncritical_unknowns


def test_obvious_manipulation_or_untradeable_impact_blocks() -> None:
    result = FastSafetyGate().evaluate(
        {
            **BASE_EVIDENCE,
            "bundle_concentration": Decimal("0.9"),
            "sellability": False,
            "sell_impact_bps": Decimal("5000"),
        }
    )

    assert result.status is FastSafetyStatus.BLOCK
    assert "BUNDLE_CONCENTRATION" in result.hard_blocks
    assert "SELLABILITY_FAILED" in result.reason_code_values
    assert "SELL_IMPACT_HIGH" in result.reason_code_values


def test_critical_missing_evidence_is_unknown_not_safe() -> None:
    result = FastSafetyGate().evaluate(
        {
            "mint_authority_safe": True,
            "freeze_authority_safe": True,
            "social_quality_state": "UNKNOWN",
        }
    )

    assert result.status is FastSafetyStatus.UNKNOWN
    assert "LIQUIDITY_UNKNOWN" in result.critical_unknowns
    assert "SELLABILITY_UNKNOWN" in result.critical_unknowns
    assert "IMPACT_UNKNOWN" in result.critical_unknowns


def test_shared_funder_collapses_apparent_smart_wallet_confluence() -> None:
    result = FastSafetyGate().evaluate(
        {
            **BASE_EVIDENCE,
            "raw_smart_wallet_count": 5,
            "independent_smart_wallet_count": 1,
            "shared_funder_ratio": Decimal("1"),
            "coordinated_wallet_probability": Decimal("0.9"),
        }
    )

    assert result.raw_smart_wallet_count == 5
    assert result.independent_smart_wallet_count == 1
    assert result.shared_funder_ratio == Decimal("1")
    assert result.coordinated_wallet_probability == Decimal("0.9")
    assert result.status is FastSafetyStatus.BLOCK


def test_creator_linked_wallets_are_preserved_as_risk_evidence() -> None:
    result = FastSafetyGate().evaluate(
        {
            **BASE_EVIDENCE,
            "creator_linked_smart_wallet_count": 2,
            "creator_related_ratio": Decimal("0.8"),
        }
    )

    assert result.status is FastSafetyStatus.BLOCK
    assert result.creator_linked_smart_wallet_count == 2
    assert "CREATOR_LINKED_ACTIVITY" in result.hard_blocks


def test_unverified_protocol_identity_is_critical_unknown() -> None:
    result = FastSafetyGate().evaluate(
        {**BASE_EVIDENCE, "protocol_identity_verified": False}
    )

    assert result.status is FastSafetyStatus.UNKNOWN
    assert "PROTOCOL_IDENTITY_UNVERIFIED" in result.critical_unknowns
