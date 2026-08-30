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

## Birdeye / DEX market layer

Sprint 2.3 implements the read-only `BirdeyeRestAdapter` in `packages/providers/src/memeradar_providers/birdeye.py`. It maps the new-listing endpoint (`/defi/v2/tokens/new_listing`) into canonical `DiscoveryCandidate` values and maps the supported token market-data, trade-data, holder and token-security endpoints into provider-independent `Observation` values. Birdeye response envelopes, field names and request paths remain inside the provider package; normalized observations carry canonical Solana token identities, ordered event timestamps, quality state and Birdeye/parser provenance.

The adapter sends the configured API key only as the `x-api-key` header, identifies the Solana chain with `x-chain: solana`, forwards a bounded correlation ID and never places credentials in URLs, payloads, fixtures, exceptions or doctor output. Its injected `ProviderTransport` applies timeout, retry, rate-limit and circuit policies, while HTTP/auth/schema failures remain classified provider errors. `BirdeyeRestAdapter.check_health` performs one read-only `/defi/networks` request and validates the returned list/mapping without making a write-capable call.

`BirdeyeListingNormalizer` and `BirdeyeDiscoveryFallback` in `birdeye_stream.py` form a stream-first, bounded polling-fallback seam for untrusted new-listing messages. Malformed messages are counted and skipped, duplicates are retained for downstream idempotency, reconnects are bounded and cancellation propagates. `BirdeyeObservationResolver` marks expired fresh evidence `STALE`, preserves `UNKNOWN`/`INVALID`/`CONFLICTED`, retains source IDs and values and emits explainable `CONFLICTED` evidence for material numeric disagreement.

