# Analysis-Only Operations Runbook

This runbook covers the Phase 11.2 operations projection and dashboard. It
does not change the protected modes:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

The dashboard is read-only. Operational health, quota, cost, latency and
alert state are evidence-quality signals only; none can add AlphaScore,
create `ENTRY_READY`, clear a kill switch, sign a wallet or submit a trade.

## Dashboard and SLO interpretation

Open `/operations` or query `GET /v1/operations/overview`. The projection
reports `HEALTHY`, `DEGRADED`, `DOWN` or `UNKNOWN` and keeps provider records,
quota/cost summaries, bounded counters and active alerts together.

`UNVERIFIED` means the versioned provider SLO policy does not have enough
non-synthetic provider-network samples. The keyless benchmark is intentionally
synthetic and cannot produce `MEASURED`. `VIOLATED` means the measured
provider-request p95 exceeds the policy target. Never relabel `UNVERIFIED` as
healthy and never claim a production SLO from fixture or local-only timing.

## Provider outage or degradation

1. Open the operations overview and the existing provider doctor.
2. Identify the affected provider/capability, freshness state, latest bounded
   latency, failure count, quota and active reason codes.
3. Confirm stream reconnect/fallback/rate-limit/malformed counters and inspect
   durable cursor/gap state where the provider supplies chain events.
4. Allow bounded retry/reconnect/fallback behavior to operate. Do not add an
   unbounded retry loop or advance past an unresolved gap.
5. Keep affected evidence `UNKNOWN`/`DEGRADED` until independently verified.
   Record live acceptance as `BLOCKED_EXTERNAL` when credentials or network
   access are unavailable.

## Database pressure or restart

1. Confirm readiness and inspect connection-pool/database errors without
   logging connection strings or credentials.
2. Preserve append-only domain events, stream state, audit records and outbox
   leases. Do not delete data to reduce pressure during an incident.
3. Use the bounded retention/index review and isolated restore procedure in
   [`RELIABILITY.md`](RELIABILITY.md). The current migration head is
   `0006_paper_execution`; no automatic destructive retention job is enabled.
4. After recovery, run migration parity and the opt-in Postgres integration
   suite. Verify dedupe, cursor/gap state and pending outbox delivery.

## Queue lag and backpressure

1. Inspect `queue_depth`, `outbox_backlog`, `queue_saturations`, retries and
   dead letters in the reliability snapshot.
2. Treat queue saturation as an active operational alert. The system must
   pause/retry, use durable handoff or degrade explicitly; it must not silently
   drop events.
3. Increase capacity or reduce bounded intake only through a reviewed config
   change. Preserve checkpoint semantics and reprocess idempotently.
4. Recompute affected evidence/decision projections if a recovered range or
   correction changes the event-time input.

## Alert delivery failure

1. Check `outbox_retries`, `outbox_dead_letters` and the notification provider
   doctor. An accepted outbox row is not proof that Telegram or another
   destination delivered it.
2. Inspect only safe error classes, dedupe keys and attempt timestamps. Never
   print bot tokens, response bodies or destination credentials.
3. Preserve the leased outbox row and use the configured bounded retry policy.
   A dead letter requires operator review and remains visible in the operations
   alert list.
4. Replaying a notification must retain the existing dedupe key; do not send
   an unbounded duplicate burst.

## Cost and quota pressure

1. Compare each provider's bounded remaining/limit quota and reported
   cost-today/budget values. Missing values are `UNKNOWN`, not zero.
2. A low or exhausted quota and a reached cost budget produce operational
   alerts and may degrade evidence collection. They are never positive market
   evidence.
3. Prefer stream/cache reuse, bounded request budgets and fixture/replay work
   while external access is constrained. Do not bypass provider limits or
   expose credentials to diagnose them.
4. Record the policy version, as-of timestamp and evidence references in the
   incident record.

## Closeout

Before closing an incident, rerun the relevant doctor and focused tests,
verify the operations projection is deterministic, and confirm the four
protected modes remain unchanged. A green dashboard is not a trade signal and
does not authorize any execution transition.
