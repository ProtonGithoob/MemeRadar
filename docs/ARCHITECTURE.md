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
dependency; candidate transitions and alert decisions remain Sprint 6.3.

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
