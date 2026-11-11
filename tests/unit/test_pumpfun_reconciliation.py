from scripts.reconcile_pumpfun_launches import build_inventory

from memeradar_providers.protocol_registry import PUMP_FUN_BUY_TAG, PUMP_FUN_CREATE_TAG
from memeradar_providers.pump_fun_idl import PUMP_FUN_PROGRAM_ID


def event(source_id, **changes):
    row = {
        "id": source_id,
        "kind": "chain.event",
        "source_id": source_id,
        "provider": "chain.integrity",
        "candidate_id": source_id,
        "token_id": source_id,
        "program_id": PUMP_FUN_PROGRAM_ID,
        "discriminator_or_tag": PUMP_FUN_CREATE_TAG.hex(),
        "signature": "signature-" + source_id,
        "event_index": 0,
        "normalized_payload": {
            "instruction_type": "create",
            "mint_address": "So11111111111111111111111111111111111111112",
        },
    }
    row.update(changes)
    return row


def test_inventory_classifies_sources_and_excludes_unverified_derived_rows():
    valid = event("valid")
    foreign = event("foreign", program_id="11111111111111111111111111111111")
    buy = event(
        "buy",
        discriminator_or_tag=PUMP_FUN_BUY_TAG.hex(),
        normalized_payload={
            "instruction_type": "buy",
            "protocol_event_type": "launch",
            "mint_address": "buy",
        },
    )
    ambiguous = event(
        "ambiguous", normalized_payload={"instruction_type": "buy", "mint_address": "ambiguous"}
    )
    missing = event("missing", discriminator_or_tag=None)
    rows = [valid, foreign, buy, ambiguous, missing]
    derived = [
        {"id": "outcome-" + row["id"], "kind": "research.outcome", "token_id": row["token_id"]}
        for row in rows
    ]
    before = repr(rows + derived)
    report = build_inventory(rows, derived)
    assert report == build_inventory(list(reversed(rows)), list(reversed(derived)))
    assert repr(rows + derived) == before
    assert report["counts"] == {
        "VERIFIED_VALID_LAUNCH": 1,
        "VERIFIED_FOREIGN_PROGRAM": 1,
        "VERIFIED_NON_CREATE_INSTRUCTION": 1,
        "AMBIGUOUS_IDENTITY": 1,
        "MISSING_SOURCE_EVIDENCE": 1,
        "REQUIRES_REEVALUATION": 0,
    }
    assert report["derived"]["research.outcome"] == {"eligible": 1, "excluded": 4, "unlinked": 0}
    assert report["total_source_records"] == 5


def test_sql_inventory_is_repeatable_read_only_and_fails_on_truncation(tmp_path):
    import asyncio
    from datetime import UTC, datetime
    from uuid import uuid4

    import pytest
    from scripts.reconcile_pumpfun_launches import inventory_database
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import create_async_engine

    from memeradar_persistence import Base, ObservationRow

    pytest.importorskip("aiosqlite")
    url = f"sqlite+aiosqlite:///{tmp_path / 'inventory.db'}"
    now = datetime.now(UTC)

    async def run():
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                ObservationRow.__table__.insert(),
                [
                    {
                        "id": uuid4(),
                        "kind": "chain.event",
                        "provider": "fixture",
                        "source_id": "one",
                        "occurred_at": now,
                        "observed_at": now,
                        "ingested_at": now,
                        "parser_version": "v1",
                        "quality_state": "FRESH",
                        "program_id": PUMP_FUN_PROGRAM_ID,
                        "discriminator_or_tag": PUMP_FUN_CREATE_TAG.hex(),
                        "signature": "sig",
                        "event_index": 0,
                        "normalized_payload": {
                            "instruction_type": "create",
                            "mint_address": "So11111111111111111111111111111111111111112",
                        },
                    }
                ],
            )
        first = await inventory_database(url, limit=1)
        assert first == await inventory_database(url, limit=1)
        assert first["counts"]["VERIFIED_VALID_LAUNCH"] == 1
        async with engine.begin() as connection:
            await connection.execute(
                ObservationRow.__table__.insert(),
                [
                    {
                        "id": uuid4(),
                        "kind": "chain.event",
                        "provider": "fixture",
                        "source_id": "two",
                        "observed_at": now,
                        "ingested_at": now,
                        "parser_version": "v1",
                        "quality_state": "UNKNOWN",
                        "normalized_payload": {},
                    }
                ],
            )
        with pytest.raises(ValueError, match="exceeds limit"):
            await inventory_database(url, limit=1)
        async with engine.connect() as connection:
            assert await connection.scalar(select(func.count()).select_from(ObservationRow)) == 2
        await engine.dispose()

    asyncio.run(run())


def test_forward_report_excludes_outcomes_without_verified_launch():
    from scripts.pumpfun_forward_report import reconciled_forward_report

    mint = "So11111111111111111111111111111111111111112"
    valid = event("valid")
    invalid = event("invalid", program_id="11111111111111111111111111111111")
    invalid["normalized_payload"] = {
        "instruction_type": "create",
        "mint_address": PUMP_FUN_PROGRAM_ID,
    }
    rows = [
        valid,
        invalid,
        {
            "kind": "research.outcome",
            "mint": mint,
            "matured": True,
            "horizon": "1h",
            "hit_10x": True,
            "executable_peak_multiple": 10,
        },
        {
            "kind": "research.outcome",
            "mint": PUMP_FUN_PROGRAM_ID,
            "matured": True,
            "horizon": "1h",
            "hit_10x": True,
            "executable_peak_multiple": 10,
        },
    ]
    report = reconciled_forward_report(rows, telegram_configured=False)
    assert report["TOTAL_LAUNCHES_OBSERVED"] == 1
    assert report["10X_COUNT"] == 1
    assert report["reconciliation"]["counts"]["VERIFIED_FOREIGN_PROGRAM"] == 1


def test_verified_launch_is_not_disqualified_by_ordinary_trades():
    from scripts.pumpfun_forward_report import reconciled_forward_report

    valid = event("valid")
    trade = event(
        "trade",
        discriminator_or_tag=PUMP_FUN_BUY_TAG.hex(),
        normalized_payload={
            "instruction_type": "buy",
            "mint_address": "So11111111111111111111111111111111111111112",
        },
    )
    report = reconciled_forward_report([valid, trade], telegram_configured=False)
    assert report["TOTAL_LAUNCHES_OBSERVED"] == 1


def test_direct_report_rejects_unreconciled_launch_and_outcome():
    from memeradar_application.pumpfun_forward_report import build_forward_report

    mint = "So11111111111111111111111111111111111111112"
    report = build_forward_report(
        [
            {"kind": "chain.event", "mint": mint, "event_type": "launch"},
            {
                "kind": "research.outcome",
                "mint": mint,
                "horizon": "1h",
                "matured": True,
                "hit_10x": True,
                "executable_peak_multiple": 10,
            },
        ]
    )
    assert report["TOTAL_LAUNCHES_OBSERVED"] == 0
    assert report["10X_COUNT"] == 0
