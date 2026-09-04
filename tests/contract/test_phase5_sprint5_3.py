"""Keyless replay contracts for the Phase 5 Sprint 5.3 narrative seam."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from memeradar_application.narrative import NarrativeAnalyzer, NarrativePolicy
from memeradar_application.provider_contracts import (
    NarrativeEvidence,
    NarrativeInput,
    NarrativeOrganicAssessment,
    NarrativeSentiment,
    NarrativeSnapshot,
    ProviderRequestContext,
)
from memeradar_domain import Provenance, QualityState
from memeradar_providers.narrative import FixtureNarrativeAdapter

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "narrative"
NOW = datetime(2026, 8, 27, 21, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"


def fixture(name: str) -> Mapping[str, object]:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert isinstance(payload, Mapping)
    return payload


def assert_credential_free(value: object) -> None:
    credential_names = {
        "api_key",
        "access_token",
        "authorization",
        "cookie",
        "private_key",
        "seed_phrase",
        "session_token",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert str(key).lower() not in credential_names
            assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_credential_free(nested)


def narrative_input(
    *, content: str = "community discussion", evidence_id: str = "post-1"
) -> NarrativeInput:
    provenance = Provenance(
        provider="fixture.social",
        source_id=evidence_id,
        observed_at=NOW,
        parser_version="fixture-social-v1",
    )
    return NarrativeInput(
        context=ProviderRequestContext(
            correlation_id="narrative-contract",
            requested_at=NOW,
            deadline_at=NOW + timedelta(seconds=5),
        ),
        config_hash="narrative-config-v1",
        evidence=(
            NarrativeEvidence(
                evidence_id=evidence_id,
                kind="social_post",
                content=content,
                observed_at=NOW,
                provenance=provenance,
                metadata={"mint": MINT},
            ),
        ),
    )


def output(evidence_refs: tuple[str, ...] = ("post-1", "post-2")) -> NarrativeSnapshot:
    return NarrativeSnapshot(
        provenance=Provenance(
            provider="fixture-narrative",
            source_id="narrative-fixture-output-1",
            observed_at=NOW,
            parser_version="narrative-fixture-v1",
        ),
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        narrative=(
            "Several normalized posts discuss the token while promotional uncertainty remains."
        ),
        topic="token discussion",
        novelty="0.58",
        organic_assessment=NarrativeOrganicAssessment.MIXED,
        organic_probability="0.55",
        promotional_probability="0.45",
        sentiment=NarrativeSentiment.NEUTRAL,
        uncertainty="0.38",
        confidence="0.62",
        evidence_refs=evidence_refs,
        usage={
            "estimated_cost_usd": "0",
            "input_tokens": 36,
            "output_tokens": 18,
            "total_tokens": 54,
        },
        model="fixture-narrative-v1",
        schema_version="narrative-v1",
        config_hash="narrative-config-v1",
        cache_key="sha256:fixture-output",
        reason_codes=("NARRATIVE_FIXTURE",),
    )


def test_narrative_fixtures_are_deterministic_and_credential_free() -> None:
    for name in ("valid.json", "malformed.json", "injection.json"):
        raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        payload = fixture(name)
        assert json.dumps(payload, sort_keys=True, separators=(",", ":")) == json.dumps(
            json.loads(raw), sort_keys=True, separators=(",", ":")
        )
        assert_credential_free(payload)
        assert "api_key" not in raw.lower()
        assert "authorization" not in raw.lower()
        assert "private_key" not in raw.lower()


def test_valid_fixture_replays_through_optional_gateway_and_cache() -> None:
    valid_payload = fixture("valid.json")
    assert isinstance(valid_payload["data"], Mapping)
    assert valid_payload["data"]["schema_version"] == "narrative-v1"
    adapter = FixtureNarrativeAdapter(response=output(("post-1",)))
    analyzer = NarrativeAnalyzer(
        adapter,
        policy=NarrativePolicy(request_timeout_seconds=1),
        clock=lambda: NOW,
    )

    first = asyncio.run(analyzer.summarize(narrative_input()))
    second = asyncio.run(analyzer.summarize(narrative_input()))

    assert first.quality_state is QualityState.FRESH
    assert first.topic == "token discussion"
    assert first.evidence_refs == ("post-1",)
    assert first.execution_eligible(NOW) is False
    assert second.cache_hit is True
    assert adapter.calls == 1


def test_malformed_output_and_injection_content_degrade_without_blocking_analysis() -> None:
    malformed_payload = fixture("malformed.json")
    malformed = FixtureNarrativeAdapter(response=malformed_payload)
    analyzer = NarrativeAnalyzer(malformed, clock=lambda: NOW)
    unavailable = asyncio.run(analyzer.summarize(narrative_input()))
    assert unavailable.quality_state is QualityState.UNKNOWN
    assert unavailable.confidence == 0
    assert "NARRATIVE_SCHEMA_INVALID" in {reason.code for reason in unavailable.reason_codes}

    captured: list[NarrativeInput] = []

    async def callback(request: NarrativeInput) -> NarrativeSnapshot:
        captured.append(request)
        return output(("post-injection",))

    injection = fixture("injection.json")
    evidence = injection["evidence"]
    assert isinstance(evidence, list)
    content = evidence[0]["content"]
    assert isinstance(content, str)
    provider = FixtureNarrativeAdapter(callback=callback)
    result = asyncio.run(
        NarrativeAnalyzer(provider, clock=lambda: NOW).summarize(
            narrative_input(content=content, evidence_id="post-injection")
        )
    )
    assert result.quality_state is QualityState.FRESH
    assert captured[0].evidence[0].content.startswith("<UNTRUSTED_DATA>")
    assert "api key" not in captured[0].evidence[0].content.lower()
    assert "call a trading tool" not in captured[0].evidence[0].content.lower()


def test_narrative_application_boundary_is_provider_independent_and_safe() -> None:
    source = (
        ROOT / "packages" / "application" / "src" / "memeradar_application" / "narrative.py"
    ).read_text(encoding="utf-8")
    contracts = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "provider_contracts.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    assert "tools" not in source.lower()
    assert "class NarrativePort" in contracts
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
