"""Provider-independent read-query, pagination and safety contracts."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from memeradar_application.read_api import (
    AuditEventView,
    CandidateQuery,
    CandidateView,
    ConfigVersionView,
    CursorCodec,
    CursorError,
    InMemoryReadQueryService,
    ProviderHealthQuery,
    ProviderHealthView,
    ReadProviderHealthState,
    TimelineEntryView,
    TimelineQuery,
    TokenView,
    WalletQuery,
    WalletView,
)
from memeradar_domain import CandidateState, QualityState

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
WALLET_A = "11111111111111111111111111111111"


def candidate(
    score: str,
    *,
    state: CandidateState = CandidateState.WATCH,
    candidate_id: UUID | None = None,
    state_changed_at: datetime = NOW,
) -> CandidateView:
    return CandidateView(
        id=candidate_id or uuid4(),
        token_id=uuid4(),
        mint_address=MINT,
        symbol="MEME",
        name="Meme Token",
        state=state,
        discovered_at=NOW - timedelta(minutes=5),
        discovery_source="fixture",
        state_changed_at=state_changed_at,
        score=Decimal(score),
        score_confidence=Decimal("0.90"),
        risk_disposition="PASS",
        risk_quality_state=QualityState.FRESH,
    )


def test_cursor_is_opaque_versioned_and_resource_scoped() -> None:
    cursor = CursorCodec.encode("candidates", ("90", NOW.isoformat(), "candidate"))

    assert cursor
    assert "/" not in cursor
    assert CursorCodec.decode("candidates", cursor) == (
        "90",
        NOW.isoformat(),
        "candidate",
    )
    with pytest.raises(CursorError):
        CursorCodec.decode("timeline", cursor)
    with pytest.raises(CursorError):
        CursorCodec.decode("candidates", "not-a-cursor")


@pytest.mark.parametrize(
    "factory",
    (
        lambda: CandidateQuery(limit=0),
        lambda: CandidateQuery(limit=101),
        lambda: CandidateQuery(min_score=Decimal("101")),
        lambda: CandidateQuery(min_score=Decimal("80"), max_score=Decimal("70")),
        lambda: TimelineQuery(token_id=uuid4(), from_at=NOW, to_at=NOW + timedelta(days=8)),
        lambda: WalletQuery(min_score=Decimal("101")),
        lambda: ProviderHealthQuery(state="NOT_A_STATE"),
    ),
)
def test_read_queries_reject_unbounded_or_invalid_filters(factory: object) -> None:
    assert callable(factory)
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_candidate_ranking_filter_and_cursor_are_deterministic() -> None:
    first = candidate("90", candidate_id=UUID("00000000-0000-0000-0000-000000000001"))
    second = candidate("75", candidate_id=UUID("00000000-0000-0000-0000-000000000002"))
    third = candidate("60", candidate_id=UUID("00000000-0000-0000-0000-000000000003"))
    service = InMemoryReadQueryService(candidates=(third, first, second))

    page = asyncio.run(service.list_candidates(CandidateQuery(limit=2, min_score=Decimal("70"))))
    assert [item.score for item in page.items] == [Decimal("90"), Decimal("75")]
    assert page.has_more is False
    assert page.next_cursor is None

    first_page = asyncio.run(service.list_candidates(CandidateQuery(limit=1)))
    next_page = asyncio.run(
        service.list_candidates(CandidateQuery(limit=1, cursor=first_page.next_cursor))
    )
    assert [item.score for item in first_page.items] == [Decimal("90")]
    assert [item.score for item in next_page.items] == [Decimal("75")]


def test_timeline_applies_as_of_and_redacts_payload() -> None:
    token_id = uuid4()
    entries = (
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="market.observation",
            source_id="fixture:1",
            occurred_at=NOW - timedelta(seconds=2),
            observed_at=NOW - timedelta(seconds=1),
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            payload={"price": "1.20", "api_key": "secret", "nested": {"token": "safe"}},
        ),
        TimelineEntryView(
            id=uuid4(),
            token_id=token_id,
            kind="market.observation",
            source_id="fixture:2",
            occurred_at=NOW + timedelta(seconds=1),
            observed_at=NOW + timedelta(seconds=1),
            ingested_at=NOW + timedelta(seconds=1),
            quality_state=QualityState.FRESH,
            payload={"price": "1.30"},
        ),
    )
    service = InMemoryReadQueryService(timelines={token_id: entries})

    page = asyncio.run(
        service.list_timeline(
            token_id,
            TimelineQuery(token_id=token_id, as_of=NOW),
        )
    )
    assert len(page.items) == 1
    assert page.items[0].payload["api_key"] == "[REDACTED]"
    assert page.items[0].payload["nested"] == {"token": "safe"}


def test_missing_health_is_explicit_unknown_and_views_never_authorize_execution() -> None:
    token_id = uuid4()
    service = InMemoryReadQueryService(
        candidates=(candidate("88"),),
        tokens=(
            TokenView(
                id=token_id,
                chain="solana",
                mint_address=MINT,
                token_program="spl-token",
                first_seen_at=NOW,
            ),
        ),
        provider_health=(
            ProviderHealthView(
                provider="fixture",
                capability="market_data",
                state=ReadProviderHealthState.UNKNOWN,
                checked_at=NOW,
            ),
        ),
        wallets=(
            WalletView(
                address=WALLET_A,
                label="fixture wallet",
                registry_tier="TIER_A",
                recommended_tier="TIER_A",
                as_of=NOW,
                expires_at=NOW + timedelta(minutes=5),
                score=Decimal("80"),
                confidence=Decimal("0.90"),
                execution_eligible=False,
            ),
        ),
    )

    health = asyncio.run(service.list_provider_health(ProviderHealthQuery()))
    wallets = asyncio.run(service.list_wallets(WalletQuery()))
    assert health.items[0].state is ReadProviderHealthState.UNKNOWN
    assert wallets.items[0].execution_eligible is False
    assert all(item.execution_eligible is False for item in service.candidates)


def test_config_and_audit_views_redact_secret_shaped_values() -> None:
    service = InMemoryReadQueryService(
        audit_events=(
            AuditEventView(
                id=uuid4(),
                actor="operator",
                action="read",
                target="config",
                occurred_at=NOW,
                correlation_id="read-test",
                before={"bot_token": "secret"},
                after={"safe": "value"},
            ),
        ),
        config_versions=(
            ConfigVersionView(
                id=uuid4(),
                version="v1",
                created_at=NOW,
                actor="system",
                config_hash="sha256:test",
                decision_affecting=True,
                config={"api_key": "secret", "threshold": "85"},
            ),
        ),
    )

    audit = asyncio.run(service.list_audit_events())
    config = asyncio.run(service.list_config_versions())
    assert audit.items[0].before["bot_token"] == "[REDACTED]"
    assert config.items[0].config["api_key"] == "[REDACTED]"
