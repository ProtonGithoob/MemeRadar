"""Bounded organic-demand evidence projected from existing early features."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from memeradar_domain import QualityState, ReasonCode
from memeradar_domain.common import bounded_decimal, normalize_texts, to_decimal
from memeradar_domain.events import normalize_reason_codes

ORGANIC_MOMENTUM_VERSION = "organic-momentum-v1"


def _decimal(metrics: Mapping[str, object], key: str) -> Decimal | None:
    value = metrics.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return to_decimal(value, key)
    except (TypeError, ValueError):
        return None


def _bounded_signal(value: Decimal | None, *, floor: Decimal = Decimal("0")) -> Decimal | None:
    if value is None:
        return None
    if value <= floor:
        return Decimal("0")
    return min(Decimal("1"), (value - floor) / (abs(value) + Decimal("1")))


@dataclass(frozen=True, slots=True)
class OrganicMomentumProjection:
    """Evidence component for EarlyScore; never an execution decision."""

    score: Decimal | None
    confidence: Decimal
    quality_state: QualityState
    positive_evidence: tuple[str, ...] = ()
    penalties: Mapping[str, Decimal] = MappingProxyType({})
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    version: str = ORGANIC_MOMENTUM_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "score",
            None
            if self.score is None
            else bounded_decimal(
                self.score, "organic momentum score", Decimal("0"), Decimal("100")
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(
                self.confidence,
                "organic momentum confidence",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "positive_evidence",
            normalize_texts(self.positive_evidence, "positive_evidence"),
        )
        object.__setattr__(
            self,
            "penalties",
            MappingProxyType(
                {
                    str(key): bounded_decimal(
                        value, "organic penalty", Decimal("0"), Decimal("100")
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

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    @classmethod
    def from_metrics(
        cls,
        metrics: Mapping[str, object],
        *,
        evidence_refs: Sequence[str] = (),
    ) -> OrganicMomentumProjection:
        if not isinstance(metrics, Mapping):
            raise TypeError("metrics must be a mapping")
        known_keys = {
            key for key, value in metrics.items() if value is not None and key != "quality_state"
        }
        if not known_keys:
            return cls(
                score=None,
                confidence=Decimal("0"),
                quality_state=QualityState.UNKNOWN,
                reason_codes=(ReasonCode("ORGANIC_MOMENTUM_EVIDENCE_MISSING"),),
                evidence_refs=evidence_refs,
            )

        positives: list[str] = []
        positive_values: list[Decimal] = []
        buyer_acceleration = _bounded_signal(_decimal(metrics, "buyer_acceleration"))
        if buyer_acceleration is not None:
            positive_values.append(buyer_acceleration)
            if buyer_acceleration > 0:
                positives.append("INDEPENDENT_BUYER_ACCELERATION")
        unique_growth = _bounded_signal(_decimal(metrics, "unique_buyer_growth"))
        if unique_growth is not None:
            positive_values.append(unique_growth)
            if unique_growth > 0:
                positives.append("UNIQUE_BUYER_GROWTH")
        liquidity_acceleration = _bounded_signal(_decimal(metrics, "liquidity_acceleration"))
        if liquidity_acceleration is not None:
            positive_values.append(liquidity_acceleration)
            if liquidity_acceleration > 0:
                positives.append("LIQUIDITY_GROWTH")
        smart_wallets = _decimal(metrics, "independent_smart_wallet_count")
        if smart_wallets is not None:
            signal = min(Decimal("1"), smart_wallets / Decimal("5"))
            positive_values.append(signal)
            if smart_wallets > 0:
                positives.append("INDEPENDENT_SMART_WALLETS")
        trade_ratio = _decimal(metrics, "buy_sell_volume_ratio")
        if trade_ratio is not None:
            healthy = Decimal("1") - min(
                Decimal("1"), abs(trade_ratio - Decimal("1")) / Decimal("2")
            )
            positive_values.append(healthy)
            if healthy > Decimal("0.5"):
                positives.append("HEALTHY_BUY_SELL_FLOW")

        penalties: dict[str, Decimal] = {}
        wash = metrics.get("wash_evidence") is True
        if wash:
            penalties["WASH_VOLUME"] = Decimal("30")
        circular = _decimal(metrics, "circular_flow_ratio")
        if circular is not None and circular > 0:
            penalties["CIRCULAR_FLOW"] = min(Decimal("25"), circular * Decimal("30"))
        repeated = _decimal(metrics, "repeated_size_ratio")
        if repeated is not None and repeated > 0:
            penalties["REPEATED_TRADE_SIZE"] = min(Decimal("20"), repeated * Decimal("25"))
        shared_funder = _decimal(metrics, "shared_funder_ratio")
        if shared_funder is not None and shared_funder > 0:
            penalties["SHARED_FUNDER_CONFLUENCE"] = min(
                Decimal("35"), shared_funder * Decimal("35")
            )
        creator_linked = _decimal(metrics, "creator_linked_buyer_ratio")
        if creator_linked is not None and creator_linked > 0:
            penalties["CREATOR_LINKED_VOLUME"] = min(
                Decimal("30"), creator_linked * Decimal("30")
            )
        for key, reason in (
            ("bundle_risk", "BUNDLE_CONCENTRATION"),
            ("sniper_risk", "SNIPER_CONCENTRATION"),
        ):
            risk = _decimal(metrics, key)
            if risk is not None and risk > 0:
                penalties[reason] = min(Decimal("35"), risk * Decimal("35"))
        growth = _decimal(metrics, "unique_buyer_growth")
        buy_volume = _decimal(metrics, "buy_volume")
        if growth is not None and growth <= 0 and buy_volume is not None and buy_volume > 0:
            penalties["VOLUME_WITHOUT_HOLDER_GROWTH"] = Decimal("15")
        price_velocity = _decimal(metrics, "price_velocity")
        if (
            price_velocity is not None
            and price_velocity > 0
            and liquidity_acceleration in {None, Decimal("0")}
        ):
            penalties["PRICE_WITHOUT_LIQUIDITY"] = Decimal("15")

        positive = (
            sum(positive_values, Decimal("0")) / Decimal(len(positive_values))
            if positive_values
            else Decimal("0")
        )
        score = max(
            Decimal("0"),
            min(
                Decimal("100"),
                Decimal("50")
                + positive * Decimal("50")
                - sum(penalties.values(), Decimal("0")),
            ),
        )
        reasons = [ReasonCode("ORGANIC_MOMENTUM_PROJECTED")]
        reasons.extend(ReasonCode(value) for value in positives)
        reasons.extend(ReasonCode(value) for value in penalties)
        return cls(
            score=score,
            confidence=min(Decimal("1"), Decimal(len(known_keys)) / Decimal("8")),
            quality_state=QualityState.FRESH,
            positive_evidence=tuple(positives),
            penalties=penalties,
            reason_codes=tuple(reasons),
            evidence_refs=evidence_refs,
        )


__all__ = ["ORGANIC_MOMENTUM_VERSION", "OrganicMomentumProjection"]
