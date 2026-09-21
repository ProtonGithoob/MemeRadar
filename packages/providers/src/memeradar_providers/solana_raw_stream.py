"""Bounded, read-only Solana logs-to-raw-transaction transport.

The WebSocket notification is only a signature/slot hint.  Protocol identity
and token fields come from the fetched transaction, then enter the existing
``RawChainTransaction`` contract.  No provider payload is treated as a
canonical protocol event until the existing registry decoder accepts it.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections import deque
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_application.stream_integrity import RawChainTransaction
from memeradar_domain import Chain, CommitmentState
from memeradar_domain.common import ensure_ordered_timestamps, ensure_utc, require_text
from memeradar_domain.identities import require_solana_address

from .pump_fun_idl import (
    PUMP_FUN_CREATE_TAG,
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_PROGRAM_ID,
    decode_pump_fun_instruction,
)
from .solana_rpc import SolanaRpcAdapter
from .transport import (
    ProviderError,
    ProviderSchemaError,
    ProviderUnavailableError,
)

try:  # The dependency is already supplied by uvicorn[standard].
    import websockets
    from websockets.exceptions import WebSocketException

    _WEBSOCKET_ERROR_TYPES: tuple[type[BaseException], ...] = (WebSocketException,)
except ImportError:  # pragma: no cover - doctor path for minimal installations
    websockets = None  # type: ignore[assignment]
    _WEBSOCKET_ERROR_TYPES = ()

Clock = Callable[[], datetime]
Sleeper = Callable[[float], Any]

SOLANA_RAW_TRANSPORT = "solana-public-rpc"
SOLANA_PUBLIC_WEBSOCKET_URL = "wss://api.mainnet-beta.solana.com"
PUMP_FUN_BUY_TAG = bytes.fromhex("66063d1201daebea")
PUMP_FUN_BUY_V2_TAG = bytes.fromhex("b817ee6167c5d33d")
PUMP_FUN_BUY_EXACT_QUOTE_IN_V2_TAG = bytes.fromhex("c2ab1c46684d5b2f")
PUMP_FUN_SELL_TAG = bytes.fromhex("33e685a4017f83ad")
PUMP_FUN_SELL_V2_TAG = bytes.fromhex("5df6823ce7e940b2")
PUMP_FUN_MIGRATE_TAG = bytes.fromhex("9beae792ec9ea21e")

_PUMP_INSTRUCTION_NAMES: dict[str, str] = {
    PUMP_FUN_CREATE_TAG.hex(): "create",
    PUMP_FUN_CREATE_V2_TAG.hex(): "create_v2",
    PUMP_FUN_BUY_TAG.hex(): "buy",
    PUMP_FUN_BUY_V2_TAG.hex(): "buy_v2",
    PUMP_FUN_BUY_EXACT_QUOTE_IN_V2_TAG.hex(): "buy_exact_quote_in_v2",
    PUMP_FUN_SELL_TAG.hex(): "sell",
    PUMP_FUN_SELL_V2_TAG.hex(): "sell_v2",
    PUMP_FUN_MIGRATE_TAG.hex(): "migrate",
}
_CREATE_NAMES = frozenset({"create", "create_v2"})
_TRADE_NAMES = frozenset(
    {"buy", "buy_v2", "buy_exact_quote_in_v2", "sell", "sell_v2"}
)


@dataclass(frozen=True, slots=True)
class SolanaLogsNotification:
    """Validated data delivered by one ``logsSubscribe`` notification."""

    slot: int
    signature: str
    error: object
    logs: tuple[str, ...]
    commitment: CommitmentState
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.slot, int) or isinstance(self.slot, bool) or self.slot < 0:
            raise ValueError("slot must be a non-negative integer")
        object.__setattr__(self, "signature", require_text(self.signature, "signature"))
        if any(not isinstance(item, str) for item in self.logs):
            raise TypeError("logs must contain text values")
        object.__setattr__(self, "logs", tuple(self.logs))
        object.__setattr__(self, "commitment", CommitmentState(self.commitment))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, "observed_at"))


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProviderSchemaError(f"{field} must be an object")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderSchemaError(f"{field} must be a non-negative integer")
    return value


def _base58_decode(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ProviderSchemaError("instruction data must be non-empty base58 text")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    indexes = {char: index for index, char in enumerate(alphabet)}
    number = 0
    for char in value:
        try:
            number = number * 58 + indexes[char]
        except KeyError as exc:
            raise ProviderSchemaError("instruction data was not valid base58") from exc
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + decoded


def _address(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderSchemaError(f"{field} must be an address string")
    try:
        return require_solana_address(value, field)
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"{field} must be a valid Solana address") from exc


def parse_logs_notification(
    value: object,
    *,
    observed_at: datetime,
    commitment: CommitmentState | str = CommitmentState.UNKNOWN,
) -> SolanaLogsNotification:
    """Parse one raw WebSocket message without admitting protocol semantics."""

    envelope = _mapping(value, "WebSocket message")
    if envelope.get("method") != "logsNotification":
        raise ProviderSchemaError("WebSocket message was not a logsNotification")
    params = _mapping(envelope.get("params"), "logsNotification params")
    result = _mapping(params.get("result"), "logsNotification result")
    context = _mapping(result.get("context"), "logsNotification context")
    notification = _mapping(result.get("value"), "logsNotification value")
    raw_logs = notification.get("logs")
    raw_signature = notification.get("signature")
    if not isinstance(raw_signature, str):
        raise ProviderSchemaError("logsNotification signature was invalid")
    if not isinstance(raw_logs, Sequence) or isinstance(raw_logs, str | bytes | bytearray):
        raise ProviderSchemaError("logsNotification logs were invalid")
    if any(not isinstance(item, str) for item in raw_logs):
        raise ProviderSchemaError("logsNotification logs contained a non-text value")
    return SolanaLogsNotification(
        slot=_nonnegative_int(context.get("slot"), "context.slot"),
        signature=require_text(raw_signature, "signature", max_length=128),
        error=notification.get("err"),
        logs=tuple(raw_logs),
        commitment=CommitmentState(commitment),
        observed_at=observed_at,
    )


def _account_keys(
    message: Mapping[str, object],
    meta: Mapping[str, object],
) -> tuple[str, ...]:
    raw = message.get("accountKeys", ())
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes | bytearray):
        raise ProviderSchemaError("transaction accountKeys were invalid")
    result: list[str] = []
    has_expanded_lookup_keys = any(
        isinstance(item, Mapping) and item.get("source") == "lookupTable" for item in raw
    )
    for item in raw:
        if isinstance(item, Mapping):
            item = item.get("pubkey")
        result.append(_address(item, "account key"))
    if not has_expanded_lookup_keys:
        loaded = meta.get("loadedAddresses")
        if loaded is not None:
            loaded_mapping = _mapping(loaded, "loadedAddresses")
            for key in ("writable", "readonly"):
                values = loaded_mapping.get(key, ())
                if not isinstance(values, Sequence) or isinstance(values, str | bytes | bytearray):
                    raise ProviderSchemaError(f"loadedAddresses.{key} was invalid")
                result.extend(_address(item, "loaded address") for item in values)
    return tuple(result)


def _instruction_accounts(
    value: object,
    *,
    account_keys: Sequence[str],
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ProviderSchemaError("instruction accounts were invalid")
    result: list[str] = []
    for item in value:
        if isinstance(item, int) and not isinstance(item, bool):
            if item < 0 or item >= len(account_keys):
                raise ProviderSchemaError("instruction account index was invalid")
            result.append(account_keys[item])
        else:
            result.append(_address(item, "instruction account"))
    return tuple(result)


def _instruction_program_id(instruction: Mapping[str, object], account_keys: Sequence[str]) -> str:
    value = instruction.get("programId")
    if value is None:
        index = instruction.get("programIdIndex")
        if not isinstance(index, int) or isinstance(index, bool):
            raise ProviderSchemaError("instruction program identity was missing")
        if index < 0 or index >= len(account_keys):
            raise ProviderSchemaError("instruction program index was invalid")
        value = account_keys[index]
    return _address(value, "instruction program")


def _instruction_payload(
    *,
    name: str,
    accounts: tuple[str, ...],
    data: str,
    decoded_data: bytes,
    notification: SolanaLogsNotification,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_type": name,
        "instruction_name": name,
        "instruction_data_base58": data,
        "accounts": accounts,
        "signature": notification.signature,
        "slot": notification.slot,
        "logs": notification.logs,
        "transaction_error": notification.error,
        "instruction_type": name,
        "protocol_event_type": (
            "launch" if name in _CREATE_NAMES else "trade" if name in _TRADE_NAMES else name
        ),
    }
    if name in _CREATE_NAMES:
        try:
            payload.update(decode_pump_fun_instruction(name, decoded_data, accounts))
        except (TypeError, ValueError) as exc:
            raise ProviderSchemaError(f"Pump.fun {name} IDL decode failed: {exc}") from exc
    elif name in _TRADE_NAMES:
        # Legacy buy/sell place mint at index 2; v2 buy places it at index 1.
        mint_index = 1 if name in {"buy_v2", "buy_exact_quote_in_v2"} else 2
        if len(accounts) > mint_index:
            payload["mint_address"] = accounts[mint_index]
        user_index = 13 if name in {"buy_v2", "buy_exact_quote_in_v2", "sell_v2"} else 6
        if len(accounts) > user_index:
            payload["user"] = accounts[user_index]
    elif name == "migrate" and len(accounts) > 2:
        payload["mint_address"] = accounts[2]
    return payload


def _event_index(parent_index: int | None, child_index: int) -> int:
    if parent_index is None:
        return child_index
    # Keep top-level and CPI instruction identities disjoint and deterministic.
    return 1_000_000 + (parent_index * 10_000) + child_index


def map_transaction_to_raw_events(
    transaction: Mapping[str, object],
    notification: SolanaLogsNotification,
    *,
    ingested_at: datetime,
    program_id: str = PUMP_FUN_PROGRAM_ID,
    transport: str = SOLANA_RAW_TRANSPORT,
) -> tuple[RawChainTransaction, ...]:
    """Map one fetched RPC transaction to verified-candidate raw events.

    Only known Pump.fun instruction discriminators are emitted.  Unknown
    instructions remain observable in provider telemetry but fail closed before
    the canonical protocol registry.
    """

    if not isinstance(transaction, Mapping):
        raise ProviderSchemaError("getTransaction result was invalid")
    slot = _nonnegative_int(transaction.get("slot"), "transaction.slot")
    if slot != notification.slot:
        raise ProviderSchemaError("WebSocket slot and HTTP transaction slot differed")
    block_time = transaction.get("blockTime")
    if not isinstance(block_time, int) or isinstance(block_time, bool):
        raise ProviderSchemaError("transaction.blockTime is required for RawChainTransaction")
    try:
        occurred_at = datetime.fromtimestamp(block_time, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ProviderSchemaError("transaction.blockTime was invalid") from exc
    observed_at = ensure_utc(notification.observed_at, "observed_at")
    ingested = ensure_utc(ingested_at, "ingested_at")
    try:
        ordered_occurred_at, observed_at, ingested = ensure_ordered_timestamps(
            occurred_at, observed_at, ingested
        )
        if ordered_occurred_at is None:
            raise ValueError("occurred_at is required")
        occurred_at = ordered_occurred_at
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError("transaction timestamps were not ordered") from exc
    if notification.error is not None:
        return ()
    tx = _mapping(transaction.get("transaction"), "transaction")
    message = _mapping(tx.get("message"), "transaction message")
    raw_signatures = tx.get("signatures")
    if raw_signatures is not None:
        if not isinstance(raw_signatures, Sequence) or isinstance(
            raw_signatures, str | bytes | bytearray
        ):
            raise ProviderSchemaError("transaction signatures were invalid")
        if any(not isinstance(signature, str) for signature in raw_signatures):
            raise ProviderSchemaError("transaction signatures contained a non-text value")
        if notification.signature not in raw_signatures:
            raise ProviderSchemaError("WebSocket and HTTP transaction signatures differed")
    meta = _mapping(transaction.get("meta"), "transaction metadata")
    account_keys = _account_keys(message, meta)
    raw_instructions: list[tuple[int, Mapping[str, object]]] = []
    top_level = message.get("instructions", ())
    if not isinstance(top_level, Sequence) or isinstance(top_level, str | bytes | bytearray):
        raise ProviderSchemaError("top-level instructions were invalid")
    raw_instructions.extend(
        (index, _mapping(instruction, "instruction"))
        for index, instruction in enumerate(top_level)
    )
    if meta.get("err") is not None:
        return ()
    inner = meta.get("innerInstructions", ())
    if not isinstance(inner, Sequence) or isinstance(inner, str | bytes | bytearray):
        raise ProviderSchemaError("innerInstructions were invalid")
    for group in inner:
        group_mapping = _mapping(group, "inner instruction group")
        parent_index = group_mapping.get("index")
        if not isinstance(parent_index, int) or isinstance(parent_index, bool):
            raise ProviderSchemaError("inner instruction parent index was invalid")
        instructions = group_mapping.get("instructions", ())
        if not isinstance(instructions, Sequence) or isinstance(
            instructions, str | bytes | bytearray
        ):
            raise ProviderSchemaError("inner instructions were invalid")
        raw_instructions.extend(
            (_event_index(parent_index, index), _mapping(instruction, "inner instruction"))
            for index, instruction in enumerate(instructions)
        )

    events: list[RawChainTransaction] = []
    for event_index, instruction in raw_instructions:
        if _instruction_program_id(instruction, account_keys) != program_id:
            continue
        decoded = _base58_decode(instruction.get("data"))
        tag = decoded[:8]
        name = _PUMP_INSTRUCTION_NAMES.get(tag.hex())
        if name is None:
            continue
        accounts = _instruction_accounts(instruction.get("accounts", ()), account_keys=account_keys)
        payload = _instruction_payload(
            name=name,
            accounts=accounts,
            data=cast(str, instruction.get("data")),
            decoded_data=decoded,
            notification=notification,
        )
        payload.update(
            {
                "provider_observed_at": observed_at.isoformat(),
                "memeradar_ingested_at": ingested.isoformat(),
                "event_time_source": "blockTime",
                "event_time_quality": "EXACT",
                "commitment": notification.commitment.value,
            }
        )
        events.append(
            RawChainTransaction(
                chain=Chain.SOLANA,
                slot=slot,
                signature=notification.signature,
                event_index=event_index,
                program_id=program_id,
                discriminator_or_tag=tag,
                payload=payload,
                occurred_at=occurred_at,
                observed_at=observed_at,
                ingested_at=ingested,
                transport=transport,
                commitment=notification.commitment,
                event_schema_version=2,
            )
        )
    return tuple(events)


class SolanaRawTransactionSource(AsyncIterator[RawChainTransaction]):
    """Bounded Pump.fun WebSocket source backed by standard HTTP RPC."""

    def __init__(
        self,
        rpc: SolanaRpcAdapter,
        *,
        websocket_url: str = SOLANA_PUBLIC_WEBSOCKET_URL,
        program_id: str = PUMP_FUN_PROGRAM_ID,
        commitment: CommitmentState | str = CommitmentState.CONFIRMED,
        clock: Clock | None = None,
        stop_event: asyncio.Event | None = None,
        seen_signature_limit: int = 20_000,
    ) -> None:
        if not isinstance(rpc, SolanaRpcAdapter):
            raise TypeError("rpc must be a SolanaRpcAdapter")
        if websockets is None:
            raise ProviderUnavailableError("websockets dependency is unavailable")
        self.rpc = rpc
        self.websocket_url = require_text(websocket_url, "websocket_url")
        self.program_id = require_text(program_id, "program_id")
        self.commitment = CommitmentState(commitment)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._stop_event = stop_event or asyncio.Event()
        self._seen: deque[str] = deque(maxlen=seen_signature_limit)
        self._seen_set: set[str] = set()
        self._queue: asyncio.Queue[RawChainTransaction] = asyncio.Queue(maxsize=256)
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._subscription: int | None = None
        self._last_slot: int | None = None
        self.metrics: dict[str, int] = {
            "notifications_received": 0,
            "signatures_deduplicated": 0,
            "transactions_fetched": 0,
            "transactions_unavailable": 0,
            "raw_events_emitted": 0,
            "stream_reconnects": 0,
            "stream_errors": 0,
        }

    def __aiter__(self) -> SolanaRawTransactionSource:
        return self

    async def __anext__(self) -> RawChainTransaction:
        if self._closed:
            raise StopAsyncIteration
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="solana-raw-source")
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                await self.aclose()
                raise StopAsyncIteration
            try:
                return await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                if self._task.done() and self._queue.empty():
                    error = self._task.exception()
                    if error is not None:
                        raise error from None
                    raise StopAsyncIteration from None

    async def aclose(self) -> None:
        self._closed = True
        self._stop_event.set()
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        if websockets is None:  # pragma: no cover
            raise ProviderUnavailableError("websockets dependency is unavailable")
        while not self._stop_event.is_set() and not self._closed:
            try:
                self.metrics["stream_reconnects"] += 1
                async with websockets.connect(
                    self.websocket_url,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=8 * 1024 * 1024,
                ) as websocket:
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "logsSubscribe",
                                "params": [
                                    {"mentions": [self.program_id]},
                                    {"commitment": self._rpc_commitment()},
                                ],
                            }
                        )
                    )
                    response = json.loads(await asyncio.wait_for(websocket.recv(), 15))
                    subscription = response.get("result")
                    if not isinstance(subscription, int):
                        raise ProviderSchemaError("logsSubscribe did not return a subscription id")
                    self._subscription = subscription
                    while not self._stop_event.is_set() and not self._closed:
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), 30)
                        except TimeoutError:
                            continue
                        observed_at = ensure_utc(self._clock(), "observed_at")
                        notification = parse_logs_notification(
                            json.loads(raw),
                            observed_at=observed_at,
                            commitment=self.commitment,
                        )
                        self.metrics["notifications_received"] += 1
                        self._last_slot = max(
                            self._last_slot or notification.slot,
                            notification.slot,
                        )
                        if notification.signature in self._seen_set:
                            self.metrics["signatures_deduplicated"] += 1
                            continue
                        self._remember(notification.signature)
                        if notification.error is not None or not self._is_launch_notification(
                            notification
                        ):
                            continue
                        context = ProviderRequestContext(
                            correlation_id=f"solana:{notification.signature}",
                            requested_at=observed_at,
                            deadline_at=observed_at + timedelta(seconds=10),
                        )
                        # The raw fetch method applies the provider transport's
                        # bounded timeout/retry/rate-limit policy.
                        transaction = await self._fetch_transaction_with_retry(
                            notification.signature,
                            context=context,
                            commitment=self._rpc_commitment(),
                        )
                        self.metrics["transactions_fetched"] += 1
                        if transaction is None:
                            self.metrics["transactions_unavailable"] += 1
                            continue
                        events = map_transaction_to_raw_events(
                            transaction,
                            notification,
                            ingested_at=ensure_utc(self._clock(), "ingested_at"),
                            program_id=self.program_id,
                        )
                        for event in events:
                            await self._queue.put(event)
                            self.metrics["raw_events_emitted"] += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not isinstance(
                    exc,
                    (
                        ProviderError,
                        OSError,
                        TimeoutError,
                        ValueError,
                        json.JSONDecodeError,
                    )
                    + _WEBSOCKET_ERROR_TYPES,
                ):
                    raise
                self.metrics["stream_errors"] += 1
                if self._stop_event.is_set() or self._closed:
                    return
                await asyncio.sleep(1.0)

    async def _fetch_transaction_with_retry(
        self,
        signature: str,
        *,
        context: ProviderRequestContext,
        commitment: str = "confirmed",
    ) -> Mapping[str, object] | None:
        # ponytail: three short retries cover the normal indexing race; a
        # durable fetch queue belongs in a separately measured backfill worker.
        for attempt in range(3):
            transaction = await self.rpc.fetch_transaction_payload(
                signature,
                context=context,
                commitment=commitment,
            )
            if transaction is not None:
                return transaction
            if attempt < 2:
                await asyncio.sleep(0.25 * (attempt + 1) + (random.random() * 0.1))
        return None

    def _is_launch_notification(self, notification: SolanaLogsNotification) -> bool:
        # ponytail: fetch only launch-shaped logs on the public endpoint.  This
        # keeps one HTTP request per launch instead of attempting every Pump
        # trade; expand to trade windows after measured provider capacity exists.
        has_program = any(
            f"Program {self.program_id}" in log for log in notification.logs
        )
        has_create = any(
            "Instruction: Create" in log or "Instruction: create" in log
            for log in notification.logs
        )
        return has_program and has_create

    def _remember(self, signature: str) -> None:
        if len(self._seen) == self._seen.maxlen:
            expired = self._seen.popleft()
            self._seen_set.discard(expired)
        self._seen.append(signature)
        self._seen_set.add(signature)

    def _rpc_commitment(self) -> str:
        return {
            CommitmentState.PROCESSED_UNCONFIRMED: "processed",
            CommitmentState.CONFIRMED: "confirmed",
            CommitmentState.FINALIZED: "finalized",
        }.get(self.commitment, "confirmed")


__all__ = [
    "PUMP_FUN_BUY_EXACT_QUOTE_IN_V2_TAG",
    "PUMP_FUN_BUY_TAG",
    "PUMP_FUN_BUY_V2_TAG",
    "PUMP_FUN_CREATE_TAG",
    "PUMP_FUN_CREATE_V2_TAG",
    "PUMP_FUN_MIGRATE_TAG",
    "PUMP_FUN_PROGRAM_ID",
    "PUMP_FUN_SELL_TAG",
    "PUMP_FUN_SELL_V2_TAG",
    "SOLANA_PUBLIC_WEBSOCKET_URL",
    "SOLANA_RAW_TRANSPORT",
    "SolanaLogsNotification",
    "SolanaRawTransactionSource",
    "map_transaction_to_raw_events",
    "parse_logs_notification",
]
