# Early Alpha Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect existing Solana discovery and evidence components into a durable, staged, analysis-only early-alpha pipeline with strict executable research labels.

**Architecture:** Extend existing `early_features.py`, `early_replay.py`, lifecycle/alert projection, and observation persistence. Add only small orchestration responsibilities for fast safety, runtime processing, and missed/false attribution. The worker composes the application service; provider identity remains registry-controlled and live-unavailable inputs remain UNKNOWN/BLOCKED_EXTERNAL.

**Tech Stack:** Python 3.12, dataclasses, SQLAlchemy append-only observations/outbox, pytest, existing React/Next read surface, Make targets.

**Spec:** `docs/superpowers/specs/2026-09-19-early-alpha-runtime-integration-design.md`

## Global Constraints

- Identity is exact `chain + mint`; ticker and name are display-only.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` remain enforced.
- Future outcomes are labels only and never enter live feature, score, risk, or decision inputs.
- Missing critical evidence is UNKNOWN, not zero or safe.
- Direct chain evidence routes by verified `(program_id, discriminator/tag)`.
- Raw market/reference price and executed/effective paper price remain distinct.
- Reuse existing provider, graph, flow, lifecycle, outbox, replay, persistence, and UI boundaries.
- No live-money execution, secret output, invented provider identity, invented benchmark timestamp, or fabricated alpha claim.

## Review Focus

- Missing liquidity/impact/sellability must not become executable — owned by Task 1 tests.
- A gap or restart must not duplicate candidates, snapshots, transitions, or alerts — owned by Tasks 4 and 6.
- Shared-funder wallets must not count as independent smart money — owned by Task 3 tests.
- Future outcomes must never enter runtime score/decision inputs — owned by Tasks 1 and 5.
- UNKNOWN must render and report as UNKNOWN rather than zero — owned by Tasks 4, 7, and 8.

---

### Task 1: Strict executable outcome semantics

**Files:**
- Modify: `packages/application/src/memeradar_application/early_replay.py:ExtremeWinnerOutcomeLabeler`
- Test: `tests/unit/test_extreme_winner_labels.py`
- Test: `tests/contract/test_extension_e10_4_extreme_winner_labels.py`

**Interfaces:**
- Consumes: existing `ReplayEventRecord`, `ReplayCheckpoint`, `market_reference_price`, liquidity/sellability/impact payload fields.
- Produces: `ExtremeWinnerOutcomeSnapshot` with separate raw/executable fields and `UNKNOWN_EXECUTABILITY` reason evidence.

- [ ] **Step 1: Write failing tests** for liquid executable 10x, mark-only 10x, 100x no exit liquidity, missing liquidity, missing impact, stale quote, sellability failure, high buy impact, and high sell impact.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/unit/test_extreme_winner_labels.py tests/contract/test_extension_e10_4_extreme_winner_labels.py`; expected: new cases fail because missing evidence is currently executable.
- [ ] **Step 3: Implement** a shared strict executability predicate in `early_replay.py`: fresh explicit liquidity, sellability, buy impact, and sell impact are all required; absent/stale values set UNKNOWN and never update executable peak/hits.
- [ ] **Step 4: Run** the focused tests and existing early replay tests; expected: all pass and existing mark-wick labels retain raw multiples.
- [ ] **Step 5: Run** `.venv/bin/ruff check packages/application/src/memeradar_application/early_replay.py tests/unit/test_extreme_winner_labels.py`.

### Task 2: Event-time features, robust acceleration, and organic momentum

**Files:**
- Modify: `packages/application/src/memeradar_application/early_features.py`
- Modify: `packages/application/src/memeradar_application/correlation.py` only where an existing projection is required
- Create: `packages/application/src/memeradar_application/organic_momentum.py`
- Test: `tests/unit/test_early_features.py`
- Create: `tests/unit/test_organic_momentum.py`

