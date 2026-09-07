# Real Alpha Evidence & Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the completed Alpha Caller engineering roadmap into production-grade real-data collection, live-shadow validation, release/operations evidence, and qualified read-only/paper-auto production readiness.

**Architecture:** Reuse the existing provider-independent, chain-qualified Solana/EVM architecture and canonical replay/paper/alert paths. Production rollout is staged: `PROD_READ_ONLY` first, then `PROD_PAPER_AUTO`; live-money execution is out of scope and remains protected.

**Tech Stack:** Existing MemeRadar Python/FastAPI/PostgreSQL/Redis/web/Telegram stack, Docker/Compose and current CI/test/replay tooling.

**Spec:** `docs/superpowers/specs/2026-09-07-real-alpha-production-readiness-design.md`

## Global Constraints

- Resume from the exact repository state after Alpha Caller Task 15 (`2acf261` or a later coherent descendant); do not restart completed tasks.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No signer, wallet private key, swap submission, sniper or live copy-trading path.
- Real social/provider data must be collected only through compliant configured access.
- Preserve no-lookahead, provenance, freshness and explicit `UNKNOWN` semantics.
- No production readiness claim may be inferred from synthetic-only evidence.
- Preserve unrelated WIP files and concurrent user changes.

---

### Task 1: Production gap inventory and acceptance registry

**Files:**
- Create: `docs/PRODUCTION_READINESS.md`
- Modify: `docs/STATUS.md`
- Modify as needed: `docs/PROVIDERS.md`, `docs/TESTING.md`, `docs/SECURITY.md`

**Produces:** Machine/human-readable inventory of PR-1..PR-8 gates with status `PASS|PARTIAL|BLOCKED_EXTERNAL|INSUFFICIENT_SAMPLES|NOT_STARTED` and exact evidence references.

- [x] Inspect actual code, tests, Compose/deployment files, provider doctors, migrations, CI workflows, alerting and current Alpha Caller outputs before writing conclusions.
- [x] Write the initial production-readiness matrix using current evidence only.
- [x] Record the exact external credentials/access needed without printing secret values.
- [x] Record the four pre-existing WIP files and preserve them.
- [x] Run `git diff --check`, update STATUS and commit.

### Task 2: Required-provider contract and doctor hardening

**Files:**
- Extend existing provider capability/health modules and doctor scripts.
- Modify: `docs/PROVIDERS.md`.
- Tests: existing provider/doctor suites.

**Produces:** Required production capability set with states `READY`, `DEGRADED`, `RATE_LIMITED`, `STALE`, `CONFIGURATION_MISSING`, `BLOCKED_EXTERNAL`, `UNSUPPORTED`.

- [x] Write failing tests proving application health and evidence-capability health are distinct.
- [x] Add/verify bounded timeout, retry/backoff, freshness and rate-limit semantics for historical/live social, Telegram, market quote, execution quote and chain reads.
- [x] Ensure optional providers never block boot unless explicitly configured as required for the selected production profile.
- [x] Run focused tests/doctors; document real external blockers, update STATUS and commit.

### Task 3: Historical X/social and Telegram real-evidence collectors

**Files:**
- Extend existing social/Telegram provider adapters and collector/orchestration modules.
- Add migrations/repository fields only where existing schema cannot retain required provenance/edit state.

**Produces:** Idempotent historical backfill and bounded live ingestion into existing `SocialCallObservation`/caller seams.

- [ ] Write failing tests for duplicate IDs, edited/deleted state where supplied, out-of-order messages, ticker-only unresolved calls, chain-qualified contract calls and provider retry/rate-limit behavior.
- [ ] Implement provider-neutral collectors; never make arbitrary web scraping a boot dependency.
- [ ] Persist `occurred_at`, `observed_at`, `ingested_at`, provider/source ID, parser/provider version, provenance and freshness.
- [ ] Add collector status/lag metrics and doctor output.
- [ ] Run tests/migration gates; update STATUS and commit.

### Task 4: Historical-real dataset builder

**Files:**
- Extend current case-study/replay dataset tooling instead of creating a parallel backtester.
- Create generated-artifact schema/metadata docs under existing research fixture/report locations.

**Produces:** Reproducible leakage-safe dataset with winners, ordinary outcomes, flats, severe losers, rugs, false positives, late callers and failed calls.

