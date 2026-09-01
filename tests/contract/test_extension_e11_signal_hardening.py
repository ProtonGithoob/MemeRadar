"""Keyless contract coverage for the provider-independent E11 hardening fixture."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.replay_harness import (
    ReplayCheckpoint,
    ReplayDataset,
    ReplayEventRecord,
    ReplayHarness,
    ResearchReplayManifest,
)
from memeradar_application.signal_hardening import (
    LockAssetScope,
    MomentumRegimeKind,
    SignalHardeningAnalyzer,
    SignalHardeningPolicy,
)
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "signal_hardening" / "replay.json"


def fixture() -> Mapping[str, object]:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, Mapping)
    return value


def token(payload: Mapping[str, object]) -> TokenIdentity:
    raw_token = payload["token"]
    assert isinstance(raw_token, Mapping)
    return TokenIdentity(
        id=UUID(str(raw_token["id"])),
        mint_address=str(raw_token["mint_address"]),
        token_program=str(raw_token["token_program"]),
    )


def observations(payload: Mapping[str, object], value: TokenIdentity) -> tuple[Observation, ...]:
    rows = payload["observations"]
    assert isinstance(rows, Sequence) and not isinstance(rows, str | bytes | bytearray)
    result: list[Observation] = []
    for row in rows:
        assert isinstance(row, Mapping)
        at = datetime.fromisoformat(str(row["at"])).astimezone(UTC)
        raw_payload = row["payload"]
        assert isinstance(raw_payload, Mapping)
        source_id = str(row["source_id"])
        result.append(
            Observation(
                id=uuid5(NAMESPACE_URL, f"signal-hardening-fixture:{source_id}"),
                token_id=value.id,
                kind=str(row["kind"]),
                provenance=Provenance(
                    provider="signal-hardening-fixture",
                    source_id=source_id,
                    observed_at=at,
                    parser_version="signal-hardening-fixture-v1",
                ),
                occurred_at=at,
                observed_at=at,
                ingested_at=at,
                quality_state=QualityState(str(row.get("quality_state", "FRESH"))),
                normalized_payload={"mint_address": value.mint_address, **raw_payload},
            )
        )
    return tuple(result)


def test_fixture_exercises_all_hardening_snapshots_deterministically() -> None:
    payload = fixture()
    assert payload["redacted"] is True
    assert payload["provider_independent"] is True
    assert payload["hypothesis_only"] is True
    value = token(payload)
    records = observations(payload, value)
    now = datetime.fromisoformat(str(payload["as_of"])).astimezone(UTC)
    config_hash = str(payload["config_hash"])
    analyzer = SignalHardeningAnalyzer(policy=SignalHardeningPolicy())

    momentum = analyzer.analyze_momentum(value, records, now=now, config_hash=config_hash)
    funding = analyzer.analyze_move_funding(value, records, now=now, config_hash=config_hash)
    deployer = analyzer.analyze_deployer_activity(value, records, now=now, config_hash=config_hash)
    launch = analyzer.analyze_launch_footprint(value, records, now=now, config_hash=config_hash)
    lock = analyzer.analyze_token_lock(value, records, now=now, config_hash=config_hash)

    expected = payload["expected"]
    assert isinstance(expected, Mapping)
    assert momentum.kind is MomentumRegimeKind(str(expected["momentum_kind"]))
    assert momentum.sustained_for_ms == int(expected["momentum_sustained_for_ms"])
    assert funding.funding_confirmed is bool(expected["move_funding_confirmed"])
    assert funding.buy_volume_usd == Decimal(str(expected["move_buy_volume_usd"]))
    assert deployer.transfer_delta == Decimal(str(expected["deployer_transfer_delta"]))
    assert launch.early_buyer_count == int(expected["launch_early_buyer_count"])
    assert launch.bundle_actor_cluster_count == int(expected["launch_bundle_actor_cluster_count"])
    assert lock.asset_scope is LockAssetScope(str(expected["lock_asset_scope"]))
    assert lock.next_unlock_at == datetime.fromisoformat(str(expected["lock_next_unlock_at"]))
    assert dict(lock.scheduled_unlocks)["1h"] == Decimal(str(expected["lock_scheduled_1h"]))
    assert all(
        snapshot.execution_eligible() is False
        for snapshot in (momentum, funding, deployer, launch, lock)
    )
    assert all(
        snapshot.quality_state is QualityState.FRESH
        for snapshot in (momentum, funding, deployer, launch, lock)
    )

    reversed_records = tuple(reversed(records))
    assert momentum == analyzer.analyze_momentum(
        value,
        reversed_records,
        now=now,
        config_hash=config_hash,
    )
    assert funding == analyzer.analyze_move_funding(
        value,
        reversed_records,
        now=now,
        config_hash=config_hash,
    )
    assert launch == analyzer.analyze_launch_footprint(
        value,
        reversed_records,
        now=now,
        config_hash=config_hash,
    )


def test_fixture_hardening_rejects_future_evidence_instead_of_looking_ahead() -> None:
    payload = fixture()
    value = token(payload)
    records = observations(payload, value)
    now = datetime.fromisoformat(str(payload["as_of"])).astimezone(UTC)
    future_at = now.replace(second=11)
    future = Observation(
        id=uuid5(NAMESPACE_URL, "signal-hardening-fixture:future"),
        token_id=value.id,
        kind="market.market_data",
        provenance=Provenance(
            provider="signal-hardening-fixture",
            source_id="future",
            observed_at=future_at,
            parser_version="signal-hardening-fixture-v1",
        ),
        occurred_at=future_at,
        observed_at=future_at,
        ingested_at=future_at,
        quality_state=QualityState.FRESH,
        normalized_payload={
            "mint_address": value.mint_address,
            "market_cap_usd": "999",
            "liquidity_usd": "1",
        },
    )
    result = SignalHardeningAnalyzer().analyze_momentum(
        value,
        (*records, future),
        now=now,
        config_hash=str(payload["config_hash"]),
    )

    assert result.quality_state is QualityState.INVALID
    assert "HARDENING_FUTURE_EVIDENCE" in {reason.code for reason in result.reason_codes}


def test_replay_uses_the_same_hardening_analyzer_and_persists_its_identity() -> None:
    payload = fixture()
    value = token(payload)
    records = observations(payload, value)
    now = datetime.fromisoformat(str(payload["as_of"])).astimezone(UTC)
    replay_events = tuple(
        ReplayEventRecord(
            observation=record,
            registry_version="registry-v1",
            venue="fixture",
        )
        for record in records
    )
    checkpoint_id = UUID("00000000-0000-0000-0000-000000001101")
    candidate_id = UUID("00000000-0000-0000-0000-000000001102")
    dataset = ReplayDataset(
        dataset_id="signal-hardening-replay",
        dataset_version="fixture-v1",
        tokens=(value,),
        events=replay_events,
        checkpoints=(
            ReplayCheckpoint(
                id=checkpoint_id,
                token_id=value.id,
                candidate_id=candidate_id,
                as_of=now,
                venue="fixture",
            ),
        ),
    )
    manifest = ResearchReplayManifest(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        as_of=now,
        parser_version="signal-hardening-fixture-v1",
        registry_version="registry-v1",
        event_schema_version=1,
        strategy_name="none",
        strategy_version="none-v1",
        config_hash=str(payload["config_hash"]),
        outcome_policy_version="outcome-labels-v1",
    )

    first = ReplayHarness().replay(dataset, manifest=manifest)
    reversed_dataset = ReplayDataset(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        tokens=(value,),
        events=tuple(reversed(replay_events)),
        checkpoints=dataset.checkpoints,
    )
    second = ReplayHarness().replay(reversed_dataset, manifest=manifest)

    assert first == second
    assert first.manifest.to_json_dict()["signal_hardening_version"] == "signal-hardening-v1"
    correlation_feature = first.checkpoints[0].correlation.window("1m")
    assert correlation_feature.signal_hardening["deployer"].transfer_delta == Decimal("-100")
    feature = next(
        value
        for value in first.checkpoints[0].feature_snapshots
        if value.values["window"] == "1m"
    )
    hardening = feature.values["signal_hardening"]
    assert isinstance(hardening, Mapping)
    assert hardening["momentum"]["kind"] == "SURGE"
    assert hardening["move_funding"]["version"] == "signal-hardening-v1"
    organic_validation = feature.values["organic_flow_validation"]
    assert isinstance(organic_validation, Mapping)
    assert organic_validation["funding_confirmed"] is True
    families = feature.values["families"]
    assert isinstance(families, Mapping)
    market_family = families["market"]
    assert isinstance(market_family, Mapping)
    assert market_family["organic_flow_validation"] == organic_validation
    on_chain_family = families["on_chain_safety"]
    assert isinstance(on_chain_family, Mapping)
    assert on_chain_family["signal_hardening"]["token_lock"]["asset_scope"] == "TOKEN"
