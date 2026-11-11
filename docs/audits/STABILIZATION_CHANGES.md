# Stabilization changes

Source base: `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`.

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml`, `Makefile` | Exclude PostgreSQL integration tests from the ordinary test phase; use CI's configured interpreter. |
| `tests/unit/test_coverage_config.py` | Assert test selection, interpreter, migration ordering and separate disposable DB contract. |
| `tests/smoke/test_production_compose_contract.py` | Isolate host environment and Compose `.env`; test intended missing-secret errors. |
| `tests/unit/test_provider_doctor.py`, `tests/unit/test_release_identity.py` | Use the current Python interpreter in child processes. |
| `packages/persistence/src/memeradar_persistence/models.py` | Add strict UTC persistence type to timezone-aware ORM columns; normalize writes and restore SQLite timezone awareness on reads. |
| `apps/worker/src/memeradar_worker/forward_evidence.py` | Avoid eagerly evaluating timestamp fallback when canonical discovery time exists. |
| `tests/unit/test_pumpfun_forward_evidence.py` | Cover UTC offsets, naive rejection, SQLite round-trip and terminal polling cycle. |
| `docs/RUNBOOKS/RELEASE.md`, `docs/RUNBOOKS/RELIABILITY.md` | Require a separate disposable PostgreSQL integration target; do not alias runtime/production DB. |

No migration, provider, route, score threshold, risk authority, or execution path
was added. Untracked `prompts/MemeRadar.md`, `scripts/run_codex_validation.sh`,
and `scripts/tailfnohup.sh` were preserved.

## Verification evidence

- Focused Ruff passed for changed Python files.
- Focused tests: 33 passed across test selection, Compose, provider doctor,
  release identity, forward evidence, persistence and migration contracts.
- `make verify`: literal exit 0. Python 1,529 passed / 21 integration tests
  deselected / 0 failed / 7 warnings. Vitest 83 passed / 24 files. Ruff, mypy
  (182 source files), CSS contract, frontend lint/typecheck, Compose config,
  secret scan, security review and SBOM passed.
- Migration graph: exit 0, one head `0012_stream_gap_diagnostics`, 27 ORM
  tables. No migration changed.
- `git diff --check` and `git diff --cached --check`: exit 0 after source edits.
- SBOM: 582 components, digest
  `sha256:e63fadcc56b9461e192ae70e9bd01ba01dc6a4e223143ab71a09aca9875933aa`.

The final aggregate ran on a modified worktree, not a clean checkout. The hosted
workflow was not rerun. Frontend production build and external vulnerability
scans remain unaccepted; see [runtime acceptance](RUNTIME_ACCEPTANCE.md).
