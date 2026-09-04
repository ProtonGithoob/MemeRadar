"""Deterministic ultra-early candidate detection over existing evidence streams."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    EarlyCandidateTiming,
    NormalizedChainEvent,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
)
from memeradar_domain.common import ensure_utc, freeze_mapping, require_text

from .provider_contracts import DiscoveryCandidate


class DetectionAuthority(str, Enum):
    """Evidence authority used to establish a candidate's first observation."""

    DIRECT_CHAIN = "DIRECT_CHAIN"
    BIRDEYE_FALLBACK = "BIRDEYE_FALLBACK"
    UNVERIFIED = "UNVERIFIED"


_DIRECT_EVENT_TYPES = frozenset(
    {
        "launch",
        "create",
        "token_created",
        "pool_created",
        "migration",
        "graduation",
        "bonding_curve_created",
    }
)
_LOWER_QUALITY = frozenset({QualityState.STALE, QualityState.UNKNOWN, QualityState.CONFLICTED})
_DIRECT_AUTHORITIES = frozenset({DetectionAuthority.DIRECT_CHAIN, DetectionAuthority.UNVERIFIED})


def _reason(code: str, *, detail: str | None = None, refs: tuple[str, ...] = ()) -> ReasonCode:
    return ReasonCode(code, detail=detail, evidence_refs=refs)


def _candidate_id(mint_address: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:early-candidate:{mint_address}")


def _token_id(mint_address: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:early-token:{mint_address}")


def _bool_flag(payload: Mapping[str, object], *names: str) -> bool:
    return any(payload.get(name) is True for name in names)


def _quality_from_value(value: object, default: QualityState = QualityState.FRESH) -> QualityState:
    if value is None:
        return default
    try:
        return QualityState(value)
    except (TypeError, ValueError):
        return QualityState.UNKNOWN


def _is_parsed_protocol_event(event: object) -> bool:
    """Recognize the provider DTO structurally without importing a provider package."""

    return type(event).__name__ == "ParsedProtocolEvent" and all(
        hasattr(event, field_name)
        for field_name in (
            "payload",
            "venue",
            "mint_address",
            "event_type",
            "source_id",
            "occurred_at",
            "parser_version",
        )
    )


@dataclass(frozen=True, slots=True)
class EarlyDetectionResult:
    """Immutable first-seen projection produced by ``UltraEarlyDetector``."""

    candidate_id: UUID
    token_id: UUID
    mint_address: str
    event_type: str
    source_id: str
    authority: DetectionAuthority | str
    first_observed_at: datetime
    launch_at: datetime | None
    quality_state: QualityState
    timing: EarlyCandidateTiming
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    duplicate: bool = False
    is_candidate: bool = True
    fallback: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate_id and token_id must be UUID values")
        object.__setattr__(self, "mint_address", require_text(self.mint_address, "mint_address"))
        object.__setattr__(self, "event_type", require_text(self.event_type, "event_type").lower())
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))
        object.__setattr__(self, "authority", DetectionAuthority(self.authority))
        object.__setattr__(
            self,
            "first_observed_at",
            ensure_utc(self.first_observed_at, "first_observed_at"),
        )
        if self.launch_at is not None:
            object.__setattr__(self, "launch_at", ensure_utc(self.launch_at, "launch_at"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if not isinstance(self.timing, EarlyCandidateTiming):
            raise TypeError("timing must be an EarlyCandidateTiming")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if any(not isinstance(value, ReasonCode) for value in self.reason_codes):
            raise TypeError("reason_codes must contain ReasonCode values")
        object.__setattr__(self, "evidence_refs", tuple(dict.fromkeys(self.evidence_refs)))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, "metadata"))
        if not isinstance(self.duplicate, bool) or not isinstance(self.is_candidate, bool):
            raise TypeError("duplicate and is_candidate must be booleans")
        if not isinstance(self.fallback, bool):
            raise TypeError("fallback must be a boolean")

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    @property
    def first_seen_at(self) -> datetime:
        return self.first_observed_at


