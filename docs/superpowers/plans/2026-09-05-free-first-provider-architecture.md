# FREE-FIRST Provider Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provider-neutral capability routing and a small bounded composition layer that makes standard Solana RPC, DexScreener market/paper quotes, local intelligence, optional RugCheck/social/Telegram, and optional Ollama usable without mandatory paid credentials.

**Architecture:** Preserve the existing application ports and adapters. Add precise capabilities and normalized social/quote evidence in the application package, implement standard Solana, DexScreener, and Ollama adapters in the provider package, and compose explicit bounded fallbacks in one provider composition module. Readiness and doctors classify core free services separately from optional enrichment and full external acceptance.

**Tech Stack:** Python 3.12, existing `httpx` async transports, `ProviderTransport`, dataclass contracts, pytest/pytest-cov, mypy, Ruff, Docker Compose, Markdown documentation.

**Spec:** `docs/superpowers/specs/2026-09-05-free-first-provider-architecture-design.md`

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Preserve Helius, Birdeye, RugCheck, social, narrative, external-wallet, Telegram, stream, fixture, launchpad, replay, paper, and frontend behavior.
- Do not emulate Helius DAS/enhanced functionality through standard Solana RPC or DexScreener.
- Do not scrape X/Twitter, add signing/private-key logic, enable live execution, or expose secrets to frontend code.
- Provider-specific HTTP payloads stay in adapters; domain/application code consumes normalized contracts only.
- Missing data remains unavailable/unknown; malformed or stale market data cannot become a valid quote.
- Every new external request uses bounded timeout, retry, 429/`Retry-After` normalization, and concurrency limits.
- No external provider credential is required for application configuration or core free readiness.
- Use TDD for every behavior change: failing test, observed red result, minimum implementation, observed green result.

---

### Task 1: Extend normalized capabilities, quote evidence, social metadata, and settings

**Files:**
- Modify: `packages/application/src/memeradar_application/provider_contracts.py`
- Modify: `packages/application/src/memeradar_application/config.py`
- Modify: `packages/application/src/memeradar_application/provider_routing.py`
- Test: `tests/unit/test_provider_contracts.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_provider_routing.py`

**Interfaces:**
- Produces `ProviderCapability.CHAIN_RPC`, `ENHANCED_ASSET_METADATA`, `TRANSACTION_HISTORY`, `REALTIME_STREAM`, `MARKET_SNAPSHOT`, `MARKET_QUOTE`, `PAIR_DISCOVERY`, `SOCIAL_METADATA`, `SOCIAL_ANALYTICS`, `RISK_SUMMARY`, `WALLET_ENRICHMENT`, and `ALERT_DELIVERY`, while retaining all existing enum members.
- Produces immutable `QuoteMarketContext`, optional `QuoteSnapshot.market_context`, and optional `QuoteSnapshot.price_semantics` defaulting to `PriceSemantics.EXECUTION_QUOTE`.
- Produces immutable `SocialMetadata` and asynchronous `SocialMetadataPort.metadata(token, *, context)`.
- Produces `FreeFirstRoutePlan` and `build_free_first_route_plan(...)` in the application routing module; it contains ordered provider names per capability and no provider-package imports.
- Extends `Settings` with provider URLs/keys and selectors: `solana_rpc_url`, `helius_rpc_url`, `helius_api_key`, `helius_stream_url`, `solana_stream_url`, `dexscreener_api_url`, `dexscreener_api_key`, `market_data_provider`, `birdeye_api_url`, `birdeye_api_key`, `paper_quote_provider`, `paper_quote_url`, `paper_quote_api_key`, `rugcheck_api_url`, `rugcheck_api_key`, `wallet_intelligence_provider`, `external_wallet_api_url`, `external_wallet_api_key`, `social_metadata_provider`, `social_api_url`, `social_api_key`, `narrative_provider`, `narrative_api_url`, `narrative_api_key`, `narrative_model`, `telegram_api_url`, `telegram_bot_token`, and `telegram_chat_id`.

- [ ] **Step 1: Write failing contract/config/routing tests**

```python
def test_free_first_capabilities_and_quote_context_are_explicit() -> None:
    assert ProviderCapability.CHAIN_RPC.value == "chain_rpc"
    assert ProviderCapability.MARKET_SNAPSHOT.value == "market_snapshot"
    assert ProviderCapability.SOCIAL_METADATA.value == "social_metadata"

    context = QuoteMarketContext(
        chain="solana",
        pair_address=PAIR,
        base_mint=MINT,
        quote_mint=USDC,
        liquidity_usd=Decimal("25000"),
        pair_created_at=NOW - timedelta(minutes=3),
    )
    quote = QuoteSnapshot(
        provenance=provenance(),
        input_mint=USDC,
        output_mint=MINT,
        input_amount=Decimal("10"),
        output_amount=Decimal("100"),
        price_impact_bps=Decimal("50"),
        route=("dexscreener", "market_reference"),
        freshness=Freshness(NOW, NOW + timedelta(minutes=1)),
        price_semantics=PriceSemantics.MARKET_REFERENCE,
        market_context=context,
    )
    assert quote.price_semantics is PriceSemantics.MARKET_REFERENCE
    assert quote.market_context.liquidity_usd == Decimal("25000")


def test_empty_optional_provider_credentials_do_not_break_settings() -> None:
    settings = Settings.from_env({})
    assert settings.solana_rpc_url == "https://api.mainnet.solana.com"
    assert settings.market_data_provider == "dexscreener"
    assert settings.paper_quote_provider == "dexscreener"
    assert settings.wallet_intelligence_provider == "local"
    assert settings.social_metadata_provider == "dexscreener"
    assert settings.narrative_provider == "ollama"
    assert settings.analysis_only is True
    assert settings.paper_trading is True
    assert settings.manual_execution is False
    assert settings.auto_execution is False


def test_route_plan_places_free_providers_before_optional_enrichment() -> None:
    plan = build_free_first_route_plan(
        helius_configured=False,
        birdeye_configured=True,
        external_social_configured=False,
        external_narrative_configured=False,
        telegram_configured=False,
    )
    assert plan.market.providers == ("dexscreener", "birdeye")
    assert plan.chain.providers == ("solana-public-rpc",)
    assert plan.enhanced_asset_metadata.providers == ("helius",)
    assert plan.social_metadata.providers == ("dexscreener",)
    assert plan.social_analytics.providers == ()
    assert plan.narrative.providers == ("ollama", "disabled")
```

