# Phase 7 / Sprint 7.3 Auth / Control API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fail-closed role authentication, auditable analysis/execution controls, validated versioned config mutation, and durable control-plane persistence without weakening MemeRadar’s protected modes.

**Architecture:** Keep role and control contracts in a provider-independent application module. Resolve static bearer tokens only at the FastAPI boundary. Implement an in-memory control plane for keyless tests and a transactional SQLAlchemy adapter backed by a new migration for control state, config versions, and audit events. Compose both the control and existing read APIs from one application engine when a database is configured.

**Tech Stack:** Python 3.12, FastAPI 0.115, Pydantic v2, SQLAlchemy 2 async, PostgreSQL 16, Alembic, pytest/TestClient.

**Spec:** `docs/superpowers/specs/2026-08-31-phase-7-sprint-7-3-auth-control-design.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DATA_MODEL.md`, `docs/SECURITY.md`, and `docs/TESTING.md`.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Never echo or log bearer tokens, provider credentials, database URLs, wallet material or raw secrets.
- Authentication fails closed: no configured role token is `503`, bad credentials are `401`, and insufficient role permissions are `403`.
- The execution kill switch defaults active; activation is idempotent and clearing remains blocked while protected modes are in force.
- No control endpoint creates decisions, authorizes `ENTRY_READY`, signs, submits or enables live execution.
- Config changes are allow-listed, bounded, canonicalized, versioned and paired with immutable audit events; invalid requests create no records.
- Application code remains free of FastAPI, SQLAlchemy and provider imports; persistence remains behind application-facing ports.
- Existing Sprint 7.2 read routes stay bounded and read-only; physical audit/config rows are projected without raw or secret material.

---

### Task 1: Define control contracts, validation and role policy

**Files:**
- Create: `packages/application/src/memeradar_application/control.py`
- Modify: `packages/application/src/memeradar_application/config.py`
- Test: `tests/unit/test_control.py`
- Modify: `tests/unit/test_health.py`

**Interfaces:**
- `ControlRole`, `ControlAction`, `ControlPrincipal`, `ControlState`, `ControlPlanePort`.
- `InMemoryControlPlane` with safe defaults, state mutations, config snapshots and audit history.
- Allow-listed alert/decision config validation, ordered thresholds, canonical hash and decision-affecting classification.
- `Settings` gains optional viewer/admin/execution role tokens and rejects duplicate non-empty role credentials.

- [x] **Step 1: Write failing unit tests** for role permissions, safe defaults, idempotent activation, protected-mode clear refusal, config range/type/order/unknown-field rejection, canonical hashes, no-op mutations, audit contents and duplicate token settings.
- [x] **Step 2: Run the focused tests** with `.venv/bin/pytest tests/unit/test_control.py tests/unit/test_health.py -q`; the initial run exposed the absent module and a draft syntax issue before the isolated control suite passed.
- [x] **Step 3: Implement the provider-free contracts and in-memory control plane** with immutable safe DTOs, shared authorization helpers, no secret-shaped config fields and explicit protected-mode enforcement.
- [x] **Step 4: Re-run focused tests plus application lint/typecheck** and verify no FastAPI/SQLAlchemy/provider import enters the application module. Evidence: control `15 passed`, health `9 passed`, Ruff clean, mypy `63 source files` clean.
- [ ] **Step 5: Commit** with `git add packages/application/src/memeradar_application/control.py packages/application/src/memeradar_application/config.py tests/unit/test_control.py tests/unit/test_health.py && git commit -m "feat: define control plane contracts"`.

### Task 2: Persist control state, config versions and audit events

**Files:**
- Modify: `packages/persistence/src/memeradar_persistence/models.py`
- Create: `packages/persistence/src/memeradar_persistence/control.py`
- Modify: `packages/persistence/src/memeradar_persistence/read_queries.py`
- Modify: `packages/persistence/src/memeradar_persistence/__init__.py`
- Create: `infra/alembic/versions/0004_control_plane.py`
- Modify: `scripts/check_migrations.py`
- Modify: `tests/unit/test_migration_contract.py`
- Create: `tests/integration/test_control_plane_postgres.py`
- Modify: `tests/integration/test_read_query_service.py`

**Interfaces:**
- `ControlStateRow`, `ConfigVersionRow`, and `AuditEventRow` mirror the logical data model with immutable config/audit history and a singleton state row.
- `SqlAlchemyControlPlane` implements `ControlPlanePort`; each mutation and its audit insert commit atomically, with safe defaults before first write.
- `SqlAlchemyReadQueryService` reads physical audit/config rows with bounded filtering and retains injectable catalog fallback when no physical rows exist.

