"""Keyless composition contract for Phase 3 Sprint 3.1."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

from memeradar_application.provider_contracts import (
    OnChainRequest,
    ProviderRequestContext,
    RiskDataRequest,
)
from memeradar_application.token_security import TokenSecurityEvaluator
from memeradar_domain import RiskDisposition, TokenIdentity
from memeradar_providers.helius import HeliusRpcAdapter
from memeradar_providers.rugcheck import RugCheckRestAdapter

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="phase3-sprint3-1-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def load_fixture(name: str) -> dict[str, object]:
    if name.startswith("helius/"):
        path = ROOT / "fixtures" / "providers" / name
    else:
        path = ROOT / "fixtures" / "providers" / "rugcheck" / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_helius_authority_and_rugcheck_findings_compose_without_provider_bypass() -> None:
    helius_payload = load_fixture("helius/get_asset_token.json")
    rugcheck_payload = load_fixture("summary_risks.json")

    async def helius_handler(request: httpx.Request) -> httpx.Response:
        assert b"getAsset" in request.content
        return httpx.Response(200, json=helius_payload)

    async def rugcheck_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/v1/tokens/{MINT}/report/summary"
        return httpx.Response(200, json=rugcheck_payload)

    helius_client = httpx.AsyncClient(transport=httpx.MockTransport(helius_handler))
    rugcheck_client = httpx.AsyncClient(transport=httpx.MockTransport(rugcheck_handler))
    token = TokenIdentity(mint_address=MINT)
    helius = HeliusRpcAdapter(
        "https://fixture.helius.example/rpc",
        client=helius_client,
        clock=lambda: NOW,
    )
    rugcheck = RugCheckRestAdapter(
        "https://fixture.rugcheck.example",
        client=rugcheck_client,
        clock=lambda: NOW,
    )
    try:
        observations = asyncio.run(helius.enrich(OnChainRequest(context=context(), token=token)))
        findings = asyncio.run(rugcheck.assess(RiskDataRequest(context=context(), token=token)))
    finally:
        asyncio.run(helius_client.aclose())
        asyncio.run(rugcheck_client.aclose())

    assessment = TokenSecurityEvaluator().evaluate(
        uuid4(),
        token,
        observations,
        security_findings=findings,
        now=NOW,
        config_hash="phase3-sprint3-1-fixture",
    )

    assert assessment.disposition is RiskDisposition.BLOCK
    assert "MINT_AUTHORITY_ACTIVE" in assessment.hard_blocks
    assert "RUGCHECK_UNCORROBORATED_BLOCK" in assessment.warnings
    assert {item.provenance.provider for item in observations} == {"helius"}
    assert {item.provenance.provider for item in findings} == {"rugcheck"}
    assert assessment.execution_eligible(NOW) is False
