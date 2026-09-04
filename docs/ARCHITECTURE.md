# Architecture

## Architectural style

Start as a modular monolith with asynchronous workers and explicit ports/adapters. This keeps deployment and transactions simple while preserving extraction boundaries for high-throughput paths.

## Layers

```text
apps/api + apps/worker + apps/web
            |
       application
            |
          domain
            ^
            |
 providers / persistence / telemetry
```

The domain has no framework/provider dependencies.

## Free-first provider composition

MemeRadar uses a small infrastructure composition layer rather than a broad
provider-registry rewrite. `build_provider_bundle` constructs the concrete
adapters and an application-owned `FreeFirstRoutePlan`; the application routing
module contains capability names and ordered provider labels only. Provider
HTTP models, authentication and retry details remain in provider adapters.

```text
application/domain ports and normalized evidence
                    ↑
        capability route plan + ports
                    ↑
       bounded provider composition layer
                    ↑
       adapter-specific HTTP transports
```

The keyless core is standard Solana JSON-RPC, DexScreener market/pair data and
local deterministic wallet/risk analysis. A configured Helius adapter is an
optional enhanced/standard-RPC preference with public RPC fallback; Helius DAS
and enhanced methods are never emulated by the generic adapter. DexScreener is
limited to market snapshots, reference quotes, deterministic pair discovery
and declared websites/social metadata. It is not a transaction, holder,
wallet-history, security-audit, realtime-stream or social-analytics provider.

The route plan is deterministic and capability-specific:

```text
CHAIN_RPC: Helius (configured) -> Solana public RPC
ENHANCED_ASSET_METADATA: Helius only -> unavailable/degraded
MARKET_SNAPSHOT / PAIR_DISCOVERY: DexScreener -> configured Birdeye
MARKET_QUOTE: DexScreener -> injected normalized custom quote port
RISK_SUMMARY: local deterministic engine + optional RugCheck evidence
WALLET_ENRICHMENT: local MemeRadar intelligence -> injected external enrichment
SOCIAL_METADATA: DexScreener -> optional analytics provider (separate capability)
NARRATIVE: Ollama -> explicitly configured external provider -> disabled
ALERT_DELIVERY: configured Telegram -> optional/unconfigured
```

Fallback wrappers attempt each route at most once and only on a normalized
provider error. Unsupported capabilities do not silently turn into unrelated
data. Every external observation/quote retains provider provenance, token/pair
identity, timestamps and freshness. The public Solana endpoint and public
market endpoint are rate-limited, non-guaranteed inputs; readiness reports
external blockers honestly and never treats the free stack as live-money
execution readiness.

## Runtime components

### API
FastAPI composition root, auth, queries, operator controls, health/readiness and manual actions.

### Worker
Async consumers/schedulers for discovery, enrichment, score recomputation, position monitoring, alerts, replay jobs and provider health.

### Web
Next.js/TypeScript operator UI consuming API contracts only.

Sprint 8.1 keeps the App Router page and layout server-rendered, with browser
APIs isolated to small client leaves for theme preference and realtime
connection lifecycle. The shell’s status primitives are display projections:
they show protected modes, advisory/live-data boundaries and non-safe
unavailable/unknown states but cannot mutate application state or authorize
execution. The optional public WebSocket seam is lifecycle-only, uses bounded
reconnect/degrade behavior and does not parse or persist incoming payloads.

Sprint 8.2 adds a bounded server-side read gateway for the Radar and token
detail routes. It validates API records before rendering, uses the internal
Compose URL when present, and keeps the optional viewer credential server-only.
The browser receives only bounded display records: API-provided candidate and
event-time ordering is preserved, raw provider payloads are not rendered,
metric charts are derived from an allow-list, and unavailable/unknown/stale/
invalid states remain visible. These routes are observability projections and
have no scoring, state-transition, configuration, signing or execution
authority.

