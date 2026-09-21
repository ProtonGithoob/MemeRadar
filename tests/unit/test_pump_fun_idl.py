"""Authoritative Pump.fun create/create_v2 IDL fixture contracts."""

import struct

import pytest

from memeradar_providers.pump_fun_idl import (
    PUMP_FUN_CREATE_ACCOUNT_NAMES,
    PUMP_FUN_CREATE_TAG,
    PUMP_FUN_CREATE_V2_ACCOUNT_NAMES,
    PUMP_FUN_CREATE_V2_TAG,
    PUMP_FUN_IDL_REVISION,
    PUMP_FUN_IDL_SHA256,
    PUMP_FUN_LOCAL_SCHEMA_VERSION,
    PUMP_FUN_PROTOCOL_DRIFT_DETECTED,
    decode_pump_fun_instruction,
    pump_fun_protocol_pin_status,
)

MINT = "DDvnac6RRxdcKWPpumhJ1HJTz3vGVkLD8fFGcVNCpump"
USER = "2J2rtMBRLxAbFkSLgrsuSNN8N5KMTJVaRTdnGfbZ5Vjw"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
CREATOR = "11111111111111111111111111111111"


def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in value:
        number = number * 58 + alphabet.index(char)
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + decoded


def _string(value: str) -> bytes:
    raw = value.encode()
    return struct.pack("<I", len(raw)) + raw


def _create_data() -> bytes:
    return PUMP_FUN_CREATE_TAG + _string("Legacy Name") + _string("LEG") + _string(
        "https://example.test/legacy.json"
    ) + _base58_decode(CREATOR)


def _create_v2_data(*, trailing: bool = True) -> bytes:
    data = (
        PUMP_FUN_CREATE_V2_TAG
        + _string("IDL Coin")
        + _string("IDL")
        + _string("https://example.test/idl.json")
        + _base58_decode(CREATOR)
        + b"\x01"
    )
    if trailing:
        data += b"\x00" + struct.pack("<Q", 125) + b"\x01"
    return data


def _legacy_accounts() -> list[str]:
    return [MINT, SOL, SOL, SOL, SOL, SOL, SOL, USER, SOL, SOL, SOL, SOL, SOL, SOL]


def _v2_accounts(*, quote: str | None = None) -> list[str]:
    accounts = [
        MINT,
        SOL,
        SOL,
        SOL,
        SOL,
        USER,
        "11111111111111111111111111111111",
        TOKEN_2022,
        SOL,
        SOL,
        SOL,
        SOL,
        SOL,
        SOL,
        SOL,
        SOL,
    ]
    if quote is not None:
        accounts.extend([quote, SOL, TOKEN_2022])
    return accounts


def test_authoritative_idl_pin_and_account_layouts() -> None:
    assert PUMP_FUN_CREATE_ACCOUNT_NAMES == (
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
    assert PUMP_FUN_CREATE_V2_ACCOUNT_NAMES[0] == "mint"
    assert PUMP_FUN_CREATE_V2_ACCOUNT_NAMES[5] == "user"
    assert PUMP_FUN_CREATE_V2_ACCOUNT_NAMES[7] == "token_program"
    assert len(PUMP_FUN_IDL_REVISION) == 40
    assert len(PUMP_FUN_IDL_SHA256) == 64
    assert PUMP_FUN_LOCAL_SCHEMA_VERSION


def test_create_decodes_legacy_launch_fields_and_sol_quote_semantics() -> None:
    decoded = decode_pump_fun_instruction("create", _create_data(), _legacy_accounts())

    assert decoded["instruction_type"] == "create"
    assert decoded["protocol_event_type"] == "launch"
    assert decoded["mint"] == MINT
    assert decoded["user"] == USER
    assert decoded["creator"] == CREATOR
    assert decoded["name"] == "Legacy Name"
    assert decoded["symbol"] == "LEG"
    assert decoded["uri"] == "https://example.test/legacy.json"
    assert decoded["is_mayhem_mode"] is False
    assert decoded["is_holder_reward"] is False
    assert decoded["is_holder_reward_present"] is False
    assert decoded["quote_mint"] is None
    assert decoded["quote_mint_semantics"] == "SOL"


def test_create_v2_uses_official_indexes_and_instruction_creator() -> None:
    decoded = decode_pump_fun_instruction(
        "create_v2", _create_v2_data(), _v2_accounts(quote=USDC)
    )

    assert decoded["mint"] == MINT
    assert decoded["user"] == USER
    assert decoded["token_program"] == TOKEN_2022
    assert decoded["creator"] == CREATOR
    assert decoded["creator"] != decoded["token_program"]
    assert decoded["name"] == "IDL Coin"
    assert decoded["symbol"] == "IDL"
    assert decoded["uri"] == "https://example.test/idl.json"
    assert decoded["is_mayhem_mode"] is True
    assert decoded["is_holder_reward"] is True
    assert decoded["is_holder_reward_present"] is True
    assert decoded["quote_mint"] == USDC
    assert decoded["quote_mint_semantics"] == "TOKEN"
    assert decoded["creator_fee_bps"] == 125


def test_create_v2_omitted_trailing_arguments_are_protocol_defaults() -> None:
    decoded = decode_pump_fun_instruction(
        "create_v2", _create_v2_data(trailing=False), _v2_accounts()
    )

    assert decoded["is_mayhem_mode"] is True
    assert decoded["is_cashback_enabled"] is False
    assert decoded["creator_fee_bps"] == 0
    assert decoded["is_holder_reward"] is False
    assert decoded["is_holder_reward_present"] is False
    assert decoded["quote_mint_semantics"] == "SOL"


def test_pin_mismatch_reports_drift_without_promoting_decoder() -> None:
    assert (
        pump_fun_protocol_pin_status(
            upstream_revision=PUMP_FUN_IDL_REVISION,
            idl_sha256=PUMP_FUN_IDL_SHA256,
            local_schema_version=PUMP_FUN_LOCAL_SCHEMA_VERSION,
        )
        == "OK"
    )
    assert (
        pump_fun_protocol_pin_status(
            upstream_revision="0" * 40,
            idl_sha256=PUMP_FUN_IDL_SHA256,
            local_schema_version=PUMP_FUN_LOCAL_SCHEMA_VERSION,
        )
        == PUMP_FUN_PROTOCOL_DRIFT_DETECTED
    )


@pytest.mark.parametrize(
    "instruction_type, data, accounts, message",
    [
        ("create_v2", PUMP_FUN_CREATE_TAG, _v2_accounts(), "discriminator"),
        ("create_v2", _create_v2_data() + b"\x00", _v2_accounts(), "trailing"),
        ("create_v2", _create_v2_data()[:-2], _v2_accounts(), "truncated"),
    ],
)
def test_idl_decoder_rejects_untrusted_or_malformed_input(
    instruction_type: str, data: bytes, accounts: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        decode_pump_fun_instruction(instruction_type, data, accounts)


def test_create_v2_rejects_partial_quote_remaining_accounts() -> None:
    with pytest.raises(ValueError, match="quote"):
        decode_pump_fun_instruction("create_v2", _create_v2_data(), _v2_accounts() + [USDC])
