"""M1 launch inventory: reconciliation, exclusions and reproducible cohorts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.launch_inventory import (
    LAUNCH_ELIGIBILITY_VERSION,
    DataRights,
    SlotState,
    build_cohort,
    reconcile,
    window_from_records,
)

T0 = datetime(2026, 11, 25, 12, tzinfo=UTC)
CUTOFF = T0 + timedelta(minutes=5)
MINT_A = "DUhswyJLpJhvPr4yBEW2Qwsu32p4UpgQWejysM3opump"
MINT_B = "BSi1PrxkjdbPYUUE6SjZ6fMGHgevyeAS2jzboE9Zpump"
MINT_C = "7VbJpjNgWwZ52P6bjiCRSaBTqduhwdRq852fuRh8pump"


def _record(mint: str, slot: int, sig: str, **extra: object) -> dict[str, object]:
    return {
        "mint": mint,
        "slot": slot,
        "signature": sig,
        "block_time": T0 + timedelta(seconds=(slot - 100) * 0.4),
        "instruction": "create_v2",
        **extra,
    }


_ALL_SLOTS = range(100, 110)


def _window(source: str, records, *, scanned=_ALL_SLOTS, unresolved=None, **kw):
    return window_from_records(
        source=source,
        from_slot=100,
        to_slot=109,
        cutoff=CUTOFF,
        scanned=[s for s in scanned if s not in (unresolved or {})],
        unresolved=unresolved,
        records=records,
        **kw,
    )


def test_no_trade_launch_is_in_the_cohort_and_sources_agree() -> None:
    # The cohort has no trading/listing condition: a create alone qualifies.
    primary = _window("block-scan", [_record(MINT_A, 101, "s1"), _record(MINT_B, 105, "s2")])
    independent = _window("address-index", [_record(MINT_A, 101, "s1"), _record(MINT_B, 105, "s2")])

    manifest = build_cohort(primary, independent)

    assert manifest.status == "APPROVED"
    assert manifest.eligibility_version == LAUNCH_ELIGIBILITY_VERSION
    assert [entry.mint for entry in manifest.entries] == sorted([MINT_A, MINT_B])
    assert manifest.ledger.primary_recall == 1.0


def test_overlapping_sources_add_references_without_inflating_the_denominator() -> None:
    primary = _window("block-scan", [_record(MINT_A, 101, "s1")])
    independent = _window("address-index", [_record(MINT_A, 101, "s1")])

    manifest = build_cohort(primary, independent)

    assert len(manifest.entries) == 1
    assert manifest.entries[0].sources == ("address-index", "block-scan")


def test_disagreement_is_kept_in_the_union_and_ledger() -> None:
    primary = _window("block-scan", [_record(MINT_A, 101, "s1")])
    independent = _window("address-index", [_record(MINT_A, 101, "s1"), _record(MINT_C, 107, "s3")])

    ledger = reconcile(primary, independent)
    manifest = build_cohort(primary, independent)

    assert ledger.independent_only == (MINT_C,)
    assert ledger.primary_recall == 0.5
    assert {entry.mint for entry in manifest.entries} == {MINT_A, MINT_C}
    assert manifest.status == "APPROVED_WITH_COVERAGE_GAPS"


def test_unresolved_slots_leave_the_denominator_instead_of_counting_as_misses() -> None:
    primary = _window("block-scan", [_record(MINT_A, 101, "s1")], unresolved={107: "RATE_LIMITED"})
    independent = _window("address-index", [_record(MINT_A, 101, "s1"), _record(MINT_C, 107, "s3")])

    ledger = reconcile(primary, independent)
    manifest = build_cohort(primary, independent)

    assert ledger.jointly_resolved_slots == 9
    assert ledger.independent_only == ()  # slot 107 is not jointly resolved
    assert ledger.unresolved_slots["block-scan"] == (107,)
    assert MINT_C not in {entry.mint for entry in manifest.entries}
    assert {"source": "block-scan", "slot": 107, "reason": "SLOT_UNRESOLVED",
            "detail": "RATE_LIMITED"} in manifest.exclusions
    assert primary.slot_states[107] is SlotState.UNRESOLVED


def test_replayed_duplicate_mint_with_two_creates_is_excluded_with_reason() -> None:
    records = [_record(MINT_A, 101, "s1"), _record(MINT_A, 104, "s9")]
    manifest = build_cohort(_window("block-scan", records), _window("address-index", records))

    assert manifest.entries == ()
    assert any(
        item.get("reason") == "DUPLICATE_MINT_MULTIPLE_CREATES" for item in manifest.exclusions
    )
    assert manifest.ledger.duplicate_mints == (MINT_A,)


def test_mismatched_decimals_future_dates_and_bad_identities_are_rejected() -> None:
    records = [
        _record(MINT_A, 101, "ok"),
        _record(MINT_B, 102, "decimals", decimals=9),
        _record(MINT_C, 103, "future", block_time=CUTOFF + timedelta(hours=1)),
        _record("not-a-mint", 104, "badid"),
        _record(MINT_C, 105, "notime", block_time=None),
    ]
    window = _window("block-scan", records)

    reasons = dict(window.rejected)
    assert [launch.signature for launch in window.launches] == ["ok"]
    assert "decimals 9" in reasons["decimals"]
    assert reasons["future"] == "FUTURE_DATED_OBSERVATION"
    assert "ambiguous mint" in reasons["badid"]
    assert "block_time" in reasons["notime"]


def test_failed_create_transactions_are_excluded_not_counted() -> None:
    records = [_record(MINT_A, 101, "s1"), _record(MINT_B, 102, "s2", transaction_failed=True)]
    manifest = build_cohort(_window("block-scan", records), _window("address-index", records))

    assert [entry.mint for entry in manifest.entries] == [MINT_A]
    assert {"source": "block-scan", "record": "s2", "reason": "TRANSACTION_FAILED"} in (
        manifest.exclusions
    )


def test_unknown_or_restricted_rights_cannot_enter_an_approved_manifest() -> None:
    primary = _window("block-scan", [_record(MINT_A, 101, "s1")])
    independent = _window("address-index", [_record(MINT_A, 101, "s1")])
    imported = _window(
        "third-party-dataset", [_record(MINT_A, 101, "s1")], data_rights=DataRights.UNKNOWN
    )

    manifest = build_cohort(primary, independent, extra_inputs=(imported,))

    assert manifest.status == "REJECTED_DATA_RIGHTS"
    assert manifest.entries == ()


def test_identical_inputs_give_identical_logical_digests() -> None:
    def run() -> str:
        records = [_record(MINT_B, 105, "s2"), _record(MINT_A, 101, "s1")]
        return build_cohort(
            _window("block-scan", records), _window("address-index", list(reversed(records)))
        ).digest

    assert run() == run()
    changed = build_cohort(
        _window("block-scan", [_record(MINT_A, 101, "s1")]),
        _window("address-index", [_record(MINT_A, 101, "s1")]),
    ).digest
    assert changed != run()


def test_window_must_describe_every_slot() -> None:
    window = _window("block-scan", [], scanned=range(100, 105))
    assert window.slot_states[107] is SlotState.UNRESOLVED
    assert window.unresolved_reasons[107] == "NOT_REPORTED_BY_SOURCE"
    with pytest.raises(ValueError):
        reconcile(window, window_from_records(
            source="x", from_slot=0, to_slot=1, cutoff=CUTOFF, scanned=[0, 1]
        ))
