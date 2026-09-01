"""Provider-independent operational projections for the operator console.

This module consumes normalized provider-health inputs and the bounded
Phase-11.1 reliability snapshot.  It deliberately does not know about
provider SDKs, persistence, HTTP or frontend code.  Operational health is
evidence quality only: it is never an AlphaScore feature and can never grant
execution authority.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import Protocol, cast

from memeradar_domain import AlertSeverity, QualityState
from memeradar_domain.common import ensure_utc, freeze_mapping, normalize_texts, require_text

from .early_observability import EarlyDetectionSnapshot
from .reliability import LatencyMetric, ReliabilityMetrics, ReliabilitySnapshot


class OperationalState(str, Enum):
    """Fail-closed state for one provider or the aggregate operation."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class OperationalSloState(str, Enum):
    """Whether the versioned SLO target has enough trustworthy evidence."""

    UNVERIFIED = "UNVERIFIED"
    MEASURED = "MEASURED"
    VIOLATED = "VIOLATED"


class OperationalAlertCode(str, Enum):
    """Allow-listed operator alert reasons."""

    PROVIDER_UNKNOWN = "PROVIDER_UNKNOWN"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    PROVIDER_QUOTA_LOW = "PROVIDER_QUOTA_LOW"
    PROVIDER_QUOTA_EXHAUSTED = "PROVIDER_QUOTA_EXHAUSTED"
    PROVIDER_COST_BUDGET = "PROVIDER_COST_BUDGET"
    LATENCY_SLO_VIOLATED = "LATENCY_SLO_VIOLATED"
    STREAM_GAP_OPEN = "STREAM_GAP_OPEN"
    STREAM_RECOVERY_FAILED = "STREAM_RECOVERY_FAILED"
    QUEUE_BACKPRESSURE = "QUEUE_BACKPRESSURE"
    OUTBOX_DEAD_LETTERS = "OUTBOX_DEAD_LETTERS"


_ERROR_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
_MODES = {
    "analysis_only": True,
    "paper_trading": True,
    "manual_execution": False,
    "auto_execution": False,
}


def _identity(value: str, field_name: str) -> str:
    return require_text(value, field_name, max_length=128)


