"""Pump.fun bonding-curve trade events decoded from program logs.

Pump.fun emits an Anchor ``TradeEvent`` as a ``Program data:`` log line for
every bonding-curve buy and sell. Decoding the log avoids one
``getTransaction`` call per trade, which makes a live trade tape feasible on
standard RPC.

Verification (2026-11-11): the discriminator equals
``sha256("event:TradeEvent")[:8]`` and was observed on Solana mainnet. The
decoded prefix below was cross-checked against 51 of 60 single-trade
mainnet transactions: ``token_amount`` and ``is_buy`` equal the trading
user's token balance delta and ``timestamp`` equals the block time. The other
nine were router or aggregator trades whose balances move through
intermediate accounts, so the user-balance check does not apply to them.
Fields after ``ix_name`` and the reserve/fee/creator fields were not
independently cross-checked, so they are not exposed.

Only log lines emitted while Pump.fun is the executing program are accepted.
Any program can write a ``Program data:`` line, so attributing a line by its
bytes alone would let another program inject a forged trade.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from memeradar_application.stream_integrity import RawChainTransaction
from memeradar_domain import Chain, CommitmentState
from memeradar_domain.identities import require_solana_address

from .pump_fun_idl import PUMP_FUN_PROGRAM_ID
from .transport import ProviderSchemaError

PUMP_FUN_TRADE_EVENT_DISCRIMINATOR = hashlib.sha256(b"event:TradeEvent").digest()[:8]
PUMP_FUN_TRADE_EVENT_DECODER_VERSION = "pumpfun-trade-event-log-v1"

_LAMPORTS_PER_SOL = Decimal(1_000_000_000)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INVOKE = re.compile(r"^Program (\S+) invoke \[(\d+)\]$")
_EXIT = re.compile(r"^Program (\S+) (?:success|failed: .*)$")
_DATA_PREFIX = "Program data: "
_TRUNCATED = "Log truncated"

# Offsets of the verified prefix (after the 8-byte discriminator).
_MINT = slice(8, 40)
_AMOUNTS = slice(40, 56)
_IS_BUY = 56
_USER = slice(57, 89)
_TIMESTAMP = slice(89, 97)
_VIRTUAL_RESERVES = slice(97, 113)
_IX_NAME_LENGTH_OFFSET = 258
_MAX_IX_NAME_LENGTH = 64


@dataclass(frozen=True, slots=True)
class PumpFunTradeEvent:
    """One decoded bonding-curve trade in raw on-chain units.

    ``executed_price`` is the trade's own SOL-per-token ratio (executed
    semantics). ``market_reference_price`` is the post-trade bonding-curve
    virtual reserve ratio (market semantics). They are different quantities
    and must not be substituted for one another.
    """

    mint: str
    user: str
    is_buy: bool
    sol_amount_lamports: int
    token_amount_raw: int
    occurred_at: datetime
    virtual_sol_reserves: int
    virtual_token_reserves: int
    ix_name: str
    log_index: int

    @property
    def executed_price(self) -> Decimal | None:
        """Lamports per raw token unit actually paid or received."""

        if self.token_amount_raw <= 0:
            return None
        return Decimal(self.sol_amount_lamports) / Decimal(self.token_amount_raw)

    @property
    def market_reference_price(self) -> Decimal | None:
        """Lamports per raw token unit implied by the curve's virtual reserves."""

        if self.virtual_token_reserves <= 0:
            return None
        return Decimal(self.virtual_sol_reserves) / Decimal(self.virtual_token_reserves)

    def to_payload(self) -> dict[str, object]:
        """Normalized, JSON-safe payload with explicit price semantics."""

        executed = self.executed_price
        reference = self.market_reference_price
        quote_amount_sol = Decimal(self.sol_amount_lamports) / _LAMPORTS_PER_SOL
        return {
            "event_type": "trade_event",
            "protocol": "pump.fun",
            "program_id": PUMP_FUN_PROGRAM_ID,
            "mint_address": self.mint,
            "side": "buy" if self.is_buy else "sell",
            "trader_wallet": self.user,
            "buyer_wallet": self.user if self.is_buy else None,
            "seller_wallet": None if self.is_buy else self.user,
            "quote_amount_lamports": self.sol_amount_lamports,
            # Feature engines read ``quote_amount`` (SOL) for flow and
            # ``market_price`` for returns. The market price is the curve
            # reference, never the trade's executed price.
            "quote_amount": str(quote_amount_sol),
            "market_price": None if reference is None else str(reference),
            "token_amount_raw": self.token_amount_raw,
            "executed_price_lamports_per_raw_token": None if executed is None else str(executed),
            "market_reference_price_lamports_per_raw_token": (
                None if reference is None else str(reference)
            ),
            "virtual_sol_reserves": self.virtual_sol_reserves,
            "virtual_token_reserves": self.virtual_token_reserves,
            "instruction_name": self.ix_name,
            "log_index": self.log_index,
            "decoder_version": PUMP_FUN_TRADE_EVENT_DECODER_VERSION,
        }


