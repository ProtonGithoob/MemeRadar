"""End-to-end contracts for the provider-independent early runtime service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from memeradar_application.early_runtime import EarlyRuntimeService
from memeradar_domain import Freshness, Observation, Provenance, QualityState

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
BASE_SAFETY = {
    "mint_authority_safe": True,
    "freeze_authority_safe": True,
    "liquidity": Decimal("25000"),
    "sellability": True,
    "buy_impact_bps": Decimal("120"),
    "sell_impact_bps": Decimal("140"),
}


class MemoryObservationStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], Observation] = {}

    async def add(self, observation: Observation) -> Observation:
        key = (
            observation.provenance.provider,
            observation.kind,
            observation.provenance.source_id,
        )
        existing = self.rows.setdefault(key, observation)
        assert existing == observation
        return existing


class MemoryCandidateStore:
    def __init__(self) -> None:
        self.rows = {}

    async def get(self, candidate_id: UUID):
        return self.rows.get(candidate_id)

    async def add(self, candidate):
        self.rows[candidate.id] = candidate
        return candidate


class MemoryOutbox:
    def __init__(self) -> None:
        self.events = {}

    async def enqueue(self, event, **_: object):
        existing = self.events.setdefault(event.dedupe_key, event)
        assert existing == event
        return existing


def observation(
    source_id: str,
    at: datetime,
    *,
    side: str = "buy",
    wallet: str = "wallet-a",
    market_cap: str = "47000",
    liquidity: str = "18000",
) -> Observation:
    return Observation(
        kind="launch.trade",
        provenance=Provenance(
            provider="pump.fun",
            source_id=source_id,
            observed_at=at + timedelta(seconds=1),
            parser_version="fixture-v1",
        ),
        occurred_at=at,
        observed_at=at + timedelta(seconds=1),
        ingested_at=at + timedelta(seconds=2),
        quality_state=QualityState.FRESH,
        normalized_payload={
            "chain": "solana",
            "mint_address": MINT,
            "event_type": "launch",
            "protocol_identity_verified": True,
            "side": side,
            "buyer_wallet": wallet,
            "quote_amount": "1200",
            "market_cap_usd": market_cap,
            "liquidity_usd": liquidity,
            "sellability": True,
            "buy_impact_bps": "120",
            "sell_impact_bps": "140",
        },
    )


def components(value: str) -> dict[str, Decimal]:
    return {
        "OrganicFlowAcceleration": Decimal(value),
        "WalletQuality": Decimal(value),
        "OnChainSafety": Decimal(value),
        "LiquidityAndSellability": Decimal(value),
        "LaunchMomentum": Decimal(value),
        "SmartMoneyConfluence": Decimal(value),
    }


def run(coro):
    return asyncio.run(coro)


def test_synthetic_launch_reaches_early_watch_and_projects_immutable_stage_alert() -> None:
    observations = MemoryObservationStore()
    candidates = MemoryCandidateStore()
    outbox = MemoryOutbox()
    service = EarlyRuntimeService(
        observation_store=observations,
        candidate_store=candidates,
        outbox_store=outbox,
    )
    first = observation("sig-1", NOW)

    result = run(
        service.process(
            first,
            observations=(first,),
            safety_evidence=BASE_SAFETY,
            score_components=components("70"),
        )
    )

    assert result.candidate.state.value == "EARLY_WATCH"
    assert result.decision.state.value == "EARLY_WATCH"
    assert result.stage_snapshot.kind == "early.stage_snapshot"
    assert result.stage_snapshot.normalized_payload["state"] == "EARLY_WATCH"
    assert result.stage_snapshot.normalized_payload["chain"] == "solana"
    assert result.stage_snapshot.normalized_payload["mint"] == MINT
    assert result.stage_snapshot.normalized_payload["DataQualityConfidence"] is not None
    assert set(result.stage_snapshot.normalized_payload["data_quality_dimensions"]) == {
        "organic_flow_quality",
        "wallet_independence_quality",
        "stream_quality",
        "price_quality",
        "provider_agreement",
        "protocol_identity_quality",
        "holder_data_quality",
    }
    discovered = next(
        row
        for row in observations.rows.values()
        if row.normalized_payload.get("state") == "DISCOVERED"
    )
    assert discovered.normalized_payload["early_score"] is not None
    assert discovered.normalized_payload["safety_status"] == "PASS"
    assert discovered.normalized_payload["score_version"] is not None
    assert result.lifecycle_event is not None
    assert result.lifecycle_event.kind == "CandidateStateChanged"
    assert result.alert is not None
    assert result.alert.type.value == "EARLY_WATCH"
    assert len(observations.rows) == 5  # source plus DISCOVERED/ENRICHING/WATCH/EARLY_WATCH
    assert len(outbox.events) == 1


def test_stage_and_alert_replay_are_idempotent_and_snapshots_do_not_mutate() -> None:
    observations = MemoryObservationStore()
    candidates = MemoryCandidateStore()
    outbox = MemoryOutbox()
    service = EarlyRuntimeService(
        observation_store=observations,
        candidate_store=candidates,
        outbox_store=outbox,
    )
    first = observation("sig-1", NOW)
    kwargs = {
        "observations": (first,),
        "safety_evidence": BASE_SAFETY,
        "score_components": components("70"),
    }

    result = run(service.process(first, **kwargs))
    original_payload = dict(result.stage_snapshot.normalized_payload)
    replay = run(service.process(first, **kwargs))

    assert replay.stage_snapshot.id == result.stage_snapshot.id
    assert dict(replay.stage_snapshot.normalized_payload) == original_payload
    assert len(observations.rows) == 5
    assert len(outbox.events) == 1
    assert len(replay.candidate.transitions) == len(result.candidate.transitions)


def test_out_of_order_observation_does_not_move_event_time_checkpoint_backwards() -> None:
    service = EarlyRuntimeService()
    first = observation("sig-late", NOW + timedelta(seconds=30), wallet="wallet-late")
    earlier = observation("sig-early", NOW + timedelta(seconds=20), wallet="wallet-early")

    first_result = run(
        service.process(
            first,
            observations=(first,),
            safety_evidence=BASE_SAFETY,
            score_components=components("70"),
        )
    )
    replay_result = run(
        service.process(
            earlier,
            observations=(earlier,),
            safety_evidence=BASE_SAFETY,
            score_components=components("70"),
        )
    )

    assert replay_result.feature_snapshot.as_of == first_result.feature_snapshot.as_of
    assert (
        tuple(reason.code for reason in replay_result.feature_snapshot.reason_codes).count(
            "FUTURE_OBSERVATIONS_EXCLUDED"
        )
        == 0
    )


def test_critical_unknown_safety_never_becomes_entry_ready_but_persists_discovery() -> None:
    service = EarlyRuntimeService()
    first = observation("sig-unknown", NOW)

    result = run(
        service.process(
            first,
            observations=(first,),
            safety_evidence={},
            score_components=components("95"),
        )
    )

    assert result.safety.status.value == "UNKNOWN"
    assert result.decision.entry_ready is False
    assert result.candidate.state.value != "ENTRY_READY"
    assert result.stage_snapshot.normalized_payload["critical_unknowns"]
    assert result.stage_snapshot.normalized_payload["execution_eligible"] is False
    assert result.stage_snapshot.normalized_payload["DataQualityConfidence"] < Decimal("100")


def test_runtime_escalates_through_strong_high_and_paper_entry_only_with_quote() -> None:
    service = EarlyRuntimeService()
    first = observation("sig-1", NOW)
    second = observation("sig-2", NOW + timedelta(seconds=30), wallet="wallet-b")
    third = observation("sig-3", NOW + timedelta(seconds=60), wallet="wallet-c")
    fourth = observation("sig-4", NOW + timedelta(seconds=90), wallet="wallet-d")

    early = run(
        service.process(
            first,
            observations=(first,),
            safety_evidence=BASE_SAFETY,
            score_components=components("70"),
        )
    )
    strong = run(
        service.process(
            second,
            observations=(second,),
            safety_evidence=BASE_SAFETY,
            score_components=components("80"),
        )
    )
    high = run(
        service.process(
            third,
            observations=(third,),
            safety_evidence=BASE_SAFETY,
            score_components=components("90"),
        )
    )
    entry = run(
        service.process(
            fourth,
            observations=(fourth,),
            safety_evidence=BASE_SAFETY,
            score_components=components("90"),
            quote={
                "freshness": Freshness(
                    as_of=NOW + timedelta(seconds=90),
                    expires_at=NOW + timedelta(seconds=120),
                ),
                "output_amount": Decimal("1"),
            },
        )
    )

    assert early.stage.value == "EARLY_WATCH"
    assert strong.stage.value == "STRONG_SETUP"
    assert high.stage.value == "HIGH_CONFLUENCE"
    assert high.decision.entry_ready is False
    assert entry.stage.value == "ENTRY_READY"
    assert entry.decision.execution_eligible is False


def test_manipulated_launch_is_rejected_without_entry_alert() -> None:
    service = EarlyRuntimeService()
    first = observation("sig-bundle", NOW)

    result = run(
        service.process(
            first,
            observations=(first,),
            safety_evidence={**BASE_SAFETY, "bundle_concentration": Decimal("0.95")},
            score_components=components("95"),
        )
    )

    assert result.safety.status.value == "BLOCK"
    assert result.stage.value == "RISK_REJECTED"
    assert result.alert is not None
    assert result.alert.type.value == "RISK_ESCALATION"
    assert result.decision.entry_ready is False


def test_unknown_launch_remains_watch_for_bounded_later_reevaluation() -> None:
    service = EarlyRuntimeService()
    first = observation("sig-unknown", NOW)

    result = run(
        service.process(
            first,
            observations=(first,),
            score_components=components("80"),
        )
    )

    assert result.safety.status.value == "UNKNOWN"
    assert result.stage.value == "WATCH"
    assert result.candidate.state.value == "WATCH"
    assert result.alert is not None
    assert result.alert.type.value == "NEW_WATCH"
    assert result.alert.payload["message_state"] == "WATCH"
