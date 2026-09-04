"""Provider-independent token authority and security-risk evaluation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from memeradar_domain import (
    Observation,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
    require_solana_address,
)
from memeradar_domain.common import ensure_utc, require_text

from .provider_contracts import RiskFinding, RiskSeverity

_MISSING = object()
_SPL_PROGRAMS = frozenset(
    {
        "spl-token",
        "spl",
        "token",
        "tokenkegqfezyinwajbnbgkpfw9ss623vq5da",
    }
)
_TOKEN_2022_PROGRAMS = frozenset({"spl-token-2022", "token-2022", "token2022"})
_SECURITY_RELEVANT_EXTENSIONS = frozenset(
    {
        "confidential_transfer",
        "default_account_state",
        "group_member_pointer",
        "group_pointer",
        "interest_bearing_config",
        "metadata_pointer",
        "pausable",
        "permanent_delegate",
        "transfer_fee_config",
        "transfer_hook",
    }
)
_AUTHORITY_STATES = frozenset({"ACTIVE", "REVOKED", "UNKNOWN", "INVALID"})


@dataclass(frozen=True, slots=True)
class TokenSecurityPolicy:
    """Versioned defaults for the deterministic token-security gate."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    risk_version: str = "token-security-v1"
    active_authority_penalty: Decimal = Decimal("30")

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(
            self,
            "risk_version",
            require_text(self.risk_version, "risk_version", max_length=64),
        )
        penalty = Decimal(str(self.active_authority_penalty))
        if penalty < 0 or penalty > 100:
            raise ValueError("active_authority_penalty must be between 0 and 100")
        object.__setattr__(self, "active_authority_penalty", penalty)


@dataclass(frozen=True, slots=True)
class _Authority:
    state: str
    address: str | None


def _authority(value: object, field: str) -> _Authority:
    if value is _MISSING:
        return _Authority("UNKNOWN", None)
    if not isinstance(value, Mapping):
        return _Authority("INVALID", None)
    raw_state = value.get("state", _MISSING)
    if not isinstance(raw_state, str):
        return _Authority("INVALID", None)
    state = raw_state.strip().upper()
    if state not in _AUTHORITY_STATES:
        return _Authority("INVALID", None)
    raw_address = value.get("address")
    if state == "ACTIVE":
        if not isinstance(raw_address, str) or not raw_address.strip():
            return _Authority("INVALID", None)
        try:
            address = require_solana_address(raw_address, f"{field} address")
        except (TypeError, ValueError):
            return _Authority("INVALID", None)
        return _Authority("ACTIVE", address)
    if raw_address is not None:
        return _Authority("INVALID", None)
    return _Authority(state, None)


