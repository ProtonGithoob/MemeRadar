# Phase 9 Sprint 9.3 Position UI / Telegram Implementation Plan

**Design:** `docs/superpowers/specs/2026-08-31-phase-9-sprint-9-3-position-ui-telegram-design.md`

## Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Extend the current read gateway and alert/outbox seams; do not create
  frontend execution authority or a second position state store.
- Treat current marks as observed evidence and PnL/MFE/MAE as derived values.
- Missing, stale, invalid or conflicted marks remain explicit and non-safe.

### Task 1: Freeze position and alert contracts with red tests

- [x] Add application/domain tests for bounded position views, mark quality,
  PnL arithmetic, MFE/MAE and closed-trade explanation.
- [x] Add read API route and persistence projection contracts.
- [x] Add exit/paper Telegram projection contracts with dedupe and safety
  boundaries.

### Task 2: Implement application and persistence read projections

- [x] Add position query/view contracts to the provider-independent read port.
- [x] Project in-memory marks/evaluations and SQL positions/observations/event
  timeline with deterministic pagination and no-lookahead.
- [x] Expose typed GET-only position API routes.

### Task 3: Implement dashboard and Telegram extension

- [x] Add server-only web gateway, `/positions` page, dashboard components and
  navigation while retaining protected UI primitives.
- [x] Project non-HOLD exit risk and paper-exit events through the existing
  alert renderer/outbox boundary.
- [x] Keep live quote/Telegram acceptance explicitly `BLOCKED_EXTERNAL`.

### Task 4: Gate and checkpoint

- [x] Run focused backend/frontend tests, Ruff, mypy and full `make verify`.
- [x] Run the opt-in Postgres position projection round trip.
- [x] Reconcile ROADMAP, ARCHITECTURE, DATA_MODEL, SCORING_AND_RISK, SECURITY,
  PROVIDERS, TESTING and STATUS.
- [x] Commit and push Sprint 9.3 keyless checkpoint; leave the next feasible
  roadmap task recorded for resumption.

## Resumability checkpoint

At each task boundary update `docs/STATUS.md` with exact active work,
verification, protected modes, external blockers and next action.
