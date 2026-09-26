"""Provider-neutral price agreement over existing typed price evidence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from memeradar_domain import Freshness, PriceSemantics, Provenance, QualityState
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)

from .price_semantics import PriceEvidence
from .reliability import ReliabilityTelemetry, emit_provider_conflict

PRICE_CONSENSUS_VERSION = "price-consensus-v1"


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """One provider/reference mark eligible for consensus, never a fill."""

    source: str
    price: Decimal | int | str
    observed_at: datetime
    quality_state: QualityState = QualityState.FRESH
    confidence: Decimal | int | str = Decimal("1")
    provenance: tuple[Provenance, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_text(self.source, "source", max_length=128))
        price = to_decimal(self.price, "price")
        if price <= 0:
            raise ValueError("price must be positive")
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True, slots=True)
class PriceConsensus:
    price: Decimal | None
    source: str | None
    observed_at: datetime
    freshness: Freshness
    quality_state: QualityState
    confidence: Decimal
    disagreement_bps: Decimal | None
    source_count: int
    provenance: tuple[Provenance, ...]
    reason_codes: tuple[str, ...]
    version: str = PRICE_CONSENSUS_VERSION

    def __post_init__(self) -> None:
        if self.price is not None:
            price = to_decimal(self.price, "price")
            if price <= 0:
                raise ValueError("price must be positive")
            object.__setattr__(self, "price", price)
        if self.source is not None:
            object.__setattr__(self, "source", require_text(self.source, "source", max_length=256))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))
        if not isinstance(self.freshness, Freshness):
            raise TypeError("freshness must be a Freshness")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        if self.disagreement_bps is not None:
            disagreement = to_decimal(self.disagreement_bps, "disagreement_bps")
            if disagreement < 0:
                raise ValueError("disagreement_bps must not be negative")
            object.__setattr__(self, "disagreement_bps", disagreement)
        if (
            not isinstance(self.source_count, int)
            or isinstance(self.source_count, bool)
            or self.source_count < 0
        ):
            raise ValueError("source_count must be a non-negative integer")
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def usable_for_market_reference(self) -> bool:
        return self.price is not None and self.quality_state is QualityState.FRESH


class PriceConsensusService:
    """Choose a robust market mark without blindly falling back between providers."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=5),
        disagreement_threshold_bps: Decimal | int | str = Decimal("500"),
        telemetry: ReliabilityTelemetry | None = None,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        threshold = to_decimal(disagreement_threshold_bps, "disagreement_threshold_bps")
        if threshold < 0:
            raise ValueError("disagreement_threshold_bps must not be negative")
        self.ttl = ttl
        self.disagreement_threshold_bps = threshold
        self._telemetry = telemetry

    @staticmethod
    def _as_observation(value: PriceObservation | PriceEvidence) -> PriceObservation | None:
        if isinstance(value, PriceObservation):
            return value
        if not isinstance(value, PriceEvidence):
            raise TypeError("observations must contain PriceObservation or PriceEvidence values")
        if value.price is None or value.semantics is not PriceSemantics.MARKET_REFERENCE:
            return None
        source = value.provenance[0].provider if value.provenance else "unknown"
        return PriceObservation(
            source=source,
            price=value.price,
            observed_at=value.as_of,
            quality_state=value.quality_state,
            confidence=Decimal("1") if value.quality_state is QualityState.FRESH else Decimal("0"),
            provenance=value.provenance,
        )

    def resolve(
        self,
        observations: Sequence[PriceObservation | PriceEvidence],
        *,
        now: datetime,
    ) -> PriceConsensus:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        if len(observations) > 64:
            raise ValueError("price observations exceeded the configured bound")
        checked_at = ensure_utc(now, "now")
        normalized = tuple(
            value for item in observations if (value := self._as_observation(item)) is not None
        )
        fresh: list[PriceObservation] = []
        stale = False
        for value in normalized:
            if value.quality_state is not QualityState.FRESH:
                stale = stale or value.quality_state is QualityState.STALE
                continue
            if value.observed_at > checked_at:
                continue
            if checked_at >= value.observed_at + self.ttl:
                stale = True
                continue
            fresh.append(value)
        freshness = Freshness(
            as_of=checked_at,
            expires_at=checked_at + self.ttl,
            quality_state=(
                QualityState.FRESH
                if fresh
                else QualityState.STALE
                if stale
                else QualityState.UNKNOWN
            ),
        )
        if not fresh:
            return PriceConsensus(
                price=None,
                source=None,
                observed_at=checked_at,
                freshness=freshness,
                quality_state=freshness.quality_state,
                confidence=Decimal("0"),
                disagreement_bps=None,
                source_count=0,
                provenance=tuple(source for value in normalized for source in value.provenance),
                reason_codes=("PRICE_EVIDENCE_STALE" if stale else "PRICE_EVIDENCE_UNKNOWN",),
            )
        ordered = sorted(fresh, key=lambda value: to_decimal(value.price, "price"))
        middle = len(ordered) // 2
        middle_price = to_decimal(ordered[middle].price, "price")
        median = (
            middle_price
            if len(ordered) % 2
            else (
                to_decimal(ordered[middle - 1].price, "price") + middle_price
            )
            / Decimal("2")
        )
        disagreement = (
            Decimal("0")
            if len(ordered) == 1
            else (
                to_decimal(ordered[-1].price, "price")
                - to_decimal(ordered[0].price, "price")
            )
            / median
            * Decimal("10000")
        )
        conflicted = disagreement > self.disagreement_threshold_bps
        provider_names = tuple(sorted({value.source for value in ordered}))
        if len(provider_names) == 2:
            emit_provider_conflict(
                self._telemetry,
                "price_conflict",
                provider_names[0],
                provider_names[1],
                conflicted=conflicted,
            )
        quality = QualityState.CONFLICTED if conflicted else QualityState.FRESH
        confidence = min(
            (to_decimal(value.confidence, "confidence") for value in fresh),
            default=Decimal("0"),
        )
        if conflicted:
            confidence *= Decimal("0.25")
        reasons = ["PRICE_CONSENSUS" if len(ordered) > 1 else "PRICE_SINGLE_SOURCE"]
        if conflicted:
            reasons.append("PRICE_PROVIDER_DISAGREEMENT")
        if stale:
            reasons.append("STALE_SOURCE_EXCLUDED")
        return PriceConsensus(
            price=median,
            source="consensus" if len(ordered) > 1 else ordered[0].source,
            observed_at=max(value.observed_at for value in ordered),
            freshness=Freshness(checked_at, checked_at + self.ttl, quality),
            quality_state=quality,
            confidence=confidence,
            disagreement_bps=disagreement,
            source_count=len(ordered),
            provenance=tuple(source for value in ordered for source in value.provenance),
            reason_codes=tuple(reasons),
        )


__all__ = [
    "PRICE_CONSENSUS_VERSION",
    "PriceConsensus",
    "PriceConsensusService",
    "PriceObservation",
]
