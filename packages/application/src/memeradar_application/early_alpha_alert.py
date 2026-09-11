"""Provider-independent Early Alpha alert projection and presentation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from memeradar_domain import Alert

from .alert_pipeline import (
    _URL_PATTERN,
    AlertRenderer,
    _safe_display,
    _safe_lines,
)

EARLY_ALPHA_ALERT_VERSION = "early-alpha-alert-v2"
_UNKNOWN = "UNKNOWN"


class EarlyAlphaState(str, Enum):
    NOT_CONFIRMED = "NOT_CONFIRMED"
    CONFIRMED = "CONFIRMED"
    DEGRADED = "DEGRADED"
    INVALIDATED = "INVALIDATED"
    CONFLICT = "CONFLICT"


_ALLOWED_TRANSITIONS: dict[EarlyAlphaState, frozenset[EarlyAlphaState]] = {
    EarlyAlphaState.NOT_CONFIRMED: frozenset(
        {
            EarlyAlphaState.CONFIRMED,
            EarlyAlphaState.DEGRADED,
            EarlyAlphaState.INVALIDATED,
            EarlyAlphaState.CONFLICT,
        }
    ),
    EarlyAlphaState.CONFIRMED: frozenset(
        {
            EarlyAlphaState.DEGRADED,
            EarlyAlphaState.INVALIDATED,
            EarlyAlphaState.CONFLICT,
        }
    ),
    EarlyAlphaState.DEGRADED: frozenset(
        {EarlyAlphaState.CONFIRMED, EarlyAlphaState.INVALIDATED, EarlyAlphaState.CONFLICT}
    ),
    EarlyAlphaState.CONFLICT: frozenset(
        {EarlyAlphaState.DEGRADED, EarlyAlphaState.INVALIDATED, EarlyAlphaState.CONFIRMED}
    ),
    EarlyAlphaState.INVALIDATED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class EarlyAlphaTransition:
    previous: EarlyAlphaState | None
    current: EarlyAlphaState
    material_change: bool = False


@dataclass(frozen=True, slots=True)
class EarlyAlphaProjection:
    identity: str
    state: EarlyAlphaState | None
    risk_gates: str
    evidence_version: str
    config_hash: str
    material_change: bool
    correlation_id: str
    snapshot: Mapping[str, object]
    payload: Mapping[str, object]


def transition_early_alpha(
    previous: EarlyAlphaState | str | None,
    current: EarlyAlphaState | str,
    *,
    material_change: bool = False,
    risk_conflict_resolved: bool = False,
) -> EarlyAlphaTransition | None:
    """Validate one alert transition; return None for a non-material repeat."""

    normalized_current = EarlyAlphaState(current)
    normalized_previous = None if previous is None else EarlyAlphaState(previous)
    if not isinstance(material_change, bool) or not isinstance(risk_conflict_resolved, bool):
        raise TypeError("transition flags must be boolean")
    if normalized_previous is None:
        return EarlyAlphaTransition(None, normalized_current, material_change)
    if normalized_previous is normalized_current:
        return (
            EarlyAlphaTransition(normalized_previous, normalized_current, True)
            if material_change
            else None
        )
    if normalized_current not in _ALLOWED_TRANSITIONS[normalized_previous]:
        raise ValueError(
            f"invalid early alpha transition: {normalized_previous.value} -> "
            f"{normalized_current.value}"
        )
    if (
        normalized_previous is EarlyAlphaState.CONFLICT
        and normalized_current is EarlyAlphaState.CONFIRMED
        and not risk_conflict_resolved
    ):
        raise ValueError("risk conflict must be resolved before confirmation")
    return EarlyAlphaTransition(normalized_previous, normalized_current, material_change)


_CONFIRMATION_TITLES = {
    EarlyAlphaState.NOT_CONFIRMED: "🚨 EXTREME EARLY ALPHA / NOT CONFIRMED",
    EarlyAlphaState.CONFIRMED: "✅ CONFIRMED",
    EarlyAlphaState.DEGRADED: "⚠️ DEGRADED",
    EarlyAlphaState.INVALIDATED: "❌ INVALIDATED",
    EarlyAlphaState.CONFLICT: "⚠️ ALPHA CONFIRMATION CONFLICT",
}

_UNSAFE_RISK_GATES = frozenset(
    {
        "BLOCK",
        "BLOCKED",
        "BLOCKED_EXTERNAL",
        "FAIL",
        "FAILED",
        "UNKNOWN",
        "STALE",
        "CONFLICTED",
        "INVALID",
        "UNVERIFIED",
        "DEGRADED",
        "INCOMPATIBLE",
        "MISSING",
        "UNAVAILABLE",
    }
)

_SENSITIVE_EVIDENCE_KEY = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|"
    r"client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|"
    r"session[_ -]?token)"
)

_CHANGE_FIELDS = (
    ("smart_wallets", "Smart Wallets"),
    ("holders", "Holders"),
    ("graduation", "Graduation"),
    ("volume_acceleration", "Volume Accel"),
    ("alpha_score", "AlphaScore"),
    ("confidence", "Confidence"),
)

_SNAPSHOT_ALIASES: dict[str, tuple[str, ...]] = {
    "smart_wallets": ("smart_wallets", "proven_smart_wallets", "smart_wallet_count"),
    "holders": ("holders", "unique_holders", "holder_count", "total_holders"),
    "graduation": ("graduation", "graduation_state", "lifecycle_state"),
    "volume_acceleration": (
        "volume_acceleration",
        "volume_acceleration_x",
        "dex_volume_acceleration",
    ),
    "alpha_score": ("alpha_score", "score", "early_score"),
    "confidence": ("confidence", "early_score_confidence", "evidence_confidence"),
}

_ALLOWED_EVIDENCE_KEYS = frozenset(
    {
        "identity",
        "token_id",
        "mint",
        "token",
        "symbol",
        "name",
        "chain",
        "venue",
        "age",
        "launch_age_seconds",
        "market_cap_usd",
        "alpha_score",
        "confidence",
        "risk",
        "risk_disposition",
        "risk_gates",
        "risk_quality_state",
        "state",
        "confirmation_state",
        "graduation",
        "volume_acceleration",
        "liquidity",
        "liquidity_usd",
        "sellability",
        "hard_blocks",
        "hard_block_reasons",
        "evidence_refs",
        "reason_codes",
        "freshness",
        "quality_state",
        "event_time_quality",
        "provenance",
        "material_change",
        "evidence_changed",
        "evidence_version",
        "version",
        "config_hash",
        "cohort_similarity",
        "changes",
        "snapshot",
        "top_positive_evidence",
        "top_risk_evidence",
        "reply_to_message_id",
    }
    | frozenset(key for aliases in _SNAPSHOT_ALIASES.values() for key in aliases)
)


def _display(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    return _safe_display(value, max_length=256) or _UNKNOWN


def _normal_state(value: object) -> EarlyAlphaState | None:
    if value is None:
        return None
    normalized = _display(value).upper().replace("-", "_").replace(" ", "_")
    try:
        return EarlyAlphaState(normalized)
    except ValueError:
        return None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _risk_gates(early_alpha: Mapping[str, object]) -> str:
    direct = early_alpha.get("risk_gates")
    direct_quality: object = None
    if isinstance(direct, Mapping):
        direct_quality = direct.get("quality_state") or direct.get("quality")
        direct = direct.get("state") or direct.get("disposition")
    direct_state = _display(direct).upper() if direct is not None else ""
    disposition = _display(
        early_alpha.get("risk_disposition") or early_alpha.get("risk")
    ).upper()
    quality_source = direct_quality
    if quality_source is None:
        quality_source = early_alpha.get("risk_quality_state")
    quality = _display(quality_source).upper() if quality_source is not None else ""
    blocks = early_alpha.get("hard_blocks") or early_alpha.get("hard_block_reasons")
    if quality in _UNSAFE_RISK_GATES:
        return quality
    if isinstance(blocks, list | tuple) and blocks:
        return "BLOCK"
    if direct_state in _UNSAFE_RISK_GATES:
        return direct_state
    if disposition in {"BLOCK", "BLOCKED", "FAIL", "FAILED"}:
        return "BLOCK"
    if direct_state == "PASS":
        if direct_quality is None and "risk_quality_state" not in early_alpha:
            return "PASS"
        return "PASS" if quality == "FRESH" else _UNKNOWN
    if disposition == "PASS" and quality in {"", _UNKNOWN, "FRESH"}:
        return "PASS" if quality == "FRESH" else _UNKNOWN
    if direct_state in {"WARN", "WARNING", "DEGRADED"}:
        return "DEGRADED"
    if disposition in {"WARN", "WARNING", "DEGRADED"}:
        return "DEGRADED"
    return _UNKNOWN


def resolved_early_alpha_state(early_alpha: Mapping[str, object]) -> EarlyAlphaState | None:
    """Map canonical confirmation plus canonical risk quality to display state."""

    state = _normal_state(
        early_alpha.get("state")
        or early_alpha.get("confirmation_state")
        or early_alpha.get("alpha_state")
    )
    if state is EarlyAlphaState.CONFIRMED and _risk_gates(early_alpha) in _UNSAFE_RISK_GATES:
        return EarlyAlphaState.CONFLICT
    return state


def _safe_evidence(value: object, *, depth: int = 0) -> object:
    if depth > 2:
        return _UNKNOWN
    if value is None or isinstance(value, bool | int | float | str):
        return _safe_display(value, max_length=256) if isinstance(value, str) else value
    if isinstance(value, Mapping):
        return {
            str(key)[:64]: _safe_evidence(item, depth=depth + 1)
            for key, item in list(value.items())[:32]
            if not _SENSITIVE_EVIDENCE_KEY.search(str(key))
            and (str(key) in _ALLOWED_EVIDENCE_KEYS or depth > 0)
        }
    if isinstance(value, list | tuple):
        return [_safe_evidence(item, depth=depth + 1) for item in value[:32]]
    return _safe_display(value, max_length=256)


def canonical_snapshot(early_alpha: Mapping[str, object]) -> dict[str, object]:
    nested = _mapping(early_alpha.get("snapshot"))
    snapshot: dict[str, object] = {}
    for name, aliases in _SNAPSHOT_ALIASES.items():
        value: object = None
        for source in (nested, early_alpha):
            for alias in aliases:
                if source.get(alias) is not None:
                    value = source[alias]
                    break
            if value is not None:
                break
        snapshot[name] = _safe_evidence(value) if value is not None else _UNKNOWN
    for name in _SNAPSHOT_ALIASES:
        change = _mapping(_mapping(early_alpha.get("changes")).get(name))
        if change.get("current") is not None:
            snapshot[name] = _safe_evidence(change["current"])
    return snapshot


def snapshot_changes(
    previous: Mapping[str, object] | None,
    current: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Build bounded before/now values from persisted/current projections."""

    previous_values = previous or {}
    result: dict[str, dict[str, object]] = {}
    for name, _label in _CHANGE_FIELDS:
        if name not in current:
            continue
        result[name] = {
            "previous": previous_values.get(name, _UNKNOWN),
            "current": current[name],
        }
    return result


