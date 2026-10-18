"""Product-owned read contracts; legacy import paths remain supported."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from memeradar_domain import (
    CandidateState,
    EarlyDecisionState,
    QualityState,
    normalize_chain,
    require_chain_address,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_utc,
    freeze_mapping,
    normalize_texts,
    require_text,
)

from .early_scoring import AsymmetricAlphaProjection
from .read_common import (
    DEFAULT_PAGE_LIMIT,
    _bounded_limit,
    _optional_cursor,
    _optional_decimal,
    _optional_nonnegative_decimal,
    _optional_nonnegative_int,
    _optional_quality,
    _optional_text,
    safe_read_payload,
)


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    state: CandidateState | str | None = None
    min_score: Decimal | None = None
    max_score: Decimal | None = None
    min_confidence: Decimal | None = None
    risk_disposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.state is not None:
            object.__setattr__(self, "state", CandidateState(self.state))
        min_score = _optional_decimal(self.min_score, "min_score")
        max_score = _optional_decimal(self.max_score, "max_score")
        min_confidence = (
            None
            if self.min_confidence is None
            else bounded_decimal(self.min_confidence, "min_confidence", Decimal("0"), Decimal("1"))
        )
        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValueError("min_score must not exceed max_score")
        object.__setattr__(self, "min_score", min_score)
        object.__setattr__(self, "max_score", max_score)
        object.__setattr__(self, "min_confidence", min_confidence)
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        if disposition is not None and disposition.upper() not in {
            "PASS",
            "WARN",
            "BLOCK",
            "UNKNOWN",
        }:
            raise ValueError("risk_disposition is invalid")
        object.__setattr__(
            self, "risk_disposition", None if disposition is None else disposition.upper()
        )


@dataclass(frozen=True, slots=True)
class EarlyRadarQuery:
    """Bounded filters for the launch-stage, read-only radar projection."""

    cursor: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    state: EarlyDecisionState | str | None = None
    min_score: Decimal | None = None
    risk_quality_state: QualityState | str | None = None
    risk_disposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _optional_cursor(self.cursor))
        object.__setattr__(self, "limit", _bounded_limit(self.limit))
        if self.state is not None:
            object.__setattr__(self, "state", EarlyDecisionState(self.state))
        object.__setattr__(self, "min_score", _optional_decimal(self.min_score, "min_score"))
        object.__setattr__(
            self,
            "risk_quality_state",
            _optional_quality(self.risk_quality_state),
        )
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        if disposition is not None and disposition.upper() not in {
            "PASS",
            "WARN",
            "BLOCK",
            "UNKNOWN",
        }:
            raise ValueError("risk_disposition is invalid")
        object.__setattr__(
            self,
            "risk_disposition",
            None if disposition is None else disposition.upper(),
        )


@dataclass(frozen=True, slots=True)
class PoolView:
    id: UUID
    venue: str
    pool_address: str
    quote_mint: str
    chain: str = "solana"

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("pool id must be a UUID")
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=64))
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "pool_address",
            require_chain_address(self.pool_address, normalized_chain, "pool_address"),
        )
        object.__setattr__(
            self,
            "quote_mint",
            require_chain_address(self.quote_mint, normalized_chain, "quote_mint"),
        )


@dataclass(frozen=True, slots=True)
class CandidateView:
    id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    state: CandidateState | str
    discovered_at: datetime
    discovery_source: str
    state_changed_at: datetime
    score: Decimal | None = None
    score_confidence: Decimal | None = None
    score_as_of: datetime | None = None
    score_expires_at: datetime | None = None
    risk_disposition: str | None = None
    risk_quality_state: QualityState | str | None = None
    risk_reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    execution_eligible: bool = False
    chain: str = "solana"

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate and token IDs must be UUIDs")
        normalized_chain = normalize_chain(self.chain).value
        object.__setattr__(self, "chain", normalized_chain)
        object.__setattr__(
            self,
            "mint_address",
            require_chain_address(self.mint_address, normalized_chain, "mint_address"),
        )
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        object.__setattr__(self, "state", CandidateState(self.state))
        object.__setattr__(self, "discovered_at", ensure_utc(self.discovered_at, "discovered_at"))
        object.__setattr__(
            self, "state_changed_at", ensure_utc(self.state_changed_at, "state_changed_at")
        )
        object.__setattr__(
            self, "discovery_source", require_text(self.discovery_source, "discovery_source")
        )
        object.__setattr__(self, "score", _optional_decimal(self.score, "score"))
        if self.score_confidence is not None:
            object.__setattr__(
                self,
                "score_confidence",
                bounded_decimal(
                    self.score_confidence, "score_confidence", Decimal("0"), Decimal("1")
                ),
            )
        if self.score_as_of is not None:
            object.__setattr__(self, "score_as_of", ensure_utc(self.score_as_of, "score_as_of"))
        if self.score_expires_at is not None:
            object.__setattr__(
                self, "score_expires_at", ensure_utc(self.score_expires_at, "score_expires_at")
            )
        disposition = _optional_text(self.risk_disposition, "risk_disposition", max_length=16)
        object.__setattr__(
            self, "risk_disposition", None if disposition is None else disposition.upper()
        )
        object.__setattr__(self, "risk_quality_state", _optional_quality(self.risk_quality_state))
        object.__setattr__(
            self, "risk_reason_codes", normalize_texts(self.risk_reason_codes, "risk_reason_codes")
        )
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        if not isinstance(self.execution_eligible, bool):
            raise TypeError("execution_eligible must be a boolean")
        if self.execution_eligible:
            raise ValueError("read views cannot authorize execution")


@dataclass(frozen=True, slots=True)
class EarlyRadarView:
    """Bounded launch-stage projection for radar, token detail and alerts."""

    candidate_id: UUID
    token_id: UUID
    mint_address: str
    symbol: str | None
    name: str | None
    launch_age_seconds: Decimal | int | float | str | None
    first_seen_at: datetime
    first_seen_source: str
    first_seen_latency_ms: Decimal | int | float | str | None
    first_seen_quality: QualityState | str
    early_score: Decimal | int | float | str | None
    early_score_confidence: Decimal | int | float | str | None
    early_state: EarlyDecisionState | str
    risk_disposition: str = "UNKNOWN"
    buy_velocity: Mapping[str, object] = field(default_factory=dict)
    buy_acceleration: Mapping[str, object] = field(default_factory=dict)
    unique_buyers: Mapping[str, object] = field(default_factory=dict)
    quote_inflow: Mapping[str, object] = field(default_factory=dict)
    liquidity_usd: Decimal | int | float | str | None = None
    price_impact_bps: Decimal | int | float | str | None = None
    creator_risk: str = "UNKNOWN"
    bundle_risk: str = "UNKNOWN"
    holder_risk: str = "UNKNOWN"
    smart_money_confluence: Decimal | int | float | str | None = None
    sellability: str = "UNKNOWN"
    shadow_entry_status: str = "NOT_ATTEMPTED"
    external_call_lead_time_ms: Decimal | int | float | str | None = None
    hard_block_reasons: tuple[str, ...] = ()
    latency_ms: Mapping[str, object] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    execution_eligible: bool = False
    asymmetric_alpha: AsymmetricAlphaProjection | Mapping[str, object] | None = None
    upside_evidence: Mapping[str, object] = field(default_factory=dict)
    market_integrity_risk: str | None = None
    contract_deployer_risk: str | None = None
    liquidity_exit_risk: str | None = None
    execution_quality: Decimal | int | float | str | None = None
    evidence_confidence: Decimal | int | float | str | None = None
    evidence_quality_state: QualityState | str | None = None
    venue: str = "UNKNOWN"
    first_seen_market_cap: Decimal | int | float | str | None = None
    current_market_cap: Decimal | int | float | str | None = None
    buyer_acceleration: Decimal | int | float | str | None = None
    volume_acceleration: Decimal | int | float | str | None = None
    liquidity_acceleration: Decimal | int | float | str | None = None
    raw_smart_wallet_count: int | Decimal | str | None = None
    independent_smart_wallet_count: int | Decimal | str | None = None
    organic_momentum: Decimal | int | float | str | None = None
    alerted: bool | None = None
    alert_latency_ms: Decimal | int | float | str | None = None
    multiple_since_discovery: Decimal | int | float | str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID) or not isinstance(self.token_id, UUID):
            raise TypeError("candidate_id and token_id must be UUIDs")
        object.__setattr__(
            self,
            "mint_address",
            require_solana_address(self.mint_address, "mint_address"),
        )
        for field_name, max_length in (("symbol", 64), ("name", 256)):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None if value is None else require_text(value, field_name, max_length=max_length),
            )
        object.__setattr__(self, "first_seen_at", ensure_utc(self.first_seen_at, "first_seen_at"))
        object.__setattr__(
            self,
            "first_seen_source",
            require_text(self.first_seen_source, "first_seen_source", max_length=256),
        )
        object.__setattr__(
            self,
            "first_seen_quality",
            QualityState(self.first_seen_quality),
        )
        object.__setattr__(self, "early_state", EarlyDecisionState(self.early_state))
        for field_name in (
            "launch_age_seconds",
            "first_seen_latency_ms",
            "liquidity_usd",
            "price_impact_bps",
            "external_call_lead_time_ms",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_decimal(getattr(self, field_name), field_name),
            )
        if self.early_score is not None:
            object.__setattr__(
                self,
                "early_score",
                bounded_decimal(self.early_score, "early_score", Decimal("0"), Decimal("100")),
            )
        if self.early_score_confidence is not None:
            object.__setattr__(
                self,
                "early_score_confidence",
                bounded_decimal(
                    self.early_score_confidence,
                    "early_score_confidence",
                    Decimal("0"),
                    Decimal("1"),
                ),
            )
        if self.smart_money_confluence is not None:
            object.__setattr__(
                self,
                "smart_money_confluence",
                bounded_decimal(
                    self.smart_money_confluence,
                    "smart_money_confluence",
                    Decimal("0"),
                    Decimal("100"),
                ),
            )
        for field_name in (
            "risk_disposition",
            "creator_risk",
            "bundle_risk",
            "holder_risk",
            "sellability",
            "shadow_entry_status",
        ):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name, max_length=32).upper(),
            )
        for field_name in (
            "buy_velocity",
            "buy_acceleration",
            "unique_buyers",
            "quote_inflow",
            "latency_ms",
            "upside_evidence",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{field_name} must be a mapping")
            object.__setattr__(self, field_name, safe_read_payload(value))
        alpha = self.asymmetric_alpha
        if not self.upside_evidence:
            derived_upside: dict[str, object] = {}
            if self.smart_money_confluence is not None:
                derived_upside["smart_money_confluence"] = self.smart_money_confluence
            if self.external_call_lead_time_ms is not None:
                derived_upside["external_call_lead_time_ms"] = self.external_call_lead_time_ms
            if isinstance(alpha, AsymmetricAlphaProjection):
                derived_upside["upside_evidence_score"] = alpha.upside_evidence_score
            elif isinstance(alpha, Mapping) and alpha.get("upside_evidence_score") is not None:
                derived_upside["upside_evidence_score"] = alpha["upside_evidence_score"]
            object.__setattr__(self, "upside_evidence", safe_read_payload(derived_upside))
        for field_name, fallback in (
            ("market_integrity_risk", self.bundle_risk),
            ("contract_deployer_risk", self.creator_risk),
            ("liquidity_exit_risk", self.sellability),
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                require_text(
                    fallback if value is None else value,
                    field_name,
                    max_length=32,
                ).upper(),
            )
        alpha_execution_quality: Decimal | int | float | str | None = None
        alpha_confidence: Decimal | int | float | str | None = None
        if isinstance(alpha, AsymmetricAlphaProjection):
            alpha_execution_quality = alpha.execution_quality
            alpha_confidence = alpha.evidence_confidence
        elif isinstance(alpha, Mapping):
            alpha_execution_quality = cast(
                Decimal | int | float | str | None,
                alpha.get("execution_quality"),
            )
            alpha_confidence = cast(
                Decimal | int | float | str | None,
                alpha.get("evidence_confidence"),
            )
        execution_quality = self.execution_quality
        if execution_quality is None:
            execution_quality = alpha_execution_quality
        object.__setattr__(
            self,
            "execution_quality",
            None
            if execution_quality is None
            else bounded_decimal(
                execution_quality,
                "execution_quality",
                Decimal("0"),
                Decimal("100"),
            ),
        )
        evidence_confidence = self.evidence_confidence
        if evidence_confidence is None:
            evidence_confidence = self.early_score_confidence
        if evidence_confidence is None:
            evidence_confidence = alpha_confidence
        object.__setattr__(
            self,
            "evidence_confidence",
            None
            if evidence_confidence is None
            else bounded_decimal(
                evidence_confidence,
                "evidence_confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "evidence_quality_state",
            QualityState(self.first_seen_quality)
            if self.evidence_quality_state is None
            else QualityState(self.evidence_quality_state),
        )
        object.__setattr__(self, "venue", require_text(self.venue, "venue", max_length=64).upper())
        for field_name in ("first_seen_market_cap", "current_market_cap", "alert_latency_ms"):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_decimal(getattr(self, field_name), field_name),
            )
        for field_name in (
            "buyer_acceleration",
            "volume_acceleration",
            "liquidity_acceleration",
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None
                if value is None
                else bounded_decimal(value, field_name, Decimal("-1"), Decimal("1")),
            )
        for field_name in ("raw_smart_wallet_count", "independent_smart_wallet_count"):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_int(getattr(self, field_name), field_name),
            )
        for field_name in ("organic_momentum", "multiple_since_discovery"):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                None
                if value is None
                else (
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("100"))
                    if field_name == "organic_momentum"
                    else _optional_nonnegative_decimal(value, field_name)
                ),
            )
        if self.alerted is not None and not isinstance(self.alerted, bool):
            raise TypeError("alerted must be a boolean or None")
        object.__setattr__(
            self,
            "hard_block_reasons",
            normalize_texts(self.hard_block_reasons, "hard_block_reasons"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        object.__setattr__(self, "reason_codes", normalize_texts(self.reason_codes, "reason_codes"))
        if not isinstance(self.execution_eligible, bool):
            raise TypeError("execution_eligible must be a boolean")
        if self.execution_eligible:
            raise ValueError("early radar views cannot authorize execution")

    @property
    def risk_quality_state(self) -> QualityState:
        """Expose first-seen quality under the read-filter compatibility name."""

        return QualityState(self.first_seen_quality)

    def to_mapping(self) -> Mapping[str, object]:
        return freeze_mapping(
            {
                "candidate_id": self.candidate_id,
                "token_id": self.token_id,
                "mint_address": self.mint_address,
                "symbol": self.symbol,
                "name": self.name,
                "launch_age_seconds": self.launch_age_seconds,
                "first_seen_at": self.first_seen_at,
                "first_seen_source": self.first_seen_source,
                "first_seen_latency_ms": self.first_seen_latency_ms,
                "first_seen_quality": QualityState(self.first_seen_quality).value,
                "early_score": self.early_score,
                "early_score_confidence": self.early_score_confidence,
                "early_state": EarlyDecisionState(self.early_state).value,
                "risk_disposition": self.risk_disposition,
                "buy_velocity": self.buy_velocity,
                "buy_acceleration": self.buy_acceleration,
                "unique_buyers": self.unique_buyers,
                "quote_inflow": self.quote_inflow,
                "liquidity_usd": self.liquidity_usd,
                "price_impact_bps": self.price_impact_bps,
                "creator_risk": self.creator_risk,
                "bundle_risk": self.bundle_risk,
                "holder_risk": self.holder_risk,
                "smart_money_confluence": self.smart_money_confluence,
                "sellability": self.sellability,
                "shadow_entry_status": self.shadow_entry_status,
                "external_call_lead_time_ms": self.external_call_lead_time_ms,
                "hard_block_reasons": self.hard_block_reasons,
                "latency_ms": self.latency_ms,
                "upside_evidence": self.upside_evidence,
                "market_integrity_risk": self.market_integrity_risk,
                "contract_deployer_risk": self.contract_deployer_risk,
                "liquidity_exit_risk": self.liquidity_exit_risk,
                "execution_quality": self.execution_quality,
                "evidence_confidence": self.evidence_confidence,
                "evidence_quality_state": QualityState(self.evidence_quality_state).value,
                "venue": self.venue,
                "first_seen_market_cap": self.first_seen_market_cap,
                "current_market_cap": self.current_market_cap,
                "buyer_acceleration": self.buyer_acceleration,
                "volume_acceleration": self.volume_acceleration,
                "liquidity_acceleration": self.liquidity_acceleration,
                "raw_smart_wallet_count": self.raw_smart_wallet_count,
                "independent_smart_wallet_count": self.independent_smart_wallet_count,
                "organic_momentum": self.organic_momentum,
                "alerted": self.alerted,
                "alert_latency_ms": self.alert_latency_ms,
                "multiple_since_discovery": self.multiple_since_discovery,
                "evidence_refs": self.evidence_refs,
                "reason_codes": self.reason_codes,
                "execution_eligible": False,
                "auto_execution": "LOCKED",
                "asymmetric_alpha": (
                    {
                        "early_quality_score": self.asymmetric_alpha.early_quality_score,
                        "upside_evidence_score": self.asymmetric_alpha.upside_evidence_score,
                        "rug_dump_risk": self.asymmetric_alpha.rug_dump_risk,
                        "execution_quality": self.asymmetric_alpha.execution_quality,
                        "evidence_confidence": self.asymmetric_alpha.evidence_confidence,
                        "data_quality_confidence": self.asymmetric_alpha.data_quality_confidence,
                        "launch_age_ms": self.asymmetric_alpha.launch_age_ms,
                        "market_cap_at_decision": self.asymmetric_alpha.market_cap_at_decision,
                        "reason_codes": [str(r) for r in self.asymmetric_alpha.reason_codes],
                        "strategy_version": self.asymmetric_alpha.strategy_version,
                        "config_hash": self.asymmetric_alpha.config_hash,
                    }
                    if isinstance(self.asymmetric_alpha, AsymmetricAlphaProjection)
                    else (
                        safe_read_payload(self.asymmetric_alpha)
                        if isinstance(self.asymmetric_alpha, Mapping)
                        else None
                    )
                ),
            },
            "early_radar",
        )
