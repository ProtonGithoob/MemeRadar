"""Provider-free high-fidelity event replay and outcome labeling.

This module is deliberately an orchestration seam around the existing
normalized observation, correlation, feature and strategy contracts.  It does
not decode provider payloads and it never turns research output into an
execution request.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from uuid import UUID

from memeradar_domain import (
    FeatureSnapshot,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)
from memeradar_domain.common import ensure_utc, normalize_texts, require_text, to_decimal
from memeradar_domain.events import normalize_reason_codes

from .alpha_strategy import AlphaStrategy, StrategySnapshot
from .correlation import (
    CorrelationSnapshot,
    CorrelationWindowBuilder,
    SignalHardeningEvidence,
)
from .event_time import exact_event_time
from .feature_windows import FeatureWindowAggregator
from .price_semantics import market_reference_price
from .signal_hardening import SIGNAL_HARDENING_VERSION, SignalHardeningAnalyzer

if TYPE_CHECKING:
    from .early_replay import EarlyOutcomeLabel, EarlyOutcomePolicy

REPLAY_HARNESS_VERSION = "research-replay-v1"
REPLAY_DATASET_SCHEMA_VERSION = 1
DEFAULT_OUTCOME_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1m", timedelta(minutes=1)),
    ("5m", timedelta(minutes=5)),
    ("15m", timedelta(minutes=15)),
    ("1h", timedelta(hours=1)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
)
DEFAULT_TARGET_MULTIPLES: tuple[Decimal, ...] = (
    Decimal("1.5"),
    Decimal("2"),
    Decimal("3"),
)
_FEATURE_WINDOWS = frozenset({"1m", "5m", "15m"})
_PRICE_KINDS = frozenset(
    {
        "market.snapshot",
        "market.market_data",
        "market.observation",
        "market.quote",
        "market.price",
        "market.trade",
        "market.trades",
        "market.trade_data",
    }
)
_RUG_KINDS = frozenset({"risk.rug_event", "risk.token_outcome", "security.rug"})
_PAPER_EXIT_KINDS = frozenset({"paper.exit", "paper_exit", "exit.paper"})
_SECRET_KEY_PARTS = frozenset(
    {
        "apikey",
        "accesskey",
        "secret",
        "privatekey",
        "seedphrase",
        "password",
        "cookie",
        "authorization",
        "bottoken",
        "sessiontoken",
    }
)
_MISSING = object()


def _canonical_json(value: object) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _json_safe(value: object) -> object:
    """Convert normalized domain values to stable JSON without raw secrets."""

    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("replay JSON cannot contain a non-finite float")
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | UUID):
        return str(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, ReasonCode):
        return {
            "code": value.code,
            "detail": value.detail,
            "evidence_refs": list(value.evidence_refs),
        }
    if isinstance(value, Provenance):
        return _provenance_to_json(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    raise TypeError(f"unsupported replay JSON value: {type(value).__name__}")


def _parse_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be an ISO timestamp")
    try:
        return ensure_utc(datetime.fromisoformat(value), field_name)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} is not a valid timestamp") from exc


def _parse_uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a UUID string")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid UUID") from exc


def _normalized_refs(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError(f"{field_name} must be a sequence")
    return normalize_texts(values, field_name)


def _is_secret_field(value: object) -> bool:
    normalized = "".join(character for character in str(value).lower() if character.isalnum())
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _assert_safe_mapping(value: object, field_name: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_secret_field(key):
                raise ValueError(f"{field_name} contains a secret-shaped field")
            _assert_safe_mapping(item, field_name)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _assert_safe_mapping(item, field_name)


def _provenance_to_json(value: Provenance) -> dict[str, object]:
    return {
        "provider": value.provider,
        "source_id": value.source_id,
        "observed_at": value.observed_at.isoformat(),
        "parser_version": value.parser_version,
        "raw_payload_hash": value.raw_payload_hash,
        "raw_payload_ref": value.raw_payload_ref,
    }


def _provenance_from_json(value: object) -> Provenance:
    if not isinstance(value, Mapping):
        raise TypeError("provenance must be an object")
    return Provenance(
        provider=cast(str, value.get("provider")),
        source_id=cast(str, value.get("source_id")),
        observed_at=_parse_datetime(value.get("observed_at"), "provenance.observed_at"),
        parser_version=cast(str, value.get("parser_version")),
        raw_payload_hash=cast(str | None, value.get("raw_payload_hash")),
        raw_payload_ref=cast(str | None, value.get("raw_payload_ref")),
    )


def _reason_codes_from_json(value: object) -> tuple[ReasonCode, ...]:
    if not isinstance(value, list):
        raise TypeError("reason_codes must be a list")
    normalized: list[ReasonCode] = []
    for item in value:
        if isinstance(item, str):
            normalized.append(ReasonCode(item))
            continue
        if not isinstance(item, Mapping):
            raise TypeError("reason code entries must be strings or objects")
        refs = item.get("evidence_refs", [])
        if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
            raise TypeError("reason code evidence_refs must be a string list")
        normalized.append(
            ReasonCode(
                code=cast(str, item.get("code")),
                detail=cast(str | None, item.get("detail")),
                evidence_refs=tuple(refs),
            )
        )
    return normalize_reason_codes(normalized)


def _risk_to_json(value: RiskAssessment) -> dict[str, object]:
    return {
        "id": str(value.id),
        "candidate_id": str(value.candidate_id),
        "as_of": value.as_of.isoformat(),
        "expires_at": value.expires_at.isoformat(),
        "risk_version": value.risk_version,
        "disposition": value.disposition.value,
        "hard_blocks": list(value.hard_blocks),
        "warnings": list(value.warnings),
        "penalties": _json_safe(value.penalties),
        "evidence_refs": list(value.evidence_refs),
        "reason_codes": _json_safe(value.reason_codes),
        "confidence": str(value.confidence),
        "config_hash": value.config_hash,
        "critical_evidence_state": value.critical_evidence_state.value,
    }


def _risk_from_json(value: object) -> RiskAssessment:
    if not isinstance(value, Mapping):
        raise TypeError("risk_assessment must be an object")
    hard_blocks = value.get("hard_blocks", [])
    warnings = value.get("warnings", [])
    evidence_refs = value.get("evidence_refs", [])
    if not all(isinstance(values, list) for values in (hard_blocks, warnings, evidence_refs)):
        raise TypeError("risk assessment text fields must be lists")
    penalties = value.get("penalties", {})
    if not isinstance(penalties, Mapping):
        raise TypeError("risk assessment penalties must be an object")
    return RiskAssessment(
        id=_parse_uuid(value.get("id"), "risk_assessment.id"),
        candidate_id=_parse_uuid(value.get("candidate_id"), "risk_assessment.candidate_id"),
        as_of=_parse_datetime(value.get("as_of"), "risk_assessment.as_of"),
        expires_at=_parse_datetime(value.get("expires_at"), "risk_assessment.expires_at"),
        risk_version=cast(str, value.get("risk_version")),
        disposition=RiskDisposition(cast(str, value.get("disposition"))),
        hard_blocks=tuple(cast(str, item) for item in hard_blocks),
        warnings=tuple(cast(str, item) for item in warnings),
        penalties=cast(Mapping[str, object], penalties),
        evidence_refs=tuple(cast(str, item) for item in evidence_refs),
        reason_codes=_reason_codes_from_json(value.get("reason_codes", [])),
        confidence=to_decimal(value.get("confidence"), "risk_assessment.confidence"),
        config_hash=cast(str, value.get("config_hash")),
        critical_evidence_state=QualityState(
            cast(str, value.get("critical_evidence_state", QualityState.UNKNOWN.value))
        ),
    )


@dataclass(frozen=True, slots=True)
class ReplayEventRecord:
    """One compact normalized observation retained for historical research."""

    observation: Observation
    registry_version: str
    venue: str = "unknown"
    event_schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.observation, Observation):
            raise TypeError("observation must be an Observation")
        replay_payload = dict(self.observation.normalized_payload)
        replay_payload["collection_mode"] = "REPLAY"
        object.__setattr__(
            self,
            "observation",
            replace(self.observation, normalized_payload=replay_payload),
        )
        if not isinstance(self.observation.id, UUID):
            raise TypeError("observation.id must be a UUID")
        if self.observation.token_id is None:
            raise ValueError("replay observations require token_id")
        if exact_event_time(self.observation) is None:
            raise ValueError("replay observations require exact occurred_at")
        object.__setattr__(
            self,
            "registry_version",
            require_text(self.registry_version, "registry_version", max_length=128),
        )
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=128).lower())
        if (
            not isinstance(self.event_schema_version, int)
            or isinstance(self.event_schema_version, bool)
            or self.event_schema_version < 1
        ):
            raise ValueError("event_schema_version must be positive")
        _assert_safe_mapping(self.observation.normalized_payload, "normalized_payload")

    @property
    def event_id(self) -> UUID:
        return self.observation.id

    @property
    def token_id(self) -> UUID:
        assert self.observation.token_id is not None
        return self.observation.token_id

    @property
    def parser_version(self) -> str:
        return self.observation.provenance.parser_version

    @property
    def event_at(self) -> datetime:
        event_at = exact_event_time(self.observation)
        assert event_at is not None
        return event_at

    @property
    def source_key(self) -> tuple[str, str, str]:
        return (
            self.observation.provenance.provider,
            self.observation.kind,
            self.observation.provenance.source_id,
        )

    @property
    def partition_key(self) -> str:
        return f"{self.event_at.date().isoformat()}/{self.venue}/{self.token_id}"

    def to_json_dict(self) -> dict[str, object]:
        result = {
            "id": str(self.event_id),
            "token_id": str(self.token_id),
            "candidate_id": (
                str(self.observation.candidate_id)
                if self.observation.candidate_id is not None
                else None
            ),
            "kind": self.observation.kind,
            "occurred_at": (
                self.observation.occurred_at.isoformat()
                if self.observation.occurred_at is not None
                else None
            ),
            "observed_at": self.observation.observed_at.isoformat(),
            "ingested_at": self.observation.ingested_at.isoformat(),
            "quality_state": self.observation.quality_state.value,
            "normalized_payload": _json_safe(self.observation.normalized_payload),
            "provenance": _provenance_to_json(self.observation.provenance),
            "registry_version": self.registry_version,
            "venue": self.venue,
            "event_schema_version": self.event_schema_version,
            "partition": self.partition_key,
        }
        return result

    @classmethod
    def from_json_dict(cls, value: Mapping[str, object]) -> ReplayEventRecord:
        payload = value.get("normalized_payload")
        if not isinstance(payload, Mapping):
            raise TypeError("event.normalized_payload must be an object")
        occurred_value = value.get("occurred_at")
        occurred_at = (
            None if occurred_value is None else _parse_datetime(occurred_value, "event.occurred_at")
        )
        replay_payload = dict(payload)
        replay_payload["collection_mode"] = "REPLAY"
        observation = Observation(
            id=_parse_uuid(value.get("id"), "event.id"),
            candidate_id=(
                None
                if value.get("candidate_id") is None
                else _parse_uuid(value.get("candidate_id"), "event.candidate_id")
            ),
            token_id=_parse_uuid(value.get("token_id"), "event.token_id"),
            kind=cast(str, value.get("kind")),
            provenance=_provenance_from_json(value.get("provenance")),
            occurred_at=occurred_at,
            observed_at=_parse_datetime(value.get("observed_at"), "event.observed_at"),
            ingested_at=_parse_datetime(value.get("ingested_at"), "event.ingested_at"),
            quality_state=QualityState(cast(str, value.get("quality_state"))),
            normalized_payload=replay_payload,
        )
        result = cls(
            observation=observation,
            registry_version=cast(str, value.get("registry_version")),
            venue=cast(str, value.get("venue", "unknown")),
            event_schema_version=cast(int, value.get("event_schema_version", 1)),
        )
        declared_partition = value.get("partition")
        if declared_partition is not None and declared_partition != result.partition_key:
            raise ValueError("event partition does not match event timestamps or identity")
        return result


@dataclass(frozen=True, slots=True)
class ReplayCheckpoint:
    """An event-time signal boundary at which features and outcomes are measured."""

    id: UUID
    token_id: UUID
    candidate_id: UUID
    as_of: datetime
    venue: str = "unknown"
    risk_assessment: RiskAssessment | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "token_id", "candidate_id"):
            if not isinstance(getattr(self, field_name), UUID):
                raise TypeError(f"{field_name} must be a UUID")
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=128).lower())
        if self.risk_assessment is not None:
            if not isinstance(self.risk_assessment, RiskAssessment):
                raise TypeError("risk_assessment must be a RiskAssessment")
            if self.risk_assessment.candidate_id != self.candidate_id:
                raise ValueError("risk_assessment candidate_id does not match checkpoint")

    def to_json_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "token_id": str(self.token_id),
            "candidate_id": str(self.candidate_id),
            "as_of": self.as_of.isoformat(),
            "venue": self.venue,
            "risk_assessment": (
                None if self.risk_assessment is None else _risk_to_json(self.risk_assessment)
            ),
        }

    @classmethod
    def from_json_dict(cls, value: Mapping[str, object]) -> ReplayCheckpoint:
        risk_value = value.get("risk_assessment")
        return cls(
            id=_parse_uuid(value.get("id"), "checkpoint.id"),
            token_id=_parse_uuid(value.get("token_id"), "checkpoint.token_id"),
            candidate_id=_parse_uuid(value.get("candidate_id"), "checkpoint.candidate_id"),
            as_of=_parse_datetime(value.get("as_of"), "checkpoint.as_of"),
            venue=cast(str, value.get("venue", "unknown")),
            risk_assessment=None if risk_value is None else _risk_from_json(risk_value),
        )


@dataclass(frozen=True, slots=True)
class ReplayDataset:
    """Normalized evidence plus explicit signal checkpoints for reproducible replay."""

    dataset_id: str
    dataset_version: str
    tokens: tuple[TokenIdentity, ...]
    events: tuple[ReplayEventRecord, ...]
    checkpoints: tuple[ReplayCheckpoint, ...]
    schema_version: int = REPLAY_DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", require_text(self.dataset_id, "dataset_id"))
        object.__setattr__(
            self,
            "dataset_version",
            require_text(self.dataset_version, "dataset_version", max_length=128),
        )
        if self.schema_version != REPLAY_DATASET_SCHEMA_VERSION:
            raise ValueError("unsupported replay dataset schema version")
        tokens = tuple(self.tokens)
        if not tokens:
            raise ValueError("replay dataset must contain a token")
        if any(not isinstance(value, TokenIdentity) for value in tokens):
            raise TypeError("tokens must contain TokenIdentity values")
        if len({value.id for value in tokens}) != len(tokens):
            raise ValueError("replay dataset contains duplicate token IDs")
        if len({value.mint_address for value in tokens}) != len(tokens):
            raise ValueError("replay dataset contains duplicate token mints")
        token_ids = {value.id for value in tokens}

        raw_events = tuple(self.events)
        if any(not isinstance(value, ReplayEventRecord) for value in raw_events):
            raise TypeError("events must contain ReplayEventRecord values")
        sorted_events = sorted(
            raw_events,
            key=lambda value: (
                value.event_at,
                value.observation.observed_at,
                value.observation.ingested_at,
                value.observation.kind,
                value.observation.provenance.provider,
                value.observation.provenance.source_id,
                str(value.event_id),
            ),
        )
        deduplicated: list[ReplayEventRecord] = []
        by_source: dict[tuple[str, str, str], ReplayEventRecord] = {}
        for record in sorted_events:
            if record.token_id not in token_ids:
                raise ValueError("replay event references an unknown token")
            token = next(value for value in tokens if value.id == record.token_id)
            mint_value = record.observation.normalized_payload.get("mint_address")
            if mint_value is not None and mint_value != token.mint_address:
                raise ValueError("replay event mint does not match token identity")
            existing = by_source.get(record.source_key)
            if existing is not None:
                if _canonical_json(existing.to_json_dict() | {"id": None}) != _canonical_json(
                    record.to_json_dict() | {"id": None}
                ):
                    raise ValueError("conflicting replay event source")
                continue
            by_source[record.source_key] = record
            deduplicated.append(record)
        object.__setattr__(self, "tokens", tuple(sorted(tokens, key=lambda value: str(value.id))))
        object.__setattr__(self, "events", tuple(deduplicated))

        checkpoints = tuple(self.checkpoints)
        if any(not isinstance(value, ReplayCheckpoint) for value in checkpoints):
            raise TypeError("checkpoints must contain ReplayCheckpoint values")
        if len({value.id for value in checkpoints}) != len(checkpoints):
            raise ValueError("replay dataset contains duplicate checkpoint IDs")
        if any(value.token_id not in token_ids for value in checkpoints):
            raise ValueError("checkpoint references an unknown token")
        object.__setattr__(
            self,
            "checkpoints",
            tuple(sorted(checkpoints, key=lambda value: (value.as_of, str(value.id)))),
        )

    @property
    def digest(self) -> str:
        return f"sha256:{hashlib.sha256(_canonical_json(self.to_json_dict()).encode()).hexdigest()}"

    @property
    def partition_counts(self) -> Mapping[str, int]:
        return MappingProxyType(
            {key: len(event_ids) for key, event_ids in self.partitioned_event_ids.items()}
        )

    @property
    def partitioned_event_ids(self) -> Mapping[str, tuple[UUID, ...]]:
        partitions: dict[str, list[UUID]] = {}
        for record in self.events:
            partitions.setdefault(record.partition_key, []).append(record.event_id)
        return MappingProxyType(
            {
                key: tuple(sorted(event_ids, key=str))
                for key, event_ids in sorted(partitions.items())
            }
        )

    def token(self, token_id: UUID) -> TokenIdentity:
        for value in self.tokens:
            if value.id == token_id:
                return value
        raise KeyError(token_id)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "tokens": [
                {
                    "id": str(value.id),
                    "chain": (value.chain.value if isinstance(value.chain, Enum) else value.chain),
                    "mint_address": value.mint_address,
                    "token_program": value.token_program,
                }
                for value in self.tokens
            ],
            "events": [value.to_json_dict() for value in self.events],
            "checkpoints": [value.to_json_dict() for value in self.checkpoints],
            "partitions": {
                key: [str(event_id) for event_id in event_ids]
                for key, event_ids in self.partitioned_event_ids.items()
            },
        }

    @classmethod
    def from_json_dict(cls, value: Mapping[str, object]) -> ReplayDataset:
        raw_tokens = value.get("tokens")
        raw_events = value.get("events")
        raw_checkpoints = value.get("checkpoints")
        if not isinstance(raw_tokens, list):
            raise TypeError("dataset tokens must be a list")
        if not isinstance(raw_events, list):
            raise TypeError("dataset events must be a list")
        if not isinstance(raw_checkpoints, list):
            raise TypeError("dataset checkpoints must be a list")
        tokens: list[TokenIdentity] = []
        for raw in raw_tokens:
            if not isinstance(raw, Mapping):
                raise TypeError("dataset token entries must be objects")
            tokens.append(
                TokenIdentity(
                    id=_parse_uuid(raw.get("id"), "token.id"),
                    chain=cast(str, raw.get("chain", "solana")),
                    mint_address=cast(str, raw.get("mint_address")),
                    token_program=cast(str, raw.get("token_program", "spl-token")),
                )
            )
        if any(not isinstance(raw, Mapping) for raw in raw_events):
            raise TypeError("dataset event entries must be objects")
        if any(not isinstance(raw, Mapping) for raw in raw_checkpoints):
            raise TypeError("dataset checkpoint entries must be objects")
        result = cls(
            dataset_id=cast(str, value.get("dataset_id")),
            dataset_version=cast(str, value.get("dataset_version")),
            schema_version=cast(int, value.get("schema_version", 1)),
            tokens=tuple(tokens),
            events=tuple(
                ReplayEventRecord.from_json_dict(cast(Mapping[str, object], raw))
                for raw in raw_events
            ),
            checkpoints=tuple(
                ReplayCheckpoint.from_json_dict(cast(Mapping[str, object], raw))
                for raw in raw_checkpoints
            ),
        )
        raw_partitions = value.get("partitions")
        if raw_partitions is not None:
            if not isinstance(raw_partitions, Mapping):
                raise TypeError("dataset partitions must be an object")
            partitions: dict[str, tuple[str, ...]] = {}
            for raw_key, raw_ids in raw_partitions.items():
                if not isinstance(raw_key, str) or not isinstance(raw_ids, list):
                    raise TypeError("dataset partition entries must be string lists")
                if not all(isinstance(raw_id, str) for raw_id in raw_ids):
                    raise TypeError("dataset partition event IDs must be strings")
                partitions[raw_key] = tuple(raw_ids)
            expected = {
                key: tuple(str(event_id) for event_id in event_ids)
                for key, event_ids in result.partitioned_event_ids.items()
            }
            if partitions != expected:
                raise ValueError("dataset partitions do not match normalized events")
        return result


@dataclass(frozen=True, slots=True)
class ResearchReplayManifest:
    """Pinned identities and event-time boundary for one research run."""

    dataset_id: str
    dataset_version: str
    as_of: datetime
    parser_version: str
    registry_version: str
    event_schema_version: int
    strategy_name: str
    strategy_version: str
    config_hash: str
    outcome_policy_version: str
    feature_window: str = "1m"
    dataset_digest: str | None = None
    schema_version: int = 1
    signal_hardening_version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        for field_name, max_length in (
            ("dataset_id", 128),
            ("dataset_version", 128),
            ("parser_version", 128),
            ("registry_version", 128),
            ("strategy_name", 128),
            ("strategy_version", 128),
            ("config_hash", 128),
            ("outcome_policy_version", 128),
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=max_length),
            )
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(
            self, "feature_window", require_text(self.feature_window, "feature_window")
        )
        if self.feature_window not in _FEATURE_WINDOWS:
            raise ValueError("feature_window must be one of 1m, 5m or 15m")
        if (
            not isinstance(self.event_schema_version, int)
            or isinstance(self.event_schema_version, bool)
            or self.event_schema_version < 1
        ):
            raise ValueError("event_schema_version must be positive")
        if self.schema_version != 1:
            raise ValueError("unsupported replay manifest schema version")
        if self.dataset_digest is not None:
            object.__setattr__(
                self, "dataset_digest", require_text(self.dataset_digest, "dataset_digest")
            )
        object.__setattr__(
            self,
            "signal_hardening_version",
            require_text(self.signal_hardening_version, "signal_hardening_version", max_length=64),
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "as_of": self.as_of.isoformat(),
            "parser_version": self.parser_version,
            "registry_version": self.registry_version,
            "event_schema_version": self.event_schema_version,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "config_hash": self.config_hash,
            "outcome_policy_version": self.outcome_policy_version,
            "feature_window": self.feature_window,
            "dataset_digest": self.dataset_digest,
            "signal_hardening_version": self.signal_hardening_version,
        }

    @classmethod
    def from_json_dict(cls, value: Mapping[str, object]) -> ResearchReplayManifest:
        return cls(
            schema_version=cast(int, value.get("schema_version", 1)),
            dataset_id=cast(str, value.get("dataset_id")),
            dataset_version=cast(str, value.get("dataset_version")),
            as_of=_parse_datetime(value.get("as_of"), "manifest.as_of"),
            parser_version=cast(str, value.get("parser_version")),
            registry_version=cast(str, value.get("registry_version")),
            event_schema_version=cast(int, value.get("event_schema_version")),
            strategy_name=cast(str, value.get("strategy_name")),
            strategy_version=cast(str, value.get("strategy_version")),
            config_hash=cast(str, value.get("config_hash")),
            outcome_policy_version=cast(str, value.get("outcome_policy_version")),
            feature_window=cast(str, value.get("feature_window", "1m")),
            dataset_digest=cast(str | None, value.get("dataset_digest")),
            signal_hardening_version=cast(
                str,
                value.get("signal_hardening_version", SIGNAL_HARDENING_VERSION),
            ),
        )


@dataclass(frozen=True, slots=True)
class OutcomeLabelPolicy:
    """Bounded, versioned future-outcome labeling policy."""

    horizons: tuple[tuple[str, timedelta], ...] = DEFAULT_OUTCOME_HORIZONS
    target_multiples: tuple[Decimal, ...] = DEFAULT_TARGET_MULTIPLES
    drawdown_fraction: Decimal = Decimal("0.5")
    liquidity_collapse_threshold: Decimal = Decimal("10000")
    liquidity_collapse_ratio: Decimal = Decimal("-0.5")
    version: str = "outcome-labels-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.horizons, Sequence) or isinstance(
            self.horizons, str | bytes | bytearray
        ):
            raise TypeError("horizons must be a sequence")
        normalized_horizons: list[tuple[str, timedelta]] = []
        previous = timedelta(0)
        for raw_name, raw_duration in self.horizons:
            name = require_text(raw_name, "horizon name", max_length=16)
            if any(name == existing for existing, _ in normalized_horizons):
                raise ValueError("horizon names must be unique")
            if not isinstance(raw_duration, timedelta) or raw_duration <= previous:
                raise ValueError("horizon durations must be strictly increasing")
            normalized_horizons.append((name, raw_duration))
            previous = raw_duration
        if not normalized_horizons:
            raise ValueError("at least one outcome horizon is required")
        object.__setattr__(self, "horizons", tuple(normalized_horizons))
        multiples = tuple(to_decimal(value, "target_multiple") for value in self.target_multiples)
        if not multiples or any(value <= Decimal("1") for value in multiples):
            raise ValueError("target_multiples must be greater than one")
        if len(set(multiples)) != len(multiples):
            raise ValueError("target_multiples must be unique")
        object.__setattr__(self, "target_multiples", tuple(sorted(multiples)))
        drawdown = to_decimal(self.drawdown_fraction, "drawdown_fraction")
        if not Decimal("0") < drawdown < Decimal("1"):
            raise ValueError("drawdown_fraction must be between zero and one")
        object.__setattr__(self, "drawdown_fraction", drawdown)
        collapse = to_decimal(
            self.liquidity_collapse_threshold,
            "liquidity_collapse_threshold",
        )
        if collapse <= 0:
            raise ValueError("liquidity_collapse_threshold must be positive")
        object.__setattr__(self, "liquidity_collapse_threshold", collapse)
        ratio = to_decimal(self.liquidity_collapse_ratio, "liquidity_collapse_ratio")
        if not Decimal("-1") <= ratio < 0:
            raise ValueError("liquidity_collapse_ratio must be between -1 and zero")
        object.__setattr__(self, "liquidity_collapse_ratio", ratio)
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class OutcomeHorizonLabel:
    """One bounded horizon of future market and safety outcomes."""

    horizon: str
    forward_return: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    time_to_multiple: Mapping[str, Decimal | None]
    time_to_drawdown: Decimal | None
    liquidity_collapsed: bool | None
    rugged: bool | None
    creator_dump: bool | None
    paper_exit_action: str | None
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon", require_text(self.horizon, "horizon", max_length=16))
        for field_name in ("forward_return", "mfe", "mae"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, to_decimal(value, field_name))
        normalized_times: dict[str, Decimal | None] = {}
        for key, value in self.time_to_multiple.items():
            normalized_key = require_text(str(key), "target multiple")
            normalized_time = None if value is None else to_decimal(value, "time_to_multiple")
            if normalized_time is not None and normalized_time < 0:
                raise ValueError("time_to_multiple must be non-negative")
            normalized_times[normalized_key] = normalized_time
        object.__setattr__(
            self, "time_to_multiple", MappingProxyType(dict(sorted(normalized_times.items())))
        )
        if self.time_to_drawdown is not None:
            time_to_drawdown = to_decimal(self.time_to_drawdown, "time_to_drawdown")
            if time_to_drawdown < 0:
                raise ValueError("time_to_drawdown must be non-negative")
            object.__setattr__(self, "time_to_drawdown", time_to_drawdown)
        for field_name in ("liquidity_collapsed", "rugged", "creator_dump"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be boolean or None")
        if self.paper_exit_action is not None:
            object.__setattr__(
                self,
                "paper_exit_action",
                require_text(self.paper_exit_action, "paper_exit_action", max_length=32).upper(),
            )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(
            self, "evidence_refs", _normalized_refs(self.evidence_refs, "evidence_refs")
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "horizon": self.horizon,
            "forward_return": _json_safe(self.forward_return),
            "mfe": _json_safe(self.mfe),
            "mae": _json_safe(self.mae),
            "time_to_multiple": _json_safe(self.time_to_multiple),
            "time_to_drawdown": _json_safe(self.time_to_drawdown),
            "liquidity_collapsed": self.liquidity_collapsed,
            "rugged": self.rugged,
            "creator_dump": self.creator_dump,
            "paper_exit_action": self.paper_exit_action,
            "quality_state": self.quality_state.value,
            "reason_codes": _json_safe(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class OutcomeLabel:
    """All future labels for one signal checkpoint."""

    checkpoint_id: UUID
    token_id: UUID
    signal_at: datetime
    baseline_price: Decimal | None
    horizons: tuple[OutcomeHorizonLabel, ...]
    quality_state: QualityState
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("checkpoint_id and token_id must be UUID values")
        object.__setattr__(self, "signal_at", ensure_utc(self.signal_at, "signal_at"))
        if self.baseline_price is not None:
            baseline = to_decimal(self.baseline_price, "baseline_price")
            if baseline <= 0:
                raise ValueError("baseline_price must be positive")
            object.__setattr__(self, "baseline_price", baseline)
        horizons = tuple(self.horizons)
        if any(not isinstance(value, OutcomeHorizonLabel) for value in horizons):
            raise TypeError("horizons must contain OutcomeHorizonLabel values")
        object.__setattr__(self, "horizons", horizons)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(
            self, "evidence_refs", _normalized_refs(self.evidence_refs, "evidence_refs")
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "token_id": str(self.token_id),
            "signal_at": self.signal_at.isoformat(),
            "baseline_price": _json_safe(self.baseline_price),
            "horizons": [value.to_json_dict() for value in self.horizons],
            "quality_state": self.quality_state.value,
            "reason_codes": _json_safe(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class ReplayCohortKey:
    """Stable dimensions used to segment replay outcomes without resampling data."""

    launch_venue: str
    liquidity_band: str
    token_age_band: str
    alpha_score_band: str
    confidence_band: str
    smart_wallet_confluence: str
    social_velocity_band: str

    def __post_init__(self) -> None:
        for field_name in (
            "launch_venue",
            "liquidity_band",
            "token_age_band",
            "alpha_score_band",
            "confidence_band",
            "smart_wallet_confluence",
            "social_velocity_band",
        ):
            normalized = require_text(getattr(self, field_name), field_name, max_length=64)
            object.__setattr__(self, field_name, normalized)
        object.__setattr__(self, "launch_venue", self.launch_venue.lower())

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.launch_venue,
                self.liquidity_band,
                self.token_age_band,
                self.alpha_score_band,
                self.confidence_band,
                self.smart_wallet_confluence,
                self.social_velocity_band,
            )
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "launch_venue": self.launch_venue,
            "liquidity_band": self.liquidity_band,
            "token_age_band": self.token_age_band,
            "alpha_score_band": self.alpha_score_band,
            "confidence_band": self.confidence_band,
            "smart_wallet_confluence": self.smart_wallet_confluence,
            "social_velocity_band": self.social_velocity_band,
        }


@dataclass(frozen=True, slots=True)
class ReplayCohortSummary:
    """Aggregate, explainable outcome metrics for one replay cohort."""

    key: ReplayCohortKey
    checkpoint_ids: tuple[UUID, ...]
    sample_count: int
    labeled_count: int
    forward_return_mean_by_horizon: Mapping[str, Decimal | None]
    rug_rate_by_horizon: Mapping[str, Decimal | None]

    def __post_init__(self) -> None:
        if not isinstance(self.key, ReplayCohortKey):
            raise TypeError("key must be a ReplayCohortKey")
        checkpoint_ids = tuple(self.checkpoint_ids)
        if any(not isinstance(value, UUID) for value in checkpoint_ids):
            raise TypeError("checkpoint_ids must contain UUID values")
        if tuple(sorted(checkpoint_ids, key=str)) != checkpoint_ids:
            raise ValueError("checkpoint_ids must be sorted")
        if not isinstance(self.sample_count, int) or self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")
        if self.sample_count != len(checkpoint_ids):
            raise ValueError("sample_count must match checkpoint_ids")
        if (
            not isinstance(self.labeled_count, int)
            or not 0 <= self.labeled_count <= self.sample_count
        ):
            raise ValueError("labeled_count must be within sample_count")
        object.__setattr__(self, "checkpoint_ids", checkpoint_ids)
        object.__setattr__(
            self,
            "forward_return_mean_by_horizon",
            self._decimal_mapping(self.forward_return_mean_by_horizon, "forward return"),
        )
        object.__setattr__(
            self,
            "rug_rate_by_horizon",
            self._rate_mapping(self.rug_rate_by_horizon),
        )

    @staticmethod
    def _decimal_mapping(
        values: Mapping[str, Decimal | None],
        field_name: str,
    ) -> Mapping[str, Decimal | None]:
        if not isinstance(values, Mapping):
            raise TypeError(f"{field_name} metrics must be a mapping")
        normalized = {
            require_text(str(key), f"{field_name} horizon"): (
                None if value is None else to_decimal(value, field_name)
            )
            for key, value in values.items()
        }
        return MappingProxyType(dict(sorted(normalized.items())))

    @classmethod
    def _rate_mapping(cls, values: Mapping[str, Decimal | None]) -> Mapping[str, Decimal | None]:
        normalized = cls._decimal_mapping(values, "rug rate")
        if any(
            value is not None and not Decimal("0") <= value <= Decimal("1")
            for value in normalized.values()
        ):
            raise ValueError("rug rates must be between zero and one")
        return normalized

    def to_json_dict(self) -> dict[str, object]:
        return {
            "key": self.key.to_json_dict(),
            "checkpoint_ids": [str(value) for value in self.checkpoint_ids],
            "sample_count": self.sample_count,
            "labeled_count": self.labeled_count,
            "forward_return_mean_by_horizon": _json_safe(self.forward_return_mean_by_horizon),
            "rug_rate_by_horizon": _json_safe(self.rug_rate_by_horizon),
        }


@dataclass(frozen=True, slots=True)
class ReplayCheckpointResult:
    """Feature, strategy and outcome projections for one checkpoint."""

    checkpoint: ReplayCheckpoint
    correlation: CorrelationSnapshot
    feature_snapshots: tuple[FeatureSnapshot, ...]
    strategy_snapshot: StrategySnapshot | None
    outcome: OutcomeLabel
    included_event_ids: tuple[UUID, ...]
    excluded_future_event_ids: tuple[UUID, ...]
    cohort: ReplayCohortKey | None = None
    early_outcome: EarlyOutcomeLabel | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint, ReplayCheckpoint):
            raise TypeError("checkpoint must be a ReplayCheckpoint")
        if not isinstance(self.correlation, CorrelationSnapshot):
            raise TypeError("correlation must be a CorrelationSnapshot")
        snapshots = tuple(self.feature_snapshots)
        if any(not isinstance(value, FeatureSnapshot) for value in snapshots):
            raise TypeError("feature_snapshots must contain FeatureSnapshot values")
        object.__setattr__(self, "feature_snapshots", snapshots)
        if self.strategy_snapshot is not None and not isinstance(
            self.strategy_snapshot, StrategySnapshot
        ):
            raise TypeError("strategy_snapshot must be a StrategySnapshot or None")
        if not isinstance(self.outcome, OutcomeLabel):
            raise TypeError("outcome must be an OutcomeLabel")
        if self.cohort is not None and not isinstance(self.cohort, ReplayCohortKey):
            raise TypeError("cohort must be a ReplayCohortKey or None")
        for field_name in ("included_event_ids", "excluded_future_event_ids"):
            values = tuple(getattr(self, field_name))
            if any(not isinstance(value, UUID) for value in values):
                raise TypeError(f"{field_name} must contain UUID values")
            object.__setattr__(self, field_name, values)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "checkpoint": self.checkpoint.to_json_dict(),
            "cohort_key": None if self.cohort is None else self.cohort.key,
            "cohort": None if self.cohort is None else self.cohort.to_json_dict(),
            "included_event_ids": [str(value) for value in self.included_event_ids],
            "excluded_future_event_ids": [str(value) for value in self.excluded_future_event_ids],
            "correlation": _correlation_to_json(self.correlation),
            "feature_snapshots": [_feature_to_json(value) for value in self.feature_snapshots],
            "strategy_snapshot": (
                None
                if self.strategy_snapshot is None
                else _strategy_to_json(self.strategy_snapshot)
            ),
            "outcome": self.outcome.to_json_dict(),
            "early_outcome": (
                None if self.early_outcome is None else self.early_outcome.to_json_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class ResearchReplayResult:
    """Deterministic, redacted artifact emitted by the replay harness."""

    manifest: ResearchReplayManifest
    dataset_digest: str
    checkpoints: tuple[ReplayCheckpointResult, ...]
    partition_counts: Mapping[str, int] = field(default_factory=dict)
    cohorts: tuple[ReplayCohortSummary, ...] = ()
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, ResearchReplayManifest):
            raise TypeError("manifest must be a ResearchReplayManifest")
        object.__setattr__(
            self, "dataset_digest", require_text(self.dataset_digest, "dataset_digest")
        )
        checkpoints = tuple(self.checkpoints)
        if any(not isinstance(value, ReplayCheckpointResult) for value in checkpoints):
            raise TypeError("checkpoints must contain ReplayCheckpointResult values")
        object.__setattr__(self, "checkpoints", checkpoints)
        if not isinstance(self.partition_counts, Mapping):
            raise TypeError("partition_counts must be a mapping")
        partitions: dict[str, int] = {}
        for key, count in self.partition_counts.items():
            normalized_key = require_text(str(key), "partition key", max_length=256)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("partition counts must be non-negative integers")
            partitions[normalized_key] = count
        object.__setattr__(
            self, "partition_counts", MappingProxyType(dict(sorted(partitions.items())))
        )
        cohorts = tuple(self.cohorts)
        if any(not isinstance(value, ReplayCohortSummary) for value in cohorts):
            raise TypeError("cohorts must contain ReplayCohortSummary values")
        if tuple(sorted(cohorts, key=lambda value: value.key.key)) != cohorts:
            raise ValueError("cohorts must be sorted by key")
        object.__setattr__(self, "cohorts", cohorts)
        material = {
            "manifest": self.manifest.to_json_dict(),
            "dataset_digest": self.dataset_digest,
            "partition_counts": self.partition_counts,
            "cohorts": [value.to_json_dict() for value in cohorts],
            "checkpoints": [value.to_json_dict() for value in checkpoints],
        }
        object.__setattr__(
            self,
            "artifact_digest",
            f"sha256:{hashlib.sha256(_canonical_json(material).encode()).hexdigest()}",
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema": REPLAY_HARNESS_VERSION,
            "manifest": self.manifest.to_json_dict(),
            "dataset_digest": self.dataset_digest,
            "artifact_digest": self.artifact_digest,
            "modes": {
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            "partition_counts": dict(self.partition_counts),
            "cohorts": [value.to_json_dict() for value in self.cohorts],
            "checkpoints": [value.to_json_dict() for value in self.checkpoints],
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_json_dict())

    def to_csv(self) -> str:
        """Return a deterministic flat outcome artifact for spreadsheet tooling."""

        fieldnames = (
            "dataset_digest",
            "strategy_name",
            "strategy_version",
            "checkpoint_id",
            "token_id",
            "signal_at",
            "cohort_key",
            "horizon",
            "baseline_price",
            "forward_return",
            "mfe",
            "mae",
            "time_to_multiple",
            "time_to_drawdown",
            "liquidity_collapsed",
            "rugged",
            "creator_dump",
            "paper_exit_action",
            "early_outcome",
            "quality_state",
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for checkpoint in self.checkpoints:
            for horizon in checkpoint.outcome.horizons:
                writer.writerow(
                    {
                        "dataset_digest": self.dataset_digest,
                        "strategy_name": self.manifest.strategy_name,
                        "strategy_version": self.manifest.strategy_version,
                        "checkpoint_id": str(checkpoint.checkpoint.id),
                        "token_id": str(checkpoint.checkpoint.token_id),
                        "signal_at": checkpoint.outcome.signal_at.isoformat(),
                        "cohort_key": (
                            None if checkpoint.cohort is None else checkpoint.cohort.key
                        ),
                        "horizon": horizon.horizon,
                        "baseline_price": _csv_value(checkpoint.outcome.baseline_price),
                        "forward_return": _csv_value(horizon.forward_return),
                        "mfe": _csv_value(horizon.mfe),
                        "mae": _csv_value(horizon.mae),
                        "time_to_multiple": _canonical_json(horizon.time_to_multiple),
                        "time_to_drawdown": _csv_value(horizon.time_to_drawdown),
                        "liquidity_collapsed": _csv_value(horizon.liquidity_collapsed),
                        "rugged": _csv_value(horizon.rugged),
                        "creator_dump": _csv_value(horizon.creator_dump),
                        "paper_exit_action": _csv_value(horizon.paper_exit_action),
                        "early_outcome": _canonical_json(checkpoint.early_outcome.to_json_dict())
                        if checkpoint.early_outcome is not None
                        else None,
                        "quality_state": horizon.quality_state.value,
                    }
                )
        return output.getvalue()


def _csv_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


@dataclass(frozen=True, slots=True)
class ReplayStrategyComparison:
    """Comparison artifact proving strategy runs share one immutable event set."""

    dataset_digest: str
    results: tuple[ResearchReplayResult, ...]
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "dataset_digest", require_text(self.dataset_digest, "dataset_digest")
        )
        results = tuple(self.results)
        if not results:
            raise ValueError("strategy comparison requires at least one result")
        if any(not isinstance(value, ResearchReplayResult) for value in results):
            raise TypeError("results must contain ResearchReplayResult values")
        if any(value.dataset_digest != self.dataset_digest for value in results):
            raise ValueError("strategy comparison results must share the dataset digest")
        identities = tuple(
            (value.manifest.strategy_name, value.manifest.strategy_version) for value in results
        )
        if len(set(identities)) != len(identities):
            raise ValueError("strategy comparison identities must be unique")
        baseline_shape = tuple(
            (
                value.checkpoint.id,
                value.included_event_ids,
                value.excluded_future_event_ids,
            )
            for value in results[0].checkpoints
        )
        if any(
            tuple(
                (
                    value.checkpoint.id,
                    value.included_event_ids,
                    value.excluded_future_event_ids,
                )
                for value in result.checkpoints
            )
            != baseline_shape
            for result in results[1:]
        ):
            raise ValueError("strategy comparison results must share checkpoint event boundaries")
        object.__setattr__(self, "results", results)
        material = {
            "dataset_digest": self.dataset_digest,
            "results": [value.to_json_dict() for value in results],
        }
        object.__setattr__(
            self,
            "artifact_digest",
            f"sha256:{hashlib.sha256(_canonical_json(material).encode()).hexdigest()}",
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema": f"{REPLAY_HARNESS_VERSION}:strategy-comparison",
            "dataset_digest": self.dataset_digest,
            "artifact_digest": self.artifact_digest,
            "modes": {
                "analysis_only": True,
                "paper_trading": True,
                "manual_execution": False,
                "auto_execution": False,
            },
            "strategies": [
                {
                    "name": value.manifest.strategy_name,
                    "version": value.manifest.strategy_version,
                    "artifact_digest": value.artifact_digest,
                }
                for value in self.results
            ],
            "results": [value.to_json_dict() for value in self.results],
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_json_dict())


def _feature_to_json(value: FeatureSnapshot) -> dict[str, object]:
    return {
        "id": str(value.id),
        "candidate_id": str(value.candidate_id),
        "as_of": value.as_of.isoformat(),
        "expires_at": value.expires_at.isoformat(),
        "feature_version": value.feature_version,
        "completeness": str(value.completeness),
        "confidence": str(value.confidence),
        "values": _json_safe(value.values),
        "provenance": [_json_safe(item) for item in value.provenance],
        "config_hash": value.config_hash,
        "quality_state": value.quality_state.value,
    }


def _strategy_to_json(value: StrategySnapshot) -> dict[str, object]:
    return {
        "strategy_name": value.strategy_name,
        "strategy_version": value.strategy_version,
        "candidate_id": str(value.candidate_id),
        "as_of": value.as_of.isoformat(),
        "raw_score": str(value.raw_score),
        "suggested_score": str(value.suggested_score),
        "components": _json_safe(value.components),
        "weighted_components": _json_safe(value.weighted_components),
        "penalties": _json_safe(value.penalties),
        "confidence": str(value.confidence),
        "risk_disposition": (
            value.risk_disposition.value
            if isinstance(value.risk_disposition, RiskDisposition)
            else value.risk_disposition
        ),
        "hard_blocks": list(value.hard_blocks),
        "reason_codes": _json_safe(value.reason_codes),
        "evidence_refs": list(value.evidence_refs),
        "feature_snapshot_id": str(value.feature_snapshot_id),
        "risk_assessment_id": str(value.risk_assessment_id),
        "config_hash": value.config_hash,
        "quality_state": value.quality_state.value,
        "advisory": value.advisory,
        "is_production": value.is_production,
    }


def _correlation_to_json(value: CorrelationSnapshot) -> dict[str, object]:
    return {
        "token_id": str(value.token.id),
        "as_of": value.as_of.isoformat(),
        "expires_at": value.expires_at.isoformat(),
        "version": value.version,
        "config_hash": value.config_hash,
        "quality_state": value.quality_state.value,
        "confidence": str(value.confidence),
        "source_independence_count": value.source_independence_count,
        "reason_codes": _json_safe(value.reason_codes),
        "evidence_refs": list(value.evidence_refs),
        "windows": {
            name: {
                "start_at": feature.start_at.isoformat(),
                "end_at": feature.end_at.isoformat(),
                "event_count": feature.event_count,
                "protocol_event_count": feature.protocol_event_count,
                "market_observation_count": feature.market_observation_count,
                "social_mention_count": feature.social_mention_count,
                "wallet_activity_count": feature.wallet_activity_count,
                "liquidity": _json_safe(feature.liquidity),
                "net_flow": _json_safe(feature.net_flow),
                "quality_state": feature.quality_state.value,
                "confidence": str(feature.confidence),
                "reason_codes": _json_safe(feature.reason_codes),
                "signal_hardening": {
                    key: _json_safe(snapshot.to_mapping())
                    for key, snapshot in feature.signal_hardening.items()
                },
            }
            for name, feature in sorted(value.windows.items())
        },
    }


def _payload_value(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        if name in payload:
            return payload[name]
    for nested_name in ("values", "metrics", "snapshot", "data"):
        nested = payload.get(nested_name)
        if isinstance(nested, Mapping):
            for name in names:
                if name in nested:
                    return nested[name]
    return _MISSING


def _decimal_value(value: object, field_name: str, *, positive: bool = False) -> Decimal | None:
    if value is _MISSING or value is None or isinstance(value, bool):
        return None
    try:
        parsed = to_decimal(value, field_name)
    except (TypeError, ValueError, InvalidOperation, OverflowError):
        return None
    if parsed <= 0 and positive:
        return None
    return parsed


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "rug", "rugged", "collapsed"}:
            return True
        if normalized in {"false", "no", "0", "safe", "healthy"}:
            return False
    return None


def _event_reference(record: ReplayEventRecord) -> str:
    return f"{record.observation.provenance.provider}:{record.observation.provenance.source_id}"


def _event_sort_key(record: ReplayEventRecord) -> tuple[object, ...]:
    return (
        record.event_at,
        record.observation.observed_at,
        record.observation.ingested_at,
        record.observation.kind,
        record.observation.provenance.provider,
        record.observation.provenance.source_id,
        str(record.event_id),
    )


class OutcomeLabeler:
    """Derive future-only labels from normalized replay observations."""

    def __init__(self, policy: OutcomeLabelPolicy | None = None) -> None:
        self.policy = policy or OutcomeLabelPolicy()

    def label(
        self,
        records: Sequence[ReplayEventRecord],
        checkpoint: ReplayCheckpoint,
    ) -> OutcomeLabel:
        if isinstance(records, str | bytes | bytearray):
            raise TypeError("records must be a sequence")
        normalized = tuple(records)
        if any(not isinstance(value, ReplayEventRecord) for value in normalized):
            raise TypeError("records must contain ReplayEventRecord values")
        token_records = tuple(
            sorted(
                (value for value in normalized if value.token_id == checkpoint.token_id),
                key=_event_sort_key,
            )
        )
        baseline_candidates = [
            (record, price)
            for record in token_records
            if record.event_at <= checkpoint.as_of
            and record.observation.observed_at <= checkpoint.as_of
            and record.observation.ingested_at <= checkpoint.as_of
            and record.observation.quality_state is QualityState.FRESH
            and (price := self._price(record)) is not None
        ]
        baseline_record: ReplayEventRecord | None = None
        baseline_price: Decimal | None = None
        if baseline_candidates:
            baseline_record, baseline_price = max(
                baseline_candidates,
                key=lambda item: _event_sort_key(item[0]),
            )
        if baseline_price is None or baseline_record is None:
            horizons = tuple(self._empty_horizon(name) for name, _ in self.policy.horizons)
            return OutcomeLabel(
                checkpoint_id=checkpoint.id,
                token_id=checkpoint.token_id,
                signal_at=checkpoint.as_of,
                baseline_price=None,
                horizons=horizons,
                quality_state=QualityState.UNKNOWN,
                reason_codes=(ReasonCode("OUTCOME_BASELINE_PRICE_MISSING"),),
                evidence_refs=(),
            )

        evidence_refs = [_event_reference(baseline_record)]
        labels: list[OutcomeHorizonLabel] = []
        for name, duration in self.policy.horizons:
            label = self._label_horizon(
                name,
                duration,
                token_records,
                checkpoint.as_of,
                baseline_price,
            )
            labels.append(label)
            for reference in label.evidence_refs:
                if reference not in evidence_refs:
                    evidence_refs.append(reference)
        quality = (
            QualityState.FRESH
            if any(
                any(
                    field is not None
                    for field in (
                        value.forward_return,
                        value.mfe,
                        value.mae,
                        value.liquidity_collapsed,
                        value.rugged,
                        value.creator_dump,
                        value.paper_exit_action,
                    )
                )
                for value in labels
            )
            else QualityState.UNKNOWN
        )
        reasons = [ReasonCode("OUTCOME_LABELS_BUILT")]
        if quality is QualityState.UNKNOWN:
            reasons.append(ReasonCode("OUTCOME_FUTURE_EVIDENCE_MISSING"))
        return OutcomeLabel(
            checkpoint_id=checkpoint.id,
            token_id=checkpoint.token_id,
            signal_at=checkpoint.as_of,
            baseline_price=baseline_price,
            horizons=tuple(labels),
            quality_state=quality,
            reason_codes=tuple(reasons),
            evidence_refs=tuple(evidence_refs),
        )

    def _empty_horizon(self, name: str) -> OutcomeHorizonLabel:
        return OutcomeHorizonLabel(
            horizon=name,
            forward_return=None,
            mfe=None,
            mae=None,
            time_to_multiple={
                self._multiple_name(value): None for value in self.policy.target_multiples
            },
            time_to_drawdown=None,
            liquidity_collapsed=None,
            rugged=None,
            creator_dump=None,
            paper_exit_action=None,
            quality_state=QualityState.UNKNOWN,
            reason_codes=(ReasonCode("OUTCOME_HORIZON_DATA_MISSING"),),
            evidence_refs=(),
        )

    def _label_horizon(
        self,
        name: str,
        duration: timedelta,
        records: Sequence[ReplayEventRecord],
        signal_at: datetime,
        baseline: Decimal,
    ) -> OutcomeHorizonLabel:
        end_at = signal_at + duration
        future = tuple(
            record
            for record in records
            if signal_at < record.event_at <= end_at
            and record.observation.observed_at <= end_at
            and record.observation.ingested_at <= end_at
            and record.observation.quality_state is QualityState.FRESH
        )
        price_points = tuple(
            (record, price) for record in future if (price := self._price(record)) is not None
        )
        price_values = tuple(price for _, price in price_points)
        terminal = price_values[-1] if price_values else None
        forward_return = None if terminal is None else terminal / baseline - Decimal("1")
        mfe = None if not price_values else max(price_values) / baseline - Decimal("1")
        mae = None if not price_values else min(price_values) / baseline - Decimal("1")
        times: dict[str, Decimal | None] = {}
        for multiple in self.policy.target_multiples:
            first = next(
                (record for record, price in price_points if price >= baseline * multiple),
                None,
            )
            times[self._multiple_name(multiple)] = (
                None
                if first is None
                else Decimal(str((first.event_at - signal_at).total_seconds()))
            )
        drawdown_target = baseline * (Decimal("1") - self.policy.drawdown_fraction)
        drawdown_record = next(
            (record for record, price in price_points if price <= drawdown_target),
            None,
        )
        time_to_drawdown = (
            None
            if drawdown_record is None
            else Decimal(str((drawdown_record.event_at - signal_at).total_seconds()))
        )
        all_refs = [_event_reference(record) for record in future]
        liquidity_values = tuple(
            (record, value) for record in future if (value := self._liquidity(record)) is not None
        )
        liquidity_collapsed: bool | None = None
        if liquidity_values:
            liquidity_collapsed = any(
                value <= self.policy.liquidity_collapse_threshold
                or (
                    previous is not None
                    and previous > 0
                    and (value - previous) / previous <= self.policy.liquidity_collapse_ratio
                )
                for (_, value), previous in self._with_previous(liquidity_values)
            )
        rugged: bool | None = None
        creator_dump: bool | None = None
        paper_exit_action: str | None = None
        for record in future:
            payload = record.observation.normalized_payload
            rugged_value = _bool_value(
                _payload_value(payload, "rugged", "rug", "is_rug", "security_risk")
            )
            if rugged_value is None and record.observation.kind in _RUG_KINDS:
                outcome = _payload_value(payload, "outcome", "event_type")
                if isinstance(outcome, str) and outcome.strip().lower() in {"rug", "rugged"}:
                    rugged_value = True
            if rugged_value is not None:
                rugged = rugged_value if rugged is None else rugged or rugged_value
            creator_value = _bool_value(
                _payload_value(payload, "creator_dump", "creator_wallet_sell", "creator_sold")
            )
            actor_role = _payload_value(payload, "actor_role", "role")
            side = _payload_value(payload, "side", "action", "direction")
            if (
                creator_value is None
                and isinstance(actor_role, str)
                and actor_role.strip().lower() == "creator"
                and isinstance(side, str)
                and side.strip().lower() in {"sell", "sold"}
            ):
                creator_value = True
            if creator_value is not None:
                creator_dump = (
                    creator_value if creator_dump is None else creator_dump or creator_value
                )
            if record.observation.kind in _PAPER_EXIT_KINDS:
                action = _payload_value(payload, "action", "exit_action", "status")
                if isinstance(action, str) and paper_exit_action is None:
                    paper_exit_action = action
        has_evidence = bool(future)
        quality = QualityState.FRESH if has_evidence else QualityState.UNKNOWN
        reasons = (
            ReasonCode("OUTCOME_HORIZON_LABELED")
            if has_evidence
            else ReasonCode("OUTCOME_HORIZON_DATA_MISSING")
        )
        return OutcomeHorizonLabel(
            horizon=name,
            forward_return=forward_return,
            mfe=mfe,
            mae=mae,
            time_to_multiple=times,
            time_to_drawdown=time_to_drawdown,
            liquidity_collapsed=liquidity_collapsed,
            rugged=rugged,
            creator_dump=creator_dump,
            paper_exit_action=paper_exit_action,
            quality_state=quality,
            reason_codes=(reasons,),
            evidence_refs=tuple(dict.fromkeys(all_refs)),
        )

    @staticmethod
    def _with_previous(
        values: Sequence[tuple[ReplayEventRecord, Decimal]],
    ) -> tuple[tuple[tuple[ReplayEventRecord, Decimal], Decimal | None], ...]:
        previous: Decimal | None = None
        result: list[tuple[tuple[ReplayEventRecord, Decimal], Decimal | None]] = []
        for value in values:
            result.append((value, previous))
            previous = value[1]
        return tuple(result)

    @staticmethod
    def _multiple_name(value: Decimal) -> str:
        normalized = f"{value.normalize():f}".rstrip("0").rstrip(".")
        return f"{normalized}x"

    @staticmethod
    def _price(record: ReplayEventRecord) -> Decimal | None:
        if record.observation.kind not in _PRICE_KINDS:
            return None
        return market_reference_price(record.observation, include_shadow=True)

    @staticmethod
    def _liquidity(record: ReplayEventRecord) -> Decimal | None:
        raw = _payload_value(
            record.observation.normalized_payload,
            "liquidity_usd",
            "liquidity",
            "liquidityUsd",
        )
        return _decimal_value(raw, "liquidity", positive=True)


def _score_band(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    if value < Decimal("25"):
        return "0-25"
    if value < Decimal("50"):
        return "25-50"
    if value < Decimal("75"):
        return "50-75"
    return "75-100"


def _confidence_band(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    if value < Decimal("0.25"):
        return "0-0.25"
    if value < Decimal("0.5"):
        return "0.25-0.5"
    if value < Decimal("0.75"):
        return "0.5-0.75"
    return "0.75-1"


def _liquidity_band(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    if value < Decimal("10000"):
        return "<10k"
    if value < Decimal("50000"):
        return "10k-50k"
    if value < Decimal("250000"):
        return "50k-250k"
    return ">=250k"


def _token_age_band(seconds: Decimal | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < Decimal("60"):
        return "0-1m"
    if seconds < Decimal("300"):
        return "1-5m"
    if seconds < Decimal("900"):
        return "5-15m"
    return "15m+"


def _family(feature: FeatureSnapshot | None, name: str) -> Mapping[str, object] | None:
    if feature is None:
        return None
    raw_families = feature.values.get("families")
    if not isinstance(raw_families, Mapping):
        return None
    raw_family = raw_families.get(name)
    return raw_family if isinstance(raw_family, Mapping) else None


def _cohort_key(
    records: Sequence[ReplayEventRecord],
    checkpoint: ReplayCheckpoint,
    features: Sequence[FeatureSnapshot],
    *,
    feature_window: str,
    strategy_snapshot: StrategySnapshot | None,
) -> ReplayCohortKey:
    launch_times = [
        record.event_at
        for record in records
        if record.event_at <= checkpoint.as_of
        and record.observation.kind in {"protocol.lifecycle", "protocol.event"}
        and isinstance(
            (
                event_type := _payload_value(
                    record.observation.normalized_payload,
                    "event_type",
                    "lifecycle_event",
                    "type",
                )
            ),
            str,
        )
        and event_type.strip().lower() in {"launch", "create", "created", "token_created", "mint"}
    ]
    token_age = (
        Decimal(str((checkpoint.as_of - min(launch_times)).total_seconds()))
        if launch_times
        else None
    )
    selected_feature = next(
        (value for value in features if value.values.get("window") == feature_window),
        None,
    )
    liquidity_family = _family(selected_feature, "liquidity")
    wallet_family = _family(selected_feature, "wallet")
    social_family = _family(selected_feature, "social")

    liquidity = (
        _decimal_value(
            _payload_value(liquidity_family or {}, "liquidity"),
            "cohort liquidity",
            positive=True,
        )
        if liquidity_family is not None and liquidity_family.get("available") is True
        else None
    )
    feature_is_fresh = (
        selected_feature is not None and selected_feature.quality_state is QualityState.FRESH
    )
    score = (
        strategy_snapshot.suggested_score
        if strategy_snapshot is not None and strategy_snapshot.quality_state is QualityState.FRESH
        else None
    )
    confidence = (
        strategy_snapshot.confidence
        if strategy_snapshot is not None and strategy_snapshot.quality_state is QualityState.FRESH
        else selected_feature.confidence
        if feature_is_fresh and selected_feature is not None
        else None
    )
    smart_confluence = "unknown"
    if wallet_family is not None and wallet_family.get("available") is True:
        clusters = _decimal_value(
            _payload_value(wallet_family, "independent_entry_clusters"),
            "independent entry clusters",
        )
        internal_score = _decimal_value(
            _payload_value(wallet_family, "internal_score"),
            "internal wallet score",
        )
        if clusters is not None or internal_score is not None:
            smart_confluence = (
                "strong"
                if (clusters is not None and clusters >= 2)
                or (internal_score is not None and internal_score >= 75)
                else "present"
                if (clusters is not None and clusters > 0)
                or (internal_score is not None and internal_score > 0)
                else "none"
            )
    social_score = None
    if social_family is not None and social_family.get("available") is True:
        social_score = _decimal_value(_payload_value(social_family, "social_score"), "social score")
    return ReplayCohortKey(
        launch_venue=checkpoint.venue,
        liquidity_band=_liquidity_band(liquidity),
        token_age_band=_token_age_band(token_age),
        alpha_score_band=_score_band(score),
        confidence_band=_confidence_band(confidence),
        smart_wallet_confluence=smart_confluence,
        social_velocity_band=_score_band(social_score),
    )


def _cohort_summaries(results: Sequence[ReplayCheckpointResult]) -> tuple[ReplayCohortSummary, ...]:
    grouped: dict[str, list[ReplayCheckpointResult]] = {}
    keys: dict[str, ReplayCohortKey] = {}
    for result in results:
        if result.cohort is None:
            continue
        grouped.setdefault(result.cohort.key, []).append(result)
        keys[result.cohort.key] = result.cohort
    summaries: list[ReplayCohortSummary] = []
    for cohort_key in sorted(grouped):
        values = grouped[cohort_key]
        horizon_names = sorted(
            {horizon.horizon for value in values for horizon in value.outcome.horizons}
        )
        means: dict[str, Decimal | None] = {}
        rug_rates: dict[str, Decimal | None] = {}
        for horizon_name in horizon_names:
            horizon_values = [
                horizon
                for value in values
                for horizon in value.outcome.horizons
                if horizon.horizon == horizon_name
            ]
            returns = [
                horizon.forward_return
                for horizon in horizon_values
                if horizon.forward_return is not None
            ]
            rug_values = [
                horizon.rugged for horizon in horizon_values if horizon.rugged is not None
            ]
            means[horizon_name] = (
                None if not returns else sum(returns, Decimal("0")) / Decimal(len(returns))
            )
            rug_rates[horizon_name] = (
                None
                if not rug_values
                else Decimal(sum(value is True for value in rug_values)) / Decimal(len(rug_values))
            )
        summaries.append(
            ReplayCohortSummary(
                key=keys[cohort_key],
                checkpoint_ids=tuple(sorted((value.checkpoint.id for value in values), key=str)),
                sample_count=len(values),
                labeled_count=sum(
                    value.outcome.quality_state is QualityState.FRESH for value in values
                ),
                forward_return_mean_by_horizon=means,
                rug_rate_by_horizon=rug_rates,
            )
        )
    return tuple(summaries)


class ReplayHarness:
    """Compose existing normalized builders into a deterministic research run."""

    def __init__(
        self,
        *,
        correlation_builder: CorrelationWindowBuilder | None = None,
        feature_aggregator: FeatureWindowAggregator | None = None,
        outcome_policy: OutcomeLabelPolicy | None = None,
        early_outcome_policy: EarlyOutcomePolicy | None = None,
        signal_hardening_analyzer: SignalHardeningAnalyzer | None = None,
    ) -> None:
        from .early_replay import EarlyOutcomeLabeler

        self.correlation_builder = correlation_builder or CorrelationWindowBuilder(
            include_shadow=True
        )
        self.feature_aggregator = feature_aggregator or FeatureWindowAggregator()
        self.outcome_labeler = OutcomeLabeler(outcome_policy)
        self.early_outcome_labeler = EarlyOutcomeLabeler(early_outcome_policy)
        self.signal_hardening_analyzer = signal_hardening_analyzer or SignalHardeningAnalyzer(
            include_shadow=True
        )

    def replay(
        self,
        dataset: ReplayDataset,
        *,
        manifest: ResearchReplayManifest,
        strategy: AlphaStrategy | None = None,
    ) -> ResearchReplayResult:
        if not isinstance(dataset, ReplayDataset):
            raise TypeError("dataset must be a ReplayDataset")
        if not isinstance(manifest, ResearchReplayManifest):
            raise TypeError("manifest must be a ResearchReplayManifest")
        if dataset.dataset_id != manifest.dataset_id:
            raise ValueError("manifest dataset_id does not match dataset")
        if dataset.dataset_version != manifest.dataset_version:
            raise ValueError("manifest dataset_version does not match dataset")
        dataset_digest = dataset.digest
        if manifest.dataset_digest is not None and manifest.dataset_digest != dataset_digest:
            raise ValueError("manifest dataset_digest does not match dataset")
        if manifest.outcome_policy_version != self.outcome_labeler.policy.version:
            raise ValueError("manifest outcome_policy_version does not match label policy")
        if manifest.signal_hardening_version != self.signal_hardening_analyzer.policy.version:
            raise ValueError("manifest signal_hardening_version does not match analyzer")
        if strategy is not None:
            if not isinstance(strategy, AlphaStrategy):
                raise TypeError("strategy must implement AlphaStrategy")
            if (
                strategy.strategy_name != manifest.strategy_name
                or strategy.strategy_version != manifest.strategy_version
            ):
                raise ValueError("manifest strategy identity does not match strategy")
        for record in dataset.events:
            if record.parser_version != manifest.parser_version:
                raise ValueError("replay event parser_version does not match manifest")
            if record.registry_version != manifest.registry_version:
                raise ValueError("replay event registry_version does not match manifest")
            if record.event_schema_version != manifest.event_schema_version:
                raise ValueError("replay event schema_version does not match manifest")
        results: list[ReplayCheckpointResult] = []
        for checkpoint in dataset.checkpoints:
            if checkpoint.as_of > manifest.as_of:
                raise ValueError("checkpoint is outside manifest event-time boundary")
            if checkpoint.risk_assessment is not None:
                if checkpoint.risk_assessment.config_hash != manifest.config_hash:
                    raise ValueError("checkpoint risk config_hash does not match manifest")
                if checkpoint.risk_assessment.as_of > checkpoint.as_of:
                    raise ValueError("checkpoint risk assessment is future evidence")
            token_records = tuple(
                record for record in dataset.events if record.token_id == checkpoint.token_id
            )
            included = tuple(
                sorted(
                    (
                        record
                        for record in token_records
                        if record.event_at <= checkpoint.as_of
                        and record.observation.observed_at <= checkpoint.as_of
                        and record.observation.ingested_at <= checkpoint.as_of
                    ),
                    key=_event_sort_key,
                )
            )
            excluded = tuple(
                sorted(
                    (record.event_id for record in token_records if record not in included),
                    key=str,
                )
            )
            token = dataset.token(checkpoint.token_id)
            signal_hardening_by_window = self._signal_hardening_by_window(
                token,
                tuple(record.observation for record in included),
                now=checkpoint.as_of,
                config_hash=manifest.config_hash,
            )
            correlation = self.correlation_builder.build(
                token,
                observations=tuple(record.observation for record in included),
                now=checkpoint.as_of,
                config_hash=manifest.config_hash,
                signal_hardening=signal_hardening_by_window,
            )
            features = self.feature_aggregator.build(
                checkpoint.candidate_id,
                correlation,
                now=checkpoint.as_of,
                config_hash=manifest.config_hash,
                risk_assessment=checkpoint.risk_assessment,
            )
            strategy_snapshot: StrategySnapshot | None = None
            if strategy is not None and checkpoint.risk_assessment is not None:
                feature = next(
                    (
                        value
                        for value in features
                        if value.values.get("window") == manifest.feature_window
                    ),
                    None,
                )
                if feature is None:
                    raise ValueError(
                        "manifest feature_window is absent from reconstructed features"
                    )
                strategy_snapshot = strategy.evaluate(
                    feature,
                    checkpoint.risk_assessment,
                    now=checkpoint.as_of,
                    config_hash=manifest.config_hash,
                )
            outcome = self.outcome_labeler.label(token_records, checkpoint)
            early_outcome = self.early_outcome_labeler.label(token_records, checkpoint)
            cohort = _cohort_key(
                token_records,
                checkpoint,
                features,
                feature_window=manifest.feature_window,
                strategy_snapshot=strategy_snapshot,
            )
            results.append(
                ReplayCheckpointResult(
                    checkpoint=checkpoint,
                    correlation=correlation,
                    feature_snapshots=features,
                    strategy_snapshot=strategy_snapshot,
                    outcome=outcome,
                    included_event_ids=tuple(record.event_id for record in included),
                    excluded_future_event_ids=excluded,
                    cohort=cohort,
                    early_outcome=early_outcome,
                )
            )
        checkpoint_results = tuple(results)
        return ResearchReplayResult(
            manifest=manifest,
            dataset_digest=dataset_digest,
            checkpoints=checkpoint_results,
            partition_counts=dataset.partition_counts,
            cohorts=_cohort_summaries(checkpoint_results),
        )

    def _signal_hardening_by_window(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
    ) -> Mapping[str, Mapping[str, SignalHardeningEvidence]]:
        """Build all hardening evidence from the same included replay observations."""

        windows: dict[str, Mapping[str, SignalHardeningEvidence]] = {}
        for name, duration in self.correlation_builder.policy.window_durations:
            window_start = now - duration
            windows[name] = {
                "momentum": self.signal_hardening_analyzer.analyze_momentum(
                    token,
                    observations,
                    now=now,
                    config_hash=config_hash,
                    window_start=window_start,
                    window_end=now,
                ),
                "move_funding": self.signal_hardening_analyzer.analyze_move_funding(
                    token,
                    observations,
                    now=now,
                    config_hash=config_hash,
                    window_start=window_start,
                    window_end=now,
                ),
                "deployer": self.signal_hardening_analyzer.analyze_deployer_activity(
                    token,
                    observations,
                    now=now,
                    config_hash=config_hash,
                ),
                "launch_footprint": self.signal_hardening_analyzer.analyze_launch_footprint(
                    token,
                    observations,
                    now=now,
                    config_hash=config_hash,
                ),
                "token_lock": self.signal_hardening_analyzer.analyze_token_lock(
                    token,
                    observations,
                    now=now,
                    config_hash=config_hash,
                ),
            }
        return windows

    def compare_strategies(
        self,
        dataset: ReplayDataset,
        *,
        manifest: ResearchReplayManifest,
        strategies: Sequence[AlphaStrategy],
    ) -> ReplayStrategyComparison:
        """Replay multiple strategies against the exact same normalized dataset."""

        if isinstance(strategies, str | bytes | bytearray):
            raise TypeError("strategies must be a sequence")
        values = tuple(strategies)
        if not values:
            raise ValueError("at least one strategy is required")
        if any(not isinstance(value, AlphaStrategy) for value in values):
            raise TypeError("strategies must implement AlphaStrategy")
        identities = tuple((value.strategy_name, value.strategy_version) for value in values)
        if len(set(identities)) != len(identities):
            raise ValueError("strategy identities must be unique")
        results = tuple(
            self.replay(
                dataset,
                manifest=replace(
                    manifest,
                    strategy_name=strategy.strategy_name,
                    strategy_version=strategy.strategy_version,
                ),
                strategy=strategy,
            )
            for strategy in values
        )
        return ReplayStrategyComparison(dataset_digest=dataset.digest, results=results)


__all__ = [
    "DEFAULT_OUTCOME_HORIZONS",
    "DEFAULT_TARGET_MULTIPLES",
    "OutcomeHorizonLabel",
    "OutcomeLabel",
    "OutcomeLabelPolicy",
    "OutcomeLabeler",
    "REPLAY_DATASET_SCHEMA_VERSION",
    "REPLAY_HARNESS_VERSION",
    "ReplayCheckpoint",
    "ReplayCheckpointResult",
    "ReplayDataset",
    "ReplayEventRecord",
    "ReplayHarness",
    "ReplayCohortKey",
    "ReplayCohortSummary",
    "ResearchReplayManifest",
    "ResearchReplayResult",
    "ReplayStrategyComparison",
]
