import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from memeradar_persistence.read_queries import SqlAlchemyReadQueryService


def test_metadata_uses_only_valid_create_fields_and_merges_missing_values() -> None:
    token_id = uuid4()
    rows = [
        SimpleNamespace(
            token_id=token_id, normalized_payload={"instruction_type": [], "symbol": "bad"}
        ),
        SimpleNamespace(
            token_id=token_id,
            normalized_payload={"instruction_type": "create_v2", "symbol": "  CAT  ", "name": ""},
        ),
        SimpleNamespace(
            token_id=token_id,
            normalized_payload={
                "instruction_type": "create",
                "symbol": "OTHER",
                "name": " Cat Name ",
            },
        ),
    ]

    class Result:
        def all(self):
            return rows

    class Session:
        async def scalars(self, statement):
            sql = str(statement)
            assert "observations.ingested_at" in sql
            assert "observations.quality_state" in sql
            return Result()

    service = object.__new__(SqlAlchemyReadQueryService)
    service._clock = lambda: datetime(2026, 11, 3, tzinfo=UTC)
    result = asyncio.run(service._token_display_metadata(Session(), (token_id,)))
    assert result == {token_id: ("CAT", "Cat Name")}
