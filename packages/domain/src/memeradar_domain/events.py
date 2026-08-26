"""Replayable internal events and stable explanation codes."""

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .common import ensure_ordered_timestamps, freeze_mapping, require_text

_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class ReasonCode:
    """Stable, provider-neutral explanation code with optional evidence links."""

    code: str
    detail: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized_code = require_text(self.code, "reason code", max_length=64).upper()
        if not _REASON_CODE.fullmatch(normalized_code):
            raise ValueError("reason code must use uppercase letters, digits, '.', '_' or '-'")
        object.__setattr__(self, "code", normalized_code)
        if self.detail is not None:
            object.__setattr__(self, "detail", require_text(self.detail, "reason detail"))
        normalized_refs = tuple(
            require_text(reference, "evidence reference") for reference in self.evidence_refs
        )
        object.__setattr__(self, "evidence_refs", normalized_refs)

    def __str__(self) -> str:
        return self.code


def normalize_reason_codes(
    values: Iterable[ReasonCode | str],
    *,
    required: bool = False,
) -> tuple[ReasonCode, ...]:
    """Normalize and de-duplicate reason codes without losing first-seen order."""

    if isinstance(values, str | ReasonCode):
        raise TypeError("reason_codes must be a sequence")
    normalized: list[ReasonCode] = []
    seen: set[str] = set()
    for value in values:
        code = value if isinstance(value, ReasonCode) else ReasonCode(value)
        if code.code not in seen:
            normalized.append(code)
            seen.add(code.code)
    if required and not normalized:
        raise ValueError("reason_codes must contain at least one reason")
    return tuple(normalized)


def _canonicalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Common internal event envelope with deterministic replay metadata."""

    kind: str
    aggregate_type: str
    aggregate_id: UUID | str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    correlation_id: str
    producer: str
    payload: Mapping[str, object]
    id: UUID = field(default_factory=uuid4)
    schema_version: int = 1
    causation_id: UUID | None = None
    idempotency_key: str | None = None
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        if occurred is None:
            raise ValueError("occurred_at is required")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "kind", require_text(self.kind, "kind"))
        object.__setattr__(
            self,
            "aggregate_type",
            require_text(self.aggregate_type, "aggregate_type"),
        )
        if isinstance(self.aggregate_id, str):
            object.__setattr__(
                self,
                "aggregate_id",
                require_text(self.aggregate_id, "aggregate_id"),
            )
        elif not isinstance(self.aggregate_id, UUID):
            raise TypeError("aggregate_id must be a UUID or string")
        object.__setattr__(
            self,
            "correlation_id",
            require_text(self.correlation_id, "correlation_id", max_length=128),
        )
        object.__setattr__(self, "producer", require_text(self.producer, "producer"))
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if self.idempotency_key is not None:
            object.__setattr__(
                self,
                "idempotency_key",
                require_text(self.idempotency_key, "idempotency_key"),
            )
        object.__setattr__(self, "payload", freeze_mapping(self.payload, "payload"))
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes),
        )

    @property
    def dedupe_key(self) -> str:
        """Return the supplied idempotency key or the immutable event ID."""

        if self.idempotency_key is not None:
            return self.idempotency_key
        material = {
            "aggregate_id": str(self.aggregate_id),
            "aggregate_type": self.aggregate_type,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "correlation_id": self.correlation_id,
            "ingested_at": self.ingested_at.isoformat(),
            "kind": self.kind,
            "observed_at": self.observed_at.isoformat(),
            "payload": self.payload,
            "producer": self.producer,
            "reason_codes": [
                {
                    "code": reason.code,
                    "detail": reason.detail,
                    "evidence_refs": reason.evidence_refs,
                }
                for reason in self.reason_codes
            ],
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.isoformat(),
        }
        canonical = json.dumps(
            _canonicalize(material),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return f"event:{hashlib.sha256(canonical.encode()).hexdigest()}"