Sprint 8.3 extends the same server-only gateway to wallet leaderboard/detail,
provider health/quota, validated control-state/configuration and audit/config
history pages. API order is preserved, catalogs remain explicit when empty,
and settings are a read-only explanation of the authenticated control boundary.
Wallet labels, provider health and audit/config metadata cannot change a
decision, protected mode or execution permission. The Playwright Gate P8 suite
exercises the rendered routes against a keyless local runtime and verifies
protected labels, fail-closed invalid input and the absence of browser
mutation/execution controls.

### PostgreSQL
System of record for normalized observations, candidates, features, decisions, positions, audit and research results.

### Redis
Ephemeral coordination only: rate limiting, dedupe windows, locks/caches and optional lightweight queue primitives. Durable business truth stays in PostgreSQL.

## Event model

Use an internal event envelope:

```text
id
kind
schema_version
aggregate_type
aggregate_id
occurred_at
observed_at
ingested_at
correlation_id
causation_id
producer
payload
```

Event handlers must be idempotent. Store processed keys or use natural/upsert constraints.

Core events:
- CandidateDiscovered
- MarketObservationReceived
- ProtocolEventObserved
- SocialMentionObserved
- WalletActivityObserved
- ExternalWalletLabelObserved
- SmartMoneySignalObserved
- RiskAssessmentUpdated
- FeaturesUpdated
- AlphaScoreUpdated
- AlphaScoreDelta
- RiskEscalation
- CandidateStateChanged
- AlertRequested/Delivered
- PaperOrderRequested/Filled/Rejected
- PositionOpened/Updated/Closed
- ExitSignalRaised
- ProviderHealthChanged
- ConfigChanged

## Candidate orchestration

```text
Discovery -> Candidate
               |
      parallel enrichments
      /    /     |      \
 market social onchain wallet
      \    \     |      /
       Feature Snapshot
              |
          Risk Gate
              |
         Alpha Strategy
              |
         Alpha Score
              |
       State Transition
          /        \
       Alert      Paper
```

A missing enrichment must not stall forever: use deadlines, explicit UNKNOWN states and retries. Critical UNKNOWN data blocks execution.

## Correlated alpha pipeline

The product must optimize for corroboration, not isolated triggers. The target hot-path correlation is:

```text
X/KOL mention --------------------+
Pump/DEX protocol event ----------+
smart-wallet/whale activity ------+--> Correlation Window
micro-flow acceleration ----------+        |
holder/bundle/side-wallet evidence+        v
liquidity/sellability -------------+   Feature Snapshot
security evidence ----------------+        |
                                           v
                                       Risk Gate
                                           |
                                      AlphaStrategy
                                           |
                                       AlphaScore
                                           |
                                 Decision State Machine
                                    /             \
                                 alert          paper entry
                                                   |
                               creator/smart-money distribution
                                                   |
                                               Exit Engine
```

Rules:
- no single X mention, KOL label, wallet signal, launch event, third-party risk score or LLM result can independently authorize entry;
- correlation uses event time and bounded windows, never processing order alone;
- provider/source independence contributes to confidence;
- correlated wallets are de-duplicated into actor clusters before smart-money breadth is calculated;
- all evidence remains traceable to source IDs and timestamps.

`FeatureWindowAggregator` consumes the immutable correlation output and
normalized application evidence to emit the canonical `1m`, `5m` and `15m`
`FeatureSnapshot` records. It is provider-, persistence- and execution-port
free; `FeatureSnapshotRepository` and the unit-of-work own durable writes.
Future evidence invalidates the derived snapshots, and missing family evidence
remains unknown. This seam prepares AlphaScore input but does not evaluate a
decision transition or authorize execution.

## Provider adapters

Each provider adapter implements a small port such as:

- CandidateDiscoveryPort
- MarketDataPort
- OnChainPort
- SocialDataPort
- RiskDataPort
- QuotePort
- ExecutionPort
- NotificationPort
- NarrativePort

