# Phase 4 / Sprint 4.3 — Confluence Implementation Plan

> **Execution note:** This is an implementation plan for the current MemeRadar
> repository. Execute each task in order, keeping the application layer
> provider-independent and preserving the protected operating modes.

**Goal:** Detect explainable smart-wallet entries and exits, deduplicate wallets
that are connected by the existing holder-graph relationship evidence, emit
confluence/distribution events, and calculate a replayable token-level
smart-money component score.

**Roadmap gate:** Gate P4 requires wallet score and confluence to replay from
fixtures and explain every component. No result from this sprint authorizes
execution.

## Design decisions

- Reuse `WalletGraphSnapshot` and `WalletGraphEdge` from Sprint 3.2 as the
  application-facing clustering seam. The confluence module will not import a
  provider SDK or infer common control from timing alone.
- A wallet qualifies only when its `SmartWalletScore` is fresh, its recommended
  tier is `TIER_A` or `TIER_B`, its score/confidence meet policy thresholds, and
  its matching `WalletTrackingSnapshot` is fresh. Blocked, stale, unknown,
  conflicted, invalid, and future evidence cannot produce a fresh confluence.
- Graph edges are unioned transitively, including non-qualifying intermediary
  nodes, so two qualified wallets funded by one observed intermediary count as
  one independent cluster. A missing graph snapshot for two or more qualified
  wallets is `UNKNOWN`, not proof of independence.
- Completed FIFO round trips provide the auditable entry/exit events. Open lots
  without a per-lot timestamp are not fabricated into events; the snapshot’s
  aggregate open quantity remains outside this sprint’s event count.
- The score is deterministic and bounded: entry breadth, entry quality, and
  independent-cluster ratio are positive components; exit pressure becomes an
  explicit distribution penalty. Non-fresh evidence forces the published score
  to zero while retaining component diagnostics and reason codes.

## Tasks

### 1. Define the confluence contract and policy

- [ ] Add immutable `ConfluencePolicy` with evidence TTL, entry/exit windows,
  qualification thresholds, event/graph bounds, distribution penalty cap, and
  version.
- [ ] Add immutable `SmartMoneyEvent` and event-type values for `ENTRY`,
  `EXIT`, `CONFLUENCE`, and `DISTRIBUTION`, preserving token identity,
  occurred/observed/ingested timestamps, cluster members, provenance, evidence
  references, quality state, reason codes, and a non-authorizing execution
  predicate.
- [ ] Add immutable `TokenSmartMoneyScore` with bounded components, penalties,
  counts, emitted events, confidence, freshness, provenance, reason codes,
  configuration hash, and a non-authorizing execution predicate.
- [ ] Validate canonical addresses, matching token identities, deterministic
  ordering, duplicate evidence normalization, and all configured bounds.

### 2. Implement independent entry/exit and cluster analysis

- [ ] Add `ConfluenceAnalyzer` that groups snapshots by token, joins wallet
  scores, applies score/freshness gates, and reconstructs recent completed
  entries/exits from `WalletRoundTrip` values.
- [ ] Deduplicate equivalent snapshots/outcomes/events and reject conflicting
  duplicate score or graph inputs rather than silently merging them.
- [ ] Build deterministic union-find clusters from fresh graph edges, preserve
  intermediary nodes for transitive clustering, and include graph evidence in
  every affected event/result.
- [ ] Emit one deterministic token-level confluence event when the configured
  number of independent clusters enter inside the configured window, and one
  distribution event per independent exit cluster with quantities and evidence.
- [ ] Calculate and expose entry breadth, entry quality, independence, exit
  pressure, and the capped distribution penalty. Keep the published score at
  zero for critical non-fresh/unknown/invalid evidence.

### 3. Add tests and replay fixtures first-class

- [ ] Add unit tests for qualification gates, independent entries/exits,
  transitive cluster deduplication, confluence-window selection, distribution
  penalties, duplicate/future/stale/unknown evidence, and safe execution
  boundaries.
- [ ] Add redacted `fixtures/providers/confluence/` inputs covering two
  independent smart wallets, one correlated pair, exits/distribution, and a
  missing/stale graph case.
- [ ] Add a keyless replay contract that rebuilds scores and events twice,
  asserts all component explanations/evidence, scans fixtures for credential
  names, and verifies Compose’s four protected mode values.
- [ ] Extend the Compose smoke contract to assert the new application seam and
  fixture packaging.

### 4. Verify, document, and checkpoint

- [ ] Run focused unit/contract/smoke checks, then the full quality gate,
  provider doctor, migration/Compose checks, and bounded runtime import probes.
- [ ] Reconcile `DATA_MODEL.md`, `SCORING_AND_RISK.md`, `PROVIDERS.md`,
  `ROADMAP.md`, and `docs/STATUS.md` with exact evidence, external blockers,
  safety modes, migration state, Git sync state, and the next roadmap task.
- [ ] Commit coherent implementation, fixture/contract, and documentation
  checkpoints and push each to `origin/main` without force-pushing.

## Verification commands

```text
.venv/bin/pytest tests/unit/test_confluence.py -q
.venv/bin/pytest tests/contract/test_phase4_sprint4_3.py tests/smoke/test_compose_contract.py -q
make verify
make doctor
make provider-doctor
docker compose -f infra/compose/docker-compose.yml config --quiet
git status --short --branch
```

## Safety and external acceptance

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
  and `AUTO_EXECUTION=false` in all local and Compose checks.
- No wallet signing, transaction submission, transfer, live-money execution,
  or provider credential is needed for the keyless gate.
- Live wallet-history/graph acceptance remains `BLOCKED_EXTERNAL` unless a
  configured read-only provider endpoint and credential produce verifiable
  evidence; fixture PASS must never be reported as live-provider PASS.
