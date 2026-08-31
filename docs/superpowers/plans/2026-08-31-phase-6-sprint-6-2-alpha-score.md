# Phase 6 / Sprint 6.2 — AlphaScore v1

**Goal:** wire the completed provider-independent `AlphaScoreV1Strategy`
arithmetic seam to a deterministic recomputation service and durable score
snapshot repository without duplicating the strategy implementation or
creating decision/execution authority.

**Scope:** application orchestration over immutable `FeatureSnapshot` and
`RiskAssessment` inputs, plus aggregate persistence for the existing
`score_snapshots` and `risk_assessments` tables. Sprint 6.3 remains responsible
for candidate state transitions, hysteresis and alert decisions.

## Safety and replay contract

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, and `AUTO_EXECUTION=false`.
- Recompute only at or after both input event-time boundaries. The strategy's
  freshness and no-lookahead checks remain authoritative.
- Preserve configurable, versioned component weights, bounded penalties,
  hard-risk disposition and confidence/reason-code explanations.
- Use deterministic score identity derived from candidate, feature/risk IDs,
  strategy identity, event-time evaluation and config hash so replay can be
  persisted idempotently.
- Keep application orchestration provider/persistence SDK free. Persistence
  adapters implement application-facing async repository protocols.
- A score snapshot is advisory; hard risk remains in the risk assessment and
  no score result can authorize `ENTRY_READY`, signing or submission.

## Tasks

### 1. Recompute and persistence contracts (test first)

- [ ] Add unit tests for stable score identity, configurable strategy policy,
  penalties, hard-risk reason preservation, no-lookahead and repository-backed
  recomputation.
- [ ] Add risk/score row mappings and aggregate repositories with JSON-safe
  values, reason codes, version/config identity and conflicting-replay failure.
- [ ] Add `AlphaScoreRecomputer`/`ScoreRecomputationService` with application
  repository protocols and idempotent score persistence.

### 2. Golden replay and integration

- [ ] Add a redacted AlphaScore fixture and contract tests for correlated,
  sparse/unknown, penalty-clamp and blocked-risk scenarios.
- [ ] Extend the opt-in Postgres round trip through risk, score and feature
  repositories.
- [ ] Add Compose/provider-independence and protected-mode smoke coverage.

### 3. Gate and reconciliation

- [ ] Run focused tests, Ruff, mypy, full `make verify`, migration parity,
  Compose config/runtime imports and the safe doctor.
- [ ] Reconcile roadmap/data-model/architecture/provider/scoring/security/
  testing/status documentation, commit and push coherent checkpoints.

## Acceptance criteria

- Identical feature/risk event-time inputs, strategy identity and config produce
  identical score output and score-snapshot identity independent of delivery
  order.
- The score output contains bounded score, confidence, seven components,
  penalties, reason codes and explicit model/strategy/config identity.
- Hard blocks, UNKNOWN and stale evidence remain visible and fail closed; no
  strategy or score result has execution authority.
- Risk and score persistence round-trip normalized data and accept equivalent
  replay while rejecting conflicting identity reuse.
