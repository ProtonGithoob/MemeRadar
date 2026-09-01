"""Measurement-only lead-time benchmarking for external social-call references.

An imported call timestamp is intentionally kept outside the scoring and
decision graph.  This module records how early MemeRadar observed, watched or
prepared a candidate relative to that reference; it never turns the reference
into evidence, clears a risk gate or submits an execution request.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from memeradar_domain import ExternalCallBenchmark, Provenance, QualityState, ReasonCode
from memeradar_domain.common import ensure_utc, freeze_mapping, normalize_texts, require_text
from memeradar_domain.events import normalize_reason_codes

EARLY_CALL_BENCHMARK_VERSION = "early-call-benchmark-v1"


@dataclass(frozen=True, slots=True)
class EarlyCallBenchmarkPolicy:
    """Versioned metadata policy for the external-call measurement seam."""

    version: str = EARLY_CALL_BENCHMARK_VERSION
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        normalized_version = require_text(self.version, "version", max_length=64)
        object.__setattr__(self, "version", normalized_version)
        material = {"version": normalized_version, "measurement_only": True}
        object.__setattr__(
            self,
            "config_hash",
            "sha256:" + hashlib.sha256(
                json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )


def _normalize_provenance(values: Sequence[Provenance] | None) -> tuple[Provenance, ...]:
    if values is None:
        return ()
    if isinstance(values, str | bytes | bytearray):
        raise TypeError("provenance must be a sequence of Provenance values")
    normalized = tuple(values)
    if any(not isinstance(value, Provenance) for value in normalized):
        raise TypeError("provenance must contain Provenance values")
    return normalized


def _reason_values(values: Sequence[ReasonCode | str]) -> tuple[ReasonCode, ...]:
    return normalize_reason_codes(values)


class EarlyCallBenchmark:
    """Build immutable external-call measurements without granting authority."""

    def __init__(self, *, policy: EarlyCallBenchmarkPolicy | None = None) -> None:
        self.policy = policy or EarlyCallBenchmarkPolicy()

    def measure(
        self,
        candidate_id: UUID,
        memeradar_first_seen_at: datetime,
        *,
        external_call_at: datetime | None = None,
        source_id: str = "external-call-reference",
        memeradar_first_watch_at: datetime | None = None,
        memeradar_entry_ready_at: datetime | None = None,
        as_of: datetime | None = None,
        quality_state: QualityState | str = QualityState.FRESH,
        evidence_refs: Sequence[str] = (),
        provenance: Sequence[Provenance] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> ExternalCallBenchmark:
        """Measure lead time while treating invalid references as non-authoritative.

        ``as_of`` is an optional import/replay cutoff.  A reference after that
        cutoff is retained only in metadata and cannot produce a lead-time
        value.  The returned domain record is safe to place beside a decision
        projection because its execution authority is permanently false.
        """

        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        first_seen = ensure_utc(memeradar_first_seen_at, "memeradar_first_seen_at")
        watch = None if memeradar_first_watch_at is None else ensure_utc(
            memeradar_first_watch_at, "memeradar_first_watch_at"
        )
        entry_ready = None if memeradar_entry_ready_at is None else ensure_utc(
            memeradar_entry_ready_at, "memeradar_entry_ready_at"
        )
        checked_as_of = None if as_of is None else ensure_utc(as_of, "as_of")
        normalized_source_id = require_text(source_id, "source_id")
        normalized_refs = normalize_texts(evidence_refs, "evidence_refs")
        normalized_provenance = _normalize_provenance(provenance)
        supplied_metadata = dict(metadata or {})
        supplied_metadata.update(
            {
                "benchmark_version": self.policy.version,
                "benchmark_config_hash": self.policy.config_hash,
                "measurement_only": True,
            }
        )

        reasons: list[str] = []
        measured_external = (
            None if external_call_at is None else ensure_utc(external_call_at, "external_call_at")
        )
        state = QualityState(quality_state)
        if measured_external is None:
            state = QualityState.UNKNOWN
            reasons.append("EXTERNAL_CALL_MISSING")
        elif measured_external < first_seen:
            state = QualityState.INVALID
            reasons.append("EXTERNAL_CALL_BEFORE_FIRST_SEEN")
            supplied_metadata["rejected_external_call_at"] = measured_external.isoformat()
            measured_external = None
        elif checked_as_of is not None and measured_external > checked_as_of:
            state = QualityState.INVALID
            reasons.append("EXTERNAL_CALL_AFTER_AS_OF")
            supplied_metadata["rejected_external_call_at"] = measured_external.isoformat()
            measured_external = None
        if checked_as_of is not None and checked_as_of < first_seen:
            state = QualityState.INVALID
            reasons.append("BENCHMARK_AS_OF_BEFORE_FIRST_SEEN")
            supplied_metadata["benchmark_as_of"] = checked_as_of.isoformat()
        elif checked_as_of is not None:
            supplied_metadata["benchmark_as_of"] = checked_as_of.isoformat()
        if state is not QualityState.FRESH and not reasons:
            reasons.append(f"EXTERNAL_CALL_REFERENCE_{state.value}")

        return ExternalCallBenchmark(
            candidate_id=candidate_id,
            memeradar_first_seen_at=first_seen,
            memeradar_first_watch_at=watch,
            memeradar_entry_ready_at=entry_ready,
            external_call_at=measured_external,
            source_id=normalized_source_id,
            quality_state=state,
            evidence_refs=normalized_refs,
            provenance=normalized_provenance,
            metadata=freeze_mapping(supplied_metadata, "metadata"),
            reason_codes=_reason_values(reasons),
        )

    benchmark = measure

    def measure_many(
        self,
        references: Sequence[Mapping[str, object]],
    ) -> tuple[ExternalCallBenchmark, ...]:
        """Replay imported reference rows in stable order with duplicate removal."""

        if isinstance(references, str | bytes | bytearray):
            raise TypeError("references must be a sequence of mappings")
        results: list[ExternalCallBenchmark] = []
        seen: dict[tuple[object, str, datetime | None], ExternalCallBenchmark] = {}
        for reference in references:
            if not isinstance(reference, Mapping):
                raise TypeError("references must contain mappings")
            result = self.measure(**dict(reference))  # type: ignore[arg-type]
            key = (result.candidate_id, result.source_id, result.external_call_at)
            prior = seen.get(key)
            if prior is not None:
                if prior != result:
                    raise ValueError("conflicting duplicate external call reference")
                continue
            seen[key] = result
            results.append(result)
        return tuple(
            sorted(
                results,
                key=lambda value: (
                    value.memeradar_first_seen_at,
                    str(value.candidate_id),
                    value.source_id,
                    value.external_call_at or value.memeradar_first_seen_at,
                ),
            )
        )

    @staticmethod
    def serialize(result: ExternalCallBenchmark) -> Mapping[str, object]:
        """Serialize one result without dropping provenance or source identity."""

        if not isinstance(result, ExternalCallBenchmark):
            raise TypeError("result must be an ExternalCallBenchmark")
        return result.to_mapping()


EarlyCallLeadTimeBenchmark = EarlyCallBenchmark
ExternalCallLeadTimeBenchmark = EarlyCallBenchmark


__all__ = [
    "EARLY_CALL_BENCHMARK_VERSION",
    "EarlyCallBenchmark",
    "EarlyCallBenchmarkPolicy",
    "EarlyCallLeadTimeBenchmark",
    "ExternalCallLeadTimeBenchmark",
]
