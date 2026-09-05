"""Replayable internal events and stable explanation codes."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import isfinite
from urllib.parse import urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .common import (
    ensure_ordered_timestamps,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)
from .evidence import Freshness, Provenance, QualityState
from .identities import (
    Chain,
    normalize_chain,
    require_chain_address,
    require_evm_address,
    require_solana_address,
)

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


class GlobalEventIdempotencyConflict(ValueError):
    """Raised when a source reuses an event ID for different normalized content."""


def _normalize_global_text(value: str, field: str, *, max_length: int) -> str:
    normalized = unicodedata.normalize("NFKC", require_text(value, field, max_length=max_length))
    normalized = " ".join(normalized.split())
    return require_text(normalized, field, max_length=max_length)


def _normalize_global_url(value: str) -> str | None:
    candidate = require_text(value, "url", max_length=1024).rstrip(".,;:!?)]}")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit(("https", parsed.hostname.lower(), parsed.path, parsed.query, ""))


def _normalize_global_urls(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError("urls must be a sequence")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("urls must contain strings")
        url = _normalize_global_url(value)
        if url is not None and url not in normalized:
            normalized.append(url)
    return tuple(normalized)


def _normalize_global_addresses(
    values: Sequence[str],
    chain: Chain | None,
) -> tuple[str, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise TypeError("contract_addresses must be a sequence")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("contract_addresses must contain strings")
        if chain is not None:
            address = require_chain_address(value, chain, "contract address")
        elif value.strip().lower().startswith("0x"):
            address = require_evm_address(value, "contract address")
        else:
            address = require_solana_address(value, "contract address")
        if address not in normalized:
            normalized.append(address)
    return tuple(normalized)


def _first_payload_value(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _payload_texts(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (require_text(value, field, max_length=256),)
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("id", "name", "symbol", "ticker"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                values.append(candidate)
        return normalize_texts(values, field, max_item_length=256)
    if not isinstance(value, Sequence) or isinstance(value, bytes | bytearray):
        raise TypeError(f"{field} must be a string, mapping or sequence")
    values = []
    for item in value:
        if isinstance(item, Mapping):
            values.extend(_payload_texts(item, field))
        elif isinstance(item, str):
            values.append(item)
        else:
            raise TypeError(f"{field} must contain strings or mappings")
    return normalize_texts(values, field, max_item_length=256)


def _payload_addresses(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        address = value.get("address", value.get("contract_address", value.get("mint_address")))
        return () if address is None else (address,) if isinstance(address, str) else ()
    if not isinstance(value, Sequence) or isinstance(value, bytes | bytearray):
        raise TypeError("contract_addresses must be a string, mapping or sequence")
    values: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            values.extend(_payload_addresses(item))
        elif isinstance(item, str):
            values.append(item)
        else:
            raise TypeError("contract_addresses must contain strings or mappings")
    return tuple(values)


def _global_timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"{field} must be finite")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError(f"{field} is invalid") from exc
    if isinstance(value, str):
        normalized = require_text(value, field, max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), field)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} is invalid") from exc
    raise TypeError(f"{field} must be a datetime, timestamp or ISO string")


@dataclass(frozen=True, slots=True)
class GlobalEvent:
    """Provider-neutral source event retained as bounded, replayable evidence."""

    source: str
    event_id: str
    event_type: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    author_id: str | None = None
    entities: tuple[str, ...] = ()
    text: str | None = None
    urls: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()
    chain: Chain | str | None = None
    quality_state: QualityState | str = QualityState.UNKNOWN
    freshness: Freshness | None = None
    raw_payload_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ()
    id: UUID | None = None

    def __post_init__(self) -> None:
        source = require_text(self.source, "source", max_length=128).lower()
        event_id = require_text(self.event_id, "event_id", max_length=256)
        event_type = require_text(self.event_type, "event_type", max_length=128).lower()
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > observed:
            raise ValueError("provenance observed_at must not be later than observed_at")
        normalized_chain = None if self.chain is None else normalize_chain(self.chain)
        normalized_author = None
        if self.author_id is not None:
            normalized_author = require_text(self.author_id, "author_id", max_length=256)
        normalized_text = (
            None
            if self.text is None
            else _normalize_global_text(self.text, "text", max_length=20_000)
        )
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "author_id", normalized_author)
        object.__setattr__(
            self,
            "entities",
            normalize_texts(self.entities, "entities", max_item_length=256),
        )
        object.__setattr__(self, "text", normalized_text)
        object.__setattr__(self, "urls", _normalize_global_urls(self.urls))
        object.__setattr__(
            self,
            "contract_addresses",
            _normalize_global_addresses(self.contract_addresses, normalized_chain),
        )
        object.__setattr__(self, "chain", normalized_chain)
        normalized_quality = QualityState(self.quality_state)
        if self.freshness is not None:
            if not isinstance(self.freshness, Freshness):
                raise TypeError("freshness must be a Freshness or None")
            if self.freshness.as_of > observed:
                raise ValueError("freshness as_of must not be later than observed_at")
            if normalized_quality is QualityState.FRESH:
                normalized_quality = self.freshness.quality_state
        object.__setattr__(self, "quality_state", normalized_quality)
        object.__setattr__(
            self,
            "raw_payload_ref",
            None
            if self.raw_payload_ref is None
            else require_text(self.raw_payload_ref, "raw_payload_ref", max_length=512),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        if self.id is None:
            object.__setattr__(
                self,
                "id",
                uuid5(NAMESPACE_URL, f"memeradar:global-event:{source}:{event_id}"),
            )
        elif not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def source_id(self) -> str:
        """Compatibility spelling for the normalized source family."""

        return self.source

    @property
    def source_event_id(self) -> str:
        """Return the provider-assigned event identity."""

        return self.event_id

    @property
    def entity_ids(self) -> tuple[str, ...]:
        """Compatibility spelling for normalized entity references."""

        return self.entities

    @property
    def dedupe_key(self) -> str:
        """Return an idempotency key scoped to the source family."""

        return f"global-event:{self.source}:{self.event_id}"

    @property
    def content_identity(self) -> tuple[object, ...]:
        """Return source content identity without delivery metadata."""

        return (
            self.source,
            self.event_id,
            self.event_type,
            self.occurred_at,
            self.author_id,
            self.entities,
            self.text,
            self.urls,
            self.contract_addresses,
            self.chain,
        )

    def freshness_state(self, at: datetime) -> QualityState:
        """Resolve freshness while preserving explicit non-fresh quality."""

        quality_state = QualityState(self.quality_state)
        if quality_state is not QualityState.FRESH or self.freshness is None:
            return quality_state
        return self.freshness.state_at(at)

    def execution_eligible(self) -> bool:
        """Global events are evidence only and never authorize execution."""

        return False


def deduplicate_global_events(events: Sequence[GlobalEvent]) -> tuple[GlobalEvent, ...]:
    """Deduplicate source events and reject conflicting source-ID reuse."""

    if isinstance(events, str | bytes | bytearray):
        raise TypeError("events must be a sequence")
    seen: dict[str, GlobalEvent] = {}
    normalized: list[GlobalEvent] = []
    for event in events:
        if not isinstance(event, GlobalEvent):
            raise TypeError("events must contain GlobalEvent values")
        previous = seen.get(event.dedupe_key)
        if previous is None:
            seen[event.dedupe_key] = event
            normalized.append(event)
        elif previous.content_identity != event.content_identity:
            raise GlobalEventIdempotencyConflict(
                f"global event key {event.dedupe_key!r} was reused for different content"
            )
    return tuple(normalized)


def normalize_global_event(
    payload: Mapping[str, object],
    *,
    source: str,
    observed_at: datetime,
    ingested_at: datetime | None = None,
    parser_version: str = "global-event-v1",
    quality_state: QualityState | str = QualityState.FRESH,
    freshness: Freshness | None = None,
    raw_payload_ref: str | None = None,
    evidence_refs: Iterable[str] = (),
    reason_codes: Iterable[ReasonCode | str] = (),
    chain: Chain | str | None = None,
    reference_at: datetime | None = None,
    provenance: Provenance | None = None,
) -> GlobalEvent:
    """Normalize an allow-listed source mapping without retaining its raw payload."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    normalized_source = require_text(source, "source", max_length=128).lower()
    event_value = _first_payload_value(
        payload,
        "event_id",
        "source_event_id",
        "id",
        "post_id",
        "message_id",
        "article_id",
    )
    if not isinstance(event_value, str):
        raise ValueError("event_id is required")
    event_id = require_text(event_value, "event_id", max_length=256)
    occurred_value = _first_payload_value(
        payload,
        "occurred_at",
        "published_at",
        "created_at",
        "posted_at",
        "timestamp",
    )
    if occurred_value is None:
        raise ValueError("occurred_at is required")
    occurred_at = _global_timestamp(occurred_value, "occurred_at")
    observed = ensure_utc(observed_at, "observed_at")
    ingested = observed if ingested_at is None else ensure_utc(ingested_at, "ingested_at")
    if reference_at is not None:
        reference = ensure_utc(reference_at, "reference_at")
        for field_name, value in (
            ("occurred_at", occurred_at),
            ("observed_at", observed),
            ("ingested_at", ingested),
        ):
            if value > reference:
                raise ValueError(f"{field_name} is in the future of reference_at")
    normalized_chain = chain
    payload_chain = payload.get("chain")
    if normalized_chain is None and isinstance(payload_chain, Chain | str):
        normalized_chain = payload_chain
    event_type = _first_payload_value(payload, "event_type", "kind", "type")
    if event_type is None:
        normalized_type = "unknown"
    elif isinstance(event_type, str):
        normalized_type = require_text(event_type, "event_type", max_length=128)
    else:
        raise TypeError("event_type must be a string")
    author_value = _first_payload_value(payload, "author_id", "user_id", "author")
    if isinstance(author_value, Mapping):
        author_value = _first_payload_value(author_value, "id", "author_id", "user_id")
    author_id = author_value if isinstance(author_value, str) else None
    text_value = _first_payload_value(payload, "text", "content", "title", "body")
    normalized_text = text_value if isinstance(text_value, str) else None
    normalized_provenance = provenance or Provenance(
        provider=normalized_source,
        source_id=event_id,
        observed_at=observed,
        parser_version=require_text(parser_version, "parser_version", max_length=128),
    )
    if normalized_provenance.source_id != event_id:
        raise ValueError("provenance source_id must match event_id")
    event_freshness = freshness or Freshness(
        as_of=observed,
        expires_at=observed + timedelta(minutes=15),
        quality_state=QualityState(quality_state),
    )
    raw_reference = raw_payload_ref
    payload_reference = payload.get("raw_payload_ref")
    if raw_reference is None and isinstance(payload_reference, str):
        raw_reference = payload_reference
    return GlobalEvent(
        source=normalized_source,
        event_id=event_id,
        event_type=normalized_type,
        occurred_at=occurred_at,
        observed_at=observed,
        ingested_at=ingested,
        provenance=normalized_provenance,
        author_id=author_id,
        entities=_payload_texts(
            _first_payload_value(payload, "entities", "entity_ids"),
            "entities",
        ),
        text=normalized_text,
        urls=_payload_texts(
            _first_payload_value(payload, "urls", "links", "canonical_links"),
            "urls",
        ),
        contract_addresses=_payload_addresses(
            _first_payload_value(
                payload,
                "contract_addresses",
                "contracts",
                "mint_addresses",
                "mints",
                "contract_address",
                "mint_address",
            )
        ),
        chain=normalized_chain,
        quality_state=quality_state,
        freshness=event_freshness,
        raw_payload_ref=raw_reference,
        evidence_refs=tuple(evidence_refs),
        reason_codes=tuple(reason_codes),
    )
