# Provider Strategy and Contracts

Providers are replaceable adapters. Domain code must never depend directly on provider response types.

## Free-first capability map

The default path is keyless and read-only. Optional providers enrich or provide
bounded fallback data; they do not change the domain contracts or protected
execution modes.

| Capability | Free/default | Optional enhancement | Boundary / limitation |
| --- | --- | --- | --- |
| `CHAIN_RPC` | standard Solana JSON-RPC plus configured read-only BNB/Robinhood EVM RPC | Helius standard/enhanced RPC | public RPC is rate-limited and non-guaranteed |
| `ENHANCED_ASSET_METADATA` | unavailable/degraded | Helius DAS/enhanced API | never emulated through public RPC |
| `TRANSACTION_HISTORY` | standard Solana RPC reads | Helius enrichment | bounded reads only |
| `REALTIME_STREAM` | explicit stream/backfill seam | Helius stream | REST market data is not a chain stream |
| `MARKET_SNAPSHOT` | DexScreener | Birdeye fallback/enrichment | only normalized market/pair data |
| `MARKET_QUOTE` | DexScreener reference quote | reviewed custom adapter | not a live swap quote or execution authority |
| `PAIR_DISCOVERY` | DexScreener | Birdeye | enabled chain and token identity are required; coverage can be UNKNOWN |
| `SOCIAL_METADATA` | DexScreener declared links | existing compliant provider | metadata only; no X scraping |
| `SOCIAL_ANALYTICS` | unavailable | existing external social provider | no fabricated counts, sentiment or velocity |
| `SOCIAL_CALLS` | unavailable unless configured | compliant social/X and Telegram Bot API call adapters | public caller evidence only; unresolved symbols remain UNKNOWN |
| `RISK_SUMMARY` | local deterministic checks | public/authenticated RugCheck evidence | third-party scores never replace local gates |
| `TOKEN_SECURITY` | local authority/token-program checks | read-only GoPlus-style normalized enrichment | SOLANA/BNB/ROBINHOOD fields are advisory; missing fields remain UNKNOWN |
| `WALLET_ENRICHMENT` | local tracking/scoring/graphs/flows | external wallet enrichment | labels remain corroborating evidence |
| `NARRATIVE` | local Ollama or disabled | explicitly configured external LLM | advisory output only |
| `ALERT_DELIVERY` | Telegram when configured | — | notification is downstream of analysis |