**Interfaces:**
- Consumes: existing normalized observations, correlation/flow/holder/wallet evidence.
- Produces: extended `EarlyFeatureSnapshot`, configurable launch windows, bounded acceleration values, and `OrganicMomentumProjection`.

- [ ] **Step 1: Write failing tests** for six configurable windows, event-time half-open boundaries, buyer/seller fields, median/p90 trade size, missingness, `0→1`, `1→20`, `10→20`, `20→40`, `100→110`, and organic penalties.
- [ ] **Step 2: Run** the focused tests; expected: missing fields/class and normalization assertions fail.
- [ ] **Step 3: Implement** the smallest extension of `EarlyFeatureEngine`: window policy override, seller/volume/liquidity/market-cap/price rates, size percentiles, wallet/creator/holder evidence extraction, and a bounded signed log-ratio acceleration helper. Preserve legacy window defaults and no-lookahead.
- [ ] **Step 4: Implement** `OrganicMomentumProjection` as a bounded evidence projection consuming existing ratios and independent counts; never import future-label modules.
- [ ] **Step 5: Run** focused early feature, correlation, flow, and organic momentum tests; expected: all pass.

### Task 3: Fast safety and smart-wallet independence

**Files:**
- Create: `packages/application/src/memeradar_application/fast_safety.py`
- Modify: `packages/application/src/memeradar_application/launch_risk.py` only for shared typed helpers
- Modify: `packages/application/src/memeradar_application/early_scoring.py` to consume independent confluence when supplied
- Create: `tests/unit/test_fast_safety.py`
- Modify: `tests/unit/test_early_scoring.py`

**Interfaces:**
- Consumes: token security, launch risk, flow/sellability, holder/creator/relationship, confluence, quote, and signal-hardening snapshots.
- Produces: `FastSafetyResult` with PASS/CAUTION/BLOCK/UNKNOWN, critical/noncritical unknowns, evidence, provenance, and measured duration.

- [ ] **Step 1: Write failing tests** for PASS, CAUTION, BLOCK, critical UNKNOWN, noncritical social UNKNOWN, shared-funder five-wallet collapse, creator-linked wallets, bundle/sniper risk, and sellability/impact failure.
- [ ] **Step 2: Run** focused tests; expected: module/result is missing.
- [ ] **Step 3: Implement** the orchestration-only gate; do not duplicate graph or flow algorithms. Ensure unknown critical evidence blocks entry and optional enrichment does not block first persistence.
- [ ] **Step 4: Add** independent smart-wallet count and shared-funder/coordinated probability to the supplied early confluence mapping without changing raw historical wallet quality semantics.
- [ ] **Step 5: Run** fast safety, confluence, launch-risk, holder, and early-scoring tests.

### Task 4: Canonical staged lifecycle and Telegram projection

**Files:**
- Modify: `packages/domain/src/memeradar_domain/lifecycle.py`
- Modify: `packages/domain/src/memeradar_domain/operations.py`
- Modify: `packages/application/src/memeradar_application/decision_engine.py`
- Modify: `packages/application/src/memeradar_application/alert_pipeline.py`
- Modify: `packages/application/src/memeradar_application/early_alpha_alert.py` only for shared rendering helpers
- Create: `tests/unit/test_early_staged_lifecycle.py`
- Modify: `tests/unit/test_alert_pipeline.py`

**Interfaces:**
- Consumes: score/risk/organic/fast-safety snapshots and existing candidate transitions.
- Produces: auditable `EARLY_WATCH`, `STRONG_SETUP`, `HIGH_CONFLUENCE`, `ENTRY_READY`, and invalidation transitions mapped to existing outbox alerts.

