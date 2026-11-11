# End-to-end acceptance — 2026-11-10

## Current-source P30 acceptance — 2026-11-11

Exact command: `COVERAGE_FILE=/tmp/memeradar-final-verify-p30.coverage make verify > artifacts/verification/2026-11-11-final/make-verify-p30.log 2>&1`; exit 0 on fingerprint `97e36f90571212c774b8827a2672a4f1a3137f5c39cdfaf3c12f4a1f2cbfe6e8` (641 files, 8,385,898 bytes). The manifest was rechecked with zero changed/missing source files. Backend: 1,650 passed / 34 integration tests deselected / 7 warnings in 406.61s. Frontend: 86 passed / 25 files. Ruff, mypy (187 files), CSS (298 classes / 62 files), ESLint, TypeScript, Compose config, secret scan, local security review and SBOM passed. Migration graph check reported head `0015_stream_verification_provenance`, 27 ORM tables. Log SHA-256: `9ab4ced53531fc3a24b1e62c24e03d97bd4bf7a9fca566641a2f60168d352c15`.

P30 added persisted bounded verification provenance (provider, scoped program, commitment, method and recovery attempt) and an operations read projection. The provider records `FINALIZED` only for backfills explicitly requested at finalized commitment; missing metadata remains `UNKNOWN`. This is local provenance, not proof of complete live subscription coverage; global source coverage remains `UNKNOWN`. The migration graph was checked, but PostgreSQL did not execute the migration.

A separate attempted full verification ended during Vitest without a durable log; its result is `UNKNOWN` and is not counted. The successful command above is the final local acceptance evidence. PostgreSQL integration/restart remains blocked because the test URL and local PostgreSQL binaries are absent and Docker API access is denied. Playwright did not start because the sandbox rejects `listen(127.0.0.1:13000)` with `EPERM`. The optimized production bundle compiled, but Next.js could not obtain TypeScript `--showConfig` child-process output; direct TypeScript config parsing and typecheck in `make verify` passed. External container/npm/pip scans were not run. Live source, real Telegram receipt and alpha remain unverified.

## Final local verification delta — 2026-11-11

`COVERAGE_FILE=/tmp/memeradar-final-verify-p25.coverage make verify` ran on the
current dirty source and exited 0. It reported 1,642 backend passed, 33
integration tests deselected, 7 warnings in 282.04 seconds, and 86 frontend
tests passed. Ruff, mypy (187 files), CSS contract, frontend lint/typecheck,
Compose config, local secret/security review, migration graph and SBOM also
passed. Stream recovery focused tests passed 33. The command log is
`/tmp/memeradar-final-verify-p25.log`; its exit record is
`/tmp/memeradar-final-verify-p25.exit`.

The current stream worker attempts persisted gaps before reading the live
source and wakes on a serialized timer even when the source is idle. Recovery
batches are capped at four gaps by default and the default cadence is 30
seconds. The operations API and Scan Monitor expose persisted gap states,
verified recovery-range count and pre-identity counts while leaving overall
source coverage `UNKNOWN`. These local changes do not establish provider
completeness.

This run does not include PostgreSQL integration, Playwright, image/dependency
external scanning, live providers, Telegram delivery, application-worker
restart, production deployment or alpha validation. The prior PostgreSQL run
(32 passed at migration `0013_social_call_asset_index`) predates the P24/P25
stream worker changes; the current paper-worker PostgreSQL recreation test
could not run because `MEMERADAR_TEST_DATABASE_URL` is unset and Docker API
access is denied. The old browser result remains 44 passed / 4 skipped, not
current-source browser acceptance.

## Final-source continuation checkpoint — 2026-11-10

