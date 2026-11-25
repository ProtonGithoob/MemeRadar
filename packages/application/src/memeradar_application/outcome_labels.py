"""M2: decision-anchored outcome labels with three independent price semantics.

A chart multiple is not money.  For each decision and horizon this module
labels separately:

* ``MARKET_MARK`` -- best *corroborated* market/reference price inside
  ``(decided_at, decided_at + horizon]`` over the eligible decision mark;
* ``EXECUTABLE_QUOTE_PEAK`` -- a hypothetical delayed entry of a stated USD
  size (first eligible entry quote at or after ``decided_at + delay``), then
  the best eligible *exit quote for exactly the tokens bought*, net of entry
  fees, before the horizon closes;
* ``PAPER_REALIZED`` -- only fills a simulated policy actually recorded; never
  inferred from marks or another policy.

Every label states its anchor, resolution and, when it cannot be computed, a
censor reason (immature horizon, no eligible entry or exit quote, missing
decision mark).  The decision snapshot hash depends only on decision-time
inputs, so mutating future evidence can never change it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from memeradar_domain.common import ensure_utc, require_text

OUTCOME_LABEL_V2_VERSION = "decision-outcome-labels-v1"
THRESHOLDS: tuple[int, ...] = (2, 5, 10, 20, 50, 100)
DEFAULT_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1h", timedelta(hours=1)),
    ("6h", timedelta(hours=6)),
    ("24h", timedelta(hours=24)),
    ("72h", timedelta(hours=72)),
)


class Semantics(str, Enum):
    MARKET_MARK = "MARKET_MARK"
    EXECUTABLE_QUOTE_PEAK = "EXECUTABLE_QUOTE_PEAK"
    PAPER_REALIZED = "PAPER_REALIZED"


class LabelStatus(str, Enum):
    MATURE = "MATURE"
    PENDING = "PENDING"
    CENSORED = "CENSORED"


@dataclass(frozen=True, slots=True)
class DecisionAnchor:
    """Decision-time inputs only; the snapshot hash is computed from these."""

    decision_id: str
    asset: str
    decided_at: datetime
    decision_mark_price_usd: Decimal | None
    feature_snapshot: Mapping[str, object] = field(default_factory=dict)
    versions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "asset", require_text(self.asset, "asset"))
        object.__setattr__(self, "decided_at", ensure_utc(self.decided_at, "decided_at"))

    @property
    def snapshot_hash(self) -> str:
        return _hash(
            {
                "decision_id": self.decision_id,
                "asset": self.asset,
                "decided_at": self.decided_at.isoformat(),
                "decision_mark_price_usd": _text(self.decision_mark_price_usd),
                "features": dict(self.feature_snapshot),
                "versions": dict(self.versions),
            }
        )


@dataclass(frozen=True, slots=True)
class MarketMark:
    at: datetime
    price_usd: Decimal
    corroborated: bool  # supported by real tape/liquidity, not a lone mark
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class ExecutableQuote:
    """One size-specific quote.  ``side`` is BUY (USD in) or SELL (tokens in)."""

    at: datetime
    side: str
    input_amount: Decimal  # USD for BUY, raw tokens for SELL
    output_amount: Decimal  # raw tokens for BUY, USD for SELL
    fee_usd: Decimal = Decimal("0")
    route_ok: bool = True
    units_verified: bool = True
    age_seconds: float = 0.0
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class PaperFill:
    policy_version: str
    at: datetime
    realized_multiple: Decimal  # net of fees, per the simulated policy ledger
    complete: bool = True


@dataclass(frozen=True, slots=True)
class LabelPolicy:
    entry_size_usd: Decimal = Decimal("50")
    entry_delay: timedelta = timedelta(seconds=15)
    max_quote_age_seconds: float = 30.0
    horizons: tuple[tuple[str, timedelta], ...] = DEFAULT_HORIZONS
    thresholds: tuple[int, ...] = THRESHOLDS
    version: str = OUTCOME_LABEL_V2_VERSION

    @property
    def assumption_hash(self) -> str:
        return _hash(
            {
                "entry_size_usd": str(self.entry_size_usd),
                "entry_delay_seconds": self.entry_delay.total_seconds(),
                "max_quote_age_seconds": self.max_quote_age_seconds,
                "horizons": [[n, d.total_seconds()] for n, d in self.horizons],
                "thresholds": list(self.thresholds),
                "version": self.version,
            }
        )


@dataclass(frozen=True, slots=True)
class OutcomeLabel:
    decision_id: str
    asset: str
    horizon: str
    semantics: Semantics
    status: LabelStatus
    anchor_at: datetime
    horizon_end: datetime
    multiple: Decimal | None
    hits: Mapping[int, bool | None]
    censor_reason: str | None
    evidence_at: datetime | None
    size_usd: Decimal | None
    decision_snapshot_hash: str
    assumption_hash: str
    version: str = OUTCOME_LABEL_V2_VERSION

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["semantics"] = self.semantics.value
        payload["status"] = self.status.value
        payload["hits"] = {f"{k}x": v for k, v in self.hits.items()}
        return {key: _json(value) for key, value in payload.items()}


def label_decision(
    anchor: DecisionAnchor,
    *,
    marks: Sequence[MarketMark] = (),
    quotes: Sequence[ExecutableQuote] = (),
    paper_fills: Sequence[PaperFill] = (),
    paper_policy_version: str | None = None,
    now: datetime,
    policy: LabelPolicy | None = None,
) -> tuple[OutcomeLabel, ...]:
    active = policy or LabelPolicy()
    checked_at = ensure_utc(now, "now")
    labels: list[OutcomeLabel] = []
    for horizon, duration in active.horizons:
        end = anchor.decided_at + duration

        def label(
            semantics: Semantics,
            multiple: Decimal | None,
            *,
            reason: str | None = None,
            evidence_at: datetime | None = None,
            size: Decimal | None = None,
            horizon_name: str = horizon,
            horizon_end: datetime = end,
        ) -> OutcomeLabel:
            if checked_at < horizon_end:
                status, reason = LabelStatus.PENDING, "HORIZON_NOT_MATURE"
                multiple = None
            elif multiple is None:
                status = LabelStatus.CENSORED
            else:
                status = LabelStatus.MATURE
            hits: dict[int, bool | None] = {
                t: (None if multiple is None else multiple >= t) for t in active.thresholds
            }
            return OutcomeLabel(
                decision_id=anchor.decision_id,
                asset=anchor.asset,
                horizon=horizon_name,
                semantics=semantics,
                status=status,
                anchor_at=anchor.decided_at,
                horizon_end=horizon_end,
                multiple=multiple,
                hits=hits,
                censor_reason=reason if status is not LabelStatus.MATURE else None,
                evidence_at=evidence_at,
                size_usd=size,
                decision_snapshot_hash=anchor.snapshot_hash,
                assumption_hash=active.assumption_hash,
            )

        for semantics, (multiple, reason, evidence_at), size in (
            (Semantics.MARKET_MARK, _mark_peak(anchor, marks, end), None),
            (
                Semantics.EXECUTABLE_QUOTE_PEAK,
                _sellable_peak(anchor, quotes, end, active),
                active.entry_size_usd,
            ),
            (
                Semantics.PAPER_REALIZED,
                _paper(paper_fills, paper_policy_version, anchor.decided_at, end),
                None,
            ),
        ):
            labels.append(
                label(semantics, multiple, reason=reason, evidence_at=evidence_at, size=size)
            )
    return tuple(labels)


def _mark_peak(
    anchor: DecisionAnchor, marks: Sequence[MarketMark], end: datetime
) -> tuple[Decimal | None, str | None, datetime | None]:
    base = anchor.decision_mark_price_usd
    if base is None or base <= 0:
        return None, "DECISION_MARK_MISSING", None
    eligible = [
        mark
        for mark in marks
        if anchor.decided_at < ensure_utc(mark.at, "mark.at") <= end and mark.corroborated
    ]
    if not eligible:
        return None, "NO_CORROBORATED_MARK_IN_HORIZON", None
    best = max(eligible, key=lambda mark: mark.price_usd)
    return _q(best.price_usd / base), None, best.at


def _quote_ok(quote: ExecutableQuote, policy: LabelPolicy) -> bool:
    return (
        quote.route_ok
        and quote.units_verified
        and quote.age_seconds <= policy.max_quote_age_seconds
        and quote.output_amount > 0
    )


def _sellable_peak(
    anchor: DecisionAnchor,
    quotes: Sequence[ExecutableQuote],
    end: datetime,
    policy: LabelPolicy,
) -> tuple[Decimal | None, str | None, datetime | None]:
    earliest_entry = anchor.decided_at + policy.entry_delay
    entries = sorted(
        (
            quote
            for quote in quotes
            if quote.side == "BUY"
            and quote.input_amount == policy.entry_size_usd
            and earliest_entry <= ensure_utc(quote.at, "quote.at") <= end
            and _quote_ok(quote, policy)
        ),
        key=lambda quote: quote.at,
    )
    if not entries:
        return None, "NO_ELIGIBLE_ENTRY_QUOTE", None
    entry = entries[0]
    cost = entry.input_amount + entry.fee_usd
    exits = [
        quote
        for quote in quotes
        if quote.side == "SELL"
        and quote.input_amount == entry.output_amount  # size-specific: the tokens bought
        and entry.at < ensure_utc(quote.at, "quote.at") <= end
        and _quote_ok(quote, policy)
    ]
    if not exits:
        return None, "NO_ELIGIBLE_EXIT_QUOTE", None
    best = max(exits, key=lambda quote: quote.output_amount - quote.fee_usd)
    return _q((best.output_amount - best.fee_usd) / cost), None, best.at


def _paper(
    fills: Sequence[PaperFill],
    policy_version: str | None,
    start: datetime,
    end: datetime,
) -> tuple[Decimal | None, str | None, datetime | None]:
    if policy_version is None:
        return None, "PAPER_POLICY_NOT_RUN", None
    own = [
        fill
        for fill in fills
        if fill.policy_version == policy_version
        and start < ensure_utc(fill.at, "fill.at") <= end
        and fill.complete
    ]
    if not own:
        return None, "NO_PAPER_FILL_FOR_POLICY", None
    last = max(own, key=lambda fill: fill.at)
    return _q(last.realized_multiple), None, last.at


def outcome_coverage(labels: Sequence[OutcomeLabel]) -> dict[str, object]:
    """Per (horizon, semantics): unique assets, mature/pending/censored, hits."""

    table: dict[str, dict[str, object]] = {}
    for item in labels:
        key = f"{item.horizon}:{item.semantics.value}"
        row = table.setdefault(
            key,
            {"assets": set(), "MATURE": set(), "PENDING": set(), "CENSORED": set(),
             "censor_reasons": {}, "hits": {f"{t}x": set() for t in THRESHOLDS}},
        )
        row["assets"].add(item.asset)  # type: ignore[attr-defined]
        row[item.status.value].add(item.asset)  # type: ignore[attr-defined]
        if item.censor_reason and item.status is LabelStatus.CENSORED:
            reasons = row["censor_reasons"]
            reasons[item.censor_reason] = reasons.get(item.censor_reason, 0) + 1  # type: ignore[index,attr-defined]
        for threshold, hit in item.hits.items():
            if hit:
                row["hits"][f"{threshold}x"].add(item.asset)  # type: ignore[index]
    return {
        key: {
            "unique_assets": len(row["assets"]),  # type: ignore[arg-type]
            "mature": len(row["MATURE"]),  # type: ignore[arg-type]
            "pending": len(row["PENDING"]),  # type: ignore[arg-type]
            "censored": len(row["CENSORED"]),  # type: ignore[arg-type]
            "censor_reasons": row["censor_reasons"],
            "unique_hit_assets": {k: len(v) for k, v in row["hits"].items()},  # type: ignore[attr-defined]
        }
        for key, row in sorted(table.items())
    }


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    return value


def _hash(material: object) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_HORIZONS",
    "OUTCOME_LABEL_V2_VERSION",
    "THRESHOLDS",
    "DecisionAnchor",
    "ExecutableQuote",
    "LabelPolicy",
    "LabelStatus",
    "MarketMark",
    "OutcomeLabel",
    "PaperFill",
    "Semantics",
    "label_decision",
    "outcome_coverage",
]
