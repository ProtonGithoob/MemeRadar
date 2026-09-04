"""Provider-independent MadeOnSol-derived signal hardening evidence.

This module contains deterministic evidence calculations only.  It does not
depend on MadeOnSol, a provider SDK, persistence, networking, signing or
execution.  The name of the extension is retained for traceability to the
approved research brief; the contracts are MemeRadar-owned and configurable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

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
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

SIGNAL_HARDENING_VERSION = "signal-hardening-v1"
DEFAULT_SIGNAL_EVIDENCE_TTL = timedelta(minutes=5)
_MISSING = object()
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}
_MARKET_KINDS = frozenset(
    {
        "market.snapshot",
        "market.market_data",
        "market.observation",
        "market.price",
    }
)
_TRADE_KINDS = frozenset(
    {
        "market.trade",
        "market.trades",
        "market.trade_data",
        "wallet.activity",
        "wallet.trade",
        "wallet.swap",
    }
)
_TRANSFER_KINDS = frozenset(
    {
        "wallet.transfer",
        "onchain.transfer",
        "token.transfer",
        "onchain.token_transfer",
    }
)
_BALANCE_KINDS = frozenset(
    {
        "wallet.balance",
        "wallet.census",
        "deployer.snapshot",
        "onchain.wallet_balance",
    }
)
_LOCK_KINDS = frozenset(
    {
        "token.lock",
        "token.vesting",
        "token.unlock",
        "token.unlock_event",
        "lock.snapshot",
        "vesting.snapshot",
        "lp.lock",
        "liquidity.lock",
    }
)


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _optional_decimal(value: object, field_name: str, *, positive: bool = False) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    parsed = to_decimal(value, field_name)
    if parsed < 0 or (positive and parsed <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be {qualifier}")
    return parsed


def _optional_int(value: object, field_name: str, *, positive: bool = False) -> int | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    parsed = to_decimal(value, field_name)
    if parsed != parsed.to_integral_value():
        raise ValueError(f"{field_name} must be an integer")
    result = int(parsed)
    if result < 0 or (positive and result <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be {qualifier}")
    return result


def _optional_address(value: object, field_name: str) -> str | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a Solana address")
    return require_solana_address(value, field_name)


def _optional_datetime(value: object, field_name: str) -> datetime | None:
    if value is _MISSING or value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value, field_name)
    if isinstance(value, str):
        try:
            return ensure_utc(datetime.fromisoformat(value), field_name)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    raise TypeError(f"{field_name} must be an ISO timestamp")


def _side(value: object) -> str | None:
    if value is _MISSING or value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"buy", "bought", "bid", "entry", "purchase"}:
        return "buy"
    if normalized in {"sell", "sold", "ask", "exit", "sale"}:
        return "sell"
    return None


def _optional_bool(value: object, field_name: str) -> bool | None:
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
        if normalized in {"unknown", "unverified", ""}:
            return None
    raise TypeError(f"{field_name} must be a boolean")


class LockAssetScope(str, Enum):
    """Asset scope for a lock; token locks and LP locks are not interchangeable."""

    TOKEN = "TOKEN"
    LP = "LP"
    UNKNOWN = "UNKNOWN"


def _lock_scope(value: object, *, kind: str | None = None) -> LockAssetScope:
    if value is _MISSING or value is None:
        normalized_kind = (kind or "").lower()
        if normalized_kind in {"lp.lock", "liquidity.lock"}:
            return LockAssetScope.LP
        if normalized_kind.startswith("token.") or normalized_kind in {
            "vesting.snapshot",
            "lock.snapshot",
        }:
            return LockAssetScope.TOKEN
        return LockAssetScope.UNKNOWN
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in {
        "token",
        "tokens",
        "vesting",
        "token_lock",
        "token_vesting",
        "token_supply",
    }:
        return LockAssetScope.TOKEN
    if normalized in {
        "lp",
        "lp_token",
        "liquidity",
        "liquidity_pool",
        "lp_lock",
    }:
        return LockAssetScope.LP
    return LockAssetScope.UNKNOWN


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _canonical(item))
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], values: Sequence[Provenance]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _reason_code_value(value: ReasonCode | str) -> str:
    return value.code if isinstance(value, ReasonCode) else value


def _normalize_provenance(values: Sequence[Provenance]) -> tuple[Provenance, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, Provenance) for value in normalized):
        raise TypeError("provenance must contain Provenance values")
    return tuple(
        sorted(
            normalized,
            key=lambda value: (
                value.provider,
                value.source_id,
                value.observed_at,
                value.parser_version,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class SignalHardeningPolicy:
    """Versioned, bounded hypotheses used by all hardening evidence."""

    evidence_ttl: timedelta = DEFAULT_SIGNAL_EVIDENCE_TTL
    momentum_window: timedelta = timedelta(minutes=1)
    minimum_sustained_duration: timedelta = timedelta(seconds=10)
    minimum_sustained_samples: int = 3
    revival_inactivity: timedelta = timedelta(hours=24)
    minimum_buy_trade_count: int = 1
    minimum_buy_quote_volume: Decimal = Decimal("0.000000001")
    minimum_unique_buyers: int = 1
    minimum_funding_ratio: Decimal = Decimal("0.5")
    wash_volume_multiplier: Decimal = Decimal("0")
    thin_liquidity_ratio: Decimal = Decimal("0.01")
    launch_max_slots: int = 10
    launch_max_duration: timedelta = timedelta(seconds=10)
    high_early_capture_pct: Decimal = Decimal("0.5")
    large_unlock_ratio: Decimal = Decimal("0.25")
    unlock_horizons: tuple[tuple[str, timedelta], ...] = (
        ("1h", timedelta(hours=1)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    )
    version: str = SIGNAL_HARDENING_VERSION
    analysis_only: bool = True
    paper_trading: bool = True
    manual_execution: bool = False
    auto_execution: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_ttl",
            "momentum_window",
            "minimum_sustained_duration",
            "revival_inactivity",
            "launch_max_duration",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, timedelta) or value <= timedelta(0):
                raise ValueError(f"{field_name} must be positive")
        for field_name in (
            "minimum_sustained_samples",
            "minimum_buy_trade_count",
            "minimum_unique_buyers",
            "launch_max_slots",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        for field_name in (
            "minimum_buy_quote_volume",
            "minimum_funding_ratio",
            "wash_volume_multiplier",
            "thin_liquidity_ratio",
            "high_early_capture_pct",
            "large_unlock_ratio",
        ):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0 or (
                field_name
                in {"minimum_funding_ratio", "wash_volume_multiplier", "thin_liquidity_ratio"}
                and value > 1
            ):
                raise ValueError(f"{field_name} must be between zero and one")
            object.__setattr__(self, field_name, value)
        if self.minimum_sustained_duration > self.momentum_window:
            raise ValueError("minimum_sustained_duration cannot exceed momentum_window")
        if not isinstance(self.unlock_horizons, Sequence) or isinstance(
            self.unlock_horizons, str | bytes | bytearray
        ):
            raise TypeError("unlock_horizons must be a sequence")
        horizons: list[tuple[str, timedelta]] = []
        previous = timedelta(0)
        for name, duration in self.unlock_horizons:
            normalized_name = require_text(name, "unlock horizon", max_length=16)
            if not isinstance(duration, timedelta) or duration <= previous:
                raise ValueError("unlock horizons must be strictly increasing")
            horizons.append((normalized_name, duration))
            previous = duration
        if not horizons:
            raise ValueError("unlock_horizons must not be empty")
        object.__setattr__(self, "unlock_horizons", tuple(horizons))
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))
        for field_name, expected in (
            ("analysis_only", True),
            ("paper_trading", True),
            ("manual_execution", False),
            ("auto_execution", False),
        ):
            if getattr(self, field_name) is not expected:
                raise ValueError(f"{field_name} is a protected operating mode")


class MomentumRegimeKind(str, Enum):
    SURGE = "SURGE"
    REVIVAL = "REVIVAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class MomentumRegimeSnapshot:
    """Evidence that a move persisted and was supported by actual buying."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    kind: MomentumRegimeKind | str
    tier: str
    config_hash: str
    started_at: datetime | None = None
    confirmed_at: datetime | None = None
    sustained_for_ms: int | None = None
    launch_market_cap: Decimal | None = None
    current_market_cap: Decimal | None = None
    market_cap_delta: Decimal | None = None
    buy_trade_count: int = 0
    sell_trade_count: int = 0
    buy_quote_volume: Decimal | None = None
    sell_quote_volume: Decimal | None = None
    unique_buyers: int | None = None
    liquidity: Decimal | None = None
    liquidity_to_market_cap_ratio: Decimal | None = None
    quality_state: QualityState = QualityState.UNKNOWN
    confidence: Decimal = Decimal("0")
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("MOMENTUM_EVIDENCE_UNKNOWN",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "kind", MomentumRegimeKind(self.kind))
        object.__setattr__(self, "tier", require_text(self.tier, "tier", max_length=64))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        for field_name in ("started_at", "confirmed_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        if self.sustained_for_ms is not None and (
            not isinstance(self.sustained_for_ms, int)
            or isinstance(self.sustained_for_ms, bool)
            or self.sustained_for_ms < 0
        ):
            raise ValueError("sustained_for_ms must be non-negative")
        for field_name in ("buy_trade_count", "sell_trade_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.unique_buyers is not None and (
            not isinstance(self.unique_buyers, int)
            or isinstance(self.unique_buyers, bool)
            or self.unique_buyers < 0
        ):
            raise ValueError("unique_buyers must be non-negative")
        for field_name in (
            "launch_market_cap",
            "current_market_cap",
            "market_cap_delta",
            "buy_quote_volume",
            "sell_quote_volume",
            "liquidity",
            "liquidity_to_market_cap_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = _optional_decimal(value, field_name)
                object.__setattr__(self, field_name, parsed)
        object.__setattr__(
            self,
            "quality_state",
            QualityState(self.quality_state),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def market_cap_delta_usd(self) -> Decimal | None:
        return self.market_cap_delta

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    @property
    def data_completeness(self) -> Decimal:
        """Expose confidence as the bounded completeness proxy for momentum evidence."""

        return self.confidence if self.quality_state is QualityState.FRESH else Decimal("0")

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "kind": MomentumRegimeKind(self.kind).value,
                "tier": self.tier,
                "started_at": self.started_at,
                "confirmed_at": self.confirmed_at,
                "sustained_for_ms": self.sustained_for_ms,
                "launch_market_cap": self.launch_market_cap,
                "current_market_cap": self.current_market_cap,
                "market_cap_delta": self.market_cap_delta,
                "buy_trade_count": self.buy_trade_count,
                "sell_trade_count": self.sell_trade_count,
                "buy_quote_volume": self.buy_quote_volume,
                "sell_quote_volume": self.sell_quote_volume,
                "unique_buyers": self.unique_buyers,
                "liquidity": self.liquidity,
                "liquidity_to_market_cap_ratio": self.liquidity_to_market_cap_ratio,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            }
        )