def evidence_fingerprint(snapshot: Mapping[str, object], *, version: str, config_hash: str) -> str:
    material = json.dumps(
        {"snapshot": dict(snapshot), "version": version, "config_hash": config_hash},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(material.encode()).hexdigest()[:24]


def build_early_alpha_projection(
    early_alpha: Mapping[str, object],
    *,
    identity: str,
    correlation_id: str,
) -> EarlyAlphaProjection:
    """Normalize existing evidence fields without calculating score or risk."""

    normalized_identity = _safe_display(identity, max_length=128) or "unknown"
    normalized_correlation = _safe_display(correlation_id, max_length=128) or "unknown"
    state = resolved_early_alpha_state(early_alpha)
    evidence_version = _safe_display(
        early_alpha.get("evidence_version")
        or early_alpha.get("version")
        or EARLY_ALPHA_ALERT_VERSION,
        max_length=64,
    ) or EARLY_ALPHA_ALERT_VERSION
    config_hash = _safe_display(early_alpha.get("config_hash"), max_length=128) or "unknown"
    material_change = bool(
        early_alpha.get("material_change") is True or early_alpha.get("evidence_changed") is True
    )
    current_snapshot = canonical_snapshot(early_alpha)
    safe_payload = _safe_evidence(early_alpha)
    if not isinstance(safe_payload, dict):
        safe_payload = {}
    safe_payload["state"] = None if state is None else state.value
    safe_payload["risk_gates"] = _risk_gates(early_alpha)
    safe_payload["early_alpha_identity"] = normalized_identity
    safe_payload["evidence_version"] = evidence_version
    safe_payload["config_hash"] = config_hash
    if "cohort_similarity" not in safe_payload:
        research = _mapping(early_alpha.get("upside_research"))
        if research:
            safe_payload["cohort_similarity"] = _safe_evidence(research)
    return EarlyAlphaProjection(
        identity=normalized_identity,
        state=state,
        risk_gates=_risk_gates(early_alpha),
        evidence_version=evidence_version,
        config_hash=config_hash,
        material_change=material_change,
        correlation_id=normalized_correlation,
        snapshot=current_snapshot,
        payload=safe_payload,
    )


def _early_alpha_payload(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    value = payload.get("early_alpha")
    if isinstance(value, Mapping):
        return value
    return payload if "early_alpha" in payload else None


def _append_value(lines: list[str], label: str, value: object) -> None:
    lines.append(f"{label}: {_display(value)}")


def _append_changes(lines: list[str], early_alpha: Mapping[str, object]) -> None:
    changes = _mapping(early_alpha.get("changes"))
    if not changes:
        return
    rendered: list[str] = []
    for key, label in _CHANGE_FIELDS:
        value = _mapping(changes.get(key))
        if not value:
            continue
        rendered.append(
            f"{label}: {_display(value.get('previous'))} → "
            f"{_display(value.get('current'))}"
        )
    if rendered:
        lines.append("EVIDENCE BEFORE → NOW")
        lines.extend(rendered)


def _append_cohort_similarity(lines: list[str], early_alpha: Mapping[str, object]) -> None:
    cohorts = _mapping(early_alpha.get("cohort_similarity"))
    if not cohorts:
        cohorts = _mapping(early_alpha.get("upside_research"))
    if not cohorts:
        return
    lines.append("COHORT SIMILARITY")
    for key in ("10x", "50x", "100x"):
        if key in cohorts:
            lines.append(f"{key}: {_display(cohorts[key])}")


def _append_tail(lines: list[str], alert: Alert, early_alpha: Mapping[str, object]) -> None:
    for label, key in (
        ("Positive evidence", "top_positive_evidence"),
        ("Risk evidence", "top_risk_evidence"),
    ):
        values = _safe_lines(early_alpha.get(key, alert.payload.get(key)), max_items=4)
        if values:
            lines.append(f"{label}: " + "; ".join(values))
    reasons = list(dict.fromkeys(reason.code for reason in alert.reason_codes))
    reasons.extend(
        reason for reason in _safe_lines(early_alpha.get("reason_codes"), max_items=4)
        if reason not in reasons
    )
    reasons = reasons[:4]
    if reasons:
        lines.append("Reasons: " + ", ".join(reasons))
    hard_blocks = _safe_lines(
        early_alpha.get("hard_blocks") or early_alpha.get("hard_block_reasons"),
        max_items=4,
    )
    if hard_blocks:
        lines.append("Hard blocks: " + "; ".join(hard_blocks))
    references: list[str] = []
    for raw in (alert.payload.get("evidence_refs"), early_alpha.get("evidence_refs")):
        references.extend(_safe_lines(raw, max_items=8))
    references.extend(
        _safe_display(reference, max_length=256)
        for reason in alert.reason_codes
        for reference in reason.evidence_refs
    )
    if references:
        lines.append("Evidence: " + ", ".join(list(dict.fromkeys(references))[:8]))
    dashboard_url = _safe_display(alert.payload.get("dashboard_url"), max_length=512)
    if dashboard_url and _URL_PATTERN.fullmatch(dashboard_url):
        lines.append(f"Dashboard: {dashboard_url}")
    correlation_id = _safe_display(
        early_alpha.get("early_alpha_correlation_id")
        or alert.payload.get("early_alpha_correlation_id"),
        max_length=128,
    )
    if correlation_id:
        lines.append(f"Correlation: {correlation_id}")
    lines.append("Auto execution: LOCKED")


class EarlyAlphaAlertRenderer(AlertRenderer):
    """Render only canonical Early Alpha evidence; ordinary alerts fall back."""

    def render(self, alert: Alert) -> str:
        if not isinstance(alert, Alert):
            raise TypeError("alert must be an Alert")
        early_alpha = _early_alpha_payload(alert.payload)
        if early_alpha is None:
            return super().render(alert)
        state = resolved_early_alpha_state(early_alpha)
        risk_gates = _risk_gates(early_alpha)
        title = (
            _CONFIRMATION_TITLES.get(state, "⚠️ EARLY ALPHA / STATUS UNKNOWN")
            if state is not None
            else "⚠️ EARLY ALPHA / STATUS UNKNOWN"
        )
        lines = [title, ""]
        snapshot = canonical_snapshot(early_alpha)
        for label, key in (
            ("Token", "token"),
            ("Chain", "chain"),
            ("Age", "age"),
            ("Market cap", "market_cap_usd"),
            ("AlphaScore", "alpha_score"),
            ("Confidence", "confidence"),
            ("Risk", "risk"),
            ("Smart Wallets", "smart_wallets"),
            ("Holders", "holders"),
            ("Graduation", "graduation"),
            ("Volume Accel", "volume_acceleration"),
            ("Liquidity", "liquidity"),
            ("Sellability", "sellability"),
            ("Freshness", "freshness"),
            ("Event time quality", "event_time_quality"),
        ):
            value = early_alpha.get(key, snapshot.get(key, _UNKNOWN))
            if key == "token" and value == _UNKNOWN:
                value = next(
                    (
                        early_alpha.get(alias)
                        for alias in ("symbol", "name", "token_id", "mint")
                        if early_alpha.get(alias)
                    ),
                    _UNKNOWN,
                )
            if key == "risk" and value == _UNKNOWN:
                value = early_alpha.get("risk_disposition", _UNKNOWN)
            if key == "freshness" and value == _UNKNOWN:
                value = early_alpha.get("quality_state", _UNKNOWN)
            _append_value(lines, label, value)
        _append_changes(lines, early_alpha)
        _append_cohort_similarity(lines, early_alpha)
        if state is not None or risk_gates != _UNKNOWN:
            lines.append(f"State: {state.value if state else _UNKNOWN}")
            lines.append(f"Risk gates: {risk_gates}")
        if state is EarlyAlphaState.NOT_CONFIRMED:
            lines.extend(("⚠️ NOT CONFIRMED", "Awaiting additional independent evidence."))
        elif state is EarlyAlphaState.CONFLICT:
            lines.append("⚠️ Confirmation conflict: authoritative risk evidence is incompatible.")
        elif state is EarlyAlphaState.DEGRADED:
            lines.append("⚠️ Signal degraded; evidence quality requires review.")
        elif state is EarlyAlphaState.INVALIDATED:
            lines.append("❌ Signal invalidated by canonical evidence.")
        elif state is EarlyAlphaState.CONFIRMED:
            lines.append("✅ Confirmation is supported by canonical evidence and risk PASS.")
        _append_tail(lines, alert, early_alpha)
        rendered = "\n".join(_safe_display(line, max_length=self.max_length) for line in lines)
        if len(rendered) <= self.max_length:
            return rendered
        suffix = "\n[…truncated]"
        return rendered[: max(0, self.max_length - len(suffix))] + suffix


__all__ = [
    "EARLY_ALPHA_ALERT_VERSION",
    "EarlyAlphaAlertRenderer",
    "EarlyAlphaProjection",
    "EarlyAlphaState",
    "EarlyAlphaTransition",
    "build_early_alpha_projection",
    "canonical_snapshot",
    "evidence_fingerprint",
    "resolved_early_alpha_state",
    "snapshot_changes",
    "transition_early_alpha",
]
