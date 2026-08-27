# Phase 3 Sprint 3.2 Holder Concentration and Wallet Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Produce deterministic top-holder concentration, address classification, bounded creator/holder funding graphs, clustering heuristics, and explainable evidence edges from normalized observations.

**Architecture:** The application module will consume only canonical TokenIdentity, Observation, Provenance, QualityState and ReasonCode values. It will normalize holder rows, exclude and label known pool/program/system addresses, build a bounded transfer/funding graph around creator and top-holder seeds, and calculate concentration after connected-wallet clustering. No provider SDK, HTTP client, persistence model or live execution path enters the module; Birdeye/Helius adapters remain responsible for producing normalized observations.

**Tech Stack:** Python 3.12, dataclasses, Decimal arithmetic, existing Solana identity validation, pytest/pytest-cov, Ruff, mypy, Make, Docker Compose smoke contracts.

**Spec:** docs/ROADMAP.md Sprint 3.2; docs/DATA_MODEL.md wallet intelligence and holder_snapshots; docs/SCORING_AND_RISK.md HolderQuality and clustering rules; docs/ARCHITECTURE.md warm-path wallet graph responsibilities.

## Global Constraints

- Preserve ANALYSIS_ONLY=true, PAPER_TRADING=true, MANUAL_EXECUTION=false, and AUTO_EXECUTION=false.
- Concentration and graph values are evidence, not execution permission; no score or graph result can enable live-money execution.
- Invalid, stale, conflicted or unknown holder evidence remains distinguishable and never becomes a safe complete snapshot.
- All bounded graph edges retain first/last event times, provenance-derived evidence references, confidence and stable reason codes.
- Validate canonical Solana addresses and reject malformed wallet identities; do not silently merge invalid or unknown addresses.
- Exclude known pool/program/system addresses from holder concentration while retaining their classification for auditability.
- Use Decimal values in the inclusive 0..1 range for concentration/weight ratios and explicit bounds for input rows, graph depth and edge count.
- Keep provider independence: the application module must not import Helius, Birdeye, RugCheck, HTTP, SQLAlchemy, FastAPI or frontend code.
- Do not add fund transfers, signing, execution permissions or external live calls.

---

### Task 1: Holder and graph application models

**Files:**
- Create: packages/application/src/memeradar_application/holder_graph.py
- Create: tests/unit/test_holder_graph.py

**Interfaces:**
- Produces: AddressKind, AddressClassification, HolderBalance, HolderConcentrationSnapshot, WalletGraphEdge, WalletGraphSnapshot, ClusterConcentration, and HolderGraphAnalyzer.
- Produces: HolderGraphAnalyzer.snapshot_holders(token, observations, now, config_hash, creator_address=None) -> HolderConcentrationSnapshot.
- Produces: HolderGraphAnalyzer.build_wallet_graph(token, observations, seed_addresses, now, config_hash) -> WalletGraphSnapshot.
- Produces: HolderGraphAnalyzer.cluster_concentration(snapshot, graph, now, config_hash) -> ClusterConcentration.

- [x] **Step 1: Write failing unit tests for holder normalization and address classification.** Cover top1/top5/top10 derivation from bounded percentage rows, Decimal range validation, creator/pool/program/system classification, exclusion from concentration, and preservation of excluded-address audit records.
- [x] **Step 2: Run the focused tests and confirm they fail because the module is absent.**

~~~bash
.venv/bin/pytest tests/unit/test_holder_graph.py -q
~~~

- [x] **Step 3: Implement immutable models and deterministic holder analysis.** Consume market.holder_data observations, validate the token/mint and provenance, enforce the configured freshness TTL, derive concentrations from descending effective holder percentages, use a provider top10 summary only when the normalized row set is incomplete, and return UNKNOWN/STALE/INVALID states with reason codes instead of fabricating complete values.
- [x] **Step 4: Add failing graph/cluster tests.** Cover bounded depth and maximum edges, direct funding relation classification, duplicate-edge aggregation, stable evidence references, shared-funder clustering, and concentration-after-clustering that is greater than or equal to raw top-holder concentration.
- [x] **Step 5: Implement the bounded graph and clustering algorithms.** Accept only allow-listed normalized transfer/funding observation kinds and field aliases, seed traversal from creator/top-holder addresses, omit known excluded system/program/pool nodes, aggregate duplicate edges without losing source references, use union-find for connected holder clusters, and emit explainable reason codes for every cluster/edge.
- [x] **Step 6: Run the full holder/graph unit suite plus Ruff and mypy.**

