"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from memeradar_domain import QualityState
from memeradar_domain.common import ensure_utc, require_text

from .provider_contracts import ProviderCapabilityStatus, provider_capability_status
from .read_common import (
    _ERROR_CLASS,
    DEFAULT_PAGE_LIMIT,
    _bounded_limit,
    _optional_cursor,
    _optional_quality,
    _optional_text,
    _time_range,
    safe_read_payload,
)


@dataclass(frozen=True, slots=True)
class ProviderHealthQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    provider: str | None = None
    capability: str | None = None
    state: ReadProviderHealthState | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        object.__setattr__(self, "provider", _optional_text(self.provider, "provider"))
        object.__setattr__(self, "capability", _optional_text(self.capability, "capability"))
        if self.state is not None:
            object.__setattr__(self, "state", ReadProviderHealthState(self.state))


@dataclass(frozen=True, slots=True)
class AuditQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    actor: str | None = None
    action: str | None = None
    target: str | None = None
    from_at: datetime | None = None
    to_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        for field_name in ("actor", "action", "target"):
            object.__setattr__(
                self,
                field_name,
                _optional_text(getattr(self, field_name), field_name),
            )
        from_at, to_at = _time_range(self.from_at, self.to_at)
        object.__setattr__(self, "from_at", from_at)
        object.__setattr__(self, "to_at", to_at)


@dataclass(frozen=True, slots=True)
class ConfigQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    decision_affecting: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.decision_affecting is not None and not isinstance(self.decision_affecting, bool):
            raise TypeError("decision_affecting must be a boolean or None")


class ReadProviderHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderHealthView:
    provider: str
    capability: str
    state: ReadProviderHealthState | str
    checked_at: datetime
    latency_ms: float | None = None
    quota: Mapping[str, object] = field(default_factory=dict)
    freshness_state: QualityState | str | None = None
    error_class: str | None = None
    consecutive_failures: int = 0
    capability_status: ProviderCapabilityStatus | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", require_text(self.provider, "provider", max_length=128)
        )
        object.__setattr__(
            self, "capability", require_text(self.capability, "capability", max_length=128)
        )
        normalized_state = ReadProviderHealthState(self.state)
        object.__setattr__(self, "state", normalized_state)
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, int | float)
            or not math.isfinite(float(self.latency_ms))
            or not 0 <= float(self.latency_ms) <= 300_000
        ):
            raise ValueError("latency_ms must be between 0 and 300000")
        object.__setattr__(self, "quota", safe_read_payload(self.quota))
        normalized_freshness = _optional_quality(self.freshness_state)
        object.__setattr__(self, "freshness_state", normalized_freshness)
        if self.error_class is not None:
            normalized_error = require_text(self.error_class, "error_class", max_length=128)
            if _ERROR_CLASS.fullmatch(normalized_error) is None:
                raise ValueError("error_class must be a safe class name")
            object.__setattr__(self, "error_class", normalized_error)
        normalized_capability_status = (
            provider_capability_status(
                normalized_state.value,
                reason=self.error_class,
                freshness_state=(
                    None if normalized_freshness is None else normalized_freshness.value
                ),
            )
            if self.capability_status is None
            else ProviderCapabilityStatus(self.capability_status)
        )
        object.__setattr__(self, "capability_status", normalized_capability_status)
        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("consecutive_failures must be non-negative")


@dataclass(frozen=True, slots=True)
class AuditEventView:
    id: UUID
    actor: str
    action: str
    target: str
    occurred_at: datetime
    correlation_id: str
    before: Mapping[str, object] = field(default_factory=dict)
    after: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("audit event id must be a UUID")
        for field_name in ("actor", "action", "target", "correlation_id"):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=256),
            )
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "before", safe_read_payload(self.before))
        object.__setattr__(self, "after", safe_read_payload(self.after))


@dataclass(frozen=True, slots=True)
class ConfigVersionView:
    id: UUID
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("config version id must be a UUID")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        object.__setattr__(self, "created_at", ensure_utc(self.created_at, "created_at"))
        object.__setattr__(self, "actor", require_text(self.actor, "actor", max_length=256))
        object.__setattr__(
            self, "config_hash", require_text(self.config_hash, "config_hash", max_length=128)
        )
        if not isinstance(self.decision_affecting, bool):
            raise TypeError("decision_affecting must be a boolean")
        object.__setattr__(self, "config", safe_read_payload(self.config))
