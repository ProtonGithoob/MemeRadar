"""Keyless contracts for repository-owned RugCheck fixtures."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import ProviderRequestContext, RiskDataRequest
from memeradar_domain import QualityState, TokenIdentity
from memeradar_providers.rugcheck import RugCheckRestAdapter

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "rugcheck"
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="rugcheck-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture(name: str) -> Mapping[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def test_rugcheck_fixtures_are_deterministic_and_credential_free() -> None:
    for name in ("summary_safe.json", "summary_risks.json"):
        raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert "api_key" not in raw.lower()
        assert "authorization" not in raw.lower()
        assert "private_key" not in raw.lower()
        payload = fixture(name)
        assert isinstance(payload["risks"], list)
        assert json.dumps(payload, sort_keys=True, separators=(",", ":")) == json.dumps(
            json.loads(raw), sort_keys=True, separators=(",", ":")
        )


def test_risk_fixture_replays_through_read_only_adapter() -> None:
    payload = fixture("summary_risks.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/v1/tokens/{MINT}/report/summary"
        assert request.headers["x-correlation-id"] == "rugcheck-fixture-contract"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        client=client,
        clock=lambda: NOW,
    )
    try:
        findings = asyncio.run(
            adapter.assess(
                RiskDataRequest(
                    context=context(),
                    token=TokenIdentity(mint_address=MINT),
                )
            )
        )
    finally:
        asyncio.run(client.aclose())

    assert len(findings) == 4
    assert findings[1].severity.value == "BLOCK"
    assert all(item.quality_state is QualityState.FRESH for item in findings)
    assert {item.provenance.provider for item in findings} == {"rugcheck"}
