"""Provider-independent alert projection, rendering and delivery orchestration."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from time import perf_counter
from typing import Protocol
from uuid import UUID

from memeradar_domain import (
    Alert,
    AlertSeverity,
    AlertState,
    AlertType,
    EventEnvelope,
    ReasonCode,
    normalize_reason_codes,
)
from memeradar_domain.common import ensure_utc, freeze_mapping, normalize_texts, require_text

from .provider_contracts import (
    DeliveryReceipt,
    NotificationPort,
    NotificationRequest,
    ProviderRequestContext,
)
from .reliability import LatencyMetric, emit_counter, emit_latency

ALERT_PIPELINE_VERSION = "alert-pipeline-v1"
MAX_TELEGRAM_TEXT_LENGTH = 4096
_SECRET_PATTERN = re.compile(
    r"(?is)\b(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)\b\s*[:=]\s*[^\s,;]+"
)
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_URL_PATTERN = re.compile(r"^https://[^\s<>]{1,512}$", re.IGNORECASE)


class AlertStore(Protocol):
    """Application-facing persistence port for mutable alert delivery state."""

    async def get_by_dedupe_key(self, dedupe_key: str) -> Alert | None: ...

    async def save(self, alert: Alert) -> Alert: ...


class EarlyAlphaStateStore(Protocol):
    """Optional lookup over the existing durable alert ledger."""

    async def get_latest_early_alpha(self, identity: str) -> Alert | None: ...


class AlertDeliveryStatus(str, Enum):
    """Outcome of one alert projection/delivery attempt."""

    DELIVERED = "DELIVERED"
    DEDUPLICATED = "DEDUPLICATED"
    SUPPRESSED = "SUPPRESSED"
    IGNORED = "IGNORED"


@dataclass(frozen=True, slots=True)
class AlertDeliveryResult:
    """Safe delivery result without response bodies or credential material."""

    alert: Alert | None
    status: AlertDeliveryStatus
    receipt: DeliveryReceipt | None = None
    retry_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.retry_at is not None:
            object.__setattr__(self, "retry_at", ensure_utc(self.retry_at, "retry_at"))
        if self.status is AlertDeliveryStatus.DELIVERED and self.receipt is None:
            raise ValueError("delivered results require a delivery receipt")
        if self.status is AlertDeliveryStatus.IGNORED and self.alert is not None:
            raise ValueError("ignored results must not contain an alert")


class AlertDeliveryDeferred(RuntimeError):
    """A notification should remain in the outbox until a bounded retry time."""

    def __init__(self, retry_at: datetime) -> None:
        self.retry_at = ensure_utc(retry_at, "retry_at")
        super().__init__("alert delivery deferred by the destination rate limit")


class NotificationRejected(RuntimeError):
    """A notification provider returned a non-accepted delivery receipt."""

    def __init__(self, error_class: str | None = None) -> None:
        self.error_class = require_text(error_class or "NotificationRejected", "error_class")
        super().__init__("notification provider rejected the delivery")


@dataclass(frozen=True, slots=True)
class AlertPolicy:
    """Bounded alert preferences and protected operating modes."""

    max_messages: int = 20
    window: timedelta = timedelta(minutes=1)
    max_reasons: int = 4
    max_evidence_refs: int = 8
    max_text_length: int = MAX_TELEGRAM_TEXT_LENGTH
    enabled_types: frozenset[AlertType] | None = None
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False

    def __post_init__(self) -> None:
        for field_name, minimum, maximum in (
            ("max_messages", 1, 1000),
            ("max_reasons", 1, 32),
            ("max_evidence_refs", 1, 64),
            ("max_text_length", 128, MAX_TELEGRAM_TEXT_LENGTH),
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not minimum <= value <= maximum
            ):
                raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
        if not isinstance(self.window, timedelta) or self.window <= timedelta(0):
            raise ValueError("window must be positive")
        if self.window > timedelta(days=1):
            raise ValueError("window must not exceed one day")
        enabled = (
            frozenset(AlertType)
            if self.enabled_types is None
            else frozenset(AlertType(value) for value in self.enabled_types)
        )
        if not enabled:
            raise ValueError("enabled_types must not be empty")
        object.__setattr__(self, "enabled_types", enabled)
        for field_name in (
            "analysis_only",
            "paper_trading",
            "manual_execution",
            "auto_execution",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        if (
            not self.analysis_only
            or not self.paper_trading
            or self.manual_execution
            or self.auto_execution
        ):
            raise ValueError("alert policy protected modes must remain enabled/disabled")

    def allows(self, alert_type: AlertType) -> bool:
        enabled_types = self.enabled_types
        assert enabled_types is not None
        return AlertType(alert_type) in enabled_types


@dataclass(frozen=True, slots=True)
class AlertRateLimitDecision:
    """Result of reserving one destination rate-limit slot."""

    allowed: bool
    retry_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.retry_at is not None:
            object.__setattr__(self, "retry_at", ensure_utc(self.retry_at, "retry_at"))
        if not self.allowed and self.retry_at is None:
            raise ValueError("rejected rate-limit decisions require retry_at")


class AlertRateLimiter:
    """Deterministic fixed-window limiter for one process/destination."""

    def __init__(self, *, policy: AlertPolicy | None = None) -> None:
        self._policy = policy or AlertPolicy()
        self._reservations: dict[str, list[datetime]] = {}

    def reserve(self, destination: str, now: datetime) -> AlertRateLimitDecision:
        normalized_destination = require_text(destination, "destination", max_length=256)
        normalized_now = ensure_utc(now, "now")
        cutoff = normalized_now - self._policy.window
        reservations = [
            value for value in self._reservations.get(normalized_destination, []) if value > cutoff
        ]
        self._reservations[normalized_destination] = reservations
        if len(reservations) >= self._policy.max_messages:
            return AlertRateLimitDecision(
                allowed=False,
                retry_at=reservations[0] + self._policy.window,
            )
        reservations.append(normalized_now)
        return AlertRateLimitDecision(allowed=True)


def _safe_display(value: object, *, max_length: int = 512) -> str:
    if value is None:
        return ""
    normalized = _CONTROL_PATTERN.sub("", str(value)).strip()
    normalized = _SECRET_PATTERN.sub("[REDACTED]", normalized)
    return normalized[:max_length]


def _safe_lines(value: object, *, max_items: int) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list | tuple):
        values = tuple(value)
    else:
        return ()
    return tuple(
        display for item in values[:max_items] if (display := _safe_display(item, max_length=256))
    )


def _safe_metric_summary(value: object, *, max_items: int = 4) -> str:
    if not isinstance(value, Mapping):
        return _safe_display(value, max_length=256)
    values: list[str] = []
    for key, item in list(value.items())[:max_items]:
        safe_key = _safe_display(key, max_length=32)
        safe_item = _safe_display(item, max_length=64)
        if safe_key and safe_item:
            values.append(f"{safe_key}={safe_item}")
    return ", ".join(values)


def _ultra_early_payload(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    nested = payload.get("ultra_early")
    if isinstance(nested, Mapping):
        return nested
    if any(
        key in payload
        for key in (
            "early_score",
            "early_state",
            "buy_velocity",
            "shadow_entry_status",
            "external_call_lead_time_ms",
        )
    ):
        return payload
    return None


_OPPORTUNITY_MARKERS = frozenset(
    {
        "chain",
        "address",
        "winner_archetype",
        "catalyst_summary",
        "pre_token_attention_state",
        "narrative_match_confidence",
        "copycat_count",
        "chain_heat",
        "smart_wallet_independent_buyer_count",
        "market_integrity_risk",
        "provider_corroboration",
    }
)

_CALLER_MARKERS = frozenset(
    {
        "caller_quality_band",
        "caller_quality",
        "convergence_state",
        "caller_convergence_state",
        "independent_caller_count",
        "earliest_call_at",
        "smart_money_state",
        "distribution_state",
        "security_quality",
        "liquidity_quality",
        "execution_quality",
        "decision_band",
        "research_state",
        "provenance",
    }
)


def _opportunity_payload(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    nested = payload.get("opportunity")
    if isinstance(nested, Mapping):
        return nested
    if any(key in payload for key in _OPPORTUNITY_MARKERS):
        return payload
    return None


def _opportunity_value(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object],
    *keys: str,
) -> object | None:
    for source in (opportunity, payload):
        for key in keys:
            value = source.get(key)
            if value is not None:
                return value
    return None


def _safe_opportunity_value(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, Mapping):
        return _safe_display(_safe_metric_summary(value), max_length=256)
    if isinstance(value, list | tuple):
        return "; ".join(_safe_lines(value, max_items=4))
    return _safe_display(value, max_length=256)


def _opportunity_lines(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object],
) -> tuple[str, ...]:
    lines: list[str] = []
    field_specs = (
        ("Chain", ("chain",)),
        ("Token", ("token", "token_id")),
        ("Address", ("address", "contract_address", "mint")),
        ("Age", ("age", "age_seconds")),
        ("Market cap", ("market_cap_usd", "market_cap", "market_cap_at_entry")),
        ("Liquidity", ("liquidity_usd", "liquidity", "liquidity_at_entry")),
        ("Winner archetype", ("winner_archetype", "archetype", "archetypes")),
        ("Catalyst", ("catalyst_summary", "catalyst_type")),
        ("Catalyst age", ("catalyst_age", "catalyst_age_seconds")),
        (
            "Pre-token attention",
            ("pre_token_attention_state", "pre_token_attention", "attention_state"),
        ),
        ("Attention velocity", ("attention_velocity", "attention_slope")),
        ("Source diversity", ("attention_source_diversity", "source_diversity")),
        (
            "Narrative match",
            ("narrative_match_confidence", "match_confidence", "narrative_token_match"),
        ),
        ("Copycats", ("copycat_count", "candidate_count")),
        ("Narrative dominance", ("narrative_dominance", "dominance")),
        ("Chain heat", ("chain_heat",)),
        (
            "Ecosystem acceleration",
            ("ecosystem_acceleration", "chain_opportunity_acceleration"),
        ),
        (
            "Smart-wallet independent buyers",
            (
                "smart_wallet_independent_buyer_count",
                "independent_buyer_count",
                "raw_qualified_wallet_count",
                "qualified_wallet_count",
                "independent_cluster_count",
                "cluster_adjusted_independent_wallet_count",
            ),
        ),
        (
            "Smart-wallet entries",
            ("smart_wallet_entry_count", "raw_entry_wallet_count", "entry_wallet_count"),
        ),
        (
            "First elite-wallet entry",
            ("first_elite_wallet_entry_age", "elite_wallet_entry_age"),
        ),
        (
            "First elite-wallet market cap",
            (
                "first_elite_wallet_entry_market_cap",
                "elite_wallet_entry_market_cap",
            ),
        ),
        ("Holder acceleration", ("holder_acceleration", "holder_growth")),
        (
            "Liquidity acceleration",
            ("liquidity_acceleration", "liquidity_inflow_acceleration"),
        ),
        ("Protocol velocity", ("protocol_velocity", "protocol_usage_velocity")),
        ("Fundamental velocity", ("fundamental_velocity",)),
        ("Hard risk", ("hard_risk", "risk_disposition", "hard_risk_blocked")),
        ("Market integrity", ("market_integrity_risk", "market_integrity")),
        ("Contract/deployer risk", ("contract_deployer_risk", "deployer_risk")),
        ("Liquidity/exit risk", ("liquidity_exit_risk", "exit_risk")),
        ("Sellability", ("sellability", "sellability_state")),
        (
            "Provider corroboration",
            ("provider_corroboration", "provider_evidence_state"),
        ),
        (
            "Provider disagreement",
            ("provider_disagreement", "provider_conflict"),
        ),
        ("Confidence", ("confidence", "evidence_confidence")),
        ("Freshness", ("freshness", "quality_state", "evidence_quality_state")),
        (
            "Evidence timing",
            ("evidence_timing", "as_of", "first_seen_at", "observed_at"),
        ),
        (
            "Alert latency",
            ("alert_latency_ms", "candidate_to_alert_ms", "alert_processing_ms"),
        ),
    )
    for label, keys in field_specs:
        value = _opportunity_value(payload, opportunity, *keys)
        if value is None:
            continue
        display = _safe_opportunity_value(value)
        if display:
            lines.append(f"{label}: {display}")

    entry_age = _opportunity_value(
        payload,
        opportunity,
        "first_elite_wallet_entry_age",
        "elite_wallet_entry_age",
    )
    entry_market_cap = _opportunity_value(
        payload,
        opportunity,
        "first_elite_wallet_entry_market_cap",
        "elite_wallet_entry_market_cap",
    )
    if entry_age is not None and entry_market_cap is not None:
        age = _safe_opportunity_value(entry_age)
        market_cap = _safe_opportunity_value(entry_market_cap)
        combined = f"First elite-wallet entry: {age} / MC {market_cap}"
        lines = [line for line in lines if not line.startswith("First elite-wallet entry:")]
        lines = [line for line in lines if not line.startswith("First elite-wallet market cap:")]
        lines.append(combined)

    raw_refs = _opportunity_value(payload, opportunity, "evidence_refs")
    refs = _safe_lines(raw_refs, max_items=8)
    raw_count = _opportunity_value(payload, opportunity, "evidence_count")
    if raw_count is None and refs:
        raw_count = len(refs)
    if raw_count is not None:
        count = _safe_opportunity_value(raw_count)
        if count:
            lines.append(f"Evidence count: {count}")

    return tuple(lines)


def _caller_payload(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    sources = tuple(source for source in (opportunity, payload) if source is not None)
    merged: dict[str, object] = {}
    for source in sources:
        for key in ("caller_intelligence", "caller_evidence", "caller_profile", "caller"):
            value = source.get(key)
            if isinstance(value, Mapping):
                merged.update({str(name): item for name, item in value.items()})
        convergence = source.get("caller_convergence")
        if isinstance(convergence, Mapping):
            merged.update({str(name): item for name, item in convergence.items()})
        for key in _CALLER_MARKERS:
            if key in source:
                merged.setdefault(key, source[key])
    return merged or None


def _caller_sources(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object] | None,
    caller: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    sources: list[Mapping[str, object]] = [caller]
    for parent in (opportunity, payload):
        if parent is None:
            continue
        for key in ("caller_intelligence", "caller_evidence", "caller_profile", "caller"):
            value = parent.get(key)
            if isinstance(value, Mapping) and value not in sources:
                sources.append(value)
    if opportunity is not None:
        sources.append(opportunity)
    sources.append(payload)
    return tuple(sources)


def _caller_value(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object] | None,
    caller: Mapping[str, object],
    *keys: str,
) -> object | None:
    for source in _caller_sources(payload, opportunity, caller):
        for key in keys:
            value = source.get(key)
            if value is not None:
                return value
    return None


def _caller_lines(
    payload: Mapping[str, object],
    opportunity: Mapping[str, object] | None,
    caller: Mapping[str, object],
) -> tuple[str, ...]:
    lines: list[str] = []
    field_specs = (
        (
            "Caller quality",
            (
                "quality_band",
                "caller_quality_band",
                "historical_quality_band",
                "profile_quality_band",
            ),
        ),
        ("Caller convergence", ("convergence_state", "caller_convergence_state", "convergence")),
        (
            "Independent callers",
            ("independent_caller_count", "independent_callers", "caller_count"),
        ),
        ("Smart-money", ("smart_money_state", "smart_wallet_state", "smart_money_confirmation")),
        (
            "Caller distribution",
            ("distribution_state", "post_call_distribution", "distribution_evidence"),
        ),
        ("Security quality", ("security_quality", "token_security_quality", "security_state")),
        ("Liquidity quality", ("liquidity_quality", "liquidity_state")),
        ("Execution quality", ("execution_quality", "execution_state")),
        ("Decision band", ("decision_band", "meme_radar_decision_band")),
        ("Research state", ("research_state", "evidence_class", "research_evidence_state")),
        ("Provenance", ("provenance", "provenance_state", "provider_provenance")),
    )
    for label, keys in field_specs:
        value = _caller_value(payload, opportunity, caller, *keys)
        if value is None:
            continue
        display = _safe_opportunity_value(value)
        if display:
            lines.append(f"{label}: {display}")

    earliest_parts: list[str] = []
    earliest_at = _caller_value(
        payload,
        opportunity,
        caller,
        "earliest_call_at",
        "earliest_call_timestamp",
        "first_call_at",
    )
    earliest_market_cap = _caller_value(
        payload,
        opportunity,
        caller,
        "earliest_call_market_cap",
        "first_call_market_cap",
    )
    earliest_age = _caller_value(
        payload,
        opportunity,
        caller,
        "earliest_call_age",
        "earliest_call_age_seconds",
        "first_call_age",
    )
    if earliest_at is not None:
        earliest_parts.append(_safe_opportunity_value(earliest_at))
    if earliest_market_cap is not None:
        earliest_parts.append(f"MC {_safe_opportunity_value(earliest_market_cap)}")
    if earliest_age is not None:
        earliest_parts.append(f"age {_safe_opportunity_value(earliest_age)}")
    if earliest_parts:
        lines.append("Earliest call: " + " / ".join(earliest_parts))
    return tuple(lines)


class AlertRenderer:
    """Render typed alerts as bounded plain text safe for Telegram."""

    _secret_patterns = (_SECRET_PATTERN,)

    def __init__(self, *, max_length: int = MAX_TELEGRAM_TEXT_LENGTH) -> None:
        if not 128 <= max_length <= MAX_TELEGRAM_TEXT_LENGTH:
            raise ValueError("max_length must be between 128 and 4096")
        self.max_length = max_length

    def render(self, alert: Alert) -> str:
        if not isinstance(alert, Alert):
            raise TypeError("alert must be an Alert")
        payload = alert.payload
        title = _safe_display(payload.get("symbol") or payload.get("name") or payload.get("mint"))
        lines = [
            f"[{alert.type.value}] {title}".rstrip(),
            f"Severity: {alert.severity.value}",
        ]
        state = _safe_display(payload.get("state") or payload.get("to_state"))
        if state:
            lines.append(f"State: {state}")
        mint = _safe_display(payload.get("mint"))
        if mint and mint != title:
            lines.append(f"Mint: {mint}")

        score = _safe_display(payload.get("score") or payload.get("alpha_score"))
        delta = _safe_display(payload.get("score_delta"))
        if score:
            score_line = f"Score: {score}"
            if delta:
                score_line += f" ({delta if delta.startswith(('+', '-')) else '+' + delta})"
            lines.append(score_line)
        opportunity = _opportunity_payload(payload)
        if opportunity is not None:
            opportunity_lines = _opportunity_lines(payload, opportunity)
            if opportunity_lines:
                lines.append("OPPORTUNITY EVIDENCE")
                lines.extend(opportunity_lines)
        caller = _caller_payload(payload, opportunity)
        if caller is not None:
            caller_lines = _caller_lines(payload, opportunity, caller)
            if caller_lines:
                lines.append("CALLER INTELLIGENCE")
                lines.extend(caller_lines)
        early_payload = _ultra_early_payload(payload)
        if early_payload is not None:
            lines.append("ULTRA EARLY SIGNAL")
            for key, label in (
                ("launch_age_seconds", "Age (seconds)"),
                ("early_score", "EarlyScore"),
                ("early_score_confidence", "Confidence"),
                ("early_state", "Early state"),
                ("buy_velocity", "Buy velocity"),
                ("buy_acceleration", "Buy acceleration"),
                ("unique_buyers", "Unique buyers"),
                ("quote_inflow", "Quote inflow"),
                ("creator_risk", "Creator risk"),
                ("bundle_risk", "Bundle risk"),
                ("holder_risk", "Holder risk"),
                ("sellability", "Sellability"),
                ("shadow_entry_status", "Shadow entry"),
                ("external_call_lead_time_ms", "Lead time (ms)"),
            ):
                value = _safe_metric_summary(early_payload.get(key))
                if value:
                    lines.append(f"{label}: {value}")
            block_reasons = _safe_lines(early_payload.get("hard_block_reasons"), max_items=4)
            if block_reasons:
                lines.append("Hard blocks: " + "; ".join(block_reasons))
        if alert.type in {AlertType.EXIT_RISK, AlertType.PAPER_EXIT}:
            action = _safe_display(payload.get("action"))
            fraction = _safe_display(payload.get("exit_fraction"))
            if action:
                lines.append(f"Exit: {action}" + (f" ({fraction})" if fraction else ""))
            pnl_value = next(
                (
                    payload[key]
                    for key in ("total_pnl", "pnl", "realized_pnl")
                    if key in payload and payload[key] is not None
                ),
                None,
            )
            pnl = _safe_display(pnl_value)
            if pnl:
                lines.append(f"PnL: {pnl}")
        if alert.type is AlertType.EARLY_WATCH:
            lines.append("NOT ENTRY_READY")
            lines.append("RESEARCH/PAPER SIGNAL")
        for key, label in (
            ("age", "Age"),
            ("liquidity_usd", "Liquidity"),
            ("market_cap_usd", "Market cap"),
            ("provider", "Provider"),
            ("capability", "Capability"),
            ("health_state", "Health"),
        ):
            value = _safe_display(payload.get(key))
            if value:
                lines.append(f"{label}: {value}")

        positive = _safe_lines(payload.get("top_positive_evidence"), max_items=4)
        if positive:
            lines.append("Positive evidence: " + "; ".join(positive))
        risks = _safe_lines(payload.get("top_risk_evidence"), max_items=4)
        if risks:
            lines.append("Risk evidence: " + "; ".join(risks))
        reasons = [reason.code for reason in alert.reason_codes]
        if opportunity is not None:
            reasons.extend(
                reason
                for reason in _safe_lines(
                    _opportunity_value(payload, opportunity, "reason_codes"),
                    max_items=8,
                )
                if reason not in reasons
            )
        reasons = list(dict.fromkeys(reasons))[:4]
        if reasons:
            lines.append("Reasons: " + ", ".join(reasons))
        references: list[str] = []
        for raw_references in (
            payload.get("evidence_refs"),
            None if opportunity is None else opportunity.get("evidence_refs"),
            None if caller is None else caller.get("evidence_refs"),
        ):
            if isinstance(raw_references, str):
                if safe_reference := _safe_display(raw_references, max_length=512):
                    references.append(safe_reference)
            elif isinstance(raw_references, list | tuple):
                references.extend(
                    safe_reference
                    for value in raw_references
                    if isinstance(value, str)
                    and (safe_reference := _safe_display(value, max_length=512))
                )
        references.extend(
            safe_reference
            for reason in alert.reason_codes
            for reference in reason.evidence_refs
            if (safe_reference := _safe_display(reference, max_length=512))
        )
        normalized_references = normalize_texts(references, "evidence_refs")[:8]
        if normalized_references:
            lines.append("Evidence: " + ", ".join(normalized_references))
        dashboard_url = _safe_display(payload.get("dashboard_url"), max_length=512)
        if dashboard_url and _URL_PATTERN.fullmatch(dashboard_url):
            lines.append(f"Dashboard: {dashboard_url}")
        lines.append("Auto execution: LOCKED")
        rendered = "\n".join(_safe_display(line, max_length=self.max_length) for line in lines)
        if len(rendered) <= self.max_length:
            return rendered
        suffix = "\n[…truncated]"
        return rendered[: max(0, self.max_length - len(suffix))] + suffix

    def to_request(
        self,
        alert: Alert,
        *,
        context: ProviderRequestContext,
        destination: str,
    ) -> NotificationRequest:
        return NotificationRequest(
            context=context,
            type=alert.type.value,
            dedupe_key=alert.dedupe_key,
            payload={
                "chat_id": require_text(destination, "destination", max_length=256),
                "text": self.render(alert),
            },
        )


def _uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _event_candidate_id(event: EventEnvelope) -> UUID | None:
    return _uuid(event.payload.get("candidate_id")) or _uuid(event.aggregate_id)


def _event_reasons(event: EventEnvelope, payload: Mapping[str, object]) -> tuple[ReasonCode, ...]:
    values: list[ReasonCode | str] = list(event.reason_codes)
    raw_reasons = payload.get("reason_codes", ())
    if isinstance(raw_reasons, str):
        raw_reasons = (raw_reasons,)
    if isinstance(raw_reasons, list | tuple):
        values.extend(value for value in raw_reasons if isinstance(value, ReasonCode | str))
    values.append(ReasonCode("ALERT_SOURCE_EVENT", evidence_refs=(f"event:{event.id}",)))
    return normalize_reason_codes(values, required=True)


_EXTERNAL_ONLY_EXIT_REASONS = frozenset(
    {
        "EXTERNAL_EXIT_CORROBORATION_ONLY",
        "EXTERNAL_EXIT_SIGNAL_ONLY",
    }
)


def _exit_reason_values(event: EventEnvelope, payload: Mapping[str, object]) -> tuple[object, ...]:
    """Collect the flattened and nested reasons carried by exit events."""

    values: list[object] = list(event.reason_codes)
    for key in ("reason_codes", "triggered_rules"):
        raw_values = payload.get(key, ())
        if isinstance(raw_values, str):
            raw_values = (raw_values,)
        if isinstance(raw_values, list | tuple):
            values.extend(raw_values)
    risk_score = payload.get("risk_score")
    if isinstance(risk_score, Mapping):
        raw_values = risk_score.get("reason_codes", ())
        if isinstance(raw_values, str):
            raw_values = (raw_values,)
        if isinstance(raw_values, list | tuple):
            values.extend(raw_values)
    return tuple(values)


def _reason_code_text(value: object) -> str | None:
    if isinstance(value, ReasonCode):
        return value.code
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        code = value.get("code")
        return code if isinstance(code, str) else None
    return None


def _reason_code(value: object) -> ReasonCode | None:
    if isinstance(value, ReasonCode):
        return value
    if isinstance(value, str):
        try:
            return ReasonCode(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, Mapping):
        return None
    code = value.get("code")
    if not isinstance(code, str):
        return None
    detail = value.get("detail")
    if detail is not None and not isinstance(detail, str):
        detail = None
    raw_refs = value.get("evidence_refs", ())
    if isinstance(raw_refs, str):
        raw_refs = (raw_refs,)
    evidence_refs = (
        tuple(reference for reference in raw_refs if isinstance(reference, str))
        if isinstance(raw_refs, list | tuple)
        else ()
    )
    try:
        return ReasonCode(code, detail=detail, evidence_refs=evidence_refs)
    except (TypeError, ValueError):
        return None


def _has_core_exit_trigger(values: tuple[object, ...]) -> bool:
    """Return whether an exit event contains a deterministic/core trigger."""

    for value in values:
        code = _reason_code_text(value)
        if code is None:
            continue
        normalized = code.upper()
        if normalized in _EXTERNAL_ONLY_EXIT_REASONS or normalized.startswith("EXTERNAL_"):
            continue
        return True
    return False


def _exit_alert_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Expose only bounded, allow-listed exit fields to alert persistence."""

    scalar_keys = {
        "position_id",
        "candidate_id",
        "token_id",
        "mint",
        "symbol",
        "name",
        "action",
        "exit_fraction",
        "pnl",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "score",
        "alpha_score",
        "score_before",
        "score_after",
        "score_delta",
        "confidence",
        "quality_state",
        "policy_version",
        "config_hash",
    }
    list_keys = {
        "reason_codes",
        "triggered_rules",
        "before_evidence_refs",
        "after_evidence_refs",
    }
    result: dict[str, object] = {}
    for key in scalar_keys:
        if key not in payload:
            continue
        display = _safe_display(payload[key], max_length=256)
        if display:
            result[key] = display
    for key in list_keys:
        values = _safe_lines(payload.get(key), max_items=8)
        if values:
            result[key] = values

    risk_score = payload.get("risk_score")
    if isinstance(risk_score, Mapping):
        for source_key, output_key in (
            ("score", "score"),
            ("confidence", "confidence"),
            ("quality_state", "quality_state"),
        ):
            if output_key not in result and source_key in risk_score:
                display = _safe_display(risk_score[source_key], max_length=256)
                if display:
                    result[output_key] = display

    evidence: list[str] = []
    for key in ("evidence_refs", "after_evidence_refs", "before_evidence_refs"):
        raw_values = payload.get(key, ())
        if isinstance(raw_values, str):
            raw_values = (raw_values,)
        if isinstance(raw_values, list | tuple):
            evidence.extend(value for value in raw_values if isinstance(value, str))
    if isinstance(risk_score, Mapping):
        raw_values = risk_score.get("evidence_refs", ())
        if isinstance(raw_values, str):
            raw_values = (raw_values,)
        if isinstance(raw_values, list | tuple):
            evidence.extend(value for value in raw_values if isinstance(value, str))
    if evidence:
        result["evidence_refs"] = tuple(dict.fromkeys(evidence))
    return result


