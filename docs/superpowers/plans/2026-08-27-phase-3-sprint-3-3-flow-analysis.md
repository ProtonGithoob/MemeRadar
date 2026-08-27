# Phase 3 Sprint 3.3 Liquidity, Sellability and Organic Flow Implementation Plan

> **For agentic workers:** Use the repository’s TDD and verification workflow. Execute the steps in order and keep this plan checked in so the sprint can resume from the repository alone.

**Goal:** Produce deterministic liquidity/sellability evidence and an explainable `OrganicFlowScore` from normalized market and trade observations without provider SDKs or execution side effects.

**Architecture:** `FlowAnalyzer` lives in the provider-independent application layer. It consumes canonical `TokenIdentity`, `Observation`, `Provenance`, `QualityState` and application `QuoteSnapshot` values. Provider adapters remain responsible for translating Birdeye/Jupiter/other responses into these contracts. Missing, stale, conflicted or invalid evidence remains explicit and cannot authorize execution.

**Tech Stack:** Python 3.12, immutable dataclasses, Decimal arithmetic, existing freshness/provenance contracts, pytest/pytest-cov, Ruff, mypy, Make and Docker Compose smoke contracts.

## Global constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.
- Do not add signing, order submission, fund transfers, live provider calls or execution permission changes.
- Use only normalized application contracts; no Birdeye/Jupiter/HTTP/SQLAlchemy/FastAPI imports in the flow-analysis module.
- Bound market observations, trade rows and repeated-size state; never allow untrusted payloads to create unbounded memory or graph work.
- Keep `occurred_at`, `observed_at` and `ingested_at` distinct and retain provenance/source IDs on every derived result.
- A missing/stale/invalid critical metric is never converted into a safe value. Quote evidence is optional for analysis but has its own explicit sellability quality state.
- Decimal ratios and scores are deterministic, inclusive and range-validated. Heuristics emit stable reason codes and penalty evidence.

## Task 1: Application flow-analysis models and algorithms

**Files:**
- Create: `packages/application/src/memeradar_application/flow_analysis.py`
- Create: `tests/unit/test_flow_analysis.py`

**Interfaces:**
- Produces `LiquiditySnapshot`, `FlowMetrics`, `OrganicFlowScore`, `FlowAnalysisPolicy` and `FlowAnalyzer`.
- Produces `FlowAnalyzer.analyze_liquidity(token, observations, now, config_hash) -> LiquiditySnapshot`.
- Produces `FlowAnalyzer.analyze(token, observations, now, config_hash, quotes=()) -> OrganicFlowScore`.

- [ ] **Step 1: Write failing unit tests for liquidity and flow normalization.** Cover liquidity/depth extraction, previous-snapshot change, bounded Decimal values, summary trade fallback, provenance and missing/stale/invalid states.
- [ ] **Step 2: Run the focused tests and confirm they fail because the module is absent.**
- [ ] **Step 3: Implement immutable models and deterministic liquidity analysis.** Select the latest matching market observation, compare it with the previous same-token market snapshot, retain nullable depth/change metrics, enforce the evidence TTL and fail closed on malformed or critical missing data.
- [ ] **Step 4: Add failing organic-flow tests.** Cover unique-maker counts, transaction/maker ratio, repeated-size ratio, reciprocal/circular flow detection, rapid buy/sell round trips, optional sell quotes, high impact penalties, explainable evidence and score bounds.
- [ ] **Step 5: Implement bounded flow heuristics and scoring.** Accept allow-listed normalized trade/market kinds and field aliases, cap rows and size groups, calculate deterministic penalties/reason codes, keep quote freshness separate, and return an advisory `OrganicFlowScore` that has no execution authority.
- [ ] **Step 6: Run the full flow-analysis unit suite plus Ruff and mypy.**

```bash
./.venv/bin/pytest tests/unit/test_flow_analysis.py -q
make lint typecheck
```

- [ ] **Step 7: Commit the application checkpoint.**

```bash
git add packages/application/src/memeradar_application/flow_analysis.py tests/unit/test_flow_analysis.py
git commit -m "feat: add liquidity and organic flow analysis"
git push origin main
```

## Task 2: Keyless fixtures and composition contracts

**Files:**
- Create: `fixtures/providers/flow_analysis/README.md`
- Create: `fixtures/providers/flow_analysis/market_safe.json`
- Create: `fixtures/providers/flow_analysis/market_suspicious.json`
- Create: `fixtures/providers/flow_analysis/trades_safe.json`
- Create: `fixtures/providers/flow_analysis/trades_suspicious.json`
- Create: `fixtures/providers/flow_analysis/quotes.json`
- Create: `tests/contract/test_phase3_sprint3_3.py`
- Modify: `tests/smoke/test_compose_contract.py`

- [ ] **Step 1: Write failing fixture/composition contracts.** Load redacted normalized fixtures, reject credential-shaped fields, build explicit observations/quotes and assert safe/suspicious classifications are deterministic.
- [ ] **Step 2: Run the focused contract and smoke tests before fixture wiring.**
- [ ] **Step 3: Add synthetic fixtures and replay contracts.** Include two market snapshots for liquidity change, safe and suspicious maker/trade sets, repeated sizes, a reciprocal/circular pattern, a rapid round trip, optional sell quote impact and explicit source IDs/timestamps.
- [ ] **Step 4: Extend Compose smoke coverage.** Assert the flow-analysis seam and fixture paths are present while all four protected modes remain unchanged.
- [ ] **Step 5: Run fixture/contract/smoke tests, Compose config and secret scan.**

```bash
./.venv/bin/pytest tests/contract/test_phase3_sprint3_3.py tests/smoke/test_compose_contract.py -q
docker compose -f infra/compose/docker-compose.yml config --quiet
./.venv/bin/python scripts/secret_scan.py
```

- [ ] **Step 6: Commit and push the fixture/contract checkpoint.**

```bash
git add fixtures/providers/flow_analysis tests/contract/test_phase3_sprint3_3.py tests/smoke/test_compose_contract.py
git commit -m "test: add organic flow replay contracts"
git push origin main
```

## Task 3: Documentation and Sprint 3.3 gate

**Files:**
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

- [ ] **Step 1: Document normalized liquidity, quote and trade contracts.** Record nullable depth/change/sellability semantics, bounded heuristics, score penalties, freshness and evidence behavior, and advisory/no-execution authority.
- [ ] **Step 2: Run the Sprint 3.3 quality gate.**

```bash
make verify
make doctor
docker compose -f infra/compose/docker-compose.yml config --quiet
```

Record exact test, type, coverage, safety-mode and Compose results.
- [ ] **Step 3: Mark Sprint 3.3 complete only after the keyless gate passes.** Record provider acceptance, blockers, current safety modes, Git sync state and the exact next task in `docs/STATUS.md`.
- [ ] **Step 4: Commit and push the synchronized Sprint 3.3 documentation checkpoint.**

```bash
git add docs/DATA_MODEL.md docs/SCORING_AND_RISK.md docs/PROVIDERS.md docs/ROADMAP.md docs/STATUS.md docs/superpowers/plans/2026-08-27-phase-3-sprint-3-3-flow-analysis.md
git commit -m "docs: complete Sprint 3.3 flow analysis checkpoint"
git push origin main
```
