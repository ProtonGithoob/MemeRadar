"""Provider-independent author trust and social velocity tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.provider_contracts import SocialMention
from memeradar_application.social_intelligence import (
    AuthorRegistryEntry,
    AuthorTrustScorer,
    AuthorTrustTier,
    SocialAuthorRegistry,
    SocialVelocityPolicy,
    SocialVelocityScorer,
)
from memeradar_domain import Provenance, QualityState, TokenIdentity

NOW = datetime(2026, 8, 27, 20, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
TOKEN = TokenIdentity(mint_address=MINT)


def mention(
    source_id: str,
    author_id: str,
    posted_at: datetime,
    *,
    fingerprint: str | None = None,
    metrics: dict[str, object] | None = None,
    quality_state: QualityState = QualityState.FRESH,
    token: TokenIdentity = TOKEN,
    observed_at: datetime = NOW,
) -> SocialMention:
    fingerprint_value = fingerprint or f"sha256:{source_id}"
    return SocialMention(
        provenance=Provenance(
            provider="social-fixture",
            source_id=source_id,
            observed_at=observed_at,
            parser_version="social-fixture-v1",
        ),
        author_id=author_id,
        posted_at=posted_at,
        observed_at=observed_at,
        ingested_at=observed_at,
        text_fingerprint=fingerprint_value,
        metrics=metrics or {},
        token_id=token.id,
        referenced_mint=token.mint_address,
        quality_state=quality_state,
        referenced_ticker="MEME",
        duplicate_cluster=(f"copy:{fingerprint_value}" if fingerprint else None),
    )


def test_author_registry_is_bounded_explicit_and_does_not_promote_from_mentions() -> None:
    registry = SocialAuthorRegistry(
        entries=(AuthorRegistryEntry("author-entry", tier=AuthorTrustTier.TRUSTED),),
        trusted_author_ids=("author-trusted",),
        kol_author_ids=("author-kol",),
        blocked_author_ids=("author-blocked",),
    )

    assert registry.resolve("author-entry").tier is AuthorTrustTier.TRUSTED
    assert registry.resolve("author-trusted").tier is AuthorTrustTier.TRUSTED
    assert registry.resolve("author-kol").tier is AuthorTrustTier.KOL
    assert registry.resolve("author-blocked").tier is AuthorTrustTier.BLOCKED
    assert registry.resolve("unlisted") is None

    with pytest.raises(ValueError, match="conflicting"):
        SocialAuthorRegistry(trusted_author_ids=("same",), kol_author_ids=("same",))
    with pytest.raises(ValueError, match="bound"):
        SocialAuthorRegistry(max_entries=1, trusted_author_ids=("a", "b"))

    trusted_mentions = (
        mention("trusted-1", "author-trusted", NOW - timedelta(seconds=30)),
        mention("unlisted-1", "unlisted", NOW - timedelta(seconds=20)),
    )
    scores = AuthorTrustScorer().score(
        trusted_mentions,
        registry,
        now=NOW,
        config_hash="social-intelligence-test",
    )
    by_author = {score.author_id: score for score in scores}
    assert by_author["author-trusted"].registry_tier is AuthorTrustTier.TRUSTED
    assert by_author["unlisted"].registry_tier is AuthorTrustTier.UNKNOWN
    assert "AUTHOR_UNLISTED" in {reason.code for reason in by_author["unlisted"].reason_codes}
    assert by_author["unlisted"].execution_eligible(NOW) is False


def test_author_trust_respects_explicit_tiers_and_coordinates_are_penalized() -> None:
    registry = SocialAuthorRegistry(
        trusted_author_ids=("trusted",),
        kol_author_ids=("kol",),
        blocked_author_ids=("blocked",),
    )
    copied = "sha256:copied"
    mentions = (
        mention(
            "kol-1",
            "kol",
            NOW - timedelta(seconds=20),
            fingerprint=copied,
            metrics={"like_count": 20, "impression_count": 1000},
        ),
        mention(
            "trusted-1",
            "trusted",
            NOW - timedelta(seconds=15),
            fingerprint=copied,
            metrics={"like_count": 10, "impression_count": 1000},
        ),
        mention(
            "blocked-1",
            "blocked",
            NOW - timedelta(seconds=10),
            metrics={"like_count": 100, "impression_count": 100},
        ),
        mention(
            "unknown-1",
            "unknown",
            NOW - timedelta(seconds=5),
            metrics={"like_count": 1, "impression_count": 1000},
        ),
    )
    scores = AuthorTrustScorer().score(
        mentions,
        registry,
        now=NOW,
        config_hash="social-intelligence-test",
    )
    by_author = {score.author_id: score for score in scores}

    assert by_author["blocked"].score == Decimal("0")
    assert by_author["kol"].score > by_author["trusted"].score
    assert by_author["trusted"].score > by_author["unknown"].score
    assert by_author["kol"].duplicate_ratio == Decimal("1")
    assert by_author["kol"].coordination_ratio == Decimal("1")
    assert by_author["kol"].score < Decimal("100")
    assert by_author["kol"].confidence > Decimal("0")
    assert by_author["kol"].freshness.is_fresh(NOW)
    assert by_author["kol"].execution_eligible(NOW) is False

    replay = AuthorTrustScorer().score(
        mentions,
        registry,
        now=NOW,
        config_hash="social-intelligence-test",
    )
    assert replay == scores


def test_social_velocity_uses_bounded_windows_unique_authors_and_penalties() -> None:
    copied = "sha256:copied"
    mentions = (
        mention("m-1", "author-1", NOW - timedelta(seconds=15), fingerprint=copied),
        mention("m-2", "author-2", NOW - timedelta(seconds=30), fingerprint=copied),
        mention(
            "m-3",
            "author-3",
            NOW - timedelta(minutes=3),
            metrics={"like_count": 5, "impression_count": 100},
        ),
        mention(
            "m-4",
            "author-4",
            NOW - timedelta(minutes=10),
            metrics={"like_count": 2, "impression_count": 100, "spam_probability": "0.9"},
        ),
        mention(
            "future",
            "author-future",
            NOW + timedelta(seconds=10),
            observed_at=NOW + timedelta(seconds=20),
        ),
    )
    scorer = SocialVelocityScorer(
        policy=SocialVelocityPolicy(
            velocity_1m_cap=2,
            velocity_5m_cap=4,
            velocity_15m_cap=6,
        )
    )
    result = scorer.score(mentions, now=NOW, config_hash="social-intelligence-test")[0]

    assert result.mention_count == 4
    assert result.window_counts == {"1m": 2, "5m": 3, "15m": 4}
    assert result.unique_author_counts == {"1m": 2, "5m": 3, "15m": 4}
    assert result.duplicate_ratio == Decimal("0.5")
    assert result.spam_ratio == Decimal("0.25")
    assert result.coordination_ratio == Decimal("0.5")
    assert result.engagement_quality is not None
    assert result.penalties["duplicate"] > Decimal("0")
    assert result.penalties["spam"] > Decimal("0")
    assert result.penalties["coordination"] > Decimal("0")
    assert result.score < Decimal("100")
    assert result.score >= Decimal("0")
    assert result.confidence == Decimal("0")
    assert result.quality_state is QualityState.INVALID
    assert "FUTURE_SOCIAL_MENTION_EXCLUDED" in {reason.code for reason in result.reason_codes}
    assert result.execution_eligible(NOW) is False


def test_social_velocity_groups_tokens_and_fails_closed_for_stale_evidence() -> None:
    second_token = TokenIdentity(mint_address="11111111111111111111111111111113")
    mentions = (
        mention("fresh", "author-1", NOW - timedelta(seconds=20)),
        mention(
            "stale",
            "author-2",
            NOW - timedelta(seconds=10),
            quality_state=QualityState.STALE,
        ),
        mention(
            "second-token",
            "author-3",
            NOW - timedelta(seconds=10),
            token=second_token,
        ),
    )
    results = SocialVelocityScorer().score(
        mentions,
        now=NOW,
        config_hash="social-intelligence-test",
    )
    by_token = {result.token_id: result for result in results}

    assert len(results) == 2
    assert by_token[TOKEN.id].quality_state is QualityState.STALE
    assert by_token[TOKEN.id].score == Decimal("0")
    assert by_token[TOKEN.id].confidence == Decimal("0")
    assert by_token[second_token.id].quality_state is QualityState.FRESH
    assert by_token[second_token.id].score > Decimal("0")
    assert all(
        result.freshness.is_fresh(NOW) is (result.quality_state is QualityState.FRESH)
        for result in results
    )
