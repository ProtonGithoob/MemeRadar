"""Provider-independent tracked-wallet activity and FIFO reconstruction."""

from __future__ import annotations

from collections import deque
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
    ReasonCode,
    TokenIdentity,
    require_solana_address,
)
from memeradar_domain.common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    ensure_utc,
    normalize_texts,
    require_text,
    to_decimal,
)
from memeradar_domain.events import normalize_reason_codes

_MISSING = object()
_ACTIVITY_KINDS = frozenset(
    {
        "wallet.activity",
        "wallet.trade",
        "wallet.swap",
        "onchain.wallet_activity",
        "onchain.swap",
        "market.trade",
    }
)
_RUG_KINDS = frozenset({"risk.rug_event", "risk.token_outcome"})
_QUALITY_PRIORITY = {
    QualityState.FRESH: 0,
    QualityState.STALE: 1,
    QualityState.UNKNOWN: 2,
    QualityState.CONFLICTED: 3,
    QualityState.INVALID: 4,
}


def _field(payload: Mapping[str, object], *names: str) -> object:
    for name in names:
        value = payload.get(name, _MISSING)
        if value is not _MISSING:
            return value
    return _MISSING


def _append_unique(target: list[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _append_provenance(target: list[Provenance], value: Provenance) -> None:
    if value not in target:
        target.append(value)


def _combined_quality(states: Sequence[QualityState]) -> QualityState:
    if not states:
        return QualityState.UNKNOWN
    return max(states, key=lambda state: _QUALITY_PRIORITY[state])


def _quality_at(observation: Observation, now: datetime, ttl: timedelta) -> QualityState:
    if observation.quality_state is not QualityState.FRESH:
        return observation.quality_state
    if observation.observed_at > now:
        return QualityState.INVALID
    if now >= observation.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _activity_quality_at(activity: WalletActivity, now: datetime, ttl: timedelta) -> QualityState:
    if activity.quality_state is not QualityState.FRESH:
        return activity.quality_state
    if activity.observed_at > now:
        return QualityState.INVALID
    if now >= activity.observed_at + ttl:
        return QualityState.STALE
    return QualityState.FRESH


def _optional_decimal(
    value: object,
    field: str,
    *,
    positive: bool = False,
) -> Decimal | None:
    if value is _MISSING or value is None:
        return None
    parsed = to_decimal(value, field)
    if parsed < 0 or (positive and parsed <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field} must be {qualifier}")
    return parsed


def _observation_matches(observation: Observation, token: TokenIdentity) -> bool:
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


class WalletTier(str, Enum):
    """Explicit operator/configuration tiers; analysis never promotes them."""

    WATCH = "WATCH"
    CANDIDATE = "CANDIDATE"
    TIER_A = "TIER_A"
    TIER_B = "TIER_B"
    BLOCKED = "BLOCKED"
    A = "TIER_A"
    B = "TIER_B"


@dataclass(frozen=True, slots=True)
class TrackedWallet:
    """A bounded, explicitly configured wallet entry."""

    address: str
    label: str = "unlabeled"
    tier: WalletTier | str = WalletTier.WATCH
    first_seen_at: datetime | None = None
    active: bool = True
    evidence_refs: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", require_solana_address(self.address, "wallet address"))
        object.__setattr__(self, "label", require_text(self.label, "wallet label", max_length=128))
        object.__setattr__(self, "tier", WalletTier(self.tier))
        if self.first_seen_at is not None:
            object.__setattr__(
                self,
                "first_seen_at",
                ensure_utc(self.first_seen_at, "first_seen_at"),
            )
        if not isinstance(self.active, bool):
            raise TypeError("active must be a boolean")
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        normalized_labels = normalize_texts(self.labels, "labels", max_item_length=128)
        if not normalized_labels:
            normalized_labels = (self.label,)
        object.__setattr__(self, "labels", normalized_labels)


class TrackedWalletRegistry:
    """Idempotent registry for explicitly watched wallets."""

    def __init__(
        self,
        *,
        max_wallets: int = 1000,
        wallets: Sequence[TrackedWallet] = (),
    ) -> None:
        if (
            not isinstance(max_wallets, int)
            or isinstance(max_wallets, bool)
            or max_wallets < 1
        ):
            raise ValueError("max_wallets must be a positive integer")
        if max_wallets > 10_000:
            raise ValueError("max_wallets exceeds the configured bound")
        if isinstance(wallets, str | bytes | bytearray):
            raise TypeError("wallets must be a sequence")
        self.max_wallets = max_wallets
        self._wallets: dict[str, TrackedWallet] = {}
        for wallet in wallets:
            self.register(wallet)

    def register(self, wallet: TrackedWallet) -> TrackedWallet:
        if not isinstance(wallet, TrackedWallet):
            raise TypeError("wallet must be a TrackedWallet")
        existing = self._wallets.get(wallet.address)
        if existing is not None:
            if existing != wallet:
                raise ValueError(f"conflicting registry entry for wallet {wallet.address}")
            return existing
        if len(self._wallets) >= self.max_wallets:
            raise ValueError("tracked-wallet registry exceeded bound")
        self._wallets[wallet.address] = wallet
        return wallet

    def get(self, address: str) -> TrackedWallet | None:
        return self._wallets.get(require_solana_address(address, "wallet address"))

    def require(self, address: str) -> TrackedWallet:
        normalized = require_solana_address(address, "wallet address")
        wallet = self._wallets.get(normalized)
        if wallet is None:
            raise KeyError(f"unknown wallet: {normalized}")
        return wallet

    def require_active(self, address: str) -> TrackedWallet:
        wallet = self.require(address)
        if not wallet.active or wallet.tier is WalletTier.BLOCKED:
            raise ValueError(f"wallet is not active or is blocked: {wallet.address}")
        return wallet

    @property
    def entries(self) -> tuple[TrackedWallet, ...]:
        return tuple(self._wallets.values())

    @property
    def wallets(self) -> tuple[TrackedWallet, ...]:
        return self.entries

    @property
    def active_wallets(self) -> tuple[TrackedWallet, ...]:
        return tuple(
            wallet
            for wallet in self._wallets.values()
            if wallet.active and wallet.tier is not WalletTier.BLOCKED
        )

    def __len__(self) -> int:
        return len(self._wallets)


class WalletAction(str, Enum):
    """Supported position-changing wallet activity."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class WalletActivity:
    """Normalized wallet trade evidence with source timestamps intact."""

    token: TokenIdentity
    wallet_address: str
    action: WalletAction | str
    quantity: Decimal
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    provenance: Provenance
    quote_amount: Decimal | None = None
    price: Decimal | None = None
    quality_state: QualityState = QualityState.FRESH
    evidence_refs: tuple[str, ...] = ()
    price_semantics: PriceSemantics | str = PriceSemantics.EXECUTION_EFFECTIVE
    market_price: Decimal | None = None
    price_source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(
            self,
            "wallet_address",
            require_solana_address(self.wallet_address, "wallet address"),
        )
        object.__setattr__(self, "action", WalletAction(self.action))
        quantity = to_decimal(self.quantity, "quantity")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(
            self,
            "quote_amount",
            _optional_decimal(self.quote_amount, "quote_amount"),
        )
        object.__setattr__(self, "price", _optional_decimal(self.price, "price", positive=True))
        semantics = PriceSemantics(self.price_semantics)
        if semantics is PriceSemantics.MARKET_REFERENCE:
            raise ValueError("wallet activity price must be execution evidence")
        object.__setattr__(self, "price_semantics", semantics)
        object.__setattr__(
            self,
            "market_price",
            _optional_decimal(self.market_price, "market_price", positive=True),
        )
        occurred, observed, ingested = ensure_ordered_timestamps(
            self.occurred_at,
            self.observed_at,
            self.ingested_at,
        )
        if occurred is None:
            raise ValueError("occurred_at is required for wallet activity")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "ingested_at", ingested)
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if self.provenance.observed_at > observed:
            raise ValueError("provenance observed_at must not be later than observed_at")
        object.__setattr__(self, "quality_state", QualityState(self.quality_state))
        object.__setattr__(
            self,
            "evidence_refs",
            normalize_texts(self.evidence_refs, "evidence_refs"),
        )
        if self.price_source is not None:
            object.__setattr__(
                self,
                "price_source",
                require_text(self.price_source, "price_source", max_length=128),
            )

    @property
    def source_id(self) -> str:
        return self.provenance.source_id

    @property
    def wallet(self) -> str:
        return self.wallet_address

    @property
    def effective_price(self) -> Decimal | None:
        if self.price is not None:
            return self.price
        if self.quote_amount is None:
            return None
        return self.quote_amount / self.quantity

    @property
    def execution_price(self) -> Decimal | None:
        """Explicit alias for the price used by wallet cost/PnL evidence."""

        return self.effective_price

    @property
    def market_reference_price(self) -> Decimal | None:
        """Optional independent mark; it is not inferred from the trade."""

        return self.market_price


@dataclass(frozen=True, slots=True)
class WalletRoundTrip:
    """One FIFO-matched buy lot slice and sell slice."""

    token: TokenIdentity
    wallet_address: str
    quantity: Decimal
    buy_at: datetime
    sell_at: datetime
    cost_basis: Decimal | None
    proceeds: Decimal | None
    realized_pnl: Decimal | None
    hold_seconds: Decimal
    token_age_at_entry_seconds: Decimal | None
    rug_exposure: bool | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(
            self,
            "wallet_address",
            require_solana_address(self.wallet_address, "wallet address"),
        )
        quantity = to_decimal(self.quantity, "round-trip quantity")
        if quantity <= 0:
            raise ValueError("round-trip quantity must be positive")
        object.__setattr__(self, "quantity", quantity)
        buy_at = ensure_utc(self.buy_at, "buy_at")
        sell_at = ensure_utc(self.sell_at, "sell_at")
        if sell_at < buy_at:
            raise ValueError("sell_at must not precede buy_at")
        object.__setattr__(self, "buy_at", buy_at)
        object.__setattr__(self, "sell_at", sell_at)
        for field_name in ("cost_basis", "proceeds"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _optional_decimal(value, field_name))
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        hold_seconds = to_decimal(self.hold_seconds, "hold_seconds")
        if hold_seconds < 0:
            raise ValueError("hold_seconds must not be negative")
        object.__setattr__(self, "hold_seconds", hold_seconds)
        if self.token_age_at_entry_seconds is not None:
            age = to_decimal(self.token_age_at_entry_seconds, "token_age_at_entry_seconds")
            if age < 0:
                raise ValueError("token age must not be negative")
            object.__setattr__(self, "token_age_at_entry_seconds", age)
        if self.rug_exposure is not None and not isinstance(self.rug_exposure, bool):
            raise TypeError("rug_exposure must be a boolean or None")
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

    @property
    def hold_duration(self) -> timedelta:
        return timedelta(seconds=float(self.hold_seconds))


@dataclass(frozen=True, slots=True)
class WalletTrackingPolicy:
    """Bounds and freshness policy for normalized wallet reconstruction."""

    evidence_ttl: timedelta = timedelta(minutes=5)
    max_wallets: int = 1000
    max_activities: int = 5000
    max_lots: int = 5000
    version: str = "wallet-tracking-v1"

    def __post_init__(self) -> None:
        if self.evidence_ttl <= timedelta(0):
            raise ValueError("evidence_ttl must be positive")
        for field_name, maximum in (
            ("max_wallets", 10_000),
            ("max_activities", 50_000),
            ("max_lots", 50_000),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")
            if value > maximum:
                raise ValueError(f"{field_name} exceeds the configured bound")
        object.__setattr__(self, "version", require_text(self.version, "version", max_length=64))


@dataclass(frozen=True, slots=True)
class WalletTrackingSnapshot:
    """Explainable wallet/token position reconstruction, never an execution signal."""

    token: TokenIdentity
    wallet_address: str
    label: str
    tier: WalletTier | str
    as_of: datetime
    expires_at: datetime
    buy_count: int
    sell_count: int
    matched_sell_count: int
    open_quantity: Decimal
    open_cost_basis: Decimal | None
    unmatched_sell_quantity: Decimal
    realized_pnl: Decimal | None
    round_trips: tuple[WalletRoundTrip, ...]
    first_entry_at: datetime | None
    token_age_at_first_entry_seconds: Decimal | None
    median_hold_seconds: Decimal | None
    rug_exposure: bool | None
    provenance: tuple[Provenance, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[ReasonCode | str, ...]
    confidence: Decimal
    config_hash: str
    quality_state: QualityState = QualityState.UNKNOWN
    version: str = "wallet-tracking-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        object.__setattr__(
            self,
            "wallet_address",
            require_solana_address(self.wallet_address, "wallet address"),
        )
        object.__setattr__(self, "label", require_text(self.label, "wallet label", max_length=128))
        object.__setattr__(self, "tier", WalletTier(self.tier))
        as_of = ensure_utc(self.as_of, "as_of")
        expires_at = ensure_utc(self.expires_at, "expires_at")
        if expires_at <= as_of:
            raise ValueError("expires_at must be later than as_of")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "expires_at", expires_at)
        for field_name in (
            "buy_count",
            "sell_count",
            "matched_sell_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.matched_sell_count > self.sell_count:
            raise ValueError("matched_sell_count cannot exceed sell_count")
        for field_name in ("open_quantity", "unmatched_sell_quantity"):
            value = to_decimal(getattr(self, field_name), field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)
        if self.open_cost_basis is not None:
            object.__setattr__(
                self,
                "open_cost_basis",
                _optional_decimal(self.open_cost_basis, "open_cost_basis"),
            )
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", to_decimal(self.realized_pnl, "realized_pnl"))
        round_trips = tuple(self.round_trips)
        if any(not isinstance(value, WalletRoundTrip) for value in round_trips):
            raise TypeError("round_trips must contain WalletRoundTrip values")
        object.__setattr__(self, "round_trips", round_trips)
        if self.first_entry_at is not None:
            object.__setattr__(
                self,
                "first_entry_at",
                ensure_utc(self.first_entry_at, "first_entry_at"),
            )
        if self.token_age_at_first_entry_seconds is not None:
            age = to_decimal(
                self.token_age_at_first_entry_seconds,
                "token_age_at_first_entry_seconds",
            )
            if age < 0:
                raise ValueError("token age must not be negative")
            object.__setattr__(self, "token_age_at_first_entry_seconds", age)
        if self.median_hold_seconds is not None:
            hold = to_decimal(self.median_hold_seconds, "median_hold_seconds")
            if hold < 0:
                raise ValueError("median hold must not be negative")
            object.__setattr__(self, "median_hold_seconds", hold)
        if self.rug_exposure is not None and not isinstance(self.rug_exposure, bool):
            raise TypeError("rug_exposure must be a boolean or None")
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
    def wallet(self) -> str:
        return self.wallet_address

    @property
    def sample_count(self) -> int:
        return self.buy_count + self.sell_count

    @property
    def wallet_tier(self) -> WalletTier:
        return WalletTier(self.tier)

    def execution_eligible(self, at: datetime) -> bool:
        """Wallet intelligence is advisory and never authorizes execution."""

        del at
        return False


@dataclass(slots=True)
class _Lot:
    quantity: Decimal
    unit_cost: Decimal | None
    buy: WalletActivity


def _parse_action(value: object) -> WalletAction:
    if not isinstance(value, str):
        raise ValueError("wallet activity action must be a string")
    normalized = value.strip().lower()
    if normalized in {"buy", "bought", "bid", "purchase"}:
        return WalletAction.BUY
    if normalized in {"sell", "sold", "ask", "sale"}:
        return WalletAction.SELL
    raise ValueError("wallet activity action must be BUY or SELL")


def _parse_address(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("wallet address is required")
    try:
        return require_solana_address(value, "wallet address")
    except (TypeError, ValueError) as exc:
        raise ValueError("wallet address must be canonical") from exc


class WalletTrackingAnalyzer:
    """Normalize watched-wallet observations and reconstruct FIFO positions."""

    def __init__(self, *, policy: WalletTrackingPolicy | None = None) -> None:
        self.policy = policy or WalletTrackingPolicy()

    def ingest_activities(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
        registry: TrackedWalletRegistry,
        *,
        now: datetime,
    ) -> tuple[WalletActivity, ...]:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if not isinstance(registry, TrackedWalletRegistry):
            raise TypeError("registry must be a TrackedWalletRegistry")
        if len(registry) > self.policy.max_wallets:
            raise ValueError("tracked-wallet registry exceeded policy bound")
        checked_at = ensure_utc(now, "now")
        if isinstance(observations, str | bytes | bytearray):
            raise TypeError("observations must be a sequence")
        matched: list[WalletActivity] = []
        seen: dict[str, WalletActivity] = {}
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation values")
            if observation.kind not in _ACTIVITY_KINDS or not _observation_matches(
                observation, token
            ):
                continue
            activity = self._normalize_activity(token, observation, registry, checked_at)
            prior = seen.get(activity.source_id)
            if prior is not None:
                if prior != activity:
                    raise ValueError(f"conflicting wallet activity source {activity.source_id}")
                continue
            seen[activity.source_id] = activity
            matched.append(activity)
            if len(matched) > self.policy.max_activities:
                raise ValueError("wallet activities exceeded the configured bound")
        return tuple(sorted(matched, key=lambda item: (item.occurred_at, item.source_id)))

    def _normalize_activity(
        self,
        token: TokenIdentity,
        observation: Observation,
        registry: TrackedWalletRegistry,
        now: datetime,
    ) -> WalletActivity:
        payload = observation.normalized_payload
        address = _parse_address(
            _field(payload, "wallet_address", "wallet", "trader", "maker", "owner", "user")
        )
        try:
            registry.require_active(address)
        except KeyError as exc:
            raise ValueError(f"wallet is not registered: {address}") from exc
        if observation.occurred_at is None:
            raise ValueError("wallet activity occurred_at is required")
        action = _parse_action(_field(payload, "action", "side", "type"))
        quantity = _optional_decimal(
            _field(payload, "quantity", "base_amount", "baseAmount", "amount", "token_amount"),
            "quantity",
            positive=True,
        )
        if quantity is None:
            raise ValueError("wallet activity quantity is required")
        quote_amount = _optional_decimal(
            _field(
                payload,
                "quote_amount",
                "quoteAmount",
                "quote_value",
                "quoteValue",
                "notional",
                "sol_amount",
            ),
            "quote_amount",
        )
        price = _optional_decimal(
            _field(payload, "price", "effective_price", "unit_price", "unitPrice"),
            "price",
            positive=True,
        )
        quality_state = _quality_at(observation, now, self.policy.evidence_ttl)
        return WalletActivity(
            token=token,
            wallet_address=address,
            action=action,
            quantity=quantity,
            quote_amount=quote_amount,
            price=price,
            occurred_at=observation.occurred_at,
            observed_at=observation.observed_at,
            ingested_at=observation.ingested_at,
            provenance=observation.provenance,
            quality_state=quality_state,
            evidence_refs=(observation.provenance.source_id,),
        )

    def reconstruct_positions(
        self,
        token: TokenIdentity,
        activities: Sequence[WalletActivity],
        registry: TrackedWalletRegistry,
        *,
        now: datetime,
        config_hash: str,
        token_created_at: datetime | None = None,
        rug_observations: Sequence[Observation] = (),
    ) -> tuple[WalletTrackingSnapshot, ...]:
        if not isinstance(token, TokenIdentity):
            raise TypeError("token must be a TokenIdentity")
        if not isinstance(registry, TrackedWalletRegistry):
            raise TypeError("registry must be a TrackedWalletRegistry")
        if len(registry) > self.policy.max_wallets:
            raise ValueError("tracked-wallet registry exceeded policy bound")
        checked_at = ensure_utc(now, "now")
        normalized_config_hash = require_text(config_hash, "config_hash")
        if isinstance(activities, str | bytes | bytearray):
            raise TypeError("activities must be a sequence")
        if len(activities) > self.policy.max_activities:
            raise ValueError("wallet activities exceeded the configured bound")
        normalized_creation = (
            None if token_created_at is None else ensure_utc(token_created_at, "token_created_at")
        )
        if isinstance(rug_observations, str | bytes | bytearray):
            raise TypeError("rug_observations must be a sequence")
        matched_rug = self._matching_rug_observations(token, rug_observations)
        by_wallet: dict[str, list[WalletActivity]] = {
            wallet.address: [] for wallet in registry.active_wallets
        }
        seen: dict[str, WalletActivity] = {}
        for activity in activities:
            if not isinstance(activity, WalletActivity):
                raise TypeError("activities must contain WalletActivity values")
            if activity.token != token:
                raise ValueError("wallet activity token does not match reconstruction token")
            registry.require_active(activity.wallet_address)
            prior = seen.get(activity.source_id)
            if prior is not None and prior != activity:
                raise ValueError(f"conflicting wallet activity source {activity.source_id}")
            if prior is None:
                seen[activity.source_id] = activity
                by_wallet[activity.wallet_address].append(activity)
        return tuple(
            self._snapshot_for_wallet(
                token,
                registry.require(wallet_address),
                wallet_activities,
                matched_rug,
                checked_at=checked_at,
                config_hash=normalized_config_hash,
                token_created_at=normalized_creation,
            )
            for wallet_address, wallet_activities in by_wallet.items()
        )

    def _matching_rug_observations(
        self,
        token: TokenIdentity,
        observations: Sequence[Observation],
    ) -> tuple[Observation, ...]:
        matched: list[Observation] = []
        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("rug_observations must contain Observation values")
            if observation.kind in _RUG_KINDS and _observation_matches(observation, token):
                matched.append(observation)
        if len(matched) > self.policy.max_activities:
            raise ValueError("rug observations exceeded the configured bound")
        return tuple(matched)

    def _snapshot_for_wallet(
        self,
        token: TokenIdentity,
        wallet: TrackedWallet,
        activities: Sequence[WalletActivity],
        rug_observations: Sequence[Observation],
        *,
        checked_at: datetime,
        config_hash: str,
        token_created_at: datetime | None,
    ) -> WalletTrackingSnapshot:
        ordered = tuple(
            sorted(
                activities,
                key=lambda item: (item.occurred_at, item.observed_at, item.source_id),
            )
        )
        evidence_refs = list(wallet.evidence_refs)
        provenance: list[Provenance] = []
        for activity in ordered:
            _append_unique(evidence_refs, (activity.source_id, *activity.evidence_refs))
            _append_provenance(provenance, activity.provenance)
        for observation in rug_observations:
            _append_unique(evidence_refs, (observation.provenance.source_id,))
            _append_provenance(provenance, observation.provenance)

        rug_state, rug_exposure, rug_reasons = self._rug_evidence(
            rug_observations,
            now=checked_at,
            first_entry_at=ordered[0].occurred_at if ordered else None,
        )
        lots: deque[_Lot] = deque()
        round_trips: list[WalletRoundTrip] = []
        activity_states: list[QualityState] = []
        buy_count = 0
        sell_count = 0
        matched_sell_count = 0
        unmatched_sell_quantity = Decimal("0")
        financial_incomplete = False
        first_entry_at: datetime | None = None

        for activity in ordered:
            state = _activity_quality_at(activity, checked_at, self.policy.evidence_ttl)
            activity_states.append(state)
            if activity.action is WalletAction.BUY:
                buy_count += 1
                first_entry_at = (
                    activity.occurred_at
                    if first_entry_at is None
                    else min(first_entry_at, activity.occurred_at)
                )
                if len(lots) >= self.policy.max_lots:
                    raise ValueError("wallet open lots exceeded the configured bound")
                unit_cost = activity.effective_price
                lots.append(_Lot(activity.quantity, unit_cost, activity))
                if unit_cost is None:
                    financial_incomplete = True
                continue

            sell_count += 1
            remaining = activity.quantity
            sell_unit_price = activity.effective_price
            if sell_unit_price is None:
                financial_incomplete = True
            matched_any = False
            while remaining > 0 and lots:
                lot = lots[0]
                matched_quantity = min(remaining, lot.quantity)
                matched_any = True
                cost_basis = (
                    None if lot.unit_cost is None else lot.unit_cost * matched_quantity
                )
                proceeds = (
                    None if sell_unit_price is None else sell_unit_price * matched_quantity
                )
                realized_pnl = (
                    None
                    if cost_basis is None or proceeds is None
                    else proceeds - cost_basis
                )
                token_age = self._token_age(token_created_at, lot.buy.occurred_at)
                trip_reasons: list[str | ReasonCode] = ["FIFO_MATCHED"]
                if realized_pnl is None:
                    trip_reasons.append("REALIZED_PNL_UNKNOWN")
                else:
                    trip_reasons.append("REALIZED_PNL_CALCULATED")
                if token_age is None:
                    trip_reasons.append("TOKEN_AGE_UNKNOWN")
                if rug_exposure is None:
                    trip_reasons.append("RUG_EXPOSURE_UNKNOWN")
                elif rug_exposure:
                    trip_reasons.append("RUG_EXPOSURE_DETECTED")
                trip_evidence = list(lot.buy.evidence_refs)
                _append_unique(trip_evidence, (activity.source_id, *activity.evidence_refs))
                trip_provenance: list[Provenance] = [lot.buy.provenance]
                _append_provenance(trip_provenance, activity.provenance)
                round_trips.append(
                    WalletRoundTrip(
                        token=token,
                        wallet_address=wallet.address,
                        quantity=matched_quantity,
                        buy_at=lot.buy.occurred_at,
                        sell_at=activity.occurred_at,
                        cost_basis=cost_basis,
                        proceeds=proceeds,
                        realized_pnl=realized_pnl,
                        hold_seconds=Decimal(
                            str((activity.occurred_at - lot.buy.occurred_at).total_seconds())
                        ),
                        token_age_at_entry_seconds=token_age,
                        rug_exposure=rug_exposure,
                        provenance=tuple(trip_provenance),
                        evidence_refs=tuple(trip_evidence),
                        reason_codes=tuple(trip_reasons),
                    )
                )
                if realized_pnl is None:
                    financial_incomplete = True
                remaining -= matched_quantity
                lot.quantity -= matched_quantity
                if lot.quantity == 0:
                    lots.popleft()
                else:
                    lots[0] = lot
            if matched_any:
                matched_sell_count += 1
            if remaining > 0:
                unmatched_sell_quantity += remaining
                financial_incomplete = True

        open_quantity = sum((lot.quantity for lot in lots), Decimal("0"))
        if not lots:
            open_cost_basis: Decimal | None = Decimal("0")
        elif any(lot.unit_cost is None for lot in lots):
            open_cost_basis = None
        else:
            open_cost_basis = sum(
                (lot.quantity * lot.unit_cost for lot in lots if lot.unit_cost is not None),
                Decimal("0"),
            )
        known_pnl = [trip.realized_pnl for trip in round_trips]
        realized_pnl = (
            None
            if not known_pnl or financial_incomplete or any(value is None for value in known_pnl)
            else sum((value for value in known_pnl if value is not None), Decimal("0"))
        )
        hold_values = sorted(trip.hold_seconds for trip in round_trips)
        median_hold = self._median(hold_values)
        token_age = self._token_age(token_created_at, first_entry_at)
        token_age_state = self._token_age_state(token_created_at, ordered, checked_at)

        reasons: list[str | ReasonCode] = ["WALLET_TIER_EXPLICIT"]
        if not ordered:
            reasons.append("WALLET_ACTIVITY_MISSING")
        else:
            reasons.append("WALLET_ACTIVITY_RECONSTRUCTED")
        if round_trips:
            reasons.append("FIFO_MATCHED")
        if realized_pnl is not None:
            reasons.append("REALIZED_PNL_CALCULATED")
        elif round_trips:
            reasons.append("REALIZED_PNL_INCOMPLETE")
        if unmatched_sell_quantity > 0:
            reasons.append("UNMATCHED_SELL")
        if token_age is None:
            reasons.append("TOKEN_AGE_EVIDENCE_MISSING")
        else:
            reasons.append("TOKEN_AGE_TRACKED")
        reasons.extend(rug_reasons)

        quality_state = _combined_quality(
            [*activity_states, rug_state, token_age_state]
            + ([QualityState.UNKNOWN] if not ordered else [])
            + ([QualityState.UNKNOWN] if financial_incomplete else [])
            + ([QualityState.UNKNOWN] if unmatched_sell_quantity > 0 else [])
        )
        if quality_state is not QualityState.FRESH:
            reasons.append(f"WALLET_TRACKING_EVIDENCE_{quality_state.value}")
        if not ordered:
            confidence = Decimal("0")
        elif quality_state is QualityState.FRESH:
            confidence = Decimal("1")
        elif quality_state is QualityState.STALE:
            confidence = Decimal("0.25")
        elif quality_state is QualityState.INVALID:
            confidence = Decimal("0")
        else:
            confidence = Decimal("0.5")
        evidence_times = [activity.observed_at for activity in ordered]
        evidence_times.extend(observation.observed_at for observation in rug_observations)
        as_of = max(evidence_times, default=checked_at)
        return WalletTrackingSnapshot(
            token=token,
            wallet_address=wallet.address,
            label=wallet.label,
            tier=wallet.tier,
            as_of=as_of,
            expires_at=as_of + self.policy.evidence_ttl,
            buy_count=buy_count,
            sell_count=sell_count,
            matched_sell_count=matched_sell_count,
            open_quantity=open_quantity,
            open_cost_basis=open_cost_basis,
            unmatched_sell_quantity=unmatched_sell_quantity,
            realized_pnl=realized_pnl,
            round_trips=tuple(round_trips),
            first_entry_at=first_entry_at,
            token_age_at_first_entry_seconds=token_age,
            median_hold_seconds=median_hold,
            rug_exposure=rug_exposure,
            provenance=tuple(provenance),
            evidence_refs=tuple(evidence_refs),
            reason_codes=tuple(reasons),
            confidence=confidence,
            config_hash=config_hash,
            quality_state=quality_state,
            version=self.policy.version,
        )

    def _rug_evidence(
        self,
        observations: Sequence[Observation],
        *,
        now: datetime,
        first_entry_at: datetime | None,
    ) -> tuple[QualityState, bool | None, tuple[str, ...]]:
        if not observations:
            return (
                QualityState.UNKNOWN,
                None,
                ("RUG_EVIDENCE_MISSING",),
            )
        states: list[QualityState] = []
        valid_values: list[tuple[datetime, bool]] = []
        invalid = False
        for observation in observations:
            state = _quality_at(observation, now, self.policy.evidence_ttl)
            states.append(state)
            raw_value = _field(observation.normalized_payload, "rugged", "rug", "is_rug", "outcome")
            if not isinstance(raw_value, bool):
                invalid = True
                continue
            event_at = observation.occurred_at or observation.observed_at
            valid_values.append((event_at, raw_value))
        quality_state = _combined_quality(states)
        if invalid:
            quality_state = _combined_quality((quality_state, QualityState.INVALID))
        if not valid_values:
            return quality_state, None, ("RUG_EVIDENCE_INVALID",)
        if quality_state is not QualityState.FRESH:
            return quality_state, None, (f"RUG_EVIDENCE_{quality_state.value}",)
        exposed = any(
            rugged and (first_entry_at is None or event_at >= first_entry_at)
            for event_at, rugged in valid_values
        )
        if exposed:
            return quality_state, True, ("RUG_EXPOSURE_DETECTED",)
        return quality_state, False, ("RUG_EVIDENCE_CLEAR",)

    @staticmethod
    def _token_age(token_created_at: datetime | None, entry_at: datetime | None) -> Decimal | None:
        if token_created_at is None or entry_at is None:
            return None
        if entry_at < token_created_at:
            return None
        return Decimal(str((entry_at - token_created_at).total_seconds()))

    @staticmethod
    def _token_age_state(
        token_created_at: datetime | None,
        activities: Sequence[WalletActivity],
        now: datetime,
    ) -> QualityState:
        if token_created_at is None:
            return QualityState.UNKNOWN
        if token_created_at > now:
            return QualityState.INVALID
        if any(activity.occurred_at < token_created_at for activity in activities):
            return QualityState.INVALID
        return QualityState.FRESH

    @staticmethod
    def _median(values: Sequence[Decimal]) -> Decimal | None:
        if not values:
            return None
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle]) / Decimal("2")


__all__ = [
    "TrackedWallet",
    "TrackedWalletRegistry",
    "WalletAction",
    "WalletActivity",
    "WalletRoundTrip",
    "WalletTier",
    "WalletTrackingAnalyzer",
    "WalletTrackingPolicy",
    "WalletTrackingSnapshot",
]