def _optional_latency(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("latency_ms must be numeric or None")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 <= normalized <= 300_000:
        raise ValueError("latency_ms must be finite and between 0 and 300000")
    return normalized


def _optional_quota(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


def _optional_cost(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{field_name} must be numeric or None")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 <= normalized <= 1_000_000_000:
        raise ValueError(f"{field_name} must be finite and between 0 and 1000000000")
    return round(normalized, 6)


def _safe_error_class(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = require_text(value, "error_class", max_length=128)
    if _ERROR_CLASS.fullmatch(normalized) is None:
        raise ValueError("error_class must be a safe class name")
    return normalized


def _safe_nested(value: object, *, depth: int = 0) -> object:
    """Copy a bounded JSON-shaped metrics payload without introducing secrets."""

    if depth > 4:
        return "[TRUNCATED]"
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[INVALID]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in list(value.items())[:128]:
            normalized_key = require_text(str(key), "metrics key", max_length=128)
            result[normalized_key] = _safe_nested(item, depth=depth + 1)
        return result
    if isinstance(value, list | tuple):
        return [_safe_nested(item, depth=depth + 1) for item in value[:128]]
    return require_text(str(value), "metrics value", max_length=256)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", "_", value.lower()).strip("_")
    return normalized[:64] or "unknown"


@dataclass(frozen=True, slots=True)
class ProviderOperationalInput:
    """Normalized provider-health record accepted by the operations projector."""

    provider: str
    capability: str
    state: OperationalState | str
    checked_at: datetime
    latency_ms: float | None = None
    freshness_state: QualityState | str | None = None
    quota_limit: int | None = None
    quota_remaining: int | None = None
    quota_reset_at: datetime | None = None
    cost_today_usd: float | None = None
    cost_budget_usd: float | None = None
    error_class: str | None = None
    consecutive_failures: int = 0
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _identity(self.provider, "provider"))
        object.__setattr__(self, "capability", _identity(self.capability, "capability"))
        object.__setattr__(self, "state", OperationalState(self.state))
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        object.__setattr__(self, "latency_ms", _optional_latency(self.latency_ms))
        if self.freshness_state is not None:
            object.__setattr__(self, "freshness_state", QualityState(self.freshness_state))
        object.__setattr__(self, "quota_limit", _optional_quota(self.quota_limit, "quota_limit"))
        object.__setattr__(
            self,
            "quota_remaining",
            _optional_quota(self.quota_remaining, "quota_remaining"),
        )
        if (
            self.quota_limit is not None
            and self.quota_remaining is not None
            and self.quota_remaining > self.quota_limit
        ):
            raise ValueError("quota_remaining must not exceed quota_limit")
        if self.quota_reset_at is not None:
            object.__setattr__(
                self,
                "quota_reset_at",
                ensure_utc(self.quota_reset_at, "quota_reset_at"),
            )
        object.__setattr__(
            self,
            "cost_today_usd",
            _optional_cost(self.cost_today_usd, "cost_today_usd"),
        )
        object.__setattr__(
            self,
            "cost_budget_usd",
            _optional_cost(self.cost_budget_usd, "cost_budget_usd"),
        )
        if (
            self.cost_today_usd is not None
            and self.cost_budget_usd is not None
            and self.cost_today_usd > self.cost_budget_usd
        ):
            raise ValueError("cost_today_usd must not exceed cost_budget_usd")
        object.__setattr__(self, "error_class", _safe_error_class(self.error_class))
        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("consecutive_failures must be a non-negative integer")
        object.__setattr__(
            self,
            "reason_codes",
            normalize_texts(self.reason_codes, "reason_codes"),
        )


@dataclass(frozen=True, slots=True)
class ProviderSloPolicy:
    """Versioned operational targets whose acceptance requires runtime evidence."""

    version: str = "provider-slo-v1"
    latency_p95_budget_ms: float = 1_000.0
    low_quota_fraction: float = 0.10
    min_measurement_samples: int = 100
    require_provider_network: bool = True

    def __post_init__(self) -> None:
        normalized_version = require_text(self.version, "policy version", max_length=64).lower()
        if _SAFE_ID.fullmatch(normalized_version) is None:
            raise ValueError("policy version must be a safe identifier")
        object.__setattr__(self, "version", normalized_version)
        if (
            isinstance(self.latency_p95_budget_ms, bool)
            or not isinstance(self.latency_p95_budget_ms, int | float)
            or not math.isfinite(float(self.latency_p95_budget_ms))
            or not 0 <= float(self.latency_p95_budget_ms) <= 300_000
        ):
            raise ValueError("latency_p95_budget_ms must be between 0 and 300000")
        object.__setattr__(self, "latency_p95_budget_ms", float(self.latency_p95_budget_ms))
        if (
            isinstance(self.low_quota_fraction, bool)
            or not isinstance(self.low_quota_fraction, int | float)
            or not math.isfinite(float(self.low_quota_fraction))
            or not 0 <= float(self.low_quota_fraction) <= 1
        ):
            raise ValueError("low_quota_fraction must be between 0 and 1")
        object.__setattr__(self, "low_quota_fraction", float(self.low_quota_fraction))
        if (
            isinstance(self.min_measurement_samples, bool)
            or not isinstance(self.min_measurement_samples, int)
            or not 1 <= self.min_measurement_samples <= 1_000_000
        ):
            raise ValueError("min_measurement_samples must be between 1 and 1000000")
        if not isinstance(self.require_provider_network, bool):
            raise TypeError("require_provider_network must be a boolean")

    def evaluate(self, reliability: ReliabilitySnapshot) -> OperationalSloState:
        """Evaluate only non-synthetic provider-request samples."""

        if not isinstance(reliability, ReliabilitySnapshot):
            raise TypeError("reliability must be a ReliabilitySnapshot")
        if reliability.measurement_method in {"synthetic_local", "fixture", "keyless"}:
            return OperationalSloState.UNVERIFIED
        summary = reliability.latencies.get(LatencyMetric.PROVIDER_REQUEST.value, {}).get("all")
        if not isinstance(summary, Mapping):
            return OperationalSloState.UNVERIFIED
        count = summary.get("count")
        p95 = summary.get("p95_ms")
        if not isinstance(count, int) or count < self.min_measurement_samples:
            return OperationalSloState.UNVERIFIED
        if self.require_provider_network:
            network = reliability.latency_source_totals.get(
                LatencyMetric.PROVIDER_REQUEST.value,
                {},
            ).get("provider_network")
            if (
                not isinstance(network, Mapping)
                or network.get("count", 0) < self.min_measurement_samples
            ):
                return OperationalSloState.UNVERIFIED
        if not isinstance(p95, int | float) or not math.isfinite(float(p95)):
            return OperationalSloState.UNVERIFIED
        return (
            OperationalSloState.VIOLATED
            if float(p95) > self.latency_p95_budget_ms
            else OperationalSloState.MEASURED
        )


@dataclass(frozen=True, slots=True)
class ProviderOperationalStatus:
    """Safe provider status displayed in the operations projection."""

    provider: str
    capability: str
    state: OperationalState
    slo_state: OperationalSloState
    checked_at: datetime
    latency_ms: float | None
    freshness_state: QualityState | None
    quota_limit: int | None
    quota_remaining: int | None
    quota_reset_at: datetime | None
    cost_today_usd: float | None
    cost_budget_usd: float | None
    error_class: str | None
    consecutive_failures: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _identity(self.provider, "provider"))
        object.__setattr__(self, "capability", _identity(self.capability, "capability"))
        object.__setattr__(self, "state", OperationalState(self.state))
        object.__setattr__(self, "slo_state", OperationalSloState(self.slo_state))
        object.__setattr__(self, "checked_at", ensure_utc(self.checked_at, "checked_at"))
        object.__setattr__(self, "latency_ms", _optional_latency(self.latency_ms))
        if self.freshness_state is not None:
            object.__setattr__(self, "freshness_state", QualityState(self.freshness_state))
        object.__setattr__(self, "quota_limit", _optional_quota(self.quota_limit, "quota_limit"))
        object.__setattr__(
            self,
            "quota_remaining",
            _optional_quota(self.quota_remaining, "quota_remaining"),
        )
        if self.quota_reset_at is not None:
            object.__setattr__(
                self,
                "quota_reset_at",
                ensure_utc(self.quota_reset_at, "quota_reset_at"),
            )
        object.__setattr__(
            self,
            "cost_today_usd",
            _optional_cost(self.cost_today_usd, "cost_today_usd"),
        )
        object.__setattr__(
            self,
            "cost_budget_usd",
            _optional_cost(self.cost_budget_usd, "cost_budget_usd"),
        )
        if (
            self.cost_today_usd is not None
            and self.cost_budget_usd is not None
            and self.cost_today_usd > self.cost_budget_usd
        ):
            raise ValueError("cost_today_usd must not exceed cost_budget_usd")
        object.__setattr__(self, "error_class", _safe_error_class(self.error_class))
        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("consecutive_failures must be a non-negative integer")
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "capability": self.capability,
            "state": self.state.value,
            "slo_state": self.slo_state.value,
            "checked_at": self.checked_at.isoformat(),
            "latency_ms": self.latency_ms,
            "freshness_state": None if self.freshness_state is None else self.freshness_state.value,
            "quota_limit": self.quota_limit,
            "quota_remaining": self.quota_remaining,
            "quota_reset_at": (
                None if self.quota_reset_at is None else self.quota_reset_at.isoformat()
            ),
            "cost_today_usd": self.cost_today_usd,
            "cost_budget_usd": self.cost_budget_usd,
            "error_class": self.error_class,
            "consecutive_failures": self.consecutive_failures,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class OperationalAlert:
    """Deduplicable operator alert with static, bounded and safe content."""

    code: OperationalAlertCode
    severity: AlertSeverity
    dedupe_key: str
    message: str
    observed_at: datetime
    provider: str | None = None
    capability: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", OperationalAlertCode(self.code))
        object.__setattr__(self, "severity", AlertSeverity(self.severity))
        object.__setattr__(
            self,
            "dedupe_key",
            require_text(self.dedupe_key, "dedupe_key", max_length=256),
        )
        object.__setattr__(self, "message", require_text(self.message, "message", max_length=256))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        if self.provider is not None:
            object.__setattr__(self, "provider", _identity(self.provider, "provider"))
        if self.capability is not None:
            object.__setattr__(self, "capability", _identity(self.capability, "capability"))
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "dedupe_key": self.dedupe_key,
            "provider": self.provider,
            "capability": self.capability,
            "message": self.message,
            "observed_at": self.observed_at.isoformat(),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class OperationsOverview:
    """Immutable, JSON-safe dashboard projection."""

    as_of: datetime
    overall_state: OperationalState
    slo_state: OperationalSloState
    policy_version: str
    measurement_method: str
    providers: tuple[ProviderOperationalStatus, ...]
    alerts: tuple[OperationalAlert, ...]
    metrics: Mapping[str, object]
    early_detection: Mapping[str, object] | EarlyDetectionSnapshot = field(default_factory=dict)
    modes: Mapping[str, bool] = field(default_factory=lambda: dict(_MODES))
    execution_eligible: bool = False
    schema_version: str = "operations-overview-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "overall_state", OperationalState(self.overall_state))
        object.__setattr__(self, "slo_state", OperationalSloState(self.slo_state))
        object.__setattr__(
            self,
            "policy_version",
            require_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "measurement_method",
            require_text(self.measurement_method, "measurement_method"),
        )
        object.__setattr__(self, "providers", tuple(self.providers))
        object.__setattr__(self, "alerts", tuple(self.alerts))
        safe_metrics = _safe_nested(self.metrics)
        if not isinstance(safe_metrics, Mapping):
            raise TypeError("metrics must be a mapping")
        object.__setattr__(
            self,
            "metrics",
            freeze_mapping(cast(Mapping[str, object], safe_metrics), "metrics"),
        )
        early_detection = self.early_detection
        if isinstance(early_detection, EarlyDetectionSnapshot):
            early_detection = early_detection.to_dict()
        safe_early_detection = _safe_nested(early_detection)
        if not isinstance(safe_early_detection, Mapping):
            raise TypeError("early_detection must be a mapping")
        object.__setattr__(
            self,
            "early_detection",
            freeze_mapping(
                cast(Mapping[str, object], safe_early_detection),
                "early_detection",
            ),
        )
        normalized_modes = dict(self.modes)
        if normalized_modes != _MODES:
            raise ValueError("operations projection modes must remain protected")
        object.__setattr__(self, "modes", freeze_mapping(normalized_modes, "modes"))
        if self.execution_eligible is not False:
            raise ValueError("operations projection cannot authorize execution")
        if self.schema_version != "operations-overview-v1":
            raise ValueError("unsupported operations schema version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "as_of": self.as_of.isoformat(),
            "overall_state": self.overall_state.value,
            "slo_state": self.slo_state.value,
            "policy_version": self.policy_version,
            "measurement_method": self.measurement_method,
            "providers": [provider.to_dict() for provider in self.providers],
            "alerts": [alert.to_dict() for alert in self.alerts],
            "metrics": _safe_nested(self.metrics),
            "early_detection": _safe_nested(self.early_detection),
            "modes": dict(self.modes),
            "execution_eligible": False,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return f"sha256:{sha256(self.to_json().encode("utf-8")).hexdigest()}"


def _alert(
    code: OperationalAlertCode,
    severity: AlertSeverity,
    *,
    as_of: datetime,
    provider: str | None = None,
    capability: str | None = None,
    reason_codes: Sequence[str] = (),
) -> OperationalAlert:
    messages = {
        OperationalAlertCode.PROVIDER_UNKNOWN: "Provider evidence is unknown",
        OperationalAlertCode.PROVIDER_DEGRADED: "Provider evidence is degraded",
        OperationalAlertCode.PROVIDER_DOWN: "Provider is unavailable",
        OperationalAlertCode.PROVIDER_QUOTA_LOW: "Provider quota is low",
        OperationalAlertCode.PROVIDER_QUOTA_EXHAUSTED: "Provider quota is exhausted",
        OperationalAlertCode.PROVIDER_COST_BUDGET: "Provider cost budget requires review",
        OperationalAlertCode.LATENCY_SLO_VIOLATED: "Provider latency target is violated",
        OperationalAlertCode.STREAM_GAP_OPEN: "Stream gap remains open",
        OperationalAlertCode.STREAM_RECOVERY_FAILED: "Stream recovery has failed",
        OperationalAlertCode.QUEUE_BACKPRESSURE: "Downstream queue backpressure is active",
        OperationalAlertCode.OUTBOX_DEAD_LETTERS: "Outbox dead letters require operator review",
    }
    subject = ""
    if provider is not None:
        subject = f":{_slug(provider)}"
        if capability is not None:
            subject += f":{_slug(capability)}"
    return OperationalAlert(
        code=code,
        severity=severity,
        dedupe_key=f"operations:{code.value.lower()}{subject}",
        message=messages[code],
        observed_at=as_of,
        provider=provider,
        capability=capability,
        reason_codes=tuple(reason_codes),
    )


class OperationsProjector:
    """Build a deterministic operations view and active advisory alerts."""

    def __init__(self, *, policy: ProviderSloPolicy | None = None) -> None:
        self.policy = policy or ProviderSloPolicy()

    def project(
        self,
        *,
        as_of: datetime,
        providers: Sequence[ProviderOperationalInput],
        reliability: ReliabilitySnapshot,
        early_detection: EarlyDetectionSnapshot | Mapping[str, object] | None = None,
    ) -> OperationsOverview:
        normalized_as_of = ensure_utc(as_of, "as_of")
        if not isinstance(reliability, ReliabilitySnapshot):
            raise TypeError("reliability must be a ReliabilitySnapshot")
        normalized_providers = tuple(providers)
        if any(not isinstance(item, ProviderOperationalInput) for item in normalized_providers):
            raise TypeError("providers must contain ProviderOperationalInput values")
        keys = [(item.provider, item.capability) for item in normalized_providers]
        if len(keys) != len(set(keys)):
            raise ValueError("provider operational inputs must be unique")
        slo_state = self.policy.evaluate(reliability)
        statuses: list[ProviderOperationalStatus] = []
        alerts: list[OperationalAlert] = []
        for item in sorted(
            normalized_providers,
            key=lambda value: (value.provider, value.capability),
        ):
            status, provider_alerts = self._provider_status(item, slo_state, normalized_as_of)
            statuses.append(status)
            alerts.extend(provider_alerts)

        counters = reliability.counters
        gauges = reliability.gauges
        if float(gauges.get("open_gap_count", 0)) > 0:
            alerts.append(
                _alert(
                    OperationalAlertCode.STREAM_GAP_OPEN,
                    AlertSeverity.CRITICAL,
                    as_of=normalized_as_of,
                    reason_codes=("OPEN_STREAM_GAP",),
                )
            )
        if counters.get("recovery_failures", 0) > 0:
            alerts.append(
                _alert(
                    OperationalAlertCode.STREAM_RECOVERY_FAILED,
                    AlertSeverity.CRITICAL,
                    as_of=normalized_as_of,
                    reason_codes=("STREAM_RECOVERY_FAILURE",),
                )
            )
        if counters.get("queue_saturations", 0) > 0:
            alerts.append(
                _alert(
                    OperationalAlertCode.QUEUE_BACKPRESSURE,
                    AlertSeverity.WARNING,
                    as_of=normalized_as_of,
                    reason_codes=("QUEUE_SATURATION",),
                )
            )
        if counters.get("outbox_dead_letters", 0) > 0:
            alerts.append(
                _alert(
                    OperationalAlertCode.OUTBOX_DEAD_LETTERS,
                    AlertSeverity.CRITICAL,
                    as_of=normalized_as_of,
                    reason_codes=("OUTBOX_DEAD_LETTER",),
                )
            )
        alerts.sort(key=lambda alert: alert.dedupe_key)
        overall_state = self._overall_state(statuses, alerts)
        return OperationsOverview(
            as_of=normalized_as_of,
            overall_state=overall_state,
            slo_state=slo_state,
            policy_version=self.policy.version,
            measurement_method=reliability.measurement_method,
            providers=tuple(statuses),
            alerts=tuple(alerts),
            metrics=reliability.to_dict(),
            early_detection=(
                {}
                if early_detection is None
                else (
                    early_detection.to_dict()
                    if isinstance(early_detection, EarlyDetectionSnapshot)
                    else early_detection
                )
            ),
        )

    def _provider_status(
        self,
        item: ProviderOperationalInput,
        slo_state: OperationalSloState,
        as_of: datetime,
    ) -> tuple[ProviderOperationalStatus, list[OperationalAlert]]:
        state = OperationalState(item.state)
        freshness_state = (
            None
            if item.freshness_state is None
            else QualityState(item.freshness_state)
        )
        reasons = list(item.reason_codes)
        alerts: list[OperationalAlert] = []
        if state is OperationalState.HEALTHY and freshness_state is None:
            state = OperationalState.UNKNOWN
            reasons.append("MISSING_FRESHNESS")
        elif state is OperationalState.HEALTHY and freshness_state in {
            QualityState.UNKNOWN,
            QualityState.INVALID,
            QualityState.CONFLICTED,
        }:
            state = OperationalState.UNKNOWN
            assert freshness_state is not None
            reasons.append(f"{freshness_state.value}_FRESHNESS")
        elif state is OperationalState.HEALTHY and freshness_state is QualityState.STALE:
            state = OperationalState.DEGRADED
            reasons.append("STALE_FRESHNESS")
        if state is OperationalState.HEALTHY and (
            item.latency_ms is not None and item.latency_ms > self.policy.latency_p95_budget_ms
        ):
            state = OperationalState.DEGRADED
            reasons.append("LATENCY_ABOVE_TARGET")

        quota_state = self._quota_state(item)
        if quota_state == OperationalAlertCode.PROVIDER_QUOTA_EXHAUSTED:
            state = OperationalState.DEGRADED if state is OperationalState.HEALTHY else state
            reasons.append("QUOTA_EXHAUSTED")
        elif quota_state == OperationalAlertCode.PROVIDER_QUOTA_LOW:
            state = OperationalState.DEGRADED if state is OperationalState.HEALTHY else state
            reasons.append("QUOTA_LOW")

        if slo_state is OperationalSloState.VIOLATED:
            state = OperationalState.DEGRADED if state is OperationalState.HEALTHY else state
            reasons.append("LATENCY_SLO_VIOLATED")
        cost_budget_reached = (
            item.cost_today_usd is not None
            and item.cost_budget_usd is not None
            and item.cost_budget_usd > 0
            and item.cost_today_usd >= item.cost_budget_usd
        )
        if cost_budget_reached:
            state = OperationalState.DEGRADED if state is OperationalState.HEALTHY else state
            reasons.append("COST_BUDGET_REACHED")

        if state is OperationalState.DOWN:
            alerts.append(
                _alert(
                    OperationalAlertCode.PROVIDER_DOWN,
                    AlertSeverity.CRITICAL,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=tuple(reasons) or ("PROVIDER_DOWN",),
                )
            )
        elif state is OperationalState.UNKNOWN:
            alerts.append(
                _alert(
                    OperationalAlertCode.PROVIDER_UNKNOWN,
                    AlertSeverity.CRITICAL,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=tuple(reasons) or ("PROVIDER_UNKNOWN",),
                )
            )
        elif state is OperationalState.DEGRADED:
            alerts.append(
                _alert(
                    OperationalAlertCode.PROVIDER_DEGRADED,
                    AlertSeverity.WARNING,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=tuple(reasons) or ("PROVIDER_DEGRADED",),
                )
            )
        if quota_state is not None:
            alerts.append(
                _alert(
                    quota_state,
                    AlertSeverity.CRITICAL
                    if quota_state is OperationalAlertCode.PROVIDER_QUOTA_EXHAUSTED
                    else AlertSeverity.WARNING,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=(quota_state.value,),
                )
            )
        if cost_budget_reached:
            alerts.append(
                _alert(
                    OperationalAlertCode.PROVIDER_COST_BUDGET,
                    AlertSeverity.CRITICAL,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=("COST_BUDGET_REACHED",),
                )
            )
        if slo_state is OperationalSloState.VIOLATED:
            alerts.append(
                _alert(
                    OperationalAlertCode.LATENCY_SLO_VIOLATED,
                    AlertSeverity.WARNING,
                    as_of=as_of,
                    provider=item.provider,
                    capability=item.capability,
                    reason_codes=("LATENCY_SLO_VIOLATED",),
                )
            )
        return (
            ProviderOperationalStatus(
                provider=item.provider,
                capability=item.capability,
                state=state,
                slo_state=slo_state,
                checked_at=item.checked_at,
                latency_ms=item.latency_ms,
                freshness_state=freshness_state,
                quota_limit=item.quota_limit,
                quota_remaining=item.quota_remaining,
                quota_reset_at=item.quota_reset_at,
                cost_today_usd=item.cost_today_usd,
                cost_budget_usd=item.cost_budget_usd,
                error_class=item.error_class,
                consecutive_failures=item.consecutive_failures,
                reason_codes=tuple(dict.fromkeys(reasons)),
            ),
            alerts,
        )

    def _quota_state(self, item: ProviderOperationalInput) -> OperationalAlertCode | None:
        if item.quota_limit is None or item.quota_remaining is None or item.quota_limit == 0:
            return (
                OperationalAlertCode.PROVIDER_QUOTA_EXHAUSTED
                if item.quota_limit == 0 and item.quota_remaining == 0
                else None
            )
        if item.quota_remaining == 0:
            return OperationalAlertCode.PROVIDER_QUOTA_EXHAUSTED
        if item.quota_remaining / item.quota_limit <= self.policy.low_quota_fraction:
            return OperationalAlertCode.PROVIDER_QUOTA_LOW
        return None

    @staticmethod
    def _overall_state(
        statuses: Sequence[ProviderOperationalStatus],
        alerts: Sequence[OperationalAlert],
    ) -> OperationalState:
        if not statuses:
            return OperationalState.UNKNOWN
        states = {status.state for status in statuses}
        if OperationalState.DOWN in states:
            return OperationalState.DOWN
        if OperationalState.UNKNOWN in states:
            return OperationalState.UNKNOWN
        if OperationalState.DEGRADED in states or alerts:
            return OperationalState.DEGRADED
        return OperationalState.HEALTHY


class OperationsReadPort(Protocol):
    """Application-facing read port for the operations dashboard."""

    async def get_operations_overview(
        self,
        as_of: datetime | None = None,
    ) -> OperationsOverview: ...


class InMemoryOperationsQueryService:
    """Keyless deterministic adapter for local operation and contract tests."""

    def __init__(
        self,
        *,
        reliability: ReliabilityMetrics | ReliabilitySnapshot | None = None,
        providers: Sequence[ProviderOperationalInput] = (),
        policy: ProviderSloPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        early_detection: EarlyDetectionSnapshot | Mapping[str, object] | None = None,
    ) -> None:
        if reliability is not None and not isinstance(
            reliability,
            ReliabilityMetrics | ReliabilitySnapshot,
        ):
            raise TypeError("reliability must be ReliabilityMetrics, ReliabilitySnapshot or None")
        if any(not isinstance(item, ProviderOperationalInput) for item in providers):
            raise TypeError("providers must contain ProviderOperationalInput values")
        self._reliability = reliability if reliability is not None else ReliabilityMetrics()
        self._providers = tuple(providers)
        if early_detection is not None and not isinstance(
            early_detection,
            EarlyDetectionSnapshot | Mapping,
        ):
            raise TypeError("early_detection must be an EarlyDetectionSnapshot, mapping or None")
        self._early_detection = early_detection
        self._projector = OperationsProjector(policy=policy)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_operations_overview(self, as_of: datetime | None = None) -> OperationsOverview:
        normalized_as_of = ensure_utc(as_of or self._clock(), "as_of")
        snapshot = (
            self._reliability.snapshot()
            if isinstance(self._reliability, ReliabilityMetrics)
            else self._reliability
        )
        return self._projector.project(
            as_of=normalized_as_of,
            providers=self._providers,
            reliability=snapshot,
            early_detection=self._early_detection,
        )


__all__ = [
    "InMemoryOperationsQueryService",
    "OperationalAlert",
    "OperationalAlertCode",
    "OperationalSloState",
    "OperationalState",
    "OperationsOverview",
    "OperationsProjector",
    "OperationsReadPort",
    "ProviderOperationalInput",
    "ProviderOperationalStatus",
    "ProviderSloPolicy",
]