Branch `main`, HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`, clean-source relation `HEAD...origin/main = 0/0`; worktree remains dirty and unchanged user/recovery work is preserved. Source/config/test fingerprint: `438681d99c35f10fe396d11894e408b90f54bc83c68dcc0cfb67e7fbf2993d06` (631 files; scope and hash method in `artifacts/verification/2026-11-10-final/source-fingerprint.txt`). Inventory: 116 modified/deleted status paths, 29 untracked status entries containing 57 files; full status and untracked file lists are saved in `artifacts/verification/2026-11-10-final/git-status.txt` and `untracked-files.txt`. Runtime: project Python 3.12.13 (system Python 3.14.4), Node 24.18.0, Next 16.4.4, PostgreSQL 16-alpine task-owned container `94679c0ac8c11694e922b573e1c95e00b051b31a05cbce244c88aa3dc79044c`; database migration head `0013_social_call_asset_index`, 27 ORM tables. No production database, real Solana source, real Telegram recipient, or live execution was used.

| Exact command | Exit | Result / duration | Scope and limit |
| --- | ---: | --- | --- |
| `make verify` | 0 | Ruff, mypy 186 files, backend 1,607 passed / 31 deselected / 7 warnings (pytest phase 165.23 s), CSS contract 298 classes, ESLint, TypeScript, Vitest 86 passed, Compose config, secret scan, migration check, local security review and SBOM 564 components passed | Non-integration backend and frontend local gates; total target duration was not separately instrumented. SBOM digest `sha256:36ceb498e0ad0f63a3166b6ca18d359330069cdf729293c33c25b210dfaba0664`. |
| `DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55439/postgres make migrate` | 0 | Migration upgrade/current head `0013_social_call_asset_index`; about 1.1 s | Only task-owned isolated PostgreSQL; container and data retained. |
| `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55439/postgres make integration-test` | 0 | 31 passed, 2 warnings; 7.09 s | PostgreSQL 16; no production data. |
| `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55439/postgres .venv/bin/python -m pytest tests/integration/test_telegram_worker_path.py -q` | 0 | 2 passed; 1.28 s | Composed Telegram state/outbox path with mocked HTTP; not real Telegram delivery. |
| `./node_modules/.bin/playwright test --workers=2` (from `apps/web`) | 0 | 44 passed, 4 skipped; 48 total; approximately 5.7 min | Full browser suite across desktop/laptop/tablet/mobile; authenticated-only scenarios skipped. Theme hydration regression passed with no React hydration error. Frontend source did not change after this run. |
| `npm run build` (from `apps/web`), also run by final Docker build | 0 | Next.js 16.4.4 production build passed | Final web image built from current app source. |
| `docker compose --project-name memeradar-validation-build-20261110 -f infra/compose/docker-compose.yml build api worker web` | 0 | Three task-owned images built | API/worker include current Debian package upgrades; web runtime removes unused npm/npx. |
| Bounded `docker run` + runtime checks on `memeradar-validation-build-20261110-web:latest` | 0 | Server ready; internal HTTP 200; `/app/server.js` present; npm/npx absent; container stopped afterward | Validates only the web image runtime, not the full production Compose stack. |
| `make security-review-external` | 0 | External dependency/config review PASS: pip-audit, production npm audit and Trivy config scan | Full npm audit separately reports 8 moderate development-only findings through minimatch; production dependencies have no reported vulnerabilities. No compatible safe lockfile fix was available without an unrelated Next major downgrade. |
| `pip-audit --no-deps --disable-pip -r requirements.lock` | 0 | No known Python dependency vulnerabilities | Lock is fully pinned; dependency resolution was disabled. |
| `npm audit --omit=dev --audit-level=high` | 0 | 0 production dependency vulnerabilities | Full development dependency graph is a separate result. |
| `npm audit --audit-level=high` | 0 | 8 moderate development-only findings through `minimatch` under `@typescript-eslint/typescript-estree` | Advisory: [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249). The only offered audit fix downgraded `eslint-config-next` to 15.5.29 from Next 16; no downgrade was applied. |
| `trivy image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL ...` (API/worker/web; JSON reports under `artifacts/verification/2026-11-10-final/`) | API 1; worker 1; web 0 | API 47 HIGH, worker 47 HIGH, zero CRITICAL, no fixed versions in current Trivy feed; web 0 findings | Python findings are Debian OS packages; `apt-get upgrade` reduced each Python image from 49 to 47 HIGH. These images do not pass the HIGH threshold. |
| `make compose-prod-config` | 2 | Blocked on absent deployment configuration | Requires actual `ADMIN_API_TOKEN`, `DATABASE_URL`, `OPERATOR_API_TOKEN`, `REDIS_URL`, `VIEWER_API_TOKEN`, Postgres user/password, and API base URLs; no fake values supplied. |
| `git diff --check` | 0 | No whitespace errors in tracked diffs | Final check after documentation edits. |
| Markdown relative-link/trailing-whitespace check | 0 | 10 authoritative edited docs checked; 0 errors | Read-only validation of current canonical reports. |
| Untracked-file secret scan | 0 | 57 untracked files scanned, 0 high-confidence findings | Uses repository `scan_files`; reports no secret values. |

## Product acceptance matrix — final checkpoint

| Capability | Implementation | Worker composition | PostgreSQL | Local E2E | Restart | External | Final status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Launch discovery | PASS | PASS | 31 integration tests | Deterministic fixture path | Worker restart NOT_RUN | Real provider BLOCKED | PARTIAL |
| Program/instruction identity | PASS | PASS | Fixture/reconciliation tests | Deterministic | NOT_RUN | Historical source BLOCKED | PARTIAL |
| Stream-gap recovery | PASS | PASS | 31 integration tests | Synthetic gaps/replay | Component recovery only | Provider coverage BLOCKED | PARTIAL |
| Source coverage | PARTIAL | PARTIAL | No complete coverage ledger | No observable-universe denominator | NOT_RUN | Provider range BLOCKED | PARTIAL |
| Candidate safety | PASS locally | PASS | Persistence contracts pass | Fixture path | NOT_RUN | Live evidence BLOCKED | PARTIAL |
| Candidate scoring | PASS; caller feature shadow-only | PASS | Existing snapshots persisted | Point-in-time fixture/replay | Replay tested | Predictive value NOT_PROVEN | PARTIAL |
| Social collection | PASS | PASS, opt-in | PostgreSQL persistence tests pass | Fixture provider | Full worker restart NOT_RUN | Live provider BLOCKED | PARTIAL |
| Caller conduct | PASS, versioned projection | PASS into early feature snapshot | Social persistence passes; projection verified by unit/replay | Point-in-time test path | Replay tested | Real cohort NOT_PROVEN | PARTIAL |
| Telegram eligibility | PASS | PASS | Composed integration passes | Mock path | Full worker restart NOT_RUN | Recipient BLOCKED | PARTIAL |
| Telegram delivery | PASS with mock HTTP | PASS | Focused worker PG: 2 passed | Mock acknowledgement | Delivery state persists; full worker drill NOT_RUN | Real Telegram BLOCKED | PARTIAL |
| Ambiguous-delivery recovery | PASS, no blind retry | PASS | Focused worker PG: 2 passed | Timeout/ack cases mocked | Unknown state durable; ambiguous external result cannot be reconciled | Telegram has no shared PG transaction/idempotency proof | PARTIAL |
| Pre-identity diagnostics | PASS, atomic gap+diagnostic | PASS through coordinator | 31-test suite passes | Injected rollback/replay | Repair replay tested | Provider coverage BLOCKED | PARTIAL |
| Pre-identity reconciliation | PASS for one exact late identity | PASS, bounded loop | Persistence tests pass | Deterministic fixtures | Replay tested | Provider re-fetch BLOCKED | PARTIAL |
| Historical correction | PASS, read-only CLI | Not a worker | Isolated fixture DB only | Fixture inventory | NOT_RUN | Verified production history unavailable | BLOCKED |
| Paper entry | Service and ledger pass; no restart-safe decision consumer | FAIL, no worker | Ledger persistence contracts pass | No composed runtime path | NOT_RUN | NOT_RUN | OPEN |
| Paper exit | Exit logic exists; no composed paper lifecycle | FAIL, no worker | NOT_RUN as worker | No composed path | NOT_RUN | NOT_RUN | OPEN |
| Outcome tracking | Bounded forward collector exists | PASS for collection | Integration contracts pass | Fixture outcomes | Worker restart NOT_RUN | Independent outcomes NOT_PROVEN | PARTIAL |
| Research validation | Point-in-time/replay infrastructure | Forward snapshots composed | Fixtures only | No independent cohort | NOT_RUN | NOT_PROVEN | NOT_PROVEN |
| Database restart | Durable component contracts | No full app restart | 31 integration tests; prior isolated unknown-row restart evidence | No current DB restart in this checkpoint | Full DB restart NOT_RUN | N/A | PARTIAL |
| Worker restart | Individual state contracts | Full multi-worker drill absent | No restart drill | NOT_RUN | NOT_RUN | N/A | BLOCKED |
| Security | Local and external config/dependency reviews pass; image scans report findings | N/A | N/A | Web runtime smoke passes | N/A | API/worker 47 HIGH each; web 0; npm dev moderate residual | PARTIAL |
| Frontend | UI and theme behavior verified | API-backed route contracts | Backend tests separate | 86 unit; 44 browser pass / 4 skip | N/A | N/A | PASS locally |

Scientific and external product readiness remain separate: the local engineering gates do not establish real source completeness, real Telegram receipt, paper-worker operation, or predictive alpha. Current 2x–100x outcome metrics remain `NOT_PROVEN`.

### Telegram Bot API reconciliation limit

The current official [`sendMessage` contract](https://core.telegram.org/bots/api#sendmessage) returns the sent `Message` on success (including its message identifier), but its documented parameters define no client-supplied idempotency key. The official [`getUpdates` contract](https://core.telegram.org/bots/api#getupdates) retrieves incoming `Update` objects, retained for no more than 24 hours; it does not provide an outgoing-message lookup by request identity. Therefore a received success response is a positive receipt, but a lost response after possible submission cannot be reconciled through the Bot API with the logical alert key. `DELIVERY_UNKNOWN` and the no-blind-retry policy remain necessary; this is a PostgreSQL/Telegram boundary limitation, not a local test gap.

### Exact image and runtime commands

The final image scan command was run once for each image:

```sh
trivy image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL --format json --output artifacts/verification/2026-11-10-final/trivy-api-after.json memeradar-validation-build-20261110-api:latest
trivy image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL --format json --output artifacts/verification/2026-11-10-final/trivy-worker-after.json memeradar-validation-build-20261110-worker:latest
trivy image --scanners vuln --exit-code 1 --severity HIGH,CRITICAL --format json --output artifacts/verification/2026-11-10-final/trivy-web-after.json memeradar-validation-build-20261110-web:latest
```

The API/worker commands exit 1 at the configured HIGH threshold; JSON contains 47 Debian OS findings each, with no CRITICAL and no `FixedVersion` in the current Trivy feed. The web scan exits 0 with no vulnerabilities. Earlier reports without `-after` preserve the pre-fix comparison.

The rebuilt web image smoke used container `memeradar-validation-web-20261110`:

```sh
docker run -d --name memeradar-validation-web-20261110 -e HOSTNAME=0.0.0.0 memeradar-validation-build-20261110-web:latest
docker exec memeradar-validation-web-20261110 sh -c 'test -f /app/server.js && ! command -v npm && ! command -v npx'
docker exec memeradar-validation-web-20261110 node -e 'async function go(){for(let i=0;i<30;i++){try{const r=await fetch("http://127.0.0.1:3000"); console.log("http_status",r.status); process.exit(r.ok?0:1)}catch(e){await new Promise(r=>setTimeout(r,1000))}} console.error("web server did not become ready"); process.exit(1)} go()'
docker stop memeradar-validation-web-20261110
```

HTTP returned 200; only the task-owned web test container was stopped. The task-owned PostgreSQL container remains running and retained.

## Historical checkpoint — 2026-11-09

Environment: dirty local checkout, `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; changed source/config/test fingerprint `c831d0950e52a4686be07a4986aa3c589df0cc3963cecf4429540a67b396bd35` across 102 files. Python 3.12.13, Node.js 24.18.0, Next.js 16.4.4. The isolated PostgreSQL 16 test container is retained but stopped. Protected operating modes remain analysis-only/paper-only.

