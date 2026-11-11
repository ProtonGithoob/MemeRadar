# Product Audit Remediation Implementation Plan

**Goal:** Repair verified product defects and expose remaining gaps against MemeRadar's evidence-first purpose.

**Architecture:** Preserve provider-independent domain contracts and reuse canonical chain identities. Keep runtime capability gaps and external acceptance separate from verified defects; do not turn research evidence into execution authority.

**Tech Stack:** Python, SQLAlchemy, pytest, Next.js.

**Spec:** `docs/audits/PRODUCT_ISSUE_GRID_2026-11-09.md`, `docs/MASTER_SPEC.md`, `docs/STATUS.md`.

## Global Constraints

- Keep analysis/paper enabled and live execution disabled; preserve existing work and data.
- Require verified program identity for protocol routing; unknown evidence is not safe.
- No synthetic data or provider absence may be represented as live success.

## Review Focus

- Same event name from a different program: reject it in both consumers.
- Missing program identity: reject it rather than infer protocol.
- Canonical Pump.fun create and create_v2 events: retain them.
- Trades: exclude them from launch cohorts.
- Existing database and provider data: do not change or delete them.

## Task 1: Program identity in launch consumers

**Files:** `apps/worker/src/memeradar_worker/forward_evidence.py`, `apps/worker/src/memeradar_worker/early_discovery.py`, `tests/unit/test_pumpfun_forward_evidence.py` and corresponding worker tests.

- [x] Add regressions for valid, foreign and absent program identities, and run them to demonstrate failure.
- [x] Use one existing Pump.fun identity and shared launch predicate for both consumers; preserve canonical event type checks.
- [x] Run focused worker tests and lint; record results in the issue grid and status.

## Task 2: Independent gaps and acceptance

- [ ] Reconcile current test/type/lint results with the grid; document exact blockers and commands.
- [ ] Before implementing social, paper or pre-identity integration, establish bounded source/portfolio/event contracts from existing specifications and prove safe failure, idempotency and replay in tests. Do not claim operational acceptance without the required isolated database and real providers.
- [ ] Run relevant repository gates and report unverified scope honestly; preserve unrelated changes and recovery data.
