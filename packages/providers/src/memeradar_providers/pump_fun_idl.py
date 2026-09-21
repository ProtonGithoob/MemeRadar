"""Pinned, local Pump.fun create instruction schema and Borsh decoder."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from memeradar_domain.identities import require_solana_address

PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_FUN_IDL_REVISION = "81091419e4457566469d4e2a27f64ed84d42419c"
PUMP_FUN_IDL_SHA256 = "ffe966c42f1af41652ee753fe2f1e3f7cd4077d7e6f49faf3138959c8b56064b"
PUMP_FUN_LOCAL_SCHEMA_VERSION = "pumpfun-idl-schema-v1"
PUMP_FUN_PROTOCOL_DRIFT_DETECTED = "PROTOCOL_DRIFT_DETECTED"
PUMP_FUN_IDL_SOURCE = (
    "https://github.com/pump-fun/pump-public-docs/blob/"
    f"{PUMP_FUN_IDL_REVISION}/idl/pump.json"
)
PUMP_FUN_CREATION_DOC_SOURCE = (
    "https://github.com/pump-fun/pump-public-docs/blob/"
    f"{PUMP_FUN_IDL_REVISION}/docs/instructions/COIN_CREATION.md"
)

PUMP_FUN_CREATE_TAG = bytes((24, 30, 200, 40, 5, 28, 7, 119))
PUMP_FUN_CREATE_V2_TAG = bytes((214, 144, 76, 236, 95, 139, 49, 180))
PUMP_FUN_SOL_MINT = "So11111111111111111111111111111111111111112"

PUMP_FUN_CREATE_ACCOUNT_NAMES = (
    "mint",
    "mint_authority",
    "bonding_curve",
    "associated_bonding_curve",
    "global",
    "mpl_token_metadata",
    "metadata",
    "user",
    "system_program",
    "token_program",
    "associated_token_program",
    "rent",
    "event_authority",
    "program",
)
PUMP_FUN_CREATE_V2_ACCOUNT_NAMES = (
    "mint",
    "mint_authority",
    "bonding_curve",
    "associated_bonding_curve",
    "global",
    "user",
    "system_program",
    "token_program",
    "associated_token_program",
    "mayhem_program_id",
    "global_params",
    "sol_vault",
    "mayhem_state",
    "mayhem_token_vault",
    "event_authority",
    "program",
)
PUMP_FUN_CREATE_V2_REMAINING_ACCOUNT_NAMES = (
    "quote_mint",
    "associated_quote_bonding_curve",
    "quote_token_program",
)


@dataclass(frozen=True, slots=True)
class _InstructionSchema:
    discriminator: bytes
    accounts: tuple[str, ...]
    arguments: tuple[str, ...]


_SCHEMAS: Mapping[str, _InstructionSchema] = {
    "create": _InstructionSchema(
        discriminator=PUMP_FUN_CREATE_TAG,
        accounts=PUMP_FUN_CREATE_ACCOUNT_NAMES,
        arguments=("name", "symbol", "uri", "creator"),
    ),
    "create_v2": _InstructionSchema(
        discriminator=PUMP_FUN_CREATE_V2_TAG,
        accounts=PUMP_FUN_CREATE_V2_ACCOUNT_NAMES,
        arguments=(
            "name",
            "symbol",
            "uri",
            "creator",
            "is_mayhem_mode",
            "is_cashback_enabled",
            "creator_fee_bps",
            "is_holder_reward",
        ),
    ),
}


class _BorshReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    @property
    def remaining(self) -> int:
        return len(self._data) - self._offset

    def _take(self, size: int, field: str) -> bytes:
        if self.remaining < size:
            raise ValueError(f"truncated {field}")
        start = self._offset
        self._offset += size
        return self._data[start : start + size]

    def string(self, field: str) -> str:
        size = int.from_bytes(self._take(4, f"{field} length"), "little")
        if size > 16_384:
            raise ValueError(f"{field} length is too large")
        try:
            return self._take(size, field).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{field} was not valid UTF-8") from exc

    def pubkey(self, field: str) -> str:
        return _base58_encode(self._take(32, field))

    def boolean(self, field: str) -> bool:
        value = self._take(1, field)[0]
        if value not in (0, 1):
            raise ValueError(f"{field} was not a bool")
        return bool(value)

    def u64(self, field: str) -> int:
        return int.from_bytes(self._take(8, field), "little")


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + (encoded or "")


def pump_fun_protocol_pin_status(
    *,
    upstream_revision: str,
    idl_sha256: str,
    local_schema_version: str,
) -> str:
    """Compare a supplied pin with the checked-in decoder pin."""

    if (
        upstream_revision != PUMP_FUN_IDL_REVISION
        or idl_sha256 != PUMP_FUN_IDL_SHA256
        or local_schema_version != PUMP_FUN_LOCAL_SCHEMA_VERSION
    ):
        return PUMP_FUN_PROTOCOL_DRIFT_DETECTED
    return "OK"


def _account_map(schema: _InstructionSchema, accounts: Sequence[str]) -> dict[str, str]:
    if len(accounts) < len(schema.accounts):
        raise ValueError(
            f"{schema.accounts[0]} instruction requires {len(schema.accounts)} accounts"
        )
    result: dict[str, str] = {}
    for index, name in enumerate(schema.accounts):
        try:
            result[name] = require_solana_address(accounts[index], name)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} account was invalid") from exc
    return result


def _quote_fields(name: str, accounts: Sequence[str]) -> tuple[str | None, str]:
    if name != "create_v2":
        return None, "SOL"
    remaining = len(accounts) - len(PUMP_FUN_CREATE_V2_ACCOUNT_NAMES)
    if remaining not in (0, len(PUMP_FUN_CREATE_V2_REMAINING_ACCOUNT_NAMES)):
        raise ValueError("quote remaining accounts must contain all three accounts")
    if remaining == 0:
        return None, "SOL"
    quote_mint = require_solana_address(
        accounts[len(PUMP_FUN_CREATE_V2_ACCOUNT_NAMES)], "quote_mint"
    )
    return quote_mint, "SOL" if quote_mint == PUMP_FUN_SOL_MINT else "TOKEN"


def decode_pump_fun_instruction(
    instruction_type: str,
    data: bytes,
    accounts: Sequence[str],
) -> Mapping[str, object]:
    """Decode the checked-in IDL subset used by Pump.fun launch discovery."""

    name = instruction_type.strip().lower()
    schema = _SCHEMAS.get(name)
    if schema is None:
        raise ValueError(f"unsupported Pump.fun IDL instruction: {instruction_type}")
    if not isinstance(data, bytes):
        raise TypeError("instruction data must be bytes")
    if len(data) < len(schema.discriminator) or data[:8] != schema.discriminator:
        raise ValueError(f"{name} discriminator did not match the pinned IDL")
    if isinstance(accounts, str | bytes | bytearray):
        raise TypeError("accounts must be a sequence of addresses")

    account_map = _account_map(schema, accounts)
    reader = _BorshReader(data[8:])
    values: dict[str, object] = {}
    values["name"] = reader.string("name")
    values["symbol"] = reader.string("symbol")
    values["uri"] = reader.string("uri")
    values["creator"] = reader.pubkey("creator")
    values["is_mayhem_mode"] = reader.boolean("is_mayhem_mode") if name == "create_v2" else False

    optional_presence: dict[str, bool] = {}
    if name == "create_v2":
        for field, reader_method, default in (
            ("is_cashback_enabled", reader.boolean, False),
            ("creator_fee_bps", reader.u64, 0),
            ("is_holder_reward", reader.boolean, False),
        ):
            if reader.remaining:
                values[field] = reader_method(field)
                optional_presence[field] = True
            else:
                values[field] = default
                optional_presence[field] = False
    else:
        values.update(
            is_cashback_enabled=False,
            creator_fee_bps=0,
            is_holder_reward=False,
        )
        optional_presence["is_holder_reward"] = False
    if reader.remaining:
        raise ValueError(f"trailing bytes after {name} arguments")

    quote_mint, quote_semantics = _quote_fields(name, accounts)
    result: dict[str, object] = {
        **account_map,
        **values,
        "mint_address": account_map["mint"],
        "instruction_type": name,
        "protocol_event_type": "launch",
        "is_holder_reward_present": optional_presence["is_holder_reward"],
        "quote_mint": quote_mint,
        "quote_mint_semantics": quote_semantics,
        "idl_source": PUMP_FUN_IDL_SOURCE,
        "idl_revision": PUMP_FUN_IDL_REVISION,
        "idl_sha256": PUMP_FUN_IDL_SHA256,
        "local_schema_version": PUMP_FUN_LOCAL_SCHEMA_VERSION,
        "protocol_pin_status": pump_fun_protocol_pin_status(
            upstream_revision=PUMP_FUN_IDL_REVISION,
            idl_sha256=PUMP_FUN_IDL_SHA256,
            local_schema_version=PUMP_FUN_LOCAL_SCHEMA_VERSION,
        ),
    }
    return result


__all__ = [
    "PUMP_FUN_CREATE_ACCOUNT_NAMES",
    "PUMP_FUN_CREATE_TAG",
    "PUMP_FUN_CREATE_V2_ACCOUNT_NAMES",
    "PUMP_FUN_CREATE_V2_TAG",
    "PUMP_FUN_CREATE_V2_REMAINING_ACCOUNT_NAMES",
    "PUMP_FUN_CREATION_DOC_SOURCE",
    "PUMP_FUN_IDL_REVISION",
    "PUMP_FUN_IDL_SHA256",
    "PUMP_FUN_IDL_SOURCE",
    "PUMP_FUN_LOCAL_SCHEMA_VERSION",
    "PUMP_FUN_PROGRAM_ID",
    "PUMP_FUN_PROTOCOL_DRIFT_DETECTED",
    "PUMP_FUN_SOL_MINT",
    "decode_pump_fun_instruction",
    "pump_fun_protocol_pin_status",
]