def _exit_alert_reasons(
    event: EventEnvelope,
    payload: Mapping[str, object],
    values: tuple[object, ...],
) -> tuple[ReasonCode, ...]:
    normalized: list[ReasonCode | str] = []
    for value in values:
        reason = _reason_code(value)
        if reason is not None:
            normalized.append(reason)
    evidence_refs = payload.get("after_evidence_refs", ())
    if isinstance(evidence_refs, str):
        evidence_refs = (evidence_refs,)
    if isinstance(evidence_refs, list | tuple):
        normalized.extend(
            ReasonCode("EXIT_EVIDENCE", evidence_refs=(value,))
            for value in evidence_refs
            if isinstance(value, str)
        )
    normalized.append(ReasonCode("ALERT_SOURCE_EVENT", evidence_refs=(f"event:{event.id}",)))
    return normalize_reason_codes(normalized, required=True)


def _dedupe_key(alert_type: AlertType, event_key: str) -> str:
    material = f"alert:{alert_type.value}:{event_key}"
    if len(material) <= 256:
        return material
    return f"alert:{alert_type.value}:sha256:{hashlib.sha256(material.encode()).hexdigest()}"


def _payload_with_event_metadata(
    event: EventEnvelope,
    payload: Mapping[str, object],
) -> dict[str, object]:
    result = {str(key): value for key, value in payload.items()}
    result.setdefault("event_id", str(event.id))
    result.setdefault("event_kind", event.kind)
    if event.aggregate_id:
        result.setdefault("aggregate_id", str(event.aggregate_id))
    return result


