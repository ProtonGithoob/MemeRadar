# M0: runtime and PostgreSQL baseline (2026-11-24)

**Plan:** [Early Alpha Intelligence Implementation Plan, M0](../superpowers/plans/2026-11-25-memeradar-early-alpha-intelligence.md)

**Run ID:** `2026-11-24-m0`

**Evidence bundle:** `artifacts/verification/2026-11-24-m0/`. The bundle is gitignored and stays local to the run. Its digests are listed in the last section.

## Source and environment identity

| Item | Value |
| --- | --- |
| Branch | `claude/exciting-brahmagupta-0k7pds` |
| Starting SHA | `5b85710` (plan commit), clean tree |
| Verified SHA | `7a1e8eb` (M0 fixes), clean tree |
| Python / Node | 3.13.18 / v22.23.4 |
| PostgreSQL / Redis | 16.15 (isolated local cluster, port 55433) / 7.0.15 (port 56380) |
| `requirements.lock` sha256 | `099788b2…8de2` |
| `apps/web/package-lock.json` sha256 | `7cc286ec…3d31` |
| Protected modes | `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` (`.env.example`, backup drill `protected_modes`) |

No connection secret was printed; local URLs use trust auth on a disposable cluster. The operator's Compose database was not touched.

## Results

| Check | Command | Exit | Result |
| --- | --- | --- | --- |
| Declared verification | `make verify` at `7a1e8eb` | 0 | Backend 1,789 passed / 34 integration deselected; frontend 91/91 in 25 files. Lint, mypy, CSS contract, frontend lint and typecheck, compose config, secret scan, migration check, security review and SBOM all passed. |
| Migration graph | `make migration-check` | 0 | Single head `0015_stream_verification_provenance`, 27 ORM tables. Recorded separately from the PostgreSQL upgrade. |
| Fresh upgrade | `alembic upgrade head` on empty `m0_fresh` | 0 | Revision `0015`, 27 tables. |
| Previous schema to head | `alembic upgrade 0014`, seed a legacy `stream_verifications` row, then `alembic upgrade head` on `m0_prev` | 0 / 0 | Revision `0015`. The legacy row survives with its new provenance columns `NULL`. The current `PersistedStreamOperations` read path loads the database without error; the legacy row is outside its default window. The previous schema is synthetic at `0014`; the operator's deployed database was not copied. |
| PostgreSQL integration | `make integration-test` with `MEMERADAR_TEST_DATABASE_URL` | 0 | 34/34 passed. Run twice more on the same reused database, both 34/34, to prove repeatability. |
| M0 named suites | early runtime, stream, checkpoint concurrency, paper persistence, Telegram worker path | 0 | 11/11 passed, including paper worker recreation after a committed decision, checkpoint claim concurrency and the Telegram outbox path. |
| Backup/restore | `make backup-restore-drill` from `m0_prev` to an empty `m0_restore` | 0 | `status: PASS`, `restore_verified`, `application_read`, head `0015`, protected modes intact. The seeded legacy row is present after restore. |
| Dependency interruption | Local API (uvicorn) with database and Redis required for readiness | n/a | See the readiness drill below. |

Readiness drill (`readiness-interruption-drill.txt`):

| Step | `/health/live` | `/health/ready` |
| --- | --- | --- |
| Baseline | 200 | 200 ready |
| PostgreSQL stopped | 200 | 503 `database: unreachable` |
| PostgreSQL restarted | 200 | 200 ready |
| Redis stopped | 200 | 503 `redis: unreachable` |
| Redis restarted | 200 | 200 ready |

## Defects found and fixed in M0

1. **Worker loops slept through shutdown (P1, operational).**
   - **Symptom:** `test_composed_paper_worker_consumes_committed_decision_after_recreation` failed on every earlier run.
   - **Cause:** these loops ignored the stop signal while sleeping:
     - the paper exit monitor (30 s);
     - pre-identity reconciliation (30 s);
     - the lifecycle watch (10 s);
     - Telegram command intake (5 s).

     Worker shutdown could therefore outlive Docker's 10 s stop grace period, and the worker was killed mid-cycle.
   - **Fix:** `sleep_until_stopped` (`apps/worker/src/memeradar_worker/operations_jobs.py`), with unit tests.