| Gate / exact command | Exit | Result | Scope and limit |
| --- | ---: | --- | --- |
| `.venv/bin/python -m pytest -q -m 'not integration' --no-cov` | 0 | 1,583 passed, 31 deselected, 7 warnings; 363.24 s | Full backend run before the final added invalid-chat test; production code was unchanged. |
| `.venv/bin/python -m pytest tests/unit/test_telegram_provider.py -q --no-cov` | 0 | 6 passed; 1.14 s | Re-run after adding invalid-chat 400 rejection coverage. |
| `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:32771/memeradar_test .venv/bin/python -m pytest tests/integration -q --no-cov` | 0 | 31 passed, 2 warnings; 20.45 s | Isolated PostgreSQL 16; no production database. |
| `MEMERADAR_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:32771/memeradar_test .venv/bin/alembic -c alembic.ini upgrade head` | 0 | Migration upgrade completed | Test database only. |
| `make lint` / `make typecheck` | 0 / 0 | Ruff passed; mypy clean for 185 source files | Local gates. |
| `make frontend-lint` / `make frontend-typecheck` | 0 / 0 | ESLint and TypeScript passed | Local gates. |
| `npm run test -- --maxWorkers=2` (from `apps/web`) | 0 | 86 passed, 25 files | Default-parallel run under competing jobs timed out in five tests; bounded-worker rerun passed all tests. |
| `npm run test:e2e -- --workers=2` (from `apps/web`) | 0 | 40 passed, 4 skipped, 44 total; 5.7 min | Local Next server, no API/provider credentials. Skips are authenticated-only cases. Theme hydration mismatch warnings appeared during theme-switching visual coverage. |
| `make frontend-css-contract` | 0 | 298 static classes checked across 62 files | First run found missing `.scan-monitor`; the selector was added and rerun passed. |
| `make frontend-build` | 0 | Next.js production build completed; `/scan-monitor` included | Final CSS source. |
| `make migration-check` | 0 | One head, `0012_stream_gap_diagnostics`; 27 ORM tables | Static migration consistency check. |
| `make compose-config` | 0 | Regular Compose configuration valid | Does not start services. |
| `make compose-prod-config` | 2 | Required production variables unset (`DATABASE_URL`, tokens, database password, API/Redis URLs) | Blocked environment; no placeholder secrets supplied. |
| `make secret-scan` / `make security-review` | 0 / 0 | No findings; local review PASS, protected modes verified | Review reports container, npm and pip external scans `NOT_RUN`. |
| `make sbom` | 0 | 564 components; digest `sha256:f138fcf1ad8dc6af75568dc5f0e8b43d2d6b5fd9343d23885bf3bf5720414082` | Lock-derived local SBOM. |
| `git diff --check` | 0 | No whitespace errors | Dirty worktree retained. |

