"""Provider-neutral price-role resolution for fills, marks and replay.

The resolver deliberately refuses to turn an ambiguous generic price into a
market mark.  A transaction/fill price is execution evidence; market and
reference prices are separate analytical evidence with their own freshness and
provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from memeradar_domain import (
    Freshness,
    Observation,
    PriceSemantics,
    Provenance,
    QualityState,
)
from memeradar_domain.common import ensure_utc, normalize_texts, require_text, to_decimal

PRICE_SEMANTICS_VERSION = "price-semantics-v1"
DEFAULT_PRICE_EVIDENCE_TTL = timedelta(minutes=5)
_MISSING = object()

_MARKET_KINDS = frozenset(
    {
        "market.snapshot",
        "market.market_data",
        "market.price",
    }
)
_EXECUTION_KINDS = frozenset(
    {
        "market.trade",
        "market.trades",
        "market.trade_data",
        "wallet.activity",
        "wallet.trade",
        "wallet.swap",
        "paper.fill",
        "paper_fill",
    }
)
_MARKET_FIELDS = (
    "market_price",
    "market_price_usd",
    "marketPrice",
    "marketPriceUsd",
    "reference_price",
    "reference_price_usd",
    "referencePrice",
    "price_usd",
    "priceUsd",
    "token_price",
    "last_price",
    "close",
)
_EXECUTION_FIELDS = (
    "execution_price",
    "executed_price",
    "effective_price",
    "fill_price",
)
_GENERIC_PRICE_FIELDS = ("price",)


def _field(payload: Mapping[str, object], *names: str) -> tuple[str, object] | None:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return name, value
    return None


def _normalize_semantics(value: object) -> PriceSemantics | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, PriceSemantics):
        return value
    normalized = str(value).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "EXECUTION": PriceSemantics.EXECUTION_EFFECTIVE,
        "EXECUTED": PriceSemantics.EXECUTION_EFFECTIVE,
        "EFFECTIVE": PriceSemantics.EXECUTION_EFFECTIVE,
        "FILL": PriceSemantics.EXECUTION_EFFECTIVE,
        "QUOTE": PriceSemantics.EXECUTION_QUOTE,
        "MARKET": PriceSemantics.MARKET_REFERENCE,
        "REFERENCE": PriceSemantics.MARKET_REFERENCE,
        "MARK": PriceSemantics.MARKET_REFERENCE,
        "UNKNOWN": PriceSemantics.UNKNOWN,
    }
    try:
        return PriceSemantics(normalized)
    except ValueError:
        return aliases.get(normalized, PriceSemantics.UNKNOWN)


def _quality_at(
    quality_state: QualityState,
    *,
    observed_at: datetime,
    provenance: Sequence[Provenance],
    now: datetime,
    ttl: timedelta,
    occurred_at: datetime | None = None,
) -> QualityState:
    if quality_state is not QualityState.FRESH:
        return quality_state
    if now < observed_at or (occurred_at is not None and occurred_at > now):
        return QualityState.INVALID
    if any(source.observed_at > now for source in provenance):
        return QualityState.INVALID
    if now >= observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


@dataclass(frozen=True, slots=True)
class PriceEvidence:
    """One typed price value with role, freshness and source identity."""

    price: Decimal | None
    semantics: PriceSemantics | str
    source_field: str | None
    as_of: datetime
    expires_at: datetime
    quality_state: QualityState
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    version: str = PRICE_SEMANTICS_VERSION

    def __post_init__(self) -> None:
        semantics = PriceSemantics(self.semantics)
        if self.price is None and semantics is not PriceSemantics.UNKNOWN:
            semantics = PriceSemantics.UNKNOWN
        if self.price is not None:
            value = to_decimal(self.price, "price")
            if value <= 0:
                raise ValueError("price must be positive")
            object.__setattr__(self, "price", value)
        object.__setattr__(self, "semantics", semantics)
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, "as_of"))
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at, "expires_at"))
        if self.expires_at <= self.as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.source_field is not None:
            object.__setattr__(
                self,
                "source_field",
                require_text(self.source_field, "source_field", max_length=64),
            )
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def role(self) -> PriceSemantics:
        """Compatibility alias for callers that use role terminology."""

        return PriceSemantics(self.semantics)

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def is_usable(self, at: datetime, *, semantics: PriceSemantics) -> bool:
        return (
            self.semantics is semantics
            and self.price is not None
            and self.freshness.is_fresh(at)
        )


def _resolve_input(
    value: Observation | Mapping[str, object],
    *,
    kind: str | None,
    observed_at: datetime | None,
    occurred_at: datetime | None,
    quality_state: QualityState,
    provenance: Sequence[Provenance],
    evidence_refs: Sequence[str],
) -> tuple[Mapping[str, object], str, datetime, datetime | None, QualityState, tuple[Provenance, ...], tuple[str, ...]]:
    if isinstance(value, Observation):
        if kind is not None or observed_at is not None or provenance:
            raise TypeError("observation input cannot be combined with explicit metadata")
        return (
            value.normalized_payload,
            value.kind,
            value.observed_at,
            value.occurred_at,
            value.quality_state,
            (value.provenance,),
            (),
        )
    if not isinstance(value, Mapping):
        raise TypeError("value must be an Observation or mapping")
    if kind is None or observed_at is None:
        raise TypeError("mapping input requires kind and observed_at")
    return (
        value,
        require_text(kind, "kind"),
        ensure_utc(observed_at, "observed_at"),
        None if occurred_at is None else ensure_utc(occurred_at, "occurred_at"),
        QualityState(quality_state),
        tuple(provenance),
        normalize_texts(evidence_refs, "evidence_refs"),
    )


def resolve_price_evidence(
    value: Observation | Mapping[str, object],
    *,
    kind: str | None = None,
    observed_at: datetime | None = None,
    occurred_at: datetime | None = None,
    quality_state: QualityState = QualityState.FRESH,
    provenance: Sequence[Provenance] = (),
    evidence_refs: Sequence[str] = (),
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_PRICE_EVIDENCE_TTL,
) -> PriceEvidence:
    """Resolve one price without crossing execution and market semantics."""

    if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
        raise ValueError("ttl must be positive")
    (
        payload,
        normalized_kind,
        normalized_observed_at,
        normalized_occurred_at,
        normalized_quality,
        normalized_provenance,
        normalized_refs,
    ) = _resolve_input(
        value,
        kind=kind,
        observed_at=observed_at,
        occurred_at=occurred_at,
        quality_state=quality_state,
        provenance=provenance,
        evidence_refs=evidence_refs,
    )
    checked_at = normalized_observed_at if now is None else ensure_utc(now, "now")
    raw_semantics = _field(payload, "price_semantics", "price_role", "price_type")
    explicit_semantics = None if raw_semantics is None else _normalize_semantics(raw_semantics[1])

    selected: tuple[str, object] | None = None
    semantics = explicit_semantics
    if semantics is PriceSemantics.MARKET_REFERENCE:
        selected = _field(payload, *_MARKET_FIELDS)
    elif semantics in {PriceSemantics.EXECUTION_EFFECTIVE, PriceSemantics.EXECUTION_QUOTE}:
        selected = _field(payload, *_EXECUTION_FIELDS)
        if selected is None:
            selected = _field(payload, *_GENERIC_PRICE_FIELDS)
    elif semantics is PriceSemantics.UNKNOWN:
        selected = None
    elif normalized_kind in _MARKET_KINDS:
        selected = _field(payload, *_MARKET_FIELDS)
        if selected is not None:
            semantics = PriceSemantics.MARKET_REFERENCE
        else:
            selected = _field(payload, *_GENERIC_PRICE_FIELDS)
            if selected is not None:
                semantics = PriceSemantics.MARKET_REFERENCE
    elif normalized_kind in _EXECUTION_KINDS:
        selected = _field(payload, *_EXECUTION_FIELDS)
        if selected is not None:
            semantics = PriceSemantics.EXECUTION_EFFECTIVE
        else:
            selected = _field(payload, *_GENERIC_PRICE_FIELDS)
            if selected is not None:
                semantics = PriceSemantics.EXECUTION_EFFECTIVE
    else:
        selected = None

    if selected is None or selected[1] is None:
        return PriceEvidence(
            price=None,
            semantics=PriceSemantics.UNKNOWN,
            source_field=None if selected is None else selected[0],
            as_of=normalized_observed_at,
            expires_at=normalized_observed_at + ttl,
            quality_state=(
                normalized_quality
                if normalized_quality is not QualityState.FRESH
                else QualityState.UNKNOWN
            ),
            provenance=normalized_provenance,
            evidence_refs=normalized_refs,
        )

    raw_price = selected[1]
    price = to_decimal(raw_price, "price")
    if price <= 0:
        raise ValueError("price must be positive")
    if semantics is None:
        semantics = PriceSemantics.UNKNOWN
    resolved_quality = _quality_at(
        normalized_quality,
        observed_at=normalized_observed_at,
        provenance=normalized_provenance,
        now=checked_at,
        ttl=ttl,
        occurred_at=normalized_occurred_at,
    )
    if resolved_quality is QualityState.INVALID:
        return PriceEvidence(
            price=None,
            semantics=PriceSemantics.UNKNOWN,
            source_field=selected[0],
            as_of=normalized_observed_at,
            expires_at=normalized_observed_at + ttl,
            quality_state=resolved_quality,
            provenance=normalized_provenance,
            evidence_refs=normalized_refs,
        )
    return PriceEvidence(
        price=price,
        semantics=semantics,
        source_field=selected[0],
        as_of=normalized_observed_at,
        expires_at=normalized_observed_at + ttl,
        quality_state=resolved_quality,
        provenance=normalized_provenance,
        evidence_refs=normalized_refs,
    )


def market_reference_price(
    value: Observation | Mapping[str, object],
    *,
    kind: str | None = None,
    observed_at: datetime | None = None,
    occurred_at: datetime | None = None,
    quality_state: QualityState = QualityState.FRESH,
    provenance: Sequence[Provenance] = (),
    evidence_refs: Sequence[str] = (),
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_PRICE_EVIDENCE_TTL,
) -> Decimal | None:
    """Return a usable market mark, never an execution-only price."""

    evidence = resolve_price_evidence(
        value,
        kind=kind,
        observed_at=observed_at,
        occurred_at=occurred_at,
        quality_state=quality_state,
        provenance=provenance,
        evidence_refs=evidence_refs,
        now=now,
        ttl=ttl,
    )
    if evidence.semantics is not PriceSemantics.MARKET_REFERENCE:
        return None
    return evidence.price


__all__ = [
    "DEFAULT_PRICE_EVIDENCE_TTL",
    "PRICE_SEMANTICS_VERSION",
    "PriceEvidence",
    "PriceSemantics",
    "market_reference_price",
    "resolve_price_evidence",
]