_ALERT_TIMING_KEY = "alert_timing"
_SENT_TO_TELEGRAM_API = "SENT_TO_TELEGRAM_API"


def _timing_sources(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    nested = payload.get("early_alpha")
    return (payload, nested) if isinstance(nested, Mapping) else (payload,)


def _payload_datetime(
    payload: Mapping[str, object],
    key: str,
    fallback: datetime | None = None,
) -> datetime | None:
    for source in _timing_sources(payload):
        value = source.get(key)
        if isinstance(value, datetime):
            return ensure_utc(value, key)
        if isinstance(value, str) and value:
            try:
                return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")), key)
            except ValueError:
                continue
    return fallback


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() * 1000)


def _alert_timing(
    alert: Alert,
    queued_clock: datetime,
    *,
    delivery_started_at: datetime | None = None,
    sent_at: datetime | None = None,
) -> dict[str, object]:
    """Build the durable timing ledger without claiming user delivery."""

    current = alert.payload.get(_ALERT_TIMING_KEY)
    current_timing = current if isinstance(current, Mapping) else {}
    decision_at = _payload_datetime(alert.payload, "decision_at")
    decision_at = _payload_datetime(
        current_timing, "decision_at", decision_at or alert.requested_at
    )
    projected_at = _payload_datetime(alert.payload, "alert_projected_at")
    projected_at = _payload_datetime(
        current_timing, "alert_projected_at", projected_at or alert.requested_at
    )
    queued_at = _payload_datetime(
        current_timing,
        "telegram_queued_at",
        max(alert.requested_at, ensure_utc(queued_clock, "queued_clock")),
    )
    started_at = delivery_started_at or _payload_datetime(
        current_timing, "telegram_delivery_started_at"
    )
    if started_at is not None:
        started_at = ensure_utc(started_at, "telegram_delivery_started_at")
    sent_timestamp = sent_at or _payload_datetime(current_timing, "telegram_sent_at")
    if sent_timestamp is not None:
        sent_timestamp = ensure_utc(sent_timestamp, "telegram_sent_at")
    provider_observed_at = _payload_datetime(alert.payload, "provider_observed_at")
    chain_created_at = _payload_datetime(alert.payload, "chain_created_at")
    return {
        "decision_at": None if decision_at is None else decision_at.isoformat(),
        "alert_projected_at": None if projected_at is None else projected_at.isoformat(),
        "telegram_queued_at": None if queued_at is None else queued_at.isoformat(),
        "telegram_delivery_started_at": (
            None if started_at is None else started_at.isoformat()
        ),
        "telegram_sent_at": None if sent_timestamp is None else sent_timestamp.isoformat(),
        "delivered_to_user_at": None,
        "sent_timestamp_semantics": _SENT_TO_TELEGRAM_API,
        "decision_to_queue_ms": _duration_ms(decision_at, queued_at),
        "queue_to_send_ms": _duration_ms(queued_at, sent_timestamp),
        "decision_to_send_ms": _duration_ms(decision_at, sent_timestamp),
        "provider_to_alert_ms": _duration_ms(provider_observed_at, projected_at),
        "chain_to_alert_ms": _duration_ms(chain_created_at, projected_at),
    }