The isolated DB row count for `alerts.state='DELIVERY_UNKNOWN'` was 3 before and 3 after restarting the task-owned PostgreSQL container. The `AlertDeliveryService` restart test also confirms an ambiguous logical send is not automatically resent; this verifies durable state, not actual Telegram delivery or every worker's restart behavior.

| Acceptance level | State | Evidence |
| --- | --- | --- |
| Unit / contract | PASS | 1,583 backend tests and 86 frontend tests. |
| PostgreSQL integration | PASS | 31 integration tests plus restart row-count check. |
| Composed local E2E | PASS | Mock Telegram outbox/provider integration and 40 browser E2E tests. |
| External Telegram delivery | BLOCKED_EXTERNAL | No authorized test recipient or real Telegram request in this run. |
| Real Solana provider recovery | BLOCKED_EXTERNAL | No bounded live provider recovery executed; provider coverage is not accepted. |
| Full worker crash/restart | PARTIAL | Telegram delivery state survived a service/database restart; full multi-worker recovery drill not run. |

### Current operational scenario matrix

| Scenario | Producer | Consumer | Database state | Tests | Runtime result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Valid Solana launch | Raw transaction source | Canonical decoder / early runtime | Observation and candidate stores | Raw stream/worker unit and PostgreSQL contracts | Fixture composition only; no provider stream | PARTIAL |
| Foreign program | Launch event decoder | Pump.fun classifier/report | Original source evidence retained | Reconciliation and launch predicate tests | Rejected locally | PASS |
| Conflicting trade label | Buy/trade instruction | Launch classifier | No corrected launch projection | Conflicting-label regression | Excluded locally | PASS |
| Duplicate launch | Replayed signature/instruction | Canonical stream store | Deduplicated identity | Stream unit and PostgreSQL tests | Deterministic replay tested | PASS |
| Stream interruption | RPC/WebSocket source | Gap coordinator | Failed-slot gap and bounded diagnostic | Stream and pre-identity PostgreSQL tests | Synthetic failure only | PARTIAL |
| Stream recovery | Backfill/replay | Canonical decoder/coordinator | Gap stays unresolved until evidence | Stream recovery tests | No live provider range recovered | BLOCKED_EXTERNAL |
| Social observation | Bounded social worker | Collector/repository | Observation, provider cursor and poll marker atomic | Social unit and PostgreSQL tests | Fixture provider; restart/rollback covered | PASS |
| Social checkpoint failure | Page persistence | Unit of work | Observations/cursor roll back together | PostgreSQL write-failure tests | Isolated database | PASS |
| Caller analysis | Stored social calls | Caller conduct/scoring | No runtime projection | Analyzer unit tests only | Not composed into scoring | FAIL |
| Qualified Telegram alert | Candidate transition | Durable outbox → mock Telegram adapter | Alert and receipt persisted | Composed PostgreSQL/mock HTTP test | Local mock delivery | PASS |
| Telegram timeout/429/auth/malformed acknowledgement | Telegram adapter | Delivery state machine | Unknown/retry/suppression persisted by outcome type | Provider and alert tests | Mock transport only | PASS |
| Invalid Telegram chat | Telegram adapter | Delivery rejection state | Explicit HTTP 400 rejection; not treated as a successful send | `test_telegram_adapter_classifies_invalid_chat_as_definite_rejection` | Mock transport only | PASS |
| Telegram retry/restart | Outbox worker | Recreated service/processor | Logical identity and unknown state retained | PostgreSQL service restart test | Unknown is not resent automatically | PASS |
| Pre-identity rejection | Raw source | Diagnostic store/reconciler | Bounded diagnostic and projection persisted | Unit and PostgreSQL tests | No provider re-fetch | PARTIAL |
| Missed-winner reconciliation | Rejection/coverage ledger | Research cohort | No complete observable denominator | No complete cohort test possible | Outcomes not independently matured | NOT_PROVEN |
| Eligible paper entry | ENTRY_READY decision | Shadow entry / paper ledger | Ledger repositories exist | Shadow/paper unit and PostgreSQL contracts | No worker composition | FAIL |
| Rejected paper entry | Ineligible decision | Shadow entry policy | Fixture ledger only | Unit tests | Local rejection contract | PARTIAL |
| Worker restart | Persisted outbox/social/stream | Worker/service recreation | Three unknown-delivery rows survived DB restart | PostgreSQL service restart and row count | Full worker recovery not exercised | PARTIAL |
| Historical cohort reconciliation | Historical raw events | Read-only inventory/report | Source rows unchanged in fixture | Reconciliation unit/PostgreSQL tests | No verified production history source | BLOCKED_ENVIRONMENT |
| Real Telegram receipt | Fresh eligible event | Telegram API | No live receipt | Not run | No authorized test recipient supplied | BLOCKED_EXTERNAL |

