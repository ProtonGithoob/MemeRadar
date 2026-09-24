"""Small provider-independent composition boundary for the early-alpha path.

The service deliberately owns orchestration only.  Discovery, feature, safety,
scoring, decision, persistence and alert implementations remain in their
existing modules and ports.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_domain import (
    Alert,
    Candidate,
    CandidateState,
    EarlyDecisionState,
    EventEnvelope,
    FeatureSnapshot,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
    StateTransition,
    TokenIdentity,
)
from memeradar_domain.common import ensure_utc, freeze_mapping, normalize_texts, to_decimal

from .age_cohorts import age_cohort, liquidity_cohort
from .alert_pipeline import AlertEventProjector
from .early_decision import EarlyDecisionEngine, EarlyDecisionPolicy, EarlyDecisionResult
from .early_detection import DetectionAuthority, EarlyDetectionResult, UltraEarlyDetector
from .early_features import (
    EARLY_RUNTIME_WINDOW_DURATIONS,
    EarlyFeatureEngine,
    EarlyFeatureSnapshot,
    EarlyFeatureWindow,
)
from .early_scoring import (
    EarlyScorer,
    EarlyScoreSnapshot,
    build_asymmetric_alpha_projection,
)
from .fast_safety import FastSafetyGate, FastSafetyResult, FastSafetyStatus
from .organic_momentum import OrganicMomentumProjection

EARLY_RUNTIME_VERSION = "early-runtime-v1"
EARLY_STAGE_SNAPSHOT_KIND = "early.stage_snapshot"
_RUNTIME_NAMESPACE = "https://memeradar.local/early-runtime/"
_SNAPSHOT_IDENTITY_VERSION = "snapshot-v2"


class ObservationSink(Protocol):
    async def add(self, observation: Observation) -> object: ...


class CandidateSink(Protocol):
    async def get(self, candidate_id: UUID) -> Candidate | None: ...

    async def add(self, candidate: Candidate) -> object: ...


class EventSink(Protocol):
    async def enqueue(
        self,
        event: EventEnvelope,
        *,
        side_effect_kind: str = "domain_event",
        available_at: datetime | None = None,
    ) -> object: ...


class FeatureSnapshotSink(Protocol):
    async def add(self, snapshot: FeatureSnapshot) -> object: ...


class RiskAssessmentSink(Protocol):
    async def add(self, assessment: RiskAssessment) -> object: ...


class ScoreSnapshotSink(Protocol):
    async def add(self, snapshot: ScoreSnapshot) -> object: ...


@dataclass(frozen=True, slots=True)
class EarlyRuntimeResult:
    """All immutable outputs from one runtime checkpoint."""

    detection: EarlyDetectionResult
    candidate: Candidate
    safety: FastSafetyResult
    feature_snapshot: EarlyFeatureSnapshot
    organic_momentum: OrganicMomentumProjection
    score: EarlyScoreSnapshot
    decision: EarlyDecisionResult
    stage: CandidateState
    stage_snapshot: Observation
    lifecycle_event: EventEnvelope | None = None
    alert: Alert | None = None
    duplicate: bool = False
    latencies_ms: Mapping[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.detection, EarlyDetectionResult):
            raise TypeError("detection must be an EarlyDetectionResult")
        if not isinstance(self.candidate, Candidate):
            raise TypeError("candidate must be a Candidate")
        if not isinstance(self.feature_snapshot, EarlyFeatureSnapshot):
            raise TypeError("feature_snapshot must be an EarlyFeatureSnapshot")
        if not isinstance(self.safety, FastSafetyResult):
            raise TypeError("safety must be a FastSafetyResult")
        if not isinstance(self.organic_momentum, OrganicMomentumProjection):
            raise TypeError("organic_momentum must be an OrganicMomentumProjection")
        if not isinstance(self.score, EarlyScoreSnapshot):
            raise TypeError("score must be an EarlyScoreSnapshot")
        if not isinstance(self.decision, EarlyDecisionResult):
            raise TypeError("decision must be an EarlyDecisionResult")
        if not isinstance(self.stage_snapshot, Observation):
            raise TypeError("stage_snapshot must be an Observation")
        object.__setattr__(self, "stage", CandidateState(self.stage))
        object.__setattr__(
            self,
            "latencies_ms",
            freeze_mapping(
                {
                    str(key): to_decimal(value, f"latency {key}")
                    for key, value in self.latencies_ms.items()
                },
                "latencies_ms",
            ),
        )


def _decimal(value: object | None, name: str) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return to_decimal(value, name)
    except (TypeError, ValueError):
        return None


def _observation_for_event(event: object, token_id: UUID | None = None) -> Observation | None:
    if isinstance(event, Observation):
        return event
    converter = getattr(event, "to_observation", None)
    if not callable(converter):
        return None
    try:
        candidate = converter(token_id=token_id) if token_id is not None else converter()
    except TypeError:
        candidate = converter()
    if not isinstance(candidate, Observation):
        raise TypeError("canonical event to_observation() must return Observation")
    return candidate


def _stage_for_decision(decision: EarlyDecisionResult) -> CandidateState:
    mapping = {
        EarlyDecisionState.WATCH: CandidateState.WATCH,
        EarlyDecisionState.EARLY_WATCH: CandidateState.EARLY_WATCH,
        EarlyDecisionState.STRONG_SETUP: CandidateState.STRONG_SETUP,
        EarlyDecisionState.HIGH_CONFLUENCE: CandidateState.HIGH_CONFLUENCE,
        EarlyDecisionState.ENTRY_READY: CandidateState.ENTRY_READY,
    }
    return mapping.get(decision.state, CandidateState.RISK_REJECTED)


def _reason_values(*sources: object) -> tuple[ReasonCode, ...]:
    values: list[ReasonCode | str] = []
    for source in sources:
        raw = (
            source.get("reason_codes", ())
            if isinstance(source, Mapping)
            else getattr(source, "reason_codes", ())
        )
        if isinstance(raw, str | ReasonCode):
            raw = (raw,)
        if isinstance(raw, Sequence):
            values.extend(item for item in raw if isinstance(item, ReasonCode | str))
    normalized: list[ReasonCode] = []
    seen: set[str] = set()
    for value in values:
        reason = value if isinstance(value, ReasonCode) else ReasonCode(value)
        if reason.code not in seen:
            seen.add(reason.code)
            normalized.append(reason)
    return tuple(normalized)


def _evidence_refs(*sources: object) -> tuple[str, ...]:
    values: list[str] = []
    for source in sources:
        raw = (
            source.get("evidence_refs", ())
            if isinstance(source, Mapping)
            else getattr(source, "evidence_refs", ())
        )
        if isinstance(raw, str):
            raw = (raw,)
        if isinstance(raw, Sequence):
            values.extend(str(item) for item in raw)
    return normalize_texts(values, "evidence_refs")


def _runtime_risk_id(candidate_id: UUID, state: CandidateState) -> UUID:
    return uuid5(NAMESPACE_URL, f"{_RUNTIME_NAMESPACE}risk:{candidate_id}:{state.value}")


def _feature_values(snapshot: EarlyFeatureSnapshot) -> Mapping[str, object]:
    return {
        "windows": {
            label: {
                "duration_seconds": Decimal(str(window.duration.total_seconds())),
                "as_of": window.as_of,
                "metrics": window.metrics,
                "quality_state": window.quality_state.value,
                "reason_codes": tuple(reason.code for reason in window.reason_codes),
                "evidence_refs": window.evidence_refs,
            }
            for label, window in snapshot.windows.items()
        },
        "quality_state": snapshot.quality_state.value,
        "launch_age_seconds": snapshot.launch_age_seconds,
        "reason_codes": tuple(reason.code for reason in snapshot.reason_codes),
        "evidence_refs": snapshot.evidence_refs,
    }


def _feature_completeness(snapshot: EarlyFeatureSnapshot) -> Decimal:
    if not snapshot.windows:
        return Decimal("0")
    populated = sum(
        any(value is not None for value in window.metrics.values())
        for window in snapshot.windows.values()
    )
    return Decimal(populated) / Decimal(len(snapshot.windows))


def _feature_confidence(snapshot: EarlyFeatureSnapshot) -> Decimal:
    return {
        QualityState.FRESH: Decimal("1"),
        QualityState.STALE: Decimal("0.5"),
        QualityState.UNKNOWN: Decimal("0"),
        QualityState.CONFLICTED: Decimal("0"),
        QualityState.INVALID: Decimal("0"),
    }[snapshot.quality_state]


class EarlyRuntimeService:
    """Compose the fast launch path with append-only evidence and outbox ports."""

    def __init__(
        self,
        *,
        detector: UltraEarlyDetector | None = None,
        safety_gate: FastSafetyGate | None = None,
        feature_engine: EarlyFeatureEngine | None = None,
        scorer: EarlyScorer | None = None,
        decision_engine: EarlyDecisionEngine | None = None,
        decision_policy: EarlyDecisionPolicy | None = None,
        observation_store: ObservationSink | None = None,
        candidate_store: CandidateSink | None = None,
        feature_store: FeatureSnapshotSink | None = None,
        risk_store: RiskAssessmentSink | None = None,
        score_store: ScoreSnapshotSink | None = None,
        outbox_store: EventSink | None = None,
        git_revision: str = "unknown",
    ) -> None:
        snapshot_stores = (feature_store, risk_store, score_store)
        if any(store is not None for store in snapshot_stores) and not all(
            store is not None for store in snapshot_stores
        ):
            raise ValueError(
                "feature_store, risk_store and score_store must be configured together"
            )
        self.detector = detector or UltraEarlyDetector()
        self.safety_gate = safety_gate or FastSafetyGate()
        self.feature_engine = feature_engine or EarlyFeatureEngine(
            window_durations=EARLY_RUNTIME_WINDOW_DURATIONS
        )
        self.scorer = scorer or EarlyScorer()
        self.decision_engine = decision_engine or EarlyDecisionEngine(decision_policy)
        self.observation_store = observation_store
        self.candidate_store = candidate_store
        self.feature_store = feature_store
        self.risk_store = risk_store
        self.score_store = score_store
        self.outbox_store = outbox_store
        self.git_revision = str(git_revision)
        self._observations: dict[str, dict[UUID, Observation]] = {}
        self._checkpoints: dict[str, datetime] = {}
        self._candidates: dict[UUID, Candidate] = {}
        self._snapshots: dict[tuple[UUID, CandidateState], Observation] = {}

    async def process(
        self,
        event: object,
        *,
        observations: Sequence[Observation] = (),
        safety_evidence: Mapping[str, object] | None = None,
        score_components: Mapping[str, object] | None = None,
        confluence: object | None = None,
        social: object | None = None,
        quote: object | None = None,
        observed_at: datetime | None = None,
        ingested_at: datetime | None = None,
        as_of: datetime | None = None,
        provider_available: bool = True,
        stream_gap: bool = False,
    ) -> EarlyRuntimeResult:
        """Process one normalized event; all writes are idempotent by source key."""

        started = perf_counter()
        event_observation = _observation_for_event(event)
        fallback_time = ensure_utc(
            observed_at
            or (
                event_observation.observed_at
                if event_observation is not None
                else datetime.now(UTC)
            ),
            "observed_at",
        )
        observed_checkpoint = (
            fallback_time
            if observed_at is None
            else ensure_utc(observed_at, "observed_at")
        )
        ingested_checkpoint = ensure_utc(
            ingested_at
            or (
                event_observation.ingested_at
                if event_observation is not None
                else observed_checkpoint
            ),
            "ingested_at",
        )
        detection_started = perf_counter()
        detection = self.detector.accept(
            event,
            observed_at=observed_checkpoint,
            ingested_at=ingested_checkpoint,
        )
        normalization_ms = Decimal(str((perf_counter() - detection_started) * 1000))
        mint_key = detection.mint_address
        bucket = self._observations.setdefault(mint_key, {})
        candidate = await self._get_or_create_candidate(detection)
        incoming = list(observations)
        if event_observation is None:
            event_observation = _observation_for_event(event, detection.token_id)
        if event_observation is not None:
            incoming.append(event_observation)
        for item in incoming:
            if not isinstance(item, Observation):
                raise TypeError("observations must contain Observation values")
            bucket[item.id] = item
            await self._save_observation(item)

        checkpoint = self._checkpoint(mint_key, as_of, bucket, detection)
        feature_started = perf_counter()
        feature_snapshot = self.feature_engine.compute(
            detection.token_id,
            checkpoint,
            tuple(bucket.values()),
        )
        feature_ms = Decimal(str((perf_counter() - feature_started) * 1000))

        evidence = dict(safety_evidence or {})
        if detection.authority is not DetectionAuthority.DIRECT_CHAIN:
            evidence.setdefault("protocol_identity_verified", False)
        if not provider_available:
            evidence.setdefault("protocol_identity_verified", False)
        if stream_gap:
            evidence.setdefault("protocol_identity_verified", False)
        safety_started = perf_counter()
        safety = self.safety_gate.evaluate(evidence, confluence=confluence)
        safety_ms = Decimal(str((perf_counter() - safety_started) * 1000))
        window = self._preferred_window(feature_snapshot)
        metrics = dict(window.metrics)
        for key in (
            "bundle_risk",
            "sniper_risk",
            "creator_related_ratio",
            "coordinated_wallet_probability",
        ):
            if key in evidence:
                metrics[key] = evidence[key]
        organic = OrganicMomentumProjection.from_metrics(
            metrics,
            evidence_refs=feature_snapshot.evidence_refs,
        )
        components = self._components(metrics, safety)
        if score_components is not None:
            components.update(score_components)
        risk = self._risk_mapping(
            safety,
            provider_available=provider_available,
            stream_gap=stream_gap,
        )
        score = self.scorer.score(
            {
                "components": components,
                "as_of": checkpoint,
                "launch_age_seconds": feature_snapshot.launch_age_seconds,
            },
            risk,
            confluence=safety.to_mapping(),
            social=social,
        )
        decision_started = perf_counter()
        decision = self.decision_engine.evaluate(
            score,
            risk,
            as_of=checkpoint,
            quote=quote,
            sellability=safety.sellability,
            liquidity_ok=(
                safety.status is FastSafetyStatus.PASS
                and safety.liquidity is not None
                and safety.liquidity >= self.safety_gate.minimum_liquidity
            ),
            price_impact_bps=self._entry_impact(safety),
            candidate_id=candidate.id,
        )
        decision_ms = Decimal(str((perf_counter() - decision_started) * 1000))
        target = _stage_for_decision(decision)
        if safety.status is FastSafetyStatus.BLOCK:
            target = CandidateState.RISK_REJECTED
        elif safety.status is FastSafetyStatus.UNKNOWN:
            # Missing early evidence is not a safe pass, but it is also not a
            # terminal rejection. The bounded scheduler can reevaluate this
            # WATCH candidate when market/safety evidence becomes available.
            target = CandidateState.WATCH
        initial_latencies = {
            "provider_to_ingestion": normalization_ms,
            "normalization_to_fast_safety": safety_ms,
            "fast_safety_to_features": feature_ms,
            "features_to_decision": decision_ms,
            "decision_to_outbox": Decimal("0"),
        }
        if not candidate.transitions:
            discovered_snapshot = self._build_snapshot(
                candidate=candidate,
                detection=detection,
                state=CandidateState.DISCOVERED,
                stage_at=detection.first_seen_at,
                observations=tuple(bucket.values()),
                feature_snapshot=feature_snapshot,
                safety=safety,
                organic=organic,
                score=score,
                decision=decision,
                latencies_ms=initial_latencies,
                initial=True,
            )
            await self._save_observation(discovered_snapshot)
            await self._save_runtime_snapshots(
                candidate=candidate,
                feature_snapshot=feature_snapshot,
                safety=safety,
                score=score,
                decision=decision,
                transition=None,
                provider_available=provider_available,
                stream_gap=stream_gap,
                initial=True,
            )
        stage_at = max(checkpoint, detection.first_seen_at, candidate.state_changed_at)
        prior_transition_keys = {item.idempotency_key for item in candidate.transitions}
        transition = self._advance_candidate(
            candidate,
            target,
            at=stage_at,
            score=score,
            decision=decision,
            safety=safety,
            feature_snapshot=feature_snapshot,
            stream_gap=stream_gap,
        )
        transition_is_new = (
            transition is not None and transition.idempotency_key not in prior_transition_keys
        )
        if transition_is_new and transition is not None and target in {
            CandidateState.EARLY_WATCH,
            CandidateState.HIGH_CONFLUENCE,
            CandidateState.ENTRY_READY,
        }:
            await self._save_runtime_snapshots(
                candidate=candidate,
                feature_snapshot=feature_snapshot,
                safety=safety,
                score=score,
                decision=decision,
                transition=transition,
                provider_available=provider_available,
                stream_gap=stream_gap,
            )
        await self._save_candidate(candidate)
        latencies = {
            "provider_to_ingestion": normalization_ms,
            "normalization_to_fast_safety": safety_ms,
            "fast_safety_to_features": feature_ms,
            "features_to_decision": decision_ms,
            "decision_to_outbox": Decimal("0"),
        }
        for transition_record in candidate.transitions:
            if transition_record.to_state in self._snapshot_states():
                intermediate = self._build_snapshot(
                    candidate=candidate,
                    detection=detection,
                    state=transition_record.to_state,
                    stage_at=transition_record.occurred_at,
                    observations=tuple(bucket.values()),
                    feature_snapshot=feature_snapshot,
                    safety=safety,
                    organic=organic,
                    score=score,
                    decision=decision,
                    latencies_ms=latencies,
                )
                await self._save_observation(intermediate)
        snapshot = self._build_snapshot(
            candidate=candidate,
            detection=detection,
            state=target,
            stage_at=stage_at,
            observations=tuple(bucket.values()),
            feature_snapshot=feature_snapshot,
            safety=safety,
            organic=organic,
            score=score,
            decision=decision,
            latencies_ms=latencies,
        )
        await self._save_observation(snapshot)
        lifecycle_event = None
        alert = None
        if transition is not None:
            lifecycle_event = self._lifecycle_event(
                candidate,
                transition.from_state,
                target,
                snapshot,
                transition.idempotency_key,
            )
            if self.outbox_store is not None:
                await self.outbox_store.enqueue(lifecycle_event)
            alert = AlertEventProjector().project(lifecycle_event)
            latencies["decision_to_outbox"] = Decimal(str((perf_counter() - started) * 1000))
        return EarlyRuntimeResult(
            detection=detection,
            candidate=candidate,
            safety=safety,
            feature_snapshot=feature_snapshot,
            organic_momentum=organic,
            score=score,
            decision=decision,
            stage=target,
            stage_snapshot=snapshot,
            lifecycle_event=lifecycle_event,
            alert=alert,
            duplicate=detection.duplicate and transition is None,
            latencies_ms=latencies,
        )

    def _checkpoint(
        self,
        mint: str,
        as_of: datetime | None,
        observations: Mapping[UUID, Observation],
        detection: EarlyDetectionResult,
    ) -> datetime:
        supplied = None if as_of is None else ensure_utc(as_of, "as_of")
        times = [
            item.occurred_at
            for item in observations.values()
            if item.occurred_at is not None
        ]
        candidate = supplied or (max(times) if times else detection.first_seen_at)
        previous = self._checkpoints.get(mint)
        checkpoint = candidate if previous is None else max(previous, candidate)
        self._checkpoints[mint] = checkpoint
        return checkpoint

    async def _save_observation(self, observation: Observation) -> None:
        if self.observation_store is None:
            return
        method = getattr(self.observation_store, "add", None) or getattr(
            self.observation_store, "save", None
        )
        if not callable(method):
            raise TypeError("observation_store must provide add() or save()")
        await method(observation)

    async def _save_candidate(self, candidate: Candidate) -> None:
        if self.candidate_store is None:
            return
        await self.candidate_store.add(candidate)

    async def _save_runtime_snapshots(
        self,
        *,
        candidate: Candidate,
        feature_snapshot: EarlyFeatureSnapshot,
        safety: FastSafetyResult,
        score: EarlyScoreSnapshot,
        decision: EarlyDecisionResult,
        transition: StateTransition | None,
        provider_available: bool,
        stream_gap: bool,
        initial: bool = False,
    ) -> None:
        if self.feature_store is None or self.risk_store is None or self.score_store is None:
            return
        if transition is None:
            checkpoint_key = f"initial:{candidate.id}:{feature_snapshot.as_of.isoformat()}"
            score_snapshot_id = uuid5(NAMESPACE_URL, f"{_RUNTIME_NAMESPACE}score:{checkpoint_key}")
            risk_assessment_id = uuid5(NAMESPACE_URL, f"{_RUNTIME_NAMESPACE}risk:{checkpoint_key}")
        else:
            if transition.score_snapshot_id is None or transition.risk_assessment_id is None:
                raise ValueError("decision transition is missing snapshot references")
            score_snapshot_id = transition.score_snapshot_id
            risk_assessment_id = transition.risk_assessment_id
        checkpoint = feature_snapshot.as_of
        expires_at = checkpoint + timedelta(minutes=5)
        provenance: list[Provenance] = []
        for window in feature_snapshot.windows.values():
            for source in window.provenance:
                if source not in provenance:
                    provenance.append(source)
        feature = FeatureSnapshot(
            id=uuid5(
                NAMESPACE_URL,
                f"{_RUNTIME_NAMESPACE}feature:{candidate.id}:{checkpoint.isoformat()}:{feature_snapshot.version}",
            ),
            candidate_id=candidate.id,
            as_of=checkpoint,
            expires_at=expires_at,
            feature_version=feature_snapshot.version,
            completeness=_feature_completeness(feature_snapshot),
            confidence=_feature_confidence(feature_snapshot),
            values=_feature_values(feature_snapshot),
            provenance=tuple(provenance),
            config_hash=decision.config_hash,
            quality_state=feature_snapshot.quality_state,
        )
        risk_quality = (
            QualityState.UNKNOWN
            if not provider_available or stream_gap
            else safety.quality_state
        )
        risk_reasons = _reason_values(score, decision, safety, feature_snapshot)
        risk = RiskAssessment(
            id=risk_assessment_id,
            candidate_id=candidate.id,
            as_of=checkpoint,
            expires_at=expires_at,
            risk_version=safety.version,
            disposition={
                FastSafetyStatus.PASS: RiskDisposition.PASS,
                FastSafetyStatus.CAUTION: RiskDisposition.WARN,
                FastSafetyStatus.BLOCK: RiskDisposition.BLOCK,
                FastSafetyStatus.UNKNOWN: RiskDisposition.UNKNOWN,
            }[safety.status],
            hard_blocks=safety.hard_blocks,
            warnings=safety.noncritical_unknowns,
            penalties=score.penalties,
            evidence_refs=safety.evidence_refs,
            reason_codes=risk_reasons or (ReasonCode("EARLY_RUNTIME_RISK_SNAPSHOT"),),
            confidence=decision.confidence,
            config_hash=decision.config_hash,
            critical_evidence_state=risk_quality,
        )
        components = {
            key: value for key, value in score.components.items() if value is not None
        }
        if not components:
            if not initial:
                raise ValueError("decision score has no observed components to persist")
            components = {"observed_component_count": Decimal("0")}
        score_projection = ScoreSnapshot(
            id=score_snapshot_id,
            candidate_id=candidate.id,
            as_of=checkpoint,
            model_version=score.version,
            strategy_name="early-alpha",
            strategy_version=score.version,
            alpha_score=score.score,
            confidence=score.confidence,
            components=components,
            penalties=score.penalties,
            reason_codes=score.reason_codes or (ReasonCode("EARLY_SCORE_SNAPSHOT"),),
            feature_snapshot_id=feature.id,
            risk_assessment_id=risk.id,
            expires_at=expires_at,
            config_hash=score.config_hash,
            quality_state=score.risk_quality_state,
        )
        await self.feature_store.add(feature)
        await self.risk_store.add(risk)
        await self.score_store.add(score_projection)

    async def _get_or_create_candidate(self, detection: EarlyDetectionResult) -> Candidate:
        if self.candidate_store is not None:
            existing = await self.candidate_store.get(detection.candidate_id)
            if existing is not None:
                self._candidates[detection.candidate_id] = existing
                return existing
        existing = self._candidates.get(detection.candidate_id)
        if existing is not None:
            return existing
        candidate = Candidate(
            id=detection.candidate_id,
            token=TokenIdentity(mint_address=detection.mint_address, id=detection.token_id),
            discovered_at=detection.first_seen_at,
            discovery_source=detection.source_id,
        )
        self._candidates[candidate.id] = candidate
        await self._save_candidate(candidate)
        return candidate

    def _advance_candidate(
        self,
        candidate: Candidate,
        target: CandidateState,
        *,
        at: datetime,
        score: EarlyScoreSnapshot,
        decision: EarlyDecisionResult,
        safety: FastSafetyResult,
        feature_snapshot: EarlyFeatureSnapshot,
        stream_gap: bool,
    ) -> StateTransition | None:
        if candidate.state is CandidateState.RISK_REJECTED:
            return None
        if candidate.state is CandidateState.DISCOVERED:
            candidate.transition(
                CandidateState.ENRICHING,
                reason_codes=("DISCOVERY_PERSISTED",),
                occurred_at=at,
                correlation_id=f"early:{candidate.id}",
                idempotency_key=f"early:{candidate.id}:ENRICHING",
            )
        if candidate.state is CandidateState.ENRICHING:
            candidate.transition(
                CandidateState.WATCH,
                reason_codes=("FAST_PATH_STARTED",),
                occurred_at=at,
                correlation_id=f"early:{candidate.id}",
                idempotency_key=f"early:{candidate.id}:WATCH",
            )
        if candidate.state is target:
            return next(
                (
                    item
                    for item in reversed(candidate.transitions)
                    if item.to_state is target
                ),
                None,
            )
        if target is CandidateState.WATCH and candidate.state is CandidateState.WATCH:
            return None
        reason_codes = _reason_values(score, decision, safety, feature_snapshot)
        if stream_gap:
            reason_codes = (*reason_codes, ReasonCode("STREAM_GAP"))
        if target is CandidateState.RISK_REJECTED and not reason_codes:
            reason_codes = (ReasonCode("FAST_SAFETY_BLOCK"),)
        evidence_refs = _evidence_refs(score, decision, safety, feature_snapshot)
        return candidate.transition(
            target,
            reason_codes=reason_codes or ("EARLY_STAGE_PROJECTED",),
            occurred_at=at,
            correlation_id=f"early:{candidate.id}",
            idempotency_key=f"early:{candidate.id}:{target.value}",
            score_snapshot_id=(
                score.id
                if target
                in {
                    CandidateState.EARLY_WATCH,
                    CandidateState.HIGH_CONFLUENCE,
                    CandidateState.ENTRY_READY,
                }
                else None
            ),
            risk_assessment_id=(
                _runtime_risk_id(candidate.id, target)
                if target
                in {
                    CandidateState.EARLY_WATCH,
                    CandidateState.HIGH_CONFLUENCE,
                    CandidateState.ENTRY_READY,
                }
                else None
            ),
            version=EARLY_RUNTIME_VERSION,
            config_hash=decision.config_hash,
            confidence=decision.confidence,
            evidence_refs=evidence_refs or (f"candidate:{candidate.id}",),
        )

    @staticmethod
    def _preferred_window(snapshot: EarlyFeatureSnapshot) -> EarlyFeatureWindow:
        for label in ("1m", "30s", "2m", "5m", "10m", "15m"):
            if label in snapshot.windows:
                return snapshot.window(label)
        return next(iter(snapshot.windows.values()))

    @staticmethod
    def _snapshot_states() -> frozenset[CandidateState]:
        return frozenset(
            {
                CandidateState.ENRICHING,
                CandidateState.WATCH,
                CandidateState.EARLY_WATCH,
                CandidateState.STRONG_SETUP,
                CandidateState.HIGH_CONFLUENCE,
                CandidateState.ENTRY_READY,
                CandidateState.RISK_REJECTED,
            }
        )

    @staticmethod
    def _components(metrics: Mapping[str, object], safety: FastSafetyResult) -> dict[str, object]:
        acceleration = _decimal(metrics.get("volume_acceleration"), "volume_acceleration")
        momentum = (
            Decimal("50") + acceleration * Decimal("50")
            if acceleration is not None
            else None
        )
        raw = safety.raw_smart_wallet_count
        independent = safety.independent_smart_wallet_count
        smart_money = (
            Decimal("100") * min(Decimal("1"), Decimal(independent) / Decimal(raw))
            if raw is not None and independent is not None and raw > 0
            else None
        )
        safety_score = {
            FastSafetyStatus.PASS: Decimal("100"),
            FastSafetyStatus.CAUTION: Decimal("60"),
            FastSafetyStatus.BLOCK: Decimal("0"),
            FastSafetyStatus.UNKNOWN: None,
        }[safety.status]
        return {
            "OrganicFlowAcceleration": None,
            "WalletQuality": smart_money,
            "OnChainSafety": safety_score,
            "LiquidityAndSellability": safety_score,
            "LaunchMomentum": momentum,
            "SmartMoneyConfluence": smart_money,
        }

    @staticmethod
    def _risk_mapping(
        safety: FastSafetyResult,
        *,
        provider_available: bool,
        stream_gap: bool,
    ) -> Mapping[str, object]:
        disposition = {
            FastSafetyStatus.PASS: "PASS",
            FastSafetyStatus.CAUTION: "WARN",
            FastSafetyStatus.BLOCK: "BLOCK",
            FastSafetyStatus.UNKNOWN: "UNKNOWN",
        }[safety.status]
        return {
            "disposition": disposition,
            "risk_disposition": disposition,
            "quality_state": (
                QualityState.UNKNOWN.value
                if not provider_available or stream_gap
                else safety.quality_state.value
            ),
            "hard_blocks": safety.hard_blocks,
            "reason_codes": safety.reason_codes,
            "evidence_refs": safety.evidence_refs,
        }

    @staticmethod
    def _entry_impact(safety: FastSafetyResult) -> Decimal | None:
        values = [
            value
            for value in (safety.buy_impact_bps, safety.sell_impact_bps)
            if value is not None
        ]
        return max(values) if values else None

    def _build_snapshot(
        self,
        *,
        candidate: Candidate,
        detection: EarlyDetectionResult,
        state: CandidateState,
        stage_at: datetime,
        observations: Sequence[Observation],
        feature_snapshot: EarlyFeatureSnapshot | None,
        safety: FastSafetyResult | None,
        organic: OrganicMomentumProjection | None,
        score: EarlyScoreSnapshot | None,
        decision: EarlyDecisionResult | None,
        latencies_ms: Mapping[str, Decimal],
        initial: bool = False,
    ) -> Observation:
        key = (candidate.id, state)
        existing = self._snapshots.get(key)
        if existing is not None:
            return existing
        ordered = sorted(
            (item for item in observations if item.occurred_at is not None),
            key=lambda item: (item.occurred_at, str(item.id)),
        )
        first = ordered[0] if ordered else None
        first_payload = {} if first is None else first.normalized_payload
        launch_at = detection.launch_at or detection.first_seen_at
        age = max(Decimal("0"), Decimal(str((stage_at - launch_at).total_seconds())))
        window = None if feature_snapshot is None else self._preferred_window(feature_snapshot)
        metrics = {} if window is None else dict(window.metrics)
        provider_to_ingestion = Decimal(
            str(
                (
                    detection.timing.first_ingested_at
                    - detection.timing.first_observed_at
                ).total_seconds()
                * 1000
            )
        )
        authority = (
            detection.authority.value
            if isinstance(detection.authority, DetectionAuthority)
            else str(detection.authority)
        )
        snapshot_liquidity = metrics.get("liquidity", first_payload.get("liquidity_usd"))
        alpha_projection = (
            None
            if score is None
            else build_asymmetric_alpha_projection(
                score,
                market_cap_at_decision=_decimal(
                    metrics.get("market_cap", first_payload.get("market_cap_usd")),
                    "market_cap",
                ),
                launch_age_ms=int(age * Decimal("1000")),
            )
        )
        payload: dict[str, object] = {
            "chain": "solana",
            "mint": detection.mint_address,
            "signature": first_payload.get("signature"),
            "slot": first_payload.get("slot"),
            "instruction_type": first_payload.get(
                "instruction_type", first_payload.get("event_type")
            ),
            "creator": first_payload.get("creator"),
            "user": first_payload.get("user"),
            "name": first_payload.get("name"),
            "symbol": first_payload.get("symbol"),
            "uri": first_payload.get("uri"),
            "is_mayhem_mode": first_payload.get("is_mayhem_mode"),
            "quote_mint_semantics": first_payload.get("quote_mint_semantics"),
            "is_holder_reward": first_payload.get("is_holder_reward"),
            "venue": first_payload.get(
                "venue", detection.metadata.get("venue", authority)
            ),
            "chain_created_at": (
                None if detection.launch_at is None else detection.launch_at.isoformat()
            ),
            "provider_observed_at": detection.first_observed_at.isoformat(),
            "memeradar_ingested_at": detection.timing.first_ingested_at.isoformat(),
            "first_seen_at": detection.first_seen_at.isoformat(),
            "discovered_at": detection.first_seen_at.isoformat(),
            "chain_occurred_at": launch_at.isoformat(),
            "first_seen_age_seconds": age,
            "age_cohort": age_cohort(age),
            "first_seen_market_cap": first_payload.get(
                "market_cap_usd", first_payload.get("market_cap")
            ),
            "first_seen_liquidity": first_payload.get(
                "liquidity_usd", first_payload.get("liquidity")
            ),
            "state": state.value,
            "state_at": stage_at.isoformat(),
            "token_age_seconds": age,
            "market_cap": metrics.get("market_cap", first_payload.get("market_cap_usd")),
            "liquidity": snapshot_liquidity,
            "liquidity_cohort": liquidity_cohort(_decimal(snapshot_liquidity, "liquidity")),
            "contract": detection.mint_address,
            "volume_velocity": metrics.get("quote_inflow_per_second"),
            "turnover": metrics.get("turnover"),
            "turnover_velocity": metrics.get("turnover_velocity"),
            "turnover_acceleration": metrics.get("turnover_acceleration"),
            "turnover_provider_provenance": metrics.get("turnover_provider_provenance", ()),
            "unique_buyers": metrics.get("unique_buyers"),
            "buyer_velocity": metrics.get("new_buyers_per_minute"),
            "holder_velocity": metrics.get("holder_velocity"),
            "liquidity_growth": metrics.get("liquidity_velocity"),
            "trade_velocity": metrics.get("buys_per_second"),
            "early_score": None if score is None else score.score,
            "organic_momentum_score": None if organic is None else organic.score,
            "risk": None if safety is None else safety.status.value,
            "safety_status": None if safety is None else safety.status.value,
            "critical_unknowns": () if safety is None else safety.critical_unknowns,
            "noncritical_unknowns": () if safety is None else safety.noncritical_unknowns,
            "hard_blocks": () if safety is None else safety.hard_blocks,
            "confidence": None if decision is None else decision.confidence,
            "AlphaIgnitionScore": (
                None if alpha_projection is None else alpha_projection.alpha_ignition_score
            ),
            "SafetyConfidence": (
                None if alpha_projection is None else alpha_projection.safety_confidence
            ),
            "OpportunityConfidence": (
                None if alpha_projection is None else alpha_projection.opportunity_confidence
            ),
            "DataQualityConfidence": (
                None if alpha_projection is None else alpha_projection.data_quality_confidence
            ),
            "alpha_ignition_score": (
                None if alpha_projection is None else alpha_projection.alpha_ignition_score
            ),
            "safety_confidence": (
                None if alpha_projection is None else alpha_projection.safety_confidence
            ),
            "opportunity_confidence": (
                None if alpha_projection is None else alpha_projection.opportunity_confidence
            ),
            "data_quality_confidence": (
                None if alpha_projection is None else alpha_projection.data_quality_confidence
            ),
            "paper_eligible": None if decision is None else decision.entry_ready,
            "execution_status": (
                "PAPER_ELIGIBLE"
                if decision is not None and decision.entry_ready
                else "EXECUTION_BLOCKED"
            ),
            "raw_smart_wallet_count": (
                None if safety is None else safety.raw_smart_wallet_count
            ),
            "independent_smart_wallet_count": (
                None if safety is None else safety.independent_smart_wallet_count
            ),
            "shared_funder_ratio": metrics.get("shared_funder_ratio"),
            "creator_linked_buyer_ratio": metrics.get("creator_linked_buyer_ratio"),
            "bundle_risk": metrics.get("bundle_risk", "UNKNOWN"),
            "sniper_risk": metrics.get("sniper_risk", "UNKNOWN"),
            "buy_impact_bps": None if safety is None else safety.buy_impact_bps,
            "sell_impact_bps": None if safety is None else safety.sell_impact_bps,
            "sellability": None if safety is None else safety.sellability,
            "reason_codes": tuple(
                reason.code
                for reason in _reason_values(
                    detection,
                    feature_snapshot,
                    safety,
                    organic,
                    score,
                    decision,
                )
            ),
            "evidence_refs": _evidence_refs(
                detection,
                feature_snapshot,
                safety,
                organic,
                score,
                decision,
            ),
            "provider_provenance": tuple(
                {
                    "provider": source.provider,
                    "source_id": source.source_id,
                    "observed_at": source.observed_at.isoformat(),
                    "parser_version": source.parser_version,
                }
                for source in detection.timing.provenance
            ),
            "config_version": self.decision_engine.policy.version,
            "score_version": None if score is None else score.version,
            "runtime_version": EARLY_RUNTIME_VERSION,
            "git_revision": self.git_revision,
            "latencies_ms": {
                "provider_to_ingestion": latencies_ms.get(
                    "provider_to_ingestion", provider_to_ingestion
                ),
                "normalization_to_fast_safety": latencies_ms.get(
                    "normalization_to_fast_safety", "UNKNOWN"
                ),
                "fast_safety_to_features": latencies_ms.get(
                    "fast_safety_to_features", "UNKNOWN"
                ),
                "features_to_decision": latencies_ms.get("features_to_decision", "UNKNOWN"),
                "decision_to_outbox": latencies_ms.get("decision_to_outbox", "UNKNOWN"),
            },
            "execution_eligible": False,
            "analysis_only": True,
            "paper_trading": True,
            "manual_execution": False,
            "auto_execution": False,
        }
        if state is not CandidateState.DISCOVERED:
            payload[f"{state.value.lower()}_at"] = stage_at.isoformat()
            payload[f"{state.value.lower()}_market_cap"] = payload["market_cap"]
        snapshot_quality_state = (
            QualityState.UNKNOWN
            if safety is not None and safety.quality_state is not QualityState.FRESH
            else detection.quality_state
        )
        fingerprint_material = {
            "payload": payload,
            "quality_state": snapshot_quality_state.value,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_material,
                sort_keys=True,
                default=str,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        snapshot_identity = (
            f"{candidate.id}:{state.value}:{_SNAPSHOT_IDENTITY_VERSION}:{fingerprint}"
        )
        source_identity = (
            f"early-stage:{candidate.id}:{state.value}:"
            f"{_SNAPSHOT_IDENTITY_VERSION}:{fingerprint}"
        )
        if initial:
            snapshot_identity += ":initial"
            source_identity += ":initial"
        snapshot = Observation(
            id=uuid5(NAMESPACE_URL, f"{_RUNTIME_NAMESPACE}snapshot:{snapshot_identity}"),
            kind=EARLY_STAGE_SNAPSHOT_KIND,
            provenance=Provenance(
                provider="memeradar.early-runtime",
                source_id=source_identity,
                observed_at=stage_at,
                parser_version=EARLY_RUNTIME_VERSION,
            ),
            occurred_at=stage_at,
            observed_at=stage_at,
            ingested_at=stage_at,
            quality_state=snapshot_quality_state,
            normalized_payload=payload,
            candidate_id=candidate.id,
            token_id=candidate.token_id,
        )
        self._snapshots[key] = snapshot
        return snapshot

    @staticmethod
    def _lifecycle_event(
        candidate: Candidate,
        from_state: CandidateState,
        to_state: CandidateState,
        snapshot: Observation,
        transition_key: str,
    ) -> EventEnvelope:
        payload = dict(snapshot.normalized_payload)
        payload.update(
            {
                "candidate_id": str(candidate.id),
                "from_state": from_state.value,
                "to_state": to_state.value,
                "state": to_state.value,
                "snapshot_id": str(snapshot.id),
                "stage_snapshot_source_id": snapshot.provenance.source_id,
                "not_entry_ready": to_state is CandidateState.EARLY_WATCH,
                "research_paper_signal": to_state is CandidateState.EARLY_WATCH,
            }
        )
        reasons = _reason_values(payload)
        return EventEnvelope(
            kind="CandidateStateChanged",
            aggregate_type="candidate",
            aggregate_id=candidate.id,
            occurred_at=snapshot.occurred_at or snapshot.observed_at,
            observed_at=snapshot.observed_at,
            ingested_at=snapshot.ingested_at,
            correlation_id=f"early:{candidate.id}",
            producer="memeradar.early-runtime",
            payload=payload,
            id=uuid5(NAMESPACE_URL, f"{_RUNTIME_NAMESPACE}event:{transition_key}"),
            idempotency_key=f"{transition_key}:alert",
            reason_codes=reasons or (ReasonCode("EARLY_STAGE_PROJECTED"),),
        )


__all__ = [
    "EARLY_RUNTIME_VERSION",
    "EARLY_STAGE_SNAPSHOT_KIND",
    "EarlyRuntimeResult",
    "EarlyRuntimeService",
]
