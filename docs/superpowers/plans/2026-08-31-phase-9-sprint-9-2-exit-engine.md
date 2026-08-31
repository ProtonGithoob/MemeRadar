# Phase 9 Sprint 9.2 Exit Engine Implementation Plan

**Goal:** implement deterministic, explainable paper exit evaluation without
granting execution or signing authority.

**Design:** `docs/superpowers/specs/2026-08-31-phase-9-sprint-9-2-exit-engine-design.md`

## Global constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Keep the exit engine provider/persistence/signing/HTTP independent.
- Use `Decimal`, UTC event time, explicit freshness/quality and bounded evidence.
- External wallet/provider alerts corroborate a core signal and cannot trigger
  an exit alone.
- Partial-exit level state is supplied by the caller and persisted/replayed;
  the engine keeps no hidden mutable strategy state.
- An exit evaluation recommends; the existing paper ledger remains the only
  portfolio/position mutation path.

### Task 1: Freeze contracts with red tests

- [x] Add domain/application tests for fixed SL/TP, trailing/break-even,
  distribution, liquidity/flow/score/time and partial ladder behavior.
- [x] Add missing/stale/invalid, external-only, event-time and provider-boundary
  safety contracts.
- [x] Run the focused red suite and record the failure reason.

### Task 2: Implement evidence, policy and independent exit score

- [x] Add immutable `ExitEvidenceSnapshot`, `ExitRulePolicy`, take-profit level,
  `ExitRiskScore` and `ExitEvaluation` contracts.
- [x] Validate bounds, UTC timestamps, quality states, provenance, reason codes,
  evidence references, policy version and config hash.
- [x] Run focused unit/contract tests.

### Task 3: Implement deterministic rule evaluation

- [x] Implement stable rule ordering and strongest-action selection.
- [x] Implement fixed protective/profit rules, high-water/trailing and
  break-even rules using explicit supplied context.
- [x] Implement wallet/creator/holder, micro/macro flow, liquidity/quote,
  score-degradation and time-stop correlation.
- [x] Ensure external-only evidence remains non-triggering and UNKNOWN remains
  explicit/non-safe.

### Task 4: Add append-oriented timeline/replay seam

- [x] Add before/after evidence references and an in-memory append-only
  evaluation store/port suitable for restart and deterministic replay.
- [x] Add no-lookahead event-time ordering and consumed take-profit level context.
- [x] Add explicit paper handoff contract with no mutation/signing/provider
  dependency; verify existing `PaperExecutionEngine` remains the mutation path.

### Task 5: Gate and checkpoint

- [x] Run focused Phase 9.2 tests, Ruff, mypy, full `make verify` and relevant
  Postgres/integration checks.
- [x] Reconcile ROADMAP, ARCHITECTURE, DATA_MODEL, SCORING_AND_RISK, SECURITY,
  PROVIDERS, TESTING and STATUS with exact evidence and blockers.
- [x] Mark Sprint 9.2/E9.4 keyless work complete only after the gate; commit and
  push, leaving Sprint 9.3 next.

## Resumability checkpoint

Sprint 9.2 checkpoint complete: keyless focused/full/Postgres verification has
passed, documentation is reconciled, and Sprint 9.3 is the next task. Live
market-data acceptance remains `BLOCKED_EXTERNAL`; all four protected modes
remain unchanged.
