# Phase 1 / Sprint 1.2 — Persistence

## Objective

Add the first durable storage boundary for the provider-independent domain. SQLAlchemy models, repositories and the unit of work must keep persistence concerns outside the domain package while retaining provenance, decision explainability and idempotency constraints.

## Contract decisions

- Use SQLAlchemy 2 async sessions with `asyncpg` for runtime and Postgres integration; metadata remains portable enough for fast local schema-contract tests.
- Persist the core Phase 1 entities first: tokens, pools, candidates, observations, feature/risk/score snapshots, state transitions, portfolios, positions, alerts, domain events and outbox rows. Later social/wallet tables can extend the same metadata without changing domain contracts.
- Store domain enums/reason codes/structured evidence as explicit strings and JSON values so historical values remain readable and migrations are deterministic.
- Use database uniqueness for token mints, pool addresses, provider observation identity, transition idempotency, event idempotency and outbox dedupe. Repository methods treat duplicate enqueue/save requests as idempotent reads where appropriate.
- Unit-of-work commit is explicit and owns one transaction boundary. Repositories do not commit independently, allowing a domain write and its outbox record to commit atomically.
- Migrations are checked keylessly by revision/import tests and exercised against the local Compose Postgres when available. No production credentials or live execution capability is introduced.

## Implementation sequence

1. Add pinned SQLAlchemy/Alembic/asyncpg dependencies and persistence package wiring.
2. Add failing metadata, repository and outbox contract tests.
3. Implement SQLAlchemy declarative tables and the initial Alembic migration.
4. Implement domain-to-row mapping, async repositories and explicit unit-of-work boundaries.
5. Add migration check/optional integration commands and run upgrade/downgrade/upgrade against local Postgres.
6. Run full quality gates, reconcile roadmap/status, commit and push the sprint checkpoint.

## Acceptance evidence

- Metadata tests prove required tables, uniqueness constraints and indexes exist.
- Repository integration tests persist and reload a candidate, preserve state-transition history and dedupe an outbox event.
- Migration smoke test proves `upgrade head`, `downgrade base`, then `upgrade head` on the local Postgres service when available.
- Domain package remains free of SQLAlchemy/provider imports; the four protected operating modes remain unchanged.
