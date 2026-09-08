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
class ExternalWalletStreamResult:
    observations: tuple[Observation, ...]
    used_fallback: bool
    reconnects: int
    duplicates: int
    malformed: int
    gaps: tuple[tuple[int, int], ...]
    health: ProviderHealth


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
    ) -> None:
        self.provider_name = require_text(provider_name, "provider_name")
        self.chain = normalize_chain(chain)
        self._source_factory = source_factory
        self._fallback = fallback
        self._policy = policy or ExternalWalletStreamPolicy()
        self._sleeper = sleeper
        self._health = ProviderHealthTracker()

    def _normalize(self, value: object, context: ProviderRequestContext) -> Observation:
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
        occurred = _timestamp(
            payload.get("occurred_at", payload.get("timestamp")), "occurred_at", observed
        )
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
            quality_state=QualityState.FRESH,
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
        gaps: set[tuple[int, int]] = set()
        reconnects = duplicates = malformed = 0
        last_sequence: int | None = None
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
                        if last_sequence is not None and sequence > last_sequence + 1:
                            gaps.add((last_sequence + 1, sequence - 1))
                        last_sequence = max(last_sequence or sequence, sequence)
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
        used_fallback = reconnects > self._policy.max_reconnects and self._fallback is not None
        if used_fallback and self._fallback is not None:
            raw = self._fallback(context)
            if inspect.isawaitable(raw):
                raw = await raw
            for item in raw:
                try:
                    observation = self._normalize(item, context)
                except (TypeError, ValueError):
                    malformed += 1
                    continue
                if observation.provenance.source_id in observations:
                    duplicates += 1
                else:
                    observations[observation.provenance.source_id] = observation
        ordered = tuple(
            sorted(
                observations.values(),
                key=lambda item: (item.occurred_at or item.observed_at, item.provenance.source_id),
            )
        )
        health = (
            self._health.record_success(
                self.provider_name, "wallet_activity", checked_at=context.requested_at
            )
            if ordered
            else self._health.get(self.provider_name, "wallet_activity")
        )
        return ExternalWalletStreamResult(
            observations=ordered,
            used_fallback=used_fallback,
            reconnects=reconnects,
            duplicates=duplicates,
            malformed=malformed,
            gaps=tuple(sorted(gaps)),
            health=health,
        )


__all__ = [
    "ExternalWalletEventStreamAdapter",
    "ExternalWalletStreamPolicy",
    "ExternalWalletStreamResult",
]
