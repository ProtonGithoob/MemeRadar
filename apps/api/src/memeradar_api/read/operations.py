"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from memeradar_application.config import Settings
from memeradar_application.provider_contracts import ProviderCapabilityStatus
from memeradar_application.provider_metadata import provider_metadata_for_settings
from memeradar_application.read_common import DEFAULT_PAGE_LIMIT, MAX_CURSOR_LENGTH, MAX_PAGE_LIMIT
from memeradar_application.read_operations import (
    AuditEventView,
    ConfigVersionView,
    ProviderHealthView,
    ReadProviderHealthState,
)
from memeradar_domain import QualityState

from .common import _mapping, _StrictModel

_SEARCH_KINDS = Literal["TOKEN", "WALLET", "CALLER", "AMBIGUOUS", "NOT_FOUND"]


class ProviderHealthQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    provider: str | None = Field(default=None, min_length=1, max_length=128)
    capability: str | None = Field(default=None, min_length=1, max_length=128)
    state: Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"] | None = None


class AuditQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    actor: str | None = Field(default=None, min_length=1, max_length=256)
    action: str | None = Field(default=None, min_length=1, max_length=256)
    target: str | None = Field(default=None, min_length=1, max_length=256)
    from_at: datetime | None = None
    to_at: datetime | None = None


class ConfigQueryParams(_StrictModel):
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    decision_affecting: bool | None = None


class ProviderHealthResponse(_StrictModel):
    provider: str
    provider_id: str
    display_name: str
    chains: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    required: bool
    enabled: bool
    configured: bool
    setting_keys: list[str] = Field(default_factory=list)
    credential_state: str
    endpoint_state: str
    fallback_position: int | None = None
    runtime_health: str
    capability: str
    state: str
    checked_at: datetime
    latency_ms: float | None = None
    quota: dict[str, object] = Field(default_factory=dict)
    freshness_state: QualityState | None = None
    error_class: str | None = None
    consecutive_failures: int
    capability_status: str


class SearchResolveResponse(_StrictModel):
    kind: _SEARCH_KINDS
    query: str
    chain: str | None = None
    identifier: str | None = None
    route: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


class AuditEventResponse(_StrictModel):
    id: UUID
    actor: str
    action: str
    target: str
    occurred_at: datetime
    correlation_id: str
    before: dict[str, object] = Field(default_factory=dict)
    after: dict[str, object] = Field(default_factory=dict)


class ConfigVersionResponse(_StrictModel):
    id: UUID
    version: str
    created_at: datetime
    actor: str
    config_hash: str
    decision_affecting: bool
    config: dict[str, object] = Field(default_factory=dict)


def _provider_health_response(
    value: ProviderHealthView,
    settings: Settings | None = None,
) -> ProviderHealthResponse:
    assert value.capability_status is not None
    metadata = provider_metadata_for_settings(value.provider, value.capability, settings)
    capability_status = (
        value.capability_status.value
        if isinstance(value.capability_status, ProviderCapabilityStatus)
        else value.capability_status
    )
    runtime_state = ReadProviderHealthState(value.state)
    enabled = metadata.enabled
    credential_state = metadata.credential_state
    endpoint_state = metadata.endpoint_state
    configured = enabled and credential_state == "CONFIGURED" and endpoint_state == "CONFIGURED"
    if settings is not None and value.provider in {"madeonsol-robinhood", "gmgn"}:
        if not enabled:
            runtime_state = ReadProviderHealthState.UNKNOWN
            capability_status = ProviderCapabilityStatus.UNSUPPORTED.value
        elif not configured:
            runtime_state = ReadProviderHealthState.UNKNOWN
            capability_status = ProviderCapabilityStatus.CONFIGURATION_MISSING.value
    return ProviderHealthResponse(
        provider=value.provider,
        provider_id=metadata.provider_id,
        display_name=metadata.display_name,
        chains=list(metadata.chains),
        capabilities=list(metadata.capabilities),
        required=metadata.required,
        enabled=enabled,
        configured=configured,
        setting_keys=list(metadata.setting_keys),
        credential_state=credential_state,
        endpoint_state=endpoint_state,
        fallback_position=metadata.fallback_position,
        runtime_health=runtime_state.value,
        capability=value.capability,
        state=runtime_state.value,
        checked_at=value.checked_at,
        latency_ms=value.latency_ms,
        quota=_mapping(value.quota),
        freshness_state=(
            None if value.freshness_state is None else QualityState(value.freshness_state)
        ),
        error_class=value.error_class,
        consecutive_failures=value.consecutive_failures,
        capability_status=capability_status,
    )


def _audit_response(value: AuditEventView) -> AuditEventResponse:
    return AuditEventResponse(
        id=value.id,
        actor=value.actor,
        action=value.action,
        target=value.target,
        occurred_at=value.occurred_at,
        correlation_id=value.correlation_id,
        before=_mapping(value.before),
        after=_mapping(value.after),
    )


def _config_response(value: ConfigVersionView) -> ConfigVersionResponse:
    return ConfigVersionResponse(
        id=value.id,
        version=value.version,
        created_at=value.created_at,
        actor=value.actor,
        config_hash=value.config_hash,
        decision_affecting=value.decision_affecting,
        config=_mapping(value.config),
    )
