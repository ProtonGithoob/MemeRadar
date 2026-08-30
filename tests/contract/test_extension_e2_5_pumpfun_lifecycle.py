"""Keyless replay contracts for rich Pump.fun lifecycle evidence."""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.launchpad_dex import (
    LAUNCHPAD_PARSER_VERSION,
    RICH_LAUNCHPAD_PARSER_VERSION,
    LaunchpadDexAdapter,
    ParsedProtocolEvent,
    ProtocolEventOrigin,
    ProtocolEventType,
    ProtocolVenue,
    PumpFunAdapter,
    PumpSwapAdapter,
)
from memeradar_providers.transport import ProviderSchemaError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "fixtures" / "providers" / "launchpad_dex" / "rich_pumpfun_replay.json"
NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
ADAPTERS: dict[str, LaunchpadDexAdapter] = {
    ProtocolVenue.PUMP_FUN.value: PumpFunAdapter(),
    ProtocolVenue.PUMP_SWAP.value: PumpSwapAdapter(),
}


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="rich-pumpfun-fixture-contract",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def fixture() -> Mapping[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    return payload


def records(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    value = payload.get("events")
    assert isinstance(value, Sequence)
    assert not isinstance(value, str | bytes | bytearray)
    result: list[Mapping[str, object]] = []
    for record in value:
        assert isinstance(record, Mapping)
        result.append(record)
    return tuple(result)


def parse_record(record: Mapping[str, object]) -> ParsedProtocolEvent:
    venue = record.get("venue")
    assert isinstance(venue, str)
    adapter = ADAPTERS[venue]
    message = {key: value for key, value in record.items() if key != "venue"}
    return adapter.parse(message, context())


def ordered(events: Sequence[ParsedProtocolEvent]) -> tuple[ParsedProtocolEvent, ...]:
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                event.observed_at,
                event.ingested_at,
                event.source_id,
            ),
        )
    )


def test_rich_fixture_replay_is_ordered_versioned_and_deterministic() -> None:
    payload = fixture()
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    original = [parse_record(record) for record in records(payload)]
    replayed = [parse_record(record) for record in reversed(records(payload))]
    original_ordered = ordered(original)
    replay_ordered = ordered(replayed)

    assert len(original_ordered) == 12
    assert original_ordered == replay_ordered
    assert [event.source_id for event in original_ordered].count(
        "pump.fun:pumpfun-rich-trade-1"
    ) == 2
    assert all(event.schema_version == 2 for event in original_ordered)
    assert all(event.parser_version == RICH_LAUNCHPAD_PARSER_VERSION for event in original_ordered)
    assert LAUNCHPAD_PARSER_VERSION != RICH_LAUNCHPAD_PARSER_VERSION
    assert all(event.observed_at == NOW for event in original_ordered)
    assert all(event.ingested_at == NOW for event in original_ordered)

    event_types = [event.protocol_event_type for event in original_ordered]
    assert ProtocolEventType.LAUNCH in event_types
    assert ProtocolEventType.TRADE in event_types
    assert ProtocolEventType.BONDING_CURVE_PROGRESS in event_types
    assert ProtocolEventType.GRADUATION in event_types
    assert ProtocolEventType.MIGRATION in event_types
    assert ProtocolEventType.POOL_CREATED in event_types
    assert ProtocolEventType.CREATOR_FEE_CLAIM in event_types
    assert ProtocolEventType.FEE_RECIPIENT_CHANGE in event_types
    curve_events = [
        event
        for event in original_ordered
        if event.protocol_event_type is ProtocolEventType.BONDING_CURVE_PROGRESS
    ]
    assert len(curve_events) == 1
    assert curve_events[0].bonding_curve_progress_bps == 4200
    whale_events = [event for event in original_ordered if event.is_derived]
    assert len(whale_events) == 1
    assert whale_events[0].protocol_event_type is ProtocolEventType.WHALE_TRADE
    assert whale_events[0].event_origin is ProtocolEventOrigin.DERIVED
    assert all(
        event.event_origin is ProtocolEventOrigin.NATIVE
        for event in original_ordered
        if event is not whale_events[0]
    )

    observations = tuple(event.to_observation() for event in original_ordered)
    replay_observations = tuple(event.to_observation() for event in replay_ordered)
    assert observations == replay_observations
    assert all(observation.kind == "protocol.lifecycle" for observation in observations)
    assert all(
        observation.provenance.parser_version == RICH_LAUNCHPAD_PARSER_VERSION
        for observation in observations
    )
    assert observations[0].normalized_payload["protocol_event_type"] == "launch"
    whale_observation = next(
        observation
        for observation in observations
        if observation.normalized_payload["protocol_event_type"] == "whale_trade"
    )
    assert whale_observation.normalized_payload["event_origin"] == "DERIVED"
    assert whale_observation.normalized_payload["schema_version"] == 2
    curve_observation = next(
        observation
        for observation in observations
        if observation.normalized_payload["protocol_event_type"] == "bonding_curve_progress"
    )
    assert curve_observation.normalized_payload["bonding_curve_progress_bps"] == 4200
    assert observations[0].token_id == observations[-1].token_id
    assert "api_key" not in raw.lower()
    assert "authorization" not in raw.lower()
    assert "private_key" not in raw.lower()
    assert "https://" not in raw.lower()


def test_rich_fixture_rejects_the_malformed_envelope() -> None:
    payload = fixture()
    malformed = payload.get("malformed")
    assert isinstance(malformed, Mapping)
    with pytest.raises(ProviderSchemaError, match="mint"):
        parse_record(malformed)


def test_rich_lifecycle_seam_has_no_execution_authority_or_network_client() -> None:
    parser_source = (
        ROOT / "packages" / "providers" / "src" / "memeradar_providers" / "launchpad_dex.py"
    ).read_text(encoding="utf-8")
    stream_source = (
        ROOT / "packages" / "providers" / "src" / "memeradar_providers" / "protocol_stream.py"
    ).read_text(encoding="utf-8")
    assert "sign(" not in parser_source
    assert "submit(" not in parser_source
    assert "httpx" not in stream_source
    assert "ProviderTransport" not in stream_source
    assert "ExecutionPort" not in parser_source
    assert "ExecutionPort" not in stream_source

    compose = yaml.safe_load((ROOT / "infra" / "compose" / "docker-compose.yml").read_text())
    for service_name in ("api", "worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ANALYSIS_ONLY"] == "true"
        assert environment["PAPER_TRADING"] == "true"
        assert environment["MANUAL_EXECUTION"] == "false"
        assert environment["AUTO_EXECUTION"] == "false"
