"""Operator commands that register manual buys/sells for exit monitoring.

These commands record what the operator already did on their own wallet.  They
never sign, route or execute anything; ``MANUAL_EXECUTION`` stays false.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from memeradar_domain import Observation, Provenance, QualityState
from memeradar_domain.common import ensure_utc
from memeradar_domain.identities import require_solana_address

MANUAL_POSITION_PARSER_VERSION = "manual-position-v1"
MANUAL_POSITION_KIND = "manual.position"
DEFAULT_POSITION_SIZE_USD = Decimal("50")
_MAX_SIZE_USD = Decimal("100000")


class CommandKind(str, Enum):
    BOUGHT = "BOUGHT"
    SOLD = "SOLD"
    POSITIONS = "POSITIONS"
    HELP = "HELP"


@dataclass(frozen=True, slots=True)
class OperatorCommand:
    kind: CommandKind
    mint: str | None = None
    entry_price_usd: Decimal | None = None
    size_usd: Decimal = DEFAULT_POSITION_SIZE_USD


class CommandError(ValueError):
    """User-facing parse error; message is safe to echo back."""


HELP_TEXT = (
    "MemeRadar manual position commands (record only, nothing is traded):\n"
    "/bought <mint> [entry_price_usd] [size_usd]\n"
    "/sold <mint>\n"
    "/positions"
)


def _positive_decimal(value: str, name: str) -> Decimal:
    try:
        parsed = Decimal(value.replace(",", "").lstrip("$"))
    except InvalidOperation:
        raise CommandError(f"{name} must be a number") from None
    if not parsed.is_finite() or parsed <= 0:
        raise CommandError(f"{name} must be positive")
    return parsed


def parse_command(text: str) -> OperatorCommand | None:
    """Parse one Telegram message; non-commands return ``None``."""

    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return None
    verb = parts[0][1:].split("@", 1)[0].lower()
    args = parts[1:]
    if verb in {"help", "start"}:
        return OperatorCommand(CommandKind.HELP)
    if verb == "positions":
        return OperatorCommand(CommandKind.POSITIONS)
    if verb not in {"bought", "buy", "sold", "sell"}:
        return None
    if not args:
        raise CommandError("mint is required")
    try:
        mint = require_solana_address(args[0], "mint")
    except (TypeError, ValueError):
        raise CommandError("mint must be a Solana address") from None
    if verb in {"sold", "sell"}:
        return OperatorCommand(CommandKind.SOLD, mint=mint)
    if len(args) > 3:
        raise CommandError("usage: /bought <mint> [entry_price_usd] [size_usd]")
    price = _positive_decimal(args[1], "entry_price_usd") if len(args) > 1 else None
    size = _positive_decimal(args[2], "size_usd") if len(args) > 2 else DEFAULT_POSITION_SIZE_USD
    if size > _MAX_SIZE_USD:
        raise CommandError("size_usd is above the bounded maximum")
    return OperatorCommand(CommandKind.BOUGHT, mint=mint, entry_price_usd=price, size_usd=size)


def position_id_for(mint: str, opened_at: datetime) -> str:
    return f"{mint[:8]}-{int(ensure_utc(opened_at, 'opened_at').timestamp())}"


def position_observation(
    *,
    event: str,
    position_id: str,
    mint: str,
    at: datetime,
    source: str,
    entry_price_usd: Decimal | None = None,
    size_usd: Decimal | None = None,
) -> Observation:
    """Append-only position lifecycle record (OPEN/CLOSE)."""

    if event not in {"OPEN", "CLOSE"}:
        raise ValueError("event must be OPEN or CLOSE")
    observed = ensure_utc(at, "at")
    source_id = f"manual:position:{position_id}:{event.lower()}"
    payload: dict[str, object] = {
        "event": event,
        "position_id": position_id,
        "mint": require_solana_address(mint, "mint"),
        "source": source,
        "execution_enabled": False,
    }
    if event == "OPEN":
        payload["size_usd"] = str(size_usd or DEFAULT_POSITION_SIZE_USD)
        payload["entry_price_usd"] = None if entry_price_usd is None else str(entry_price_usd)
        payload["entry_price_semantics"] = (
            "MARKET_REFERENCE_AT_REGISTRATION" if entry_price_usd is None else "OPERATOR_EXECUTED"
        )
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:{MANUAL_POSITION_KIND}:{source_id}"),
        kind=MANUAL_POSITION_KIND,
        provenance=Provenance(
            provider="memeradar.operator",
            source_id=source_id,
            observed_at=observed,
            parser_version=MANUAL_POSITION_PARSER_VERSION,
        ),
        occurred_at=observed,
        observed_at=observed,
        ingested_at=observed,
        quality_state=QualityState.FRESH,
        normalized_payload=payload,
    )


__all__ = [
    "DEFAULT_POSITION_SIZE_USD",
    "HELP_TEXT",
    "MANUAL_POSITION_KIND",
    "CommandError",
    "CommandKind",
    "OperatorCommand",
    "parse_command",
    "position_id_for",
    "position_observation",
]
