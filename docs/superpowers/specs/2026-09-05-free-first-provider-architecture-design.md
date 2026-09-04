# FREE-FIRST Provider Architecture Design

**Status:** Approved for implementation  
**Date:** 2026-09-05  
**Baseline:** `main` at `ba5de244152d2c45e678cd07d44265e67c2f4ee1`

## Goal

Make MemeRadar bootable and useful for local analysis and protected paper/read-only shadow work with approximately `$0` mandatory external API cost, while preserving the existing provider-neutral contracts, deterministic analysis, replay behavior, and execution protections.

The migration is intentionally additive. Existing Helius, Birdeye, RugCheck, social, narrative, external-wallet, Telegram, stream, fixture, and launchpad adapters remain available. Free providers become the default path only where their documented capabilities are sufficient.

## Non-goals

- Replacing the existing provider framework or rewriting the application into a provider registry.
- Making public Solana RPC production-grade or pretending it supplies Helius DAS data.
- Turning DexScreener into a transaction, wallet, stream, security, or social-analytics provider.
- Adding X/Twitter scraping, private-key handling, signing, live order submission, or live-money execution.
- Rebuilding or redesigning the frontend.
- Treating an external provider response, third-party label, or narrative output as trading authority.

## Invariants

The following values remain protected and validated by `Settings.from_env`, Compose, shadow startup, doctors, and tests:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Domain and application code continue to consume normalized contracts. Provider-specific SDKs, HTTP transports, response envelopes, credentials, and retry details remain in the provider package or composition root. Every external observation retains provider provenance, source identity, observed/ingested timestamps, quality/freshness, and normalized payload data. Missing evidence remains `UNKNOWN` or unavailable rather than being converted into a safe value.

## Architecture

The existing application ports remain the stable seam. The capability vocabulary is extended minimally so a provider can advertise what it really does without being selected merely because its name appears in configuration.

```text
application/domain contracts
        ^
provider-neutral capability plan and ports
        ^
bounded provider composition/fallback layer
        ^
existing and new provider adapters
        ^
shared ProviderTransport and injected HTTP clients
```

The composition layer is small and explicit. It builds ordered providers for a capability and performs at most one attempt per configured provider in that ordered list. It does not recursively fall back, average conflicting values, or turn a capability-unavailable response into an unrelated capability.

### Capability routing

The existing enum values remain for compatibility. New values represent the distinct capabilities required by the free-first plan:

| Capability | Default/free provider | Optional provider | Important boundary |
| --- | --- | --- | --- |
| `CHAIN_RPC` / `ON_CHAIN` | `solana-public-rpc` | Helius RPC | Standard JSON-RPC only on the free path |
| `ENHANCED_ASSET_METADATA` / `DAS_ENHANCED` | unavailable | Helius | Never emulated by public RPC |
| `TRANSACTION_HISTORY` | standard RPC where the requested operation supports it | Helius enhancement | No DexScreener substitution |
| `REALTIME_STREAM` | unavailable unless a configured stream adapter exists | Helius/Birdeye stream | Stream remains separate from REST |
| `MARKET_SNAPSHOT` / `MARKET_DATA` | DexScreener | Birdeye | Normalized observations only |
| `MARKET_QUOTE` / `QUOTE` | DexScreener paper reference quote | configured legacy/custom quote | Never presented as live execution authority |
| `PAIR_DISCOVERY` | DexScreener token-pairs endpoint | Birdeye where configured | Solana and token identity are mandatory |
| `SOCIAL_METADATA` | DexScreener `info.websites`/`info.socials` | existing social provider | Links only; no invented analytics |
| `SOCIAL_ANALYTICS` / `SOCIAL_DATA` | unavailable | existing social provider | Missing analytics is unavailable, not zero |
| `RISK_SUMMARY` / `RISK_DATA` | local deterministic engine plus public RugCheck where configured | authenticated RugCheck | RugCheck never replaces local checks |
| `WALLET_ENRICHMENT` | local wallet/holder/flow/scoring modules | external wallet | External labels are corroboration only |
| `NARRATIVE` | Ollama when configured/reachable | explicitly selected external narrative | Advisory only; disabled is valid |
| `ALERT_DELIVERY` / `NOTIFICATION` | unavailable | Telegram | Optional and rate-limited |

Legacy capability names remain accepted by health, fixture, persistence, and read-API code. New providers expose both the precise capability set and the legacy port they implement where applicable.

## Provider adapters

### Generic Solana RPC

`packages/providers/src/memeradar_providers/solana_rpc.py` introduces `SolanaRpcAdapter` for standard JSON-RPC methods that the repository can use without enhanced APIs: health, account information, transaction lookup, address signatures, blocks, and block retrieval. The adapter normalizes standard responses into provider-neutral `Observation` records and exposes a safe health check.

The default endpoint is `https://api.mainnet.solana.com`. The endpoint is treated as rate-limited and best-effort. The adapter uses `ProviderTransport` for bounded timeout/retry/429 behavior, honors `Retry-After`, limits in-flight requests with a semaphore, records safe rate-limit metadata, and never emits response bodies or credentials in errors.

