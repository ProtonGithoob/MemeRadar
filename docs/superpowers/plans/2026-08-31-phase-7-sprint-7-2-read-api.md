# Phase 7 / Sprint 7.2 Read API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose bounded, read-only candidate, token/timeline, wallet, provider-health and audit/config query APIs over provider-independent contracts.

**Architecture:** Define validated query DTOs, safe read models, cursor encoding and an application-facing `ReadQueryPort` in the application package. Add a SQLAlchemy adapter for the existing persisted candidate/token/observation/feature/risk/score/transition/alert tables and deterministic in-memory catalogs for application records whose physical persistence is a later roadmap task. Compose the port into FastAPI with typed response models; no route may mutate state, invoke a provider, sign, submit, enable a mode or expose secret/raw provider material.

**Tech Stack:** Python 3.12, FastAPI 0.115, Pydantic v2, SQLAlchemy 2 async, PostgreSQL 16, pytest/TestClient.

**Spec:** `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md` (Sprint 7.2), `docs/SECURITY.md` and `docs/TESTING.md`.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- All endpoints are GET-only and read-only; no query response grants execution authority.
- Reject invalid/unknown filters, oversized limits, malformed cursors and unbounded time ranges.
- Preserve `UNKNOWN`, `STALE`, `CONFLICTED` and `INVALID`; never convert missing evidence to `SAFE`.
- Return only normalized/bounded payloads; redact secret-shaped values and omit raw provider bodies.
- Preserve event-time ordering and no-lookahead `as_of` behavior for timeline queries.
- Keep domain/application query contracts free of FastAPI, SQLAlchemy and provider imports.

---

### Task 1: Define the provider-independent read contracts and cursor utilities

**Files:**
- Create: `packages/application/src/memeradar_application/read_api.py`
- Test: `tests/unit/test_read_api.py`

**Interfaces:**
- `ReadQueryPort` exposes `list_candidates`, `get_candidate`, `get_token`,
  `list_timeline`, `list_wallets`, `get_wallet`, `list_provider_health`,
  `list_audit_events` and `list_config_versions`.
- `CandidateQuery`, `TimelineQuery`, `WalletQuery`, `ProviderHealthQuery`,
  `AuditQuery` and `ConfigQuery` validate bounded filters.
- `CandidateView`, `TokenView`, `TimelineEntryView`, `WalletView`,
  `ProviderHealthView`, `AuditEventView`, `ConfigVersionView` are safe immutable
  response DTOs.
- `CursorCodec.encode(resource, values)` and `CursorCodec.decode(resource,
  cursor)` produce/validate versioned URL-safe opaque cursors.
- `InMemoryReadQueryService` implements the port for keyless replay and API
  tests, with deterministic sorting and `Page` results.

- [x] **Step 1: Write failing contract tests** for cursor version/resource validation, limit/time-window bounds, candidate ranking/filtering, timeline `as_of` exclusion, deterministic pagination, unknown provider health, secret-shaped payload redaction, and permanent `execution_eligible=False`.
- [x] **Step 2: Run the focused tests** with `.venv/bin/pytest -q tests/unit/test_read_api.py`; expect import/contract failures.
- [x] **Step 3: Implement the bounded DTOs, cursor codec, safe payload normalizer, in-memory query service and port.** Use score-descending candidate ordering, event-time timeline ordering, and explicit empty pages for catalogs without records.
- [x] **Step 4: Re-run the focused tests** and add edge cases for cursor mismatch, invalid date order, `UNKNOWN` health and oversized payloads.
- [x] **Step 5: Commit** with `git add packages/application/src/memeradar_application/read_api.py tests/unit/test_read_api.py && git commit -m "feat: define read API contracts"`.

### Task 2: Add the SQLAlchemy read adapter over persisted core records

**Files:**
- Create: `packages/persistence/src/memeradar_persistence/read_queries.py`
- Modify: `packages/persistence/src/memeradar_persistence/__init__.py`
- Test: `tests/unit/test_read_persistence.py`
- Modify: `tests/integration/test_persistence_postgres.py`