Optional extension ports may be introduced only if current normalized contracts cannot represent evidence without ambiguity:
- `ProtocolEventPort` for typed launchpad/DEX lifecycle events;
- `ExternalWalletIntelligencePort` for labeled KOL/smart-money/whale evidence;
- `CrossValidationPort` for secondary provider corroboration;
- `LowLatencyDexEventSource` for Yellowstone/native stream ingestion.

Adapters own transport, auth, provider payload mapping, timeout/retry/rate-limit semantics and health telemetry. External labels and third-party token scores are evidence, never authority.

The provider-health comparison seam in
`memeradar_application.provider_routing` consumes normalized operational
health records only. It deterministically prefers fresh healthy candidates and
returns explicit degraded, unknown, conflicted or unavailable outcomes when a
safe selection is not possible. It has no provider SDK, scoring, configuration
mutation, signer or execution authority.

## Launch-time micro-feature path

In addition to normal `1m/5m/15m` feature windows, newly launched candidates may use `5s/15s/30s/60s` bounded micro-windows for:

- unique buyer arrival rate;
- buy/sell volume;
- buy/sell ratio;
- net flow and acceleration;
- transaction/maker ratio;
- liquidity growth/decay;
- smart-wallet entry count after actor clustering;
- creator/related-wallet sell pressure;
- bonding-curve progress where reliable.

Micro-features never weaken minimum safety, liquidity or freshness requirements. When sample size is insufficient, confidence drops rather than inventing a signal.

## Pump.fun / launchpad event semantics

Where reliably derivable from official/public transaction/program evidence, normalize typed protocol events such as:

- launch/create;
- trade;
- graduation/migration;
- bonding-curve progress;
- whale trade;
- creator fee claim;
- fee-recipient/CTO-style change;
- pool creation/migration.

The stream path should be preferred and bounded polling used only as fallback. Restrictive or unclear third-party repository licenses must never be bypassed; implement protocol behavior independently from public contracts/evidence when necessary.

## External wallet intelligence

External labeled-wallet sources can enrich but not replace MemeRadar's own wallet scoring. Normalize:

- wallet address;
- label/tier claim;
- source and source confidence;
- label observed time and TTL;
- token-level position/activity if supplied;
- smart-money/KOL/whale classification;
- bundle/side-wallet relationship evidence when supplied.

Application correlation should expose separate features such as:

- `smart_wallet_confluence`;
- `tracked_supply_pct`;
- `external_label_confidence`;
- `bundle_confidence`;
- `side_wallet_cluster_confidence`.

External labels must be compared with internally derived `SmartWalletScore`. Material disagreement becomes explicit conflict evidence.

## Cross-validation layer

Secondary providers such as GMGN-style token/smart-money APIs may be used as corroboration providers. Cross-validation rules:

- agreement between independent sources can raise evidence confidence within configured bounds;
- disagreement creates `CONFLICTED` quality/reason codes;
- third-party security/rug claims never override deterministic on-chain checks;
- source-specific values remain preserved for audit and replay;
- provider outage reduces confidence but must not rewrite historical observations.

## Strategy abstraction

Before AlphaScore/decision execution, introduce a versioned `AlphaStrategy` application interface. It receives a fixed feature/risk snapshot and configuration and returns deterministic strategy components/reasons.

Requirements:
- pure/deterministic for identical input/config;
- no direct provider/network access;
- no signing/execution access;
- cannot override hard risk blocks;
- version/config hash persisted with results;
- multiple strategies can be replayed/A-B compared in Phase 10 without changing ingestion.

The initial strategy remains AlphaScore v1 from `SCORING_AND_RISK.md`.

Core Sprint 6.2 uses `AlphaScoreRecomputer` to load immutable feature/risk
records through application-facing repository protocols, delegate evaluation
to the selected strategy, assign a replay-stable score identity and persist
through the caller-owned unit of work. It exposes no provider or execution
dependency.

