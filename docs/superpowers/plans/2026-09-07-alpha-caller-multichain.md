# Alpha Caller Multi-Chain Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add chain-neutral caller/social intelligence, historical caller verification, conduct/convergence evidence, Telegram evidence and fail-closed paper-auto research to MemeRadar.

**Architecture:** Reuse existing chain-qualified identities, generic EVM routing, wallet/social/opportunity/replay/paper engines and promotion gates. New providers normalize at adapter boundaries; all caller evidence begins measurement-only and cannot bypass hard safety/execution gates.

**Tech Stack:** Existing MemeRadar Python/FastAPI/PostgreSQL/Redis stack, existing web/Telegram surfaces, deterministic pytest/replay tooling.

**Spec:** `docs/superpowers/specs/2026-09-07-alpha-caller-multichain-design.md`

## Global Constraints

- Mandatory initial chains: `SOLANA`, `BNB`, `ROBINHOOD`; Robinhood and BNB reuse generic EVM primitives.
- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No live signing, swaps, snipers, private keys or live copy trading.
- Future outcomes never enter event-time features.
- Missing required evidence is `UNKNOWN`, never safe/zero.
- No ticker/name identity.
- External repository ideas require provenance/license review; do not copy AGPL code.
- Follow existing package/file naming discovered during implementation rather than creating duplicate engines.

---

### Task 1: Map existing seams and freeze interfaces

**Files:**
- Modify: `docs/STATUS.md`
- Modify only if necessary: `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`

**Interfaces:**
- Consumes: existing chain identity, social, wallet graph, opportunity, replay and paper-execution contracts.
- Produces: documented mapping from each new contract to the exact existing module/repository/service that will own it.

- [x] Inspect existing implementations for chain identity, normalized social observations, wallet intelligence, smart-money convergence, opportunity evidence, replay labels and paper execution.
- [x] Record reuse-vs-new decisions in `docs/STATUS.md`; explicitly reject duplicate engines.
- [x] Run `git diff --check` and commit the mapping checkpoint.

### Task 2: Canonical caller and social-call contracts

**Files:**
- Modify/create in the existing domain/model package discovered in Task 1.
- Test in the matching unit-test package.

**Interfaces:**
- Produces: `CallerIdentity`, `SocialCallObservation`, `CrossChainIdentityEvidence` with chain-qualified asset/wallet references, timestamps, confidence and provenance.

- [x] Write failing deterministic tests proving symbols cannot become canonical identity, EVM/Solana identities normalize correctly, ambiguous wallet linkage remains evidence, and published time is distinct from ingestion time.
- [x] Run focused tests and confirm failure.
- [x] Implement the smallest immutable contracts using existing project conventions.
- [x] Run focused tests, lint/typecheck relevant files, update STATUS, commit.

### Task 3: Persistence and idempotency

**Files:**
- Modify/create matching repository/ORM modules and next Alembic migration after current head `0007_multichain_identity`.
- Test repository/migration behavior.

**Interfaces:**
- Consumes: Task 2 contracts.
- Produces: idempotent storage keyed by provider/source message identity plus canonical caller/asset references.

- [x] Write failing tests for duplicate delivery, edit-state update, unresolved asset evidence, cross-chain address separation and provenance retention.
- [x] Confirm failures.
- [x] Implement schema/repository migration without weakening existing data constraints.
- [x] Run migration/repository tests and existing migration gate; update STATUS and commit.

### Task 4: Telegram and social-provider normalization

**Files:**
- Modify existing provider/social adapter package; do not create a second provider framework.
- Test adapter normalization and degraded states.

**Interfaces:**
- Produces: normalized `SocialCallObservation` streams from Telegram and configured compliant social/X provider seams.

- [x] Write failing fixtures/tests for contract-address calls, unresolved ticker-only calls, bullish/watch intent, edit/delete evidence where supplied, malformed messages, duplicate messages and provider outage.
- [x] Confirm failures.
- [x] Implement bounded parsers/adapters with parser version and provenance; no arbitrary runtime scraping dependency.
- [x] Run focused provider tests/doctors where available; classify external blockers honestly; update STATUS and commit.

### Task 5: Event-time snapshot and historical caller outcomes

**Files:**
- Reuse existing market/execution snapshot and extreme-winner outcome/replay modules.
- Add only focused caller-outcome module if no suitable extension point exists.

**Interfaces:**
- Produces: `HistoricalCallerOutcome` for 5m/15m/1h/6h/24h/7d with executable MFE/MAE and 2x..100x research labels.

- [x] Write failing no-lookahead tests where future price/liquidity mutations cannot alter call-time features.
- [x] Add thin-liquidity wick fixture that must not count as executable multiple.
- [x] Implement caller outcome projection by composing existing canonical replay/outcome logic.
- [x] Run focused replay/no-lookahead tests, update STATUS and commit.

### Task 6: Caller performance research profile

**Files:**
- Extend existing research/scoring package.
- Tests: caller profile research tests.

**Interfaces:**
- Produces: `CallerPerformanceProfile` with sample adequacy, early-entry quality, executable win cohorts, MFE/MAE, rug avoidance, consistency, specialization, smart-wallet confirmation and confidence intervals.

- [x] Write failing tests for sparse sample => `INSUFFICIENT_SAMPLES`, failed/rug calls retained, late caller penalty evidence and no future leakage.
- [x] Implement metrics without production weighting or automatic promotion.
- [x] Run focused tests, lint/typecheck, update STATUS and commit.

### Task 7: Caller-linked wallet conduct evidence

**Files:**
- Extend existing wallet graph/flow/correlation package.
- Tests: deterministic temporal-correlation fixtures.

