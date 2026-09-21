from memeradar_providers.pump_fun_protocol_drift import (
    IDL_SHA256,
    PINNED_REVISION,
    compare_upstream,
)


def test_pinned_upstream_matches_without_promoting_decoder_changes() -> None:
    result = compare_upstream(PINNED_REVISION, IDL_SHA256)
    assert result["status"] == "PASS"
    assert result["production_decoder_action"] == "UNCHANGED"


def test_revision_or_hash_change_is_protocol_drift() -> None:
    result = compare_upstream("changed", IDL_SHA256)
    assert result["status"] == "PROTOCOL_DRIFT_DETECTED"
    assert result["production_decoder_action"] == "UNCHANGED"
    result = compare_upstream(PINNED_REVISION, "changed")
    assert result["status"] == "PROTOCOL_DRIFT_DETECTED"