- [ ] Write failing tests rejecting winner-only datasets and partitions where one caller dominates TEST above the configured cap.
- [ ] Implement versioned sample-adequacy checks: target >=1000 matured calls, >=50 caller identities, >=500 matured token outcomes and >=40% negative controls; insufficient evidence remains `INSUFFICIENT_SAMPLES`.
- [ ] Preserve chain/caller/archetype/regime labels and chronological/leakage-safe partition metadata.
- [ ] Never check future target fields into event-time observations.
- [ ] Run dataset validator/replay tests; update STATUS and commit.

### Task 5: Winner-first reverse caller discovery on real evidence

**Files:**
- Extend existing caller discovery/research orchestration.

**Produces:** Earliest-caller cohorts mined from winners *and* negative controls without survivorship leakage.

- [ ] Write failing tests proving only pre-move observations are eligible and late callers/failures/rugs remain in the history.
- [ ] Implement asset-outcome -> pre-move social search -> caller backfill -> historical profile -> future out-of-sample cohort flow.
- [ ] Preserve unresolved/deleted-history uncertainty as `UNKNOWN`.
- [ ] Run focused tests and update STATUS/commit.

### Task 6: Executable event-time outcome reconstruction

**Files:**
- Extend existing execution quote, replay, paper execution and outcome-label modules.

**Produces:** Realistic call/signal outcome records with decision/quote latency, liquidity, impact, costs, executable entry/exit and MFE/MAE.

- [ ] Write failing tests preventing mark/reference price from substituting for executable price when execution evidence is missing.
- [ ] Add signal-to-decision, decision-to-quote, quote age, market-cap/token-age-at-decision, liquidity, impact, modeled fees/slippage/priority cost and partial-fill coverage semantics.
- [ ] Add Solana priority/MEV exposure evidence where measurable without fabricating absent data.
- [ ] Ensure 2x..100x labels use executable semantics.
- [ ] Run replay/paper/no-lookahead suites; update STATUS and commit.

### Task 7: Real caller leaderboard and confidence read model

**Files:**
- Extend existing caller profile API/read model and current frontend surface.

**Produces:** Read-only caller leaderboard with sample size, executable 2x/5x/10x/20x+, rug/failure rate, median call market cap, MFE/MAE, specialization and confidence state.

- [ ] Write API/UI tests for sparse callers, confidence/INSUFFICIENT_SAMPLES, pagination/filtering and no guaranteed-alpha language.
- [ ] Implement using existing caller profile data; do not create a second scoring engine.
- [ ] Display data coverage/provenance and distinguish historical-real versus synthetic evidence.
- [ ] Run backend/frontend focused gates; update STATUS and commit.

### Task 8: Live-shadow run controller and evidence durability

**Files:**
- Extend current `shadow-start`, `shadow-status`, run/provenance and scheduler tooling.

**Produces:** Durable 14-day-capable live-shadow collection with resume-safe run identity and exact readiness classification.

- [ ] Write failing tests for restart/resume, duplicate events, unresolved gaps, provider degradation and run closure.
- [ ] Ensure live-shadow uses the same canonical decoder/normalizer/decision path as replay/backfill.
- [ ] Persist config hash, git SHA, provider versions/states, run start/end and evidence coverage.
- [ ] Add matured actionable-signal count and target >=200 guardrail; otherwise `INSUFFICIENT_SAMPLES`.
- [ ] Run shadow/reliability tests; update STATUS and commit.

### Task 9: Real-time telemetry and alerting

**Files:**
- Extend current metrics/logging/health modules and operational docs.

**Produces:** Metrics for provider success/error/rate-limit/stale, ingestion lag, queue depth/age, idempotency, stream gaps, parsing, resolution rate, quote freshness, decision latency, Telegram latency/failure, paper-gate reasons, DB/Redis/API/worker health.

- [ ] Write failing telemetry tests for each critical failure state.
- [ ] Add alerts for sustained ingestion stop, stale evidence, required-provider loss, unresolved stream gap, queue growth, DB storage pressure/migration mismatch and Telegram failure.
- [ ] Keep provider availability separate from application availability.
- [ ] Document initial SLO targets without claiming PASS until measured.
- [ ] Run observability/reliability tests; update STATUS and commit.

### Task 10: Database durability, retention and restore acceptance

**Files:**
- Modify deployment/DB scripts and `docs/DATA_RETENTION.md`; create restore/runbook docs if missing.

**Produces:** Tested migration, backup and restore procedure suitable for production read-only/paper-auto operation.