- [ ] **Step 2: Run the focused tests and observe the missing-contract failure**

Run: `pytest -q tests/unit/test_provider_contracts.py tests/unit/test_config.py tests/unit/test_provider_routing.py`

Expected: FAIL because the new capability members, quote context, social metadata port, settings fields, and route-plan builder do not yet exist.

- [ ] **Step 3: Implement the minimum provider-neutral contracts and validated settings**

Add the new enum members and dataclasses with address, chain, finite-decimal, timestamp, mapping-freeze, and bounded-text validation. Keep existing `QuoteSnapshot` constructor calls valid by making new fields optional. Add explicit settings defaults and aliases: `DEXSCREENER_API_BASE_URL` for `DEXSCREENER_API_URL`, `SOLANA_STREAM_URL`/`HELIUS_WEBSOCKET_URL` for the stream URL, and the existing Jupiter/custom quote keys as legacy fields. Derive an explicit external narrative selection only when legacy external narrative configuration is present and `NARRATIVE_PROVIDER` is absent.

Implement `FreeFirstRoutePlan` as immutable route records. The plan must contain no imports from `memeradar_providers` and must return an empty provider tuple for unavailable capabilities rather than inventing a fallback.

- [ ] **Step 4: Update paper fingerprint serialization for the new normalized evidence**

Include `price_semantics` and all `QuoteMarketContext` fields in `packages/application/src/memeradar_application/paper_execution.py::_quote_payload` so replay and idempotency distinguish reference-derived paper quotes from execution quotes without changing the protected paper-only ledger behavior.

- [ ] **Step 5: Run the focused tests and the existing provider contract suite**

Run: `pytest -q tests/unit/test_provider_contracts.py tests/unit/test_config.py tests/unit/test_provider_routing.py tests/unit/test_paper_execution.py tests/contract/test_provider_adapters.py`

Expected: PASS with the existing quote/paper/replay behavior preserved.

- [ ] **Step 6: Commit the contract slice**

```bash
git add packages/application/src/memeradar_application/provider_contracts.py packages/application/src/memeradar_application/config.py packages/application/src/memeradar_application/provider_routing.py packages/application/src/memeradar_application/paper_execution.py tests/unit/test_provider_contracts.py tests/unit/test_config.py tests/unit/test_provider_routing.py
git commit -m "feat: add free-first provider contracts and route plan"
```

### Task 2: Add typed capability-unavailable errors and generic Solana RPC

**Files:**
- Modify: `packages/providers/src/memeradar_providers/transport.py`
- Create: `packages/providers/src/memeradar_providers/solana_rpc.py`
- Create: `fixtures/providers/solana_rpc/health.json`
- Create: `fixtures/providers/solana_rpc/account_info.json`
- Create: `fixtures/providers/solana_rpc/transaction.json`
- Test: `tests/unit/test_solana_rpc.py`
- Test: `tests/contract/test_solana_rpc_provider.py`

**Interfaces:**
- Produces `CapabilityUnavailableError(ProviderError)` for unsupported Helius-only operations.
- Produces `SolanaRpcAdapter(OnChainPort)` with `provider_name == "solana-public-rpc"`, `check_health`, `fetch_account`, `fetch_transaction`, `fetch_signatures_for_address`, `fetch_blocks`, `fetch_block`, and `enrich`.
- `enrich(OnChainRequest(token=...))` raises `CapabilityUnavailableError`; address and signature requests use standard `getAccountInfo` and `getTransaction` only.
- `SolanaRpcAdapter` uses an `asyncio.Semaphore` concurrency bound, `ProviderTransport.execute`, header-only correlation metadata, and normalized `Observation` records with parser version `solana-rpc-v1`.

- [ ] **Step 1: Write failing Solana RPC tests**

