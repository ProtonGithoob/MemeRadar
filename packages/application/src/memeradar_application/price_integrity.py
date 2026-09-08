"""Reference-oracle versus executable-quote integrity evidence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from memeradar_domain import (
    Freshness,
    Provenance,
    QualityState,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)

REFERENCE_PRICE_VERSION = "reference-price-integrity-v1"


@dataclass(frozen=True, slots=True)
class ReferencePriceEvidence:
    chain: str
    asset_address: str
    reference_price: Decimal | None
    quote_price: Decimal | None
    deviation_bps: Decimal | None
    oracle_timestamp: datetime
    oracle_age_seconds: Decimal | None
    stale: bool
    market_integrity_risk: str
    as_of: datetime
    expires_at: datetime
    confidence: Decimal
    quality_state: QualityState
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    config_hash: str
    version: str = REFERENCE_PRICE_VERSION

    def __post_init__(self) -> None:
        normalized_chain = normalize_chain(self.chain)
        object.__setattr__(self, "chain", normalized_chain.value)
        object.__setattr__(
            self,
            "asset_address",
            require_chain_address(self.asset_address, normalized_chain, "asset_address"),
        )
        for field in ("reference_price", "quote_price", "deviation_bps", "oracle_age_seconds"):
            value = getattr(self, field)
            if value is not None:
                value = to_decimal(value, field)
                if value < 0:
                    raise ValueError(f"{field} must not be negative")
                if field in {"reference_price", "quote_price"} and value <= 0:
                    raise ValueError(f"{field} must be positive")
                object.__setattr__(self, field, value)
        for field in ("oracle_timestamp", "as_of", "expires_at"):
            object.__setattr__(self, field, ensure_utc(getattr(self, field), field))
        if self.expires_at <= self.as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "market_integrity_risk",
            require_text(
                self.market_integrity_risk, "market_integrity_risk", max_length=32
            ).upper(),
        )
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if any(not isinstance(value, Provenance) for value in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def execution_price(self) -> None:
        return None

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return self.reason_codes

    def execution_eligible(self, at: datetime) -> bool:
        del at
        return False


def compare_reference_price(
    chain: str,
    asset_address: str,
    reference_price: object,
    quote_price: object,
    oracle_timestamp: datetime,
    now: datetime,
    *,
    provenance: Sequence[Provenance],
    config_hash: str,
    max_oracle_age: timedelta = timedelta(minutes=5),
    deviation_threshold_bps: Decimal | int | str = Decimal("500"),
) -> ReferencePriceEvidence:
    checked_at = ensure_utc(now, "now")
    oracle_at = ensure_utc(oracle_timestamp, "oracle_timestamp")
    if max_oracle_age <= timedelta(0):
        raise ValueError("max_oracle_age must be positive")
    threshold = to_decimal(deviation_threshold_bps, "deviation_threshold_bps")
    if threshold < 0:
        raise ValueError("deviation_threshold_bps must not be negative")

    def positive(value: object, field: str) -> Decimal | None:
        try:
            result = to_decimal(value, field)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    reference = positive(reference_price, "reference_price")
    quote = positive(quote_price, "quote_price")
    age = Decimal(str((checked_at - oracle_at).total_seconds()))
    stale = age < 0 or age > Decimal(str(max_oracle_age.total_seconds()))
    deviation = (
        None
        if reference is None or quote is None
        else abs(quote - reference) / reference * Decimal("10000")
    )
    reasons: list[str] = []
    if reference is None or quote is None:
        quality = QualityState.UNKNOWN
        reasons.append("REFERENCE_OR_QUOTE_MISSING")
    elif stale:
        quality = QualityState.UNKNOWN
        reasons.append("ORACLE_STALE")
    else:
        quality = QualityState.FRESH
    large_deviation = deviation is not None and deviation > threshold
    if large_deviation:
        reasons.append("MARKET_INTEGRITY_DEVIATION")
    if not reasons:
        reasons.append("REFERENCE_PRICE_ALIGNED")
    return ReferencePriceEvidence(
        chain=chain,
        asset_address=asset_address,
        reference_price=reference,
        quote_price=quote,
        deviation_bps=deviation,
        oracle_timestamp=oracle_at,
        oracle_age_seconds=age if age >= 0 else None,
        stale=stale,
        market_integrity_risk="WARN"
        if large_deviation
        else ("UNKNOWN" if quality is not QualityState.FRESH else "CLEAR"),
        as_of=checked_at,
        expires_at=checked_at + max_oracle_age,
        confidence=Decimal("0")
        if quality is not QualityState.FRESH
        else (Decimal("0.50") if large_deviation else Decimal("0.90")),
        quality_state=quality,
        provenance=tuple(provenance),
        evidence_refs=tuple(item.source_id for item in provenance),
        reason_codes=tuple(dict.fromkeys(reasons)),
        config_hash=config_hash,
    )


__all__ = ["REFERENCE_PRICE_VERSION", "ReferencePriceEvidence", "compare_reference_price"]
