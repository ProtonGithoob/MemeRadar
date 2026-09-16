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

## Synthetic reliability benchmark

Run the keyless failure matrix with an explicitly bounded load:

```bash
make reliability-benchmark RELIABILITY_ITERATIONS=1000 \
  RELIABILITY_OUTPUT=/tmp/memeradar-reliability.json
```

The report is a synthetic local failure matrix. It covers provider
timeout/rate-limit recovery, Redis restart, database interruption,
duplicate/delayed/out-of-order events, stale quotes, stream gaps and Telegram
outage/retry/dedupe, but it performs no provider, database or cache operation.
Its rate/headroom/resource values are not production soak evidence.

## Read-only stack soak

Poll an already-running production-like API/web/worker/PostgreSQL/Redis stack
with a server-side viewer token:

```bash
MEMERADAR_STACK_VIEWER_API_TOKEN="$MEMERADAR_VIEWER_API_TOKEN" \
  make production-stack-smoke STACK_API_BASE_URL=http://127.0.0.1:18000
MEMERADAR_STACK_VIEWER_API_TOKEN="$MEMERADAR_VIEWER_API_TOKEN" \
  make production-soak STACK_SOAK_ITERATIONS=100 \
  STACK_SOAK_INTERVAL_SECONDS=1 \
  STACK_CONTAINER_NAMES=compose-api-1,compose-worker-1,compose-postgres-1,compose-redis-1,compose-web-1 \
  STACK_SOAK_OUTPUT=/tmp/memeradar-production-stack-soak.json
```

This emits `production-stack-soak-v1` with the candidate Git SHA, request
counts/errors, readiness failures, HTTP latency, dependency interruption
observations, persisted real-observation delta, duplicate-event delta/rate,
container liveness/restart counts, bounded memory samples, protected modes and
an artifact digest. Supplying `STACK_CONTAINER_NAMES` enables the Docker
inspect/stats portion; without it, those fields are explicitly
`NOT_MEASURED`, not inferred. It is read-only and never starts/stops services
or writes to the database. This generic smoke/soak is intentionally looser.

For a production-read-only acceptance gate, require the measured Docker
evidence explicitly:

```bash
MEMERADAR_STACK_VIEWER_API_TOKEN="$MEMERADAR_VIEWER_API_TOKEN" \
  make production-stack-acceptance STACK_SOAK_ITERATIONS=100 \
  STACK_SOAK_INTERVAL_SECONDS=1 \
  STACK_API_BASE_URL=http://127.0.0.1:18000 \
  STACK_CONTAINER_NAMES=compose-api-1,compose-worker-1,compose-postgres-1,compose-redis-1,compose-web-1
```

Strict acceptance fails when container runtime, worker liveness, restart
counts, memory samples, database/Redis readiness, protected modes or
`execution_eligible=false` are not observed. Real observation and duplicate
metrics are either measured or labelled `UNAVAILABLE_TRUTHFUL` with a reason;
zero optional-provider observations are not treated as an error. The
synthetic reliability benchmark remains a separate `synthetic_local` report
and is never called a production soak.

`make production-dependency-drill` performs bounded independent scenarios
using the base plus production Compose override for every operation. It first
checks a healthy baseline, then stops only PostgreSQL (Redis must remain
reachable), expects readiness `503` with database degradation, recovers
PostgreSQL and expects readiness `200`, then repeats the same sequence with
only Redis stopped. A combined outage is not a substitute for these two
cases. Managed provider/DB/Redis/Telegram soak remains an external acceptance
gate.

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

Migration recovery is forward-first: stop the affected writer, preserve a
backup, inspect the applied Alembic revision and deploy a reviewed corrective
migration. Do not downgrade a shared production database as an ad-hoc repair;
an Alembic downgrade is reserved for the disposable restore target after the
backup and downgrade path have been verified. Application startup must not
silently run an irreversible migration.

## Retention, partition and index review

The current schema uses append-oriented tables and event-time indexes. The
current migration head is `0011_collection_checkpoints`; the review found
no physical table partitions and no automatic destructive retention job. Important
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
export MEMERADAR_BACKUP_SOURCE_URL="$MEMERADAR_DATABASE_URL"
# Point this at a newly created, empty, isolated restore-check database.
export MEMERADAR_BACKUP_RESTORE_URL="$MEMERADAR_RESTORE_DATABASE_URL"
make backup-restore-drill BACKUP_FILE="$BACKUP_FILE"

MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_RESTORE_DATABASE_URL" \
  make integration-test
make migration-check
```

Record backup timestamp, source schema head, restore target, row-count/checksum
verification and test results in the change or incident record. Do not print
the URLs, passwords or provider credentials. The repository drill first checks
database identity and rejects source/restore aliases that resolve to the same
database. It also rejects any restore target with existing public tables before
`pg_restore`; it never drops a database or schema to make the target fit.
Unavailable `pg_dump`/`pg_restore` binaries or an unreachable preflight are
`BLOCKED_EXTERNAL`. A rejected target, restore command error or verification
mismatch is `FAIL`, never `BLOCKED_EXTERNAL`.
The wrapper invokes `pg_dump --format=custom` and `pg_restore --exit-on-error`
only after those safety checks.

## Production connection boundary

`create_database_engine` applies bounded PostgreSQL defaults unless a caller
explicitly supplies a pool class: pool size `5`, max overflow `5`, pool
timeout `30s`, pool recycle `1800s`, asyncpg command timeout `30s`, server
statement timeout `30s` and idle-in-transaction timeout `60s`. Research jobs
must use a separate process/connection budget and must not share a long-lived
transaction with live ingestion or API work.

The repository-native `make backup-restore-drill` target runs
`scripts/backup_restore_drill.py` with source and disposable restore URLs held
only in `MEMERADAR_BACKUP_SOURCE_URL` and `MEMERADAR_BACKUP_RESTORE_URL`. It
creates a custom-format dump, restores only into the separately supplied
empty target, verifies the migration head, public table count, critical
observation count and an application read, and emits a redacted digest. The current
disposable evidence is PostgreSQL 16.14, migration head
`0011_collection_checkpoints`, 27 metadata tables / 28 public tables including
`alembic_version`. This is local disposable evidence, not a managed-production
backup SLA; retention, RPO/RTO and scheduled restore monitoring remain
deployment responsibilities.

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