```python
def test_standard_rpc_enriches_account_without_helius_das() -> None:
    async def scenario() -> None:
        adapter = SolanaRpcAdapter(
            "https://fixture.solana.example",
            client=fixture_client(account_payload),
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        observations = await adapter.enrich(
            OnChainRequest(context=context(), address=ACCOUNT)
        )
        assert observations[0].provenance.provider == "solana-public-rpc"
        assert observations[0].kind == "onchain.account_info"
        assert observations[0].normalized_payload["address"] == ACCOUNT

    asyncio.run(scenario())


def test_standard_rpc_rejects_helius_only_token_metadata() -> None:
    async def scenario() -> None:
        adapter = SolanaRpcAdapter("https://fixture.solana.example", client=unused_client())
        with pytest.raises(CapabilityUnavailableError):
            await adapter.enrich(OnChainRequest(context=context(), token=TokenIdentity(MINT)))

    asyncio.run(scenario())


def test_standard_rpc_normalizes_429_and_retry_after_without_secret_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/"
        assert "api-key" not in str(request.url)
        return httpx.Response(429, headers={"Retry-After": "2"})

    adapter = SolanaRpcAdapter(
        "https://fixture.solana.example",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        transport=one_shot_transport(),
    )
    with pytest.raises(ProviderRateLimitedError) as caught:
        asyncio.run(adapter.check_health(context=context()))
    assert caught.value.retry_after_seconds == 2
```

- [ ] **Step 2: Run the Solana tests and observe the expected import/exception failure**

Run: `pytest -q tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py`

Expected: FAIL because `SolanaRpcAdapter` and `CapabilityUnavailableError` do not exist.

- [ ] **Step 3: Implement the typed error and standard JSON-RPC adapter**

Add `CapabilityUnavailableError` to transport exports. Implement validated HTTPS endpoint handling without credential query parameters, bounded JSON-RPC POSTs, status/error normalization, safe rate-limit snapshots, and deterministic standard normalizers. Use only documented standard methods and do not add `getAsset` or any DAS method. A `null` standard result becomes a normalized `UNKNOWN` observation where an observation is contractually useful; unsupported capability remains an explicit typed error.

- [ ] **Step 4: Add credential-free Solana fixtures marked as redacted**

Store only sanitized JSON-RPC envelopes and standard response fields under `fixtures/providers/solana_rpc/`. Fixture metadata must not contain API keys, bearer values, cookies, wallet signing material, or credential-bearing URLs.

- [ ] **Step 5: Run Solana tests plus existing Helius tests**

Run: `pytest -q tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py tests/unit/test_helius_normalization.py tests/contract/test_helius_provider.py tests/unit/test_provider_transport.py`

Expected: PASS, including the existing Helius adapter behavior.

- [ ] **Step 6: Harden Helius credential transport without changing its public contract**

Add a failing assertion to the Helius transport test that configured keys are sent in a request header and never appear in `request.url` or adapter errors. Change the Helius request helper to use a redacted endpoint plus `x-api-key` header while retaining all existing Helius methods and normalized output.

- [ ] **Step 7: Run Helius regression tests and commit**

Run: `pytest -q tests/unit/test_helius_normalization.py tests/contract/test_helius_provider.py tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py`

```bash
git add packages/providers/src/memeradar_providers/transport.py packages/providers/src/memeradar_providers/solana_rpc.py packages/providers/src/memeradar_providers/helius.py fixtures/providers/solana_rpc tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py tests/unit/test_helius_normalization.py
git commit -m "feat: add standard Solana RPC provider"
```

### Task 3: Add DexScreener market, metadata, and paper-reference quote adapter

**Files:**
- Create: `packages/providers/src/memeradar_providers/dexscreener.py`
- Create: `fixtures/providers/dexscreener/pairs.json`
- Create: `fixtures/providers/dexscreener/pairs_multiple.json`
- Create: `fixtures/providers/dexscreener/metadata.json`
- Test: `tests/unit/test_dexscreener_provider.py`
- Test: `tests/contract/test_dexscreener_provider.py`

**Interfaces:**
- Produces `DexScreenerAdapter(MarketDataPort, QuotePort, SocialMetadataPort)` with `provider_name == "dexscreener"`.
- `register_token(TokenIdentity)` supports existing UUID-based market requests.
- `snapshot(MarketDataRequest)` calls `/token-pairs/v1/solana/{mint}` and emits `market.market_data` with normalized price/liquidity/volume/transaction/FDV/market-cap/pair metadata.
- `metadata(token, *, context)` emits normalized `SocialMetadata` with websites/socials only.
- `quote(QuoteRequest)` selects one eligible pair deterministically and emits `QuoteSnapshot` with `PriceSemantics.MARKET_REFERENCE`, a `QuoteMarketContext`, a positive paper-reference amount pair, and fresh provenance.
- The adapter exposes no transaction-history, holder, wallet-history, stream, DAS, security-audit, or social-analytics methods.

- [ ] **Step 1: Write failing fixture and adapter tests**

```python
def test_dexscreener_selects_highest_liquidity_solana_pair_deterministically() -> None:
    async def scenario() -> None:
        adapter = adapter_for("pairs_multiple.json")
        quote = await adapter.quote(
            QuoteRequest(
                context=context(),
                input_mint=USDC,
                output_mint=MINT,
                amount=Decimal("100"),
                slippage_bps=100,
            )
        )
        assert quote.provenance.provider == "dexscreener"
        assert quote.market_context is not None
        assert quote.market_context.pair_address == HIGH_LIQUIDITY_PAIR
        assert quote.market_context.liquidity_usd == Decimal("50000")
        assert quote.price_semantics is PriceSemantics.MARKET_REFERENCE

    asyncio.run(scenario())


def test_dexscreener_rejects_wrong_chain_missing_price_and_zero_liquidity() -> None:
    async def scenario() -> None:
        adapter = adapter_for("pairs.json", payload=invalid_pairs_payload)
        with pytest.raises(ProviderSchemaError):
            await adapter.quote(request())

    asyncio.run(scenario())


def test_dexscreener_maps_declared_social_links_without_analytics() -> None:
    async def scenario() -> None:
        metadata = await adapter_for("metadata.json").metadata(TOKEN, context=context())
        assert metadata.websites == ("https://project.example",)
        assert metadata.socials["twitter"] == "https://x.com/project"
        assert not hasattr(metadata, "mention_count")

    asyncio.run(scenario())
```

