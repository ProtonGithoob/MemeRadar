# MemeRadar Ultra-Early Detection and Shadow Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend MemeRadar with launch-time Solana meme-token detection, deterministic ultra-early micro-features, EarlyScore v1, shadow/paper entry, forward-outcome calibration, benchmark lead-time measurement and operator visibility while keeping all live-money execution locked.

**Architecture:** Reuse the existing modular-monolith/event-driven pipeline, canonical protocol decoder, stream-integrity layer, deterministic risk gates, paper ledger, replay/backtesting stack and read-only UI/API. Add focused provider-independent ultra-early components instead of a parallel trading stack; LLM output stays outside the latency-critical path.

**Tech Stack:** Python 3.13+, asyncio, existing MemeRadar domain/application/provider/persistence packages, FastAPI/Pydantic v2, PostgreSQL/SQLAlchemy, pytest/ruff/mypy, Next.js/TypeScript, Vitest/Playwright, existing replay/backtest/telemetry infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-01-ultra-early-detection-shadow-execution-design.md`

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Real-money signing/submission is excluded. No task may add a private-key/seed handling path or enable live transaction submission.
- Existing deterministic hard risk gates always override EarlyScore.
- Provider SDK/payload types remain inside provider adapters; domain/application use normalized contracts only.
- Live, replay and backfill data must continue through the same canonical decoder/normalizer path.
- Protocol routing remains verified `(program_id, discriminator/tag)` only; unknown/unverified identities fail closed.
- Missing/stale/conflicted critical evidence is UNKNOWN/non-fresh, never safe.
- LLM/social narrative is advisory and must not block or authorize the hot path.
- No future evidence may enter feature computation before its event-time boundary.
- Synthetic latency evidence must be labelled synthetic; production SLO claims require live evidence.
- TDD for each task: failing focused tests first, minimal implementation, focused verification, then repository gates.
- Do not restart completed roadmap work. Reuse current `correlation`, `alpha_strategy`, `decision_engine`, `paper`, replay, telemetry and UI contracts where possible.

---

### Task 1: Ultra-Early Domain Models and Latency Contract

**Files:**
- Create: `packages/domain/src/memeradar_domain/early.py`
- Modify: `packages/domain/src/memeradar_domain/__init__.py`
- Modify: `packages/application/src/memeradar_application/event_processing.py`
- Test: `tests/unit/test_early_domain.py`

**Interfaces:**
- Produces immutable `EarlyCandidateTiming`, `EarlyLatencySnapshot`, `EarlyDecisionState`, and `ExternalCallBenchmark` domain values.
- Timestamps must preserve launch/occurred/observed/ingested semantics and nullable unknown launch time.
- Latency fields: `launch_to_first_observed_ms`, `first_observed_to_ingested_ms`, `ingested_to_normalized_ms`, `normalized_to_risk_complete_ms`, `normalized_to_features_complete_ms`, `features_to_score_ms`, `first_observed_to_decision_ms`, `first_observed_to_entry_ready_ms`, `entry_ready_to_shadow_quote_ms`, `entry_ready_to_shadow_fill_ms`.

- [ ] Write `tests/unit/test_early_domain.py` asserting UTC validation, non-negative durations, unknown launch-time preservation, immutable mappings/reason codes, and rejection of decision timestamps before first observation.
- [ ] Run `pytest tests/unit/test_early_domain.py -q` and confirm RED because `memeradar_domain.early` does not exist.
- [ ] Implement the minimal frozen dataclasses/enums and export them from `memeradar_domain.__init__`; use existing `ensure_utc`, bounded numeric helpers and `QualityState` conventions.
- [ ] Add event-processing timing hooks that record stage boundaries without changing provider payload contracts or authorizing execution.
- [ ] Run `pytest tests/unit/test_early_domain.py tests/unit/test_event_processing.py -q`, then `ruff check`/`mypy` for touched files.
- [ ] Commit: `feat: add ultra-early timing domain contract`.

### Task 2: Ultra-Early Candidate Detector over Existing Streams

**Files:**
- Create: `packages/application/src/memeradar_application/early_detection.py`
- Modify: `packages/providers/src/memeradar_providers/protocol_stream.py`
- Modify: `packages/providers/src/memeradar_providers/helius_stream.py`
- Modify: `packages/providers/src/memeradar_providers/birdeye_stream.py`
- Modify: `packages/providers/src/memeradar_providers/launchpad_dex.py`
- Test: `tests/unit/test_early_detection.py`
- Test: `tests/unit/test_helius_stream.py`
- Test: `tests/unit/test_birdeye_stream.py`

**Interfaces:**
- `UltraEarlyDetector.accept(event, *, observed_at, ingested_at) -> EarlyDetectionResult`.
- Primary launch authority is a verified direct-chain/protocol event when present; Birdeye/new-listing remains fallback/corroboration.
- Duplicate deliveries are idempotent; conflicting source identity or unresolved stream gaps degrade quality instead of creating multiple candidates.

- [ ] Add failing tests covering Pump.fun launch, PumpSwap migration, Raydium/Meteora pool creation, direct-chain-vs-Birdeye timestamp precedence, duplicate delivery and unverified protocol identity.
- [ ] Run focused tests and verify RED.
- [ ] Implement `UltraEarlyDetector` using current canonical identity/decoder/stream-integrity contracts; do not add a new RPC stack.
- [ ] Attach source, slot/signature, transport, parser/registry versions, timing quality and evidence references to each result.
- [ ] Verify reconnect/gap/revert paths cannot upgrade evidence quality or score potential.
- [ ] Run detector/provider stream unit tests plus existing stream-integrity tests.
- [ ] Commit: `feat: detect ultra-early launch candidates`.

### Task 3: 1s/5s/15s/30s/60s/3m/5m Micro-Feature Engine

**Files:**
- Create: `packages/application/src/memeradar_application/early_features.py`
- Modify: `packages/application/src/memeradar_application/correlation.py`
- Modify: `packages/application/src/memeradar_application/alpha_strategy.py`
- Test: `tests/unit/test_early_features.py`
- Test: `tests/unit/test_correlation.py`

**Interfaces:**
- `EarlyFeatureEngine.compute(token_id, as_of, observations) -> EarlyFeatureSnapshot`.
- Window set is exactly `1s, 5s, 15s, 30s, 60s, 3m, 5m` and is event-time bounded.
- Required metrics include buys/sec, quote/SOL inflow/sec, acceleration, unique-buyer growth, repeat-buyer ratio, buy/sell ratios, return, volume acceleration, liquidity change, bonding-curve velocity, migration state, buyer concentration and maker diversity.

- [ ] Write deterministic fixture tests with observations immediately before/at/after every window boundary; assert no-lookahead and exact Decimal math.
- [ ] Add tests where missing trade rows leave row-level metrics nullable with explicit reason codes instead of zero.
- [ ] Run focused tests and verify RED.
- [ ] Implement window slicing and metrics by reusing normalized correlation/market observations; do not infer absent wallet or liquidity evidence.
- [ ] Add adjacent-window acceleration calculations only when both source windows are valid/fresh.
- [ ] Run `pytest tests/unit/test_early_features.py tests/unit/test_correlation.py -q` and touched lint/typecheck.
- [ ] Commit: `feat: add launch micro-feature windows`.

### Task 4: Launch-Specific Bundle, Sniper and Creator Hardening

**Files:**
- Create: `packages/application/src/memeradar_application/launch_risk.py`
- Modify: `packages/application/src/memeradar_application/correlation.py`
- Modify: `packages/application/src/memeradar_application/decision_engine.py`
- Test: `tests/unit/test_launch_risk.py`

**Interfaces:**
- `LaunchRiskAnalyzer.evaluate(...) -> LaunchRiskSnapshot`.
- Outputs separate `bundle_concentration`, `first_block_concentration`, `creator_related_ratio`, `shared_funder_ratio`, `fresh_wallet_ratio`, quality/confidence, penalties, reason codes and hard-block candidates.
- Absence of labels is UNKNOWN, not a clean-launch PASS.

- [ ] Add failing tests for one operator split across bundled wallets, creator self-buying, shared-funder clusters, insufficient funding graph evidence, reverted first-block activity and clean synthetic control cases.
- [ ] Run focused tests and verify RED.
- [ ] Implement bounded heuristics using existing wallet graph/deployer/sniper evidence; timing alone must never imply common ownership.
- [ ] Integrate only versioned/config-driven penalties and hard-block evidence; preserve existing token-security/liquidity hard-gate precedence.
- [ ] Run launch-risk, holder-graph, flow, confluence and decision-engine tests.
- [ ] Commit: `feat: harden launch bundle and creator risk`.

### Task 5: EarlyScore v1 and Confidence

**Files:**
- Create: `packages/application/src/memeradar_application/early_scoring.py`
- Modify: `packages/application/src/memeradar_application/alpha_strategy.py`
- Modify: `packages/application/src/memeradar_application/config.py`
- Test: `tests/unit/test_early_scoring.py`
- Test: `tests/unit/test_alpha_strategy.py`

**Interfaces:**
- `EarlyScorePolicy(version="early-score-v1", ...)` with configuration-driven weights.
- Components: OrganicFlowAcceleration 25%, WalletQuality 20%, OnChainSafety 20%, LiquidityAndSellability 15%, LaunchMomentum 10%, SmartMoneyConfluence 5%, SocialCorroboration 5%.
- `EarlyScorer.score(snapshot, risk, confluence, social, policy) -> EarlyScoreSnapshot` with separate score/confidence and evidence references.

- [ ] Write failing tests for exact weighted calculation, penalty ordering, clamping, config hash/version, score/confidence separation, missing social evidence and hard-risk non-overridability.
- [ ] Run focused tests and verify RED.
- [ ] Implement `early-score-v1`; apply penalties only after weighted base score and preserve every reason/evidence reference.
- [ ] Add launch-age handoff metadata so normal AlphaScore can become primary after the configured early-stage horizon without rewriting AlphaScore.
- [ ] Verify score `90` with low confidence does not become equivalent to high-confidence `90`.
- [ ] Run scoring/config/alpha strategy tests and typecheck.
- [ ] Commit: `feat: add EarlyScore v1`.

### Task 6: Decision-State Integration and ENTRY_READY Safety

**Files:**
- Modify: `packages/application/src/memeradar_application/decision_engine.py`
- Modify: `packages/domain/src/memeradar_domain/lifecycle.py`
- Test: `tests/unit/test_decision_engine.py`
- Test: `tests/unit/test_early_decision.py`

**Interfaces:**
- Early states: `REJECT/LOW`, `WATCH`, `EARLY_WATCH`, `STRONG_SETUP`, `HIGH_CONFLUENCE`; `ENTRY_READY` remains a gated state, not a score band.
- `ENTRY_READY` requires score threshold, minimum confidence, fresh critical evidence, hard-risk PASS, valid sellability/quote for paper size, acceptable liquidity/impact and protected execution modes.

- [ ] Add failing state-transition tests covering threshold boundaries 39/40, 59/60, 74/75, 84/85 plus high-score hard-block and stale-evidence cases.
- [ ] Add invariant test proving `AUTO_EXECUTION=false`/`MANUAL_EXECUTION=false` even after `ENTRY_READY`.
- [ ] Implement minimal decision integration without weakening the existing candidate state machine.
- [ ] Emit explainable decision timeline events with score version, config hash, confidence, risk reasons and timing snapshot references.
- [ ] Run decision/lifecycle/property invariant tests.
- [ ] Commit: `feat: integrate ultra-early decision states`.

### Task 7: Shadow Entry Orchestration Reusing Paper Engine

**Files:**
- Create: `packages/application/src/memeradar_application/shadow_entry.py`
- Modify: `packages/application/src/memeradar_application/paper_trading.py`
- Modify: `packages/domain/src/memeradar_domain/paper.py`
- Modify: `packages/persistence/src/memeradar_persistence/paper.py`
- Test: `tests/unit/test_shadow_entry.py`
- Test: `tests/unit/test_paper_trading.py`
- Test: `tests/integration/test_paper_persistence_postgres.py`

**Interfaces:**
- `ShadowEntryService.on_entry_ready(decision, quote_port, paper_engine) -> ShadowEntryResult`.
- Must request/revalidate quote, apply conservative paper sizing/fees/slippage/price impact, record intended/quoted/filled timestamps and then enter existing paper ledger/position lifecycle.
- It must never invoke `ExecutionPort`, a signer or transaction submission.

- [ ] Write failing tests with fake quote port and a poison execution/signer stub that raises if touched; assert shadow path never touches it.
- [ ] Add stale quote, high price impact, no sellability, drift/missed-fill and duplicate ENTRY_READY tests.
- [ ] Run focused tests and verify RED.
- [ ] Implement orchestration around existing paper engine and idempotency keys.
- [ ] Persist shadow intent/quote/fill evidence using existing paper/event persistence patterns.
- [ ] Run unit plus PostgreSQL integration test when `MEMERADAR_TEST_DATABASE_URL` is available; otherwise record the existing integration skip honestly.
- [ ] Commit: `feat: add locked shadow entry orchestration`.

### Task 8: Replay, Forward Outcomes and No-Lookahead Calibration

**Files:**
- Modify: `packages/application/src/memeradar_application/backtesting.py`
- Modify: `packages/application/src/memeradar_application/calibration.py`
- Modify: `packages/application/src/memeradar_application/call_performance.py`
- Modify: `scripts/replay_dataset.py`
- Modify: `scripts/backtest_replay.py`
- Create: `tests/unit/test_early_replay.py`
- Modify: `tests/unit/test_backtesting.py`
- Modify: `tests/unit/test_calibration.py`

**Interfaces:**
- Forward labels: max return at +1m/+3m/+5m/+15m/+30m/+1h, pre-target drawdown, configurable market-cap milestone crossings (`50K`, `100K`, `250K` baseline), time-to-milestone, liquidity survival, severe dump/rug outcome and shadow-exit executability.
- Feature path receives only observations with event time <= checkpoint; labels are computed strictly afterward.

- [ ] Write failing replay test where a future 10x trade exists in dataset and prove it cannot affect the earlier EarlyScore/ENTRY_READY result.
- [ ] Add deterministic forward-label tests for milestone crossing, drawdown and missing market-cap/liquidity evidence.
- [ ] Run focused tests and verify RED.
- [ ] Extend replay/backtest artifacts with EarlyScore, timing, state, shadow-entry and forward-outcome fields while preserving manifest/version/config identity.
- [ ] Extend calibration summaries by EarlyScore bucket and launch-age segment; never auto-promote production thresholds from insufficient samples.
- [ ] Run replay/backtest/calibration tests and deterministic repeated-run equality check.
- [ ] Commit: `feat: calibrate ultra-early outcomes`.

### Task 9: External Call Lead-Time Benchmark

**Files:**
- Create: `packages/application/src/memeradar_application/early_benchmark.py`
- Modify: `packages/application/src/memeradar_application/call_performance.py`
- Test: `tests/unit/test_early_benchmark.py`

**Interfaces:**
- Accept operator/imported reference timestamps without granting them scoring authority.
- Metrics: `memeradar_first_seen_at`, `memeradar_first_watch_at`, `memeradar_entry_ready_at`, `external_call_at`, `lead_time_to_external_call_ms`.

- [ ] Write failing tests for MemeRadar-before-call, after-call, missing-call, duplicate-call and future-dated invalid reference cases.
- [ ] Run focused tests and verify RED.
- [ ] Implement measurement-only benchmark projection; the benchmark record cannot raise score/confidence or clear a risk block.
- [ ] Add serialization/replay support with provenance and source identity.
- [ ] Run benchmark/call-performance tests.
- [ ] Commit: `feat: measure external call lead time`.

### Task 10: Read API, Radar/Token UI and Telegram Projection

**Files:**
- Modify: `packages/application/src/memeradar_application/read_api.py`
- Modify: `packages/persistence/src/memeradar_persistence/read_queries.py`
- Modify: `apps/api/src/memeradar_api/read.py`
- Modify: `packages/application/src/memeradar_application/alert_pipeline.py`
- Modify: `apps/web/src/app/components/radar.tsx`
- Modify: `apps/web/src/app/components/radar.test.tsx`
- Modify: `apps/web/src/app/tokens/[tokenId]/page.tsx`
- Create: `apps/web/src/app/components/ultra-early.tsx`
- Create: `apps/web/src/app/components/ultra-early.test.tsx`
- Modify: `apps/web/e2e/operator-dashboard.spec.ts`

**Interfaces:**
- Candidate/token projection includes launch age, first-seen source/latency quality, EarlyScore/confidence, buy velocity/acceleration, unique buyers, quote/SOL inflow, liquidity/impact, creator/bundle/holder risk, smart-money confluence, shadow status and benchmark lead time.
- Browser and alerts always render `Auto execution: LOCKED`; no mutation/sign/submit control is introduced.

- [ ] Add failing application/API projection tests verifying safe bounded fields and `execution_eligible=false` semantics.
- [ ] Add failing Vitest tests for unknown/stale/blocked states and explicit `LOCKED` label.
- [ ] Implement read-model/API mapping, reusing existing secret redaction and pagination.
- [ ] Implement operator view as observed/derived/paper sections; avoid profit guarantees or unsafe green-safe semantics for UNKNOWN.
- [ ] Extend Telegram alert payload with the same explainable ultra-early fields, dedupe and rate limits; no execution commands.
- [ ] Run backend unit tests, `npm test`, typecheck and targeted Playwright.
- [ ] Commit: `feat: expose ultra-early radar intelligence`.

### Task 11: Observability and Latency Benchmarking

**Files:**
- Modify: `packages/application/src/memeradar_application/operations.py`
- Modify: `scripts/reliability_benchmark.py`
- Create: `scripts/early_detection_benchmark.py`
- Modify: `apps/web/src/app/components/operations.tsx`
- Modify: `apps/web/src/app/components/operations.test.tsx`
- Modify: `Makefile`
- Test: `tests/unit/test_early_detection_benchmark.py`

**Interfaces:**
- Metrics include candidate rate, source distribution, first-seen/decision latency percentiles, score-by-age, hard-block reasons, ENTRY_READY rate, shadow-fill rate, quote/sellability failures, milestone precision/false-positive/rug rate, external-call lead time and stream reconnect/gap/backpressure.
- Every latency summary carries `SYNTHETIC`, `LIVE_VERIFIED`, or `UNVERIFIED` evidence class.

- [ ] Add failing tests for percentile aggregation and explicit synthetic-vs-live labelling.
- [ ] Implement benchmark CLI with deterministic fixture mode and bounded JSON output; do not claim production SLO from local data.
- [ ] Add `early-detection-benchmark` Make target.
- [ ] Add read-only operations projection/dashboard fields.
- [ ] Run benchmark tests, reliability tests and frontend operations tests.
- [ ] Commit: `feat: observe ultra-early detection latency`.

### Task 12: Live Read-Only Acceptance Tooling

**Files:**
- Create: `scripts/early_live_doctor.py`
- Modify: `Makefile`
- Modify: `docs/PROVIDERS.md`
- Test: `tests/unit/test_early_live_doctor.py`

**Interfaces:**
- Doctor checks configuration presence and performs only bounded read-only stream/provider health checks when credentials/endpoints already exist.
- Result is exactly `PASS`, `FAIL`, or `BLOCKED_EXTERNAL`; secrets/raw provider payloads are never printed.

- [ ] Write failing tests for missing config => `BLOCKED_EXTERNAL`, auth error => `FAIL`, healthy read-only fixture => `PASS`, and secret redaction.
- [ ] Implement doctor using existing Helius/Birdeye/stream-integrity health seams; do not create trading/signing dependencies.
- [ ] Add `early-live-doctor` Make target.
- [ ] Document precise external evidence needed to call live detection verified.
- [ ] Run doctor unit tests and secret scan.
- [ ] Commit: `feat: add ultra-early live read-only doctor`.

### Task 13: Locked Future Auto-Execution Boundary and Final Gate

**Files:**
- Modify: `packages/application/src/memeradar_application/config.py`
- Modify: `packages/application/src/memeradar_application/control.py`
- Modify: `apps/api/src/memeradar_api/control.py`
- Modify: `tests/unit/test_control.py`
- Modify: `tests/unit/test_control_api.py`
- Modify: `docs/STATUS.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/TESTING.md`
- Modify: `README.md`

**Interfaces:**
- Prepare only the explicit future boundary `ENTRY_READY -> Execution Eligibility Gate -> Operator/Policy Unlock -> Quote Revalidation -> Unsigned Execution Plan -> Isolated Signer -> Submit -> Finality/Reconciliation` as documentation/types if missing.
- Current configuration must continue rejecting attempts to enable manual/auto execution.

- [ ] Add/retain failing-first regression tests proving config/control/API cannot turn on `MANUAL_EXECUTION` or `AUTO_EXECUTION` in this phase and no browser/API endpoint signs/submits.
- [ ] Implement only missing locked boundary types/diagnostics; do not build or enable a signer.
- [ ] Run focused control/security tests, then full `make verify`.
- [ ] Run replay/backtest/early benchmark twice and compare deterministic artifacts.
- [ ] Run `make integration-test`; record skip/blockers if the test DB is unavailable, never fabricate PASS.
- [ ] Run `make early-live-doctor`; record real result as PASS/FAIL/BLOCKED_EXTERNAL.
- [ ] Update `docs/STATUS.md` to final verdict `ULTRA_EARLY_DETECTION_READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING_AUTO_EXECUTION_LOCKED` only if all keyless acceptance is genuinely complete; otherwise record exact remaining blocker and next task.
- [ ] Confirm final safety modes: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- [ ] `git diff --check`, secret scan, clean-tree/sync verification; commit and push final coherent checkpoint.
- [ ] Commit: `docs: close ultra-early shadow trading gate`.

## Final Acceptance Checklist

- Ultra-early launch detection is deterministic and replayable.
- Required 1s through 5m feature windows pass no-lookahead tests.
- Bundle/sniper/creator risk remains fail-closed.
- EarlyScore v1 is versioned, explainable and confidence-separated.
- ENTRY_READY cannot override hard risk/freshness/sellability policy.
- Shadow order runs through paper infrastructure without signer/submission access.
- Forward outcomes and external-call lead-time are measurement-only research evidence.
- API/UI/Telegram show ultra-early evidence and `AUTO EXECUTION: LOCKED`.
- Synthetic vs live latency evidence is explicit.
- Live provider doctor reports PASS/FAIL/BLOCKED_EXTERNAL honestly.
- Full repository quality/security gates pass for feasible local work.
- GitHub is synchronized at each coherent checkpoint; `docs/STATUS.md` is sufficient for another Codex session to resume without chat context.
