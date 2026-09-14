"""Read-only GMGN OpenAPI adapter contracts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest

from memeradar_application.config import Settings
from memeradar_application.discovery_collection import CandidateDiscoveryCollector
from memeradar_application.early_features import EarlyFeatureEngine
from memeradar_application.historical_dataset import ExternalProviderReadinessReport
from memeradar_application.provider_contracts import (
    DiscoveryRequest,
    OnChainRequest,
    ProviderRequestContext,
)
from memeradar_domain import (
    CandidateState,
    Chain,
    Observation,
    Provenance,
    QualityState,
    TokenIdentity,
)
from memeradar_providers.composition import build_provider_bundle
from memeradar_providers.gmgn import (
    GMGN_DEFAULT_BASE_URL,
    GMGN_PARSER_VERSION,
    GMGN_PROVIDER,
    GmgnAdapter,
    _decimal,
    _signed_decimal,
)
from memeradar_providers.transport import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderSchemaError,
    ProviderTimeoutError,
    ProviderTransport,
    ProviderUnavailableError,
    RetryPolicy,
)

NOW = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
SOL_TOKEN = "So11111111111111111111111111111111111111112"
SOL_WALLET = "Vote111111111111111111111111111111111111111"
BSC_TOKEN = "0x" + "11" * 20
BSC_WALLET = "0x" + "22" * 20


def _context() -> ProviderRequestContext:
    return ProviderRequestContext("gmgn-test", NOW, NOW + timedelta(seconds=30))


def _token(address: str = SOL_TOKEN, chain: Chain = Chain.SOLANA) -> TokenIdentity:
    return TokenIdentity(
        address,
        chain=chain,
        id=uuid5(NAMESPACE_URL, f"test:{chain}:{address}"),
    )


def _response(path: str, address: str = SOL_TOKEN) -> dict[str, object]:
    if path == "/v1/market/rank":
        return {
            "code": 0,
            "data": {
                "rank": [
                    {
                        "address": address,
                        "symbol": "MEME",
                        "open_timestamp": int(NOW.timestamp()) - 30,
                    }
                ]
            },
        }
    if path == "/v1/token/info":
        return {
            "code": 0,
            "data": {
                "address": address,
                "symbol": "MEME",
                "name": "Test Meme",
                "price": {"price": "0.12", "price_1m": "0.11"},
                "liquidity": "10000",
                "holder_count": 40,
                "creation_timestamp": int(NOW.timestamp()) - 90,
                "launchpad_status": "bonding",
                "is_on_curve": True,
                "stat": {
                    "smart_degen_count": 5,
                    "fresh_wallet_rate": "0.25",
                    "top_10_holder_rate": "0.31",
                },
                "dev": {"creator_address": BSC_WALLET if address == BSC_TOKEN else SOL_WALLET},
                "wallet_tags_stat": {"renowned_wallets": 2, "smart_wallets": 4},
            },
        }
    if path == "/v1/token/security":
        return {
            "code": 0,
            "data": {
                "is_honeypot": None,
                "rug_ratio": "0.18",
                "is_wash_trading": True,
                "suspected_insider_hold_rate": "0.07",
                "rat_trader_amount_rate": "0.04",
                "bundler_trader_amount_rate": "0.03",
                "sniper_count": 3,
            },
        }
    if path == "/v1/market/token_top_holders":
        return {
            "code": 0,
            "data": {
                "list": [
                    {
                        "address": BSC_WALLET if address == BSC_TOKEN else SOL_WALLET,
                        "amount_percentage": "0.08",
                        "is_on_curve": True,
                    }
                ],
                "holder_count": 40,
            },
        }
    if path == "/v1/market/token_top_traders":
        return {
            "code": 0,
            "data": {
                "list": [
                    {
                        "address": BSC_WALLET if address == BSC_TOKEN else SOL_WALLET,
                        "amount_percentage": "0.04",
                        "profit": "0",
                        "maker_token_tags": ["smart_money"],
                    }
                ]
            },
        }
    raise AssertionError(path)


def _adapter(
    handler,
    *,
    max_concurrency: int = 4,
    chains: tuple[Chain, ...] = (Chain.SOLANA,),
) -> GmgnAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GmgnAdapter(
        GMGN_DEFAULT_BASE_URL,
        api_key="gmgn-test-secret",
        client=client,
        transport=ProviderTransport(
            provider_name=GMGN_PROVIDER,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        clock=lambda: NOW,
        max_concurrency=max_concurrency,
        chains=chains,
    )


def test_gmgn_settings_are_disabled_by_default_and_read_only() -> None:
    settings = Settings.from_env({})
    assert settings.gmgn_enabled is False
    assert settings.gmgn_api_key is None
    assert settings.gmgn_base_url == GMGN_DEFAULT_BASE_URL

    configured = Settings.from_env(
        {
            "GMGN_ENABLED": "true",
            "GMGN_API_KEY": "gmgn-secret",
            "GMGN_BASE_URL": "https://fixture.gmgn.example",
        }
    )
    assert configured.gmgn_enabled is True
    assert configured.gmgn_api_key == "gmgn-secret"
    assert configured.gmgn_base_url == "https://fixture.gmgn.example"


def test_gmgn_composition_is_optional_and_never_enters_core_routes() -> None:
    configured = Settings.from_env(
        {
            "GMGN_ENABLED": "true",
            "GMGN_API_KEY": "gmgn-secret",
            "GMGN_BASE_URL": "https://fixture.gmgn.example",
        }
    )
    bundle = build_provider_bundle(configured)
    try:
        assert bundle.gmgn is not None
        assert bundle.optional["gmgn"] == "CONFIGURED"
        assert bundle.route_plan.market.providers == ("dexscreener",)
        assert bundle.market_data.provider_name == "dexscreener"
    finally:
        asyncio.run(bundle.aclose())


def test_gmgn_discovery_and_enrichment_use_verified_read_routes_and_canonical_evidence() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        assert request.headers["x-apikey"] == "gmgn-test-secret"
        assert "gmgn-test-secret" not in str(request.url)
        assert "x-signature" not in request.headers
        return httpx.Response(200, json=_response(request.url.path))

    adapter = _adapter(handler)
    try:
        candidates = asyncio.run(adapter.discover(DiscoveryRequest(context=_context(), limit=10)))
        observations = asyncio.run(
            adapter.enrich(OnChainRequest(context=_context(), token=candidates[0].token))
        )
    finally:
        asyncio.run(adapter.aclose())

    assert len(candidates) == 1
    assert candidates[0].token.chain is Chain.SOLANA
    assert {item.kind for item in observations} == {
        "market.snapshot",
        "social.caller_consensus",
        "wallet.top_traders",
        "market.holder_data",
        "security.provider_risk",
        "creator.profile",
    }
    assert all(item.provenance.provider == GMGN_PROVIDER for item in observations)
    assert all(item.provenance.parser_version == GMGN_PARSER_VERSION for item in observations)
    assert all(item.normalized_payload["live_shadow"] is True for item in observations)
    assert all(item.occurred_at is None for item in observations)
    assert {
        item.normalized_payload["observation_semantics"] for item in observations
    } == {"SNAPSHOT", "AGGREGATE"}
    security = next(item for item in observations if item.kind == "security.provider_risk")
    assert security.normalized_payload["is_honeypot"] is None
    assert security.normalized_payload["rug_ratio"] == "0.18"
    assert (
        next(item for item in observations if item.kind == "market.snapshot").normalized_payload[
            "is_on_curve"
        ]
        is True
    )
    assert {request.url.path for request in calls} == {
        "/v1/market/rank",
        "/v1/token/info",
        "/v1/token/security",
        "/v1/market/token_top_holders",
        "/v1/market/token_top_traders",
    }


def test_gmgn_adapter_collector_and_readiness_keep_shadow_out_of_early_features() -> None:
    class Sink:
        def __init__(self) -> None:
            self.candidates = []
            self.observations = []

        async def save_candidate(self, candidate: object) -> object:
            self.candidates.append(candidate)
            return candidate

        async def save_observation(self, observation: object) -> object:
            self.observations.append(observation)
            return observation

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_response(request.url.path))

    async def collect() -> tuple[object, Sink]:
        adapter = _adapter(handler)
        sink = Sink()
        try:
            report = await CandidateDiscoveryCollector(clock=lambda: NOW).collect(
                adapter,
                sink,
                DiscoveryRequest(context=_context(), limit=10),
                evidence_class="REAL_EXTERNAL",
                evidence_origin="REAL_EXTERNAL",
                collection_mode="LIVE_SHADOW",
            )
        finally:
            await adapter.aclose()
        return report, sink

    report, sink = asyncio.run(collect())
    candidate = sink.candidates[0]
    observations = tuple(sink.observations)
    readiness = ExternalProviderReadinessReport.from_persisted_observations(
        "gmgn", observations
    )

    assert candidate.state is CandidateState.DISCOVERED
    assert report.persisted_observation_count == 7
    assert readiness.real_observation_count == 7
    assert readiness.unique_token_count == 1
    assert readiness.independent_sample_count == 1
    assert readiness.status == "INSUFFICIENT_SAMPLES"
    assert EarlyFeatureEngine().compute(candidate.token.id, NOW, observations) == (
        EarlyFeatureEngine().compute(candidate.token.id, NOW, ())
    )


@pytest.mark.parametrize("profit", ("-1250.40", "0", "725.10"))
def test_gmgn_signed_trader_profit_is_normalized_without_failing_enrichment(
    profit: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = _response(request.url.path)
        if request.url.path == "/v1/market/token_top_traders":
            data = payload["data"]
            assert isinstance(data, dict)
            rows = data["list"]
            assert isinstance(rows, list)
            rows[0] = {**rows[0], "profit": profit}
        return httpx.Response(200, json=payload)

    adapter = _adapter(handler)
    try:
        observations = asyncio.run(
            adapter.enrich(OnChainRequest(context=_context(), token=_token()))
        )
    finally:
        asyncio.run(adapter.aclose())

    traders = next(item for item in observations if item.kind == "wallet.top_traders")
    assert traders.normalized_payload["traders"][0]["profit"] == profit


@pytest.mark.parametrize(
    ("path", "field"),
    (
        ("/v1/token/info", "liquidity"),
        ("/v1/market/token_top_holders", "amount_percentage"),
    ),
)
def test_gmgn_non_negative_numeric_domains_reject_negative_values(path: str, field: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = _response(request.url.path)
        if request.url.path == path:
            data = payload["data"]
            assert isinstance(data, dict)
            if path.endswith("info"):
                data[field] = "-1"
            else:
                rows = data["list"]
                assert isinstance(rows, list)
                rows[0] = {**rows[0], field: "-1"}
        return httpx.Response(200, json=payload)

    adapter = _adapter(handler)
    try:
        with pytest.raises(ProviderSchemaError):
            asyncio.run(adapter.enrich(OnChainRequest(context=_context(), token=_token())))
    finally:
        asyncio.run(adapter.aclose())


def test_gmgn_decimal_parser_preserves_none_and_rejects_malformed_values() -> None:
    assert _decimal(None, "optional") is None
    assert _signed_decimal(None, "profit") is None
    with pytest.raises(ProviderSchemaError):
        _decimal("not-a-number", "optional")
    with pytest.raises(ProviderSchemaError):
        _signed_decimal("not-a-number", "profit")


def test_gmgn_valid_empty_discovery_is_not_a_provider_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/market/rank"
        return httpx.Response(200, json={"code": 0, "data": {"rank": []}})

    adapter = _adapter(handler)
    try:
        candidates = asyncio.run(adapter.discover(DiscoveryRequest(context=_context(), limit=10)))
    finally:
        asyncio.run(adapter.aclose())

    assert candidates == ()
    assert adapter.error_count == 0


@pytest.mark.parametrize(
    ("response", "error"),
    (
        (httpx.Response(403), ProviderAuthenticationError),
        (httpx.Response(429, headers={"retry-after": "2"}), ProviderRateLimitedError),
        (httpx.Response(503), ProviderUnavailableError),
        (httpx.Response(200, json={"code": 1, "message": "bad"}), ProviderError),
        (httpx.Response(200, json={"code": 0, "data": []}), ProviderSchemaError),
    ),
)
def test_gmgn_read_failures_are_classified_without_secret_leaks(
    response: httpx.Response,
    error: type[Exception],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return response

    adapter = _adapter(handler)
    try:
        with pytest.raises(error) as raised:
            asyncio.run(adapter.discover(DiscoveryRequest(context=_context(), limit=10)))
    finally:
        asyncio.run(adapter.aclose())

    assert "gmgn-test-secret" not in str(raised.value)
    assert "gmgn-test-secret" not in repr(adapter)


def test_gmgn_timeout_is_normalized() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    adapter = _adapter(handler)
    try:
        with pytest.raises(ProviderTimeoutError):
            asyncio.run(adapter.discover(DiscoveryRequest(context=_context(), limit=10)))
    finally:
        asyncio.run(adapter.aclose())


def _observation(
    kind: str,
    source_id: str,
    payload: dict[str, object],
    *,
    provider: str = GMGN_PROVIDER,
    evidence_origin: str = "REAL_EXTERNAL",
    collection_mode: str | None = None,
) -> Observation:
    return Observation(
        kind=kind,
        provenance=Provenance(
            provider=provider,
            source_id=source_id,
            observed_at=NOW,
            parser_version=GMGN_PARSER_VERSION,
        ),
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        quality_state=QualityState.FRESH,
        normalized_payload={
            **payload,
            "evidence_origin": evidence_origin,
            "evidence_class": evidence_origin,
            **({"collection_mode": collection_mode} if collection_mode is not None else {}),
        },
    )


def test_gmgn_readiness_counts_only_real_provider_evidence_and_stays_insufficient() -> None:
    ignored = tuple(
        _observation(
            "market.snapshot",
            f"ignored:{origin.lower()}",
            {"chain": "solana", "token_address": BSC_TOKEN},
            evidence_origin=origin,
        )
        for origin in ("FIXTURE", "SYNTHETIC", "DEMO", "REPLAY", "REDACTED")
    )
    observations = (
        _observation(
            "candidate.discovery",
            "real:candidate",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "social.caller_consensus",
            "real:caller",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "wallet.top_traders",
            "real:wallet",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "market.holder_data",
            "real:holder",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "security.provider_risk",
            "real:security",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "market.snapshot",
            "foreign:ignored",
            {"chain": "solana", "token_address": BSC_TOKEN},
            provider="other-provider",
            evidence_origin="REAL_EXTERNAL",
        ),
        _observation(
            "market.snapshot",
            "replay:ignored",
            {"chain": "solana", "token_address": SOL_TOKEN},
            evidence_origin="REAL_EXTERNAL",
            collection_mode="REPLAY",
        ),
        *ignored,
    )

    report = ExternalProviderReadinessReport.from_persisted_observations("gmgn", observations)

    assert report.real_observation_count == 5
    assert report.unique_token_count == 1
    assert report.independent_sample_count == 1
    assert report.chain_token_counts == {"solana": 1}
    assert report.candidate_observation_count == 1
    assert report.caller_kol_observation_count == 1
    assert report.smart_wallet_observation_count == 1
    assert report.holder_distribution_observation_count == 1
    assert report.security_risk_observation_count == 1
    assert report.status == "INSUFFICIENT_SAMPLES"
    assert "GMGN_LABELED_OUTCOMES_UNAVAILABLE" in report.reason_codes


def test_gmgn_repeated_polling_snapshots_are_not_independent_alpha_samples() -> None:
    observations = tuple(
        _observation(
            "market.snapshot",
            f"poll:{index}",
            {"chain": "solana", "token_address": SOL_TOKEN},
            collection_mode="LIVE_SHADOW",
        )
        for index in range(100)
    )

    report = ExternalProviderReadinessReport.from_persisted_observations("gmgn", observations)

    assert report.real_observation_count == 100
    assert report.unique_token_count == 1
    assert report.independent_sample_count == 1
    assert report.status == "INSUFFICIENT_SAMPLES"


def test_gmgn_readiness_counts_unique_tokens_as_independent_units() -> None:
    observations = (
        _observation(
            "market.snapshot",
            "solana:token",
            {"chain": "solana", "token_address": SOL_TOKEN},
        ),
        _observation(
            "market.snapshot",
            "bnb:token",
            {"chain": "bnb", "token_address": BSC_TOKEN},
        ),
    )

    report = ExternalProviderReadinessReport.from_observations("gmgn", observations)

    assert report.real_observation_count == 2
    assert report.unique_token_count == 2
    assert report.independent_sample_count == 2
