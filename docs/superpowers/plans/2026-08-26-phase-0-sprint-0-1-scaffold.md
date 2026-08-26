# Phase 0 Sprint 0.1 Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a keyless, reproducible modular-monolith scaffold with API, worker, web, local infrastructure, safe defaults and honest health checks.

**Architecture:** Keep the domain/provider boundary visible from the first package layout. The FastAPI API and async worker are separate entrypoints, while the Next.js web app consumes the API over an environment-configured base URL. PostgreSQL and Redis are local Compose dependencies, but readiness reports them as optional until a later persistence sprint makes them business-critical.

**Tech Stack:** Python 3.12-compatible FastAPI/Pydantic/Uvicorn, pytest, Ruff, mypy; Next.js 16.3.3 with React 19 and TypeScript; PostgreSQL 16; Redis 7; Docker Compose.

**Spec:** `README.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` Sprint 0.1, `docs/SECURITY.md`, `docs/TESTING.md`.

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No provider SDKs or persistence frameworks enter the domain package.
- The API must start without credentials and must not claim unavailable dependencies are healthy.
- No secrets, private keys, tokens or production credentials may enter tracked files.
- Compose is local development infrastructure; it must not enable live-money execution.

---

### Task 1: Repository package and toolchain baseline

**Files:**
- Create: `pyproject.toml`, `requirements.lock`, `.python-version`, `.env.example`, `.gitignore`, `.editorconfig`
- Create: `packages/domain/src/memeradar_domain/__init__.py`, `apps/api/src/memeradar_api/__init__.py`, `apps/worker/src/memeradar_worker/__init__.py`
- Create: `tests/conftest.py`, `tests/unit/test_package_layout.py`

**Interfaces:**
- Produces importable `memeradar_domain`, `memeradar_api`, and `memeradar_worker` packages through the repository test/runtime path.

- [ ] **Step 1: Write the failing package-layout test**

```python
def test_runtime_packages_are_importable():
    import memeradar_api
    import memeradar_domain
    import memeradar_worker

    assert memeradar_api.__version__
    assert memeradar_domain.__version__
    assert memeradar_worker.__version__
```

- [ ] **Step 2: Run `pytest tests/unit/test_package_layout.py -q` and verify it fails because the packages do not exist**
- [ ] **Step 3: Add the package markers, version constants and pinned Python project metadata**
- [ ] **Step 4: Run the focused test and verify it passes**
- [ ] **Step 5: Commit the repository baseline with `git add` and `git commit -m "build: scaffold Python workspace"`**

### Task 2: Safe configuration and honest API health endpoints

**Files:**
- Create: `packages/application/src/memeradar_application/__init__.py`, `packages/application/src/memeradar_application/config.py`
- Create: `apps/api/src/memeradar_api/health.py`, `apps/api/src/memeradar_api/main.py`
- Create: `tests/unit/test_health.py`

**Interfaces:**
- `memeradar_application.config.Settings.from_env(environ: Mapping[str, str] | None = None) -> Settings`
- `memeradar_api.health.build_health_router(settings: Settings) -> APIRouter`
- `GET /health/live` returns a liveness payload without dependency claims.
- `GET /health/ready` returns dependency states and HTTP 503 when a configured required dependency is unreachable.

- [ ] **Step 1: Write tests for safe defaults, liveness and optional/required readiness**
- [ ] **Step 2: Run `pytest tests/unit/test_health.py -q` and verify the new tests fail for missing modules/routes**
- [ ] **Step 3: Implement environment parsing, mode validation, bounded TCP dependency probes and FastAPI routes**
- [ ] **Step 4: Run the focused tests and verify they pass**
- [ ] **Step 5: Commit with `git commit -m "feat: add safe configuration and health checks"`**

### Task 3: Worker and web entrypoints

**Files:**
- Create: `apps/worker/src/memeradar_worker/main.py`, `tests/unit/test_worker_entrypoint.py`
- Create: `apps/worker/src/memeradar_worker/__main__.py`
- Create: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/tsconfig.json`, `apps/web/next.config.ts`, `apps/web/next-env.d.ts`, `apps/web/eslint.config.mjs`
- Create: `apps/web/src/app/layout.tsx`, `apps/web/src/app/page.tsx`, `apps/web/src/app/globals.css`

**Interfaces:**
- `python -m memeradar_worker` starts a cancellable analysis-only worker loop and handles SIGTERM.
- `npm run dev`, `npm run build`, `npm run lint` and `npm run typecheck` are defined in `apps/web/package.json`.
- The initial page visibly labels the system as analysis-only/paper-trading and does not imply live state.

- [ ] **Step 1: Write the worker lifecycle test**
- [ ] **Step 2: Run `pytest tests/unit/test_worker_entrypoint.py -q` and verify it fails**
- [ ] **Step 3: Implement the cancellable worker and create the minimal Next.js shell**
- [ ] **Step 4: Run the backend test plus frontend lint/typecheck/build checks**
- [ ] **Step 5: Commit with `git commit -m "feat: add worker and operator web shell"`**

### Task 4: Local containers and Compose topology

**Files:**
- Create: `infra/docker/api.Dockerfile`, `infra/docker/worker.Dockerfile`, `infra/docker/web.Dockerfile`
- Create: `infra/compose/docker-compose.yml`, `infra/compose/.dockerignore`
- Create: `.dockerignore`
- Create: `tests/smoke/test_compose_contract.py`

**Interfaces:**
- Compose services are named `api`, `worker`, `web`, `postgres`, and `redis`.
- API/worker images run without signing credentials and retain the four safe mode values.
- Postgres and Redis have health checks; API readiness can require them explicitly through environment configuration.

- [ ] **Step 1: Write static Compose/Docker contract tests**
- [ ] **Step 2: Run the contract test and verify it fails because the infrastructure files do not exist**
- [ ] **Step 3: Add Dockerfiles, health checks, safe environment defaults and dependency ordering**
- [ ] **Step 4: Run `pytest tests/smoke/test_compose_contract.py -q` and `docker compose -f infra/compose/docker-compose.yml config`
- [ ] **Step 5: Commit with `git commit -m "build: add local compose infrastructure"`**

### Task 5: Developer commands and sprint evidence

**Files:**
- Create: `Makefile`, `scripts/__init__.py`, `scripts/doctor.py`, `scripts/secret_scan.py`, `.github/workflows/ci.yml`
- Modify: `docs/STATUS.md`
- Test: `tests/unit/test_doctor.py`, `tests/unit/test_secret_scan.py`

**Interfaces:**
- Make targets: `bootstrap`, `lint`, `typecheck`, `test`, `verify`, `up`, `down`, `migrate`, `doctor`.
- `python scripts/doctor.py` prints redacted configuration/mode/dependency diagnostics and exits nonzero only for a required local failure.
- CI runs backend tests/lint/typecheck, frontend checks, Compose config validation and secret scanning without provider credentials.

- [ ] **Step 1: Write the doctor contract test**
- [ ] **Step 2: Run it and verify it fails**
- [ ] **Step 3: Implement the doctor, Make targets and CI workflow**
- [ ] **Step 4: Run the full local verification commands and record exact results in `docs/STATUS.md`**
- [ ] **Step 5: Commit the completed Sprint 0.1 checkpoint**

## Sprint 0.1 Acceptance Evidence

Run from the repository root:

```bash
python3 -m pytest -q
docker compose -f infra/compose/docker-compose.yml config
make verify
```

The sprint is complete only when the command results, current safety modes, external-provider state, Git synchronization state and the exact next roadmap task are recorded in `docs/STATUS.md`.