A standard RPC request for a Helius-only DAS/enhanced asset operation returns an explicit capability-unavailable error. It does not issue an invented JSON-RPC method or reinterpret a mint account response as DAS metadata.

### DexScreener

`packages/providers/src/memeradar_providers/dexscreener.py` implements the existing `MarketDataPort` and `QuotePort` contracts and a small provider-neutral social-metadata port. It uses the public API documented at <https://docs.dexscreener.com/api/reference>. The adapter maps pair data into normalized market observations and quote evidence containing:

- Solana chain and token identity;
- base/quote mint semantics;
- pair address and DEX identity;
- price/reference value, liquidity, volume, transaction aggregates, FDV, and market cap when present;
- pair creation timestamp when present;
- websites and declared social links when present;
- provider/source/parser provenance and freshness.

The adapter does not implement discovery of arbitrary chain transactions, holder history, wallet history, a realtime stream, DAS, security auditing, X search, follower/engagement counts, sentiment, or social velocity.

The adapter uses a token registry like the existing Birdeye adapter for UUID-based `MarketDataRequest` compatibility and takes mint addresses directly from `QuoteRequest`. It provides bounded metadata caching for stable pair/social metadata only. Price-sensitive snapshots and quotes are not served from the metadata cache.

### Deterministic pair selection

For a requested Solana mint, pair candidates are normalized and ranked in this order:

1. `chainId` must equal `solana`.
2. The requested mint must equal either the base or quote token address.
3. The selected direction must have a finite, strictly positive price and a valid positive liquidity value.
4. A pair whose opposite token matches the requested output mint receives priority for a directed quote.
5. Known stable quote assets receive priority for USD-style reference quotes; otherwise the provider’s native quote remains explicit.
6. Higher valid USD liquidity ranks above lower liquidity.
7. A more recent `pairCreatedAt` breaks otherwise equal quality ties.
8. The lexicographically smallest normalized pair address is the final deterministic tie-break.

Pairs with missing, malformed, zero, or negative liquidity are not eligible for a normal paper quote. Missing liquidity is retained as unknown in market observations but cannot authorize a quote. Missing/null/malformed/non-positive prices are rejected rather than coerced to zero. If no eligible pair remains, the operation returns a normalized unavailable/schema result; it never selects the first API item.

DexScreener paper quotes are explicitly marked as market-reference-derived paper evidence. They carry pair/liquidity metadata and a freshness window, and the existing paper fill model remains responsible for adverse slippage, fees, fill ratio, and ledger mutation. These quotes are never used to claim a live executable route.

### Ollama narrative

`packages/providers/src/memeradar_providers/ollama.py` implements `NarrativePort` against the local Ollama HTTP API. It uses a version/health endpoint and non-streaming structured chat generation. The model is configuration-driven; an empty model is unconfigured rather than a hard-coded runtime dependency. The adapter maps valid structured output into the existing advisory `NarrativeSnapshot` contract, bounds request size, redacts errors, and returns explicit unavailable/degraded failures when Ollama is absent.

`NARRATIVE_PROVIDER=disabled` bypasses network access and returns the existing application-level unavailable narrative behavior. An external narrative adapter is selected only by an explicit external provider setting; Ollama absence never blocks core readiness.

## Composition and fallback

`packages/providers/src/memeradar_providers/composition.py` provides the narrow composition layer. It receives validated settings and optional injected clients/transports, constructs only configured adapters, and exposes ordered capability routes. The application routing module defines provider-neutral route names and capability policy; it does not import provider classes.

The route order is:

```text
standard chain RPC: configured Helius standard endpoint -> SOLANA_RPC_URL
Helius enhanced/DAS: Helius only -> capability unavailable
market: DexScreener -> configured Birdeye
paper quote: DexScreener -> configured legacy/custom quote seam
wallet: local application engines -> external enrichment
social metadata: DexScreener -> external social enrichment
social analytics: external social provider only
narrative: Ollama -> explicitly configured external narrative -> disabled
alerts: configured Telegram -> optional/unconfigured
```

Fallback catches only normalized provider failures that mean the same capability cannot currently be served: timeout, transport unavailability, rate limit, authentication failure, and schema/data failure. Capability-unavailable is returned directly for a capability that the next provider cannot legitimately satisfy. Fallback is bounded by the route length and exposes selected provider, fallback count, reason code, and final state for health/telemetry.

Helius and Birdeye adapters are not deleted or silently reinterpreted. A configured Helius endpoint/key remains the enhanced path, while the standard route can use public RPC. A configured Birdeye adapter remains an optional market/discovery fallback and its REST/stream distinction remains explicit.

## Configuration

`Settings` gains validated, optional provider fields with safe defaults and compatibility aliases:

- `SOLANA_RPC_URL` defaults to `https://api.mainnet.solana.com`.
- `MARKET_DATA_PROVIDER` defaults to `dexscreener`.
- `DEXSCREENER_API_URL` defaults to `https://api.dexscreener.com`; its key is optional and never placed in a URL.
- `PAPER_QUOTE_PROVIDER` defaults to `dexscreener`; existing custom quote variables remain valid.
- `WALLET_INTELLIGENCE_PROVIDER` defaults to `local`.
- `SOCIAL_METADATA_PROVIDER` defaults to `dexscreener`; existing social analytics variables remain optional.
- `NARRATIVE_PROVIDER` defaults to `ollama`; `disabled` is supported and external behavior requires an explicit external setting.
- `NARRATIVE_API_URL` defaults to `http://host.docker.internal:11434`, permitting local Ollama without requiring it.

