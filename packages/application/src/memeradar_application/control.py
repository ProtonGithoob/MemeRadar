"""Provider-independent authorization and operator control contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol, cast
from uuid import UUID, uuid4

from memeradar_domain.common import ensure_utc, freeze_mapping, require_text

from .read_api import AuditEventView, ConfigVersionView

CONTROL_API_VERSION = "control-api-v1"
_CONFIG_VERSION_PREFIX = "control-config-v"
_ZERO_UUID = UUID(int=0)

DEFAULT_CONTROL_CONFIG: Mapping[str, object] = freeze_mapping(
    {
        "alert_max_messages_per_window": 20,
        "alert_rate_limit_window_seconds": 60.0,
        "decision_watch_threshold": 40.0,
        "decision_strong_setup_threshold": 75.0,
        "decision_entry_ready_threshold": 85.0,
        "decision_minimum_confidence": 0.60,
    },
    "default control config",
)

_INTEGER_CONFIG_FIELDS = frozenset({"alert_max_messages_per_window"})
_ALERT_CONFIG_FIELDS = frozenset(
    {"alert_max_messages_per_window", "alert_rate_limit_window_seconds"}
)
_DECISION_CONFIG_FIELDS = frozenset(
    {
        "decision_watch_threshold",
        "decision_strong_setup_threshold",
        "decision_entry_ready_threshold",
        "decision_minimum_confidence",
    }
)
_ALLOWED_CONFIG_FIELDS = _ALERT_CONFIG_FIELDS | _DECISION_CONFIG_FIELDS
_PROTECTED_CONFIG_FIELDS = frozenset(
    {"ANALYSIS_ONLY", "PAPER_TRADING", "MANUAL_EXECUTION", "AUTO_EXECUTION"}
)


def _now() -> datetime:
    return datetime.now(UTC)


class ControlRole(str, Enum):
    """Role represented by a configured control credential."""

    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"
    EXECUTION = "EXECUTION"


class ControlAction(str, Enum):
    """Auditable actions exposed by the control plane."""

    READ_STATE = "control.read_state"
    READ_CONFIG = "control.read_config"
    PAUSE_ANALYSIS = "control.analysis_pause"
    RESUME_ANALYSIS = "control.analysis_resume"
    ACTIVATE_EXECUTION_KILL_SWITCH = "control.execution_kill_switch.activate"
    CLEAR_EXECUTION_KILL_SWITCH = "control.execution_kill_switch.clear"
    MUTATE_CONFIG = "control.config.update"


class ControlAuthorizationError(PermissionError):
    """Raised when a principal lacks the requested control permission."""


class ControlConfigError(ValueError):
    """Raised when a control configuration patch is invalid."""


class ControlSafetyError(RuntimeError):
    """Raised when a requested control action would loosen protected safety."""


@dataclass(frozen=True, slots=True)
class ControlPrincipal:
    """Non-secret identity attached to one authenticated role."""

    subject: str
    role: ControlRole

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", require_text(self.subject, "subject", max_length=256))
        object.__setattr__(self, "role", ControlRole(self.role))


@dataclass(frozen=True, slots=True)
class ControlState:
    """Versioned emergency controls with restrictive defaults."""

    analysis_paused: bool = False
    execution_kill_switch: bool = True
    version: int = 0
    updated_at: datetime = field(default_factory=_now)
    updated_by: str = "system"
    correlation_id: str = "system"

    def __post_init__(self) -> None:
        for field_name in ("analysis_paused", "execution_kill_switch"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 0:
            raise ValueError("version must be a non-negative integer")
        object.__setattr__(self, "updated_at", ensure_utc(self.updated_at, "updated_at"))
        object.__setattr__(
            self,
            "updated_by",
            require_text(self.updated_by, "updated_by", max_length=256),
        )
        object.__setattr__(
            self,
            "correlation_id",
            require_text(self.correlation_id, "correlation_id", max_length=128),
        )


_ROLE_PERMISSIONS: Mapping[ControlRole, frozenset[ControlAction]] = {
    ControlRole.VIEWER: frozenset({ControlAction.READ_STATE, ControlAction.READ_CONFIG}),
    ControlRole.OPERATOR: frozenset(
        {
            ControlAction.READ_STATE,
            ControlAction.READ_CONFIG,
            ControlAction.PAUSE_ANALYSIS,
            ControlAction.RESUME_ANALYSIS,
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH,
        }
    ),
    ControlRole.ADMIN: frozenset(
        {
            ControlAction.READ_STATE,
            ControlAction.READ_CONFIG,
            ControlAction.PAUSE_ANALYSIS,
            ControlAction.RESUME_ANALYSIS,
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH,
            ControlAction.CLEAR_EXECUTION_KILL_SWITCH,
            ControlAction.MUTATE_CONFIG,
        }
    ),
    ControlRole.EXECUTION: frozenset(
        {
            ControlAction.READ_STATE,
            ControlAction.READ_CONFIG,
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH,
        }
    ),
}


def authorize(principal: ControlPrincipal, action: ControlAction) -> None:
    """Fail closed when a principal does not have an explicit permission."""

    if not isinstance(principal, ControlPrincipal):
        raise TypeError("principal must be a ControlPrincipal")
    normalized_action = ControlAction(action)
    if normalized_action not in _ROLE_PERMISSIONS[principal.role]:
        raise ControlAuthorizationError("principal is not authorized for this control action")


def _normalize_reason(reason: str) -> str:
    return require_text(reason, "reason", max_length=512)


def _normalize_correlation_id(correlation_id: str) -> str:
    return require_text(correlation_id, "correlation_id", max_length=128)


def _normalize_config_value(field_name: str, value: object) -> object:
    if field_name not in _ALLOWED_CONFIG_FIELDS:
        if field_name.upper() in _PROTECTED_CONFIG_FIELDS:
            raise ControlConfigError(f"{field_name} is a protected operating mode")
        raise ControlConfigError(f"unknown config field: {field_name}")
    if field_name in _INTEGER_CONFIG_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ControlConfigError(f"{field_name} must be an integer")
        if not 1 <= value <= 1000:
            raise ControlConfigError(f"{field_name} must be between 1 and 1000")
        return value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ControlConfigError(f"{field_name} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ControlConfigError(f"{field_name} must be finite")
    lower, upper = (1.0, 86400.0)
    if field_name in _DECISION_CONFIG_FIELDS:
        lower, upper = (0.0, 1.0) if field_name == "decision_minimum_confidence" else (0.0, 100.0)
    if not lower <= numeric <= upper:
        raise ControlConfigError(f"{field_name} must be between {lower:g} and {upper:g}")
    return numeric


def normalize_config(values: Mapping[str, object]) -> Mapping[str, object]:
    """Validate and normalize a complete control configuration mapping."""

    if not isinstance(values, Mapping):
        raise TypeError("config must be a mapping")
    normalized: dict[str, object] = {}
    for raw_name, value in values.items():
        if not isinstance(raw_name, str):
            raise ControlConfigError("config field names must be strings")
        field_name = require_text(raw_name, "config field", max_length=128)
        normalized[field_name] = _normalize_config_value(field_name, value)
    missing = _ALLOWED_CONFIG_FIELDS.difference(normalized)
    if missing:
        raise ControlConfigError(f"config is missing required fields: {', '.join(sorted(missing))}")
    watch_threshold = cast(float, normalized["decision_watch_threshold"])
    strong_setup_threshold = cast(float, normalized["decision_strong_setup_threshold"])
    entry_ready_threshold = cast(float, normalized["decision_entry_ready_threshold"])
    if not watch_threshold <= strong_setup_threshold <= entry_ready_threshold:
        raise ControlConfigError("decision threshold values must be ordered")
    return freeze_mapping(normalized, "config")


def normalize_config_patch(changes: Mapping[str, object]) -> Mapping[str, object]:
    """Validate a non-empty partial configuration patch."""

    if not isinstance(changes, Mapping):
        raise TypeError("changes must be a mapping")
    if not changes:
        raise ControlConfigError("config changes must not be empty")
    if len(changes) > len(_ALLOWED_CONFIG_FIELDS):
        raise ControlConfigError("config changes contain too many fields")
    normalized: dict[str, object] = {}
    for raw_name, value in changes.items():
        if not isinstance(raw_name, str):
            raise ControlConfigError("config field names must be strings")
        field_name = require_text(raw_name, "config field", max_length=128)
        normalized[field_name] = _normalize_config_value(field_name, value)
    return freeze_mapping(normalized, "config changes")


def apply_config_patch(
    current: Mapping[str, object], changes: Mapping[str, object]
) -> Mapping[str, object]:
    """Apply and validate a partial patch against the current full snapshot."""

    normalized_current = normalize_config(current)
    normalized_changes = normalize_config_patch(changes)
    merged = dict(normalized_current)
    merged.update(normalized_changes)
    return normalize_config(merged)


def canonical_config_hash(values: Mapping[str, object]) -> str:
    """Hash the canonical validated JSON representation of a config snapshot."""

    normalized = normalize_config(values)
    encoded = json.dumps(
        dict(normalized),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def config_is_decision_affecting(changes: Mapping[str, object]) -> bool:
    """Return whether a patch changes deterministic decision inputs."""

    return bool(set(changes).intersection(_DECISION_CONFIG_FIELDS))


def _config_version_number(version: str) -> int:
    if not version.startswith(_CONFIG_VERSION_PREFIX):
        return 0
    try:
        return max(0, int(version.removeprefix(_CONFIG_VERSION_PREFIX)))
    except ValueError:
        return 0


def make_config_version(
    values: Mapping[str, object],
    *,
    version: str,
    actor: str,
    created_at: datetime,
    identifier: UUID | None = None,
    decision_affecting: bool | None = None,
) -> ConfigVersionView:
    """Create a safe, immutable config read model from validated values."""

    normalized = normalize_config(values)
    return ConfigVersionView(
        id=_ZERO_UUID if identifier is None else identifier,
        version=require_text(version, "version", max_length=64),
        created_at=ensure_utc(created_at, "created_at"),
        actor=require_text(actor, "actor", max_length=256),
        config_hash=canonical_config_hash(normalized),
        decision_affecting=(
            bool(decision_affecting)
            if decision_affecting is not None
            else True
        ),
        config=normalized,
    )


def _state_payload(state: ControlState) -> Mapping[str, object]:
    return {
        "analysis_paused": state.analysis_paused,
        "execution_kill_switch": state.execution_kill_switch,
        "version": state.version,
        "updated_at": state.updated_at,
        "updated_by": state.updated_by,
        "correlation_id": state.correlation_id,
    }


def _config_payload(config: ConfigVersionView) -> Mapping[str, object]:
    return {
        "version": config.version,
        "config_hash": config.config_hash,
        "decision_affecting": config.decision_affecting,
        "config": config.config,
    }


def _audit_event(
    *,
    principal: ControlPrincipal,
    action: ControlAction,
    target: str,
    before: Mapping[str, object],
    after: Mapping[str, object],
    occurred_at: datetime,
    correlation_id: str,
) -> AuditEventView:
    return AuditEventView(
        id=uuid4(),
        actor=principal.subject,
        action=action.value,
        target=target,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        before=before,
        after=after,
    )


class ControlPlanePort(Protocol):
    """Application-facing async port implemented by memory or persistence."""

    async def get_state(self) -> ControlState:
        raise NotImplementedError

    async def get_config(self) -> ConfigVersionView:
        raise NotImplementedError

    async def set_analysis_paused(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        raise NotImplementedError

    async def set_execution_kill_switch(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        raise NotImplementedError

    async def mutate_config(
        self,
        principal: ControlPrincipal,
        *,
        changes: Mapping[str, object],
        reason: str,
        correlation_id: str,
    ) -> ConfigVersionView:
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryControlPlane(ControlPlanePort):
    """Deterministic keyless control-plane implementation for tests/replay."""

    initial_config: Mapping[str, object] = field(default_factory=lambda: DEFAULT_CONTROL_CONFIG)
    execution_clear_allowed: bool = False
    clock: Callable[[], datetime] = _now
    _state: ControlState = field(init=False)
    _config: ConfigVersionView = field(init=False)
    _audit_events: list[AuditEventView] = field(init=False, default_factory=list)
    _config_versions: list[ConfigVersionView] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.execution_clear_allowed, bool):
            raise TypeError("execution_clear_allowed must be a boolean")
        now = ensure_utc(self.clock(), "clock timestamp")
        self._state = ControlState(updated_at=now)
        self._config = make_config_version(
            self.initial_config,
            version=_CONFIG_VERSION_PREFIX + "0",
            actor="system",
            created_at=now,
            identifier=_ZERO_UUID,
            decision_affecting=True,
        )

    @property
    def audit_events(self) -> tuple[AuditEventView, ...]:
        return tuple(self._audit_events)

    @property
    def config_versions(self) -> tuple[ConfigVersionView, ...]:
        return tuple(self._config_versions)

    async def get_state(self) -> ControlState:
        return self._state

    async def get_config(self) -> ConfigVersionView:
        return self._config

    async def set_analysis_paused(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        _normalize_reason(reason)
        normalized_correlation = _normalize_correlation_id(correlation_id)
        if not isinstance(active, bool):
            raise TypeError("active must be a boolean")
        action = ControlAction.PAUSE_ANALYSIS if active else ControlAction.RESUME_ANALYSIS
        authorize(principal, action)
        current = self._state
        if current.analysis_paused is active:
            return current
        now = ensure_utc(self.clock(), "clock timestamp")
        updated = ControlState(
            analysis_paused=active,
            execution_kill_switch=current.execution_kill_switch,
            version=current.version + 1,
            updated_at=now,
            updated_by=principal.subject,
            correlation_id=normalized_correlation,
        )
        self._state = updated
        self._audit_events.append(
            _audit_event(
                principal=principal,
                action=action,
                target="analysis",
                before=_state_payload(current),
                after=_state_payload(updated),
                occurred_at=now,
                correlation_id=normalized_correlation,
            )
        )
        return updated

    async def set_execution_kill_switch(
        self,
        principal: ControlPrincipal,
        *,
        active: bool,
        reason: str,
        correlation_id: str,
    ) -> ControlState:
        _normalize_reason(reason)
        normalized_correlation = _normalize_correlation_id(correlation_id)
        if not isinstance(active, bool):
            raise TypeError("active must be a boolean")
        action = (
            ControlAction.ACTIVATE_EXECUTION_KILL_SWITCH
            if active
            else ControlAction.CLEAR_EXECUTION_KILL_SWITCH
        )
        authorize(principal, action)
        if not active and not self.execution_clear_allowed:
            raise ControlSafetyError(
                "execution kill switch cannot be cleared in protected operating modes"
            )
        current = self._state
        if current.execution_kill_switch is active:
            return current
        now = ensure_utc(self.clock(), "clock timestamp")
        updated = ControlState(
            analysis_paused=current.analysis_paused,
            execution_kill_switch=active,
            version=current.version + 1,
            updated_at=now,
            updated_by=principal.subject,
            correlation_id=normalized_correlation,
        )
        self._state = updated
        self._audit_events.append(
            _audit_event(
                principal=principal,
                action=action,
                target="execution",
                before=_state_payload(current),
                after=_state_payload(updated),
                occurred_at=now,
                correlation_id=normalized_correlation,
            )
        )
        return updated

    async def mutate_config(
        self,
        principal: ControlPrincipal,
        *,
        changes: Mapping[str, object],
        reason: str,
        correlation_id: str,
    ) -> ConfigVersionView:
        _normalize_reason(reason)
        normalized_correlation = _normalize_correlation_id(correlation_id)
        authorize(principal, ControlAction.MUTATE_CONFIG)
        current_config = self._config
        updated_values = apply_config_patch(current_config.config, changes)
        if updated_values == current_config.config:
            return current_config
        now = ensure_utc(self.clock(), "clock timestamp")
        updated = make_config_version(
            updated_values,
            version=_CONFIG_VERSION_PREFIX + str(_config_version_number(self._config.version) + 1),
            actor=principal.subject,
            created_at=now,
            identifier=uuid4(),
            decision_affecting=config_is_decision_affecting(changes),
        )
        self._config = updated
        self._config_versions.append(updated)
        self._audit_events.append(
            _audit_event(
                principal=principal,
                action=ControlAction.MUTATE_CONFIG,
                target="runtime-config",
                before=_config_payload(current_config),
                after=_config_payload(updated),
                occurred_at=now,
                correlation_id=normalized_correlation,
            )
        )
        return updated


__all__ = [
    "CONTROL_API_VERSION",
    "DEFAULT_CONTROL_CONFIG",
    "ControlAction",
    "ControlAuthorizationError",
    "ControlConfigError",
    "ControlPlanePort",
    "ControlPrincipal",
    "ControlRole",
    "ControlSafetyError",
    "ControlState",
    "InMemoryControlPlane",
    "apply_config_patch",
    "authorize",
    "canonical_config_hash",
    "config_is_decision_affecting",
    "make_config_version",
    "normalize_config",
    "normalize_config_patch",
]
