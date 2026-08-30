# Roadmap Research Extensions — Executable Codex Backlog

This file converts the external repository/protocol research in `RESEARCH_REUSE_REGISTRY.md` into implementation work. It supplements `ROADMAP.md`; it does not invalidate completed tasks.

## Execution rule

Codex must:

1. finish the current task recorded in `docs/STATUS.md` first;
2. preserve all completed Phase 0–5 work;
3. insert the extensions below at the specified roadmap points;
4. use TDD/contract tests and keyless fixtures first;
5. keep live-provider acceptance separate as `BLOCKED_EXTERNAL` when credentials/network are absent;
6. never enable manual/automatic real-money execution merely because execution-related code is implemented;
7. update `docs/STATUS.md` after each extension sprint.

Status legend: `TODO`, `IN_PROGRESS`, `BLOCKED_EXTERNAL`, `DONE`.

---

## Extension E5.4 — Historical Caller/KOL Outcome Evidence

**When:** after Sprint 5.3 / Gate P5 and before Phase 6 feature scoring.

**Goal:** improve `AuthorTrustScore` using measurable historical token-call outcomes rather than static labels/follower counts.

### Tasks

- [x] Add normalized `SocialCall` model linking author, token/mint, call/event timestamp, source post IDs and provenance.
- [x] Add `SocialCallOutcome` research/application model with fixed forward horizons, MFE/MAE, liquidity-collapse/rug flags and data quality.
- [x] Reconstruct outcomes using only observations occurring after each call; prohibit future leakage.
- [x] Add bounded duplicate/conflicting-call handling.
- [x] Add `CallPerformanceSnapshot` per author with sample count, hit rates, median forward return/MFE, rug avoidance, token-age-at-call and uncertainty.
- [x] Update `AuthorTrustScorer` to optionally consume historical performance with shrinkage toward neutral.
- [x] Do not automatically promote authors based on one/few successful calls.
- [x] Add fixtures for good, poor, rug-heavy, duplicated and insufficient-sample callers.
- [x] Add reason codes and model/config versioning.

**Acceptance:** identical social/market event logs reproduce identical author-performance snapshots; missing outcome history lowers confidence instead of becoming a negative/positive fact.

**Keyless status (2026-08-30):** `DONE` for the provider-independent application
contract. `CallPerformanceAnalyzer` reconstructs fixed `5m`/`15m`/`1h`/`6h`/`24h`
forward windows without look-ahead, preserves nullable risk and token-age
evidence, applies bounded neutral shrinkage and keeps all results advisory.
Deterministic fixtures and replay contracts cover good, poor, rug-heavy,
duplicated and insufficient-sample callers. Live social/provider acceptance is
not required for this extension and remains separately `BLOCKED_EXTERNAL` where
credentials or endpoints are absent.

---

## Extension E6.0 — Correlation and Launch Micro-Features

**When:** before/inside Phase 6 Sprint 6.1.

**Goal:** model the first seconds/minute of a launch and correlate social/on-chain/wallet evidence without letting one source dominate.

### Tasks

- [x] Extend feature-window configuration to support `5s`, `15s`, `30s`, `60s`, `1m`, `5m`, `15m`.
- [x] Add micro-flow features:
  - unique buyers/sellers;
  - buyer arrival rate;
  - buy/sell quote volume;
  - buy/sell ratio;
  - net flow;
  - net-flow acceleration;
  - transaction/maker ratio;
  - liquidity delta and acceleration;
  - repeated-size/circular/rapid-round-trip diagnostics where row data exists.
- [x] Add smart-wallet micro-features after actor-cluster dedupe:
  - independent entry clusters;
  - weighted entry quality;
  - tracked-supply percentage when evidence supports it;
  - creator/related-wallet sell pressure.
- [x] Implement `CorrelationWindowBuilder` joining social, protocol, market, wallet and risk evidence by token and event time.
- [x] Add source-independence count and source-diversity confidence component.
- [x] Add minimum sample rules for ultra-short windows; insufficient samples become low confidence/UNKNOWN, never strong momentum.
- [x] Add no-lookahead and out-of-order tests.
- [x] Add golden fixtures representing organic acceleration, bot/wash burst, smart-wallet-only burst, social-only burst and creator dump.

**Acceptance:** a social-only or wallet-only burst cannot reach `ENTRY_READY`; correlated independent evidence can improve score/confidence only after hard risk requirements are satisfied.