- [ ] **Step 1: Write failing tests** for staged transitions, material dedup, invalidation reasons, `EARLY_WATCH` copy, and paper-only `ENTRY_READY`.
- [ ] **Step 2: Run** focused tests; expected: canonical state/alert mapping rejects new stages.
- [ ] **Step 3: Extend** `CandidateState`, allow-list, decision desired-state logic, downgrade logic, and `AlertType`/projector mapping while preserving existing lifecycle tests.
- [ ] **Step 4: Render** staged payloads with age, market cap, liquidity, accelerations, independent wallets, risk, impact, score, confidence, reason/evidence IDs, and explicit research/paper language.
- [ ] **Step 5: Run** all domain lifecycle, decision, alert, and Telegram adapter tests.

### Task 5: Immutable snapshots and provider-independent runtime service

**Files:**
- Create: `packages/application/src/memeradar_application/early_runtime.py`
- Modify: `packages/application/src/memeradar_application/early_detection.py` only for runtime timing/provenance handoff if needed
- Modify: `packages/persistence/src/memeradar_persistence/repositories.py` only for observation idempotency conflict handling if needed
- Modify: `packages/application/src/memeradar_application/read_api.py` for snapshot-derived fields where existing view supports them
- Create: `tests/unit/test_early_runtime.py`
- Create: `tests/integration/test_early_runtime_persistence.py`

**Interfaces:**
- Consumes: normalized observations/parsed protocol events, `UltraEarlyDetector`, `FastSafetyGate`, `EarlyFeatureEngine`, `OrganicMomentumProjection`, `EarlyScorer`, `EarlyDecisionEngine`, and `DecisionEngine`.
- Produces: deterministic `EarlyRuntimeResult`, append-only `early.stage_snapshot` observations, lifecycle events, alert events, and latency evidence.

- [ ] **Step 1: Write failing tests** for synthetic launch → DISCOVERED → FAST safety → EARLY_WATCH → immutable snapshot → alert event → escalation, duplicate event/stage/alert replay, out-of-order event-time handling, and critical gap/provider UNKNOWN.
- [ ] **Step 2: Run** focused runtime tests; expected: service and snapshot serializer are missing.
- [ ] **Step 3: Implement** an application service that receives normalized observations and uses deterministic source identities for candidate/stage snapshot idempotency. Serialize all required fields into existing observations with provenance/config/git revision.
- [ ] **Step 4: Add** an append-only snapshot reader/projection using existing observation queries; do not add a migration unless the test proves observation persistence insufficient.
- [ ] **Step 5: Run** unit/integration runtime persistence tests and existing event-processing tests.

### Task 6: Worker composition, restart/recovery, and source matrix

**Files:**
- Modify: `apps/worker/src/memeradar_worker/main.py` to compose the application runtime only
- Modify: `packages/providers/src/memeradar_providers/composition.py` only to expose existing stream seams
- Create: `tests/unit/test_early_worker_pipeline.py`
- Modify: `tests/contract/test_protocol_registry.py`
- Create: `docs/EARLY_ALPHA_SOURCE_MATRIX.md`

**Interfaces:**
- Consumes: existing provider bundle, protocol stream fallback, checkpoints, stream integrity, and `EarlyRuntimeService`.
- Produces: optional live-shadow worker loop that fails closed when no stream is configured and resumes durable cursor/checkpoint without duplicates.

- [ ] **Step 1: Write failing tests** for worker composition with an injected async stream, restart cursor, gap state, provider-unavailable UNKNOWN, and no business logic in `main.py`.
- [ ] **Step 2: Run** focused worker/registry tests; expected: early runtime worker path is absent.
- [ ] **Step 3: Implement** an application-facing worker adapter and minimal `main.py` composition. Keep live stream activation gated by configured provider capability; do not invent protocol IDs.
- [ ] **Step 4: Generate** source matrix for Pump.fun, PumpSwap, Raydium, and Meteora from the actual registry statuses, decoder, normalizer, fixture, contract test, worker connection, and live verification state.
- [ ] **Step 5: Run** stream integrity, protocol registry, worker, and checkpoint tests.

