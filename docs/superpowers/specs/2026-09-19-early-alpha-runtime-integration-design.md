# Early Alpha Runtime Integration Design

**Date:** 2026-09-19  
**Status:** Approved for implementation  
**Baseline:** `docs/EARLY_ALPHA_GAP_AUDIT.md`

## Goal

Connect MemeRadar's existing Solana discovery, event-time evidence, risk,
scoring, lifecycle, outbox, replay, and UI boundaries into one restart-safe
analysis-only early-alpha path. The path must produce an actionable staged
paper/research alert before later screener visibility when the available
evidence supports it, while preserving UNKNOWN, provenance, no-lookahead, and
executable-price semantics.

This is an integration change. It does not introduce a second winner detector,
a second Telegram implementation, a new frontend, or a new AlphaScore.

## Non-negotiable constraints

- Identity is exact `chain + mint`; ticker and name are display-only.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
  `AUTO_EXECUTION=false` remain enforced.
- Future outcomes are labels only and never enter live feature, score, risk, or
  decision inputs.
- Missing critical evidence is UNKNOWN, not zero or safe.
- A stream gap, unverified protocol identity, stale quote, absent liquidity,
  absent sellability, or absent impact evidence cannot improve a score or create
  executable outcome credit.
- Direct chain evidence must route by verified `(program_id, discriminator/tag)`.
- Raw market/reference price and executed/effective paper price remain distinct.

## Runtime architecture

The application boundary owns the following pipeline:

```text
provider event
  -> protocol decoder/normalizer
  -> stream integrity and cursor/gap state
  -> UltraEarlyDetector
  -> FastSafetyGate
  -> EarlyFeatureEngine (event time)
  -> existing wallet/creator/flow evidence
  -> OrganicMomentumProjection
  -> EarlyScorer + EarlyDecisionEngine
  -> Candidate/DecisionEngine lifecycle
  -> immutable early stage Observation
  -> existing AlertEventProjector/AlertDeliveryService/outbox
  -> asynchronous deep enrichment and later re-evaluation
```

The worker composes the service; it does not contain business logic. The live
provider seam remains optional and fail-closed. The same application service
accepts synthetic/replay observations, so deterministic tests exercise the
same normalization and scoring path as live shadow.

### Fast and deep paths

The fast path persists `DISCOVERED`, performs cheap authority/liquidity/
sellability/launch-risk checks, computes bounded early flow features, and may
produce `WATCH` or `EARLY_WATCH`. Creator graphs, historical wallet quality,
bundle analysis, social evidence, and deep flow enrichment run after the first
snapshot and can produce escalation or invalidation. A deep result can never
rewrite an earlier snapshot.

### FastSafetyGate

`FastSafetyGate` composes existing `token_security`, `LaunchRiskAnalyzer`,
flow/sellability/quote evidence, holder/creator/relationship evidence, and
signal-hardening snapshots. It returns a typed result with:

- disposition: `PASS`, `CAUTION`, `BLOCK`, or `UNKNOWN`;
- `CRITICAL_UNKNOWN` and `NONCRITICAL_UNKNOWN` reason groups;
- hard blocks, reason codes, evidence IDs, provenance, quality, and latency;
- no execution authority.

Critical UNKNOWN blocks `ENTRY_READY`; optional social/deep enrichment can
remain noncritical for early discovery.

### EarlyFeatureEngine and organic momentum

`EarlyFeatureEngine` is extended rather than duplicated. Its window policy is
configurable and includes approximately 30 seconds, 1, 2, 5, 10, and 15
minutes while retaining existing compatibility labels. Each window remains
half-open and event-time bounded.

The snapshot adds available buyer/seller, flow, velocity/acceleration,
liquidity/market-cap/price, trade-size, freshness, wallet, holder, creator,
and manipulation evidence. Missing values remain `None` with reason codes.

Acceleration uses a bounded log-ratio transform with an explicit denominator
floor and direction-preserving signed change. This makes `10 -> 25 -> 60`
meaningfully faster than `60 -> 61 -> 62` without letting `0 -> 1` dominate.