Existing Helius, Birdeye, RugCheck, social, external-wallet, narrative, Telegram, Jupiter, and custom quote variables continue to parse. Empty optional credentials are represented as `None` and cannot make core configuration invalid. New fields are included in configuration hashing where they affect normalized output or routing.

Compose passes provider configuration only to server-side API/worker services. No `NEXT_PUBLIC_*` provider secret is introduced. Linux Compose adds `host.docker.internal:host-gateway` only to the service that can invoke narrative work; the stack does not depend on Ollama being installed.

## Readiness and doctors

The existing doctor vocabulary remains (`PASS`, `FAIL`, `BLOCKED_EXTERNAL`) and gains explicit classification fields (`core`, `optional`, `credential`, `capability`, `external_reason`) instead of treating every missing provider as a failure.

The free aggregate doctor reports:

```text
CORE_FREE_READINESS
  local contracts/modes
  local wallet/risk engines
  standard Solana RPC
  DexScreener market and paper quote capability
  free social metadata capability

OPTIONAL_ENRICHMENT_READINESS
  Helius
  Birdeye
  authenticated RugCheck
  external social analytics
  external wallet
  Ollama availability/model
  Telegram

FULL_PROVIDER_READINESS
  only PASS when all explicitly required/configured provider checks pass
  never equivalent to live-money readiness
```

`early_live_doctor.py` and `shadow_status.py` use core free readiness for the read-only shadow verdict. A healthy keyless local stack may report `READY_FOR_FREE_READ_ONLY_SHADOW`; it cannot report `PROVIDERS_READY` for a full external provider set or any live execution state. Stream transport and decoder verification remain separate evidence and are not promoted by a successful REST call.

The individual doctors are preserved and extended for Solana RPC, Helius, DexScreener, Birdeye, RugCheck, social, external wallet, Ollama/narrative, and Telegram. Network checks are bounded and injectable in tests. CI remains offline/deterministic; live doctor results may honestly be `BLOCKED_EXTERNAL`, `RATE_LIMITED`, `DEGRADED`, or `OPTIONAL_UNCONFIGURED`.

## Error handling, rate limits, and observability

New adapters reuse `ProviderTransport` and its typed errors, with per-adapter concurrency bounds and no uncontrolled retry loops. HTTP 429 responses preserve safe retry metadata, including bounded `Retry-After`; 5xx, timeout, malformed JSON, invalid schemas, and authentication failures are normalized. Provider URLs are validated to reject credentials and fragments. API keys and bearer tokens are sent only in headers where supported and are never included in logs, provenance, fixture payloads, or exception text.

Stable DexScreener pair and social metadata may be cached in a bounded process-local cache with explicit TTL and cache-hit telemetry. Quotes and price-sensitive market observations always perform a fresh request. The provider route records the actual selected source and fallback reason; material disagreement is retained as separate provenance rather than averaged.

## Testing strategy

Tests are added before implementation for each slice:

1. capability enum, route policy, composition order, bounded fallback, and keyless settings;
2. Solana standard JSON-RPC normalization, method boundaries, retries, 429, and no-DAS behavior;
3. DexScreener fixtures and adapter normalization, pair ranking, invalid/missing data, social metadata, quote semantics, cache boundaries, and all transport classes;
4. Ollama structured output, model-unconfigured behavior, unavailable/disabled behavior, and advisory contract;
5. readiness/doctor matrices, early-live/shadow status, and protected modes;
6. Compose/env/secret-scan contracts and the full existing suite.

The keyless acceptance environment leaves all optional credential variables empty. It must initialize `Settings`, local wallet/risk engines, protected paper execution, and the provider composition without configuration failure. External probes can independently be blocked or rate-limited without weakening that result. Existing Helius/Birdeye/RugCheck/social/narrative/Telegram/fixture tests remain in the verification set.

## Documentation and acceptance

The implementation updates README, architecture/provider/privacy/read-only/shadow/testing/status documentation and `.env.example` to describe FREE-FIRST, PAID-OPTIONAL, provider-independent, capability-based routing, local analysis primary, and keyless core boot. Limitations of public RPC, DexScreener market references, missing social analytics, optional Ollama, and optional alerts are explicit.

Acceptance requires:

- all protected modes remain exact;
- no required paid/keyed credential for core boot/readiness;
- generic standard Solana RPC is usable without Helius and never claims DAS;
- DexScreener is default for market/paper quote/social metadata where valid;
- deterministic pair selection and quote validation reject unsafe/ambiguous data;
- local wallet/risk intelligence remains default and external providers remain enrichment;
- Ollama is optional/advisory and disabled mode is clean;
- full repository verification passes, with external failures classified honestly;
- implementation is committed and pushed without force-pushing or discarding unrelated work.
