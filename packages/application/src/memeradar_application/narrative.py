"""Optional advisory narrative gateway with deterministic safety boundaries."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_domain import Observation, Provenance, QualityState, ReasonCode
from memeradar_domain.common import ensure_utc, require_text

from .provider_contracts import (
    NarrativeEvidence,
    NarrativeInput,
    NarrativeOrganicAssessment,
    NarrativePort,
    NarrativeSentiment,
    NarrativeSnapshot,
)

NARRATIVE_SCHEMA_VERSION = "narrative-v1"
NARRATIVE_GATEWAY_VERSION = "narrative-gateway-v1"
_SECRET_PATTERN = re.compile(
    r"(?is)\b(?:api[\s_-]*key|access[\s_-]*token|authorization|bearer|"
    r"private[\s_-]*key|seed(?:[\s_-]*phrase)?|password|session[\s_-]*token|cookie)"
    r"(?:\s*[:=]\s*|\s+)[^\s,;]+"
)
_INSTRUCTION_PATTERN = re.compile(
    r"(?is)\b(?:ignore|disregard|override)\s+(?:all\s+|any\s+|the\s+)?"
    r"(?:previous|prior|above|system|developer)?\s*instructions?\b"
)
_TOOL_PATTERN = re.compile(
    r"(?is)\b(?:call|invoke|use|run)\s+(?:a\s+)?"
    r"(?:trading|execution|wallet|system)?\s*(?:tool|function|command)\b"
)


def _bounded_positive_float(value: float, field: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{field} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 < normalized <= maximum:
        raise ValueError(f"{field} must be finite and between 0 and {maximum}")
    return normalized


def _bounded_positive_int(value: int, field: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= maximum:
        raise ValueError(f"{field} must be a positive integer no greater than {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class NarrativePolicy:
    """Bounded policy for optional narrative calls and derived snapshots."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    snapshot_ttl: timedelta = timedelta(minutes=5)
    cache_ttl: timedelta = timedelta(minutes=5)
    request_timeout_seconds: float = 2.0
    max_evidence: int = 100
    max_chars_per_evidence: int = 2_000
    max_total_chars: int = 12_000
    max_input_tokens: int = 3_000
    max_output_tokens: int = 500
    max_cost_usd: Decimal = Decimal("0.05")
    max_cache_entries: int = 512
    schema_version: str = NARRATIVE_SCHEMA_VERSION
    version: str = NARRATIVE_GATEWAY_VERSION

    def __post_init__(self) -> None:
        for field_name in ("evidence_ttl", "snapshot_ttl", "cache_ttl"):
            value = getattr(self, field_name)
            if value <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        object.__setattr__(
            self,
            "request_timeout_seconds",
            _bounded_positive_float(self.request_timeout_seconds, "request_timeout_seconds", 60.0),
        )
        for field_name, maximum in (
            ("max_evidence", 100),
            ("max_chars_per_evidence", 20_000),
            ("max_total_chars", 100_000),
            ("max_input_tokens", 100_000),
            ("max_output_tokens", 10_000),
            ("max_cache_entries", 10_000),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_int(getattr(self, field_name), field_name, maximum),
            )
        max_cost = Decimal(str(self.max_cost_usd))
        if not max_cost.is_finite() or max_cost <= 0 or max_cost > Decimal("1000"):
            raise ValueError("max_cost_usd must be finite and between 0 and 1000")
        object.__setattr__(self, "max_cost_usd", max_cost)
        if self.max_total_chars < self.max_chars_per_evidence:
            raise ValueError("max_total_chars must meet max_chars_per_evidence")
        object.__setattr__(
            self,
            "schema_version",
            require_text(self.schema_version, "schema_version", max_length=64),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class NarrativeCache:
    """Small in-process cache whose entries are reused only while fresh."""

    def __init__(self, *, max_entries: int = 512) -> None:
        self._max_entries = _bounded_positive_int(max_entries, "max_entries", 10_000)
        self._entries: dict[str, NarrativeSnapshot] = {}

    @property
    def size(self) -> int:
        return len(self._entries)

    def get(self, key: str, *, now: datetime) -> NarrativeSnapshot | None:
        normalized_now = ensure_utc(now, "now")
        snapshot = self._entries.get(key)
        if snapshot is None:
            return None
        if not snapshot.freshness.is_fresh(normalized_now):
            self._entries.pop(key, None)
            return None
        return snapshot

    def put(self, key: str, snapshot: NarrativeSnapshot) -> None:
        if not isinstance(snapshot, NarrativeSnapshot):
            raise TypeError("snapshot must be a NarrativeSnapshot")
        if key in self._entries:
            self._entries.pop(key)
        elif len(self._entries) >= self._max_entries:
            oldest_key = next(iter(self._entries))
            self._entries.pop(oldest_key)
        self._entries[key] = snapshot

    def clear(self) -> None:
        self._entries.clear()


def _safe_plain_text(value: str, *, maximum: int) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(
        character
        if character in "\n\r\t" and character != "\x00"
        or (ord(character) >= 32 and ord(character) != 127)
        else " "
        for character in normalized
    )
    normalized = normalized.replace("<", "&lt;").replace(">", "&gt;")
    normalized = _SECRET_PATTERN.sub("[REDACTED_SECRET]", normalized)
    normalized = _INSTRUCTION_PATTERN.sub("[UNTRUSTED_INSTRUCTION_TEXT]", normalized)
    normalized = _TOOL_PATTERN.sub("[UNTRUSTED_TOOL_TEXT]", normalized)
    return normalized[:maximum].strip() or "[EMPTY_UNTRUSTED_DATA]"


def _delimit_untrusted(value: str, *, maximum: int) -> str:
    return f"<UNTRUSTED_DATA>{_safe_plain_text(value, maximum=maximum)}</UNTRUSTED_DATA>"


def _safe_value(value: object, *, maximum: int) -> object:
    if isinstance(value, str):
        return _safe_plain_text(value, maximum=maximum)
    if isinstance(value, Mapping):
        return {
            str(key)[:128]: _safe_value(item, maximum=maximum)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_safe_value(item, maximum=maximum) for item in value[:100])
    if isinstance(value, datetime):
        return ensure_utc(value, "narrative timestamp").isoformat()
    return value


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return ensure_utc(value, "narrative timestamp").isoformat()
    if hasattr(value, "value"):
        enum_value = value.value
        if isinstance(enum_value, str):
            return enum_value
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _reason_codes(
    values: Sequence[ReasonCode | str],
    extra: str | None = None,
) -> tuple[ReasonCode | str, ...]:
    normalized = list(values)
    if extra is not None and extra not in normalized:
        normalized.append(extra)
    return tuple(normalized)


class NarrativeAnalyzer:
    """Run optional narrative analysis without coupling deterministic paths to an LLM."""

    def __init__(
        self,
        provider: NarrativePort,
        *,
        policy: NarrativePolicy | None = None,
        cache: NarrativeCache | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not hasattr(provider, "summarize"):
            raise TypeError("provider must implement NarrativePort")
        self.provider = provider
        self.policy = policy or NarrativePolicy()
        self.cache = cache or NarrativeCache(max_entries=self.policy.max_cache_entries)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _canonicalize(
        self,
        request: NarrativeInput,
        *,
        now: datetime,
    ) -> tuple[NarrativeInput, tuple[str, ...], int]:
        if not isinstance(request, NarrativeInput):
            raise TypeError("request must be a NarrativeInput")
        policy = self.policy
        reasons: list[str] = []
        evidence_values: tuple[NarrativeEvidence | Observation, ...] = (
            *request.evidence,
            *request.observations,
        )
        for item in evidence_values:
            observed_at = item.observed_at
            quality_state = item.quality_state
            if (
                quality_state is not QualityState.FRESH
                or observed_at > now
                or observed_at < now - policy.evidence_ttl
            ):
                reasons.append("NARRATIVE_EVIDENCE_NOT_FRESH")
        evidence = request.evidence[: policy.max_evidence]
        if len(evidence) != len(request.evidence):
            reasons.append("NARRATIVE_INPUT_TRUNCATED")
        remaining_chars = min(policy.max_total_chars, policy.max_input_tokens * 4)
        safe_evidence: list[NarrativeEvidence] = []
        for item in evidence:
            raw_content = item.content
            allowed = min(policy.max_chars_per_evidence, max(1, remaining_chars))
            if len(raw_content) > allowed:
                reasons.append("NARRATIVE_INPUT_TRUNCATED")
            safe_content = _delimit_untrusted(raw_content, maximum=allowed)
            safe_metadata = _safe_value(item.metadata, maximum=policy.max_chars_per_evidence)
            if not isinstance(safe_metadata, Mapping):
                raise TypeError("narrative evidence metadata must remain a mapping")
            safe_evidence.append(
                replace(
                    item,
                    content=safe_content,
                    metadata=safe_metadata,
                )
            )
            remaining_chars = max(0, remaining_chars - min(len(raw_content), allowed))
        safe_observations = tuple(
            self._safe_observation(observation, maximum=policy.max_chars_per_evidence)
            for observation in request.observations
        )
        normalized = replace(
            request,
            observations=safe_observations,
            evidence=tuple(safe_evidence),
            schema_version=policy.schema_version,
        )
        canonical = self._canonical_document(normalized)
        input_tokens = max(1, math.ceil(len(json.dumps(canonical, sort_keys=True)) / 4))
        if input_tokens > policy.max_input_tokens:
            reasons.append("NARRATIVE_INPUT_TRUNCATED")
            input_tokens = policy.max_input_tokens
        return normalized, tuple(dict.fromkeys(reasons)), input_tokens

    @staticmethod
    def _safe_observation(observation: Observation, *, maximum: int) -> Observation:
        safe_payload = _safe_value(
            observation.normalized_payload,
            maximum=maximum,
        )
        if not isinstance(safe_payload, Mapping):
            raise TypeError("narrative observation payload must remain a mapping")
        return replace(observation, normalized_payload=safe_payload)

    @staticmethod
    def _canonical_document(request: NarrativeInput) -> dict[str, object]:
        return {
            "schema_version": request.schema_version,
            "config_hash": request.config_hash,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "kind": item.kind,
                    "content": item.content,
                    "observed_at": item.observed_at.isoformat(),
                    "quality_state": item.quality_state.value,
                    "provenance": {
                        "provider": item.provenance.provider,
                        "source_id": item.provenance.source_id,
                        "parser_version": item.provenance.parser_version,
                    },
                    "metadata": _json_value(item.metadata),
                }
                for item in request.evidence
            ],
            "observations": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "occurred_at": None
                    if item.occurred_at is None
                    else item.occurred_at.isoformat(),
                    "observed_at": item.observed_at.isoformat(),
                    "quality_state": item.quality_state.value,
                    "provenance": {
                        "provider": item.provenance.provider,
                        "source_id": item.provenance.source_id,
                        "parser_version": item.provenance.parser_version,
                    },
                    "normalized_payload": _json_value(item.normalized_payload),
                }
                for item in request.observations
            ],
        }

    def _cache_key(self, request: NarrativeInput) -> str:
        payload = json.dumps(
            self._canonical_document(request),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _evidence_refs(request: NarrativeInput) -> tuple[str, ...]:
        values: list[str] = []
        for value in (
            *(item.evidence_id for item in request.evidence),
            *(item.provenance.source_id for item in request.observations),
        ):
            if value not in values:
                values.append(value)
        return tuple(values)

    def _fallback(
        self,
        request: NarrativeInput,
        *,
        key: str,
        input_tokens: int,
        reasons: Sequence[str],
        now: datetime,
    ) -> NarrativeSnapshot:
        normalized_reasons = list(reasons)
        if not normalized_reasons:
            normalized_reasons.append("NARRATIVE_UNAVAILABLE")
        if "NARRATIVE_UNAVAILABLE" not in normalized_reasons:
            normalized_reasons.append("NARRATIVE_UNAVAILABLE")
        provenance = Provenance(
            provider="narrative-gateway",
            source_id=f"fallback:{key[7:]}",
            observed_at=now,
            parser_version=NARRATIVE_GATEWAY_VERSION,
            raw_payload_hash=key,
        )
        return NarrativeSnapshot(
            provenance=provenance,
            as_of=now,
            expires_at=now + self.policy.snapshot_ttl,
            narrative="Narrative unavailable; deterministic evidence remains authoritative.",
            topic="unknown",
            novelty=0,
            organic_assessment=NarrativeOrganicAssessment.UNKNOWN,
            organic_probability=Decimal("0.5"),
            promotional_probability=Decimal("0.5"),
            sentiment=NarrativeSentiment.UNKNOWN,
            uncertainty=1,
            confidence=0,
            evidence_refs=self._evidence_refs(request),
            usage={
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "total_tokens": input_tokens,
                "estimated_cost_usd": "0",
            },
            model="unavailable",
            schema_version=self.policy.schema_version,
            config_hash=request.config_hash,
            cache_key=key,
            reason_codes=tuple(normalized_reasons),
            quality_state=QualityState.UNKNOWN,
        )

    def _validate_output(
        self,
        result: object,
        request: NarrativeInput,
        *,
        key: str,
        now: datetime,
    ) -> NarrativeSnapshot:
        if not isinstance(result, NarrativeSnapshot):
            raise ValueError("narrative provider did not return a strict snapshot")
        if result.schema_version != request.schema_version:
            raise ValueError("narrative schema version mismatch")
        if result.config_hash != request.config_hash:
            raise ValueError("narrative config hash mismatch")
        if result.quality_state is not QualityState.FRESH or not result.freshness.is_fresh(now):
            raise ValueError("narrative output was not fresh")
        allowed_refs = set(self._evidence_refs(request))
        if any(reference not in allowed_refs for reference in result.evidence_refs):
            raise ValueError("narrative output referenced unknown evidence")
        usage = result.usage
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, int) and input_tokens > self.policy.max_input_tokens:
            raise ValueError("narrative input token budget exceeded")
        if isinstance(output_tokens, int) and output_tokens > self.policy.max_output_tokens:
            raise ValueError("narrative output token budget exceeded")
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int) and total_tokens > (
            self.policy.max_input_tokens + self.policy.max_output_tokens
        ):
            raise ValueError("narrative total token budget exceeded")
        cost = usage.get("estimated_cost_usd")
        if isinstance(cost, Decimal) and cost > self.policy.max_cost_usd:
            raise ValueError("narrative cost budget exceeded")
        return replace(
            result,
            cache_key=key,
            cache_hit=False,
            reason_codes=_reason_codes(result.reason_codes, "NARRATIVE_ADVISORY"),
        )

    async def summarize(self, request: NarrativeInput) -> NarrativeSnapshot:
        """Return a strict advisory result, falling back without raising provider errors."""

        now = ensure_utc(self._clock(), "now")
        try:
            normalized, input_reasons, input_tokens = self._canonicalize(request, now=now)
            key = self._cache_key(normalized)
        except Exception:
            # Input is expected to be validated by NarrativeInput; retain a safe
            # local failure boundary if a caller supplies a malformed object.
            if not isinstance(request, NarrativeInput):
                raise
            key = f"sha256:{hashlib.sha256(request.config_hash.encode()).hexdigest()}"
            return self._fallback(
                request,
                key=key,
                input_tokens=0,
                reasons=("NARRATIVE_INPUT_INVALID",),
                now=now,
            )
        cached = self.cache.get(key, now=now)
        if cached is not None:
            return replace(
                cached,
                cache_hit=True,
                reason_codes=_reason_codes(cached.reason_codes, "NARRATIVE_CACHE_HIT"),
            )
        reasons = list(input_reasons)
        if "NARRATIVE_EVIDENCE_NOT_FRESH" in reasons:
            return self._fallback(
                request,
                key=key,
                input_tokens=input_tokens,
                reasons=reasons,
                now=now,
            )
        try:
            result = await asyncio.wait_for(
                self.provider.summarize(normalized),
                timeout=self.policy.request_timeout_seconds,
            )
            validated = self._validate_output(result, normalized, key=key, now=now)
        except TimeoutError:
            reasons.append("NARRATIVE_TIMEOUT")
            return self._fallback(
                request,
                key=key,
                input_tokens=input_tokens,
                reasons=reasons,
                now=now,
            )
        except ValueError:
            reasons.append("NARRATIVE_SCHEMA_INVALID")
            return self._fallback(
                request,
                key=key,
                input_tokens=input_tokens,
                reasons=reasons,
                now=now,
            )
        except Exception:
            reasons.append("NARRATIVE_PROVIDER_UNAVAILABLE")
            return self._fallback(
                request,
                key=key,
                input_tokens=input_tokens,
                reasons=reasons,
                now=now,
            )
        if reasons:
            validated = replace(
                validated,
                reason_codes=_reason_codes(validated.reason_codes, reasons[0]),
            )
        cache_snapshot = replace(
            validated,
            expires_at=min(validated.expires_at, now + self.policy.cache_ttl),
        )
        self.cache.put(key, cache_snapshot)
        return validated

    async def analyze(self, request: NarrativeInput) -> NarrativeSnapshot:
        """Alias for callers that use analysis terminology instead of provider terminology."""

        return await self.summarize(request)


__all__ = [
    "NARRATIVE_GATEWAY_VERSION",
    "NARRATIVE_SCHEMA_VERSION",
    "NarrativeAnalyzer",
    "NarrativeCache",
    "NarrativePolicy",
]
