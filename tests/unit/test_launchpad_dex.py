"""Unit contracts for protocol-local launchpad and DEX event parsing."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from memeradar_application.provider_contracts import ProviderRequestContext, QuoteRequest
from memeradar_domain import QualityState
from memeradar_providers.launchpad_dex import (
    LAUNCHPAD_PARSER_VERSION,
    PROTOCOL_EVENT_SCHEMA_VERSION,
    RICH_LAUNCHPAD_PARSER_VERSION,
    MeteoraAdapter,
    ParsedProtocolEvent,
    ProtocolEventOrigin,
    ProtocolEventType,
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
QUOTE_POOL = "Vote111111111111111111111111111111111111111"
SIGNATURE = "1" * 88


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="launchpad-dex-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=10),
    )


def test_raydium_pool_parser_and_cpmm_quote_keep_liquidity_evidence_explicit() -> None:
    adapter = RaydiumAdapter()
    pool = adapter.parse_pool(
        {
            "pool_address": POOL,
            "base_mint": MINT,
            "quote_mint": QUOTE_POOL,
            "pool_type": "CPMM",
            "executable_liquidity": True,
            "base_reserve": "1000",
            "quote_reserve": "2000",
            "fee_bps": 25,
            "created_at": "2026-08-27T10:59:58Z",
        },
        context(),
    )
    assert pool.pool_type == "CPMM"
    assert pool.quality_state is QualityState.FRESH
    quote = asyncio.run(
        adapter.quote(
            QuoteRequest(
                context=context(),
                input_mint=MINT,
                output_mint=QUOTE_POOL,
                amount=Decimal("100"),
                slippage_bps=100,
            ),
            pool=pool,
        )
    )
    assert quote.output_amount > Decimal("0")
    assert quote.price_impact_bps > Decimal("0")
    assert POOL in quote.route


def test_raydium_unknown_executable_liquidity_does_not_produce_a_fresh_quote() -> None:
    pool = RaydiumAdapter().parse_pool(
        {
            "pool_address": POOL,
            "base_mint": MINT,
            "quote_mint": QUOTE_POOL,
            "pool_type": "CLMM",
            "base_reserve": "0",
            "quote_reserve": "0",
        },
        context(),
    )
    assert pool.quality_state is QualityState.UNKNOWN


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


def test_parser_preserves_unknown_event_time_and_does_not_create_a_candidate() -> None:
    parsed = PumpFunAdapter().parse(
        {"event_type": "launch", "event_id": "unknown-time", "data": {"mint": MINT}},
        context(),
    )

    assert parsed.occurred_at is None
    assert parsed.to_observation().occurred_at is None
    assert parsed.to_observation().normalized_payload["event_time_quality"] == "UNKNOWN"
    with pytest.raises(ProviderSchemaError, match="exact occurred_at"):
        PumpFunAdapter().normalize(
            {"event_type": "launch", "event_id": "unknown-time", "data": {"mint": MINT}},
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


@pytest.mark.parametrize(
    ("event_type", "expected_type"),
    (
        ("launch", ProtocolEventType.LAUNCH),
        ("trade", ProtocolEventType.TRADE),
        ("bonding_curve_progress", ProtocolEventType.BONDING_CURVE_PROGRESS),
        ("graduation", ProtocolEventType.GRADUATION),
        ("migration", ProtocolEventType.MIGRATION),
        ("pool_created", ProtocolEventType.POOL_CREATED),
        ("creator_fee_claim", ProtocolEventType.CREATOR_FEE_CLAIM),
        ("fee_recipient_change", ProtocolEventType.FEE_RECIPIENT_CHANGE),
    ),
)
def test_rich_pumpfun_events_are_typed_versioned_and_observable(
    event_type: str,
    expected_type: ProtocolEventType,
) -> None:
    data: dict[str, object] = {"mint": MINT}
    if event_type == "pool_created":
        data.update({"pool": POOL, "quote_mint": QUOTE})
    if event_type == "bonding_curve_progress":
        data["progress_bps"] = 4200
    parsed = PumpFunAdapter().parse(
        {
            "schema_version": PROTOCOL_EVENT_SCHEMA_VERSION,
            "event_type": event_type,
            "source_id": f"rich-{event_type}",
            "occurred_at": "2026-08-27T10:59:00Z",
            "data": data,
        },
        context(),
    )

    assert parsed.protocol_event_type is expected_type
    assert parsed.event_origin is ProtocolEventOrigin.NATIVE
    assert parsed.is_derived is False
    assert parsed.schema_version == PROTOCOL_EVENT_SCHEMA_VERSION
    assert parsed.parser_version == RICH_LAUNCHPAD_PARSER_VERSION
    observation = parsed.to_observation()
    assert observation.kind == "protocol.lifecycle"
    assert observation.provenance.parser_version == RICH_LAUNCHPAD_PARSER_VERSION
    assert observation.normalized_payload["protocol_event_type"] == expected_type.value
    assert observation.normalized_payload["event_origin"] == "NATIVE"
    assert observation.token_id is not None
    if event_type == "bonding_curve_progress":
        assert parsed.bonding_curve_progress_bps == 4200
        assert observation.normalized_payload["bonding_curve_progress_bps"] == 4200


def test_legacy_discovery_event_remains_v1_and_whale_trade_is_derived() -> None:
    legacy = PumpFunAdapter().parse(
        {
            "event_type": "token_created",
            "event_id": "legacy-event",
            "data": {"mint": MINT, "token_program": "spl-token"},
        },
        context(),
    )
    assert legacy.protocol_event_type is ProtocolEventType.TOKEN_CREATED
    assert legacy.event_origin is ProtocolEventOrigin.NATIVE
    assert legacy.schema_version == 1
    assert legacy.parser_version == LAUNCHPAD_PARSER_VERSION

    whale = PumpFunAdapter().parse(
        {
            "schema_version": PROTOCOL_EVENT_SCHEMA_VERSION,
            "event_type": "trade",
            "source_id": "derived-whale",
            "occurred_at": "2026-08-27T10:59:00Z",
            "data": {"mint": MINT, "is_whale": True, "amount": "100000"},
        },
        context(),
    )
    assert whale.protocol_event_type is ProtocolEventType.WHALE_TRADE
    assert whale.event_origin is ProtocolEventOrigin.DERIVED
    assert whale.is_derived is True
    assert whale.to_observation().normalized_payload["event_origin"] == "DERIVED"

    with pytest.raises(ProviderSchemaError, match="timestamp"):
        MeteoraAdapter().parse(
            {
                "event_type": "pool_created",
                "occurred_at": "not-a-time",
                "data": {"mint": MINT, "pool": POOL, "quote_mint": QUOTE},
            },
            context(),
        )
