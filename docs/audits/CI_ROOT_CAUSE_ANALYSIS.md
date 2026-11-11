# CI root-cause analysis

Scope: read-only GitHub Actions run `40011971215` and local reproductions from
`main`, HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`. The hosted run was not
rerun after local changes.

## Backend failures

| Original failure | Root cause and owner | Change | Regression evidence |
| --- | --- | --- | --- |
| 20 PostgreSQL integration tests failed before migration | General pytest collected tests marked `integration` before the CI migration step. The Make `test` target owned test-scope selection; the integration target already ran after migrations. | `make test` excludes `integration`; CI invokes `make test PYTHON=python`, then migrates and runs the dedicated integration target. | `tests/unit/test_coverage_config.py`; final `make verify` exit 0, 21 integration tests deselected (including the new runtime-settings concurrency contract). Real PostgreSQL acceptance remains unrun. |
| `test_production_compose_requires_secrets_before_startup` | The smoke test inherited host environment and Compose project `.env`; its assertion reached missing `POSTGRES_USER` before the intended missing-`DATABASE_URL` condition. | Clear related variables, pass an empty Compose interpolation env file, and seed earlier required Postgres variables in the missing-URL case. | `tests/smoke/test_production_compose_contract.py`; included in focused and aggregate test passes. |
| `test_supported_make_invocation_bootstraps_scripts_package` | Child Make invocation assumed local-only `.venv/bin/python`, absent in hosted CI. | Pass `PYTHON=sys.executable` to the child process. | `tests/unit/test_provider_doctor.py`; focused and aggregate tests passed. |
| `test_release_identity_cli_writes_the_same_safe_artifact` | Test hard-coded `.venv/bin/python`, absent in hosted CI. | Invoke the CLI with `sys.executable`. | `tests/unit/test_release_identity.py`; focused and aggregate tests passed. |

The hosted run reported 23 failures, 1,519 passes and 1 skip. Compose and image
build jobs passed; secret scan passed; release-identity job was skipped due to
dependency failures. Local regressions passed; hosted rerun is not claimed.

## Additional local defect found during closure

`tests/unit/test_pumpfun_forward_evidence.py::test_no_pair_is_persisted_as_unknown_and_second_cycle_is_idempotent`
failed in the broad local suite. SQLite strips timezone information from bare
SQLAlchemy `DateTime(timezone=True)` values, so an aware timestamp reloaded as
naive and strict `ensure_utc` rejected it. A second issue evaluated the strict
fallback passed to `dict.get` even when canonical discovery time existed. The
persistence boundary now uses `UTCDateTime`: writes reject naive values and
normalize aware values to UTC; reads restore UTC awareness on SQLite.
`ensure_utc` remains strict. The worker fallback is conditional. Tests cover
UTC, +04, -07, naive-write rejection, SQLite reload and polling exhaustion.

Focused persistence/forward-evidence tests passed (16). Final aggregate
`make verify` exited 0 with 1,529 Python passes, 21 integration deselections,
zero failures and 7 warnings. The PostgreSQL concurrency test remains skipped
without the dedicated test database URL.

## Frontend production dependency audit

`npm audit --omit=dev` found 3 production advisories: Next.js `16.3.3`
(critical; audit reported same-major patched version `16.4.3`), `sharp` `0.35.4`
(high), and `source-map-js` `1.2.1` (high). Full audit reported 9 findings (3
critical, 5 high, 1 moderate), including development tooling. Online package
metadata stalled; offline update failed because required metadata was not
cached. No dependency or lockfile was changed. The findings remain unresolved;
offline `npm ci` output is not vulnerability-audit evidence.

### Dependency remediation — 2026-11-03

Updated Next.js and `eslint-config-next` to `16.4.4`, `sharp` to `0.35.5`,
`source-map-js` to `1.2.2`, and Vitest to `5.1.0`. `npm audit --omit=dev`
reports zero production vulnerabilities. The full audit now reports 16
moderate `minimatch` advisories in the development ESLint dependency tree; the
available forced fix would downgrade ESLint to `4.0.0`, so that change was not
applied. Frontend tests, lint, typecheck, and production build pass with the
updated lockfile.

## Separate environment failures

- The production build compiled but Next's TypeScript configuration subprocess
  returned empty stdout under this host's process/stream restriction. Direct
  TypeScript checks passed; build acceptance did not.
- Route-budget scripts are absent from current `apps/web/package.json`,
  Makefile and workflow. An attempted package-script invocation returned
  “Missing script”; no budget result is claimed.
- PostgreSQL integration was unavailable: no isolated test URL, PostgreSQL
  binaries, or Docker daemon access.

See [stabilization evidence](STABILIZATION_CHANGES.md),
[runtime boundaries](RUNTIME_ACCEPTANCE.md), and
[remaining blockers](REMAINING_BLOCKERS.md).
