"""Fail-closed launch bundle, sniper and creator-related risk analysis."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID, uuid4

from memeradar_domain import Observation, Provenance, QualityState, ReasonCode, RiskDisposition
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .evidence_policy import production_observations

LAUNCH_RISK_VERSION = "launch-risk-v1"
_QUALITY_SEVERITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_MISSING = object()


def _reason(code: str, *, detail: str | None = None) -> ReasonCode:
    return ReasonCode(code, detail=detail)


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return _MISSING


def _fraction(value: object) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    parsed = to_decimal(value, "launch risk ratio")
    if not Decimal("0") <= parsed <= Decimal("1"):
        raise ValueError("launch risk ratios must be between zero and one")
    return parsed


@dataclass(frozen=True, slots=True)
class LaunchRiskPolicy:
    """Configuration-driven launch-risk thresholds; never inferred from timing."""

    bundle_concentration_block: Decimal = Decimal("0.70")
    first_block_concentration_block: Decimal = Decimal("0.80")
    creator_related_ratio_block: Decimal = Decimal("0.50")
    shared_funder_ratio_block: Decimal = Decimal("0.75")
    fresh_wallet_ratio_block: Decimal = Decimal("0.80")
    evidence_ttl: timedelta = timedelta(minutes=5)
    version: str = LAUNCH_RISK_VERSION
    config_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "bundle_concentration_block",
            "first_block_concentration_block",
            "creator_related_ratio_block",
            "shared_funder_ratio_block",
            "fresh_wallet_ratio_block",
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_decimal(
                    getattr(self, field_name),
                    field_name,
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        material = {
            field_name: str(getattr(self, field_name))
            for field_name in (
                "bundle_concentration_block",
                "first_block_concentration_block",
                "creator_related_ratio_block",
                "shared_funder_ratio_block",
                "fresh_wallet_ratio_block",
                "evidence_ttl",
                "version",
            )
        }
        calculated = (
            f"sha256:{hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}"
        )
        object.__setattr__(self, "config_hash", self.config_hash or calculated)


@dataclass(frozen=True, slots=True)
class LaunchRiskSnapshot:
    """Bounded launch-risk evidence with distinct UNKNOWN and BLOCK outcomes."""

    as_of: datetime
    bundle_concentration: Decimal | None
    first_block_concentration: Decimal | None
    creator_related_ratio: Decimal | None
    shared_funder_ratio: Decimal | None
    fresh_wallet_ratio: Decimal | None
    quality_state: QualityState
    confidence: Decimal
    risk_disposition: RiskDisposition
    hard_blocks: tuple[str, ...]
    penalties: Mapping[str, Decimal]
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    config_hash: str
    version: str = LAUNCH_RISK_VERSION
    token_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        if self.token_id is not None and not isinstance(self.token_id, UUID):
            raise TypeError("token_id must be a UUID or None")
        for field_name in (
            "bundle_concentration",
            "first_block_concentration",
            "creator_related_ratio",
            "shared_funder_ratio",
            "fresh_wallet_ratio",
        ):
            object.__setattr__(self, field_name, _fraction(getattr(self, field_name)))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "hard_blocks", normalize_texts(self.hard_blocks, "hard_blocks"))
        object.__setattr__(
            self,
            "penalties",
            MappingProxyType(
                {
                    require_text(key, "penalty key"): bounded_decimal(
                        value,
                        "penalty",
                        Decimal("0"),
                        Decimal("100"),
                    )
                    for key, value in self.penalties.items()
                }
            ),
        )
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    @property
    def data_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.bundle_concentration,
                self.first_block_concentration,
                self.creator_related_ratio,
                self.shared_funder_ratio,
                self.fresh_wallet_ratio,
            )
        )

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "bundle_concentration": self.bundle_concentration,
                "first_block_concentration": self.first_block_concentration,
                "creator_related_ratio": self.creator_related_ratio,
                "shared_funder_ratio": self.shared_funder_ratio,
                "fresh_wallet_ratio": self.fresh_wallet_ratio,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "risk_disposition": self.risk_disposition.value,
                "hard_blocks": self.hard_blocks,
                "penalties": self.penalties,
                "reason_codes": tuple(reason.code for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            },
            "launch_risk",
        )


class LaunchRiskAnalyzer:
    """Analyze explicit launch actor evidence and preserve missingness."""

    def __init__(self, policy: LaunchRiskPolicy | None = None) -> None:
        self.policy = policy or LaunchRiskPolicy()

    def evaluate(
        self,
        observations: Sequence[Observation] = (),
        *,
        as_of: datetime,
        token_id: UUID | None = None,
        launch_footprint: object | None = None,
        deployer_activity: object | None = None,
        holder_graph: object | None = None,
        include_shadow: bool = False,
    ) -> LaunchRiskSnapshot:
        checkpoint = ensure_utc(as_of, "as_of")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        normalized = production_observations(observations, include_shadow=include_shadow)
        actors: list[str] = []
        bundles: list[str] = []
        funders: list[str] = []
        creator_count = 0
        fresh_count = 0
        slots: list[tuple[int, str]] = []
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        quality_states: list[QualityState] = []
        for observation in normalized:
            if observation.occurred_at is not None and observation.occurred_at > checkpoint:
                quality_states.append(QualityState.INVALID)
                continue
            quality = QualityState(observation.quality_state)
            if quality is QualityState.FRESH and checkpoint >= (
                observation.observed_at + self.policy.evidence_ttl
            ):
                quality = QualityState.STALE
            quality_states.append(quality)
            provenance.append(observation.provenance)
            evidence_refs.append(f"observation:{observation.id}")
            payload = observation.normalized_payload
            actor = _field(payload, "wallet", "buyer_wallet", "buyer", "trader", "owner", "address")
            if actor is not _MISSING:
                actor_text = str(actor).strip()
                if actor_text:
                    actors.append(actor_text)
                    bundle = _field(
                        payload,
                        "bundle_id",
                        "bundle",
                        "bundle_cluster",
                        "actor_cluster",
                    )
                    bundles.append(str(bundle) if bundle is not _MISSING else "")
                    funder = _field(payload, "funder", "shared_funder", "funding_wallet")
                    funders.append(str(funder) if funder is not _MISSING else "")
                    if payload.get("creator_related") is True or payload.get("is_creator") is True:
                        creator_count += 1
                    if payload.get("fresh_wallet") is True or payload.get("wallet_age_seconds") in {
                        0,
                        "0",
                    }:
                        fresh_count += 1
                    slot = _field(payload, "slot", "first_block_slot")
                    if slot is not _MISSING:
                        try:
                            slots.append((int(str(slot)), actor_text))
                        except (TypeError, ValueError):
                            quality_states.append(QualityState.UNKNOWN)

        explicit = self._explicit_metrics(launch_footprint, deployer_activity, holder_graph)
        total = len(actors)
        metrics: dict[str, Decimal | None] = {
            "bundle_concentration": explicit.get("bundle_concentration")
            or self._group_concentration(bundles),
            "first_block_concentration": explicit.get("first_block_concentration")
            or self._first_block_concentration(slots, total),
            "creator_related_ratio": explicit.get("creator_related_ratio")
            or (Decimal(creator_count) / Decimal(total) if total else None),
            "shared_funder_ratio": explicit.get("shared_funder_ratio")
            or self._shared_ratio(funders),
            "fresh_wallet_ratio": explicit.get("fresh_wallet_ratio")
            or (Decimal(fresh_count) / Decimal(total) if total else None),
        }
        # Explicit zero is meaningful; the expression above treats it as a
        # missing value, so restore all supplied metrics after fallback.
        for key, explicit_value in explicit.items():
            if key in metrics and explicit_value is not None:
                metrics[key] = explicit_value
        quality = (
            QualityState.UNKNOWN
            if not quality_states
            else max(quality_states, key=lambda value: _QUALITY_SEVERITY[value])
        )
        available = sum(value is not None for value in metrics.values())
        confidence = (
            Decimal(available) / Decimal(len(metrics))
            if quality is QualityState.FRESH
            else Decimal("0")
        )
        hard_blocks: list[str] = []
        penalties: dict[str, Decimal] = {}
        if quality is QualityState.FRESH:
            thresholds = {
                "bundle_concentration": (
                    self.policy.bundle_concentration_block,
                    "BUNDLE_CONCENTRATION",
                ),
                "first_block_concentration": (
                    self.policy.first_block_concentration_block,
                    "FIRST_BLOCK_CONCENTRATION",
                ),
                "creator_related_ratio": (
                    self.policy.creator_related_ratio_block,
                    "CREATOR_RELATED_BUYING",
                ),
                "shared_funder_ratio": (
                    self.policy.shared_funder_ratio_block,
                    "SHARED_FUNDER_CONCENTRATION",
                ),
                "fresh_wallet_ratio": (
                    self.policy.fresh_wallet_ratio_block,
                    "FRESH_WALLET_CONCENTRATION",
                ),
            }
            for metric_name, (threshold, code) in thresholds.items():
                metric_value = metrics[metric_name]
                if metric_value is not None and metric_value >= threshold:
                    hard_blocks.append(code)
                    penalties[code] = bounded_decimal(
                        (metric_value - threshold) * Decimal("100"),
                        "penalty",
                        Decimal("0"),
                        Decimal("100"),
                    )
        reasons: list[ReasonCode] = []
        if not quality_states or not any(value is not None for value in metrics.values()):
            reasons.append(_reason("LAUNCH_RISK_EVIDENCE_UNKNOWN"))
        if any(value is None for value in metrics.values()):
            reasons.append(_reason("LAUNCH_RISK_EVIDENCE_INCOMPLETE"))
        if quality is not QualityState.FRESH and quality_states:
            reasons.append(_reason(f"LAUNCH_RISK_EVIDENCE_{quality.value}"))
        reasons.extend(_reason(code) for code in hard_blocks)
        if hard_blocks:
            disposition = RiskDisposition.BLOCK
        elif quality is QualityState.FRESH and not any(value is None for value in metrics.values()):
            disposition = RiskDisposition.PASS
        else:
            disposition = RiskDisposition.UNKNOWN
        return LaunchRiskSnapshot(
            as_of=checkpoint,
            bundle_concentration=metrics["bundle_concentration"],
            first_block_concentration=metrics["first_block_concentration"],
            creator_related_ratio=metrics["creator_related_ratio"],
            shared_funder_ratio=metrics["shared_funder_ratio"],
            fresh_wallet_ratio=metrics["fresh_wallet_ratio"],
            quality_state=quality,
            confidence=confidence,
            risk_disposition=disposition,
            hard_blocks=tuple(hard_blocks),
            penalties=penalties,
            reason_codes=tuple(reasons),
            evidence_refs=tuple(evidence_refs),
            provenance=tuple(provenance),
            config_hash=self.policy.config_hash,
            version=self.policy.version,
            token_id=token_id,
        )

    @staticmethod
    def _group_concentration(values: Sequence[str]) -> Decimal | None:
        present = tuple(value for value in values if value)
        if not present:
            return None
        counts = Counter(present)
        return Decimal(max(counts.values())) / Decimal(len(present))

    @staticmethod
    def _shared_ratio(values: Sequence[str]) -> Decimal | None:
        present = tuple(value for value in values if value)
        if not present:
            return None
        counts = Counter(present)
        shared = sum(count for count in counts.values() if count > 1)
        return Decimal(shared) / Decimal(len(present))

    @staticmethod
    def _first_block_concentration(values: Sequence[tuple[int, str]], total: int) -> Decimal | None:
        if not values or total == 0:
            return None
        first_slot = min(slot for slot, _ in values)
        first_actors = [actor for slot, actor in values if slot == first_slot]
        return Decimal(len(first_actors)) / Decimal(total)

    @staticmethod
    def _explicit_metrics(*sources: object | None) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        aliases = {
            "bundle_concentration": (
                "bundle_concentration",
                "actor_cluster_adjusted_concentration",
            ),
            "first_block_concentration": ("first_block_concentration", "first_slot_concentration"),
            "creator_related_ratio": ("creator_related_ratio", "creator_buy_ratio"),
            "shared_funder_ratio": ("shared_funder_ratio", "shared_funder_concentration"),
            "fresh_wallet_ratio": ("fresh_wallet_ratio",),
        }
        for source in sources:
            if source is None:
                continue
            for name, candidate_names in aliases.items():
                for candidate_name in candidate_names:
                    value = getattr(source, candidate_name, None)
                    if value is not None:
                        result[name] = bounded_decimal(
                            value,
                            candidate_name,
                            Decimal("0"),
                            Decimal("1"),
                        )
                        break
        return result


__all__ = ["LAUNCH_RISK_VERSION", "LaunchRiskAnalyzer", "LaunchRiskPolicy", "LaunchRiskSnapshot"]
