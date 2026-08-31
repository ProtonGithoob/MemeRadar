# Phase 9 Sprint 9.1 Paper Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement a deterministic paper portfolio, fill and reconciliation seam before any live execution work.

**Architecture:** Add provider-neutral paper value objects to the domain, a policy/fill/ledger orchestrator to the application, and an atomic SQLAlchemy adapter behind an application protocol. Reuse the existing `QuoteSnapshot` and `Position` contracts; all paper outcomes remain append-oriented, replayable and permanently unable to sign or submit transactions.

**Tech Stack:** Python 3.12, dataclasses, `Decimal`, pytest, SQLAlchemy async, Alembic, existing Make quality gates and opt-in Postgres integration.

**Spec:** `docs/superpowers/specs/2026-08-31-phase-9-sprint-9-1-paper-execution-design.md`, `docs/MASTER_SPEC.md`, `docs/ROADMAP.md`, `docs/DATA_MODEL.md`, `docs/SCORING_AND_RISK.md`.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Do not add signing, private-key, transaction submission, wallet custody or live-money provider behavior.
- Domain/application paper modules must not import provider SDKs, FastAPI, SQLAlchemy or persistence.
- Use `Decimal` for monetary/quantity arithmetic and preserve quote provenance/freshness.
- Unknown, stale, conflicted or invalid quote/risk evidence rejects paper mutation unless the policy explicitly labels a research-only request; this sprint uses the conservative reject behavior.
- Idempotency conflicts preserve existing records and never partially apply cash, fills or positions.
- Add tests before production code for each task and run the smallest relevant test command after each change.

---

### Task 1: Freeze paper domain and application contracts

**Files:**
- Create: `tests/unit/test_paper_domain.py`
- Create: `tests/unit/test_paper_execution.py`
- Create: `tests/contract/test_phase9_sprint9_1.py`
- Modify: `packages/domain/src/memeradar_domain/operations.py`
- Create: `packages/domain/src/memeradar_domain/paper.py`
- Modify: `packages/domain/src/memeradar_domain/__init__.py`
- Create: `packages/application/src/memeradar_application/paper_execution.py`

**Interfaces:**
- Produce `PaperPortfolio`, `CashLedgerEntry`, `PaperOrder`, `PaperFill`, `PaperOrderSide`, `PaperOrderState` and fill-aware `Position` methods.
- Produce `PaperSizingPolicy`, `PaperOrderRequest`, `PaperExecutionPolicy`, `PaperFillModel`, `PaperLedgerStore`, `InMemoryPaperLedgerStore`, `PaperExecutionEngine`, `PaperExecutionResult` and `PaperReconciler` with provider-neutral types.

- [x] **Step 1: Write failing domain tests.** Cover paper-only portfolio validation, signed ledger entries, order state/idempotency validation, fill fee/slippage fields and position open/add/reduce/close arithmetic.
- [x] **Step 2: Run the domain tests and verify the failure is for missing paper contracts.**

```bash
./.venv/bin/pytest tests/unit/test_paper_domain.py -q
```

- [x] **Step 3: Write failing application/contract tests.** Cover conservative risk-budget sizing, quote freshness rejection, deterministic BUY/SELL fill arithmetic, insufficient cash/position, partial fill state, duplicate no-op, conflicting key, restart reuse, and protected-mode/provider-boundary assertions.
- [x] **Step 4: Run the application/contract tests and verify the failure is for missing application contracts.**

```bash
./.venv/bin/pytest tests/unit/test_paper_execution.py tests/contract/test_phase9_sprint9_1.py -q
```

- [x] **Step 5: Commit the red contract checkpoint.** The red contracts were retained and completed in the coherent Sprint 9.1 implementation checkpoint.

```bash
git add tests/unit/test_paper_domain.py tests/unit/test_paper_execution.py tests/contract/test_phase9_sprint9_1.py
git commit -m "test: define Sprint 9.1 paper contracts"
```

### Task 2: Implement deterministic domain records and fill-aware position lifecycle

**Files:**
- Modify: `packages/domain/src/memeradar_domain/operations.py`
- Create: `packages/domain/src/memeradar_domain/paper.py`
- Modify: `packages/domain/src/memeradar_domain/__init__.py`
- Test: `tests/unit/test_paper_domain.py`

**Interfaces:**
- `Position.apply_entry_fill(quantity, price, occurred_at, decision_ref)` updates weighted cost and opens/adds a paper position.
- `Position.apply_exit_fill(quantity, net_proceeds, occurred_at, decision_ref)` realizes net PnL, preserves partial state, and closes at zero quantity.
- All paper records validate UTC timestamps, finite `Decimal`s, positive quantities/prices, paper mode and bounded mappings/reason codes.

- [x] **Step 1: Implement the smallest domain records required by the red tests.** Keep provider/persistence imports out of the module.
- [x] **Step 2: Implement and test the two `Position` fill methods, including full-close and invalid over-sell behavior.**
- [x] **Step 3: Run the domain suite and existing domain regression tests.**

```bash
./.venv/bin/pytest tests/unit/test_paper_domain.py tests/unit/test_domain_models.py -q
```

- [x] **Step 4: Commit the domain checkpoint.** Included in the coherent Sprint 9.1 implementation checkpoint.