Add separate tests for successful snapshot, missing pairs, malformed numeric values, stale/future timestamps, 404, 429 with `Retry-After`, 5xx, timeout, invalid JSON, nullable optional fields, wrong token identity, pair tie-break ordering, no API-key requirement, and metadata caching without quote caching.

- [ ] **Step 2: Run the DexScreener tests and observe the missing-adapter failure**

Run: `pytest -q tests/unit/test_dexscreener_provider.py tests/contract/test_dexscreener_provider.py`

Expected: FAIL because the adapter, fixtures, and normalized adapter methods do not exist.

- [ ] **Step 3: Implement response validation and deterministic pair ranking**

Validate the official response shape at the adapter boundary. Filter to `chainId == "solana"`, require the requested mint in base or quote, parse finite positive prices and liquidity, and preserve nullable optional metrics as `None`. Rank directed output-token matches, stable quote matches, valid liquidity descending, pair creation recency, and pair address ascending. A pair with missing or non-positive liquidity remains available for a market observation with `QualityState.UNKNOWN` but is not eligible for a quote.

- [ ] **Step 4: Implement normalized market observations and social metadata**

Map only provider-neutral payload fields: `mint_address`, `pair_address`, `venue`, `base_mint`, `quote_mint`, `market_price_usd`, `price_native`, `liquidity`, volume windows, transaction windows, `fdv`, `market_cap`, `pair_created_at`, `websites`, and `socials`. Set `occurred_at` to pair creation time when valid, otherwise `observed_at`; retain `observed_at` and `ingested_at` separately. Social metadata contains links only and does not synthesize counts, sentiment, or velocity.

- [ ] **Step 5: Implement fresh paper-reference quote conversion**

Use the selected pair’s requested direction and positive `priceUsd` or `priceNative` value to calculate output amount. Mark `PriceSemantics.MARKET_REFERENCE`, include the selected pair/liquidity context, and use a short freshness window derived from the observed timestamp. Reject ambiguous direction, absent price, absent/zero liquidity, and unsupported quote currency instead of creating a fill. Do not call an external swap or execution endpoint.

- [ ] **Step 6: Add bounded transport, concurrency, and metadata cache behavior**

Use `ProviderTransport` with one adapter semaphore and bounded attempts. Parse rate-limit headers without retaining secrets. Add a bounded TTL cache for pair/social metadata keyed by Solana mint; do not cache `quote` or price-sensitive `snapshot` responses. Expose safe `last_rate_limit` and cache-hit state for doctors/tests.

- [ ] **Step 7: Add sanitized DexScreener fixtures and run the full provider slice**

Fixtures must mirror documented public response fields and contain no credential-shaped keys or secret-bearing URLs. Run:

`pytest -q tests/unit/test_dexscreener_provider.py tests/contract/test_dexscreener_provider.py tests/unit/test_price_semantics.py tests/unit/test_paper_execution.py tests/contract/test_phase3_sprint3_3.py`

Expected: PASS.

- [ ] **Step 8: Commit DexScreener**

```bash
git add packages/providers/src/memeradar_providers/dexscreener.py fixtures/providers/dexscreener tests/unit/test_dexscreener_provider.py tests/contract/test_dexscreener_provider.py
git commit -m "feat: add DexScreener market and paper quote adapter"
```

### Task 4: Add optional Ollama narrative adapter

**Files:**
- Create: `packages/providers/src/memeradar_providers/ollama.py`
- Create: `fixtures/providers/ollama/version.json`
- Create: `fixtures/providers/ollama/chat.json`
- Test: `tests/unit/test_ollama_provider.py`
- Test: `tests/contract/test_ollama_provider.py`
- Modify: `packages/providers/src/memeradar_providers/narrative.py` only for shared redacted transport helpers if duplication would otherwise violate existing conventions

**Interfaces:**
- Produces `OllamaNarrativeAdapter(NarrativePort)` with `provider_name == "ollama"`.
- `check_health(context)` performs bounded `GET /api/version`.
- `summarize(NarrativeInput)` performs non-streaming `POST /api/chat` with configured model and maps only valid structured narrative output into `NarrativeSnapshot`.
- Empty model raises `CapabilityUnavailableError` without a network call; disabled mode is represented by the composition layer and never calls Ollama.

- [ ] **Step 1: Write failing Ollama tests**

```python
def test_ollama_maps_structured_chat_response_to_advisory_snapshot() -> None:
    async def scenario() -> None:
        adapter = OllamaNarrativeAdapter(
            "http://fixture.ollama.example",
            model="fixture-model",
            client=fixture_client("chat.json"),
            transport=one_shot_transport(),
            clock=lambda: NOW,
        )
        snapshot = await adapter.summarize(narrative_input())
        assert snapshot.advisory is True
        assert snapshot.provenance.provider == "ollama"

    asyncio.run(scenario())


def test_ollama_without_model_is_optional_unavailable_and_does_not_call_http() -> None:
    async def scenario() -> None:
        client = CountingAsyncClient()
        adapter = OllamaNarrativeAdapter("http://fixture.ollama.example", model="", client=client)
        with pytest.raises(CapabilityUnavailableError):
            await adapter.summarize(narrative_input())
        assert client.calls == 0

    asyncio.run(scenario())
```

