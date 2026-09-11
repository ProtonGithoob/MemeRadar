"""Read-only operations observability API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from memeradar_application.control import ControlAction
from memeradar_application.observability import (
    OperationalAlert,
    OperationsOverview,
    OperationsReadPort,
    ProviderOperationalStatus,
)
from memeradar_application.provider_metadata import provider_metadata
from memeradar_domain import AlertSeverity, QualityState

from .auth import RoleTokenAuthenticator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderOperationalResponse(_StrictModel):
    provider: str
    provider_id: str
    display_name: str
    chains: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    required: bool
    enabled: bool
    setting_keys: list[str] = Field(default_factory=list)
    credential_state: str
    endpoint_state: str
    fallback_position: int | None = None
    runtime_health: str
    capability: str
    state: str
    slo_state: str
    checked_at: datetime
    latency_ms: float | None = None
    freshness_state: QualityState | None = None
    quota_limit: int | None = None
    quota_remaining: int | None = None
    quota_reset_at: datetime | None = None
    cost_today_usd: float | None = None
    cost_budget_usd: float | None = None
    error_class: str | None = None
    consecutive_failures: int
    reason_codes: list[str] = Field(default_factory=list)


class OperationalAlertResponse(_StrictModel):
    code: str
    severity: AlertSeverity
    dedupe_key: str
    provider: str | None = None
    capability: str | None = None
    message: str
    observed_at: datetime
    reason_codes: list[str] = Field(default_factory=list)


class OperationsOverviewResponse(_StrictModel):
    schema_version: str
    as_of: datetime
    overall_state: str
    slo_state: str
    policy_version: str
    measurement_method: str
    providers: list[ProviderOperationalResponse] = Field(default_factory=list)
    alerts: list[OperationalAlertResponse] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)
    early_detection: dict[str, object] = Field(default_factory=dict)
    modes: dict[str, bool]
    execution_eligible: bool = False


def _provider_response(value: ProviderOperationalStatus) -> ProviderOperationalResponse:
    metadata = provider_metadata(value.provider, value.capability)
    return ProviderOperationalResponse(
        provider=value.provider,
        provider_id=metadata.provider_id,
        display_name=metadata.display_name,
        chains=list(metadata.chains),
        capabilities=list(metadata.capabilities),
        required=metadata.required,
        enabled=metadata.enabled,
        setting_keys=list(metadata.setting_keys),
        credential_state=metadata.credential_state,
        endpoint_state=metadata.endpoint_state,
        fallback_position=metadata.fallback_position,
        runtime_health=value.state.value,
        capability=value.capability,
        state=value.state.value,
        slo_state=value.slo_state.value,
        checked_at=value.checked_at,
        latency_ms=value.latency_ms,
        freshness_state=value.freshness_state,
        quota_limit=value.quota_limit,
        quota_remaining=value.quota_remaining,
        quota_reset_at=value.quota_reset_at,
        cost_today_usd=value.cost_today_usd,
        cost_budget_usd=value.cost_budget_usd,
        error_class=value.error_class,
        consecutive_failures=value.consecutive_failures,
        reason_codes=list(value.reason_codes),
    )


def _alert_response(value: OperationalAlert) -> OperationalAlertResponse:
    return OperationalAlertResponse(
        code=value.code.value,
        severity=value.severity,
        dedupe_key=value.dedupe_key,
        provider=value.provider,
        capability=value.capability,
        message=value.message,
        observed_at=value.observed_at,
        reason_codes=list(value.reason_codes),
    )


def _overview_response(value: OperationsOverview) -> OperationsOverviewResponse:
    if value.execution_eligible:
        raise ValueError("operations overview cannot authorize execution")
    serialized = value.to_dict()
    metrics = serialized["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError("operations metrics must serialize to a mapping")
    early_detection = serialized["early_detection"]
    if not isinstance(early_detection, dict):
        raise ValueError("early detection metrics must serialize to a mapping")
    return OperationsOverviewResponse(
        schema_version=value.schema_version,
        as_of=value.as_of,
        overall_state=value.overall_state.value,
        slo_state=value.slo_state.value,
        policy_version=value.policy_version,
        measurement_method=value.measurement_method,
        providers=[_provider_response(item) for item in value.providers],
        alerts=[_alert_response(item) for item in value.alerts],
        metrics=metrics,
        early_detection=early_detection,
        modes=dict(value.modes),
        execution_eligible=False,
    )


def build_operations_router(
    service: OperationsReadPort | None,
    authenticator: RoleTokenAuthenticator | None = None,
) -> APIRouter:
    """Build a single bounded operations read route over an application port."""

    dependencies = []
    if authenticator is not None and authenticator.configured:

        async def require_read_auth(
            authorization: Annotated[str | None, Header()] = None,
        ) -> None:
            authenticator.require(authorization, ControlAction.READ_STATE)

        dependencies.append(Depends(require_read_auth))
    router = APIRouter(prefix="/v1", tags=["operations"], dependencies=dependencies)

    @router.get("/operations/overview", response_model=OperationsOverviewResponse)
    async def get_operations_overview() -> OperationsOverviewResponse:
        if service is None:
            raise RuntimeError("operations read service is not configured")
        return _overview_response(await service.get_operations_overview())

    return router


__all__ = [
    "OperationalAlertResponse",
    "OperationsOverviewResponse",
    "ProviderOperationalResponse",
    "build_operations_router",
]