~~~bash
.venv/bin/pytest tests/unit/test_holder_graph.py -q
make lint typecheck
~~~

- [x] **Step 7: Commit the application checkpoint.**

~~~bash
git add packages/application/src/memeradar_application/holder_graph.py tests/unit/test_holder_graph.py
git commit -m "feat: add bounded holder concentration graph analysis"
git push origin main
~~~

### Task 2: Keyless fixtures and composition contracts

**Files:**
- Create: fixtures/providers/wallet_graph/README.md
- Create: fixtures/providers/wallet_graph/holder_data.json
- Create: fixtures/providers/wallet_graph/transfers.json
- Create: tests/contract/test_phase3_sprint3_2.py
- Modify: tests/smoke/test_compose_contract.py

**Interfaces:**
- Consumes: the Birdeye holder observation shape, synthetic normalized transfer observations, and HolderGraphAnalyzer.
- Produces: deterministic fixture replay proving raw and clustered concentrations, bounded graph edges, canonical address exclusion, provenance/evidence references, and all-four-mode safety assertions.

- [x] **Step 1: Write failing fixture/composition contracts.** Load the redacted JSON fixtures, assert there are no credential-shaped fields, build normalized Observations with explicit provenance/timestamps, and assert the analyzer produces stable concentration/cluster/edge outputs.
- [x] **Step 2: Run the focused contract and smoke tests to confirm the new contract fails before fixture wiring exists.**
- [x] **Step 3: Add deterministic redacted fixtures and a composition contract.** Include at least three holder wallets, one shared funder, one known system/program address, one creator, repeated transfer evidence and one out-of-depth edge; assert repeated evidence is aggregated and the out-of-depth edge is excluded.
- [x] **Step 4: Extend the Compose smoke contract.** Assert HolderGraphAnalyzer imports, the holder-graph fixture path, and all protected operating modes remain unchanged.
- [x] **Step 5: Run the fixture/contract/smoke suites and Compose config.**

~~~bash
.venv/bin/pytest tests/contract/test_phase3_sprint3_2.py tests/smoke/test_compose_contract.py -q
docker compose -f infra/compose/docker-compose.yml config --quiet
~~~

- [x] **Step 6: Commit the fixture and contract checkpoint.**

~~~bash
git add fixtures/providers/wallet_graph tests/contract/test_phase3_sprint3_2.py tests/smoke/test_compose_contract.py
git commit -m "test: add holder graph replay contracts"
git push origin main
~~~

### Task 3: Sprint 3.2 documentation and handoff

**Files:**
- Modify: docs/DATA_MODEL.md
- Modify: docs/SCORING_AND_RISK.md
- Modify: docs/PROVIDERS.md
- Modify: docs/ROADMAP.md
- Modify: docs/STATUS.md
- Modify: docs/superpowers/plans/2026-08-27-phase-3-sprint-3-2-holder-graph.md

- [x] **Step 1: Document the normalized holder/graph contracts.** Record nullable concentration semantics, exclusion/classification policy, graph bounds, cluster interpretation, evidence references, freshness behavior and lack of execution authority.
- [x] **Step 2: Run the Sprint 3.2 quality gate.**

~~~bash
make verify
make doctor
docker compose -f infra/compose/docker-compose.yml config --quiet
~~~

Record exact test, type, coverage, safety-mode and Compose results.
- [x] **Step 3: Mark Sprint 3.2 complete only after the keyless gate passes.** Update docs/STATUS.md with completed work, exact verification results, provider acceptance, blockers, safety modes, Git checkpoint/sync state, and the exact Sprint 3.3 task.
- [x] **Step 4: Commit and push the synchronized Sprint 3.2 documentation checkpoint.**

~~~bash
git add docs/DATA_MODEL.md docs/SCORING_AND_RISK.md docs/PROVIDERS.md docs/ROADMAP.md docs/STATUS.md docs/superpowers/plans/2026-08-27-phase-3-sprint-3-2-holder-graph.md
git commit -m "docs: complete Sprint 3.2 holder graph checkpoint"
git push origin main
~~~
