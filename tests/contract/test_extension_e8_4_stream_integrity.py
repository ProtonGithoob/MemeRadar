"""Keyless E8.4 extension acceptance and provider-boundary contracts."""

from pathlib import Path

from memeradar_domain import CommitmentState, RecoveryState

ROOT = Path(__file__).resolve().parents[2]


def test_e8_4_domain_and_application_boundaries_are_provider_independent() -> None:
    for relative in (
        "packages/domain/src/memeradar_domain/chain.py",
        "packages/application/src/memeradar_application/stream_integrity.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "memeradar_providers" not in source
        assert "sqlalchemy" not in source.lower()
        assert "fastapi" not in source.lower()
        assert "signer" not in source.lower()
        assert "private_key" not in source.lower()


def test_e8_4_state_names_preserve_safe_commitment_and_recovery_semantics() -> None:
    assert CommitmentState.PROCESSED_UNCONFIRMED.value == "PROCESSED_UNCONFIRMED"
    assert CommitmentState.FINALIZED.value == "FINALIZED"
    assert CommitmentState.REVERTED.value == "REVERTED"
    assert RecoveryState.RECOVERED_UNVERIFIED.value == "RECOVERED_UNVERIFIED"
    assert RecoveryState.RECOVERED_VERIFIED.value == "RECOVERED_VERIFIED"


def test_e8_4_has_no_execution_authority_in_new_domain_contracts() -> None:
    source = (
        ROOT / "packages/application/src/memeradar_application/stream_integrity.py"
    ).read_text(encoding="utf-8")
    assert "AUTO_EXECUTION = true" not in source
    assert "MANUAL_EXECUTION = true" not in source
    assert "sign_transaction" not in source
    assert "submit_transaction" not in source
