"""Persistence contracts for Alpha Caller Intelligence evidence."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import UniqueConstraint

from memeradar_domain import (
    CallerIdentity,
    CallIntent,
    CrossChainIdentityEvidence,
    IdempotencyConflict,
    IdentityEvidenceType,
    IdentityLinkState,
    Provenance,
    QualityState,
    SocialCallObservation,
    TokenIdentity,
    WalletIdentity,
)
from memeradar_persistence import (
    Base,
    CrossChainIdentityEvidenceRepository,
    SocialCallObservationRepository,
    caller_identity_from_row,
    caller_identity_to_row,
    cross_chain_identity_evidence_from_row,
    cross_chain_identity_evidence_to_row,
    social_call_observation_from_row,
    social_call_observation_to_row,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 7, 13, 0, tzinfo=UTC)
SOLANA_MINT = "So11111111111111111111111111111111111111112"
EVM_ADDRESS = "0x" + "AB" * 20


class FakeSession:
    def __init__(self) -> None:
        self.rows: dict[tuple[type[object], UUID], object] = {}
        self.added: list[object] = []

    async def get(self, model: type[object], identity: UUID) -> object | None:
        return self.rows.get((model, identity))

    def add(self, row: object) -> None:
        identity = row.id
        self.rows[(type(row), identity)] = row
        self.added.append(row)

    async def flush(self) -> None:
        return None


def source(
    source_id: str = "message-1",
    parser_version: str = "caller-persistence-v1",
) -> Provenance:
    return Provenance(
        provider="fixture.social",
        source_id=source_id,
        observed_at=NOW + timedelta(minutes=2),
        parser_version=parser_version,
        raw_payload_hash="sha256:caller-fixture",
        raw_payload_ref="fixture://caller/message-1",
    )


def caller(author_id: str = "caller-1") -> CallerIdentity:
    return CallerIdentity(platform="telegram", author_id=author_id, handle="alpha_calls")


def call_observation(
    *,
    asset: TokenIdentity | None = None,
    chain: str | None = None,
    unresolved_references: tuple[str, ...] = (),
) -> SocialCallObservation:
    if asset is None and not unresolved_references:
        asset = TokenIdentity(mint_address=SOLANA_MINT)
    return SocialCallObservation(
        source="telegram",
        message_id="message-1",
        caller_identity=caller(),
        published_at=NOW,
        observed_at=NOW + timedelta(minutes=2),
        ingested_at=NOW + timedelta(minutes=3),
        provenance=(source(),),
        asset=asset,
        chain=chain,
        unresolved_references=unresolved_references,
        intent=CallIntent.BULLISH,
        confidence=Decimal("0.80"),
        quality_state=QualityState.FRESH,
    )


def linkage(chain: str) -> CrossChainIdentityEvidence:
    return CrossChainIdentityEvidence(
        caller_identity=caller(),
        wallet=WalletIdentity(address=EVM_ADDRESS, chain=chain),
        evidence_type=IdentityEvidenceType.TEMPORAL_CORRELATION,
        link_state=IdentityLinkState.AMBIGUOUS,
        confidence=Decimal("0.42"),
        observed_at=NOW + timedelta(minutes=4),
        provenance=(source(f"link-{chain}"),),
        evidence_refs=("flow:before-call",),
    )


def test_identity_and_social_call_rows_round_trip_chain_and_provenance() -> None:
    original = call_observation()

    caller_row = caller_identity_to_row(original.caller_identity)
    call_row = social_call_observation_to_row(original, caller_row.id)
    restored_caller = caller_identity_from_row(caller_row)
    restored_call = social_call_observation_from_row(call_row, restored_caller)

    assert restored_caller == original.caller_identity
    assert restored_call.canonical_id == original.canonical_id
    assert restored_call.canonical_asset_id == original.canonical_asset_id
    assert restored_call.published_at == original.published_at
    assert restored_call.ingested_at == original.ingested_at
    assert restored_call.provenance == original.provenance


def test_unresolved_asset_evidence_round_trips_without_creating_token_identity() -> None:
    original = call_observation(asset=None, chain="bnb", unresolved_references=("$MEME",))
    caller_row = caller_identity_to_row(original.caller_identity)
    row = social_call_observation_to_row(original, caller_row.id)
    restored = social_call_observation_from_row(row, original.caller_identity)

    assert restored.asset is None
    assert restored.canonical_asset_id is None
    assert restored.chain.value == "bnb"
    assert restored.unresolved_references == ("$MEME",)


def test_social_call_repository_is_idempotent_and_allows_edit_state_update() -> None:
    session = FakeSession()
    repository = SocialCallObservationRepository(session)
    original = call_observation()

    first = asyncio.run(repository.add(original))
    duplicate = asyncio.run(repository.add(original))
    edited = replace(
        original,
        edited=True,
        ingested_at=NOW + timedelta(minutes=5),
        provenance=(source(parser_version="caller-persistence-v2"),),
    )
    updated = asyncio.run(repository.add(edited))

    assert first.id == duplicate.id == updated.id
    assert len(session.added) == 2  # caller identity plus one social call row
    assert social_call_observation_from_row(updated, original.caller_identity).edited is True
    assert asyncio.run(repository.get(updated.id)).provenance[0].parser_version == (
        "caller-persistence-v2"
    )

    conflicting = replace(original, caller_identity=caller("different-caller"))
    with pytest.raises(IdempotencyConflict, match="social call"):
        asyncio.run(repository.add(conflicting))


def test_cross_chain_identity_repository_keeps_same_evm_address_separate() -> None:
    session = FakeSession()
    repository = CrossChainIdentityEvidenceRepository(session)
    bnb = linkage("bnb")
    robinhood = linkage("robinhood")

    bnb_row = asyncio.run(repository.add(bnb))
    robinhood_row = asyncio.run(repository.add(robinhood))

    assert bnb_row.id != robinhood_row.id
    assert len(session.added) == 3  # caller identity plus one row per chain
    assert cross_chain_identity_evidence_from_row(
        bnb_row,
        bnb.caller_identity,
    ).canonical_wallet_id == f"bnb:{EVM_ADDRESS.lower()}"
    assert cross_chain_identity_evidence_from_row(
        robinhood_row,
        robinhood.caller_identity,
    ).canonical_wallet_id == f"robinhood:{EVM_ADDRESS.lower()}"


def test_cross_chain_identity_row_key_contains_provider_source_and_chain_address() -> None:
    row = cross_chain_identity_evidence_to_row(linkage("bnb"), caller_identity_to_row(caller()).id)

    assert row.provider == "fixture.social"
    assert row.source_id == "link-bnb"
    assert row.wallet_chain == "bnb"
    assert row.wallet_address == EVM_ADDRESS.lower()


def test_alpha_caller_tables_and_unique_keys_are_declared() -> None:
    tables = Base.metadata.tables

    assert {
        "caller_identities",
        "social_call_observations",
        "cross_chain_identity_evidence",
    } <= set(tables)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"platform", "author_id"}
        for constraint in tables["caller_identities"].constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns}
        == {"provider", "source", "message_id"}
        for constraint in tables["social_call_observations"].constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {
            "provider",
            "source_id",
            "wallet_chain",
            "wallet_address",
            "cluster_id",
        }
        == {column.name for column in constraint.columns}
        for constraint in tables["cross_chain_identity_evidence"].constraints
    )


def test_alpha_caller_migration_follows_multichain_identity() -> None:
    migration = (
        ROOT / "infra" / "alembic" / "versions" / "0008_alpha_caller_intelligence.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0008_alpha_caller_intelligence"' in migration
    assert 'down_revision: str | None = "0007_multichain_identity"' in migration
    assert 'op.create_table(\n        "caller_identities"' in migration
    assert 'op.create_table(\n        "social_call_observations"' in migration
    assert 'op.create_table(\n        "cross_chain_identity_evidence"' in migration
    assert 'op.drop_table("cross_chain_identity_evidence")' in migration
