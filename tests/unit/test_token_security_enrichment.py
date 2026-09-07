"""Keyless contracts for optional multi-chain token-security enrichment."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    RiskDataRequest,
    RiskSeverity,
)
from memeradar_domain import Chain, QualityState, TokenIdentity
from memeradar_providers.token_security import GoPlusTokenSecurityAdapter
from memeradar_providers.transport import (
    CapabilityUnavailableError,
    ProviderTimeoutError,
    ProviderTransport,
    RetryPolicy,
    TransportTimeouts,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SOLANA_MINT = "So11111111111111111111111111111111111111112"
BNB_TOKEN = "0x1111111111111111111111111111111111111111"
ROBINHOOD_TOKEN = "0x2222222222222222222222222222222222222222"


def context() -> ProviderRequestContext:
    return ProviderRequestContext(
        correlation_id="token-security-test",
        requested_at=NOW,
        deadline_at=NOW + timedelta(seconds=5),
    )


def request(token: TokenIdentity) -> RiskDataRequest:
    return RiskDataRequest(context=context(), token=token)


def transport() -> ProviderTransport:
    return ProviderTransport(
        timeouts=TransportTimeouts(overall_seconds=1),
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_supported_chains_use_generic_security_routes_and_normalized_fields() -> None:
    seen: list[httpx.Request] = []
    tokens = (
        TokenIdentity(mint_address=SOLANA_MINT, chain=Chain.SOLANA),
        TokenIdentity(mint_address=BNB_TOKEN, chain=Chain.BNB),
        TokenIdentity(mint_address=ROBINHOOD_TOKEN, chain=Chain.ROBINHOOD),
    )

    async def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(http_request)
        expected_address = http_request.url.params["contract_addresses"]
        return httpx.Response(
            200,
            json={
                "code": 1,
                "result": {
                    expected_address: {
                        "is_honeypot": "0",
                        "is_blacklisted": "1",
                        "is_mintable": "1",
                        "is_proxy": "0",
                        "is_open_source": "1",
                        "buy_tax": "5",
                        "sell_tax": "10",
                    }
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoPlusTokenSecurityAdapter(
        "https://fixture.security.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        findings = tuple(
            finding
            for token in tokens
            for finding in asyncio.run(adapter.assess(request(token)))
        )
    finally:
        asyncio.run(client.aclose())

    assert adapter.capabilities >= {"token_security", "risk_data"}
    assert [item.url.path for item in seen] == [
        "/api/v1/solana/token_security",
        "/api/v1/token_security/56",
        "/api/v1/token_security/4663",
    ]
    assert all(item.method == "GET" for item in seen)
    assert all(item.provenance.provider == "goplus" for item in findings)
    assert {item.code for item in findings} == {
        "TOKEN_SECURITY_HONEYPOT",
        "TOKEN_SECURITY_BLACKLISTED",
        "TOKEN_SECURITY_MINTABLE",
        "TOKEN_SECURITY_PROXY",
        "TOKEN_SECURITY_OPEN_SOURCE",
        "TOKEN_SECURITY_BUY_TAX",
        "TOKEN_SECURITY_SELL_TAX",
    }
    assert (
        next(item for item in findings if item.code == "TOKEN_SECURITY_HONEYPOT").severity
        is RiskSeverity.INFO
    )
    assert (
        next(item for item in findings if item.code == "TOKEN_SECURITY_BLACKLISTED").severity
        is RiskSeverity.WARN
    )
    assert all(item.quality_state is QualityState.FRESH for item in findings)


def test_unsupported_chain_is_explicitly_unavailable_without_network_access() -> None:
    called = False

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoPlusTokenSecurityAdapter(
        "https://fixture.security.example",
        supported_chains=(Chain.BNB, Chain.ROBINHOOD),
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(CapabilityUnavailableError, match="solana"):
            asyncio.run(
                adapter.assess(
                    request(TokenIdentity(mint_address=SOLANA_MINT, chain=Chain.SOLANA))
                )
            )
    finally:
        asyncio.run(client.aclose())

    assert called is False


def test_timeout_remains_a_classified_external_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoPlusTokenSecurityAdapter(
        "https://fixture.security.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(
                adapter.assess(
                    request(TokenIdentity(mint_address=BNB_TOKEN, chain=Chain.BNB))
                )
            )
    finally:
        asyncio.run(client.aclose())


def test_partial_response_emits_unknown_for_absent_fields_instead_of_safe_defaults() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 1, "result": {BNB_TOKEN.lower(): {"is_honeypot": "0"}}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoPlusTokenSecurityAdapter(
        "https://fixture.security.example",
        client=client,
        transport=transport(),
        clock=lambda: NOW,
    )
    try:
        findings = asyncio.run(
            adapter.assess(request(TokenIdentity(mint_address=BNB_TOKEN, chain=Chain.BNB)))
        )
    finally:
        asyncio.run(client.aclose())

    by_code = {item.code: item for item in findings}
    assert by_code["TOKEN_SECURITY_HONEYPOT"].severity is RiskSeverity.INFO
    assert by_code["TOKEN_SECURITY_HONEYPOT"].quality_state is QualityState.FRESH
    assert by_code["TOKEN_SECURITY_BUY_TAX"].severity is RiskSeverity.UNKNOWN
    assert by_code["TOKEN_SECURITY_BUY_TAX"].quality_state is QualityState.UNKNOWN
    assert by_code["TOKEN_SECURITY_SELL_TAX"].severity is RiskSeverity.UNKNOWN
    assert by_code["TOKEN_SECURITY_SELL_TAX"].quality_state is QualityState.UNKNOWN
