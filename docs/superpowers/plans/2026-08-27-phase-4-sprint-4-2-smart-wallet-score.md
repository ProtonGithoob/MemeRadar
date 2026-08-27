# Phase 4 Sprint 4.2 SmartWalletScore Implementation Plan

> **For agentic workers:** Use the repository's TDD and verification workflow. Execute the steps in order and keep this plan checked in so the sprint can resume from the repository alone.

**Goal:** Derive a versioned, explainable SmartWalletScore from completed Sprint 4.1 FIFO evidence using win rate, realized PnL, median return, early-entry rate, rug avoidance and manipulation penalties with rolling-window and minimum-sample/confidence safeguards.

**Architecture:** `SmartWalletScorer` lives in the provider-independent application layer. It consumes `WalletTrackingSnapshot`/`WalletRoundTrip` records and optional normalized manipulation-penalty evidence; it does not import provider SDKs, persistence models, HTTP clients or execution paths. Registry tiers remain explicit configuration and are never mutated by scoring.

**Tech Stack:** Python 3.12, immutable dataclasses, Decimal arithmetic, bounded rolling-window aggregation, pytest/pytest-cov, Ruff, mypy, Make and Docker Compose smoke contracts.

## Global constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.
- Scores are advisory evidence only. `SmartWalletScore.execution_eligible()` is always false and scoring never changes a `TrackedWalletRegistry` entry.
- Use completed FIFO round trips only for outcome metrics; no future event may enter a score as of `now`.
- Keep unknown/stale/conflicted/invalid tracking evidence distinct. Do not convert missing PnL, age, rug or manipulation evidence into safe values.
- Apply a bounded rolling window, deterministic duplicate suppression and explicit minimum sample/confidence gates. Tiny samples cannot receive a Tier-A recommendation.
- Retain score version, config hash, timestamps, provenance, evidence references, component values, penalty values and reason codes for replay/explanation.

## Task 1: Versioned score model and rolling aggregation

**Files:**
- Create: `packages/application/src/memeradar_application/wallet_scoring.py`
- Create: `tests/unit/test_wallet_scoring.py`

**Interfaces:**
- Produces `SmartWalletScoringPolicy`, `SmartWalletScore` and `SmartWalletScorer`.
- Produces `SmartWalletScorer.score(snapshots, now, config_hash, manipulation_penalties=()) -> tuple[SmartWalletScore, ...]`.

- [ ] **Step 1: Write failing unit tests for score inputs and aggregation.** Cover completed FIFO outcomes, win rate, realized PnL, median return, early entries, rug avoidance, manipulation penalties, duplicate round trips, future exclusion and rolling-window bounds.
- [ ] **Step 2: Run focused tests and confirm they fail because the module is absent.**
- [ ] **Step 3: Implement immutable score/policy models.** Validate Decimal ranges, provenance/evidence, score components, quality states, version/config hash and non-authorizing execution predicate.
- [ ] **Step 4: Add failing threshold/confidence tests.** Cover Bayesian/shrinkage confidence, minimum sample, minimum confidence, explicit blocked tiers and the prohibition on tiny-sample Tier A.
- [ ] **Step 5: Implement deterministic scoring and tier recommendation.** Aggregate only in-window completed round trips, keep incomplete metrics nullable, shrink sparse evidence toward neutral, apply bounded manipulation penalties and return a non-mutating recommended tier.
- [ ] **Step 6: Run the full scoring unit suite plus Ruff and mypy.**

```bash
./.venv/bin/pytest tests/unit/test_wallet_scoring.py -q
make lint typecheck
```

- [ ] **Step 7: Commit the application checkpoint.**

```bash
git add packages/application/src/memeradar_application/wallet_scoring.py tests/unit/test_wallet_scoring.py
git commit -m "feat: add versioned smart wallet scoring"
git push origin main
```

## Task 2: Keyless score fixtures and composition contracts

**Files:**
- Create: `fixtures/providers/wallet_scoring/README.md`
- Create: `fixtures/providers/wallet_scoring/snapshots.json`
- Create: `fixtures/providers/wallet_scoring/penalties.json`
- Create: `tests/contract/test_phase4_sprint4_2.py`
- Modify: `tests/smoke/test_compose_contract.py`

- [ ] **Step 1: Write failing fixture/composition contracts.** Load credential-free Sprint 4.1-style snapshot fixtures and assert deterministic score decomposition.
- [ ] **Step 2: Run focused contract and smoke tests before fixture wiring.**
- [ ] **Step 3: Add deterministic fixtures.** Include a sufficiently sampled high-quality wallet, a tiny-sample wallet, stale/unknown evidence and a rolling-window boundary case with optional manipulation penalties.
- [ ] **Step 4: Extend Compose smoke coverage.** Assert wallet-scoring imports and fixture paths while all four protected modes remain unchanged.
- [ ] **Step 5: Run fixture/contract/smoke tests, Compose config and secret scan.**

```bash
./.venv/bin/pytest tests/contract/test_phase4_sprint4_2.py tests/smoke/test_compose_contract.py -q
docker compose -f infra/compose/docker-compose.yml config --quiet
./.venv/bin/python scripts/secret_scan.py
```

- [ ] **Step 6: Commit and push the fixture/contract checkpoint.**

```bash
git add fixtures/providers/wallet_scoring tests/contract/test_phase4_sprint4_2.py tests/smoke/test_compose_contract.py
git commit -m "test: add smart wallet score replay contracts"
git push origin main
```

## Task 3: Documentation and Sprint 4.2 gate

**Files:**
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

- [ ] **Step 1: Document the score formula, component nullability, rolling window, shrinkage and Tier-A gates.**
- [ ] **Step 2: Run the Sprint 4.2 quality gate.**

```bash
make verify
make doctor
docker compose -f infra/compose/docker-compose.yml config --quiet
```

Record exact test, type, coverage, safety-mode and Compose results.
- [ ] **Step 3: Mark Sprint 4.2 complete only after the keyless gate passes.** Record provider acceptance, blockers, current safety modes, Git sync state and the exact next task in `docs/STATUS.md`.
- [ ] **Step 4: Commit and push the synchronized Sprint 4.2 documentation checkpoint.**

```bash
git add docs/DATA_MODEL.md docs/SCORING_AND_RISK.md docs/PROVIDERS.md docs/ROADMAP.md docs/STATUS.md docs/superpowers/plans/2026-08-27-phase-4-sprint-4-2-smart-wallet-score.md
git commit -m "docs: complete Sprint 4.2 smart wallet score checkpoint"
git push origin main
```
