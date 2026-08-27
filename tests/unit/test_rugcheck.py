"""Unit and keyless contract tests for the RugCheck risk adapter."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    RiskDataRequest,
    RiskSeverity,
)
from memeradar_domain import QualityState, TokenIdentity
from memeradar_providers.rugcheck import RugCheckRestAdapter, normalize_report_summary
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    RetryPolicy,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "rugcheck"
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
SECRET = "rugcheck-test-bearer"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="rugcheck-unit",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def token() -> TokenIdentity:
    return TokenIdentity(mint_address=MINT)


def one_shot_transport() -> ProviderTransport:
    return ProviderTransport(retry_policy=RetryPolicy(max_attempts=1))


def test_safe_summary_maps_informational_verification_with_provenance() -> None:
    payload = fixture("summary_safe.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/v1/tokens/{MINT}/report/summary"
        assert request.url.query == b""
        assert request.headers["x-correlation-id"] == "rugcheck-unit"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        client=client,
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    try:
        findings = asyncio.run(
            adapter.assess(RiskDataRequest(context=context(), token=token()))
        )
    finally:
        asyncio.run(client.aclose())

    assert len(findings) == 1
    assert findings[0].code == "VERIFICATION_STATUS"
    assert findings[0].severity is RiskSeverity.INFO
    assert findings[0].quality_state is QualityState.FRESH
    assert findings[0].provenance.provider == "rugcheck"
    assert findings[0].provenance.source_id == f"report:summary:{MINT}"
    assert findings[0].evidence_refs == (f"report:summary:{MINT}",)


def test_risk_levels_map_to_provider_neutral_findings() -> None:
    findings = normalize_report_summary(
        token(),
        fixture("summary_risks.json"),
        observed_at=NOW,
        ingested_at=NOW,
    )

    assert [finding.code for finding in findings] == [
        "RUGCHECK_LOW_LIQUIDITY",
        "RUGCHECK_MINT_AUTHORITY",
        "RUGCHECK_UNCLASSIFIED_SIGNAL",
        "VERIFICATION_STATUS",
    ]
    assert [finding.severity for finding in findings] == [
        RiskSeverity.WARN,
        RiskSeverity.BLOCK,
        RiskSeverity.UNKNOWN,
        RiskSeverity.INFO,
    ]
    assert all(finding.quality_state is QualityState.FRESH for finding in findings)
    assert all(finding.provenance.observed_at == NOW for finding in findings)


def test_optional_bearer_header_is_not_put_in_url_or_repr() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        assert SECRET.encode() not in request.url.query
        return httpx.Response(200, json={"message": "pong"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        api_key=SECRET,
        client=client,
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    try:
        assert asyncio.run(adapter.check_health(context=context())) == "pong"
    finally:
        asyncio.run(client.aclose())

    assert SECRET not in repr(adapter)


def test_report_summary_rejects_missing_or_invalid_risks() -> None:
    with pytest.raises(ProviderSchemaError):
        normalize_report_summary(
            token(),
            {"tokenProgram": "Tokenkeg"},
            observed_at=NOW,
            ingested_at=NOW,
        )
    with pytest.raises(ProviderSchemaError):
        normalize_report_summary(
            token(),
            {"risks": "not-a-list"},
            observed_at=NOW,
            ingested_at=NOW,
        )


def test_report_summary_rejects_mismatched_mint() -> None:
    payload = dict(fixture("summary_risks.json"))
    payload["mint"] = "Vote111111111111111111111111111111111111111"

    with pytest.raises(ProviderSchemaError):
        normalize_report_summary(
            token(),
            payload,
            observed_at=NOW,
            ingested_at=NOW,
        )


def test_authentication_failure_is_classified_without_body_echo() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": SECRET})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        client=client,
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderAuthenticationError):
            asyncio.run(adapter.check_health(context=context()))
    finally:
        asyncio.run(client.aclose())

    assert SECRET not in repr(adapter)


def test_timeout_is_classified_and_not_retried_when_bounded_to_one_attempt() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        client=client,
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(adapter.check_health(context=context()))
    finally:
        asyncio.run(client.aclose())


def test_base_url_rejects_credential_query_parameters() -> None:
    with pytest.raises(ValueError):
        RugCheckRestAdapter("https://fixture.rugcheck.example?api_key=secret")
