# Phase 0 Sprint 0.2 Quality and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining Phase 0 quality gate work with measured coverage, a meaningful frontend unit-test baseline, and correlation-aware structured logging.

**Architecture:** Keep quality tooling at the repository boundary and add telemetry as a provider-independent package consumed by the API composition root. Request correlation is generated or validated at the API edge, stored in context for downstream logs, and returned to operators through a response header without exposing secrets or changing domain behavior.

**Tech Stack:** Python 3.12, pytest-cov, Ruff, mypy, standard-library JSON logging/contextvars; Next.js 16.3.3, React 19, TypeScript, Vitest, Testing Library and jsdom; GitHub Actions.

**Spec:** `docs/ROADMAP.md` Sprint 0.2, `docs/MASTER_SPEC.md` §11, `docs/ARCHITECTURE.md` failure/observability sections, `docs/SECURITY.md`, `docs/TESTING.md`.

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Structured logs must be JSON, include correlation IDs, and never include credentials or raw secret values.
- Correlation IDs are untrusted input: accept only bounded safe characters or generate a UUID.
- Frontend tests must assert visible operator behavior, including analysis-only/paper labels.
- CI remains keyless and provider-independent; hosted results must never be reported as passing without evidence.

---

### Task 1: Coverage configuration

**Files:**
- Modify: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`
- Test: `tests/unit/test_coverage_config.py`

**Interfaces:**
- `make test` runs pytest with branch coverage over `apps` and `packages` and emits a terminal report.
- Coverage configuration excludes tests/scripts from measured application source and does not impose a vanity global threshold.

- [ ] **Step 1: Write a test that verifies the repository coverage configuration and Make target**
- [ ] **Step 2: Run `pytest tests/unit/test_coverage_config.py -q` and verify it fails because coverage configuration is absent**
- [ ] **Step 3: Add `[tool.coverage.*]` configuration, update `make test`, and use the same coverage command in CI**
- [ ] **Step 4: Run the focused test and `make test`; verify the configuration and report are valid**
- [ ] **Step 5: Commit with `git commit -m "test: configure backend coverage"`**

### Task 2: Frontend unit-test baseline

**Files:**
- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/tsconfig.json`
- Create: `apps/web/vitest.config.ts`, `apps/web/src/test/setup.ts`, `apps/web/src/app/page.test.tsx`

**Interfaces:**
- `npm run test` runs Vitest in non-watch mode with jsdom.
- The page test verifies the visible product name and all protected mode labels/statuses.

- [ ] **Step 1: Write the page test and Vitest configuration reference**
- [ ] **Step 2: Run `npm run test` and verify it fails because Vitest/configuration is absent**
- [ ] **Step 3: Add pinned Vitest, Testing Library and jsdom dependencies and configure TypeScript/Vitest setup**
- [ ] **Step 4: Run `npm run test`, `npm run lint`, `npm run typecheck` and `npm run build`; verify all pass**
- [ ] **Step 5: Commit with `git commit -m "test: add frontend unit test baseline"`**

### Task 3: Correlation-aware structured logging

**Files:**
- Create: `packages/telemetry/src/memeradar_telemetry/__init__.py`, `packages/telemetry/src/memeradar_telemetry/logging.py`
- Modify: `apps/api/src/memeradar_api/main.py`, `pyproject.toml`
- Test: `tests/unit/test_telemetry.py`

**Interfaces:**
- `memeradar_telemetry.logging.correlation_id() -> str | None`
- `memeradar_telemetry.logging.correlation_scope(value: str) -> ContextManager[str]`
- `memeradar_telemetry.logging.JsonFormatter` emits timestamp, level, logger, message and correlation ID fields.
- API requests accept a bounded `X-Correlation-ID` or generate one, echo it in the response, and log completion as JSON.

- [ ] **Step 1: Write tests for formatter fields, context scoping, valid header propagation and invalid-header replacement**
- [ ] **Step 2: Run `pytest tests/unit/test_telemetry.py -q` and verify it fails because the telemetry package/middleware is absent**
- [ ] **Step 3: Implement the contextvar, redacting JSON formatter, safe ID validation and API middleware**
- [ ] **Step 4: Run the focused test plus full Ruff/mypy/pytest checks**
- [ ] **Step 5: Commit with `git commit -m "feat: add correlation-aware structured logging"`**

### Task 4: P0 gate and status evidence

**Files:**
- Modify: `docs/ROADMAP.md`, `docs/STATUS.md`

**Interfaces:**
- `make verify` includes coverage-backed backend tests, frontend Vitest tests, telemetry checks, Compose validation and secret scanning.
- Status records exact local results, hosted CI observation state, safety modes, migration state, provider state, commit/sync state and the exact next roadmap task.

- [ ] **Step 1: Run `make verify`, frontend audit, Compose contract/config and local Docker smoke checks**
- [ ] **Step 2: Inspect GitHub Actions availability without exposing credentials; record only observed state**
- [ ] **Step 3: Mark only verified Sprint 0.2 tasks/gate items in the roadmap and status**
- [ ] **Step 4: Commit status/roadmap evidence with `git commit -m "docs: record phase 0 quality gate"`**
- [ ] **Step 5: Push and verify local/origin synchronization**

## Sprint 0.2 Acceptance Evidence

```bash
make verify
npm --prefix apps/web audit --omit=dev
docker compose -f infra/compose/docker-compose.yml config --quiet
```

The P0 gate is complete only after these commands and the hosted-CI observation state are recorded in `docs/STATUS.md`, with all safety modes unchanged.