def _set_alert_timing(alert: Alert, timing: Mapping[str, object]) -> Alert:
    payload = dict(alert.payload)
    payload[_ALERT_TIMING_KEY] = dict(timing)
    alert.payload = freeze_mapping(payload, "alert.payload")
    return alert


class AlertEventProjector:
    """Turn meaningful internal events into typed, explainable alert requests."""

    def project(self, event: EventEnvelope) -> Alert | None:
        if not isinstance(event, EventEnvelope):
            raise TypeError("event must be an EventEnvelope")
        payload = event.payload
        alert_type: AlertType | None = None
        severity = AlertSeverity.INFO
        alert_payload: Mapping[str, object] = payload

        if event.kind in {
            "EarlyAlphaStateChanged",
            "EarlyAlphaProjection",
            "EarlyAlphaAlertRequested",
        }:
            nested = payload.get("early_alpha")
            if not isinstance(nested, Mapping):
                return None
            alert_type = AlertType.EARLY_ALPHA
            alert_payload = {"early_alpha": dict(nested)}
            for key in (
                "symbol",
                "name",
                "mint",
                "evidence_refs",
                "dashboard_url",
                "top_positive_evidence",
                "top_risk_evidence",
            ):
                if key in payload:
                    alert_payload[key] = payload[key]
            raw_state = nested.get("state") or nested.get("confirmation_state")
            state = _safe_display(raw_state).upper()
            severity = (
                AlertSeverity.CRITICAL
                if state in {"INVALIDATED", "CONFLICT"}
                else AlertSeverity.WARNING
                if state == "DEGRADED"
                else AlertSeverity.INFO
            )
        elif event.kind == "AlertRequested":
            try:
                alert_type = AlertType(payload["type"])
                severity = AlertSeverity(payload.get("severity", AlertSeverity.INFO))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("AlertRequested must contain a valid type and severity") from exc
            nested = payload.get("payload", {})
            if not isinstance(nested, Mapping):
                raise ValueError("AlertRequested payload must be a mapping")
            alert_payload = nested
            if alert_type is AlertType.EARLY_ALPHA and "early_alpha" not in nested:
                alert_payload = {"early_alpha": dict(nested)}
        elif event.kind in {"CandidateStateChanged", "AlphaScoreDelta"}:
            from_state = _safe_display(payload.get("from_state"))
            to_state = _safe_display(payload.get("to_state"))
            if not to_state or from_state == to_state:
                return None
            state_types = {
                "WATCH": AlertType.NEW_WATCH,
                "EARLY_WATCH": AlertType.EARLY_WATCH,
                "STRONG_SETUP": AlertType.STRONG_SETUP,
                "HIGH_CONFLUENCE": AlertType.HIGH_CONFLUENCE,
                "ENTRY_READY": AlertType.ENTRY_READY,
            }
            alert_type = state_types.get(to_state)
            if alert_type is None:
                if to_state != "RISK_REJECTED":
                    return None
                alert_type = AlertType.RISK_ESCALATION
                severity = AlertSeverity.CRITICAL
        elif event.kind == "RiskEscalation":
            alert_type = AlertType.RISK_ESCALATION
            severity = (
                AlertSeverity.CRITICAL
                if _safe_display(payload.get("disposition")) == "BLOCK"
                or bool(payload.get("hard_blocks"))
                else AlertSeverity.WARNING
            )
        elif event.kind == "ProviderHealthChanged":
            health_state = _safe_display(payload.get("state") or payload.get("health_state"))
            if health_state not in {"DEGRADED", "DOWN", "UNKNOWN"}:
                return None
            alert_type = AlertType.PROVIDER_DEGRADED
            severity = AlertSeverity.CRITICAL if health_state == "DOWN" else AlertSeverity.WARNING
            alert_payload = {
                **payload,
                "health_state": health_state,
            }
        elif event.kind in {"ExitSignal", "ExitEvaluation", "PaperExit"}:
            action = _safe_display(payload.get("action")).upper()
            if action not in {"REDUCE", "CLOSE"}:
                return None
            exit_reasons = _exit_reason_values(event, payload)
            if not _has_core_exit_trigger(exit_reasons):
                # External intelligence can corroborate an exit recommendation but
                # cannot create an operator alert by itself.
                return None
            alert_type = AlertType.PAPER_EXIT if event.kind == "PaperExit" else AlertType.EXIT_RISK
            raw_severity = payload.get("severity")
            if raw_severity is None:
                signal_payload = payload.get("signal")
                if isinstance(signal_payload, Mapping):
                    raw_severity = signal_payload.get("severity")
            try:
                severity = (
                    AlertSeverity(raw_severity)
                    if raw_severity is not None
                    else (AlertSeverity.CRITICAL if action == "CLOSE" else AlertSeverity.WARNING)
                )
            except ValueError:
                severity = AlertSeverity.CRITICAL if action == "CLOSE" else AlertSeverity.WARNING
            alert_payload = _exit_alert_payload(payload)
            alert_reasons = _exit_alert_reasons(event, payload, exit_reasons)
        elif event.kind in {"SystemKillSwitch", "SystemHealthChanged"}:
            alert_type = AlertType.SYSTEM_KILL_SWITCH
            severity = AlertSeverity.CRITICAL
        else:
            return None

        assert alert_type is not None
        candidate_id = _event_candidate_id(event)
        position_id = _uuid(payload.get("position_id"))
        normalized_payload = _payload_with_event_metadata(event, alert_payload)
        return Alert(
            type=alert_type,
            severity=severity,
            payload=normalized_payload,
            dedupe_key=_dedupe_key(alert_type, str(payload.get("dedupe_key", event.dedupe_key))),
            requested_at=event.ingested_at,
            candidate_id=candidate_id,
            position_id=position_id,
            reason_codes=(
                alert_reasons
                if event.kind in {"ExitSignal", "ExitEvaluation", "PaperExit"}
                else _event_reasons(event, payload)
            ),
        )