Add tests for version health, unavailable transport, invalid JSON, invalid structured content, bounded prompt content, and no API-key leakage.

- [ ] **Step 2: Run Ollama tests and observe the missing-adapter failure**

Run: `pytest -q tests/unit/test_ollama_provider.py tests/contract/test_ollama_provider.py`

Expected: FAIL because `OllamaNarrativeAdapter` does not exist.

- [ ] **Step 3: Implement the adapter using the existing narrative contract**

Validate local HTTP/HTTPS URLs without URL credentials or fragments, send optional credentials only as headers, request `stream: false`, bound model/prompt size, parse the JSON content returned in `message.content`, and reuse existing narrative validation/sanitization. Normalize unavailable, timeout, rate-limited, authentication, malformed, and schema errors with `ProviderTransport`.

- [ ] **Step 4: Run Ollama and existing narrative tests**

Run: `pytest -q tests/unit/test_ollama_provider.py tests/contract/test_ollama_provider.py tests/unit/test_narrative.py tests/unit/test_narrative_provider.py tests/unit/test_narrative_doctor.py`

Expected: PASS.

- [ ] **Step 5: Commit Ollama**

```bash
git add packages/providers/src/memeradar_providers/ollama.py fixtures/providers/ollama tests/unit/test_ollama_provider.py tests/contract/test_ollama_provider.py
git commit -m "feat: add optional Ollama narrative provider"
```

### Task 5: Implement the small bounded provider composition layer

**Files:**
- Create: `packages/providers/src/memeradar_providers/composition.py`
- Create: `tests/unit/test_provider_composition.py`
- Create: `tests/contract/test_provider_composition.py`

**Interfaces:**
- Produces `FreeFirstProviderBundle` with `chain`, `enhanced_asset_metadata`, `market`, `quote`, `social_metadata`, `social_analytics`, `narrative`, `telegram`, `optional`, and `route_plan` fields.
- Produces `build_free_first_provider_bundle(settings, *, client=None, transport=None, clock=None, custom_quote_port=None)`.
- Produces typed bounded fallback ports for `OnChainPort`, `MarketDataPort`, `QuotePort`, `SocialMetadataPort`, and `NarrativePort`; each has a concrete protocol method and never dynamically dispatches arbitrary provider methods.
- Fallback catches only `ProviderTimeoutError`, `ProviderUnavailableError`, `ProviderRateLimitedError`, `ProviderAuthenticationError`, and `ProviderSchemaError`; `CapabilityUnavailableError` stops the route and remains explicit.
- Bundle construction never instantiates an optional provider without its required endpoint/key configuration and never creates an external-wallet “adapter” that does not exist.

- [ ] **Step 1: Write failing composition tests**

```python
def test_bundle_defaults_to_dexscreener_and_public_rpc_without_credentials() -> None:
    bundle = build_free_first_provider_bundle(Settings.from_env({}), client=fixture_client())
    assert bundle.route_plan.market.providers == ("dexscreener",)
    assert bundle.route_plan.chain.providers == ("solana-public-rpc",)
    assert bundle.market.provider_name == "dexscreener"
    assert bundle.quote.provider_name == "dexscreener"
    assert bundle.social_metadata.provider_name == "dexscreener"
    assert bundle.optional["helius"] == "UNCONFIGURED_OPTIONAL"
    assert bundle.optional["birdeye"] == "UNCONFIGURED_OPTIONAL"


def test_market_fallback_is_bounded_and_records_the_failed_primary() -> None:
    fallback = FallbackMarketDataPort((FailingMarket(), SuccessfulMarket()))
    observations = asyncio.run(fallback.snapshot(market_request()))
    assert observations[0].provenance.provider == "fallback-market"
    assert fallback.fallback_count == 1
    assert fallback.last_failure_reason == "EXTERNAL_UNAVAILABLE"


def test_capability_unavailable_is_not_rewritten_as_a_fallback_success() -> None:
    fallback = FallbackOnChainPort((UnavailableEnhanced(), StandardRpc()))
    with pytest.raises(CapabilityUnavailableError):
        asyncio.run(fallback.enrich(OnChainRequest(context=context(), token=TOKEN)))
```

- [ ] **Step 2: Run composition tests and observe the missing-module failure**

Run: `pytest -q tests/unit/test_provider_composition.py tests/contract/test_provider_composition.py`

Expected: FAIL because the bundle and bounded fallback classes do not exist.

- [ ] **Step 3: Implement typed bounded fallback ports**

Create a shared private base that iterates a fixed tuple once, captures the first normalized failure reason, and exposes provider names/fallback count. Implement only the five concrete methods required by current ports. Return the first successful normalized result without averaging or mutating provenance. Re-raise the final typed error with the original safe classification when every provider fails.

- [ ] **Step 4: Implement settings-driven bundle construction**

Always construct DexScreener and standard Solana RPC from validated defaults. Construct Helius enhanced, Birdeye, RugCheck, external social, Ollama, and Telegram only when their explicit configuration permits it. Use the application route plan to order providers. Keep local wallet/risk routing as provider-neutral status entries, not a duplicate provider implementation. Accept an injected custom `QuotePort` as the only legacy/custom quote seam; do not make raw HTTP calls from paper logic.

- [ ] **Step 5: Add composition contract assertions**

