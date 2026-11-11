# Recursive acceptance report

## Authoritative P30 final-source checkpoint — 2026-11-11

Branch `main`, HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`, dirty worktree preserved. Source fingerprint `97e36f90571212c774b8827a2672a4f1a3137f5c39cdfaf3c12f4a1f2cbfe6e8` covers 641 files / 8,385,898 bytes; manifest recheck: zero mismatches and zero missing files. No commit, reset, clean, remote operation, production database write or volume removal occurred.

| Gate | Current evidence | Status / limit |
| --- | --- | --- |
| `make verify` | Exit 0; 1,650 backend passed / 34 integration deselected / 7 warnings in 406.61s; 86 frontend passed; Ruff, mypy 187, ESLint, TypeScript, CSS, Compose, local secret/security, migration graph (`0015_stream_verification_provenance`) and SBOM passed. Log `artifacts/verification/2026-11-11-final/make-verify-p30.log`, SHA-256 `9ab4ced53531fc3a24b1e62c24e03d97bd4bf7a9fca566641a2f60168d352c15`. | PASS for declared local scope; PostgreSQL is excluded. |
| Stream verification provenance | Provider, program scope, commitment, method and attempt are retained/projected where known; absent values stay UNKNOWN. | Local traceability improved; total source/subscription coverage remains UNKNOWN. |
| PostgreSQL | 34 integration tests deselected; migration graph checked, not applied. Test URL unset, local binaries absent, Docker API denied. | BLOCKED_ENVIRONMENT. |
| Browser/build | Browser server bind failed with sandbox `EPERM`; production bundle compiled but Next TypeScript child output was unavailable. | BLOCKED_ENVIRONMENT; typecheck inside `make verify` passed. |
| Security scans | Local secret/security review and SBOM passed; external npm/pip/container scans NOT_RUN. Historical API/worker Trivy findings were 47 HIGH each. | PARTIAL; no P30 rescan. |
| Runtime/external | No current worker restart, authorized source recovery, Telegram receipt or verified production historical inventory. | BLOCKED / NOT_VERIFIED. |
| Alpha | No independent mature cohort or chronological performance metrics. | NOT_PROVEN; no 10x–100x claim. |

See [E2E acceptance](E2E_ACCEPTANCE_REPORT.md), [latest issue grid](PRODUCT_ISSUE_GRID_LATEST.md), [final product readiness](FINAL_PRODUCT_READINESS.md) and the verification ledger.


## Historical P29 final-source checkpoint — 2026-11-11

This section is authoritative for the P29 dirty worktree; older inventories and continuation tables below are preserved as historical evidence. Branch `main`, HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`, source fingerprint `2a10b8229e4be28fbe3e54a4b24a23128f01640e609be97bef542a6e9ff461cd` (640 files). The worktree remains dirty; no commit, reset, clean, production database write or volume removal occurred.

| Gate | Current evidence | Status / limit |
| --- | --- | --- |
| `make verify` | P29 exit 0; 1,648 backend passed, 34 integration deselected, 7 warnings; 86 frontend passed; Ruff, mypy 187 files, ESLint, TypeScript, CSS, Compose, local secret/security checks, migration graph (`0014_stream_gap_recovery_claims`) and SBOM pass. | PASS for declared local scope. PostgreSQL is excluded. |
| Focused P07 | Final paper/backtest/worker/domain suite: 92 passed. | PASS locally; quote-unit regression fixed and the standard paper engine still rejects display-unit quotes. |
| Isolated PostgreSQL integration | Historical run at migration `0013_social_call_asset_index`: 32 passed, 2 warnings; focused Telegram worker integration: 2 passed. P29 recovery slice skipped 2 PostgreSQL cases. | Historical only; current claim race, migration and restart are blocked because DB URL/binaries are absent and Docker API is denied. |
| Browser | Historical Playwright matrix: 44 passed, 4 skipped. Current attempt exited before tests because local server listen returned EPERM. | Historical browser evidence only; P29 browser acceptance BLOCKED_ENVIRONMENT. |
| Production build | P29 optimized bundle compiled, then Next TypeScript config discovery failed to parse child-process output; direct tsc config parsing and typecheck pass. | BLOCKED_ENVIRONMENT; no current-source build pass. |
| External security | P29 local security review passed; container/npm/pip scans NOT_RUN. Historical Trivy: API/worker 47 HIGH OS findings each. | PARTIAL; external image/dependency findings need a rerun in a capable environment. |
| Runtime images | Rebuilt web image returns HTTP 200 and has no npm/npx; Trivy: web 0 findings, API 47 HIGH OS findings, worker 47 HIGH OS findings, no CRITICALs/fixed versions in feed. | PARTIAL; Python base-image risk remains. |
| Production Compose | `make compose-prod-config` exit 2 due missing deployment values. | BLOCKED_ENVIRONMENT; no fake secret values supplied. |
| Product external acceptance | No authorized Solana provider run, real Telegram recipient, verified production history, complete observable universe or full multi-worker restart. | BLOCKED / NOT_PROVEN as applicable. |
| Paper worker | Durable decision consumer and persisted-position exit monitor are composed conditionally; explicit policy and provisioned PAPER/SOL portfolio are required. | Implemented locally; final-source PostgreSQL worker recreation, caps and restart acceptance remain open. |
| Scientific result | No independent mature cohort, outcomes or chronological baseline metrics. | NOT_PROVEN; no 10x–100x probability claim. |