Core Sprint 6.3 uses `DecisionEngine` and a versioned `DecisionPolicy` to
consume score/risk snapshots and apply one lifecycle transition at a time.
The default score bands are 40/75/85 with 35/70/80 downward hysteresis floors,
0.60 minimum decision confidence and a 30-second cooldown. Critical risk
freshness, hard blocks, config identity, score freshness and risk execution
eligibility are rechecked above the score. Unsafe risk becomes
`RISK_REJECTED`; warnings cap progression before `ENTRY_READY`. The engine
only reaches `ENTRY_READY`, never opens a paper/live position, and persists
through caller-owned `CandidateStore`/snapshot ports when requested.

Score-delta and risk-escalation `EventEnvelope` values carry stable
idempotency identities, timestamps, reason codes, snapshot references and
config/policy identity. `EvidenceTimelineProjector` produces a deterministic
event-time projection of transitions, events and feature/risk/score snapshots;
its optional `as_of` boundary excludes future evidence.

The Sprint 7.1 alert path projects meaningful decision, risk, provider-health
and system-health events through the provider-independent
`AlertEventProjector`. `AlertRenderer` emits bounded, plain-text messages with
reason codes and evidence references; it allow-lists payload fields and
redacts secret-shaped values. `AlertDeliveryService` persists the existing
`Alert` aggregate by `dedupe_key`, applies protected alert policy and a
per-destination fixed-window limiter, then sends through `NotificationPort`.
Notification work is enqueued as `side_effect_kind=notification` and consumed
by the leased outbox processor, so transient failures and provider rate limits
remain retryable without holding up candidate processing. Delivery state never
changes a candidate, risk gate, operating mode or execution permission.

## Read API

Sprint 7.2 exposes a typed, GET-only operator read surface over the
application-facing `ReadQueryPort`. Candidate ranking/filtering, token detail,
event-time timeline, wallet intelligence, provider health and audit/config
queries return bounded page envelopes with versioned, resource-scoped opaque
keyset cursors. The FastAPI layer maps immutable application views into strict
response models; it does not invoke providers, mutate state, transition a
candidate, send an alert, change configuration or authorize execution.

`SqlAlchemyReadQueryService` reads the existing normalized token, pool,
candidate, observation, feature, risk, score, transition and alert tables with
bounded storage reads. Audit/config views now project the physical Sprint 7.3
control-plane tables; wallet/provider-health remain injectable catalogs until
their physical persistence task. An empty catalog is explicit and never
fabricated as healthy. Read payloads are copied through a recursive bounded
redactor, raw provider body references are not returned, and malformed queries
or unavailable storage fail with safe public errors. Timeline ordering uses
occurred time plus a stable ID tie-breaker, and `as_of` excludes future
evidence. If any role credential is configured, all read routes require a
valid role bearer token; an unconfigured development process retains its
keyless read behavior.

The web read gateway is a separate server-side composition boundary over these
contracts. It applies a bounded timeout, status-safe failure mapping and
strict UUID/timestamp/numeric/string/array parsing before passing records to
server components. The token detail view iterates the API timeline order and
projects only allow-listed market, liquidity, flow and holder fields into
native SVG/CSS; social and narrative entries expose provenance/reason codes,
not untrusted text or raw provider bodies. Wallet/provider/control/audit
records use the same strict boundary and allow-listed display projections; no
browser fetch or control mutation is introduced.

## Authenticated control plane

Sprint 7.3 adds an application-facing control port with explicit viewer,
operator, admin and execution roles. The API resolves static role-scoped
bearer tokens only at the boundary, compares them in constant time and emits
non-secret principals. Viewer roles can read control state/config; operators
can pause/resume analysis and activate the restrictive execution kill switch;
admins can mutate validated config; the execution role can only read and
activate the execution stop. Config changes are allow-listed, hash-stable,
versioned and paired with immutable audit events. The SQLAlchemy adapter writes
state/config/audit changes transactionally. The default execution kill switch
is active, and protected modes prevent clearing it. No control route changes
the four operating modes or grants execution/signing authority.

## Persistence

Repositories should be aggregate-oriented, not generic CRUD abstractions. Use transaction boundaries around state transitions/decision persistence. Adopt outbox semantics before any external side effect that must not be lost (alerts/execution).

