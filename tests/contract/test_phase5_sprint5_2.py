"""Keyless replay contracts for Phase 5 Sprint 5.2 social intelligence."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import yaml

from memeradar_application.provider_contracts import SocialMention
from memeradar_application.social_intelligence import (
    AuthorRegistryEntry,
    AuthorTrustScorer,
    AuthorTrustTier,
    SocialAuthorRegistry,
    SocialVelocityScorer,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "providers" / "social_intelligence"
NOW = datetime(2026, 8, 27, 20, 0, tzinfo=UTC)


def load_fixture(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
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


def build_mentions(payload: dict[str, object], token: TokenIdentity) -> tuple[SocialMention, ...]:
    raw_mentions = payload["mentions"]
    assert isinstance(raw_mentions, list)
    result: list[SocialMention] = []
    for row in raw_mentions:
        assert isinstance(row, dict)
        observed_at = datetime.fromisoformat(str(row["observed_at"]))
        result.append(
            SocialMention(
                provenance=Provenance(
                    provider="social-intelligence-fixture",
                    source_id=str(row["source_id"]),
                    observed_at=observed_at,
                    parser_version="social-intelligence-fixture-v1",
                ),
                author_id=str(row["author_id"]),
                posted_at=datetime.fromisoformat(str(row["posted_at"])),
                observed_at=observed_at,
                ingested_at=datetime.fromisoformat(str(row["ingested_at"])),
                text_fingerprint=str(row["text_fingerprint"]),
                metrics=row.get("metrics", {}),
                token_id=token.id,
                referenced_mint=token.mint_address,
                referenced_ticker=row.get("referenced_ticker"),
                duplicate_cluster=row.get("duplicate_cluster"),
                quality_state=QualityState(str(row["quality_state"])),
            )
        )
    return tuple(result)


def build_registry(payload: dict[str, object]) -> SocialAuthorRegistry:
    raw_registry = payload["registry"]
    assert isinstance(raw_registry, dict)
    raw_entries = raw_registry.get("entries", [])
    assert isinstance(raw_entries, list)
    entries = tuple(
        AuthorRegistryEntry(
            author_id=str(row["author_id"]),
            tier=AuthorTrustTier(str(row["tier"])),
            label=str(row["label"]),
        )
        for row in raw_entries
        if isinstance(row, dict)
    )
    return SocialAuthorRegistry(
        entries=entries,
        trusted_author_ids=tuple(str(value) for value in raw_registry["trusted_author_ids"]),
        kol_author_ids=tuple(str(value) for value in raw_registry["kol_author_ids"]),
        blocked_author_ids=tuple(str(value) for value in raw_registry["blocked_author_ids"]),
    )


def test_social_intelligence_fixture_replays_author_and_velocity_scores() -> None:
    payload = load_fixture("replay.json")
    assert_credential_free(payload)
    raw_token = payload["token"]
    assert isinstance(raw_token, dict)
    token = TokenIdentity(mint_address=str(raw_token["mint_address"]))
    mentions = build_mentions(payload, token)
    registry = build_registry(payload)

    trust_scores = AuthorTrustScorer().score(
        mentions,
        registry,
        now=NOW,
        config_hash="phase5-sprint5-2-fixture",
    )
    velocity_scores = SocialVelocityScorer().score(
        mentions,
        now=NOW,
        config_hash="phase5-sprint5-2-fixture",
    )
    velocity = velocity_scores[0]
    trust = {score.author_id: score for score in trust_scores}

    assert velocity.mention_count == 4
    assert velocity.window_counts == {"1m": 2, "5m": 3, "15m": 4}
    assert velocity.unique_author_counts == {"1m": 2, "5m": 3, "15m": 4}
    assert velocity.duplicate_ratio == 0.5
    assert velocity.spam_ratio == 0.25
    assert velocity.coordination_ratio == 0.5
    assert velocity.bot_heuristic_ratio == 0.5
    assert velocity.coordination_clusters
    assert velocity.quality_state is QualityState.FRESH
    assert velocity.score >= 0
    assert velocity.confidence > 0
    assert velocity.provenance and velocity.evidence_refs
    assert velocity.execution_eligible(NOW) is False
    assert trust["author-kol"].registry_tier is AuthorTrustTier.KOL
    assert trust["author-trusted"].registry_tier is AuthorTrustTier.TRUSTED
    assert trust["author-blocked"].score == 0
    assert trust["author-kol"].score > trust["author-trusted"].score
    assert trust["author-trusted"].score > trust["author-unknown"].score
    assert trust["author-kol"].coordination_ratio == 1
    assert trust["author-kol"].bot_heuristic_ratio == 1
    assert trust["author-kol"].execution_eligible(NOW) is False
    assert registry.resolve("author-entry").label == "fixture explicit author"

    assert (
        SocialVelocityScorer().score(
            mentions,
            now=NOW,
            config_hash="phase5-sprint5-2-fixture",
        )
        == velocity_scores
    )
    assert (
        AuthorTrustScorer().score(
            mentions,
            registry,
            now=NOW,
            config_hash="phase5-sprint5-2-fixture",
        )
        == trust_scores
    )


def test_social_intelligence_fixture_withholds_future_and_stale_evidence() -> None:
    payload = load_fixture("future_stale.json")
    assert_credential_free(payload)
    raw_token = payload["token"]
    assert isinstance(raw_token, dict)
    token = TokenIdentity(mint_address=str(raw_token["mint_address"]))
    result = SocialVelocityScorer().score(
        build_mentions(payload, token),
        now=NOW,
        config_hash="phase5-sprint5-2-future-stale",
    )[0]

    assert result.mention_count == 1
    assert result.window_counts == {"1m": 0, "5m": 0, "15m": 0}
    assert result.quality_state is QualityState.INVALID
    assert result.score == 0
    assert result.confidence == 0
    assert "FUTURE_SOCIAL_MENTION_EXCLUDED" in {reason.code for reason in result.reason_codes}
    assert result.execution_eligible(NOW) is False


def test_social_intelligence_is_provider_independent_and_safe_in_compose() -> None:
    source = (
        ROOT
        / "packages"
        / "application"
        / "src"
        / "memeradar_application"
        / "social_intelligence.py"
    ).read_text(encoding="utf-8")
    assert "memeradar_providers" not in source
    assert "httpx" not in source
    assert "sign(" not in source.lower()
    assert "submit(" not in source.lower()
    compose = yaml.safe_load(
        (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