Assert that `composition.py` is the only new module importing concrete provider adapters, that application source has no `memeradar_providers` import, that no fallback route contains a stream adapter for REST market data, and that optional absent credentials produce statuses rather than exceptions.

- [ ] **Step 6: Run the composition and regression suites**

Run: `pytest -q tests/unit/test_provider_composition.py tests/contract/test_provider_composition.py tests/unit/test_provider_routing.py tests/contract/test_provider_adapters.py tests/contract/test_phase2_gate.py tests/unit/test_paper_execution.py`

Expected: PASS.

- [ ] **Step 7: Commit composition**

```bash
git add packages/providers/src/memeradar_providers/composition.py tests/unit/test_provider_composition.py tests/contract/test_provider_composition.py
git commit -m "feat: compose bounded free-first provider routes"
```

### Task 6: Add and update provider doctors and readiness semantics

**Files:**
- Create: `scripts/solana_rpc_doctor.py`
- Create: `scripts/dexscreener_doctor.py`
- Create: `scripts/free_provider_doctor.py`
- Modify: `scripts/early_live_doctor.py`
- Modify: `scripts/narrative_doctor.py`
- Modify: `scripts/paper_trading_doctor.py`
- Modify: `scripts/shadow_status.py`
- Test: `tests/unit/test_solana_rpc_doctor.py`
- Test: `tests/unit/test_dexscreener_doctor.py`
- Test: `tests/unit/test_free_provider_doctor.py`
- Modify: `tests/unit/test_early_live_doctor.py`
- Modify: `tests/unit/test_shadow_tooling.py`
- Modify: `tests/unit/test_narrative_doctor.py`
- Modify: `tests/unit/test_paper_trading_doctor.py`

**Interfaces:**
- `solana_rpc_doctor.run_doctor(...)` reports public RPC health without requiring a key.
- `dexscreener_doctor.run_doctor(...)` reports public market/metadata capability without requiring a key.
- `free_provider_doctor.run_doctor(...)` returns `core_free_readiness`, `optional_enrichment_readiness`, `full_provider_readiness`, a redacted provider matrix, and safe modes.
- `early_live_doctor.run_doctor(...)` keeps legacy `checks` keys but no longer requires Helius/Birdeye for core free readiness; it adds `core_free_readiness`, `optional_enrichment_readiness`, and `full_provider_readiness`.
- `shadow_status.evaluate_free_provider_readiness(...)` returns `READY_FOR_FREE_READ_ONLY_SHADOW` only when API stack and free provider health are ready; legacy `evaluate_primary_provider_readiness` remains available for old callers/tests but is no longer used for free readiness.

- [ ] **Step 1: Write failing doctor/readiness tests**

```python
def test_free_provider_doctor_keyless_mode_has_no_credential_blocker() -> None:
    report = run_doctor(
        {
            "SOLANA_RPC_URL": "https://fixture.solana.example",
            "DEXSCREENER_API_URL": "https://fixture.dex.example",
            "HELIUS_API_KEY": "",
            "BIRDEYE_API_KEY": "",
            "RUGCHECK_API_KEY": "",
            "SOCIAL_API_KEY": "",
            "EXTERNAL_WALLET_API_KEY": "",
            "NARRATIVE_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
        },
        client=fixture_client(),
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    assert report["core_free_readiness"] == "PASS"
    assert report["optional_enrichment_readiness"] in {"OPTIONAL_UNCONFIGURED", "DEGRADED"}
    assert report["providers"]["helius"]["status"] == "UNCONFIGURED_OPTIONAL"
    assert report["providers"]["dexscreener"]["status"] == "PASS"
    assert SECRET not in json.dumps(report)


def test_early_live_doctor_does_not_require_helius_or_birdeye() -> None:
    report = run_doctor(
        {"SOLANA_RPC_URL": "https://fixture.solana.example", "DEXSCREENER_API_URL": "https://fixture.dex.example"},
        client=fixture_client(),
        transport=one_shot_transport(),
        clock=lambda: NOW,
    )
    assert report["core_free_readiness"] == "PASS"
    assert report["status"] == "PASS"
    assert report["live_detection_evidence"] == "UNVERIFIED_STREAM_TRANSPORT"
```

Add tests for public RPC/Dex timeout, 429, schema failure, optional keyed-provider absence, Ollama unavailable, disabled narrative, safe modes, and full readiness remaining blocked unless explicitly configured external providers pass.

- [ ] **Step 2: Run doctor tests and observe old mandatory-provider failures**

Run: `pytest -q tests/unit/test_solana_rpc_doctor.py tests/unit/test_dexscreener_doctor.py tests/unit/test_free_provider_doctor.py tests/unit/test_early_live_doctor.py tests/unit/test_shadow_tooling.py tests/unit/test_narrative_doctor.py tests/unit/test_paper_trading_doctor.py`

Expected: FAIL because new doctors/readiness fields do not exist and old tests still encode Helius/Birdeye mandatory semantics.

- [ ] **Step 3: Implement individual public/free doctors**

Reuse the existing redacted doctor structure and injected `httpx.AsyncClient`/`ProviderTransport`. Public RPC and DexScreener missing keys are valid; classify network failures as `BLOCKED_EXTERNAL` or `RATE_LIMITED`, malformed responses as `FAIL`, and optional provider absence as `UNCONFIGURED_OPTIONAL`. Keep process exit mapping `PASS=0`, `BLOCKED_EXTERNAL=2`, `FAIL=1`.

- [ ] **Step 4: Implement the aggregate free-provider matrix**

