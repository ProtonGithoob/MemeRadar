# Phase 6 / Sprint 6.1 — Feature Windows

**Goal:** turn the completed correlation, internal component and external-wallet
evidence seams into immutable, versioned `FeatureSnapshot` records for the
required `1m`, `5m` and `15m` windows, with deterministic replay and durable
provenance.

**Scope:** provider-independent application aggregation and the existing
`feature_snapshots` persistence table. The implementation does not add a
provider client, score/decision transition, signer, or execution path.

## Safety and replay contract

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, and `AUTO_EXECUTION=false`.
- Use the `CorrelationSnapshot.as_of` event-time boundary. Inputs dated after
  the requested evaluation time are excluded and make the derived snapshot
  `INVALID` with zero confidence; processing/delivery order cannot affect the
  result.
- Preserve `FRESH`, `STALE`, `UNKNOWN`, `CONFLICTED` and `INVALID` states.
  Missing optional family evidence remains absent/unknown rather than being
  converted into a safe value.
- External-wallet data is copied only as corroborating family evidence. It
  cannot alter internal wallet scores, risk assessments or execution modes.
- Feature snapshots retain feature version, config hash, timestamps, family
  values, source provenance and freshness. They are advisory and do not
  authorize execution.

## Tasks

### 1. Feature-window aggregation (test first)

- [x] Add unit tests for exact `1m`/`5m`/`15m` outputs, all six feature
  families, component normalization, provenance/freshness, sparse evidence,
  future input rejection and reverse-delivery determinism.
- [x] Implement `FeatureWindowPolicy` and `FeatureWindowAggregator` in the
  application layer. Consume `CorrelationSnapshot`, optional existing
  holder/wallet/social/risk snapshots and optional external-wallet
  reconciliation without importing providers or persistence.
- [x] Emit one domain `FeatureSnapshot` per required window, including family
  maps and AlphaStrategy-compatible normalized components where evidence is
  available.
- [x] Add redacted deterministic feature-window replay fixtures and a sprint
  contract/smoke test.

### 2. Feature snapshot persistence

- [x] Add lossless provenance deserialization and an aggregate-oriented
  `FeatureSnapshotRepository` around the existing `feature_snapshots` table.
- [x] Make insert/replay idempotent by snapshot ID and reject conflicting
  reuse; preserve JSON-safe values, freshness, config and feature version.
- [x] Add repository contract coverage and an opt-in Postgres round trip.
  No migration is expected because the Phase 1 table already contains the
  required columns.

### 3. Gate and reconciliation

- [ ] Run focused tests, Ruff, mypy, full `make verify`, migration parity,
  Compose config/runtime imports and the safe doctor.
- [ ] Reconcile roadmap/data-model/provider/security/status documentation with
  exact evidence and the next unfinished task, then commit and push coherent
  checkpoints.

## Acceptance criteria

- `1m`, `5m` and `15m` feature snapshots are deterministic for identical
  event-time evidence/config and cannot see future evidence.
- Market, liquidity, holder, wallet, social and momentum families retain
  bounded explainable values and quality/availability state.
- Snapshot persistence round-trips provenance, values, timestamps, version,
  config hash and quality state; duplicate identity is idempotent and
  conflicting identity fails closed.
- No feature snapshot or external corroboration result has execution authority.
