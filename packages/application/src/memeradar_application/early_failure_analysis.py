"""Future-outcome attribution for missed winners and false positives.

This module reads immutable early snapshots and future-only labels.  It never
feeds findings back into runtime scoring or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import cast

from memeradar_domain import Observation, ReasonCode
from memeradar_domain.common import normalize_texts, require_text, to_decimal


class EvidenceAttribution(str, Enum):
    ATTRIBUTED_EVIDENCE = "ATTRIBUTED_EVIDENCE"
    SUSPECTED = "SUSPECTED"
    UNKNOWN = "UNKNOWN"


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Observation):
        return value.normalized_payload
    if isinstance(value, Mapping):
        return value
    payload = getattr(value, "normalized_payload", None)
    return payload if isinstance(payload, Mapping) else {}


def _value(value: object, *names: str) -> object | None:
    payload = _mapping(value)
    for name in names:
        if name in payload:
            return payload[name]
        attribute = getattr(value, name, None)
        if attribute is not None:
            return cast(object, attribute)
    return None


def _bool(value: object, *names: str) -> bool | None:
    candidate = _value(value, *names)
    if isinstance(candidate, bool):
        return candidate
    if isinstance(candidate, str):
        normalized = candidate.strip().lower()
        if normalized in {"true", "yes", "1", "pass", "rug", "failed"}:
            return True
        if normalized in {"false", "no", "0", "fail", "safe", "healthy"}:
            return False
    return None


def _decimal(value: object, *names: str) -> Decimal | None:
    candidate = _value(value, *names)
    if candidate is None or isinstance(candidate, bool):
        return None
    try:
        return to_decimal(candidate, "outcome_multiple")
    except (TypeError, ValueError):
        return None


def _codes(value: object) -> tuple[str, ...]:
    candidate = _value(value, "reason_codes", "reason_code_values")
    if isinstance(candidate, str):
        return (candidate,)
    if not isinstance(candidate, Sequence):
        return ()
    result: list[str] = []
    for item in candidate:
        code = item.code if isinstance(item, ReasonCode) else str(item)
        if code not in result:
            result.append(code)
    return tuple(result)


def _refs(value: object) -> tuple[str, ...]:
    candidate = _value(value, "evidence_refs")
    if isinstance(candidate, str):
        candidate = (candidate,)
    if not isinstance(candidate, Sequence):
        return ()
    return normalize_texts(tuple(str(item) for item in candidate), "evidence_refs")


def _states(snapshots: Sequence[object]) -> tuple[tuple[str, object], ...]:
    values: list[tuple[str, object]] = []
    for snapshot in snapshots:
        raw_state = _value(snapshot, "state", "stage")
        if raw_state is None:
            continue
        state = getattr(raw_state, "value", raw_state)
        values.append((str(state).upper(), snapshot))
    return tuple(values)


def _outcome_multiple(outcome: object) -> Decimal | None:
    direct = _decimal(outcome, "executable_peak_multiple", "executable_multiple")
    if direct is not None:
        return direct
    horizons = getattr(outcome, "horizons", None)
    if isinstance(horizons, Mapping):
        values = tuple(
            value for value in (_outcome_multiple(item) for item in horizons.values())
            if value is not None
        )
        return max(values) if values else None
    return None


def _outcome_flag(outcome: object, *names: str) -> bool | None:
    direct = _bool(outcome, *names)
    if direct is not None:
        return direct
    horizons = getattr(outcome, "horizons", None)
    if isinstance(horizons, Mapping):
        values = [_outcome_flag(value, *names) for value in horizons.values()]
        known = [value for value in values if value is not None]
        return any(known) if known else None
    return None


def _finding_refs(*values: object) -> tuple[str, ...]:
    refs: list[str] = []
    for value in values:
        for ref in _refs(value):
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _reason_tuple(codes: Sequence[str]) -> tuple[ReasonCode, ...]:
    return tuple(ReasonCode(code) for code in dict.fromkeys(codes))


@dataclass(frozen=True, slots=True)
class MissedWinnerFinding:
    token_key: str
    threshold_multiple: Decimal
    reason_codes: tuple[ReasonCode, ...]
    attribution: EvidenceAttribution
    explanation: str
    evidence_refs: tuple[str, ...]
    stage_reached: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_key", require_text(self.token_key, "token_key"))
        object.__setattr__(
            self,
            "threshold_multiple",
            to_decimal(self.threshold_multiple, "threshold_multiple"),
        )
        if self.threshold_multiple <= 1:
            raise ValueError("threshold_multiple must be greater than one")
        object.__setattr__(
            self,
            "reason_codes",
            _reason_tuple(tuple(code.code for code in self.reason_codes)),
        )
        object.__setattr__(self, "attribution", EvidenceAttribution(self.attribution))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "token_key": self.token_key,
            "threshold_multiple": str(self.threshold_multiple),
            "reason_codes": [reason.code for reason in self.reason_codes],
            "attribution": self.attribution.value,
            "explanation": self.explanation,
            "evidence_refs": list(self.evidence_refs),
            "stage_reached": self.stage_reached,
        }


@dataclass(frozen=True, slots=True)
class FalsePositiveFinding:
    token_key: str
    stage: str
    reason_codes: tuple[ReasonCode, ...]
    attribution: EvidenceAttribution
    explanation: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_key", require_text(self.token_key, "token_key"))
        object.__setattr__(self, "stage", require_text(self.stage, "stage").upper())
        object.__setattr__(
            self,
            "reason_codes",
            _reason_tuple(tuple(code.code for code in self.reason_codes)),
        )
        object.__setattr__(self, "attribution", EvidenceAttribution(self.attribution))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "token_key": self.token_key,
            "stage": self.stage,
            "reason_codes": [reason.code for reason in self.reason_codes],
            "attribution": self.attribution.value,
            "explanation": self.explanation,
            "evidence_refs": list(self.evidence_refs),
        }


class MissedWinnerAnalyzer:
    """Explain why an executable future winner lacked an early alert."""

    def __init__(
        self,
        *,
        thresholds: Sequence[Decimal] = (
            Decimal("10"),
            Decimal("20"),
            Decimal("50"),
            Decimal("100"),
        ),
        max_alert_age_seconds: Decimal = Decimal("300"),
        provider_delay_ms: Decimal = Decimal("30000"),
    ) -> None:
        self.thresholds = tuple(sorted(to_decimal(value, "threshold") for value in thresholds))
        self.max_alert_age_seconds = to_decimal(max_alert_age_seconds, "max_alert_age_seconds")
        self.provider_delay_ms = to_decimal(provider_delay_ms, "provider_delay_ms")

    def analyze(
        self,
        token_key: str,
        outcome: object,
        *,
        stage_snapshots: Sequence[object] = (),
        telegram_timestamps: Mapping[str, object] | None = None,
        provider_latency_ms: Mapping[str, object] | None = None,
        stream_gap: bool = False,
    ) -> tuple[MissedWinnerFinding, ...]:
        multiple = _outcome_multiple(outcome)
        if multiple is None:
            return ()
        states = _states(stage_snapshots)
        state_names = {state for state, _ in states}
        timestamps = telegram_timestamps or {}
        first_alert_age = _decimal(timestamps, "telegram_alert_age_seconds", "alert_age_seconds")
        first_alert_at = timestamps.get("first_telegram_alert_at")
        alerted = first_alert_age is not None or first_alert_at is not None
        if not alerted:
            for _state, snapshot in states:
                if _value(snapshot, "first_telegram_alert_at", "telegram_alert_at") is not None:
                    alerted = True
                    break
        latency = provider_latency_ms or {}
        delayed_provider = any(
            (value := _decimal(latency, key)) is not None and value > self.provider_delay_ms
            for key in ("provider_to_ingestion_ms", "provider_to_alert_ms", "chain_to_alert_ms")
        )
        findings: list[MissedWinnerFinding] = []
        for threshold in self.thresholds:
            if multiple < threshold:
                continue
            codes: list[str] = []
            attribution = EvidenceAttribution.UNKNOWN
            if "DISCOVERED" not in state_names:
                codes.append("MISSED_DISCOVERY")
                attribution = EvidenceAttribution.ATTRIBUTED_EVIDENCE
            if delayed_provider:
                codes.append("PROVIDER_DELAY")
                attribution = EvidenceAttribution.ATTRIBUTED_EVIDENCE
            if stream_gap:
                codes.append("STREAM_GAP")
                attribution = EvidenceAttribution.ATTRIBUTED_EVIDENCE
            if "EARLY_WATCH" not in state_names:
                latest = states[-1][1] if states else None
                latest_codes = _codes(latest) if latest is not None else ()
                if any("CRITICAL" in code or "UNKNOWN" in code for code in latest_codes):
                    codes.append("CRITICAL_RISK_UNKNOWN")
                elif any("SCORE" in code or "LOW" in code for code in latest_codes):
                    codes.append("LOW_EARLY_SCORE")
                else:
                    codes.append("MISSING_FEATURE_EVIDENCE")
            if "RISK_REJECTED" in state_names:
                codes.append("FALSE_RISK_BLOCK")
                rejected = next(snapshot for state, snapshot in states if state == "RISK_REJECTED")
                if any("BUNDLE" in code for code in _codes(rejected)):
                    codes.append("FALSE_BUNDLE_POSITIVE")
            if (first_alert_age is None and not alerted) or (
                first_alert_age is not None and first_alert_age > self.max_alert_age_seconds
            ):
                codes.append("TELEGRAM_DELAY")
            if _bool(latency, "smart_wallet_data_late") is True:
                codes.append("SMART_WALLET_DATA_LATE")
            if _bool(latency, "creator_data_late") is True:
                codes.append("CREATOR_DATA_LATE")
            if not codes:
                continue
            if attribution is EvidenceAttribution.UNKNOWN:
                attribution = EvidenceAttribution.SUSPECTED
            stage_reached = states[-1][0] if states else None
            explanation = "; ".join(dict.fromkeys(codes)).replace("_", " ").lower()
            findings.append(
                MissedWinnerFinding(
                    token_key=token_key,
                    threshold_multiple=threshold,
                    reason_codes=_reason_tuple(codes),
                    attribution=attribution,
                    explanation=(
                        f"Executable {threshold}x outcome; early path evidence indicates "
                        f"{explanation}."
                    ),
                    evidence_refs=_finding_refs(outcome, *(snapshot for _, snapshot in states)),
                    stage_reached=stage_reached,
                )
            )
        return tuple(findings)


class FalsePositiveAnalyzer:
    """Explain evidence that preceded a failed or economically unusable setup."""

    def __init__(self, *, minimum_executable_multiple: Decimal = Decimal("2")) -> None:
        self.minimum_executable_multiple = to_decimal(
            minimum_executable_multiple,
            "minimum_executable_multiple",
        )

    def analyze(
        self,
        token_key: str,
        outcome: object,
        *,
        stage_snapshots: Sequence[object] = (),
    ) -> tuple[FalsePositiveFinding, ...]:
        multiple = _outcome_multiple(outcome)
        failure_codes: list[tuple[str, EvidenceAttribution]] = []
        explicit_flags = (
            ("rug_detected", "RUG", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
            ("rugged", "RUG", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
            ("liquidity_failure", "LIQUIDITY_FAILURE", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
            ("creator_dump", "CREATOR_DUMP", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
            ("holder_dump", "HOLDER_CONCENTRATION", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
            ("sellability_failure", "SELLABILITY_FAILURE", EvidenceAttribution.ATTRIBUTED_EVIDENCE),
        )
        for name, code, attribution in explicit_flags:
            if _bool(outcome, name) is True:
                failure_codes.append((code, attribution))
        if multiple is None or multiple < self.minimum_executable_multiple:
            failure_codes.append(
                ("POOR_EXECUTABLE_OUTCOME", EvidenceAttribution.ATTRIBUTED_EVIDENCE)
            )
        states = _states(stage_snapshots)
        for state, snapshot in states:
            if state not in {"STRONG_SETUP", "HIGH_CONFLUENCE", "ENTRY_READY"}:
                continue
            codes = _codes(snapshot)
            payload = _mapping(snapshot)
            if (
                payload.get("wash_trading")
                or payload.get("wash_volume")
                or payload.get("circular_flow")
            ):
                failure_codes.append(("WASH_VOLUME", EvidenceAttribution.SUSPECTED))
            if payload.get("shared_funder_ratio") not in (None, 0, Decimal("0")):
                failure_codes.append(("SHARED_FUNDER_CONFLUENCE", EvidenceAttribution.SUSPECTED))
            if payload.get("creator_linked_buyer_ratio") not in (None, 0, Decimal("0")):
                failure_codes.append(("CREATOR_LINKED_BUYERS", EvidenceAttribution.SUSPECTED))
            for code in codes:
                if "BUNDLE" in code:
                    failure_codes.append(("BUNDLE", EvidenceAttribution.SUSPECTED))
                if "SNIPER" in code:
                    failure_codes.append(("SNIPER_CONCENTRATION", EvidenceAttribution.SUSPECTED))
                if "HOLDER" in code:
                    failure_codes.append(("HOLDER_CONCENTRATION", EvidenceAttribution.SUSPECTED))
                if "IMPACT" in code:
                    failure_codes.append(("PRICE_IMPACT_FAILURE", EvidenceAttribution.SUSPECTED))
            if payload.get("price_without_liquidity"):
                failure_codes.append(("LIQUIDITY_SPOOF", EvidenceAttribution.SUSPECTED))
        if not failure_codes:
            return ()
        grouped: dict[str, EvidenceAttribution] = {}
        for code, attribution in failure_codes:
            prior = grouped.get(code)
            if prior is None or attribution is EvidenceAttribution.ATTRIBUTED_EVIDENCE:
                grouped[code] = attribution
        refs = _finding_refs(outcome, *(snapshot for _, snapshot in states))
        return tuple(
            FalsePositiveFinding(
                token_key=token_key,
                stage=state,
                reason_codes=_reason_tuple(tuple(grouped)),
                attribution=(
                    EvidenceAttribution.ATTRIBUTED_EVIDENCE
                    if EvidenceAttribution.ATTRIBUTED_EVIDENCE in grouped.values()
                    else EvidenceAttribution.SUSPECTED
                ),
                explanation=(
                    "High-confidence setup later failed; suspected evidence failure: "
                    + ", ".join(code.replace("_", " ").lower() for code in grouped)
                ),
                evidence_refs=refs,
            )
            for state, _ in states
            if state in {"STRONG_SETUP", "HIGH_CONFLUENCE", "ENTRY_READY"}
        )


__all__ = [
    "EvidenceAttribution",
    "FalsePositiveAnalyzer",
    "FalsePositiveFinding",
    "MissedWinnerAnalyzer",
    "MissedWinnerFinding",
]
