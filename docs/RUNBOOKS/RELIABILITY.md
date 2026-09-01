# Analysis-Only Reliability Runbook

This runbook covers the Phase 11.1 reliability seam. It is intentionally
analysis-only: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`. No step signs, submits or
authorizes a transaction.

## Readiness and baseline measurement

Run the keyless checks from a checkout with the protected modes loaded:

```bash
make reliability-doctor
make reliability-benchmark RELIABILITY_ITERATIONS=1000 \
  RELIABILITY_OUTPUT=/tmp/memeradar-reliability.json
```

The doctor reports `BLOCKED_EXTERNAL` when live provider checks are not run;
that status is honest and is not a failure of the local contracts. The
benchmark reports p50/p95/p99 for:

- `chain_event_to_ingest_ms`
- `social_event_to_ingest_ms`
- `ingest_to_feature_ms`
- `feature_to_decision_ms`
- `chain_event_to_decision_ms`
- `candidate_to_alert_ms`

It also reports provider-labelled reconnect, fallback, duplicate, conflict,
malformed-drop, rate-limit and retry counters. Synthetic network-shaped
samples are labelled `synthetic_local`; they must not be used as live provider
SLO evidence. Do not add an SLO or extract Rust/Yellowstone based only on this
keyless report.

## Provider and stream outage

1. Inspect the latest reliability snapshot and the existing provider doctor.
2. Confirm reconnects, fallbacks, rate limits, malformed drops, duplicate and
   conflict counters by provider.
3. Inspect stream cursor/gap state. An unresolved gap remains explicit and
   durable; it must not be advanced as contiguous or treated as safe evidence.
4. Allow the bounded reconnect/backfill policy to retry. Do not add an
   unbounded retry loop or silently discard the saturated queue.
5. If live access is unavailable, record `BLOCKED_EXTERNAL` and continue using
   fixtures/replay. Never report a provider PASS without provider evidence.

## Queue and outbox pressure

1. Check `queue_saturations`, `queue_depth`, `outbox_backlog`,
   `outbox_retries` and `outbox_dead_letters`.
2. Preserve the durable outbox and lease state. A worker may be restarted;
   leased messages are reclaimed by the existing expiry policy.
3. Reduce intake or increase downstream capacity only through a reviewed,
   bounded configuration change. Never drop events silently.
4. Inspect dead-letter error classes without attempting to recover raw
   exception text or provider payloads.

## Database restart and recovery

Restart the database only through the deployment operator's normal local or
managed-service procedure. After it is reachable:

```bash
make migrate
MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_DATABASE_URL" make integration-test
```

Readiness must remain failed while a required database is unavailable. After
reconnect, verify that cursors/gaps, normalized observations and pending
outbox rows are still present and that replay/dedupe does not create a second
business event.

## Retention, partition and index review

The current schema uses append-oriented tables and event-time indexes. The
current migration head is `0006_paper_execution`; the 11.1 review found no physical table partitions and no automatic destructive retention job. Important
indexes include observation kind/time and chain/slot, stream cursor progress,
stream gap status/range, verification time, domain-event aggregate/time and
outbox availability/status/lease expiry.

Do not delete observations, normalized chain evidence, domain events, audit
events, gaps or verification history in an incident. Before a future retention
job is approved, measure table growth, archive an immutable export, validate a
restore, and define per-table retention with legal/privacy review. Delivered
outbox rows may be compacted only after their downstream effects and audit
requirements are explicitly verified. Physical partitioning remains a later
volume-driven decision, not an assumed optimization.

## Backup and isolated restore drill

The source database is never overwritten by this procedure. Store the backup
in an access-controlled location and keep the connection strings in the
operator environment, not in scripts, logs or commits.

```bash
export BACKUP_FILE=/secure/backup/location/memeradar-$(date -u +%Y%m%dT%H%M%SZ).dump
pg_dump --format=custom --no-owner --no-acl \
  --file "$BACKUP_FILE" "$MEMERADAR_DATABASE_URL"

# Point this at a newly created, isolated restore-check database.
pg_restore --exit-on-error --no-owner --no-acl \
  --dbname "$MEMERADAR_RESTORE_DATABASE_URL" "$BACKUP_FILE"

MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_RESTORE_DATABASE_URL" \
  make integration-test
make migration-check
```

Record backup timestamp, source schema head, restore target, row-count/checksum
verification and test results in the change or incident record. Do not print
the URLs, passwords or provider credentials. A restore drill that cannot
connect is `BLOCKED_EXTERNAL`, not a fabricated PASS.

## Protected-mode closeout

Before closing an incident or reliability change, verify the report still
contains exactly:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Healthy telemetry is neutral evidence. It cannot add AlphaScore points, clear
critical UNKNOWN state or create `ENTRY_READY`.