**Keyless status (2026-08-30):** `DONE` for the provider-independent
correlation/replay seam. `CorrelationWindowPolicy` exposes the seven required
event-time windows, including the intentionally equivalent `60s` and `1m`
views. `CorrelationWindowBuilder` normalizes existing observations, social
mentions, wallet activities, smart-money events and risk assessments; sorts
by `(event_at, observed_at, ingested_at, provider, source_id, kind)`;
deduplicates equivalent source deliveries; rejects conflicting source reuse;
excludes future timestamps; and emits immutable, versioned features with
provenance, evidence references, freshness, source diversity and config hash.
Flow, liquidity, protocol lifecycle, social, wallet, actor-cluster and
creator/related-wallet features remain advisory. Missing/stale/unknown or
single-source evidence becomes low-confidence/`UNKNOWN`, malformed or
conflicting/future evidence is `INVALID`, and `execution_eligible()` is
permanently false. Synthetic golden scenarios and reverse-delivery replay
contracts live under `fixtures/providers/correlation/`; no physical migration
or final AlphaScore/decision wiring is introduced by E6.0.

---

## Extension E6.1 — Versioned AlphaStrategy Interface

**When:** before implementing final AlphaScore v1 decision wiring in Phase 6.

**Goal:** allow multiple deterministic strategies to be replayed/backtested without changing ingestion/provider code.

### Tasks

- [x] Define provider-free `AlphaStrategy` protocol/interface in application layer.
- [x] Inputs: immutable feature snapshot, risk assessment, current mode-safe policy/config.
- [x] Output: versioned strategy snapshot with components, raw score suggestion, penalties, confidence adjustments, reason codes and config hash.
- [x] Implement `AlphaScoreV1Strategy` matching `SCORING_AND_RISK.md`.
- [x] Hard risk blocks are evaluated outside/above the strategy and cannot be cleared by strategy output.
- [x] Strategy cannot access network, DB session, provider SDK, signer or execution port.
- [x] Persist strategy name/version/config hash with score/decision snapshots.
- [x] Add deterministic golden tests.
- [x] Add a second trivial/reference strategy only for framework tests, not production ranking.

**Keyless status (2026-08-30):** `DONE` for the provider-independent strategy
contract. `AlphaScoreV1Strategy` consumes immutable `FeatureSnapshot` and
`RiskAssessment` records, applies the documented seven weighted components and
bounded risk penalties, preserves hard blocks above the score, and emits an
advisory `StrategySnapshot` with strategy identity, confidence adjustments,
reason/evidence references and config hash. `ReferenceStrategy` exists only for
protocol tests. Score snapshots now persist explicit strategy name/version via
the reversible `0003_score_strategy_identity` migration. Golden replay covers
reverse mapping determinism, sparse evidence, penalty clamping, blocked and
unknown risk, strategy switching and no-provider imports. Live provider
acceptance remains separately `BLOCKED_EXTERNAL`.

**Acceptance:** same event/features/config produce byte-equivalent logical strategy output; switching strategy versions requires explicit config and is visible in audit/replay.

---

## Extension E6.2 — External Wallet Intelligence / Cross Validation

**When:** during Phase 6 after core internal SmartWalletScore exists.

**Goal:** use GMGN/CabalSpy-style labels/signals as corroboration while preserving internal scoring authority.

### Tasks

- [ ] Define normalized `ExternalWalletLabel` and `ExternalWalletTokenSignal` contracts.
- [ ] Preserve source, source confidence, observed time, expiry/TTL and raw source identifier.
- [ ] Implement `ExternalWalletIntelligencePort` adapter seam.
- [ ] Add keyless fake/fixture provider.
- [ ] Add optional GMGN-style adapter only against documented/legal endpoints available to the operator; no brittle scraping.
- [ ] Reconcile external labels with internal `SmartWalletScore`:
  - agreement -> bounded confidence bonus;
  - disagreement -> `CONFLICTED_EXTERNAL_WALLET_LABEL`;
  - stale label -> ignored for positive confidence;
  - internal graph correlation still collapses actor clusters.
- [ ] Add token-level features: `external_label_confidence`, `tracked_supply_pct`, `bundle_confidence`, `side_wallet_cluster_confidence` when evidence exists.
- [ ] External security/rug fields map only to corroborating risk evidence and never replace deterministic hard gates.
- [ ] Add provider doctor and fixture/live-acceptance split.

**Acceptance:** removing the external provider cannot change deterministic internal risk results; it only removes corroborating features/confidence.

---

