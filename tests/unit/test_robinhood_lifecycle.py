"""Robinhood launch evidence must be reconciled with canonical RPC data."""

from datetime import UTC, datetime

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import QualityState
from memeradar_providers.robinhood import (
    RobinhoodLaunchpadDecoder,
    VerifiedLaunchpadContract,
)

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
CONTRACT = "0x" + "ab" * 20
TX_HASH = "0x" + "12" * 32


def _decoder() -> RobinhoodLaunchpadDecoder:
    return RobinhoodLaunchpadDecoder(
        (
            VerifiedLaunchpadContract(
                "verified-launchpad",
                CONTRACT,
                ("0x12345678",),
                verification_source="fixture",
                verified_at=NOW,
            ),
        )
    )


def _message() -> dict[str, object]:
    return {
        "contract_address": CONTRACT,
        "selector": "0x12345678",
        "tx_hash": TX_HASH,
        "event_id": "launch-1",
        "event_type": "graduation",
        "token_address": "0x" + "cd" * 20,
    }


def _receipt() -> dict[str, object]:
    return {
        "transactionHash": TX_HASH,
        "chainId": 4663,
        "status": "0x1",
        "finality": "FINALIZED",
        "logs": [{"address": CONTRACT, "selector": "0x12345678"}],
    }


def test_verified_sequencer_event_requires_canonical_rpc_reconciliation() -> None:
    decoder = _decoder()
    context = ProviderRequestContext("rh-launch", NOW)
    unreconciled = decoder.decode(_message(), context)
    assert unreconciled.quality_state is QualityState.UNKNOWN
    assert unreconciled.normalized_payload["rpc_reconciled"] is False
    assert "RPC_RECONCILIATION_REQUIRED" in unreconciled.normalized_payload["reason_codes"]

    reconciled = decoder.decode(_message(), context, canonical_receipt=_receipt())
    assert reconciled.quality_state is QualityState.FRESH
    assert reconciled.normalized_payload["rpc_reconciled"] is True
    assert reconciled.normalized_payload["authoritative"] is True
    assert reconciled.normalized_payload["commitment"] == "FINALIZED"
    assert reconciled.normalized_payload["launchpad"] == "verified-launchpad"


def test_unverified_identity_stays_unknown_even_when_rpc_receipt_matches() -> None:
    message = _message()
    message["selector"] = "0xdeadbeef"
    observation = RobinhoodLaunchpadDecoder().decode(
        message,
        ProviderRequestContext("rh-launch-unknown", NOW),
        canonical_receipt=_receipt(),
    )
    assert observation.quality_state is QualityState.UNKNOWN
    assert observation.normalized_payload["authoritative"] is False
    assert "UNVERIFIED_LAUNCHPAD_IDENTITY" in observation.normalized_payload["reason_codes"]


def test_rpc_mismatch_or_unknown_finality_stays_unknown() -> None:
    message = _message()
    mismatched = _receipt()
    mismatched["transactionHash"] = "0x" + "34" * 32
    observation = _decoder().decode(
        message,
        ProviderRequestContext("rh-launch-mismatch", NOW),
        canonical_receipt=mismatched,
    )
    assert observation.quality_state is QualityState.UNKNOWN
    assert "RPC_RECONCILIATION_FAILED" in observation.normalized_payload["reason_codes"]

    not_final = _receipt()
    not_final.pop("finality")
    observation = _decoder().decode(
        message,
        ProviderRequestContext("rh-launch-pending", NOW),
        canonical_receipt=not_final,
    )
    assert observation.quality_state is QualityState.UNKNOWN
    assert "RPC_FINALITY_UNKNOWN" in observation.normalized_payload["reason_codes"]