@dataclass(frozen=True, slots=True)
class _NormalizedDetection:
    mint_address: str
    token_id: UUID
    event_type: str
    source_id: str
    launch_at: datetime | None
    observed_at: datetime
    ingested_at: datetime
    authority: DetectionAuthority
    quality_state: QualityState
    metadata: Mapping[str, object]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    identity_key: str
    conflict_key: str


class UltraEarlyDetector:
    """Project first trustworthy launch evidence without creating parallel streams."""

    def __init__(self, *, parser_version: str = "early-detector-v1") -> None:
        self.parser_version = require_text(parser_version, "parser_version", max_length=128)
        self._results: dict[str, EarlyDetectionResult] = {}
        self._identities: dict[str, str] = {}

    @property
    def results(self) -> tuple[EarlyDetectionResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))

    def accept(
        self,
        event: object,
        *,
        observed_at: datetime,
        ingested_at: datetime,
    ) -> EarlyDetectionResult:
        """Accept one normalized launch event or listing and deduplicate by source identity."""

        normalized = self._normalize(event, observed_at=observed_at, ingested_at=ingested_at)
        existing_source = self._identities.get(normalized.identity_key)
        existing = self._results.get(normalized.mint_address)
        if existing_source is not None and existing is not None:
            return replace(existing, duplicate=True)

        if existing is None:
            result = self._build_result(normalized)
            self._results[normalized.mint_address] = result
            self._identities[normalized.identity_key] = normalized.mint_address
            return result

        reasons = list(existing.reason_codes)
        quality = existing.quality_state
        selected = existing
        if (
            normalized.conflict_key == existing.source_id
            and normalized.source_id != existing.source_id
        ):
            quality = QualityState.CONFLICTED
            reasons.append(_reason("CONFLICTING_SOURCE_IDENTITY", refs=normalized.evidence_refs))
        if (
            normalized.authority is DetectionAuthority.DIRECT_CHAIN
            and existing.authority is not DetectionAuthority.DIRECT_CHAIN
        ):
            selected = self._build_result(normalized)
            reasons.extend(selected.reason_codes)
            quality = min(
                (quality, selected.quality_state),
                key=lambda value: (
                    value not in _LOWER_QUALITY,
                    value.value,
                ),
            )
            selected = replace(selected, reason_codes=tuple(reasons), quality_state=quality)
        elif (
            existing.authority is DetectionAuthority.DIRECT_CHAIN
            and normalized.authority is DetectionAuthority.BIRDEYE_FALLBACK
        ):
            selected = replace(
                existing,
                evidence_refs=tuple(
                    dict.fromkeys((*existing.evidence_refs, *normalized.evidence_refs))
                ),
            )
        elif (
            existing.authority is DetectionAuthority.DIRECT_CHAIN
            and normalized.authority is DetectionAuthority.DIRECT_CHAIN
            and normalized.event_type != existing.event_type
        ):
            selected = replace(
                existing,
                event_type=normalized.event_type,
                metadata={**dict(existing.metadata), **dict(normalized.metadata)},
                evidence_refs=tuple(
                    dict.fromkeys((*existing.evidence_refs, *normalized.evidence_refs))
                ),
            )
        elif (
            normalized.event_type in _DIRECT_EVENT_TYPES
            and existing.event_type in _DIRECT_EVENT_TYPES
        ):
            if (
                normalized.source_id != existing.source_id
                and normalized.launch_at != existing.launch_at
            ):
                quality = QualityState.CONFLICTED
                reasons.append(_reason("CONFLICTING_LAUNCH_TIMESTAMPS"))
                selected = replace(existing, quality_state=quality, reason_codes=tuple(reasons))

        self._results[normalized.mint_address] = selected
        self._identities[normalized.identity_key] = normalized.mint_address
        return selected

    def _build_result(self, event: _NormalizedDetection) -> EarlyDetectionResult:
        candidate_id = _candidate_id(event.mint_address)
        timing = EarlyCandidateTiming(
            candidate_id=candidate_id,
            token_id=event.token_id,
            launch_at=event.launch_at,
            first_observed_at=event.observed_at,
            first_ingested_at=event.ingested_at,
            source_id=event.source_id,
            quality_state=event.quality_state,
            parser_version=self.parser_version,
            evidence_refs=event.evidence_refs,
            provenance=event.provenance,
            metadata=event.metadata,
        )
        reasons: tuple[ReasonCode, ...] = ()
        is_candidate = event.authority is DetectionAuthority.DIRECT_CHAIN
        if event.authority is DetectionAuthority.UNVERIFIED:
            reasons = (_reason("UNVERIFIED_PROTOCOL_IDENTITY", refs=event.evidence_refs),)
        if event.quality_state is not QualityState.FRESH:
            reasons = (*reasons, _reason(f"DETECTION_QUALITY_{event.quality_state.value}"))
        return EarlyDetectionResult(
            candidate_id=candidate_id,
            token_id=event.token_id,
            mint_address=event.mint_address,
            event_type=event.event_type,
            source_id=event.source_id,
            authority=event.authority,
            first_observed_at=event.observed_at,
            launch_at=event.launch_at,
            quality_state=event.quality_state,
            timing=timing,
            reason_codes=reasons,
            evidence_refs=event.evidence_refs,
            metadata=event.metadata,
            is_candidate=is_candidate,
            fallback=event.authority is DetectionAuthority.BIRDEYE_FALLBACK,
        )

    def _normalize(
        self,
        event: object,
        *,
        observed_at: datetime,
        ingested_at: datetime,
    ) -> _NormalizedDetection:
        supplied_observed = ensure_utc(observed_at, "observed_at")
        supplied_ingested = ensure_utc(ingested_at, "ingested_at")
        if supplied_ingested < supplied_observed:
            raise ValueError("ingested_at must not precede observed_at")
        if isinstance(event, DiscoveryCandidate):
            payload: Mapping[str, object] = {"provider": event.provenance.provider}
            return _NormalizedDetection(
                mint_address=event.token.mint_address,
                token_id=event.token.id,
                event_type="listing",
                source_id=event.source_id,
                launch_at=event.occurred_at,
                observed_at=supplied_observed,
                ingested_at=supplied_ingested,
                authority=DetectionAuthority.BIRDEYE_FALLBACK,
                quality_state=QualityState.FRESH,
                metadata=payload,
                provenance=(event.provenance,),
                evidence_refs=(f"source:{event.source_id}",),
                identity_key=f"{event.token.mint_address}:{event.source_id}",
                conflict_key=event.token.mint_address,
            )
        if _is_parsed_protocol_event(event):
            parsed = cast(Any, event)
            payload = cast(Mapping[str, object], parsed.payload)
            verified = _bool_flag(
                payload,
                "protocol_identity_verified",
                "verified_protocol_identity",
                "canonical_protocol_verified",
            )
            quality = QualityState.FRESH if verified else QualityState.UNKNOWN
            if parsed.event_type in {"reverted", "correction"}:
                quality = QualityState.CONFLICTED
            provenance = Provenance(
                provider=parsed.venue.value,
                source_id=parsed.source_id,
                observed_at=supplied_observed,
                parser_version=parsed.parser_version,
            )
            return _NormalizedDetection(
                mint_address=parsed.mint_address,
                token_id=_token_id(parsed.mint_address),
                event_type=str(
                    parsed.protocol_event_type.value
                    if parsed.protocol_event_type
                    else parsed.event_type
                ),
                source_id=parsed.source_id,
                launch_at=parsed.occurred_at,
                observed_at=supplied_observed,
                ingested_at=supplied_ingested,
                authority=(
                    DetectionAuthority.DIRECT_CHAIN if verified else DetectionAuthority.UNVERIFIED
                ),
                quality_state=quality,
                metadata={**dict(payload), "venue": parsed.venue.value},
                provenance=(provenance,),
                evidence_refs=(f"signature:{parsed.source_id}", f"venue:{parsed.venue.value}"),
                identity_key=f"{parsed.mint_address}:{parsed.source_id}:{parsed.event_type}",
                conflict_key=parsed.mint_address,
            )
        if isinstance(event, NormalizedChainEvent):
            payload = event.normalized_payload
            verified = _bool_flag(
                payload,
                "protocol_identity_verified",
                "verified_protocol_identity",
                "canonical_protocol_verified",
            )
            quality = QualityState(event.quality_state)
            if not verified:
                quality = QualityState.UNKNOWN
            recovery_value = (
                event.recovery_state.value
                if isinstance(event.recovery_state, Enum)
                else event.recovery_state
            )
            if recovery_value in {"RECOVERED_UNVERIFIED", "RECOVERY_FAILED"}:
                quality = QualityState.UNKNOWN
            commitment_value = (
                event.commitment.value if isinstance(event.commitment, Enum) else event.commitment
            )
            if commitment_value == "REVERTED":
                quality = QualityState.CONFLICTED
            mint = payload.get("mint_address", payload.get("mint"))
            if not isinstance(mint, str):
                raise ValueError("canonical launch event is missing mint_address")
            return _NormalizedDetection(
                mint_address=mint,
                token_id=event.token_id or _token_id(mint),
                event_type=event.event_type.lower(),
                source_id=event.signature,
                launch_at=event.occurred_at,
                observed_at=supplied_observed,
                ingested_at=supplied_ingested,
                authority=(
                    DetectionAuthority.DIRECT_CHAIN if verified else DetectionAuthority.UNVERIFIED
                ),
                quality_state=quality,
                metadata={
                    **dict(payload),
                    "slot": event.slot,
                    "signature": event.signature,
                    "transport": event.source_transport,
                    "parser_version": event.parser_version,
                    "registry_version": event.registry_version,
                },
                provenance=(event.provenance, *event.additional_provenance),
                evidence_refs=(f"slot:{event.slot}", f"signature:{event.signature}"),
                identity_key=event.canonical_identity,
                conflict_key=mint,
            )
        if isinstance(event, Observation):
            payload = event.normalized_payload
            mint = payload.get("mint_address", payload.get("mint", payload.get("token_address")))
            if not isinstance(mint, str):
                raise ValueError("observation is missing mint identity")
            provider = event.provenance.provider.lower()
            verified = _bool_flag(
                payload,
                "protocol_identity_verified",
                "verified_protocol_identity",
                "canonical_protocol_verified",
            )
            authority = (
                DetectionAuthority.BIRDEYE_FALLBACK
                if "birdeye" in provider
                else DetectionAuthority.DIRECT_CHAIN
                if verified
                else DetectionAuthority.UNVERIFIED
            )
            quality = event.quality_state
            if authority is DetectionAuthority.UNVERIFIED:
                quality = QualityState.UNKNOWN
            return _NormalizedDetection(
                mint_address=mint,
                token_id=event.token_id or _token_id(mint),
                event_type=str(payload.get("protocol_event_type", event.kind)).lower(),
                source_id=event.provenance.source_id,
                launch_at=event.occurred_at,
                observed_at=supplied_observed,
                ingested_at=supplied_ingested,
                authority=authority,
                quality_state=quality,
                metadata=payload,
                provenance=(event.provenance,),
                evidence_refs=(f"observation:{event.id}",),
                identity_key=f"{mint}:{event.provenance.source_id}:{event.kind}",
                conflict_key=mint,
            )
        raise TypeError(
            "event must be a DiscoveryCandidate, ParsedProtocolEvent, "
            "NormalizedChainEvent or Observation"
        )


__all__ = ["DetectionAuthority", "EarlyDetectionResult", "UltraEarlyDetector"]