2. **Non-repeatable PostgreSQL test.**
   - **Symptom:** `test_position_read_postgres` failed on a reused database.
   - **Cause:** it used a fixed mint, which violated the unique `(chain, mint)` token constraint.
   - **Fix:** derive a per-run mint.

## G0 assessment

**Current-source local scope: PASS.** This covers declared checks, PostgreSQL fresh and previous-schema upgrade, restart and retry and ledger/outbox idempotency in the integration suites, backup/restore, dependency readiness, and zero mode violations.

**Still open:**
- **Bounded-traffic worker drill.** Stream-gap, processing-latency, queue-delay and persistence-failure counters under a database or Redis interruption have not been measured. This needs the worker running live ingestion, which is unavailable in this sandbox (no Docker daemon for Compose). Owner: operator or platform, on the Compose host.
- **Upgrade of the operator's actual deployed database.** Take a copy of the operator's database, run the drill on it, and record the resulting revision.
- **Not in M0 scope:** real Telegram receipt (G5), image builds and `frontend-build` (G6 release gates).

## Artifact digests (sha256)

```
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  alembic-fresh-upgrade.log
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  alembic-prev-0014-to-head.log
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  alembic-prev-0014.log
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  alembic-upgrade.log
    9c8d81c91ceec6c34e2cf8af6a9aef80668ecdf466e8d938a891f3ed2f4accd4  make-backup-restore-drill.log
    d2baeb94f304df5074bdbe8b61bb17fb63bc0e3b277626e01d952d710d5905b8  make-integration-test-final.log
    1af180b34bcf2b3958281c9406d69d1aff978f9cbe5b98174c67652ec4a728b7  make-integration-test-run1.log
    239c157181479983f5cf7106fcdace8ee71a3dd9f0b190c690a57ff8cc0197c4  make-integration-test-run2.log
    fb2e0b387d651638f65953f0b3c0f10b192b0ce132f5d2230fb9d6a343e834a2  make-integration-test.log
    62bde3b8cb6ee0007bcd0ef244d01615fa6a2a10201562cfcd1aca914d333e7d  make-migration-check-final.log
    62bde3b8cb6ee0007bcd0ef244d01615fa6a2a10201562cfcd1aca914d333e7d  make-migration-check.log
    039ab603e59053916a2642cebf161e0fbfacd3a669b8b47cae8e48d5f7e383d3  make-verify-final.log
    07c960e6e80f4d0d4a79a9b8fba75f27da24ccf092499b5e1d61d998df285346  make-verify.log
    a488153b4eade72b3d06fdfd61938cc3f7af6168cf3489e8b2452024bb76d95e  mypy.log
    90ec199179eb2792d40648923a4ce536d1632707c8526d5cc2dde27337fce0c8  pytest-integration-postgres.log
    879019836dd810178caec9192d3a85f7aa1ea71bdec99a604f459cdff0ecd14e  pytest-m0-named-integration.log
    69ea7ee04f3fd72cec58644bb2e1769ab532b48025a68b998c5a64c5c918424e  pytest-unit.log
    82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18  ruff.log
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  secret-scan.log
    7a732d0018601ab99c1bfeca2984dea46d31f57939d5f4056f38a4a59369d499  exit-codes.txt
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  git-status.txt
    a80fd18bf13146c226dd256992b08f41750dc71c9f94d82096daff457b4f527d  legacy-row-read.txt
    e4fb587cf201ef2772765f2ebd66fc9189c8d62d513c293b7db3d1f43aefaaee  postgres-revisions.txt
    160a5a58d0beae44b4097c2183e59bcc1f1b7579f7f030b8b8e919c198b8f8fd  readiness-interruption-drill.txt
    60ba0755ddb2539b26614f152648597efc735c147fbcbed7e7a7c618ea05840f  source-identity.txt
    c4ec1ac264605a73a8be9cb31f83ffc42b350323fc744605996d507ebd423ece  source-sha.txt
    88aee8131f8eb3f455f88c1a07c84c97fdcf9ae8ab17cba7e30cb574ecb5def7  backup-restore-drill.json
```