**Interfaces:**
- Produces: `CallerMarketConductEvidence` classifications `PRE_POSITIONING_CORRELATION`, `POST_CALL_DISTRIBUTION`, `COORDINATED_CALL_CLUSTER`, `CALLER_SMART_MONEY_CONFIRMATION`, `INSUFFICIENT_EVIDENCE`.

- [x] Write failing tests for buy-before-call/sell-after-call, unrelated wallet, weak identity link, clustered callers and missing flow evidence.
- [x] Implement confidence-bounded temporal evidence; never assert misconduct or hard identity from weak linkage.
- [x] Run focused graph/flow tests, update STATUS and commit.

### Task 8: Caller discovery feedback loop

**Files:**
- Extend existing opportunity/research discovery modules and replay fixtures.

**Interfaces:**
- Consumes: matured winner and negative-control outcomes plus historical social observations.
- Produces: research watch cohorts of candidate callers evaluated out-of-sample.

- [x] Write failing tests proving earliest-call discovery includes negative controls, failures, rugs and late callers and prevents winner-only survivorship selection.
- [x] Implement bounded historical caller discovery/backfill orchestration using existing provider seams.
- [x] Run focused tests, update STATUS and commit.

### Task 9: Caller convergence fusion

**Files:**
- Extend existing smart-money/opportunity convergence module.

**Interfaces:**
- Produces: measurement-only `CallerConvergenceEvidence` with independent/cluster-adjusted callers, temporal dispersion, smart-wallet confirmation, narrative alignment and contradictory/distribution evidence.

- [x] Write failing tests showing duplicated/linked callers do not inflate convergence and caller evidence cannot override critical BLOCK/UNKNOWN safety evidence.
- [x] Implement measurement-only fusion without changing production EarlyScore weights.
- [x] Run focused tests, update STATUS and commit.

### Task 10: Multi-chain security enrichment audit/adapter

**Files:**
- Modify existing provider/security capability package and `docs/PROVIDERS.md`.

**Interfaces:**
- Produces: optional normalized `token_security` capability across supported chains; GoPlus or equivalent remains enrichment.

- [x] Audit existing RugCheck/local risk coverage against GoPlus-style token/address security fields and record license/provenance decision.
- [x] Write failing adapter contract tests for supported, unsupported, timeout and partial evidence.
- [x] Implement only missing high-value normalized fields; `UNKNOWN` on absence.
- [x] Run tests/doctors, update provider docs/STATUS and commit.

### Task 11: Telegram alpha evidence alerts

**Files:**
- Extend existing Telegram notifier/formatter and tests.

**Interfaces:**
- Consumes: caller profile/convergence, smart-money, risk, liquidity/execution and decision evidence.
- Produces: concise evidence-rich research alerts.

- [x] Write failing snapshot/contract tests for chain+address, caller quality band, convergence, earliest-call context, smart-money, security/liquidity, decision band and provenance.
- [x] Ensure no guaranteed-multiple or live-buy wording is emitted.
- [x] Implement formatter using existing Telegram delivery path.
- [x] Run notifier tests/doctor if configured, update STATUS and commit.

### Task 12: Fail-closed PAPER_AUTO gate

**Files:**
- Extend existing paper execution/control package; do not create live execution paths.

**Interfaces:**
- Produces: `PaperAutoExecutionGate` decision using existing promoted decision evidence plus caller convergence and hard execution/risk prerequisites.

- [x] Write failing tests for allowed paper candidate and blocks on critical risk, required UNKNOWN, stale quote, non-sellability, low liquidity, excessive impact, unsupported chain or protected-mode violation.
- [x] Implement paper-only gate with no signer/private-key/swap dependency.
- [x] Verify exact protected modes in tests and doctor output; update STATUS and commit.

### Task 13: Exit-policy research extensions

**Files:**
- Extend existing convex exit evaluator/candidate policy modules.

**Interfaces:**
- Produces: versioned research candidates for partial TP, trailing protection, liquidity collapse, deployer/caller-linked distribution, smart-wallet distribution and drawdown circuit breakers.

- [x] Write failing replay tests comparing candidate exits without selecting on TEST data.
- [x] Implement candidates as research policies only.
- [x] Run focused exit/replay tests, update STATUS and commit.

### Task 14: API/read model and optional UI evidence

**Files:**
- Extend existing FastAPI read routes/read models; modify frontend only after API contracts pass.

**Interfaces:**
- Produces: read-only caller profile/call/convergence projections with provenance and explicit research state.

- [ ] Write failing API contract tests for pagination/filtering, chain-qualified identity, UNKNOWN/provenance and absence of execution controls.
- [ ] Implement read models/routes following existing patterns.
- [ ] Add minimal UI evidence views only if current frontend architecture has a natural surface; no live-order controls.
- [ ] Run backend/frontend focused gates, update STATUS and commit.

### Task 15: Replay, ablation and final promotion acceptance

**Files:**
- Extend existing research fixtures/report generator and `docs/RESEARCH_GATE_REPORT.md`.

**Interfaces:**
- Produces: caller-only, smart-money-only, opportunity-only, caller+smart-money, caller+opportunity and full-fusion ablation against baseline.

- [ ] Add deterministic engineering fixtures plus historical-real/live-shadow inputs only when genuinely available; label provenance exactly.
- [ ] Write mutation tests for future-label separation and winner-only survivorship leakage.
- [ ] Run TRAIN/VALIDATION/TEST ablation, sample adequacy, false-positive cost and confidence reporting.
- [ ] If evidence is insufficient, return `INSUFFICIENT_SAMPLES` and preserve all production weights/modes.
- [ ] Run `make verify`, relevant doctors and `git diff --check`; document all external blockers.
- [ ] Update STATUS with exact next unfinished task, commit and push coherent final checkpoint.
