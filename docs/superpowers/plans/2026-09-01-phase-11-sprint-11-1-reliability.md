# Phase 11 / Sprint 11.1 — Reliability Implementation Plan

> Execute with focused tests and a resumable checkpoint after each coherent
> slice. Preserve the four protected operating modes throughout.

## Task 1 — Freeze reliability contracts

- [x] Add unit/contract tests for bounded histograms, percentile calculation,
  provider-labelled counters, protected modes, and deterministic benchmark
  artifacts.
- [x] Add reconnect/fallback, rate-limit, outbox saturation/retry and DB
  restart tests using injected fakes or the opt-in local Postgres.

## Task 2 — Implement the shared reliability seam

- [x] Add application-layer allow-listed reliability metric names, bounded
  histograms, snapshots and source attribution.
- [x] Preserve compatibility with the existing E8.4 `StreamTelemetry` port.

## Task 3 — Instrument existing paths

- [x] Instrument provider transport, stream consumers and outbox processing
  with classified counters and stage timers without leaking provider payloads.
- [x] Keep canonical decoding and event/outbox semantics unchanged.

## Task 4 — Benchmark and operational documentation

- [x] Add keyless reliability benchmark/doctor commands and Make targets.
- [x] Add retention/index review and isolated backup/restore runbook.

## Task 5 — Gate and handoff

- [ ] Run focused tests, the full quality gate, integration tests when the local
  database is available, and keyless benchmark/doctor checks.
- [ ] Reconcile roadmap and `docs/STATUS.md`, record exact evidence and
  blockers, commit and push. Leave Gate P11 pending until Sprints 11.2 and
  11.3 are complete.