Persist enough normalized event/feature history for deterministic historical replay. Raw provider payload retention is optional and must be bounded/redacted; normalized event truth is mandatory for research.

The core Sprint 6.1 feature-window slice uses the existing
`feature_snapshots` table. Its aggregate repository preserves deterministic
snapshot identity, JSON-safe values, provenance, freshness and config
identity, while callers retain transaction ownership through the unit of
work.

The core Sprint 6.2 score slice similarly uses the existing risk and score
tables. Risk/score repositories preserve hard-block references, penalties,
reason codes, strategy identity and config hashes while equivalent replay is
accepted and conflicting identity reuse fails closed.

Sprint 7.1 reuses the existing `alerts` and `outbox` tables. Alert repository
writes preserve typed severity/state, payload, reasons, evidence and delivery
timestamps; equivalent dedupe keys are idempotent and conflicting alert
identity is rejected. Notification outbox claims are filtered by side-effect
kind and retain bounded retry/error metadata. Telegram is an adapter concern;
the keyless fixture and doctor allow local verification without credentials.

Sprint 7.3 adds `control_state`, `config_versions` and `audit_events` through
reversible migration `0004_control_plane`. The singleton state row is the
durable restrictive control projection; config versions contain only validated
non-secret values and unique canonical hashes; audit rows retain actor,
action, target, safe before/after values, timestamp and correlation identity.
Control mutations and their audit records share a transaction, while read
queries remain bounded and append-oriented.

### E8.4 stream integrity and protocol verification

The Solana ingest retrofit keeps transport, completeness and protocol decoding
separate:

```text
stream -> ChainCursor/GapDetector -> ProtocolIdentityRegistry
       -> CanonicalProtocolDecoder -> NormalizedChainEvent
       -> durable observation/event log -> feature/correlation/AlphaScore
```

`StreamIntegrityCoordinator` persists a normalized event before advancing the
durable cursor. A discontinuity creates an explicit bounded `StreamGap`; RPC
or another approved backfill source returns actual produced slots, and every
recovered transaction goes through the same canonical decoder used by live and
replay traffic. Overlapping gaps merge deterministically, skipped slots are
not treated as produced blocks, and a queue saturation raises observable
backpressure instead of dropping an event.

`ChainCursor` retains observed, contiguous and finalized progress separately.
Commitment is normalized as processed/unconfirmed, confirmed, finalized,
reverted or unknown. A later revert retains the original projection and emits
an append-only correction event. Recovery provenance, parser/registry/schema
versions and replay strategy/config identities remain attached to normalized
evidence. The protocol registry routes only on
`(program_id, discriminator_or_tag)`; unknown, unverified or conflicting
identities fail closed.

Open, failed, unverified or conflicting integrity state only reduces feature
completeness/confidence and can never increase AlphaScore or authorize
`ENTRY_READY`. `ReplayManifest` pins the event-time boundary and parser,
registry, event-schema, strategy and config identities so replay is
provider-independent and cannot use future evidence. Migration
`0005_stream_integrity` adds durable cursors, gaps, verification reports and
nullable chain metadata to normalized observations. The optional Rust/
Yellowstone path remains deferred until E11.1 measures a material need.

### Phase 9.1 paper execution

The paper boundary consumes only normalized `QuoteSnapshot` values plus an
immutable decision reference and risk snapshot:

```text
decision/risk + quote -> PaperSizingPolicy -> PaperFillModel
                    -> PaperOrder/PaperFill -> cash ledger + Position
                    -> PaperLedgerStore -> reconciliation/replay projection
```

`PaperExecutionEngine` is provider- and persistence-independent. It applies
bounded Decimal sizing, quote freshness checks, adverse slippage and fees,
append-only cash movements, explicit partial/rejected states and idempotent
order keys. `InMemoryPaperLedgerStore` is the deterministic fixture/replay
store; `SqlAlchemyPaperLedgerStore` persists the same application result
atomically under migration `0006_paper_execution`. Replay uses a fresh store,
event-time ordering with deterministic tie-breakers, deterministic identities,
and `PaperReplayManifest` policy/config/fill-model/schema pins. It excludes
future requests or future-observed quotes and has no provider, signer or
transaction-submission capability. Reconciliation never repairs evidence;
mismatches remain explicit `CONFLICTED` results.

