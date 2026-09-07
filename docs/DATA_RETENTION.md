# Data retention and partition policy

Version: `data-handling-v1`
Reviewed: 2026-09-01

This policy describes the current analysis-only storage posture. It is an
operating contract, not legal advice. Deployment-specific retention periods
require privacy, legal and provider-terms review before activation.

## Principles

- Preserve normalized, provenance-bearing evidence long enough to explain and
  replay decisions, subject to an approved deployment retention schedule.
- Minimize collection: retain the normalized fields and hashes needed for
  analysis, audit and replay; do not retain unnecessary raw provider payloads.
- Keep credentials, private keys, seed phrases, cookies and bearer tokens out
  of the database, event log, telemetry, fixtures and research artifacts.
- Do not silently mutate historical evidence. Corrections and reorgs remain
  append-oriented events with their original provenance.

## Data classes

| Data class | Purpose | Current posture |
| --- | --- | --- |
| Normalized observations/events | Analysis, evidence timelines and replay | Durable application records; provider payload bodies are not required by the current schema |
| Stream cursors, gaps and verification | Restart, recovery and integrity audit | Durable until an approved retention process removes the record |
| Features, risk, scores and decisions | Explainable projections | Versioned records with timestamps, reason codes and evidence references |
| Paper orders, fills, positions and exits | Paper ledger and research | Append-oriented audit history; no live-money authority |
| Alerts, outbox and control audit | Notification and operator accountability | Delivery/idempotency history is retained for diagnosis and audit |
| Telemetry | Operational diagnosis | Bounded labels/counters/timings only; no raw provider bodies or secret-shaped values |
| Credentials and signing material | Authentication/execution | Never persisted by MemeRadar analysis/paper services |

## Retention and partition operation

There is currently **no automatic destructive retention job**. A future
retention change must name the data classes, legal basis, schedule, operator,
backup, restore test, audit record and rollback plan before deployment. A
controlled database operator must scope and review any deletion; application
workers must not delete broad history as a side effect of normal processing.

## Backup policy boundary

For a deployment that enables production read-only or paper-auto operation,
the deployment operator must schedule an access-controlled PostgreSQL custom
format dump at least daily, retain backups according to the approved
deployment/privacy schedule, and exercise an isolated restore before release
and after material schema changes. WAL/point-in-time recovery is deployment-
specific and is required when the target recovery point cannot be met by the
daily dump alone. MemeRadar does not silently create a backup scheduler or
persist backup credentials; an environment with no configured scheduler is
`NOT_CONFIGURED`, not backup acceptance.

The repository runbook records the non-destructive `pg_dump`/`pg_restore`
procedure and the 2026-09-07 disposable restore evidence. Managed backup
retention, off-host encryption, restore objective and legal/privacy approval
remain deployment acceptance items.

Logical replay partitions already preserve event-time/date/venue/token
boundaries. Physical PostgreSQL table partitioning is not enabled in the
current migration set. If volume measurements justify physical partitioning,
introduce it with a migration, bounded indexes, retention proofs and an
isolated backup/restore test. Never drop a partition until the relevant
backup and replay/audit obligations are verified.

Incident response must preserve the affected stream gap, recovery, correction,
decision and audit records. Use the isolated backup/restore procedure in
[`docs/RUNBOOKS/RELIABILITY.md`](RUNBOOKS/RELIABILITY.md) before any material
retention operation.

## Privacy review boundary

Public on-chain addresses, public social identifiers and provider source IDs
can still be personal data in some jurisdictions. The minimization and
provider-terms rules in [`docs/PRIVACY_PROVIDER_TOS.md`](PRIVACY_PROVIDER_TOS.md)
apply to collection, display, export and deletion requests. Live legal and
provider acceptance remains an external review item and is never inferred
from local tests.
