"""Normalized observations, provenance and evidence freshness value objects."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from .common import ensure_ordered_timestamps, ensure_utc, require_text


class QualityState(str, Enum):
    """Quality states that must remain distinct in decision logic."""

    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"


class PriceSemantics(str, Enum):
    """The economic meaning of a normalized price observation.

    Execution/effective prices are used for fills, cost basis and PnL.  Market
    references are independent marks used for analytical price series and
    market-cap movement.  A quote is intentionally distinct from both: it is
    an execution input, not proof of the market mark.
    """

    EXECUTION_EFFECTIVE = "EXECUTION_EFFECTIVE"
    EXECUTION_QUOTE = "EXECUTION_QUOTE"
    MARKET_REFERENCE = "MARKET_REFERENCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Freshness:
    """Validity window for evidence or a derived snapshot."""

    as_of: datetime
    expires_at: datetime
    quality_state: QualityState = QualityState.FRESH

    def __post_init__(self) -> None:
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))

    def state_at(self, at: datetime) -> QualityState:
        """Resolve freshness at a point in time, preserving non-fresh states."""

        checked_at = ensure_utc(at, "at")
        if self.quality_state is not QualityState.FRESH:
            return self.quality_state
        if checked_at < self.as_of or checked_at >= self.expires_at:
            return QualityState.STALE
        return QualityState.FRESH

    def is_fresh(self, at: datetime) -> bool:
        """Return true only for evidence inside its window and marked fresh."""

        return self.state_at(at) is QualityState.FRESH


@dataclass(frozen=True, slots=True)
class Provenance:
    """Source and parser metadata retained beside normalized evidence."""

    provider: str
    source_id: str
    observed_at: datetime
    parser_version: str
    raw_payload_hash: str | None = None
    raw_payload_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", require_text(self.provider, "provider"))
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(
            self,
            "parser_version",
            require_text(self.parser_version, "parser_version"),
        )
        if self.raw_payload_hash is not None:
            object.__setattr__(
                self,
                "raw_payload_hash",
                require_text(self.raw_payload_hash, "raw_payload_hash"),
            )
        if self.raw_payload_ref is not None:
            object.__setattr__(
                self,
                "raw_payload_ref",
                require_text(self.raw_payload_ref, "raw_payload_ref"),
            )


@dataclass(frozen=True, slots=True)
class Observation:
    """Append-oriented normalized provider observation."""

    kind: str
    provenance: Provenance
    occurred_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    quality_state: QualityState
    normalized_payload: Mapping[str, object]
    id: UUID = field(default_factory=uuid4)
    candidate_id: UUID | None = None
    token_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        assert occurred is not None or self.occurred_at is None
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        if self.provenance.observed_at > observed:
            raise ValueError(
                "provenance observed_at must not be later than observation observed_at"
            )
        object.__setattr__(self, "kind", require_text(self.kind, "kind"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "normalized_payload", dict(self.normalized_payload))


def default_freshness(as_of: datetime, ttl: timedelta) -> Freshness:
    """Create a fresh window while keeping timestamp policy in one place."""

    if ttl <= timedelta(0):
        raise ValueError("ttl must be positive")
    normalized_as_of = ensure_utc(as_of, "as_of")
    return Freshness(as_of=normalized_as_of, expires_at=normalized_as_of + ttl)