class AlertDeliveryService:
    """Deliver projected alerts through a NotificationPort and alert store."""

    def __init__(
        self,
        store: AlertStore,
        notification: NotificationPort,
        *,
        policy: AlertPolicy | None = None,
        destination: str,
        renderer: AlertRenderer | None = None,
        early_alpha_renderer: AlertRenderer | None = None,
        limiter: AlertRateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
        telemetry: object | None = None,
    ) -> None:
        if not hasattr(notification, "send"):
            raise TypeError("notification must implement NotificationPort")
        self._store = store
        self._notification = notification
        self.policy = policy or AlertPolicy()
        self.destination = require_text(destination, "destination", max_length=256)
        self.renderer = renderer or AlertRenderer(max_length=self.policy.max_text_length)
        self.early_alpha_renderer = early_alpha_renderer
        self.limiter = limiter or AlertRateLimiter(policy=self.policy)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._telemetry = telemetry

    async def handle_event(self, event: EventEnvelope) -> AlertDeliveryResult:
        alert = AlertEventProjector().project(event)
        if alert is None:
            return AlertDeliveryResult(alert=None, status=AlertDeliveryStatus.IGNORED)
        if alert.type is AlertType.EARLY_ALPHA:
            return await self._handle_early_alpha_event(alert, event)
        context = ProviderRequestContext(
            correlation_id=event.correlation_id,
            requested_at=event.ingested_at,
        )
        return await self.deliver(alert, context=context)

    async def _handle_early_alpha_event(
        self,
        alert: Alert,
        event: EventEnvelope,
    ) -> AlertDeliveryResult:
        from .early_alpha_alert import (
            EarlyAlphaState,
            build_early_alpha_projection,
            evidence_fingerprint,
            snapshot_changes,
            transition_early_alpha,
        )

        raw_early_alpha = alert.payload.get("early_alpha")
        if not isinstance(raw_early_alpha, Mapping):
            return AlertDeliveryResult(alert=None, status=AlertDeliveryStatus.IGNORED)
        identity = _safe_display(
            raw_early_alpha.get("identity")
            or raw_early_alpha.get("early_alpha_identity")
            or raw_early_alpha.get("candidate_id")
            or raw_early_alpha.get("token_id")
            or raw_early_alpha.get("mint")
            or (f"candidate:{event.aggregate_id}" if event.aggregate_id else None),
            max_length=128,
        ) or "unknown"
        projection = build_early_alpha_projection(
            raw_early_alpha,
            identity=identity,
            correlation_id=event.correlation_id,
        )
        if projection.state is None:
            return AlertDeliveryResult(alert=None, status=AlertDeliveryStatus.IGNORED)

        latest: Alert | None = None
        lookup = getattr(self._store, "get_latest_early_alpha", None)
        if callable(lookup):
            latest = await lookup(projection.identity)
        previous_state: EarlyAlphaState | None = None
        previous_snapshot: Mapping[str, object] | None = None
        correlation_id = projection.correlation_id
        if latest is not None:
            stored_alpha = latest.payload.get("early_alpha")
            stored = stored_alpha if isinstance(stored_alpha, Mapping) else latest.payload
            raw_state = stored.get("early_alpha_state")
            if isinstance(raw_state, str):
                previous_state = EarlyAlphaState(raw_state)
            stored_snapshot = stored.get("early_alpha_snapshot")
            if isinstance(stored_snapshot, Mapping):
                previous_snapshot = stored_snapshot
            stored_correlation = stored.get("early_alpha_correlation_id")
            if isinstance(stored_correlation, str) and stored_correlation:
                correlation_id = stored_correlation

        risk_resolved = projection.risk_gates == "PASS"
        try:
            transition = transition_early_alpha(
                previous_state,
                projection.state,
                material_change=projection.material_change,
                risk_conflict_resolved=risk_resolved,
            )
        except ValueError:
            emit_counter(self._telemetry, "early_alpha_alert_deduped")
            return AlertDeliveryResult(alert=None, status=AlertDeliveryStatus.IGNORED)

        if transition is None:
            if latest is not None and latest.state is AlertState.FAILED:
                context = ProviderRequestContext(
                    correlation_id=correlation_id,
                    requested_at=event.ingested_at,
                )
                try:
                    return await self.deliver(latest, context=context)
                except Exception:
                    emit_counter(self._telemetry, "early_alpha_alert_delivery_failure")
                    raise
            emit_counter(self._telemetry, "early_alpha_alert_deduped")
            return AlertDeliveryResult(
                alert=latest,
                status=(
                    AlertDeliveryStatus.DEDUPLICATED
                    if latest is not None
                    else AlertDeliveryStatus.IGNORED
                ),
            )

        current_snapshot = dict(projection.snapshot)
        changes = snapshot_changes(previous_snapshot, current_snapshot)
        payload = dict(projection.payload)
        payload["changes"] = changes
        payload["early_alpha_snapshot"] = current_snapshot
        payload["early_alpha_state"] = projection.state.value
        payload["early_alpha_identity"] = projection.identity
        payload["early_alpha_correlation_id"] = correlation_id
        payload["early_alpha_transition"] = {
            "previous": None if previous_state is None else previous_state.value,
            "current": projection.state.value,
        }
        payload["early_alpha_fingerprint"] = evidence_fingerprint(
            current_snapshot,
            version=projection.evidence_version,
            config_hash=projection.config_hash,
        )
        alert = replace(
            alert,
            payload={"early_alpha": payload},
            dedupe_key=(
                f"early-alpha:{projection.identity}:"
                f"{previous_state.value if previous_state else 'INITIAL'}-to-"
                f"{projection.state.value}:"
                f"{projection.evidence_version}:{payload['early_alpha_fingerprint']}"
            ),
            severity=(
                AlertSeverity.CRITICAL
                if projection.state in {EarlyAlphaState.INVALIDATED, EarlyAlphaState.CONFLICT}
                else AlertSeverity.WARNING
                if projection.state is EarlyAlphaState.DEGRADED
                else AlertSeverity.INFO
            ),
        )
        emit_counter(
            self._telemetry,
            "early_alpha_alert_created"
            if previous_state is None
            else "early_alpha_alert_followup",
        )
        emit_counter(
            self._telemetry,
            f"early_alpha_alert_{projection.state.value.lower()}",
        )
        context = ProviderRequestContext(
            correlation_id=correlation_id,
            requested_at=event.ingested_at,
        )
        try:
            return await self.deliver(alert, context=context)
        except Exception:
            emit_counter(self._telemetry, "early_alpha_alert_delivery_failure")
            raise

    async def deliver(
        self,
        alert: Alert,
        *,
        context: ProviderRequestContext,
    ) -> AlertDeliveryResult:
        if not isinstance(alert, Alert):
            raise TypeError("alert must be an Alert")
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        now = ensure_utc(self._clock(), "now")
        existing = await self._store.get_by_dedupe_key(alert.dedupe_key)
        if existing is not None:
            if existing.state is AlertState.DELIVERED:
                return AlertDeliveryResult(
                    alert=existing,
                    status=AlertDeliveryStatus.DEDUPLICATED,
                )
            if existing.state is AlertState.SUPPRESSED:
                return AlertDeliveryResult(
                    alert=existing,
                    status=AlertDeliveryStatus.SUPPRESSED,
                )
            alert = existing
        else:
            alert = _set_alert_timing(alert, _alert_timing(alert, now))
            await self._store.save(alert)

        if not isinstance(alert.payload.get(_ALERT_TIMING_KEY), Mapping):
            alert = _set_alert_timing(alert, _alert_timing(alert, now))
            await self._store.save(alert)

        if not self.policy.allows(alert.type):
            alert.mark_suppressed((ReasonCode("ALERT_TYPE_DISABLED"),))
            await self._store.save(alert)
            return AlertDeliveryResult(alert=alert, status=AlertDeliveryStatus.SUPPRESSED)

        reservation = self.limiter.reserve(self.destination, now)
        if not reservation.allowed:
            assert reservation.retry_at is not None
            raise AlertDeliveryDeferred(reservation.retry_at)

        timing_start = max(
            now,
            _payload_datetime(alert.payload, "alert_projected_at", alert.requested_at)
            or alert.requested_at,
        )
        alert = _set_alert_timing(
            alert,
            _alert_timing(alert, now, delivery_started_at=timing_start),
        )
        await self._store.save(alert)

        renderer = self.renderer
        if alert.type is AlertType.EARLY_ALPHA:
            if self.early_alpha_renderer is not None:
                renderer = self.early_alpha_renderer
            elif type(renderer) is AlertRenderer:
                from .early_alpha_alert import EarlyAlphaAlertRenderer

                renderer = EarlyAlphaAlertRenderer(max_length=self.policy.max_text_length)
        rendering_started = perf_counter()
        try:
            request = renderer.to_request(
                alert,
                context=context,
                destination=self.destination,
            )
        finally:
            emit_latency(
                self._telemetry,
                LatencyMetric.ALERT_RENDERING,
                round((perf_counter() - rendering_started) * 1000, 3),
                source="internal",
            )
        try:
            receipt = await self._notification.send(request)
            if not isinstance(receipt, DeliveryReceipt):
                raise TypeError("notification provider returned an invalid delivery receipt")
            if not receipt.accepted:
                raise NotificationRejected(receipt.error_class)
        except AlertDeliveryDeferred:
            raise
        except Exception:
            alert.mark_failed()
            await self._store.save(alert)
            raise
        alert = _set_alert_timing(
            alert,
            _alert_timing(
                alert,
                now,
                delivery_started_at=timing_start,
                sent_at=receipt.delivered_at,
            ),
        )
        alert.mark_delivered(receipt.delivered_at)
        await self._store.save(alert)
        return AlertDeliveryResult(
            alert=alert,
            status=AlertDeliveryStatus.DELIVERED,
            receipt=receipt,
        )


