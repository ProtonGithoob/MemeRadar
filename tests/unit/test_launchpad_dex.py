"""Unit contracts for protocol-local launchpad and DEX event parsing."""

from datetime import UTC, datetime, timedelta

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_providers.launchpad_dex import (
    MeteoraAdapter,
    ParsedProtocolEvent,
    ProtocolVenue,
    PumpFunAdapter,
    PumpSwapAdapter,
    RaydiumAdapter,
)
from memeradar_providers.transport import ProviderSchemaError

NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
SIGNATURE = "1" * 88


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="launchpad-dex-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


@pytest.mark.parametrize(
    ("adapter", "message", "venue", "event_type", "pool_expected"),
    (
        (
            PumpFunAdapter(),
            {
                "event_type": "token_created",
                "signature": SIGNATURE,
                "occurred_at": "2026-08-27T10:59:58Z",
                "data": {"mint": MINT, "token_program": "spl-token"},
            },
            ProtocolVenue.PUMP_FUN,
            "token_created",
            False,
        ),
        (
            PumpSwapAdapter(),
            {
                "type": "pool_created",
                "event_id": "pumpswap-event-1",
                "data": {
                    "baseToken": {"address": MINT},
                    "poolAddress": POOL,
                    "quoteMint": QUOTE,
                },
            },
            ProtocolVenue.PUMP_SWAP,
            "pool_created",
            True,
        ),
        (
            RaydiumAdapter(),
            {
                "instruction": "initialize2",
                "source_id": "raydium-event-1",
                "data": {"base_mint": MINT, "amm_id": POOL, "quote_mint": QUOTE},
            },
            ProtocolVenue.RAYDIUM,
            "initialize2",
            True,
        ),
        (
            MeteoraAdapter(),
            {
                "event_type": "dlmm_pool_created",
                "signature": SIGNATURE,
                "data": {"token_mint": MINT, "pool": POOL, "quoteTokenAddress": QUOTE},
            },
            ProtocolVenue.METEORA,
            "dlmm_pool_created",
            True,
        ),
    ),
)
def test_protocol_adapters_parse_representative_envelopes(
    adapter: object,
    message: object,
    venue: ProtocolVenue,
    event_type: str,
    pool_expected: bool,
) -> None:
    parsed = adapter.parse(message, context())  # type: ignore[attr-defined]

    assert isinstance(parsed, ParsedProtocolEvent)
    assert parsed.venue is venue
    assert parsed.event_type == event_type
    assert parsed.mint_address == MINT
    assert parsed.pool_address == (POOL if pool_expected else None)
    assert parsed.quote_mint == (QUOTE if pool_expected else None)
    assert parsed.observed_at == NOW
    assert parsed.ingested_at == NOW
    assert parsed.source_id.startswith(f"{venue.value}:")


def test_parser_redacts_credential_shaped_nested_payload_values() -> None:
    message = {
        "event_type": "token_created",
        "event_id": "redaction-event",
        "data": {
            "mint": MINT,
            "metadata": {"api_key": "must-not-cross-boundary", "name": "Fixture"},
            "headers": {"authorization": "Bearer must-not-cross-boundary"},
        },
    }

    parsed = PumpFunAdapter().parse(message, context())

    assert "api_key" not in repr(parsed.payload).lower()
    assert "authorization" not in repr(parsed.payload).lower()
    assert "must-not-cross-boundary" not in repr(parsed.payload)
    assert parsed.payload["mint"] == MINT


def test_parser_rejects_unsupported_event_type() -> None:
    with pytest.raises(ProviderSchemaError, match="unsupported"):
        PumpFunAdapter().parse(
            {"event_type": "swap_executed", "data": {"mint": MINT}},
            context(),
        )


def test_parser_rejects_non_solana_identity_and_incomplete_pool() -> None:
    with pytest.raises(ProviderSchemaError, match="mint"):
        RaydiumAdapter().parse(
            {"event_type": "pool_created", "data": {"mint": "not-a-solana-key"}},
            context(),
        )

    with pytest.raises(ProviderSchemaError, match="quote"):
        PumpSwapAdapter().parse(
            {"event_type": "pool_created", "data": {"mint": MINT, "pool": POOL}},
            context(),
        )


def test_parser_rejects_future_or_malformed_event_time() -> None:
    with pytest.raises(ProviderSchemaError, match="timestamp"):
        MeteoraAdapter().parse(
            {
                "event_type": "pool_created",
                "occurred_at": "2026-08-27T11:00:01Z",
                "data": {"mint": MINT, "pool": POOL, "quote_mint": QUOTE},
            },
            context(),
        )

    with pytest.raises(ProviderSchemaError, match="timestamp"):
        MeteoraAdapter().parse(
            {
                "event_type": "pool_created",
                "occurred_at": "not-a-time",
                "data": {"mint": MINT, "pool": POOL, "quote_mint": QUOTE},
            },
            context(),
        )
