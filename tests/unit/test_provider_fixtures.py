"""Safe fixture recording and fake-provider tests."""

import asyncio
from datetime import UTC, datetime

import pytest

from memeradar_application.provider_contracts import ProviderCapability
from memeradar_providers.fixtures import (
    FakeProvider,
    FixtureMetadata,
    FixtureRecorder,
    FixtureRedactor,
)
from memeradar_providers.transport import ProviderUnavailableError

NOW = datetime(2026, 8, 27, 5, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def test_redactor_removes_nested_credentials_but_preserves_public_token_data() -> None:
    payload = {
        "mint": MINT,
        "api_key": "secret-api-key",
        "nested": {
            "Authorization": "Bearer secret-session",
            "access_token": "secret-access",
        },
        "url": "https://provider.example/data?api_key=secret-query&mint=" + MINT,
        "items": [{"private_key": "secret-private", "value": 7}],
    }

    redacted = FixtureRedactor().redact(payload)

    assert redacted["mint"] == MINT
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["Authorization"] == "[REDACTED]"
    assert redacted["nested"]["access_token"] == "[REDACTED]"
    assert "secret" not in str(redacted)
    assert "api_key=secret-query" not in redacted["url"]


def test_fixture_recorder_exports_deterministic_redacted_json() -> None:
    metadata = FixtureMetadata(
        provider="fixture.discovery",
        capability=ProviderCapability.CANDIDATE_DISCOVERY,
        endpoint="https://provider.example/listings?api_key=secret",
        captured_at=NOW,
        schema_version="provider-v1",
        parser_version="parser-v1",
    )
    recorder = FixtureRecorder()
    record = recorder.record(
        "listing-basic",
        metadata,
        {"api_key": "secret", "mint": MINT, "value": 1},
    )

    exported = recorder.export("listing-basic")

    assert record.metadata.redacted is True
    assert "secret" not in exported
    assert "[REDACTED]" in exported
    assert "api_key=secret" not in exported
    assert exported == recorder.export("listing-basic")
    assert recorder.names() == ("listing-basic",)

    with pytest.raises(ValueError, match="redacted"):
        FixtureMetadata(
            provider="fixture",
            capability="market_data",
            endpoint="https://provider.example",
            captured_at=NOW,
            schema_version="v1",
            parser_version="v1",
            redacted=False,
        )


def test_fake_provider_returns_configured_response_and_records_bounded_call() -> None:
    fake = FakeProvider(
        "fixture.discovery",
        responses={ProviderCapability.CANDIDATE_DISCOVERY: {"items": [MINT]}},
    )

    result = asyncio.run(
        fake.request(
            ProviderCapability.CANDIDATE_DISCOVERY,
            request_type="DiscoveryRequest",
            correlation_id="fixture-correlation",
        )
    )

    assert result == {"items": [MINT]}
    assert fake.calls == (
        {
            "capability": "candidate_discovery",
            "request_type": "DiscoveryRequest",
            "correlation_id": "fixture-correlation",
        },
    )


def test_fake_provider_can_replay_typed_failure_without_network() -> None:
    fake = FakeProvider("fixture.market")
    fake.queue_failure(ProviderCapability.MARKET_DATA, ProviderUnavailableError())

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(
            fake.request(
                ProviderCapability.MARKET_DATA,
                request_type="MarketDataRequest",
                correlation_id="fixture-correlation",
            )
        )
