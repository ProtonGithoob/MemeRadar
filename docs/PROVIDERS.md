# Provider Strategy and Contracts

Providers are replaceable adapters. Domain code must never depend directly on provider response types.

## Capability map

| Capability | Primary planned source | Secondary/fallback | Notes |
|---|---|---|---|
| Solana RPC/on-chain enrichment | Helius | standard Solana RPC / another provider | normalize before domain use |
| Streaming/webhook observations | Helius | polling/WSS fallback | exact product chosen by measured latency/cost |
| New token/pool + market data | Birdeye | DEX Screener / direct protocol parsing | independent corroboration preferred |
| Token security | on-chain checks + Birdeye/RugCheck | independent internal checks | third-party result never sole authority |
| Social/X | compliant X data provider/API | manually configured alternative | preserve ToS; no brittle scraping dependency |
| Narrative LLM | configurable provider | disabled/fallback provider | optional, structured output only |
| Quote/routing | Jupiter | disabled if unavailable | execution phase only |
| Telegram | Telegram Bot API | notification abstraction later | outbox/retry required |

## Ports

### CandidateDiscoveryPort
- stream/poll new token/pool candidates;
- return canonical source IDs and event times;
- support checkpoint/resume where provider permits.

### MarketDataPort
- token/pool snapshots;
- price/liquidity/volume/trade stats;
- recent trades/unique maker evidence where available;
- quote/depth information where supported.

### OnChainPort
- mint metadata and authority state;
- transaction/account lookups;
- holder/token-account data;
- wallet activity/funding evidence.

### RiskDataPort
- security findings with severity and evidence;
- must preserve UNKNOWN versus SAFE;
- provider taxonomy maps to internal stable reason codes.

### SocialDataPort
- search/stream configured token/KOL references;
- normalized author/post identity, timestamps and metrics;
- compliant source references.

### NarrativePort
Input: bounded normalized social/evidence bundle.
Output: strict schema containing narrative, novelty, organic/promo assessment, sentiment/uncertainty and evidence IDs. No free-form command execution.

### QuotePort
- input token pair/amount/slippage policy;
- output quote, price impact, route, expiry/freshness metadata;
- no signing side effect.

### ExecutionPort
- build/submit/reconcile transaction;
- isolated from analysis runtime;
- supports simulation/dry-run;
- idempotency and finality state required.

### NotificationPort
- typed alert payload;
- delivery receipt/error classification;
- no domain state changes inside adapter.

## Implemented application contract surface

Sprint 2.1 defines the provider ports in `packages/application/src/memeradar_application/provider_contracts.py`. The protocols are application-facing and asynchronous; provider SDKs and transport response types remain outside the domain package.

| Port | Normalized request/result contract |
|---|---|
| `CandidateDiscoveryPort` | `DiscoveryRequest` -> `DiscoveryCandidate` values with `TokenIdentity`, optional `PoolIdentity`, source ID, event timestamps and `Provenance` |
| `MarketDataPort` | `MarketDataRequest` -> provider-independent domain `Observation` values |
| `OnChainPort` | `OnChainRequest` -> provider-independent domain `Observation` values |
| `RiskDataPort` | `RiskDataRequest` -> `RiskFinding` values preserving `QualityState.UNKNOWN` |
| `SocialDataPort` | `SocialDataRequest` -> `SocialMention` values with author/post identity, timestamps, metrics and provenance |
| `NarrativePort` | bounded `NarrativeInput` -> strict `NarrativeSnapshot`; output is advisory evidence only |
| `QuotePort` | `QuoteRequest` -> `QuoteSnapshot` with route, impact, freshness and provenance; no signing side effect |
| `ExecutionPort` | `ExecutionRequest` -> unsigned `ExecutionPlan`, `ExecutionReceipt` and reconciliation; live submission remains policy-gated and unused |
| `NotificationPort` | `NotificationRequest` -> `DeliveryReceipt`; adapters do not mutate domain state |

