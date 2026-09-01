# Phase 11 / Sprint 11.2 — Observability and Operations Plan

## Task 1 — Contract-first tests

- [x] Add application tests for provider normalization, policy validation,
  state precedence, quota thresholds, SLO evidence requirements and alert
  deduplication.
- [x] Add API contract tests for the bounded GET-only operations route and
  protected modes.
- [x] Add frontend parser/component tests for valid, empty, unavailable and
  unknown operations data.

## Task 2 — Provider-independent projection

- [x] Implement versioned `ProviderSloPolicy`, operational records and a
  deterministic `OperationsProjector` over `ReliabilitySnapshot`.
- [x] Preserve explicit `UNKNOWN`, `UNVERIFIED`, `DEGRADED` and `DOWN` states;
  make operational health neutral to AlphaScore and execution authority.
- [x] Add an in-memory async query adapter for local/keyless use.

## Task 3 — API/dashboard

- [x] Expose `GET /v1/operations/overview` through an injected application
  port with role-read protection matching existing read routes.
- [x] Add a server-rendered `/operations` dashboard with bounded cards for
  state, SLO evidence, providers, quota, counters and active alerts.
- [x] Keep provider degradation and unavailable evidence visible; add no
  browser mutation, signing or submission path.

## Task 4 — Operations documentation

- [x] Document provider outage, DB pressure, queue lag, alert failure and
  quota/cost response procedures with safe escalation and no secret logging.
- [x] Reconcile roadmap/status/testing/security/architecture documentation.

## Task 5 — Quality gate and checkpoint

- [x] Run focused tests, frontend checks and the full repository gate.
- [x] Record exact evidence and external blockers in `docs/STATUS.md`.
- [x] Commit and push a coherent Sprint 11.2 checkpoint.