The standard Solana adapter implements ordinary JSON-RPC operations only. The
official [Solana JSON-RPC method documentation](https://solana.com/docs/rpc)
defines these reads; Helius-only DAS/enhanced methods remain in the Helius
adapter. DexScreener's public [API reference](https://docs.dexscreener.com/api/reference)
is used for pair/market metadata and declared project links, not transaction
history, holder graphs, wallet history, security audits, realtime blockchain
streams or social search/firehose.

### Composition and provenance

`build_provider_bundle` is the small infrastructure composition root. It builds
the provider-neutral `FreeFirstRoutePlan` and bounded fallback wrappers without
putting provider imports in application routing:

```text
standard Solana reads: Helius (when URL + key are configured) -> Solana RPC
configured BNB/Robinhood reads: generic EVM JSON-RPC adapter -> optional route
Helius enhanced capability: Helius only -> explicit unavailable/degraded
market/pair: DexScreener -> Birdeye only when configured
paper reference quote: DexScreener -> injected normalized custom port
risk: local deterministic checks + optional RugCheck evidence
wallet: local intelligence -> injected external enrichment
social metadata: DexScreener -> optional social analytics (separate capability)
narrative: Ollama -> configured external -> disabled
alerts: configured Telegram -> optional/unconfigured
```

Fallback is ordered, bounded and observable. It advances only after a concrete
provider error; an unsupported capability is not silently converted into an
unrelated provider result. Normalized observations and quotes retain provider,
chain, token/pair identity, timestamps, freshness and provenance.

Runtime capability policy is canonical across settings, composition, provider
metadata, doctors and readiness. The default enabled chains are `solana` and
`robinhood`; BNB is not enabled unless `BNB_RPC_URL` supplies its canonical
read transport. Helius is an optional enhanced Solana capability over the
public RPC and its absence does not make the minimum Solana path unhealthy.
Disabled, unconfigured, unknown, degraded and healthy provider states remain
distinct in operator projections.

### Research-only wallet, social and Robinhood extensions

The optional `ExternalWalletEventStreamAdapter` accepts an injected
CabalSpy-style stream for Solana, BNB and Robinhood (and rejects other chains
through canonical identity validation). It emits the existing normalized wallet
observation shape with chain-qualified source IDs, event-time timestamps,
deduplication, sequence-gap evidence, bounded reconnect/backoff, bounded event
count, provider health and optional RPC/provider fallback. The thin
`CabalSpyWebSocketSource` uses the documented subscription envelope but remains
optional and doctor-gated; credentials never enter normalized payloads.
External labels or scores are retained as advisory payload evidence only; local
wallet history, graph and conduct calculations remain authoritative. An
unresolved sequence gap is `DEGRADED`, never fully healthy/fresh.

`HistoricalSocialBackfillProvider` extends the existing `SocialCallPort` with a
bounded time window. `SocialRestAdapter.backfill` reuses
`SocialCallObservation`, retains message/edit/delete/unresolved-reference and
parser/provenance fields, and marks the result
`EXTERNAL_RESEARCH_EVIDENCE`. It does not promote unofficial or scraped
observations to production truth; replay and caller-outcome evaluation still
apply the existing no-lookahead, negative-control and sample-adequacy gates.

`RobinhoodSequencerAdapter` reuses the generic EVM chain identity and wallet
stream normalization, with ordered low-latency observations, gap detection,
deduplication and an RPC-backfill seam. Sequencer observations are explicitly
non-authoritative until canonical RPC/finality reconciliation. The versioned
verified launchpad registry remains empty until an authoritative
`(chain_id, contract_address, selector)` identity is verified. Unsupported
NOXA, Odyssey or other identities remain `UNKNOWN`; no selector or contract is
guessed from an external reference.

`ReferencePriceEvidence` compares a verified Chainlink AggregatorV3 observation
with a DEX executable quote through the read-only EVM RPC seam. A stale,
missing, invalid or unavailable oracle is `UNKNOWN`; a large unexplained
deviation is market-integrity risk evidence; the oracle value never becomes an
execution price. Robinhood feed addresses remain unregistered until verified.
All new evidence is measurement-only and `execution_eligible=false`.

The implementation reimplements small provider-neutral seams rather than
copying external code. CabalSpy's public MIT SDK/docs, GMGN-style scanner
material and Robinhood launchpad references were used only for
architecture/research; no external source code or unverified protocol identity
was imported. The optional GMGN adapter is independently implemented against
the audited server-side read contract and remains `LIVE_SHADOW` with weight
zero. Live provider credentials and compliant historical real-data cohorts
remain external validation blockers.

### Opportunity discovery evidence

Opportunity discovery observes `SOLANA`, `BNB` and `ROBINHOOD` through the
existing normalized event, market, wallet and social seams. Robinhood reuses
the generic EVM identity/RPC and market primitives and remains read-only; no
chain-specific scoring or execution adapter is introduced. Chain heat,
narrative/pre-token attention, KOL and smart-money convergence are
measurement-only evidence until canonical no-lookahead replay, independent
TRAIN/VALIDATION/TEST ablation, sufficient real samples and the existing
human-reviewed promotion gate demonstrate incremental out-of-sample value.
Missing provider evidence is `UNKNOWN`, not zero or safe; provider labels and
LLM narratives cannot authorize `ENTRY_READY`.

The shared `DexScreenerAdapter` normalizes market pairs for all enabled
discovery chains. It sends Solana requests with `solana`, BNB requests with
DexScreener's `bsc` identifier, and Robinhood requests with `robinhood`, while
returning MemeRadar's canonical `solana`/`bnb`/`robinhood` chain values. Address
validation follows the canonical domain identity, so equal EVM addresses on
different chains cannot share a metadata-cache entry. Pair selection remains
deterministic: positive liquidity, preferred stable/native quote assets, depth,
pair age and address/DEX tie-breakers. An EVM token with no eligible coverage
returns `QualityState.UNKNOWN`; it never becomes a zero-price or safe market
mark.

## Live Read-Only Acceptance & Readiness

See `LIVE_READONLY_CHECKLIST.md` for full environment setup, doctor commands, and degraded mode behavior. A successful free core is reported as `READY_FOR_FREE_READ_ONLY_SHADOW`; it is never full-provider or live-money readiness.

Production capability health is explicit and separate from application health.
The aggregate free-first doctor and `/v1/providers/health` expose the
canonical states `READY`, `DEGRADED`, `RATE_LIMITED`, `STALE`,
`CONFIGURATION_MISSING`, `BLOCKED_EXTERNAL` and `UNSUPPORTED`; unprobed health
is `UNKNOWN`. `/health/live` and `/health/ready` report only the API process
and its configured database/Redis dependencies, so optional social, Telegram
or enrichment outages do not become application boot failures or silently
become evidence readiness. Capability readiness is read from the provider
health endpoint/doctor instead.

All provider calls continue through the shared bounded transport: request
deadlines, bounded retries/backoff, rate-limit waits and circuit-open behavior
are preserved for chain, market/reference quote, execution-quote, social and
Telegram adapters. Optional providers remain non-blocking when absent; an
explicitly configured provider reports its concrete configuration, rate-limit,
freshness or external failure state without being relabeled as `READY`.

All provider ports operate under strict fail-closed boundaries:
- Missing optional API keys or endpoints report `UNCONFIGURED_OPTIONAL`; configured network failures report `BLOCKED_EXTERNAL`/`DEGRADED`. The free core uses keyless adapters or explicit `QualityState.UNKNOWN` without crashing.
- Stream gaps or unverified protocol routing reduce quality to `DEGRADED` or `UNKNOWN` and cannot authorize `ENTRY_READY` or inflate `AlphaScore`.
- Third-party risk scores are corroborating evidence only and never override MemeRadar's deterministic risk hard gates.
- `AUTO_EXECUTION=false` and `MANUAL_EXECUTION=false` remain permanently locked.

The application `SocialCallCollector` is the shared bounded orchestration seam
for historical and live call ingestion. It consumes the existing
`SocialCallPort`/`SocialDataRequest`, paginates historical cursors only up to a
configured page bound, keeps live collection to one resumable batch, orders
calls by published/observed/ingested event time, replaces an earlier record
only when a later provider observation explicitly marks it edited, and rejects
conflicting duplicate identities. It writes through the existing
`SocialCallObservationRepository`-compatible sink, so provider payloads and
database details do not enter application logic. Reports expose bounded page,
duplicate, persistence, cursor and ingestion-lag metrics; social and Telegram
doctors expose `collector=UNKNOWN` until a collection run exists, or
`CONFIGURATION_MISSING` when required access is absent.

## Paper execution boundary

The Phase 9.1 paper engine is not a provider adapter. It consumes the existing
application `QuoteSnapshot` contract, including freshness, market context and
provenance, and simulates fills with a versioned fee/slippage model. It does
not call a quote endpoint, import a provider SDK, hold a signer or submit a
transaction. The `PaperLedgerStore` protocol has in-memory and SQLAlchemy
implementations behind the application boundary. DexScreener supplies a
normalized market-reference quote by default; a custom quote URL/key remains
only a compatibility configuration until a reviewed `QuotePort` is injected.
`make paper-trading-doctor` checks local paper contracts and reports quote
provider status without probing or echoing endpoint values. Live-money quote
and execution acceptance remains blocked.

The Sprint 9.2 exit engine is likewise not a provider adapter. It consumes
normalized evidence snapshots with freshness and provenance, and the
`SqlAlchemyExitEvaluationStore` persists evidence through the application
timeline boundary. External wallet-distribution alerts are corroboration only;
missing live market access remains `BLOCKED_EXTERNAL` and cannot be converted
into a provider PASS by configuration presence.

## Phase 10.1 provider-free replay

`ReplayDataset` and `ReplayHarness` are cold-path application contracts, not
provider adapters. They consume persisted/fixture normalized observations and
rehydrate them without network access, provider SDKs or live credentials.
Live, backfill and historical data must already have converged through the
canonical decoder/normalizer path before entering a replay dataset. The
manifest pins parser, protocol registry, event schema, strategy and config
identity; provider disagreement or non-fresh evidence remains explicit and
cannot become a provider PASS. `make replay-dataset` produces canonical JSON,
`--format csv` produces a flat outcome export, and `make profile-replay`
measures local throughput only. Live market/provider acceptance remains
`BLOCKED_EXTERNAL`.

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
| `SocialDataPort` | `SocialDataRequest` -> `SocialMention` values with author/post identity, timestamps, metrics and provenance; optional `search_global_events` returns bounded `GlobalEvent` values or family-local `UNKNOWN` status |
| `NarrativePort` | bounded `NarrativeInput` -> strict `NarrativeSnapshot`; output is advisory evidence only |
| `QuotePort` | `QuoteRequest` -> `QuoteSnapshot` with route, impact, freshness and provenance; no signing side effect |
| `ExecutionPort` | `ExecutionRequest` -> unsigned `ExecutionPlan`, `ExecutionReceipt` and reconciliation; live submission remains policy-gated and unused |
| `NotificationPort` | `NotificationRequest` -> `DeliveryReceipt`; adapters do not mutate domain state |

Shared request contexts carry a bounded correlation ID and optional deadline. The keyless provider framework in `packages/providers/src/memeradar_providers/` supplies callback-based transport resilience, health/quota/freshness projections, recursively redacted fixture recording and deterministic fake responses. These seams are tested without provider credentials; live acceptance remains a separate adapter-phase concern.

## Telegram notification and caller adapter

Sprint 7.1 implements `TelegramNotificationAdapter` in
`packages/providers/src/memeradar_providers/telegram.py`. It is an
HTTPS-only, bounded adapters for Telegram Bot API `sendMessage`, `getMe` and
read-only `getUpdates`, using the shared transport timeout/retry/rate-limit
policy and forwarding a bounded correlation ID. `TelegramCallAdapter` extends
the existing notification adapter rather than creating another provider
framework. It normalizes messages and channel posts into
`SocialCallObservation`, preserves chat/message identity, published versus
observed/ingested timestamps, caller, chain-qualified address or unresolved
reference, intent and supplied edit/delete evidence, and deduplicates exact
updates. It never scrapes Telegram pages or authorizes execution.

`FixtureNotificationAdapter` provides deterministic credential-free delivery
for replay and local integration tests. `make telegram-doctor` reports only
configuration presence, safe health metadata and protected modes; missing
endpoint/token/chat configuration is `BLOCKED_EXTERNAL`, while configured
health failures are classified without printing credentials. The current
checkout has no Telegram configuration, so no live provider success is
claimed. Telegram notification and caller evidence remain downstream of
deterministic analysis and cannot authorize execution.

Alpha Caller Task 11 extends the same `AlertRenderer` path with a bounded
`CALLER INTELLIGENCE` section when normalized caller evidence is present. It
can show caller historical-quality band, convergence state/count,
event-time earliest-call context, smart-money/distribution state,
security/liquidity/execution quality, the MemeRadar decision band, research
state and provenance/evidence references. Profile and convergence mappings
are merged without creating another alert engine. Missing fields are omitted
rather than guessed, while existing `UNKNOWN` values remain visible. The
renderer always ends with `Auto execution: LOCKED` and emits no guaranteed
multiple, live-buy, copy-trading or swap instruction.

The Sprint 7.2 read API is not a provider adapter. Its application
`ReadQueryPort` consumes normalized views, and the SQLAlchemy implementation
reads persisted normalized records without importing provider SDKs or making
network calls. Sprint 7.3 projects audit/config rows from the physical control
plane; wallet/provider-health records remain explicit injectable catalogs until
their persistence tasks. An empty catalog does not imply provider health or
live acceptance. Public/local read projections retain source/timestamp/
freshness and reason evidence while omitting raw provider bodies and
secret-shaped fields; configured operator deployments require a valid role
token. Provider disagreement and unknown health therefore remain visible
evidence, never execution authority.

The authenticated control plane has no provider dependency. Provider health,
external labels, smart-money evidence and LLM narratives cannot grant a role,
clear a kill switch, mutate protected modes or authorize execution. Missing
provider or role credentials are configuration blockers for their live
acceptance, not provider PASS results.

The cross-cutting `ProviderHealthRouter` compares normalized
`ProviderOperationalInput` values for one capability and selects only a fresh
healthy candidate using deterministic priority, latency and provider-name
ordering. Missing freshness, stale/degraded state, unknown state, provider
disagreement and all-down conditions remain explicit route outcomes; a
conflicted candidate fails closed even when another candidate is healthy. The
selection is an application diagnostic seam only: it does not call a provider,
change AlphaScore, authorize `ENTRY_READY` or grant execution eligibility.
Live multi-provider comparison and contractual acceptance remain
`BLOCKED_EXTERNAL` until configured read-only providers are available.

Sprint 9.3 position views are not a provider adapter. The SQLAlchemy read
projection consumes existing normalized `ObservationRow` market records and
paper `PositionRow` values, allow-lists price fields, and preserves source,
parser and timestamp provenance. Exit evaluations are rehydrated from the
existing domain-event timeline. Position reads make no provider calls and
never infer a mark when the source is missing or non-fresh. Exit events enter
the existing alert/outbox path; `TelegramNotificationAdapter` remains the only
network delivery boundary, while fixture delivery keeps keyless replay and
tests credential-free. No Telegram or market-data live acceptance is claimed.

## Helius / Solana read layer

Sprint 2.2 implements the read-only Helius adapter in `packages/providers/src/memeradar_providers/helius.py`. `HeliusRpcAdapter` maps `getAsset`, `getAccountInfo` and `getTransaction` JSON-RPC/DAS responses into canonical `TokenIdentity`, account and transaction records plus application `Observation` values. It validates Solana base58 identities, preserves `occurred_at`/`observed_at`/`ingested_at`, attaches Helius/source/parser provenance, forwards request correlation IDs, and classifies timeout, availability, authentication, rate-limit and schema failures without retaining raw response text.

Token metadata explicitly distinguishes SPL Token and Token-2022 programs. Mint and freeze authorities normalize to `ACTIVE`, `REVOKED`, `UNKNOWN` or `INVALID`; missing evidence remains `UNKNOWN` and never becomes safe evidence. Invalid account keys, owner values, numeric fields and future transaction times fail closed as classified schema errors. `last_rate_limit` exposes only safe quota/reset metadata for health reporting. The adapter has no signing or execution path.

`HeliusObservationNormalizer` and `HeliusStreamConsumer` in `helius_stream.py` form the webhook/WebSocket seam. They accept only injected async sources, redact credential-shaped fields, map event types to an allow-list, validate event timestamps, and create deterministic observation IDs from `helius` plus the provider source ID. Duplicate deliveries are forwarded so downstream persistence can apply its idempotency policy. Reconnects are bounded and cancellation propagates; untrusted messages cannot invoke execution or mutate configuration.

The stream consumer accepts an optional provider-independent reliability sink.
It reports only bounded Helius reconnect, duplicate and malformed-drop
counters plus chain-event-to-ingest timing; raw messages, credentials and
exception text never enter telemetry.

The explicit `make helius-doctor` command runs one bounded, read-only
`getHealth` call when both `HELIUS_RPC_URL` and `HELIUS_API_KEY` are configured.
Its JSON report includes only configuration presence, network/auth/schema
status, rounded latency, safe rate-limit metadata and the protected operating
modes. Missing optional Helius configuration is not a core failure. The
`make solana-rpc-doctor` command checks the generic standard-RPC path, while
`make free-provider-doctor` reports both paths and their readiness tiers.

## E8.4 Solana stream integrity and protocol verification

The provider-independent `StreamIntegrityCoordinator` is the reliability
seam for Solana transports. It consumes bounded raw transaction envelopes,
tracks a durable slot/signature cursor, records explicit gaps, performs
bounded backfill through `ChainBackfillPort`, and appends normalized evidence
before contiguous progress advances. Backfill blocks report their actual
produced slots, so skipped Solana slots are not treated as missing blocks.
Overlapping gaps merge deterministically; queue saturation, timeouts,
rate-limits, duplicates and conflicts remain observable instead of silently
dropping evidence.

`ProtocolIdentityRegistry` is versioned and routes only on
`(program_id, discriminator_or_tag)`. `CanonicalProtocolDecoder` delegates
live, backfill and replay calls to one decode path while preserving the
existing Pump.fun, PumpSwap, Raydium and Meteora adapters. Production entries
remain `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` until authoritative and
independently corroborated identity evidence is recorded; synthetic verified
entries are fixture-only. Unknown, unverified or conflicting identities fail
closed.

Normalized chain events retain commitment (`PROCESSED_UNCONFIRMED`,
`CONFIRMED`, `FINALIZED`, `REVERTED`, `UNKNOWN`), recovery state, slot/signature,
transport, backfill/recovery timestamps, parser/registry/schema versions and
provenance. Reverts retain the prior event and append an explicit correction.
`ReplayManifest` provides an event-time boundary and pins parser, registry,
schema, strategy and config identities without contacting a provider. The
`make stream-integrity-doctor` check reports local keyless contract status and
configuration presence only; configured external stream/RPC acceptance is
still `BLOCKED_EXTERNAL` unless a real bounded check is performed.

## Birdeye / DEX market layer

Sprint 2.3 implements the read-only `BirdeyeRestAdapter` in `packages/providers/src/memeradar_providers/birdeye.py`. It maps the new-listing endpoint (`/defi/v2/tokens/new_listing`) into canonical `DiscoveryCandidate` values and maps the supported token market-data, trade-data, holder and token-security endpoints into provider-independent `Observation` values. Birdeye response envelopes, field names and request paths remain inside the provider package; normalized observations carry canonical Solana token identities, ordered event timestamps, quality state and Birdeye/parser provenance.

The adapter sends the configured API key only as the `x-api-key` header, identifies the Solana chain with `x-chain: solana`, forwards a bounded correlation ID and never places credentials in URLs, payloads, fixtures, exceptions or doctor output. Its injected `ProviderTransport` applies timeout, retry, rate-limit and circuit policies, while HTTP/auth/schema failures remain classified provider errors. `BirdeyeRestAdapter.check_health` performs one read-only `/defi/networks` request and validates the returned list/mapping without making a write-capable call.

`BirdeyeListingNormalizer` and `BirdeyeDiscoveryFallback` in `birdeye_stream.py` form a stream-first, bounded polling-fallback seam for untrusted new-listing messages. Malformed messages are counted and skipped, duplicates are retained for downstream idempotency, reconnects are bounded and cancellation propagates. `BirdeyeObservationResolver` marks expired fresh evidence `STALE`, preserves `UNKNOWN`/`INVALID`/`CONFLICTED`, retains source IDs and values and emits explainable `CONFLICTED` evidence for material numeric disagreement.

When wired to the optional reliability sink, the fallback reports provider-
labelled reconnect, fallback, duplicate and malformed-drop counters without
changing its existing bounded poll behavior.

The explicit `make birdeye-doctor` command performs one bounded, read-only
supported-networks call when `BIRDEYE_API_URL` and `BIRDEYE_API_KEY` are
configured. It reports only configuration presence, network/auth/schema
status, rounded latency, safe rate-limit metadata and protected modes. Missing
Birdeye is `UNCONFIGURED_OPTIONAL` in the aggregate doctor; it does not prevent
DexScreener-backed market analysis. Synthetic fixtures and keyless contract
tests are committed under `fixtures/providers/birdeye/`. Reference endpoint
documentation: [new listing](https://docs.birdeye.so/reference/get-defi-v2-tokens-new_listing), [market data](https://docs.birdeye.so/reference/get-defi-v3-token-market-data), [trade data](https://docs.birdeye.so/reference/get-defi-v3-token-trade-data-single), [holder data](https://docs.birdeye.so/reference/get-defi-v3-token-holder) and [supported networks](https://docs.birdeye.so/reference/get-defi-networks).

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

An optional reliability sink records protocol-venue reconnect, fallback,
duplicate and malformed-drop counters. These counters are diagnostics only and
cannot raise score, change stream-quality state or authorize a decision.

## Phase 11 reliability measurement

`ProviderTransport` optionally reports bounded provider request latency and
classified timeout, failure, rate-limit, retry, schema-drop and circuit-open
counters. Application outbox processing optionally reports delivery,
retry/dead-letter and processing latency. All labels are allow-listed and
redaction-safe. `make reliability-doctor` validates only local contracts and
returns `BLOCKED_EXTERNAL` when no live provider check is performed.

Phase 11.2 projects these records through the provider-independent
`OperationsProjector` and `GET /v1/operations/overview`. The versioned
provider SLO policy requires a minimum number of non-synthetic provider-network
samples before reporting `MEASURED`; fixture/keyless timing remains
`UNVERIFIED`. Current provider state, freshness, quota and cost-budget
pressure produce explicit `UNKNOWN`/`DEGRADED`/`DOWN` alerts and are visible in
the server-rendered `/operations` dashboard. They are operational evidence
only and cannot increase AlphaScore or authorize `ENTRY_READY`. See
[`docs/RUNBOOKS/OPERATIONS.md`](RUNBOOKS/OPERATIONS.md) for bounded outage,
quota and alert-failure response.

## Ultra-Early Option A read-only acceptance

The approved ultra-early path reuses canonical chain/protocol normalization,
the free DexScreener market path, optional Helius/Birdeye enrichment and the
existing stream-integrity contracts. `make early-live-doctor` always checks
the free standard Solana RPC and DexScreener paths when external probing is
requested; Helius and Birdeye are probed only when configured. It reports
three separate tiers: `CORE_FREE_READINESS`,
`OPTIONAL_ENRICHMENT_READINESS` and `FULL_PROVIDER_READINESS`. A healthy free
core may be `READY_FOR_FREE_READ_ONLY_SHADOW`, but no tier is live-money
readiness. Keys, endpoints and raw provider payloads are never printed. The
local stream contract is checked, while merely configuring a WebSocket does
not become `LIVE_VERIFIED` evidence. Network/rate-limit failures remain
`BLOCKED_EXTERNAL` and authentication/schema/configuration failures remain
explicit failures or degradation in the optional tier.

Live detection can be called verified only after a bounded real stream run
demonstrates continuity, gap detection and recovery, commitment/revert
handling, fresh canonical launch events, and observed first-seen/decision
latency samples. Those samples must be classified `LIVE_VERIFIED` by the
early observability projection; synthetic benchmark output never establishes a
production SLO. The doctor has no quote, signer, transaction or live-money
execution dependency.

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

## E11.4–E11.9 signal hardening

The MadeOnSol-derived signal-hardening extension is intentionally outside the
provider layer. `SignalHardeningAnalyzer` consumes only normalized
`Observation` values and emits versioned, provider-independent evidence for
sustained momentum, economic tape funding, deployer/transfer deltas, bounded
sniper/bundle footprints and token/vesting unlock schedules. It preserves
quote units when an independent USD conversion is unavailable and keeps
execution/effective price semantics separate from market/reference price
semantics.

MadeOnSol is not a required adapter or source of trading truth. A future live
adapter, if separately approved and legally configured, may provide optional
corroboration only; external labels and scores cannot replace internal
deterministic risk, authorize `ENTRY_READY` or enable execution. Missing,
stale, conflicted or unverified evidence remains explicit `UNKNOWN`/degraded
data, and no live provider acceptance is claimed. Keyless fixtures and the
replay contract live under
`fixtures/providers/signal_hardening/` and
`tests/contract/test_extension_e11_signal_hardening.py`.

## Feature-window aggregation

Core Sprint 6.1 is intentionally outside the provider layer. The
provider-independent `FeatureWindowAggregator` consumes only normalized
application contracts and emits deterministic `FeatureSnapshot` values for
`1m`, `5m` and `15m`. It retains source provenance and freshness, fails closed
on future evidence, and leaves missing families unknown. The replay fixture
under `fixtures/providers/feature_windows/` is credential-free; no provider
doctor or live-provider PASS is implied by this application-level checkpoint.

## AlphaScore recomputation

Core Sprint 6.2 is also outside the provider layer. `AlphaScoreRecomputer`
delegates to the provider-free `AlphaStrategy` contract and communicates with
repository protocols only; no provider SDK, transport response or credential
enters score evaluation. The redacted golden fixture under
`fixtures/providers/alpha_score/` validates score, confidence, penalties,
hard-risk explanations and strategy/config identity without implying live
provider success.

## Decision state and timeline projection

Core Sprint 6.3 is also outside the provider layer. `DecisionEngine` consumes
only immutable domain snapshots and an application-facing candidate store;
`EvidenceTimelineProjector` consumes normalized events and snapshots. Neither
module imports provider SDKs or network clients, and neither can sign, submit,
open a position or enable a trading mode. Provider disagreement, stale or
unknown critical risk and missing eligibility evidence remain fail-closed at
the decision boundary. The keyless replay fixture under
`fixtures/providers/decision/` is the acceptance path; no live provider PASS
is implied.

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
`fixtures/providers/external_wallet/` and contains no credentials. GMGN is a
separate optional read-only adapter using only the audited market/token HTTP
routes; its labels and risk fields remain corroborating evidence and never
replace internal wallet/security authority. Both live acceptance and external
wallet acceptance are separate from keyless fixture PASS; the local wallet
pipeline remains the default.

## GMGN read-only LIVE_SHADOW

`GmgnAdapter` in
`packages/providers/src/memeradar_providers/gmgn.py` uses the shared transport,
typed provider errors, redaction, canonical chain/address normalization and
`CandidateDiscoveryCollector`. It is optional, disabled by default, not
required for health, read-only, and excluded from the core provider route plan.
Its normalized discovery, market, creator, top-trader/KOL, holder and security
observations are persisted as `REAL_EXTERNAL` evidence with
`collection_mode=LIVE_SHADOW`; the shared application evidence policy keeps
unpromoted shadow rows out of production decision projections while replay and
research may opt in explicitly. Readiness distinguishes retained polling rows
from `unique_token_sample_count`, a unique-token proxy rather than a claim of
statistical independence. Correlated outcome cohorts remain a separate
research requirement.

The adapter accepts only the audited `GET /v1/market/rank`,
`GET /v1/token/info`, `GET /v1/token/security`,
`GET /v1/market/token_top_holders` and
`GET /v1/market/token_top_traders` routes. GMGN smart-money/KOL/insider/rug,
honeypot and lifecycle fields are provider evidence only. There is no
`gmgn-cli`, browser scraping, private key, signer, wallet custody, swap,
order, cooking or copy-trading path. Missing credentials, unavailable network
access and insufficient real labels remain explicit external blockers.

## RugCheck / token-security risk layer

Sprint 3.1 adds the provider-local `RugCheckRestAdapter` in `packages/providers/src/memeradar_providers/rugcheck.py`. It performs a read-only `GET /v1/tokens/{id}/report/summary` request, validates the official summary shape, and maps each `risks[]` item into an application `RiskFinding` with the requested token, source ID, observation timestamp and `QualityState.FRESH`. The adapter accepts an optional JWT through the `Authorization: Bearer ...` header; it never places credentials in a URL, report body, fixture, exception or doctor output. The adapter uses the shared bounded transport policy and exposes only safe rate-limit metadata.

The official `danger`, `critical` and `block` levels remain `RiskSeverity.BLOCK` findings at the provider boundary, but the application `TokenSecurityEvaluator` treats those third-party findings as uncorroborated warnings. Only deterministic on-chain evidence can establish the authority hard gates; a severe provider finding becomes a hard block only after an independent on-chain corroboration path is implemented. Provider `warn` and unknown levels remain warning/unknown advisory evidence. RugCheck verification fields are normalized as `VERIFICATION_STATUS` with `INFO` severity and are never an endorsement, score boost or execution gate.

The evaluator consumes Helius-normalized `onchain.token_metadata` observations. Active mint or freeze authority is a hard block under the current policy. Missing, unknown, invalid, conflicted or stale critical authority evidence produces `UNKNOWN` and is not execution-eligible. Token-2022 program identity and extension names are retained in normalized Helius payloads; security-relevant extensions are surfaced as explicit warnings and do not silently become safe evidence. The default authority-evidence TTL is five minutes, and every resulting risk assessment carries a version, configuration hash, reason codes and all evidence references.

`make rugcheck-doctor` performs one bounded read-only `GET /ping` call when
`RUGCHECK_API_URL` is configured. The official ping response must contain
`message: pong`; the optional `RUGCHECK_API_KEY` is reported only as
present/missing and is sent as a bearer header when set. Missing URL is
`UNCONFIGURED_OPTIONAL`; unavailable network access or rate limiting is
`BLOCKED_EXTERNAL`; authentication/schema failures are `FAIL`. RugCheck is
never required for the local deterministic risk engine. Keyless fixtures and
contracts are stored under `fixtures/providers/rugcheck/`.

Reference contract: [RugCheck API Swagger](https://api.rugcheck.xyz/swagger/index.html) and its [raw API specification](https://api.rugcheck.xyz/swagger/doc.json).

### Multi-chain token-security enrichment

The existing security audit was compared against the common GoPlus-style
token/address fields. Local `TokenSecurityEvaluator` remains the authority for
Solana token-program identity, mint/freeze authorities and Token-2022
extensions. RugCheck contributes free-form risk names/levels, and the existing
Birdeye security observation contributes Solana `is_freezable`, `is_mintable`,
`is_mutable`, blacklist and creator fields. None of those paths provide one
bounded, chain-neutral contract for the high-value honeypot, blacklist,
mintability, proxy, source-verification and buy/sell-tax fields across all
mandatory chains.

`GoPlusTokenSecurityAdapter` in
`packages/providers/src/memeradar_providers/token_security.py` fills only that
missing enrichment seam. It reuses the existing bounded RugCheck HTTP
transport and `RiskDataPort`, performs a read-only GET, routes Solana through
the Solana endpoint and BNB/Robinhood through the generic EVM chain IDs `56`
and `4663`, and emits provider-neutral `RiskFinding` values with provenance.
Each absent field is an explicit `UNKNOWN` finding; unsupported chain,
timeout, authentication, schema and provider failures remain typed failures.
The normalized fields are `is_honeypot`, `is_blacklisted`, `is_mintable`,
`is_proxy`, `is_open_source`, `buy_tax` and `sell_tax` (tax values are bounded
percentages). Address/owner/deployer and liquidity-lock fields remain
`UNKNOWN` until a reviewed normalized contract supplies them.

The external `GoPlusSecurity/goplus-mcp` repository was used only as a
research/protocol input. No code was copied or vendored (`NO`); the local
adapter independently implements the response validation, provenance,
timeouts and fail-closed semantics. No license grant or live provider
acceptance is inferred. Synthetic keyless fixtures live under
`fixtures/providers/token_security/`; an endpoint/key is not required for the
local core, and live acceptance remains `BLOCKED_EXTERNAL` until an operator
configures and verifies an approved endpoint. These findings remain advisory
to the local evaluator and do not change score weights, hard-risk authority or
execution eligibility.

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

The same adapter also exposes `search_calls` through `SocialCallPort`. Its
shared call normalizer accepts explicit Solana, BNB and Robinhood-compatible
EVM chain/address fields, retains ticker/name/address references when an asset
cannot be resolved, and extracts bounded intent, entry/target, disclosure and
edit/delete evidence. It uses only the configured compliant `/v1/search` seam;
missing configuration and provider outages remain optional/degraded and never
become a boot dependency.

`make social-doctor` performs one bounded read-only `/health` call when both
`SOCIAL_API_URL` and `SOCIAL_API_KEY` are configured. The redacted JSON report
contains configuration presence, network/auth/schema status, latency,
rate-limit metadata and the four protected operating modes. Missing
configuration, unavailable network access and rate limiting are
`BLOCKED_EXTERNAL`; authentication or schema failures are `FAIL`. Synthetic
search/health fixtures and keyless contracts live under
`fixtures/providers/social/`. DexScreener declared links provide the separate
free social-metadata path; the external social endpoint is optional and is not
configured in the current checkout, so no live social-analytics success is
claimed.

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

## Research backtesting boundary

Phase 10.2 backtesting is intentionally provider-free. It consumes normalized
`ResearchReplayResult` artifacts and does not call a market, social, wallet,
quote or execution provider. Fee/slippage assumptions come from the existing
provider-neutral `PaperFillModel`; an unavailable or non-fresh replay outcome
is recorded as an explicit skip. Live market and Telegram acceptance remains
`BLOCKED_EXTERNAL` when credentials or network access are unavailable; no
backtest report is treated as provider acceptance or execution authority.

## Research score calibration boundary

Phase 10.3 calibration is also provider-free. The CLI consumes a redacted
`ResearchReplayResult`/dataset artifact and uses the application replay,
strategy and backtest contracts without importing a provider SDK, calling a
market/social/wallet service, or writing persistence. Provider-derived author,
wallet, external-label and bundle information may enter only as previously
normalized, timestamped samples with quality/provenance metadata. The
calibration report preserves unknown and insufficient evidence, and live
provider acceptance remains `BLOCKED_EXTERNAL`; configuration presence or a
positive shadow metric is never a provider PASS or a production promotion.

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
