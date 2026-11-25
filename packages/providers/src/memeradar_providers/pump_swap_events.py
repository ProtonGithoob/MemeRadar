"""PumpSwap (pump_amm) BuyEvent/SellEvent decoding from AMM-context logs.

Identity: program ``pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`` plus the
Anchor event discriminators from the official IDL (pump-public-docs
``639b87f`` ``idl/pump_amm.json``, sha256 ``b7d8c57a…b89b``).  Only a
``Program data:`` line emitted while pump_amm itself is executing counts.

Only the fixed prefix is read (timestamp, 13 u64 fields, pool, user); later
fields have grown across IDL revisions.  Amounts are raw units; base is the
token, quote is the pool's quote asset (WSOL for graduated Pump.fun tokens --
verified per transaction by the caller against balance deltas, not assumed).
"""

from __future__ import annotations

import base64
import binascii
import struct
from collections.abc import Sequence
from dataclasses import dataclass

from .pump_fun_events import _base58, _program_log_lines
from .transport import ProviderSchemaError

PUMP_SWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PUMP_SWAP_IDL_REVISION = "639b87fb45c3adeffa6f7c4a1bf0cb85e392bf22"
PUMP_SWAP_BUY_EVENT_DISCRIMINATOR = bytes.fromhex("67f4521f2cf57777")
PUMP_SWAP_SELL_EVENT_DISCRIMINATOR = bytes.fromhex("3e2f370aa503dc2a")
PUMP_SWAP_EVENT_DECODER_VERSION = "pump-swap-event-v1"
_PREFIX = 8 + 8 + 13 * 8 + 32 + 32
_DATA = "Program data: "


@dataclass(frozen=True, slots=True)
class PumpSwapTradeEvent:
    is_buy: bool
    timestamp: int
    base_amount: int  # tokens out (buy) or in (sell)
    quote_amount: int  # user side: paid incl. fees (buy) / received net (sell)
    pool_quote_amount: int  # pool side: quote into (buy) / out of (sell) the pool
    pool_base_reserves: int  # BEFORE the trade (verified against balances)
    pool_quote_reserves: int

    @property
    def post_trade_reserves(self) -> tuple[int, int]:
        """(base, quote) pool reserves after this trade."""

        if self.is_buy:
            return (
                self.pool_base_reserves - self.base_amount,
                self.pool_quote_reserves + self.pool_quote_amount,
            )
        return (
            self.pool_base_reserves + self.base_amount,
            self.pool_quote_reserves - self.pool_quote_amount,
        )
    pool: str
    user: str
    log_index: int


def decode_pump_swap_event(raw: bytes, *, log_index: int = 0) -> PumpSwapTradeEvent:
    discriminator = raw[:8]
    if discriminator not in {PUMP_SWAP_BUY_EVENT_DISCRIMINATOR, PUMP_SWAP_SELL_EVENT_DISCRIMINATOR}:
        raise ProviderSchemaError("not a PumpSwap trade event")
    if len(raw) < _PREFIX:
        raise ProviderSchemaError("PumpSwap trade event was truncated")
    timestamp = struct.unpack_from("<q", raw, 8)[0]
    values = struct.unpack_from("<13Q", raw, 16)
    is_buy = discriminator == PUMP_SWAP_BUY_EVENT_DISCRIMINATOR
    # Field order (both events): [0] base amount, [1] limit, [2..3] user
    # reserves, [4] pool base reserves, [5] pool quote reserves, [6] quote
    # amount, ..., [12] user_quote_amount_in (buy) / user_quote_amount_out (sell).
    # Reserves are pre-trade: verified on a mainnet buy where event reserves
    # equal the pool's post-trade token balance plus the base amount.
    pool_offset = 16 + 13 * 8
    return PumpSwapTradeEvent(
        is_buy=is_buy,
        timestamp=timestamp,
        base_amount=values[0],
        quote_amount=values[12],
        pool_quote_amount=values[6],
        pool_base_reserves=values[4],
        pool_quote_reserves=values[5],
        pool=_base58(raw[pool_offset : pool_offset + 32]),
        user=_base58(raw[pool_offset + 32 : pool_offset + 64]),
        log_index=log_index,
    )


def extract_pump_swap_events(logs: Sequence[str]) -> tuple[PumpSwapTradeEvent, ...]:
    events: list[PumpSwapTradeEvent] = []
    for index, line, program in _program_log_lines(logs):
        if program != PUMP_SWAP_PROGRAM_ID or not line.startswith(_DATA):
            continue
        try:
            raw = base64.b64decode(line[len(_DATA):], validate=True)
        except (binascii.Error, ValueError):
            continue
        if raw[:8] in {PUMP_SWAP_BUY_EVENT_DISCRIMINATOR, PUMP_SWAP_SELL_EVENT_DISCRIMINATOR}:
            events.append(decode_pump_swap_event(raw, log_index=index))
    return tuple(events)


__all__ = [
    "PUMP_SWAP_BUY_EVENT_DISCRIMINATOR",
    "PUMP_SWAP_EVENT_DECODER_VERSION",
    "PUMP_SWAP_IDL_REVISION",
    "PUMP_SWAP_PROGRAM_ID",
    "PUMP_SWAP_SELL_EVENT_DISCRIMINATOR",
    "PumpSwapTradeEvent",
    "decode_pump_swap_event",
    "extract_pump_swap_events",
]
