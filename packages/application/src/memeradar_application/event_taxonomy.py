"""Provider-independent transaction taxonomy for evidence classification."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum


class TransactionEventType(str, Enum):
    DEX_SWAP_BUY = "DEX_SWAP_BUY"
    DEX_SWAP_SELL = "DEX_SWAP_SELL"
    CEX_INFLOW = "CEX_INFLOW"
    CEX_OUTFLOW = "CEX_OUTFLOW"
    LP_ADD = "LP_ADD"
    LP_REMOVE = "LP_REMOVE"
    BRIDGE_IN = "BRIDGE_IN"
    BRIDGE_OUT = "BRIDGE_OUT"
    TOKEN_LAUNCH = "TOKEN_LAUNCH"
    TOKEN_MIGRATION = "TOKEN_MIGRATION"
    WHALE_TRANSFER = "WHALE_TRANSFER"
    SMART_MONEY_ENTRY = "SMART_MONEY_ENTRY"
    SMART_MONEY_EXIT = "SMART_MONEY_EXIT"
    MEV_ACTIVITY = "MEV_ACTIVITY"
    DEVELOPER_SELL = "DEVELOPER_SELL"
    UNKNOWN = "UNKNOWN"


_DIRECT = {value.value: value for value in TransactionEventType}
_ALIASES = {
    "SWAP_BUY": TransactionEventType.DEX_SWAP_BUY,
    "BUY": TransactionEventType.DEX_SWAP_BUY,
    "SWAP_SELL": TransactionEventType.DEX_SWAP_SELL,
    "SELL": TransactionEventType.DEX_SWAP_SELL,
    "SWAP": TransactionEventType.UNKNOWN,
    "LIQUIDITY_ADD": TransactionEventType.LP_ADD,
    "LIQUIDITY_REMOVE": TransactionEventType.LP_REMOVE,
    "BRIDGE": TransactionEventType.BRIDGE_IN,
    "MEV_ARBITRAGE": TransactionEventType.MEV_ACTIVITY,
    "WHALE": TransactionEventType.WHALE_TRANSFER,
}


def classify_transaction(payload: Mapping[str, object]) -> tuple[TransactionEventType, str]:
    """Classify explicit transaction labels without guessing from descriptions."""

    for key in ("canonical_event_type", "event_taxonomy", "classification"):
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
            direct = _DIRECT.get(normalized) or _ALIASES.get(normalized)
            if direct is not None and direct is not TransactionEventType.UNKNOWN:
                return direct, "EXPLICIT"
    raw_activity = payload.get("activity_kind", payload.get("activity_type"))
    activity = (
        raw_activity.strip().upper().replace("-", "_").replace(" ", "_")
        if isinstance(raw_activity, str)
        else ""
    )
    side = payload.get("side", payload.get("action"))
    normalized_side = side.strip().upper() if isinstance(side, str) else ""
    if activity in {"SWAP", "DEX_SWAP"}:
        if normalized_side in {"BUY", "BOUGHT", "IN"}:
            return TransactionEventType.DEX_SWAP_BUY, "DERIVED_EXPLICIT_SIDE"
        if normalized_side in {"SELL", "SOLD", "OUT"}:
            return TransactionEventType.DEX_SWAP_SELL, "DERIVED_EXPLICIT_SIDE"
    direct = _DIRECT.get(activity) or _ALIASES.get(activity)
    if direct is not None and direct is not TransactionEventType.UNKNOWN:
        return direct, "DERIVED_EXPLICIT_ACTIVITY"
    return TransactionEventType.UNKNOWN, "UNKNOWN"


__all__ = ["TransactionEventType", "classify_transaction"]
