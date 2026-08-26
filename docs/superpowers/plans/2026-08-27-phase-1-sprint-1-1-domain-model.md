# Phase 1 / Sprint 1.1 — Domain Model

## Objective

Implement the provider-independent domain primitives required for replayable candidate analysis. The domain package must own identity validation, lifecycle invariants, event/reason-code contracts, evidence provenance/freshness and explainable decision/operation snapshots without importing framework, persistence or provider code.

## Contract decisions

- Solana addresses are validated as canonical base58 public keys decoding to 32 bytes; malformed identities fail at construction time.
- Domain timestamps are timezone-aware and normalized to UTC. Event and observation envelopes preserve occurred, observed and ingested timestamps in order.
- Candidate transitions use an explicit allow-list matching `MASTER_SPEC.md`. Each transition requires reason codes, correlation context and an idempotency key (or a deterministic fallback key); an exact duplicate returns the original transition without mutating state.
- Evidence quality distinguishes `FRESH`, `STALE`, `UNKNOWN`, `CONFLICTED` and `INVALID`. Missing or non-fresh critical evidence is never treated as safe for execution eligibility.
- Snapshot models retain version/config identifiers, timestamps, confidence/completeness, penalties, reason codes and evidence/provenance references so decisions can be explained and replayed.
- Models use standard-library dataclasses/enums and immutable value objects where practical. No live provider, persistence or execution side effect is introduced; `LIVE` is representable as a future persisted position mode only.

## Implementation sequence

1. Add unit tests for address/value validation, valid and invalid lifecycle transitions, duplicate/conflicting idempotency, timestamp/freshness behavior and snapshot invariants.
2. Implement identities and lifecycle models.
3. Implement event/reason-code and provenance/freshness models.
4. Implement feature, risk, score, alert and position models.
5. Run focused tests, full backend quality gates and a package import/architecture check.
6. Reconcile roadmap/status, commit and push a coherent Sprint 1.1 checkpoint.

## Acceptance evidence

- Domain unit tests cover valid/invalid state transitions and idempotency.
- Malformed identity, invalid score/confidence, inconsistent timestamps and stale/unknown risk evidence are rejected or fail closed.
- `ruff`, `mypy`, coverage and `make verify` pass without changing the four protected operating modes.
- `docs/ROADMAP.md` and `docs/STATUS.md` record exact results, external-provider state, safety modes, Git synchronization and the next task.
