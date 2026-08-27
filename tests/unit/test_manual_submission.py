"""Provider-independent manual mint submission contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.manual_submission import (
    ManualMintRequest,
    ManualMintSubmissionService,
)
from memeradar_application.provider_contracts import ProviderRequestContext

NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="manual-submission-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def test_service_creates_deterministic_analysis_candidate() -> None:
    result = ManualMintSubmissionService().submit(ManualMintRequest(context(), MINT))

    assert result.duplicate is False
    assert result.candidate.token.mint_address == MINT
    assert result.candidate.token.token_program == "spl-token"
    assert result.candidate.pool is None
    assert result.candidate.source_id == f"manual:{MINT}"
    assert result.candidate.provenance.provider == "manual"
    assert result.candidate.provenance.parser_version == "manual-submission-v1"
    assert result.candidate.occurred_at == NOW
    assert result.candidate.observed_at == NOW
    assert result.candidate.ingested_at == NOW


def test_repeated_submission_is_reported_duplicate_with_stable_identity() -> None:
    service = ManualMintSubmissionService()

    first = service.submit(ManualMintRequest(context(), MINT))
    second = service.submit(ManualMintRequest(context(), MINT))

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.candidate.token.id == first.candidate.token.id
    assert second.candidate.source_id == first.candidate.source_id


@pytest.mark.parametrize("mint", ("not-a-solana-mint", "", "1" * 65))
def test_service_rejects_invalid_or_oversized_mint(mint: str) -> None:
    with pytest.raises(ValueError):
        ManualMintRequest(context(), mint)


def test_service_rejects_invalid_request_types() -> None:
    with pytest.raises(TypeError):
        ManualMintSubmissionService().submit(object())  # type: ignore[arg-type]