def _program(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _SPL_PROGRAMS:
        return "spl-token"
    if normalized in _TOKEN_2022_PROGRAMS or normalized.startswith("tokenz"):
        return "spl-token-2022"
    return None


def _extensions(value: object) -> tuple[str, ...] | None:
    if value is _MISSING or value is None:
        return ()
    if isinstance(value, str | bytes | bytearray) or not isinstance(value, Sequence):
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        name = item.strip().lower().replace("-", "_")
        if name not in normalized:
            normalized.append(name)
    return tuple(normalized)


def _quality_at(observation: Observation, now: datetime, ttl: timedelta) -> QualityState:
    if observation.quality_state is not QualityState.FRESH:
        return observation.quality_state
    if observation.observed_at > now:
        return QualityState.INVALID
    if now >= observation.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
    payload_mint = observation.normalized_payload.get("mint_address")
    if payload_mint is not None and payload_mint != token.mint_address:
        return False
    if observation.token_id is not None:
        return observation.token_id == token.id
    return payload_mint == token.mint_address


def _critical_fingerprint(observation: Observation) -> tuple[object, ...]:
    payload = observation.normalized_payload
    return (
        payload.get("token_program"),
        repr(payload.get("mint_authority")),
        repr(payload.get("freeze_authority")),
        repr(payload.get("token_extensions")),
        repr(payload.get("token_extensions_reported")),
    )


class TokenSecurityEvaluator:
    """Evaluate normalized authority evidence without importing providers."""

    def __init__(self, policy: TokenSecurityPolicy | None = None) -> None:
        self.policy = policy or TokenSecurityPolicy()

    def evaluate(
        self,
        candidate_id: UUID,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        security_findings: Sequence[RiskFinding] = (),
        now: datetime,
        config_hash: str,
    ) -> RiskAssessment:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        if isinstance(security_findings, str | bytes | bytearray):
            raise TypeError("security_findings must be a sequence")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")

        matched = tuple(
            observation
            for observation in observations
            if isinstance(observation, Observation)
            and observation.kind == "onchain.token_metadata"
            and _observation_matches(observation, token)
        )
        evidence_refs = self._evidence_refs(matched, security_findings)
        reasons: list[ReasonCode] = []
        hard_blocks: list[str] = []
        warnings: list[str] = []
        penalties: dict[str, Decimal] = {}

        def add_reason(code: str, *, detail: str | None = None) -> None:
            if code not in {reason.code for reason in reasons}:
                reasons.append(ReasonCode(code, detail=detail, evidence_refs=evidence_refs))

        def add_hard_block(code: str, *, detail: str | None = None) -> None:
            if code not in hard_blocks:
                hard_blocks.append(code)
            add_reason(code, detail=detail)

        def add_warning(code: str, *, detail: str | None = None) -> None:
            if code not in warnings:
                warnings.append(code)
            add_reason(code, detail=detail)

        critical_state = QualityState.UNKNOWN
        latest: Observation | None = None
        if not matched:
            add_hard_block("CRITICAL_AUTHORITY_EVIDENCE_MISSING")
        else:
            latest = max(matched, key=lambda item: (item.observed_at, item.ingested_at))
            latest_at = latest.observed_at
            same_time = tuple(item for item in matched if item.observed_at == latest_at)
            if len({_critical_fingerprint(item) for item in same_time}) > 1:
                critical_state = QualityState.CONFLICTED
                add_hard_block("CRITICAL_AUTHORITY_EVIDENCE_CONFLICT")
            else:
                critical_state = _quality_at(latest, checked_at, self.policy.evidence_ttl)

            if critical_state is QualityState.STALE:
                add_hard_block("CRITICAL_EVIDENCE_STALE")
            elif critical_state is QualityState.UNKNOWN:
                add_hard_block("CRITICAL_EVIDENCE_UNKNOWN")
            elif critical_state is QualityState.INVALID:
                add_hard_block("CRITICAL_EVIDENCE_INVALID")

            if critical_state is QualityState.FRESH:
                payload_state = self._evaluate_payload(
                    latest.normalized_payload,
                    add_hard_block=add_hard_block,
                    add_warning=add_warning,
                    penalties=penalties,
                    active_authority_penalty=self.policy.active_authority_penalty,
                )
                if payload_state is not None:
                    critical_state = payload_state

        self._evaluate_provider_findings(
            security_findings,
            add_warning=add_warning,
            add_reason=add_reason,
        )

        if critical_state is not QualityState.FRESH:
            disposition = RiskDisposition.UNKNOWN
            confidence = Decimal("0")
        elif hard_blocks:
            disposition = RiskDisposition.BLOCK
            confidence = Decimal("0.85")
        elif warnings:
            disposition = RiskDisposition.WARN
            confidence = Decimal("0.65")
        else:
            disposition = RiskDisposition.PASS
            confidence = Decimal("1")
            add_reason("TOKEN_SECURITY_EVALUATED")

        as_of = latest.observed_at if latest is not None else checked_at
        expires_at = as_of + self.policy.evidence_ttl
        return RiskAssessment(
            candidate_id=candidate_id,
            as_of=as_of,
            expires_at=expires_at,
            risk_version=self.policy.risk_version,
            disposition=disposition,
            hard_blocks=tuple(hard_blocks),
            warnings=tuple(warnings),
            penalties=penalties,
            evidence_refs=evidence_refs,
            reason_codes=tuple(reasons),
            confidence=confidence,
            config_hash=normalized_config_hash,
            critical_evidence_state=critical_state,
        )

    @staticmethod
    def _evidence_refs(
        observations: Sequence[Observation],
        findings: Sequence[RiskFinding],
    ) -> tuple[str, ...]:
        refs: list[str] = []
        for item in (*observations, *findings):
            if isinstance(item, Observation):
                candidates: tuple[str, ...] = (item.provenance.source_id,)
            elif isinstance(item, RiskFinding):
                candidates = (item.provenance.source_id, *item.evidence_refs)
            else:
                raise TypeError("evidence inputs must be normalized observations/findings")
            for reference in candidates:
                if reference not in refs:
                    refs.append(reference)
        return tuple(refs)

    @staticmethod
    def _evaluate_payload(
        payload: Mapping[str, object],
        *,
        add_hard_block: Callable[..., None],
        add_warning: Callable[..., None],
        penalties: dict[str, Decimal],
        active_authority_penalty: Decimal,
    ) -> QualityState | None:
        hard_block = add_hard_block
        warning = add_warning
        program = _program(payload.get("token_program", _MISSING))
        if program is None:
            hard_block("TOKEN_PROGRAM_UNKNOWN")
            return QualityState.UNKNOWN

        payload_state: QualityState | None = None

        authorities = (
            ("mint_authority", "MINT_AUTHORITY_ACTIVE"),
            ("freeze_authority", "FREEZE_AUTHORITY_ACTIVE"),
        )
        for field, reason in authorities:
            value = _authority(payload.get(field, _MISSING), field)
            if value.state == "ACTIVE":
                hard_block(reason)
                penalties[field] = active_authority_penalty
            elif value.state == "UNKNOWN":
                hard_block(f"{field.upper()}_UNKNOWN")
                payload_state = QualityState.UNKNOWN
            elif value.state == "INVALID":
                hard_block(f"{field.upper()}_INVALID")
                payload_state = QualityState.INVALID

        if program != "spl-token-2022":
            return payload_state
        raw_reported = payload.get("token_extensions_reported", _MISSING)
        if raw_reported is not _MISSING and not isinstance(raw_reported, bool):
            hard_block("CRITICAL_TOKEN_2022_METADATA_INVALID")
            return QualityState.INVALID
        raw_extensions = payload.get("token_extensions", _MISSING)
        normalized_extensions = _extensions(raw_extensions)
        if normalized_extensions is None:
            hard_block("CRITICAL_TOKEN_2022_METADATA_INVALID")
            return QualityState.INVALID
        if raw_extensions is _MISSING or payload.get("token_extensions_reported") is False:
            warning(
                "TOKEN_2022_EXTENSIONS_NOT_REPORTED",
                detail="Token-2022 extension metadata was not reported by the source",
            )
        warning("TOKEN_2022_PROGRAM")
        if _SECURITY_RELEVANT_EXTENSIONS.intersection(normalized_extensions):
            warning(
                "TOKEN_2022_SECURITY_EXTENSION",
                detail=",".join(
                    sorted(_SECURITY_RELEVANT_EXTENSIONS.intersection(normalized_extensions))
                ),
            )
        return payload_state

    @staticmethod
    def _evaluate_provider_findings(
        findings: Sequence[RiskFinding],
        *,
        add_warning: Callable[..., None],
        add_reason: Callable[..., None],
    ) -> None:
        warning = add_warning
        reason = add_reason
        for finding in findings:
            if not isinstance(finding, RiskFinding):
                raise TypeError("security_findings must contain RiskFinding values")
            if finding.code in {"VERIFICATION_STATUS", "VERIFIED", "VERIFICATION"}:
                reason("VERIFICATION_STATUS_INFORMATIONAL", detail=finding.detail)
                continue
            if finding.severity is RiskSeverity.INFO:
                reason(finding.code, detail=finding.detail)
                continue
            if finding.severity is RiskSeverity.BLOCK:
                warning(
                    "RUGCHECK_UNCORROBORATED_BLOCK",
                    detail=finding.code,
                )
            elif finding.severity is RiskSeverity.WARN:
                warning("RUGCHECK_WARNING", detail=finding.code)
            else:
                warning("RUGCHECK_EVIDENCE_UNKNOWN", detail=finding.code)
            if finding.quality_state is not QualityState.FRESH:
                warning(
                    f"RUGCHECK_EVIDENCE_{finding.quality_state.value}",
                    detail=finding.code,
                )


def evaluate_token_security(
    candidate_id: UUID,
    token: TokenIdentity,
    observations: Sequence[Observation],
    *,
    security_findings: Sequence[RiskFinding] = (),
    now: datetime,
    config_hash: str,
    policy: TokenSecurityPolicy | None = None,
) -> RiskAssessment:
    """Convenience function for callers that do not need to retain an evaluator."""

    return TokenSecurityEvaluator(policy).evaluate(
        candidate_id,
        token,
        observations,
        security_findings=security_findings,
        now=now,
        config_hash=config_hash,
    )


__all__ = [
    "TokenSecurityEvaluator",
    "TokenSecurityPolicy",
    "evaluate_token_security",
]