## Extension E2.5 / E6.3 — Rich Pump.fun Protocol Lifecycle Events

**When:** implementation can occur after current Phase 5 work; wire features in Phase 6.

**Goal:** enrich existing Pump.fun/PumpSwap parsing with high-value lifecycle events derived independently from public protocol/transaction evidence.

### Tasks

- [x] Extend typed protocol event enum/schema with supported forms of:
  - `LAUNCH`;
  - `TRADE`;
  - `BONDING_CURVE_PROGRESS`;
  - `GRADUATION`/`MIGRATION`;
  - `POOL_CREATED`;
  - `WHALE_TRADE` (derived classification, not protocol fact when appropriate);
  - `CREATOR_FEE_CLAIM`;
  - `FEE_RECIPIENT_CHANGE`/CTO-like fee redirection.
- [x] Clearly distinguish native protocol facts from derived classifications.
- [x] Add parser/version/provenance to each normalized event.
- [x] Implement stream-first consumer with bounded reconnect and polling fallback where a legal/documented polling source exists.
- [x] Add deterministic fixture replay for event ordering, duplicates and malformed transactions.
- [x] Derive bonding-curve progress feature where state is reliably available.
- [x] Feed graduation/migration/creator-fee/fee-recipient events into timeline and risk/exit evidence without hard-coding them as positive/negative.

**License rule:** do not copy code from PumpKit or any repository with unclear/restrictive license. Independently implement behavior from official/public protocol contracts and transaction evidence.

**Acceptance:** existing Phase 2 parser contracts remain backward compatible or receive explicit schema version migration; new event types cannot trigger execution directly.

**Keyless status (2026-08-30):** `DONE` for the provider-independent event
and replay seam. `launchpad-dex-v2` / schema v2 normalizes the rich lifecycle
aliases, preserves parser provenance and event-time fields, validates reliable
`bonding_curve_progress_bps` evidence and marks whale classifications as
`DERIVED`. `ParsedProtocolEvent.to_observation()` emits deterministic
`protocol.lifecycle` evidence, while `ProtocolEventStreamFallback` bounds
reconnects, malformed input, duplicates, message counts and one poll fallback.
The synthetic replay covers Pump.fun and PumpSwap lifecycle ordering and safe
mode boundaries. Phase 6 correlation will consume these observations; rich
events do not directly transition candidates, clear risk, or authorize
execution. Live protocol/provider acceptance remains `BLOCKED_EXTERNAL` when
no documented read-only endpoint and credentials are configured.

---

## Extension E9.4 — Smart-Money / Creator Distribution Exit Correlation

**When:** Phase 9 Exit Engine.

**Goal:** make exits as evidence-driven as entries.

### Tasks

- [ ] Add rolling smart-wallet distribution pressure from independent actor clusters.
- [ ] Add creator/related-wallet sell pressure and holder-cluster reduction evidence.
- [ ] Add micro/macro buy-velocity collapse and sell-pressure acceleration.
- [ ] Add liquidity decay and quote deterioration correlation.
- [ ] Add external-wallet provider exit signals only as corroborating evidence.
- [ ] Add reason-coded composite `ExitRiskScore` separated from AlphaScore.
- [ ] Support partial exits based on configured policy; no hidden strategy state.
- [ ] Persist evidence timeline before/after exit.
- [ ] Backtest exit rules independently of entry rules.

**Acceptance:** every paper exit can explain which wallet, creator, liquidity, flow, score or time evidence caused it; one external provider alert alone cannot force an exit unless explicit emergency policy says so.

---

## Extension E10.1 — High-Fidelity Event Replay Dataset

**When:** Phase 10.

**Goal:** evaluate whether MemeRadar actually finds useful tokens early and calibrate thresholds using event-time replay.

### Tasks

- [ ] Persist/export compact normalized launch/event streams partitioned by date/venue/token.
- [ ] Implement deterministic event-time replay with tie-break rules.
- [ ] Pin provider parser version, strategy version and config hash for each run.
- [ ] Reconstruct all windows without future leakage.
- [ ] Add outcome labels:
  - MFE/MAE after 1m/5m/15m/1h/6h/24h as data permits;
  - time-to-1.5x/2x/3x;
  - time-to-50% drawdown;
  - liquidity collapse;
  - rug/security event;
  - creator dump;
  - paper exit result.
- [ ] Add cohorts by launch venue, liquidity band, token age at signal, AlphaScore band, confidence band, smart-wallet confluence and social velocity.
- [ ] Compare AlphaStrategy versions against the identical event set.
- [ ] Export reproducible research artifacts (JSON/CSV/Parquet as appropriate) without secrets/raw credentials.
- [ ] Profile replay throughput before considering Rust extraction.