The explicit `make birdeye-doctor` command performs one bounded, read-only supported-networks call when `BIRDEYE_API_URL` and `BIRDEYE_API_KEY` are configured. It reports only configuration presence, network/auth/schema status, rounded latency, safe rate-limit metadata and protected modes. Synthetic fixtures and keyless contract tests are committed under `fixtures/providers/birdeye/`; live acceptance remains `BLOCKED_EXTERNAL` when the endpoint/key configuration is absent. Reference endpoint documentation: [new listing](https://docs.birdeye.so/reference/get-defi-v2-tokens-new_listing), [market data](https://docs.birdeye.so/reference/get-defi-v3-token-market-data), [trade data](https://docs.birdeye.so/reference/get-defi-v3-token-trade-data-single), [holder data](https://docs.birdeye.so/reference/get-defi-v3-token-holder) and [supported networks](https://docs.birdeye.so/reference/get-defi-networks).

## Launchpad / DEX coverage

Sprint 2.4 adds provider-local `PumpFunAdapter`, `PumpSwapAdapter`, `RaydiumAdapter` and `MeteoraAdapter` in `packages/providers/src/memeradar_providers/launchpad_dex.py`. Each adapter accepts an injected untrusted event envelope, applies a venue-specific event allow-list and field-alias map, validates canonical Solana mint/pool/quote addresses, preserves event-time ordering and emits a normalized `ParsedProtocolEvent`. No protocol SDK, network call or provider payload type enters the domain layer.

`CanonicalIdentityMapper` maps a mint and optional pool to deterministic UUID5 `TokenIdentity`/`PoolIdentity` values, and `CanonicalDuplicateDetector` reports token/pool key collisions with prior source IDs while retaining duplicate deliveries for downstream idempotency. Synthetic event fixtures and replay contracts for all four venues live under `fixtures/providers/launchpad_dex/`. The adapter boundary is intentionally keyless; live protocol acceptance is a separate read-only gate and remains `BLOCKED_EXTERNAL` when no provider endpoint or credentials are configured.

The analysis-only manual input path is exposed at `POST /v1/manual/mints`. It requires the configured `OPERATOR_API_TOKEN` bearer credential, returns `503` when operator authentication is not configured, validates a canonical mint and creates a deterministic `manual:<mint>` discovery candidate. It reports duplicate submissions without dropping them and always returns `execution_enabled: false`; it has no signing, quote, transaction or live-money path.

The E2.5 rich lifecycle extension adds schema-v2 `ProtocolEventType` values for
launch, trade, bonding-curve progress, graduation/migration, pool creation,
creator-fee claims and fee-recipient changes. `ProtocolEventOrigin` keeps
native protocol facts separate from derived classifications; for example,
`WHALE_TRADE` is `DERIVED` only when an explicit deterministic trade-size flag
is present. A reliable integer `bonding_curve_progress_bps` value is validated
in the inclusive `0..10000` range and is retained as feature-ready evidence.

`ParsedProtocolEvent.to_observation()` maps rich events to provider-neutral
`protocol.lifecycle` observations with deterministic IDs, schema/parser
versions, venue/source provenance and ordered event timestamps. The injected
`ProtocolEventStreamFallback` consumes an async stream first, retries only
bounded transport outages, sorts by event time, retains duplicate deliveries
for downstream idempotency and invokes one bounded poll fallback after the
retry budget. It has no network client, persistence, signer or execution
authority. Synthetic Pump.fun/PumpSwap replay data and malformed/duplicate
contracts live in `fixtures/providers/launchpad_dex/`; live protocol access
remains a separate `BLOCKED_EXTERNAL` acceptance.

## Correlation / launch micro-feature seam

Research extension E6.0 consumes only application-facing normalized
`Observation`, `SocialMention`, `WalletActivity`,
`TokenSmartMoneyScore` and `RiskAssessment` values.
`CorrelationWindowBuilder` is provider-independent; provider adapters do not
cross into it and no SDK, HTTP client, persistence session, signer or
execution port is available in the module.

The builder supports event-time windows `5s`/`15s`/`30s`/`60s` plus
`1m`/`5m`/`15m`, deterministic reverse-delivery replay, bounded input
counts, equivalent duplicate collapse and fail-closed future/conflict/
malformed handling. Its output preserves provenance, evidence IDs, freshness,
reason codes, source-category diversity, version and config hash. It is an
advisory feature seam only; a social, market, protocol, wallet or external
label burst cannot authorize `ENTRY_READY`.

## Versioned AlphaStrategy seam

Research extension E6.1 is intentionally outside the provider layer.
`AlphaStrategy`, `StrategyPolicy`, `AlphaScoreV1Strategy` and
`StrategySnapshot` live in
`packages/application/src/memeradar_application/alpha_strategy.py` and
consume only immutable domain snapshots. The module imports no provider SDK,
HTTP client, persistence session, signer or execution port. It applies the
documented AlphaScore v1 weights and risk penalties, preserves hard-block and
freshness/UNKNOWN semantics, and records strategy/version/config identity for
replay. Its output is advisory with a permanently false execution-eligibility
predicate. The synthetic fixture under
`fixtures/providers/alpha_strategy/` is the keyless acceptance path; no live
provider success is implied.

## External wallet intelligence / cross validation

Research extension E6.2 adds the provider-neutral
`ExternalWalletIntelligencePort` plus bounded request/result contracts in
`packages/application/src/memeradar_application/external_wallet.py`.
`ExternalWalletLabel` and `ExternalWalletTokenSignal` retain source name,
source confidence, observed time, expiry/TTL, raw source ID, provenance,
evidence references and quality state. Token signals can carry tracked-supply,
bundle, side-wallet-cluster and security/rug fields as bounded corroborating
evidence.

The application `ExternalWalletReconciler` accepts fresh internal
`SmartWalletScore` records and the existing `WalletGraphSnapshot`. Only
agreement with a qualified internal score receives a bounded confidence bonus;
different/conflicting labels become `CONFLICTED_EXTERNAL_WALLET_LABEL`, stale
labels cannot add positive confidence, and graph-connected wallets count as one
actor cluster. External fields never mutate internal wallet scores, replace
deterministic token-security hard gates or authorize execution.

`FixtureExternalWalletIntelligenceAdapter` in
`packages/providers/src/memeradar_providers/external_wallet.py` is the
network-free replay adapter. Its redacted fixture lives under
`fixtures/providers/external_wallet/` and contains no credentials. No GMGN,
CabalSpy or other live adapter is enabled: this checkout has no documented and
legally approved operator endpoint contract, so adding a brittle scraper would
violate the provider and security boundaries. `make external-wallet-doctor`
reports configuration presence and returns `BLOCKED_EXTERNAL` for missing or
unsupported live configuration without probing arbitrary URLs or emitting
secrets. Live acceptance is separate from the keyless fixture PASS.

## RugCheck / token-security risk layer

Sprint 3.1 adds the provider-local `RugCheckRestAdapter` in `packages/providers/src/memeradar_providers/rugcheck.py`. It performs a read-only `GET /v1/tokens/{id}/report/summary` request, validates the official summary shape, and maps each `risks[]` item into an application `RiskFinding` with the requested token, source ID, observation timestamp and `QualityState.FRESH`. The adapter accepts an optional JWT through the `Authorization: Bearer ...` header; it never places credentials in a URL, report body, fixture, exception or doctor output. The adapter uses the shared bounded transport policy and exposes only safe rate-limit metadata.

The official `danger`, `critical` and `block` levels remain `RiskSeverity.BLOCK` findings at the provider boundary, but the application `TokenSecurityEvaluator` treats those third-party findings as uncorroborated warnings. Only deterministic on-chain evidence can establish the authority hard gates; a severe provider finding becomes a hard block only after an independent on-chain corroboration path is implemented. Provider `warn` and unknown levels remain warning/unknown advisory evidence. RugCheck verification fields are normalized as `VERIFICATION_STATUS` with `INFO` severity and are never an endorsement, score boost or execution gate.

The evaluator consumes Helius-normalized `onchain.token_metadata` observations. Active mint or freeze authority is a hard block under the current policy. Missing, unknown, invalid, conflicted or stale critical authority evidence produces `UNKNOWN` and is not execution-eligible. Token-2022 program identity and extension names are retained in normalized Helius payloads; security-relevant extensions are surfaced as explicit warnings and do not silently become safe evidence. The default authority-evidence TTL is five minutes, and every resulting risk assessment carries a version, configuration hash, reason codes and all evidence references.

`make rugcheck-doctor` performs one bounded read-only `GET /ping` call when `RUGCHECK_API_URL` is configured. The official ping response must contain `message: pong`; the optional `RUGCHECK_API_KEY` is reported only as present/missing and is sent as a bearer header when set. Missing URL, unavailable network access or rate limiting is `BLOCKED_EXTERNAL`; authentication/schema failures are `FAIL`. The current checkout has no RugCheck endpoint configured, so no live provider success is claimed. Keyless fixtures and contracts are stored under `fixtures/providers/rugcheck/`.

Reference contract: [RugCheck API Swagger](https://api.rugcheck.xyz/swagger/index.html) and its [raw API specification](https://api.rugcheck.xyz/swagger/doc.json).

## Holder concentration / wallet graph analysis

Sprint 3.2 adds the provider-independent `HolderGraphAnalyzer` in
`packages/application/src/memeradar_application/holder_graph.py`. Birdeye or
Helius adapters may supply normalized `market.holder_data` and transfer/
funding observations, but provider response types and SDKs do not cross into
the application module. Holder rows accept the normalized owner/address,
amount and percentage aliases already emitted by the market adapters.

The analyzer labels creator, configured pool, known SPL Token/Token-2022/
associated-token programs and the system address. Excluded addresses remain in
the snapshot audit data but do not inflate holder concentration. It derives
`top1`, `top5`, `top10` and optional `clustered_top` ratios as Decimal values,
preserves nullable metrics for incomplete evidence, and attaches provider
source IDs, provenance, quality state, expiry, reason codes and config hash.

The wallet graph accepts only normalized transfer/funding kinds, starts from
creator/top-holder seeds and applies explicit bounds (default: one hop, 100
holder rows, 500 edges and 500 nodes). Repeated source events are aggregated
into `funded_by` or `transfer` edges without losing transfer count, amount,
first/last timestamps or evidence references. Connected components use
explainable `SHARED_FUNDER_CLUSTER`/`RELATED_WALLET_CLUSTER` reason codes to
calculate concentration after clustering. `FRESH` evidence expires after five
minutes; stale, unknown, conflicted, future-dated or invalid evidence remains
non-authoritative and fail-closed. This analysis has no quote, signing,
execution or operating-mode authority.

Keyless replay fixtures and contracts are stored under
`fixtures/providers/wallet_graph/`. They include a shared funder, repeated
evidence, known system/program addresses and a deliberately out-of-depth edge;
they are synthetic and contain no credentials. Live holder/graph provider
acceptance remains separate from this deterministic application contract.

## Flow, liquidity and sellability analysis

Sprint 3.3 adds the provider-independent `FlowAnalyzer` in
`packages/application/src/memeradar_application/flow_analysis.py`. It accepts
normalized `market.market_data`/liquidity observations, row-level
`market.trade` observations or bounded provider trade summaries, and optional
application `QuoteSnapshot` values. No provider SDK, HTTP client or quote
response type is imported by the analyzer.

Liquidity evidence retains current liquidity, optional depth and a signed
change against the previous fresh same-token snapshot. Trade evidence derives
unique makers, transaction/maker ratio, repeated-size participation,
reciprocal/circular flow and rapid round-trip behavior. A provider summary can
provide counts and volumes, but cannot fabricate row-level maker heuristics.
Sell quotes retain input/output amounts, route, impact, provenance and their
own freshness state; missing or stale quote data is not a successful sellability
result.

The default analysis bounds are 20 market observations, 500 trade rows and 100
distinct size buckets, with a five-minute evidence TTL and a two-minute rapid
round-trip window. `OrganicFlowScore` records the score, confidence, metrics,
penalties, stable reason codes, source IDs, provenance and config hash. It is
advisory, exposes an explicit non-authorizing execution predicate and cannot
submit/sign orders or alter operating modes.

Synthetic safe/suspicious liquidity, trade and quote fixtures are stored under
`fixtures/providers/flow_analysis/`; the replay contract verifies deterministic
classification and the absence of credential-shaped fields. Live market/quote
acceptance remains a separate provider gate and is not claimed by these
keyless contracts.

## Wallet tracking and activity reconstruction

Sprint 4.1 adds the provider-independent `WalletTrackingAnalyzer` in
`packages/application/src/memeradar_application/wallet_tracking.py`. Provider
adapters may normalize chain activity into `wallet.activity`, `wallet.trade`,
`wallet.swap` or the other allow-listed wallet activity kinds, and may provide
`risk.rug_event`/`risk.token_outcome` observations. Provider SDK types,
transport clients and persistence models do not cross this application seam.

The explicit `TrackedWalletRegistry` validates canonical addresses, labels and
operator-supplied tiers, bounds entries, rejects conflicting duplicate
registrations and excludes inactive/blocked wallets. Activity normalization
preserves source provenance and all three event timestamps, deduplicates
equivalent source deliveries and rejects unknown wallets or conflicting source
IDs. It accepts BUY/SELL aliases, positive quantities and nullable quote/price
fields without inventing financial values.

The analyzer reconstructs watched positions with bounded FIFO lots. It emits
round-trip evidence, open quantity/cost basis, conservative realized PnL,
hold duration, token age at entry, rug exposure, quality state, expiry,
reason codes and evidence references. Unknown, stale, conflicted, invalid,
unmatched or incomplete evidence remains visible and fail-closed. The result
is advisory only and cannot quote, sign, submit or alter any operating mode.

Synthetic registry/activity/risk fixtures and replay contracts are stored under
`fixtures/providers/wallet_tracking/`. They contain no credentials. Live wallet
activity and rug-outcome acceptance remains `BLOCKED_EXTERNAL` until a
configured read-only chain/risk provider is available; keyless replay is not
substituted for live-provider success.

## Smart-wallet scoring

Sprint 4.2 adds the provider-independent `SmartWalletScorer`. It consumes
`WalletTrackingSnapshot` and `WalletRoundTrip` evidence after provider
normalization; no provider client or persistence model is imported. The
scorer aggregates completed outcomes by wallet over a bounded rolling window,
deduplicates replayed round trips, excludes old outcomes and marks future
outcomes invalid to prevent look-ahead leakage.

`SmartWalletScore` retains component values, nullable metrics, sample and
known-outcome counts, manipulation penalties, confidence, tier recommendation,
quality/freshness, provenance, evidence references, reason codes, version and
config hash. Sparse components shrink toward neutral and minimum sample/
confidence gates prevent tiny samples from receiving a Tier-A recommendation.
The recommendation is not written back to the tracked-wallet registry and the
score has no quote, signing, submission or live-money authority.

Synthetic score snapshots and explicit penalty inputs are stored under
`fixtures/providers/wallet_scoring/`. They contain no credentials and replay
the scoring seam without any live provider call. Live wallet-history acceptance
remains `BLOCKED_EXTERNAL` until a configured read-only chain/provider path is
available.

## Smart-money confluence and clustering

Sprint 4.3 adds the provider-independent `ConfluenceAnalyzer` in
`packages/application/src/memeradar_application/confluence.py`. It consumes
`SmartWalletScore`, `WalletTrackingSnapshot` and the existing
`WalletGraphSnapshot`/`WalletGraphEdge` application contracts; provider SDK
types, HTTP clients and persistence models do not cross this seam. Fresh graph
relationships are unioned transitively, including intermediary nodes, so
correlated wallets do not multiply token confluence. The analyzer never
infers common control from coincident timestamps alone.

The analyzer emits explainable `ENTRY`, `EXIT`, `CONFLUENCE` and `DISTRIBUTION`
events and a bounded `TokenSmartMoneyScore` with component/penalty maps,
cluster counts, confidence, quality, reason codes and complete provenance and
evidence references. It rejects conflicting duplicate inputs, deduplicates
equivalent replay deliveries and excludes future activity. Missing or
non-fresh graph evidence for multiple qualified wallets is an explicit
fail-closed `UNKNOWN` result; no confluence event is claimed in that state.

Credential-free replay inputs are stored under
`fixtures/providers/confluence/`, including fresh correlated-wallet and stale
graph cases. The Sprint 4.3 contract and Compose smoke tests verify deterministic
replay, safe modes, provider independence and absence of credential-shaped
fixture fields. Live wallet-history/graph acceptance remains
`BLOCKED_EXTERNAL` without a configured read-only chain/provider endpoint and
credential; fixture PASS is not live-provider PASS.

## Social / X read layer

Sprint 5.1 adds the provider-local `SocialRestAdapter` in
`packages/providers/src/memeradar_providers/social.py`. It is a bounded,
read-only HTTPS adapter for a compliant social/X search service configured by
the operator. The service contract is intentionally narrow: `GET /v1/search`
returns post records and pagination metadata, and `GET /health` provides the
doctor check. The adapter sends an optional configured API key only as a
Bearer header, forwards a correlation ID, and retains only safe rate-limit
metadata. It never uses cookies, browser sessions, brittle scraping, arbitrary
URL fetches or write-capable social endpoints.

The normalizer accepts common post/author aliases, canonicalizes UTC timestamps
and bounded engagement/follower metrics, and preserves post/author IDs and
provider provenance. It extracts syntactically valid Solana mint addresses,
`$TICKER` values and HTTPS canonical links without treating a ticker as proof
of token identity. URL/mention-insensitive SHA-256 text fingerprints identify
copied-text clusters; exact duplicate source IDs are collapsed while
conflicting duplicates fail as schema errors. All normalized mentions remain
freshness-aware advisory evidence and carry no execution authority.

`make social-doctor` performs one bounded read-only `/health` call when both
`SOCIAL_API_URL` and `SOCIAL_API_KEY` are configured. The redacted JSON report
contains configuration presence, network/auth/schema status, latency,
rate-limit metadata and the four protected operating modes. Missing
configuration, unavailable network access and rate limiting are
`BLOCKED_EXTERNAL`; authentication or schema failures are `FAIL`. Synthetic
search/health fixtures and keyless contracts live under
`fixtures/providers/social/`. The current checkout has no social endpoint or
credential configured, so no live provider success is claimed.

Sprint 5.2 adds provider-independent `SocialAuthorRegistry`,
`AuthorTrustScorer` and `SocialVelocityScorer` in
`packages/application/src/memeradar_application/social_intelligence.py`.
They consume only normalized `SocialMention` values, preserve source
provenance and evidence references, and calculate bounded author trust,
engagement quality, duplicate/spam ratios, 1m/5m/15m velocity and unique
author breadth. Copied-text bursts provide a conservative coordinated-
promotion/bot-like heuristic; they are diagnostics, not identity or execution
authority. The scorers work without an LLM or live provider and fail closed on
future/non-fresh critical evidence.

## Historical caller outcome evidence

The E5.4 warm path adds provider-independent `SocialCall`,
`SocialCallOutcome`, `CallPerformanceSnapshot` and `CallPerformanceAnalyzer`
under `packages/application/src/memeradar_application/call_performance.py`.
The analyzer consumes normalized `SocialMention`-derived call records plus
provider-neutral market, risk and optional token-creation observations; no
provider SDK, HTTP client, database session or execution port crosses this
boundary. Existing social adapters remain responsible only for read-only
normalization and provenance.

The analyzer sorts by event time, rejects conflicting duplicate source IDs,
collapses equivalent duplicate calls with an explicit reason code, excludes
future observations and preserves `UNKNOWN`/`INVALID` evidence states. It
records fixed forward-horizon returns, MFE/MAE, nullable rug/liquidity flags,
token age, sample/confidence gates and versioned config hashes. Author history
is an optional trust component with a default zero weight; it cannot change
registry tiers or authorize execution. All snapshots have
`execution_eligible() == false`.

Credential-free replay data and contracts are stored under
`fixtures/providers/call_performance/` and
`tests/contract/test_extension_e5_4_call_performance.py`. The fixture contract
replays records in reversed delivery order and verifies identical snapshots,
neutral treatment of insufficient history and explicit duplicate/risk reasons.
This is a keyless application acceptance; it does not claim live social
provider success.

## Narrative / LLM seam

Sprint 5.3 adds the provider-independent `NarrativeAnalyzer` gateway in
`packages/application/src/memeradar_application/narrative.py` and the
provider-local `FixtureNarrativeAdapter`/`NarrativeRestAdapter` in
`packages/providers/src/memeradar_providers/narrative.py`. The gateway
canonicalizes bounded `NarrativeInput` evidence, strips secret-shaped and
instruction/tool-shaped control text from the model view, delimits untrusted
content as data, enforces evidence/character/token/cost budgets, and caches
validated results by a deterministic `sha256` key over the sanitized canonical
document with a bounded TTL and entry count.

Provider output must be a strict `NarrativeSnapshot` whose schema version and
config hash match the request, whose evidence references only cite supplied
input IDs, whose usage stays inside the configured budgets and whose freshness
is valid at call time; any violation, timeout or provider error degrades to a
deterministic zero-confidence fallback snapshot with explicit reason codes and
never raises into deterministic analysis. Non-fresh input evidence skips the
provider call entirely. Every snapshot is advisory-only and
`execution_eligible()` is always false.

`make narrative-doctor` performs one bounded read-only structured-output check
only when `NARRATIVE_API_URL` and `NARRATIVE_API_KEY` are configured. It
reports configuration presence, network/auth/schema status, rounded latency,
safe rate-limit metadata and the four protected modes, and returns
`BLOCKED_EXTERNAL` with `CONFIGURATION_MISSING` when configuration is absent.
The credential is sent only as a Bearer header and never appears in URLs,
fixtures, errors or doctor output. Synthetic fixtures and keyless contracts
live under `fixtures/providers/narrative/`; live narrative acceptance remains
`BLOCKED_EXTERNAL` without configured safe read-only access.

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
