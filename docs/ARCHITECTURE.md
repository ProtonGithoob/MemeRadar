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
- SocialMentionObserved
- WalletActivityObserved
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
         Alpha Score
              |
       State Transition
          /        \
       Alert      Paper
```

A missing enrichment must not stall forever: use deadlines, explicit UNKNOWN states and retries. Critical UNKNOWN data blocks execution.

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

Adapters own transport, auth, provider payload mapping, timeout/retry/rate-limit semantics and health telemetry.

## Persistence

Repositories should be aggregate-oriented, not generic CRUD abstractions. Use transaction boundaries around state transitions/decision persistence. Adopt outbox semantics before any external side effect that must not be lost (alerts/execution).

## Data paths

### Hot path
new candidate -> minimal safety/market/on-chain features -> score -> alert. Keep network fan-out bounded and cache reusable provider observations.

### Warm path
holder graph, wallet profiling, social author enrichment and narrative analysis.

### Cold/research path
replay, historical backtests, cohort analysis, score calibration.

## Freshness

Feature values include `as_of`, `expires_at` and provenance. Score snapshots record freshness completeness. Live execution checks the exact freshness policy immediately before quote/order submission.

## Scaling strategy

Do not split services until measurements justify it. Likely future extraction candidates:
1. stream ingestion;
2. social ingestion;
3. wallet/graph analysis;
4. research/replay;
5. execution boundary.

## Failure behavior

- Provider timeout: bounded retry + jitter, then degrade feature/provider state.
- Rate limit: honor reset/backoff; no retry storm.
- Duplicate event: idempotent no-op/update.
- Out-of-order observation: preserve event time; recompute only if relevant.
- DB unavailable: stop side effects and fail readiness.
- Redis unavailable: degrade optional caching; do not lose business truth.
- Telegram unavailable: retain outbox/retry; do not block candidate processing.
- LLM unavailable: narrative becomes unavailable; deterministic scoring continues.
- Critical risk provider unavailable: analysis may continue with UNKNOWN; live execution blocked.

## Security boundaries

Analysis/paper workers must not need signing secrets. Live execution should run with a separate runtime role/secret scope when implemented. API authorization for execution/config changes is distinct from read-only dashboard access.

## Deployment progression

1. Local Docker Compose.
2. Single-node/staging deployment with managed Postgres/Redis.
3. Production analysis-only deployment.
4. Paper-trading production shadow mode.
5. Separate live execution component only after acceptance.