**Acceptance:** replay run is reproducible from dataset + config + versions, and metrics are generated without live provider calls.

---

## Extension E10.2 — Author and Wallet Calibration

**When:** after E10.1.

### Tasks

- [ ] Calibrate `AuthorTrustScore` forward-outcome contribution.
- [ ] Calibrate SmartWalletScore minimum sample thresholds and shrinkage priors.
- [ ] Measure whether external labels add incremental predictive value over internal scores.
- [ ] Measure whether bundle/side-wallet detection reduces false smart-money confluence.
- [ ] Detect overfitting by time-split validation.
- [ ] Freeze production config only after out-of-sample evaluation.

**Acceptance:** any score-weight change includes reproducible evidence and before/after metrics.

---

## Extension E11.1 — Latency SLO and Stream Benchmarking

**When:** Phase 11 production hardening, before adding Rust/Yellowstone complexity.

### Tasks

- [ ] Add histograms/metrics for:
  - `chain_event_to_ingest_ms`;
  - `social_event_to_ingest_ms`;
  - `ingest_to_feature_ms`;
  - `feature_to_decision_ms`;
  - `chain_event_to_decision_ms`;
  - `candidate_to_alert_ms`.
- [ ] Add per-provider reconnect, fallback, duplicate, conflict and dropped-malformed counters.
- [ ] Establish baseline p50/p95/p99 in analysis-only environment.
- [ ] Define explicit latency SLOs only after measurement.
- [ ] Identify whether network/provider latency or internal processing is dominant.

**Acceptance:** optimization decisions cite measured bottlenecks rather than assumptions.

---

## Extension E11.2 — Optional Yellowstone gRPC / Rust Ingestion Sidecar

**When:** only if E11.1 demonstrates meaningful latency/throughput benefit.

**Goal:** reduce hot-path ingest latency without moving scoring/risk/execution authority into the sidecar.

### Tasks

- [ ] Define versioned sidecar-to-MemeRadar normalized event schema.
- [ ] Implement Yellowstone gRPC subscriptions for selected Pump.fun/PumpSwap/Raydium/LaunchLab account/transaction filters.
- [ ] Implement native event decoding only for required protocols.
- [ ] Add deterministic signature/source-event dedupe.
- [ ] Add bounded reconnect/backoff/checkpoint behavior.
- [ ] Add health/readiness and safe telemetry.
- [ ] Sidecar has no signer, no wallet private key and no execution capability.
- [ ] Keep Python/current provider path as fallback.
- [ ] Run A/B latency benchmark against existing ingestion.
- [ ] Deploy only if reliability and latency materially improve.

**Acceptance:** normalized downstream replay is semantically identical regardless of whether events arrived through current provider path or Rust sidecar.

---

## Extension E12.1 — Execution Simulation / Fee Accuracy

**When:** Phase 12 before any manual live submission.

### Tasks

- [ ] Improve Pump.fun/PumpSwap/Jupiter quote and transaction simulation using current protocol fee/creator-fee/bonding-curve information.
- [ ] Keep deterministic unsigned instruction/build simulation behind `QuotePort`/`ExecutionPort`.
- [ ] Validate expected fee, slippage, minimum received and route freshness before submission.
- [ ] Add stale blockhash/route and simulation-failure reason codes.
- [ ] Never introduce signer secrets into analysis/paper runtimes.

**Acceptance:** manual execution remains disabled by default; simulation can fail closed without a signer.

---

## Codex integration order

After finishing current Sprint 5.3:

```text
E5.4 Historical Caller/KOL Outcome Evidence
        ↓
E2.5 Rich Pump.fun events (provider enhancement)
        ↓
E6.0 Correlation + micro-features
        ↓
E6.1 AlphaStrategy interface
        ↓
E6.2 External wallet intelligence / cross-validation
        ↓
continue Phase 6 core score + decision work
        ↓
Phase 7–8
        ↓
Phase 9 + E9.4 exit correlation
        ↓
Phase 10 + E10.1/E10.2 replay/calibration
        ↓
Phase 11 + E11.1 latency benchmark
        ↓
E11.2 Rust/Yellowstone only if justified
        ↓
Phase 12 + E12.1 simulation accuracy
```

Codex must not skip unfinished core roadmap work just to implement a more exciting low-latency or execution feature.
