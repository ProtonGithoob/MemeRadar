"""Untrusted Helius webhook and stream normalization seams."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import json
import math
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memeradar_application.event_taxonomy import classify_transaction
from memeradar_application.reliability import ReliabilityTelemetry, emit_counter, emit_latency
from memeradar_domain import Observation, Provenance, QualityState, require_solana_address
from memeradar_domain.common import (
    ensure_ordered_timestamps,
    ensure_utc,
    require_text,
    to_decimal,
)

from .fixtures import FixtureRedactor
from .transport import (
    ProviderAuthenticationError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

HELIUS_PROVIDER = "helius"
HELIUS_STREAM_PARSER_VERSION = "helius-stream-v1"
_ACTIVITY_ALIASES = {
    "SWAP": "SWAP",
    "TOKEN_SWAP": "SWAP",
    "DEX_SWAP": "SWAP",
    "SWAP_TRANSACTION": "SWAP",
    "ADD_LIQUIDITY": "LIQUIDITY_ADD",
    "LIQUIDITY_ADD": "LIQUIDITY_ADD",
    "LIQUIDITY_ADDED": "LIQUIDITY_ADD",
    "DEPOSIT_LIQUIDITY": "LIQUIDITY_ADD",
    "REMOVE_LIQUIDITY": "LIQUIDITY_REMOVE",
    "LIQUIDITY_REMOVE": "LIQUIDITY_REMOVE",
    "LIQUIDITY_REMOVED": "LIQUIDITY_REMOVE",
    "WITHDRAW_LIQUIDITY": "LIQUIDITY_REMOVE",
    "BRIDGE": "BRIDGE",
    "BRIDGE_TRANSFER": "BRIDGE",
    "CROSS_CHAIN_TRANSFER": "BRIDGE",
    "TOKEN_BRIDGE": "BRIDGE",
    "TRANSFER": "TRANSFER",
    "TOKEN_TRANSFER": "TRANSFER",
    "SPL_TRANSFER": "TRANSFER",
    "NATIVE_TRANSFER": "TRANSFER",
    "ERC20_TRANSFER": "TRANSFER",
    "TOKEN_LAUNCH": "TOKEN_LAUNCH",
    "TOKEN_CREATED": "TOKEN_LAUNCH",
    "CREATE_TOKEN": "TOKEN_LAUNCH",
    "LAUNCH": "TOKEN_LAUNCH",
    "MEV": "MEV_ARBITRAGE",
    "ARBITRAGE": "MEV_ARBITRAGE",
    "MEV_ARBITRAGE": "MEV_ARBITRAGE",
    "ARBITRAGE_TRADE": "MEV_ARBITRAGE",
}
_ACTIVITY_FIELDS = (
    "activity_kind",
    "activity_type",
    "transaction_type",
    "event_type",
    "action",
    "type",
)
_ACTIVITY_NESTED_FIELDS = ("event", "activity", "operation")
_ACTIVITY_FLAG_ALIASES = {
    "is_swap": "SWAP",
    "is_bridge": "BRIDGE",
    "is_transfer": "TRANSFER",
    "is_token_launch": "TOKEN_LAUNCH",
    "is_mev": "MEV_ARBITRAGE",
    "is_arbitrage": "MEV_ARBITRAGE",
}
MessageSource = AsyncIterable[object]
SourceFactory = Callable[[], MessageSource | Awaitable[MessageSource]]
ObservationSink = Callable[[Observation], Awaitable[None] | None]
Clock = Callable[[], datetime]
_MISSING = object()


def _parse_event_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value, "occurred_at")
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ProviderSchemaError("event timestamp must be finite")
        if abs(numeric) >= 10_000_000_000:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ProviderSchemaError("event timestamp was outside the supported range") from exc
    if isinstance(value, str):
        normalized = require_text(value, "occurred_at", max_length=64)
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(normalized), "occurred_at")
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("event timestamp was not valid ISO-8601") from exc
    raise ProviderSchemaError("event timestamp has an unsupported type")


def _source_id(payload: Mapping[str, object]) -> str:
    for key in ("source_id", "event_id", "signature", "webhook_id", "id"):
        value = payload.get(key, _MISSING)
        if value is not _MISSING:
            try:
                return require_text(value, "source_id", max_length=256)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError("stream source_id was invalid") from exc
    raise ProviderSchemaError("stream source_id is missing")


def _kind(payload: Mapping[str, object]) -> str:
    raw_kind = payload.get("kind", payload.get("type", payload.get("event_type", _MISSING)))
    if raw_kind is _MISSING:
        return "onchain.helius.event"
    if not isinstance(raw_kind, str):
        raise ProviderSchemaError("stream event type was invalid")
    normalized = require_text(raw_kind, "event_type", max_length=64).lower().replace("-", "_")
    if "transaction" in normalized:
        return "onchain.helius.transaction"
    if "account" in normalized:
        return "onchain.helius.account"
    if "token" in normalized or "mint" in normalized:
        return "onchain.helius.token"
    return "onchain.helius.event"


def _quality(payload: Mapping[str, object]) -> QualityState:
    value = payload.get("quality_state", _MISSING)
    if value is _MISSING:
        return QualityState.FRESH
    if not isinstance(value, str):
        return QualityState.UNKNOWN
    try:
        return QualityState(value.strip().upper())
    except ValueError:
        return QualityState.UNKNOWN


def _activity_alias(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    return _ACTIVITY_ALIASES.get(normalized)


def _activity_kind(payload: Mapping[str, object]) -> str:
    """Classify only explicit transaction/activity labels, never descriptions."""

    candidates: list[str] = []
    for field in _ACTIVITY_FIELDS:
        value = payload.get(field, _MISSING)
        if value is not _MISSING:
            normalized = _activity_alias(value)
            if normalized is not None:
                candidates.append(normalized)
    for field in _ACTIVITY_NESTED_FIELDS:
        value = payload.get(field)
        if isinstance(value, Mapping):
            for nested_field in ("activity_kind", "activity_type", "type", "kind", "name"):
                normalized = _activity_alias(value.get(nested_field))
                if normalized is not None:
                    candidates.append(normalized)
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            for item in value:
                if isinstance(item, Mapping):
                    for nested_field in ("activity_kind", "activity_type", "type", "kind", "name"):
                        normalized = _activity_alias(item.get(nested_field))
                        if normalized is not None:
                            candidates.append(normalized)
    for field, normalized in _ACTIVITY_FLAG_ALIASES.items():
        if payload.get(field) is True:
            candidates.append(normalized)
    distinct = set(candidates)
    return next(iter(distinct)) if len(distinct) == 1 else "UNKNOWN"


def _deterministic_observation_id(source_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"memeradar:{HELIUS_PROVIDER}:stream:{source_id}")


class HeliusObservationNormalizer:
    """Convert an untrusted Helius message into one replayable observation."""

    provider_name = HELIUS_PROVIDER
    parser_version = HELIUS_STREAM_PARSER_VERSION

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        parser_version: str = HELIUS_STREAM_PARSER_VERSION,
        redactor: FixtureRedactor | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.parser_version = require_text(parser_version, "parser_version", max_length=64)
        self._redactor = redactor or FixtureRedactor()

    def normalize(
        self,
        message: object,
        *,
        observed_at: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> Observation:
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("stream message must be an object")
        source_id = _source_id(message)
        kind = _kind(message)
        event_time = _MISSING
        for key in ("occurred_at", "block_time", "timestamp", "event_time"):
            if key in message:
                event_time = message[key]
                break
        occurred_at = (
            None if event_time is _MISSING or event_time is None else _parse_event_time(event_time)
        )
        effective_observed = ensure_utc(observed_at or self._clock(), "observed_at")
        effective_ingested = ensure_utc(
            ingested_at if ingested_at is not None else effective_observed,
            "ingested_at",
        )
        try:
            normalized_occurred, normalized_observed, normalized_ingested = (
                ensure_ordered_timestamps(occurred_at, effective_observed, effective_ingested)
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("stream message timestamps were not ordered") from exc
        safe_payload = self._redactor.redact(message)
        if not isinstance(safe_payload, Mapping):
            raise ProviderSchemaError("stream message could not be normalized")
        normalized_payload = {str(key): value for key, value in safe_payload.items()}
        normalized_payload["source_id"] = source_id
        normalized_payload["normalized_kind"] = kind
        normalized_payload["activity_kind"] = _activity_kind(message)
        taxonomy, taxonomy_confidence = classify_transaction(normalized_payload)
        normalized_payload["canonical_event_type"] = taxonomy.value
        normalized_payload["classification_confidence"] = taxonomy_confidence
        normalized_payload["collection_mode"] = "PRODUCTION"
        provenance = Provenance(
            provider=HELIUS_PROVIDER,
            source_id=source_id,
            observed_at=normalized_observed,
            parser_version=self.parser_version,
        )
        try:
            return Observation(
                id=_deterministic_observation_id(source_id),
                kind=kind,
                provenance=provenance,
                occurred_at=normalized_occurred,
                observed_at=normalized_observed,
                ingested_at=normalized_ingested,
                quality_state=_quality(message),
                normalized_payload=normalized_payload,
            )
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError("stream message failed observation validation") from exc


class HeliusWalletWebhookAdapter:
    """Authenticate and map Helius wallet webhooks to existing wallet evidence."""

    provider_name = HELIUS_PROVIDER
    parser_version = "helius-wallet-webhook-v1"
    capabilities = frozenset({"wallet_activity", "realtime_stream"})

    def __init__(
        self,
        *,
        webhook_secret: str,
        watched_wallets: Sequence[str] = (),
        replay_ttl: float = 900.0,
        max_replay_ids: int = 10_000,
        clock: Clock | None = None,
    ) -> None:
        self._secret = require_text(webhook_secret, "webhook_secret", max_length=512)
        if isinstance(watched_wallets, str | bytes | bytearray):
            raise TypeError("watched_wallets must be a sequence")
        self._watched_wallets = frozenset(
            require_solana_address(value, "watched wallet") for value in watched_wallets
        )
        if not 0 < replay_ttl <= 86_400:
            raise ValueError("replay_ttl must be between 0 and 86400 seconds")
        if not isinstance(max_replay_ids, int) or not 1 <= max_replay_ids <= 100_000:
            raise ValueError("max_replay_ids must be between 1 and 100000")
        self._replay_ttl = replay_ttl
        self._max_replay_ids = max_replay_ids
        self._clock = clock or (lambda: datetime.now(UTC))
        self._seen_events: dict[str, datetime] = {}

    def authenticate(self, body: bytes, signature: str) -> None:
        if not isinstance(body, bytes):
            raise TypeError("webhook body must be bytes")
        supplied = require_text(signature, "signature", max_length=256)
        if supplied.lower().startswith("sha256="):
            supplied = supplied[7:]
        expected = hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied.lower()):
            raise ProviderAuthenticationError("Helius webhook signature was invalid")

    @staticmethod
    def _event_id(event: Mapping[str, object]) -> str:
        value = next(
            (
                event.get(key)
                for key in ("event_id", "webhook_id", "signature", "transactionSignature", "id")
                if event.get(key) is not None
            ),
            None,
        )
        if not isinstance(value, str) or not value.strip():
            raise ProviderSchemaError("wallet webhook event id is missing")
        return require_text(value, "event_id", max_length=256)

    @staticmethod
    def _address(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        try:
            return require_solana_address(value, "wallet address")
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _transfer_amount(transfer: Mapping[str, object]) -> Decimal | None:
        raw = transfer.get("tokenAmount", transfer.get("amount", transfer.get("quantity")))
        decimals = transfer.get("decimals")
        if isinstance(raw, Mapping):
            decimals = raw.get("decimals", decimals)
            raw = raw.get("tokenAmount", raw.get("amount", raw.get("value")))
        if raw is None:
            return None
        try:
            amount = to_decimal(raw, "token amount")
            if isinstance(decimals, int) and not isinstance(decimals, bool) and decimals >= 0:
                amount /= Decimal(10) ** decimals
            return amount if amount > 0 else None
        except (TypeError, ValueError, ArithmeticError):
            return None

    def _transfer_observation(
        self,
        event: Mapping[str, object],
        transfer: Mapping[str, object],
        *,
        event_id: str,
        index: int,
        observed_at: datetime,
        occurred_at: datetime | None,
    ) -> Observation | None:
        mint = next(
            (
                transfer.get(key, event.get(key))
                for key in ("mint", "tokenMint", "mintAddress")
                if transfer.get(key, event.get(key)) is not None
            ),
            None,
        )
        if not isinstance(mint, str):
            return None
        try:
            mint = require_solana_address(mint, "token mint")
        except (TypeError, ValueError):
            return None
        from_wallet = self._address(
            transfer.get("fromUserAccount", transfer.get("from", event.get("fromUserAccount")))
        )
        to_wallet = self._address(
            transfer.get("toUserAccount", transfer.get("to", event.get("toUserAccount")))
        )
        candidates = tuple(
            value
            for value in (from_wallet, to_wallet, self._address(event.get("walletAddress")))
            if value
        )
        wallets = tuple(value for value in candidates if value in self._watched_wallets)
        if not wallets:
            return None
        wallet = wallets[0]
        raw_side = event.get("side", event.get("action"))
        normalized_side = raw_side.strip().upper() if isinstance(raw_side, str) else ""
        if normalized_side in {"BUY", "BOUGHT"} or to_wallet == wallet:
            action = "BUY"
        elif normalized_side in {"SELL", "SOLD"} or from_wallet == wallet:
            action = "SELL"
        else:
            action = "TRANSFER"
        if action == "TRANSFER":
            # WalletTrackingAnalyzer intentionally accepts only position-changing actions.
            return None
        amount = self._transfer_amount(transfer)
        if amount is None:
            return None
        quote = event.get("usdValue", event.get("quoteAmount", event.get("value")))
        try:
            quote_amount = None if quote is None else to_decimal(quote, "quote amount")
        except (TypeError, ValueError):
            quote_amount = None
        source_id = f"webhook:{event_id}:{index}:{wallet}:{mint}"
        payload: dict[str, object] = {
            "wallet_address": wallet,
            "action": action,
            "quantity": str(amount),
            "mint_address": mint,
            "signature": event_id,
            "slot": event.get("slot"),
            "protocol": event.get("source", event.get("protocol")),
            "dex": event.get("source", event.get("protocol")),
            "usd_value": None if quote_amount is None else str(quote_amount),
            "classification_confidence": (
                "EXPLICIT_SIDE" if normalized_side else "TRANSFER_DIRECTION"
            ),
            "collection_mode": "PRODUCTION",
        }
        return Observation(
            kind="wallet.activity",
            provenance=Provenance(
                provider=HELIUS_PROVIDER,
                source_id=source_id,
                observed_at=observed_at,
                parser_version=self.parser_version,
            ),
            occurred_at=occurred_at,
            observed_at=observed_at,
            ingested_at=observed_at,
            quality_state=QualityState.FRESH,
            normalized_payload=payload,
        )

    def normalize(
        self,
        payload: Mapping[str, object] | Sequence[Mapping[str, object]],
        *,
        signature: str,
        raw_body: bytes | None = None,
        observed_at: datetime | None = None,
    ) -> tuple[Observation, ...]:
        body = (
            raw_body
            if raw_body is not None
            else json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
        self.authenticate(body, signature)
        checked_at = ensure_utc(observed_at or self._clock(), "observed_at")
        events = (payload,) if isinstance(payload, Mapping) else tuple(payload)
        if not events or any(not isinstance(event, Mapping) for event in events):
            raise ProviderSchemaError("wallet webhook payload must contain objects")
        output: list[Observation] = []
        for event in events:
            event_id = self._event_id(event)
            prior = self._seen_events.get(event_id)
            if prior is not None and checked_at - prior <= timedelta(seconds=self._replay_ttl):
                continue
            self._seen_events[event_id] = checked_at
            if len(self._seen_events) > self._max_replay_ids:
                oldest = min(self._seen_events, key=lambda key: self._seen_events[key])
                del self._seen_events[oldest]
            raw_time = event.get("timestamp", event.get("blockTime", event.get("occurred_at")))
            occurred = None if raw_time is None else _parse_event_time(raw_time)
            if occurred is not None and occurred > checked_at:
                occurred = None
            transfers = event.get("tokenTransfers", event.get("token_transfers", ()))
            if not isinstance(transfers, Sequence) or isinstance(
                transfers, str | bytes | bytearray
            ):
                transfers = ()
            for index, transfer in enumerate(transfers):
                if isinstance(transfer, Mapping):
                    normalized = self._transfer_observation(
                        event,
                        transfer,
                        event_id=event_id,
                        index=index,
                        observed_at=checked_at,
                        occurred_at=occurred,
                    )
                    if normalized is not None:
                        output.append(normalized)
        return tuple(output)

    ingest = normalize


class HeliusStreamConsumer:
    """Consume injected async messages with bounded reconnects and cancellation."""

    provider_name = HELIUS_PROVIDER
    capabilities = frozenset({"realtime_stream"})

    def __init__(
        self,
        *,
        normalizer: HeliusObservationNormalizer | None = None,
        max_reconnects: int = 3,
        reconnect_delay_seconds: float = 1.0,
        max_reconnect_delay_seconds: float = 30.0,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        telemetry: ReliabilityTelemetry | None = None,
    ) -> None:
        if (
            not isinstance(max_reconnects, int)
            or isinstance(max_reconnects, bool)
            or not 0 <= max_reconnects <= 10
        ):
            raise ValueError("max_reconnects must be between 0 and 10")
        for value, field in (
            (reconnect_delay_seconds, "reconnect_delay_seconds"),
            (max_reconnect_delay_seconds, "max_reconnect_delay_seconds"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(float(value))
                or not 0 < float(value) <= 60
            ):
                raise ValueError(f"{field} must be finite and between 0 and 60")
        if max_reconnect_delay_seconds < reconnect_delay_seconds:
            raise ValueError(
                "max_reconnect_delay_seconds must not be below reconnect_delay_seconds"
            )
        self._normalizer = normalizer or HeliusObservationNormalizer()
        self._max_reconnects = max_reconnects
        self._reconnect_delay_seconds = float(reconnect_delay_seconds)
        self._max_reconnect_delay_seconds = float(max_reconnect_delay_seconds)
        self._sleeper = sleeper
        self._telemetry = telemetry

    @staticmethod
    async def _resolve_source(factory: SourceFactory) -> MessageSource:
        source = factory()
        if inspect.isawaitable(source):
            source = await cast(Awaitable[MessageSource], source)
        if not isinstance(source, AsyncIterable):
            raise TypeError("source factory must return an async iterable")
        return source

    def _delay_for(self, reconnect_number: int) -> float:
        return float(
            min(
                self._max_reconnect_delay_seconds,
                self._reconnect_delay_seconds * (2 ** (reconnect_number - 1)),
            )
        )

    async def consume(
        self,
        source_factory: SourceFactory,
        sink: ObservationSink,
        *,
        stop_event: asyncio.Event | None = None,
    ) -> StreamStats:
        received = 0
        emitted = 0
        malformed = 0
        reconnects = 0
        seen_ids: set[UUID] = set()
        while True:
            if stop_event is not None and stop_event.is_set():
                return StreamStats(received, emitted, malformed, reconnects)
            try:
                source = await self._resolve_source(source_factory)
                async for message in source:
                    if stop_event is not None and stop_event.is_set():
                        return StreamStats(received, emitted, malformed, reconnects)
                    received += 1
                    try:
                        observation = self._normalizer.normalize(message)
                    except ProviderSchemaError:
                        malformed += 1
                        emit_counter(
                            self._telemetry,
                            "dropped_malformed",
                            provider=HELIUS_PROVIDER,
                        )
                        continue
                    if observation.id in seen_ids:
                        emit_counter(
                            self._telemetry,
                            "duplicate_events",
                            provider=HELIUS_PROVIDER,
                        )
                    seen_ids.add(observation.id)
                    if observation.occurred_at is not None:
                        emit_latency(
                            self._telemetry,
                            "chain_event_to_ingest_ms",
                            max(
                                0.0,
                                (observation.ingested_at - observation.occurred_at).total_seconds()
                                * 1000,
                            ),
                            source="provider_network",
                            provider=HELIUS_PROVIDER,
                        )
                    result = sink(observation)
                    if inspect.isawaitable(result):
                        await result
                    emitted += 1
                if stop_event is not None and stop_event.is_set():
                    return StreamStats(received, emitted, malformed, reconnects)
            except asyncio.CancelledError:
                raise
            except (ProviderTimeoutError, ProviderUnavailableError, ConnectionError, TimeoutError):
                if reconnects >= self._max_reconnects:
                    raise
            else:
                if reconnects >= self._max_reconnects:
                    return StreamStats(received, emitted, malformed, reconnects)
            reconnects += 1
            emit_counter(
                self._telemetry,
                "stream_reconnects",
                provider=HELIUS_PROVIDER,
            )
            await self._sleeper(self._delay_for(reconnects))


@dataclass(frozen=True, slots=True)
class StreamStats:
    """Immutable counters for one bounded consumer run."""

    received: int
    emitted: int
    malformed: int
    reconnects: int

    def __post_init__(self) -> None:
        for field in ("received", "emitted", "malformed", "reconnects"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")


__all__ = [
    "HELIUS_STREAM_PARSER_VERSION",
    "HeliusObservationNormalizer",
    "HeliusStreamConsumer",
    "HeliusWalletWebhookAdapter",
    "MessageSource",
    "ObservationSink",
    "SourceFactory",
    "StreamStats",
]
