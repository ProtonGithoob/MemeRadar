from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from memeradar_application.kol_bundle import KOLBundleClusterAnalyzer
from memeradar_application.price_integrity import compare_reference_price
from memeradar_application.provider_contracts import ProviderRequestContext, SocialDataRequest
from memeradar_domain import Observation, Provenance, QualityState, TokenIdentity
from memeradar_providers.robinhood import (
    RobinhoodLaunchpadDecoder,
    RobinhoodSequencerAdapter,
    VerifiedLaunchpadContract,
)
from memeradar_providers.smart_money_stream import (
    ExternalWalletEventStreamAdapter,
    ExternalWalletStreamPolicy,
)
from memeradar_providers.social import SocialRestAdapter
from memeradar_providers.transport import ProviderTransport, RetryPolicy, TransportTimeouts

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
MINT = "So11111111111111111111111111111111111111112"
CALLER = "11111111111111111111111111111112"
SIDE = "11111111111111111111111111111113"
FUNDER = "11111111111111111111111111111114"
EVM_TOKEN = "0x1111111111111111111111111111111111111111"
EVM_WALLET = "0x2222222222222222222222222222222222222222"


def prov(source_id: str, provider: str = "fixture") -> Provenance:
    return Provenance(
        provider=provider, source_id=source_id, observed_at=NOW, parser_version="test-v1"
    )


def obs(source_id: str, payload: dict[str, object], *, at: datetime | None = None) -> Observation:
    at = at or NOW - timedelta(seconds=5)
    return Observation(
        kind="wallet.activity",
        provenance=Provenance(
            provider="fixture", source_id=source_id, observed_at=at, parser_version="test-v1"
        ),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=QualityState.FRESH,
        normalized_payload=payload,
    )


def test_kol_bundle_evidence_uses_multiple_explicit_correlations_without_ownership_claim() -> None:
    token = TokenIdentity(mint_address=MINT)
    result = KOLBundleClusterAnalyzer().analyze(
        token,
        (
            obs(
                "caller-buy",
                {
                    "chain": "solana",
                    "mint_address": MINT,
                    "wallet_address": CALLER,
                    "action": "BUY",
                    "quantity": "10",
                    "bundle_id": "b1",
                    "jito_bundle": True,
                    "slot": 10,
                },
            ),
            obs(
                "side-buy",
                {
                    "chain": "solana",
                    "mint_address": MINT,
                    "wallet_address": SIDE,
                    "action": "BUY",
                    "quantity": "5",
                    "bundle_id": "b1",
                    "jito_bundle": True,
                    "slot": 10,
                    "funder": FUNDER,
                },
            ),
        ),
        caller_wallet=CALLER,
        now=NOW,
        config_hash="kol-test",
    )

    assert result.visible_caller_position == Decimal("10")
    assert result.cluster_adjusted_accumulation == Decimal("15")
    assert result.probable_related_side_wallet_count == 1
    assert result.confidence > 0
    assert result.ownership_asserted is False
    assert "JITO_BUNDLE_EVIDENCE" in result.reason_code_values


def test_external_wallet_stream_is_chain_qualified_deduped_and_marks_gaps() -> None:
    async def source():
        yield {
            "chain": "robinhood",
            "event_id": "a",
            "sequence": 1,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "2",
            "occurred_at": NOW.isoformat(),
        }
        yield {
            "chain": "robinhood",
            "event_id": "a",
            "sequence": 1,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "2",
            "occurred_at": NOW.isoformat(),
        }
        yield {
            "chain": "robinhood",
            "event_id": "c",
            "sequence": 3,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "1",
            "occurred_at": NOW.isoformat(),
        }

    adapter = ExternalWalletEventStreamAdapter("cabalspy-fixture", "robinhood", lambda: source())
    result = asyncio.run(adapter.collect(ProviderRequestContext("stream-test", NOW)))

    assert len(result.observations) == 2
    assert result.duplicates == 1
    assert result.gaps == ((2, 2),)
    assert result.observations[0].normalized_payload["chain"] == "robinhood"
    assert result.observations[0].provenance.source_id == "robinhood:a"
    assert result.used_fallback is False
    assert result.health.state.value == "HEALTHY"


def test_external_wallet_stream_outage_is_degraded_and_never_synthesizes_evidence() -> None:
    async def source():
        raise RuntimeError("synthetic outage")
        yield {}

    adapter = ExternalWalletEventStreamAdapter(
        "cabalspy-fixture",
        "robinhood",
        lambda: source(),
        policy=ExternalWalletStreamPolicy(max_reconnects=0),
        sleeper=lambda _delay: asyncio.sleep(0),
    )
    result = asyncio.run(adapter.collect(ProviderRequestContext("stream-outage", NOW)))
    assert result.observations == ()
    assert result.used_fallback is False
    assert result.health.state.value == "DEGRADED"


