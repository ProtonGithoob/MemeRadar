"""Measurement-only join of narrative, opportunity, market and wallet evidence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol, cast

from memeradar_domain import (
    Chain,
    Freshness,
    Provenance,
    QualityState,
    ReasonCode,
    RiskAssessment,
    RiskDisposition,
    TokenIdentity,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

from .chain_opportunity import ChainOpportunitySnapshot
from .confluence import TokenSmartMoneyScore
from .correlation import CorrelationSnapshot, CorrelationWindowFeatures
from .narrative_catalyst import NarrativeCatalystSnapshot

SMART_MONEY_CONVERGENCE_VERSION = "smart-money-convergence-v1"

_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


class ConvergenceSignalState(str, Enum):
    """Research classification of the currently available signal families."""

    UNKNOWN = "UNKNOWN"
    NARRATIVE_ONLY = "NARRATIVE_ONLY"
    WALLET_ONLY = "WALLET_ONLY"
    CONVERGENT = "CONVERGENT"
    DISAGREEMENT = "DISAGREEMENT"


@dataclass(frozen=True, slots=True)
class SmartMoneyConvergencePolicy:
    """Bounded research thresholds; these are not production score weights."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    minimum_narrative_confidence: Decimal = Decimal("0.60")
    minimum_wallet_score: Decimal = Decimal("60")
    minimum_wallet_confidence: Decimal = Decimal("0.60")
    minimum_independent_clusters: int = 2
    version: str = SMART_MONEY_CONVERGENCE_VERSION

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, maximum in (
            ("minimum_independent_clusters", 10_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(
            self,
            "minimum_narrative_confidence",
            bounded_decimal(
                self.minimum_narrative_confidence,
                "minimum_narrative_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "minimum_wallet_confidence",
            bounded_decimal(
                self.minimum_wallet_confidence,
                "minimum_wallet_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "minimum_wallet_score",
            bounded_decimal(
                self.minimum_wallet_score,
                "minimum_wallet_score",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


class _FreshnessSource(Protocol):
    @property
    def as_of(self) -> datetime: ...

    @property
    def freshness(self) -> Freshness: ...


def _state_at(source: _FreshnessSource, now: datetime) -> QualityState:
    if source.as_of > now:
        return QualityState.INVALID
    return source.freshness.state_at(now)


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _append_unique[T](target: list[T], values: Sequence[T]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _source_metadata(
    target_provenance: list[Provenance],
    target_refs: list[str],
    target_reasons: list[ReasonCode],
    source: object,
) -> None:
    provenance = getattr(source, "provenance", ())
    if isinstance(provenance, Sequence) and not isinstance(provenance, str | bytes | bytearray):
        _append_unique(target_provenance, tuple(provenance))
    refs = getattr(source, "evidence_refs", ())
    if isinstance(refs, Sequence) and not isinstance(refs, str | bytes | bytearray):
        _append_unique(target_refs, tuple(refs))
    reasons = getattr(source, "reason_codes", ())
    if isinstance(reasons, Sequence) and not isinstance(reasons, str | bytes | bytearray):
        _append_unique(target_reasons, normalize_reason_codes(tuple(reasons)))


def _source_confidence(source: object) -> Decimal | None:
    value = getattr(source, "confidence", None)
    return value if isinstance(value, Decimal) else None


@dataclass(frozen=True, slots=True)
class SmartMoneyConvergenceProjection:
    """Transparent cross-signal evidence; it cannot authorize execution."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    signal_state: ConvergenceSignalState | str
    narrative_signal: bool | None
    wallet_signal: bool | None
    narrative_confidence: Decimal | None
    wallet_confidence: Decimal | None
    joint_confidence: Decimal
    chain_opportunity_chain: Chain | None
    chain_opportunity_confidence: Decimal | None
    raw_qualified_wallet_count: int | None
    raw_entry_wallet_count: int | None
    raw_exit_wallet_count: int | None
    cluster_adjusted_independent_wallet_count: int | None
    cluster_adjusted_entry_cluster_count: int | None
    cluster_adjusted_exit_cluster_count: int | None
    confluence_detected: bool | None
    distribution_detected: bool | None
    liquidity: Decimal | None
    liquidity_delta: Decimal | None
    unique_buyers: int | None
    liquidity_confirmation: bool | None
    holder_confirmation: bool | None
    risk_disposition: RiskDisposition | None
    risk_quality_state: QualityState
    hard_risk_blocked: bool | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState
    version: str = SMART_MONEY_CONVERGENCE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "signal_state", ConvergenceSignalState(self.signal_state))
        for field_name in (
            "narrative_confidence",
            "wallet_confidence",
            "joint_confidence",
            "confidence",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        for field_name in (
            "raw_qualified_wallet_count",
            "raw_entry_wallet_count",
            "raw_exit_wallet_count",
            "cluster_adjusted_independent_wallet_count",
            "cluster_adjusted_entry_cluster_count",
            "cluster_adjusted_exit_cluster_count",
            "unique_buyers",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        for field_name in ("liquidity", "liquidity_delta"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal or None")
        for field_name in (
            "narrative_signal",
            "wallet_signal",
            "confluence_detected",
            "distribution_detected",
            "liquidity_confirmation",
            "holder_confirmation",
            "hard_risk_blocked",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be a boolean or None")
        if self.chain_opportunity_chain is not None and not isinstance(
            self.chain_opportunity_chain, Chain
        ):
            raise TypeError("chain_opportunity_chain must be a Chain or None")
        if self.chain_opportunity_confidence is not None:
            object.__setattr__(
                self,
                "chain_opportunity_confidence",
                bounded_decimal(
                    self.chain_opportunity_confidence,
                    "chain_opportunity_confidence",
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        if self.risk_disposition is not None:
            object.__setattr__(self, "risk_disposition", RiskDisposition(self.risk_disposition))
        object.__setattr__(self, "risk_quality_state", QualityState(self.risk_quality_state))
        provenance = tuple(self.provenance)
        if any(not isinstance(value, Provenance) for value in provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in normalize_reason_codes(self.reason_codes))

    @property
    def raw_independent_wallet_count(self) -> int | None:
        return self.raw_qualified_wallet_count

    @property
    def independent_cluster_count(self) -> int | None:
        return self.cluster_adjusted_independent_wallet_count

    @property
    def smart_money_convergence_confidence(self) -> Decimal:
        return self.wallet_confidence or Decimal("0")

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> dict[str, object]:
        return dict(
            freeze_mapping(
                {
                    "token": self.token.canonical_id,
                    "as_of": self.as_of.isoformat(),
                    "expires_at": self.expires_at.isoformat(),
                    "signal_state": ConvergenceSignalState(self.signal_state).value,
                    "narrative_signal": self.narrative_signal,
                    "wallet_signal": self.wallet_signal,
                    "narrative_confidence": self.narrative_confidence,
                    "wallet_confidence": self.wallet_confidence,
                    "joint_confidence": self.joint_confidence,
                    "chain_opportunity_chain": (
                        None
                        if self.chain_opportunity_chain is None
                        else self.chain_opportunity_chain.value
                    ),
                    "chain_opportunity_confidence": self.chain_opportunity_confidence,
                    "raw_qualified_wallet_count": self.raw_qualified_wallet_count,
                    "raw_entry_wallet_count": self.raw_entry_wallet_count,
                    "raw_exit_wallet_count": self.raw_exit_wallet_count,
                    "cluster_adjusted_independent_wallet_count": (
                        self.cluster_adjusted_independent_wallet_count
                    ),
                    "cluster_adjusted_entry_cluster_count": (
                        self.cluster_adjusted_entry_cluster_count
                    ),
                    "cluster_adjusted_exit_cluster_count": (
                        self.cluster_adjusted_exit_cluster_count
                    ),
                    "confluence_detected": self.confluence_detected,
                    "distribution_detected": self.distribution_detected,
                    "liquidity": self.liquidity,
                    "liquidity_delta": self.liquidity_delta,
                    "unique_buyers": self.unique_buyers,
                    "liquidity_confirmation": self.liquidity_confirmation,
                    "holder_confirmation": self.holder_confirmation,
                    "risk_disposition": (
                        None if self.risk_disposition is None else self.risk_disposition.value
                    ),
                    "risk_quality_state": self.risk_quality_state.value,
                    "hard_risk_blocked": self.hard_risk_blocked,
                    "provenance": self.provenance,
                    "evidence_refs": self.evidence_refs,
                    "reason_codes": self.reason_code_values,
                    "confidence": self.confidence,
                    "config_hash": self.config_hash,
                    "quality_state": self.quality_state.value,
                    "version": self.version,
                    "execution_eligible": False,
                },
                "smart-money convergence mapping",
            )
        )


class SmartMoneyConvergenceAnalyzer:
    """Join existing snapshots without calculating or mutating a production score."""

    def __init__(self, *, policy: SmartMoneyConvergencePolicy | None = None) -> None:
        self.policy = policy or SmartMoneyConvergencePolicy()

    def analyze(
        self,
        token: TokenIdentity | None = None,
        *,
        narrative: NarrativeCatalystSnapshot | None = None,
        smart_money: TokenSmartMoneyScore | None = None,
        smart_money_score: TokenSmartMoneyScore | None = None,
        chain_opportunity: ChainOpportunitySnapshot | None = None,
        correlation: CorrelationSnapshot | None = None,
        risk: RiskAssessment | None = None,
        now: datetime,
        config_hash: str,
    ) -> SmartMoneyConvergenceProjection:
        if (
            smart_money is not None
            and smart_money_score is not None
            and smart_money != smart_money_score
        ):
            raise ValueError("smart_money and smart_money_score must identify one snapshot")
        smart = smart_money or smart_money_score
        for field_name, value, expected in (
            ("narrative", narrative, NarrativeCatalystSnapshot),
            ("smart_money", smart, TokenSmartMoneyScore),
            ("chain_opportunity", chain_opportunity, ChainOpportunitySnapshot),
            ("correlation", correlation, CorrelationSnapshot),
            ("risk", risk, RiskAssessment),
        ):
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"{field_name} has an unsupported snapshot type")

        candidates = tuple(
            value.token
            for value in (smart, correlation)
            if value is not None
        )
        if token is None:
            token = candidates[0] if candidates else None
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity or derivable from evidence")

        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        sources: list[tuple[str, _FreshnessSource]] = []
        for name, value in (
            ("narrative", narrative),
            ("smart_money", smart),
            ("chain_opportunity", chain_opportunity),
            ("correlation", correlation),
            ("risk", risk),
        ):
            if value is not None:
                sources.append((name, cast(_FreshnessSource, value)))

        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        reasons: list[ReasonCode] = [ReasonCode("SMART_MONEY_CONVERGENCE_PROJECTION_BUILT")]
        states: list[QualityState] = []
        future = False
        for name, source in sources:
            state = _state_at(source, checked_at)
            states.append(state)
            if state is QualityState.INVALID:
                future = True
            _source_metadata(provenance, evidence_refs, reasons, source)
            if name == "risk":
                _source_metadata(provenance, evidence_refs, reasons, source)

        identity_conflict = False
        for candidate in candidates:
            if candidate != token:
                identity_conflict = True
        if (
            narrative is not None
            and narrative.chain is not None
            and narrative.chain is not token.chain
        ):
            identity_conflict = True
        if (
            chain_opportunity is not None
            and chain_opportunity.chain is not token.chain
        ):
            identity_conflict = True
        if identity_conflict:
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_TOKEN_MISMATCH"))

        quality_state = _combined_quality(states)
        if future:
            quality_state = QualityState.INVALID
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_FUTURE_EVIDENCE"))
        elif identity_conflict:
            quality_state = QualityState.CONFLICTED
        elif any(state is not QualityState.FRESH for state in states):
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_NONFRESH_EVIDENCE"))

        narrative_state = None if narrative is None else _state_at(narrative, checked_at)
        narrative_confidence = None if narrative is None else narrative.confidence
        narrative_signal = (
            None
            if narrative is None or narrative_state is not QualityState.FRESH
            else narrative.confidence >= self.policy.minimum_narrative_confidence
        )

        wallet_state = None if smart is None else _state_at(smart, checked_at)
        wallet_confidence = None if smart is None else smart.confidence
        wallet_signal = (
            None
            if smart is None or wallet_state is not QualityState.FRESH
            else (
                smart.score >= self.policy.minimum_wallet_score
                and smart.confidence >= self.policy.minimum_wallet_confidence
                and smart.confluence_detected
                and smart.independent_cluster_count >= self.policy.minimum_independent_clusters
            )
        )
        if wallet_signal:
            reasons.append(ReasonCode("SMART_WALLET_CONVERGENCE_HIGH"))
        if smart is not None and smart.independent_cluster_count < smart.qualified_wallet_count:
            reasons.append(ReasonCode("SMART_WALLET_INDEPENDENCE_LOW"))

        distribution_detected = (
            None
            if smart is None or wallet_state is not QualityState.FRESH
            else smart.distribution_event_count > 0
            or smart.exit_wallet_count > 0
            or smart.exit_cluster_count > 0
        )
        if distribution_detected:
            reasons.append(ReasonCode("SMART_MONEY_DISTRIBUTION"))

        risk_disposition: RiskDisposition | None = None
        risk_states: list[QualityState] = []
        risk_values: list[RiskDisposition] = []
        if correlation is not None and correlation.risk_disposition is not None:
            risk_values.append(RiskDisposition(correlation.risk_disposition))
            risk_states.append(QualityState(correlation.risk_quality_state))
        if risk is not None:
            risk_values.append(RiskDisposition(risk.disposition))
            risk_states.append(_state_at(risk, checked_at))
        if risk_values:
            risk_disposition = risk_values[0]
            if any(value is not risk_disposition for value in risk_values[1:]):
                reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_RISK_CONFLICT"))
                quality_state = QualityState.CONFLICTED
                identity_conflict = True
        risk_quality_state = _combined_quality(risk_states)
        hard_risk_blocked: bool | None = None
        if risk_disposition is RiskDisposition.BLOCK:
            hard_risk_blocked = True
        elif risk_disposition in {RiskDisposition.PASS, RiskDisposition.WARN} and all(
            state is QualityState.FRESH for state in risk_states
        ):
            hard_risk_blocked = False
        elif risk_disposition is None:
            reasons.append(ReasonCode("SMART_MONEY_CONVERGENCE_RISK_EVIDENCE_UNKNOWN"))

        liquidity: Decimal | None = None
        liquidity_delta: Decimal | None = None
        unique_buyers: int | None = None
        liquidity_confirmation = None
        holder_confirmation = None
        market_window: CorrelationWindowFeatures | None = None
        if correlation is not None:
            market_window = correlation.windows.get("5m")
            if market_window is None:
                market_window = next(iter(correlation.windows.values()), None)
            if market_window is not None:
                liquidity = (
                    None
                    if market_window.liquidity is None
                    else to_decimal(market_window.liquidity, "liquidity")
                )
                liquidity_delta = (
                    None
                    if market_window.liquidity_delta is None
                    else to_decimal(market_window.liquidity_delta, "liquidity_delta")
                )
                unique_buyers = market_window.unique_buyers
                if QualityState(market_window.quality_state) is QualityState.FRESH:
                    liquidity_confirmation = liquidity is not None and liquidity > 0
                    holder_confirmation = (
                        unique_buyers is not None
                        and unique_buyers > 0
                        and market_window.independent_entry_clusters > 0
                    )

        signal_state = ConvergenceSignalState.UNKNOWN
        if not future and not identity_conflict and quality_state is QualityState.FRESH:
            risk_disagreement = hard_risk_blocked is True
            wallet_disagreement = distribution_detected is True
            if (narrative_signal or wallet_signal) and (risk_disagreement or wallet_disagreement):
                signal_state = ConvergenceSignalState.DISAGREEMENT
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_DISAGREEMENT"))
            elif narrative_signal and wallet_signal:
                signal_state = ConvergenceSignalState.CONVERGENT
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_CONVERGENCE"))
            elif narrative_signal:
                signal_state = ConvergenceSignalState.NARRATIVE_ONLY
                reasons.append(ReasonCode("SMART_MONEY_NARRATIVE_ONLY"))
            elif wallet_signal:
                signal_state = ConvergenceSignalState.WALLET_ONLY
                reasons.append(ReasonCode("SMART_MONEY_WALLET_ONLY"))

        confidence_sources: list[Decimal] = []
        if narrative_confidence is not None and narrative_signal:
            confidence_sources.append(narrative_confidence)
        if wallet_confidence is not None and wallet_signal:
            confidence_sources.append(wallet_confidence)
        if signal_state is ConvergenceSignalState.CONVERGENT:
            for evidence_source in (chain_opportunity, correlation):
                if evidence_source is not None:
                    source_confidence = _source_confidence(evidence_source)
                    if source_confidence is not None:
                        confidence_sources.append(source_confidence)
        joint_confidence = (
            min(confidence_sources, default=Decimal("0"))
            if signal_state in {
                ConvergenceSignalState.NARRATIVE_ONLY,
                ConvergenceSignalState.WALLET_ONLY,
                ConvergenceSignalState.CONVERGENT,
            }
            else Decimal("0")
        )
        chain_value = (
            None
            if chain_opportunity is None
            else Chain(chain_opportunity.chain)
        )
        chain_confidence = _source_confidence(chain_opportunity) if chain_opportunity else None
        return SmartMoneyConvergenceProjection(
            token=token,
            as_of=checked_at,
            expires_at=checked_at + self.policy.evidence_ttl,
            signal_state=signal_state,
            narrative_signal=narrative_signal,
            wallet_signal=wallet_signal,
            narrative_confidence=narrative_confidence,
            wallet_confidence=wallet_confidence,
            joint_confidence=joint_confidence,
            chain_opportunity_chain=chain_value,
            chain_opportunity_confidence=chain_confidence,
            raw_qualified_wallet_count=None if smart is None else smart.qualified_wallet_count,
            raw_entry_wallet_count=None if smart is None else smart.entry_wallet_count,
            raw_exit_wallet_count=None if smart is None else smart.exit_wallet_count,
            cluster_adjusted_independent_wallet_count=(
                None if smart is None else smart.independent_cluster_count
            ),
            cluster_adjusted_entry_cluster_count=(
                None if smart is None else smart.entry_cluster_count
            ),
            cluster_adjusted_exit_cluster_count=(
                None if smart is None else smart.exit_cluster_count
            ),
            confluence_detected=None if smart is None else smart.confluence_detected,
            distribution_detected=distribution_detected,
            liquidity=liquidity,
            liquidity_delta=liquidity_delta,
            unique_buyers=unique_buyers,
            liquidity_confirmation=liquidity_confirmation,
            holder_confirmation=holder_confirmation,
            risk_disposition=risk_disposition,
            risk_quality_state=risk_quality_state,
            hard_risk_blocked=hard_risk_blocked,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reasons),
            confidence=joint_confidence,
            config_hash=normalized_config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    build = analyze


__all__ = [
    "ConvergenceSignalState",
    "SMART_MONEY_CONVERGENCE_VERSION",
    "SmartMoneyConvergenceAnalyzer",
    "SmartMoneyConvergencePolicy",
    "SmartMoneyConvergenceProjection",
]