Run local contract/mode checks, bounded public RPC and DexScreener health checks, and local-engine import/constructor checks. Report each provider with `status`, `class`, `capability`, `credential`, `network`, `reason`, and safe latency/rate data. Do not print URLs, keys, headers, response bodies, or tokens. Core status is independent of missing Helius, Birdeye, authenticated RugCheck, external social, external wallet, Ollama, and Telegram.

- [ ] **Step 5: Refactor early-live and shadow readiness**

Keep legacy report keys for compatibility, add the three readiness levels, and base free shadow status on public RPC plus DexScreener plus local contracts. A free core external failure remains honestly blocked/degraded; it is never converted to PASS. Full provider readiness continues to require the explicitly configured full provider set. Preserve stream configuration-only and live-evidence-unverified semantics.

- [ ] **Step 6: Update paper and narrative doctors**

Make `PAPER_QUOTE_PROVIDER=dexscreener` and no custom quote key a valid local paper configuration; the doctor must still never claim live execution. Make narrative doctor route to Ollama, explicit external narrative, or disabled, and classify Ollama absence as optional rather than core failure.

- [ ] **Step 7: Run the doctor/readiness slice**

Run: `pytest -q tests/unit/test_solana_rpc_doctor.py tests/unit/test_dexscreener_doctor.py tests/unit/test_free_provider_doctor.py tests/unit/test_early_live_doctor.py tests/unit/test_shadow_tooling.py tests/unit/test_narrative_doctor.py tests/unit/test_paper_trading_doctor.py`

Expected: PASS with old Helius/Birdeye configured fixture cases still passing and keyless cases now passing core readiness.

- [ ] **Step 8: Commit readiness and doctors**

```bash
git add scripts/solana_rpc_doctor.py scripts/dexscreener_doctor.py scripts/free_provider_doctor.py scripts/early_live_doctor.py scripts/narrative_doctor.py scripts/paper_trading_doctor.py scripts/shadow_status.py tests/unit/test_solana_rpc_doctor.py tests/unit/test_dexscreener_doctor.py tests/unit/test_free_provider_doctor.py tests/unit/test_early_live_doctor.py tests/unit/test_shadow_tooling.py tests/unit/test_narrative_doctor.py tests/unit/test_paper_trading_doctor.py
git commit -m "feat: separate free and optional provider readiness"
```

### Task 7: Wire environment, Compose, Make targets, and compatibility documentation

**Files:**
- Modify: `.env.example`
- Modify: `infra/compose/docker-compose.yml`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/PRIVACY_PROVIDER_TOS.md`
- Modify: `docs/LIVE_READONLY_CHECKLIST.md`
- Modify: `docs/LIVE_SHADOW_VALIDATION.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/SECURITY.md`
- Modify: `docs/STATUS.md`
- Test: `tests/smoke/test_compose_contract.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- `.env.example` includes grouped free-first defaults and all legacy variables.
- Compose passes provider settings to API/worker server-side services, preserves exact protected modes, and adds `host.docker.internal:host-gateway` only to the narrative-capable service.
- Make targets include `solana-rpc-doctor`, `dexscreener-doctor`, and `free-provider-doctor` while retaining all existing targets.
- Documentation states the free/optional capability matrix, provider limitations, readiness meanings, and no-secret core boot.

- [ ] **Step 1: Write failing environment/Compose/documentation contract tests**

```python
def test_env_example_declares_free_first_defaults_and_legacy_aliases() -> None:
    env = (ROOT / ".env.example").read_text()
    for line in (
        "SOLANA_RPC_URL=https://api.mainnet.solana.com",
        "MARKET_DATA_PROVIDER=dexscreener",
        "DEXSCREENER_API_URL=https://api.dexscreener.com",
        "PAPER_QUOTE_PROVIDER=dexscreener",
        "WALLET_INTELLIGENCE_PROVIDER=local",
        "SOCIAL_METADATA_PROVIDER=dexscreener",
        "NARRATIVE_PROVIDER=ollama",
        "ANALYSIS_ONLY=true",
        "PAPER_TRADING=true",
        "MANUAL_EXECUTION=false",
        "AUTO_EXECUTION=false",
    ):
        assert line in env


def test_compose_keeps_provider_credentials_server_side_and_protected_modes() -> None:
    services = yaml.safe_load(COMPOSE_PATH.read_text())["services"]
    for service in ("api", "worker"):
        env = services[service]["environment"]
        assert env["ANALYSIS_ONLY"] == "true"
        assert env["PAPER_TRADING"] == "true"
        assert env["MANUAL_EXECUTION"] == "false"
        assert env["AUTO_EXECUTION"] == "false"
        assert not any(str(key).startswith("NEXT_PUBLIC_") and "KEY" in str(key) for key in env)
```

- [ ] **Step 2: Run the contracts and observe missing defaults/targets**

Run: `pytest -q tests/smoke/test_compose_contract.py tests/unit/test_config.py`

Expected: FAIL for missing new environment defaults and Make/Compose contracts.

- [ ] **Step 3: Organize `.env.example` and preserve compatibility variables**

Add CORE, SOLANA FREE-FIRST, MARKET DATA FREE-FIRST, PAPER QUOTES, RISK, WALLET, SOCIAL, NARRATIVE, TELEGRAM, AUTH, and PROTECTED MODES sections. Keep `HELIUS_RPC_URL`, `HELIUS_API_KEY`, `BIRDEYE_API_URL`, `BIRDEYE_API_KEY`, `MEMERADAR_PAPER_QUOTE_URL`, `MEMERADAR_PAPER_QUOTE_API_KEY`, `RUGCHECK_*`, `SOCIAL_*`, `EXTERNAL_WALLET_*`, `NARRATIVE_API_*`, and Telegram variables.

