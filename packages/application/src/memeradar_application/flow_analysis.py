"""Provider-independent liquidity and organic-flow analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from memeradar_domain import (
    Freshness,
    Observation,
    Provenance,
    QualityState,
    ReasonCode,
    TokenIdentity,
    require_solana_address,
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

from .event_time import exact_event_time
from .evidence_helpers import (
    append_unique as _append_unique,
)
from .evidence_helpers import (
    append_unique_value as _append_provenance,
)
from .evidence_helpers import (
    combined_quality as _combined_quality,
)
from .evidence_policy import production_observations
from .provider_contracts import QuoteSnapshot

_MISSING = object()
_MARKET_KINDS = frozenset({"market.market_data", "market.liquidity", "market.depth"})
_TRADE_KINDS = frozenset({"market.trade", "market.trades", "market.trade_data"})


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
    payload_mint = observation.normalized_payload.get("mint_address")
    if payload_mint is not None and payload_mint != token.mint_address:
        return False
    if observation.token_id is not None:
        return observation.token_id == token.id
    return payload_mint == token.mint_address


def _quality_at(observation: Observation, now: datetime, ttl: timedelta) -> QualityState:
    if observation.quality_state is not QualityState.FRESH:
        return observation.quality_state
    if observation.observed_at > now:
        return QualityState.INVALID
    if now >= observation.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _optional_amount(value: object, field: str) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    try:
        amount = to_decimal(value, field)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative decimal") from exc
    if amount < 0:
        raise ValueError(f"{field} must be a non-negative decimal")
    return amount


def _optional_int(value: object, field: str) -> int | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be a non-negative integer") from exc
    else:
        raise ValueError(f"{field} must be a non-negative integer")
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return parsed


def _optional_side(value: object) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("trade side must be a string")
    side = value.strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("trade side must be buy or sell")
    return side


def _optional_boolean(value: object, field: str) -> bool | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ValueError(f"{field} must be a boolean")


def _optional_label(value: object, field: str) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalized_entropy(values: Sequence[str]) -> Decimal | None:
    if not values:
        return None
    counts = Counter(values)
    if len(counts) <= 1:
        return Decimal("0")
    total = Decimal(len(values))
    entropy = sum(
        (
            -(probability := Decimal(count) / total) * probability.ln()
            for count in counts.values()
        ),
        Decimal("0"),
    )
    return entropy / Decimal(len(counts)).ln()


def _optional_address(value: object, field: str) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical Solana address")
    try:
        return require_solana_address(value, field)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a canonical Solana address") from exc


@dataclass(frozen=True, slots=True)
class FlowAnalysisPolicy:
    """Explicit bounds and initial heuristic thresholds for flow analysis."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    max_market_observations: int = 20
    max_trade_rows: int = 500
    max_size_buckets: int = 100
    rapid_round_trip_window: timedelta = timedelta(minutes=2)
    minimum_liquidity: Decimal = Decimal("10000")
    minimum_depth: Decimal = Decimal("5000")
    maximum_price_impact_bps: Decimal = Decimal("100")
    liquidity_decay_threshold: Decimal = Decimal("0.25")
    transaction_maker_threshold: Decimal = Decimal("1.5")
    repeated_size_threshold: Decimal = Decimal("0.5")
    circular_flow_threshold: Decimal = Decimal("0.25")
    rapid_round_trip_threshold: Decimal = Decimal("0.25")
    minimum_organic_volume_ratio: Decimal = Decimal("0.5")
    organic_volume_penalty: Decimal = Decimal("25")

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        if self.rapid_round_trip_window <= timedelta(0):
            raise ValueError("rapid_round_trip_window must be positive")
        for field_name, maximum in (
            ("max_market_observations", 1000),
            ("max_trade_rows", 5000),
            ("max_size_buckets", 1000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        for field_name in (
            "minimum_liquidity",
            "minimum_depth",
            "maximum_price_impact_bps",
            "transaction_maker_threshold",
        ):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "liquidity_decay_threshold",
            "repeated_size_threshold",
            "circular_flow_threshold",
            "rapid_round_trip_threshold",
            "minimum_organic_volume_ratio",
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
        object.__setattr__(
            self,
            "organic_volume_penalty",
            bounded_decimal(
                self.organic_volume_penalty,
                "organic_volume_penalty",
                Decimal("0"),
                Decimal("100"),
            ),
        )


@dataclass(frozen=True, slots=True)
class LiquiditySnapshot:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    liquidity: Decimal | None
    depth: Decimal | None
    previous_liquidity: Decimal | None
    liquidity_change_ratio: Decimal | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    version: str = "liquidity-analysis-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in ("liquidity", "depth", "previous_liquidity"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _optional_amount(value, field_name))
        if self.liquidity_change_ratio is not None:
            change = to_decimal(self.liquidity_change_ratio, "liquidity_change_ratio")
            if change < Decimal("-1"):
                raise ValueError("liquidity_change_ratio must not be below -1")
            object.__setattr__(self, "liquidity_change_ratio", change)
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if any(not isinstance(value, Provenance) for value in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
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


@dataclass(frozen=True, slots=True)
class FlowMetrics:
    buy_volume: Decimal | None
    sell_volume: Decimal | None
    unique_makers: int | None
    transaction_count: int | None
    transaction_maker_ratio: Decimal | None
    repeated_size_ratio: Decimal | None
    circular_flow_ratio: Decimal | None
    rapid_round_trip_ratio: Decimal | None
    sellable: bool | None
    price_impact_bps: Decimal | None
    quote_quality_state: QualityState
    unique_buyers: int | None = None
    unique_sellers: int | None = None
    unique_buyer_ratio: Decimal | None = None
    buy_sell_unique_wallet_ratio: Decimal | None = None
    cluster_adjusted_buyer_count: int | None = None
    wallet_entropy: Decimal | None = None
    funded_sibling_ratio: Decimal | None = None
    repeat_trade_ratio: Decimal | None = None
    round_trip_ratio: Decimal | None = None
    gross_volume: Decimal | None = None
    organic_volume_estimate: Decimal | None = None
    wash_suspected_volume: Decimal | None = None
    organic_volume_ratio: Decimal | None = None
    raw_turnover: Decimal | None = None
    organic_turnover: Decimal | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "buy_volume",
            "sell_volume",
            "price_impact_bps",
            "gross_volume",
            "organic_volume_estimate",
            "wash_suspected_volume",
            "raw_turnover",
            "organic_turnover",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _optional_amount(value, field_name))
        for field_name in (
            "unique_makers",
            "transaction_count",
            "unique_buyers",
            "unique_sellers",
            "cluster_adjusted_buyer_count",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        if self.transaction_maker_ratio is not None:
            object.__setattr__(
                self,
                "transaction_maker_ratio",
                _optional_amount(self.transaction_maker_ratio, "transaction_maker_ratio"),
            )
        if self.buy_sell_unique_wallet_ratio is not None:
            object.__setattr__(
                self,
                "buy_sell_unique_wallet_ratio",
                _optional_amount(
                    self.buy_sell_unique_wallet_ratio,
                    "buy_sell_unique_wallet_ratio",
                ),
            )
        for field_name in (
            "repeated_size_ratio",
            "circular_flow_ratio",
            "rapid_round_trip_ratio",
            "unique_buyer_ratio",
            "wallet_entropy",
            "funded_sibling_ratio",
            "repeat_trade_ratio",
            "round_trip_ratio",
            "organic_volume_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    bounded_decimal(value, field_name, Decimal("0"), Decimal("1")),
                )
        object.__setattr__(self, "quote_quality_state", QualityState(self.quote_quality_state))


@dataclass(frozen=True, slots=True)
class OrganicFlowScore:
    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    score: Decimal
    confidence: Decimal
    liquidity: LiquiditySnapshot
    metrics: FlowMetrics
    penalties: Mapping[str, Decimal]
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    config_hash: str
    quality_state: QualityState = QualityState.FRESH
    version: str = "organic-flow-v2"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if not isinstance(self.liquidity, LiquiditySnapshot):
            raise TypeError("liquidity must be a LiquiditySnapshot")
        if not isinstance(self.metrics, FlowMetrics):
            raise TypeError("metrics must be FlowMetrics")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "score",
            bounded_decimal(self.score, "score", Decimal("0"), Decimal("100")),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        normalized_penalties: dict[str, Decimal] = {}
        for key, value in self.penalties.items():
            normalized_key = require_text(key, "penalty key")
            normalized_penalties[normalized_key] = bounded_decimal(
                value,
                f"penalty {normalized_key}",
                Decimal("0"),
                Decimal("100"),
            )
        object.__setattr__(self, "penalties", freeze_mapping(normalized_penalties, "penalties"))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if any(not isinstance(value, Provenance) for value in self.provenance):
            raise TypeError("provenance must contain Provenance values")
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes, required=True),
        )
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self, at: datetime) -> bool:
        """Organic-flow analysis is advisory and never authorizes execution."""

        del at
        return False