### Phase 9.2 exit intelligence

The exit boundary consumes an immutable, normalized evidence snapshot and a
versioned `ExitRulePolicy`. `ExitEngine` produces an independent
`ExitRiskScore` and advisory `ExitEvaluation` for fixed protective,
distribution/flow/liquidity, score/time, trailing/break-even and partial
take-profit rules. It never mutates a position or submits an order. The
append-oriented in-memory timeline and `SqlAlchemyExitEvaluationStore` persist
the same evidence-bearing evaluation through the existing `domain_events` log,
including before/after evidence references and idempotency checks. Replay
sorts by event time and excludes future observations while pinning policy,
configuration and schema identity. External distribution labels remain
corroboration only and live market-data acceptance remains `BLOCKED_EXTERNAL`.

### Phase 9.3 position projections and Telegram alerts

The position read surface extends the existing application `ReadQueryPort` over
`PositionRow`, token identity and normalized market observations. It selects an
allow-listed latest mark at or before the optional event-time boundary, keeps
provider/source/parser and all observation timestamps visible, and derives
current value and PnL only when the mark is fresh and valid. Missing, stale,
invalid or conflicted marks leave current PnL unknown; persisted realized PnL,
MFE and MAE remain visible as explicitly qualified evidence. Exit evaluations
are rehydrated through the same immutable domain-event contract, so the
dashboard can show advisory exit risk and closed-trade explanations without a
second position store or invisible history mutation.

`ExitSignal`, `ExitEvaluation` and `PaperExit` events reuse the existing
`AlertEventProjector`, alert repository, notification outbox and
`NotificationPort`/Telegram adapter. Only non-HOLD events with a core
deterministic trigger produce `EXIT_RISK` or `PAPER_EXIT`; external-only wallet
intelligence remains corroboration and cannot create a notification by itself.
The server-rendered `/positions` route and API are GET-only and permanently
non-authorizing. No browser or notification path can mutate a position, change
operating modes, sign or submit a transaction.

## Data paths

### Hot path
new candidate -> minimal safety/market/on-chain features -> correlation/micro-features -> score -> alert. Keep network fan-out bounded and cache reusable provider observations.

### Warm path
holder graph, wallet profiling, external label reconciliation, social author enrichment and narrative analysis.

### Cold/research path
replay, historical backtests, cohort analysis, score calibration, alternate AlphaStrategy comparison and event-latency analysis.

## Freshness

Feature values include `as_of`, `expires_at` and provenance. Score snapshots record freshness completeness. Live execution checks the exact freshness policy immediately before quote/order submission.

External labels also have TTL/freshness; a historical KOL label is not permanent truth.

## Observability and latency

Record latency separately for provider/network and internal processing. At minimum:

- `chain_event_to_ingest_ms`;
- `social_event_to_ingest_ms`;
- `ingest_to_feature_ms`;
- `feature_to_decision_ms`;
- `chain_event_to_decision_ms`;
- provider reconnect/fallback counts;
- duplicate/conflict counts;
- candidate-to-alert latency.

Use histograms/percentiles where appropriate. Latency optimization is not accepted if it bypasses normalization, risk or idempotency.

Phase 11.1 adds the provider-independent `ReliabilityMetrics` collector in
`packages/application/src/memeradar_application/reliability.py`. It keeps
fixed-memory nearest-rank p50/p95/p99 histograms with explicit eviction
counts, safe provider-labelled counters and provider-network versus internal
source attribution. `ProviderTransport`, the Helius/Birdeye/protocol stream
fallback seams, the canonical stream coordinator and the durable outbox may
report classified outcomes through the optional sink; telemetry failures never
change business outcomes. `make reliability-benchmark` is a synthetic,
keyless measurement of the six stages and reports live provider acceptance as
`BLOCKED_EXTERNAL`; it is evidence for measurement only, not an SLO or a
Rust/Yellowstone authorization. The operational retention/index review and
isolated backup/restore procedure are in
[`docs/RUNBOOKS/RELIABILITY.md`](RUNBOOKS/RELIABILITY.md).

