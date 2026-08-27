"""Deterministic, provider-independent token-security assessment tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from memeradar_application.provider_contracts import RiskFinding, RiskSeverity
from memeradar_application.token_security import TokenSecurityEvaluator
from memeradar_domain import (
    Observation,
    Provenance,
    QualityState,
    RiskDisposition,
    TokenIdentity,
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
AUTHORITY = "11111111111111111111111111111111"
SOURCE_ID = "getAsset:So11111111111111111111111111111111111111112"


def token(*, token_program: str = "spl-token") -> TokenIdentity:
    return TokenIdentity(
        mint_address=MINT,
        token_program=token_program,
        id=uuid4(),
    )


def authority_observation(
    token_value: TokenIdentity,
    *,
    mint_state: str = "REVOKED",
    freeze_state: str = "REVOKED",
    observed_at: datetime = NOW - timedelta(minutes=1),
    quality_state: QualityState = QualityState.FRESH,
    token_program: str | None = None,
    token_extensions: object = (),
    source_id: str = SOURCE_ID,
) -> Observation:
    observed = observed_at.astimezone(UTC)
    return Observation(
        kind="onchain.token_metadata",
        provenance=Provenance(
            provider="helius",
            source_id=source_id,
            observed_at=observed,
            parser_version="helius-read-v1",
        ),
        occurred_at=None,
        observed_at=observed,
        ingested_at=observed + timedelta(seconds=1),
        quality_state=quality_state,
        normalized_payload={
            "mint_address": token_value.mint_address,
            "token_program": token_program or token_value.token_program,
            "mint_authority": {
                "state": mint_state,
                "address": AUTHORITY if mint_state == "ACTIVE" else None,
            },
            "freeze_authority": {
                "state": freeze_state,
                "address": AUTHORITY if freeze_state == "ACTIVE" else None,
            },
            "token_extensions": token_extensions,
        },
        token_id=token_value.id,
    )


def assess(
    token_value: TokenIdentity,
    observations: tuple[Observation, ...],
    *,
    security_findings: tuple[RiskFinding, ...] = (),
):
    return TokenSecurityEvaluator().evaluate(
        uuid4(),
        token_value,
        observations,
        security_findings=security_findings,
        now=NOW,
        config_hash="token-security-test-config",
    )


def risk_finding(
    code: str,
    severity: RiskSeverity,
    *,
    quality_state: QualityState = QualityState.FRESH,
) -> RiskFinding:
    return RiskFinding(
        code=code,
        severity=severity,
        quality_state=quality_state,
        detail="fixture finding",
        evidence_refs=("rugcheck:summary:fixture",),
        provenance=Provenance(
            provider="rugcheck",
            source_id="rugcheck:summary:fixture",
            observed_at=NOW - timedelta(seconds=1),
            parser_version="rugcheck-summary-v1",
        ),
    )


def test_revoked_authorities_produce_fresh_execution_eligible_pass() -> None:
    token_value = token()

    result = assess(token_value, (authority_observation(token_value),))

    assert result.disposition is RiskDisposition.PASS
    assert result.hard_blocks == ()
    assert result.warnings == ()
    assert result.critical_evidence_state is QualityState.FRESH
    assert result.evidence_refs == (SOURCE_ID,)
    assert result.execution_eligible(NOW) is True


def test_active_mint_authority_is_a_deterministic_hard_block() -> None:
    token_value = token()

    result = assess(
        token_value,
        (authority_observation(token_value, mint_state="ACTIVE"),),
    )

    assert result.disposition is RiskDisposition.BLOCK
    assert result.hard_blocks == ("MINT_AUTHORITY_ACTIVE",)
    assert result.execution_eligible(NOW) is False
    assert {reason.code for reason in result.reason_codes} >= {"MINT_AUTHORITY_ACTIVE"}


def test_active_freeze_authority_is_a_deterministic_hard_block() -> None:
    token_value = token()

    result = assess(
        token_value,
        (authority_observation(token_value, freeze_state="ACTIVE"),),
    )

    assert result.disposition is RiskDisposition.BLOCK
    assert result.hard_blocks == ("FREEZE_AUTHORITY_ACTIVE",)
    assert result.execution_eligible(NOW) is False


def test_missing_authority_evidence_is_unknown_and_not_safe() -> None:
    token_value = token()

    result = assess(token_value, ())

    assert result.disposition is RiskDisposition.UNKNOWN
    assert result.critical_evidence_state is QualityState.UNKNOWN
    assert "CRITICAL_AUTHORITY_EVIDENCE_MISSING" in result.hard_blocks
    assert result.execution_eligible(NOW) is False


def test_stale_authority_evidence_is_unknown_and_not_execution_eligible() -> None:
    token_value = token()
    stale = authority_observation(
        token_value,
        observed_at=NOW - timedelta(minutes=30),
    )

    result = assess(token_value, (stale,))

    assert result.disposition is RiskDisposition.UNKNOWN
    assert result.critical_evidence_state is QualityState.STALE
    assert "CRITICAL_EVIDENCE_STALE" in result.hard_blocks
    assert result.execution_eligible(NOW) is False


def test_conflicting_authority_snapshots_are_unknown() -> None:
    token_value = token()
    first = authority_observation(token_value, source_id="helius:first")
    second = authority_observation(
        token_value,
        mint_state="ACTIVE",
        source_id="helius:second",
    )

    result = assess(token_value, (first, second))

    assert result.disposition is RiskDisposition.UNKNOWN
    assert result.critical_evidence_state is QualityState.CONFLICTED
    assert "CRITICAL_AUTHORITY_EVIDENCE_CONFLICT" in result.hard_blocks
    assert result.execution_eligible(NOW) is False


def test_token_2022_extensions_are_retained_as_advisory_security_evidence() -> None:
    token_value = token(token_program="spl-token-2022")

    result = assess(
        token_value,
        (
            authority_observation(
                token_value,
                token_program="spl-token-2022",
                token_extensions=("permanent_delegate", "transfer_hook"),
            ),
        ),
    )

    assert result.disposition is RiskDisposition.WARN
    assert result.hard_blocks == ()
    assert "TOKEN_2022_PROGRAM" in result.warnings
    assert "TOKEN_2022_SECURITY_EXTENSION" in result.warnings
    assert result.execution_eligible(NOW) is False


def test_malformed_token_2022_extensions_fail_closed() -> None:
    token_value = token(token_program="spl-token-2022")

    result = assess(
        token_value,
        (
            authority_observation(
                token_value,
                token_program="spl-token-2022",
                token_extensions="not-a-sequence",
            ),
        ),
    )

    assert result.disposition is RiskDisposition.UNKNOWN
    assert result.critical_evidence_state is QualityState.INVALID
    assert "CRITICAL_TOKEN_2022_METADATA_INVALID" in result.hard_blocks
    assert result.execution_eligible(NOW) is False


def test_rugcheck_block_finding_is_not_a_sole_authority_hard_block() -> None:
    token_value = token()
    finding = risk_finding("HONEYPOT", RiskSeverity.BLOCK)

    result = assess(
        token_value,
        (authority_observation(token_value),),
        security_findings=(finding,),
    )

    assert result.disposition is RiskDisposition.WARN
    assert result.hard_blocks == ()
    assert "RUGCHECK_UNCORROBORATED_BLOCK" in result.warnings
    assert result.execution_eligible(NOW) is False


def test_provider_verification_is_informational_and_never_endorsement() -> None:
    token_value = token()
    verified = risk_finding("VERIFICATION_STATUS", RiskSeverity.INFO)

    result = assess(
        token_value,
        (authority_observation(token_value),),
        security_findings=(verified,),
    )

    assert result.disposition is RiskDisposition.PASS
    assert result.hard_blocks == ()
    assert "VERIFICATION_STATUS_INFORMATIONAL" in {
        reason.code for reason in result.reason_codes
    }
    assert result.execution_eligible(NOW) is True
