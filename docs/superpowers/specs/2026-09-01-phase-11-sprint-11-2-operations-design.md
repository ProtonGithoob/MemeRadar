# Phase 11 / Sprint 11.2 — Observability and Operations Design

## Outcome

Provide one provider-independent, read-only operational projection over the
bounded Phase 11.1 reliability seam. Operators must be able to see current
provider degradation, quota pressure, measured-versus-unverified latency,
queue/outbox pressure and actionable operational alerts without treating
healthy telemetry as AlphaScore evidence.

## Boundaries

- The projection consumes normalized provider-health records and
  `ReliabilitySnapshot` values only. It does not import provider SDKs,
  persistence, FastAPI or frontend code.
- The API and dashboard are GET-only read surfaces. They expose bounded,
  validated projections and never expose raw provider payloads, credentials or
  execution controls.
- SLO targets are versioned policy inputs, not proof of production acceptance.
  Synthetic/keyless measurements remain `UNVERIFIED`; a `MEASURED` result
  requires sufficient non-synthetic runtime samples.
- Missing or stale provider evidence is `UNKNOWN`/`DEGRADED`, never healthy.
  A quota or latency violation creates an operational warning/critical alert;
  it never increases AlphaScore or creates `ENTRY_READY`.
- Operational alerts are advisory notifications. Existing append-only alert
  and outbox paths remain the delivery boundary; no direct notification or
  execution side effect is added to the projection.

## Contract

`ProviderOperationalInput` normalizes provider/capability identity, health,
freshness, latest latency, quota and failure count. `ProviderSloPolicy` pins
the policy version, freshness budget, latency target, quota floor and minimum
non-synthetic measurement sample count. `OperationsProjector` deterministically
produces:

- overall `HEALTHY`, `DEGRADED`, `DOWN` or `UNKNOWN` state;
- per-provider state and SLO status;
- bounded quota summaries;
- allow-listed reliability counters/gauges/latency summaries;
- deduplicable operational alerts for provider, stream, queue, outbox and
  recovery degradation;
- exact protected operating modes and `execution_eligible: false`.

`InMemoryOperationsQueryService` is the keyless adapter for tests and local
operation. `GET /v1/operations/overview` is the versioned API projection;
the `/operations` server-rendered page consumes it through the existing
server-side read gateway.

## Failure behavior

- No provider records or no measurement evidence yields `UNKNOWN` and
  `UNVERIFIED`, with no fabricated PASS.
- Synthetic reports cannot satisfy a production SLO.
- Any unresolved queue/outbox/recovery problem is represented as an active
  operational alert and remains visible in the response.
- Projection/telemetry errors do not mutate score, risk, decision or operating
  mode state.

## Verification

Deterministic tests cover healthy/degraded/down/unknown precedence, stale and
low-quota evidence, measured-versus-synthetic SLO status, queue/outbox/stream
alerts, stable serialization/deduplication, API GET-only boundaries,
frontend invalid/empty states, redaction and all protected modes.