Phase 11.2 adds the provider-independent `OperationsProjector` and
`OperationsReadPort`. It combines normalized provider-health records with the
bounded reliability snapshot into a deterministic, read-only overview of
provider state, versioned SLO evidence, stream/queue/outbox alerts and
quota/cost pressure. Synthetic or insufficient provider-network samples stay
`UNVERIFIED`; missing/stale/conflicted evidence stays `UNKNOWN`/`DEGRADED`.
The API route and server-rendered `/operations` page are projections only.
Operational health is never passed to AlphaScore, decision transitions or
execution authority. Incident procedures are in
[`docs/RUNBOOKS/OPERATIONS.md`](RUNBOOKS/OPERATIONS.md) and the lower-level
[`docs/RUNBOOKS/RELIABILITY.md`](RUNBOOKS/RELIABILITY.md).

Phase 11.3 keeps security review outside the application/domain path. The
repository-owned `security-review-v1` diagnostic verifies exact lock metadata,
versioned/non-root image construction, tracked-file secret absence, bearer
RBAC/session contracts, strict advisory narrative boundaries and protected
modes. Optional pip-audit/npm-audit/container vulnerability checks use fixed
commands and classify missing tools or registries as `BLOCKED_EXTERNAL`; raw
scanner output is never persisted. The reviewed threat model and procedures
are in [`docs/THREAT_MODEL.md`](THREAT_MODEL.md) and
[`docs/RUNBOOKS/SECURITY_REVIEW.md`](RUNBOOKS/SECURITY_REVIEW.md).

The approved E11.4–E11.9 signal-hardening extension is a provider-independent
application seam in
`packages/application/src/memeradar_application/signal_hardening.py`. It
normalizes sustained surge/revival, economic move funding, deployer
self-activity/transfer deltas, bounded launch sniper/bundle footprints and
token/vesting unlock evidence from the same `Observation` contract used by
live and replay paths. `CorrelationWindowBuilder` carries typed snapshots;
`FeatureWindowAggregator`, the evidence timeline and exit diagnostics expose
them as corroborating quality/risk data without adding an AlphaScore component
or execution authority. `ReplayHarness` invokes the same analyzer at each
event-time checkpoint and pins `signal_hardening_version` alongside parser,
registry, schema, strategy and config identity. Missing/stale/conflicted
evidence remains explicit, healthy stream status is neutral to score, and
MadeOnSol is not a runtime dependency or source of trading truth.

## Scaling strategy

Do not split services until measurements justify it. Likely future extraction candidates:
1. stream ingestion;
2. social ingestion;
3. wallet/graph analysis;
4. research/replay;
5. execution boundary.

### Optional low-latency ingestion sidecar

If measurements show the Python stream path cannot meet the target, add a Rust sidecar for Yellowstone gRPC/native Pump.fun/PumpSwap/Raydium/LaunchLab decoding.

Hard rules:
- sidecar is ingestion/decoding only;
- output uses a versioned normalized internal contract identical in semantics to existing events;
- sidecar cannot score risk, change operating modes, sign or authorize trades;
- signature/source-event dedupe remains deterministic;
- benchmark before and after extraction and retain fallback to the standard provider path;
- do not introduce this complexity before profiling proves value.

## Replay architecture

Phase 10 research must replay normalized events by event time with no future-data leakage. Required capabilities:

- deterministic ordering/tie-break rules;
- configuration/model version pinning;
- historical feature reconstruction;
- alternate `AlphaStrategy` execution against the same event stream;
- candidate cohort queries by launch venue/token age/score band;
- outcome labels such as MFE/MAE, time-to-2x/3x, rug/liquidity-collapse and realized paper exit;
- fast bulk replay, with optional Rust extraction only if profiling justifies it.

