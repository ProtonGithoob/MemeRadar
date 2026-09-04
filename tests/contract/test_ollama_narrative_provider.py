"""Contract checks for local Ollama and explicit disabled narrative ports."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from memeradar_application.provider_contracts import (
    NarrativeEvidence,
    NarrativeInput,
    NarrativePort,
    ProviderRequestContext,
)
from memeradar_domain import Provenance
from memeradar_providers.narrative import (
    DisabledNarrativeAdapter,
    OllamaNarrativeAdapter,
)
from memeradar_providers.transport import ProviderTransport, RetryPolicy

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "providers" / "ollama" / "generate.json"
NOW = datetime(2026, 8, 27, 21, 0, tzinfo=UTC)


def test_ollama_adapter_is_an_advisory_narrative_port() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    request = _narrative_input()

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async def scenario() -> object:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = OllamaNarrativeAdapter(
            "http://fixture.ollama.example:11434",
            model="qwen3:latest",
            client=client,
            transport=ProviderTransport(retry_policy=RetryPolicy(max_attempts=1)),
            clock=lambda: NOW,
        )
        try:
            port: NarrativePort = adapter
            return await port.summarize(request)
        finally:
            await client.aclose()

    snapshot = asyncio.run(scenario())
    assert snapshot.provenance.provider == "ollama"
    assert snapshot.advisory is True
    assert snapshot.execution_eligible(NOW) is False
    assert OllamaNarrativeAdapter.capabilities == frozenset({"narrative"})


def test_disabled_adapter_exposes_no_narrative_capability() -> None:
    adapter = DisabledNarrativeAdapter()
    assert adapter.capabilities == frozenset()
    assert asyncio.run(adapter.check_health(context=_narrative_input().context)) == {
        "status": "disabled"
    }


def _narrative_input() -> NarrativeInput:
    return NarrativeInput(
        context=ProviderRequestContext(
            correlation_id="ollama-contract",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        evidence=(
            NarrativeEvidence(
                evidence_id="contract-evidence",
                kind="social_post",
                content="bounded evidence",
                observed_at=NOW,
                provenance=Provenance(
                    provider="fixture",
                    source_id="contract-evidence",
                    observed_at=NOW,
                    parser_version="fixture-v1",
                ),
            ),
        ),
    )
