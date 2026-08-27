# Phase 4 Sprint 4.1 Wallet Tracking Implementation Plan

> **For agentic workers:** Use the repository’s TDD and verification workflow. Execute the steps in order and keep this plan checked in so the sprint can resume from the repository alone.

**Goal:** Create an explicit tracked-wallet registry and conservatively reconstruct watched-wallet buy/sell activity, FIFO realized PnL, token age at entry, hold duration and rug exposure from normalized observations.

**Architecture:** `WalletTrackingAnalyzer` lives in the provider-independent application layer. It consumes canonical `TokenIdentity`, `Observation`, `Provenance`, `QualityState` and explicit registry entries. Provider adapters translate chain/market payloads into normalized wallet activity or risk observations; no provider SDK, persistence model, HTTP client or execution path enters the analyzer.

**Tech Stack:** Python 3.12, immutable dataclasses, Decimal arithmetic, explicit canonical Solana validation, pytest/pytest-cov, Ruff, mypy, Make and Docker Compose smoke contracts.

## Global constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.
- Never infer a Tier-A wallet from a small sample and never promote registry tiers automatically; labels/tiers are explicit operator/configuration data.
- Validate canonical wallet/token identities and positive quantities; do not silently merge malformed or unknown activity.
- Reconstruct PnL only from known quote amounts/prices and matched FIFO lots. Unmatched sells, missing prices, stale/unknown/conflicted evidence and missing token-age/rug evidence remain explicit and fail closed.
- Keep activity provenance and `occurred_at`/`observed_at`/`ingested_at` distinct. Duplicate source deliveries are idempotent; conflicting duplicate source IDs are invalid.
- Bound registry entries, activity rows and open lots. Results are explainability evidence only and cannot authorize trades or submit transactions.

## Task 1: Wallet registry, activity normalization and reconstruction

**Files:**
- Create: `packages/application/src/memeradar_application/wallet_tracking.py`
- Create: `tests/unit/test_wallet_tracking.py`

**Interfaces:**
- Produces `WalletTier`, `TrackedWallet`, `TrackedWalletRegistry`, `WalletActivity`, `WalletRoundTrip`, `WalletTrackingSnapshot`, `WalletTrackingPolicy` and `WalletTrackingAnalyzer`.
- Produces `WalletTrackingAnalyzer.ingest_activities(token, observations, registry, now) -> tuple[WalletActivity, ...]`.
- Produces `WalletTrackingAnalyzer.reconstruct_positions(token, activities, registry, now, config_hash, token_created_at=None, rug_observations=()) -> tuple[WalletTrackingSnapshot, ...]`.

- [ ] **Step 1: Write failing unit tests for registry and activity normalization.** Cover canonical addresses, explicit labels/tiers, idempotent duplicates, unknown-wallet rejection, BUY/SELL aliases, quantities/prices, source provenance and bounds.
- [ ] **Step 2: Run the focused tests and confirm they fail because the module is absent.**
- [ ] **Step 3: Implement registry and normalized activity models.** Keep registry tier changes explicit, accept only allow-listed wallet activity kinds, preserve evidence metadata, deduplicate equivalent source IDs and return UNKNOWN/INVALID states instead of inventing values.
- [ ] **Step 4: Add failing FIFO/PnL tests.** Cover multiple buys and partial sells, realized PnL, open quantity/cost basis, hold duration, token age at entry, rug exposure, unmatched sells, missing quote values and stale/future evidence.
- [ ] **Step 5: Implement bounded conservative reconstruction.** Sort by event time, match FIFO lots, retain round-trip evidence/reason codes, calculate Decimal PnL/median holds, keep incomplete fields nullable and never promote a wallet tier.
- [ ] **Step 6: Run the full wallet-tracking unit suite plus Ruff and mypy.**

```bash
./.venv/bin/pytest tests/unit/test_wallet_tracking.py -q
make lint typecheck
```

- [ ] **Step 7: Commit the application checkpoint.**

```bash
git add packages/application/src/memeradar_application/wallet_tracking.py tests/unit/test_wallet_tracking.py
git commit -m "feat: add conservative wallet tracking"
git push origin main
```

## Task 2: Keyless fixtures and composition contracts

**Files:**
- Create: `fixtures/providers/wallet_tracking/README.md`
- Create: `fixtures/providers/wallet_tracking/registry.json`
- Create: `fixtures/providers/wallet_tracking/activities.json`
- Create: `fixtures/providers/wallet_tracking/risk.json`
- Create: `tests/contract/test_phase4_sprint4_1.py`
- Modify: `tests/smoke/test_compose_contract.py`

- [ ] **Step 1: Write failing fixture/composition contracts.** Load redacted fixtures, reject credential-shaped fields, inject explicit provenance/timestamps and assert deterministic tracked-wallet reconstruction.
- [ ] **Step 2: Run focused contract and smoke tests before fixture wiring.**
- [ ] **Step 3: Add deterministic fixtures and replay contracts.** Include two explicit watched wallets/tiers, duplicate source delivery, buys/sells with a partial FIFO close, token creation time, a rug-event observation and an unmatched sell case.
- [ ] **Step 4: Extend Compose smoke coverage.** Assert wallet-tracking imports and fixture paths while all four protected modes remain unchanged.
- [ ] **Step 5: Run fixture/contract/smoke tests, Compose config and secret scan.**

```bash
./.venv/bin/pytest tests/contract/test_phase4_sprint4_1.py tests/smoke/test_compose_contract.py -q
docker compose -f infra/compose/docker-compose.yml config --quiet
./.venv/bin/python scripts/secret_scan.py
```

- [ ] **Step 6: Commit and push the fixture/contract checkpoint.**

```bash
git add fixtures/providers/wallet_tracking tests/contract/test_phase4_sprint4_1.py tests/smoke/test_compose_contract.py
git commit -m "test: add wallet tracking replay contracts"
git push origin main
```

## Task 3: Documentation and Sprint 4.1 gate

**Files:**
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

- [ ] **Step 1: Document the normalized wallet registry/activity/PnL contracts.** Record explicit tier policy, FIFO matching, nullable evidence, token age/hold/rug semantics, bounds, freshness and lack of execution authority.
- [ ] **Step 2: Run the Sprint 4.1 quality gate.**

```bash
make verify
make doctor
docker compose -f infra/compose/docker-compose.yml config --quiet
```

Record exact test, type, coverage, safety-mode and Compose results.
- [ ] **Step 3: Mark Sprint 4.1 complete only after the keyless gate passes.** Record provider acceptance, blockers, current safety modes, Git sync state and the exact next task in `docs/STATUS.md`.
- [ ] **Step 4: Commit and push the synchronized Sprint 4.1 documentation checkpoint.**

```bash
git add docs/DATA_MODEL.md docs/SCORING_AND_RISK.md docs/PROVIDERS.md docs/ROADMAP.md docs/STATUS.md docs/superpowers/plans/2026-08-27-phase-4-sprint-4-1-wallet-tracking.md
git commit -m "docs: complete Sprint 4.1 wallet tracking checkpoint"
git push origin main
```
