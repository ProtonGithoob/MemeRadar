"""Robinhood launch evidence must be reconciled with canonical RPC data."""

import asyncio
from datetime import UTC, datetime

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import QualityState
from memeradar_providers.robinhood import (
    ROBINHOOD_CHAIN_ID,
    RobinhoodLaunchpadDecoder,
    RobinhoodLaunchpadReconciler,
    VerifiedLaunchpadContract,
)
from memeradar_providers.transport import ProviderSchemaError

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
    assert unreconciled.provenance.provider == "robinhood-sequencer"
    assert unreconciled.normalized_payload["rpc_reconciled"] is False
    assert "RPC_RECONCILIATION_REQUIRED" in unreconciled.normalized_payload["reason_codes"]

    reconciled = decoder.decode(_message(), context, canonical_receipt=_receipt())
    assert reconciled.quality_state is QualityState.FRESH
    assert reconciled.normalized_payload["rpc_reconciled"] is True
    assert reconciled.normalized_payload["authoritative"] is True
    assert reconciled.normalized_payload["commitment"] == "FINALIZED"
    assert reconciled.normalized_payload["launchpad"] == "verified-launchpad"
    assert reconciled.provenance.provider == "evm-public-rpc:robinhood"


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


class _ReceiptProvider:
    def __init__(self, receipt: dict[str, object] | None, finality: str | None = None) -> None:
        self.receipt = receipt
        self.finality = finality
        self.calls: list[str] = []

    async def fetch_transaction_receipt(self, transaction_hash: str, *, context: object) -> object:
        del context
        self.calls.append(transaction_hash)
        return self.receipt

    async def fetch_transaction_finality(
        self, receipt: object, *, context: object
    ) -> str | None:
        del receipt, context
        return self.finality


class _ReceiptProviderWithChain(_ReceiptProvider):
    def __init__(self, receipt: dict[str, object] | None, chain_id: int) -> None:
        super().__init__(receipt)
        self.chain_id = chain_id

    async def verify_chain_id(self, *, context: object) -> int:
        del context
        if self.chain_id < 0:
            raise ProviderSchemaError("wrong canonical chain")
        return self.chain_id


def test_runtime_reconciler_fetches_canonical_receipt_without_manual_receipt_input() -> None:
    provider = _ReceiptProvider(_receipt())
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(_decoder(), provider).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime", NOW),
        )
    )

    assert provider.calls == [TX_HASH]
    assert observation.normalized_payload["rpc_reconciled"] is True
    assert observation.normalized_payload["authoritative"] is True
    assert observation.quality_state is QualityState.FRESH


def test_runtime_reconciler_keeps_missing_receipt_unknown() -> None:
    provider = _ReceiptProvider(None)
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(_decoder(), provider).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime-missing", NOW),
        )
    )

    assert observation.quality_state is QualityState.UNKNOWN
    assert observation.normalized_payload["authoritative"] is False
    assert "RPC_RECONCILIATION_REQUIRED" in observation.normalized_payload["reason_codes"]


def test_runtime_reconciler_asks_canonical_rpc_for_finality_when_receipt_omits_it() -> None:
    receipt = _receipt()
    receipt.pop("finality")
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(
            _decoder(), _ReceiptProvider(receipt, finality="FINALIZED")
        ).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime-finality", NOW),
        )
    )

    assert observation.quality_state is QualityState.FRESH
    assert observation.normalized_payload["rpc_reconciled"] is True


def test_runtime_reconciler_uses_canonical_rpc_chain_identity_for_standard_receipts() -> None:
    receipt = _receipt()
    receipt.pop("chainId")
    provider = _ReceiptProviderWithChain(receipt, ROBINHOOD_CHAIN_ID)
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(_decoder(), provider).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime-chain", NOW),
        )
    )

    assert observation.quality_state is QualityState.FRESH
    assert observation.normalized_payload["rpc_reconciled"] is True


def test_runtime_reconciler_rejects_wrong_canonical_rpc_chain_identity() -> None:
    receipt = _receipt()
    receipt.pop("chainId")
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(
            _decoder(), _ReceiptProviderWithChain(receipt, 56)
        ).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime-wrong-chain", NOW),
        )
    )

    assert observation.quality_state is QualityState.UNKNOWN
    assert "RPC_RECONCILIATION_FAILED" in observation.normalized_payload["reason_codes"]


def test_runtime_reconciler_rechecks_canonical_rpc_chain_when_receipt_has_chain_id() -> None:
    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(
            _decoder(), _ReceiptProviderWithChain(_receipt(), 56)
        ).reconcile(
            _message(),
            ProviderRequestContext("rh-runtime-wrong-endpoint", NOW),
        )
    )

    assert observation.quality_state is QualityState.UNKNOWN
    assert "RPC_RECONCILIATION_FAILED" in observation.normalized_payload["reason_codes"]


def test_runtime_reconciler_hands_final_observation_to_persistence_callback() -> None:
    provider = _ReceiptProvider(_receipt())
    persisted = []

    async def persist(observation: object) -> None:
        persisted.append(observation)

    observation = asyncio.run(
        RobinhoodLaunchpadReconciler(_decoder(), provider).reconcile_and_persist(
            _message(),
            ProviderRequestContext("rh-runtime-persist", NOW),
            persist,
        )
    )

    assert persisted == [observation]
    assert observation.normalized_payload["rpc_reconciled"] is True


def test_decoder_preserves_source_event_time_or_unknown() -> None:
    message = _message()
    message["occurred_at"] = (NOW - datetime.resolution).isoformat()
    exact = _decoder().decode(message, ProviderRequestContext("rh-time", NOW))
    missing = _decoder().decode(
        {key: value for key, value in message.items() if key != "occurred_at"},
        ProviderRequestContext("rh-time-missing", NOW),
    )

    assert exact.occurred_at == NOW - datetime.resolution
    assert missing.occurred_at is None


def test_rpc_receipt_rejects_wrong_chain_failed_tx_and_wrong_log() -> None:
    for change in (
        {"chainId": 56},
        {"status": "0x0"},
        {"logs": [{"address": "0x" + "ef" * 20, "selector": "0x12345678"}]},
        {"logs": [{"address": CONTRACT, "selector": "0xdeadbeef"}]},
    ):
        receipt = _receipt()
        receipt.update(change)
        observation = _decoder().decode(
            _message(),
            ProviderRequestContext("rh-invalid-receipt", NOW),
            canonical_receipt=receipt,
        )
        assert observation.quality_state is QualityState.UNKNOWN
        assert "RPC_RECONCILIATION_FAILED" in observation.normalized_payload["reason_codes"]