## Earlier checkpoint evidence (historical)

Environment: local dirty checkout, Python `.venv`, no isolated PostgreSQL URL. No clean commit identity or real provider acceptance is claimed.

| Command | Result | Scope |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q --no-cov tests/unit/test_social_call_collection.py tests/unit/test_pumpfun_forward_evidence.py tests/unit/test_early_worker_pipeline.py tests/unit/test_pumpfun_live_acceptance.py tests/contract/test_extension_e2_5_pumpfun_lifecycle.py` | exit 0; 24 passed | Focused fixtures, not live E2E. |
| `.venv/bin/python -m pytest -q --no-cov tests/unit/test_social_call_collection.py tests/unit/test_pumpfun_forward_evidence.py tests/unit/test_stream_integrity.py tests/unit/test_shadow_entry.py` | exit 0; 41 passed, before final instruction-label fix | Focused fixtures, not live E2E. |
| `make lint` | exit 0 | Python Ruff. |
| `git diff --check` | exit 0 | Whitespace only. |
| `make migration-check` | exit 0; one head `0012_stream_gap_diagnostics`, 27 tables | Static check only. |
| `make integration-test` | exit 0, explicitly skipped | Isolated PostgreSQL URL unset; not a pass. |
| `make compose-config` | exit 0 | Configuration only, no runtime services. |
| `cd apps/web && npm test -- --run` | exit 0; 86 passed, 25 files | Frontend unit tests, no browser E2E. |

The full composed scenarios A–J and real Telegram delivery are not accepted. Historical observations, external provider reliability, PostgreSQL concurrency/restart and browser workflows require their own tests and evidence.

Additional current checks: `make frontend-lint frontend-typecheck` exited 0; `make typecheck` exited 0 (183 source files); `make lint` exited 0. A full non-integration diagnostic `timeout 240 .venv/bin/python -m pytest -q -m "not integration" --no-cov` reached over 80% and timed out (exit 124), with no final test count.

A dedicated Docker PostgreSQL 16 container was migrated using `MEMERADAR_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:32768/memeradar_retest .venv/bin/alembic -c alembic.ini upgrade head` (exit 0). `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:32768/memeradar_retest .venv/bin/python -m pytest tests/integration -q --no-cov` initially failed one qualified-read test after fixture corrections; after the liquidity snapshot fix, it exited 0: 22 passed, 2 warnings. This proves those integration contracts against the isolated database, not a production restart drill. The task-owned container and test databases are retained; network authentication was changed to reject TCP after testing.

A subsequent longer run, `timeout 600 .venv/bin/python -m pytest -q -m "not integration" --no-cov`, exited 0: 1,550 passed, 22 deselected, 7 warnings in 343.12 seconds. Standalone `scripts/secret_scan.py` and `make security-review sbom` were interrupted (exit 130); no standalone scan result is claimed.

## Operational acceptance matrix — continuation

| Scenario | Producer | Consumer | Database state | Tests | Runtime result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Valid Solana launch | Raw source | Canonical decoder / early runtime | Existing observation and candidate stores | Raw stream and early worker fixtures | Local fixture path | PARTIAL |
| Foreign program | Registry / reconciliation | Forward report | Original preserved | Reconciliation fixtures | Excluded from corrected report | PASS |
| Conflicting trade label | Source observation | Launch predicate | Original preserved | Forward evidence regression | Excluded locally | PASS |
| Duplicate launch | Canonical decoder | Stream store | Event identity dedupe | Stream integrity tests | Deterministic fixtures | PARTIAL |
| Stream interruption | WebSocket | Source / coordinator | Failed-slot gap and diagnostic | Raw-stream tests | Local synthetic failure | PARTIAL |
| Stream recovery | Backfill | Coordinator | Gap/verification tables | Stream and PostgreSQL tests | Real provider not exercised | BLOCKED_EXTERNAL |
| Social observation | Opt-in worker | Social adapter and repository | Page/cursor transaction | Social worker and PostgreSQL tests | Fixture provider | PARTIAL |
| Social checkpoint crash | Collector | Database transaction | Calls and cursor roll back together | PostgreSQL rollback test | Local isolated database | PASS |
| Caller analysis | Existing analyzer | Research/scoring | No runtime projection | Isolated unit tests | Not composed | FAIL |
| Qualified Telegram alert | Early runtime | Outbox worker / adapter | Outbox and AlertRow | PostgreSQL mock HTTP integration | One mocked send | PARTIAL |
| Telegram delivery failure | Adapter | Delivery service | Retry metadata / suppressed alerts | Alert/provider unit tests | Real transport not exercised | PARTIAL |
| Telegram retry/recovery | Outbox | Recreated processor | Durable outbox | PostgreSQL mock restart test | Logical replay checked | PARTIAL |
| Pre-identity rejection | Raw source | Diagnostic sink / coordinator | Bounded observation and gap | Unit and PostgreSQL tests | Local fixture | PARTIAL |
| Missed-winner reconciliation | Not composed | Research | No independent universe | Existing research tests only | No complete reconciliation | FAIL |
| Eligible paper entry | ShadowEntryService | Paper engine | Ledger available | Unit tests | Worker not composed | FAIL |
| Rejected paper entry | ShadowEntryService | Paper engine | Local test ledger | Unit tests | Safe rejection tested | PARTIAL |
| Worker restart | Stream coordinator / outbox | Recreated coordinator/processor | Isolated PostgreSQL | Gap and mock Telegram restart tests | Partial component restart | PARTIAL |
| Historical cohort reconciliation | Read-only inventory CLI | Forward report | Source rows unchanged | Fixture and isolated PostgreSQL tests | Real data not inventoried | PARTIAL |

Continuation commands: `timeout 600 .venv/bin/python -m pytest -q -m 'not integration' --no-cov` exited 0, 1,566 passed / 26 deselected / 7 warnings; this run began before the final stream-gap changes, which were checked separately. `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:32769/memeradar_test .venv/bin/python -m pytest tests/integration -q --no-cov` exited 0, 27 passed / 2 warnings after stream isolation correction. `make lint` and `make typecheck` exited 0 (185 source files); `make sbom` exited 0 (564 components); standalone `timeout 420 .venv/bin/python scripts/secret_scan.py` exited 0. An earlier full PostgreSQL run failed because cross-stream gaps leaked into another coordinator; the final run passed after the fix. No real Telegram message was sent.

Final focused stream/pre-identity command `.venv/bin/python -m pytest -q --no-cov tests/unit/test_stream_integrity.py tests/unit/test_pre_identity_rejection.py tests/unit/test_solana_raw_stream.py` exited 0: 39 passed. The standalone secret scan does not automatically cover untracked files; an explicit `scan_files` pass over the new untracked source/test files exited 0 with zero findings. The task-owned PostgreSQL container and its test database are retained with TCP access set to reject.

`timeout 420 make security-review` exited 0: local security review PASS, including tracked/artifact/history secret checks and protected modes. External container, npm and Python vulnerability scans were not run by this review and remain unaccepted. `make sbom` exited 0. The isolated test database was retained with TCP connections rejected after testing.
