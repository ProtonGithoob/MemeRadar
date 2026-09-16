"""Provider-neutral, read-only external wallet/KOL stream normalization."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import (
    Observation,
    Provenance,
    QualityState,
    normalize_chain,
    require_chain_address,
)
from memeradar_domain.common import ensure_utc, require_text

from .health import ProviderHealth, ProviderHealthTracker
from .transport import ProviderError

SourceFactory = Callable[[], AsyncIterable[object] | Awaitable[AsyncIterable[object]]]


def _timestamp(value: object, field: str, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if isinstance(value, datetime):
        return ensure_utc(value, field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")), field)
    raise ValueError(f"{field} is invalid")


def _hash(value: Mapping[str, object]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class ExternalWalletStreamPolicy:
    max_reconnects: int = 3
    reconnect_delay_seconds: float = 0.1
    max_reconnect_delay_seconds: float = 2.0
    max_events: int = 1_000

    def __post_init__(self) -> None:
        if not 0 <= self.max_reconnects <= 10:
            raise ValueError("max_reconnects must be between 0 and 10")
        if not 0 < self.reconnect_delay_seconds <= self.max_reconnect_delay_seconds <= 60:
            raise ValueError("reconnect delays are invalid")
        if not 1 <= self.max_events <= 100_000:
            raise ValueError("max_events must be between 1 and 100000")


@dataclass(frozen=True, slots=True)
class ExternalWalletStreamGap:
    first_missing_sequence: int
    last_missing_sequence: int
    detected_at: datetime
    recovery_attempted: bool = False
    recovery_result: str = "NOT_ATTEMPTED"


@dataclass(frozen=True, slots=True)
class ExternalWalletStreamResult:
    observations: tuple[Observation, ...]
    used_fallback: bool
    reconnects: int
    duplicates: int
    malformed: int
    gaps: tuple[tuple[int, int], ...]
    health: ProviderHealth
    continuity_state: str = "UNKNOWN"
    gap_reports: tuple[ExternalWalletStreamGap, ...] = ()
    unresolved_gap_count: int = 0


class ExternalWalletEventStreamAdapter:
    """Normalize CabalSpy-style wallet events into existing wallet observations."""

    def __init__(
        self,
        provider_name: str,
        chain: str,
        source_factory: SourceFactory,
        *,
        fallback: Callable[[ProviderRequestContext], Sequence[object] | Awaitable[Sequence[object]]]
        | None = None,
        policy: ExternalWalletStreamPolicy | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        source_layer: str = "EXTERNAL_STREAM",
        authoritative: bool = False,
    ) -> None:
        self.provider_name = require_text(provider_name, "provider_name")
        self.chain = normalize_chain(chain)
        self._source_factory = source_factory
        self._fallback = fallback
        self._policy = policy or ExternalWalletStreamPolicy()
        self._sleeper = sleeper
        self._source_layer = require_text(source_layer, "source_layer", max_length=32).upper()
        self._authoritative = authoritative
        self._health = ProviderHealthTracker()

    def _normalize(
        self,
        value: object,
        context: ProviderRequestContext,
        *,
        source_layer: str | None = None,
    ) -> Observation:
        if not isinstance(value, Mapping):
            raise ValueError("wallet stream event must be a mapping")
        payload = dict(value)
        event_chain = normalize_chain(str(payload.get("chain", self.chain.value)))
        if event_chain is not self.chain:
            raise ValueError("wallet stream event chain mismatch")
        token = payload.get("token_address", payload.get("mint_address", payload.get("token")))
        wallet = payload.get("wallet_address", payload.get("wallet", payload.get("trader")))
        source = payload.get("event_id", payload.get("signature", payload.get("tx_hash")))
        action = payload.get("action", payload.get("side"))
        quantity = payload.get("quantity", payload.get("amount", payload.get("token_amount")))
        if (
            not all(
                isinstance(item, str) and item.strip() for item in (token, wallet, source, action)
            )
            or quantity is None
        ):
            raise ValueError("wallet stream event is missing canonical fields")
        normalized_token = require_chain_address(cast(str, token), self.chain, "token_address")
        normalized_wallet = require_chain_address(cast(str, wallet), self.chain, "wallet_address")
        observed = ensure_utc(context.requested_at, "observed_at")
        raw_occurred = payload.get("occurred_at", payload.get("timestamp"))
        occurred = (
            None if raw_occurred is None else _timestamp(raw_occurred, "occurred_at", observed)
        )
        event_time_quality = "EXACT" if occurred is not None else "MISSING"
        normalized_source = require_text(cast(str, source), "source_id", max_length=256)
        source_id = f"{self.chain.value}:{normalized_source}"
        normalized = {
            "chain": self.chain.value,
            "mint_address": normalized_token,
            "wallet_address": normalized_wallet,
            "action": cast(str, action),
            "quantity": quantity,
            "quote_amount": payload.get("quote_amount", payload.get("notional")),
            "price": payload.get("price", payload.get("effective_price")),
            "venue": payload.get("venue"),
            "canonical_trade_id": source_id,
            "external_classification": payload.get("classification", payload.get("label")),
            "external_score": payload.get("score"),
            "sequence": payload.get("sequence", payload.get("slot", payload.get("block_number"))),
            "event_time_quality": event_time_quality,
            "occurred_at_estimated": False,
            "source_layer": self._source_layer if source_layer is None else source_layer,
            "authoritative": self._authoritative,
            "collection_mode": "PRODUCTION",
        }
        return Observation(
            kind="wallet.activity",
            provenance=Provenance(
                provider=self.provider_name,
                source_id=source_id,
                observed_at=observed,
                parser_version="external-wallet-stream-v1",
                raw_payload_hash=_hash(payload),
            ),
            occurred_at=occurred,
            observed_at=observed,
            ingested_at=observed,
            quality_state=QualityState.FRESH if occurred is not None else QualityState.UNKNOWN,
            normalized_payload=normalized,
        )

    async def _source(self) -> AsyncIterable[object]:
        value = self._source_factory()
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, AsyncIterable):
            raise TypeError("source_factory must return an async iterable")
        return value

    async def collect(
        self, context: ProviderRequestContext, *, stop_event: asyncio.Event | None = None
    ) -> ExternalWalletStreamResult:
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        observations: dict[str, Observation] = {}
        reconnects = duplicates = malformed = 0
        sequence_values: set[int] = set()
        while True:
            try:
                source = await self._source()
                async for message in source:
                    if stop_event is not None and stop_event.is_set():
                        break
                    if len(observations) >= self._policy.max_events:
                        raise ProviderError("wallet stream exceeded configured bound")
                    try:
                        observation = self._normalize(message, context)
                    except (TypeError, ValueError):
                        malformed += 1
                        continue
                    prior = observations.get(observation.provenance.source_id)
                    if prior is not None:
                        duplicates += 1
                        if prior.normalized_payload != observation.normalized_payload:
                            malformed += 1
                        continue
                    sequence = observation.normalized_payload.get("sequence")
                    if isinstance(sequence, int) and not isinstance(sequence, bool):
                        sequence_values.add(sequence)
                    observations[observation.provenance.source_id] = observation
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reconnects += 1
                self._health.record_failure(
                    self.provider_name,
                    "wallet_activity",
                    checked_at=context.requested_at,
                    error=exc,
                )
                if reconnects > self._policy.max_reconnects:
                    break
                await self._sleeper(
                    min(
                        self._policy.max_reconnect_delay_seconds,
                        self._policy.reconnect_delay_seconds * (2 ** (reconnects - 1)),
                    )
                )

        def missing_ranges(values: set[int]) -> tuple[tuple[int, int], ...]:
            if len(values) < 2:
                return ()
            ordered_values = sorted(values)
            ranges: list[tuple[int, int]] = []
            for previous, current in zip(ordered_values, ordered_values[1:], strict=False):
                if current > previous + 1:
                    ranges.append((previous + 1, current - 1))
            return tuple(ranges)

        initial_gaps = missing_ranges(sequence_values)
        used_fallback = bool(
            self._fallback is not None
            and (reconnects > self._policy.max_reconnects or initial_gaps)
        )
        recovery_attempted = False
        recovery_result = "NOT_ATTEMPTED"
        if used_fallback and self._fallback is not None:
            recovery_attempted = bool(initial_gaps)
            try:
                raw = self._fallback(context)
                if inspect.isawaitable(raw):
                    raw = await raw
                for item in raw:
                    try:
                        observation = self._normalize(item, context, source_layer="RPC_BACKFILL")
                    except (TypeError, ValueError):
                        malformed += 1
                        continue
                    if observation.provenance.source_id in observations:
                        duplicates += 1
                    else:
                        observations[observation.provenance.source_id] = observation
                        sequence = observation.normalized_payload.get("sequence")
                        if isinstance(sequence, int) and not isinstance(sequence, bool):
                            sequence_values.add(sequence)
                recovery_result = "RECOVERED" if not missing_ranges(sequence_values) else "FAILED"
            except Exception:
                recovery_result = "FAILED"
        gaps = missing_ranges(sequence_values)
        gap_reports = tuple(
            ExternalWalletStreamGap(
                first_missing_sequence=first,
                last_missing_sequence=last,
                detected_at=ensure_utc(context.requested_at, "detected_at"),
                recovery_attempted=recovery_attempted,
                recovery_result=(recovery_result if recovery_attempted else "UNRESOLVED"),
            )
            for first, last in (initial_gaps or gaps)
        )
        ordered = tuple(
            sorted(
                observations.values(),
                key=lambda item: (item.occurred_at or item.observed_at, item.provenance.source_id),
            )
        )
        if gaps:
            health = self._health.record_failure(
                self.provider_name,
                "wallet_activity",
                checked_at=context.requested_at,
                error=ProviderError("unresolved wallet stream sequence gap"),
            )
            continuity_state = "DEGRADED"
        elif initial_gaps and recovery_attempted:
            health = self._health.record_success(
                self.provider_name, "wallet_activity", checked_at=context.requested_at
            )
            continuity_state = "RECOVERED"
        elif ordered:
            health = self._health.record_success(
                self.provider_name, "wallet_activity", checked_at=context.requested_at
            )
            continuity_state = "CONTIGUOUS"
        else:
            health = self._health.get(self.provider_name, "wallet_activity")
            continuity_state = "UNKNOWN"
        return ExternalWalletStreamResult(
            observations=ordered,
            used_fallback=used_fallback,
            reconnects=reconnects,
            duplicates=duplicates,
            malformed=malformed,
            gaps=gaps,
            health=health,
            continuity_state=continuity_state,
            gap_reports=gap_reports,
            unresolved_gap_count=len(gaps),
        )


class CabalSpyWebSocketSource:
    """Thin documented CabalSpy stream source; payloads still use the shared normalizer."""

    def __init__(
        self,
        url: str,
        *,
        blockchain: str,
        stream: str = "tx",
        event_type: str = "kol",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(url, str) or not url.startswith("wss://"):
            raise ValueError("CabalSpy websocket URL must use wss")
        self.url = url
        self.blockchain = require_text(blockchain, "blockchain", max_length=32)
        self.stream = require_text(stream, "stream", max_length=32)
        self.event_type = require_text(event_type, "event_type", max_length=32)
        self._headers = dict(headers or {})

    async def events(self) -> AsyncIterable[object]:
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise ProviderError("websocket transport is not installed") from exc
        subscription = {
            "op": "subscribe",
            "stream": self.stream,
            "blockchain": self.blockchain,
            "type": self.event_type,
        }
        async with websockets.connect(self.url, additional_headers=self._headers) as socket:
            await socket.send(json.dumps(subscription))
            async for message in socket:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                if not isinstance(message, str):
                    raise ProviderError("CabalSpy websocket payload was not text")
                payload = json.loads(message)
                if not isinstance(payload, Mapping):
                    raise ProviderError("CabalSpy websocket payload was not an object")
                yield payload

    def __repr__(self) -> str:
        return (
            f"CabalSpyWebSocketSource(url={self.url!r}, blockchain={self.blockchain!r}, "
            f"stream={self.stream!r}, event_type={self.event_type!r}, "
            f"headers_configured={bool(self._headers)})"
        )


__all__ = [
    "ExternalWalletEventStreamAdapter",
    "ExternalWalletStreamPolicy",
    "ExternalWalletStreamResult",
    "ExternalWalletStreamGap",
    "CabalSpyWebSocketSource",
]