@dataclass(frozen=True, slots=True)
class _TradeRecord:
    maker: str | None
    side: str | None
    amount: Decimal | None
    buyer: str | None
    seller: str | None
    event_at: datetime
    source_id: str
    quote_amount: Decimal | None = None
    cluster_id: str | None = None
    wash_suspected: bool | None = None


class FlowAnalyzer:
    """Analyze bounded normalized market/trade evidence without provider coupling."""

    def __init__(
        self,
        *,
        policy: FlowAnalysisPolicy | None = None,
        include_shadow: bool = False,
    ) -> None:
        self.policy = policy or FlowAnalysisPolicy()
        if not isinstance(include_shadow, bool):
            raise TypeError("include_shadow must be a boolean")
        self.include_shadow = include_shadow

    def _matching(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        kinds: frozenset[str],
    ) -> tuple[Observation, ...]:
        values: list[Observation] = []
        for observation in production_observations(
            observations,
            include_shadow=self.include_shadow,
        ):
            if observation.kind in kinds and _observation_matches(observation, token):
                values.append(observation)
        return tuple(values)

    def _empty_liquidity(
        self,
        token: TokenIdentity,
        *,
        as_of: datetime,
        quality_state: QualityState,
        config_hash: str,
        reason_codes: Sequence[ReasonCode | str],
        provenance: Sequence[Provenance] = (),
        evidence_refs: Sequence[str] = (),
    ) -> LiquiditySnapshot:
        normalized_as_of = ensure_utc(as_of, "as_of")
        return LiquiditySnapshot(
            token=token,
            as_of=normalized_as_of,
            expires_at=normalized_as_of + self.policy.evidence_ttl,
            liquidity=None,
            depth=None,
            previous_liquidity=None,
            liquidity_change_ratio=None,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=normalize_reason_codes(reason_codes, required=True),
            confidence=Decimal("0"),
            config_hash=config_hash,
            quality_state=quality_state,
        )

    @staticmethod
    def _market_values(observation: Observation) -> tuple[Decimal | None, Decimal | None]:
        payload = observation.normalized_payload
        liquidity = _optional_amount(
            _field(payload, "liquidity", "liquidity_usd", "liquidityUsd"),
            "liquidity",
        )
        depth = _optional_amount(
            _field(
                payload,
                "depth",
                "liquidity_depth",
                "sell_depth",
                "quote_depth",
                "depth_usd",
                "quote_depth_usd",
            ),
            "depth",
        )
        return liquidity, depth

    def analyze_liquidity(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
    ) -> LiquiditySnapshot:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        matched = self._matching(token, observations, _MARKET_KINDS)
        if not matched:
            return self._empty_liquidity(
                token,
                as_of=checked_at,
                quality_state=QualityState.UNKNOWN,
                config_hash=normalized_config_hash,
                reason_codes=("LIQUIDITY_EVIDENCE_MISSING",),
            )
        if len(matched) > self.policy.max_market_observations:
            return self._empty_liquidity(
                token,
                as_of=checked_at,
                quality_state=QualityState.INVALID,
                config_hash=normalized_config_hash,
                reason_codes=("LIQUIDITY_DATA_INVALID",),
            )
        latest = max(matched, key=lambda item: (item.observed_at, item.ingested_at))
        try:
            parsed = {item.id: self._market_values(item) for item in matched}
            latest_values = parsed[latest.id]
            same_time = tuple(item for item in matched if item.observed_at == latest.observed_at)
            if any(parsed[item.id] != latest_values for item in same_time):
                return self._empty_liquidity(
                    token,
                    as_of=latest.observed_at,
                    quality_state=QualityState.CONFLICTED,
                    config_hash=normalized_config_hash,
                    provenance=tuple(item.provenance for item in same_time),
                    evidence_refs=tuple(item.provenance.source_id for item in same_time),
                    reason_codes=("LIQUIDITY_EVIDENCE_CONFLICT",),
                )
            quality_state = _quality_at(latest, checked_at, self.policy.evidence_ttl)
            if quality_state is not QualityState.FRESH:
                return self._empty_liquidity(
                    token,
                    as_of=latest.observed_at,
                    quality_state=quality_state,
                    config_hash=normalized_config_hash,
                    provenance=(latest.provenance,),
                    evidence_refs=(latest.provenance.source_id,),
                    reason_codes=(f"LIQUIDITY_EVIDENCE_{quality_state.value}",),
                )
            liquidity, depth = latest_values
            if liquidity is None:
                return self._empty_liquidity(
                    token,
                    as_of=latest.observed_at,
                    quality_state=QualityState.UNKNOWN,
                    config_hash=normalized_config_hash,
                    provenance=(latest.provenance,),
                    evidence_refs=(latest.provenance.source_id,),
                    reason_codes=("LIQUIDITY_EVIDENCE_MISSING",),
                )
            previous_candidates = tuple(
                item
                for item in matched
                if item.observed_at < latest.observed_at
                and _quality_at(item, checked_at, self.policy.evidence_ttl) is QualityState.FRESH
            )
            previous = (
                max(previous_candidates, key=lambda item: (item.observed_at, item.ingested_at))
                if previous_candidates
                else None
            )
            previous_liquidity = None if previous is None else parsed[previous.id][0]
            change_ratio: Decimal | None = None
            if previous_liquidity is not None:
                if previous_liquidity == 0:
                    change_ratio = None
                else:
                    change_ratio = (liquidity - previous_liquidity) / previous_liquidity
            selected = (latest,) if previous is None else (previous, latest)
            evidence_refs = [item.provenance.source_id for item in selected]
            provenance = [item.provenance for item in selected]
            reasons: list[ReasonCode] = [ReasonCode("LIQUIDITY_SNAPSHOT_BUILT")]
            if depth is None:
                reasons.append(ReasonCode("LIQUIDITY_DEPTH_MISSING"))
            if previous is None or previous_liquidity is None:
                reasons.append(ReasonCode("LIQUIDITY_CHANGE_EVIDENCE_MISSING"))
            elif previous_liquidity == 0:
                reasons.append(ReasonCode("LIQUIDITY_CHANGE_UNDEFINED"))
            if liquidity < self.policy.minimum_liquidity:
                reasons.append(ReasonCode("LIQUIDITY_LOW"))
            if depth is not None and depth < self.policy.minimum_depth:
                reasons.append(ReasonCode("LIQUIDITY_DEPTH_LOW"))
            if change_ratio is not None and change_ratio <= -self.policy.liquidity_decay_threshold:
                reasons.append(ReasonCode("LIQUIDITY_DECAY"))
            confidence = Decimal("0.5")
            if depth is not None:
                confidence += Decimal("0.25")
            if change_ratio is not None:
                confidence += Decimal("0.25")
            return LiquiditySnapshot(
                token=token,
                as_of=latest.observed_at,
                expires_at=latest.observed_at + self.policy.evidence_ttl,
                liquidity=liquidity,
                depth=depth,
                previous_liquidity=previous_liquidity,
                liquidity_change_ratio=change_ratio,
                provenance=tuple(provenance),
                evidence_refs=tuple(evidence_refs),
                reason_codes=tuple(reasons),
                confidence=confidence,
                config_hash=normalized_config_hash,
            )
        except (TypeError, ValueError, OverflowError):
            return self._empty_liquidity(
                token,
                as_of=latest.observed_at,
                quality_state=QualityState.INVALID,
                config_hash=normalized_config_hash,
                provenance=(latest.provenance,),
                evidence_refs=(latest.provenance.source_id,),
                reason_codes=("LIQUIDITY_DATA_INVALID",),
            )

    @staticmethod
    def _parse_trade(observation: Observation) -> _TradeRecord:
        payload = observation.normalized_payload
        event_at = exact_event_time(observation)
        if event_at is None:
            raise ValueError("trade analysis requires exact occurred_at")
        return _TradeRecord(
            maker=_optional_address(
                _field(payload, "maker", "maker_address", "trader", "wallet", "owner"),
                "maker",
            ),
            side=_optional_side(_field(payload, "side", "action", "direction")),
            amount=_optional_amount(
                _field(
                    payload,
                    "amount",
                    "base_amount",
                    "baseAmount",
                    "size",
                    "quantity",
                    "ui_amount",
                ),
                "trade amount",
            ),
            buyer=_optional_address(
                _field(payload, "buyer", "buyer_address", "from_address", "from"),
                "buyer",
            ),
            seller=_optional_address(
                _field(payload, "seller", "seller_address", "to_address", "to"),
                "seller",
            ),
            event_at=event_at,
            source_id=observation.provenance.source_id,
            quote_amount=_optional_amount(
                _field(
                    payload,
                    "quote_amount",
                    "quoteAmount",
                    "quote_volume",
                    "quoteVolume",
                    "notional",
                    "notional_usd",
                    "usd_value",
                    "volume_usd",
                ),
                "trade quote amount",
            ),
            cluster_id=_optional_label(
                _field(
                    payload,
                    "cluster_id",
                    "wallet_cluster_id",
                    "shared_funder",
                    "funder",
                    "funding_wallet",
                ),
                "trade cluster id",
            ),
            wash_suspected=_optional_boolean(
                _field(payload, "wash_trade", "wash", "bot_trade"),
                "wash trade",
            ),
        )

    @staticmethod
    def _summary_metrics(
        observation: Observation,
    ) -> tuple[int | None, int | None, Decimal | None, Decimal | None]:
        payload = observation.normalized_payload
        return (
            _optional_int(
                _field(payload, "trade_count", "trade_24h", "trade24h", "transactions"),
                "trade count",
            ),
            _optional_int(
                _field(
                    payload,
                    "unique_makers",
                    "unique_maker_count",
                    "unique_wallet_24h",
                    "uniqueWallet24h",
                ),
                "unique maker count",
            ),
            _optional_amount(
                _field(payload, "buy_volume", "buy_volume_24h", "buyVolume24h"),
                "buy volume",
            ),
            _optional_amount(
                _field(payload, "sell_volume", "sell_volume_24h", "sellVolume24h"),
                "sell volume",
            ),
        )

    @staticmethod
    def _empty_metrics(*, quote_quality_state: QualityState = QualityState.UNKNOWN) -> FlowMetrics:
        return FlowMetrics(
            buy_volume=None,
            sell_volume=None,
            unique_makers=None,
            transaction_count=None,
            transaction_maker_ratio=None,
            repeated_size_ratio=None,
            circular_flow_ratio=None,
            rapid_round_trip_ratio=None,
            sellable=None,
            price_impact_bps=None,
            quote_quality_state=quote_quality_state,
        )

    def _trade_metrics(
        self,
        matched: Sequence[Observation],
        *,
        now: datetime,
    ) -> tuple[
        FlowMetrics, QualityState, tuple[str, ...], tuple[Provenance, ...], tuple[ReasonCode, ...]
    ]:
        if not matched:
            return (
                self._empty_metrics(),
                QualityState.UNKNOWN,
                (),
                (),
                (ReasonCode("TRADE_EVIDENCE_MISSING"),),
            )
        if len(matched) > self.policy.max_trade_rows:
            return (
                self._empty_metrics(),
                QualityState.INVALID,
                (),
                (),
                (ReasonCode("FLOW_DATA_INVALID"),),
            )
        if any(exact_event_time(item) is None for item in matched):
            return (
                self._empty_metrics(),
                QualityState.UNKNOWN,
                tuple(item.provenance.source_id for item in matched),
                tuple(item.provenance for item in matched),
                (ReasonCode("TRADE_EVENT_TIME_UNKNOWN"),),
            )
        states = tuple(_quality_at(item, now, self.policy.evidence_ttl) for item in matched)
        quality_state = _combined_quality(states)
        evidence_refs = tuple(item.provenance.source_id for item in matched)
        provenance = tuple(item.provenance for item in matched)
        if quality_state is not QualityState.FRESH:
            return (
                self._empty_metrics(),
                quality_state,
                evidence_refs,
                provenance,
                (ReasonCode(f"TRADE_EVIDENCE_{quality_state.value}"),),
            )
        try:
            records = tuple(self._parse_trade(item) for item in matched)
            individual = tuple(
                record
                for record in records
                if record.maker is not None or record.buyer is not None or record.seller is not None
            )
            if not individual:
                transaction_count, unique_makers, buy_volume, sell_volume = self._summary_metrics(
                    max(matched, key=lambda item: (item.observed_at, item.ingested_at))
                )
                if transaction_count is None and unique_makers is None:
                    return (
                        self._empty_metrics(),
                        QualityState.UNKNOWN,
                        evidence_refs,
                        provenance,
                        (ReasonCode("TRADE_DATA_INCOMPLETE"),),
                    )
                ratio = (
                    None
                    if transaction_count is None or unique_makers is None or unique_makers == 0
                    else Decimal(transaction_count) / Decimal(unique_makers)
                )
                return (
                    FlowMetrics(
                        buy_volume=buy_volume,
                        sell_volume=sell_volume,
                        unique_makers=unique_makers,
                        transaction_count=transaction_count,
                        transaction_maker_ratio=ratio,
                        repeated_size_ratio=None,
                        circular_flow_ratio=None,
                        rapid_round_trip_ratio=None,
                        sellable=None,
                        price_impact_bps=None,
                        quote_quality_state=QualityState.UNKNOWN,
                    ),
                    QualityState.FRESH,
                    evidence_refs,
                    provenance,
                    (ReasonCode("TRADE_DATA_SUMMARY_ONLY"), ReasonCode("TRADE_ROWS_MISSING")),
                )
            if len(individual) > self.policy.max_trade_rows:
                raise ValueError("trade rows exceeded the configured bound")
            makers = {record.maker for record in individual if record.maker is not None}
            unique_makers = len(makers) if makers else None
            transaction_count = len(individual)
            ratio = (
                None
                if unique_makers is None or unique_makers == 0
                else Decimal(transaction_count) / Decimal(unique_makers)
            )
            def trade_volume(record: _TradeRecord) -> Decimal | None:
                return record.quote_amount if record.quote_amount is not None else record.amount

            buy_records = tuple(record for record in individual if record.side == "buy")
            sell_records = tuple(record for record in individual if record.side == "sell")
            buy_amounts = tuple(
                value for record in buy_records if (value := trade_volume(record)) is not None
            )
            sell_amounts = tuple(
                value for record in sell_records if (value := trade_volume(record)) is not None
            )
            buy_volume = sum(buy_amounts, Decimal("0")) if buy_amounts else None
            sell_volume = sum(sell_amounts, Decimal("0")) if sell_amounts else None
            gross_volume = (
                (buy_volume or Decimal("0")) + (sell_volume or Decimal("0"))
                if buy_volume is not None or sell_volume is not None
                else None
            )
            buyer_records = tuple(
                (record, buyer)
                for record in buy_records
                if (buyer := (record.buyer or record.maker)) is not None
            )
            seller_values = tuple(
                record.seller or record.maker
                for record in sell_records
                if (record.seller or record.maker) is not None
            )
            buyer_values = tuple(buyer for _, buyer in buyer_records)
            cluster_values = tuple(record.cluster_id or buyer for record, buyer in buyer_records)
            cluster_buyers: defaultdict[str, set[str]] = defaultdict(set)
            for (record, buyer), cluster in zip(buyer_records, cluster_values, strict=True):
                if record.cluster_id is not None:
                    cluster_buyers[cluster].add(buyer)
            funded_sibling_rows = sum(
                1
                for record, buyer in buyer_records
                if record.cluster_id is not None
                and len(cluster_buyers[record.cluster_id]) > 1
            )
            funded_sibling_ratio = (
                Decimal(funded_sibling_rows) / Decimal(len(buyer_records))
                if funded_sibling_rows
                else None
            )
            sizes = tuple(record.amount for record in individual if record.amount is not None)
            if sizes:
                size_counts = Counter(sizes)
                if len(size_counts) > self.policy.max_size_buckets:
                    raise ValueError("trade size buckets exceeded the configured bound")
                repeated_count = sum(count for count in size_counts.values() if count >= 2)
                repeated_size_ratio = Decimal(repeated_count) / Decimal(len(sizes))
            else:
                repeated_size_ratio = None
            directed: Counter[tuple[str, str]] = Counter()
            for record in individual:
                if record.buyer is not None and record.seller is not None:
                    if record.buyer == record.seller:
                        raise ValueError("trade buyer and seller must differ")
                    directed[(record.buyer, record.seller)] += 1
            circular_count = sum(
                count for (buyer, seller), count in directed.items() if (seller, buyer) in directed
            )
            circular_flow_ratio = Decimal(circular_count) / Decimal(transaction_count)
            by_maker: defaultdict[str, list[tuple[datetime, str]]] = defaultdict(list)
            for record in individual:
                if record.maker is not None and record.side is not None:
                    by_maker[record.maker].append((record.event_at, record.side))
            rapid_makers = 0
            for maker_records in by_maker.values():
                maker_records.sort()
                found_round_trip = False
                for index, (buy_at, side) in enumerate(maker_records):
                    if side != "buy":
                        continue
                    for sell_at, sell_side in maker_records[index + 1 :]:
                        if sell_side == "sell":
                            if sell_at - buy_at <= self.policy.rapid_round_trip_window:
                                found_round_trip = True
                            break
                if found_round_trip:
                    rapid_makers += 1
            rapid_ratio = (
                None
                if unique_makers is None or unique_makers == 0
                else Decimal(rapid_makers) / Decimal(unique_makers)
            )
            # ponytail: bounded O(n²) comparison over the 500-trade window.
            # Bucket by maker/time only if replay profiling needs it.
            repeated_indices = {
                index
                for index, record in enumerate(individual)
                if record.amount is not None
                and sum(1 for other in individual if other.amount == record.amount) >= 2
            }
            directed_pairs = {
                (record.buyer, record.seller)
                for record in individual
                if record.buyer is not None
                and record.seller is not None
                and record.buyer != record.seller
            }
            circular_indices = {
                index
                for index, record in enumerate(individual)
                if record.buyer is not None
                and record.seller is not None
                and record.buyer != record.seller
                and (record.seller, record.buyer) in directed_pairs
            }
            rapid_indices: set[int] = set()
            for index, record in enumerate(individual):
                if record.side != "buy" or record.maker is None:
                    continue
                for later_index, later in enumerate(individual[index + 1 :], index + 1):
                    if (
                        later.maker == record.maker
                        and later.side == "sell"
                        and timedelta(0) <= later.event_at - record.event_at
                        <= self.policy.rapid_round_trip_window
                    ):
                        rapid_indices.update((index, later_index))
                        break
            cluster_sibling_indices = {
                index
                for index, (record, buyer) in enumerate(buyer_records)
                if record.cluster_id is not None
                and len(cluster_buyers[record.cluster_id]) > 1
                and buyer is not None
            }
            # The index above is over buyer_records; map it back to individual rows.
            buyer_record_ids = {id(record): index for index, record in enumerate(individual)}
            cluster_sibling_indices = {
                buyer_record_ids[id(buyer_records[index][0])] for index in cluster_sibling_indices
            }
            suspected_indices = circular_indices | rapid_indices
            if (
                repeated_size_ratio is not None
                and repeated_size_ratio >= self.policy.repeated_size_threshold
            ):
                suspected_indices.update(repeated_indices)
            suspected_indices.update(cluster_sibling_indices)
            suspected_indices.update(
                index
                for index, record in enumerate(individual)
                if record.wash_suspected is True
            )
            suspected_amounts = tuple(
                value
                for index, record in enumerate(individual)
                if index in suspected_indices and (value := trade_volume(record)) is not None
            )
            wash_suspected_volume = (
                sum(suspected_amounts, Decimal("0")) if suspected_amounts else None
            )
            organic_volume_estimate = (
                max(Decimal("0"), gross_volume - (wash_suspected_volume or Decimal("0")))
                if gross_volume is not None
                else None
            )
            organic_volume_ratio = (
                organic_volume_estimate / gross_volume
                if organic_volume_estimate is not None and gross_volume
                else None
            )
            return (
                FlowMetrics(
                    buy_volume=buy_volume,
                    sell_volume=sell_volume,
                    unique_makers=unique_makers,
                    transaction_count=transaction_count,
                    transaction_maker_ratio=ratio,
                    repeated_size_ratio=repeated_size_ratio,
                    circular_flow_ratio=circular_flow_ratio,
                    rapid_round_trip_ratio=rapid_ratio,
                    sellable=None,
                    price_impact_bps=None,
                    quote_quality_state=QualityState.UNKNOWN,
                    unique_buyers=len(set(buyer_values)) if buyer_values else None,
                    unique_sellers=len(set(seller_values)) if seller_values else None,
                    unique_buyer_ratio=(
                        Decimal(len(set(buyer_values))) / Decimal(len(buyer_values))
                        if buyer_values
                        else None
                    ),
                    buy_sell_unique_wallet_ratio=(
                        Decimal(len(set(buyer_values))) / Decimal(len(set(seller_values)))
                        if buyer_values and seller_values
                        else None
                    ),
                    cluster_adjusted_buyer_count=(
                        len(set(cluster_values)) if cluster_values else None
                    ),
                    wallet_entropy=_normalized_entropy(cluster_values),
                    funded_sibling_ratio=funded_sibling_ratio,
                    repeat_trade_ratio=(
                        Decimal(transaction_count - unique_makers) / Decimal(transaction_count)
                        if unique_makers is not None and transaction_count
                        else None
                    ),
                    round_trip_ratio=rapid_ratio,
                    gross_volume=gross_volume,
                    organic_volume_estimate=organic_volume_estimate,
                    wash_suspected_volume=wash_suspected_volume,
                    organic_volume_ratio=organic_volume_ratio,
                ),
                QualityState.FRESH,
                evidence_refs,
                provenance,
                (ReasonCode("TRADE_ROWS_ANALYZED"),),
            )
        except (TypeError, ValueError, OverflowError):
            return (
                self._empty_metrics(),
                QualityState.INVALID,
                evidence_refs,
                provenance,
                (ReasonCode("FLOW_DATA_INVALID"),),
            )

    def _quote_metrics(
        self,
        token: TokenIdentity,
        quotes: Sequence[QuoteSnapshot],
        *,
        now: datetime,
    ) -> tuple[
        bool | None,
        Decimal | None,
        QualityState,
        tuple[str, ...],
        tuple[Provenance, ...],
        tuple[ReasonCode, ...],
    ]:
        matching: list[QuoteSnapshot] = []
        for quote in quotes:
            if not isinstance(quote, QuoteSnapshot):
                raise TypeError("quotes must contain QuoteSnapshot values")
            if quote.input_mint == token.mint_address and quote.output_mint != token.mint_address:
                matching.append(quote)
        if not matching:
            return (
                None,
                None,
                QualityState.UNKNOWN,
                (),
                (),
                (ReasonCode("SELLABILITY_EVIDENCE_MISSING"),),
            )
        latest = max(matching, key=lambda item: item.freshness.as_of)
        state = latest.freshness.state_at(now)
        if state is not QualityState.FRESH:
            return (
                None,
                None,
                state,
                (latest.provenance.source_id,),
                (latest.provenance,),
                (ReasonCode(f"SELLABILITY_EVIDENCE_{state.value}"),),
            )
        input_amount = to_decimal(latest.input_amount, "quote input amount")
        output_amount = to_decimal(latest.output_amount, "quote output amount")
        impact = to_decimal(latest.price_impact_bps, "quote price impact")
        sellable = input_amount > 0 and output_amount > 0
        reasons: list[ReasonCode] = [ReasonCode("SELLABILITY_QUOTE_FRESH")]
        if not sellable:
            reasons.append(ReasonCode("SELLABILITY_FAILED"))
        if impact > self.policy.maximum_price_impact_bps:
            reasons.append(ReasonCode("PRICE_IMPACT_HIGH"))
        return (
            sellable,
            impact,
            state,
            (latest.provenance.source_id,),
            (latest.provenance,),
            tuple(reasons),
        )

    def _invalid_result(
        self,
        token: TokenIdentity,
        liquidity: LiquiditySnapshot,
        *,
        config_hash: str,
        evidence_refs: Sequence[str],
        provenance: Sequence[Provenance],
        reason_codes: Sequence[ReasonCode | str],
    ) -> OrganicFlowScore:
        return OrganicFlowScore(
            token=token,
            as_of=liquidity.as_of,
            expires_at=liquidity.as_of + self.policy.evidence_ttl,
            score=Decimal("0"),
            confidence=Decimal("0"),
            liquidity=liquidity,
            metrics=self._empty_metrics(),
            penalties={},
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=normalize_reason_codes(reason_codes, required=True),
            config_hash=config_hash,
            quality_state=QualityState.INVALID,
        )

    def analyze(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        quotes: Sequence[QuoteSnapshot] = (),
    ) -> OrganicFlowScore:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        liquidity = self.analyze_liquidity(
            token,
            observations,
            now=checked_at,
            config_hash=normalized_config_hash,
        )
        matched_trades = self._matching(token, observations, _TRADE_KINDS)
        metrics, trade_state, trade_refs, trade_provenance, trade_reasons = self._trade_metrics(
            matched_trades,
            now=checked_at,
        )
        try:
            sellable, impact, quote_state, quote_refs, quote_provenance, quote_reasons = (
                self._quote_metrics(token, quotes, now=checked_at)
            )
        except (TypeError, ValueError, OverflowError):
            return self._invalid_result(
                token,
                liquidity,
                config_hash=normalized_config_hash,
                evidence_refs=(*liquidity.evidence_refs, *trade_refs),
                provenance=(*liquidity.provenance, *trade_provenance),
                reason_codes=("FLOW_DATA_INVALID",),
            )
        metrics = FlowMetrics(
            buy_volume=metrics.buy_volume,
            sell_volume=metrics.sell_volume,
            unique_makers=metrics.unique_makers,
            transaction_count=metrics.transaction_count,
            transaction_maker_ratio=metrics.transaction_maker_ratio,
            repeated_size_ratio=metrics.repeated_size_ratio,
            circular_flow_ratio=metrics.circular_flow_ratio,
            rapid_round_trip_ratio=metrics.rapid_round_trip_ratio,
            sellable=sellable,
            price_impact_bps=impact,
            quote_quality_state=quote_state,
            unique_buyers=metrics.unique_buyers,
            unique_sellers=metrics.unique_sellers,
            unique_buyer_ratio=metrics.unique_buyer_ratio,
            buy_sell_unique_wallet_ratio=metrics.buy_sell_unique_wallet_ratio,
            cluster_adjusted_buyer_count=metrics.cluster_adjusted_buyer_count,
            wallet_entropy=metrics.wallet_entropy,
            funded_sibling_ratio=metrics.funded_sibling_ratio,
            repeat_trade_ratio=metrics.repeat_trade_ratio,
            round_trip_ratio=metrics.round_trip_ratio,
            gross_volume=metrics.gross_volume,
            organic_volume_estimate=metrics.organic_volume_estimate,
            wash_suspected_volume=metrics.wash_suspected_volume,
            organic_volume_ratio=metrics.organic_volume_ratio,
            raw_turnover=(
                metrics.gross_volume / liquidity.liquidity
                if metrics.gross_volume is not None and liquidity.liquidity
                else None
            ),
            organic_turnover=(
                metrics.organic_volume_estimate / liquidity.liquidity
                if metrics.organic_volume_estimate is not None and liquidity.liquidity
                else None
            ),
        )
        evidence_refs: list[str] = []
        _append_unique(evidence_refs, liquidity.evidence_refs)
        _append_unique(evidence_refs, trade_refs)
        _append_unique(evidence_refs, quote_refs)
        provenance: list[Provenance] = []
        for value in (*liquidity.provenance, *trade_provenance, *quote_provenance):
            _append_provenance(provenance, value)
        quality_state = _combined_quality((liquidity.quality_state, trade_state))
        reasons: list[ReasonCode] = [ReasonCode("ORGANIC_FLOW_ANALYZED")]
        reasons.extend(liquidity.reason_codes)
        reasons.extend(trade_reasons)
        reasons.extend(quote_reasons)
        penalties: dict[str, Decimal] = {}

        def add_penalty(key: str, amount: Decimal, reason: str) -> None:
            if amount > 0:
                penalties[key] = amount
                reasons.append(ReasonCode(reason))

        if liquidity.liquidity is not None and liquidity.liquidity < self.policy.minimum_liquidity:
            add_penalty("liquidity_low", Decimal("25"), "LIQUIDITY_LOW")
        if liquidity.depth is not None and liquidity.depth < self.policy.minimum_depth:
            add_penalty("liquidity_depth_low", Decimal("15"), "LIQUIDITY_DEPTH_LOW")
        if (
            liquidity.liquidity_change_ratio is not None
            and liquidity.liquidity_change_ratio <= -self.policy.liquidity_decay_threshold
        ):
            add_penalty("liquidity_decay", Decimal("20"), "LIQUIDITY_DECAY")
        if impact is not None and impact > self.policy.maximum_price_impact_bps:
            add_penalty("price_impact_high", Decimal("20"), "PRICE_IMPACT_HIGH")
        if sellable is False:
            add_penalty("sellability_failed", Decimal("25"), "SELLABILITY_FAILED")
        if (
            metrics.transaction_maker_ratio is not None
            and metrics.transaction_maker_ratio > self.policy.transaction_maker_threshold
        ):
            add_penalty(
                "transaction_maker_concentration",
                Decimal("15"),
                "TRANSACTION_MAKER_CONCENTRATION",
            )
        if (
            metrics.repeated_size_ratio is not None
            and metrics.repeated_size_ratio >= self.policy.repeated_size_threshold
        ):
            add_penalty("repeated_trade_size", Decimal("15"), "REPEATED_TRADE_SIZE")
        if (
            metrics.circular_flow_ratio is not None
            and metrics.circular_flow_ratio >= self.policy.circular_flow_threshold
        ):
            add_penalty("circular_flow", Decimal("20"), "CIRCULAR_FLOW_DETECTED")
        if (
            metrics.rapid_round_trip_ratio is not None
            and metrics.rapid_round_trip_ratio >= self.policy.rapid_round_trip_threshold
        ):
            add_penalty("rapid_round_trip", Decimal("15"), "RAPID_ROUND_TRIP")
        if metrics.wash_suspected_volume is not None and metrics.wash_suspected_volume > 0:
            reasons.append(ReasonCode("WASH_VOLUME_SUSPECTED"))
        if (
            metrics.organic_volume_ratio is not None
            and metrics.organic_volume_ratio < self.policy.minimum_organic_volume_ratio
        ):
            add_penalty(
                "organic_volume_low",
                self.policy.organic_volume_penalty,
                "ORGANIC_VOLUME_LOW",
            )

        if quality_state is not QualityState.FRESH:
            score = Decimal("0")
            confidence = Decimal("0")
        else:
            score = max(Decimal("0"), Decimal("100") - sum(penalties.values(), Decimal("0")))
            confidence = min(Decimal("1"), liquidity.confidence + Decimal("0.2"))
            if matched_trades and trade_reasons == (ReasonCode("TRADE_ROWS_ANALYZED"),):
                confidence = min(Decimal("1"), confidence + Decimal("0.2"))
            if quote_state is QualityState.FRESH:
                confidence = min(Decimal("1"), confidence + Decimal("0.1"))
            if metrics.organic_volume_ratio is not None:
                confidence *= metrics.organic_volume_ratio
        trade_as_of = (
            checked_at if not matched_trades else max(item.observed_at for item in matched_trades)
        )
        as_of = max(liquidity.as_of, trade_as_of)
        return OrganicFlowScore(
            token=token,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            score=score,
            confidence=confidence,
            liquidity=liquidity,
            metrics=metrics,
            penalties=penalties,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reasons),
            config_hash=normalized_config_hash,
            quality_state=quality_state,
        )


__all__ = [
    "FlowAnalysisPolicy",
    "FlowAnalyzer",
    "FlowMetrics",
    "LiquiditySnapshot",
    "OrganicFlowScore",
]
