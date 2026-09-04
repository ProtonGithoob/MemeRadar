"""Contracts for durable exit-evaluation timeline persistence."""

from pathlib import Path

from memeradar_persistence import DomainEventRow, SqlAlchemyExitEvaluationStore

ROOT = Path(__file__).resolve().parents[2]


def test_exit_timeline_uses_the_existing_append_only_domain_event_log() -> None:
    assert SqlAlchemyExitEvaluationStore
    assert "domain_events" in DomainEventRow.__table__.metadata.tables
    assert {
        "id",
        "kind",
        "aggregate_type",
        "aggregate_id",
        "occurred_at",
        "observed_at",
        "ingested_at",
        "payload",
        "idempotency_key",
        "reason_codes",
    } <= {column.name for column in DomainEventRow.__table__.columns}
    assert (
        ROOT / "packages" / "persistence" / "src" / "memeradar_persistence" / "exit.py"
    ).exists()


def test_exit_persistence_adapter_keeps_provider_and_signing_boundaries() -> None:
    source = (
        ROOT / "packages" / "persistence" / "src" / "memeradar_persistence" / "exit.py"
    ).read_text()
    forbidden = (
        "PrivateKey",
        "secret_key",
        "sign_transaction",
        "submit_transaction",
        "QuotePort",
        "ExecutionPort",
    )
    assert not any(value in source for value in forbidden)
    assert "before_evidence_refs" in source
    assert "after_evidence_refs" in source