def test_external_wallet_stream_reconnects_once_then_uses_ordered_fallback() -> None:
    attempts = 0

    async def source():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic disconnect")
        yield {
            "chain": "robinhood",
            "event_id": "stream-event",
            "sequence": 1,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "1",
            "occurred_at": NOW.isoformat(),
        }

    adapter = ExternalWalletEventStreamAdapter(
        "cabalspy-fixture",
        "robinhood",
        lambda: source(),
        fallback=lambda _context: (
            {
                "chain": "robinhood",
                "event_id": "rpc-fallback",
                "sequence": 1,
                "token_address": EVM_TOKEN,
                "wallet_address": EVM_WALLET,
                "action": "buy",
                "quantity": "1",
                "occurred_at": NOW.isoformat(),
            },
        ),
        policy=ExternalWalletStreamPolicy(max_reconnects=0),
        sleeper=lambda _delay: asyncio.sleep(0),
    )
    result = asyncio.run(adapter.collect(ProviderRequestContext("stream-retry", NOW)))
    assert attempts == 1
    assert result.reconnects == 1
    assert result.used_fallback is True
    assert len(result.observations) == 1


def test_social_backfill_reuses_call_normalization_and_marks_research_evidence() -> None:
    async def handler(request):
        return __import__("httpx").Response(
            200,
            json={
                "data": [
                    {
                        "id": "x-1",
                        "author_id": "author",
                        "created_at": "2026-09-08T11:59:00Z",
                        "text": "buy $MEME",
                        "edited": True,
                        "deleted": False,
                    }
                ]
            },
        )

    import httpx

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = SocialRestAdapter(
        "https://fixture.social.example",
        client=client,
        transport=ProviderTransport(
            timeouts=TransportTimeouts(overall_seconds=1), retry_policy=RetryPolicy(max_attempts=1)
        ),
        clock=lambda: NOW,
    )
    request = SocialDataRequest(
        context=ProviderRequestContext("backfill-test", NOW),
        query="MEME",
        limit=10,
        from_at=NOW - timedelta(minutes=2),
        to_at=NOW,
    )
    try:
        calls = asyncio.run(adapter.backfill(request))
    finally:
        asyncio.run(client.aclose())
    assert len(calls) == 1
    assert calls[0].disclosure["evidence_class"] == "EXTERNAL_RESEARCH_EVIDENCE"
    assert calls[0].edited is True
    assert calls[0].provenance[0].parser_version.endswith("-calls")


def test_robinhood_sequencer_orders_events_and_unverified_launchpad_is_unknown() -> None:
    async def source():
        yield {
            "event_id": "b",
            "sequence": 2,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "1",
            "occurred_at": NOW.isoformat(),
        }
        yield {
            "event_id": "a",
            "sequence": 1,
            "token_address": EVM_TOKEN,
            "wallet_address": EVM_WALLET,
            "action": "buy",
            "quantity": "1",
            "occurred_at": (NOW - timedelta(seconds=1)).isoformat(),
        }

    adapter = RobinhoodSequencerAdapter(lambda: source())
    result = asyncio.run(adapter.collect(ProviderRequestContext("rh-test", NOW)))
    assert [item.provenance.source_id for item in result.observations] == [
        "robinhood:a",
        "robinhood:b",
    ]
    assert result.gaps == ()
    unknown = RobinhoodLaunchpadDecoder().decode(
        {"contract_address": EVM_TOKEN, "selector": "0xdeadbeef", "event_id": "launch-1"},
        ProviderRequestContext("rh-launch", NOW),
    )
    assert unknown.quality_state is QualityState.UNKNOWN
    assert "UNVERIFIED_LAUNCHPAD_IDENTITY" in unknown.normalized_payload["reason_codes"]
    verified = RobinhoodLaunchpadDecoder(
        (
            VerifiedLaunchpadContract(
                "verified-launchpad", EVM_TOKEN, ("0x12345678",)
            ),
        )
    ).decode(
        {
            "contract_address": EVM_TOKEN,
            "selector": "0x12345678",
            "event_id": "launch-2",
            "event_type": "first_liquidity",
        },
        ProviderRequestContext("rh-launch-verified", NOW),
    )
    assert verified.quality_state is QualityState.FRESH
    assert verified.normalized_payload["launchpad"] == "verified-launchpad"


def test_reference_price_evidence_stales_or_flags_deviation_without_becoming_executable_quote() -> (
    None
):
    stale = compare_reference_price(
        "robinhood",
        EVM_TOKEN,
        "1",
        "1.1",
        NOW - timedelta(minutes=10),
        NOW,
        provenance=(prov("oracle"),),
        config_hash="price-test",
    )
    assert stale.quality_state is QualityState.UNKNOWN
    assert stale.deviation_bps == Decimal("1000")
    assert stale.execution_price is None
    fresh = compare_reference_price(
        "robinhood",
        EVM_TOKEN,
        "1",
        "1.2",
        NOW - timedelta(seconds=5),
        NOW,
        provenance=(prov("oracle"),),
        config_hash="price-test",
    )
    assert fresh.quality_state is QualityState.FRESH
    assert "MARKET_INTEGRITY_DEVIATION" in fresh.reason_code_values