See [E2E acceptance](E2E_ACCEPTANCE_REPORT.md), [latest issue grid](PRODUCT_ISSUE_GRID_LATEST.md), and [final product readiness](FINAL_PRODUCT_READINESS.md) for the detailed matrix and source-level residual risks.

Updated: 2026-10-24T07:39:48Z. Source context: canonical repository `/home/ubra/codex/MemeRadar`, branch `main`, HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`. The worktree is dirty and this is not a clean-source release binding.

## Resolved local defects

| Issue | Root cause | Fix | Evidence | State |
| --- | --- | --- | --- | --- |
| Order-claim metadata diverged from migration 0010 | ORM represented the claim as a named unique constraint while the migration creates a named unique index. | ORM now declares the matching index; regression asserts the contract. | `tests/unit/test_paper_persistence_contract.py`; included in final `make verify` (exit 0). | Unit verified; not committed because Git metadata is host-read-only. |
| Concurrent initial runtime-settings mutation could race | `SELECT FOR UPDATE` cannot lock a nonexistent singleton row; simultaneous first writes could both attempt insert. | PostgreSQL path seeds the singleton with `ON CONFLICT (id) DO NOTHING`, then retains locked read/version/audit logic. | Provider-free contract passed; opt-in PostgreSQL race test exists. Focused run: 1 passed, 2 skipped. | Fix implemented; live concurrency acceptance blocked on isolated PostgreSQL. |
| CI deterministic pytest included integration cases before DB migration | The ordinary test target did not exclude integration marker; hosted workflow later has explicit migration/integration phase. | Make/test and CI workflow now separate deterministic tests from integration and keep the DB phase explicit. | `make verify` exit 0; migration graph check. | Locally verified; hosted CI not rerun. |
| Test subprocesses assumed a local `.venv` | CI runner can invoke Python without project-local venv. | Tests use `sys.executable` / configured interpreter. | Focused suites and aggregate pass. | Verified locally. |
| Compose smoke inherited local env interpolation | Test result depended on operator `.env` contents. | Compose contract supplies explicit empty interpolation input and asserts secret preconditions. | Focused suite and aggregate pass. | Verified locally. |
| SQLite timestamp persistence lost UTC awareness / admitted naive timestamps | SQLite strips timezone on reload and bare datetime type did not enforce aware writes. | Existing stabilization introduced `UTCDateTime`, normalizing aware inputs and restoring awareness on read; `ensure_utc` stays strict. | Test coverage included in Python aggregate. | Deterministic verification only; PG timestamp runtime not run. |
| Forward collector used eager fallback and fixture stopped one poll too early | `dict.get` evaluated fallback even when canonical value existed; terminal schedule exhaustion is reported on cycle after the final offset. | Conditional timestamp fallback and correct terminal-cycle fixture. | Focused forward-evidence suite and final aggregate. | Verified. |

## Duplicate repository findings

The full directory inventory is in [`directory-inventory-final.json`](../../artifacts/audit/MemeRadar-consolidation/directory-inventory-final.json), with bundle proofs, patches, status snapshots and logs in the same audit directory. Fifteen sibling directories total 14.552 GiB. None was removed; 0 bytes were reclaimed. The newest snapshot tip is independently preserved by a verified bundle but not in a canonical ref. See [duplicate workspace audit](DUPLICATE_WORKSPACE_AUDIT.md).

The recovery root contains 17 commit objects not present in canonical Git; a verified refs bundle preserves them. The original before-cleanup bundle also verifies. The canonical main HEAD and staged index remained unchanged. Semantic fixes from the newest snapshot are represented in the working tree, but no commit/ref could be created because sandbox policy makes `.git` read-only.

## Verification

`make verify` was directly captured with exit code 0 on the current dirty working tree. Python: 1,529 passed, 21 integration deselected, 7 warnings. Frontend: 83 passed across 24 files. Ruff, mypy (182 files), frontend lint/typecheck, CSS contract, Compose config, secret scan, migration graph, local security review and SBOM passed. Log SHA-256: `c16a3ecc9ab6c4a5cfd2b7ac83340642c16f2a77607b3cbd3c2a92bb4ddb9590`.

Migration graph is `0012_stream_gap_diagnostics` with 27 ORM tables. The separate release snapshot at `12423c3…` has prior identity evidence for migration 0022/40 tables; it is not the current main source. Snapshot `4402fc4…` identity computation succeeded (0022/40 tables) but full verification was not run, so it is not accepted.

## Remaining gates

- **Environment/external:** host permission for canonical Git ref/object writes and sibling access; Docker API/container mounts; isolated PostgreSQL; browser endpoint; live provider access; network-enabled dependency scanners and safe lockfile updates; compatible Next build subprocess host.
- **Product contract:** bounded source/query/request budget before wiring social collection; versioned caller-conduct persistence/read owner; paper portfolio and quote evidence policy; verified pre-identity event family, provisional identity and retention bounds.
- **Evidence/time:** mature independent real chronological outcomes for alpha validation.
- **Optional:** GeckoTerminal, Honeypot, and external wallet-intelligence adapters were not introduced without verified unique need and accepted source contracts.

The complete issue ledger is [`RECURSIVE_ACCEPTANCE_LEDGER.json`](../../artifacts/verification/RECURSIVE_ACCEPTANCE_LEDGER.json). Current product status remains `PARTIALLY_IMPLEMENTED_WITH_EXPLICIT_BLOCKERS`; `READ_ONLY_SHADOW_READY` and `ALPHA_VALIDATED` are not accepted.

## Documentation integrity

The final current-doc check covered 23 authoritative README/status/architecture/security/provider/testing/runbook/audit files: zero broken relative links and zero disposable-path references. A coarse whole-docs scan reported 13 candidate relative-link targets under older historical/report material; that scan includes at least one link-like code example, and the historical targets were not individually repaired or removed. No historical report was rewritten in this pass.

## Current runtime reconciliation — 2026-11-06

| Finding | Documented status | Actual code / wiring | Tests | Status |
| --- | --- | --- | --- | --- |
| Social calls | Collector and SQL repository exist; worker integration open | `social_call_collection.py:134` collector; `repositories.py:748` persistence; no worker call site | Social/caller focused suites included in 43 passing tests | Not operationally wired |
| Caller conduct | Analyzer exists; producer open | `correlation.py:678`; no worker call site | Caller focused tests included in 43 passing tests | Not operationally wired |
| Shadow PAPER | Engine and entry service exist; worker integration open | `paper_execution.py:1234` and `shadow_entry.py:247`; no worker constructor | Shadow focused tests included in 43 passing tests | Not operationally wired |
| Pre-identity rejection | No durable producer/reconciliation read | Current early discovery path and persistence inspection do not establish such a producer | End-to-end reconciliation not run | Open |
| Stream recovery | State machine and persistence seam exist | `early_discovery.py` integrates existing coordinator | Stream focused tests included in 43 passing tests | Deterministic only; runtime not accepted |
| PostgreSQL | Requires isolated database | Test URL absent; `docker info` denied on sandbox socket; existing volumes untouched | Not run | BLOCKED_ENVIRONMENT |
| Quote timing | Future-observed quote previously filled | `QuoteSnapshot.is_fresh_at` used in paper, shadow and discovery | 103 related tests passed | Focused verified; runtime not accepted |
| Security history scan | 120-second diagnostic timed out | Scanner now streams object-by-object, fails closed, invalidates cache when refs change | Earlier full scanner/security suite 12 passed in 150.45s before final follow-up; current full run pending | PARTIAL |

## Earlier continuation evidence — 2026-11-10 (superseded by final-source checkpoint)

| Finding | Previous state | Current code path | Current verification | Remaining acceptance |
| --- | --- | --- | --- | --- |
| Caller conduct | Persisted calls/analyzer lacked early feature consumer | Social collection → `CallerMarketConductAnalyzer` → persisted `caller-conduct-research-v1` projection → early shadow `FeatureSnapshot` with no production weight | Caller/research/runtime slice included in 73 focused passing tests | Live provider timestamps and real-cohort comparative value not available. |
| Pre-identity atomicity | Gap and rejection diagnostic were independent commits | Early source supplies a companion observation; stream persistence writes gap and diagnostic in one transaction and replays deterministically | Pre-identity and stream regressions pass; injected SQLite failure rolls both back | PostgreSQL continuation skipped; no provider-side refetch or verified observable-universe coverage. |
| Telegram outcomes | Explicit rejection/generic exceptions could retry; 429 delay lost; dashboard showed only count | Adapter reports proven-not-sent, rate-limited, rejected or unknown; unknown age/reason sample reaches Scan Monitor | Focused provider, alert and operations tests pass; current Telegram PostgreSQL cases skipped (2) | No real recipient; database/Telegram atomic delivery is impossible and pre-send crash ambiguity remains. |
| Continuation runtime | Previous full test and security gates were 2026-11-09 evidence | No live provider, Telegram, production DB, or full worker process was invoked | `make lint`, migration graph, 73 Python tests, 25 runtime tests and 2 UI tests pass in focused runs | Full post-change backend/frontend/PG/security gates and multi-worker restart remain outstanding. |
| Theme hydration | Previous browser log contained a hydration-mismatch warning without a reproduced functional failure | New Playwright regression loads a saved light theme, hydrates, switches to dark, and captures hydration console errors | `playwright test e2e/theme-hydration.spec.ts --project=desktop`: 1 passed; no hydration error captured | Prior warning not reproduced; full current multi-viewport E2E not rerun. |