@dataclass(frozen=True, slots=True)
class PumpFunTradeEventExtraction:
    """Decoded trades plus whether the log stream was complete."""

    events: tuple[PumpFunTradeEvent, ...]
    logs_truncated: bool


def _base58(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    leading = len(value) - len(value.lstrip(b"\0"))
    return "1" * leading + encoded


def decode_pump_fun_trade_event(raw: bytes, *, log_index: int = 0) -> PumpFunTradeEvent:
    """Decode one TradeEvent payload, failing closed on any layout mismatch."""

    if raw[:8] != PUMP_FUN_TRADE_EVENT_DISCRIMINATOR:
        raise ProviderSchemaError("payload is not a Pump.fun TradeEvent")
    if len(raw) < _IX_NAME_LENGTH_OFFSET + 4:
        raise ProviderSchemaError("Pump.fun TradeEvent payload is shorter than verified layout")
    is_buy_byte = raw[_IS_BUY]
    if is_buy_byte not in (0, 1):
        raise ProviderSchemaError("Pump.fun TradeEvent is_buy flag is not boolean")
    (name_length,) = struct.unpack(
        "<I", raw[_IX_NAME_LENGTH_OFFSET : _IX_NAME_LENGTH_OFFSET + 4]
    )
    name_start = _IX_NAME_LENGTH_OFFSET + 4
    if name_length > _MAX_IX_NAME_LENGTH or len(raw) < name_start + name_length:
        raise ProviderSchemaError("Pump.fun TradeEvent instruction name is out of bounds")
    try:
        ix_name = raw[name_start : name_start + name_length].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProviderSchemaError("Pump.fun TradeEvent instruction name is not ASCII") from exc
    sol_amount, token_amount = struct.unpack("<QQ", raw[_AMOUNTS])
    (timestamp,) = struct.unpack("<q", raw[_TIMESTAMP])
    virtual_sol, virtual_token = struct.unpack("<QQ", raw[_VIRTUAL_RESERVES])
    if timestamp <= 0:
        raise ProviderSchemaError("Pump.fun TradeEvent timestamp is not positive")
    try:
        mint = require_solana_address(_base58(raw[_MINT]), "mint")
        user = require_solana_address(_base58(raw[_USER]), "user")
    except ValueError as exc:
        raise ProviderSchemaError("Pump.fun TradeEvent address is invalid") from exc
    return PumpFunTradeEvent(
        mint=mint,
        user=user,
        is_buy=bool(is_buy_byte),
        sol_amount_lamports=sol_amount,
        token_amount_raw=token_amount,
        occurred_at=datetime.fromtimestamp(timestamp, UTC),
        virtual_sol_reserves=virtual_sol,
        virtual_token_reserves=virtual_token,
        ix_name=ix_name,
        log_index=log_index,
    )


_INSTRUCTION_LOG_PREFIX = "Program log: Instruction: "


def _program_log_lines(logs: Sequence[str]) -> Iterator[tuple[int, str, str | None]]:
    """Yield ``(index, line, executing_program)`` while tracking the invoke stack.

    Invoke, success and failure lines themselves are consumed. A ``Log
    truncated`` line is yielded with the program that was executing.
    """

    if isinstance(logs, str | bytes | bytearray):
        raise TypeError("logs must be a sequence of log lines")
    stack: list[str] = []
    for index, line in enumerate(logs):
        if not isinstance(line, str):
            raise ProviderSchemaError("log line was not text")
        invoked = _INVOKE.match(line)
        if invoked is not None:
            depth = int(invoked.group(2))
            # Depth is 1-based; trim any frames left by a truncated exit.
            del stack[depth - 1 :]
            stack.append(invoked.group(1))
            continue
        exited = _EXIT.match(line)
        if exited is not None:
            if stack and stack[-1] == exited.group(1):
                stack.pop()
            continue
        yield index, line, stack[-1] if stack else None


def pump_fun_logged_instructions(
    logs: Sequence[str],
    *,
    program_id: str = PUMP_FUN_PROGRAM_ID,
) -> tuple[str, ...]:
    """Instruction names Anchor logged while ``program_id`` was executing.

    Other programs log similar names (for example the associated token
    program's ``CreateIdempotent``), so substring matches over the whole log
    misclassify ordinary trades as launches.
    """

    return tuple(
        line[len(_INSTRUCTION_LOG_PREFIX) :].strip()
        for _, line, executing in _program_log_lines(logs)
        if executing == program_id and line.startswith(_INSTRUCTION_LOG_PREFIX)
    )


def extract_pump_fun_trade_events(
    logs: Sequence[str],
    *,
    program_id: str = PUMP_FUN_PROGRAM_ID,
) -> PumpFunTradeEventExtraction:
    """Extract TradeEvents emitted while ``program_id`` is the executing program.

    The same function serves live ``logsSubscribe`` notifications and
    backfilled ``meta.logMessages`` so both paths share one decoder.
    """

    events: list[PumpFunTradeEvent] = []
    truncated = False
    for index, line, executing in _program_log_lines(logs):
        if line.startswith(_TRUNCATED):
            truncated = True
            continue
        if not line.startswith(_DATA_PREFIX) or executing != program_id:
            continue
        try:
            raw = base64.b64decode(line[len(_DATA_PREFIX) :], validate=True)
        except (binascii.Error, ValueError):
            continue
        if raw[:8] != PUMP_FUN_TRADE_EVENT_DISCRIMINATOR:
            continue
        events.append(decode_pump_fun_trade_event(raw, log_index=index))
    return PumpFunTradeEventExtraction(events=tuple(events), logs_truncated=truncated)


def trade_events_to_raw_transactions(
    events: Sequence[PumpFunTradeEvent],
    *,
    signature: str,
    slot: int,
    observed_at: datetime,
    ingested_at: datetime,
    commitment: CommitmentState,
    transport: str,
    program_id: str = PUMP_FUN_PROGRAM_ID,
    connection_id: str | None = None,
    reconnect_reason: str | None = None,
) -> tuple[RawChainTransaction, ...]:
    """Wrap decoded trades as canonical raw events keyed by (program, event tag)."""

    raw: list[RawChainTransaction] = []
    for event in events:
        payload = event.to_payload()
        payload.update(
            {
                "provider_observed_at": observed_at.isoformat(),
                "memeradar_ingested_at": ingested_at.isoformat(),
                "event_time_source": "trade_event_timestamp",
                "event_time_quality": "EXACT",
                "commitment": commitment.value,
            }
        )
        raw.append(
            RawChainTransaction(
                chain=Chain.SOLANA,
                slot=slot,
                signature=signature,
                event_index=event.log_index,
                program_id=program_id,
                discriminator_or_tag=PUMP_FUN_TRADE_EVENT_DISCRIMINATOR,
                payload=payload,
                occurred_at=event.occurred_at,
                observed_at=observed_at,
                ingested_at=ingested_at,
                transport=transport,
                commitment=commitment,
                event_schema_version=2,
                connection_id=connection_id,
                reconnect_reason=reconnect_reason,
            )
        )
    return tuple(raw)


__all__ = [
    "PUMP_FUN_TRADE_EVENT_DECODER_VERSION",
    "PUMP_FUN_TRADE_EVENT_DISCRIMINATOR",
    "PumpFunTradeEvent",
    "PumpFunTradeEventExtraction",
    "decode_pump_fun_trade_event",
    "extract_pump_fun_trade_events",
    "pump_fun_logged_instructions",
    "trade_events_to_raw_transactions",
]
