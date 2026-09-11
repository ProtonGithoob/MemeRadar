# Design: Frontend and Early Alpha presentation hardening

## Scope

Correct the open PR #3 integration and the remaining presentation/read-model
defects without changing scoring, risk, execution, provider adapters, or the
protected operating modes. `main`, the merged PR state, and `docs/STATUS.md`
are authoritative; PR #3 is an unmerged reference diff, not a base commit.

## Canonical flow

`EventEnvelope` carries the existing score/risk/evidence projection. The alert
pipeline normalizes that payload into one bounded Early Alpha projection and
uses one explicit state transition function. `AlertDeliveryService` remains the
only delivery/retry/rate-limit/transport boundary. Ordinary events continue to
use `AlertRenderer`; only payloads marked as Early Alpha select
`EarlyAlphaAlertRenderer`.

The existing `alerts` table is the durable state/snapshot ledger. Early Alpha
alerts carry a bounded canonical snapshot, stable identity, transition, config
version, and correlation id. A prefix query over the existing dedupe-key index
retrieves the latest snapshot after worker restart; no new migration is needed.

## Early Alpha policy

States are `NOT_CONFIRMED`, `CONFIRMED`, `DEGRADED`, `INVALIDATED`, and
`CONFLICT`. Confirmation is projected as `CONFLICT` when the canonical risk
projection is not an explicit compatible PASS. The transition table rejects
meaningless repeats unless the upstream payload explicitly marks a material
evidence update. Prior values render as `UNKNOWN` when no persisted snapshot
exists; no zero default is introduced. Cohort labels are always rendered under
`COHORT SIMILARITY` and never as a prediction or target.

## Web/API parity

Extend existing read contracts, not TypeScript calculations: operational
counters preserve missing/malformed values as `UNKNOWN`; provider and chain
aggregation consumes stable metadata and is fail-closed; graph responses expose
`root_id`, policy limits, observed facets, and all quality states; settings keep
raw numeric drafts until validated; search errors are visible; token detail has
one lifecycle evidence panel; the parity manifest documents Telegram Early
Alpha fields and intentional omissions.

## Verification

Add focused failing tests for the state machine, historical snapshots, conflict,
dedupe/retry/restart, ordinary-renderer fallback, API graph metadata, frontend
unknown counters, provider aggregate, settings validation, visible search
errors, and semantic graph classes. Then run focused tests, full Python and
frontend suites, static CSS check, lint/typecheck/build, browser checks where
the local server/credentials permit, migration/security/SBOM/diff checks, and
fresh `make verify` evidence. External hosted CI and real provider sample
claims remain explicitly blocked if unavailable.