- [ ] **Step 4: Wire Compose provider configuration without browser secrets**

Pass non-`NEXT_PUBLIC_*` provider settings through API/worker environment mappings. Add the host gateway mapping only to the service that may instantiate the Ollama narrative adapter. Keep the Compose service dependency health checks and exact protected mode values unchanged.

- [ ] **Step 5: Add Make targets and update docs**

Add `.PHONY` entries and targets for the two individual free doctors and aggregate doctor. Replace claims that Helius/Birdeye are mandatory with the three readiness layers. Document official DexScreener capabilities, standard RPC rate-limit limitations, market-reference quote semantics, local wallet/risk primacy, no X scraping, optional analytics, and live-money lockout.

- [ ] **Step 6: Run configuration, Compose, secret, and documentation checks**

Run: `pytest -q tests/smoke/test_compose_contract.py tests/unit/test_config.py`; `make compose-config`; `make secret-scan`; `git diff --check`

Expected: PASS with no secret-shaped frontend environment variables and no protected-mode drift.

- [ ] **Step 7: Commit configuration/docs**

```bash
git add .env.example infra/compose/docker-compose.yml Makefile README.md docs/ARCHITECTURE.md docs/PROVIDERS.md docs/PRIVACY_PROVIDER_TOS.md docs/LIVE_READONLY_CHECKLIST.md docs/LIVE_SHADOW_VALIDATION.md docs/TESTING.md docs/SECURITY.md docs/STATUS.md tests/smoke/test_compose_contract.py tests/unit/test_config.py
git commit -m "docs: document free-first provider operation"
```

### Task 8: Full TDD regression, quality gates, and final integration

**Files:**
- Modify: `docs/STATUS.md` with final command evidence and remaining external classifications
- Modify: any touched test or adapter only when a fresh verification failure identifies a real compatibility defect

**Interfaces:**
- All existing application, provider, replay, paper, frontend, security, migration, Compose, and doctor contracts remain green.
- Keyless provider composition initializes successfully with all optional credential values empty.
- No claim of external PASS is made without a live command result.

- [ ] **Step 1: Run all targeted provider and routing tests**

Run:

```bash
pytest -q tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py tests/unit/test_dexscreener_provider.py tests/contract/test_dexscreener_provider.py tests/unit/test_ollama_provider.py tests/contract/test_ollama_provider.py tests/unit/test_provider_composition.py tests/contract/test_provider_composition.py tests/unit/test_provider_contracts.py tests/unit/test_provider_routing.py tests/unit/test_config.py tests/unit/test_early_live_doctor.py tests/unit/test_shadow_tooling.py
```

Expected: 0 failures.

- [ ] **Step 2: Run static checks**

Run: `make lint`; `make typecheck`; `make compose-config`; `make secret-scan`; `make migration-check`; `make security-review`; `make sbom`

Expected: exit 0 for each command.

- [ ] **Step 3: Run the full authoritative gate**

Run: `make verify`

Expected: exit 0; record exact test/pass/skip counts from fresh output.

- [ ] **Step 4: Run local/keyless acceptance and individual doctors**

Run:

```bash
env HELIUS_API_KEY= BIRDEYE_API_KEY= RUGCHECK_API_KEY= SOCIAL_API_KEY= EXTERNAL_WALLET_API_KEY= NARRATIVE_API_KEY= MEMERADAR_PAPER_QUOTE_API_KEY= TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= make free-provider-doctor
env HELIUS_API_KEY= BIRDEYE_API_KEY= RUGCHECK_API_KEY= SOCIAL_API_KEY= EXTERNAL_WALLET_API_KEY= NARRATIVE_API_KEY= MEMERADAR_PAPER_QUOTE_API_KEY= TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= make paper-trading-doctor
make solana-rpc-doctor
make dexscreener-doctor
make provider-doctor
make birdeye-doctor
make rugcheck-doctor
make social-doctor
make external-wallet-doctor
make narrative-doctor
make telegram-doctor
```

Expected: local/keyless contracts PASS; optional missing providers are `UNCONFIGURED_OPTIONAL`; live public endpoint outcomes are recorded as `PASS`, `RATE_LIMITED`, `BLOCKED_EXTERNAL`, or `DEGRADED` exactly as returned. No credential is echoed.

- [ ] **Step 5: Inspect final diff and repository sync**

Run: `git diff HEAD~1 --check`; `git status --short`; `git log -5 --oneline`; `git fetch origin`; `git rev-parse --short HEAD`; `git rev-parse --short origin/main`

Confirm no unrelated edits, unsafe mode changes, generated secrets, provider-specific imports in application/domain, or accidental frontend redesign.

- [ ] **Step 6: Update status evidence and commit final reconciliation**

Record the actual targeted/full test counts, doctor classifications, keyless result, and external blockers in `docs/STATUS.md`. Commit only after fresh verification output is read.

```bash
git add docs/STATUS.md
git commit -m "chore: record free-first provider verification"
```

- [ ] **Step 7: Push and verify synchronization**

```bash
git push origin main
git fetch origin
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Report the exact final commit, branch, changed/new files, provider matrix, test counts, doctor classifications, remaining external limitations, and local/origin synchronization.