- [ ] Test migration apply on a production-like database fixture/copy and document rollback/forward-fix strategy.
- [ ] Configure/document automated backups appropriate to the deployment target.
- [ ] Perform a restore drill in a disposable environment and record objective evidence.
- [ ] Validate indexes/query plans for caller/social/observation/replay volumes and isolate research jobs from live ingestion transactions.
- [ ] Verify connection pools and statement timeouts are explicit.
- [ ] Update STATUS and commit.

### Task 11: Security and secret boundary production audit

**Files:**
- Extend `docs/SECURITY.md`, security checks and deployment config.

**Produces:** Release-grade security acceptance evidence.

- [ ] Run/extend secret scans including history/artifacts/config examples; ensure no secrets in frontend bundle/logs.
- [ ] Verify operator/control endpoint auth/RBAC and request bounds/rate limits.
- [ ] Verify unsafe mode combinations fail startup.
- [ ] Review container privileges, exposed ports, CORS/origins, dependency/SBOM findings and log redaction.
- [ ] Do not print actual provider/Telegram credentials in reports.
- [ ] Run security gates; update STATUS and commit.

### Task 12: Remote CI and reproducible release gate

**Files:**
- Extend `.github/workflows/*` and release/build documentation using existing tooling.

**Produces:** Remote CI evidence tied to exact commit plus reproducible release metadata.

- [ ] Inspect existing workflows; write/update CI so canonical `make verify` or equivalent mandatory gates run on PR/push/release candidate without weakening checks.
- [ ] Persist/report git SHA, migration head, config/schema/app version and SBOM/build identity for the candidate artifact.
- [ ] Add release-candidate checklist and rollback procedure.
- [ ] Confirm an actual remote workflow run succeeds; if GitHub Actions permissions/network are external blockers, mark PR-1 `PARTIAL/BLOCKED_EXTERNAL` rather than claiming PASS.
- [ ] Update STATUS and commit/push.

### Task 13: Production-like soak, load and chaos/failure tests

**Files:**
- Add/extend existing reliability/performance scripts and `docs/TESTING.md`.

**Produces:** Measured capacity/recovery evidence, separate from alpha quality.

- [ ] Run bounded production-like soak with provider retry/refresh paths exercised.
- [ ] Test provider timeout/rate limit/recovery, Redis restart, DB connection interruption, duplicate/delayed/out-of-order events, stale quotes, stream gaps and Telegram outage/retry/dedupe.
- [ ] Benchmark expected API/ingestion load with documented headroom and resource assumptions.
- [ ] Record bottlenecks rather than tuning blindly.
- [ ] Update STATUS and commit.

### Task 14: Historical-real and live-shadow ablation/promotion rerun

**Files:**
- Extend existing research report inputs only; no new independent scorer.
- Modify: `docs/RESEARCH_GATE_REPORT.md`.

**Produces:** Baseline/caller/smart-money/opportunity/fusion out-of-sample comparison using real evidence where available.

- [ ] Run six Alpha Caller ablation families on historical-real TRAIN/VALIDATION/TEST evidence.
- [ ] Run the same version/config against matured live-shadow data.
- [ ] Report false-positive cost, precision/recall, confidence intervals, chain/caller/regime slices, executable net expectancy and drawdown.
- [ ] Require no-lookahead/survivorship mutation suites to pass.
- [ ] If evidence is sparse/uncertain/non-positive, retain `INSUFFICIENT_SAMPLES`/not promoted; never tune TEST results into production.
- [ ] Update STATUS and commit.

### Task 15: Production acceptance and staged deployment

**Files:**
- Modify: `docs/PRODUCTION_READINESS.md`, `docs/STATUS.md` and deployment/runbook docs.

**Produces:** Final PR-1..PR-8 matrix and an evidence-backed deployment classification.

- [ ] Evaluate PR-1 Engineering/release, PR-2 Provider/evidence, PR-3 Historical-real research, PR-4 Live-shadow, PR-5 Operations independently.
- [ ] Allow `PRODUCTION_READY_READ_ONLY` only when PR-1 + PR-2 + PR-5 pass.
- [ ] Allow `PRODUCTION_READY_PAPER_AUTO` only when PR-1..PR-5 and real-environment paper-auto fail-closed acceptance pass.
- [ ] Never declare generic `PRODUCTION_READY` or live-money readiness.
- [ ] `LIVE_MONEY_CANDIDATE` requires a separate future operator-approved design; do not change protected modes.
- [ ] Run final `make verify`, doctors, security, migrations, build/release checks and `git diff --check`.
- [ ] Record exact test counts, provider blockers, evidence class/sample counts, CI run, backup/restore evidence, soak evidence, git sync state and exact next task.
- [ ] Commit/push coherent final checkpoint.