### Task 3: Implement policy, fill model, idempotent engine and reconciliation

**Files:**
- Modify: `packages/application/src/memeradar_application/paper_execution.py`
- Test: `tests/unit/test_paper_execution.py`, `tests/contract/test_phase9_sprint9_1.py`

**Interfaces:**
- `PaperSizingPolicy.size(input: PaperSizingInput) -> SizingResult` uses bankroll, risk budget, stop distance, confidence, liquidity and existing exposure caps.
- `PaperFillModel.simulate(...) -> PaperFill` applies configured adverse slippage and quote-currency fees deterministically.
- `PaperExecutionEngine.execute(request: PaperOrderRequest) -> PaperExecutionResult` persists an atomic result through `PaperLedgerStore`.
- `PaperReconciler.reconcile(portfolio_id, as_of) -> ReconciliationReport` returns `PASS` or explicit `CONFLICTED`/`UNKNOWN` reasons without repairing evidence.

- [x] **Step 1: Implement sizing and fill arithmetic until their tests pass.** Reject non-fresh quotes, non-positive output, invalid amounts and policy violations.
- [x] **Step 2: Implement in-memory portfolio creation and atomic result storage.** Preserve the original result for an equivalent idempotency retry and reject material key reuse.
- [x] **Step 3: Implement BUY/SELL position updates, partial fills and append-only cash ledger entries.** Never mutate prior fills or ledger rows.
- [x] **Step 4: Implement restart-safe loading and reconciliation from stored records.** Mismatches become explicit non-safe results.
- [x] **Step 5: Run focused tests and existing risk/provider/domain regressions.**

```bash
./.venv/bin/pytest tests/unit/test_paper_execution.py tests/contract/test_phase9_sprint9_1.py tests/unit/test_domain_models.py tests/unit/test_provider_contracts.py -q
```

- [x] **Step 6: Commit the application checkpoint.** Included in the coherent Sprint 9.1 implementation checkpoint.

### Task 4: Persist orders, fills and cash ledger transactionally

**Files:**
- Modify: `packages/persistence/src/memeradar_persistence/models.py`
- Create: `packages/persistence/src/memeradar_persistence/paper.py`
- Modify: `packages/persistence/src/memeradar_persistence/__init__.py`
- Create: `infra/alembic/versions/0006_paper_execution.py`
- Modify: `scripts/check_migrations.py`, `tests/unit/test_migration_contract.py`, `tests/unit/test_persistence_contract.py`
- Create: `tests/unit/test_paper_persistence_contract.py`, `tests/integration/test_paper_persistence_postgres.py`

**Interfaces:**
- Declare `OrderRow`, `FillRow`, `CashLedgerRow` with unique order idempotency, fill identity, ledger idempotency and lookup indexes.
- `SqlAlchemyPaperLedgerStore` implements the application `PaperLedgerStore` and atomically persists portfolio/order/fill/ledger/position state.

- [x] **Step 1: Add failing metadata/migration tests for the three new tables, constraints, reversible upgrade and table-count parity.**
- [x] **Step 2: Implement SQLAlchemy rows and migration `0006_paper_execution` with downgrade dropping only its own objects.**
- [x] **Step 3: Implement row/domain mapping and an atomic async store without importing SQLAlchemy into application/domain code.**
- [x] **Step 4: Run migration parity and opt-in Postgres round-trip/restart/idempotency tests.**

```bash
./.venv/bin/python scripts/check_migrations.py
MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://memeradar:memeradar_local_only@127.0.0.1:25432/memeradar .venv/bin/pytest tests/integration/test_paper_persistence_postgres.py -q
```

- [x] **Step 5: Commit the persistence checkpoint.** Included in the coherent Sprint 9.1 implementation checkpoint.

### Task 5: Add replay/doctor/docs and Sprint 9.1 gate

**Files:**
- Modify: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/SCORING_AND_RISK.md`, `docs/SECURITY.md`, `docs/TESTING.md`, `docs/PROVIDERS.md`, `docs/STATUS.md`
- Create/modify: `scripts/paper-trading-doctor.py`, `Makefile`, `.env.example`
- Modify: `tests/unit/test_paper_execution.py`, `tests/contract/test_phase9_sprint9_1.py`, `tests/unit/test_paper_persistence_contract.py`

- [x] **Step 1: Add deterministic paper replay/no-lookahead tests with policy/config identity and no signing/provider dependency.**
- [x] **Step 2: Add key-safe paper doctor output.** Missing external quote/live execution configuration remains `BLOCKED_EXTERNAL`; local paper contracts still pass and no secret values are printed.
- [x] **Step 3: Reconcile roadmap/data/security/testing/provider documentation and record exact evidence, blockers and protected modes in `docs/STATUS.md`.**
- [x] **Step 4: Run the focused Sprint 9.1 command, Ruff, mypy, full `make verify`, migration parity, Postgres integration and doctor.**
- [x] **Step 5: Commit and push the coherent Sprint 9.1 checkpoint; mark only the completed five roadmap items and leave Sprint 9.2 next.**

## Resumability checkpoint

At every task checkpoint update `docs/STATUS.md` with the active task, exact
tests/evidence, migration head, external blockers, protected modes and next
step. Never leave the paper engine dependent on chat context alone.
