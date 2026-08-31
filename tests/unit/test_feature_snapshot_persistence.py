"""Unit contracts for durable feature-snapshot serialization and idempotency."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from memeradar_domain import FeatureSnapshot, IdempotencyConflict, Provenance, QualityState
from memeradar_persistence import (
    FeatureSnapshotRepository,
    feature_snapshot_from_row,
    feature_snapshot_to_row,
    provenance_from_json,
    provenance_to_json,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def source(source_id: str = "feature:1") -> Provenance:
    return Provenance(
        provider="fixture",
        source_id=source_id,
        observed_at=NOW - timedelta(seconds=1),
        parser_version="feature-v1",
        raw_payload_hash="sha256:fixture",
        raw_payload_ref="fixture://feature/1",
    )


def snapshot() -> FeatureSnapshot:
    return FeatureSnapshot(
        id=uuid4(),
        candidate_id=uuid4(),
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        feature_version="feature-windows-v1",
        completeness=Decimal("0.875"),
        confidence=Decimal("0.81"),
        values={
            "window": "5m",
            "components": {"Momentum": Decimal("72.5")},
            "evidence_refs": ("feature:1",),
        },
        provenance=(source(),),
        config_hash="sha256:feature-config",
        quality_state=QualityState.FRESH,
    )


class FakeSession:
    def __init__(self) -> None:
        self.rows = {}
        self.added = []

    async def get(self, model, identity):
        del model
        return self.rows.get(identity)

    def add(self, row) -> None:
        self.rows[row.id] = row
        self.added.append(row)

    async def flush(self) -> None:
        return None


def test_provenance_json_round_trip_preserves_parser_and_raw_references() -> None:
    encoded = provenance_to_json((source(),))
    decoded = provenance_from_json(encoded)

    assert decoded == (source(),)
    assert encoded[0]["parser_version"] == "feature-v1"
    assert encoded[0]["raw_payload_hash"] == "sha256:fixture"
    assert encoded[0]["raw_payload_ref"] == "fixture://feature/1"


def test_feature_snapshot_row_round_trip_preserves_json_safe_values_and_freshness() -> None:
    original = snapshot()
    row = feature_snapshot_to_row(original)
    restored = feature_snapshot_from_row(row)

    assert row.id == original.id
    assert row.candidate_id == original.candidate_id
    assert row.values["components"]["Momentum"] == "72.5"
    assert restored.id == original.id
    assert restored.candidate_id == original.candidate_id
    assert restored.values["components"]["Momentum"] == "72.5"
    assert restored.provenance == original.provenance
    assert restored.feature_version == original.feature_version
    assert restored.config_hash == original.config_hash
    assert restored.quality_state is QualityState.FRESH
    assert restored.freshness.is_fresh(NOW)


def test_feature_snapshot_repository_is_idempotent_and_rejects_conflicting_reuse() -> None:
    session = FakeSession()
    repository = FeatureSnapshotRepository(session)
    original = snapshot()

    first = asyncio.run(repository.add(original))
    second = asyncio.run(repository.add(original))

    assert first is second
    assert len(session.added) == 1

    conflicting = replace(
        original,
        values={"window": "5m", "components": {"Momentum": Decimal("12")}},
    )
    with pytest.raises(IdempotencyConflict, match="feature snapshot"):
        asyncio.run(repository.add(conflicting))
