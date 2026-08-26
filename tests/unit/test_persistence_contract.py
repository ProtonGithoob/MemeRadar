"""Contract tests for the SQLAlchemy persistence boundary."""

from pathlib import Path

from sqlalchemy import UniqueConstraint

from memeradar_persistence import Base

ROOT = Path(__file__).resolve().parents[2]


def test_core_persistence_tables_are_declared() -> None:
    expected = {
        "tokens",
        "pools",
        "candidates",
        "observations",
        "feature_snapshots",
        "risk_assessments",
        "score_snapshots",
        "state_transitions",
        "portfolios",
        "positions",
        "alerts",
        "domain_events",
        "outbox",
    }

    assert expected <= set(Base.metadata.tables)


def test_idempotency_and_identity_constraints_are_explicit() -> None:
    tables = Base.metadata.tables

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"mint_address"}
        for constraint in tables["tokens"].constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"provider", "kind", "source_id"}
        for constraint in tables["observations"].constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"candidate_id", "idempotency_key"}
        for constraint in tables["state_transitions"].constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"idempotency_key"}
        for constraint in tables["outbox"].constraints
    )


def test_query_indexes_cover_candidate_ordering_observation_windows_and_outbox() -> None:
    indexes = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name is not None
    }

    assert {
        "ix_candidates_state_latest_score",
        "ix_observations_kind_occurred_at",
        "ix_observations_token_kind_occurred",
        "ix_outbox_available",
        "ix_outbox_processing",
    } <= indexes


def test_outbox_processing_columns_support_leases_and_dead_letters() -> None:
    columns = Base.metadata.tables["outbox"].c

    assert {
        "status",
        "claim_token",
        "lease_expires_at",
        "dead_lettered_at",
    } <= {column.name for column in columns}
    assert columns["status"].nullable is False


def test_domain_source_has_no_persistence_or_framework_imports() -> None:
    forbidden = ("sqlalchemy", "fastapi", "asyncpg", "memeradar_persistence")
    domain_root = ROOT / "packages" / "domain" / "src"

    for source_file in domain_root.rglob("*.py"):
        source = source_file.read_text()
        assert not any(token in source for token in forbidden), source_file