@dataclass(frozen=True, slots=True)
class MoveFundingEvidence:
    """Economic corroboration for a market-cap move and its tape funding."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    config_hash: str
    market_cap_delta_usd: Decimal | None = None
    buy_volume: Decimal | None = None
    sell_volume: Decimal | None = None
    volume_unit: str | None = None
    buy_volume_usd: Decimal | None = None
    sell_volume_usd: Decimal | None = None
    buy_volume_to_mc_move_ratio: Decimal | None = None
    liquidity_usd: Decimal | None = None
    liquidity_to_mc_ratio: Decimal | None = None
    wash_adjusted_buy_volume: Decimal | None = None
    wash_adjusted_buy_volume_usd: Decimal | None = None
    funding_confirmed: bool | None = None
    data_completeness: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    confidence: Decimal = Decimal("0")
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("MOVE_VOLUME_EVIDENCE_MISSING",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if self.volume_unit is not None:
            object.__setattr__(
                self,
                "volume_unit",
                require_text(self.volume_unit, "volume_unit", max_length=32).upper(),
            )
        for field_name in (
            "market_cap_delta_usd",
            "buy_volume",
            "sell_volume",
            "buy_volume_usd",
            "sell_volume_usd",
            "buy_volume_to_mc_move_ratio",
            "liquidity_usd",
            "liquidity_to_mc_ratio",
            "wash_adjusted_buy_volume",
            "wash_adjusted_buy_volume_usd",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = to_decimal(value, field_name)
                if field_name != "market_cap_delta_usd" and parsed < 0:
                    raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, parsed)
        object.__setattr__(
            self,
            "data_completeness",
            bounded_decimal(
                self.data_completeness, "data_completeness", Decimal("0"), Decimal("1")
            ),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.funding_confirmed is not None and not isinstance(self.funding_confirmed, bool):
            raise TypeError("funding_confirmed must be a boolean or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def liquidity(self) -> Decimal | None:
        return self.liquidity_usd

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "market_cap_delta_usd": self.market_cap_delta_usd,
                "buy_volume": self.buy_volume,
                "sell_volume": self.sell_volume,
                "volume_unit": self.volume_unit,
                "buy_volume_usd": self.buy_volume_usd,
                "sell_volume_usd": self.sell_volume_usd,
                "buy_volume_to_mc_move_ratio": self.buy_volume_to_mc_move_ratio,
                "liquidity_usd": self.liquidity_usd,
                "liquidity_to_mc_ratio": self.liquidity_to_mc_ratio,
                "wash_adjusted_buy_volume": self.wash_adjusted_buy_volume,
                "wash_adjusted_buy_volume_usd": self.wash_adjusted_buy_volume_usd,
                "funding_confirmed": self.funding_confirmed,
                "data_completeness": self.data_completeness,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            }
        )


@dataclass(frozen=True, slots=True)
class DeployerActivitySnapshot:
    """Deployer trade/transfer reconciliation, never an intent verdict."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    config_hash: str
    deployer_wallet: str | None = None
    launch_timestamp: datetime | None = None
    initial_buy_amount: Decimal | None = None
    initial_acquired_supply_pct: Decimal | None = None
    post_launch_buys: Decimal | None = None
    post_launch_sells: Decimal | None = None
    post_launch_buy_count: int = 0
    post_launch_sell_count: int = 0
    first_sell_at: datetime | None = None
    last_sell_at: datetime | None = None
    trade_derived_holdings: Decimal | None = None
    observed_onchain_holdings: Decimal | None = None
    transfer_delta: Decimal | None = None
    tokens_transferred_out_without_swap: Decimal | None = None
    tokens_transferred_in_without_swap: Decimal | None = None
    wallet_empty: bool | None = None
    current_holdings: Decimal | None = None
    current_holdings_pct: Decimal | None = None
    data_completeness: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    confidence: Decimal = Decimal("0")
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("DEPLOYER_ACTIVITY_UNKNOWN",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        if self.deployer_wallet is not None:
            object.__setattr__(
                self,
                "deployer_wallet",
                require_solana_address(self.deployer_wallet, "deployer_wallet"),
            )
        if self.launch_timestamp is not None:
            object.__setattr__(
                self, "launch_timestamp", ensure_utc(self.launch_timestamp, "launch_timestamp")
            )
        for field_name in ("first_sell_at", "last_sell_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, ensure_utc(value, field_name))
        for field_name in (
            "initial_buy_amount",
            "initial_acquired_supply_pct",
            "post_launch_buys",
            "post_launch_sells",
            "trade_derived_holdings",
            "observed_onchain_holdings",
            "transfer_delta",
            "tokens_transferred_out_without_swap",
            "tokens_transferred_in_without_swap",
            "current_holdings",
            "current_holdings_pct",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = to_decimal(value, field_name)
                if field_name not in {"transfer_delta"} and parsed < 0:
                    raise ValueError(f"{field_name} must be non-negative")
                if (
                    field_name in {"initial_acquired_supply_pct", "current_holdings_pct"}
                    and parsed > 1
                ):
                    raise ValueError(f"{field_name} must be between zero and one")
                object.__setattr__(self, field_name, parsed)
        for field_name in ("post_launch_buy_count", "post_launch_sell_count"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        object.__setattr__(
            self,
            "data_completeness",
            bounded_decimal(
                self.data_completeness, "data_completeness", Decimal("0"), Decimal("1")
            ),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        if self.wallet_empty is not None and not isinstance(self.wallet_empty, bool):
            raise TypeError("wallet_empty must be a boolean or None")
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def expected_trade_derived_holdings(self) -> Decimal | None:
        return self.trade_derived_holdings

    @property
    def on_chain_holdings(self) -> Decimal | None:
        return self.observed_onchain_holdings

    @property
    def transfer_delta_tokens(self) -> Decimal | None:
        return self.transfer_delta

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "deployer_wallet": self.deployer_wallet,
                "launch_timestamp": self.launch_timestamp,
                "initial_buy_amount": self.initial_buy_amount,
                "initial_acquired_supply_pct": self.initial_acquired_supply_pct,
                "post_launch_buys": self.post_launch_buys,
                "post_launch_sells": self.post_launch_sells,
                "post_launch_buy_count": self.post_launch_buy_count,
                "post_launch_sell_count": self.post_launch_sell_count,
                "first_sell_at": self.first_sell_at,
                "last_sell_at": self.last_sell_at,
                "trade_derived_holdings": self.trade_derived_holdings,
                "observed_onchain_holdings": self.observed_onchain_holdings,
                "transfer_delta": self.transfer_delta,
                "tokens_transferred_out_without_swap": self.tokens_transferred_out_without_swap,
                "tokens_transferred_in_without_swap": self.tokens_transferred_in_without_swap,
                "wallet_empty": self.wallet_empty,
                "current_holdings": self.current_holdings,
                "current_holdings_pct": self.current_holdings_pct,
                "data_completeness": self.data_completeness,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            }
        )


@dataclass(frozen=True, slots=True)
class LaunchFootprintSnapshot:
    """Bounded early-launch footprint and actor-cluster evidence."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    config_hash: str
    first_n_slots: int = 10
    first_n_seconds: int = 10
    launch_slot: int | None = None
    launch_timestamp: datetime | None = None
    early_buyer_count: int | None = None
    sniper_wallet_count: int | None = None
    bundle_actor_cluster_count: int | None = None
    quote_acquired: Decimal | None = None
    quote_unit: str | None = None
    supply_acquired_pct: Decimal | None = None
    still_held_pct: Decimal | None = None
    actor_cluster_adjusted_concentration: Decimal | None = None
    data_available: bool = False
    data_completeness: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    confidence: Decimal = Decimal("0")
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("EARLY_BUYER_DATA_INCOMPLETE",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        for field_name in ("first_n_slots", "first_n_seconds"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
        if self.launch_slot is not None and (
            not isinstance(self.launch_slot, int)
            or isinstance(self.launch_slot, bool)
            or self.launch_slot < 0
        ):
            raise ValueError("launch_slot must be a non-negative integer")
        if self.launch_timestamp is not None:
            object.__setattr__(
                self,
                "launch_timestamp",
                ensure_utc(self.launch_timestamp, "launch_timestamp"),
            )
        for field_name in (
            "early_buyer_count",
            "sniper_wallet_count",
            "bundle_actor_cluster_count",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or None")
        if self.quote_unit is not None:
            object.__setattr__(
                self,
                "quote_unit",
                require_text(self.quote_unit, "quote_unit", max_length=32).upper(),
            )
        for field_name in (
            "quote_acquired",
            "supply_acquired_pct",
            "still_held_pct",
            "actor_cluster_adjusted_concentration",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = _optional_decimal(value, field_name)
                if field_name != "quote_acquired" and parsed is not None and parsed > 1:
                    raise ValueError(f"{field_name} must be between zero and one")
                object.__setattr__(self, field_name, parsed)
        if not isinstance(self.data_available, bool):
            raise TypeError("data_available must be a boolean")
        object.__setattr__(
            self,
            "data_completeness",
            bounded_decimal(
                self.data_completeness,
                "data_completeness",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
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
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "first_n_slots": self.first_n_slots,
                "first_n_seconds": self.first_n_seconds,
                "launch_slot": self.launch_slot,
                "launch_timestamp": self.launch_timestamp,
                "early_buyer_count": self.early_buyer_count,
                "sniper_wallet_count": self.sniper_wallet_count,
                "bundle_actor_cluster_count": self.bundle_actor_cluster_count,
                "quote_acquired": self.quote_acquired,
                "quote_unit": self.quote_unit,
                "supply_acquired_pct": self.supply_acquired_pct,
                "still_held_pct": self.still_held_pct,
                "actor_cluster_adjusted_concentration": self.actor_cluster_adjusted_concentration,
                "data_available": self.data_available,
                "data_completeness": self.data_completeness,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            }
        )


@dataclass(frozen=True, slots=True)
class TokenUnlockEvent:
    """An immutable future-supply release observation."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    config_hash: str
    unlock_at: datetime
    amount: Decimal
    unlock_type: str
    asset_scope: LockAssetScope | str = LockAssetScope.TOKEN
    locker_program: str | None = None
    cancelable_by_sender: bool | None = None
    quality_state: QualityState = QualityState.UNKNOWN
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("VESTING_SCHEDULE_PRESENT",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "unlock_at", ensure_utc(self.unlock_at, "unlock_at"))
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        amount = to_decimal(self.amount, "amount")
        if amount < 0:
            raise ValueError("amount must be non-negative")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(
            self,
            "unlock_type",
            require_text(self.unlock_type, "unlock_type", max_length=32).upper(),
        )
        object.__setattr__(self, "asset_scope", LockAssetScope(self.asset_scope))
        if self.locker_program is not None:
            object.__setattr__(
                self,
                "locker_program",
                require_text(self.locker_program, "locker_program", max_length=128),
            )
        if self.cancelable_by_sender is not None and not isinstance(
            self.cancelable_by_sender, bool
        ):
            raise TypeError("cancelable_by_sender must be a boolean or None")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "unlock_at": self.unlock_at,
                "amount": self.amount,
                "unlock_type": self.unlock_type,
                "asset_scope": LockAssetScope(self.asset_scope).value,
                "locker_program": self.locker_program,
                "cancelable_by_sender": self.cancelable_by_sender,
                "quality_state": self.quality_state.value,
                "evidence_refs": self.evidence_refs,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "version": self.version,
                "config_hash": self.config_hash,
            }
        )


@dataclass(frozen=True, slots=True)
class TokenLockSnapshot:
    """Token/vesting lock state, deliberately distinct from LP lock state."""

    token: TokenIdentity
    as_of: datetime
    expires_at: datetime
    config_hash: str
    asset_scope: LockAssetScope | str = LockAssetScope.UNKNOWN
    locker_program: str | None = None
    lock_present: bool | None = None
    deposited_amount: Decimal | None = None
    locked_amount: Decimal | None = None
    unlocked_amount: Decimal | None = None
    withdrawn_amount: Decimal | None = None
    claimable_amount: Decimal | None = None
    next_unlock_at: datetime | None = None
    next_unlock_type: str | None = None
    cancelable_by_sender: bool | None = None
    scheduled_unlocks: tuple[tuple[str, Decimal], ...] = ()
    unlock_events: tuple[TokenUnlockEvent, ...] = ()
    data_completeness: Decimal = Decimal("0")
    quality_state: QualityState = QualityState.UNKNOWN
    confidence: Decimal = Decimal("0")
    provenance: tuple[Provenance, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[ReasonCode | str, ...] = ("LOCK_DATA_UNKNOWN",)
    version: str = SIGNAL_HARDENING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "config_hash", require_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "asset_scope", LockAssetScope(self.asset_scope))
        if self.locker_program is not None:
            object.__setattr__(
                self,
                "locker_program",
                require_text(self.locker_program, "locker_program", max_length=128),
            )
        if self.lock_present is not None and not isinstance(self.lock_present, bool):
            raise TypeError("lock_present must be a boolean or None")
        for field_name in (
            "deposited_amount",
            "locked_amount",
            "unlocked_amount",
            "withdrawn_amount",
            "claimable_amount",
        ):
            value = getattr(self, field_name)
            if value is not None:
                parsed = to_decimal(value, field_name)
                if parsed < 0:
                    raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, parsed)
        if self.next_unlock_at is not None:
            object.__setattr__(
                self, "next_unlock_at", ensure_utc(self.next_unlock_at, "next_unlock_at")
            )
        if self.next_unlock_type is not None:
            object.__setattr__(
                self,
                "next_unlock_type",
                require_text(self.next_unlock_type, "next_unlock_type", max_length=32).upper(),
            )
        if self.cancelable_by_sender is not None and not isinstance(
            self.cancelable_by_sender, bool
        ):
            raise TypeError("cancelable_by_sender must be a boolean or None")
        normalized_schedule: list[tuple[str, Decimal]] = []
        seen_schedule: set[str] = set()
        for name, amount in self.scheduled_unlocks:
            normalized_name = require_text(name, "unlock horizon", max_length=32)
            if normalized_name in seen_schedule:
                raise ValueError("scheduled_unlocks must not contain duplicate horizons")
            parsed_amount = to_decimal(amount, f"scheduled unlock {normalized_name}")
            if parsed_amount < 0:
                raise ValueError("scheduled unlock amount must be non-negative")
            normalized_schedule.append((normalized_name, parsed_amount))
            seen_schedule.add(normalized_name)
        object.__setattr__(self, "scheduled_unlocks", tuple(normalized_schedule))
        if any(not isinstance(event, TokenUnlockEvent) for event in self.unlock_events):
            raise TypeError("unlock_events must contain TokenUnlockEvent values")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "data_completeness",
            bounded_decimal(
                self.data_completeness,
                "data_completeness",
                Decimal("0"),
                Decimal("1"),
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            bounded_decimal(self.confidence, "confidence", Decimal("0"), Decimal("1")),
        )
        object.__setattr__(self, "provenance", _normalize_provenance(self.provenance))
        object.__setattr__(
            self, "evidence_refs", normalize_texts(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "reason_codes", normalize_reason_codes(self.reason_codes, required=True)
        )
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))

    @property
    def token_lock_present(self) -> bool | None:
        if self.asset_scope is not LockAssetScope.TOKEN:
            return None
        return self.lock_present

    @property
    def freshness(self) -> Freshness:
        return Freshness(self.as_of, self.expires_at, self.quality_state)

    def scheduled_unlock_amount(self, horizon: str) -> Decimal | None:
        for name, amount in self.scheduled_unlocks:
            if name == horizon:
                return amount
        return None

    def execution_eligible(self) -> bool:
        return False

    def to_mapping(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "asset_scope": LockAssetScope(self.asset_scope).value,
                "locker_program": self.locker_program,
                "lock_present": self.lock_present,
                "token_lock_present": self.token_lock_present,
                "deposited_amount": self.deposited_amount,
                "locked_amount": self.locked_amount,
                "unlocked_amount": self.unlocked_amount,
                "withdrawn_amount": self.withdrawn_amount,
                "claimable_amount": self.claimable_amount,
                "next_unlock_at": self.next_unlock_at,
                "next_unlock_type": self.next_unlock_type,
                "cancelable_by_sender": self.cancelable_by_sender,
                "scheduled_unlocks": MappingProxyType(dict(self.scheduled_unlocks)),
                "unlock_events": tuple(event.to_mapping() for event in self.unlock_events),
                "data_completeness": self.data_completeness,
                "quality_state": self.quality_state.value,
                "confidence": self.confidence,
                "reason_codes": tuple(_reason_code_value(reason) for reason in self.reason_codes),
                "evidence_refs": self.evidence_refs,
                "version": self.version,
                "config_hash": self.config_hash,
                "execution_eligible": False,
            }
        )


