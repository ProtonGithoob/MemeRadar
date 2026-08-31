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