`OrganicMomentumProjection` is a bounded evidence projection consumed by the
existing EarlyScore component path. It is not a second score or execution
decision. Independent buyers/holders/liquidity/distributed sizes/smart money
raise it; wash/circular/repeated-size/shared-funder/creator-linked/bundle/
sniper/concentration/price-without-liquidity evidence lowers it.

### Canonical lifecycle and alerts

`CandidateState` gains `EARLY_WATCH` and `HIGH_CONFLUENCE` in the existing
decision lifecycle. Risk deterioration uses explicit downward transitions and
retains all previous transitions. The existing alert projector maps those
state changes to staged Telegram alert types and the existing outbox. Alert
dedupe identity is `(candidate, stage, stage evidence fingerprint)`.

`EARLY_WATCH` explicitly says `NOT ENTRY_READY` and `RESEARCH/PAPER SIGNAL`.
`ENTRY_READY` still requires the existing deterministic paper/shadow gates;
no alert grants live execution authority.

### Immutable stage snapshots

The existing append-only `observations` repository is the ledger. An
`early.stage_snapshot` observation contains the exact chain/mint, venue,
creation/observation/ingestion timestamps, first-seen values, one immutable
stage record, score/risk/organic/confidence, wallet/creator/bundle evidence,
buy/sell impact, sellability, reason/evidence IDs, provenance, configuration
hashes, and git revision when available. Its deterministic source identity is
unique for `(candidate, stage, decision_at, evidence fingerprint)`, so replay
and restart are idempotent without adding a duplicate persistence system.

Latency timestamps (`decision_at`, `alert_projected_at`, `telegram_queued_at`,
`telegram_delivery_started_at`, `telegram_sent_at`) are carried in the same
stage/alert evidence. `SENT_TO_TELEGRAM_API` is never mislabeled as user
delivery.

### Strict executable outcomes

`ExtremeWinnerOutcomeLabeler` retains raw mark peak separately from executable
peak. Executability requires fresh, sufficient liquidity, sellability, and
both buy and sell impact evidence within configured limits. Missing or stale
critical evidence yields `UNKNOWN_EXECUTABILITY`; it does not count toward
executable multiples. Stage baselines are labeled independently for first
seen, each signal stage, and first Telegram across 1h/6h/24h/72h/7d maturity
windows.

### Research analyzers and benchmark

`MissedWinnerAnalyzer` and `FalsePositiveAnalyzer` consume immutable stage
snapshots, transitions, latency/gap evidence, and future-only labels. They
emit reason-coded explanations with `ATTRIBUTED_EVIDENCE`, `SUSPECTED`, or
`UNKNOWN`; they do not claim causal proof.

`EarlyCallBenchmark` is extended for exact-mint DexScreener observations.
Only observed authoritative timestamps are stored. Trending/Top Volume
timestamps remain UNKNOWN when the API does not expose authoritative history.

## Persistence and compatibility

No new migration is required for the first implementation: stage evidence is
stored through the existing append-only `observations` table and outbox,
preserving provider-independent schemas and existing migration head. The read
projection is extended to recognize stage snapshots where available. If a
typed query cannot be expressed through the current observation boundary, the
implementation must first prove that limitation with a test before introducing
one narrowly scoped migration.

## Provider identity and external limits

Pump.fun, PumpSwap, Raydium, and Meteora keep their existing registry status.
Only `SUPPORTED_VERIFIED` entries can become authoritative. Unverified or
unavailable providers produce explicit UNKNOWN/BLOCKED_EXTERNAL evidence.
No protocol program ID or discriminator is invented. The worker records a
source matrix with decoder, normalizer, fixture, contract-test, connection,
and live-verification status.

## Testing strategy

Tests are added in this order: strict executable labels; lifecycle and staged
alert projection; fast safety; event-time features/acceleration; wallet
independence; organic momentum; immutable snapshots; worker integration and
restart/idempotency; missed/false analysis; benchmark/report; API/UI. The
end-to-end fixture covers organic winner, manipulated launch, incomplete
optional evidence, late winner, and future-label isolation. Full repository
verification remains the final gate.