### Task 7: Stage outcomes, missed/false analyzers, benchmark, and report

**Files:**
- Modify: `packages/application/src/memeradar_application/early_replay.py`
- Modify: `packages/application/src/memeradar_application/early_benchmark.py`
- Create: `packages/application/src/memeradar_application/early_failure_analysis.py`
- Create: `scripts/early_alpha_report.py`
- Create: `tests/unit/test_early_failure_analysis.py`
- Create: `tests/unit/test_early_benchmark.py` additions
- Create: `tests/contract/test_future_label_isolation.py`

**Interfaces:**
- Consumes: immutable snapshot payloads/transitions, provider latency/gaps, future-only records, and exact-mint benchmark observations.
- Produces: stage/horizon executable labels, `MissedWinnerAnalyzer`, `FalsePositiveAnalyzer`, DexScreener benchmark records, and an UNKNOWN-safe report in `artifacts/research/early-alpha/`.

- [ ] **Step 1: Write failing tests** for all stage baselines, 1h/6h/24h/72h/7d outcomes, missed reason codes, suspected-vs-attributed false positives, exact mint benchmarks, and future-label import boundaries.
- [ ] **Step 2: Run** focused tests; expected: analyzers and stage/horizon projections are missing.
- [ ] **Step 3: Extend** future-only labels without importing them into runtime packages; preserve raw/executable/UNKNOWN semantics and MFE/MAE/drawdown/failure fields.
- [ ] **Step 4: Implement** reason-coded analyzers and exact-mint benchmark; absent authoritative Trending/Top Volume timestamps remain UNKNOWN.
- [ ] **Step 5: Implement** the report script using synthetic/live evidence classes and explicit matured sample counts; do not label fixtures real alpha.
- [ ] **Step 6: Run** focused research tests and generate the report artifact.

### Task 8: Existing UI, verification, and status reconciliation

**Files:**
- Modify: `apps/api/src/memeradar_api/read.py`
- Modify: `apps/web/src/app/components/ultra-early.tsx`
- Modify: `apps/web/src/app/lib/read-api.ts`
- Modify: `tests/unit/test_early_read_projection.py`
- Modify: `apps/web/src/app/components/ultra-early.test.tsx`
- Modify: `docs/STATUS.md`
- Modify: `docs/TESTING.md` only for new commands/evidence

**Interfaces:**
- Consumes: existing `/v1/early-radar` projection and persisted early snapshot fields.
- Produces: UNKNOWN-safe early-alpha/live-launch columns, sorting, alert latency, multiple-since-discovery, and final evidence/status documentation.

- [ ] **Step 1: Write failing API/UI tests** for the required columns, sorting, unknown rendering, stage alert status, and latency.
- [ ] **Step 2: Run** focused API/UI tests; expected: fields/sorting are incomplete.
- [ ] **Step 3: Extend** the existing view and component; do not create a new frontend route or execution control.
- [ ] **Step 4: Run** focused API/UI tests, frontend lint/typecheck/test/build, and browser tests where available.
- [ ] **Step 5: Run** `make verify`, migration round-trip, provider doctors, `make early-live-doctor`, `make shadow-status`, and `scripts/early_alpha_report.py`.
- [ ] **Step 6: Reconcile** `docs/STATUS.md` with exact test counts, provider blockers, latency sample classes, live-shadow state, and remaining highest-value gaps.

## Completion gates

- [ ] Full Python suite passes with no new failures.
- [ ] Lint and type checking pass for touched areas.
- [ ] Frontend tests/build/browser checks pass where supported.
- [ ] Migration head remains valid; no migration is added without evidence it is required.
- [ ] Synthetic end-to-end organic, manipulated, incomplete-enrichment, and missed-winner paths pass.
- [ ] Protected modes are unchanged and no live execution authority exists.
- [ ] Final report distinguishes synthetic, historical real, and live-shadow evidence.

