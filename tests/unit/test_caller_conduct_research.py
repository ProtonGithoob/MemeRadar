import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from memeradar_application.correlation import build_caller_conduct_research_projection
from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    Observation,
    Provenance,
    QualityState,
    SocialCallObservation,
    TokenIdentity,
)
from memeradar_persistence import (
    Base,
    FeatureSnapshotRow,
    ObservationRow,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_worker.caller_conduct_research import process_with_caller_conduct_research
from memeradar_worker.early_discovery import _BoundRuntimeRepositories

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
OTHER_MINT = "11111111111111111111111111111112"


def call(
    *,
    author: str,
    token: TokenIdentity,
    message_id: str,
    source: str = "telegram",
    published_at: datetime = NOW - timedelta(seconds=30),
    observed_at: datetime = NOW - timedelta(seconds=5),
    ingested_at: datetime = NOW,
) -> SocialCallObservation:
    return SocialCallObservation(
        source=source,
        message_id=message_id,
        caller_identity=CallerIdentity(platform="telegram", author_id=author),
        published_at=published_at,
        observed_at=observed_at,
        ingested_at=ingested_at,
        provenance=(
            Provenance(
                provider=f"{source}-provider",
                source_id=message_id,
                observed_at=observed_at,
                parser_version="fixture-v1",
            ),
        ),
        asset=token,
        intent=CallIntent.BULLISH,
        confidence=Decimal("0.9"),
        quality_state=QualityState.FRESH,
    )


def test_projection_is_bounded_point_in_time_deduplicated_and_shadow_only() -> None:
    token = TokenIdentity(mint_address=MINT, id=uuid4())
    same_mint = TokenIdentity(mint_address=MINT, id=uuid4())
    other_token = TokenIdentity(mint_address=OTHER_MINT, id=uuid4())
    first = call(author="alpha", token=token, message_id="first")
    duplicate = call(author="alpha", token=same_mint, message_id="duplicate", source="x")
    related = call(
        author="beta",
        token=same_mint,
        message_id="related",
        published_at=NOW - timedelta(seconds=25),
    )
    other = call(author="alpha", token=other_token, message_id="other-token")
    late = call(
        author="late",
        token=same_mint,
        message_id="late-ingested",
        observed_at=NOW + timedelta(seconds=1),
        ingested_at=NOW + timedelta(seconds=1),
    )

    result = build_caller_conduct_research_projection(
        token,
        (first, duplicate, related, other, late),
        as_of=NOW,
    )

    assert result["version"] == "caller-conduct-research-v1"
    assert result["sample_size"] == 2
    assert result["caller_count"] == 2
    assert result["available_at"] == NOW
    assert result["available_at"] <= result["as_of"]
    assert result["quality_state"] == QualityState.FRESH.value
    assert result["source_coverage"] == "UNKNOWN"
    assert result["no_lookahead_verified"] is True
    assert result["classification_counts"]["COORDINATED_CALL_CLUSTER"] == 2
    assert set(result["evidence_refs"]) >= {"first", "duplicate", "related"}
    assert "score" not in result
    reordered = build_caller_conduct_research_projection(
        token,
        (late, related, first, duplicate, other),
        as_of=NOW,
    )
    assert result == reordered


def test_empty_or_unavailable_social_evidence_stays_unknown() -> None:
    result = build_caller_conduct_research_projection(
        TokenIdentity(mint_address=MINT),
        (),
        as_of=NOW,
    )

    assert result["sample_size"] == 0
    assert result["caller_count"] == 0
    assert result["available_at"] is None
    assert result["quality_state"] == QualityState.UNKNOWN.value
    assert result["source_coverage"] == "UNKNOWN"
    assert result["no_lookahead_verified"] is True


def test_social_repository_returns_only_calls_available_for_exact_mint_at_checkpoint() -> None:
    async def run() -> None:
        engine = create_database_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        token = TokenIdentity(mint_address=MINT)
        available = call(author="alpha", token=token, message_id="available")
        late = call(
            author="beta",
            token=token,
            message_id="late",
            observed_at=NOW + timedelta(seconds=1),
            ingested_at=NOW + timedelta(seconds=1),
        )
        other = call(
            author="gamma",
            token=TokenIdentity(mint_address=OTHER_MINT),
            message_id="other-mint",
        )
        async with SqlAlchemyUnitOfWork(engine) as uow:
            for item in (available, late, other):
                await uow.social_calls.save(item)
            await uow.commit()
        async with SqlAlchemyUnitOfWork(engine) as uow:
            rows = await uow.social_calls.list_for_asset(token, as_of=NOW, limit=10)
        await engine.dispose()
        assert tuple(item.message_id for item in rows) == ("available",)
        assert rows[0].asset is not None
        assert rows[0].asset.canonical_id == token.canonical_id

    asyncio.run(run())


def test_persisted_social_calls_reach_the_composed_runtime_feature_projection() -> None:
    async def run() -> None:
        engine = create_database_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        token = TokenIdentity(mint_address=MINT, id=uuid4())
        first = call(author="alpha", token=token, message_id="runtime-first")
        related = call(
            author="beta",
            token=TokenIdentity(mint_address=MINT, id=uuid4()),
            message_id="runtime-related",
            published_at=NOW - timedelta(seconds=25),
        )
        async with SqlAlchemyUnitOfWork(engine) as uow:
            await uow.social_calls.save(first)
            await uow.social_calls.save(related)
            await uow.commit()

        stores = _BoundRuntimeRepositories()
        runtime = EarlyRuntimeService(
            observation_store=stores,
            candidate_store=stores,
            feature_store=stores,
            risk_store=stores,
            score_store=stores,
            outbox_store=stores,
        )
        launch = Observation(
            kind="launch.trade",
            provenance=Provenance(
                provider="pump.fun",
                source_id="runtime-launch",
                observed_at=NOW,
                parser_version="launch-v1",
            ),
            occurred_at=NOW,
            observed_at=NOW,
            ingested_at=NOW,
            quality_state=QualityState.FRESH,
            normalized_payload={
                "chain": "solana",
                "mint_address": MINT,
                "event_type": "launch",
                "protocol_identity_verified": True,
                "liquidity_usd": "25000",
            },
        )
        async with SqlAlchemyUnitOfWork(engine) as uow:
            stores.bind(uow)
            result = await process_with_caller_conduct_research(
                runtime,
                uow,
                launch,
                token,
                as_of=NOW,
                observations=(launch,),
                safety_evidence={"protocol_identity_verified": True},
            )
            await uow.commit()
            stores.clear()

        async with SqlAlchemyUnitOfWork(engine) as uow:
            feature_rows = (
                await uow._session.scalars(
                    select(FeatureSnapshotRow).where(
                        FeatureSnapshotRow.candidate_id == result.candidate.id
                    )
                )
            ).all()
            feature_values = tuple(row.values for row in feature_rows)
            projection_count = await uow._session.scalar(
                select(func.count()).select_from(ObservationRow).where(
                    ObservationRow.kind == "research.caller_conduct_projection",
                    ObservationRow.candidate_id == result.candidate.id,
                )
            )
        await engine.dispose()

        assert feature_values
        caller_feature = feature_values[-1]["research_features"]["caller_conduct"]
        assert caller_feature["sample_size"] == 2
        assert caller_feature["classification_counts"]["COORDINATED_CALL_CLUSTER"] == 2
        assert {"runtime-first", "runtime-related"} <= set(caller_feature["evidence_refs"])
        assert projection_count == 1

    asyncio.run(run())