Sprint 10.1 implements this boundary in
`packages/application/src/memeradar_application/replay_harness.py`. A
`ReplayDataset` stores normalized `Observation` records with parser/registry/
schema provenance and explicit signal checkpoints; its deterministic
date/venue/token partition index is included in the dataset digest. Each
checkpoint passes only evidence whose occurred, observed and ingested times
are known by that boundary into the existing `CorrelationWindowBuilder` and
`FeatureWindowAggregator`. `OutcomeLabeler` consumes the later evidence only
for outcome labels, never for features or strategy input. The result includes
stable cohort dimensions, a future-event exclusion list, canonical JSON and
flat CSV projections, while `ReplayStrategyComparison` reruns alternate
strategies against the same dataset digest and checkpoint boundaries. The
local profile command measures throughput; it does not introduce a provider,
database, signer or execution dependency.

Phase 10.2 implements the downstream
`packages/application/src/memeradar_application/backtesting.py` projection.
It consumes only the immutable replay result, uses fresh advisory strategy
snapshots with explicit PASS risk evidence for entry selection, and evaluates
exit rules independently from entry thresholds. Both trade legs reuse the
existing `paper-fill-v1` model with bounded fee/slippage assumptions. Reports
are fixed-notional research artifacts with explicit unknown/skip states,
score-bucket calibration and deterministic segment metrics for venue,
liquidity, token age, market regime, social velocity and smart-wallet
confluence. Backtest output cannot mutate paper positions, create alerts,
authorize `ENTRY_READY` or change protected operating modes.

Phase 10.3 adds the provider-free score-calibration projection in
`packages/application/src/memeradar_application/calibration.py`. It consumes
the immutable `ResearchReplayResult`, rebuilds each candidate strategy from
the feature/risk snapshot available at that checkpoint, and delegates all
trade arithmetic to `BacktestHarness`; live, replay and calibration therefore
share the same normalized event-time evidence boundary. Half-open UTC
train/validation/test partitions prevent future-data leakage, candidate
selection uses train metrics only, and validation/test results remain
out-of-sample evidence. Feature ablations neutralize only the named component
while preserving missing/unknown quality and hard-risk behavior. Candidates
carry versioned hashes and `is_production=false` shadow identity; reports are
descriptive artifacts with no production-config write, promotion, decision or
execution path. The E10.2 attribution seam similarly measures author trust,
internal smart-money, external-label incremental value and bundle/side-wallet
false confluence without making external evidence authoritative.

## Failure behavior

- Provider timeout: bounded retry + jitter, then degrade feature/provider state.
- Rate limit: honor reset/backoff; no retry storm.
- Stream unavailable: bounded reconnect then configured polling/secondary-source fallback.
- Duplicate event: idempotent no-op/update.
- Conflicting independent evidence: preserve both; emit `CONFLICTED`; reduce confidence/block where policy requires.
- Out-of-order observation: preserve event time; recompute only if relevant.
- DB unavailable: stop side effects and fail readiness.
- Redis unavailable: degrade optional caching; do not lose business truth.
- Telegram unavailable: retain outbox/retry; do not block candidate processing.
- Notification authentication/schema failure: record only a bounded error
  class, retry only according to the provider policy, and never persist the
  response body, token or raw provider text.
- LLM unavailable: narrative becomes unavailable; deterministic scoring continues.
- Critical risk provider unavailable: analysis may continue with UNKNOWN; live execution blocked.

## Security boundaries

Analysis/paper workers must not need signing secrets. Live execution should run with a separate runtime role/secret scope when implemented. API authorization for execution/config changes is distinct from read-only dashboard access.

Low-latency ingestion, external smart-money sources and cross-validation providers receive no signing authority.

## Deployment progression

1. Local Docker Compose.
2. Single-node/staging deployment with managed Postgres/Redis.
3. Production analysis-only deployment.
4. Paper-trading production shadow mode.
5. Separate live execution component only after acceptance.
