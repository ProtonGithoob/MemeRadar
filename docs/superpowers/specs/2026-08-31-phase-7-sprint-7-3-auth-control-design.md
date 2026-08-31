# Phase 7 / Sprint 7.3 — Auth / Control API Design

## Status

Approved for autonomous implementation on 2026-08-31. This design is limited to
the current Sprint 7.3 roadmap scope and preserves the existing analysis-only
deployment boundary.

## Goal

Provide an authenticated operator control surface with explicit viewer,
operator, admin, and execution roles; durable audit/config history; and
emergency analysis/execution controls. The API must fail closed when role
credentials are not configured and must never expose credentials or permit a
control request to change the protected operating modes.

## Existing seams to preserve

- `Settings` remains the single source for the four protected modes and rejects
  unsafe environment overrides.
- The existing `OPERATOR_API_TOKEN` continues to authorize the manual mint
  endpoint. New role credentials are optional `VIEWER_API_TOKEN`,
  `ADMIN_API_TOKEN`, and `EXECUTION_API_TOKEN` values.
- Application code remains independent of FastAPI, SQLAlchemy, and provider
  SDKs.
- The Sprint 7.2 read API remains bounded and read-only. Its audit and config
  catalog methods will read the new physical rows when a database is present,
  while fixture catalogs remain injectable for keyless tests.
- `ENTRY_READY` and all execution-like states remain deterministic domain
  decisions. Control endpoints cannot create a candidate decision or sign a
  transaction.

## Application control contract

Add a provider-free `memeradar_application.control` module containing:

- `ControlRole`: `VIEWER`, `OPERATOR`, `ADMIN`, and `EXECUTION`.
- `ControlAction`: read state/config, pause/resume analysis, activate/clear the
  execution kill switch, and mutate config.
- Immutable `ControlPrincipal` and `ControlState` values.
- `ControlPlanePort`, an async application port for reading state/config and
  applying the three control mutations.
- `InMemoryControlPlane` for deterministic fixtures and API tests.
- Shared authorization, safe-state, config-validation, canonical-hash, and
  audit-event helpers used by the persistence adapter.

The role matrix is:

| Role | Read control | Analysis pause/resume | Activate execution kill switch | Config mutation | Clear execution kill switch |
| --- | --- | --- | --- | --- | --- |
| viewer | yes | no | no | no | no |
| operator | yes | yes | yes | no | no |
| admin | yes | yes | yes | yes | yes, subject to protected-mode safety |
| execution | yes | no | yes | no | no |

The `execution` role is intentionally narrow: it can make the emergency
execution stop more restrictive, but it cannot loosen policy or mutate
configuration. Clearing the execution switch is an admin-only action and is
rejected while the current protected modes remain
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`.

The initial state is `analysis_paused=false`,
`execution_kill_switch=true`, and version `0`. State changes increment the
version and carry the actor, timestamp, and correlation ID in an immutable
audit event.

## Mutable configuration

The control plane accepts only these JSON fields:

- `alert_max_messages_per_window`: integer from 1 through 1000;
- `alert_rate_limit_window_seconds`: finite number from 1 through 86400;
- `decision_watch_threshold`: finite number from 0 through 100;
- `decision_strong_setup_threshold`: finite number from 0 through 100;
- `decision_entry_ready_threshold`: finite number from 0 through 100;
- `decision_minimum_confidence`: finite number from 0 through 1.

The three decision thresholds must remain ordered and config values are
canonicalized before hashing. Unknown fields, booleans in numeric positions,
non-finite numbers, empty patches, and protected-mode fields are rejected.
Decision fields set `decision_affecting=true`; alert fields do not. No secret,
provider credential, database URL, wallet material, or execution mode is part
of this mutation surface. A config mutation creates a new immutable
`control-config-vN` snapshot and a paired audit event; the response exposes
only the validated non-secret snapshot and its hash.

The current worker and decision engine continue to receive their startup
configuration through their existing composition roots. The control API does
not claim a hot reload until a consumer explicitly reads and applies a
versioned snapshot. This avoids silently changing a running scorer without a
matching config hash in its decision output.

## API surface

Add `/v1/control` routes:

- `GET /state` — any configured role;
- `GET /config` — any configured role;
- `POST /analysis-kill-switch` with `{active, reason}` — operator/admin;
- `POST /execution-kill-switch` with `{active, reason}` — operator/admin/
  execution when `active=true`; admin-only when clearing is requested, with
  protected-mode rejection;
- `POST /config` with `{changes, reason}` — admin only.

All mutation bodies use strict models and bounded text/maps. Responses include
the control API version, safe state/config data, and no bearer token. Auth
failures are `503` when no role token is configured, `401` for a missing or
invalid bearer credential, and `403` for a valid principal without the action.
Validation failures are `422`; a protected-mode refusal to clear the
execution switch is `409`.

Role tokens are compared in constant time. Token values are never used as
principal subjects, audit actors, exception details, response fields, or log
fields. Duplicate non-empty role tokens are rejected at settings construction
so one credential cannot ambiguously represent multiple roles.

The existing read routes remain usable without credentials in an unconfigured
development process. When control credentials are configured, the dedicated
control surface is always authenticated; no new public mutation route is
introduced.

## Persistence

Migration `0004_control_plane` adds:

- `control_state`: singleton state row with pause/kill flags, monotonic
  version, actor, timestamp, and update correlation ID;
- `config_versions`: immutable version, timestamp, actor, unique canonical
  config hash, decision-affecting flag, and validated JSON config;
- `audit_events`: immutable actor/action/target, before/after JSON, timestamp,
  and correlation ID, with indexes for time and action queries.

The SQLAlchemy adapter performs each state/config mutation and its audit insert
in one transaction. State mutations use a row lock when an existing singleton
is present. Reads return safe defaults if the singleton or initial config has
not yet been persisted. The Sprint 7.2 read adapter queries physical audit and
config rows and retains its existing bounded in-memory catalog fallback.

## Failure and safety behavior

- No configured role token means control auth is unavailable (`503`), never an
  anonymous admin path.
- Missing, malformed, or wrong bearer credentials do not disclose configured
  token presence or values beyond the stable status class.
- Authorization is evaluated before mutation validation and persistence.
- Failed validation does not create a config version or audit event.
- Duplicate/no-op config changes return the existing snapshot without a second
  audit record.
- Execution kill-switch activation is idempotent and remains safe if repeated.
- Clearing the execution switch cannot proceed while protected modes are in
  force, even for an authenticated admin.
- `UNKNOWN`, provider disagreement, external labels, LLM output, or any other
  advisory signal is not consulted as execution authority.
- All four protected modes are asserted in API, persistence, smoke, and
  runtime contract tests.

## Verification plan

- Application unit tests cover role permissions, immutable safe defaults,
  allow-list/type/range/order validation, canonical hashes, no-op behavior,
  audit contents, and protected-mode refusal.
- API tests cover all auth classes, role separation, strict request models,
  secret non-disclosure, state/config responses, mutation status codes, and
  correlation propagation.
- Persistence tests cover migration metadata, transactional state/config/audit
  writes, rehydration after a new adapter instance, and read API projection.
- Contract tests assert provider-free application boundaries, read-only
  existing routes, no execution/signing material, and protected modes.
- The Sprint 7.3 gate is the repository `make verify`, opt-in Postgres
  integration tests including migration upgrade, Compose rebuild/runtime
  probes, safe doctor output, and honest external credential blocking.