- [ ] **Step 1: Add failing migration/model/adapter tests** for metadata parity, upgrade schema, transactional state/config/audit writes, rehydration across adapter instances, rollback on invalid mutation, and read API projection.
- [ ] **Step 2: Implement the three SQLAlchemy models and reversible `0004_control_plane` migration** with indexes, unique config hashes, JSON-only validated values and no secrets.
- [ ] **Step 3: Implement `SqlAlchemyControlPlane`** using shared application validation/authorization, row locking for state updates, monotonic versions and paired audit writes.
- [ ] **Step 4: Extend the read adapter** to query and safely map persisted audit/config rows under the existing `MAX_STORAGE_ROWS` bound.
- [ ] **Step 5: Run migration metadata checks and opt-in Postgres tests**, including upgrade from the current `0003_score_strategy_identity` head and downgrade/upgrade reversibility.
- [ ] **Step 6: Commit** with `git add packages/persistence infra/alembic scripts/check_migrations.py tests/unit/test_migration_contract.py tests/integration && git commit -m "feat: persist control plane audit state"`.

### Task 3: Add role authentication and control routes

**Files:**
- Create: `apps/api/src/memeradar_api/auth.py`
- Create: `apps/api/src/memeradar_api/control.py`
- Modify: `apps/api/src/memeradar_api/main.py`
- Modify: `apps/api/src/memeradar_api/manual.py`
- Test: `tests/unit/test_control_api.py`
- Modify: `tests/unit/test_manual_api.py`

**Interfaces:**
- Constant-time `RoleTokenAuthenticator` maps configured bearer tokens to non-secret principals and enforces `ControlAction` permissions.
- Strict `/v1/control/state`, `/v1/control/config`, `/v1/control/analysis-kill-switch`, `/v1/control/execution-kill-switch` and `/v1/control/config` routes.
- `create_app(..., control_plane=None)` composes an injected or in-memory control plane and shares one SQLAlchemy engine with the read adapter when configured.

- [ ] **Step 1: Write failing TestClient tests** for `503` unconfigured auth, `401` missing/wrong/malformed bearer credentials, `403` role separation, successful state/config reads, analysis pause, kill activation, protected clear `409`, admin config mutation, strict bodies, correlation IDs and secret non-disclosure.
- [ ] **Step 2: Implement the authenticator and strict control response/request models**; keep token values out of principals, audit actors, errors, logs and response serialization.
- [ ] **Step 3: Implement the control routes and app composition** with stable error mapping, safe mode response fields, shared engine ownership and clean shutdown.
- [ ] **Step 4: Re-run API/manual tests and add route-surface/provider-boundary contracts** proving no new execution or signing path exists.
- [ ] **Step 5: Commit** with `git add apps/api/src/memeradar_api tests/unit/test_control_api.py tests/unit/test_manual_api.py && git commit -m "feat: add authenticated control API"`.

### Task 4: Complete Sprint 7.3 quality gate and documentation

**Files:**
- Create: `tests/contract/test_phase7_sprint7_3.py`
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `.env.example`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/SECURITY.md`, `docs/PROVIDERS.md`, `docs/TESTING.md`, `docs/STATUS.md`
- Modify: this plan

**Interfaces:**
- Contract/replay tests cover deterministic control transitions, role matrix, audit/config persistence projections, protected modes, and safe UNKNOWN/external-blocker handling.
- Provider doctor/runtime checks remain keyless and honest; missing role/provider credentials are reported as blocked configuration, never fabricated PASS.

- [ ] **Step 1: Add replay, route-boundary, safe-mode, migration and secret-scan contracts** before the phase gate.
- [ ] **Step 2: Run focused tests, full `make verify`, opt-in integration/migration checks, Compose rebuild/runtime probes and doctor checks.**
- [ ] **Step 3: Reconcile all documentation and mark Sprint 7.3 complete only with exact evidence; record that control config is versioned and consumers retain startup reload semantics until a future hot-reload task.**
- [ ] **Step 4: Commit docs/status and push coherent implementation and documentation checkpoints.**
- [ ] **Step 5: Continue automatically to the next unblocked roadmap or approved research-extension task after this checkpoint.**

## Protected modes

Every control test, response and runtime probe must preserve
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`. The execution kill switch is a restrictive safety
control only; clearing it cannot enable execution and is blocked under the
current modes. LLM, social, wallet, market, protocol and external-provider
signals remain advisory or corroborating and cannot grant control permission.
