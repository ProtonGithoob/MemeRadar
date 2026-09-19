"""Small, fail-closed orchestration boundary for launch-time safety evidence."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from memeradar_domain import Provenance, QualityState, ReasonCode, RiskDisposition
from memeradar_domain.common import bounded_decimal, normalize_texts, to_decimal
from memeradar_domain.events import normalize_reason_codes

FAST_SAFETY_VERSION = "fast-safety-v1"


class FastSafetyStatus(str, Enum):
    PASS = "PASS"
    CAUTION = "CAUTION"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


def _source_value(source: object, name: str) -> object | None:
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)


def _decimal(value: object | None, name: str) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return to_decimal(value, name)
    except (TypeError, ValueError):
        return None


def _boolean(value: object | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "safe", "pass"}:
            return True
        if normalized in {"false", "no", "0", "unsafe", "fail", "blocked"}:
            return False
    return None


@dataclass(frozen=True, slots=True)
class FastSafetyResult:
    status: FastSafetyStatus
    critical_unknowns: tuple[str, ...] = ()
    noncritical_unknowns: tuple[str, ...] = ()
    hard_blocks: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    quality_state: QualityState = QualityState.UNKNOWN
    latency_ms: Decimal = Decimal("0")
    liquidity: Decimal | None = None
    sellability: bool | None = None
    buy_impact_bps: Decimal | None = None
    sell_impact_bps: Decimal | None = None
    raw_smart_wallet_count: int | None = None
    independent_smart_wallet_count: int | None = None
    shared_funder_ratio: Decimal | None = None
    creator_linked_smart_wallet_count: int | None = None
    coordinated_wallet_probability: Decimal | None = None
    version: str = FAST_SAFETY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", FastSafetyStatus(self.status))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "critical_unknowns",
            normalize_texts(self.critical_unknowns, "critical_unknowns"),
        )
        object.__setattr__(
            self,
            "noncritical_unknowns",
            normalize_texts(self.noncritical_unknowns, "noncritical_unknowns"),
        )
        object.__setattr__(self, "hard_blocks", normalize_texts(self.hard_blocks, "hard_blocks"))
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
        object.__setattr__(
            self,
            "latency_ms",
            bounded_decimal(self.latency_ms, "latency_ms", Decimal("0"), Decimal("3_600_000")),
        )
        for name in ("liquidity", "buy_impact_bps", "sell_impact_bps"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, to_decimal(value, name))
        for name in ("shared_funder_ratio", "coordinated_wallet_probability"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    bounded_decimal(value, name, Decimal("0"), Decimal("1")),
                )
        for name in (
            "raw_smart_wallet_count",
            "independent_smart_wallet_count",
            "creator_linked_smart_wallet_count",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        object.__setattr__(self, "version", str(self.version))

    @property
    def reason_code_values(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reason_codes)

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "status": self.status.value,
                "critical_unknowns": self.critical_unknowns,
                "noncritical_unknowns": self.noncritical_unknowns,
                "hard_blocks": self.hard_blocks,
                "reason_codes": self.reason_code_values,
                "evidence_refs": self.evidence_refs,
                "quality_state": self.quality_state.value,
                "latency_ms": self.latency_ms,
                "liquidity": self.liquidity,
                "sellability": self.sellability,
                "buy_impact_bps": self.buy_impact_bps,
                "sell_impact_bps": self.sell_impact_bps,
                "raw_smart_wallet_count": self.raw_smart_wallet_count,
                "independent_smart_wallet_count": self.independent_smart_wallet_count,
                "shared_funder_ratio": self.shared_funder_ratio,
                "creator_linked_smart_wallet_count": self.creator_linked_smart_wallet_count,
                "coordinated_wallet_probability": self.coordinated_wallet_probability,
                "version": self.version,
                "execution_eligible": False,
            }
        )


class FastSafetyGate:
    """Compose already-calculated evidence without doing deep enrichment."""

    def __init__(
        self,
        *,
        minimum_liquidity: Decimal = Decimal("1000"),
        maximum_impact_bps: Decimal = Decimal("1000"),
        bundle_block: Decimal = Decimal("0.70"),
        creator_block: Decimal = Decimal("0.50"),
        shared_funder_block: Decimal = Decimal("0.75"),
        coordinated_block: Decimal = Decimal("0.80"),
    ) -> None:
        self.minimum_liquidity = to_decimal(minimum_liquidity, "minimum_liquidity")
        self.maximum_impact_bps = to_decimal(maximum_impact_bps, "maximum_impact_bps")
        self.bundle_block = bounded_decimal(
            bundle_block, "bundle_block", Decimal("0"), Decimal("1")
        )
        self.creator_block = bounded_decimal(
            creator_block, "creator_block", Decimal("0"), Decimal("1")
        )
        self.shared_funder_block = bounded_decimal(
            shared_funder_block, "shared_funder_block", Decimal("0"), Decimal("1")
        )
        self.coordinated_block = bounded_decimal(
            coordinated_block, "coordinated_block", Decimal("0"), Decimal("1")
        )

    def evaluate(
        self,
        evidence: Mapping[str, object] | None = None,
        *,
        token_security: object | None = None,
        launch_risk: object | None = None,
        flow: object | None = None,
        holder: object | None = None,
        creator: object | None = None,
        confluence: object | None = None,
        quote: object | None = None,
        signal_hardening: object | None = None,
        social: object | None = None,
    ) -> FastSafetyResult:
        started = time.perf_counter()
        sources = {
            "token_security": token_security,
            "launch_risk": launch_risk,
            "flow": flow,
            "holder": holder,
            "creator": creator,
            "confluence": confluence,
            "quote": quote,
            "signal_hardening": signal_hardening,
            "social": social,
        }
        sources = {key: value for key, value in sources.items() if value is not None}
        direct = dict(evidence or {})

        def value(*names: str) -> object | None:
            for name in names:
                if name in direct:
                    return direct[name]
                for source in sources.values():
                    candidate = _source_value(source, name)
                    if candidate is not None:
                        return candidate
            return None

        critical: list[str] = []
        noncritical: list[str] = []
        blocks: list[str] = []
        reasons: list[ReasonCode] = []
        refs: list[str] = []
        provenance: list[Provenance] = []
        for source in sources.values():
            raw_refs = _source_value(source, "evidence_refs")
            if isinstance(raw_refs, Sequence) and not isinstance(raw_refs, str | bytes | bytearray):
                refs.extend(str(ref) for ref in raw_refs)
            raw_provenance = _source_value(source, "provenance")
            if isinstance(raw_provenance, Sequence) and not isinstance(
                raw_provenance, str | bytes | bytearray
            ):
                provenance.extend(item for item in raw_provenance if isinstance(item, Provenance))

        for key, reason in (
            ("mint_authority_safe", "MINT_AUTHORITY_UNSAFE"),
            ("freeze_authority_safe", "FREEZE_AUTHORITY_UNSAFE"),
        ):
            flag = _boolean(value(key))
            if flag is None:
                critical.append(f"{key.upper()}_UNKNOWN")
            elif not flag:
                blocks.append(reason)
                reasons.append(ReasonCode(reason))

        liquidity = _decimal(
            value("liquidity", "liquidity_usd", "effective_liquidity"),
            "liquidity",
        )
        if liquidity is None:
            critical.append("LIQUIDITY_UNKNOWN")
        elif liquidity < self.minimum_liquidity:
            blocks.append("LIQUIDITY_TOO_LOW")
            reasons.append(ReasonCode("LIQUIDITY_TOO_LOW"))

        sellability = _boolean(value("sellability", "is_sellable", "sellable"))
        if sellability is None:
            critical.append("SELLABILITY_UNKNOWN")
        elif not sellability:
            blocks.append("SELLABILITY_FAILED")
            reasons.append(ReasonCode("SELLABILITY_FAILED"))

        buy_impact = _decimal(
            value("buy_impact_bps", "buy_price_impact_bps", "impact_bps"),
            "buy_impact_bps",
        )
        sell_impact = _decimal(
            value("sell_impact_bps", "sell_price_impact_bps", "impact_bps"),
            "sell_impact_bps",
        )
        if buy_impact is None or sell_impact is None:
            critical.append("IMPACT_UNKNOWN")
        else:
            if buy_impact > self.maximum_impact_bps:
                blocks.append("BUY_IMPACT_HIGH")
                reasons.append(ReasonCode("BUY_IMPACT_HIGH"))
            if sell_impact > self.maximum_impact_bps:
                blocks.append("SELL_IMPACT_HIGH")
                reasons.append(ReasonCode("SELL_IMPACT_HIGH"))

        risk_disposition = value("risk_disposition", "disposition")
        try:
            disposition = None if risk_disposition is None else RiskDisposition(risk_disposition)
        except (TypeError, ValueError):
            disposition = RiskDisposition.UNKNOWN
        if disposition is RiskDisposition.BLOCK:
            blocks.append("LAUNCH_RISK_BLOCK")
            reasons.append(ReasonCode("LAUNCH_RISK_BLOCK"))
        elif disposition is RiskDisposition.UNKNOWN:
            critical.append("LAUNCH_RISK_UNKNOWN")
        elif disposition is RiskDisposition.WARN:
            reasons.append(ReasonCode("LAUNCH_RISK_WARNING"))

        for key, code, threshold in (
            ("bundle_concentration", "BUNDLE_CONCENTRATION", self.bundle_block),
            ("creator_related_ratio", "CREATOR_LINKED_ACTIVITY", self.creator_block),
            ("shared_funder_ratio", "SHARED_FUNDER_CONFLUENCE", self.shared_funder_block),
            ("coordinated_wallet_probability", "COORDINATED_WALLETS", self.coordinated_block),
        ):
            metric = _decimal(value(key), key)
            if metric is not None and metric >= threshold:
                blocks.append(code)
                reasons.append(ReasonCode(code))

        social_quality = (
            value("social_quality_state", "quality_state")
            if social is not None
            else direct.get("social_quality_state")
        )
        if social_quality is not None:
            try:
                if QualityState(social_quality) is not QualityState.FRESH:
                    noncritical.append("SOCIAL_EVIDENCE_UNKNOWN")
            except (TypeError, ValueError):
                noncritical.append("SOCIAL_EVIDENCE_UNKNOWN")

        status = (
            FastSafetyStatus.BLOCK
            if blocks
            else FastSafetyStatus.UNKNOWN
            if critical
            else FastSafetyStatus.CAUTION
            if noncritical or disposition is RiskDisposition.WARN
            else FastSafetyStatus.PASS
        )
        quality = QualityState.UNKNOWN if critical else QualityState.FRESH
        raw_smart = _decimal(
            value("raw_smart_wallet_count", "qualified_wallet_count"),
            "raw_smart_wallet_count",
        )
        independent = _decimal(
            value(
                "independent_smart_wallet_count",
                "independent_wallet_count",
                "independent_cluster_count",
            ),
            "independent_smart_wallet_count",
        )
        creator_linked = _decimal(
            value("creator_linked_smart_wallet_count"), "creator_linked_smart_wallet_count"
        )
        elapsed_ms = Decimal(str((time.perf_counter() - started) * 1000))
        return FastSafetyResult(
            status=status,
            critical_unknowns=tuple(dict.fromkeys(critical)),
            noncritical_unknowns=tuple(dict.fromkeys(noncritical)),
            hard_blocks=tuple(dict.fromkeys(blocks)),
            reason_codes=tuple(dict.fromkeys(reasons)),
            evidence_refs=tuple(dict.fromkeys(refs)),
            provenance=tuple(provenance),
            quality_state=quality,
            latency_ms=elapsed_ms,
            liquidity=liquidity,
            sellability=sellability,
            buy_impact_bps=buy_impact,
            sell_impact_bps=sell_impact,
            raw_smart_wallet_count=None if raw_smart is None else int(raw_smart),
            independent_smart_wallet_count=None if independent is None else int(independent),
            shared_funder_ratio=_decimal(value("shared_funder_ratio"), "shared_funder_ratio"),
            creator_linked_smart_wallet_count=None
            if creator_linked is None
            else int(creator_linked),
            coordinated_wallet_probability=_decimal(
                value("coordinated_wallet_probability"), "coordinated_wallet_probability"
            ),
        )


__all__ = ["FAST_SAFETY_VERSION", "FastSafetyGate", "FastSafetyResult", "FastSafetyStatus"]