def provider_health_event(
    *,
    provider: str,
    capability: str,
    state: str,
    checked_at: datetime,
    correlation_id: str = "provider-health",
    error_class: str | None = None,
) -> EventEnvelope:
    """Build a safe health event for degradation alert projection."""

    normalized_checked_at = ensure_utc(checked_at, "checked_at")
    normalized_provider = require_text(provider, "provider", max_length=128)
    normalized_capability = require_text(capability, "capability", max_length=128)
    normalized_state = require_text(state, "state", max_length=32).upper()
    payload: dict[str, object] = {
        "provider": normalized_provider,
        "capability": normalized_capability,
        "state": normalized_state,
    }
    if error_class is not None:
        payload["error_class"] = require_text(error_class, "error_class", max_length=128)
    return EventEnvelope(
        kind="ProviderHealthChanged",
        aggregate_type="provider",
        aggregate_id=f"{normalized_provider}:{normalized_capability}",
        occurred_at=normalized_checked_at,
        observed_at=normalized_checked_at,
        ingested_at=normalized_checked_at,
        correlation_id=correlation_id,
        producer="provider-health",
        payload=payload,
        idempotency_key=(
            f"provider-health:{normalized_provider}:{normalized_capability}:"
            f"{normalized_state}:{normalized_checked_at.isoformat()}"
        ),
        reason_codes=(ReasonCode("PROVIDER_HEALTH_CHANGED"),),
    )


__all__ = [
    "ALERT_PIPELINE_VERSION",
    "AlertDeliveryDeferred",
    "AlertDeliveryResult",
    "AlertDeliveryService",
    "AlertDeliveryStatus",
    "AlertEventProjector",
    "AlertPolicy",
    "AlertRateLimitDecision",
    "AlertRateLimiter",
    "AlertRenderer",
    "AlertStore",
    "MAX_TELEGRAM_TEXT_LENGTH",
    "NotificationRejected",
    "provider_health_event",
]