@dataclass(frozen=True, slots=True)
class _TimedObservation:
    observation: Observation
    event_at: datetime
    quality_state: QualityState


class SignalHardeningAnalyzer:
    """Analyze normalized observations at an event-time boundary."""

    def __init__(self, *, policy: SignalHardeningPolicy | None = None) -> None:
        self.policy = policy or SignalHardeningPolicy()

    @staticmethod
    def _matches(observation: Observation, token: TokenIdentity) -> bool:
        payload_mint = _field(
            observation.normalized_payload,
            "mint_address",
            "token_mint",
            "tokenMint",
        )
        if payload_mint is not _MISSING and payload_mint != token.mint_address:
            return False
        if observation.token_id is not None:
            return observation.token_id == token.id
        return payload_mint == token.mint_address

    def _prepare(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
    ) -> tuple[tuple[_TimedObservation, ...], bool, bool]:
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        records: list[_TimedObservation] = []
        by_source: dict[tuple[str, str, str], object] = {}
        future = False
        conflict = False
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if not self._matches(observation, token):
                continue
            event_at = observation.occurred_at or observation.observed_at
            if event_at > now or observation.observed_at > now or observation.ingested_at > now:
                future = True
            key = (
                observation.provenance.provider,
                observation.provenance.source_id,
                observation.kind,
            )
            signature = _canonical(observation.normalized_payload)
            prior = by_source.get(key)
            if prior is not None and prior != signature:
                conflict = True
            else:
                by_source[key] = signature
            state = observation.quality_state
            if state is QualityState.FRESH:
                if event_at > now or observation.observed_at > now or observation.ingested_at > now:
                    state = QualityState.INVALID
                elif now >= observation.observed_at + self.policy.evidence_ttl:
                    state = QualityState.STALE
            records.append(_TimedObservation(observation, event_at, state))
        return (
            tuple(
                sorted(
                    records,
                    key=lambda value: (value.event_at, value.observation.provenance.source_id),
                )
            ),
            future,
            conflict,
        )

    @staticmethod
    def _refs(records: Sequence[_TimedObservation]) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    f"{record.observation.provenance.provider}:{record.observation.provenance.source_id}"
                    for record in records
                }
            )
        )

    @staticmethod
    def _provenance(records: Sequence[_TimedObservation]) -> tuple[Provenance, ...]:
        return _normalize_provenance(tuple(record.observation.provenance for record in records))

    def _snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        kind: MomentumRegimeKind,
        tier: str,
        reasons: Sequence[ReasonCode | str],
        start_at: datetime | None = None,
        confirmed_at: datetime | None = None,
        sustained_for_ms: int | None = None,
        launch_market_cap: Decimal | None = None,
        current_market_cap: Decimal | None = None,
        market_cap_delta: Decimal | None = None,
        buy_trade_count: int = 0,
        sell_trade_count: int = 0,
        buy_quote_volume: Decimal | None = None,
        sell_quote_volume: Decimal | None = None,
        unique_buyers: int | None = None,
        liquidity: Decimal | None = None,
        liquidity_to_market_cap_ratio: Decimal | None = None,
        quality_state: QualityState | None = None,
        confidence: Decimal = Decimal("0"),
    ) -> MomentumRegimeSnapshot:
        state = _combined_quality(tuple(record.quality_state for record in records))
        if quality_state is not None:
            state = quality_state
        return MomentumRegimeSnapshot(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            kind=kind,
            tier=tier,
            config_hash=config_hash,
            started_at=start_at,
            confirmed_at=confirmed_at,
            sustained_for_ms=sustained_for_ms,
            launch_market_cap=launch_market_cap,
            current_market_cap=current_market_cap,
            market_cap_delta=market_cap_delta,
            buy_trade_count=buy_trade_count,
            sell_trade_count=sell_trade_count,
            buy_quote_volume=buy_quote_volume,
            sell_quote_volume=sell_quote_volume,
            unique_buyers=unique_buyers,
            liquidity=liquidity,
            liquidity_to_market_cap_ratio=liquidity_to_market_cap_ratio,
            quality_state=state,
            confidence=confidence,
            provenance=self._provenance(records),
            evidence_refs=self._refs(records),
            reason_codes=tuple(reasons),
            version=self.policy.version,
        )

    def _unknown_momentum(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        reasons: Sequence[ReasonCode | str],
        quality_state: QualityState | None = None,
    ) -> MomentumRegimeSnapshot:
        return self._snapshot(
            token,
            now=now,
            config_hash=config_hash,
            records=records,
            kind=MomentumRegimeKind.UNKNOWN,
            tier="UNKNOWN",
            reasons=reasons,
            quality_state=quality_state,
        )

    def analyze_momentum(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> MomentumRegimeSnapshot:
        """Classify one bounded momentum window without future evidence."""

        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_end = ensure_utc(now if window_end is None else window_end, "window_end")
        if checked_end > ensure_utc(now, "now"):
            raise ValueError("window_end cannot be in the future")
        start = ensure_utc(
            checked_end - self.policy.momentum_window if window_start is None else window_start,
            "window_start",
        )
        if start >= checked_end:
            raise ValueError("window_start must precede window_end")
        normalized_hash = require_text(config_hash, "config_hash")
        records, future, conflict = self._prepare(token, observations, now=checked_end)
        if future:
            return self._unknown_momentum(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                reasons=("HARDENING_FUTURE_EVIDENCE",),
                quality_state=QualityState.INVALID,
            )
        if conflict:
            return self._unknown_momentum(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                reasons=("HARDENING_DUPLICATE_CONFLICT",),
                quality_state=QualityState.CONFLICTED,
            )
        current = tuple(record for record in records if start < record.event_at <= checked_end)
        critical_current = tuple(
            record for record in current if record.observation.kind in _MARKET_KINDS | _TRADE_KINDS
        )
        nonfresh_critical = tuple(
            record for record in critical_current if record.quality_state is not QualityState.FRESH
        )
        if nonfresh_critical:
            state = _combined_quality(tuple(record.quality_state for record in nonfresh_critical))
            return self._unknown_momentum(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=current,
                reasons=("MOMENTUM_EVIDENCE_NOT_FRESH", f"MOMENTUM_EVIDENCE_{state.value}"),
                quality_state=state,
            )
        fresh_current = tuple(
            record for record in current if record.quality_state is QualityState.FRESH
        )
        current_market = tuple(
            record
            for record in fresh_current
            if record.observation.kind in _MARKET_KINDS
            and _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "market_cap_usd",
                    "market_cap",
                    "marketCapUsd",
                    "market_capitalization",
                ),
                "market_cap",
                positive=True,
            )
            is not None
        )
        current_market = tuple(
            sorted(
                current_market,
                key=lambda record: (record.event_at, record.observation.provenance.source_id),
            )
        )
        fresh_trades = tuple(
            record for record in fresh_current if record.observation.kind in _TRADE_KINDS
        )
        historical_trade_records = tuple(
            record
            for record in records
            if record.event_at <= start
            and record.quality_state not in {QualityState.INVALID, QualityState.CONFLICTED}
            and record.observation.kind in _TRADE_KINDS
        )
        buy_trades = tuple(
            record
            for record in fresh_trades
            if _side(_field(record.observation.normalized_payload, "side", "action", "direction"))
            == "buy"
        )
        sell_trades = tuple(
            record
            for record in fresh_trades
            if _side(_field(record.observation.normalized_payload, "side", "action", "direction"))
            == "sell"
        )
        buy_volumes = tuple(
            value
            for record in buy_trades
            if (
                value := _optional_decimal(
                    _field(
                        record.observation.normalized_payload,
                        "quote_amount_usd",
                        "quote_amount",
                        "quote_volume",
                        "notional_usd",
                        "usd_value",
                        "volume_usd",
                    ),
                    "buy_quote_volume",
                    positive=True,
                )
            )
            is not None
        )
        sell_volumes = tuple(
            value
            for record in sell_trades
            if (
                value := _optional_decimal(
                    _field(
                        record.observation.normalized_payload,
                        "quote_amount_usd",
                        "quote_amount",
                        "quote_volume",
                        "notional_usd",
                        "usd_value",
                        "volume_usd",
                    ),
                    "sell_quote_volume",
                    positive=True,
                )
            )
            is not None
        )
        buy_volume = sum(buy_volumes, Decimal("0")) if buy_volumes else None
        sell_volume = sum(sell_volumes, Decimal("0")) if sell_volumes else None
        buyers = {
            address
            for record in buy_trades
            if (
                address := _optional_address(
                    _field(
                        record.observation.normalized_payload,
                        "buyer",
                        "buyer_address",
                        "wallet_address",
                        "maker",
                        "trader",
                    ),
                    "buyer",
                )
            )
            is not None
        }
        market_caps = tuple(
            (
                record,
                _optional_decimal(
                    _field(
                        record.observation.normalized_payload,
                        "market_cap_usd",
                        "market_cap",
                        "marketCapUsd",
                        "market_capitalization",
                    ),
                    "market_cap",
                    positive=True,
                ),
            )
            for record in current_market
        )
        valid_market_caps = tuple(
            (record, value) for record, value in market_caps if value is not None
        )
        prior_trade_records = historical_trade_records
        launch_market_cap = None
        all_market_records = tuple(
            record
            for record in records
            if record.quality_state is QualityState.FRESH
            and record.observation.kind in _MARKET_KINDS
        )
        for record in all_market_records:
            value = _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "market_cap_usd",
                    "market_cap",
                    "marketCapUsd",
                    "market_capitalization",
                ),
                "launch_market_cap",
                positive=True,
            )
            if value is not None:
                launch_market_cap = value
                break
        if not valid_market_caps or not buy_trades:
            reasons: list[ReasonCode | str] = ["MOMENTUM_EVIDENCE_UNKNOWN"]
            if not current:
                reasons.append("MOMENTUM_EVIDENCE_MISSING")
            if not valid_market_caps:
                reasons.append("MOMENTUM_MARKET_CAP_MISSING")
            if (
                not buy_trades
                or buy_volume is None
                or buy_volume < self.policy.minimum_buy_quote_volume
            ):
                reasons.append("MOMENTUM_BUY_EVIDENCE_MISSING")
                if prior_trade_records:
                    reasons.append("REVIVAL_BUY_EVIDENCE_MISSING")
            if prior_trade_records == () and current:
                reasons.append("REVIVAL_HISTORY_UNKNOWN")
            quality_records = current if current else records
            state = _combined_quality(tuple(record.quality_state for record in quality_records))
            return self._unknown_momentum(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=current,
                reasons=reasons,
                quality_state=state,
            )
        first_record, first_cap = valid_market_caps[0]
        last_record, last_cap = valid_market_caps[-1]
        assert first_cap is not None and last_cap is not None
        peak_cap = max(value for _, value in valid_market_caps)
        sustained_for_ms = int(
            (last_record.event_at - first_record.event_at).total_seconds() * 1000
        )
        positive_move = last_cap > first_cap
        no_immediate_reversal = last_cap >= peak_cap
        enough_samples = len(valid_market_caps) >= self.policy.minimum_sustained_samples
        enough_duration = (
            last_record.event_at - first_record.event_at >= self.policy.minimum_sustained_duration
        )
        enough_buy_flow = (
            len(buy_trades) >= self.policy.minimum_buy_trade_count
            and buy_volume is not None
            and buy_volume >= self.policy.minimum_buy_quote_volume
            and len(buyers) >= self.policy.minimum_unique_buyers
        )
        current_liquidity: Decimal | None = None
        for record in reversed(current_market):
            current_liquidity = _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "liquidity_usd",
                    "liquidity",
                    "liquidityUsd",
                ),
                "liquidity",
                positive=True,
            )
            if current_liquidity is not None:
                break
        liquidity_ratio = (
            current_liquidity / last_cap if current_liquidity is not None and last_cap > 0 else None
        )
        base_reasons: list[ReasonCode | str] = []
        if not enough_samples or not enough_duration or not no_immediate_reversal:
            base_reasons.extend(("MOMENTUM_NOT_SUSTAINED", "ONE_TICK_PRICE_SPIKE"))
        if not enough_buy_flow:
            base_reasons.append("MOMENTUM_BUY_EVIDENCE_MISSING")
        if current_liquidity is None:
            base_reasons.append("MOMENTUM_LIQUIDITY_EVIDENCE_MISSING")
        elif liquidity_ratio is not None and liquidity_ratio < self.policy.thin_liquidity_ratio:
            base_reasons.append("THIN_LIQUIDITY_MARK")
        if not positive_move:
            base_reasons.append("MOMENTUM_MOVE_NOT_POSITIVE")
        confirmed = (
            positive_move
            and enough_samples
            and enough_duration
            and no_immediate_reversal
            and enough_buy_flow
            and current_liquidity is not None
        )
        if not confirmed:
            if prior_trade_records == () and current:
                base_reasons.append("REVIVAL_HISTORY_UNKNOWN")
            if prior_trade_records and not enough_buy_flow:
                base_reasons.append("REVIVAL_BUY_EVIDENCE_MISSING")
            return self._snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=current,
                kind=MomentumRegimeKind.NONE,
                tier="UNCONFIRMED",
                reasons=base_reasons or ("MOMENTUM_NOT_SUSTAINED",),
                start_at=first_record.event_at,
                sustained_for_ms=sustained_for_ms,
                launch_market_cap=launch_market_cap,
                current_market_cap=last_cap,
                market_cap_delta=last_cap - first_cap,
                buy_trade_count=len(buy_trades),
                sell_trade_count=len(sell_trades),
                buy_quote_volume=buy_volume,
                sell_quote_volume=sell_volume,
                unique_buyers=len(buyers),
                liquidity=current_liquidity,
                liquidity_to_market_cap_ratio=liquidity_ratio,
                confidence=Decimal("0"),
            )
        prior_last_trade = prior_trade_records[-1] if prior_trade_records else None
        is_revival = (
            prior_last_trade is not None
            and first_record.event_at - prior_last_trade.event_at >= self.policy.revival_inactivity
        )
        reasons = ["MOMENTUM_SUSTAINED"]
        kind = MomentumRegimeKind.SURGE
        tier = "SUSTAINED"
        if is_revival:
            kind = MomentumRegimeKind.REVIVAL
            tier = "REVIVAL"
            reasons.append("REVIVAL_CONFIRMED")
        else:
            reasons.append("SURGE_CONFIRMED")
        duration_factor = min(
            Decimal("1"),
            Decimal(sustained_for_ms)
            / Decimal(int(self.policy.minimum_sustained_duration.total_seconds() * 1000)),
        )
        sample_factor = min(
            Decimal("1"),
            Decimal(len(valid_market_caps)) / Decimal(self.policy.minimum_sustained_samples),
        )
        buyer_factor = min(
            Decimal("1"),
            Decimal(len(buyers)) / Decimal(self.policy.minimum_unique_buyers),
        )
        confidence = min(duration_factor, sample_factor, buyer_factor)
        if liquidity_ratio is not None and liquidity_ratio < self.policy.thin_liquidity_ratio:
            confidence = min(confidence, Decimal("0.25"))
        return self._snapshot(
            token,
            now=checked_end,
            config_hash=normalized_hash,
            records=current,
            kind=kind,
            tier=tier,
            reasons=reasons,
            start_at=first_record.event_at,
            confirmed_at=last_record.event_at,
            sustained_for_ms=sustained_for_ms,
            launch_market_cap=launch_market_cap,
            current_market_cap=last_cap,
            market_cap_delta=last_cap - first_cap,
            buy_trade_count=len(buy_trades),
            sell_trade_count=len(sell_trades),
            buy_quote_volume=buy_volume,
            sell_quote_volume=sell_volume,
            unique_buyers=len(buyers),
            liquidity=current_liquidity,
            liquidity_to_market_cap_ratio=liquidity_ratio,
            confidence=confidence,
        )

    def _funding_snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        quality_state: QualityState,
        reasons: Sequence[ReasonCode | str],
        market_cap_delta_usd: Decimal | None = None,
        buy_volume: Decimal | None = None,
        sell_volume: Decimal | None = None,
        volume_unit: str | None = None,
        buy_volume_usd: Decimal | None = None,
        sell_volume_usd: Decimal | None = None,
        buy_volume_to_mc_move_ratio: Decimal | None = None,
        liquidity_usd: Decimal | None = None,
        liquidity_to_mc_ratio: Decimal | None = None,
        wash_adjusted_buy_volume: Decimal | None = None,
        wash_adjusted_buy_volume_usd: Decimal | None = None,
        funding_confirmed: bool | None = None,
        data_completeness: Decimal = Decimal("0"),
        confidence: Decimal = Decimal("0"),
    ) -> MoveFundingEvidence:
        return MoveFundingEvidence(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            config_hash=config_hash,
            market_cap_delta_usd=market_cap_delta_usd,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            volume_unit=volume_unit,
            buy_volume_usd=buy_volume_usd,
            sell_volume_usd=sell_volume_usd,
            buy_volume_to_mc_move_ratio=buy_volume_to_mc_move_ratio,
            liquidity_usd=liquidity_usd,
            liquidity_to_mc_ratio=liquidity_to_mc_ratio,
            wash_adjusted_buy_volume=wash_adjusted_buy_volume,
            wash_adjusted_buy_volume_usd=wash_adjusted_buy_volume_usd,
            funding_confirmed=funding_confirmed,
            data_completeness=data_completeness,
            quality_state=quality_state,
            confidence=confidence,
            provenance=self._provenance(records),
            evidence_refs=self._refs(records),
            reason_codes=tuple(reasons),
            version=self.policy.version,
        )

    def _trade_volume(
        self,
        record: _TimedObservation,
    ) -> tuple[Decimal | None, Decimal | None, str | None, Decimal | None]:
        payload = record.observation.normalized_payload
        usd = _optional_decimal(
            _field(
                payload,
                "quote_amount_usd",
                "quote_volume_usd",
                "notional_usd",
                "usd_value",
                "volume_usd",
            ),
            "trade buy volume usd",
            positive=True,
        )
        quote = _optional_decimal(
            _field(
                payload,
                "quote_amount",
                "quote_volume",
                "quoteAmount",
                "notional",
            ),
            "trade quote volume",
            positive=True,
        )
        if usd is None and quote is None:
            return None, None, None, None
        if usd is not None:
            amount = usd
            unit = "USD"
        else:
            assert quote is not None
            amount = quote
            raw_unit = _field(payload, "quote_currency", "quote_unit", "currency")
            unit = "QUOTE" if raw_unit is _MISSING or raw_unit is None else str(raw_unit).upper()
        wash_factor = Decimal("1")
        wash_flag = _field(payload, "wash_trade", "bot_trade", "wash_flag")
        if wash_flag is True or (
            isinstance(wash_flag, str) and wash_flag.strip().lower() in {"true", "yes", "1"}
        ):
            wash_factor = self.policy.wash_volume_multiplier
        else:
            wash_score = _optional_decimal(_field(payload, "wash_score", "bot_score"), "wash_score")
            if wash_score is not None:
                wash_factor = max(Decimal("0"), Decimal("1") - min(Decimal("1"), wash_score))
        return amount, usd, unit, amount * wash_factor

    def analyze_move_funding(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> MoveFundingEvidence:
        """Measure whether a market-cap movement has economically credible tape."""

        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_end = ensure_utc(now if window_end is None else window_end, "window_end")
        checked_now = ensure_utc(now, "now")
        if checked_end > checked_now:
            raise ValueError("window_end cannot be in the future")
        start = ensure_utc(
            checked_end - self.policy.momentum_window if window_start is None else window_start,
            "window_start",
        )
        if start >= checked_end:
            raise ValueError("window_start must precede window_end")
        normalized_hash = require_text(config_hash, "config_hash")
        records, future, conflict = self._prepare(token, observations, now=checked_end)
        if future:
            return self._funding_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.INVALID,
                reasons=("HARDENING_FUTURE_EVIDENCE",),
            )
        if conflict:
            return self._funding_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.CONFLICTED,
                reasons=("HARDENING_DUPLICATE_CONFLICT",),
            )
        current = tuple(record for record in records if start < record.event_at <= checked_end)
        critical_current = tuple(
            record for record in current if record.observation.kind in _MARKET_KINDS | _TRADE_KINDS
        )
        nonfresh_critical = tuple(
            record for record in critical_current if record.quality_state is not QualityState.FRESH
        )
        if nonfresh_critical:
            state = _combined_quality(tuple(record.quality_state for record in nonfresh_critical))
            stale_reasons: list[ReasonCode | str] = [
                "MOVE_EVIDENCE_NOT_FRESH",
                f"MOVE_EVIDENCE_{state.value}",
            ]
            if any(
                record.observation.kind in _MARKET_KINDS
                and record.quality_state is QualityState.STALE
                and _field(
                    record.observation.normalized_payload,
                    "liquidity_usd",
                    "liquidity",
                    "liquidityUsd",
                )
                is not _MISSING
                for record in nonfresh_critical
            ):
                stale_reasons.append("MOVE_LIQUIDITY_STALE")
            return self._funding_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=current,
                quality_state=state,
                reasons=stale_reasons,
            )
        current_market = tuple(
            record for record in current if record.observation.kind in _MARKET_KINDS
        )
        fresh_market = tuple(
            record for record in current_market if record.quality_state is QualityState.FRESH
        )
        fresh_trades = tuple(
            record
            for record in current
            if record.observation.kind in _TRADE_KINDS
            and record.quality_state is QualityState.FRESH
        )

        def market_cap(record: _TimedObservation) -> Decimal | None:
            return _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "market_cap_usd",
                    "market_cap",
                    "marketCapUsd",
                    "market_capitalization",
                ),
                "market_cap",
                positive=True,
            )

        market_points = tuple(
            (record, value)
            for record in sorted(fresh_market, key=lambda value: value.event_at)
            if (value := market_cap(record)) is not None
        )
        market_delta = None
        last_market_cap = None
        if len(market_points) >= 2:
            market_delta = market_points[-1][1] - market_points[0][1]
            last_market_cap = market_points[-1][1]
        elif market_points:
            last_market_cap = market_points[-1][1]
        buy_values: list[Decimal] = []
        sell_values: list[Decimal] = []
        buy_usd_values: list[Decimal] = []
        sell_usd_values: list[Decimal] = []
        adjusted_buy_values: list[Decimal] = []
        adjusted_buy_usd_values: list[Decimal] = []
        units: list[str] = []
        wash_seen = False
        for record in fresh_trades:
            side = _side(
                _field(record.observation.normalized_payload, "side", "action", "direction")
            )
            amount, amount_usd, unit, adjusted = self._trade_volume(record)
            if amount is None or unit is None:
                continue
            units.append(unit)
            if side == "buy":
                buy_values.append(amount)
                if amount_usd is not None:
                    buy_usd_values.append(amount_usd)
                if adjusted is not None:
                    adjusted_buy_values.append(adjusted)
                    if amount_usd is not None:
                        adjusted_buy_usd_values.append(adjusted)
                if adjusted != amount:
                    wash_seen = True
            elif side == "sell":
                sell_values.append(amount)
                if amount_usd is not None:
                    sell_usd_values.append(amount_usd)
        volume_unit = None
        buy_volume = None
        sell_volume = None
        adjusted_buy_volume = None
        if units:
            unique_units = tuple(dict.fromkeys(units))
            if len(unique_units) == 1:
                volume_unit = unique_units[0]
                buy_volume = sum(buy_values, Decimal("0")) if buy_values else None
                sell_volume = sum(sell_values, Decimal("0")) if sell_values else None
                adjusted_buy_volume = (
                    sum(adjusted_buy_values, Decimal("0")) if adjusted_buy_values else None
                )
        buy_volume_usd = sum(buy_usd_values, Decimal("0")) if buy_usd_values else None
        sell_volume_usd = sum(sell_usd_values, Decimal("0")) if sell_usd_values else None
        adjusted_buy_volume_usd = (
            sum(adjusted_buy_usd_values, Decimal("0")) if adjusted_buy_usd_values else None
        )
        ratio = None
        if market_delta is not None and market_delta > 0 and adjusted_buy_volume_usd is not None:
            ratio = adjusted_buy_volume_usd / market_delta
        latest_liquidity: Decimal | None = None
        liquidity_state = QualityState.UNKNOWN
        for record in reversed(current_market):
            value = _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "liquidity_usd",
                    "liquidity",
                    "liquidityUsd",
                ),
                "liquidity",
                positive=True,
            )
            if value is not None:
                latest_liquidity = value
                liquidity_state = record.quality_state
                break
        liquidity_ratio = (
            latest_liquidity / last_market_cap
            if latest_liquidity is not None and last_market_cap is not None and last_market_cap > 0
            else None
        )
        required_present = (
            market_delta is not None,
            adjusted_buy_volume_usd is not None or adjusted_buy_volume is not None,
            latest_liquidity is not None,
        )
        completeness = Decimal(sum(required_present)) / Decimal(len(required_present))
        reasons: list[ReasonCode | str] = []
        if market_delta is None:
            reasons.append("MOVE_MARKET_CAP_EVIDENCE_MISSING")
        if not fresh_trades or (buy_volume_usd is None and buy_volume is None):
            reasons.append("MOVE_VOLUME_EVIDENCE_MISSING")
        if volume_unit is not None and volume_unit != "USD":
            reasons.append("MOVE_VOLUME_UNIT_UNCONVERTED")
        if wash_seen:
            reasons.append("WASH_VOLUME_DISCOUNTED")
        if ratio is None and market_delta is not None and buy_volume is not None:
            reasons.append("MOVE_VOLUME_UNIT_UNCONVERTED")
        if ratio is not None:
            if ratio >= self.policy.minimum_funding_ratio:
                reasons.append("MOVE_VOLUME_CORROBORATED")
            else:
                reasons.append("MC_MOVE_UNDERFUNDED_BY_BUY_VOLUME")
        if liquidity_ratio is None:
            reasons.append("MOVE_LIQUIDITY_EVIDENCE_MISSING")
        elif liquidity_ratio < self.policy.thin_liquidity_ratio:
            reasons.append("THIN_LIQUIDITY_MARK")
        if liquidity_state is QualityState.STALE:
            reasons.append("MOVE_LIQUIDITY_STALE")
        if not reasons:
            reasons.append("MOVE_VOLUME_EVIDENCE_MISSING")
        if not current:
            state = QualityState.UNKNOWN
        elif future:
            state = QualityState.INVALID
        elif conflict:
            state = QualityState.CONFLICTED
        elif liquidity_state is QualityState.STALE:
            state = QualityState.STALE
        elif (
            market_delta is None
            or not fresh_trades
            or (buy_volume_usd is None and buy_volume is None)
        ):
            state = QualityState.UNKNOWN
        else:
            state = QualityState.FRESH
        funding_confirmed = None if ratio is None else ratio >= self.policy.minimum_funding_ratio
        confidence = completeness
        if funding_confirmed is False:
            confidence = min(confidence, Decimal("0.25"))
        if liquidity_ratio is not None and liquidity_ratio < self.policy.thin_liquidity_ratio:
            confidence = min(confidence, Decimal("0.25"))
        if volume_unit is not None and volume_unit != "USD":
            confidence = min(confidence, Decimal("0.5"))
        if state is not QualityState.FRESH:
            confidence = Decimal("0")
        return self._funding_snapshot(
            token,
            now=checked_end,
            config_hash=normalized_hash,
            records=current,
            quality_state=state,
            reasons=reasons,
            market_cap_delta_usd=market_delta,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            volume_unit=volume_unit,
            buy_volume_usd=buy_volume_usd,
            sell_volume_usd=sell_volume_usd,
            buy_volume_to_mc_move_ratio=ratio,
            liquidity_usd=latest_liquidity,
            liquidity_to_mc_ratio=liquidity_ratio,
            wash_adjusted_buy_volume=adjusted_buy_volume,
            wash_adjusted_buy_volume_usd=adjusted_buy_volume_usd,
            funding_confirmed=funding_confirmed,
            data_completeness=completeness,
            confidence=confidence,
        )

    def _deployer_snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        quality_state: QualityState,
        reasons: Sequence[ReasonCode | str],
        deployer_wallet: str | None = None,
        launch_timestamp: datetime | None = None,
        initial_buy_amount: Decimal | None = None,
        initial_acquired_supply_pct: Decimal | None = None,
        post_launch_buys: Decimal | None = None,
        post_launch_sells: Decimal | None = None,
        post_launch_buy_count: int = 0,
        post_launch_sell_count: int = 0,
        first_sell_at: datetime | None = None,
        last_sell_at: datetime | None = None,
        trade_derived_holdings: Decimal | None = None,
        observed_onchain_holdings: Decimal | None = None,
        transfer_delta: Decimal | None = None,
        tokens_transferred_out_without_swap: Decimal | None = None,
        tokens_transferred_in_without_swap: Decimal | None = None,
        wallet_empty: bool | None = None,
        current_holdings_pct: Decimal | None = None,
        data_completeness: Decimal = Decimal("0"),
        confidence: Decimal = Decimal("0"),
    ) -> DeployerActivitySnapshot:
        return DeployerActivitySnapshot(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            config_hash=config_hash,
            deployer_wallet=deployer_wallet,
            launch_timestamp=launch_timestamp,
            initial_buy_amount=initial_buy_amount,
            initial_acquired_supply_pct=initial_acquired_supply_pct,
            post_launch_buys=post_launch_buys,
            post_launch_sells=post_launch_sells,
            post_launch_buy_count=post_launch_buy_count,
            post_launch_sell_count=post_launch_sell_count,
            first_sell_at=first_sell_at,
            last_sell_at=last_sell_at,
            trade_derived_holdings=trade_derived_holdings,
            observed_onchain_holdings=observed_onchain_holdings,
            transfer_delta=transfer_delta,
            tokens_transferred_out_without_swap=tokens_transferred_out_without_swap,
            tokens_transferred_in_without_swap=tokens_transferred_in_without_swap,
            wallet_empty=wallet_empty,
            current_holdings=observed_onchain_holdings,
            current_holdings_pct=current_holdings_pct,
            data_completeness=data_completeness,
            quality_state=quality_state,
            confidence=confidence,
            provenance=self._provenance(records),
            evidence_refs=self._refs(records),
            reason_codes=tuple(reasons),
            version=self.policy.version,
        )

    def analyze_deployer_activity(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        deployer_wallet: str | None = None,
        now: datetime,
        config_hash: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DeployerActivitySnapshot:
        """Reconcile deployer trades, transfers and the latest wallet census."""

        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_end = ensure_utc(now if window_end is None else window_end, "window_end")
        if checked_end > ensure_utc(now, "now"):
            raise ValueError("window_end cannot be in the future")
        start = ensure_utc(
            checked_end - self.policy.momentum_window if window_start is None else window_start,
            "window_start",
        )
        if start >= checked_end:
            raise ValueError("window_start must precede window_end")
        normalized_hash = require_text(config_hash, "config_hash")
        records, future, conflict = self._prepare(token, observations, now=checked_end)
        if future:
            return self._deployer_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.INVALID,
                reasons=("HARDENING_FUTURE_EVIDENCE",),
                deployer_wallet=deployer_wallet,
            )
        if conflict:
            return self._deployer_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.CONFLICTED,
                reasons=("HARDENING_DUPLICATE_CONFLICT",),
                deployer_wallet=deployer_wallet,
            )
        candidate_deployer = deployer_wallet
        launch_record: _TimedObservation | None = None
        for record in records:
            payload = record.observation.normalized_payload
            found = _optional_address(
                _field(payload, "deployer", "deployer_wallet", "creator", "creator_wallet"),
                "deployer_wallet",
            )
            event_type = str(_field(payload, "event_type", "type")).strip().lower()
            if candidate_deployer is None and found is not None:
                candidate_deployer = found
            if found is not None and (
                event_type in {"create", "launch", "created"} or launch_record is None
            ):
                launch_record = record
        if candidate_deployer is not None:
            candidate_deployer = require_solana_address(candidate_deployer, "deployer_wallet")
        if launch_record is not None:
            launch_payload = launch_record.observation.normalized_payload
            launch_timestamp = (
                _optional_datetime(
                    _field(launch_payload, "launch_at", "launch_timestamp", "created_at"),
                    "launch_timestamp",
                )
                or launch_record.event_at
            )
            initial_buy_amount = _optional_decimal(
                _field(
                    launch_payload,
                    "initial_buy_amount",
                    "initial_acquired_amount",
                    "create_buy_amount",
                ),
                "initial_buy_amount",
                positive=True,
            )
            initial_acquired_supply_pct = _optional_decimal(
                _field(
                    launch_payload,
                    "initial_acquired_supply_pct",
                    "initial_supply_pct",
                    "initial_acquired_percent",
                ),
                "initial_acquired_supply_pct",
            )
        else:
            launch_timestamp = None
            initial_buy_amount = None
            initial_acquired_supply_pct = None
        if candidate_deployer is None:
            return self._deployer_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.UNKNOWN,
                reasons=("DEPLOYER_ACTIVITY_UNKNOWN",),
            )
        relevant = tuple(
            record
            for record in records
            if record.event_at <= checked_end
            and (
                _optional_address(
                    _field(
                        record.observation.normalized_payload,
                        "wallet_address",
                        "wallet",
                        "maker",
                        "trader",
                        "owner",
                    ),
                    "wallet_address",
                )
                == candidate_deployer
                or _optional_address(
                    _field(record.observation.normalized_payload, "from_address", "from"),
                    "from_address",
                )
                == candidate_deployer
                or _optional_address(
                    _field(record.observation.normalized_payload, "to_address", "to"),
                    "to_address",
                )
                == candidate_deployer
                or record is launch_record
            )
        )
        if not relevant:
            return self._deployer_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=records,
                quality_state=QualityState.UNKNOWN,
                reasons=("DEPLOYER_ACTIVITY_UNKNOWN",),
                deployer_wallet=candidate_deployer,
                launch_timestamp=launch_timestamp,
                initial_buy_amount=initial_buy_amount,
                initial_acquired_supply_pct=initial_acquired_supply_pct,
            )
        relevant_quality = _combined_quality(tuple(record.quality_state for record in relevant))
        trade_records = tuple(
            record
            for record in records
            if record.observation.kind in _TRADE_KINDS
            and record.quality_state is QualityState.FRESH
            and (
                _optional_address(
                    _field(
                        record.observation.normalized_payload,
                        "wallet_address",
                        "wallet",
                        "maker",
                        "trader",
                        "owner",
                    ),
                    "wallet_address",
                )
                == candidate_deployer
            )
            and (launch_timestamp is None or record.event_at >= launch_timestamp)
        )
        buy_amounts: list[Decimal] = []
        sell_amounts: list[Decimal] = []
        sell_times: list[datetime] = []
        for record in trade_records:
            amount = _optional_decimal(
                _field(
                    record.observation.normalized_payload,
                    "amount",
                    "base_amount",
                    "token_amount",
                    "quantity",
                    "size",
                ),
                "deployer token amount",
                positive=True,
            )
            if amount is None:
                continue
            side = _side(
                _field(record.observation.normalized_payload, "side", "action", "direction")
            )
            if side == "buy":
                buy_amounts.append(amount)
            elif side == "sell":
                sell_amounts.append(amount)
                sell_times.append(record.event_at)
        post_buys = sum(buy_amounts, Decimal("0")) if buy_amounts else None
        post_sells = sum(sell_amounts, Decimal("0")) if sell_amounts else None
        derived_parts = [
            value for value in (initial_buy_amount, post_buys, post_sells) if value is not None
        ]
        derived_holdings = None
        if derived_parts:
            derived_holdings = (
                (initial_buy_amount or Decimal("0"))
                + (post_buys or Decimal("0"))
                - (post_sells or Decimal("0"))
            )
            if derived_holdings < 0:
                derived_holdings = Decimal("0")
        transfer_out = Decimal("0")
        transfer_in = Decimal("0")
        transfer_seen = False
        for record in records:
            if record.observation.kind not in _TRANSFER_KINDS or record.quality_state in {
                QualityState.INVALID,
                QualityState.CONFLICTED,
            }:
                continue
            payload = record.observation.normalized_payload
            amount = _optional_decimal(
                _field(payload, "amount", "token_amount", "quantity", "value"),
                "transfer amount",
                positive=True,
            )
            if amount is None:
                continue
            sender = _optional_address(_field(payload, "from_address", "from"), "from_address")
            receiver = _optional_address(_field(payload, "to_address", "to"), "to_address")
            if sender == candidate_deployer:
                transfer_out += amount
                transfer_seen = True
            if receiver == candidate_deployer:
                transfer_in += amount
                transfer_seen = True
        balance_record: _TimedObservation | None = None
        observed_holdings: Decimal | None = None
        observed_pct: Decimal | None = None
        for record in records:
            if record.observation.kind not in _BALANCE_KINDS:
                continue
            payload = record.observation.normalized_payload
            wallet = _optional_address(
                _field(payload, "wallet_address", "wallet", "owner", "deployer"),
                "wallet_address",
            )
            if wallet != candidate_deployer or record.event_at > checked_end:
                continue
            if balance_record is None or record.event_at > balance_record.event_at:
                balance_record = record
                observed_holdings = _optional_decimal(
                    _field(
                        payload,
                        "token_holdings",
                        "current_holdings",
                        "on_chain_holdings",
                        "balance",
                        "amount",
                    ),
                    "observed_onchain_holdings",
                )
                observed_pct = _optional_decimal(
                    _field(payload, "holdings_pct", "current_holdings_pct", "supply_pct"),
                    "current_holdings_pct",
                )
        delta = None
        if observed_holdings is not None and derived_holdings is not None:
            delta = observed_holdings - derived_holdings
        reasons: list[ReasonCode | str] = []
        if (initial_buy_amount or Decimal("0")) > 0 or (post_buys or Decimal("0")) > 0:
            reasons.append("DEPLOYER_SELF_BUY")
        if (post_sells or Decimal("0")) > 0:
            reasons.append("DEPLOYER_SELLING")
        if observed_holdings == Decimal("0") and (derived_holdings or Decimal("0")) > 0:
            reasons.append("DEPLOYER_HOLDINGS_DRAINED")
        if delta is not None:
            if delta < 0:
                reasons.append("DEPLOYER_TRANSFER_DELTA_NEGATIVE")
            elif delta > 0:
                reasons.append("DEPLOYER_TRANSFER_DELTA_POSITIVE")
        if not transfer_seen:
            reasons.append("DEPLOYER_TRANSFER_EVIDENCE_MISSING")
        if balance_record is None or observed_holdings is None:
            reasons.append("DEPLOYER_ACTIVITY_UNKNOWN")
        if relevant_quality is not QualityState.FRESH:
            reasons.extend(
                ("DEPLOYER_EVIDENCE_NOT_FRESH", f"DEPLOYER_EVIDENCE_{relevant_quality.value}")
            )
        if not reasons:
            reasons.append("DEPLOYER_ACTIVITY_OBSERVED")
        if balance_record is None or observed_holdings is None:
            state = QualityState.UNKNOWN
        elif balance_record.quality_state is not QualityState.FRESH:
            state = balance_record.quality_state
        else:
            state = QualityState.FRESH
        state = _combined_quality((state, relevant_quality))
        completeness = Decimal("0")
        required = (
            candidate_deployer is not None,
            derived_holdings is not None,
            observed_holdings is not None,
        )
        completeness = Decimal(sum(required)) / Decimal(len(required))
        confidence = completeness if state is QualityState.FRESH else Decimal("0")
        return self._deployer_snapshot(
            token,
            now=checked_end,
            config_hash=normalized_hash,
            records=relevant,
            quality_state=state,
            reasons=reasons,
            deployer_wallet=candidate_deployer,
            launch_timestamp=launch_timestamp,
            initial_buy_amount=initial_buy_amount,
            initial_acquired_supply_pct=initial_acquired_supply_pct,
            post_launch_buys=post_buys,
            post_launch_sells=post_sells,
            post_launch_buy_count=len(buy_amounts),
            post_launch_sell_count=len(sell_amounts),
            first_sell_at=min(sell_times) if sell_times else None,
            last_sell_at=max(sell_times) if sell_times else None,
            trade_derived_holdings=derived_holdings,
            observed_onchain_holdings=observed_holdings,
            transfer_delta=delta,
            tokens_transferred_out_without_swap=transfer_out if transfer_seen else None,
            tokens_transferred_in_without_swap=transfer_in if transfer_seen else None,
            wallet_empty=None if observed_holdings is None else observed_holdings == Decimal("0"),
            current_holdings_pct=observed_pct,
            data_completeness=completeness,
            confidence=confidence,
        )

    def _launch_snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        quality_state: QualityState,
        reasons: Sequence[ReasonCode | str],
        launch_slot: int | None = None,
        launch_timestamp: datetime | None = None,
        early_buyer_count: int | None = None,
        sniper_wallet_count: int | None = None,
        bundle_actor_cluster_count: int | None = None,
        quote_acquired: Decimal | None = None,
        quote_unit: str | None = None,
        supply_acquired_pct: Decimal | None = None,
        still_held_pct: Decimal | None = None,
        actor_cluster_adjusted_concentration: Decimal | None = None,
        data_available: bool = False,
        data_completeness: Decimal = Decimal("0"),
        confidence: Decimal = Decimal("0"),
    ) -> LaunchFootprintSnapshot:
        return LaunchFootprintSnapshot(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            config_hash=config_hash,
            first_n_slots=self.policy.launch_max_slots,
            first_n_seconds=int(self.policy.launch_max_duration.total_seconds()),
            launch_slot=launch_slot,
            launch_timestamp=launch_timestamp,
            early_buyer_count=early_buyer_count,
            sniper_wallet_count=sniper_wallet_count,
            bundle_actor_cluster_count=bundle_actor_cluster_count,
            quote_acquired=quote_acquired,
            quote_unit=quote_unit,
            supply_acquired_pct=supply_acquired_pct,
            still_held_pct=still_held_pct,
            actor_cluster_adjusted_concentration=actor_cluster_adjusted_concentration,
            data_available=data_available,
            data_completeness=data_completeness,
            quality_state=quality_state,
            confidence=confidence,
            provenance=self._provenance(records),
            evidence_refs=self._refs(records),
            reason_codes=tuple(reasons),
            version=self.policy.version,
        )

    def analyze_launch_footprint(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> LaunchFootprintSnapshot:
        """Measure bounded launch capture and clustering without clean/unsafe claims."""

        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_end = ensure_utc(now if window_end is None else window_end, "window_end")
        if checked_end > ensure_utc(now, "now"):
            raise ValueError("window_end cannot be in the future")
        start = None if window_start is None else ensure_utc(window_start, "window_start")
        if start is not None and start >= checked_end:
            raise ValueError("window_start must precede window_end")
        normalized_hash = require_text(config_hash, "config_hash")
        records, future, conflict = self._prepare(token, observations, now=checked_end)
        scoped = tuple(record for record in records if start is None or record.event_at >= start)
        if future:
            return self._launch_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.INVALID,
                reasons=("HARDENING_FUTURE_EVIDENCE",),
            )
        if conflict:
            return self._launch_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.CONFLICTED,
                reasons=("HARDENING_DUPLICATE_CONFLICT",),
            )

        launch_record: _TimedObservation | None = None
        for record in scoped:
            payload = record.observation.normalized_payload
            event_type_value = _field(
                payload,
                "event_type",
                "lifecycle_event",
                "type",
                "action",
            )
            event_type = (
                "" if event_type_value is _MISSING else str(event_type_value).strip().lower()
            )
            slot_value = _field(payload, "launch_slot", "created_slot", "slot")
            if (
                event_type in {"create", "created", "launch", "launched", "token_created"}
                or slot_value is not _MISSING
            ) and (launch_record is None or record.event_at < launch_record.event_at):
                launch_record = record
        if launch_record is None:
            return self._launch_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.UNKNOWN,
                reasons=("LAUNCH_HISTORY_UNKNOWN",),
            )

        launch_payload = launch_record.observation.normalized_payload
        launch_slot = _optional_int(
            _field(launch_payload, "launch_slot", "created_slot", "slot"),
            "launch_slot",
        )
        launch_timestamp = (
            _optional_datetime(
                _field(launch_payload, "launch_at", "launch_timestamp", "created_at"),
                "launch_timestamp",
            )
            or launch_record.event_at
        )
        reasons: list[ReasonCode | str] = []
        incomplete = launch_slot is None
        if launch_slot is None:
            reasons.append("EARLY_BUYER_DATA_INCOMPLETE")

        early_records: list[_TimedObservation] = []
        wallet_missing = False
        for record in scoped:
            if record is launch_record or record.observation.kind not in _TRADE_KINDS:
                continue
            if record.quality_state in {QualityState.INVALID, QualityState.CONFLICTED}:
                incomplete = True
                continue
            payload = record.observation.normalized_payload
            if _side(_field(payload, "side", "action", "direction")) != "buy":
                continue
            if record.event_at < launch_timestamp:
                continue
            trade_slot = _optional_int(
                _field(payload, "slot", "slot_number", "transaction_slot"),
                "trade slot",
            )
            in_slot_window = True
            in_time_window = record.event_at <= launch_timestamp + self.policy.launch_max_duration
            if launch_slot is not None:
                if trade_slot is None:
                    incomplete = True
                else:
                    in_slot_window = (
                        launch_slot <= trade_slot < launch_slot + self.policy.launch_max_slots
                    )
            elif trade_slot is None:
                incomplete = True
            if trade_slot is None and not in_time_window:
                continue
            if not in_slot_window or not in_time_window:
                continue
            wallet = _optional_address(
                _field(payload, "wallet_address", "wallet", "buyer", "trader", "maker"),
                "early buyer wallet",
            )
            if wallet is None:
                wallet_missing = True
                incomplete = True
                continue
            early_records.append(record)

        if not early_records:
            reasons.append("EARLY_BUYER_DATA_INCOMPLETE")
            no_trade_state = (
                QualityState.UNKNOWN
                if launch_record.quality_state is QualityState.FRESH
                else launch_record.quality_state
            )
            return self._launch_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=(launch_record,),
                quality_state=no_trade_state,
                reasons=reasons,
                launch_slot=launch_slot,
                launch_timestamp=launch_timestamp,
                early_buyer_count=0,
                data_available=False,
            )

        early_wallets: set[str] = set()
        internal_sniper_wallets: set[str] = set()
        sniper_label_seen = False
        bundle_label_seen = False
        bundle_clusters: set[str] = set()
        cluster_supply: dict[str, Decimal] = {}
        quote_by_unit: dict[str, Decimal] = {}
        supply_values: list[Decimal] = []
        supply_missing = False
        quote_missing = False
        held_by_wallet: dict[str, tuple[datetime, Decimal, QualityState]] = {}
        quality_records: list[_TimedObservation] = [launch_record, *early_records]
        external_conflict = False
        for record in early_records:
            payload = record.observation.normalized_payload
            wallet = _optional_address(
                _field(payload, "wallet_address", "wallet", "buyer", "trader", "maker"),
                "early buyer wallet",
            )
            assert wallet is not None
            early_wallets.add(wallet)
            internal_label = _optional_bool(
                _field(payload, "is_sniper", "sniper", "sniper_label", "internal_sniper"),
                "sniper label",
            )
            external_label = _optional_bool(
                _field(
                    payload,
                    "external_sniper_label",
                    "external_is_sniper",
                    "external_sniper",
                ),
                "external sniper label",
            )
            if internal_label is not None:
                sniper_label_seen = True
                if internal_label:
                    internal_sniper_wallets.add(wallet)
            if (
                external_label is not None
                and internal_label is not None
                and external_label != internal_label
            ):
                external_conflict = True

            cluster_value = _field(
                payload,
                "actor_cluster_id",
                "wallet_cluster_id",
                "controller_wallet",
                "cluster_id",
            )
            cluster = (
                wallet if cluster_value is _MISSING or cluster_value is None else str(cluster_value)
            )
            bundle_value = _field(
                payload,
                "bundle_cluster_id",
                "bundle_id",
                "bundle_actor_cluster",
            )
            bundle_flag = _optional_bool(
                _field(payload, "is_bundle", "bundled", "bundle"),
                "bundle label",
            )
            if bundle_value is not _MISSING and bundle_value is not None:
                bundle_label_seen = True
                bundle_clusters.add(str(bundle_value))
            elif bundle_flag is not None:
                bundle_label_seen = True
                if bundle_flag:
                    bundle_clusters.add(cluster)

            supply = _optional_decimal(
                _field(
                    payload,
                    "acquired_supply_pct",
                    "supply_acquired_pct",
                    "token_supply_pct",
                    "amount_supply_pct",
                ),
                "acquired_supply_pct",
            )
            if supply is None:
                supply_missing = True
            else:
                if supply > 1:
                    raise ValueError("acquired_supply_pct must be between zero and one")
                supply_values.append(supply)
                cluster_supply[cluster] = cluster_supply.get(cluster, Decimal("0")) + supply

            quote = _optional_decimal(
                _field(payload, "quote_amount_usd", "quote_volume_usd", "notional_usd"),
                "early buy quote amount usd",
            )
            unit = "USD"
            if quote is None:
                quote = _optional_decimal(
                    _field(payload, "quote_amount", "quote_volume", "notional"),
                    "early buy quote amount",
                )
                raw_unit = _field(payload, "quote_currency", "quote_unit", "currency")
                unit = (
                    "QUOTE" if raw_unit is _MISSING or raw_unit is None else str(raw_unit).upper()
                )
            if quote is None:
                quote_missing = True
            else:
                quote_by_unit[unit] = quote_by_unit.get(unit, Decimal("0")) + quote

            held = _optional_decimal(
                _field(payload, "current_holdings_pct", "still_held_pct", "still_held_supply_pct"),
                "still_held_pct",
            )
            if held is not None:
                if held > 1:
                    raise ValueError("still_held_pct must be between zero and one")
                prior = held_by_wallet.get(wallet)
                if prior is None or record.event_at >= prior[0]:
                    held_by_wallet[wallet] = (record.event_at, held, record.quality_state)

        for record in scoped:
            if record.observation.kind not in _BALANCE_KINDS:
                continue
            payload = record.observation.normalized_payload
            wallet = _optional_address(
                _field(payload, "wallet_address", "wallet", "owner"),
                "early buyer balance wallet",
            )
            if wallet not in early_wallets:
                continue
            held = _optional_decimal(
                _field(payload, "current_holdings_pct", "holdings_pct", "supply_pct"),
                "early buyer current holdings pct",
            )
            if held is None:
                continue
            if held > 1:
                raise ValueError("current_holdings_pct must be between zero and one")
            prior = held_by_wallet.get(wallet)
            if prior is None or record.event_at >= prior[0]:
                held_by_wallet[wallet] = (record.event_at, held, record.quality_state)
                quality_records.append(record)

        if (
            wallet_missing
            or quote_missing
            or supply_missing
            or len(held_by_wallet) < len(early_wallets)
        ):
            incomplete = True
        if not sniper_label_seen:
            incomplete = True
            reasons.append("SNIPER_EVIDENCE_ABSENT_NOT_CLEAN")
        elif not internal_sniper_wallets:
            reasons.append("SNIPER_EVIDENCE_ABSENT_NOT_CLEAN")
        if not bundle_label_seen:
            incomplete = True
            reasons.append("BUNDLE_EVIDENCE_ABSENT_NOT_CLEAN")
        if external_conflict:
            reasons.append("SNIPER_CLASSIFICATION_CONFLICT")
        if not quote_by_unit:
            quote_acquired = None
            quote_unit = None
        elif len(quote_by_unit) == 1:
            quote_unit, quote_acquired = next(iter(quote_by_unit.items()))
        else:
            quote_acquired = None
            quote_unit = "MIXED"
            incomplete = True
            reasons.append("EARLY_BUYER_QUOTE_UNIT_CONFLICT")
        supply_acquired = None if supply_missing else sum(supply_values, Decimal("0"))
        still_held = None
        if len(held_by_wallet) == len(early_wallets):
            still_held = sum((value[1] for value in held_by_wallet.values()), Decimal("0"))
        concentration = None
        if supply_acquired is not None and supply_acquired > 0:
            concentration = max(cluster_supply.values(), default=Decimal("0")) / supply_acquired
        if supply_acquired is not None and still_held is not None and still_held < supply_acquired:
            reasons.append("EARLY_BUYERS_EXITING")
        if len(internal_sniper_wallets) > 0 and (
            concentration is not None and concentration >= self.policy.high_early_capture_pct
        ):
            reasons.append("SNIPER_FOOTPRINT_HIGH")
        if bundle_clusters:
            reasons.append("BUNDLED_LAUNCH_EVIDENCE")
        state: QualityState = _combined_quality(
            tuple(record.quality_state for record in quality_records)
        )
        if external_conflict:
            state = QualityState.CONFLICTED
        if incomplete and "EARLY_BUYER_DATA_INCOMPLETE" not in reasons:
            reasons.append("EARLY_BUYER_DATA_INCOMPLETE")
        if not reasons:
            reasons.append("EARLY_BUYER_DATA_OBSERVED")
        completeness_values = (
            launch_slot is not None,
            bool(early_wallets) and not wallet_missing,
            quote_acquired is not None,
            supply_acquired is not None,
            sniper_label_seen,
            bundle_label_seen,
            still_held is not None,
        )
        data_completeness = Decimal(sum(completeness_values)) / Decimal(len(completeness_values))
        confidence = data_completeness if state is QualityState.FRESH else Decimal("0")
        return self._launch_snapshot(
            token,
            now=checked_end,
            config_hash=normalized_hash,
            records=quality_records,
            quality_state=state,
            reasons=reasons,
            launch_slot=launch_slot,
            launch_timestamp=launch_timestamp,
            early_buyer_count=len(early_wallets),
            sniper_wallet_count=len(internal_sniper_wallets) if sniper_label_seen else None,
            bundle_actor_cluster_count=len(bundle_clusters) if bundle_label_seen else None,
            quote_acquired=quote_acquired,
            quote_unit=quote_unit,
            supply_acquired_pct=supply_acquired,
            still_held_pct=still_held,
            actor_cluster_adjusted_concentration=concentration,
            data_available=True,
            data_completeness=data_completeness,
            confidence=confidence,
        )

    def _token_lock_snapshot(
        self,
        token: TokenIdentity,
        *,
        now: datetime,
        config_hash: str,
        records: Sequence[_TimedObservation],
        quality_state: QualityState,
        reasons: Sequence[ReasonCode | str],
        asset_scope: LockAssetScope = LockAssetScope.UNKNOWN,
        locker_program: str | None = None,
        lock_present: bool | None = None,
        deposited_amount: Decimal | None = None,
        locked_amount: Decimal | None = None,
        unlocked_amount: Decimal | None = None,
        withdrawn_amount: Decimal | None = None,
        claimable_amount: Decimal | None = None,
        next_unlock_at: datetime | None = None,
        next_unlock_type: str | None = None,
        cancelable_by_sender: bool | None = None,
        scheduled_unlocks: Sequence[tuple[str, Decimal]] = (),
        unlock_events: Sequence[TokenUnlockEvent] = (),
        data_completeness: Decimal = Decimal("0"),
        confidence: Decimal = Decimal("0"),
    ) -> TokenLockSnapshot:
        return TokenLockSnapshot(
            token=token,
            as_of=now,
            expires_at=now + self.policy.evidence_ttl,
            config_hash=config_hash,
            asset_scope=asset_scope,
            locker_program=locker_program,
            lock_present=lock_present,
            deposited_amount=deposited_amount,
            locked_amount=locked_amount,
            unlocked_amount=unlocked_amount,
            withdrawn_amount=withdrawn_amount,
            claimable_amount=claimable_amount,
            next_unlock_at=next_unlock_at,
            next_unlock_type=next_unlock_type,
            cancelable_by_sender=cancelable_by_sender,
            scheduled_unlocks=tuple(scheduled_unlocks),
            unlock_events=tuple(unlock_events),
            data_completeness=data_completeness,
            quality_state=quality_state,
            confidence=confidence,
            provenance=self._provenance(records),
            evidence_refs=self._refs(records),
            reason_codes=tuple(reasons),
            version=self.policy.version,
        )

    def analyze_token_lock(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        *,
        now: datetime,
        config_hash: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> TokenLockSnapshot:
        """Normalize token-lock, vesting and unlock observations at event time."""

        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        checked_end = ensure_utc(now if window_end is None else window_end, "window_end")
        if checked_end > ensure_utc(now, "now"):
            raise ValueError("window_end cannot be in the future")
        start = None if window_start is None else ensure_utc(window_start, "window_start")
        if start is not None and start >= checked_end:
            raise ValueError("window_start must precede window_end")
        normalized_hash = require_text(config_hash, "config_hash")
        records, future, conflict = self._prepare(token, observations, now=checked_end)
        scoped = tuple(record for record in records if start is None or record.event_at >= start)
        if future:
            return self._token_lock_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.INVALID,
                reasons=("HARDENING_FUTURE_EVIDENCE",),
            )
        if conflict:
            return self._token_lock_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.CONFLICTED,
                reasons=("HARDENING_DUPLICATE_CONFLICT",),
            )

        lock_records = tuple(
            record for record in scoped if record.observation.kind.lower() in _LOCK_KINDS
        )
        if not lock_records:
            return self._token_lock_snapshot(
                token,
                now=checked_end,
                config_hash=normalized_hash,
                records=scoped,
                quality_state=QualityState.UNKNOWN,
                reasons=("LOCK_DATA_UNKNOWN",),
            )
        token_records = tuple(
            record
            for record in lock_records
            if _lock_scope(
                _field(
                    record.observation.normalized_payload, "asset_scope", "asset_type", "lock_type"
                ),
                kind=record.observation.kind,
            )
            is LockAssetScope.TOKEN
        )
        lp_records = tuple(
            record
            for record in lock_records
            if _lock_scope(
                _field(
                    record.observation.normalized_payload, "asset_scope", "asset_type", "lock_type"
                ),
                kind=record.observation.kind,
            )
            is LockAssetScope.LP
        )
        unknown_records = tuple(
            record
            for record in lock_records
            if _lock_scope(
                _field(
                    record.observation.normalized_payload, "asset_scope", "asset_type", "lock_type"
                ),
                kind=record.observation.kind,
            )
            is LockAssetScope.UNKNOWN
        )
        asset_scope = (
            LockAssetScope.TOKEN
            if token_records
            else LockAssetScope.LP
            if lp_records
            else LockAssetScope.UNKNOWN
        )
        scoped_records = token_records or lp_records or unknown_records
        latest_values: dict[str, tuple[datetime, Decimal]] = {}
        latest_strings: dict[str, tuple[datetime, str]] = {}
        latest_bools: dict[str, tuple[datetime, bool]] = {}
        future_unlocks: list[tuple[datetime, str]] = []
        schedule_amounts: dict[str, Decimal] = {}
        unlock_events: list[TokenUnlockEvent] = []
        event_unlocked = Decimal("0")
        event_withdrawn = Decimal("0")
        event_claimable = Decimal("0")
        token_lock_observed = False
        token_lock_explicit: bool | None = None

        for record in scoped_records:
            payload = record.observation.normalized_payload
            kind = record.observation.kind.lower()
            scope = _lock_scope(
                _field(payload, "asset_scope", "asset_type", "lock_type"),
                kind=kind,
            )
            if scope is LockAssetScope.TOKEN:
                explicit_present = _optional_bool(
                    _field(payload, "lock_present", "is_locked", "locked"),
                    "lock_present",
                )
                if explicit_present is not None:
                    token_lock_explicit = explicit_present
                    token_lock_observed = True
                event_type_value = _field(
                    payload,
                    "event_type",
                    "unlock_type",
                    "lock_event_type",
                    "action",
                )
                event_type = (
                    "" if event_type_value is _MISSING else str(event_type_value).strip().lower()
                )
                if event_type == "" and kind.endswith("unlock"):
                    event_type = "unlock"
                if event_type in {
                    "lock",
                    "deposit",
                    "vest",
                    "vesting",
                    "snapshot",
                    "create",
                } or any(
                    _field(payload, name) is not _MISSING
                    for name in ("deposited_amount", "locked_amount")
                ):
                    token_lock_observed = True
                locker = _field(payload, "locker_program", "locker", "program_id", "program")
                if locker is not _MISSING and locker is not None:
                    latest_strings["locker_program"] = (record.event_at, str(locker))
                for field_name, aliases in {
                    "deposited_amount": ("deposited_amount", "deposited", "amount_deposited"),
                    "locked_amount": ("locked_amount", "locked", "amount_locked"),
                    "unlocked_amount": ("unlocked_amount", "unlocked", "amount_unlocked"),
                    "withdrawn_amount": ("withdrawn_amount", "withdrawn", "amount_withdrawn"),
                    "claimable_amount": ("claimable_amount", "claimable", "amount_claimable"),
                }.items():
                    value = _optional_decimal(_field(payload, *aliases), field_name)
                    if value is not None:
                        latest_values[field_name] = (record.event_at, value)
                amount = _optional_decimal(
                    _field(payload, "amount", "unlock_amount", "token_amount"),
                    "unlock amount",
                )
                if event_type in {"unlock", "unlocked", "release", "released", "tranche"}:
                    if (
                        amount is not None
                        and _field(payload, "unlocked_amount", "unlocked", "amount_unlocked")
                        is _MISSING
                    ):
                        event_unlocked += amount
                elif event_type in {"withdraw", "withdrawn"}:
                    if (
                        amount is not None
                        and _field(payload, "withdrawn_amount", "withdrawn", "amount_withdrawn")
                        is _MISSING
                    ):
                        event_withdrawn += amount
                elif event_type in {"claim", "claimed"} and (
                    amount is not None
                    and _field(payload, "claimable_amount", "claimable", "amount_claimable")
                    is _MISSING
                ):
                    event_claimable += amount
                unlock_at = _optional_datetime(
                    _field(payload, "next_unlock_at", "unlock_at", "scheduled_at"),
                    "unlock_at",
                )
                if unlock_at is not None:
                    unlock_type_value = _field(payload, "unlock_type", "event_type")
                    unlock_type = (
                        "TRANCHE" if unlock_type_value is _MISSING else str(unlock_type_value)
                    )
                    if unlock_at >= checked_end:
                        future_unlocks.append((unlock_at, unlock_type.upper()))
                cancelable = _optional_bool(
                    _field(
                        payload,
                        "cancelable_by_sender",
                        "cancelable",
                        "cancellable_by_sender",
                    ),
                    "cancelable_by_sender",
                )
                if cancelable is not None:
                    latest_bools["cancelable_by_sender"] = (record.event_at, cancelable)
                schedule = _field(payload, "scheduled_unlocks", "unlock_schedule", "schedule")
                if isinstance(schedule, Mapping):
                    for horizon, raw_amount in schedule.items():
                        value = raw_amount
                        if isinstance(raw_amount, Mapping):
                            value = raw_amount.get("amount", _MISSING)
                        amount_value = _optional_decimal(value, f"scheduled unlock {horizon}")
                        if amount_value is not None:
                            name = require_text(str(horizon), "unlock horizon", max_length=32)
                            schedule_amounts[name] = (
                                schedule_amounts.get(name, Decimal("0")) + amount_value
                            )
                elif isinstance(schedule, Sequence) and not isinstance(
                    schedule, str | bytes | bytearray
                ):
                    for item in schedule:
                        if not isinstance(item, Mapping):
                            raise TypeError("unlock schedule entries must be mappings")
                        item_at = _optional_datetime(
                            item.get("unlock_at", item.get("at", _MISSING)),
                            "scheduled unlock at",
                        )
                        item_amount = _optional_decimal(
                            item.get("amount", _MISSING),
                            "scheduled unlock amount",
                        )
                        if item_at is None or item_amount is None or item_at < checked_end:
                            continue
                        for horizon, duration in self.policy.unlock_horizons:
                            if item_at <= checked_end + duration:
                                schedule_amounts[horizon] = (
                                    schedule_amounts.get(horizon, Decimal("0")) + item_amount
                                )
                if (
                    event_type in {"unlock", "unlocked", "release", "released", "tranche"}
                    and amount is not None
                ):
                    unlock_at_for_event = (
                        _optional_datetime(
                            _field(payload, "unlock_at", "scheduled_at"),
                            "unlock_at",
                        )
                        or record.event_at
                    )
                    unlock_events.append(
                        TokenUnlockEvent(
                            token=token,
                            as_of=record.event_at,
                            expires_at=record.event_at + self.policy.evidence_ttl,
                            config_hash=normalized_hash,
                            unlock_at=unlock_at_for_event,
                            amount=amount,
                            unlock_type=(
                                "TRANCHE"
                                if _field(
                                    payload,
                                    "unlock_type",
                                    "lock_event_type",
                                    "event_type",
                                )
                                is _MISSING
                                else str(
                                    _field(
                                        payload,
                                        "unlock_type",
                                        "lock_event_type",
                                        "event_type",
                                    )
                                )
                            ),
                            asset_scope=LockAssetScope.TOKEN,
                            locker_program=None
                            if locker is _MISSING or locker is None
                            else str(locker),
                            cancelable_by_sender=cancelable,
                            quality_state=record.quality_state,
                            provenance=(record.observation.provenance,),
                            evidence_refs=(
                                f"{record.observation.provenance.provider}:{record.observation.provenance.source_id}",
                            ),
                            reason_codes=("VESTING_SCHEDULE_PRESENT",),
                            version=self.policy.version,
                        )
                    )

        def latest_decimal(name: str) -> Decimal | None:
            value = latest_values.get(name)
            return None if value is None else value[1]

        def latest_string(name: str) -> str | None:
            value = latest_strings.get(name)
            return None if value is None else value[1]

        def latest_bool(name: str) -> bool | None:
            value = latest_bools.get(name)
            return None if value is None else value[1]

        deposited_amount = latest_decimal("deposited_amount")
        locked_amount = latest_decimal("locked_amount")
        unlocked_amount = latest_decimal("unlocked_amount")
        if unlocked_amount is None and event_unlocked > 0:
            unlocked_amount = event_unlocked
        withdrawn_amount = latest_decimal("withdrawn_amount")
        if withdrawn_amount is None and event_withdrawn > 0:
            withdrawn_amount = event_withdrawn
        claimable_amount = latest_decimal("claimable_amount")
        if claimable_amount is None and event_claimable > 0:
            claimable_amount = event_claimable
        next_unlock = min(future_unlocks, default=None)
        next_unlock_at = None if next_unlock is None else next_unlock[0]
        next_unlock_type = None if next_unlock is None else next_unlock[1]
        if token_lock_explicit is not None:
            lock_present = token_lock_explicit if token_records else None
        elif token_records and token_lock_observed:
            lock_present = True
        else:
            lock_present = True if lp_records and not token_records else None
        reasons: list[ReasonCode | str] = []
        if lp_records:
            reasons.append("LP_LOCK_SEPARATE_FROM_TOKEN_LOCK")
        if not token_records or lock_present is None:
            reasons.append("TOKEN_LOCK_DATA_UNKNOWN")
        if unknown_records:
            reasons.append("LOCK_DATA_UNKNOWN")
        if not any(
            value is not None
            for value in (
                deposited_amount,
                locked_amount,
                unlocked_amount,
                withdrawn_amount,
                claimable_amount,
            )
        ):
            reasons.append("LOCK_DATA_UNKNOWN")
        if schedule_amounts or unlock_events:
            reasons.append("VESTING_SCHEDULE_PRESENT")
        if latest_bool("cancelable_by_sender") is True:
            reasons.append("LOCK_CANCELABLE_BY_SENDER")
        first_horizon_name = self.policy.unlock_horizons[0][0]
        first_horizon_amount = schedule_amounts.get(first_horizon_name)
        lock_base = locked_amount or deposited_amount
        if (
            first_horizon_amount is not None
            and lock_base is not None
            and lock_base > 0
            and first_horizon_amount / lock_base >= self.policy.large_unlock_ratio
        ):
            reasons.append("LARGE_UNLOCK_IMMINENT")
        if not reasons:
            reasons.append("LOCK_EVIDENCE_OBSERVED")
        scope_known = asset_scope is not LockAssetScope.UNKNOWN
        amount_known = any(
            value is not None
            for value in (
                deposited_amount,
                locked_amount,
                unlocked_amount,
                withdrawn_amount,
                claimable_amount,
            )
        )
        data_completeness_values = (
            scope_known,
            amount_known,
            next_unlock_at is not None or bool(schedule_amounts),
            latest_bool("cancelable_by_sender") is not None,
            bool(token_records),
        )
        data_completeness = Decimal(sum(data_completeness_values)) / Decimal(
            len(data_completeness_values)
        )
        state = _combined_quality(tuple(record.quality_state for record in lock_records))
        confidence = data_completeness if state is QualityState.FRESH else Decimal("0")
        return self._token_lock_snapshot(
            token,
            now=checked_end,
            config_hash=normalized_hash,
            records=lock_records,
            quality_state=state,
            reasons=reasons,
            asset_scope=asset_scope,
            locker_program=latest_string("locker_program"),
            lock_present=lock_present,
            deposited_amount=deposited_amount,
            locked_amount=locked_amount,
            unlocked_amount=unlocked_amount,
            withdrawn_amount=withdrawn_amount,
            claimable_amount=claimable_amount,
            next_unlock_at=next_unlock_at,
            next_unlock_type=next_unlock_type,
            cancelable_by_sender=latest_bool("cancelable_by_sender"),
            scheduled_unlocks=tuple(schedule_amounts.items()),
            unlock_events=unlock_events,
            data_completeness=data_completeness,
            confidence=confidence,
        )


__all__ = [
    "DEFAULT_SIGNAL_EVIDENCE_TTL",
    "MomentumRegimeKind",
    "MomentumRegimeSnapshot",
    "MoveFundingEvidence",
    "DeployerActivitySnapshot",
    "LaunchFootprintSnapshot",
    "LockAssetScope",
    "SIGNAL_HARDENING_VERSION",
    "SignalHardeningAnalyzer",
    "SignalHardeningPolicy",
    "TokenLockSnapshot",
    "TokenUnlockEvent",
]