**Interfaces:**
- `SqlAlchemyReadQueryService(engine, *, wallets=(), provider_health=(), audit_events=(), config_versions=())` implements `ReadQueryPort`.
- Candidate ranking joins `CandidateRow` to its denormalized latest score/risk IDs and returns bounded normalized views.
- Token detail resolves the token, candidate, pools and latest score/risk; timeline combines observations, transitions, snapshots and alerts using event-time ordering and the supplied `as_of` boundary.
- Wallet/provider/audit/config catalogs remain injectable until their later physical tables exist; empty catalogs are explicit, not fabricated health.

- [x] **Step 1: Add fake-session/unit tests** proving the adapter maps persisted rows without raw provider bodies or secret fields and returns explicit empty non-persisted catalogs.
- [x] **Step 2: Add an opt-in Postgres integration test** that persists one candidate, score/risk/feature record, observation, transition and alert, then verifies ranking, token detail and timeline pagination.
- [x] **Step 3: Implement SQLAlchemy queries and mapping helpers** with maximum result bounds, deterministic tie-breakers, `selectinload` only where needed and no writes/commits.
- [x] **Step 4: Run unit and opt-in Postgres tests**; verify no migration is required and that `UNKNOWN`/non-fresh states survive mapping.
- [x] **Step 5: Commit** with `git add packages/persistence/src/memeradar_persistence tests/unit/test_read_persistence.py tests/integration/test_persistence_postgres.py && git commit -m "feat: add persisted read query adapter"`.

### Task 3: Compose typed FastAPI read routes

**Files:**
- Create: `apps/api/src/memeradar_api/read.py`
- Modify: `apps/api/src/memeradar_api/main.py`
- Test: `tests/unit/test_read_api_routes.py`

**Interfaces:**
- `build_read_router(service: ReadQueryPort | None) -> APIRouter` exposes:
  `GET /v1/candidates`, `GET /v1/candidates/{candidate_id}`,
  `GET /v1/tokens/{token_id}`, `GET /v1/tokens/{token_id}/timeline`,
  `GET /v1/wallets`, `GET /v1/wallets/{address}`,
  `GET /v1/providers/health`, `GET /v1/audit/events` and
  `GET /v1/config/versions`.
- Pydantic v2 query models forbid extra parameters and bound `limit` to 1..100.
- Responses are explicit page envelopes with `items`, `limit`, `has_more` and
  `next_cursor`; missing resources return 404 and unconfigured storage returns
  503 without leaking connection details.
- `create_app(..., read_service=None)` injects a test service or creates the
  SQLAlchemy adapter when `DATABASE_URL` is configured, disposing its engine on
  shutdown; no database URL leaves routes safely unavailable.

- [x] **Step 1: Write failing TestClient tests** for every route, response shape, filters/cursors, 404/422/503 behavior, correlation headers, safe modes and no execution fields.
- [x] **Step 2: Implement response models, query-model validation, route mapping and app composition.** Use FastAPI `response_model` filtering and `HTTPException` for bounded public errors.
- [x] **Step 3: Re-run route tests** and add tests for invalid UUID/address, extra query parameters, future timeline evidence and secret-shaped config/audit values.
- [x] **Step 4: Run API lint/typecheck and the API-focused regression suite.**
- [x] **Step 5: Commit** with `git add apps/api/src/memeradar_api tests/unit/test_read_api_routes.py && git commit -m "feat: expose bounded read API"`.

### Task 4: Add Sprint 7.2 replay/Compose contracts and documentation

**Files:**
- Create: `tests/contract/test_phase7_sprint7_2.py`
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`,
  `docs/SECURITY.md`, `docs/TESTING.md`, `docs/PROVIDERS.md`, `docs/STATUS.md`
- Modify: this plan

**Interfaces:**
- Fixture-free replay proves repeated query output and cursor traversal are deterministic.
- Contract checks prove application/persistence boundaries, GET-only route surface,
  bounded query controls, protected modes and no execution/provider authority.

- [x] **Step 1: Add replay and route-boundary contracts** before the phase gate.
- [x] **Step 2: Run focused, full, migration, Compose and runtime checks** and record exact evidence.
- [x] **Step 3: Mark Sprint 7.2 complete only after the keyless gate passes;** record physical wallet/provider-health/audit/config persistence as a later schema boundary when catalogs are empty.
- [x] **Step 4: Commit docs/status and push both coherent implementation and documentation checkpoints.**

## Protected modes

The read API remains `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`. Querying a candidate at
`ENTRY_READY` is informational; it cannot transition state, send an alert,
open a paper position, invoke execution, sign a wallet transaction or change
configuration.
