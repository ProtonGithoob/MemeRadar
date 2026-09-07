"""Repository-fixture contract for optional multi-chain security enrichment."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import httpx

from memeradar_application.provider_contracts import ProviderRequestContext, RiskDataRequest
from memeradar_domain import Chain, TokenIdentity
from memeradar_providers.token_security import GoPlusTokenSecurityAdapter

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
BNB_TOKEN = "0x1111111111111111111111111111111111111111"


def test_security_fixture_is_deterministic_and_credential_free() -> None:
    raw = (ROOT / "fixtures" / "providers" / "token_security" / "full.json").read_text(
        encoding="utf-8"
    )
    assert "api_key" not in raw.lower()
    assert "authorization" not in raw.lower()
    assert "private_key" not in raw.lower()
    assert json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")) == json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":")
    )


def test_security_fixture_replays_through_generic_evm_adapter() -> None:
    payload = cast(
        dict[str, object],
        json.loads(
            (ROOT / "fixtures" / "providers" / "token_security" / "full.json").read_text(
                encoding="utf-8"
            )
        ),
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/token_security/56"
        assert request.url.params["contract_addresses"] == BNB_TOKEN
        assert "authorization" not in request.headers
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoPlusTokenSecurityAdapter(
        "https://fixture.security.example",
        client=client,
        clock=lambda: NOW,
    )
    try:
        findings = asyncio.run(
            adapter.assess(
                RiskDataRequest(
                    context=ProviderRequestContext(
                        "alpha-token-security-contract",
                        NOW,
                        NOW + timedelta(seconds=5),
                    ),
                    token=TokenIdentity(mint_address=BNB_TOKEN, chain=Chain.BNB),
                )
            )
        )
    finally:
        asyncio.run(client.aclose())

    assert len(findings) == 7
    assert {item.provenance.provider for item in findings} == {"goplus"}
    assert all(item.quality_state.value == "FRESH" for item in findings)
