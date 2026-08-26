# Phase 1 / Sprint 1.3 — Internal Event Processing

## Objective

Add a provider-independent internal event dispatcher and a durable outbox worker contract. Processing must be at-least-once, idempotency-aware and observable, with bounded retries and an explicit dead-letter terminal state. Out-of-order events retain their event timestamps and are dispatched in deterministic event-time order within a batch.

## Contract decisions

- Keep event handlers behind an application-layer protocol. Handlers receive the existing immutable `EventEnvelope` and cannot depend on SQLAlchemy, FastAPI or provider SDKs.
- Deduplicate equivalent event keys within each dispatch batch. Reuse of a key with different event content is a hard conflict and is never silently ignored.
- Sort a batch by `occurred_at`, then `observed_at`, `ingested_at` and event ID for deterministic replay. A late event is not discarded; its original timestamps remain intact.
- Outbox rows use a short lease token and expiry so crashed workers can be retried by another worker. Delivery, retry and dead-letter updates require the current lease token.
- Retry policy is deterministic exponential backoff with a configurable attempt cap. Handler error metadata stores only a redacted exception class/reason code, never exception text or credentials.
- Dead-letter rows are terminal and remain queryable for operator/replay tooling. No external side effect or live execution is introduced.
- Event-processing telemetry is an allowlisted structured-log seam with outcome, event kind/ID, attempt and bounded latency fields.

## Implementation sequence

1. Add application event-handler, outbox-store and telemetry protocols plus dispatcher/retry/processor contract tests.
2. Extend the outbox persistence model and add a reversible migration for processing state and leases.
3. Implement Postgres claim/ack/retry/dead-letter operations and map persisted domain events back to `EventEnvelope`.
4. Implement structured event-processing telemetry and a worker polling contract without enabling live-money behavior.
5. Add duplicate, conflicting-key, out-of-order, retry, lease-expiry and dead-letter tests; run unit and Postgres integration checks.
6. Run the Phase 1 quality gate, reconcile roadmap/status, commit and push the sprint checkpoint.

## Acceptance evidence

- Dispatcher tests prove deterministic event-time ordering, equivalent duplicate no-op behavior and conflicting-key rejection.
- Processor tests prove success acknowledgement, retry backoff, lease-aware failure handling and dead-letter after the configured cap.
- Postgres integration tests prove persisted outbox rows can be claimed, recovered after lease expiry, delivered and dead-lettered without duplicate rows.
- Structured logs expose event-processing outcomes without leaking error messages or secrets.
- All four operating modes remain `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