Shared request contexts carry a bounded correlation ID and optional deadline. The keyless provider framework in `packages/providers/src/memeradar_providers/` supplies callback-based transport resilience, health/quota/freshness projections, recursively redacted fixture recording and deterministic fake responses. These seams are tested without provider credentials; live acceptance remains a separate adapter-phase concern.

## Helius / Solana read layer

Sprint 2.2 implements the read-only Helius adapter in `packages/providers/src/memeradar_providers/helius.py`. `HeliusRpcAdapter` maps `getAsset`, `getAccountInfo` and `getTransaction` JSON-RPC/DAS responses into canonical `TokenIdentity`, account and transaction records plus application `Observation` values. It validates Solana base58 identities, preserves `occurred_at`/`observed_at`/`ingested_at`, attaches Helius/source/parser provenance, forwards request correlation IDs, and classifies timeout, availability, authentication, rate-limit and schema failures without retaining raw response text.

Token metadata explicitly distinguishes SPL Token and Token-2022 programs. Mint and freeze authorities normalize to `ACTIVE`, `REVOKED`, `UNKNOWN` or `INVALID`; missing evidence remains `UNKNOWN` and never becomes safe evidence. Invalid account keys, owner values, numeric fields and future transaction times fail closed as classified schema errors. `last_rate_limit` exposes only safe quota/reset metadata for health reporting. The adapter has no signing or execution path.

`HeliusObservationNormalizer` and `HeliusStreamConsumer` in `helius_stream.py` form the webhook/WebSocket seam. They accept only injected async sources, redact credential-shaped fields, map event types to an allow-list, validate event timestamps, and create deterministic observation IDs from `helius` plus the provider source ID. Duplicate deliveries are forwarded so downstream persistence can apply its idempotency policy. Reconnects are bounded and cancellation propagates; untrusted messages cannot invoke execution or mutate configuration.

The explicit `make provider-doctor` command runs one bounded, read-only `getHealth` call when both `HELIUS_RPC_URL` and `HELIUS_API_KEY` are configured. Its JSON report includes only configuration presence, network/auth/schema status, rounded latency, safe rate-limit metadata and the protected operating modes. It returns `PASS`, `FAIL` or `BLOCKED_EXTERNAL`; the current keyless checkout reports `BLOCKED_EXTERNAL` with `CONFIGURATION_MISSING`.

## Adapter requirements

Every network adapter must implement:
- explicit connect/read/request timeout;
- bounded retries with exponential backoff+jitter only for retryable classes;
- rate-limit handling;
- structured redacted errors;
- request correlation;
- provider health metrics;
- response/schema validation;
- fixture/contract tests;
- cancellation-safe async behavior where relevant.

## Freshness and conflicts

No “latest value wins” without provenance. Persist provider and timestamps. Feature composition rules explicitly choose or combine observations.

When critical providers disagree materially:
- record conflict;
- reduce confidence;
- trigger additional verification if configured;
- block live execution when uncertainty crosses policy.

## Provider doctors

Each real provider receives a key-safe doctor command that reports:
- configuration present/missing;
- DNS/network reachability where applicable;
- authentication result;
- one bounded read-only call;
- schema parse status;
- latency;
- rate-limit/quota metadata when available.

Never print secret values.

## Fixture policy

Record only payloads safe to commit after redaction, or construct faithful synthetic fixtures. Fixture metadata records provider, endpoint/capability, capture date, schema/parser version and redaction status.

## Cost controls

- Central request budgets per provider/capability.
- Prefer streaming/cache reuse to repeated full polling.
- Coalesce duplicate enrichment for the same token/window.
- Budget LLM calls separately and cache by evidence/config hash.
- Expose quota/cost telemetry to the operator UI.

## Future repo reuse guidance

External open-source repositories may be studied/reused only after license and dependency review. Prefer adopting isolated protocol parsers/IDLs/connectors behind these ports rather than importing entire trading frameworks into the domain.
