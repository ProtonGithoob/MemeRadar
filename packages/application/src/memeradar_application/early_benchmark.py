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
from decimal import Decimal
from uuid import UUID

from memeradar_domain import (
    Chain,
    ExternalCallBenchmark,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
)
from memeradar_domain.common import (
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

EARLY_CALL_BENCHMARK_VERSION = "early-call-benchmark-v1"
DEXSCREENER_BENCHMARK_VERSION = "dexscreener-benchmark-v1"


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
            "sha256:"
            + hashlib.sha256(
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
        watch = (
            None
            if memeradar_first_watch_at is None
            else ensure_utc(memeradar_first_watch_at, "memeradar_first_watch_at")
        )
        entry_ready = (
            None
            if memeradar_entry_ready_at is None
            else ensure_utc(memeradar_entry_ready_at, "memeradar_entry_ready_at")
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


def _snapshot_payload(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    payload = getattr(value, "normalized_payload", None)
    return payload if isinstance(payload, Mapping) else {}


def _optional_timestamp(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime, ISO timestamp or None")
    return ensure_utc(value, field_name)


def _optional_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return to_decimal(value, field_name)


@dataclass(frozen=True, slots=True)
class DexScreenerBenchmark:
    """Exact-mint DexScreener comparison with unavailable history explicit."""

    chain: str
    mint_address: str
    first_seen_at: datetime | None = None
    first_seen_age_seconds: object | None = None
    first_seen_market_cap: object | None = None
    early_watch_at: datetime | None = None
    early_watch_market_cap: object | None = None
    strong_setup_at: datetime | None = None
    strong_setup_market_cap: object | None = None
    high_confluence_at: datetime | None = None
    high_confluence_market_cap: object | None = None
    entry_ready_at: datetime | None = None
    entry_ready_market_cap: object | None = None
    first_telegram_alert_at: datetime | None = None
    first_telegram_alert_market_cap: object | None = None
    dex_first_pair_observed_at: datetime | None = None
    dex_first_pair_observed_mc: object | None = None
    dex_first_meaningful_volume_at: datetime | None = None
    dex_first_meaningful_volume_mc: object | None = None
    dex_visibility_milestone_at: datetime | None = None
    dex_visibility_milestone_mc: object | None = None
    dex_trending_at: datetime | None = None
    dex_top_volume_at: datetime | None = None
    later_observed_market_cap: object | None = None
    future_executable_peak_market_cap: object | None = None
    alert_to_peak_executable_multiple: object | None = None
    unknown_fields: tuple[str, ...] = ()
    quality_state: QualityState = QualityState.UNKNOWN
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    version: str = DEXSCREENER_BENCHMARK_VERSION

    def __post_init__(self) -> None:
        identity = TokenIdentity(mint_address=self.mint_address, chain=self.chain)
        chain = identity.chain.value if isinstance(identity.chain, Chain) else str(identity.chain)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "mint_address", identity.mint_address)
        for field_name in (
            "first_seen_at",
            "early_watch_at",
            "strong_setup_at",
            "high_confluence_at",
            "entry_ready_at",
            "first_telegram_alert_at",
            "dex_first_pair_observed_at",
            "dex_first_meaningful_volume_at",
            "dex_visibility_milestone_at",
            "dex_trending_at",
            "dex_top_volume_at",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_timestamp(getattr(self, field_name), field_name),
            )
        for field_name in (
            "first_seen_age_seconds",
            "first_seen_market_cap",
            "early_watch_market_cap",
            "strong_setup_market_cap",
            "high_confluence_market_cap",
            "entry_ready_market_cap",
            "first_telegram_alert_market_cap",
            "dex_first_pair_observed_mc",
            "dex_first_meaningful_volume_mc",
            "dex_visibility_milestone_mc",
            "later_observed_market_cap",
            "future_executable_peak_market_cap",
            "alert_to_peak_executable_multiple",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_decimal(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "unknown_fields",
            normalize_texts(self.unknown_fields, "unknown_fields"),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if any(not isinstance(item, Provenance) for item in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "version", require_text(self.version, "version"))

    @property
    def identity(self) -> str:
        return f"{self.chain}:{self.mint_address}"

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "identity": self.identity,
            "chain": self.chain,
            "mint_address": self.mint_address,
            "first_seen_at": (
                None if self.first_seen_at is None else self.first_seen_at.isoformat()
            ),
            "first_seen_age_seconds": _json_value(self.first_seen_age_seconds),
            "first_seen_market_cap": _json_value(self.first_seen_market_cap),
            "early_watch_at": (
                None if self.early_watch_at is None else self.early_watch_at.isoformat()
            ),
            "early_watch_market_cap": _json_value(self.early_watch_market_cap),
            "strong_setup_at": (
                None if self.strong_setup_at is None else self.strong_setup_at.isoformat()
            ),
            "strong_setup_market_cap": _json_value(self.strong_setup_market_cap),
            "high_confluence_at": (
                None if self.high_confluence_at is None else self.high_confluence_at.isoformat()
            ),
            "high_confluence_market_cap": _json_value(self.high_confluence_market_cap),
            "entry_ready_at": (
                None if self.entry_ready_at is None else self.entry_ready_at.isoformat()
            ),
            "entry_ready_market_cap": _json_value(self.entry_ready_market_cap),
            "first_telegram_alert_at": (
                None
                if self.first_telegram_alert_at is None
                else self.first_telegram_alert_at.isoformat()
            ),
            "first_telegram_alert_market_cap": _json_value(self.first_telegram_alert_market_cap),
            "dex_first_pair_observed_at": (
                None
                if self.dex_first_pair_observed_at is None
                else self.dex_first_pair_observed_at.isoformat()
            ),
            "dex_first_pair_observed_mc": _json_value(self.dex_first_pair_observed_mc),
            "dex_first_meaningful_volume_at": (
                None
                if self.dex_first_meaningful_volume_at is None
                else self.dex_first_meaningful_volume_at.isoformat()
            ),
            "dex_first_meaningful_volume_mc": _json_value(self.dex_first_meaningful_volume_mc),
            "dex_visibility_milestone_at": (
                None
                if self.dex_visibility_milestone_at is None
                else self.dex_visibility_milestone_at.isoformat()
            ),
            "dex_visibility_milestone_mc": _json_value(self.dex_visibility_milestone_mc),
            "dex_trending_at": (
                None if self.dex_trending_at is None else self.dex_trending_at.isoformat()
            ),
            "dex_top_volume_at": (
                None if self.dex_top_volume_at is None else self.dex_top_volume_at.isoformat()
            ),
            "later_observed_market_cap": _json_value(self.later_observed_market_cap),
            "future_executable_peak_market_cap": _json_value(
                self.future_executable_peak_market_cap
            ),
            "alert_to_peak_executable_multiple": _json_value(
                self.alert_to_peak_executable_multiple
            ),
            "unknown_fields": list(self.unknown_fields),
            "quality_state": self.quality_state.value,
            "reason_codes": [reason.code for reason in self.reason_codes],
            "evidence_refs": list(self.evidence_refs),
            "version": self.version,
        }


def _json_value(value: object) -> object:
    return None if value is None else str(value)


class DexScreenerBenchmarkBuilder:
    """Build exact-mint benchmarks from immutable early and market evidence."""

    def measure(
        self,
        token: TokenIdentity,
        *,
        stage_snapshots: Mapping[str, object] | None = None,
        telegram: Mapping[str, object] | None = None,
        dexscreener_observations: Sequence[Mapping[str, object]] = (),
        future_executable_peak_market_cap: object | None = None,
        provenance: Sequence[Provenance] = (),
    ) -> DexScreenerBenchmark:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        snapshots = {
            str(key).upper(): _snapshot_payload(value)
            for key, value in (stage_snapshots or {}).items()
        }
        stage = snapshots

        def stage_value(name: str, key: str) -> object | None:
            payload = stage.get(name, {})
            return payload.get(key)

        telegram_payload = dict(telegram or {})
        unknown: list[str] = []
        reasons: list[ReasonCode] = []
        refs: list[str] = []
        pair: tuple[datetime, object] | None = None
        volume: tuple[datetime, object] | None = None
        visibility: tuple[datetime, object] | None = None
        trending: datetime | None = None
        top_volume: datetime | None = None
        later_caps: list[object] = []
        token_chain = token.chain.value if isinstance(token.chain, Chain) else str(token.chain)
        for row in dexscreener_observations:
            if not isinstance(row, Mapping):
                raise TypeError("dexscreener_observations must contain mappings")
            row_chain = row.get("chain")
            row_mint = row.get("mint_address", row.get("mint"))
            if row_chain is not None and str(row_chain).lower() != token_chain:
                raise ValueError("DexScreener observation chain does not match token")
            if row_mint is not None and row_mint != token.mint_address:
                raise ValueError("DexScreener observation mint does not match token")
            observed_at = row.get("observed_at")
            if not isinstance(observed_at, datetime):
                raise ValueError("DexScreener observations require observed_at")
            observed_at = ensure_utc(observed_at, "observed_at")
            event_type = str(row.get("event_type", row.get("milestone", ""))).lower()
            market_cap = row.get("market_cap", row.get("market_cap_usd"))
            if market_cap is not None:
                later_caps.append(market_cap)
            if row.get("evidence_ref") is not None:
                refs.append(str(row["evidence_ref"]))
            if event_type in {"new_pair", "first_pair", "pair_created"}:
                pair = (
                    min(pair, (observed_at, market_cap), key=lambda value: value[0])
                    if pair
                    else (observed_at, market_cap)
                )
            elif event_type in {"meaningful_volume", "volume"}:
                volume = (
                    min(volume, (observed_at, market_cap), key=lambda value: value[0])
                    if volume
                    else (observed_at, market_cap)
                )
            elif event_type in {"visibility", "visibility_milestone", "mainstream_visibility"}:
                visibility = (
                    min(visibility, (observed_at, market_cap), key=lambda value: value[0])
                    if visibility
                    else (observed_at, market_cap)
                )
            elif event_type == "trending":
                if row.get("authoritative") is True:
                    trending = observed_at
                else:
                    unknown.append("dex_trending_at")
                    reasons.append(ReasonCode("DEX_TRENDING_TIMESTAMP_UNAVAILABLE"))
            elif event_type in {"top_volume", "top-volume"}:
                if row.get("authoritative") is True:
                    top_volume = observed_at
                else:
                    unknown.append("dex_top_volume_at")
                    reasons.append(ReasonCode("DEX_TOP_VOLUME_TIMESTAMP_UNAVAILABLE"))
        alert_mc = telegram_payload.get(
            "market_cap",
            telegram_payload.get("first_telegram_alert_market_cap"),
        )
        peak_mc = future_executable_peak_market_cap
        alert_multiple = None
        if alert_mc is not None and peak_mc is not None:
            alert_value = to_decimal(alert_mc, "alert_market_cap")
            if alert_value > 0:
                alert_multiple = to_decimal(
                    peak_mc,
                    "future_executable_peak_market_cap",
                ) / alert_value
        if trending is None and "dex_trending_at" not in unknown:
            unknown.append("dex_trending_at")
            reasons.append(ReasonCode("DEX_TRENDING_TIMESTAMP_UNKNOWN"))
        if top_volume is None and "dex_top_volume_at" not in unknown:
            unknown.append("dex_top_volume_at")
            reasons.append(ReasonCode("DEX_TOP_VOLUME_TIMESTAMP_UNKNOWN"))
        if not pair:
            unknown.append("dex_first_pair_observed_at")
        state = QualityState.FRESH if pair or volume or visibility else QualityState.UNKNOWN
        return DexScreenerBenchmark(
            chain=token.chain,
            mint_address=token.mint_address,
            first_seen_at=_optional_timestamp(
                stage_value("DISCOVERED", "state_at"), "first_seen_at"
            ),
            first_seen_age_seconds=stage_value("DISCOVERED", "first_seen_age_seconds"),
            first_seen_market_cap=stage_value("DISCOVERED", "first_seen_market_cap"),
            early_watch_at=_optional_timestamp(
                stage_value("EARLY_WATCH", "state_at"), "early_watch_at"
            ),
            early_watch_market_cap=stage_value("EARLY_WATCH", "market_cap"),
            strong_setup_at=_optional_timestamp(
                stage_value("STRONG_SETUP", "state_at"), "strong_setup_at"
            ),
            strong_setup_market_cap=stage_value("STRONG_SETUP", "market_cap"),
            high_confluence_at=_optional_timestamp(
                stage_value("HIGH_CONFLUENCE", "state_at"), "high_confluence_at"
            ),
            high_confluence_market_cap=stage_value("HIGH_CONFLUENCE", "market_cap"),
            entry_ready_at=_optional_timestamp(
                stage_value("ENTRY_READY", "state_at"), "entry_ready_at"
            ),
            entry_ready_market_cap=stage_value("ENTRY_READY", "market_cap"),
            first_telegram_alert_at=_optional_timestamp(
                telegram_payload.get("first_telegram_alert_at"), "first_telegram_alert_at"
            ),
            first_telegram_alert_market_cap=alert_mc,
            dex_first_pair_observed_at=None if pair is None else pair[0],
            dex_first_pair_observed_mc=None if pair is None else pair[1],
            dex_first_meaningful_volume_at=None if volume is None else volume[0],
            dex_first_meaningful_volume_mc=None if volume is None else volume[1],
            dex_visibility_milestone_at=None if visibility is None else visibility[0],
            dex_visibility_milestone_mc=None if visibility is None else visibility[1],
            dex_trending_at=trending,
            dex_top_volume_at=top_volume,
            later_observed_market_cap=max(
                (to_decimal(value, "later_observed_market_cap") for value in later_caps),
                default=None,
            ),
            future_executable_peak_market_cap=peak_mc,
            alert_to_peak_executable_multiple=alert_multiple,
            unknown_fields=tuple(dict.fromkeys(unknown)),
            quality_state=state,
            reason_codes=tuple(dict.fromkeys(reasons)),
            evidence_refs=tuple(dict.fromkeys(refs)),
            provenance=tuple(provenance),
        )


EarlyCallLeadTimeBenchmark = EarlyCallBenchmark
ExternalCallLeadTimeBenchmark = EarlyCallBenchmark


__all__ = [
    "DEXSCREENER_BENCHMARK_VERSION",
    "EARLY_CALL_BENCHMARK_VERSION",
    "EarlyCallBenchmark",
    "EarlyCallBenchmarkPolicy",
    "EarlyCallLeadTimeBenchmark",
    "ExternalCallLeadTimeBenchmark",
    "DexScreenerBenchmark",
    "DexScreenerBenchmarkBuilder",
]
