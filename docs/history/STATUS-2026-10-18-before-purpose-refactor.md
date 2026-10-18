> Historical snapshot, archived 2026-10-18. Not current acceptance.
> Original docs/STATUS.md SHA-256: `f58181eca3209fbc140e17ab4bc7fab26f65411f0b9d4420283181419b3a0e1d`. Only relative Markdown link targets
> were rebased one directory upward; checkpoint text/evidence is retained.

# MemeRadar Status

Last updated: 2026-10-18

## Current task checkpoint — runtime settings final acceptance — 2026-10-18

**CURRENT_PHASE:** final local acceptance complete; external runtime acceptance blocked.
**CURRENT_TASK:** close only remaining runtime-settings acceptance risks; no feature expansion.
**STATUS:** `RUNTIME_SETTINGS_LOCAL_COMPLETE_WITH_EXTERNAL_ACCEPTANCE_BLOCKERS`.
**LAST_COMPLETED_STEP:** marked the Sprint 8.3 Settings security paragraph HISTORICAL/SUPERSEDED with a pointer to the current guarded runtime-settings contract. One bounded probe per runtime confirmed external restrictions. Existing API regressions plus a one-off in-memory sentinel/audit probe passed: 9 tests, 0 failures, 2 dependency warnings, 8.53s. No functional defect reproduced.
**NEXT_STEP:** authorized PostgreSQL and browser hosts must execute the blocked acceptance below. Stop local work; no new feature phase or full-suite rerun is pending.
**LAST_VERIFIED_HEAD:** `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e` on `main`.
**SOURCE_ID:** `sha256:855f21191ab86dde418267c63157ebe9af93b608abf2a70456419a4bb7bd9ab7`. Repository-native pre/post identity equality PASS, 710 scoped files; documentation-only repository changes do not alter identity.
**TEST_STATUS:** `UV_CACHE_DIR=/tmp/memeradar-uv-cache uv run pytest -q tests/unit/test_runtime_settings_api.py /tmp/test_memeradar_settings_acceptance.py`: exit 0, 9 passed / 0 failed / 2 warnings (8.53s). Existing secret, metadata, Admin authorization, safe effective/pending mutation, legacy protected override projection and stable safety-reason regressions retained unchanged. Supplemental malformed sentinel request is absent from response, captured logs and audit projection, with version unchanged. These checks use the in-memory owner, not PostgreSQL; exact-source recovery `make verify` exit 0 below remains valid.
**BLOCKERS:** `NEEDS_DATABASE_RUNTIME`: test database URL unset, bounded Docker probe denied (exit 1). `NEEDS_BROWSER_RUNTIME`: approved endpoint preflight `BLOCKED_HOST_RUNTIME`, `endpointProbe=host_permission_blocked` (exit 2). No retry, PostgreSQL concurrency test, or credentialed browser journey is attempted. `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` are absent within a read-only host boundary; this section remains the writable durable checkpoint.
**DIFF_CHECK:** `git diff --check` PASS after the security documentation edit. Only `docs/SECURITY.md` and this checkpoint changed in the repository during final acceptance; no functional source, test suite, migration, credential, protected mode or persistence owner was changed. Existing malformed-request and secret-write regressions were retained; the supplemental sentinel probe lives only in `/tmp`.

Runtime acceptance disposition (not inferred from in-memory tests):

| Gate | Final evidence |
| --- | --- |
| PostgreSQL safe override/read/audit | BLOCKED — NEEDS_DATABASE_RUNTIME |
| PostgreSQL pending/restart semantics | BLOCKED — NEEDS_DATABASE_RUNTIME |
| PostgreSQL same-version concurrent writes | BLOCKED — NEEDS_DATABASE_RUNTIME; no concurrency test added because runtime is unavailable |
| PostgreSQL rollback atomicity and absence of orphan audit | BLOCKED — NEEDS_DATABASE_RUNTIME |
| PostgreSQL secret no-write/no-audit and protected legacy override rejection | BLOCKED — NEEDS_DATABASE_RUNTIME; corresponding in-memory rejection/projection tests pass |
| PostgreSQL reconstruction/restart persistence | BLOCKED — NEEDS_DATABASE_RUNTIME |
| Credentialed browser mutation, refresh, credential clearing/storage/URL checks | BLOCKED — NEEDS_BROWSER_RUNTIME; no browser tests executed in this pass |
| Secret 422 and LIVE/AUTO stable 409 responses | PASS locally through existing API tests; browser/PostgreSQL acceptance remains blocked |
| Invalid sentinel absent from response/log/audit projection | PASS through one-off in-memory probe; not a PostgreSQL assertion |

The authorized operator must use an isolated migrated PostgreSQL test database to
exercise the existing `SqlAlchemyControlPlane` runtime-settings owner and the
listed concurrency/rollback scenarios. The existing control-plane PostgreSQL
integration test alone does not cover all these runtime-settings acceptance
criteria. On an authorized browser host, use test-only role tokens and the
existing Settings credential input for the requested safe-edit/save/refresh
journey; tokens must never be hardcoded or persisted. The existing host
preflight command is
`MEMERADAR_E2E_BASE_URL=http://127.0.0.1:13000 node apps/web/scripts/host-acceptance.mjs --check`.
Do not classify a generic browser suite as proof of this credentialed journey.

LOCAL_IMPLEMENTATION_COMPLETE; PROVIDER_OPERATIONAL_ACCEPTANCE remains NOT
VERIFIED; PRODUCTION_READY=false. No LIVE readiness or PostgreSQL/browser runtime
acceptance is claimed. All six protected mode values remain unchanged.

**UPDATED_AT:** 2026-10-18.

## Historical checkpoint — runtime settings regression recovery — 2026-10-18

**CURRENT_PHASE:** regression recovery complete.
**CURRENT_TASK:** reconcile the existing runtime-settings safety/configuration contracts; no feature expansion.
**STATUS:** `RUNTIME_SETTINGS_REGRESSION_RECOVERED`.
**LAST_COMPLETED_STEP:** all focused and relevant broader tests passed, then one full `make verify` exited 0 on the exact final source identity. Registry metadata, external-secret refusal, protected environment modes, stable safety conflicts, Admin authorization and ordinary safe mutations are verified locally. Structural-error secret echo and legacy protected-mode pending projection were reproduced and repaired as part of this slice.
**CURRENT_FAILURES:** 0.
**NEXT_STEP:** stop this recovery. External production/runtime/provider acceptance remains separate.
**NEXT_EXACT_ACTION:** none within this recovery; no additional feature phase or full-suite rerun is pending.
**LAST_VERIFIED_HEAD:** `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e` on `main`.
**SOURCE_ID_BEFORE:** `sha256:855f21191ab86dde418267c63157ebe9af93b608abf2a70456419a4bb7bd9ab7`.
**SOURCE_ID_AFTER:** `sha256:855f21191ab86dde418267c63157ebe9af93b608abf2a70456419a4bb7bd9ab7`. Pre/post equality PASS, 710 scoped files; no source edits occurred during the successful aggregate run.
**TEST_STATUS:** backend focus 25 passed / 0 failed / 2 dependency warnings (6.96s); frontend focus 11 passed / 0 failed (6.76s). Broader existing control/config tests 32 passed (10.14s); frontend reader 58 passed (3.17s). Full `make verify`: exit 0; Python 1,952 passed / 25 skipped / 0 failed / 8 warnings (416.10s); frontend 252 tests / 36 files PASS; repository Ruff, configured mypy (184 files), frontend ESLint/typecheck, CSS contract (443 classes), Compose config, secret scan, static migration check, local security review, and SBOM (565 components) PASS. Five scoped Python files pass Ruff format. An earlier selected-file mypy invocation omitted package roots and failed import resolution; the configured invocation and full verify subsequently passed.
**MIGRATION:** no new migration or table; existing runtime-settings, pending-values, config-version and audit owners are reused. Head remains `0022_cross_chain_evidence`, one head, 40 tables.
**WORKTREE:** 2,035 recursive porcelain entries: 218 tracked, 1,817 untracked files, 0 staged, 1 inherited tracked deletion. These include unrelated inherited/generated work; they are not attributed to this task. No reset/clean/restore, commit or remote Git operation was performed. `git diff --check` PASS.
**EVIDENCE:** [complete make verify log](../../artifacts/verification/runtime-settings-recovery-2026-10-18.log). Source identity excludes docs and generated artifacts under the repository-native helper.
**BLOCKERS:** no remaining focused local regression. PostgreSQL runtime, browser E2E and provider operational acceptance remain unverified from the prior checkpoint; no external/runtime probe was performed in this recovery. Production readiness is not claimed. `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` are absent under the host's read-only `.codex` boundary; this section is the writable durable checkpoint.
**UPDATED_AT:** 2026-10-18.

Original failure disposition:

1. Safe defaults: the original failing code lacked `Settings.canary`/`live`; preserved and verified the partial repair with keyless defaults and no provider credential requirement.
2. CANARY: its environment input was ignored; the protected environment parser now rejects enablement and the read-only registry entry reports ENV/DEFAULT.
3. LIVE: the same missing environment contract; no DB override or execution path is allowed.
4. Metadata: canonical registry metadata was incomplete, and the interrupted exact-response expectation omitted the intentionally added `configured_value`. The expectation was strengthened to retain that field, sensitivity, source, classifications, and null secret value fields.
5. Secret replacement/clear: RESTART_REQUIRED incorrectly implied mutability for credentials. The shared registry/validator now makes every credential EXTERNAL_SECRET_ONLY, refuses writes/clears with 422, and ignores legacy override values. Rejected values do not enter audit history or logs.
6. LIVE/AUTO enablement: generic non-mutable validation intercepted valid prohibited transitions as 422. Explicit safety checks precede it and return 409 with the required stable reasons.

Task-touched paths (existing dirty work outside these paths was preserved):

- `packages/application/src/memeradar_application/config.py`
- `packages/application/src/memeradar_application/control.py`
- `apps/api/src/memeradar_api/control.py`
- `apps/web/src/app/api/control/runtime-settings/route.ts`
- `apps/web/src/app/api/control/runtime-settings/route.test.ts`
- `apps/web/src/app/components/settings.tsx`
- `apps/web/src/app/components/settings.test.tsx`
- `apps/web/src/app/lib/read-api.ts`
- `apps/web/src/app/lib/read-api.test.ts`
- `tests/unit/test_config.py`
- `tests/unit/test_runtime_settings_api.py`
- `docs/STATUS.md`
- `docs/SECURITY.md`

This is the current authoritative project state. Historical checkpoint detail
was consolidated here; implementation contracts remain in the canonical
documents below.

## Historical authoritative checkpoint — upstream integration — 2026-10-16

**CURRENT_PHASE:** final local evidence closure complete; external runtime/provider acceptance remains.
**CURRENT_TASK:** retain exact-source verification evidence and hand off only PostgreSQL, browser, and verified-provider acceptance.
**STATUS:** `CLOSED_LOCAL_WITH_EXTERNAL_BLOCKERS`.
**LAST_COMPLETED_STEP:** `make verify` ran once and exited 0 on source identity `sha256:193a7a14cd88b434acb604350504a1381b1ff8976ad82106edc092671f3d33b9`; pre/post identities match (710 files, branch `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`). Python: 1,944 passed, 25 skipped, 0 failed, 10 warnings in 592s. Ruff lint and mypy (184 files) passed; frontend ESLint, typecheck and Vitest (248/36) passed; Compose, secret scan, migration check, security review and SBOM passed. The 27-file scoped Ruff lint passed; 26 whole-file-safe format checks passed, and the isolated 0022 test hunk in `test_worker_entrypoint.py` is formatted. `git diff --check` passed. Migration head `0022_cross_chain_evidence`, 40 tables.
**NEXT_EXACT_ACTION:** provide an approved PostgreSQL runtime, browser host, and provider evidence packet as documented in the closure report; no further local verification command is pending.
**LAST_VERIFIED_HEAD:** `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e` on `main`.
**SOURCE_ID:** `sha256:193a7a14cd88b434acb604350504a1381b1ff8976ad82106edc092671f3d33b9` across 710 source/config/test/acceptance files. `make verify` used this exact identity and its pre/post identities match.
**TEST_STATUS:** final-source `make verify` exit 0: Python 1,944 passed / 25 skipped / 0 failed / 10 warnings; mypy 184 files; frontend Vitest 248/36, ESLint and typecheck pass; migration 0022/40 tables; security review PASS, secret scan PASS, SBOM PASS (565 components), Compose config PASS. Scoped Ruff lint/format and final diff checks pass for the task-owned scope. One inherited whole-file formatting drift remains outside the new 0022 test hunk; no bulk reformat was applied.
**WORKTREE:** `main`, HEAD above; current porcelain inventory with `--untracked-files=all`: 213 tracked entries, 1,814 untracked file entries, 0 staged, 1 tracked deletion, 2,027 entries total. This includes inherited and generated work; no unrelated work was discarded.
**BLOCKERS:** PostgreSQL runtime unavailable (`MEMERADAR_TEST_DATABASE_URL` unset; Docker daemon socket denied); browser E2E/screenshots, runtime accessibility, and Web Vitals unverified. No verified sequencer frame/calldata fixtures or Relay producer exists; source-specific decoder/producer requires `NEEDS_EXTERNAL_PROVIDER`. Provider operational acceptance and production readiness are not claimed. Do not add an Operations/UI panel until a producer establishes real source health/completeness. Protected execution modes remain unchanged.

## Historical project state — 2026-10-13

The latest completed engineering checkpoint is V8.3. Its final report is
[`MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md`](../reports/MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md)
and its resumable checkpoint is
[`V8_3_CURRENT.md`](../reports/agentic-loop/V8_3_CURRENT.md). The report records
1,660 backend unit tests, 220 frontend tests, static/type checks, a 28-route
production build, and 85 passed / 10 configured skips / 0 failed in the
five-viewport browser matrix. These are V8.3 results, not rerun by the current
documentation/UI task.

External acceptance remains open: PostgreSQL runtime is `BLOCKED_HOST`; live
provider-backed wallet/creator/funder/bundle/Relay evidence, mature real
outcomes, and locked chronological OOS are not verified. Real alpha and
production readiness are not claimed. Operating modes remain
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`.

## Historical frontend acceptance update — VNext 7 (2026-10-14)

The current dirty frontend source was revalidated independently of the V8.3
backend/report checkpoint above. It contains 22 filesystem page routes and the
V6 desktop research workspace compositions. V7 fixed one source-level trust
boundary: Social Alpha and caller-source links now allow only absolute,
credential-free HTTP(S), and invalid source URLs are rejected before the
operator API request. The convergence pass also fixed the acceptance runner's
existing-server state: fixture-backed suites are marked
`NOT_RUN_EXTERNAL_BASE`, and a successful primary-only run is reported as
`PARTIAL_EXTERNAL_BASE` (11 host-runner regression tests pass). The final V7
frontend source identity is
`sha256:215c3fe104fbbbeef5192365570033265b3d0e276afbe7ff44e3adb97237ae5d`
(137 frontend source/config/test/acceptance files; branch `main`, HEAD
`35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`). The 36-file/246-test Vitest
suite, typecheck, ESLint, CSS contract (443 classes), root helper tests, build
(28 App Router entries), and all five configured route bundle budgets were
rerun and pass.

Playwright collection passes (main 130, social/services 60, visual fixtures 30,
performance 3), but no V7 browser tests or screenshots ran. The Compose web
container is running on port 13000, but the host runner's explicit existing
server probe returns `host_permission_blocked` (exit 2); CUA has no browser.
Runtime axe/keyboard, manual screen-reader acceptance and Web Vitals remain
unverified. The V8.3 85/10/0 browser run predates the final V7 source identity
and is not current-source acceptance. Current UI terminal state is
`FRONTEND_IMPLEMENTED_RUNTIME_BLOCKED`, not full visual or production
acceptance. Details and exact host handoff are in
[`ui-redesign-vnext/FINAL_CLOSURE_REPORT.md`](../ui-redesign-vnext/FINAL_CLOSURE_REPORT.md).

The active UI design contract is [`apps/web/DESIGN.md`](../../apps/web/DESIGN.md),
and the current route/API audit and cleanup work are indexed in
[`ui-redesign/README.md`](../ui-redesign/README.md) and
[`DOCS_CLEANUP_REPORT.md`](../DOCS_CLEANUP_REPORT.md). The former frontend
modernization prompt is archived as reverted history; it is not an active
implementation plan.

## Upstream intelligence integration — intermediate implementation history (2026-10-14)

The semantic gap audit is recorded in
[`upstream-intelligence-integration-matrix-2026-10-14.md`](../reports/upstream-intelligence-integration-matrix-2026-10-14.md).
Typed wallet-role evidence, deterministic chain/version-aware operator-cluster
resolution, normalized PostgreSQL models/migration, a bounded refresh in the
existing wallet-history worker, and Wallet Graph wallet/cluster read projections
are implemented. Behavioral correlation remains distinct from observed
relationships; cluster and membership projections force
`ownership_asserted=false`. Incomplete scans are skipped and logged at UNKNOWN
quality instead of persisting truncated clusters.

Local implementation now includes an explicit Pump.fun creator-role producer,
the bounded as-of wallet-role projection and Wallet Detail presentation, plus
FIFO inventory maturity retained as a separate observation from Smart Wallet
scoring. A test-first integration fix also connects exact Pump.fun swap balance
rows to wallet inventory reconstruction; partial inventory remains PARTIAL and
price/PnL/costs remain UNKNOWN when the normalized quote economics are absent.
No other wallet roles are inferred from behavior or incomplete coverage.

The combined wallet/role/forward/operator/read regression passed **137 tests**;
the wallet-history/tracking/reputation regression passed **28 tests**; the
focused frontend role/read-client suite passed **74 tests**. Ruff, web
typecheck, and touched-file ESLint passed. The test-first wallet-history case
failed before repair because zero exact swap rows reached the tracker, then
passed after the `token_address` and exact-classification adapter was added.
The SQLite/contract checks do not constitute PostgreSQL migration acceptance.

Typed sequencer intent joins, Relay order-leg correlation, provider-backed
creator-funding purpose, verified Jito membership/disposition, full wallet
history economics, and shred discovery remain source/schema/runtime gated as
specified in the integration matrix. No live provider, PostgreSQL runtime, or
current browser acceptance is claimed. Protected operating modes are unchanged.

## 2026-09-26 frontend and live-readiness closure checkpoint

Current findings and mandatory answers are in
[`frontend-live-closure-final.md`](../reports/frontend-live-closure-final.md).
All 15 routes have a visual maturity grade. Radar retains SVG plus table
access; the wallet graph remains SVG. Backend read models now expose named
stream cursor/gap rows and report-only strategy failure metadata. Token-scoped
provider conflicts and some position/stream fields remain UNKNOWN or absent
where canonical persisted evidence is unavailable.

Readiness contains 117 inert proposal-only parameters (the original 56 plus 61
safety categories). ANALYSIS remains effective, allowed promotions are empty,
`AUTO_EXECUTION=false`, no signer is active, no live submission path is
enabled, and mature out-of-sample evidence is insufficient.

Final `make verify`: **FAIL**, 1,528 passed, 21 skipped, 3 failed; all three
failures are security-review assertions caused by the retained
`.env.example` scanner finding. `LIKELY_SECRET` is the conservative
classification; the value remains untouched and unprinted pending external
rotation/revocation and owner approval for placeholder replacement. Ruff and
mypy pass. Independent gates pass for frontend lint/typecheck, 87 frontend
unit tests, CSS contract (329 classes across 61 files), Compose config,
migration check (27 tables, one head), and SBOM (582 components). Secret scan
and keyless security review fail only at the secret boundary; no scanner or
execution control was weakened.

The production build and route JavaScript budgets pass. A dev-server Playwright
run passed 44 tests and skipped 4 credential-gated tests; all 120 requested
screens were captured and geometry-checked, but representative images only
were manually reviewed and no baseline was accepted. Local production browser
and runtime runs are blocked by `listen EPERM` on local listener creation.
Lighthouse, runtime FPS/Web Vitals, populated mobile table scroll, and a full
screen-reader review remain unmeasured. An `@lhci/cli@0.15.1` install reported
12 vulnerabilities; its detailed audit failed with `EAI_AGAIN`, so it was
removed. Full audit on the retained dependency tree found two moderate
dev-only Vitest advisories; runtime high-severity audit passed.

Production Compose validation passes using CI-only dummy values. Docker daemon
access is available; API, worker, and web Dockerfile builds succeeded with
non-root runtime users after `.dockerignore` was tightened to exclude env,
`.codex/`, prompts, and protected script outputs. The daemon context is a local
socket. Earlier builds preceded this hardening; Dockerfiles copy explicit
application paths, but protected files may have been included in the local
context transfer. Sanitized rebuild digests are recorded in the closure
report; no release identity was generated from the dirty worktree. Docker
Scout, Trivy, Grype, and pip-audit are unavailable. The pinned Lighthouse CI
package attempt was removed after install reported 12 advisories and the
registry audit failed with `EAI_AGAIN`. `.git` and `.codex/` remain read-only
mounts. No commit or remote Git operation was made; a sanitized patch is
preserved outside `.git`. Real provider, mature PAPER, temporal OOS,
incident-free CANARY and LIVE acceptance remain blocked.

## 2026-09-26 earlier frontend modernization checkpoint (superseded)

The earlier snapshot is retained in
[`frontend-modernization-final.md`](../reports/frontend-modernization-final.md).

## 2026-09-26 external capability integration checkpoint

The external audit and implementation report is recorded in
[`external-alpha-capability-integration-2026-09-26.md`](../reports/external-alpha-capability-integration-2026-09-26.md).
The exact pre-change matrix is in
[`external-feature-gap-matrix.md`](../reports/external-feature-gap-matrix.md),
with license and reuse decisions in
[`external-repo-license-matrix.md`](../reports/external-repo-license-matrix.md).

The P0 path now has unique-buyer windows (10s/30s/1m/3m), cluster-adjusted
buyers, wallet entropy, funded-sibling evidence, wash-suspected volume,
organic volume and raw-versus-organic turnover in the existing flow/early
feature owners.  Local P2/P3 seams now include the authenticated Helius wallet
webhook adapter, explainable smart-wallet leaderboard, transaction taxonomy,
evidence-only wallet labels, alert storm controller, price consensus,
Robinhood named-subscription descriptors, adaptive EVM logs, ticker-collision
protection, optional chain-configured read-only Multicall3, and report-only
strategy failure metadata.  Par, HoodiePad/Doppler, NOXA and Odyssey parsers
remain read-only candidate contracts; unverified deployments are rejected by
the existing log reader.

Protected modes remain unchanged.  No source was copied, no external
dependency was added, and no live execution path was enabled.  The full
Python run reached `1507 passed, 21 skipped, 7 warnings` with total coverage
`79%`; `make lint` and `make typecheck` passed.  Frontend CSS/lint/typecheck/
tests, Compose config, migration check, and SBOM also passed (`83` frontend
tests, `582` SBOM components).  The repository security review is currently
blocked by a pre-existing dirty `.env.example` value that
matches the secret scanner's Telegram-token pattern; the file was preserved
unchanged and the value is not recorded here.  `HEAD:.env.example` passes the
same scan.  Real provider acceptance and mature OOS alpha evidence remain
`BLOCKED_EXTERNAL` / `INSUFFICIENT_SAMPLES`.

The requested `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` files
remain unwritable because `.codex/` is host-mounted read-only; this checkpoint
and verification evidence are durable under `docs/reports/`.

## 2026-09-26 root-cause closure and real-acceptance checkpoint

The required closure report is
[`external-alpha-real-acceptance-2026-09-26.md`](../reports/external-alpha-real-acceptance-2026-09-26.md).
The local implementation/test checkpoint is `b0c3636` on top of baseline
`5e39666`; no remote Git operation was run.

The organic-flow audit now keeps shared-funder cluster membership, repeated
trade size, market-maker-like shape and other correlation signals as evidence
instead of automatically labeling every related trade as wash. Suspected wash
volume is limited to round-trip/rapid/explicit evidence, with bounded
`wash_confidence`, raw/organic volume and raw/organic turnover exposed through
the existing flow, early-feature and alert owners. The new alert evidence is
rendered for high-priority states without changing score authority.

`DataQualityConfidence` now persists seven dimensions — organic flow, wallet
independence, stream quality, price quality, provider agreement, protocol
identity and holder data — with explicit UNKNOWN/DEGRADED reason codes. The
existing asymmetric score remains unchanged. Provider conflict telemetry now
exposes total/rate, conflict type, and canonical provider-pair buckets through
the existing reliability collector; live counts remain unavailable until two
real providers are reachable.

Final backend evidence is `1518 passed, 21 skipped, 7 warnings`; three
security-review tests fail only because the user-owned `.env.example` edit
matches the secret scanner. Global combined line/branch coverage is `78.69%`
(`83.22%` statements, `66.34%` branches). Ruff, mypy (`164` source files),
frontend CSS/lint/typecheck/tests (`83` tests), Compose syntax, migration check
and SBOM (`582` components) pass. `make verify` therefore remains a genuine
security-gate failure, not a suppressed result.

The bounded synthetic hot path reports `1616.587` iterations/s and
chain-event-to-decision p50/p95/p99 `0.434/0.485/0.498 ms`; it is explicitly
`synthetic_local` and does not prove live SLOs. Real Helius, Telegram,
Robinhood named-stream, public EVM, dual-price-source and unverified protocol
acceptance remain `BLOCKED_EXTERNAL`/`TODO_VERIFY`. Pump.fun forward shadow has
`1278` launches and `995` one-hour-due rows, but mature 6h/24h/72h/7d counts
remain `0/0/0/0`; OOS lift and paper lifecycle remain
`INSUFFICIENT_SAMPLES`.

## Current classification

| Dimension | Current state | Evidence / constraint |
|---|---|---|
| System stage | `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION` | The canonical stream-to-alert/research path and PostgreSQL-backed restart/idempotency contracts are locally verified; external source and statistical alpha validation are separate. |
| Stack readiness | `PASS` (`STACK_READY / DEGRADED`) | A bounded Compose run passed PostgreSQL, Redis, API liveness/readiness, worker startup, web reachability and protected-mode checks on isolated ports. |
| Core provider readiness | `READY_FOR_FREE_READ_ONLY_SHADOW` / `PASS` (bounded Pump.fun launch acceptance) | Public Solana RPC/WebSocket, pinned IDL-driven create/create_v2 decoding, canonical routing and PostgreSQL-backed discovery persistence are proven on one real launch. |
| Shadow collection | `PASS` (bounded acceptance; not a statistical sample) | One real `create_v2` traversed raw transport, stream integrity, canonical decode, normalized launch and `DISCOVERED` persistence. No threshold or alpha claim is made. |
| Real-world alpha | `REAL_WORLD_ALPHA_NOT_YET_PROVEN` | Historical-real and matured live-shadow samples remain insufficient. |
| Production readiness | `NOT_PRODUCTION_READY` | See [Production Readiness](../PRODUCTION_READINESS.md). |
| Read-only production gate | `PROD_READ_ONLY_NOT_ACCEPTED` | Local deterministic and production-like gates pass; hosted CI, branch protection, managed deployment/operations, and credentialed external acceptance remain blocked. |
| Live-money eligibility | `OUT_OF_SCOPE` / not eligible | No live-money workflow is enabled or authorized. |

Protected modes are unchanged and enforced:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

There is no wallet signer, live order submission, automatic execution, or
execution authority in the web client. Missing, stale, conflicted, invalid,
unverified, and unresolved-gap evidence remains fail-closed and distinct from
zero or safe evidence.

## 2026-09-24 multi-chain validation checkpoint

The local implementation checkpoint is recorded in
[`multichain-alpha-validation-2026-09-24.md`](../reports/multichain-alpha-validation-2026-09-24.md).
The repository now has read-only, provider-independent seams for the generic
EVM chains, Robinhood Chain identity `4663`, BNB/Four.meme/Pancake lifecycle
normalization, Base/Uniswap/Aerodrome candidates, Ethereum/Uniswap identity,
optional Blockscout enrichment, provider-neutral EVM sell simulation,
Raydium pool/quote normalization, Jupiter Swap API V2 quote/order reads, and
a thin read-only `memeradar-mcp` operator surface. No protocol deployment is
authoritative until chain, address, runtime bytecode, event identity, and a
sample transaction are verified; current candidates remain `TODO_VERIFY`.

The prior clean local quality gate was green: `make verify` passed with backend
tests `1492 passed, 21 skipped, 7 warnings`, total coverage `79%` (delta `0`
from the prior `79%` baseline), frontend tests `83 passed`, migration head
`0012_stream_gap_diagnostics`, security review `PASS`, and SBOM `PASS` for
`582` components. Keyless free-provider readiness is `PASS`; the paper
contract doctor is `PASS`. The full evidence table, capability matrix, and
remaining external blockers are in the report linked above.

Database-backed forward-shadow acceptance is still `BLOCKED_EXTERNAL`: the
repository Compose stack cannot access the host Docker socket in this
session, no `DATABASE_URL` is configured, and no PostgreSQL row/restart proof
was collected. The real post-fix stream-gap count is therefore
`NOT_MEASURED`; the legacy `1408` counter is documented as a superseded
scope-mismatch measurement, not silently reported as a current loss count.
Telegram real-send latency is also `NOT_MEASURED`: the process has no bot/API
configuration and the supplied local credential probe timed out. The requested `.codex/CURRENT_TASK.md` and
`.codex/VERIFICATION.md` files remain unwritable because `.codex/` is
host-mounted read-only; the plan, ledger, and reports are durable in the
repository's writable tree.

## 2026-09-24 real-acceptance continuation checkpoint

Full evidence: [`real-multichain-acceptance-2026-09-24.md`](../reports/real-multichain-acceptance-2026-09-24.md).

The first unresolved runtime gate remains `BLOCKED_EXTERNAL`. Compose still
cannot access `/var/run/docker.sock`, no PostgreSQL URL or local PostgreSQL
server is available, and the bounded public Solana WebSocket probe recorded
transport errors/reconnects with zero notifications. The existing Solana HTTP
RPC doctor remains `PASS`; this is not stream-continuity acceptance. A
bounded Jupiter quote probe timed out, and the supplied local Telegram
credentials could not complete the health call after the canonical API URL was
supplied in-process. No Telegram message was sent.

The local acceptance seam was tightened without changing canonical Pump.fun
routing: `ProtocolCertificationRecord` and
`DEFAULT_PROTOCOL_CERTIFICATION_REGISTRY` now expose the required chain,
deployment, bytecode, interface, event, sample, timestamp, normalized-output,
version, source, and status fields. Decoder-only identities remain
`TODO_VERIFY`; no deployment is promoted by documentation or fixtures. The
existing asymmetric projection now carries `DataQualityConfidence`, derived
from its existing evidence coverage/freshness contract and kept separate from
AlphaIgnitionScore, SafetyConfidence, and OpportunityConfidence. Protected
modes remain unchanged.

## 2026-09-24 autonomous implementation checkpoint

The first requested live acceptance step was attempted through the existing
Compose stack. Compose syntax and the migration graph pass, but the host
Docker socket is not accessible in this session:
`permission denied while trying to connect to the Docker API at
unix:///var/run/docker.sock`. The development environment has no configured
`DATABASE_URL`, so PostgreSQL row/restart evidence could not be collected.

The exact result is recorded in
[`forward-shadow-live-acceptance-2026-09-24.md`](../reports/forward-shadow-live-acceptance-2026-09-24.md).
This is `BLOCKED_EXTERNAL` for the runtime only; local implementation and
contract verification continue. The requested `.codex` checkpoint files are
still unavailable because `.codex/` is host-mounted read-only; the active
plan and ledger are in
[`docs/superpowers/plans/2026-09-24-multichain-alpha-validation.md`](../superpowers/plans/2026-09-24-multichain-alpha-validation.md)
and `.superpowers/sdd/`.

The first stream-gap root-cause pass is recorded in
[`stream-gap-root-cause-2026-09-24.md`](../reports/stream-gap-root-cause-2026-09-24.md).
The prior `1408` value was traced to the superseded health scope that merged
global/sparse-slot gaps into Pump.fun launch health. Current program-scoped
health does not infer slot gaps; explicit reconnect markers are persisted and
bounded finalized-slot recovery uses the canonical decoder. Real unresolved
gap counts remain unverified until the blocked Compose acceptance can run.

## 2026-09-24 autonomous audit checkpoint

The required repository audit is complete at local HEAD `c29b84c`. The gap
matrix is recorded in
[`docs/reports/early-alpha-gap-analysis.md`](../reports/early-alpha-gap-analysis.md).
The requested `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` recovery
files could not be written because the host exposes `.codex/` read-only; the
limitation and the recovery information are recorded in the report.

The audit found reusable owners for canonical identity, early discovery,
event-time features, wallet/creator graphs, security evidence, stream
integrity, alerts, paper execution, replay, ablation, and promotion. No
parallel score, lifecycle, execution, or provider framework was added. The
first unresolved acceptance gate remains compliant real-data and
out-of-sample validation with mature outcomes. The named case studies are not
present as historical replay samples, and the bounded Pump.fun artifact has
`1278` launches, `121` MemeRadar-before-Dex leads, and `0` matured executable
winner labels. This remains `REAL_WORLD_ALPHA_NOT_YET_PROVEN` and
`INSUFFICIENT_SAMPLES`.

Pre-existing untracked operator artifacts were preserved. Remote
synchronization is intentionally unavailable; no remote operation was run.

Local verification after the audit passed: `git diff --check`, Ruff, mypy
(`146` source files), `make test` (`1444 passed, 21 skipped, 7 warnings`), and
`make verify`. The full verify also passed frontend CSS/lint/typecheck/tests
(`83` tests), Compose configuration, secret scan, migration check, security
review, and SBOM. External container/npm/pip scans remain `NOT_RUN`, and
credentialed integration/production acceptance remains `BLOCKED_EXTERNAL`.

The host filesystem exposes `.codex/` read-only, so the requested
`.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` checkpoint files could
not be created. The durable audit and verification record is in
[`docs/reports/early-alpha-gap-analysis.md`](../reports/early-alpha-gap-analysis.md);
this is an environment limitation and did not require weakening any control.

## 2026-09-24 early-alpha validation implementation checkpoint

The first unresolved acceptance gate was implemented locally in commit
`6113083`:
[`early-alpha-validation-implementation.md`](../reports/early-alpha-validation-implementation.md).
The existing worker now follows all observed Pump.fun launches through durable
1m–7d outcome horizons, versioned research labels, idempotent maturation
upserts, forward-shadow reporting, matched-control/recall/ablation seams, and
explicit sample insufficiency. Existing early features now include unified
effective-liquidity turnover, age cohorts, explainable smart-wallet
copyability/convergence, supply-quality evidence, and the separate
`AlphaIgnitionScore`, `SafetyConfidence`, and `OpportunityConfidence`
projection fields.

The existing Telegram renderer/outbox now emits state-aware WATCH,
EARLY_ALPHA, HIGH_CONFIDENCE_ALPHA, PAPER_ELIGIBLE, RISK_BLOCK, and EXIT
transitions with deduplication and signal/enqueue/send timing. No Telegram
credentials are configured locally, so external delivery remains
`BLOCKED_EXTERNAL`. Historical case rows, Base protocol acceptance, and
fresh mature labels remain `BLOCKED_EXTERNAL` or
`INSUFFICIENT_SAMPLES`; the checked-in Pump.fun artifact still records
1,278 launches, 121 MemeRadar-before-Dex leads, 995 1h-due observations, and
zero measured executable winners.

Post-commit verification: `make lint` PASS, `make typecheck` PASS for 147
source files, `make test` PASS with 1,456 passed and 21 skipped, plus the
focused persistence upsert regression (5 passed). The final `make verify`
gate also passed, including frontend lint/typecheck and 83 frontend tests,
CSS contract, Compose config, secret scan, migration check, security review,
and SBOM. Protected modes remain unchanged.

## 2026-09-21 Pump.fun launch decoding and first live acceptance

The local decoder is pinned to the exact public-docs revision used for the
checked-in schema: [`pump.json`](https://github.com/pump-fun/pump-public-docs/blob/81091419e4457566469d4e2a27f64ed84d42419c/idl/pump.json),
revision `81091419e4457566469d4e2a27f64ed84d42419c`, SHA-256
`ffe966c42f1af41652ee753fe2f1e3f7cd4077d7e6f49faf3138959c8b56064b`, local
schema `pumpfun-idl-schema-v1`. The official [`COIN_CREATION.md`](https://github.com/pump-fun/pump-public-docs/blob/81091419e4457566469d4e2a27f64ed84d42419c/docs/instructions/COIN_CREATION.md)
account layout is preserved: `create_v2` mint `0`, user `5`, token program
`7`; creator is decoded from instruction data only. Pin mismatches fail closed
as `PROTOCOL_DRIFT_DETECTED`.

The bounded acceptance runner composed the existing public raw source, stream
integrity coordinator, canonical decoder, early runtime and SQL persistence.
It observed and persisted this first real launch:

| Field | Evidence |
|---|---|
| signature | `3kAL4U6up2aEC3Xx9DvGzSDwP4Sdis1BEqJ4X5L61RJzuDqpUeJ8WNWUu6SWK3q6uT6mrHHeKBSkGrhSDhw23aQK` |
| slot | `448986608` |
| program ID | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` |
| discriminator | `d6904cec5f8b31b4` |
| instruction | `create_v2` / canonical `launch` |
| mint | `9vRzjUmVLv894UwsBkCtmbFFLUPwUC3p8bU7RgL7pump` |
| creator | `7BKBVk2zfH2hcbXGEeJufPTT3FvYcdf89yHEFpyTBCop` |
| user | `7BKBVk2zfH2hcbXGEeJufPTT3FvYcdf89yHEFpyTBCop` |
| name / symbol | `Pump` / `PUMP` |
| provider observed | `2026-09-21T07:22:51.918948+00:00` |
| MemeRadar ingested | `2026-09-21T07:22:52.503712+00:00` |
| MemeRadar `DISCOVERED` | `2026-09-21T07:22:51.918948+00:00` |

Acceptance gates: `RawChainTransaction=PASS`, `canonical decode=PASS`,
`normalized launch=PASS`, and `DISCOVERED persisted=PASS`. An immediate
exact-mint DexScreener lookup was attempted with no pair known at that time;
the later forward tracker records the first successful observation in the
forward-evidence section below. The launch did not produce `EARLY_WATCH`;
thresholds were unchanged. `REAL_WORLD_ALPHA_VALIDATED=NO`.

Evidence artifact: `artifacts/research/pumpfun-live/20260921T073000Z.json`
(local research output, intentionally not committed).

Verification for this checkpoint: focused Pump.fun/stream/runtime/persistence
suite `73 passed`; full `make test` `1429 passed, 20 skipped, 7 warnings`;
`make typecheck` passed for 142 source files; full Ruff passed; opt-in
PostgreSQL stream/runtime integration `2 passed`; rebuilt Compose stack and
`make status` `PASS` with all five services healthy.

## 2026-09-21 Pump.fun forward alpha evidence collection

The accepted canonical Pump.fun launch stream now feeds one bounded,
restart-safe forward research scheduler. It persists every verified
`create`/`create_v2` launch projection, exact-mint DexScreener polls at
`0s, 5s, 10s, 20s, 30s, 60s, 120s, 300s, 600s, 1200s, 1800s, 3600s`, market
snapshots through 7d, horizon-gated outcome rows, creator-history evidence,
missed-winner/false-positive projections, funnel transitions, Telegram timing,
and raw-stream health. The scheduler uses the existing worker and generic
observation repository; no detector, migration, score threshold, or execution
path was added.

The reproducible report is [pumpfun-forward/report.md](../../artifacts/research/pumpfun-forward/report.md)
with machine-readable [report.json](../../artifacts/research/pumpfun-forward/report.json).
The latest live-shadow report generated at `2026-09-21T10:45:55.491446+00:00`
contains:

| Measure | Evidence |
|---|---:|
| total launches / legacy `create` / `create_v2` | `1278 / 16 / 1262` |
| DISCOVERED / WATCH / EARLY_WATCH | `1278 / 1275 / 0` |
| Dex first observations / MemeRadar-before-Dex leads | `124 / 121` |
| MemeRadar→Dex lead | `N=121`, median `76.815456s`, p90 `1071.072466s`, p95 `6604.977256s`, max `9251.576703s` |
| horizon-due outcomes | `1h=995`; `6h/24h/72h/7d=0` |
| measured executable winner labels | `0` at `2x/5x/10x/20x/50x/100x` |
| missed winners / false positives | `0 / {}` |

The accepted real launch remains fully evidenced: raw transaction, canonical
decode, normalized launch, and `DISCOVERED` persistence all PASS. Its immediate
DexScreener query at discovery had no pair; the first successful exact-mint
forward observation was later persisted at
`2026-09-21T09:57:03.495651+00:00` with lead `9251.576703s`. This is a
MemeRadar-observed API timestamp, not DexScreener internal listing latency.

Outcome rows with `quality_state=UNKNOWN` are excluded from measured returns;
therefore `OUTCOME_STATUS=INSUFFICIENT_SAMPLES`,
`STATISTICAL_SAMPLE_SUFFICIENT=NO`, and `REAL_WORLD_ALPHA_VALIDATED=NO`.
The latest health row records `1158` notifications, `3` raw decoded launches
(`1` `create_v2`), p50/p90/p95 latency `472.466/472.466/472.466ms`, zero decoder
failures, zero dropped events, `1` signature deduplication, no stream errors,
and `stream_gaps=1408`; therefore `LIVE_SHADOW_OPERATIONAL=DEGRADED` remains
explicit. The worker remained up for the post-restart verification window with
no traceback or idempotency conflict. Telegram is `UNKNOWN` because credentials
are not configured. Protected modes remain unchanged.

The non-destructive upstream check now hashes the pinned commit's raw IDL URL
and returns `PASS`: revision
`81091419e4457566469d4e2a27f64ed84d42419c`, SHA-256
`ffe966c42f1af41652ee753fe2f1e3f7cd4077d7e6f49faf3138959c8b56064b`, schema
`pumpfun-idl-schema-v1`. A changed revision/hash/schema is covered by the
negative test and reports `PROTOCOL_DRIFT_DETECTED` without promotion.

Verification: full `make test` `1440 passed, 21 skipped, 7 warnings`;
`make lint` PASS; `make typecheck` PASS for 146 source files; focused forward
suite `11 passed, 1 skipped`; rebuilt Compose stack and protected-mode checks
PASS. No scoring thresholds or live execution settings changed.

## 2026-09-20 raw Solana ingestion checkpoint

The keyless raw-source slice is implemented and remains analysis-only:

- `SolanaRawTransactionSource` subscribes to Pump.fun logs, bounds the queue,
  deduplicates signatures, retries transaction indexing races, resolves parsed
  and address-table account keys, and emits the existing
  `RawChainTransaction` contract.
- The worker constructs that source from the standard Solana RPC adapter when
  the database and Solana chain are enabled. Injected sources remain available
  for replay and tests.
- `create`, `create_v2` and `buy_v2` use exact Pump.fun full-key registry
  entries backed by the current public IDL/instruction documentation. Creator
  is not inferred from an account slot; the `create_v2` user account is index
  5 and the token program is index 7.
- A finalized public-RPC probe at slot `448814566` confirmed the current
  parsed versioned-transaction shape, lookup-table expansion, Pump.fun program
  identity and an exact `buy_exact_quote_in_v2` instruction tag. This is
  transport/protocol evidence, not a launch sample.

The 2026-09-20 checkpoint above predates the pinned local IDL decoder and the
accepted launch evidence recorded on 2026-09-21. The protected modes remain
unchanged and the source cannot authorize paper or live execution.

## 2026-09-20 early-alpha integration and operational closure

The approved early-alpha integration was implemented through commit `a522c99`
(`feat: persist staged alert delivery timing`); this closure pass adds the
PostgreSQL-backed runtime snapshot and restart fixes described below. The
authoritative baseline audit is [EARLY_ALPHA_GAP_AUDIT.md](../EARLY_ALPHA_GAP_AUDIT.md);
the design and execution record are [the design spec](../superpowers/specs/2026-09-19-early-alpha-runtime-integration-design.md),
[the implementation plan](../superpowers/plans/2026-09-19-early-alpha-runtime-integration.md),
and [the source matrix](../EARLY_ALPHA_SOURCE_MATRIX.md).

### Delivered path

The worker now composes canonical protocol decoding, stream cursor/gap
handling, `UltraEarlyDetector`, fail-closed `FastSafetyGate`, the existing
event-time `EarlyFeatureEngine`, wallet/creator/bundle evidence, organic
momentum projection, EarlyScore/decision, lifecycle transitions, append-only
early stage snapshots, the existing alert projector/outbox and Telegram
delivery path. Deep research remains outside the synchronous fast path.
Restart, duplicate, out-of-order and unresolved-gap contracts are covered by
deterministic tests.

Executable winner labels now require fresh liquidity, sellability and both
buy/sell impact evidence. Missing or stale evidence is
`UNKNOWN_EXECUTABILITY`; raw mark-price peaks remain separate from executable
peaks. Stage-specific 2x/5x/10x/20x/50x/100x labels, MFE/MAE, horizon labels,
`MissedWinnerAnalyzer`, `FalsePositiveAnalyzer`, and exact-mint benchmark
projections are research-only and cannot enter runtime scoring.

Alert payloads retain a durable `alert_timing` ledger containing decision,
projection, queue, delivery-start and Telegram API-send timestamps plus
derived latencies. `telegram_sent_at` is explicitly
`SENT_TO_TELEGRAM_API`; user delivery remains `UNKNOWN` unless a provider
offers authoritative user-delivery evidence. Existing alert dedupe and the
existing outbox remain the only delivery path.

### Verification evidence

```text
baseline make test: 1399 passed, 20 skipped, 7 warnings
current full make test with isolated PostgreSQL: 1419 passed, 7 warnings in 146.40s
current `make test` after raw-source changes: 1413 passed, 20 skipped, 7 warnings in 131.96s
current DB integration: 20 passed, 2 warnings; isolated PostgreSQL migration head 0011_collection_checkpoints
targeted post-fix unit tests: 13 passed
make verify: PASS (Python, frontend, migration, security and SBOM gates)
current make verify: PASS; 1413 passed, 20 skipped, 7 warnings; frontend 83 passed; SBOM 582 components
make lint: PASS
make typecheck: PASS (141 source files)
raw Solana ingestion focused suite: 31 passed; targeted Ruff and mypy PASS
frontend lint: PASS; frontend typecheck: PASS; frontend unit: 83 passed
frontend build: PASS (Docker image build)
migrations: PASS; head 0011_collection_checkpoints; 27 metadata tables
frontend browser: 36 passed, 4 skipped
no migration: existing head 0011_collection_checkpoints; 27 metadata tables
```

The report artifact is [early-alpha/report.md](../../artifacts/research/early-alpha/report.md)
with machine-readable [report.json](../../artifacts/research/early-alpha/report.json).
It currently reports `LIVE_SHADOW_INSUFFICIENT_SAMPLES`, zero live launches,
zero matured outcomes and no real-world alpha claim. Fixture evidence is not
mixed with live latency distributions.

### Provider and shadow limits

- `make doctor`: PASS for local protected-mode/configuration checks.
- `make paper-trading-doctor`: PASS; live execution remains disabled.
- `make solana-rpc-doctor`: PASS, public endpoint reachable (618.896 ms health probe).
- `make dexscreener-doctor`: PASS, exact canonical SOL mint metadata/pair route
  parsed (344.259 ms probe).
- `make free-provider-doctor`: PASS, `READY_FOR_FREE_READ_ONLY_SHADOW`.
- `make early-live-doctor`: PASS for local engines and HTTP core, with
  `UNVERIFIED_STREAM_TRANSPORT`.
- `make stream-integrity-doctor`: `BLOCKED_EXTERNAL` / configuration missing;
  keyless contracts PASS.
- `make telegram-doctor`: `BLOCKED_EXTERNAL` / configuration missing; no API
  call was attempted and no secret was printed.
- Public WebSocket smoke: `logsSubscribe` accepted and was cancelled cleanly;
  this is transport evidence only, not canonical launch evidence.
- Shadow start previously succeeded on isolated ports 55434/56381/18001/13001
  and all services were healthy. That run predates the raw source factory;
  no new live launch collection run is claimed by this checkpoint.
- Docker daemon is healthy (client/server 29.1.3, default context). The prior
  socket denial was a host permission/session issue, not a daemon failure; the
  isolated stack was run successfully without changing host privileges.
- Pump.fun `create`, `create_v2`, buy/sell variants and migration now have
  exact pinned registry entries; other protocol rows remain `TODO_VERIFY`,
  `SUPPORTED_NEEDS_REVERIFY` or `BLOCKED_EXTERNAL` as applicable. No
  unverified identity is treated as an authoritative decoder.

Reference examples FLEX, JUPCAT, URANUS, KMS, wildebeest and BLESS have no
verified historical MemeRadar observation in this checkout. They remain
`NOT OBSERVED / INSUFFICIENT HISTORICAL EVIDENCE`, are not hard-coded and are
not scoring exceptions.

## 2026-09-16 final release-gate correctness sprint

The resumed baseline was clean and synchronized at
`8e1600e760e1af72c8dd7726cafe3f156ed58200`; the saved checkpoint documents
were read before work began. The intentionally scoped correctness changes
were committed as `1e7aecc09019ae94a0a9d2291082e471f21847eb`
(`fix: close final release gate correctness gaps`). No scoring, provider
intelligence, lifecycle, execution path, UI feature or protected mode changed.

### Closed gaps

- Backup/restore now resolves source and target database identity, rejects
  aliases of the same database and any non-empty public target before
  `pg_restore`, and distinguishes `PASS`, `FAIL` and `BLOCKED_EXTERNAL`
  without persisting command stderr or connection URLs.
- Production dependency recovery uses one base-plus-production Compose command,
  tests PostgreSQL-only and Redis-only outages independently, and inspects the
  recovered API/worker environment for production readiness flags, protected
  modes and worker role-token absence.
- `production-build-e2e` and `prod-read-only-verify` require an explicit
  production-build URL; they cannot silently start the development server.
- Strict stack acceptance requires measured container liveness, restart counts,
  memory, worker liveness, dependency readiness, protected modes and
  `execution_eligible=false`; optional-provider counts remain truthful when
  unavailable.
- Release and reliability runbooks now separate deterministic checks from
  production-like local acceptance.

### Current evidence

```text
make verify: PASS; 1361 passed, 19 skipped, 7 warnings
focused post-commit correctness/config suite: 34 passed
Ruff: PASS
mypy: PASS (135 source files)
frontend unit: 24 files, 83 tests passed
frontend build: PASS
development browser: 36 passed, 0 failed, 4 skipped
production-build browser: 36 passed, 0 failed, 4 skipped
PostgreSQL integration: 19 passed, 2 warnings
migration head: 0011_collection_checkpoints; 27 metadata / 28 public tables
production Compose: missing-secret expansion fails closed; supplied contract PASS
strict stack soak: 100 iterations, 500 requests, 0 errors, 0 readiness failures
post-commit strict identity soak: final SHA, 5 requests, 0 errors, PASS
PostgreSQL-only and Redis-only dependency recovery: PASS
Docker backup/restore: PASS; 69611-byte custom dump, restore/read verified
host backup wrapper: BLOCKED_EXTERNAL (host PostgreSQL client binaries absent)
runtime npm audit: 0 vulnerabilities
full npm audit: 2 moderate dev-only Vitest findings; 0 high/critical
SBOM: 582 components, sha256:e63fadcc56b9461e192ae70e9bd01ba01dc6a4e223143ab71a09aca9875933aa
```

The Docker backup artifact digest was
`sha256:b33c0a0644537e6c424d04afb9af8e91afeed3c18077c42b33c4f802aa7d1ab8`;
restore verification found migration head `0011_collection_checkpoints`, 28
public tables, 2 observations and a successful application read. The strict
100-iteration artifact digest was
`sha256:3d1a65ba2f624d02b3eceea8c4234a4508883bd331847c9145c4864cc5b10e28`.

Fresh doctor classifications were: provider and Helius
`BLOCKED_EXTERNAL/CONFIGURATION_MISSING`; Solana public RPC `PASS/HEALTH_OK`;
Dexscreener `BLOCKED_EXTERNAL/EXTERNAL_UNAVAILABLE` for that probe;
free-provider aggregate `PASS/FREE_READ_ONLY_CORE_READY` with optional
providers unconfigured; stream integrity
`BLOCKED_EXTERNAL/CONFIGURATION_MISSING`; paper trading
`PASS/PAPER_QUOTE_PROVIDER_READY`; reliability
`BLOCKED_EXTERNAL/EXTERNAL_CHECK_NOT_RUN`.

The post-implementation release identity was generated from the implementation
commit with local image identity bound. Its artifact digest was
`sha256:7c08f07d8fa9cad1a33f3eafe91b752b0022187f3b95c205a771163af356d3c8`.
The final evidence-only documentation commit is intentionally separate; the
final release identity is regenerated after that commit and is reported in the
handoff.

Repository-controlled blockers are empty. External blockers remain hosted
Actions billing/runner access, branch protection/admin capability, managed
secret injection/deployment/rollback, managed backup scheduling/RPO/RTO,
sustained managed soak, registry manifest digests and credentialed external
provider validation. Real GMGN observations remain `0`, unique tokens/sample
units `0`, labels unavailable, `INSUFFICIENT_SAMPLES`, and live validation
`BLOCKED_EXTERNAL`.

## 2026-09-16 resumed final verification

The saved dirty sprint candidate was resumed without reset, restore, checkout,
clean or stash. The implementation was audited, verified and committed as
`769ee58f62e39e181e7464ce5057db4923b7aa05` (`fix: harden production read-only
release boundaries`). The implementation commit was pushed to `origin/main`.

### Verification

```text
make verify: PASS; 1349 Python passed, 19 skipped, 7 warnings
Ruff: PASS
mypy: PASS (135 source files)
frontend unit: 24 files, 83 tests passed
frontend build: PASS
Compose smoke/contract tests: 30 passed
PostgreSQL integration: 19 passed, 2 warnings
migration head: 0011_collection_checkpoints
migration metadata tables: 27; public tables including alembic_version: 28
development browser: 36 passed, 0 failed, 4 skipped (preserved checkpoint evidence)
production browser: 36 passed, 0 failed, 4 skipped
secret scan/security review: PASS
runtime npm audit: 0 vulnerabilities
full npm audit: 2 moderate dev-only Vitest findings, 0 high/critical
SBOM: 582 components, sha256:e63fadcc56b9461e192ae70e9bd01ba01dc6a4e223143ab71a09aca9875933aa
synthetic benchmark: 1000 iterations, synthetic_local, external_network=not_run
production-like stack soak: 100 iterations, 500 requests, 0 errors, 0 readiness failures
stack soak: worker liveness PASS, 0 restarts, 0 duplicate-event delta
dependency outage/recovery: outage degraded as expected, recovery PASS
Docker backup/restore: PASS; 70124-byte custom dump, restore/read verified
host backup wrapper: BLOCKED_EXTERNAL (host pg_dump/pg_restore unavailable)
```

The production-like stack smoke and soak used the rebuilt API/worker/web
services with viewer-authenticated reads. The web mutation gateway returned
`403` without credentials and the read gateway returned `200` through its
server-side viewer-only path. No browser credential or admin token was
returned. The production browser suite independently verified the same
read-only boundary.

### Security and provider boundaries

- `APP_ENV` absent defaults to development; `development` and `production` are
  valid; `prod`, `produciton`, empty and arbitrary values are rejected.
- Production Compose fails closed when DB, Redis, API-role or web inputs are
  missing. Local Compose retains only its explicitly local development
  defaults.
- The worker receives no `VIEWER_API_TOKEN`, `OPERATOR_API_TOKEN`,
  `ADMIN_API_TOKEN` or `EXECUTION_API_TOKEN`; API role validation is API-owned.
- Solana public RPC is the free minimum path. Helius is optional enhancement;
  missing Helius does not block free read-only readiness. BNB is not enabled by
  default and explicit BNB enablement requires a canonical RPC. Robinhood uses
  its canonical transport. GMGN remains optional, disabled by default,
  `LIVE_SHADOW`, weight zero and non-authoritative with no execution path.
- Real GMGN observations: `0`; unique tokens/sample units: `0`; winner/rug
  labels: `null`; sample status: `INSUFFICIENT_SAMPLES`; live validation:
  `BLOCKED_EXTERNAL`.

### Release identity

```text
git SHA: 769ee58f62e39e181e7464ce5057db4923b7aa05
app/API version: 0.1.0 / 0.1.0
config hash: sha256:02357dab7e94009965762ca8e9a0a811ffbe4c1acbbf5dcf3cace68a5b92e1c3
migration head: 0011_collection_checkpoints
migration table count: 27 metadata tables (28 public including alembic_version)
SBOM digest: sha256:e63fadcc56b9461e192ae70e9bd01ba01dc6a4e223143ab71a09aca9875933aa
api image ID: sha256:6e5d8d68ddedff562b50fbad2ee81c7c1a2b5c0dbd829b9b6c0f6fbe9402dba5
worker image ID: sha256:5e818c417389830d0dc0340aed498d64caf857fda5449e18ddd93f6917a4e21b
web image ID: sha256:525d0383606e85a8b9f387524b2aa249180f42b8746ed40f92390291b40127e0
registry digests: unavailable; IDs above are local immutable image identities
```

Hosted Actions run `35100554937` for the implementation SHA completed with
all deterministic jobs failing at startup with zero executed steps/no runner;
the release identity job was skipped with zero steps. This is
`BLOCKED_EXTERNAL`, not local test evidence. Repository-controlled blockers are
empty. External blockers are hosted Actions billing/runner access, branch
protection/admin access, managed secret injection/deployment/rollback,
managed backup scheduling/RPO/RTO, sustained managed soak, and credentialed
Helius/GMGN/Telegram/stream acceptance.

The resulting classification is:

```text
REPOSITORY_PROD_READ_ONLY_ENGINEERING_READY
PROD_READ_ONLY_NOT_ACCEPTED
ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION
REAL_WORLD_ALPHA_NOT_YET_PROVEN
NOT_READY_FOR_PROD_PAPER_AUTO
NOT_LIVE_MONEY_READY
```

## 2026-09-15 paused root-cause hardening checkpoint

Work was intentionally paused at the operator's request after the focused
hardening regressions, before the final full-gate, commit and push phase. The
starting synchronized candidate remains
`f61070faac7a1b73fe686b0ce2870d3cb11cdc09`; all sprint changes below are
currently uncommitted.

Latest checkpoint evidence:

```text
focused hardening suite: 122 passed
Compose contract suite: 29 passed
production-build browser: 36 passed, 0 failed, 4 skipped
development browser: 36 passed, 0 failed, 4 skipped
production-like stack soak: 100 iterations, 500 requests, 0 errors, 0 readiness failures
production-like stack soak: worker liveness PASS, 0 restarts, 0 duplicate-event delta
production-like stack soak: execution_eligible=false, protected modes exact
fresh disposable dependency outage/recovery drill: outage degraded, recovery PASS
disposable backup/restore: backup and restore PASS; application read path exercised
host backup wrapper: BLOCKED_EXTERNAL (pg_dump/pg_restore unavailable on host)
real GMGN observations: 0
sample status: INSUFFICIENT_SAMPLES
GMGN live validation: BLOCKED_EXTERNAL / disabled without credentials
```

Two additional root causes were found and fixed after the previous checkpoint:
local Compose now derives the API database URL from the same
`POSTGRES_PASSWORD` source as the Postgres service, and the production web
container derives its server-side viewer credential from the API
`VIEWER_API_TOKEN` so SSR reads cannot use an unrecognized token. The backup
drill now invokes the existing SQL read service against the restored database
instead of asserting `application_read` without exercising it.

The remaining resume sequence is: rerun the full current verification matrix
after these final edits; rebuild API/worker/web images and generate the final
release identity; update the gap matrix and readiness documents with final
SHAs/artifact digests; audit the diff; commit and push; then recheck
`HEAD == origin/main`. Hosted Actions execution, branch-protection API access,
managed secrets/hosting/backup/rollback/soak, and credentialed Helius/GMGN/
Telegram/stream acceptance remain external blockers.

## 2026-09-15 root-cause production hardening

The hardening candidate starts from synchronized `f61070faac7a1b73fe686b0ce2870d3cb11cdc09`.
It closes repository-controlled confused-deputy, environment fail-open,
production secret fallback, worker least-privilege, provider-capability,
evidence-isolation, CI-parity, soak-semantics, legacy-mode and release-image
identity gaps. No production score/risk weight, protected mode, execution
path, provider-specific scorer, duplicate lifecycle, wallet graph or alert
pipeline was added. The implementation commit is pending final verification;
the gap matrix records the before/after evidence.

### Current evidence

```text
full Python suite: 1344 passed, 19 skipped, 7 warnings
frontend unit suite: 24 files, 83 tests passed
frontend browser development: 36 passed, 0 failed, 4 skipped
frontend browser production build/container: 36 passed, 0 failed, 4 skipped
PostgreSQL integration: 19 passed, 2 warnings on disposable PostgreSQL 16.14
migrations: head 0011_collection_checkpoints, 27 metadata / 28 public tables
production stack soak: 100 iterations, 500 requests, 0 errors, 0 readiness failures
real GMGN observations: 0
unique GMGN tokens: 0
independent/unique-token sample units: 0
winner labels: null
rug labels: null
first/last real observation: null / null
sample status: INSUFFICIENT_SAMPLES
GMGN live validation: BLOCKED_EXTERNAL / disabled without credentials
```

The local production-like stack was deployed with the production Compose
override and safe local-only credentials. `/health/live`, dependency readiness,
viewer-authenticated operations/provider/readiness views, execution lock and
protected modes were verified. A dependency outage/recovery drill passed.
The repository backup wrapper correctly reports `BLOCKED_EXTERNAL` because
the host lacks `pg_dump`/`pg_restore`; the Docker-native disposable drill
created a 70,038-byte custom dump, restored it successfully, and proved
application reads. This is not relabeled as a wrapper PASS.

Current external blockers remain hosted Actions runner/billing availability,
GitHub branch-protection API access (HTTP 403), managed secret injection and
deployment/rollback, managed backup scheduling/RPO/RTO, sustained managed
soak, and credentialed Helius/GMGN/Telegram/stream acceptance. Full npm audit
has only the documented moderate dev-only Vitest finding
`GHSA-82fw-gwwq-j7x9`; the production graph has zero vulnerabilities.

## 2026-09-15 final PROD_READ_ONLY closure sprint

The synchronized baseline was `4de20300c064ce903ecd482bd52a12ccf7a23114`
(`main == origin/main`, clean worktree). This closure sprint addressed the
three reviewed correctness boundaries and the remaining repository-controlled
release defects without adding a provider-specific scorer, risk engine,
lifecycle, execution path, wallet graph or alert pipeline.

Implementation commit: `5a4d5e4ec167bea162ca4f2308f800c1e0dd4ed7`.

### Root-cause fixes

- Evidence policy now allow-lists recognized collection modes and admits only
  explicit `PRODUCTION` rows to production-facing projections. Missing mode is
  retained only for audited legacy rows with no trust markers. Provider
  `evidence_promotion_state` is never promotion authority; shadow payloads
  claiming `PROMOTED` remain ineligible.
- The full production decision chain has a provider-neutral equality regression
  for baseline versus baseline plus GMGN `LIVE_SHADOW`. Canonical GMGN rows
  remain persisted and research/readiness/replay-visible.
- Readiness uses raw observation volume separately from the bounded
  `unique_token_sample_count` proxy. One token polled 100 times remains one
  sample unit and `INSUFFICIENT_SAMPLES`; no statistical independence claim is
  made.
- Production configuration now requires database/Redis/readiness and strong
  role tokens, the web gateway reads server-only runtime environment values,
  and the web image is a non-root standalone production build. The provider
  doctor Make targets use the supported module invocation.
- The web runtime/build boundary and two browser contract defects were fixed;
  the production-like authenticated browser matrix is `33 passed, 0 failed,
  7 scoped skips`.
- The frontend runtime graph has no vulnerabilities; full npm audit retains
  only two moderate dev-only Vitest findings (GHSA-82fw-gwwq-j7x9), requiring a
  separate major upgrade decision. Python `pip-audit` is clean.

### Verification snapshot

- `make verify`: `1330 passed, 19 skipped, 7 warnings`; Ruff, mypy, CSS
  contract, frontend lint/typecheck/tests (`23 files, 80 tests`), Compose,
  secret scan, migration check, local security review and SBOM all pass.
- Disposable PostgreSQL 16.14 integration: `19 passed, 2 warnings`; migration
  head `0011_collection_checkpoints`; 27 metadata tables / 28 public tables
  including `alembic_version`. Checkpoint/CAS, persistence, readiness and
  repeated-poll accounting are covered.
- Backup/restore and a non-destructive rollback from the prior ref were proven
  against disposable/local Compose infrastructure. The bounded read-only
  production-soak tool completed 100 synthetic iterations; live acceptance is
  not claimed.
- Current SBOM: 582 components, digest
  `sha256:e63fadcc56b9461e192ae70e9bd01ba01dc6a4e223143ab71a09aca9875933aa`.

### Current data and blockers

```text
real GMGN observations: 0
unique SOL/BSC tokens: 0
unique token sample units: 0
winner labels: null
rug labels: null
first/last real observation: null / null
sample status: INSUFFICIENT_SAMPLES
GMGN live validation: BLOCKED_EXTERNAL (no credentialed real provider access)
```

Local API/worker/web/PostgreSQL/Redis health, auth, runtime provider-state
truthfulness, protected modes and `execution_eligible=false` are verified.
`PROD_READ_ONLY_ACCEPTED` is not claimed because hosted Actions execution is
blocked by the account runner/billing state, branch protection returns GitHub
API HTTP 403 for the private repository plan, and managed production
deployment/rollback, backup/restore, sustained soak, and external-provider
credentials are not available. These exact results are recorded in the
[closure gap matrix](../PROD_READ_ONLY_CLOSURE_GAP_MATRIX_2026-09-15.md).

The hosted CI run for the exact implementation SHA was `34964417900`. Backend,
Frontend, Compose and Secret jobs failed at startup with zero steps and no
runner; Release candidate identity was skipped with zero steps. This is
classified `BLOCKED_EXTERNAL`, not a local test pass or code failure.

## 2026-09-14 external alpha intelligence integration

The current root-cause hardening baseline is `origin/main` at
`76794f4177a5c0efe5c6f7379d749908f66b344b`; the worktree was clean and the
local remote-tracking ref matched before implementation. The initial fetch
could not update `.git/FETCH_HEAD` and the network retry was blocked by DNS;
this environmental limitation is recorded in the [before gap
matrix](../GMGN_ROOT_CAUSE_HARDENING_GAP_MATRIX_2026-09-14.md). The committed
requirements and plan remain the [integration specification](../superpowers/specs/2026-09-14-external-alpha-intelligence-integration.md)
and [implementation plan](../superpowers/plans/2026-09-14-external-alpha-intelligence-integration.md).

### Implementation result

The implementation checkpoint is commit `9a4e9d1`
(`fix: harden GMGN shadow evidence boundaries`).

- GMGN remains a direct, read-only, optional backend adapter using the audited
  `https://openapi.gmgn.ai` contract. It is disabled by default, requires an
  explicit API key and HTTPS endpoint, never enters the core provider route
  plan, has `scoring_weight=0`, and runs only in `LIVE_SHADOW` when configured.
  No GMGN execution, signer, wallet-custody or subprocess surface exists.
- Signed trader `profit` uses a dedicated signed decimal parser; physical
  quantities, ratios and counts retain their non-negative/count validation.
  Snapshot and aggregate enrichment rows retain `occurred_at=null` and record
  their observation semantics instead of pretending to be provider events.
- The provider-neutral evidence policy excludes unpromoted `LIVE_SHADOW` rows
  from production-facing raw-observation projections while replay/research
  opts in explicitly. Canonical observations remain persisted for readiness,
  replay, ablation and diagnostics.
- Readiness keeps raw real observation volume separate from independent sample
  units, with independent units derived from unique provider tokens. Fixtures,
  mocks, synthetic, demo, replay-only and redacted rows remain excluded.
- Runtime read and operations projections derive GMGN `enabled`, `configured`
  and health state from canonical settings without exposing credentials.
- Helius taxonomy and canonical lifecycle behavior remain unchanged except for
  regression protection; a failing shadow lifecycle test proved the shared
  evidence policy was also required at the lifecycle owner.
- No scoring/risk weights, database migration, protected mode, signer,
  execution path, duplicate wallet graph, alert engine, reliability framework,
  or second Helius stack was introduced. Solbeam remains documentation/UI
  research only.

### Current GMGN real-data inventory

```text
real observations: 0
unique SOL/BSC tokens: 0
independent sample units: 0
candidate observations: 0
caller/KOL observations: 0
smart-wallet observations: 0
holder/distribution observations: 0
security/risk observations: 0
first/last real observation: null / null
provider errors/rate limits: null / null (no persisted real attempt)
winner/rug labels: null / null
sample status: INSUFFICIENT_SAMPLES
live validation: BLOCKED_EXTERNAL
```

### Verification evidence

- Focused hardening suite: `49 passed, 1 warning` for GMGN, shadow isolation,
  read API, readiness API and operations; the Helius taxonomy/provider suite
  passed `26`; the lifecycle suite passed `26`; the readiness contract/API
  suite passed `6, 1 warning`; and the worker/provider-doctor/provider-health/
  transport suite passed `26`.
- `make verify` passed locally: Python `1306 passed, 18 skipped, 1 warning`;
  frontend CSS contract `290` classes across `59` files; frontend lint and
  typecheck passed; frontend tests `22 files, 79 tests passed`; Compose,
  secret scan, migrations, deterministic security review and SBOM passed.
  SBOM: `581` components, digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- `make frontend-build` passed and generated `15` routes. The PostgreSQL
  integration target was skipped because `MEMERADAR_TEST_DATABASE_URL` is not
  configured; this is not counted as a pass.
- Browser verification is environmental: the dev journey run recorded `26
  passed, 10 failed, 4 skipped`, dominated by dev-server/page-load timeouts;
  a production-server retry was blocked by the Chromium and system Chrome host
  sandbox (`Operation not permitted`). These browser checks are not reported
  as passed.
- `make provider-doctor` remains blocked by its existing direct-script import
  defect; the module invocation ran and reported `BLOCKED_EXTERNAL` with
  missing Helius credentials. Deterministic security checks passed, while
  external container/npm/pip scans remain `BLOCKED_EXTERNAL`; direct web
  `npm audit` reports `3 vulnerabilities (2 moderate, 1 high)` and no audit
  fix or dependency upgrade was applied in this sprint.
- Final `git diff --check`, lint, typecheck, secret scan, security review, SBOM
  and migration verification passed after the documentation updates.

## Current blockers

- Compliant historical-real X/Telegram data, CabalSpy-style wallet/KOL stream
  data, Chainlink feed identities, and matured live-shadow observations are
  unavailable; real-provider validation is `BLOCKED_EXTERNAL` and calibration
  is `INSUFFICIENT_SAMPLES`.
- Latest hosted CI run `34717558195` ran for final pushed SHA
  `3b6aa7f6460a366f990d3de195106743f3ba49e8`. Backend quality, Frontend
  quality, Compose contract, and Secret scan each terminated with `failure`
  and zero executed steps; Release candidate identity was `skipped` with zero
  steps. This repeats the previously documented account billing/spending
  restriction pattern, so hosted CI is `BLOCKED_EXTERNAL`, not code failure or
  PASS. Managed backup/restore and production-like dependency restart/soak
  remain externally unverified.
- PR #3 (`feat: add B+C early-alpha Telegram alerts`) is still `OPEN` with
  `merged=false`; the current API reports `mergeable_state=unknown`, and its
  head is `82f14b33152bb9c1cc2c91037e19eebe2d315b4d` against base
  `1fd899b35676e9e3cfbf2a973941f34d51d107f6`. Its branch was inspected and
  was not merged or cherry-picked. The current main implementation corrects
  the architecture with the canonical state machine, persisted snapshots,
  dedupe/retry/restart behavior, and shared delivery path.
- `MAIN_BRANCH_PROTECTION_NOT_ENFORCED`: the GitHub branch-protection API
  returned HTTP 403 because the private repository requires GitHub Pro or
  public visibility for that feature. No repository protection is claimed.
- The browser gateway remains fail-closed when server credentials are absent;
  with injected test-only server credentials, authenticated acceptance is
  covered without exposing tokens to browser JavaScript.
- Optional Helius, Birdeye, social, Telegram, stream, narrative, and external
  wallet enrichment may report unavailable or degraded; the free core remains
  provider-independent.

No blocker changes the readiness classification or authorizes a mode change.

## 2026-09-13 root-cause data-integrity hardening sprint

Baseline source of truth was `origin/main` at
`b0ff4192d220b3511043ace3653164c8c3f505f7`; `main` was clean and
synchronized before implementation. PR #3 remains open and untouched; it was
not merged, cherry-picked, or used as the source of truth.

### Before → after matrix

| Area | Before | After | Result |
|---|---|---|---|
| Real evidence classification | `LIVE_SHADOW` was used as the evidence class, so readiness excluded real shadow observations | `evidence_origin=REAL_EXTERNAL` is independent from `collection_mode=LIVE_SHADOW`; fixtures remain non-real | `RESOLVED` |
| Collection mode | Mode and evidence origin were conflated | Origin is `REAL_EXTERNAL`/`SYNTHETIC`/`FIXTURE`/`REPLAY`/`REDACTED`; mode is `LIVE_SHADOW`/`RESEARCH`/`PRODUCTION` | `RESOLVED` |
| Candidate rediscovery | `CandidateRepository.add` could overwrite the lifecycle aggregate | Discovery-only refresh preserves state, score, risk, rejection, and transition history | `RESOLVED` |
| Candidate first-seen semantics | Rediscovery could overwrite the canonical discovery boundary | Earlier verified discovery updates candidate/token first-seen only; transition timestamps are not rewritten | `RESOLVED` |
| Observation replay | Same immutable event with later transport timestamps raised a conflict | Immutable replay is benign; changed immutable payload remains `IdempotencyConflict` | `RESOLVED` |
| Checkpoint atomicity | Same-transaction behavior lacked adversarial proof | Observation/candidate/checkpoint writes roll back together | `RESOLVED` |
| Checkpoint concurrency | First-run insert and stale cursor overwrite were not proven | PostgreSQL upsert/row lock plus compare-and-set prevents stale cursor regression | `RESOLVED` |
| Provider telemetry | Runtime collection attempts were not persisted for readiness | Generic `provider.collection_health` observations persist success, error class, rate-limit state, and item counts | `RESOLVED` |
| Rate-limit count | Missing telemetry could look like measured zero | Persisted attempts are counted; no attempt is `null`/`UNKNOWN` | `RESOLVED` semantics; current data `INSUFFICIENT_SAMPLES` |
| Provider error count | Missing telemetry could look like measured zero | Persisted failed attempts are counted; no attempt is `null`/`UNKNOWN` | `RESOLVED` semantics; current data `INSUFFICIENT_SAMPLES` |
| Winner labels | No runtime canonical matured outcome source was found | Readiness returns `null` with `MADEONSOL_LABELED_OUTCOMES_UNAVAILABLE`, never fabricated zero | `INSUFFICIENT_SAMPLES` |
| Rug labels | No runtime canonical matured outcome source was found | Readiness returns `null` with the same explicit unavailable reason | `INSUFFICIENT_SAMPLES` |
| Provider health runtime composition | Catalog health could have no MadeOnSol rows to overlay | Canonical registry capabilities seed `UNKNOWN`; durable collection-health observations overlay actual state | `RESOLVED` |
| Readiness over 5,000 rows | DB projection truncated the aggregate input at `MAX_STORAGE_ROWS=5000` | SQL aggregates compute totals; bounded detail retrieval remains separate | `RESOLVED` |
| PostgreSQL acceptance | SQLite/fake-UoW coverage did not prove transaction semantics | Real PostgreSQL covered migration round-trip, rollback, replay, rediscovery, worker restart, checkpoint writers, and runtime readiness | `RESOLVED` |
| Caller/wallet/creator research consumption | MadeOnSol labels were raw canonical research observations | They remain raw-only by deliberate design; no provider-specific projection or confidence inflation was added | `NOT_NEEDED` for this integrity sprint |

### Proven runtime path

The real worker path is now covered end-to-end by a PostgreSQL integration
test:

```text
MADEONSOL_ENABLED
→ ProviderBundle
→ MadeOnSolRobinhoodAdapter
→ CandidateDiscoveryCollector
→ CandidateRepository + candidate.discovery Observation
→ enrichment Observations
→ ObservationRepository + collection checkpoint
→ MadeOnSolReadinessReport
→ /v1/readiness.alpha_validation
→ Web readiness projection
```

The worker supplies `evidence_origin=REAL_EXTERNAL` and
`collection_mode=LIVE_SHADOW`. A fake external transport produced one
candidate and one enrichment observation exactly once, preserved provider
event time through delayed observation, and appeared in readiness only while
explicitly marked real. Fixture/synthetic origin never contributes to the
real count. Retry/restart identity, valid-empty discovery, dynamic snapshot
identity, LP-event identity, and malformed/timeout/429 handling remain on the
existing provider/collector seams.

### Runtime counts and classification

The actual local database contains no compliant MadeOnSol sample:

```text
real observations: 0
unique Robinhood tokens: 0
caller/KOL observations: 0
smart-wallet observations: 0
deployer observations: 0
holder/distribution observations: 0
bundle/LP/security observations: 0
mature winner labels: null / UNKNOWN
mature rug labels: null / UNKNOWN
rate-limit events: null / UNKNOWN (no persisted collection attempt)
provider errors: null / UNKNOWN (no persisted collection attempt)
status: INSUFFICIENT_SAMPLES
```

No production alpha/risk/execution weight changed. No migration or schema
change was required; migration verification remains at head
`0011_collection_checkpoints` with 27 tables.

### Verification

- Full Python: `1263 passed, 18 skipped, 1 warning`.
- PostgreSQL integration: `18 passed, 1 warning` with local
  `MEMERADAR_TEST_DATABASE_URL`, including the end-to-end worker round trip,
  >5,000-row readiness aggregation, replay/conflict, candidate lifecycle,
  rollback, and concurrent checkpoint tests.
- Telegram Early Alpha: `31 passed`; ordinary `AlertRenderer`: `13 passed`.
- Vitest: `78 passed` across `22` files; frontend lint, typecheck and
  production build passed.
- Browser: `36 passed, 4 skipped` of 40; the isolated authenticated-free
  serial run covered all requested routes, themes, and four viewports. The
  four skips require unavailable test-only authenticated/stateful credentials.
- CSS contract, migrations, security review, SBOM, and `git diff --check`
  passed. SBOM remains 581 components with digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- `make verify` passed with the same local gates; its security report keeps
  container/npm/pip external scans `NOT_RUN` and external acceptance
  `BLOCKED_EXTERNAL`.
- Latest hosted Actions state: run `34717558195`, HEAD
  `3b6aa7f6460a366f990d3de195106743f3ba49e8`; Backend quality, Frontend
  quality, Secret scan, and Compose contract were `failure` with `0` executed
  steps, and Release candidate identity was `skipped` with `0` steps.
- Main branch protection remains unverified; the GitHub protection endpoint
  returned HTTP `403`.

Implementation commit: `09e0caa981b5e333ce2baaf6d80d06c76fc950ef`.

### Remaining blockers and next task

- `BLOCKED_EXTERNAL`: compliant read-only MadeOnSol credentials/real data,
  hosted Actions billing/spending restriction, and GitHub branch-protection
  API HTTP 403. No external success is fabricated.
- `INSUFFICIENT_SAMPLES`: real observations, matured winner/rug labels,
  caller/wallet samples, calibration, precision/recall, false-positive rate,
  lead time, and extreme-winner capture remain unmeasured.
- Protected modes remain exactly
  `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Production classification remains `NOT_PRODUCTION_READY`; engineering is
  `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION` because the runtime can
  now ingest and report real external evidence without manual rewriting.
- Exact next unfinished task: obtain compliant read-only MadeOnSol access,
  collect real Robinhood observations and matured outcomes, then run the
  existing no-lookahead/out-of-sample calibration gate without changing
  production weights or protected modes.

## Prior engineering evidence

The latest local full gate recorded after the alpha-readiness and paper-integrity
follow-up:

- `make verify`: 1251 Python tests passed, 11 skipped, 1 warning; 22 frontend
  test files and 77 Vitest tests passed. Skips remain environment/optional
  provider cases and are not counted as passes.
- Telegram-focused tests: 31 passed (`test_early_alpha_alert.py` and
  `test_early_alpha_pipeline.py`); ordinary `AlertRenderer` regression passed.
- Ordinary `AlertRenderer` focused regression: 13 passed
  (`tests/unit/test_alert_pipeline.py`).
- Ruff, strict mypy across 133 source files, frontend lint/typecheck,
  production build, Compose validation, tracked-file secret scan, migrations,
  security review, SBOM, CSS contract, and `git diff --check`: passed.
- Migration head: `0011_collection_checkpoints`; metadata tables: 27. Runtime
  migration was skipped because `MEMERADAR_DATABASE_URL`/`DATABASE_URL` was
  absent; offline PostgreSQL SQL generation verified both new unique indexes.
  Database integration was skipped because `MEMERADAR_TEST_DATABASE_URL` was
  absent.
- SBOM: 581 components, digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- Security review returned `PASS` with protected modes verified, while its
  external acceptance remained `BLOCKED_EXTERNAL` and container/npm/pip
  external scans remained `NOT_RUN`.
- Backend/API/frontend parity is closed for the current routes: canonical
  runtime-settings mutation with restart-required and secret-safe semantics,
  protected-mode enforcement, authenticated server gateways, universal
  multichain search, multichain shell state, readiness projection, provider
  configuration/runtime-health views, caller/opportunity evidence, and a
  generated route parity manifest are covered by focused tests.
- Fresh production browser acceptance across 1440x900, 1024x768, 768x1024,
  and 390x844 was `36 passed, 4 skipped` out of 40. The visual matrix covered
  all 15 requested routes in dark and light themes, including global overflow,
  topbar overlap, mobile navigation, local table behavior, and fail-closed
  route states. The four skips are authenticated credential/stateful journeys;
  no test-only credentials were available, so authenticated Settings mutation
  was not claimed. The browser suite did not exercise live-money execution.
- Missing frontend evidence checks cover explicit `0` versus `UNKNOWN`, all
  operational counters, provider aggregation, settings numeric drafts, graph
  root selection, and persisted Early Alpha before→now snapshots. No
  `0 → current` fallback remains for absent tracked evidence.
- Web↔Telegram parity manifest now covers `/tokens/[tokenId]`, `/ultra-early`,
  and `Telegram/EarlyAlpha`; the Early Alpha renderer consumes only the
  canonical projection, uses `COHORT SIMILARITY`, and renders confirmation
  conflict when authoritative risk is unknown, blocked, stale, invalid,
  unavailable, or incompatible.
- Early Alpha transitions are explicit:
  `NOT_CONFIRMED → CONFIRMED|DEGRADED|INVALIDATED|CONFLICT`,
  `CONFIRMED → DEGRADED|INVALIDATED|CONFLICT`,
  `DEGRADED → CONFIRMED|INVALIDATED|CONFLICT`,
  `CONFLICT → DEGRADED|INVALIDATED|CONFIRMED` only after risk conflict
  resolution; `INVALIDATED` is terminal. Same-state repeats require explicit
  material evidence change and stable logical dedupe identity.
- Early Alpha dedupe/retry/restart/correlation tests pass: persisted alert
  state and snapshots prevent duplicate initial/follow-up events, failed
  transport retries the same dedupe key, and follow-ups retain bounded
  correlation metadata. No raw provider payload or secret is rendered.
- Release identity and synthetic soak evidence remain local/measurement-only;
  external acceptance remains `BLOCKED_EXTERNAL`.

The bounded `make alpha-readiness` report over the existing redacted case-study
fixture is truthful: `sample_count=7`, `real_sample_count=0`,
`real_winner_count=0`, `real_rug_count=0`, `caller_observation_count=0`,
`smart_wallet_observation_count=0`, evidence class `SYNTHETIC_REDACTED=7`,
provider `UNKNOWN=7`, `no_lookahead_verified=true`, and status
`INSUFFICIENT_SAMPLES`. The report is an inventory seam, not calibration.

## 2026-09-13 frontend parity and precision workstation sprint

Baseline source of truth was `origin/main` at
`a0f3ae4d3bfdf52eee08822cf36a07737bc6daa0`; `main` was clean and
synchronized before implementation. PR #3 remains open and untouched; it was
not merged, cherry-picked, or used as a source of truth. The backend data-
integrity hardening from `09e0caa981b5e333ce2baaf6d80d06c76fc950ef` was
preserved.

### Before → after frontend/backend parity matrix

| Area | Before | After | Result |
|---|---|---|---|
| Route/field ownership | Historical coverage and silent omissions | Machine-reviewable `docs/FRONTEND_BACKEND_PARITY.md`, route owners, backend route families, and categorized omissions | `RESOLVED` |
| Parity enforcement | Manifest checked only for basic shape | Every entry has an owner/backend route and every omission has an allowed explicit status/reason | `RESOLVED` |
| Provider capability/runtime health | Frontend parser dropped `capability_status` and conflated runtime state | `CAPABILITY` and `RUNTIME HEALTH` are parsed and rendered as separate backend fields; unknown remains unknown | `RESOLVED` |
| Readiness layers | Success showed alpha data, but failed reads collapsed the operator model | Engineering, alpha-evidence, and production lanes render separately; failed reads keep lanes `UNKNOWN` | `RESOLVED` |
| Visual system | Functional but generic/flat page treatment and duplicated heading patterns | Canonical `apps/web/DESIGN.md`, design tokens, shared `PageHeader`, restrained surfaces, semantic state styling, and responsive shell refinements | `RESOLVED` |
| CSS contract | Critical graph classes were checked narrowly | All static frontend classes are checked: 290 classes across 59 files | `RESOLVED` |
| Mobile navigation | Floating control could cover content | Navigation control is reserved in the topbar region with accessible labeling and reduced-motion support | `RESOLVED` |
| Frontend business logic | Must remain projection-only | No frontend alpha, risk, insider, provider-health, or readiness calculation was added | `RESOLVED` |

### Scope and artifacts

The inspected design methodology was the MIT-licensed
[`xiaopu-ai/web-design`](https://github.com/xiaopu-ai/web-design) repository at
commit `22a4f482cc4caa2394391c0c31ff0aefd1908774`. Its methodology and
quality principles were used only as a reference; MemeRadar retains its own
teal, evidence-first workstation identity and no external logo, font, or brand
identity was copied.

The canonical UI contract is now [apps/web/DESIGN.md](../../apps/web/DESIGN.md),
and the route/field inventory is
[FRONTEND_BACKEND_PARITY.md](../FRONTEND_BACKEND_PARITY.md). The audit covered
the 15 requested operator routes (`/`, `/radar`, `/ultra-early`,
`/opportunities`, `/positions`, `/wallets`, wallet detail, `/wallet-graph`,
`/callers`, token detail, `/providers`, `/operations`, `/audit`, `/settings`,
and `/readiness`) plus global search, health/operations/control routes,
runtime settings, and `Telegram/EarlyAlpha` parity. Shared page headers,
surface/typography/spacing tokens, state treatment, local table scrolling,
responsive shell behavior, reduced motion, and accessible focus treatment were
upgraded without creating a second component library or adding a runtime
dependency.

The only backend truth surfaced differently in this sprint is the existing
provider `capability_status` and `runtime_health` pair, parsed and shown
separately by the generic provider card. Readiness lanes are also a frontend
projection of the existing `/v1/readiness` response. No backend service,
schema, migration, provider adapter, scoring/risk policy, Telegram semantic,
or execution path changed. `devIndicators: false` was removed because it hid
framework diagnostics without being a product contract; production browser
verification remains authoritative.

### Verification

- Full local `make verify`: PASS. Python `1263 passed, 18 skipped, 1
  warning`; Vitest `79 passed` across `22` files; Ruff, strict mypy, frontend
  lint/typecheck, Compose validation, secret scan, migrations, security review,
  SBOM, CSS contract, and `git diff --check` passed.
- CSS contract: `290` static frontend classes checked across `59` files.
- Production build: PASS; Next `16.3.3` generated the complete route table.
- Browser matrix: `36 passed, 4 skipped` of `40` in the serial production
  run, covering all requested routes, dark/light themes, and
  `1440x900`, `1024x768`, `768x1024`, and `390x844`. The four skips require
  unavailable test-only authenticated/stateful credentials. A parallel
  browser attempt had a session-level Chrome flake; the isolated test and
  final serial matrix passed, so no arbitrary delay was added.
- PostgreSQL integration was not rerun because this sprint changed no backend
  code or schema; the prior root-cause baseline remains `18 passed` and
  migration head `0011_collection_checkpoints` with `27` tables.
- Security remains `PASS` with the four protected modes verified; external
  container/npm/pip scans remain `NOT_RUN` and external acceptance remains
  `BLOCKED_EXTERNAL`. SBOM remains `581` components with digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- Development-only Playwright requests against `next dev` were blocked by
  the current Next origin/HMR harness when using `127.0.0.1`; production
  server acceptance passed. No product behavior was inferred from that
  harness condition and no timeout/sleep workaround was introduced.

### Data, safety, and next task

Real MadeOnSol observations remain `0`; unique Robinhood tokens, caller/KOL,
smart-wallet, deployer, holder/distribution, and security/LP observations are
all `0`. Mature winner/rug labels remain `null`/`UNKNOWN`, and alpha
validation remains `INSUFFICIENT_SAMPLES`. No fake sample or readiness claim
was added. Protected modes remain exactly
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`; production remains
`NOT_PRODUCTION_READY` while engineering remains
`ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION`.

Implementation commit: `066d59f` (`feat: complete frontend parity and
workstation design`). Exact next unfinished task: obtain compliant real
provider evidence and run the existing out-of-sample alpha calibration gates;
no additional frontend semantics or scoring weights are required before that
data exists.

## 2026-09-12 A+C end-to-end shadow proof and Web evidence parity

This is the current sprint checkpoint. Baseline source of truth was
`origin/main` at `e14b889b3aa992f9b088eaaa9f0c4455363db2b0`; it was clean and
synchronized before implementation. No PR branch was merged or cherry-picked.

### Before → after gap matrix

| Capability | Before | After | Evidence / target |
|---|---|---|---|
| MadeOnSol runtime wiring | `MISSING` | `WIRED` | Optional worker uses `ProviderBundle.madeonsol` and the generic collector; `apps/worker/.../main.py` |
| Candidate discovery | `MISSING` | `WIRED` | `CandidateDiscoveryCollector` persists deterministic candidates from `DiscoveryCandidate` |
| Observation persistence | `MISSING` | `WIRED` | Existing `ObservationRepository` plus durable `collection_checkpoints` migration `0011` |
| Readiness API | `MISSING` | `WIRED` | Canonical `MadeOnSolReadinessReport` is nested at `/v1/readiness.alpha_validation` |
| Readiness frontend | `MISSING` | `WIRED` | `/readiness` renders live-shadow counts/status from the API only |
| Provider runtime status | `PARTIAL` | `WIRED` | Canonical API overlay covers disabled, missing credential and configured/actual health states |
| Settings parity | `EXISTING` | `VERIFIED` | Dynamic catalog renders `madeonsol_enabled`, `madeonsol_base_url` and secret state only |
| Insider backend evidence | `PARTIAL` | `WIRED` | Token read projection reuses `HolderGraphAnalyzer` and `InsiderAllocationAnalyzer` |
| Insider frontend evidence | `MISSING` | `WIRED` | Token Detail renders bounded `INSIDER PATTERN EVIDENCE` |
| Caller projection | `RAW_OBSERVATION_ONLY` | `RAW_OBSERVATION_ONLY` | Deliberate: no MadeOnSol-specific caller model or confidence inflation |
| Wallet projection | `RAW_OBSERVATION_ONLY` | `RAW_OBSERVATION_ONLY` | Deliberate: canonical wallet read models are not fed raw provider labels |
| Creator projection | `RAW_OBSERVATION_ONLY` | `RAW_OBSERVATION_ONLY` | Deliberate: existing creator graph remains authoritative |
| Provenance visibility | `PARTIAL` | `WIRED` | Token Detail/timeline and bounded insider projection expose provider/source/time/quality |
| UNKNOWN semantics | `EXISTING` | `VERIFIED` | Missing values remain `UNKNOWN`/`null`; explicit zero remains zero |
| Real sample count | `0` | `0` | No credentials or compliant MadeOnSol observations were available |
| Alpha validation | `CLI_ONLY` | `API + UI` | Shared canonical report remains `INSUFFICIENT_SAMPLES` |

### Runtime proof and reuse boundary

The proven path is:

```text
MADEONSOL_ENABLED + server credential + Robinhood enabled
→ existing ProviderBundle
→ MadeOnSolRobinhoodAdapter
→ generic CandidateDiscoveryCollector
→ CandidateRepository + candidate.discovery Observation
→ token enrichment Observations
→ existing ObservationRepository / durable cursor
→ SQL/InMemory read service
→ MadeOnSolReadinessReport
→ /v1/readiness.alpha_validation
→ Web readiness projection
```

The collector is the existing application seam for optional discovery
sources; no MadeOnSol daemon, scorer, risk engine, lifecycle, caller model,
wallet model or Telegram pipeline was added. Stable candidate identity and
the existing `(provider, kind, source_id)` observation identity make retries
and worker restarts idempotent. Checkpoints are committed in the same unit of
work as candidates and observations, so a failed transaction does not advance
the cursor. Provider event time remains `occurred_at`; delayed ingestion does
not rewrite it. Valid empty discovery is reported as `VALID_EMPTY_RESULT`, not
as an outage.

`scripts/alpha_readiness.py` now marks only explicitly listed exported real
observation IDs as `REAL_EXTERNAL` and calls the same canonical
`from_persisted_observations` report used by the read API. Fixtures and
shadow-only observations therefore remain excluded from real counts.

The MadeOnSol feed audit remains intentionally narrow:

| Feed | Classification | Result |
|---|---|---|
| KOL first-touch / hot-token discovery | `DISCOVERY_UNIQUE` | Wired through the generic collector |
| Token snapshot, holders, buyer quality, top traders, flow | `ENRICHMENT_ONLY` | Collected only after canonical token discovery |
| Bundle, provider risk, LP events, deployer evidence | `ENRICHMENT_ONLY` | Collected as canonical security/liquidity/creator observations |
| Global alpha-wallet, deployer-trajectory or coordination polling | `NOT_USEFUL` / unproven unique lead | Not added; no second poller was justified |

### Operator parity and browser result

`/readiness` visibly separates engineering/release gates, alpha evidence
readiness and `NOT_PRODUCTION_READY`. It shows zero counts as measured zero
and missing timestamps as `UNKNOWN`; provider health is explicitly not alpha
validation or execution authority. `/providers` uses runtime MadeOnSol
configuration overlays without returning secrets. `/settings` uses the
existing dynamic registry. `/tokens/[tokenId]` exposes canonical insider
allocation evidence, quality, exclusions, reason codes and provenance without
calculating suspicion in TypeScript. The parity manifest covers these fields.

The prior mobile/tablet browser failure was reproduced. The root cause was
interaction before client hydration, not an application navigation contract.
The fix uses a server/client hydration snapshot (`useSyncExternalStore`), an
explicit `data-nav-hydrated` contract, and normal Playwright actionability
checks; no sleep or timeout inflation was added. `devIndicators: false` was
audited and retained only to prevent the dev-only indicator from changing the
visual test viewport; it does not suppress application errors. The fresh
parallel visual matrix passed `4/4` projects, and the full browser suite
passed `36` with `4` credential/state skips.

### Fresh verification and external state

- `make verify`: `1251 passed, 11 skipped, 1 warning`; skips are unchanged
  optional/environment cases and are not passes.
- Focused A+C runtime/readiness/provider contract set: `33 passed, 1 warning`
  through the repository `.venv` runner, including the worker-level fake
  MadeOnSol round trip.
- Telegram Early Alpha: `31 passed`; ordinary `AlertRenderer` regression:
  `13 passed`.
- Vitest: `77 passed` across `22` files; frontend lint, typecheck and
  production build passed.
- Browser: `36 passed, 4 skipped` of `40`; visual matrix `4 passed` in the
  final hydration/interaction rerun. The four skips require authenticated or
  stateful test-only credentials.
- CSS contract: `116` classes checked. Migration check: head
  `0011_collection_checkpoints`, `27` metadata tables. Security: `PASS`
  with external scans `BLOCKED_EXTERNAL`/`NOT_RUN`. SBOM: `581` components,
  digest `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- Latest non-skipped hosted Actions run is `34709174166` at the previous
  synchronized implementation/status SHA
  `a8a3a2078c04a8e85d06c52ce08e4b463990a6be`.
  Backend quality, Frontend
  quality, Secret scan and Compose contract were `failure` with zero executed
  steps because GitHub reported the account billing/spending restriction;
  Release candidate identity was `skipped`. Main branch protection remains
  unverified: GitHub API returned HTTP 403 requiring Pro/public visibility.

Implementation checkpoint: `251c6b3`
(`feat: prove madeonsol shadow and evidence parity`); final worker-proof
checkpoint: `903d9fb` (worker round-trip test plus reconciled status counts).
The final checkpoint is intentionally marked `[skip ci]` because hosted CI is
externally blocked; the previous checkpoint is the latest hosted CI subject.

Real MadeOnSol observations: `0`; unique Robinhood tokens: `0`; caller/KOL,
smart-wallet, deployer, holder/distribution and bundle/LP/security
observations: `0`; labeled winners: `0`; labeled rugs/failures: `0`;
rate-limit/error counts: `0/0`. Calibration is `INSUFFICIENT_SAMPLES` and
provider access is `BLOCKED_EXTERNAL`. Protected modes remain exactly
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`. Production remains `NOT_PRODUCTION_READY`; the
engineering target is `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION`.

Exact next unfinished task: obtain compliant, read-only MadeOnSol credentials
and real Robinhood observations, then let the existing persisted report
surface counts and run the no-lookahead/out-of-sample calibration gate without
changing production weights or protected modes.

## 2026-09-12 A+C MadeOnSol shadow and insider-evidence sprint

Baseline source of truth was `origin/main` at
`80c449eecd41e3d8b6f2679f1a1f625efdc18cdc`; no old or diverged PR branch was
merged or cherry-picked. PR #3 remains open/dirty and is not the source of
truth.

### Before-implementation gap matrix

| Requirement | Existing | Partial | Missing | Not needed | Target files |
|---|---|---|---|---|---|
| Canonical provider contracts, provenance, freshness, shared transport | yes |  |  |  | existing provider contracts/transport |
| Robinhood RPC, sequencer, reconciliation, Dexscreener, GoPlus, Chainlink | yes |  |  | MadeOnSol duplicate paths | existing Robinhood/provider composition |
| Provider metadata/configuration seam | yes | optional composition seam |  | second registry | `provider_metadata.py`, `config.py`, `composition.py` |
| MadeOnSol Robinhood read-only evidence adapter |  |  | yes |  | `madeonsol_robinhood.py` |
| Caller, wallet, creator, holder, security/distribution evidence | yes | some provider mapping |  | new scoring models | existing application models |
| Solana insider-pattern evidence |  | existing E6.4 allocation heuristic |  | second analyzer | `holder_graph.py` |
| Live-shadow persistence/readiness | yes | provider-specific inventory |  | new storage subsystem | `historical_dataset.py`, `alpha_readiness.py` |
| New MadeOnSol scoring/risk/alpha weights |  |  |  | intentionally not needed | existing scoring/risk |

### Implemented A+C architecture

The existing flow remains:

```text
MadeOnSol/RPC/other providers
→ canonical observations and evidence
→ existing scoring/risk
→ existing Early Alpha projection
→ existing Web/Telegram projections
```

`MadeOnSolRobinhoodAdapter` is an optional, disabled-by-default,
Robinhood-only, read-only `LIVE_SHADOW` source. It uses the existing
`CandidateDiscoveryPort`, `OnChainPort`, `ProviderRequestContext`,
`ProviderTransport`, retry/timeout, rate-limit, circuit-breaker and
provenance contracts. Its canonical discovery method normalizes KOL
first-touch and hot-token events with stable token identity, exact event time,
pagination cursor and deduplication. Token enrichment normalizes the
currently available MadeOnSol API surfaces for token snapshots, KOL
consensus/first-touch, buyer quality, top traders, token flow, holders,
bundle evidence, provider risk and LP events. It has no alpha/risk/execution
classification and is not placed in the core fallback route, so MadeOnSol
failure cannot break RPC, market, quote or existing Robinhood paths.

The upstream `MadeOnSol/robinhood-chain-sdk` API was audited at commit
`241d63978f35458ecac85507098278cdb2f1440d`; GitHub reports MIT licensing.
MemeRadar independently implemented the adapter and copied no source. The
`ultranumblol/solana-meme-analyzer` repository had no identified license;
only the general problem concept was considered. The proprietary
`solana-sniper-mcp` was not used, copied, adapted, translated or derived from.

Configuration is server-side only and defaults to:

```env
MADEONSOL_ENABLED=false
MADEONSOL_API_KEY=
MADEONSOL_BASE_URL=https://madeonsol.com/api/v1
```

No migration or new schema is required: observations use the existing
repository and idempotent provenance boundary. Missing numeric fields remain
`null`/`UNKNOWN`; explicit zero remains zero; valid empty results remain
successful empty evidence; provider errors remain distinct from empty data.

The C path extends the existing holder graph/insider allocation analyzer. It
honors explicit LP, burn, system and program exclusions (and existing
service/custody/infrastructure classifications), preserves unknown native SOL
as unknown, and treats low native SOL plus a large token allocation as a weak
supporting reason only. That combination cannot produce a confirmed insider
classification and no creator/wallet graph or security engine was duplicated.

### Live-shadow/readiness result

The new readiness report counts only explicitly marked real observations from
provider `madeonsol-robinhood`; fixtures and synthetic records do not count.
The fresh `make alpha-readiness` report is:

```text
real MadeOnSol observations: 0
unique Robinhood tokens: 0
caller/KOL: 0
smart-wallet: 0
deployer: 0
holder/distribution: 0
bundle/LP/security: 0
labeled winners: 0
labeled rugs/failures: 0
rate limits/errors: 0/0
status: INSUFFICIENT_SAMPLES
```

No production score or risk weight changed. Promotion remains blocked until
out-of-sample, no-lookahead, non-survivorship-biased evidence proves lead
time, precision, false-positive rate, rug avoidance, multiple capture and
calibration value.

### Verification

- A+C focused tests: `16 passed` for MadeOnSol and insider-pattern behavior;
  the provider/metadata/composition/runtime-settings contract subset brings
  the focused total to `29 passed`.
- Full Python: `1245 passed, 11 skipped, 1 warning`.
- Telegram Early Alpha: `31 passed`; ordinary AlertRenderer regression:
  `13 passed`.
- Frontend: `74 passed` across `21` Vitest files; lint, typecheck and
  production build passed.
- Browser serial verification: `36 passed, 4 skipped` out of 40 across
  1440x900, 1024x768, 768x1024 and 390x844. The visual matrix covered all 15
  routes in dark and light themes. Four skips are authenticated/stateful
  journeys without test-only credentials. One fully-parallel rerun had one
  mobile navigation timing failure; the isolated case and the serial matrix
  passed, so this remains a test-runner flake rather than a blessed failure.
- CSS contract, migrations, secret scan, security review, SBOM and
  `git diff --check` passed. SBOM remains 581 components with digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- `make verify` reports the protected modes as analysis-only, paper trading,
  manual execution false and auto execution false.
- Latest hosted CI observed before this local checkpoint: run `34697008654`,
  HEAD `d07c9d0dab98a14de2c4ecf612d11982decb0ddb`; four jobs failed before
  steps executed for the GitHub billing/spending restriction, and one release
  job was skipped with zero steps. The post-checkpoint run is reported in the
  final handoff after push.

Implementation SHA: `c29216d` (`feat: expose MadeOnSol canonical discovery`),
on top of the prior A+C implementation `b2c6b02`.
Final branch SHA is the documentation checkpoint commit pushed with this
entry; the exact full SHA and hosted run are recorded in the final handoff.

Remaining P0/P1 issues and exact next unfinished task are unchanged in kind:
real MadeOnSol credentials/data and labeled historical cohorts are required
for alpha validation (`BLOCKED_EXTERNAL` / `INSUFFICIENT_SAMPLES`), while
hosted CI billing/spending restrictions, disabled branch protection (HTTP
403), and unavailable authenticated browser/database credentials remain
external blockers. Exact next task: collect compliant read-only Robinhood
MadeOnSol observations and matured winner/rug/caller/smart-wallet labels,
then run existing no-lookahead promotion/calibration gates without changing
protected modes or production weights.

## 2026-09-11 alpha-readiness and execution-integrity follow-up

PR #3 actual state is `OPEN`, unmerged, and dirty against current main. It is
`CORRECTED/INTEGRATED` on current main by preserving the existing architecture:

```text
canonical observations
→ existing scoring/risk engines
→ canonical Early Alpha projection
→ EarlyAlphaAlertRenderer
→ existing AlertDeliveryService
→ Telegram
```

Ordinary alerts remain on `AlertRenderer`; both alert families use the same
`AlertDeliveryService`. No second scorer, risk engine, execution engine,
Telegram alpha calculation, or prediction path was added.

The exact Early Alpha transition model is:

```text
NOT_CONFIRMED → CONFIRMED | DEGRADED | INVALIDATED | CONFLICT
CONFIRMED     → DEGRADED | INVALIDATED | CONFLICT
DEGRADED      → CONFIRMED | INVALIDATED | CONFLICT
CONFLICT      → DEGRADED | INVALIDATED | CONFIRMED (risk conflict resolved)
INVALIDATED   → terminal
```

Repeated transitions are deduped by stable logical identity; same-state
updates require a material evidence change. Confirmation with risk `UNKNOWN`,
`BLOCK`, stale/invalid/unavailable/conflicted critical evidence renders
`ALPHA CONFIRMATION CONFLICT`, never normal `CONFIRMED`. Before→now fields use
persisted snapshots and render `UNKNOWN → current` when no prior snapshot is
known. Cohorts are labeled `COHORT SIMILARITY` only.

Web↔Telegram parity is documented in the parity manifest for
`/tokens/[tokenId]`, `/ultra-early`, and `Telegram/EarlyAlpha`; token identity,
chain, early state, AlphaScore, confidence, risk disposition/quality,
smart-wallet, holder, lifecycle/graduation, volume, liquidity, sellability,
hard blocks, reason codes, freshness, event-time quality, and cohort
similarity are canonical-field mappings or explicit omissions. Neither
surface calculates AlphaScore or risk independently.

Implemented P0 seams in this follow-up:

- missing asymmetric-alpha and smart-money confidence evidence remains `null`
  / `UNKNOWN`, not neutral zero or fifty;
- PAPER_AUTO execution quotes require route, minimum output, slippage, fresh
  quote semantics, and existing price-impact/liquidity/sellability evidence;
- chain-specific native fee reserves fail closed for Solana, BNB, and
  Robinhood paper buys;
- in-memory and SQL paper ledgers enforce durable opportunity and active
  position claims, with a migration-backed uniqueness boundary and concurrent
  worker tests;
- `alpha-readiness-report` counts real samples, winners/rugs, caller and
  smart-wallet observations, providers, event-time bounds, no-lookahead, and
  survivorship signals without promoting fixtures.

The frontend/API, Telegram, provider, graph, settings, CSS, lifecycle,
caller-scope, search-error, opportunities, and existing parity fixes from the
previous sprint were deliberately reused rather than duplicated. No new
provider adapter, environment variable, credential, or production scoring/risk
weight was introduced.

Verification evidence for this follow-up:

- Python: `make verify` fresh `1230 passed, 11 skipped, 1 warning`.
- Frontend: `74 passed` across `21` Vitest files; lint, typecheck, and
  production build passed.
- Telegram: `31 passed`; ordinary renderer: `13 passed`.
- Browser: production `next start` acceptance, `36 passed, 4 skipped` out of
  40 across 1440x900, 1024x768, 768x1024, and 390x844; all 15 routes in dark
  and light themes. Four skips are authenticated/stateful journeys without
  test-only credentials.
- UNKNOWN handling, before→now snapshots, concurrent claiming, paper quote
  completeness, fee reserves, dedupe/restart/correlation, ordinary renderer
  fallback, protected modes, migration head, security, SBOM, and CSS contract
  all have fresh local evidence.

Implementation SHA: `ea2c1dc21c28be1214e6040ff235a07cf4e23130`.
The final HEAD after the docs-only reconciliation is reported in the final
handoff; this code checkpoint is already synchronized with `origin/main`.

Remaining P0/P1 issues and exact next unfinished task:

- `BLOCKED_EXTERNAL`: hosted CI billing/spending restriction, disabled main
  branch protection (GitHub API HTTP 403), absent authenticated browser/test
  database credentials, and unavailable compliant real provider data.
- `INSUFFICIENT_SAMPLES`: real external sample count is `0`; caller, smart
  wallet, winner/rug, calibration, precision/recall/FPR, and extreme-winner
  capture validation remain unproven.
- The control-plane kill switch is fail-closed and protected by default, but
  there is no live execution path and the current immutable shadow policy is
  the only paper-entry authority; direct runtime control-plane injection into
  a future automatic paper worker remains a P0 follow-up before any mode can
  change.
- Exact next task: obtain compliant, independently verified real
  Robinhood/Solana market, social, caller, and smart-wallet evidence; populate
  the required historical cohorts; wire the existing control-plane state into
  any future paper worker; then rerun no-lookahead calibration/promotion gates
  without changing protected modes or production weights.

Protected modes remain exactly:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Production classification remains `NOT_PRODUCTION_READY`, with the nearer
engineering label `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION`.

The current checkpoint hardens the reused canonical seams: KOL evidence now
requires independent strong dimensions for above-weak confidence and exposes
measurement-only precision/recall/FPR/calibration by dimension; external
wallet streams fail closed on unresolved gaps and preserve provider event-time
quality; historical social backfill is resumable, deduplicated and cohort
counted; Robinhood sequencer observations remain non-authoritative until RPC
verification/finality; the verified launchpad registry and Robinhood
Chainlink-feed registry remain empty until authoritative identities are
verified; and reference prices remain risk evidence, never executable fills.
Existing caller/wallet/graph, social outcome/replay, provider-health,
opportunity and read-model surfaces were extended without a second intelligence
engine. KOL evidence remains `execution_eligible=false` and production weights
are unchanged.

Real external samples: 0. Calibration: `INSUFFICIENT_SAMPLES`, promotion
false. CabalSpy-compatible stream, X/Telegram compliant backfill, Robinhood
sequencer runtime, launchpad identity verification and Chainlink feed runtime
are `BLOCKED_EXTERNAL`; deterministic transport, gap, no-lookahead, negative
control, dedupe, resume and failure tests pass. No unverified launchpad or
external provider score is authoritative.

The 2026-09-10 completion/hardening sprint is implemented for the feasible
local scope. The reused `GraduationAwareRouteAnalyzer` now materializes bounded
SQL-backed lifecycle reads from persisted observations, preserving freshness,
provenance, ordering, provider conflict, and no-lookahead semantics. Robinhood
sequencer observations have a bounded read-only automatic RPC reconciliation
service: chain 4663, receipt success, contract/event identity, and finality
must all verify before an observation becomes authoritative; missing external
feed access and an empty verified launchpad registry remain
`BLOCKED_EXTERNAL`. Candidate-only wallet relationship evidence now flows from
bounded persisted funding/transfer/bridge/activity/link observations through
the existing creator graph and wallet read surface. Known exchange, bridge,
router, aggregator, custodian, pool, program, system, and shared-service
addresses are excluded fail-closed across all relationship paths; ownership is
never asserted and production weights are unchanged. Strict lifecycle parsing,
operator lifecycle/relationship evidence, parity-manifest coverage, and
conflicted/unknown display states are exposed in the existing frontend.
The free-first Solana launch path was audited and already covers public RPC,
launchpad lifecycle, and DexScreener route discovery, so no duplicate fallback
engine was added.

## Hardening sprint layer status

| Capability | Domain implemented | Runtime wired | Persisted | API exposed | Frontend exposed | Real data verified |
|---|---|---|---|---|---|---|
| Launch lifecycle and graduation-aware route discovery | `YES` | `YES` | `YES` via observations and bounded SQL materialization | `YES` via token reads | `YES` via Token Detail | `NO` (`0` real samples) |
| Robinhood sequencer → canonical RPC reconciliation | `YES` | `YES` via bounded reconciler/persistence callback | `YES` when the runtime callback persists the canonical observation | `YES` through canonical lifecycle evidence; operational counters are not persisted | `PARTIAL` (lifecycle evidence; no fabricated Operations counters) | `NO` (`BLOCKED_EXTERNAL`) |
| Exact event-time/no-lookahead semantics | `YES` | `YES` | `YES` with nullable occurred/observed/ingested times | `YES` with time quality | `YES` where displayed | `NO` |
| Wallet relationship evidence | `YES` | `YES` | `YES` from normalized observations | `YES` via wallet graph/read model | `YES` via relationship edge details | `NO` (`0` real samples) |
| Solana free-first launch path | `YES` existing architecture | `YES` existing providers | `YES` existing normalized path | `YES` existing reads | `YES` existing lifecycle projections | `NO` real-alpha verification |

Relationship evidence remains measurement-only, candidate-only,
`ownership_asserted=false`, and `execution_eligible=false`. No new lifecycle,
relationship, graph, optimizer, or Solana fallback engine was added.

## Current operational references

- [Master specification](../MASTER_SPEC.md)
- [Architecture](../ARCHITECTURE.md)
- [Roadmap](../ROADMAP.md)
- [Research extensions](../ROADMAP_RESEARCH_EXTENSIONS.md)
- [Data model](../DATA_MODEL.md)
- [Scoring and risk](../SCORING_AND_RISK.md)
- [Provider contracts](../PROVIDERS.md)
- [Security](../SECURITY.md)
- [Testing](../TESTING.md)
- [Production readiness](../PRODUCTION_READINESS.md)
- [Live read-only checklist](../LIVE_READONLY_CHECKLIST.md)
- [Live-shadow validation](../LIVE_SHADOW_VALIDATION.md)
- [Release runbook](../RUNBOOKS/RELEASE.md)
- [Free-first migration report](../FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md)
- [Alpha caller extension](../ALPHA_CALLER_INTELLIGENCE_EXTENSION.md)
- [Current opportunity-discovery plan](../superpowers/plans/2026-09-05-opportunity-discovery.md)
- [Current alpha-caller design](../superpowers/specs/2026-09-07-alpha-caller-multichain-design.md)
- [Current real-alpha readiness plan](../superpowers/plans/2026-09-07-real-alpha-production-readiness.md)

## 2026-09-11 frontend and Early Alpha parity sprint (historical checkpoint)

This checkpoint is superseded by the alpha-readiness and execution-integrity
follow-up above; its implementation and verification SHAs are retained for
history only.

PR #3 was inspected rather than assumed merged. It remains open/unmerged;
the locally corrected integration follows:

```text
canonical observations → existing scoring/risk engines
→ canonical Early Alpha projection → EarlyAlphaAlertRenderer
→ existing AlertDeliveryService → Telegram
```

There is no Telegram scorer, risk engine, prediction engine, or execution
path. Ordinary alerts still use `AlertRenderer`; only Early Alpha alerts use
`EarlyAlphaAlertRenderer`, and both use the existing delivery service.

The web fixes preserve `UNKNOWN`/`BLOCKED_EXTERNAL`/`INVALID` semantics,
remove provider-name and chain-regex heuristics, use explicit graph `root_id`,
expose all canonical graph quality states, validate raw numeric settings
drafts, remove duplicate runtime-settings sources, show search failures,
label caller filter scope, clean duplicate lifecycle UI, and add the
semantic graph CSS contract (`116` static classes checked). Opportunities and
token detail remain bounded read-model projections; unavailable mappings are
listed in the parity manifest rather than recomputed in TypeScript.

Implementation SHA: `8b9d73a`; final pushed verification SHA:
`bed8726ae0362d530f9e4a4350f5dbb709cafda3`. Protected modes and
`NOT_PRODUCTION_READY` are
unchanged. Remaining P0/external blockers are authenticated browser
acceptance without test credentials, GitHub billing for hosted CI, main branch
protection, and zero real external samples. Exact next task: obtain compliant,
independently verified real provider/market/social/wallet evidence, populate
the required winner/ordinary/flat/severe-loser/rug/fake-hype/late/failed
cohorts, and rerun the existing no-lookahead calibration/promotion gates.

## Historical summary

- Phases 0–7 established the provider-independent domain, persistence,
  normalized read paths, deterministic scoring/risk contracts, alerting,
  control boundaries, and authenticated read APIs.
- Phases 8–9 established the operator UI, bounded graph/radar surfaces,
  paper execution, exit/replay contracts, Telegram boundaries, and protected
  execution semantics.
- Phases 10–11 established replay/backtesting/calibration, stream-integrity
  and provenance hardening, caller and cross-venue research, operational
  telemetry, release identity, security review, and synthetic soak evidence.
- The free-first provider migration made standard Solana RPC and DexScreener
  the keyless core while retaining optional provider-specific capabilities.
- The 2026-09-05 to 2026-09-07 frontend/backend parity work completed the
  remaining read-only opportunities projection and browser acceptance.
- The 2026-09-08 evidence-hardening checkpoint reused the canonical wallet,
  social, provider-health, generic-EVM, read-model and quote semantics seams;
  external provider runtime validation remains blocked without compliant
  credentials/data.
- The 2026-09-09 parity checkpoint made Settings an audited ADMIN workspace,
  added the server-side browser control gateway, universal multichain search,
  readiness projection, provider configuration/runtime parity, and route
  parity coverage without changing scoring, production classification, or
  protected modes.
- Real-alpha production-readiness evaluation retained
  `NOT_PRODUCTION_READY`; the next meaningful acceptance step is external
  evidence collection and replay-cohort maturation, not a code or mode change.

Exact next unfinished task: obtain independently verified Robinhood launchpad
contract/event identities and compliant real X/Telegram plus optional
wallet/KOL provider data; then populate all winner/ordinary/flat/severe-loser/
rug/fake-hype/late/failed cohorts and run the existing no-lookahead
ablation/promotion gates without changing protected modes or production
weights. Historical implementation commits: `db7cebc`, `38dd9e2`, and
`868c709`; current implementation commit: `8b9d73a`. The final status
reconciliation commit must preserve `HEAD == origin/main`. Hosted CI billing
and main-branch protection remain separate operational blockers.

Historical plans and checkpoint logs are intentionally archived from this
status file. The canonical documents and the current plans above are the
source of truth for active work.

## Social Alpha / Caller Intelligence sprint — local checkpoint

- Recovery audit at start: branch `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`; existing worktree edits were preserved and no remote Git commands were used.
- Added `docs/reports/social-alpha-gap-audit.md` covering the requested capability phases, current owners, missing seams, routes, tests, dependencies and privacy boundaries.
- The requested `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` cannot be updated: `.codex` is on a read-only host mount. Both writes returned `Read-only file system`; the blocker is recorded in the audit report. Writable project docs are used as durable progress records.
- Added canonical public `SocialSource` domain validation, persistence mapping/table migration, authenticated and audited `/v1/social/sources` CRUD, and deterministic source API/persistence tests. Social changes use the existing control/audit and auth owners. No provider credential field is exposed.
- Focused verification so far: `.venv/bin/python -m pytest -q tests/unit/test_alpha_caller_persistence.py tests/contract/test_social_source_api.py tests/unit/test_social_sources.py` — 14 passed before the current frontend-only changes. A first `pytest` invocation used system Python and could not import FastAPI; the repository virtualenv was then used. An attempted SQLite integration check could not run because `aiosqlite` is not installed; it was replaced with an injected-session contract test and no dependency was added.
- Current next step: complete and typecheck `/social-alpha`; then add canonical claim parsing / immutable edit evidence where local contracts allow. Live X/TG provider acceptance and mature OOS caller evidence remain blocked on external access and real samples.
- Checkpoint before current validation: `/social-alpha` page, filters, forms and server-side mutation actions are implemented; next command is `npm run typecheck` in `apps/web`. Result: pending.
- `npm run typecheck` result: failed once at `apps/web/src/app/lib/read-api.ts:1839` because the new SocialSource parser did not narrow optional `display_name`; fixed by rejecting `undefined` before building the record. Next command: rerun `npm run typecheck` in `apps/web`.
- Second frontend typecheck produced no TypeScript diagnostics. Re-run with explicit exit-code capture before recording final pass.
- Frontend typecheck was explicitly rerun: `npm run typecheck` in `apps/web` exited 0. New read-api, component and validation coverage is being added. Next checks: `npm run test -- --run src/app/components/social-alpha.test.tsx src/app/lib/read-api.test.ts` in `apps/web`; `.venv/bin/python -m pytest -q tests/unit/test_social_sources.py tests/unit/test_alpha_caller_persistence.py tests/contract/test_social_source_api.py` in the repository root.
- Social Alpha focused tests passed: web `npm run test -- --run src/app/components/social-alpha.test.tsx src/app/lib/read-api.test.ts` exited 0 (22 tests); Python `.venv/bin/python -m pytest -q tests/unit/test_social_sources.py tests/unit/test_alpha_caller_persistence.py tests/contract/test_social_source_api.py` exited 0 (14 tests). Next quality gates: `make lint` (root) and `npm run lint` (`apps/web`).
- Lint checkpoint: `make lint` found only new-file issues (import ordering/unused imports and line wrapping); `npm run lint` found an impure `Date.now()` in render. Imports/formatting were fixed and the social-alpha reference time now comes from the server page props. Next: rerun `make lint` and `npm run lint`.
- Durable checkpoint write was retried at `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md`; both remain blocked by the read-only `.codex/` mount. Continue using this writable status file and the sprint verification report.
- Claim parser verification: `tests/unit/test_social_claims.py` initially exposed a runtime error from combining compiled regular expressions with `|`; the parser was corrected to use one alternation with distinct capture names. Rerun result: 3 passed.
- Before the schema change: next exact gate is migration-backed persistence of call classification/claims plus append-only content-hash revisions. No database migration or revision-history read projection has been run yet.
- Schema/read-model implementation checkpoint: added `0014_social_call_claims_and_revisions`, extended the canonical call row with deterministic classification, claims, promotion and narrative evidence, and added a content-hash-deduplicated append-only revision row. Claim values/read API expose `NOT_VERIFIABLE` until canonical post-time market observations are wired. Next exact command: `.venv/bin/ruff format ... && .venv/bin/ruff check ... && .venv/bin/python -m pytest -q tests/unit/test_social_claims.py tests/unit/test_alpha_caller_persistence.py tests/contract/test_alpha_caller_read_api.py`.
- First backend slice run: Ruff passed; pytest collection failed because `SocialCallRevisionRow` was missing from `memeradar_persistence` exports. Export added. Next exact step: rerun the same focused Python slice and record outcome.
- Backend claim/revision/read-API slice rerun: Ruff passed; `.venv/bin/python -m pytest -q tests/unit/test_social_claims.py tests/unit/test_alpha_caller_persistence.py tests/contract/test_alpha_caller_read_api.py` exited 0 (18 passed, 2 dependency deprecation warnings). The revision test confirms initial and changed message evidence are retained by distinct content hashes, with no raw text in the snapshot. Next: frontend typecheck/focused test, then full touched-area type/lint checks.
- Frontend typecheck found one typed `SocialCallRecord` fixture in `apps/web/src/app/components/callers.test.tsx` that predates the new event fields. Updating the fixture is the only reported TypeScript error; next run is `npm run typecheck` and the focused social-alpha/read-api Vitest slice in `apps/web`.
- Frontend event projection check: `npm run typecheck` exited 0; focused `social-alpha.test.tsx`, `callers.test.tsx`, and `read-api.test.ts` exited 0 (25 tests). Claim verification remains explicitly `NOT_VERIFIABLE` because no post-time canonical market lookup is connected.
- Current implementation step: the canonical call event now retains its watched `social_source_id`/`source_handle`; Telegram channel polling is a separate adapter from outbound alert delivery and X/TG adapters bind calls to the watchlist. Added a bounded worker cycle (one Telegram updates poll, up to ten least-recently-polled X sources per 60s cycle) with source health and request/latency/quota observations. The `ponytail:` ceiling is documented next to the scheduler constants. No configured real source/provider was contacted.
- Next exact gate: Ruff format/check on the touched Python files, then `.venv/bin/python -m pytest -q tests/contract/test_alpha_caller_providers.py tests/unit/test_social_source_worker.py tests/unit/test_social_claims.py tests/unit/test_alpha_caller_persistence.py tests/contract/test_alpha_caller_read_api.py`; then frontend typecheck and focused Social Alpha/Radar/Token Detail/read-api tests.
- First worker/source Ruff pass flagged only the long `ponytail:` scheduler-ceiling comment. The comment is wrapped; rerun Ruff plus the documented Python slice.
- Worker/provider slice: Ruff passed, but two focused tests found defects: the multiple parser treated an EVM `0x` prefix as a zero multiple, and the scheduler fixture used handles invalid under X's handle contract. Tightened the `x`-multiple boundary and corrected the fixture; rerun the same slice.
- Second focused rerun passed the parser/provider/persistence/API checks (24 passed) but found one remaining hyphenated handle in the new scheduling fixture. Replacing it with a valid underscore handle; next rerun the same Python slice.
- Python social/caller contract slice rerun: Ruff passed; 25 passed with 2 dependency deprecation warnings. This confirms source scheduling bounds, Telegram outbound/ingest separation, public source binding, call claim extraction, claim/event persistence and revision snapshots, and read API claims marked `NOT_VERIFIABLE`. Next: token/Radar frontend wiring checks, then `make typecheck`, migration verification, and wider suites.
- Before the next implementation gate: wire source tracking options into normalized-event persistence, keep Telegram per-channel health `UNKNOWN` until a channel message is observed, align the migration checker with head `0014_social_call_claims_and_revisions`, and update frontend/backend parity for token and Radar social-call reads. Exact next validation after edits: focused worker/persistence/API tests and the migration graph checker.
- Validation checkpoint: running `.venv/bin/ruff check ...`, focused Python worker/claims/persistence/API tests, `.venv/bin/python scripts/check_migrations.py`, and focused web Social Alpha/Radar/Token Detail/parity/read-api tests. Results are pending until each command exits.
- Claim-verification implementation checkpoint: extended the existing caller-outcome module with a versioned, configurable price/market-cap/entry verifier; SQL social-call reads now join to canonical token and market observations and enforce occurred/observed/ingested-at <= post time. API/UI views expose observed values, error percentage, evidence references, and policy version. The focused no-lookahead test covers time cutoffs, UNKNOWN units, unsupported profit claims, and configurable tolerances. Next exact validation: Python format/lint, `tests/unit/test_alpha_caller_outcomes.py`, persistence/API social-call tests, and web typecheck plus Token Detail/read-api tests.
- Claim-verification focused gate: `.venv/bin/ruff check` passed; focused Python tests passed (36); web typecheck passed; focused web tests passed (38); migration graph reports one head at `0014_social_call_claims_and_revisions`. The first Ruff run flagged import ordering and one long ceiling comment; imports were auto-sorted and the comment wrapped, then the exact Ruff check passed. Next long gate is `make verify` with result to be recorded immediately.
- First `make verify` attempt: root Ruff passed; mypy failed with 20 typing errors across the new SocialSource API/worker plus normalized enum-union serialization, singular Observation provenance, and exception-variable inference. No test stage ran. Fixes are being applied at the shared domain/adapter boundaries; next exact gate is `.venv/bin/ruff format ...`, focused Ruff, then rerun `make verify`.
- After fixing those boundaries, `make typecheck` reports one remaining worker-only mypy error: the X branch redeclared the Telegram branch's `raw_calls` local. The X branch now uses `x_raw_calls`; exact next command is `make typecheck`.
- `make typecheck` rerun passed: mypy checked all 169 source files with no issues. The full `make verify` gate is next; exact command: `make verify`.
- Second `make verify` attempt stopped at root Ruff before mypy/tests due the SocialSource API `Callable` import/URL line and one duplicate worker import. The import was corrected and Ruff auto-fixed the duplicate; exact next command is `make verify`.
- Full `make verify` reached the full Python suite after root Ruff and mypy passed, then stopped with 6 failures, 1,541 passed, and 21 skipped in 198s. Failures: API schema expectations omit `/v1/social/sources` routes; migration tests and release-identity test still expect migration head `0012`; two security-review tests receive FAIL from one deterministic review finding. No test was weakened; next inspect `make security-review`, update forward-compatible expected routes/head, fix the actual security-review finding, then rerun the six tests and full gate.
- Resumed recovery at local HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e` on `main`; pre-existing dirty files preserved. `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` are absent, `.codex` contains local runtime/secret artifacts and is read-only under the workspace policy; do not inspect secret contents. `docs/STRATEGY_VALIDATION_LAB.md` is absent. First unresolved gate: six `make verify` test failures (social route allowlist; migration-head references; security review). Exact next command: `make security-review` (safe summary only), then update stale contracts and rerun focused failures.
- `make security-review` returned FAIL only at `secret_boundary_scan`; RBAC, LLM prompt, deployment, container, dependency-lock and protected-mode checks passed. External audits remain `BLOCKED_EXTERNAL`/`NOT_RUN`. Next exact command is `.venv/bin/python scripts/secret_scan.py`; its implementation prints only rule, path and line metadata, never matched content.
- Safe scanner identified one Telegram-token-shaped value in modified `.env.example` at line 171; the candidate is not present in `HEAD` and no other finding was reported. Its value was not printed. Treating it as a possible credential: next action is to replace only the matched value with a non-secret placeholder, preserving surrounding user edits, then inspect route/migration contract failures.
- Additional secret review: `.env.example` contains provider-credential-shaped values and a concrete Telegram chat identifier in the pre-existing local diff; one credential-bearing diff was inadvertently emitted by a diagnostic. No values will be repeated. Treat the provider credentials as exposed. Exact next action: replace template values with backend-managed placeholders, keep X provider disabled, then update API/migration expectations and rerun focused gates. No external revocation/rotation is possible or authorized in this local-only run.
- Security recovery edits complete: secret-bearing `.env.example` fields are sanitized (X disabled); API schema contract includes social source GET/POST and GET/PATCH; migration/release identity contracts expect head `0014_social_call_claims_and_revisions` and 29 metadata tables; security review now checks social-source role-gating and input-sanitization markers. Before focused validation: STATUS=IN_PROGRESS; exact next command is `.venv/bin/python -m pytest -q tests/contract/test_api_schema.py tests/contract/test_phase11_sprint11_3.py tests/unit/test_migration_contract.py tests/unit/test_release_identity.py tests/unit/test_security_review.py tests/contract/test_social_source_api.py`.
- Focused acceptance rerun passed: 20 tests, 2 existing dependency deprecation warnings, 68.28s. This verifies social-source CRUD/RBAC, API schema mutation allow-list, migration head/table count, release identity, and keyless security review. Before the long full gate: STATUS=IN_PROGRESS; exact next command is `make verify`.
- Full `make verify` completed with exit 0. Evidence: Ruff passed; mypy passed for 169 source files; Python 1,547 passed / 21 skipped / 7 warnings in 229.41s; CSS contract passed for 340 classes across 64 files; frontend lint and typecheck passed; Vitest 93 tests across 25 files passed; Compose config passed; secret scan passed; migration check reported one head `0014_social_call_claims_and_revisions` / 29 tables; keyless security review status PASS with `external_acceptance=BLOCKED_EXTERNAL` and pip/npm/container scans NOT_RUN; SBOM check passed (582 components). Before next long gates: STATUS=IN_PROGRESS; next commands are `npm run build` and `npm run test:e2e` in `apps/web`.
- Frontend production build passed: `npm run build` exited 0; Next generated `/social-alpha` and existing Radar/Token/Caller operator routes. Next exact command: `npm run test:e2e` in `apps/web`.
- Configured Playwright suite passed: 48 passed / 4 skipped across desktop/laptop/tablet/mobile in 3.3m. Coverage inventory confirms no Social Alpha E2E cases (only operator dashboard, visual matrix and wallet graph). Next task: add deterministic `/social-alpha` watchlist journeys for X and Telegram source entry, then run those journeys in a narrow Playwright command.
- Playwright Social Alpha test-first step: added two journeys to `apps/web/e2e/social-alpha.spec.ts` for X and Telegram source creation using only public fixture handles. Before implementation, exact RED command: `npm run test:e2e -- --project=desktop --workers=1 e2e/social-alpha.spec.ts` (local page currently has no API fixture).
- Social E2E RED attempt failed as intended to be diagnostic, but the first assertion had an ambiguous heading locator (two matching headings); no product behavior was exercised. Test now uses an exact heading name. Next exact command reruns the desktop-only Social Alpha journeys to confirm the expected missing-watchlist failure before wiring fixtures.
- Social Alpha E2E RED confirmed: both X and Telegram flows rendered the page but timed out at the Add Source control because the local API was unconfigured. Added an isolated Node fixture API (bounded, in-memory source rows; fixed test-only operator token; no provider integration) and configured Playwright to start it before Next. Tests use per-project unique fixture handles. Next exact GREEN command: `npm run test:e2e -- --project=desktop --workers=1 e2e/social-alpha.spec.ts`.
- Social Alpha desktop E2E green: 2 passed. Follow-up audit of adjacent UI found Claim Verification still renders the old “not available” state despite persisted claim fields in `SocialCallRecord`. Next test-first change: verify a `CLAIM_MISMATCH` claim renders its observed value, error percentage, state and market evidence reference; empty pages should state no claim evidence rather than service unavailability.
- Claim Verification RED step: added an empty-state contract and a mismatch fixture requiring claimed MC, observed MC, error percentage, `CLAIM_MISMATCH`, and evidence reference. Next exact command: `npm run test -- --run src/app/components/social-alpha.test.tsx` to confirm the stale panel fails before implementation.
- Claim Verification RED confirmed: the stale component rendered “CLAIM VERIFICATION NOT AVAILABLE” and did not surface the parsed mismatch fixture. Implemented the minimum fix: claim tab filters calls with parsed numeric claims, shows claimed/observed/error/state, evidence refs and policy version, and reports an explicit empty evidence state while retaining UNKNOWN semantics. Next exact command: `npm run test -- --run src/app/components/social-alpha.test.tsx`.
- Claim Verification green attempt exercised the new mismatch row and confirmed claimed/observed/error/state rendering; one assertion failed because evidence ref and policy version share a single `<small>` text node. The implementation shows both. Next update the test to assert the combined visible provenance text, then rerun the focused test.
- Caller detail read seam test-first: added an API contract requiring `GET /v1/social-calls?source_id=<UUID>` to return only calls for that watched source. Current route has no source filter; next exact RED command is `.venv/bin/python -m pytest -q tests/contract/test_alpha_caller_read_api.py::test_social_call_source_filter_is_bounded_to_the_watched_source`.
- Source filter implementation complete across the existing read owner: `source_id` is a validated UUID query filter, applied in memory and SQL, and exposed in the web read client with UUID validation; added bounded single-source reads. Next exact GREEN command: `.venv/bin/python -m pytest -q tests/contract/test_alpha_caller_read_api.py`.
- Caller detail UI test-first: watchlist contract now requires an internal CALLER DETAIL link using the canonical watched-source UUID. Current watchlist has only external source links; next exact RED command is `npm run test -- --run src/app/components/social-alpha.test.tsx`.
- Caller detail implementation: watchlist rows now link by watched-source UUID; `/callers/[sourceId]` loads the authenticated source record, bounded single-source call history and matching existing caller-profile evidence, with UNKNOWN/empty states and execution boundary. Added the caller-detail hop to the X E2E journey and a mock GET source record. Next exact checks: focused Social Alpha Vitest, then desktop Playwright Social Alpha journeys.
- Caller detail Playwright retry: fixture startup reported port 13000 occupied, but an immediate bounded listener check showed no process bound to ports 13000/13001; the transient local test server has exited. No process was stopped. Next exact step is to rerun the desktop Social Alpha E2E.
- Second E2E startup attempt again rejected port 13000 as occupied while no listener was visible. To isolate the fixture from workspace services, next change moves the local Playwright app/API ports to 13100/13101; then rerun only Social Alpha E2E.
- Recent-call UI test-first setup: deterministic fixture API can now seed a canonical X social-call event with a `CLAIM_MISMATCH` market-cap claim and return a safe UUID route from the existing server-side search resolver. Added E2E checks for claim mismatch and recent-call navigation. Production UI still lacks the token-detail resolver control. Next exact RED command: `npm run test:e2e -- --project=desktop --workers=1 --grep "recent calls resolve canonical chain identity"`.
- Recent-call token navigation RED confirmed: the deterministic fixture delivered a resolved chain/address and mismatch claim, but the Social Alpha row had no Token Detail action. Added a client action that sends the canonical `(chain,address)` to the existing authenticated search resolver and only accepts a UUID `/tokens/...` result. Next exact GREEN command: `npm run test:e2e -- --project=desktop --workers=1 --grep "recent calls resolve canonical chain identity"`.
- Recent-call token navigation GREEN: desktop Playwright passed (1 test). New route flow keeps token identity canonical: resolve chain/address server-side, navigate only to returned token UUID. Next exact command runs all Social Alpha desktop E2E cases, including X/TG add, caller detail, claim mismatch and Token Detail.
- Social Alpha E2E suite passed: 4 desktop journeys (X add + caller detail, Telegram add, claim mismatch with post-time evidence, canonical identity to Token Detail). Before touched-area validation: STATUS=IN_PROGRESS; run `npm run lint`, `npm run typecheck`, and focused Social Alpha/read-api Vitest in `apps/web`.
- Resume checkpoint 2026-09-28: recovery state reconfirmed at branch `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`; no remotes were contacted. `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` remain unavailable per the recorded read-only mount blocker. Focused Social Alpha/read-api Vitest passed 24 tests after the router test stub. Current task: reconcile stale Social Alpha parity/audit records with implemented routes; next step: add `/callers/[sourceId]` parity contract and update the bounded API/claim-availability notes. Full gates remain pending after this reconciliation.
- Social Alpha parity refresh: added the `/callers/[sourceId]` route to the frontend parity contract and documentation; corrected claim-verification availability and UNKNOWN semantics. A test-first route parity check failed on the missing manifest entry, then passed after the manifest was added (3 tests). Caller detail now summarizes post-time claim match/mismatch, partial, unverifiable, UNKNOWN and median-error counts from its bounded 100-call page; this remains separate from alpha quality and has no score/execution authority. One expected-value assertion was adjusted to include the explicit UNKNOWN count. Before touched-area validation: STATUS=IN_PROGRESS; exact next commands are `npm run test -- --run src/app/lib/read-api.test.ts src/app/components/social-alpha.test.tsx` and `npm run typecheck` in `apps/web`.
- Touched-area frontend verification passed: `npm run test -- --run src/app/lib/read-api.test.ts src/app/components/social-alpha.test.tsx` — 25 tests passed; `npm run typecheck` — exit 0. Next step: reconcile the 52-capability gap audit against current source/claim/UI owners and fill remaining deterministic local gaps; external live-source and mature-OOS acceptance remain blocked.
- Added a frontend regression asserting ticker-only `$PAID` remains `TOKEN RESOLUTION UNKNOWN` and offers no Token Detail action; Social Alpha component suite passed 4 tests. X source browser journey now explicitly asserts provider health is UNKNOWN when no provider is available. Before browser validation: STATUS=IN_PROGRESS; exact next command is `npm run test:e2e -- --project=desktop --workers=1 e2e/social-alpha.spec.ts` in `apps/web`.
- Recent-call evidence integration: Social Alpha joins the existing convergence projection only on exact `(chain, asset_address)`, labels smart-wallet confirmation as token-level corroboration, renders parsed promotion evidence, and shows source last-success/error timestamps. `social-alpha.test.tsx` passed 5 tests after the UI change. Caller-detail source health now includes the same timestamps. Before touched-area checks: STATUS=IN_PROGRESS; exact next commands are `npm run lint`, `npm run typecheck`, and `git diff --check`.
- Touched-area checks passed: `npm run lint` exited 0, `npm run typecheck` exited 0, and `git diff --check` exited 0. Before full Playwright suite: STATUS=IN_PROGRESS; exact next command is `npm run test:e2e` in `apps/web` (local deterministic fixture API only).
- Full Playwright diagnosis (68 tests, 4 viewports) exposed 17 failures: the new Social Alpha mock API had been injected into the general operator suite, so Settings/Readiness saw invalid responses while that suite expected an unconfigured API; Social Alpha's `PROVIDER UNKNOWN` locator was also ambiguous across two source rows. The suite recorded 47 passed / 4 skipped. Root cause is the shared test-server API base, confirmed from baseline config and Playwright DOM/error traces. Isolated Social Alpha into `playwright.social-alpha.config.ts`, restored the general runner's environment-derived API boundary, source-filtered fixture call reads, and scoped the provider assertion to its source row. Before focused browser regression: STATUS=IN_PROGRESS; exact next command is `npm run test:e2e:social -- --project=desktop --workers=1` in `apps/web`.
- E2E harness separation is implemented: the general Playwright config once again inherits its actual API/token environment and excludes Social Alpha; `test:e2e` now runs the general suite plus an isolated local Social Alpha fixture suite. Social Alpha calls are filtered by `source_id`, and multi-viewport assertions scope to each unique source row. The first focused rerun could not start the fixture: Node returned `EPERM` binding 127.0.0.1 ports 13100, 13101, and 13201, with `ss` and `ps` showing no stale listeners/processes. Before another network-dependent check: STATUS=IN_PROGRESS; exact next commands are `npx playwright test --list`, `npx playwright test --config=playwright.social-alpha.config.ts --list`, and focused web Vitest.
- Harness checks after isolation passed: Playwright test discovery lists 52 general tests and 16 Social Alpha journeys; focused frontend Vitest passed 30 tests across 3 files. Local browser execution remains blocked by loopback bind `EPERM` with no listener, so test discovery is not counted as an E2E pass. Before full frontend quality gates: STATUS=IN_PROGRESS; exact next commands are `npm run test`, `npm run lint`, `npm run typecheck`, and `npm run build` in `apps/web`.
- Full frontend gates passed: `npm run test` — 97 passed / 25 files; `npm run lint` — exit 0; `npm run typecheck` — exit 0; `npm run build` — exit 0, with Social Alpha and Caller Source routes generated. `make verify` includes backend lint/typecheck/test plus frontend contracts and secret/migration/security/SBOM gates. Before the long verification run: STATUS=IN_PROGRESS; exact next command is `make verify`.
- `make verify` long-test result persisted immediately: Ruff passed; mypy passed on 169 source files; Python pytest passed 1,548 / skipped 21 / 7 existing deprecation warnings in 278.88s; CSS contract passed (340 classes, 65 files). The target is continuing through frontend lint/typecheck/test and compose/security/migration/SBOM gates; next active command is `cd apps/web && npm run lint` inside `make verify`.

## Fullstack root-cause hardening — recovery checkpoint (2026-09-29)

CURRENT_PHASE=11-12/39 — PAPER cost and risk evidence
CURRENT_TASK=Persist an explicit partial ExecutionCostBreakdown and populate every PAPER risk snapshot with known inputs plus explicit UNKNOWN fields.
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Named stream cursor persistence and read projection extended for event ID/time, provider/connection, freshness, reconnect/resume, lag, event-time quality and safe error code. Backend focused slice PASS (58); migration graph PASS with one head `0015_named_stream_runtime_state`. Frontend focused Services/Operations/read-api/parity tests PASS (34); typecheck/lint PASS. Token detail in-page navigation and wallet sample-confidence hierarchy implemented; focused component tests PASS (9), typecheck/lint/diff-check PASS. Audit filters and safe reason/evidence rendering implemented; Providers links to Services and no longer duplicates named-stream list; focused component tests PASS (6). PAPER cost breakdown and risk snapshot carry typed completeness/UNKNOWN fields; focused PAPER/shadow tests PASS (22).
NEXT_STEP=Run `.venv/bin/python -m pytest -q tests/unit/test_early_runtime.py` to verify that a RISK_REJECTED snapshot is persisted with reasons, evidence references, and execution blocked.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; not a clean candidate)
TEST_STATUS=Baseline current-tree `make verify` PASS before this sprint changes. Named stream focused backend tests PASS (58); migration graph PASS. Frontend focused tests PASS (34); typecheck/lint PASS. Token/wallet tests PASS (9), post-change typecheck/lint/diff-check PASS. Audit/Providers tests PASS (6). PAPER/shadow/persistence tests PASS (22). Safe settings probe: ANALYSIS/PAPER true; manual/auto false; X API key/bearer and Telegram outbound token/chat absent; Robinhood RPC configured. Bounded RPC check returned DOWN/CONNECT_TIMEOUT at about 2.25 seconds; the Python process required the outer `timeout` to exit, so external health acceptance is blocked by runner/network behavior. Rejection persistence test is in progress. Playwright remains HOST_RESTRICTION (`127.0.0.1:13101`, EPERM). Full `make verify` is not rerun after current changes. npm/pip/container scans remain `NOT_RUN`.
BLOCKERS=Requested `/tmp/memeradar-closure-20260926` worktree and HEAD `af67be94c1ef143a35124f0c98bd263eab456cd` are unavailable; no such local commit/ref exists. `.codex` checkpoint files are unavailable on the read-only mount. Local browser execution is HOST_RESTRICTION (`listen EPERM` on `127.0.0.1:13101`). Preserve all existing edits.
UPDATED_AT=2026-09-29T21:45Z

Baseline progress 2026-09-29: full `make verify` completed from the beginning with exit 0. Security review PASS; protected modes remain `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false`; SBOM PASS (582 components). npm, pip, and container scans are `NOT_RUN`; external acceptance is `BLOCKED_EXTERNAL`. Test-first focused EVM/caller tests passed (10). A registry from 26 provider descriptors plus 6 internal service descriptors and operator/admin-only audited service doctor are implemented; runtime remains UNKNOWN until measured. Ruff and focused service/EVM/caller tests pass (15). Frontend API/parity and `/services` UI are next.


## Fullstack root-cause hardening — recovery update (2026-09-29)

CURRENT_PHASE=Accessibility and mobile acceptance
CURRENT_TASK=Re-run axe after fixing shared low-contrast text tokens, page-level heading hierarchy, and link distinction; then verify mobile widths.
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Added `axe-core` 4.13.0 and route scanner. First axe run reported low text contrast, missing h1s, and a section-note link distinguished only by color. Updated shared text tokens, page heading semantics, and link underline. A subsequent run caught the token h1's mismatched JSX closing tag; the tag is corrected.
NEXT_STEP=Rerun `cd apps/web && npx playwright test e2e/accessibility.spec.ts --project=desktop` to verify the corrected JSX and remaining WCAG findings.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; .git read-only)
TEST_STATUS=Prior complete baseline `make verify` PASS is recorded in this checkout: Python 1,548 passed / 21 skipped; frontend 97 tests / 25 files; full verification after current edits remains pending. `npm run lint`, `npm run typecheck`, and `npm run analyze:routes` pass. All route gzip budgets pass; largest chunk is 229,156 bytes and module attribution remains unavailable. `/opportunities` focused component test PASS (1). Token detail summary tests PASS (7); missing evidence remains UNKNOWN. Current default Playwright suite passes: 48 passed, 4 skipped across four viewport projects; it excludes fixture-only Services/Social Alpha specs. The deterministic fixture API is blocked by host bind restriction (`listen EPERM`, `127.0.0.1:13101`). Tablet visual matrix passed in isolation; one concurrent hydration timeout did not reproduce.
BLOCKERS=Fixture-backed Playwright API server bind is HOST_RESTRICTION (`listen EPERM`, `127.0.0.1:13101`); Services/Social Alpha browser acceptance requires a browser-enabled runner with loopback support. Requested candidate worktree/ref unavailable; `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` unavailable on read-only mount; `docs/STRATEGY_VALIDATION_LAB.md` and requested prior Services/Social final reports are absent. `.git` is read-only. External X/Telegram credentials and matured outcome samples are unavailable; bounded Robinhood RPC probe previously timed out. Preserve the pre-existing dirty tree.
UPDATED_AT=2026-09-30 (local recovery update)

## Fullstack hardening checkpoint (2026-09-30)

CURRENT_PHASE=Full operator browser acceptance
CURRENT_TASK=Re-run the complete non-fixture Playwright operator suite against the current Providers and wallet UI.
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Full `make verify`, production build and route budgets PASS. Fixture suite retry is HOST_RESTRICTION on 127.0.0.1:13101. Current-code axe and keyboard check PASS across desktop, 390x844 and 430x932: 5 passed / 1 intentionally skipped; axe scanned all 18 routes in both themes.
NEXT_STEP=Run `cd apps/web && npx playwright test --workers=1` for the full current non-fixture browser suite.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; source `.git` is read-only)
TEST_STATUS=Current full `make verify` PASS: Python 1,560/21; frontend 107/27; mypy171; CSS362/67; migration0015/29; secret scan, Compose, security review and SBOM564 all PASS. Providers + wallet focused tests PASS. Browser route/navigation rerun PASS (2). Production build and route budget scan PASS, 23 app/API routes; 17 chunks / 730,205 B; largest chunk 229,156 B. Services/Social fixture rerun BLOCKED before test execution by `listen EPERM` on 127.0.0.1:13101. Axe/keyboard 5 PASS / 1 skip across desktop and both mobile viewports; all 18 routes/two themes scanned. Full current browser suite pending. npm audit returned zero vulnerabilities; pip/container scanner tools remain unavailable.
BLOCKERS=The requested `/tmp/memeradar-closure-20260926` worktree and `af67be94c1ef143a35124f0c98bd263eab456cd` are unavailable. `.codex` is mounted read-only, so `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` cannot be created or updated; this file is the writable checkpoint. Fixture/production browser servers are blocked by host `listen EPERM` on loopback. Real X/TG credentials and mature outcome samples are unavailable; Robinhood RPC previously timed out. Preserve all existing user artifacts.
UPDATED_AT=2026-09-30

CURRENT_PHASE=Read-only EVM protocol certification
CURRENT_TASK=Validate the verifier's declared-version, sample-block bytecode, receipt, and canonical event checks
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=The checker now refuses certificates missing an explicit protocol version or evidence source, hashes deployed runtime code at the sample transaction's block, and reports the configured protocol version. Registry projection carries that version; temporary verified parser state is not written back.
NEXT_STEP=Run `.venv/bin/ruff format` and `.venv/bin/ruff check` on the touched EVM verifier files, then `.venv/bin/python -m pytest -q tests/unit/test_protocol_verification.py tests/unit/test_protocol_registry.py tests/unit/test_evm_protocols.py tests/unit/test_evm_rpc.py`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused verification for the final verifier edits is pending. Earlier protocol verifier fixtures passed before the sample-block and version/source requirements were tightened.
BLOCKERS=No deployment-level EVM sample is available in the repository configuration, so runtime provider acceptance remains unverified; existing Pons evidence remains unavailable.
UPDATED_AT=2026-09-30

Full current-code Playwright rerun completed: `cd apps/web && npx playwright test --workers=1` exited 0 — 65 passed / 10 skipped across desktop, laptop, tablet, mobile (390×844), and mobile-wide (430×932), 9.3 minutes. No failures. The fixture-backed Services/Social journeys remain separately blocked before execution by loopback `listen EPERM`; the default suite does not include them. Next audit: close or explicitly record the wallet detail projection gap for canonical funding/transfer/bridge evidence, then update the gap/maturity/performance/final closure reports and final diff check.

Wallet timeline root-cause audit: `ObservationRow` already persists `wallet.funding`, `wallet.transfer`, `onchain.transfer`, `wallet.bridge`, `wallet.relationship`, and `wallet.link`, while `get_wallet()` projected only `wallet.activity` and inner-joined a token. Therefore canonical tokenless events could never reach wallet detail. Repository-controlled fix in progress: bounded address-linked observation read model with optional token identity, preserved event time/quality/provenance, and UNKNOWN confidence when absent. Exact next gate: implement and focus-test application/API/persistence/frontend projection.

Wallet activity projection implementation is in place across the application read model, SQL adapter, API response, frontend parser/detail table and parity manifest. It scans at most 500 matching persisted rows and returns at most 50, retaining a token link only when a canonical token row exists; side-chain mismatches are discarded. Before focused gates: STATUS=IN_PROGRESS; exact next commands are Ruff format/check plus `.venv/bin/python -m pytest -q tests/unit/test_bounded_read_extensions.py tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py`, then web wallet/read-api/parity Vitest, lint and typecheck.

First wallet projection gate: Python 22 passed / 1 failed because an explicitly BNB-addressed transfer incorrectly fell back to a Solana row default; the selector now uses an explicit side-chain value as authoritative. Web focused tests were 28 passed / 1 failed because the test expected the raw provider ID instead of the rendered provenance (`provider:source_id`); expectation corrected. Web lint and typecheck both exited 0. Before rerunning: STATUS=IN_PROGRESS; exact next gate is Ruff import/format cleanup and the same focused Python/frontend tests.

Wallet timeline focused rerun passed: Ruff PASS; Python read/persistence/API slice 23 passed (four existing deprecation warnings); web WalletDetail/read-api/parity 29 passed; web lint/typecheck PASS. Tokenless bridge and funding records serialize without fabricated token IDs, and wrong-chain matches are rejected. Full `make verify` must be rerun after this change.

PAPER cost audit found the explicit `route_fee` component was absent even though it is required by the contract. Added nullable `route_fee` to `ExecutionCostBreakdown`; it remains UNKNOWN without protocol quote evidence. Before the focused cost test: STATUS=IN_PROGRESS; exact next command is `.venv/bin/python -m pytest -q tests/unit/test_paper_execution.py` plus Ruff format/check on the touched model and test.

PAPER cost focused gate passed: Ruff PASS and `tests/unit/test_paper_execution.py` 13 passed. DEX, launchpad, route, network and priority fees remain nullable rather than inferred.

Before local browser-runtime measurement: STATUS=IN_PROGRESS; exact next command is `cd apps/web && npm run measure:browser`. The checked-in CI workflow already performs `npm ci`, build, browser E2E, measurement, route budget analysis and uploads test artifacts; this local run probes whether runtime metrics are available in this host.

Local measurement attempt failed before navigation. `DEBUG=pw:webserver npx playwright test --config=playwright.perf.config.ts` confirms the first probe to `127.0.0.1:13010` returns `connect EPERM`; `npm run start` exits 1 and Playwright aborts. This is a host restriction, not a browser metric. Checking the already-working E2E server port for a safe reuse path before classifying runtime metrics blocked.

The non-fixture E2E suite already uses `127.0.0.1:13100` successfully, so the measurement harness now uses the same port; only the harness binding changed. Before retry: STATUS=IN_PROGRESS; exact next command is `cd apps/web && npm run measure:browser`.

The measurement retry remains HOST_RESTRICTED even on port 13100: Playwright's readiness probe returns `connect EPERM`, and `npm run start` exits 1. No LCP/CLS/interaction/heap/frame result was produced; the 13100 port alignment remains useful for CI consistency, not a local pass.

## Recovery checkpoint — fullstack hardening (2026-09-30)

CURRENT_PHASE=Full verification after wallet activity and PAPER cost changes
CURRENT_TASK=Run `make verify` from the beginning against the current dirty worktree
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Wallet activity read projection focused checks passed (Python 23; web 29; lint/typecheck); PAPER route-fee focused test passed (13). Browser runtime measurement retry on port 13100 is HOST_RESTRICTION (`connect/listen EPERM`); no runtime metric was generated.
NEXT_STEP=Run `make verify`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Previous full `make verify` on this checkout passed before the latest wallet activity and route-fee edits: Python 1,560 passed / 21 skipped; frontend 107 tests / 27 files; mypy 171 files; CSS 362 classes / 67 files; migration head 0015 / 29 tables; Compose, secret scan, security review, and SBOM passed. Latest wallet focused slice passed and the PAPER cost test passed. Full verification after those edits is pending. Production browser E2E 65 passed / 10 skipped; axe/keyboard 5 passed / 1 intentional skip. Fixture journeys and runtime measurements are blocked before test execution by host loopback `EPERM`.
BLOCKERS=Requested `/tmp/memeradar-closure-20260926` worktree and requested HEAD are absent. `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` are unavailable in this mounted checkout; `docs/STATUS.md` is the writable checkpoint. `.git` is read-only. Runtime browser/fixture server binding is restricted by host `EPERM`. Real X/TG credentials, matured outcome samples, and independent Pons deployment/transaction evidence are unavailable. Preserve all pre-existing edits.
UPDATED_AT=2026-09-30

`make verify` recovery gate update (2026-09-30): root Ruff PASS; mypy PASS (171 source files); Python pytest PASS (1,560 passed / 21 skipped / 7 warnings in 210.90s); CSS contract PASS (362 classes / 67 files). The same full invocation is continuing at frontend lint; full gate is not yet complete.

`make verify` completed on the current dirty worktree with exit 0 (2026-09-30). Root Ruff PASS; mypy PASS (171 source files); Python pytest PASS (1,560 passed / 21 skipped / 7 warnings); CSS contract PASS (362 classes / 67 files); frontend lint, typecheck and Vitest PASS (107 tests / 27 files); Compose config PASS; secret scan PASS; migration graph PASS (single head `0015_named_stream_runtime_state`, 29 tables); security review PASS (all local checks and protected modes); SBOM PASS (564 components, digest `sha256:a05ea994cb63e711bee6e2d327b1b6e5bd1781df622e9155154cf54d8f339415`). npm/pip/container audits were reported `NOT_RUN`; external acceptance remains `BLOCKED_EXTERNAL`. Next exact gate: `cd apps/web && npm run build && npm run analyze:routes`.

Current production build and route analysis (2026-09-30): `npm run build` PASS; 23 dynamic app/API routes generated, including `/services`, `/social-alpha`, and `/callers/[sourceId]`. `npm run analyze:routes` exit 0; all five route gzip budgets PASS. Bundle total 730,205 B across 17 chunks; largest shared chunk `3byuobrkyz9bj.js` is 229,156 B and module attribution is unavailable from current artifacts. Next: review unresolved local gaps and refresh the dated closure reports.

CURRENT_PHASE=Service health truth hardening
CURRENT_TASK=Replace database/cache TCP-only doctor verdicts with bounded protocol readiness checks
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Current-tree `make verify`, production build, and route bundle budgets all pass. Root-cause review confirms PostgreSQL/Redis doctors only establish TCP reachability, which cannot verify authentication or an actual command.
NEXT_STEP=Implement bounded PostgreSQL `SELECT 1` and Redis `PING` checks against configured service URLs, with safe canonical failure mapping and injected tests for healthy/down outcomes.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full `make verify` PASS after latest edits; build PASS; route budgets PASS. DB/cache doctor protocol tests are not yet implemented.
BLOCKERS=Requested `/tmp` candidate, `.codex` checkpoint files, `.git` write access, host browser socket, live providers and matured outcome data remain unavailable as recorded above.
UPDATED_AT=2026-09-30

Service doctor root-cause fix (2026-09-30): PostgreSQL uses configured `DATABASE_URL` for bounded `SELECT 1`; Redis uses configured `REDIS_URL` for bounded RESP PING and optional AUTH. Reasons map authentication, permission, DNS, timeout, refused, and protocol failures without returning driver/server text. The doctor remains registered-ID-only, audited, and does not write readiness. Focused Ruff PASS; `tests/contract/test_services_api.py` PASS (8 tests). Next exact gate: rerun the current full non-fixture browser suite after the Wallet Detail activity timeline change.

CURRENT_PHASE=Current-code browser acceptance
CURRENT_TASK=Run the full non-fixture Playwright suite after Wallet Detail activity timeline and service health changes
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Service doctor focused backend contract tests passed (8); current `make verify` before doctor changes passed; production build and route budgets passed.
NEXT_STEP=cd apps/web && npx playwright test --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Latest complete `make verify` and production build pass prior to the focused service health change. Full current-browser rerun pending. Fixture/API browser checks and runtime metrics remain host-restricted.
BLOCKERS=See prior checkpoint. No browser server processes were identified in the recorded process-pid check.
UPDATED_AT=2026-09-30

Current-code non-fixture Playwright rerun completed (2026-09-30): `cd apps/web && npx playwright test --workers=1` exit 0 — 65 passed / 10 skipped in 9.4 minutes across desktop, laptop, tablet, mobile 390×844, and mobile-wide 430×932. Includes current Wallet Detail activity rendering; axe, keyboard, and the route/theme layout matrix pass. Screenshots exercise the unconfigured/empty read API; this does not count as populated Services/Social acceptance or golden-baseline approval. Next: attempt the current fixture-backed Services/Social suites and record host result.

CURRENT_PHASE=Fixture browser acceptance
CURRENT_TASK=Run current Services/Social Alpha deterministic fixture browser journeys
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Current non-fixture Playwright suite passed 65/75 (10 intentional skips) across all five viewport projects, including accessibility and visual matrix.
NEXT_STEP=cd apps/web && npm run test:e2e:social -- --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full UI route E2E pass is current; fixture-only acceptance pending on the latest worktree.
BLOCKERS=Prior attempts were blocked by host loopback `EPERM`; retry current code once and record exact result.
UPDATED_AT=2026-09-30

Current fixture-backed browser attempt (2026-09-30): `npm run test:e2e:social -- --workers=1` exits 1 before any test. The fixture API process fails `listen EPERM: operation not permitted 127.0.0.1:13101`; classify `HOST_RESTRICTION`, not a product assertion failure. The default full E2E suite passed separately on this code.

CURRENT_PHASE=Dependency security evidence
CURRENT_TASK=Run production-only npm audit and inventory locally available Python/container scanners
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Fixture browser suite was attempted on current code and failed before test execution with host `listen EPERM` on 127.0.0.1:13101.
NEXT_STEP=cd apps/web && npm audit --omit=dev
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Current default Playwright 65 passed / 10 skipped; fixture suite HOST_RESTRICTION.
BLOCKERS=Dependency registry/network may prevent npm audit. Scanner availability will be checked separately.
UPDATED_AT=2026-09-30

Services inventory audit correction (2026-09-30): current checkout contains 36 descriptors; removed Helius→public RPC and Jupiter quote→DexScreener as whole-service fallbacks because their registered capabilities do not match. The only remaining registered service fallback is Birdeye→DexScreener (market data). Fixture Telegram is now explicitly not required, not enabled, and DISABLED in the runtime projection while retaining `VERIFIED_FIXTURE`. Focused service API tests PASS (8).

CURRENT_PHASE=Read-only EVM protocol certification
CURRENT_TASK=Add a reusable EVM verifier that certifies only a configured deployment with chain, code hash, receipt event decode, and block timestamp evidence
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Current route E2E passed 65/75, fixture E2E is HOST_RESTRICTION, production npm audit --omit=dev PASS with 0 vulnerabilities; pip-audit, Trivy, Grype unavailable and Docker Scout plugin absent. Service registry fallbacks were corrected and focused API tests pass.
NEXT_STEP=Finish protocol-version/source requirements and verify the sample deployment bytecode at the sample transaction block; map a matched event topic through the registered decoder identity.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Current full `make verify` PASS before the latest service doctor/fallback changes; those changes pass focused tests. The EVM verifier has focused fixture coverage but the integration contract is still under review; final full verification remains pending.
BLOCKERS=EVM candidate deployments have no configured address/hash/topic/sample transaction. Runtime acceptance will remain TODO_VERIFY or BLOCKED_EXTERNAL until independently evidenced data and working RPC access exist. No Solana verifier evidence is yet available.
UPDATED_AT=2026-09-30

Protocol verifier focused gate (2026-09-30): Ruff format/check PASS; EVM protocol verification, identity registry, parser, and RPC slice PASS (`46 passed`). The verifier now uses `eth_getCode` at the sample receipt block, requires explicit protocol version/source metadata, and leaves configured candidates unpromoted. Next exact gate: `make typecheck`.

CURRENT_PHASE=Read-only EVM protocol certification
CURRENT_TASK=Check whole-repository typing after completing the verifier slice
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Protocol focused tests passed (46); Ruff passed on all touched protocol files. Existing candidate deployments still lack real address/hash/topic/sample evidence and remain TODO_VERIFY.
NEXT_STEP=make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused protocol slice PASS (46). Full typecheck and final make verify remain pending.
BLOCKERS=No live EVM/RPC certificate or independent Pons deployment evidence is available; no candidate is promoted from fixtures.
UPDATED_AT=2026-09-30

Typecheck root cause (2026-09-30): first `make typecheck` after the protocol changes found seven mypy errors because the checker stored optional deployment values and deadline in a boolean preflight, which did not narrow their types for use. The fix keeps validated values in locals, checks missing metadata before use, rejects malformed hash syntax, and handles an absent/expired deadline explicitly. Next exact gate: `make typecheck`.

CURRENT_PHASE=Read-only EVM protocol certification
CURRENT_TASK=Re-run whole-repository mypy after fixing explicit input narrowing
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Focused protocol tests and Ruff passed (46); the first full typecheck identified seven optional-value narrowing issues in the verifier; those source issues are fixed.
NEXT_STEP=make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full typecheck rerun pending. The earlier failure was mypy only; no test stage ran.
BLOCKERS=Real deployment samples remain unavailable; fixtures cannot promote protocol candidates.
UPDATED_AT=2026-09-30

CURRENT_PHASE=Final full verification
CURRENT_TASK=Verify service doctor, provider fallback, PAPER evidence, wallet activity, and read-only EVM protocol verifier together
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=The EVM checker requires explicit protocol version/source, verifies chain and successful sample receipt, checks runtime bytecode at the sample block using a documented SHA-256 evidence fingerprint, and decodes only a registered event identity. Malformed odd-length bytecode now returns PROTOCOL_DRIFT instead of raising. Focused verifier/registry/parser/RPC suite PASS (47); touched files pass Ruff. Whole-repository typecheck PASS (172 source files).
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; .git read-only)
TEST_STATUS=Latest full make verify passed before service doctor and protocol verifier edits. Focused doctor tests PASS (8); EVM protocol slice PASS (47); typecheck PASS (172). Full integration verification after those edits is pending.
BLOCKERS=Requested /tmp worktree and HEAD unavailable; .codex checkpoint files cannot be written in this mounted checkout; source .git is read-only. Browser loopback bind is HOST_RESTRICTION. Live social credentials, independent Pons deployment/sample evidence, and mature OOS samples are unavailable. Preserve the existing dirty tree.
UPDATED_AT=2026-09-30

`make verify` live recovery checkpoint (2026-09-30): Ruff PASS; mypy PASS (172 source files); Python suite PASS (1,568 passed / 21 skipped / 7 existing deprecation warnings in 277.86s); CSS contract PASS (362 classes / 67 files). Same invocation is continuing at frontend lint; this is not yet a complete verification result. Next active gate: `cd apps/web && npm run lint` inside `make verify`.

`make verify` frontend stage (2026-09-30): frontend lint PASS; typecheck PASS; Vitest PASS (107 tests / 27 files). Compose configuration PASS. The same full verification invocation is now running the secret scan; migration, security review and SBOM remain pending.

`make verify` completed on the current dirty worktree with exit 0 (2026-09-30). Ruff PASS; mypy PASS (172 source files); Python pytest PASS (1,568 passed / 21 skipped / 7 existing deprecation warnings); CSS contract PASS (362 classes / 67 files); frontend lint/typecheck/Vitest PASS (107 tests / 27 files); Compose config PASS; secret scan PASS; migration graph PASS (single head `0015_named_stream_runtime_state`, 29 tables); security review PASS (all local checks and protected modes); SBOM PASS (564 components, digest `sha256:a05ea994cb63e711bee6e2d327b1b6e5bd1781df622e9155154cf54d8f339415`). Security review records `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false`; npm, pip, and container audits remain `NOT_RUN`; external live acceptance is `BLOCKED_EXTERNAL`.

CURRENT_PHASE=Final evidence and blocker reports
CURRENT_TASK=Refresh service, social, frontend maturity, visual, performance, gap matrix, and dated closure reports from current code and verification
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Full `make verify` PASS on the current dirty worktree with exact counts above. Focused verifier tests PASS (47); whole-repository typecheck and service doctor tests pass.
NEXT_STEP=Audit the current 36 service descriptors and report their real verification/capability/dependency/fallback states; then update final reports and run `git diff --check`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; .git read-only)
TEST_STATUS=Full make verify PASS: Python 1,568/21; frontend 107/27; mypy172; CSS362/67; migration0015/29; Compose, secret scan, security review, SBOM564 PASS. Build and route budget evidence from current frontend remains PASS (23 routes, 17 chunks, 730,205 B); current browser 65 PASS / 10 skips; fixture browser HOST_RESTRICTION; runtime metrics unmeasured.
BLOCKERS=No `/tmp/memeradar-closure-20260926` checkout/ref or writable `.git`; `.codex` checkpoint files unavailable in this mount. Local browser fixture/performance server is blocked by host loopback `EPERM`; X/TG credentials and external acceptance absent; independent Pons and other live protocol samples absent; mature OOS samples insufficient. No live execution authority.
UPDATED_AT=2026-09-30

CURRENT_PHASE=MCP service metadata closure
CURRENT_TASK=Expose canonical MCP tool count and honest unmanaged-supervisor state on Services without implying process health
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Final `make verify` PASS (Python 1,568/21; frontend 107/27; mypy172; CSS362/67; security/compose/migration/SBOM PASS). Inventory audit confirms 36 registered services, not 69; MCP currently exposes transport/read-only authority but not its safe tool count or supervisor-state field.
NEXT_STEP=Add MCP count metadata tied by a contract test to the MCP tool registry; expose NOT_MANAGED and last_seen=null, keep runtime UNKNOWN, and render those fields in service detail.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full make verify PASS immediately before this narrow MCP metadata change. Relevant test: `tests/contract/test_services_api.py`, frontend parser/component tests.
BLOCKERS=No MCP supervisor exists. This change reports static tool inventory only; runtime/liveness remains UNKNOWN and last_seen unavailable. Existing host/browser/provider/OOS blockers remain.
UPDATED_AT=2026-09-30

MCP and required-core service projection changes: MCP Services API now exposes a static 17-tool count tied to `TOOL_SPECS`, `supervisor_state=NOT_MANAGED`, and null `last_seen_at`; runtime remains UNKNOWN. Safe current settings showed PostgreSQL/Redis absent, but the old projection returned NOT_REQUIRED/DISABLED despite their canonical CORE_REQUIRED registry flags. It now reports MISSING/required/enabled/BLOCKED with NOT_CONFIGURED. Service contract tests PASS (9), Services/read-api tests PASS (29), frontend lint/typecheck PASS, mypy PASS (172), Ruff PASS, and diff check PASS. Before production artifact validation: STATUS=IN_PROGRESS; exact next command is `cd apps/web && npm run build && npm run analyze:routes`.

CURRENT_PHASE=Current-candidate frontend build and route budgets
CURRENT_TASK=Build the Services MCP-detail metadata changes and recalculate current route chunk budgets
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Full make verify passed before MCP/service-config projection changes; after those changes backend doctor/service tests PASS (9), web Services/read-api tests PASS (29), mypy172, frontend lint/typecheck, Ruff, and git diff --check pass.
NEXT_STEP=cd apps/web && npm run build && npm run analyze:routes
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; source .git read-only)
TEST_STATUS=Full integration verification after the MCP and required PostgreSQL/Redis status changes remains pending. Browser fixture server remains HOST_RESTRICTION.
BLOCKERS=See the current checkout and external blockers above; preserve all pre-existing dirty files.
UPDATED_AT=2026-09-30

CURRENT_PHASE=Final full verification after MCP/core-required status fixes
CURRENT_TASK=Run the complete verification gate after the Services MCP metadata and core configuration correction
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Current-candidate build compiled but Next failed while capturing `tsc --showConfig`; a direct Node `spawnSync` of the exact TypeScript CLI returns `error=EPERM`, `stdoutBytes=0`. The same `tsc --showConfig` executed directly exits 0 and `npm run typecheck` passes. This confirms HOST_RESTRICTION at Node child-process creation; type checking was not disabled or bypassed. MCP/service-contract tests PASS (9), Services/read-api frontend tests PASS (29), mypy172, Ruff/lint/typecheck PASS.
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; `.git` read-only)
TEST_STATUS=Last full make verify passed before the narrow MCP and required-core projection edits: Python 1,568/21, frontend 107/27, security/compose/migration/SBOM PASS. Build/route analysis on the final candidate remains HOST_RESTRICTION; prior successful build evidence predates the new MCP detail fields.
BLOCKERS=Node child spawn and loopback bind are host-restricted. Requested `/tmp` candidate absent; source `.git` read-only; live provider credentials and mature OOS samples unavailable. Preserve all current user files.
UPDATED_AT=2026-09-30

`make verify` live checkpoint (2026-09-30): Ruff PASS; mypy PASS (172 source files); Python pytest PASS (1,569 passed / 21 skipped / 7 existing deprecation warnings in 238.59s); CSS contract PASS (362 classes / 67 files). Same invocation is continuing through frontend lint, then frontend typecheck/tests, Compose, secret scan, migrations, security review, and SBOM. Full result is not complete yet.

`make verify` frontend stage (2026-09-30): frontend lint and typecheck PASS; Vitest PASS (108 tests / 27 files). Compose configuration PASS; secret scan PASS; migration graph PASS (single head `0015_named_stream_runtime_state`, 29 tables). Security review and SBOM are running; invocation remains in progress.

`make verify` completed on the current dirty worktree with exit 0 (2026-09-30). Ruff PASS; mypy PASS (172 source files); Python pytest PASS (1,569 passed / 21 skipped / 7 existing deprecation warnings); CSS contract PASS (362 classes / 67 files); frontend lint/typecheck/Vitest PASS (108 tests / 27 files); Compose config PASS; secret scan PASS; migration graph PASS (single head `0015_named_stream_runtime_state`, 29 tables); security review PASS; SBOM PASS (564 components, digest `sha256:a05ea994cb63e711bee6e2d327b1b6e5bd1781df622e9155154cf54d8f339415`). Protected modes remain `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false`; npm/pip/container scans remain `NOT_RUN` in security review. Final-candidate Next build and route budget run remain host-restricted by Node child `spawnSync` EPERM; direct typecheck passed.

CURRENT_PHASE=Final report reconciliation and repository state
CURRENT_TASK=Update dated fullstack closure evidence, run diff check, and determine whether a safe local commit is possible without touching the read-only source metadata
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Full make verify PASS after MCP tool-count/supervisor metadata and missing-core dependency state fixes: Python 1,569/21; frontend 108/27; mypy172; CSS362/67; migration0015/29; Compose, secret scan, security review, and SBOM564 PASS. Current Next build failure has direct child-process EPERM evidence; no checks were disabled.
NEXT_STEP=Refresh final reports, then run `git diff --check`, inspect exact status, and verify source `.git` write access before any local commit attempt.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty source checkout; .git read-only)
TEST_STATUS=Full verify PASS on current source. Build/route analyzer current candidate HOST_RESTRICTION; last successful build/budgets predate final MCP detail fields. Browser fixture and runtime metrics are host-restricted; main suite last passed 65/10; service focused tests pass.
BLOCKERS=Requested `/tmp` candidate HEAD absent; source `.git` read-only; Node child spawn and loopback sockets restricted; X/TG credentials, independent Pons/protocol samples, and mature OOS cohorts absent. Preserve all existing artifacts; no remote Git operations.
UPDATED_AT=2026-09-30


## Shutdown recovery checkpoint — 2026-10-06

CURRENT_PHASE=Recover interrupted read-projection work
CURRENT_TASK=Validate named stream and strategy failure-mode Operations projections, then resume remaining P0 gaps
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Recovered accessible candidate at HEAD 35274d2fd7ae07ef6446b66cef70ac6b93f5e84e on main; the requested /tmp worktree is absent. Added safe-class redaction for stream error fields after test-first leak tests. Focused Ruff, Python route/read/persistence tests (26), read-api/Operations Vitest (29), mypy (172 files), ESLint and TypeScript all pass.
NEXT_STEP=Audit and implement the canonical durable service/asset conflict path only from real two-sided source observations; then audit Smart Wallet, Caller→Wallet, and rejection→Outcome paths.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused recovery gates PASS; full make verify has not been rerun after recovery changes. Global git diff --check reports one existing blank line at EOF in .env.example.
BLOCKERS=Requested /tmp/memeradar-closure-20260926 unavailable. .codex and .git are read-only in this mounted checkout; CURRENT_TASK/VERIFICATION cannot be written and local commit is unavailable. Host Node stream warning observed on Vitest with exit 0. Live provider credentials, PostgreSQL runtime, browser loopback, independent protocol evidence, and mature outcomes remain to be reprobed.
UPDATED_AT=2026-10-06 23:02 local

CURRENT_PHASE=Service conflict canonical persistence and read projection
CURRENT_TASK=Complete a PRICE-only conflict producer over fresh token-linked provider snapshots, versioned persistence, bounded APIs, and source-backed UI surfaces
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Interrupted Operations read path validated; unsafe stream error values now fail closed in app DTO and TypeScript parser. TDD RED/GREEN passed. Added canonical ServiceConflictEvidence domain object, PRICE pair detector, SQLAlchemy model/migration 0016, and SQLite-gated persistence contract test.
NEXT_STEP=Finish API/web contract wiring, worker ingestion over persisted snapshots, then run focused validation and update observed verification evidence.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; source .git read-only)
TEST_STATUS=Read projection recovery focus passed earlier: Python 26 passed; web 29 passed; mypy172; ESLint and TypeScript pass. New PRICE detector tests pass 2; persistence/replay test is skipped because aiosqlite is not installed. No PostgreSQL acceptance run.
BLOCKERS=/tmp/memeradar-closure-20260926 absent; .git metadata read-only. PostgreSQL binary/Docker availability remains to be reprobed. Other open repository gaps: operational Smart Wallet candidate pipeline, Caller→Wallet pipeline, and resolved rejection→Outcome consumer.
UPDATED_AT=2026-10-06 23:40 local

Service-conflict recovery checkpoint (2026-10-06): service conflict API route tests now pass (2 passed, 2 existing Starlette/AnyIO deprecation warnings), including Viewer authorization and backend-projected evidence. The interrupted changes are intact. Current incomplete link: persisted provider market observations are not yet normalized into the conflict detector by the worker; active conflict resolve/stale transitions are also not yet driven. Exact next step: add a tested conversion from allow-listed canonical market observations, then connect a bounded worker scan to the existing conflict repository.

CURRENT_PHASE=Service conflict observation-to-worker path
CURRENT_TASK=Consume persisted fresh GMGN/DexScreener market observations, detect PRICE conflicts, and persist deterministic lifecycle updates without granting readiness authority
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Focused service API route tests PASS (2); detector tests PASS (2); service-conflict persistence contract is present but skipped because aiosqlite is unavailable. No PostgreSQL run yet.
NEXT_STEP=Add failing tests for provider observation normalization and recovery/stale classification, implement those in the canonical application service/worker, then run focused and full checks.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; git metadata read-only)
TEST_STATUS=Service API routes 2 passed; detector 2 passed; persistence test SKIPPED (aiosqlite not installed); whole-repository verification not rerun after conflict changes.
BLOCKERS=/tmp/memeradar-closure-20260926 unavailable; source .git read-only. PostgreSQL/Docker availability not yet reprobed for this resume. Other repository gaps remain as recorded in the prior current-state audit.
UPDATED_AT=2026-10-06 23:55 local

Service-conflict source path update (2026-10-06): added normalization through the existing `resolve_price_evidence` owner, restricted to persisted token-linked GMGN/DexScreener market observations with fresh provenance. The worker queries at most 250 observations per provider from the five-minute window, persists through `ServiceConflictRepository`, and explicitly resolves fresh agreement or marks expired evidence stale. Read-only conflict evidence is now projected to Services, Token Detail, and Operations through a strict bounded TypeScript parser. New detector/normalizer/reconcile tests pass (4); API projection tests pass (2); web read API and conflict-panel tests pass (33). Exact next command: run Ruff on changed Python and Python unit/contract tests for API, migration, and conflict paths, then mypy and frontend lint/typecheck.

CURRENT_PHASE=Service conflict integration validation
CURRENT_TASK=Validate worker wiring, migration contract, Python API projections, and frontend conflict panels/parsers
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Persisted observation normalizer + shared market kind correction + bounded worker scan + conflict read API/UI wiring are present. Focused API tests PASS (2); conflict detector/normalizer/reconcile tests PASS (4); frontend read-api/conflict-panel tests PASS (33).
NEXT_STEP=.venv/bin/ruff check packages/application/src/memeradar_application/service_conflicts.py packages/application/src/memeradar_application/price_semantics.py apps/worker/src/memeradar_worker/main.py tests/unit/test_service_conflicts.py tests/unit/test_read_api_routes.py && .venv/bin/pytest -q tests/unit/test_service_conflicts.py tests/unit/test_service_conflict_persistence.py tests/unit/test_read_api_routes.py tests/unit/test_migration_contract.py
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; git metadata read-only)
TEST_STATUS=Python conflict/API focused results listed above; SQL persistence test remains unverified because aiosqlite availability has not changed. Worker not yet runtime-tested against a database.
BLOCKERS=/tmp candidate remains unavailable; `.git` metadata read-only. Current PG/Docker runtime has not yet been probed in this resume. Broader Smart Wallet, Caller→Wallet, and rejection→Outcome paths remain to audit/close.
UPDATED_AT=2026-10-07 00:05 local

Service-conflict focused integration gate (2026-10-07): Ruff PASS for the producer, market-price semantics, worker, API tests, and migration checker. Migration graph checker PASS with exact head `0016_service_conflict_evidence` and metadata table count 30. Focused Python suite PASS: 20 passed / 1 skipped / 4 warnings; the skipped test is SQLite persistence because `aiosqlite` is unavailable. The initial run exposed only stale migration-head assertions; they now target the new migration. Exact next commands: `make typecheck`, then in `apps/web`, `npm run lint`, `npm run typecheck`, and focused Vitest for Services/Operations/Token Detail/read-api.

CURRENT_PHASE=Service conflict type and UI acceptance
CURRENT_TASK=Prove backend typing and compile the new bounded conflict read model across Services, Operations, and Token Detail
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Focused Python conflict/API/migration tests PASS (20/1 skipped/4 warnings); migration checker PASS with head `0016_service_conflict_evidence`, 30 tables; web parser + panel tests PASS (33).
NEXT_STEP=make typecheck; then `cd apps/web && npm run lint && npm run typecheck && npm test -- --run src/app/lib/read-api.test.ts src/app/components/service-conflicts.test.tsx src/app/components/services.test.tsx src/app/components/operations.test.tsx src/app/components/token-detail.test.tsx`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; git metadata read-only)
TEST_STATUS=Worker has not run against a database. No PostgreSQL migration/restart acceptance. Current Python domain/API/migration static gate PASS; `aiosqlite` persistence test skipped.
BLOCKERS=/tmp candidate unavailable; `.git` read-only. PostgreSQL/Docker reprobe, production browser host, and broader repository P0 audits pending. Keep all existing user/runtime artifacts.
UPDATED_AT=2026-10-07 00:20 local

Type/UI contract fixes (2026-10-07): frontend lint PASS, frontend typecheck PASS, and 48 focused Vitest cases pass after updating the Services assertion for the new backend conflict panel. The first backend typecheck found a loop-variable type collision in conflict reconciliation plus `ServiceConflictView` accepted domain `Provenance` while API conversion required bounded `ProvenanceView`; both source issues are fixed. Exact next gate: rerun `make typecheck` and focused API/producer tests.

Post-fix conflict type/API verification (2026-10-07): `make typecheck` PASS (174 source files); Ruff PASS; conflict/route/migration Python suite PASS (20 tests / 4 existing warnings). Current DB runtime reprobe found all DB URLs missing, PostgreSQL binaries missing, and Docker socket access denied on both `docker info` and `docker ps`; the SQLite persistence test still skips because `aiosqlite` is not installed. Classify exact-tree database acceptance as `NEEDS_DATABASE_RUNTIME`. Exact next gate: current-source production build and route analysis, then rerun browser acceptance for the touched routes.

CURRENT_PHASE=Current-code build and browser acceptance for conflict projections
CURRENT_TASK=Build changed Next pages and rerun available Services/Operations/Token Detail browser journeys
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Current backend typing/producer/API/migration focused checks PASS; web lint/typecheck and 48 relevant component/parser tests PASS. Exact-current DB substrate is unavailable.
NEXT_STEP=cd apps/web && npm run build && npm run analyze:routes
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; git metadata read-only)
TEST_STATUS=Current source contract validated statically. Build and browser checks after conflict UI changes not run. PostgreSQL acceptance NOT_RUN/NEEDS_DATABASE_RUNTIME.
BLOCKERS=PostgreSQL URLs/binaries unavailable; Docker socket permission denied; aiosqlite absent. Browser runner must be reprobed for current-code use. Preserve existing dirty files/runtime artifacts.
UPDATED_AT=2026-10-07 00:40 local

## 2026-10-07 current-code recovery checkpoint

STATUS=IN_PROGRESS
CURRENT_PHASE=Classify current production build failure and continue conflict projection acceptance
CURRENT_TASK=Verify the direct TypeScript configuration/compiler path and run route analysis separately; then retry current-code browser acceptance where the host permits
LAST_COMPLETED_STEP=Backend conflict focused tests, migration graph, Python typing, web lint/typecheck, and 48 focused Vitest tests passed. Current `npm run build` compiled Next.js but exited 1 in Next's TypeScript-config subprocess with `Could not parse output from TypeScript's --showConfig`; application TypeScript had passed directly.
NEXT_STEP=In apps/web, inspect scripts/Next version and run direct `npx tsc --showConfig`, direct `npm run typecheck`, and `npm run analyze:routes` independently to classify the wrapper failure
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree; Git metadata is read-only)
TEST_STATUS=Focused service conflict Python suite 20 passed/1 skipped/4 warnings; frontend focused suite 48 passed; make typecheck passed for 174 source files; frontend lint/typecheck passed. Full build failed after compilation during Next's TypeScript config subprocess. Browser acceptance after current conflict UI remains unverified.
BLOCKERS=/tmp/memeradar-closure-20260926 is absent. PostgreSQL URLs and host binaries are missing; Docker daemon socket is permission denied. The untracked `.codex` directory has no CURRENT_TASK.md or VERIFICATION.md, and the requested checkpoint directory is host-read-only. Existing user/runtime artifacts remain preserved.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Known early-wallet balance evidence
CURRENT_TASK=Rerun repository typecheck after correcting exception-union narrowing and local variable inference in the refresh scheduler
LAST_COMPLETED_STEP=First make typecheck identified four local mypy issues: gather's BaseException union, a reused variable name inferred as ObservationRow, and resulting timestamp tuple types. These were corrected without changing behavior.
NEXT_STEP=make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused source/worker/state tests PASS 99; touched Ruff PASS; diff check PASS. Initial repository typecheck FAIL was fixed; rerun pending.
BLOCKERS=No live RPC or PostgreSQL runtime acceptance. Per-wallet balances cannot prove bundle membership or complete token supply; percentage remains UNKNOWN unless the RPC context slots and decimals agree.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Verified Pump.fun trades enter shared early participant features
CURRENT_TASK=Inspect canonical Solana transaction evidence for realized trade amounts; only normalize amounts when transaction balance/event evidence can be tied to the exact mint, wallet, side, and quote asset
LAST_COMPLETED_STEP=Reviewed the official pinned Pump.fun IDL at revision 81091419e4457566469d4e2a27f64ed84d42419c and corrected the local contract table's argument names. The shared EarlyFeatureEngine now accepts canonical chain.event rows only for verified protocol identity, trade event type, and explicit buy/sell side; unverified chain-shaped rows remain excluded.
NEXT_STEP=Audit RawChainTransaction/getTransaction meta and Pump.fun TradeEvent decoding; determine whether executed token/quote amounts can be calculated without confusing slippage bounds or account fees with realized flow
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; 232 dirty paths observed; inherited work preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused Pump raw/registry contract suites: 34 passed. Combined early feature/runtime/detection/signal hardening/protocol registry/raw stream/forward report suites: 133 passed. Touched Ruff, make typecheck (177 source files), and git diff --check passed. Exact-current PostgreSQL, live RPC and production browser acceptance remain unrun.
BLOCKERS=No live provider acceptance; PostgreSQL test URL unset and localhost TCP is host-blocked. Pump.fun IDL arguments are request inputs/bounds and are not realized transaction quantities. No whole-supply bundle exposure is established.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Verified canonical Pump.fun trades in early feature trajectory
CURRENT_TASK=Run the focused raw decoder, registry, early feature and runtime checks after admitting only registry-verified chain trade observations
LAST_COMPLETED_STEP=Official Pump.fun pinned-IDL contract doc added. Raw decoder/account-index and registry provenance suite passed 34 tests. A token-identity-aligned test reproduced that verified `chain.event` buy/sell rows were silently excluded by EarlyFeatureEngine; the shared selector now admits only `protocol_identity_verified=true`, `protocol_event_type=trade`, and explicit buy/sell rows. Unverified chain-shaped rows remain excluded.
NEXT_STEP=Run the focused canonical chain/early feature/runtime/read projection suites, touched Ruff, `make typecheck`, and `git diff --check`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Pump raw decoder + protocol registry: 34 passed, Ruff PASS, diff check PASS. Canonical chain feature regression: initial RED confirmed with aligned token identity, then targeted GREEN 1 passed. Broader affected suites and static checks pending.
BLOCKERS=No executed quantities are inferred from IDL swap input bounds. Current owner/mint balance refresh remains unimplemented; whole-supply bundle exposure stays UNKNOWN. PostgreSQL/browser/live provider/OOS blockers unchanged.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Official Pump.fun instruction-contract review
CURRENT_TASK=Pin the official Pump.fun instruction identity and prove registry normalization retains its verification provenance
LAST_COMPLETED_STEP=Reviewed the official pinned Pump.fun public IDL at revision 81091419e4457566469d4e2a27f64ed84d42419c. It confirms create/create_v2, legacy buy/sell, v2 buy/sell, exact-quote buy, and migrate discriminators plus legacy/v2 mint and user account positions. Added docs/providers/pump-fun-contract.md; checksum is reported as the existing local pin and was not independently recomputed from a download.
NEXT_STEP=Add a regression proving verified canonical chain.event buy/sell observations enter EarlyFeatureEngine while unverified lookalikes remain excluded
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Pump instruction identities were checked against official pinned IDL and existing fixture mappings; no new test run yet. No live transaction or program-account cross-check is claimed.
BLOCKERS=Official IDL defines instruction inputs, not executed trade amounts. No RPC balance refresh/worker exists; provider RPC reads alone cannot prove complete bundle exposure. Keep all other inherited dirty files intact.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Same-age failure-control matching
CURRENT_TASK=Fix the type errors and lint violations found by the first full report validation
LAST_COMPLETED_STEP=The 8-test pumpfun_forward_report unit suite passes. The first touched Ruff/typecheck run identified two line-length issues, mypy inference of optional snapshots from min(default=None), and len(object) on a dynamically typed matched controls field.
NEXT_STEP=Use an explicit empty-list guard for winner snapshots, cast nested control rows at the length boundary, wrap long lines, then rerun report tests, Ruff, make typecheck and git diff --check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Report unit tests PASS 8/8. Ruff FAIL 2 E501; make typecheck FAIL 3 mypy errors; git diff --check PASS. These failures are confined to the new report change and are being repaired.
BLOCKERS=No real matched-control/OOS data. No PostgreSQL/browser acceptance claim.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Same-age failure-control matching
CURRENT_TASK=Run the complete forward-report regression suite, touched Ruff and repository typecheck for strict age/control matching
LAST_COMPLETED_STEP=Added a report-level regression that was RED against the prior coarse age-cohort matcher. The existing report now pairs only mature, outcome-evidenced RUG/HONEYPOT/DEAD/SEVERE_DRAWDOWN/NEUTRAL controls using a prior-or-same-age snapshot, same chain/venue/launch date and positive liquidity/market cap within 2x; it reports candidate matches separately from sample sufficiency and keeps research acceptance NOT_ESTABLISHED. New regression passed 1/1.
NEXT_STEP=Run all tests/unit/test_pumpfun_forward_report.py, touched Ruff, make typecheck and git diff --check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Matched-control test observed RED on missing age-aware output, then GREEN 1/1. Broader report suite and static checks pending.
BLOCKERS=Current research fixture remains synthetic and has no matured negative controls. Algorithm presence is not real matched-twin or OOS evidence. Preserve all pre-existing dirty files.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Same-age failure-control matching
CURRENT_TASK=Audit and tighten the existing forward report's matched-control algorithm so only mature explicit negative outcomes with comparable historical launch-age evidence are paired
LAST_COMPLETED_STEP=Confirmed the report already has a coarse matched-control function, but it matches a broad age_cohort at DISCOVERED and reports IMPLEMENTED when any same-bucket pair exists. The checked-in research validation fixture has 7 SYNTHETIC_REDACTED records, 0 matured outcomes and 0 negative controls.
NEXT_STEP=Add a report-level regression for same-age, same-venue winners versus mature negative controls and future-only/unknown exclusions; observe it fail before implementation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Audit only for this slice. No matched-control tests run yet. No real matched sample or OOS claim.
BLOCKERS=Real matured failed/rug controls and chronological OOS data are absent. Keep report acceptance INSUFFICIENT_SAMPLES even when the matching algorithm finds candidate fixture pairs. Preserve protected .env.example and all unrelated dirty files.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Bundle exposure and pre-graduation evidence audit
CURRENT_TASK=Assess whether existing launch-footprint observations can expose a bounded current holding estimate for explicitly bundle-labeled launch wallets without presenting it as total supply exposure
LAST_COMPLETED_STEP=Token similarity read projection implemented and focused validated: backend API/persistence 25 passed, frontend parser/detail 46 passed, Ruff and mypy 176 sources passed, web lint/typecheck passed. PostgreSQL assertion exists but remains blocked before connect by host localhost TCP EPERM. Current-state audit now records this slice and its partial status.
NEXT_STEP=Write a focused regression first for launch-bundle wallet balances and missing-balance coverage, run it to confirm the expected failure, then implement only a clearly scoped observed-cohort estimate if the model can preserve UNKNOWN and completeness
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; .git/.codex read-only; no commit)
TEST_STATUS=Token similarity backend 25/25 and web 46/46 pass; Ruff, make typecheck (176 sources), npm lint/typecheck pass. Current-bundle/pre-graduation work not yet tested. Exact-current PostgreSQL and browser acceptance remain blocked/unverified.
BLOCKERS=Bundle fields may be sourced from advisory labels; any derived number must be named observed bundle-cohort holdings, carry wallet/balance coverage and provenance, and never be called total current bundle exposure. Pre-graduation values must remain unavailable/UNKNOWN without verified canonical event evidence. Preserve .env.example and all pre-existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Rerun the exact-mint false-confidence regression and final affected projection checks, then continue with advisory token identity similarity audit
LAST_COMPLETED_STEP=Focused recovery suite passed 77 tests/2 warnings; Token Detail passed 8/8; touched Ruff passed; make typecheck passed for 176 files; web lint/typecheck passed. A new test-first regression caught and removed the false `social_identity_confidence=1` assignment for exact-mint posts while account ownership was UNVERIFIED. Current audit and ledger updated; a read-projection fixture was corrected to NULL confidence.
NEXT_STEP=Run `.venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_early_read_projection.py tests/unit/test_market_archetypes.py tests/unit/test_early_runtime.py --show-capture=no --tb=short`, then touched Ruff and `git diff --check`; inspect canonical token metadata before deciding if a minimal advisory clone projection is safe
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=77-test recovery suite passed after production confidence fix; 8 Token Detail tests passed. API fixture update and direct classifier regression are pending final rerun. No PostgreSQL or browser E2E for this slice.
BLOCKERS=No authoritative social-account ownership verification source is configured. Exact token references remain claims only. Keep `.env.example` and unrelated pre-existing changes untouched.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Social-to-on-chain evidence binding
CURRENT_TASK=Validate the exact-mint persisted social evidence path from SQL query through runtime, API projection and Token Detail
LAST_COMPLETED_STEP=Implemented `SocialCallObservationRepository.for_asset_window()` with exact chain/address, published/observed/ingested cutoffs, deterministic ordering and explicit truncation; EarlyFeatureEngine calculates event-time exact-mint call/account velocity and acceleration, excludes deleted/future/late/wrong-mint calls, and labels account ownership UNVERIFIED. Worker event, lifecycle-reevaluation and DexScreener runtime paths now load the bounded persisted slice. Runtime projection and Token Detail expose only bounded counts and state.
NEXT_STEP=Run focused unit/worker/read-projection and Token Detail tests, then Ruff and typecheck; repair any integration mismatch and record exact evidence
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; extensive pre-existing dirty worktree preserved; no commit)
TEST_STATUS=Core feature unit and runtime social tests 5 passed; repository query and persistence tests 2 passed. Worker helper test and UI projection test have not yet passed; component test was RED as expected before UI implementation.
BLOCKERS=.codex checkpoints are unavailable/read-only; docs/STATUS.md remains writable checkpoint. Preserve unrelated changes and .env.example. Exact persisted evidence is scoped to stored social calls; no account ownership, source-wide coverage, live social validity or calibration is claimed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Run static checks for the recovered social evidence path and UI
LAST_COMPLETED_STEP=Focused Python recovery suite passed: 77 passed, 2 existing dependency deprecation warnings in 13.88s. The earlier six failures were incomplete worker test doubles; after adding the missing fake repository, the complete focused set passes.
NEXT_STEP=Run touched Ruff, `make typecheck`, `npm run lint`, `npm run typecheck`, then `git diff --check`; record each exit status and continue the current gap matrix
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Focused Python: PASS, 77 passed / 2 existing warnings. Token Detail Vitest: PASS, 8 passed. Static checks pending. No PostgreSQL runtime integration for the bounded query has been run.
BLOCKERS=Exact mint references are not account ownership verification. Preserve `.env.example` and all pre-existing dirty changes. Live source acceptance, historical calibration and elapsed-data gates remain open.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Prevent exact-mint post references from being treated as verified social account identity
LAST_COMPLETED_STEP=The new focused assertion reproduced that the feature path assigned social_identity_confidence=1 to an exact-mint post even though account ownership is UNVERIFIED; removed that false binding signal. Fixed worker chain validation so absent/invalid event chain data is normalized safely and mypy narrows it before TokenIdentity construction.
NEXT_STEP=Rerun exact-mint social tests plus the 77-test focused worker/runtime/repository suite; rerun touched Ruff and `make typecheck`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Prior 77-test suite passed before these small safety/type fixes. `make typecheck` exposed two nullable chain errors and failed; web lint and typecheck passed. Focused regression assertion was RED as expected before implementation. Post-fix verification pending.
BLOCKERS=Account ownership and official social-to-mint verification remain unavailable; exact mint references stay advisory only. Preserve `.env.example` and all pre-existing dirty changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Social-to-on-chain evidence binding
CURRENT_TASK=Wire persisted exact chain+mint calls into early feature windows, bounded worker reads, runtime persistence and Token Detail projection
LAST_COMPLETED_STEP=Added early-feature and repository-query tests first. The feature tests fail because EarlyFeatureEngine has no social-call input; the repository test fails because SocialCallObservationRepository has no bounded exact-asset query.
NEXT_STEP=Implement the bounded persisted-call query, event-time exact-mint aggregation, runtime/worker wiring, read projection display, then run focused Python and frontend checks
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; extensive pre-existing dirty worktree preserved; no commit)
TEST_STATUS=New feature tests are intentionally RED; no production changes for this slice yet
BLOCKERS=.codex checkpoints are unavailable/read-only; docs/STATUS.md is the writable durable checkpoint. Preserve all unrelated edits and do not modify .env.example. Social account ownership remains unverified from post-to-mint references.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Social-to-on-chain evidence binding
CURRENT_TASK=Wire persisted exact chain+mint social calls into existing early feature windows and runtime projections without claiming project-account ownership
LAST_COMPLETED_STEP=Audited identity owners: exact social calls are durably token-address qualified and source/caller attributed; `PROJECT` is operator configuration only. Existing narrative matcher safely rejects ticker-only matching but is not in the early runtime path.
NEXT_STEP=Add tests first for exact-mint association, independent account counts, social acceleration, ticker-only exclusion, deleted/future/late-arriving evidence exclusion, and explicit unverified ownership; then wire worker persistence query and runtime projection
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=No implementation or tests run yet for social-to-on-chain binding. Latest completed liquidity slice: Python 40 passed, Token Detail 8 passed, Ruff/mypy/web lint/typecheck/diff-check passed.
BLOCKERS=No provider-level verified official account-to-mint evidence source is present. Exact mint references can bind a post to a token but cannot prove account ownership; preserve this distinction.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Liquidity and valuation quality
CURRENT_TASK=Complete validation of the paired USD liquidity/market-cap quality projection and then recompute the next repository-owned gap
LAST_COMPLETED_STEP=Audited the current social/token identity owners. `TokenIdentity` is chain+address canonical; `SocialCallObservation` persists exact token mentions and account attribution; `SocialSource.source_type=PROJECT` is operator-managed configuration, not ownership verification. `NarrativeTokenMatcher` safely avoids ticker-only identity but has no production social-account binding path. Exact mint posts can be treated only as claims until authoritative ownership evidence exists.
NEXT_STEP=Run touched Ruff, `make typecheck`, Token Detail Vitest, web lint/typecheck and `git diff --check`; then update the current-state matrix and slice ledger
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit)
TEST_STATUS=Test-first failures reproduced missing liquidity quality fields (4 targeted failures). Focused EarlyFeatureEngine/runtime/read-projection suite now passes 40 tests with 2 existing deprecation warnings. Ruff/typechecks and Token Detail Vitest pending.
BLOCKERS=Preserve protected `.env.example` and unrelated dirty changes. Social-account ownership/official-site evidence is not derivable from current stored records; direct mint mentions are claims, not verification. Liquidity quality is locally implementable from paired USD market snapshots.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha V4 participant evidence correctness
CURRENT_TASK=Reverify the versioned fail-closed cluster-coverage change and record exact source evidence
LAST_COMPLETED_STEP=Added wallet-cluster evidence coverage to canonical early and flow metrics; entropy remains UNKNOWN unless cluster evidence covers every observed buyer. Organic momentum ignores missing/zero coverage and weights partial coverage. Feature, organic momentum, and flow versions advanced to v3. Red regressions failed before the fix; focused feature/flow/runtime tests pass (41 passed, 2 warnings), touched Ruff and `git diff --check` pass, and `make typecheck` passes on 175 source files. Evidence: `docs/reports/agentic-loop/2026-10-07-wallet-cluster-evidence-coverage.md`.
LAST_COMPLETED_STEP=The social-as-trade regression failed first and now passes after restricting flow aggregation to canonical trade kinds. A second red test showed generic execution `price` creating market return; EarlyFeatureEngine now delegates mark selection to the existing `market_reference_price` owner. Corrected the fixture to use market snapshots for reference returns. Full affected caller selection: 113 passed, 2 warnings; Ruff, `make typecheck` (175 files), and `git diff --check` pass. Evidence: `docs/reports/agentic-loop/2026-10-07-early-feature-event-semantics.md`.
NEXT_STEP=Proceed to the missing market-behavior classifier by inspecting the existing early-runtime feature snapshot serialization and winner-archetype owners; preserve uncalibrated status and multi-label semantics
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved)
TEST_STATUS=Focused affected feature/runtime/replay/flow/organic/GMGN/price-semantics pytest PASS: 113 passed, 2 existing deprecation warnings. `make typecheck` PASS (175 source files); touched Ruff PASS; `git diff --check` PASS. No DB schema change; exact-current PostgreSQL round-trip for the new v3 metrics not run. Prior cohort coverage slice: worker tests 20 passed and Ruff/typecheck passed.
BLOCKERS=Current tree has 213 status entries including pre-existing edits. `.env.example`, `.git`, and `.codex` remain protected. PostgreSQL exact-delta restart, live providers, browser runtime and mature OOS remain separately blocked/unverified.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha V4 cohort coverage
CURRENT_TASK=Prevent DexScreener discovery batches from losing candidates beyond the 100-item enrichment limit; add explicit backlog and fairness evidence
LAST_COMPLETED_STEP=Reconciled the current tree: 211 pre-existing dirty paths, branch main, HEAD 35274d2fd7ae07ef6446b66cef70ac6b93f5e84e. Traced `_run_dexscreener_early_discovery`: discovery observations are persisted only in the capped enrichment loop, and persisted discovery loading is capped at 500 without coverage telemetry.
NEXT_STEP=Inspect EarlyFeatureSnapshot and FlowAnalyzer inputs/outputs plus existing tests, then write a failing event-time test before changing feature owners.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Current cohort slice: worker tests 20 passed/2 warnings; touched Ruff PASS; mypy 175 source files PASS; `git diff --check` PASS. Exact-current PostgreSQL cursor restart/replay and full `make verify` remain pending.
BLOCKERS=Protected `.env.example` remains untouched. `.codex` and `.git` are read-only. DexScreener live DNS, browser listener, npm registry, and mature real OOS data remain unavailable.
UPDATED_AT=2026-10-07 local

## DexScreener / Early Gem recovery checkpoint — 2026-10-07

CURRENT_PHASE=Validation and evidence reconciliation
CURRENT_TASK=Close the DexScreener early-discovery slice without promoting unverified market evidence or using launch-observation time as token age
STATUS=IN_PROGRESS_WITH_ENVIRONMENT_BLOCKERS
LAST_COMPLETED_STEP=Public-feed worker integration and exact pair-created-time launch-age guard are present; focused DEX/detection/runtime/worker tests passed (20); current reassessment, MUNK evidence boundary, and DexScreener integration report written
NEXT_STEP=Continue repository-actionable Early Gem gaps only where canonical input and no-lookahead tests can be added; re-run exact-tree database/browser/security gates when their runtime/tooling is available
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; pre-existing dirty worktree preserved)
TEST_STATUS=make verify: Ruff and mypy(175) pass; pytest 1592 passed, 24 skipped, 4 failed, 7 warnings. Frontend Vitest 124/28, lint, typecheck pass. Build compiles but Next fails parsing TypeScript --showConfig output. Route analysis has no build artifact. Playwright did not start due listener EPERM. Dex provider live request blocked by DNS. npm audit: production 3 findings (1 critical, 2 high); full 8 (1 critical, 7 high).
BLOCKERS=Registry EAI_AGAIN prevents fetching an audit fix; DexScreener DNS unavailable; host denies browser listener and Next child output parsing; pip-audit/Trivy/Grype/Docker Scout absent; protected .env.example is not inspected or modified; .codex checkpoint files are not writable in the current workspace
UPDATED_AT=2026-10-07 local

Evidence: `docs/reports/dexscreener-early-market-intelligence-2026-10-07.md`,
`docs/case_studies/MUNK_EARLY_DISCOVERY.md`, and the current reassessment in
`docs/audits/EARLY_GEM_V2_BASELINE.md`. No commit was created; all dirty files
remain preserved. The report verdict is `IMPLEMENTATION_INCOMPLETE`.

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend parity and final evidence
CURRENT_TASK=Run web-specific unit/lint/type/build/e2e checks after nullable DexScreener launch-age projection; reconcile reports and record limitations
LAST_COMPLETED_STEP=Post-change `make verify` completed: Ruff PASS, mypy PASS (175 files), pytest 4 failed / 1592 passed / 24 skipped / 7 warnings (300.21s). Failures exactly match the four preserved `.env.example`/Compose contract failures. The Make target stopped before frontend gates.
NEXT_STEP=Run npm test, npm lint, and npm typecheck for apps/web; then production build, bundle analysis, and browser E2E if host allows.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; no Git metadata writes)
TEST_STATUS=Focused DEX/runtime 74 passed before the final assertion changes; latest focused DEX/detector/runtime/worker 20 passed. `make typecheck` PASS (175). Exact-current `make verify` has the four known protected-tree failures.
BLOCKERS=Protected dirty `.env.example` remains untouched. Public DexScreener DNS blocked; no live provider or Telegram acceptance claimed. `.codex` checkpoints are mounted read-only; docs/STATUS.md is the writable checkpoint.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=PostgreSQL restart/replay regression repair
CURRENT_TASK=Run the exact current migration head and complete integration suite in a fresh disposable PostgreSQL 16 database
LAST_COMPLETED_STEP=Reproduced and fixed process-local latency contamination of immutable early-stage snapshot identity; added nullable stream_gaps.provider_id so unknown provider identity survives persistence. Focused unit/contracts: 14 passed; Ruff: PASS.
NEXT_STEP=Apply Alembic head 0018_stream_gap_provider_id to a fresh PostgreSQL 16 tmpfs instance, then run all tests/integration.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Fresh migration run and full integration suite pending. Prior PG suite was 19 passed / 2 failed / 2 warnings at head 0017.
BLOCKERS=One prior disposable PostgreSQL container could not be removed under Docker policy; left untouched. A separate fresh tmpfs PostgreSQL 16 container started. Host live sockets remain restricted.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=PostgreSQL-backed current-candidate validation
CURRENT_TASK=Run migrations and integration tests only against the tmpfs-backed disposable PostgreSQL 16 container
LAST_COMPLETED_STEP=Reproduced fresh migration failure caused by the 37-character 0014 Alembic revision ID; changed the symbolic revision to 0014_social_call_revisions, updated its direct dependent/contracts, and verified static graph remains one head (0017; 32 metadata tables). Fresh migration now passes inside the isolated container.
NEXT_STEP=Run tests/integration in the isolated Python worker image against the disposable database; record exact pass/skip/fail count before stopping the database
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Fresh PostgreSQL 16 migration PASS after the revision-ID correction; focused migration contracts 4 passed; migration graph check PASS. Full PostgreSQL integration suite pending.
BLOCKERS=.codex files read-only; .env.example protected dirty artifact. Host Python process cannot open sockets, so DB checks run via isolated Docker network namespace. No live provider result claimed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=DexScreener production integration validation
CURRENT_TASK=Finish endpoint normalization and run the existing bounded discovery → persistence → early-runtime path
LAST_COMPLETED_STEP=Focused DEX/config/worker/early-runtime/provider-routing suite PASS (98 tests); Ruff PASS; `make typecheck` PASS (175 source files). Worker now evaluates snapshots after fetch, counts fetched/persisted separately, marks state-load failures DOWN, and honors DEX disablement for forward collection. Mixed-chain search normalization was added under a regression test.
NEXT_STEP=Run the full Python suite and fresh-database acceptance on a disposable PostgreSQL container; then probe the public read-only endpoint if the network allows it
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Focused suites 98 passed; new mixed-chain search 1 passed; make lint PASS; make typecheck PASS. Full `make verify` after the current DEX edits pending. No PostgreSQL DEX round-trip claimed yet.
BLOCKERS=.codex checkpoint files are mounted read-only. `.env.example` is protected dirty user data and remains unread/unmodified. Git metadata is read-only. Live DexScreener access not yet tested. Current repo already has unrelated dirty changes; no reset/stash/commit performed.
UPDATED_AT=2026-10-07 local

Baseline make verify (2026-10-07, before DexScreener edits): Ruff PASS; mypy PASS (175 source files); pytest FAIL with 4 failed / 1575 passed / 24 skipped / 7 warnings in 296.68s. Failures are the preserved `.env.example` secret-scan/release-example findings: `test_security_review_keyless_gate_is_pass_and_external_acceptance_is_explicit`, `test_external_wallet_intelligence_replay_seam_is_packaged_and_safe`, and two `test_security_review` assertions. The protected example file was not inspected or modified. The baseline `git diff --check` finding is its existing trailing blank line. No DexScreener edits were present when this baseline ran.

STATUS=IN_PROGRESS
CURRENT_PHASE=DexScreener provider implementation
CURRENT_TASK=Add bounded official profile/boost/takeover discovery to the existing DexScreener adapter and route normalized candidates through EarlyRuntimeService with durable first-seen and market evidence
LAST_COMPLETED_STEP=Fresh baseline make verify captured: Ruff PASS; mypy PASS (175); pytest 4 protected-file failures / 1575 passed / 24 skipped / 7 warnings. Baseline audit exists at docs/audits/EARLY_GEM_V2_BASELINE.md.
NEXT_STEP=Inspect exact config/composition and EarlyRuntime observation/projection contracts, then add focused discovery/parser/worker tests before implementation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Baseline make verify FAIL only in the same four pre-existing protected `.env.example` tests; baseline git diff check has pre-existing `.env.example` trailing blank line. Focused DexScreener tests not rerun yet.
BLOCKERS=Protected dirty `.env.example` must not be inspected/modified. PostgreSQL, live DexScreener and Telegram acceptance are environmental/external gates. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Gem V2 / DexScreener baseline
CURRENT_TASK=Capture a fresh make verify baseline, then connect official DexScreener discovery to canonical early-runtime persistence and scoring
LAST_COMPLETED_STEP=Audited the existing adapter, candidate/observation contracts, early runtime, feature engine, worker, alert/outcome owners and documented the current dependency map in docs/audits/EARLY_GEM_V2_BASELINE.md
NEXT_STEP=Run make verify on the preserved dirty candidate and record exact baseline counts/failures
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Baseline make verify pending. Existing repository evidence remains as recorded above; git diff --check has the pre-existing .env.example trailing blank-line finding.
BLOCKERS=Do not inspect, alter, or commit protected dirty .env.example contents. PostgreSQL/Docker runtime unavailable in prior checks; Git metadata read-only. Live DexScreener and Telegram remain external acceptance gates.
UPDATED_AT=2026-10-07 local

CURRENT_PHASE=Classify final verification failures and continue independent repository work
CURRENT_TASK=Record the current `make verify` result, then audit Caller-to-Wallet and rejection-to-Outcome operational paths
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=After adding `/v1/wallet-candidates` to the stale route contract, `make verify` completed: Ruff PASS, mypy PASS (175 source files), pytest 4 failed / 1575 passed / 24 skipped / 7 warnings (229.19s). The former route-contract failure is resolved.
NEXT_STEP=Inspect caller event, wallet activity, relation persistence, rejection reconciliation, and OutcomeTracker owners before implementing the next narrow gap
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Current full verification FAILS only in `test_keyless_review_reports_each_local_boundary_and_does_not_claim_external_scans`, `test_external_scans_without_installed_tools_are_blocked_not_passed`, `test_security_review_keyless_gate_is_pass_and_external_acceptance_is_explicit`, and `test_external_wallet_intelligence_replay_seam_is_packaged_and_safe`. The tests inspect protected dirty `.env.example`; it remains unread/unmodified. Focused route contract PASS (1 passed, 2 warnings). Migration graph check previously PASS (head 0017_smart_wallet_candidates; ORM metadata 32 tables).
BLOCKERS=Protected `.env.example` mismatch blocks security/release tests and must not be changed. PostgreSQL runtime unavailable (Docker socket denied, no host PostgreSQL). Git metadata read-only. npm registry EAI_AGAIN; production Next build subprocess capture limitation.
UPDATED_AT=2026-10-07 local

Smart Wallet candidate focused validation (2026-10-07): after correcting the frontend request assertion and candidate display matcher, targeted Vitest passed `39/39`; focused Python evaluator/read API/read persistence/migration/release identity/API schema passed `32 passed, 1 skipped` (the skip is the SQLite persistence test because `aiosqlite` is absent). The focused API route fixture is now being extended to assert bounded candidate response fields and explicit UNKNOWN copyability/quality.

STATUS=IN_PROGRESS
CURRENT_PHASE=Smart Wallet candidate API and worker contract validation
CURRENT_TASK=Run the API candidate projection regression, worker tests, mypy, frontend lint/typecheck, and focused browser candidate check if available
LAST_COMPLETED_STEP=Candidate evaluator has event-time and target-token tests; SQL model/repository/migration and API/UI path compile in focused contracts. Fixed the release-identity migration head/table count expectations to 0017/32.
NEXT_STEP=.venv/bin/ruff format tests/unit/test_read_api_routes.py tests/unit/test_release_identity.py && .venv/bin/pytest tests/unit/test_read_api_routes.py tests/unit/test_release_identity.py tests/contract/test_api_schema.py
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused candidate Python suite 32 passed/1 skipped; candidate frontend parser/component suites 39 passed. New route fixture assertion pending.
BLOCKERS=PostgreSQL/SQLite persistence runtime unavailable; Git metadata read-only; preserved .env.example is protected and dirty.
UPDATED_AT=2026-10-07 local

Smart Wallet candidate discovery application slice: added event-time bounded discovery over existing canonical wallet trade observations. It reuses WalletTrackingAnalyzer, SmartWalletScorer, and copyability projection; excludes discovery-token performance, excludes observations not available by cutoff, enforces five independent historical tokens/samples before QUALIFIED, and never auto-promotes to VERIFIED. Current focused tests: 3 passed; focused Ruff: PASS. This is not operational completion yet: durable owner/migration, checkpointed worker, API, and candidate UI remain open.

STATUS=IN_PROGRESS
CURRENT_PHASE=Implement operational Smart Wallet candidate discovery
CURRENT_TASK=Add a replay-safe candidate evaluator over existing canonical wallet trade observations and reuse WalletTrackingAnalyzer/SmartWalletScorer
LAST_COMPLETED_STEP=Confirmed the canonical observation table contains normalized wallet activity and candidate token lifecycle, while no durable wallet-candidate owner, worker, API, or separate candidate UI exists. Existing SmartWalletScorer and copyability projection are reusable.
NEXT_STEP=Write focused application-level tests for target-token exclusion, event-time cutoff, and candidate state gating before implementation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Prior recovery suites remain as recorded above. No Smart Wallet candidate pipeline tests run yet.
BLOCKERS=PostgreSQL runtime unavailable. Protected dirty .env.example; Next build subprocess capture restriction; npm registry DNS; Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code Services and Social Alpha fixture browser acceptance
CURRENT_TASK=Rerun the complete 60-case Social Alpha/Services fixture suite after fixing the Doctor same-origin host comparison
LAST_COMPLETED_STEP=Origin diagnostic proved Next server URL host is `localhost` while browser Origin and Host are `127.0.0.1`. Fixed comparison using request scheme + actual Host. Doctor route unit tests 3/3 and desktop Doctor E2E 1/1 pass.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused Doctor unit and browser tests PASS. Full viewport suite now PASS: 60/60 across desktop, laptop, tablet, mobile, mobile-wide.
BLOCKERS=PostgreSQL runtime unavailable. Next production build wrapper hits host child-process stdio capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

Services/Social Alpha current-code browser acceptance (2026-10-07): after the same-origin root-cause fix, `npx playwright test --config=playwright.social-alpha.config.ts --workers=1` passed all 60 cases over desktop (1440x900), laptop (1024x768), tablet (768x1024), mobile (390x844), and mobile-wide (430x932). This includes the bounded Service Doctor journey, service conflict rendering, stream state, and Social Alpha fixture journeys. Evidence is fixture/browser acceptance only; no real provider or PostgreSQL claim.

STATUS=IN_PROGRESS
CURRENT_PHASE=Audit remaining source-to-UI operational gaps
CURRENT_TASK=Trace Smart Wallet candidate, caller-wallet relation, and resolved-rejection outcome paths across domain, persistence, worker, API, UI, and tests
LAST_COMPLETED_STEP=Fixed Doctor same-origin handling with Host-aware comparison; route tests 3/3; full Services/Social Alpha fixture E2E 60/60.
NEXT_STEP=Search current source/schema/routes/UI for candidate lifecycle, caller-wallet relation producer/read projection, and rejection-to-outcome consumer; classify each layer
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Services/Social Alpha fixture browser acceptance 60/60 PASS. Next production build remains host-restricted at Next child-process output capture. PostgreSQL runtime unavailable.
BLOCKERS=No PostgreSQL test runtime; Docker socket denied and host PostgreSQL binaries absent. Production build child capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Validate the Services Doctor same-origin root-cause fix
CURRENT_TASK=Run the focused one-worker Doctor browser journey after switching the same-origin authority check to the request protocol plus Host header
LAST_COMPLETED_STEP=Root cause observed: Next URL host was `localhost`, while browser Origin and Host were `127.0.0.1`. Updated the guard to compare normalized Origin against request scheme plus Host, and added unit coverage for foreign/missing origins. Doctor route tests: 3 passed.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'services doctor is bounded' --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused Doctor route unit tests PASS (3). Current browser verification of the change pending.
BLOCKERS=PostgreSQL runtime unavailable. Next production build wrapper hits host child-process stdio capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

Current-code build root-cause evidence (2026-10-07): direct `npm run typecheck` exits 0. Direct `tsc --showConfig --project tsconfig.json --pretty false` writes valid JSON (6,141 bytes; 107 source files) when run by the shell. Next 16.3.3's exact `runTypeScriptCli` helper spawns Node with piped stdio but receives exit 0 with **0 stdout and 0 stderr bytes**; even a child `node -e 'process.stdout.write("hello")'` returns zero captured bytes. This reproduces the build parser failure below the application/TypeScript layer and is classified `NEEDS_BROWSER_RUNTIME` / host child-process stdio restriction. No typecheck gate was weakened. `npm run analyze:routes` was attempted separately and correctly refused because `.next/diagnostics/route-bundle-stats.json` was not produced by the failed build.

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code browser/runtime acceptance and remaining repository-owned P0 audit
CURRENT_TASK=Probe current Playwright runner; in parallel, inspect existing wallet-candidate, caller-wallet, and rejection-outcome owners before any further edits
LAST_COMPLETED_STEP=Direct TypeScript configuration is valid and direct frontend typecheck passes; the Next helper child-process pipe capture is the host failure. Route analysis remains unavailable without build stats.
NEXT_STEP=Inspect Playwright server config and feature owners, then run one bounded current-code Services/Operations browser journey; record listener restriction if it reproduces
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree; Git metadata is read-only)
TEST_STATUS=Focused service conflict Python and web tests pass; direct frontend typecheck passes. Production build cannot pass its Next child-process stdout capture. PostgreSQL remains `NEEDS_DATABASE_RUNTIME`.
BLOCKERS=Host child-process capture returns empty stdout/stderr for spawned subprocesses. `/tmp` target checkout absent; current `.git` read-only. Database runtime unavailable. Preserve dirty and untracked files.
UPDATED_AT=2026-10-07 local

Services browser recovery (2026-10-07): a bounded current-code Playwright run successfully started both fixture API and Next dev servers on loopback, so browser binding works in this runner. It failed at the first inventory assertion because the fixture omitted nullable `tool_count`, `supervisor_state`, and `last_seen_at` fields required by the strict `/v1/services` parser; the page correctly rendered `SERVICE INVENTORY UNKNOWN`. Fixed the fixture response to include canonical nulls (actual API response model supplies these fields). The product parser remains strict. Exact next gate: rerun the same one-test Services journey; if green, run the complete current Services fixture suite and Operations/Token Detail conflict tests.

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code populated browser acceptance for Services conflict projection
CURRENT_TASK=Verify the Services fixture/API contract after repairing fixture nullability
LAST_COMPLETED_STEP=Identified Services E2E failure as a non-conformant test fixture, not an app/runtime issue; strict read parser correctly failed closed. Added the API's nullable fields to fixture serialization.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'services fixture separates runtime'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree)
TEST_STATUS=Before the fixture patch, the test failed because inventory parsed as invalid. Build remains host-blocked at captured child stdout; direct TypeScript passes. PostgreSQL remains unavailable.
BLOCKERS=Current browser host can bind localhost and launch browser. Need re-run fixture suite after fix. Preserve pre-existing dirty files.
UPDATED_AT=2026-10-07 local

Conflict UI browser coverage: added an E2E contract asserting backend-projected PRICE conflict evidence on a service detail and Operations aggregate. Before fixture implementation, the expected red is missing Dexscreener inventory/conflict fixture data; the existing API read parser/unit test already proves response validation.

STATUS=IN_PROGRESS
CURRENT_PHASE=Add current-code browser proof for service-scoped and aggregate conflict projections
CURRENT_TASK=Run the new focused conflict E2E before extending its fixture
LAST_COMPLETED_STEP=One current Services fixture browser journey passes after canonical nullable fields were added.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'backend price conflict evidence'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree)
TEST_STATUS=Current UI fixture journey PASS (1 test). New conflict browser assertion not yet run.
BLOCKERS=No external/browser bind blocker observed. Production build remains blocked by empty stdout in host child-process pipes.
UPDATED_AT=2026-10-07 local

Service conflict fixture repair (2026-10-07): the new conflict E2E first failed because the fixture inventory had no service IDs from the real producer pair. Added the existing Dexscreener/GMGN descriptors to test data and a viewer-authenticated fixed `/v1/operations/conflicts` response with bounded synthetic PRICE evidence. These rows are fixture-only and do not change production certification/readiness. Next run is the focused Services page/conflict E2E on current source.

STATUS=IN_PROGRESS
CURRENT_PHASE=Validate current Service conflict browser projections
CURRENT_TASK=Run the service inventory and service/Operations conflict fixture journeys
LAST_COMPLETED_STEP=Fixture contract root cause confirmed: actual conflict producer uses service IDs Dexscreener and GMGN; Services E2E fixture lacked those descriptors and conflict endpoint. Added canonical rows.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'services fixture separates runtime|backend price conflict evidence'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=New conflict browser test red on missing Dexscreener fixture; corrected fixture and endpoint, rerun pending.
BLOCKERS=Host build subprocess stdout restriction remains; live PostgreSQL unavailable.
UPDATED_AT=2026-10-07 local

Current-code conflict browser gate (2026-10-07): focused desktop Playwright tests passed after fixture corrections: 2 passed (Services inventory contract and backend PRICE conflict rendered in selected service detail and Operations aggregate). This is fixture UI acceptance only, not production provider or DB evidence. Next run: full Social Alpha Playwright config (Services + Social Alpha across configured desktop/laptop/tablet/mobile viewports).

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code Services and Social Alpha fixture browser acceptance
CURRENT_TASK=Run the full current Services/Social Alpha browser config across all configured viewports
LAST_COMPLETED_STEP=Conflict projections visibly render backend fixture evidence on Services detail and Operations aggregate (2 focused E2E passed).
NEXT_STEP=cd apps/web && npm run test:e2e:social
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree)
TEST_STATUS=Focused current-browser conflict acceptance PASS. Production build remains host-restricted. No live/provider acceptance claimed.
BLOCKERS=PostgreSQL runtime unavailable; Next production typecheck wrapper cannot capture child stdio; read-only Git metadata.
UPDATED_AT=2026-10-07 local

Full fixture browser reprobe (2026-10-07): `npm run test:e2e:social` exited before test execution because its fixture API could not bind `127.0.0.1:13101` (`listen EPERM`). This is distinct from the focused 2-test E2E run that passed under the same config shortly before. Classify provisionally as host listener restriction pending leftover-listener inspection and one-worker retry; no browser test count is claimed from this run.

STATUS=IN_PROGRESS
CURRENT_PHASE=Reprobe intermittent Playwright listener restriction
CURRENT_TASK=Check whether a stale local listener exists; retry the fixture suite with one worker
LAST_COMPLETED_STEP=Focused conflict UI browser tests passed (2). Full five-viewport fixture suite failed at webServer startup before tests because fixture API bind returned EPERM.
NEXT_STEP=Inspect listening TCP sockets and process names, then run `npx playwright test --config=playwright.social-alpha.config.ts --workers=1` if no stale listener is present
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty preserved worktree)
TEST_STATUS=No tests executed in last run; startup-only EPERM. Prior focused E2E remains PASS.
BLOCKERS=Intermittent host listener restriction; PostgreSQL unavailable; Next child stdout capture restriction.
UPDATED_AT=2026-10-07 local

Listener check (2026-10-07): `ss -ltn` cannot inspect sockets because netlink returns `Operation not permitted`; no Next/Playwright/fixture API processes are present by process-name check. Retrying the current fixture suite with one worker to reduce host bind contention.

NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts --workers=1

Full Services/Social Alpha fixture browser run (2026-10-07): `npx playwright test --config=playwright.social-alpha.config.ts --workers=1` executed all 60 viewport cases; 55 passed and 5 failed, exactly the Service Doctor journey once per viewport. The fixture-backed conflict UI, service inventory, mobile overflow, and Social Alpha paths passed. Doctor displays `Operator authorization was rejected.`; the current E2E assertion does not capture whether the 403 came from same-origin validation or the fixture API operator check. Next action is to add a test-only safe response-detail assertion and run one desktop Doctor case. No credential values will be logged.

STATUS=IN_PROGRESS
CURRENT_PHASE=Diagnose current Services Doctor E2E authorization response
CURRENT_TASK=Distinguish same-origin guard 403 from upstream fixture auth 403 with safe response detail
LAST_COMPLETED_STEP=Full five-viewport Services/Social Alpha browser run completed: 55 passed, 5 doctor failures.
NEXT_STEP=Add Playwright response assertion for the doctor proxy status and non-secret detail, then run one desktop doctor case
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full fixture E2E: 55 PASS / 5 FAIL; all failures same doctor auth response. Focused conflict projection E2E remains PASS.
BLOCKERS=Doctor E2E cause not yet isolated. Host Next build pipe capture and PostgreSQL runtime remain unavailable.
UPDATED_AT=2026-10-07 local

Doctor boundary follow-up (2026-10-07): the focused browser response body identifies the 403 as `same-origin request required`, so the operator-token fixture check was not reached. Added a non-secret E2E diagnostic assertion that reports only the browser request origin and the safe response detail. Next: rerun one desktop Doctor journey to see whether the browser's Origin header is absent or differs from the request URL.

NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'services doctor is bounded'

STATUS=IN_PROGRESS
CURRENT_PHASE=Diagnose the Services Doctor same-origin rejection
CURRENT_TASK=Run only the desktop Doctor fixture and inspect the server-side URL origin, Origin, and Host values
LAST_COMPLETED_STEP=Confirmed the route rejects with the same-origin detail despite matching browser URL origin and Origin. Added a temporary diagnostic limited to origin and Host values.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts e2e/services.spec.ts --project=desktop --grep 'services doctor is bounded' --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Doctor fixture was failing; the server comparison mismatch is now understood and repaired. Diagnostic excluded credentials and request body.
BLOCKERS=PostgreSQL runtime unavailable. Next production build wrapper hits host child-process stdio capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code Services and Social Alpha fixture browser acceptance
CURRENT_TASK=Rerun the complete Social Alpha/Services fixture suite after fixing the Doctor same-origin host comparison
LAST_COMPLETED_STEP=Origin diagnostic proved Next server URL host is `localhost` while browser Origin and Host are `127.0.0.1`. Fixed comparison using request scheme + actual Host. Doctor route unit tests 3/3 and desktop Doctor E2E 1/1 pass.
NEXT_STEP=cd apps/web && npx playwright test --config=playwright.social-alpha.config.ts --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused Doctor unit and browser tests PASS. Full viewport suite is the active gate.
BLOCKERS=PostgreSQL runtime unavailable. Next production build wrapper hits host child-process stdio capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Run repository verification after shutdown recovery and Doctor fix
CURRENT_TASK=Run make verify on the preserved current worktree
LAST_COMPLETED_STEP=The full Services/Social Alpha current-code fixture browser matrix passed 60/60 after the Doctor same-origin fix.
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused Doctor route tests 3/3, focused Doctor browser 1/1, Services/Social Alpha browser 60/60. Full repository verification pending.
BLOCKERS=PostgreSQL runtime unavailable; production Next build subprocess output capture issue; Git metadata read-only.
UPDATED_AT=2026-10-07 local

Verification result after recovery (2026-10-07): `make verify` stopped at its first gate, Ruff, on one import-order issue in `packages/domain/src/memeradar_domain/__init__.py` (ServiceConflict exports). No tests ran under this command. Repair that formatting-only issue, then rerun `make verify`.

STATUS=IN_PROGRESS
CURRENT_PHASE=Repair first full-verification failure
CURRENT_TASK=Apply Ruff's import organizer to the touched domain package export file, then rerun make verify
LAST_COMPLETED_STEP=make verify reproduced exactly one I001 import-order violation in the ServiceConflict domain export block.
NEXT_STEP=.venv/bin/ruff check --fix packages/domain/src/memeradar_domain/__init__.py
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=make verify stopped before unit tests due Ruff I001. Browser E2E 60/60 and focused doctor checks passed.
BLOCKERS=PostgreSQL runtime unavailable; Next production build child stdio capture issue; Git metadata read-only.
UPDATED_AT=2026-10-07 local

Full verification result (2026-10-07): after Ruff repaired the domain export order, `make verify` passed Ruff and mypy (174 source files), then pytest ended `7 failed, 1567 passed, 22 skipped, 7 warnings` in 228.25s. Failures: API OpenAPI route expectation missing the 3 implemented conflict routes; read-route contract missing Operations/Token conflict projections; release-identity expected migration head 0015 instead of current 0016; security-review status failures; `.env.example` contract expected an absent `X_PROVIDER_ENABLED=false`. No browser tests are included in this target. The `.env.example` is already dirty and contains a secret-like line in test output; preserve it and do not print or modify its contents until ownership/safety is resolved.

STATUS=IN_PROGRESS
CURRENT_PHASE=Repair repository verification drift without touching protected env artifact
CURRENT_TASK=Inspect security-review result names/status and update stale route/migration contract expectations; preserve .env.example
LAST_COMPLETED_STEP=make verify counts captured: Ruff PASS, mypy PASS, pytest 7 failed/1567 passed/22 skipped/7 warnings. Full Services/Social Alpha browser E2E 60/60 passed.
NEXT_STEP=Get redacted security-review check names/status only, then fix the API schema and release identity expectations
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=make verify FAIL due 7 tests described above. No database verification claimed.
BLOCKERS=.env.example is a dirty user artifact with a secret-like line; do not print/commit or alter it during this gate. PostgreSQL runtime unavailable. Git metadata read-only.
UPDATED_AT=2026-10-07 local

Verification triage: security review check metadata identifies only `.env.example` line 194 under the `telegram_bot_token` rule. The file was already dirty at resume and its value is not inspected or modified. This explains the security-review status failures; it is a protected local artifact issue, not grounds to weaken or skip the secret scanner. `test_compose_contract.py` also fails because the dirty example lacks an expected `X_PROVIDER_ENABLED=false` line. Preserve this file unchanged.

STATUS=IN_PROGRESS
CURRENT_PHASE=Re-run full verification after updating stale API/migration contracts
CURRENT_TASK=Run make verify on the current preserved candidate
LAST_COMPLETED_STEP=Updated route contract expectations for all three conflict endpoints and migration identity to 0016/30 tables; focused tests passed 3/3 in .venv. An initial focused run used system Python and failed collection for missing FastAPI; no application tests ran in that attempt.
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused route/migration contracts 3 passed. Current full verification pending.
BLOCKERS=Secret scanner reports protected dirty .env.example line 194 under telegram_bot_token rule; do not inspect or alter value. PostgreSQL runtime unavailable; Git metadata read-only.
UPDATED_AT=2026-10-07 local

Full verification rerun (2026-10-07): Ruff PASS; mypy PASS (174 files); pytest `4 failed, 1570 passed, 22 skipped, 7 warnings` in 226.84s. The route-surface and release-identity failures are resolved. Remaining failures are `test_compose_contract.py` missing `X_PROVIDER_ENABLED=false` in the preserved dirty `.env.example`, plus three security-review assertions because secret scanning detects that file's protected Telegram-token-rule match. The actual value remains unread/unmodified. The security gate stays enabled and FAIL; no bypass added.

STATUS=IN_PROGRESS
CURRENT_PHASE=Run remaining independent frontend verification and update final evidence
CURRENT_TASK=Run complete frontend Vitest, lint, and typecheck commands independently of the Python test failure
LAST_COMPLETED_STEP=Full make verify rerun: Ruff/mypy pass; pytest 4 failed/1570 passed/22 skipped/7 warnings. Stale API/migration expectations now pass; remaining failures are confined to preserved dirty .env.example policy/example content.
NEXT_STEP=cd apps/web && npm test, npm run lint, and npm run typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Frontend fixture browser 60/60 PASS. Full frontend unit/lint/typecheck pending. PostgreSQL runtime unavailable.
BLOCKERS=Do not inspect/modify/commit `.env.example`; secret scan reports line 194 under token rule and test expects missing X provider default. Production build host child-process capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

Frontend verification after recovery (2026-10-07): full Vitest `118 passed` across 28 files; `npm run lint` PASS. First typecheck found an inferred optional-header union error in the new Doctor negative-origin test; annotated the cases as `HeadersInit[]`, then reran route tests (3 passed) and `npm run typecheck` PASS. Host emitted `Failed to create stream fd: Operation not permitted` warnings while the typecheck postcondition passed.

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-code operator-route browser acceptance
CURRENT_TASK=Run the default populated/empty operator dashboard, accessibility, and visual matrix E2E config on current dev source
LAST_COMPLETED_STEP=Full frontend Vitest 118/118, lint PASS, typecheck PASS after test typing repair; Services/Social Alpha fixture suite 60/60.
NEXT_STEP=cd apps/web && npx playwright test --workers=1
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Default operator route E2E pending. Production-mode E2E remains blocked because current Next build cannot capture TypeScript subprocess output.
BLOCKERS=PostgreSQL runtime unavailable; production build host child-process output capture issue; protected dirty .env.example secret-scan finding; Git metadata read-only.
UPDATED_AT=2026-10-07 local

Default operator browser acceptance (2026-10-07): `npx playwright test --workers=1` completed 75 cases across desktop, laptop, tablet, mobile, and mobile-wide: 65 passed, 10 skipped, zero failures. Together with the separate current Services/Social Alpha fixture suite (60/60), dev/fixture browser results are 125 passed / 10 skipped. The default axe and keyboard journeys in this run passed where scheduled. These are not production-server E2E and do not establish real provider or populated production database acceptance.

STATUS=IN_PROGRESS
CURRENT_PHASE=Current dependency scan availability and production build gate
CURRENT_TASK=Run npm production audit and then the full audit; record each independently without changing dependencies
LAST_COMPLETED_STEP=Dev/fixture E2E current code complete: 125 passed, 10 skipped across Services/Social Alpha and operator dashboard routes.
NEXT_STEP=cd apps/web && npm audit --omit=dev
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Python make verify remains blocked by preserved `.env.example` security finding and missing X flag; frontend Vitest/lint/typecheck PASS; browser E2E PASS as above.
BLOCKERS=Protected dirty `.env.example` finding. PostgreSQL unavailable. Production Next build subprocess stdio capture restriction. Git metadata read-only.
UPDATED_AT=2026-10-07 local

Dependency audit: `npm audit --omit=dev` returned FAIL with 3 production dependency vulnerabilities: Next.js 16.3.3 (critical; audit says 16.4.0 is outside current exact pin), sharp (<0.35.5, high), and source-map-js (<=1.2.1, high). No fixes were applied by audit. Next step is inspect peer/engine compatibility and the current package diff before any dependency mutation.

STATUS=IN_PROGRESS
CURRENT_PHASE=Audit remaining operational repository gaps
CURRENT_TASK=Trace Smart Wallet candidate, Caller-Wallet relation, and resolved-rejection OutcomeTracker paths before implementing or classifying
LAST_COMPLETED_STEP=Production npm audit found three advisories; registry metadata lookup for compatibility returned EAI_AGAIN for registry.npmjs.org. No dependency changes were made.
NEXT_STEP=Inspect current source, persistence, worker, API, frontend, and test paths for the three remaining operational gaps
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Python make verify: 4 failures, 1570 passed, 22 skipped, 7 warnings; frontend: 118 tests/28 files PASS, lint/typecheck PASS, dev/fixture browser 125 passed/10 skipped. Production audit FAIL (3 vulnerabilities). Full npm audit pending.
BLOCKERS=PostgreSQL runtime unavailable. Production build subprocess output capture restriction. Protected dirty .env.example prevents security/release verification. Git metadata read-only. npm registry lookup failed EAI_AGAIN.
UPDATED_AT=2026-10-07 local

Full dependency audit attempt (2026-10-07): `npm audit` did not return an advisory report because the npm registry endpoint failed DNS resolution (`EAI_AGAIN registry.npmjs.org`). Status is `BLOCKED_NETWORK`, not PASS. The prior successful `npm audit --omit=dev` result remains the only current advisory evidence (three production advisories); package metadata lookup is likewise unavailable, so no dependency update was attempted.

STATUS=IN_PROGRESS
CURRENT_PHASE=Reprobe database acceptance and verify conflict persistence test coverage
CURRENT_TASK=Check current isolated PostgreSQL availability and inspect whether the conflict repository has an integration/restart test
LAST_COMPLETED_STEP=Full npm audit was separately attempted and failed at the npm advisory endpoint with EAI_AGAIN; no dependency changes were made.
NEXT_STEP=Check database URL presence, local PostgreSQL/Docker tools, and service-conflict integration coverage
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=No new application tests run after the checkpoint. Existing conflict unit/API/frontend tests pass as previously recorded; PostgreSQL acceptance remains unproven.
BLOCKERS=Registry DNS EAI_AGAIN. Protected dirty .env.example; PostgreSQL runtime previously unavailable; host Next build subprocess output capture restriction; read-only git metadata.
UPDATED_AT=2026-10-07 local

Service-conflict PostgreSQL coverage (2026-10-07): added `tests/integration/test_service_conflict_persistence_postgres.py` using the production SQLAlchemy repository and migration-backed table. It covers initial insert, idempotent replay, timezone-aware timestamp round-trip, continued-conflict versioning, explicit resolution history, process/session restart readback and evidence/provenance equality. Ruff passes. The test is correctly skipped (`1 skipped`) because `MEMERADAR_TEST_DATABASE_URL` is unset; no PostgreSQL pass is claimed. Docker client exists, but `docker info` fails with permission denied on `/var/run/docker.sock`; PostgreSQL binaries are absent.

STATUS=IN_PROGRESS
CURRENT_PHASE=Smart Wallet candidate operational-gap audit
CURRENT_TASK=Trace canonical wallet observations through discovery/scoring and identify the smallest complete candidate persistence/read path
LAST_COMPLETED_STEP=Service/asset conflict model, migration, PRICE producer, APIs/UI and current fixture acceptance exist. Added the missing PostgreSQL restart/replay integration test; its local execution is skipped due unavailable isolated DB.
NEXT_STEP=Inspect WalletActivity and SmartWalletScorer composition, observation ingestion/worker scheduling, and injectable wallet read catalog contract
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Service conflict integration test Ruff PASS; PostgreSQL test SKIPPED (no DB URL). Existing conflict persistence SQLite test, unit/API/frontend tests and conflict fixture browser checks were previously PASS. Docker socket denied.
BLOCKERS=PostgreSQL runtime unavailable (no DB URL/binaries; Docker socket permission denied). User-owned dirty `.env.example` secret-scan failure remains protected. npm registry DNS EAI_AGAIN. Next build wrapper has host subprocess-capture limitation. Git metadata read-only.
UPDATED_AT=2026-10-07 local

CURRENT_PHASE=Smart Wallet candidate implementation validation
CURRENT_TASK=Validate the event-time evaluator, SQL candidate repository, migration contract, read API and frontend candidate projection
LAST_COMPLETED_STEP=Full frontend Vitest passed 124 tests across 28 files; frontend lint/typecheck passed after the Playwright run completed; current `/wallets` route browser acceptance passed at 1440x900, 1024x768, 768x1024, 390x844, and 430x932. Candidate API route/OpenAPI, worker scheduling, event-time candidate tests, and make typecheck also passed.
NEXT_STEP=Add `/v1/wallet-candidates` to the stale phase-7 read-route contract and run that focused contract, then rerun make verify with protected-file output redaction
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Full make verify: Ruff PASS, mypy PASS (175 files), pytest FAIL (5 failed, 1574 passed, 24 skipped, 7 warnings). One failure is a stale repository route contract missing `/v1/wallet-candidates`; four are attributable to protected dirty `.env.example` (missing X flag and secret scanner). Migration graph PASS (0017/32); git diff check excluding `.env.example` PASS.
BLOCKERS=PostgreSQL runtime unavailable (no DB URL/binaries; Docker socket permission denied). Git metadata read-only. `.env.example` remains a protected dirty artifact.
UPDATED_AT=2026-10-07 local

RECOVERY_UPDATE=Interrupted candidate API/read-projection work resumed on 2026-10-07 from the preserved dirty tree at HEAD 35274d2fd7ae07ef6446b66cef70ac6b93f5e84e, branch main. Added the already-implemented GET `/v1/wallet-candidates` path to the stale bounded-read-route contract. Focused route contract: 1 passed, 2 deprecation warnings. No interrupted edits were truncated; candidate implementation files parse and typecheck.
CURRENT_PHASE=Final current-candidate verification
CURRENT_TASK=Rerun `make verify` after the stale route contract repair, capture redacted diagnostics, and update observed evidence
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Focused `test_read_api_route_surface_is_bounded_get_only_and_provider_free_at_application_boundary` passed (1 passed, 2 warnings).
NEXT_STEP=Run `make verify` through an in-memory output filter that redacts any `.env.example` or `telegram_bot_token` diagnostic line
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Focused contract PASS. Prior full verify had 5 failures / 1574 passed / 24 skipped / 7 warnings; one stale route contract is now fixed. Current complete verification pending.
BLOCKERS=Protected dirty `.env.example` must remain unread/unmodified; its policy/example mismatch may fail security/release tests. PostgreSQL runtime unavailable (Docker socket denied, no host PostgreSQL). Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Continue repository-owned closure after recovered candidate route contract
CURRENT_TASK=Audit and close the next narrow operational gap: caller-wallet event relations and rejection-to-outcome analysis
LAST_COMPLETED_STEP=Added `/v1/wallet-candidates` to the stale bounded-read-route contract; focused route contract PASS (1 passed, 2 deprecation warnings). Current `make verify`: Ruff PASS, mypy PASS (175 source files), pytest 4 failed / 1575 passed / 24 skipped / 7 warnings (229.19s). The former route failure is resolved.
NEXT_STEP=Inspect canonical social calls, wallet activity, caller outcome persistence and pre-identity rejection/outcome owners before deciding minimal work
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata is read-only)
TEST_STATUS=Current make verify FAILS in three protected `.env.example` security/release assertions and one compose contract assertion. Exact failed tests: `test_keyless_review_reports_each_local_boundary_and_does_not_claim_external_scans`, `test_external_scans_without_installed_tools_are_blocked_not_passed`, `test_security_review_keyless_gate_is_pass_and_external_acceptance_is_explicit`, `test_external_wallet_intelligence_replay_seam_is_packaged_and_safe`. Focused route contract PASS. Do not inspect, edit, or commit `.env.example`.
BLOCKERS=PostgreSQL runtime unavailable (no DB URL/binaries; Docker socket permission denied). `.env.example` is protected dirty user data. Git metadata read-only. npm registry DNS unavailable. Production Next build child-process output capture is host-restricted.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Recovery evidence finalized; remaining repository gaps classified
CURRENT_TASK=Continue with durable Caller-to-Wallet relations and pre-identity rejection-to-outcome ownership in a follow-up implementation slice
LAST_COMPLETED_STEP=Recovered interrupted read/API/Operations edits; fixed bounded route contract; full make verify rerun and current authoritative/root-cause reports recorded
NEXT_STEP=Implement one canonical per-call CallerWallet event relation producer, persistence, bounded projection and caller-detail display; separately design provisional rejection identity and immutable outcome linkage
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata read-only)
TEST_STATUS=make verify: Ruff PASS, mypy PASS (175), pytest 4 failed / 1575 passed / 24 skipped / 7 warnings. The stale candidate route contract is fixed. Frontend Vitest 124/28, lint and typecheck PASS; recorded dev/fixture browser 125 passed / 10 skipped. PG current-tree acceptance not run. Migration metadata head 0017, 32 tables.
BLOCKERS=Repository gaps remain: per-call Caller-to-Wallet relation producer/projection; pre-identity rejection reconciliation/outcome consumer; candidate outcome maturation. Environment: PostgreSQL/Docker unavailable, production browser/listener restricted, npm full audit blocked by DNS. Protected `.env.example` causes current security/release test failures and is preserved. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-current-tree database and replay validation
CURRENT_TASK=Complete legacy migration acceptance, run provider read-only probe, then run make verify and frontend/build checks
LAST_COMPLETED_STEP=Fresh PostgreSQL 16 migration to 0018_stream_gap_provider_id passed; full integration suite passed 21 tests with 2 dependency deprecation warnings. Legacy head 0015_named_stream_runtime_state upgraded to current head 0018. Repaired deterministic early snapshot replay and lossless nullable stream-gap provider identity; feature snapshot count now correctly asserted once per shared immutable checkpoint.
NEXT_STEP=Run exact local make verify with protected-file diagnostics redacted; then run frontend tests/lint/typecheck/build and security audits.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Focused snapshot/stream/migration/release contracts: 14 passed; Ruff touched paths PASS. Fresh and legacy PostgreSQL migration PASS; integration 21 passed/2 warnings. Full verify pending.
BLOCKERS=Public DexScreener read-only adapter probe did not complete within the local command window; host/Docker network restrictions are suspected but not yet confirmed. Protected dirty `.env.example` remains untouched and can fail repository security/release assertions. No application writes or live trading were performed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Final verification after documented search quota correction
CURRENT_TASK=Run complete `make verify` on the post-rate-bucket source and capture a secret-safe summary
LAST_COMPLETED_STEP=Context7 official DexScreener documentation confirms public profile/discovery/search/meta limits of 60 requests/minute and market-data limit groups; corrected `/latest/dex/search` from the 300/min market bucket into its own 60/min bucket with a focused regression test. Provider probe returned DNS error `Could not resolve host: api.dexscreener.com` and HTTP status 000.
NEXT_STEP=Run `make verify` with output redirected to a private log; expose only aggregate test counts and gate statuses.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree)
TEST_STATUS=Fresh PostgreSQL 16 head 0018 migration PASS; legacy 0015 to 0018 upgrade PASS; current PostgreSQL integration 21 passed/2 warnings. Focused replay/stream/migration tests 14 passed, Ruff touched paths PASS. Full verify pending after the last search-rate code/test change.
BLOCKERS=Protected dirty `.env.example` causes four known repository verification failures and remains untouched. DexScreener live acceptance blocked by DNS resolution. No provider data or Telegram send was fabricated.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=DexScreener launch-time provenance correction
CURRENT_TASK=Keep provider first-seen time distinct from pair creation time; score and project launch age only when an explicit bounded event timestamp is available
LAST_COMPLETED_STEP=Red tests reproduced DexScreener discovery `occurred_at` being treated as launch time and the resulting fabricated runtime age. Added nullable-age behavior and exact pair timestamp handoff from the latest same-token Dex market snapshot. Focused DEX/detector/runtime/worker tests: 20 passed; Ruff on touched paths passed.
NEXT_STEP=Run full `make verify` on the current dirty tree and capture a redacted aggregate summary.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata read-only)
TEST_STATUS=Focused DEX/runtime suite 74 passed before the final exact-pair assertions; latest focused detector/runtime/worker/provider run 20 passed; `make typecheck` PASS (175 source files). Full post-change `make verify` pending. Previous full make verify had 4 protected-file-related failures, 1,589 passed, 24 skipped, 7 warnings.
BLOCKERS=Protected dirty `.env.example` remains unread/unmodified. DexScreener public API DNS is unavailable. No live provider or Telegram evidence is claimed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Production frontend and browser validation
CURRENT_TASK=Reprobe current-code browser E2E and route bundle analysis after frontend build reaches its host-limited TypeScript subprocess step
LAST_COMPLETED_STEP=Frontend direct checks: Vitest 124/28 files PASS, ESLint PASS, TypeScript PASS. `npm run build` compiled, then exited 1 because Next could not parse `tsc --showConfig` output; no type checks were disabled.
NEXT_STEP=Run `npm run test:e2e` with output redirected and report whether the host permits local fixture/server listeners; do not call failed pre-navigation runs browser passes.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree; Git metadata read-only)
TEST_STATUS=DEX/runtime focused 20 passed; broad DEX/runtime subset 74 passed before final test additions. `make typecheck` PASS (175). Current `make verify` has four pre-existing protected-tree failures. Frontend Vitest 124/28, ESLint and TypeScript PASS. Production build blocked after compile by Next/TypeScript child-output parsing.
BLOCKERS=Protected dirty `.env.example` remains unread/unmodified. DexScreener live DNS and Telegram live acceptance are unavailable. Production browser listener has not been re-probed after this source correction.
UPDATED_AT=2026-10-07 local

## Final recovery checkpoint — 2026-10-07

CURRENT_PHASE=Exact-tree PostgreSQL acceptance
CURRENT_TASK=Prove legacy 0015 migration to head on the current source and record schema counts
STATUS=IN_PROGRESS
LAST_COMPLETED_STEP=Fresh migration and legacy 0015-to-head migration PASS; tests/integration passed 21/21 against each schema with 2 known deprecation warnings per run. Both schemas report 33 DB tables (32 ORM tables plus alembic_version), 31 FKs, 95 indexes and 74 timestamptz columns.
NEXT_STEP=Remove only the temporary PostgreSQL container and isolated test network created in this run, then update final evidence and verify the worktree/diff state
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; worktree dirty and preserved)
TEST_STATUS=Focused DEX/detection/runtime/worker 20 passed; prior broad subset 74 passed before final test additions; make typecheck 175 files passed; Vitest 124/28 passed, frontend lint/typecheck passed; make verify 1592 passed, 24 skipped, 4 failed, 7 warnings; fresh migration and integration 21 passed; legacy 0015 migration to head and integration 21 passed; current migration head 0018; ORM 32 tables; PostgreSQL 33 tables, 31 FKs, 95 indexes, 74 timestamptz; Next build blocked after compile at TypeScript --showConfig output parsing; E2E blocked before tests by listener EPERM; DexScreener live request blocked by DNS
BLOCKERS=Full make verify failures involve protected dirty .env.example/Compose security contracts; npm registry EAI_AGAIN prevents fetching patch; production audit sees one critical and two high findings; DexScreener DNS unavailable; host Python TCP connect and browser listener return EPERM; Next build subprocess output parsing is host-blocked; pip-audit, Trivy, Grype and Docker Scout unavailable; .codex checkpoint files are read-only in this workspace. No remaining database blocker for the tested disposable fresh/legacy paths.
UPDATED_AT=2026-10-07 local

Evidence is in `docs/reports/dexscreener-early-market-intelligence-2026-10-07.md`,
`docs/case_studies/MUNK_EARLY_DISCOVERY.md`, and the reassessment section of
`docs/audits/EARLY_GEM_V2_BASELINE.md`. No commit or remote operation was made.
Final report verdict: `IMPLEMENTATION_INCOMPLETE`.

STATUS=IN_PROGRESS
CURRENT_PHASE=DexScreener forward-outcome enrollment
CURRENT_TASK=Validate DEX discovery outcome enrollment, replay bounds, and persistent worker path
LAST_COMPLETED_STEP=Added a failing test for a DexScreener-only candidate; it failed with zero outcomes as expected. Extended the existing forward collector with validated Solana Dex candidate records, discovery-relative outcome IDs, explicit unknown launch age, and as-of filtering for future market/stage rows. Added an opt-in PostgreSQL insert/outcome/replay test. Ruff and focused unit/replay tests passed; the focused unit+integration selection reports 17 passed, 2 skipped (SQLite driver and missing PostgreSQL URL). `make verify` before this test-only addition returned Ruff PASS, mypy PASS (175), pytest 4 failed/1593 passed/24 skipped/7 warnings; four failures are the already-recorded protected `.env.example` and Compose checks.
NEXT_STEP=Rerun make verify on the current tree; stream only sanitized suite summaries to avoid disclosing protected .env.example diagnostics
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (dirty worktree preserved)
TEST_STATUS=Focused unit+integration selection PASS (17 passed, 2 skipped); make typecheck PASS (175 files); current make verify rerun pending; PostgreSQL persistence/restart test is present but SKIPPED because no test DB is configured.
BLOCKERS=No test database URL, host PostgreSQL tools or Docker daemon. Protected dirty .env.example remains untouched. DexScreener live DNS, npm registry DNS, production browser listener, Next build subprocess, and unavailable extra security scanners remain. Prior exact-tree PostgreSQL results predate this collector change.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=DexScreener forward-outcome enrollment and current verification
CURRENT_TASK=Continue the remaining Early Gem v2 and DexScreener repository gaps after recording the DEX outcome-enrollment slice
LAST_COMPLETED_STEP=Extended the shared forward collector to process canonical Solana DexScreener discovery rows as first-seen checkpoints, with stable DEX outcome IDs, unknown launch-age fields, and as-of filtering. Added unit and opt-in PostgreSQL tests. Current focused selection: 17 passed, 2 skipped. `make typecheck`: 175 source files passed. Current `make verify`: Ruff/mypy PASS; pytest 4 failed, 1593 passed, 25 skipped, 7 warnings. Four failures remain the protected `.env.example`/Compose checks.
NEXT_STEP=Audit the next repository-owned gap from the current Early Gem baseline and implement the smallest canonical extension with focused tests
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved)
TEST_STATUS=Focused DEX forward outcome tests PASS (17 passed, 2 skipped). PostgreSQL insert/replay test SKIPPED because no test DB URL is configured; existing SQLite persistence test SKIPPED because aiosqlite is absent. Prior schema migration acceptance predates the collector change. Current full verify has four protected-tree failures.
BLOCKERS=Protected dirty .env.example/Compose checks prevent clean make verify; do not modify those user-owned changes. Exact-current collector PostgreSQL persistence, DexScreener live request, Telegram delivery, production browser acceptance, available security scanners, and mature real OOS data remain unverified or environment blocked.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Market microstructure evidence
CURRENT_TASK=Add an uncalibrated multi-label market-behavior classifier to the existing early-feature JSON and token-detail read path
LAST_COMPLETED_STEP=Corrected EarlyFeatureEngine trade-kind filtering and market-reference price semantics. Focused early-feature/runtime/replay/flow/organic/GMGN/price-semantics tests passed 113; touched Ruff, make typecheck (175 files), and diff-check passed.
NEXT_STEP=Add focused tests for evidence-gated archetype labels, multi-label output, UNKNOWN handling, and no future-input leakage before implementation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved)
TEST_STATUS=Latest focused source evidence is in docs/reports/agentic-loop/2026-10-07-early-feature-event-semantics.md. Existing PostgreSQL fresh/legacy tests passed previously, but exact-current new nested metric persistence has not been rerun.
BLOCKERS=No current live launch cohort or calibrated winner probabilities. DexScreener DNS, browser listener, npm registry, and optional scanner tooling remain host/external blocked. Preserve unrelated dirty files and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Market microstructure evidence
CURRENT_TASK=Validate the uncalibrated market-behavior archetype path from feature calculation through read API and Token Detail
LAST_COMPLETED_STEP=Added a rule-based multi-label classifier to existing EarlyFeatureEngine metrics, flattened its bounded labels/confidence into early-radar flow windows, and added the Token Detail advisory label. A first API contract test exposed the read payload depth bound; the projection was flattened without widening the global payload limit.
NEXT_STEP=Run the focused Python unit/runtime/API projection suite, touched-file Ruff, `make typecheck`, and the Token Detail Vitest; then record results and continue to price efficiency/sell response
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved)
TEST_STATUS=Classifier direct and early-runtime tests passed before the projection flattening; Token Detail Vitest passed 8/8 after flattening. Python API projection and full typechecks are pending.
BLOCKERS=No real-market calibration or live cohort. Preserve protected .env.example and unrelated dirty files. Existing browser/provider/dependency blockers remain as recorded above.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant and market-response evidence
CURRENT_TASK=Extend existing EarlyFeatureEngine with event-time ParticipantExpansionScore inputs and price-efficiency/sell-absorption measurements
LAST_COMPLETED_STEP=Added separate `market-archetype-rules-v1` output to existing early-feature JSON. Runtime/read API expose bounded flattened labels and per-rule evidence coverage; Token Detail labels the patterns uncalibrated/advisory. The nested payload test exposed and preserved the global read depth bound by flattening the projection. Focused Python suite 35 passed/2 existing warnings; Token Detail Vitest 8 passed; Ruff, mypy 176 source files, web lint/typecheck and diff-check passed.
NEXT_STEP=Inspect existing window metrics/trade events and `FlowAnalysis` to find canonical inputs for participant expansion, price response to sell flow, and price-per-flow measures; add tests before changing calculation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved)
TEST_STATUS=Exact archetype slice evidence: docs/reports/agentic-loop/2026-10-07-market-behavior-archetypes.md. No migration. PostgreSQL restart/replay of this new JSON metric not rerun; real market calibration and browser acceptance not obtained.
BLOCKERS=Archetype slice remains PARTIAL: identity-bound social acceleration is not wired to EarlyFeatureEngine; scores are uncalibrated; no real cohort/failed twins. Existing external/provider, browser, dependency, security-scanner, and elapsed-data blockers remain.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant and market-response evidence
CURRENT_TASK=Reconcile the current Early Alpha gap matrix and continue with the next repository-owned identity/clone-binding gap
LAST_COMPLETED_STEP=Current slice passed `.venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_flow_analysis.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py` (50 passed), Token Detail Vitest (8 passed), touched Ruff, `make typecheck` (176 files), web lint/typecheck and diff-check. Added participant expansion and price-efficiency values to existing snapshot/API/UI path; sell-absorption score remains null without event-level price response. `docs/reports/agentic-loop/2026-10-07-participant-price-response.md` records scope and limits.
NEXT_STEP=Inspect existing canonical token/social/creator identity owners and tests; implement only missing evidence-bound clone/social identity confidence in the canonical owner
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit)
TEST_STATUS=Focused Python 50 passed/2 existing warnings; Token Detail 8 passed; Ruff PASS; mypy 176 files PASS; npm lint/typecheck PASS; git diff --check PASS. Full `make verify`, full web suite, current-delta PostgreSQL restart, production browser acceptance and live provider acceptance remain pending.
BLOCKERS=Participant and price-efficiency scores are uncalibrated and require real data; independent buyer evidence is not complete participant coverage. Sell absorption is explicitly UNKNOWN absent event-level market response. Preserve `.env.example` and all unrelated dirty worktree changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha continuation
CURRENT_TASK=Continue with the next repository-owned identity/clone-binding gap using persisted social sources, exact mint calls, and canonical chain+mint identity
LAST_COMPLETED_STEP=Added paired explicit-USD liquidity/market-cap ratio, versioned liquidity class and ratio-only valuation risk to the existing EarlyFeatureEngine; UNKNOWN retained for absent, unpaired, invalid or stale evidence. Extended existing early snapshot/read/API/Token Detail paths. Focused Python 40 passed/2 warnings; Token Detail Vitest 8 passed; touched Ruff, make typecheck (176 files), web lint/typecheck and diff-check passed. Ledger: docs/reports/agentic-loop/2026-10-07-liquidity-valuation-quality.md.
NEXT_STEP=Inspect canonical token/social/creator identity projections and persistence, then add the smallest claim-vs-verified binding evidence path without treating PROJECT tags or ticker-only references as proof
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; worktree dirty and preserved; Git metadata read-only)
TEST_STATUS=Liquidity slice tests pass: `.venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py` = 40 passed, 2 existing warnings; Token Detail Vitest = 8 passed; touched Ruff PASS; `make typecheck` PASS (176); `npm run lint` PASS; `npm run typecheck` PASS with host stream-fd warnings; `git diff --check` PASS. No migration, full make verify/web suites or current-delta PostgreSQL restart run.
BLOCKERS=Keep `.env.example` and all unrelated dirty changes untouched. Liquidity thresholds are uncalibrated and the ratio is not executable depth. PostgreSQL restart/replay of the new JSON fields, production browser acceptance, real market calibration, and full suites remain open. Social ownership cannot be verified from exact-mint posts or operator source-type labels alone.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Rerun the focused persistence-to-runtime-to-API and Token Detail gates after wiring bounded social-call query evidence into EarlyFeatureEngine
LAST_COMPLETED_STEP=Added exact chain+mint social-reference aggregation with event-time filtering, revision dedupe and explicit UNVERIFIED ownership; wired the existing social-call repository query through worker/runtime, read projection and Token Detail. Initial integrated tests found two DexScreener test UOWs without the new repository fixture; those fixtures were corrected. Token Detail test passed 8/8.
NEXT_STEP=Run `.venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py tests/unit/test_alpha_caller_persistence.py tests/unit/test_worker_entrypoint.py --show-capture=no --tb=short`, then touched Ruff, `make typecheck`, web lint/typecheck, and diff-check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Focused feature/repository/runtime subtests passed before worker wiring; Token Detail Vitest passed 8/8. Full worker-linked Python rerun and static checks are pending. No PostgreSQL runtime integration for this new bounded query has been run.
BLOCKERS=Exact mint references do not prove project ownership; social account/claim binding remains unverified. Preserve `.env.example` and all pre-existing dirty changes. Live source acceptance, historical calibration and elapsed-data gates remain open.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Rerun the exact-mint false-confidence regression and final affected projection checks, then continue with advisory token identity similarity audit
LAST_COMPLETED_STEP=Focused recovery suite passed 77 tests/2 warnings; Token Detail passed 8/8; touched Ruff passed; make typecheck passed for 176 files; web lint/typecheck passed. A test-first regression caught and removed the false social_identity_confidence=1 assignment for exact-mint posts while account ownership was UNVERIFIED. Current audit and evidence ledger updated; a read-projection fixture was corrected to NULL confidence.
NEXT_STEP=Run .venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_early_read_projection.py tests/unit/test_market_archetypes.py tests/unit/test_early_runtime.py --show-capture=no --tb=short, then touched Ruff and git diff --check; inspect canonical token metadata before deciding if a minimal advisory clone projection is safe
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=77-test recovery suite passed after production confidence fix; 8 Token Detail tests passed. API fixture update and direct classifier regression are pending final rerun. No PostgreSQL or browser E2E for this slice.
BLOCKERS=No authoritative social-account ownership verification source is configured. Exact token references remain claims only. Keep .env.example and unrelated pre-existing changes untouched.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence binding
CURRENT_TASK=Audit the next P0/P1: current bundle exposure and pre-graduation trajectory; do not score unverified data
LAST_COMPLETED_STEP=Final social reference regression/projection subset passed 49 tests with 2 existing warnings in 9.20s. The 77-test worker/runtime/repository set passed with 2 warnings; Token Detail Vitest 8/8; touched Ruff PASS; make typecheck PASS (176 files); npm lint/typecheck PASS; git diff --check PASS. `social_identity_confidence` now remains null for exact-mint references; archetype social rule remains unknown absent verified binding. Evidence: docs/reports/agentic-loop/2026-10-07-social-exact-mint-evidence.md; current-state audit reconciled.
NEXT_STEP=Inspect canonical LaunchFootprintAnalyzer, bonding-curve progress observations and existing projections; identify which current bundle/curve fields can be surfaced without inferring complete holdings or protocol certification
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; worktree dirty preserved; no commit)
TEST_STATUS=Social slice source/unit/UI-component/static checks pass. Exact-current PostgreSQL restart/replay and browser E2E not run. No live source verification or alpha calibration.
BLOCKERS=Official account-to-token ownership data is absent. Current bundle completeness depends on external/chain holder evidence; don't convert partial observations into total current exposure. Preserve .env.example and all pre-existing dirty changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence PostgreSQL acceptance
CURRENT_TASK=Exercise bounded social-call persistence, restart query and early-feature projection against the available isolated PostgreSQL test container
LAST_COMPLETED_STEP=The active social implementation and final 49-test focused suite pass. Docker is available; isolated `memeradar-dex-pg-20261007-fresh` reports PostgreSQL 16.15 and Alembic head `0018_stream_gap_provider_id`, and a separate legacy test container reports `0017_smart_wallet_candidates`. Added an opt-in integration test that round-trips a social call across UOWs, checks exact-mint exclusion and verifies ownership remains UNVERIFIED.
NEXT_STEP=Create a disposable local-only role in the existing dedicated fresh test container, run the new PostgreSQL integration test with MEMERADAR_TEST_DATABASE_URL, then drop the role and record evidence
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no Git writes)
TEST_STATUS=Unit/static/UI checks are recorded in `docs/reports/agentic-loop/2026-10-07-social-exact-mint-evidence.md`. PostgreSQL round-trip is pending.
BLOCKERS=Do not touch application or compose Postgres containers/volumes; use only the named dedicated `memeradar-dex-pg-20261007-fresh` database. Test credential is local-only and will be removed. Preserve `.env.example` and all unrelated changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-mint social evidence PostgreSQL acceptance
CURRENT_TASK=Record the precise host-boundary result and continue the next repository-owned lifecycle/bundle gap
LAST_COMPLETED_STEP=The opt-in PostgreSQL test was attempted against the dedicated fresh test container after confirming its Alembic head was 0018_stream_gap_provider_id. The host Python process failed before connecting with PermissionError [Errno 1] Operation not permitted on localhost TCP; no database assertions ran. The disposable test role was dropped. This is not a product PASS or test assertion failure.
NEXT_STEP=Trace LaunchFootprintSnapshot and canonical launch_lifecycle through current worker/read projections; determine if any existing current-bundle or bonding progress data can be exposed without claiming completeness or increasing alpha score
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Social unit/runtime/projection suite PASS (49 tests, 2 existing warnings); worker/repository suite PASS (77 tests, 2 existing warnings); Token Detail Vitest PASS (8); Ruff, make typecheck (176 sources), npm lint/typecheck, and diff-check PASS. Exact-delta PostgreSQL round-trip BLOCKED before connect by host TCP EPERM. Full make verify, full frontend suite/build/E2E, and complete migration acceptance remain open.
BLOCKERS=Localhost TCP to the isolated PostgreSQL container is denied to the host test process; no social persistence/restart PASS is claimed. Social account ownership is unverified. Current bundle remaining-supply completeness and sourced winner/failure cohorts are unavailable. Preserve .env.example and all pre-existing dirty changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Validate the bounded token metadata-match read path from persistence mappers through the API contract
LAST_COMPLETED_STEP=Test-first route regression failed as expected because TokenSimilarityEvidenceView did not exist. Added a bounded application read model and persistence projection design: exact same-chain name/ticker/metadata-URI/creator matches; distinct canonical mints; equivalence remains NOT_ESTABLISHED; no score or provider claim.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py --show-capture=no --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=The new route regression is RED before implementation. The exact-delta persistence/API implementation and tests are pending focused validation. No schema migration or provider adapter change.
BLOCKERS=PostgreSQL execution over localhost TCP is host-blocked with EPERM. Similarity is evidence of shared labels/URI/creator only; it cannot be called a clone score or token equivalence. Preserve .env.example and unrelated changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Repeat persistence mapper and API route tests after correcting a test assertion inserted outside its original test
LAST_COMPLETED_STEP=First implementation test run: 24 passed, 1 failed in 18.43s. Failure was a misplaced pre-existing conflict assertion inside the newly added test (NameError), not the similarity projection. Restored the assertions to their original service-conflict test.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py --show-capture=no --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Similarity regression test still pending clean rerun. No PostgreSQL query test run due localhost TCP EPERM.
BLOCKERS=Identity matches remain hints only; no clone score or equivalence derived. Preserve .env.example and unrelated changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Validate strict web parsing and Token Detail rendering for bounded similarity evidence
LAST_COMPLETED_STEP=Persistence mapper and API route tests passed (25 passed, 4 existing deprecation warnings in 16.77s). Added a PostgreSQL integration assertion to the existing read-query test for same-chain ticker/metadata-URI/creator matches, distinct mints, and NOT_ESTABLISHED; PostgreSQL execution remains blocked before TCP connect by host EPERM.
NEXT_STEP=cd apps/web && npm test -- --run src/app/lib/read-api.test.ts src/app/components/token-detail.test.tsx
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Backend unit/API serialization PASS. PostgreSQL query integration is written but not executed. Frontend parser/component regressions are pending.
BLOCKERS=No clone risk is computed; current evidence is limited to exact catalog name/ticker/metadata URI/creator matches and explicitly does not prove identity. Preserve .env.example and existing dirty changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Run touched Python lint/type and frontend lint/type checks
LAST_COMPLETED_STEP=Frontend parser and Token Detail component suites passed: 46 tests across 2 files. Backend route/persistence unit suite passed 25 tests. PostgreSQL query test was added but host TCP EPERM prevents execution.
NEXT_STEP=Run `.venv/bin/ruff check packages/application/src/memeradar_application/read_api.py packages/persistence/src/memeradar_persistence/read_queries.py apps/api/src/memeradar_api/read.py tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py tests/integration/test_read_query_service.py`, then `make typecheck`, `cd apps/web && npm run lint && npm run typecheck`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Python focused and frontend unit/component PASS. Static analysis pending. No migration or external provider code change.
BLOCKERS=PostgreSQL query round-trip not executed due host TCP EPERM. Clone/ownership equivalence remains UNKNOWN. Preserve protected `.env.example` and existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Repeat mypy and frontend lint/type checks after fixing typed match-list conversion and formatting findings
LAST_COMPLETED_STEP=Initial static checks exposed three formatting/import issues and one mypy tuple-vs-list contract mismatch. Fixed only those issues; touched-file Ruff now passes. The first frontend lint/type jobs did not return exit codes before the tool window ended, so they are rerun for exact evidence.
NEXT_STEP=Run `make typecheck`, `cd apps/web && npm run lint`, and `cd apps/web && npm run typecheck`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Backend 25-test suite and frontend 46-test suite pass. Touched Ruff PASS. Full mypy/web lint/type pending rerun after repair.
BLOCKERS=PostgreSQL query test blocked before connect by host TCP EPERM. Clone equivalence remains unestablished. Preserve .env.example and prior dirty edits.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical token similarity evidence projection
CURRENT_TASK=Rerun backend API/persistence tests after final typed serialization correction and record the slice evidence
LAST_COMPLETED_STEP=Backend unit/API tests passed 25/25 before the final tuple-to-list serialization typing adjustment. Frontend parser/Token Detail passed 46/46. Touched Ruff PASS; make typecheck PASS (176 source files); npm lint PASS; npm typecheck PASS with host stream-fd warnings and exit 0.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py --show-capture=no --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Static checks pass; backend final rerun pending. PostgreSQL integration assertion added but not run (host TCP EPERM). No migration.
BLOCKERS=Exact-current database execution remains host-blocked; no clone score/ownership inference. Protected `.env.example` and unrelated existing dirty files remain untouched.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Bundle exposure and pre-graduation evidence audit
CURRENT_TASK=Validate the bundle-cohort observation fields through the existing SignalHardening model and type/lint contracts
LAST_COMPLETED_STEP=Test-first launch-footprint regressions failed because bundle wallet/coverage/observed-holding fields were absent. Added bounded metrics to the existing LaunchFootprintSnapshot owner: explicit bundle-member count, observed balance count, membership coverage, balance coverage, and observed holdings sum. Partial holdings remain explicitly a lower-coverage observed cohort; contradictory ID/boolean labels yield unknown membership rather than a count. The metrics do not feed score or execution gates.
NEXT_STEP=Run Ruff on signal_hardening.py and its unit test, run make typecheck, then rerun the complete signal-hardening tests including serialization assertions
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit; Git metadata read-only)
TEST_STATUS=Red: two focused tests failed as expected on missing bundle metrics; after implementation 28 unit/contract tests passed before adding mapping assertions. Ruff/typecheck pending. No DB or UI integration claimed.
BLOCKERS=Analyzer consumes only supplied canonicalized observation payloads; production worker has no fully verified complete bundle-holder feed. These fields are advisory in the existing replay/feature-hardening path only. Preserve .env.example and all pre-existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pre-graduation trajectory evidence audit
CURRENT_TASK=Audit bonding-curve progress provenance and downstream consumers before exposing any trajectory metric
LAST_COMPLETED_STEP=Bundle analysis now reports bundle_wallet_count, bundle_balance_observed_wallet_count, bundle_membership_coverage, bundle_balance_coverage, and bundle_observed_still_held_pct from the existing LaunchFootprintSnapshot owner. Partial holdings are never labeled as total exposure; membership conflicts suppress the count. TDD regression was observed red on missing fields and on contradictory ID/boolean labels, then the full focused signal-hardening unit/contract suite passed 28 tests; Ruff and make typecheck passed (176 sources). No scoring, schema, worker, API, or provider change.
NEXT_STEP=Trace verified protocol identity markers from canonical decoder into EarlyFeatureEngine progress inputs and inspect whether bonding_curve_velocity has any consumer; test an unknown provider event remains UNKNOWN before adding any read surface
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit; Git metadata read-only)
TEST_STATUS=Bundle focused unit/contract 28 passed; touched Ruff PASS; make typecheck PASS 176 sources. PostgreSQL/browser acceptance not applicable to the isolated analyzer and not run. Bundle data from production worker remains unavailable/unverified.
BLOCKERS=No complete production bundle-holder source or worker wiring exists, so the metrics are advisory/replay evidence only. Do not infer bundle completeness, promote score, or call observed holdings total current exposure. Preserve .env.example and all pre-existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pre-graduation trajectory provenance hardening
CURRENT_TASK=Run the EarlyFeatureEngine regression suite after gating bonding/migration evidence on canonical protocol identity
LAST_COMPLETED_STEP=Test-first regressions exposed that unverified market snapshots could mark liquidity as migration liquidity and that arbitrary bonding progress generated velocity. EarlyFeatureEngine now accepts progress only when protocol_identity_verified=true and protocol_event_type=bonding_curve_progress, calculates velocity against only the matching progress observations, and accepts migration state only from verified graduation/migration protocol events. Targeted suite passed 3 tests including verified migration, unverified migration rejection, unverified progress rejection, and interleaved-time velocity.
NEXT_STEP=Run all tests/unit/test_early_features.py, tests/unit/test_early_runtime.py, tests/unit/test_early_read_projection.py, then Ruff and make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit; Git metadata read-only)
TEST_STATUS=New focused tests passed 3; full early-engine dependent suite pending. No provider adapter, schema, score policy, or execution authorization changed.
BLOCKERS=Verified protocol registry coverage remains incomplete; unsupported/unverified protocol identities produce UNKNOWN curve/migration evidence. This change does not implement Pump.fun pre-graduation ingestion or launch momentum scoring. Preserve .env.example and all pre-existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical launch lifecycle provenance hardening
CURRENT_TASK=Run lifecycle unit contracts after making bonding/graduation evidence require verified protocol identity
LAST_COMPLETED_STEP=EarlyFeatureEngine focused suite passed 57 tests with 2 existing deprecation warnings across features, runtime, read projection, and lifecycle. Ruff and mypy passed (176 files). Test-first lifecycle projection regression now reproduced that an unverified bonding progress payload created BONDING state and a route. GraduationAwareRouteAnalyzer now gates lifecycle/curve projection on verified protocol identity or strong RPC reconciliation; unverified progress is excluded, and graduation timestamps require verified evidence.
NEXT_STEP=Run tests/unit/test_launch_lifecycle.py and tests/unit/test_read_persistence.py; adjust canonical fixtures explicitly where they currently omit verified identity, without converting external-provider fixtures into trusted ones
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit; Git metadata read-only)
TEST_STATUS=EarlyFeatureEngine: 57 passed/2 warnings, Ruff PASS, typecheck PASS 176 sources. Lifecycle new regression was red before code; lifecycle suite after change pending.
BLOCKERS=Only verified registry/RPC evidence can supply curve/migration progress; unverified protocol identity remains UNKNOWN. This does not yet provide a full pre-graduation trajectory or scoring/runtime completeness. Preserve .env.example and pre-existing edits.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical launch lifecycle provenance hardening
CURRENT_TASK=Run callers of the shared lifecycle analyzer and static contracts after requiring verified evidence
LAST_COMPLETED_STEP=Lifecycle regressions initially exposed eight fixture events that had implicitly treated arbitrary protocol-shaped payloads as canonical. Canonical fixtures now set protocol_identity_verified explicitly; weak-provider fixtures remain untrusted. A verified route event can still establish a DEX route independently of lifecycle claims. `tests/unit/test_launch_lifecycle.py tests/unit/test_read_persistence.py` now pass 20/20; the new unverified bonding-progress regression was red before the change.
NEXT_STEP=Run lifecycle consumers (`tests/unit/test_gmgn_shadow_isolation.py`, `tests/unit/test_read_api_routes.py`), then touched Ruff and `make typecheck`; afterward update the current-state audit and create slice ledger
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; dirty worktree preserved; no commit; Git metadata read-only)
TEST_STATUS=Lifecycle + persistence mapper suite PASS 20/20. Early feature/runtime/read suite PASS 57/57 with 2 existing deprecation warnings. Ruff and mypy passed before latest lifecycle edit; rerun pending.
BLOCKERS=Unverified launch lifecycle remains UNKNOWN; protocol registry identities are incomplete and no live Pump.fun graduation trajectory/OOS evidence exists. Preserve .env.example and all pre-existing changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Bundle and launch lifecycle evidence checkpoint
CURRENT_TASK=Inspect existing false-positive/outcome owners for a same-age matched-control path and isolate code gaps from missing real labels
LAST_COMPLETED_STEP=Extended the existing LaunchFootprintSnapshot with explicitly observed bundle-cohort counts/coverage and still-held subtotal; incomplete or conflicting membership is not promoted to total exposure. Gated EarlyFeatureEngine progress/migration and GraduationAwareRouteAnalyzer lifecycle projection on verified protocol identity or strong RPC reconciliation. Verified tests: signal hardening 28; early feature/runtime/read/lifecycle 57 with 2 existing warnings; lifecycle/read persistence 20; GMGN/read API consumers 42 with 4 existing warnings. Touched Ruff PASS after correcting a source-path typo; make typecheck PASS (176 sources). Current-state audit and slice ledger updated.
NEXT_STEP=Inspect packages/application/src/memeradar_application/early_failure_analysis.py, its unit tests, and forward-outcome model/query paths; determine whether same-age controls can be generated locally without inventing labels
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused bundle, lifecycle, early-feature, persistence-mapper, GMGN and read-API suites pass as recorded in docs/reports/agentic-loop/2026-10-07-bundle-and-lifecycle-provenance.md. make typecheck PASS, 176 sources. Documentation diff check pending. No exact-current PostgreSQL, live provider, production browser or OOS result claimed.
BLOCKERS=No complete verified current-holder bundle feed; no full pre-graduation momentum/score/post-migration window pipeline. Real matched-failure case data and temporal OOS maturity remain unavailable. Preserve the pre-existing .env.example change and all unclassified dirty work.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Expose existing event-derived seller and raw unique-trader metrics through the shared early-radar projection and Token Detail, with explicit buyer-only score scope
LAST_COMPLETED_STEP=Audited EarlyFeatureEngine, EarlyRuntimeService, early-radar flow_windows and Token Detail. Raw unique_sellers/new_sellers_per_minute and seller_growth_rate are already calculated from event-derived trades, but the runtime projection omits them and participant_expansion describes a buyer-only score as participant expansion. No seller-side independent cluster metric is currently produced.
NEXT_STEP=Add failing unit/read-projection/component assertions for raw seller/trader metrics, seller cluster coverage, UNKNOWN on incomplete seller clustering, and explicit BUY_SIDE_ONLY score scope before implementation
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Audit only for this slice; no code tests run. Prior bundle/lifecycle focused evidence is recorded in docs/reports/agentic-loop/2026-10-07-bundle-and-lifecycle-provenance.md.
BLOCKERS=No repository event feed can prove unobserved transactions; these metrics must remain raw-observed or UNKNOWN. Do not promote a participant score or change risk/execution policy. Exact-current PostgreSQL/browser/OOS gaps remain.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Implement the raw seller/trader projection and fail-closed cluster coverage exposed by the new regressions
LAST_COMPLETED_STEP=Added two regression tests. Red is reproduced: seller/trader projection fields are absent, and a buy observation without wallet identity leaves buyer cluster coverage incorrectly at 1.0 instead of 0.5.
NEXT_STEP=Extend EarlyFeatureEngine with observed unique-trader and seller cluster metrics; include all side observations in cluster-coverage denominators and mark the existing score scope BUY_SIDE_ONLY; then wire through EarlyRuntimeService and Token Detail
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=New test selection: 1 passed, 2 failed as expected on missing metrics and optimistic cluster coverage. No implementation or typecheck run yet.
BLOCKERS=Metrics rely on the completeness of the event source; unobserved trades remain unknowable. Keep raw observed participant counts distinct from cluster-adjusted counts, and preserve UNKNOWN when identity/cluster evidence is incomplete.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Run focused feature, runtime, read API and Token Detail tests for seller/unique-trader evidence and buyer-only score labeling
LAST_COMPLETED_STEP=New feature tests first failed on absent raw unique-trader fields and overestimated buyer cluster coverage when a trade lacked wallet identity. EarlyFeatureEngine now counts cluster coverage against all side trades, derives observed unique-trader velocity, independently clustered seller/trader counts only with complete consistent labels, and marks the score scope BUY_SIDE_ONLY. EarlyRuntimeService projects the bounded metrics, and Token Detail displays them as advisory data.
NEXT_STEP=Run tests/unit/test_early_features.py, tests/unit/test_early_runtime.py, tests/unit/test_early_read_projection.py, then Token Detail Vitest
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Feature-level tests passed after implementation (3/3 selected). Runtime and component tests were observed red before projection/UI wiring; focused end-to-end unit/component validation is pending.
BLOCKERS=Observed participant counts depend on event-source coverage. Cluster-independent seller/trader counts remain UNKNOWN when any side lacks complete wallet+cluster evidence or a wallet has conflicting cluster assignments. No scoring threshold, risk disposition, or execution authority changes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Rerun the focused feature/runtime/read/component selection after aligning fixtures to canonical sell-side wallet fields
LAST_COMPLETED_STEP=The feature-level changes pass. The first wider run found the runtime test fixture supplied a sell using buyer_wallet, while production correctly reads seller_wallet for sell events; the fixture now supplies seller_wallet. A UI assertion also assumed adjacent text before the unique-trader value; assertions now check each rendered substring independently.
NEXT_STEP=Run tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py and Token Detail Vitest
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=First broad selection: Python 48 passed/1 failed on invalid fixture identity shape; web 8 passed/1 failed on brittle assertion adjacency. Fixture and assertion corrected; rerun pending.
BLOCKERS=No product failure established by the first broad run. Preserve UNKNOWN when sell-side identity/cluster evidence is absent.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Rerun focused participant tests using production-eligible runtime events
LAST_COMPLETED_STEP=The first corrected runtime fixture still produced UNKNOWN because the production evidence policy excludes unclassified observations ingested after 2026-09-15. This confirms fail-closed behavior; the focused runtime fixture now explicitly labels only its two test events collection_mode=PRODUCTION. Token Detail component tests pass 9/9.
NEXT_STEP=Run the backend early feature/runtime/read-projection selection and Token Detail Vitest again; then run Ruff and make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Feature/read/API tests: 48 passed, one runtime projection test failed because its evidence was intentionally ineligible; production-mode fixture added. Token Detail: 9 passed. No production code failure remains established; rerun pending.
BLOCKERS=Do not bypass the production evidence policy to make test metrics appear. Runtime test signals must carry explicit PRODUCTION collection mode; unknown and fixture evidence remain excluded.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Remove a repeating-decimal artifact from per-minute rates and rerun focused validation
LAST_COMPLETED_STEP=With explicit PRODUCTION events, the runtime reached and projected the seller count. The remaining assertion exposed the existing count/(seconds/60) arithmetic returning 5.999999999999999999999999999 for exactly one event in ten seconds. Token Detail remains 9/9 passing.
NEXT_STEP=Compute buyer/seller/trader per-minute rates as count*60/elapsed_seconds and rerun focused backend/UI tests
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Backend selection: 48 passed, 1 failed only due repeating-decimal expected value; component tests 9 passed. Arithmetic correction and final focused rerun pending.
BLOCKERS=No external blocker. Keep rates time-normalized and avoid rounding the raw decimal evidence in the application layer.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Run final focused tests after preserving the original runtime test body and correcting exact per-minute arithmetic
LAST_COMPLETED_STEP=Per-minute buyer, seller and observed-trader rates now use count*60/elapsed_seconds, avoiding the repeating intermediate division by seconds/60. Review found the new runtime test had been inserted before the original test's final assertions; those original assertions are restored to their original test, and the new projection test is isolated.
NEXT_STEP=Run tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py, Token Detail Vitest, and touched Ruff
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Previous backend run failed on test placement after seller-rate count; component tests 9/9 pass. No feature implementation failure is known; focused rerun pending.
BLOCKERS=No external blocker. Continue fail-closed production evidence filtering and UNKNOWN cluster semantics.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity
CURRENT_TASK=Run repository type, web lint/type and diff gates for the completed projection slice
LAST_COMPLETED_STEP=Extended EarlyFeatureEngine with seller/trader measures and strict cluster coverage, projected metrics through EarlyRuntimeService.flow_windows, and rendered them in existing Token Detail with BUY_SIDE_ONLY score scope. Backend focused selection passed 49 tests with 2 existing deprecation warnings; Token Detail passed 9 tests; touched Python Ruff passed. Updated the current-state audit and added docs/reports/agentic-loop/2026-10-07-participant-expansion-parity.md.
NEXT_STEP=Run make typecheck; run apps/web npm run lint and npm run typecheck; then run git diff --check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused backend 49 passed/2 warnings; Token Detail 9 passed; touched Python Ruff PASS. Typecheck, web lint/typecheck and post-doc diff check pending. One incorrect Ruff-on-TSX invocation is not a product failure and is not counted as web lint.
BLOCKERS=No exact-current PostgreSQL persistence/replay, production browser, live provider or temporal OOS acceptance. Preserve protected pre-existing .env.example change and all other dirty work.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion projection parity complete
CURRENT_TASK=Recompute P0/P1 gaps; audit the existing same-age failure-analysis and replay owners for locally executable matched-control capability
LAST_COMPLETED_STEP=Focused backend tests passed 49/49 with 2 existing deprecation warnings; Token Detail passed 9/9; touched Python Ruff passed; make typecheck passed with 176 files; web lint passed; web typecheck exited 0 with the host stream-fd warning; git diff --check passed. Audit matrix and slice ledger record the evidence. Score remains BUY_SIDE_ONLY and uncalibrated; independent seller/trader counts remain UNKNOWN with incomplete/conflicting clusters.
NEXT_STEP=Inspect existing research/replay command paths and early_failure_analysis outcome consumers to determine whether matched same-age controls can be generated from current persisted/fixture data without synthetic success claims
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Participant expansion slice focused validation PASS; exact-current PostgreSQL JSON restart, production browser and live-cohort validation remain open. A final full make verify has not yet run after all current slices.
BLOCKERS=Real case studies and mature real failure/winner labels are absent; any fixture-based output must be marked synthetic and cannot satisfy matched-real-twin or OOS acceptance. No exact-current DB/browser/live provider acceptance claimed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Same-age failure-control matching complete
CURRENT_TASK=Recompute the P0/P1 matrix and continue with the next locally actionable evidence gap; independently validate report-to-worker integration before broad repository gates
LAST_COMPLETED_STEP=Reused pumpfun_forward_report matched-control owner; replaced discovery-age cohort equality with prior-or-same-age alpha/control snapshot matching, same chain/venue/launch date, positive liquidity/market cap within 2x, fresh matured executable/observed outcomes, explicit negative labels, candidate-vs-sample-status separation and NOT_ESTABLISHED research acceptance. Added a RED→GREEN report regression. Full report unit suite 8 passed; Ruff PASS; make typecheck PASS (176 sources); git diff --check PASS. Current audit and slice ledger updated.
NEXT_STEP=Run worker forward-evidence and failure-analysis consumer tests, then inspect remaining independent repository-owned participant, wallet/bundle, graduation and identity gaps for missing canonical projection/persistence paths
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused same-age matcher validation PASS: 8 report tests, touched Ruff, 176-source mypy, and diff check. No exact-current PostgreSQL, browser, real cohort or OOS acceptance.
BLOCKERS=Actual same-age failures/rugs are not present: fixture validation is synthetic-redacted with 0 matured outcomes and 0 negative controls. Report matcher does not close real twin/OOS gates. Continue inspecting local code gaps.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Same-age failure-control matching complete; continue repository P0/P1 audit
CURRENT_TASK=Inspect current market-response and identity evidence paths to identify another source-code gap that can be closed without requiring real cohort labels or provider evidence
LAST_COMPLETED_STEP=Same-age matcher report suite passed 8/8, touched Ruff PASS, make typecheck PASS (176 sources), git diff --check PASS. Forward-evidence worker plus failure-analysis consumer suites passed 7 with 1 existing skip. Updated the audit row and added a durable slice ledger.
NEXT_STEP=Trace the existing trade-to-market snapshot path for post-sell response evidence and confirm whether any deterministic sell-absorption calculation is safely possible from current timestamps/fields
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Same-age report and worker/analyzer focused tests PASS as recorded. No PostgreSQL, browser, real historical twins or temporal OOS acceptance.
BLOCKERS=Real matured negative controls absent; synthetic-redacted dataset has 0 matured outcomes and 0 negative controls. Inspect independent code-owned gaps next.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical observation-to-token matching
CURRENT_TASK=Add a failing early-feature regression for a same-token-id observation whose payload names a different mint; then centralize the shared identity check for existing consumer paths
LAST_COMPLETED_STEP=Audited same-age outcome consumers (7 passed, 1 skipped) and source paths. Found EarlyFeatureEngine accepts token_id matches without checking payload chain/address, while launch lifecycle and correlation already have separate matchers. Canonical TokenIdentity is chain+mint; payload disagreement must not contaminate early metrics.
NEXT_STEP=Add a TDD test proving a wrong-mint market trade with the same token_id is excluded when token_identity is supplied
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused report/worker tests PASS; no identity regression test run yet.
BLOCKERS=No current blocker; preserve token identity and observation payload provenance.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical observation-to-token matching
CURRENT_TASK=Run full repository typecheck after repairing persistence's stale private-matcher import
LAST_COMPLETED_STEP=Replaced persistence read projection's import/use of launch_lifecycle._token_matches with the shared canonical matcher; removed unused lifecycle import and sorted correlation imports. Focused early-feature/lifecycle/correlation/read-query tests PASS 53, 1 skipped (PostgreSQL integration unavailable/not configured). Touched Ruff PASS.
NEXT_STEP=Run make typecheck, then git diff --check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused unit tests PASS 53; opt-in PostgreSQL integration test SKIPPED. Touched Ruff PASS. Repository typecheck and diff check pending.
BLOCKERS=PostgreSQL test skipped because MEMERADAR_TEST_DATABASE_URL is not configured; no database acceptance is implied.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical chain-aware token observation matching
CURRENT_TASK=Run complete identity-matching focused suites after using the domain chain-aware address canonicalizer
LAST_COMPLETED_STEP=Added a valid Solana base58 case-variant regression; it failed before the repair (trade_count 1). Replaced generic lowercase matching with the domain `require_chain_address`, preserving Solana case sensitivity and EVM/Sui canonicalization, and rejecting non-string address payloads.
NEXT_STEP=Run early-feature, lifecycle, correlation and persistence read-query tests; then touched Ruff, make typecheck and diff check
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Prior 53-test slice passed but was superseded by a newly identified case-folding defect. Regression observed RED; post-fix tests/static checks pending.
BLOCKERS=No known external blocker for the address normalization fix. Preserve existing dirty worktree and safety state.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Sell-response evidence audit
CURRENT_TASK=Trace canonical trade/pair/market snapshot fields and the existing early-radar projection to determine a fail-closed event-level sell-response implementation
LAST_COMPLETED_STEP=Explicit `OBSERVATION_TIME` and unknown provider event-quality values now fail closed to UNKNOWN; market snapshots remain available by observed_at measurement time without being represented as source event time. Affected event-time/early-feature/lifecycle/correlation/DexScreener suites passed 82 tests; touched Ruff, make typecheck (177 files), and git diff --check passed. The chain-aware identity slice was separately recorded.
NEXT_STEP=Inspect existing trade pool/quote identity and feature-to-API/UI wiring; add a RED regression for largest observed sell with same-pool pre/post market snapshots if the normalized source fields support it
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Event-time and affected consumer suites PASS 82/82; touched Ruff PASS; make typecheck PASS 177 sources; git diff --check PASS.
BLOCKERS=PostgreSQL read-query/restart test skipped because `MEMERADAR_TEST_DATABASE_URL` is unset. No live/browser/statistical evidence claimed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Verified Pump.fun pre-graduation and migration trajectory
CURRENT_TASK=Reconcile the current-state matrix and identify the next independently actionable P0/P1 gap
LAST_COMPLETED_STEP=Verified Pump.fun trajectory slice passed focused EarlyFeatureEngine/EarlyRuntime/read-projection/lifecycle selection 72/72 (2 existing deprecation warnings); Token Detail Vitest 9/9; touched Ruff PASS; mypy PASS 177 files; web lint/typecheck PASS; git diff --check PASS. No schema/scorer/entry-policy change.
NEXT_STEP=Audit canonical holder data and current bundle exposure coverage to determine whether whole-supply exposure can be computed from existing verified observations or is genuinely data-blocked
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Graduation/migration/read-projection/lifecycle Python PASS 72/72 (2 deprecation warnings); Token Detail Vitest PASS 9/9; touched Ruff PASS; mypy PASS 177; web lint/typecheck PASS; diff check PASS. PostgreSQL/browser/provider/OOS acceptance not run.
BLOCKERS=.codex is read-only in this environment. PostgreSQL test URL is unset; browser listener/provider DNS remain host-blocked. Preserve all inherited work. Real historical response cohort and matched negative controls are unavailable.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Canonical Pump.fun trade normalization and state-time handling
CURRENT_TASK=Make verified Pump.fun buy/sell events expose canonical side and wallet fields to the shared feature/hardening owners; preserve observed_at only as a current-state measurement clock
LAST_COMPLETED_STEP=Official Solana `getTokenAccountsByOwner`/`getTokenSupply` docs were fetched and recorded. Audit found that the verified Pump.fun raw decoder emits `user` and instruction name but not normalized `side`/buyer/seller wallet fields; canonical `chain.event` was also missing from SignalHardeningAnalyzer trade kinds. A RED regression reproduced the missing side. Holder/wallet state snapshots without occurred_at are now ordered by observed_at only for current-state evidence.
NEXT_STEP=Implement the explicitly documented standard Solana RPC owner/mint balance read behind a provider contract, then wire it only to a bounded, point-in-time known-wallet refresh path; do not infer bundle membership
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused combined Python suites PASS 105/105 (`test_solana_raw_stream`, `test_signal_hardening`, `test_early_features`, `test_early_runtime`, `test_read_persistence`); decoder red regression was observed before fix. Touched Ruff PASS; `make typecheck` PASS, 177 source files; `git diff --check` PASS.
BLOCKERS=PostgreSQL test URL is unset and localhost TCP is host-blocked; browser listener and DexScreener DNS are host-blocked. RPC reads can measure requested owner/mint balances but cannot establish bundle membership, complete bundle coverage or same-slot total supply without additional evidence. Preserve all inherited dirty work including protected `.env.example`.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Verified Pump.fun executed trade evidence complete
CURRENT_TASK=Recompute the P0/P1 gap matrix and inspect the next repository-owned blocker: current bundle exposure, holder coverage, and early trajectory owners
LAST_COMPLETED_STEP=Decoded the complete pinned official TradeEvent from bounded Program data logs only within Pump invocation; attached raw quantities to exactly one matching verified instruction by mint/user/side; normalized WSOL lamports to SOL, retained custom quote values raw-only, and isolated chain vs market flow units. Full downstream selection passed 175 tests; touched Ruff PASS; make typecheck PASS 177 sources.
NEXT_STEP=Inspect holder graph and read-only Solana account-balance provider contracts for known bundle wallet refresh, point-in-time cutoffs, and whether coverage can ever support current total exposure; do not infer bundle membership
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited 232-path worktree preserved at start; 233 dirty paths now including one new run ledger; Git metadata read-only; no commit)
TEST_STATUS=RED→GREEN raw event quantity/ambiguity/truncation/source-scope tests; downstream raw-stream/IDL/registry/early feature/runtime/detection/worker/forward report/risk/persistence/lifecycle selection PASS 175; focused post-type contract decoder PASS 10; touched Ruff PASS; make typecheck PASS 177 source files. Post-documentation diff check pending.
BLOCKERS=No live Pump sample, exact-current PostgreSQL restart, browser runtime, or provider-network evidence. Custom quote decimals/USD remain UNKNOWN; truncated/ambiguous event logs remain UNKNOWN. Preserve all inherited work.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation progress evidence path
CURRENT_TASK=Parse the pinned CreateEvent reserve baseline from Pump program-scoped logs and associate it only with one matching verified launch instruction
LAST_COMPLETED_STEP=RED run reproduced 3 intended failures: two missing worker refresh helpers and one feature engine path rejecting occurred_at=None account measurements; unrelated selected cases passed 2.
NEXT_STEP=Implement bounded eligible-curve target selection, read isolation, and observation-time ordering for only verified current BondingCurve snapshots
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty worktree preserved; Git metadata read-only; no commit)
TEST_STATUS=CreateEvent/raw-stream focused suite PASS 39/39; BondingCurve decoder/RPC selection PASS 6/6; worker/feature regression RED as expected (3 failures, 2 passes).
BLOCKERS=PostgreSQL URL unset/host TCP unavailable; browser listener and provider DNS blocked; no complete bundle membership/whole-supply evidence. Preserve inherited dirty work including protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation progress evidence path
CURRENT_TASK=Repeat the repository typecheck after raw-stream match-key local naming repair
LAST_COMPLETED_STEP=Renamed trade, launch, CreateEvent, and TradeEvent match locals to avoid incompatible inferred types; raw-stream and Pump IDL tests pass 43/43 after this type-only repair.
NEXT_STEP=make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (branch main; inherited dirty tree; Git metadata read-only; no commit)
TEST_STATUS=Focused canonical Pump.fun path PASS 161/161; raw-stream/IDL tests PASS 43/43; selector/RPC deterministic replay and mismatch selection PASS 4/4; touched Ruff PASS. Previous make typecheck failed on 8 matcher-local inference errors; rerun pending.
BLOCKERS=Exact-current PostgreSQL URL unset/host TCP unavailable; browser listener and live provider DNS blocked. No complete bundle membership/whole-supply evidence. Preserve inherited dirty work including protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation progress evidence path
CURRENT_TASK=Probe exact-current PostgreSQL integration availability and run the reusable EarlyRuntime persistence test
LAST_COMPLETED_STEP=The Pump.fun raw decode/RPC/worker/current-feature path passed 161 focused tests; raw-stream/IDL selection passed 43; mismatch and deterministic RPC replay selection passed 4; touched Ruff passed; make typecheck passed 177 source files.
NEXT_STEP=Check whether MEMERADAR_TEST_DATABASE_URL is configured without printing its value; locate the documented disposable PostgreSQL integration path and run the EarlyRuntime persistence gate if available.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Unit/runtime and typecheck gates PASS as stated; PostgreSQL persistence/restart acceptance not yet run. Scoped diff check pending.
BLOCKERS=PostgreSQL runtime availability not yet re-probed; live RPC, production browser, and historical calibration remain blocked/unverified. No complete bundle membership/whole-supply evidence. .env.example remains untouched in this run.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation persistence acceptance
CURRENT_TASK=Start a dedicated disposable PostgreSQL 16 container on loopback with tmpfs storage, then migrate it to current head and run integration coverage
LAST_COMPLETED_STEP=MEMERADAR_TEST_DATABASE_URL is unset; Docker daemon is available and a local postgres:16-alpine image exists. The pre-existing compose PostgreSQL container is stopped and will not be reused or modified.
NEXT_STEP=docker run --rm --detach --name memeradar-pg-resume-20261007 -e POSTGRES_DB=memeradar_test -e POSTGRES_USER=memeradar_test -e POSTGRES_PASSWORD=memeradar_test_only -p 127.0.0.1:55439:5432 --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=256m postgres:16-alpine
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused unit and runtime suites PASS 161; raw-stream/IDL 43; deterministic/mismatch RPC-worker 4; Ruff PASS; mypy PASS 177 sources. EarlyRuntime PostgreSQL integration skipped 1 because test URL was unset.
BLOCKERS=No live RPC/provider/browser/real historical OOS acceptance. The PostgreSQL integration blocker is being re-probed with an isolated local container. Preserve all existing containers/volumes and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation persistence acceptance
CURRENT_TASK=Apply Alembic migrations to the disposable PostgreSQL 16 database
LAST_COMPLETED_STEP=Started isolated container memeradar-pg-resume-20261007 using postgres:16-alpine with tmpfs data and loopback-only port 55439; `pg_isready` reports accepting connections. Existing compose containers and volumes were not touched.
NEXT_STEP=MEMERADAR_DATABASE_URL='postgresql+asyncpg://memeradar_test:memeradar_test_only@127.0.0.1:55439/memeradar_test' .venv/bin/python -m alembic -c alembic.ini upgrade head
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused unit/runtime/typecheck checks pass as previously recorded. PostgreSQL container readiness PASS; migration and integration tests not yet run.
BLOCKERS=No live RPC/provider/browser/real historical OOS acceptance. PostgreSQL runtime is now available for local tests. Preserve existing containers/volumes and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation persistence acceptance
CURRENT_TASK=Move Alembic and PostgreSQL integration execution into a disposable Docker runner because the host process cannot open TCP sockets
LAST_COMPLETED_STEP=Disposable PostgreSQL reports healthy. Host-side Alembic `upgrade head` failed before any migration with `PermissionError [Errno 1] Operation not permitted` at socket creation to the local container; database remains untouched by migration. Docker can run a local container, so test the container-side runner path.
NEXT_STEP=docker run --rm --network host --entrypoint python compose-worker:latest -c 'import sys; print(sys.version)'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused Pump tests PASS 161; raw-stream/IDL 43; provider replay/mismatch 4; Ruff PASS; mypy PASS 177. Host-side DB connection attempt blocked at socket creation; no migration result.
BLOCKERS=Host Python network sockets are restricted. Dedicated Docker PostgreSQL is available and isolated; retry inside container network. No live RPC/provider/browser/real historical OOS acceptance. Preserve existing compose containers/volumes and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation persistence acceptance
CURRENT_TASK=Use the already-running worker container for disposable PostgreSQL validation because this session cannot create a new Docker runner
LAST_COMPLETED_STEP=Verified `docker ps` and read-only `docker exec`; the worker has Python 3.12.15, pytest 9.0.3 and asyncpg. `docker run` was rejected by the Docker API with permission denied. The dedicated PostgreSQL container is healthy on isolated bridge networking. Neither the host nor worker app services have been changed.
NEXT_STEP=Attach only `memeradar-pg-resume-20261007` to `compose_default` and probe disposable DB connectivity from `compose-worker-1`; if supported, copy current source into a temporary validation directory inside that container and run migration/integration checks there.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused Pump/runtime tests PASS 161; raw-stream/IDL 43; provider replay/mismatch 4; touched Ruff PASS; mypy PASS 177. Host Alembic attempt was blocked at socket creation before migration. No migration result yet.
BLOCKERS=Host Python sockets restricted; Docker API denies create-runner but allows inspect/exec. No live RPC/provider/browser/real historical OOS acceptance. Preserve existing compose containers/volumes and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun graduation persistence acceptance
CURRENT_TASK=Probe whether the existing worker can reach the isolated PostgreSQL container without changing container networking
LAST_COMPLETED_STEP=Docker API denied `docker network connect`, so no networking changed. The standalone `docker run` runner and new network attachment are unavailable under current Docker policy; existing containers remain intact.
NEXT_STEP=docker exec compose-worker-1 python -c '<bounded asyncpg connection attempt to disposable postgres container IP 172.17.0.2>'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Focused Pump/runtime tests PASS 161; raw-stream/IDL 43; provider replay/mismatch 4; touched Ruff PASS; mypy PASS 177. PostgreSQL migration/integration still unverified.
BLOCKERS=Host Python sockets restricted; Docker runner/network attachment denied. Testing only direct container-to-container route remains. No live RPC/provider/browser/real historical OOS acceptance. Preserve all existing containers/volumes and protected .env.example.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha V4 gap recomputation
CURRENT_TASK=Audit current owners for the next repository-actionable P0/P1 after the Pump.fun recovery slice
LAST_COMPLETED_STEP=PostgreSQL acceptance marked environment-blocked for this run: Docker API denied runner creation/network attachment, while host socket creation is restricted. The dedicated disposable container remains isolated; no migration or integration result is claimed.
NEXT_STEP=Read the latest current-state matrix and search existing owners/tests for cohort coverage, participant expansion, bundle exposure, microstructure, price efficiency, sell absorption, liquidity quality, archetypes and exact identity.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Pump/runtime focused checks PASS 161; raw-stream/IDL 43; provider replay/mismatch 4; Ruff PASS; mypy PASS 177 sources. PostgreSQL fresh/legacy/integration NOT_RUN because no current permitted network path. `make verify` not rerun in this recovery slice.
BLOCKERS=PostgreSQL runtime gate blocked by host socket and Docker API restrictions. Live RPC/provider, browser runtime and actual matched-control/OOS data remain unavailable unless separately evidenced. No existing containers or volumes were stopped or modified; .env.example preserved.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Event-time safety / raw-stream runtime cutoff
CURRENT_TASK=Reproduce whether the live Pump event path evaluates at event time before observation and ingestion
LAST_COMPLETED_STEP=Rechecked Pump.fun official migration docs: a successful pinned `migrate` instruction moves completed curve liquidity to PumpSwap, but current raw PumpSwap pool identity is not independently verified. Cross-venue continuity and lifecycle projection owners exist; pool-address certification remains UNKNOWN.
NEXT_STEP=Add a focused failing worker-cutoff test for an event with occurred_at < observed_at < ingested_at; then trace/fix the shared runtime and social-evidence cutoff in the live raw-chain processor.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=Pump graduation focused suites PASS 161 plus follow-up 4; Ruff PASS; mypy PASS 177. DB acceptance BLOCKED by host TCP/Docker API restrictions.
BLOCKERS=Exact-current PostgreSQL restart remains environment-blocked. Official Pump docs link source-event semantics; no supported PumpSwap migration pool identity is available for independent acceptance. Continue actionable time-cutoff audit.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Event-time safety and Pump.fun migration lifecycle
CURRENT_TASK=Run focused live-chain cutoff, migration normalization/runtime, feature, replay, and worker regression suites
LAST_COMPLETED_STEP=Test-first reproduced the worker signal cutoff omission (missing selector helper), then passed the cutoff and runtime event-clock regression. Test-first reproduced missing Pump migration state, then passed exact raw instruction normalization and runtime projection with pool identity kept UNKNOWN.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_worker_entrypoint.py tests/unit/test_early_runtime.py tests/unit/test_early_features.py tests/unit/test_solana_raw_stream.py tests/unit/test_launchpad_dex.py tests/unit/test_cross_venue_continuity.py tests/unit/test_early_detection.py --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only; no commit)
TEST_STATUS=New focused regression pair 2 passed; migration normalization/runtime slice 4 passed; cross-venue/lifecycle slice 10 passed. Full touched-scope selection pending.
BLOCKERS=PostgreSQL fresh/legacy/restart blocked by host socket restriction and Docker API denial; live RPC and pool certification not available. No protected config or unrelated container/volume changed.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Event-time safety and Pump.fun migration lifecycle
CURRENT_TASK=Fail closed on non-fresh migration evidence in both migration timestamp and state projections
LAST_COMPLETED_STEP=Focused regression matrix completed with 149 passed and 1 failed. The failure is new adversarial coverage: a migration observation downgraded to QualityState.UNKNOWN still projected PUMPSWAP_MIGRATED. This is a real source defect; no test was suppressed or weakened.
NEXT_STEP=Update the shared verified migration selector in `early_features.py` to require fresh protocol-verified evidence, then rerun the failing test and full focused matrix.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; no commit)
TEST_STATUS=Worker/feature/stream/provider/continuity selection 149 passed, 1 failed due to unsafe migration quality acceptance. Typecheck and touched Ruff not rerun after latest edits.
BLOCKERS=PostgreSQL fresh/legacy/restart blocked by host socket restriction and Docker API denial; live RPC/pool certification and real cohorts remain external/data acceptance. Preserve protected .env.example and all existing containers/volumes.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Event-time safety and Pump.fun migration lifecycle
CURRENT_TASK=Rerun the focused worker/runtime/protocol regression matrix after fail-closed lifecycle selector fix
LAST_COMPLETED_STEP=Shared lifecycle selector now requires fresh quality, verified protocol identity, no transaction error/reverted flag, and no retracted/recovered-unverified state. The focused pass covering valid migration and UNKNOWN-quality exclusion passed 2/2.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_worker_entrypoint.py tests/unit/test_early_runtime.py tests/unit/test_early_features.py tests/unit/test_solana_raw_stream.py tests/unit/test_launchpad_dex.py tests/unit/test_cross_venue_continuity.py tests/unit/test_early_detection.py --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; no commit)
TEST_STATUS=Specific migration quality failure repaired and retested. Broad selection pending.
BLOCKERS=PostgreSQL fresh/legacy/restart blocked by host socket restriction and Docker API denial; live RPC/pool certification and real cohorts remain external/data acceptance.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Pump.fun and runtime regression validation
CURRENT_TASK=Run Ruff on touched Python paths, make typecheck across current source, and scoped diff validation
LAST_COMPLETED_STEP=Focused worker/runtime/feature/raw-stream/adapter/cross-venue/detection matrix passed 150 tests after the lifecycle quality fix.
NEXT_STEP=Run `.venv/bin/ruff check` on touched source/tests, `make typecheck`, and `git diff --check -- . ':!.env.example'`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; no commit)
TEST_STATUS=Focused tests PASS 150; whole current typecheck/lint/diff validation pending.
BLOCKERS=PostgreSQL fresh/legacy/restart blocked by host socket restriction and Docker API denial; live RPC/pool certification and real cohorts remain external/data acceptance.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha V4 gap recomputation
CURRENT_TASK=Inspect remaining repository-owned P0/P1 items after the recovered clock/migration slice
LAST_COMPLETED_STEP=Focused regression matrix PASS 150. Touched Ruff PASS. `make typecheck` PASS with 177 source files. `git diff --check -- . ':!.env.example'` PASS; protected .env.example excluded and untouched.
NEXT_STEP=Audit whether multi-worker DexScreener quota is an actionable repository gap (deployment worker count, limiter owner, existing Redis quota primitives), then select the next non-blocked source gap from the current-state matrix.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; no commit)
TEST_STATUS=Focused Pump/runtime suite 150 passed; Ruff PASS; mypy PASS 177; scoped diff PASS. PostgreSQL acceptance remains BLOCKED.
BLOCKERS=Exact-current PostgreSQL restart, live RPC/provider, production browser, social/Telegram credentials, matched real controls and temporal OOS remain environment/external/data gates as documented. No remote git operations.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-tree full verification
CURRENT_TASK=Run make verify against the preserved current dirty tree and classify failures without changing protected or unrelated files
LAST_COMPLETED_STEP=Recovery slice and event-time/migration projection focused matrix PASS 150; touched Ruff PASS; make typecheck PASS with 177 sources; scoped diff-check PASS. DexScreener worker is single-replica in default/prod Compose; quota limiter is process-local, so shared quota is conditional on intentionally scaling workers (no shared Redis client or replica policy exists).
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensive inherited dirty tree preserved; Git metadata read-only)
TEST_STATUS=Focused tests and static gates PASS; full current-tree verify pending.
BLOCKERS=PostgreSQL fresh/legacy/restart blocked by host socket restriction and Docker API denial; live RPC/provider and browser runtime blocked; historical case data/OOS remains unavailable. No .env.example, unrelated worktree, container, or volume modified.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Independent verification after full Python suite
CURRENT_TASK=Run Make verification prerequisites after pytest stopped on four protected-tree failures
LAST_COMPLETED_STEP=`make verify` completed Ruff PASS, mypy PASS (177 sources), and full pytest: 4 failed, 1,701 passed, 26 skipped, 7 warnings in 305.69s. Two failures are the secret-boundary/security-review expectations caused by the protected dirty `.env.example`; one smoke contract expects `X_PROVIDER_ENABLED=false` missing from that protected file; no other Python failures were reported.
NEXT_STEP=make -k frontend-css-contract frontend-lint frontend-typecheck frontend-test compose-config secret-scan migration-check security-review sbom
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commits)
TEST_STATUS=All 1,701 other Python tests passed; frontend, compose, secret/security, migration, and SBOM gates are being run independently.
BLOCKERS=Do not modify or print protected .env.example. PostgreSQL/live RPC/browser/OOS blockers remain. Git metadata read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend CSS contract repair
CURRENT_TASK=Add the missing static CSS rule for the existing backend-owned service-conflict list and rerun its contract
LAST_COMPLETED_STEP=Independent Make gates: frontend lint PASS; frontend typecheck PASS; frontend Vitest 127/127 PASS; Compose config PASS; migration graph PASS (single head 0018_stream_gap_provider_id, 32 tables); SBOM PASS (564 components, sha256:a05ea994cb63e711bee6e2d327b1b6e5bd1781df622e9155154cf54d8f339415). `make -k` also reproduced CSS contract failure (`conflict-evidence-list`), secret scan/security review FAIL tied to protected .env.example material at line 209, and the protected example contract's missing X_PROVIDER_ENABLED=false. No secret value was inspected or changed.
NEXT_STEP=Add minimal `.conflict-evidence-list` layout rule to apps/web/src/app/globals.css, then run make frontend-css-contract.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no commits)
TEST_STATUS=CSS contract is the only discovered frontend-source failure; all frontend unit/lint/typecheck gates passed.
BLOCKERS=Protected .env.example prevents secret/security smoke gates from passing; exact PG/live RPC/browser/data/OOS gates remain blocked. Git metadata is read-only.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend production acceptance
CURRENT_TASK=Run the production Next build after repairing the missing conflict-list CSS contract
LAST_COMPLETED_STEP=Added one grid/gap rule for the existing `conflict-evidence-list`; `make frontend-css-contract` now passes with 363 classes/69 files. Service conflict + Operations Vitest selection passes 5/5. Earlier full frontend gates passed lint/typecheck/127 tests.
NEXT_STEP=make frontend-build
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; preserved dirty tree; Git metadata read-only)
TEST_STATUS=Production build and E2E are not yet validated against the current frontend tree.
BLOCKERS=Protected .env.example security contract remains unresolved by design. Exact PG/live RPC/browser listener and real-data acceptance gates remain open.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Production build root-cause
CURRENT_TASK=Diagnose the Next build TypeScript showConfig parsing failure before classifying it as host-only
LAST_COMPLETED_STEP=`make frontend-build` compiled successfully with Next.js 16.3.3/Turbopack, then exited 2 with `Could not parse output from TypeScript's --showConfig` before build completion. No build PASS claim.
NEXT_STEP=Inspect the direct TypeScript showConfig output and installed TypeScript/Next versions, then identify whether the repository config or host wrapper causes the parse failure.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=CSS, component, frontend lint/typecheck/tests pass; production build FAIL/INCOMPLETE at Next TypeScript config parsing.
BLOCKERS=Protected .env.example security finding; PostgreSQL/live RPC/browser/data/OOS gates remain. Build root cause under investigation.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Browser acceptance
CURRENT_TASK=Run the available Playwright E2E command and record host listener restrictions
LAST_COMPLETED_STEP=Production Next build compiles but does not complete: Next's `runTypeScriptCli` parser received exitCode 0 with empty captured stdout/stderr and threw Unexpected end of JSON; direct `tsc --showConfig --project tsconfig.json --pretty false` emitted valid JSON (6,141 bytes, 27 compiler options). This matches the host stream/process-pipe EPERM warning; no tsconfig bypass or product workaround applied.
NEXT_STEP=make frontend-e2e
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; preserved dirty tree)
TEST_STATUS=Frontend unit/lint/typecheck/CSS pass; production build blocked by host capture behavior; browser E2E pending.
BLOCKERS=Protected .env.example security gate; PostgreSQL runtime, live providers, and real data/OOS. Host TypeScript child-pipe behavior prevents clean build evidence.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Browser E2E blocker classification
CURRENT_TASK=Reproduce the Playwright webServer startup failure and confirm whether it is the known host listener restriction
LAST_COMPLETED_STEP=`make frontend-e2e` exited 2: Playwright reported `Process from config.webServer was not able to start. Exit code: 1`. No browser assertions ran.
NEXT_STEP=Inspect Playwright server command/config and its generated log/artifact to determine the exact startup postcondition, without changing product code.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; preserved dirty tree)
TEST_STATUS=Playwright environment startup failed before tests.
BLOCKERS=Host may prohibit listener creation; confirm from server log. Other blockers: protected .env.example, PostgreSQL, live providers, historical/OOS data.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Provider and dependency acceptance
CURRENT_TASK=Run bounded read-only DexScreener provider doctor and npm audit gates; inventory installed external scanners
LAST_COMPLETED_STEP=Playwright E2E failed before browser tests. Direct `npm run dev -- --hostname 127.0.0.1 --port 13100` reproduced `listen EPERM: operation not permitted` on the exact test address/port, confirming host listener policy rather than application startup failure. No code workaround attempted.
NEXT_STEP=Run current provider doctor, production/full npm audits, and installed scanner inventory with bounded network waits.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=Playwright browser acceptance BLOCKED_HOST; production build HOST_PIPE_CAPTURE_BLOCKED; frontend component/unit/lint/typecheck/CSS gates pass.
BLOCKERS=Protected .env.example security finding; PostgreSQL listener/Docker restrictions; no real case cohorts/OOS; live provider DNS/network may be blocked.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Bounded live discovery-feed contract check
CURRENT_TASK=Probe the official DexScreener discovery feeds once using the existing normalized adapter, with no writes or alerts
LAST_COMPLETED_STEP=Corrected the doctor’s misleading `PAIR_DISCOVERY_OK` label: its exact route is `/token-pairs/v1/solana/{wrapped SOL mint}`, not a discovery feed. Test-first contract failed before the fix, then passed 1/1; repeated live doctor passed with `TOKEN_PAIR_ENRICHMENT_OK`, 354 ms, keyless, schema passed, no rate-limit headers.
NEXT_STEP=Call the existing DexScreener adapter `discover(limit=5)` once with default public feeds and a 5-second/one-attempt transport; report only counts, source quality, errors.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=Doctor contract test PASS 1; live token-pair enrichment PASS. Discovery-feed live probe pending.
BLOCKERS=Package registry DNS EAI_AGAIN blocks dependency patching; protected .env.example causes security review FAIL; PostgreSQL/browser/OOS remain blocked.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Bounded live discovery-feed contract check
CURRENT_TASK=Retry the provider read using only the documented latest-profile feed because the five-feed probe was interrupted without a result
LAST_COMPLETED_STEP=The first adapter `discover(limit=5)` probe configured all five official feeds and one concurrency slot; it produced no output before the shell session was interrupted, so it is NOT counted as evidence and no candidate values were printed.
NEXT_STEP=Run one `profile` feed only through the normalized adapter with the standard bounded timeout, then stop if the host/network does not complete it.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; preserved dirty tree)
TEST_STATUS=Keyless token-pair enrichment doctor PASS; live discovery-feed acceptance pending.
BLOCKERS=Do not infer discovery live acceptance from the pair endpoint. npm registry DNS EAI_AGAIN; protected .env.example; PostgreSQL/browser/OOS gates remain blocked.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Final focused validation and checkpoint
CURRENT_TASK=Validate exact DexScreener doctor contract changes, current types/lint, and scoped diff before writing shutdown recovery evidence
LAST_COMPLETED_STEP=Doctor success label now says `TOKEN_PAIR_ENRICHMENT_OK`; its test asserts the exact official token-pairs path. Focused test passed 1/1 and live pair-enrichment doctor passed. The attempted official latest-profile adapter probe did not return before interruption and is not accepted as evidence. Current reports distinguish endpoint pass from feed coverage.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_free_provider_doctors.py; .venv/bin/ruff check scripts/dexscreener_doctor.py tests/unit/test_free_provider_doctors.py; make typecheck; make frontend-css-contract; git diff --check -- . ':!.env.example'
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no commits)
TEST_STATUS=Focused final checks pending; earlier full suite remains 4 failures tied to protected .env.example.
BLOCKERS=Provider registry DNS EAI_AGAIN prevents npm patch metadata/install; critical/high npm advisories remain. PostgreSQL, browser listener/build capture, social credentials, exact cases and OOS remain blocked.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Early Alpha V4 remaining source-owned gaps
CURRENT_TASK=Replace the buyer-only participant expansion score with a cluster-complete two-sided independent-trader trajectory score
LAST_COMPLETED_STEP=Recovered Pump.fun graduation/current-state path and its focused matrix; current-state audit still marks participant expansion as BUY_SIDE_ONLY despite independent buyer/seller/trader metrics being available.
NEXT_STEP=Add focused regression assertions first, then update EarlyFeatureEngine, runtime projection and Token Detail advisory rendering; keep score uncalibrated and fail UNKNOWN without complete buy/sell cluster evidence.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Prior focused Pump/runtime tests PASS 150; full verify 4 failures from protected .env.example; make typecheck PASS 177; exact-current PostgreSQL and production browser remain blocked.
BLOCKERS=Current feature extension is local/source-actionable; PostgreSQL restart, live provider evidence, browser host, historical real controls and OOS remain separate blockers. Do not modify protected .env.example or Git metadata.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Independent participant expansion score
CURRENT_TASK=Run focused EarlyFeatureEngine, runtime persistence-projection and read-projection regressions for the two-sided score
LAST_COMPLETED_STEP=Test-first regression failed as expected because the current snapshot had no independent-trader acceleration and still labeled the score BUY_SIDE_ONLY. Updated the engine to require complete buy+sell cluster evidence, calculate bounded independent-trader acceleration against the prior window, persist uncalibrated participant metrics through the existing flow snapshot, and render the broader score as advisory UI evidence.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Focused participant test was red before implementation; post-change feature/runtime/projection checks pending.
BLOCKERS=Exact-current PostgreSQL restart is unavailable in this host; do not claim database acceptance. Production browser listener, protected .env.example scan, real provider data and real temporal controls remain separate blockers.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion validation
CURRENT_TASK=Run touched Ruff, full Python source typecheck, Token Detail component test/lint/typecheck, then reconcile audit evidence
LAST_COMPLETED_STEP=Two-sided independent-trader expansion now uses complete buy/sell wallet-cluster evidence, independent-trader breadth/velocity and bounded adjacent-window acceleration; incomplete cluster evidence yields null score. Existing feature/runtime/read-projection regression matrix passes 68 tests after relocating the new metric into the initialized snapshot map.
NEXT_STEP=.venv/bin/ruff check packages/application/src/memeradar_application/early_features.py packages/application/src/memeradar_application/early_runtime.py tests/unit/test_early_features.py tests/unit/test_early_runtime.py tests/unit/test_early_read_projection.py; make typecheck; cd apps/web && npm test -- --run src/app/components/token-detail.test.tsx && npm run lint && npm run typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Focused Python feature/runtime/read-projection suite PASS 68; touched Ruff, typecheck, frontend gates pending.
BLOCKERS=Current-delta PostgreSQL persistence/restart cannot be exercised due host localhost/Docker restrictions. Browser E2E remains listener-blocked; historical data and temporal OOS remain unavailable.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion regression repair
CURRENT_TASK=Re-run focused Python and Token Detail tests after correcting the metrics-map initialization placement and updating visible text assertions
LAST_COMPLETED_STEP=The first broad focused run found the new acceleration assignment occurred before the snapshot metrics dictionary was initialized (59 failures shared one UnboundLocalError). Root cause was source ordering, confirmed at `EarlyFeatureEngine._window`; assignment was removed from the pre-map block and added to the map literal. Ruff also identified one duplicate nested key and line wrapping; the component test correctly failed because it asserted the old BUY_SIDE_ONLY UI text.
NEXT_STEP=Run touched Ruff plus the same 68 Python tests and Token Detail Vitest selection.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=First post-change feature suite failed due shared initialization ordering; no tests are currently considered passed after the correction.
BLOCKERS=No PostgreSQL/browser acceptance in this host; external case data/OOS remain unavailable. Protected .env.example remains untouched.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Participant expansion broad validation
CURRENT_TASK=Run the full frontend unit suite, frontend lint/typecheck and repository source typecheck for the changed participant projection
LAST_COMPLETED_STEP=After fixing the shared snapshot-map ordering, touched Ruff PASS; EarlyFeatureEngine/EarlyRuntime/read-projection tests PASS 68 with 2 existing warnings; Token Detail Vitest PASS 9/9.
NEXT_STEP=Run `make typecheck` and from `apps/web`: `npm test`, `npm run lint`, and `npm run typecheck`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; preserved dirty tree; no commit)
TEST_STATUS=Focused implementation validation PASS; broad Python and frontend validation after this delta pending.
BLOCKERS=PostgreSQL persistence/restart, browser listener/production wrapper, registry security patch, real protocol/case/OOS evidence remain blocked or unavailable.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Current-tree full verification after participant expansion change
CURRENT_TASK=Run `make verify` on the preserved current worktree and capture exact final Python/static results
LAST_COMPLETED_STEP=`make typecheck` PASS (177 source files); full frontend Vitest PASS (127 tests/28 files), ESLint PASS, and TypeScript `--noEmit` PASS. Focused token detail test PASS 9/9.
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Focused and broad frontend/Python typecheck pass. Full current Python suite and Ruff aggregate gate pending.
BLOCKERS=Previous full verify hit 4 protected `.env.example`/Compose failures; preserve file exactly. PostgreSQL/browser/live historical-data gates remain blocked or external.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend production acceptance after participant projection update
CURRENT_TASK=Run the production frontend build on the exact current UI tree; retain host failure details if reproduced
LAST_COMPLETED_STEP=`make verify` on current source: Ruff PASS; mypy PASS 177 sources; Python suite 1,701 passed, 26 skipped, 4 failed, 7 warnings (same protected `.env.example`/Compose failures; no participant regression). Full frontend suite 127/127, lint/typecheck PASS; focused feature/runtime/read projection 68/68 and Token Detail 9/9 PASS.
NEXT_STEP=make frontend-build
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Unit/source checks pass; production build recheck pending.
BLOCKERS=Known Next TypeScript child-output parse issue after compilation; browser listener EPERM; exact-current PostgreSQL blocked; provider/security/data/OOS blockers as above.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Identity overlap score validation
CURRENT_TASK=Run touched Ruff/mypy, all frontend tests/lint/typecheck, and current Token Detail/read-parser/API regression after clone-overlap projection addition
LAST_COMPLETED_STEP=Test-first identity regression failed on absent `clone_risk_score` and API field, then a versioned `clone-overlap-rules-v1` advisory score was added to the existing token similarity projection. Exact metadata URI and creator+name/ticker are two equal rule-coverage indicators; score is null/UNKNOWN for weak-only matches, carries reasons, and explicitly is not a probability. API, strict TypeScript parser and Token Detail display are wired; focused read persistence/API tests PASS 25, focused frontend tests PASS 47.
NEXT_STEP=.venv/bin/ruff check packages/application/src/memeradar_application/read_api.py apps/api/src/memeradar_api/read.py tests/unit/test_read_persistence.py tests/unit/test_read_api_routes.py; make typecheck; cd apps/web && npm test && npm run lint && npm run typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Focused identity API/persistence and frontend parser/UI tests pass; broad lint/typecheck and full frontend suite pending.
BLOCKERS=Persisted identity relation graph/social account authority remains unavailable in current model/data; exact-current PostgreSQL, browser E2E, external real evidence and OOS gates remain separate.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Identity overlap broad and production frontend validation
CURRENT_TASK=Build the updated frontend and run route analysis, then attempt production-mode Playwright once to confirm browser-host availability
LAST_COMPLETED_STEP=Identity overlap tests now prove strong exact evidence yields score 100/REVIEW, ticker-only yields null/UNKNOWN, API serializes the assessment, and frontend rejects score 101. Python identity tests PASS 25; frontend tests PASS 128/28 files; touched Ruff PASS; typecheck PASS 177. Frontend lint PASS. An initial combined run caught nullable TypeScript narrowing, fixed with an explicit null guard; parser tests PASS 38 and web typecheck PASS afterward.
NEXT_STEP=make frontend-build, then `npm run analyze:routes`; if build passes, run `MEMERADAR_E2E_PRODUCTION=1 npm run test:e2e` as a bounded host check.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Unit, lint and typechecks pass; production build and browser acceptance after identity change pending.
BLOCKERS=Browser listener previously returned EPERM; exact-current PG unavailable; real historical cohorts/OOS and external provider credentials absent.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Production E2E host diagnosis
CURRENT_TASK=Confirm the exact standalone server startup error underlying the production Playwright pre-test failure
LAST_COMPLETED_STEP=`make frontend-build` PASS on current tree; route analysis PASS for `/`, `/radar`, `/wallet-graph`, `/settings`, `/readiness` (17 JS chunks, largest chunk 229,156 bytes). Production-mode Playwright exited 1 before browser assertions (`webServer` startup failed); exact standalone error is being reproduced.
NEXT_STEP=Bounded direct standalone server start on the configured 127.0.0.1:13100 address, then classify based on exit/postcondition.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Production build and route analysis PASS; production E2E BLOCKED before test assertions, host root cause confirmation pending.
BLOCKERS=Host server listener expected to be restricted based on earlier dev EPERM. Exact-current PostgreSQL, live providers, real controls/OOS remain blocked/unavailable.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Final current-tree verification
CURRENT_TASK=Run `make verify` after the participant and identity-overlap changes; record exact failures and totals
LAST_COMPLETED_STEP=Production build PASS; route analysis PASS (five routes within gzip budgets, 17 chunks); production Playwright fails before tests and bounded standalone server confirms `listen EPERM` at 127.0.0.1:13100.
NEXT_STEP=make verify
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensively dirty tree preserved; no commit)
TEST_STATUS=Focused changes and frontend full tests pass; final exact-tree full Python suite pending.
BLOCKERS=Only host browser bind restriction confirmed for E2E. PostgreSQL localhost/Docker, protected `.env.example` security/Compose contracts, external provider inputs and real temporal research data remain.
UPDATED_AT=2026-10-07 local

STATUS=VALIDATION_COMPLETE_WITH_BLOCKERS
CURRENT_PHASE=Shutdown recovery and current-state evidence reconciliation
CURRENT_TASK=Persist final Early Alpha V4 recovery record and exact current-tree acceptance matrix
LAST_COMPLETED_STEP=Pump.fun graduation worker/runtime recovery, two-sided participant expansion, advisory clone-overlap read projection, current-state audit and final report are recorded. `make verify` returned Ruff PASS, mypy PASS (177 sources), 1,701 Python passed, 26 skipped, 4 failed, 7 warnings; failures are the protected `.env.example`/Compose contracts. Frontend Vitest 128/28, lint, typecheck, build, route analysis, migration check, CSS contract and SBOM pass. Production Playwright is blocked before assertions by `listen EPERM`.
NEXT_STEP=Run exact-current PostgreSQL restart/integration and browser production acceptance only on a host that permits the configured DB/listener; collect real provider and matured chronological outcome data before calibrating any score.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; unchanged; dirty worktree preserved; no commit)
TEST_STATUS=Source/unit/static and production build gates pass as listed in docs/reports/EARLY_ALPHA_V4_FINAL.md. Exact-current PostgreSQL and production browser acceptance are environment-blocked; four verify failures remain tied to protected inherited `.env.example`/Compose contracts.
BLOCKERS=PostgreSQL runtime/network unavailable; browser listener denied with EPERM; X/Telegram/Helius/Solana RPC credentials absent; npm registry EAI_AGAIN and scanner tools absent; exact historical case identities/time series, real matched controls and mature chronological OOS unavailable. `.env.example` was not manually inspected or modified; the failed test harness read it programmatically and its output is not reproduced in this checkpoint. `.codex/CURRENT_TASK.md`, `.codex/VERIFICATION.md`, and docs/STRATEGY_VALIDATION_LAB.md are absent in this accessible checkout.
UPDATED_AT=2026-10-07 local

STATUS=VALIDATION_COMPLETE_WITH_BLOCKERS
CURRENT_PHASE=Final exact-tree source verification
CURRENT_TASK=Record the final `make verify` result and remaining environment/data gates
LAST_COMPLETED_STEP=Fresh `make verify`: Ruff PASS; mypy PASS (177 sources); pytest 1,703 passed, 26 skipped, 4 failed, 7 warnings in 310.39s. All four failures are protected `.env.example`/Compose contract assertions. Frontend Vitest PASS 128/28, lint/typecheck/build/route analysis PASS; migration head `0018_stream_gap_provider_id`, CSS contract PASS (363 classes/69 files), SBOM PASS (564 components; SHA256 `a05ea994cb63e711bee6e2d327b1b6e5bd1781df622e9155154cf54d8f339415`).
NEXT_STEP=Production browser and exact-current PostgreSQL acceptance on a host that permits listener/database access; external provider and chronological real-data acceptance when credentials/data are available.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Final exact-tree verification completed; `make verify` fails only at the four protected config/Compose contract tests after Ruff and mypy pass. Separate frontend, migration, CSS contract and SBOM gates pass. Production E2E fails before assertions with host `listen EPERM`.
BLOCKERS=Exact-current PostgreSQL restart/integration unavailable; browser listener denied with EPERM; four protected `.env.example`/Compose assertions unresolved without modifying the protected user-owned file; provider credentials/live protocol evidence absent; exact historical case data, matched real controls and mature chronological OOS unavailable. DexScreener quota sharing is conditional: deployed worker count is one, so process-local limiting meets current topology; revisit on scale-out. `.env.example` was not manually inspected or modified; test harness output is not reproduced here.
UPDATED_AT=2026-10-07 local

STATUS=VALIDATION_COMPLETE_WITH_BLOCKERS
CURRENT_PHASE=Early Alpha V5 dataset-integrity continuation
CURRENT_TASK=Record the exact-tree research-integrity fix and stop alpha evaluation at the real-data gate
LAST_COMPLETED_STEP=Fixed chronological partition leakage by grouping equal decision timestamps and refusing a test partition without three distinct timestamps. Unverified research samples now default to no-lookahead=false; canonical case-study construction attests only after validating event/observed/ingested clocks. Dataset/report semantics were versioned and synthetic artifacts regenerated. Focused tests PASS 35; full `make verify` completed with Ruff PASS, mypy PASS (177 sources), pytest 1,706 passed, 26 skipped, 4 failed, 7 warnings in 301.10s. Three security-review assertions fail closed on one Telegram-token-shaped match at line 209 of the protected dirty `.env.example` (value not reproduced); the Compose contract test separately expects `X_PROVIDER_ENABLED=false` there. `make alpha-readiness` confirms 7 synthetic rows (2 fixture winners, 1 fixture rug), 0 real samples, 0 real outcomes, 0 caller identities, and 0 negative controls.
NEXT_STEP=Acquire timestamped real launch/outcome and matched-negative data, then run chronological validation; exact-current PostgreSQL/browser gates also require a host with permitted database/listener access.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; pre-existing dirty tree preserved; Git metadata read-only)
TEST_STATUS=V5 focused research/replay suite PASS 35; V5 full `make verify` FAIL: Ruff and mypy pass, pytest 1,706 passed / 26 skipped / 4 failed / 7 warnings. Three security-review failures result from one token-shaped match in the protected file; the Compose contract separately asserts a missing example flag. Artifact/history secret scans found 0; tracked-file scan found 1. `make alpha-readiness` reports INSUFFICIENT_SAMPLES with CHRONOLOGICAL_PARTITIONS_REQUIRED, MATURED_CALLS_REQUIRED, CALLER_IDENTITIES_REQUIRED, MATURED_TOKEN_OUTCOMES_REQUIRED, NEGATIVE_CONTROLS_REQUIRED, REQUIRED_COHORTS_MISSING, HISTORICAL_REAL_EVIDENCE_REQUIRED. Existing frontend/build/migration/SBOM evidence is documented in the V4 report and was not rerun in V5.
BLOCKERS=Real historical data and negative controls are absent; all seven fixture rows share one event time and are synthetic/redacted. No database/provider credentials are configured. Production browser listener is host-blocked. The protected `.env.example` has one token-shaped finding and one config-contract mismatch; it was not manually inspected or modified. No chronological OOS, calibration, or alpha claim is supported.
UPDATED_AT=2026-10-07 local

STATUS=IN_PROGRESS
CURRENT_PHASE=V6 persisted real-data funnel
CURRENT_TASK=Connect strict point-in-time readiness import to canonical persisted observations and make forward outcomes carry source attestation only when their launch and market evidence qualify
LAST_COMPLETED_STEP=Confirmed the zero-real-data root cause: `scripts/alpha_readiness.py` previously read only seven synthetic/redacted case-study rows; the old Pump.fun report is aggregate-only and cannot provide importable per-token outcomes. Added a strict real-outcome importer, separate token-level readiness, source-gated forward-outcome attestation, and a read-only database readiness path. Current `scripts/alpha_readiness.py` output reports DATABASE_NOT_CONFIGURED, 0 persisted inputs, and keeps the seven synthetic rows separate. Focused tests: 13 passed, 2 skipped; touched Ruff PASS.
NEXT_STEP=Run source typecheck and broader affected tests, then persist the V6 funnel and blocker registry from exact current evidence.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensively dirty worktree preserved; Git metadata read-only)
TEST_STATUS=Focused readiness/import/forward collector/contracts: 13 passed, 2 skipped because aiosqlite is unavailable. Touched Ruff PASS. Async DB query and current PostgreSQL acceptance are not validated in this host.
BLOCKERS=DATABASE_URL/MEMERADAR_DATABASE_URL are unavailable and Docker/psql are unavailable in this unchanged host; live-shadow artifacts are failed-start aggregates without records; historical Pump.fun artifact has only aggregate horizon counts. `.env.example` was not opened or changed; additional credential-shaped matches require owner review/rotation. No real outcomes, matched negatives, OOS, calibration, or alpha claim.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=V6 funnel evidence and repository gates
CURRENT_TASK=Build the exact zero-real-sample funnel and blocker registry, then complete remaining locally executable validation
LAST_COMPLETED_STEP=`scripts/alpha_readiness.py` exited 0 and now explicitly reports DATABASE_NOT_CONFIGURED with zero persisted rows; the seven synthetic fixture rows remain isolated. `make typecheck` PASS (177 sources), script-specific mypy PASS (1 file), touched Ruff PASS, and focused tests PASS (14 passed / 2 skipped).
NEXT_STEP=Write `V6_REAL_DATA_FUNNEL.md`, `V6_BLOCKER_REGISTRY.md`, and the current V6 report from this run's evidence; inspect collector operator entrypoints without reading secret files.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no commit)
TEST_STATUS=Focused V6 suite 14 passed, 2 skipped (SQLite database integration requires unavailable `aiosqlite`). Touched Ruff and mypy checks pass. Real database query, PostgreSQL, browser, provider-backed collection, and full `make verify` have not been accepted on this V6 tree.
BLOCKERS=No configured database URL, Docker, or psql; old research artifacts lack per-token provenance/outcomes; no real cohort or matured negative labels. The protected `.env.example` has additional credential-shaped content; leave unchanged and mark SECURITY_ROTATION_REQUIRED. No OOS/calibration/alpha claim.
UPDATED_AT=2026-10-08 local


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 final local validation and evidence ledger
CURRENT_TASK=Recheck strict real-data import and outcome attestation, then run focused tests, typecheck, readiness and scoped diff validation
LAST_COMPLETED_STEP=Recovered the V6 importer, source-gated real-outcome attestation, and canonical database readiness query from the preserved dirty tree. The active host marks `.codex/` read-only, so the requested .codex checkpoints cannot be written; this writable STATUS record is the durable checkpoint.
NEXT_STEP=.venv/bin/python -m pytest -q tests/unit/test_historical_dataset_ingest.py tests/unit/test_alpha_readiness_database.py tests/unit/test_pumpfun_forward_evidence.py tests/contract/test_alpha_readiness_report.py --tb=short
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; 256 status entries; 90 untracked; 0 staged; Git metadata read-only)
TEST_STATUS=Prior focused V6 suite 14 passed / 2 skipped; touched Ruff and mypy passed. SQLite readiness integration skipped because aiosqlite is unavailable. Recovery-turn rerun pending.
BLOCKERS=No configured database URL, Docker, or psql; old Pump.fun artifact has aggregate counts but no per-token evidence; real outcomes, negatives and OOS require collection and maturation. Protected .env.example contains additional credential-shaped content and remains unopened/unchanged; SECURITY_ROTATION_REQUIRED. .codex is host read-only. Browser/provider/security-registry gates remain blocked.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext responsive browser failure investigation
CURRENT_TASK=Determine whether the mobile nav hydration assertion fails in the application or because the full visual matrix leaves inadequate hydration time
LAST_COMPLETED_STEP=Full Playwright command main matrix completed: 79 passed, 10 skipped, 1 failed. The sole failure was the mobile visual matrix observing `data-nav-hydrated=false` for five seconds after a route navigation; the combined command stopped before the social/services suite. Frontend 145 tests, typecheck, lint, build, backend focused 32 passed/1 skipped, Ruff, and mypy remain green.
NEXT_STEP=Run `npx playwright test e2e/visual-matrix.spec.ts --project=mobile --workers=1` with failure context to identify the route and reproduce the hydration state.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Source/unit/build gates PASS; responsive Playwright matrix FAIL 79/1/10; focused reproduction pending
BLOCKERS=PostgreSQL runtime remains unavailable; fixture browser suite did not start because main Playwright command failed; hydration failure root cause not yet established
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome evidence projection
CURRENT_TASK=Expose persisted candidate-linked forward outcomes through the canonical read API and use them in the Outcomes/Missed Winners workflows without implying unavailable real-data findings
LAST_COMPLETED_STEP=Recovered the current dirty-tree state at main/35274d2fd7ae07ef6446b66cef70ac6b93f5e84e. V6 full make verify is recorded PASS (1,721 passed / 27 skipped / 7 warnings); current frontend responsive browser suite passed 80 tests with 10 intentional skips across five viewport projects, fixture services/social suite passed 60/60, frontend Vitest 139/139, typecheck and production build PASS. Existing persisted research.outcome and research.missed_winner observations were found in the worker path, contradicting the older frontend parity claim that candidate outcome evidence is not persisted.
NEXT_STEP=Inspect the typed read-query contract, persistence observation schema, worker outcome payload and API tests; add the smallest bounded projection that exposes persisted outcome evidence with provenance and point-in-time filtering.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; 267 status entries, 101 untracked, 0 staged; extensively dirty tree preserved)
TEST_STATUS=VNext browser suites and frontend unit/type/build gates have passed as recorded above; final chained `npm run test:e2e` was not rerun after the E2E-only hydration wait change, though its responsive and fixture suites each passed independently. Outcome projection not yet implemented or tested.
BLOCKERS=No accepted real/mature outcomes, negative controls, rule-match attribution, or alpha validation; live/PostgreSQL source remains unavailable per V6 checkpoint. `.codex/CURRENT_TASK.md`, `.codex/VERIFICATION.md`, and `docs/STRATEGY_VALIDATION_LAB.md` are absent in this checkout. Browser listen was available during this run; older host-blocked browser evidence is superseded for VNext.
UPDATED_AT=2026-10-08 local


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 broad source validation
CURRENT_TASK=Run touched Ruff and full repository mypy after V6 readiness/importer changes
LAST_COMPLETED_STEP=Recovery focused V6 suite PASS: 14 passed, 2 skipped (the optional aiosqlite database test is skipped).
NEXT_STEP=.venv/bin/ruff check packages/application/src/memeradar_application/historical_dataset.py apps/worker/src/memeradar_worker/forward_evidence.py scripts/alpha_readiness.py tests/unit/test_historical_dataset_ingest.py tests/unit/test_alpha_readiness_database.py tests/unit/test_pumpfun_forward_evidence.py tests/contract/test_alpha_readiness_report.py; make typecheck
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; 0 staged)
TEST_STATUS=Focused V6 suite PASS 14 / SKIP 2. Touched Ruff and full mypy pending.
BLOCKERS=No configured database URL, Docker, psql, per-token historical outcome artifacts, matured real negatives or OOS. Protected .env.example unchanged; SECURITY_ROTATION_REQUIRED. .codex is host read-only.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 readiness and migration inventory
CURRENT_TASK=Re-run real-data readiness and current migration graph; the prior focused test and typecheck results have been confirmed
LAST_COMPLETED_STEP=Recovery focused tests PASS 14 / SKIP 2; touched Ruff PASS; `make typecheck` PASS (177 source files).
NEXT_STEP=Run `make alpha-readiness` and `make migration-check`, recording only sanitized count/status fields.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no staged files)
TEST_STATUS=Focused V6 tests, touched Ruff and full mypy pass. Readiness and migration graph recheck pending.
BLOCKERS=No DB URL/runtime, Docker or psql; no per-token historical outcomes or real controls. Protected .env.example remains unopened/unchanged; credential-shaped findings trigger SECURITY_ROTATION_REQUIRED. .codex is read-only.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 exact-tree full verification
CURRENT_TASK=Run `make verify` with stdout/stderr captured privately and report only gate status/counts, not config values
LAST_COMPLETED_STEP=Readiness rerun: DATABASE_NOT_CONFIGURED, 0 persisted inputs, 0 accepted real samples; fixture report remains 7 SYNTHETIC_REDACTED rows at one timestamp. Migration check PASS: one head 0018_stream_gap_provider_id, 32 tables.
NEXT_STEP=make verify (capture output to /tmp/memeradar-v6-make-verify.log; print only exit code and sanitized test/gate summaries)
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; 0 staged)
TEST_STATUS=Focused V6 tests 14 passed / 2 skipped; Ruff PASS; typecheck PASS 177 sources; readiness and migration check PASS. Full verify pending.
BLOCKERS=DB URL/runtime, Docker, psql, per-token old outcomes, mature real controls and OOS remain unavailable. Protected .env.example unchanged and credential-shaped content remains SECURITY_ROTATION_REQUIRED. .codex read-only.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 post-failure independent gates
CURRENT_TASK=Run the make verify stages that were not reached after pytest failed, without exposing protected configuration values
LAST_COMPLETED_STEP=`make verify` exact-tree: Ruff PASS; mypy PASS (177 files); pytest 1,714 passed, 27 skipped, 4 failed, 7 warnings in 283.98s. Failing contracts are the pre-existing protected example/config scan boundaries; no scanner output or config values were reproduced. Make stopped at pytest, so downstream frontend/Compose/secret/migration/security/SBOM stages were not reached.
NEXT_STEP=Run independent CSS, frontend lint/typecheck/test, Compose config, secret scan, migration check, keyless security review, and SBOM with outputs captured and only status fields surfaced.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no staged files)
TEST_STATUS=Focused V6 PASS 14 / SKIP 2. Full verify FAIL at pytest with 1,714 passed / 27 skipped / 4 failed / 7 warnings; Ruff and mypy pass.
BLOCKERS=Protected .env.example has additional credential-shaped content; SECURITY_ROTATION_REQUIRED and no edit. Its example config contract still blocks tests. Database/provider/outcome/data/browser constraints remain. .codex is host read-only.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 frontend source gates
CURRENT_TASK=Revalidate frontend tests, lint, typecheck and production build; no frontend source changed during V6
LAST_COMPLETED_STEP=Independent gates: CSS contract PASS; Compose config PASS; migration graph PASS (0018_stream_gap_provider_id, 32 tables); SBOM PASS (564 components). Secret scan and keyless security review exit nonzero; output was captured and no finding values were emitted. `make verify` stopped at pytest before these stages.
NEXT_STEP=Run `make frontend-test`, `make frontend-lint`, `make frontend-typecheck`, and `make frontend-build` with summaries only.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no staged files)
TEST_STATUS=V6 backend focused suite PASS 14 / SKIP 2; full verify 1,714 passed / 27 skipped / 4 failed. Frontend current recheck pending.
BLOCKERS=Credential-shaped config finding keeps secret scan/security review FAIL and protected .env.example remains unmodified; config contract tests also fail. No DB/runtime or real temporal data.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 production frontend build diagnosis
CURRENT_TASK=Capture one sanitized reproduction of the current frontend build failure
LAST_COMPLETED_STEP=Current frontend recheck: Vitest PASS 128/128 across 28 files; lint PASS; typecheck PASS. `make frontend-build` exited 2, but the first run did not retain diagnostic output.
NEXT_STEP=Run `make frontend-build` once with output captured to /tmp; report only error category and safe source path/message fields.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no staged files)
TEST_STATUS=Frontend tests/lint/typecheck PASS; production build FAIL pending root-cause classification.
BLOCKERS=Protected config/security scan failures; no DB/runtime or real outcomes. Build retry is bounded to one diagnostic capture.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 final full verification
CURRENT_TASK=Run make verify after completing shared outcome horizons and read-only per-horizon coverage reporting
LAST_COMPLETED_STEP=Expanded V6 focused suite PASS: 25 passed, 2 skipped; touched Ruff PASS; make typecheck PASS (177 sources). Per-horizon completion reports attempted, matured, succeeded, provider-missing, explicit failures, quality-unknown, due-unattempted and not-yet-mature counts; unavailable DB state returns null counts.
NEXT_STEP=make verify (capture full output privately; surface only gate summaries and failed test names)
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree; 0 staged)
TEST_STATUS=Focused suite PASS 25 / SKIP 2; Ruff PASS; typecheck PASS; full verify pending.
BLOCKERS=No current database/runtime, public outbound provider access, or elapsed matured outcome cohort. Protected config/secret-review blocker remains unchanged.
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=V6 final current-tree verification after authorized example-config remediation
CURRENT_TASK=Run `make verify` after emptying the scanner-identified Telegram example assignment, disabling X in the example, and removing the unused TELEGRAM_ENABLED key
LAST_COMPLETED_STEP=Key-only environment audit: 107 canonical runtime environment names, 102 example keys, no duplicates, production-required names present, nine absent optional/compatibility settings. `make secret-scan`, `make security-review`, `make compose-config` PASS; the four previously failing security/Compose tests pass (4 passed in 48.21s). Five other non-empty credential-looking assignments remain untouched and require owner review.
NEXT_STEP=Run `make verify` with output captured to `/tmp/memeradar-v6-final-verify-post-config.log`; report only gate summaries and failed test names
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; extensively dirty worktree preserved; no staged files; no commit)
TEST_STATUS=V6 focused suite 25 passed / 2 skipped; Ruff PASS; typecheck PASS (177 sources); prior full verify had 1,717 passed / 27 skipped / 4 failed; the four failures were individually rerun and pass after example remediation. Final full verify pending.
BLOCKERS=Database/Docker/psql unavailable, so DB contents and real launch/outcome funnel remain unknown; aggregate historical outcomes are not importable. No real samples, mature outcomes, negative controls, matching, calibration or OOS. Five unverified credential-looking example assignments require owner review and possible rotation. Public provider network unavailable; browser child/listener permission failures and package-registry access remain external/host blockers. No alpha claim.
UPDATED_AT=2026-10-08


STATUS=BLOCKED_EXTERNAL
CURRENT_PHASE=V6 local engineering closure
CURRENT_TASK=Resume real-data collection and research after database/provider access is available; no further local alpha claim is supportable
LAST_COMPLETED_STEP=Full `make verify` PASS after example remediation: exit 0; Ruff PASS; mypy PASS (177 sources); pytest 1,721 passed / 27 skipped / 7 warnings in 291.00s; configured frontend and remaining Makefile gates completed. Four previous security/Compose failures PASS on rerun. Key-only env contract audit and V6 reports are complete.
NEXT_STEP=On a configured host, provide the database through the approved secret path and run `make start`, `make status`, and `make alpha-readiness`; keep the read-only collector running through required outcome horizons, then build real negatives, matched controls, ablation and chronological OOS. Owner-review the five unverified credential-looking example assignments before any credential use.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; final worktree 258 entries: 167 tracked dirty, 91 untracked, 0 staged; no commit)
TEST_STATUS=V6 focused suite 25 passed / 2 skipped; Ruff PASS; typecheck PASS (177 sources); full `make verify` PASS (1,721 passed / 27 skipped / 7 warnings); secret scan, security review, Compose and focused previously failing tests PASS. Frontend production build/browser E2E are host-blocked; PostgreSQL, live provider and Telegram acceptance were not run.
BLOCKERS=Current DB data is unknown because DATABASE_URL/runtime, Docker and psql are unavailable; legacy launch history is aggregate-only and non-importable. No real accepted samples, mature outcomes, negative controls, matched controls, calibration or OOS; 7d outcomes require elapsed time. Public provider network, browser listener/Next child-pipe and package registry are blocked. Five non-empty credential-looking example assignments remain unverified and untouched; owner review/possible rotation required. No alpha claim.
FINAL_VERDICT=EARLY_ALPHA_V6_BLOCKED_EXTERNAL
UPDATED_AT=2026-10-08


STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext fixture suite verification
CURRENT_TASK=Rerun social/services browser suite with explicit app hydration wait in the claim workflow
LAST_COMPLETED_STEP=The isolated mobile-wide claim test passed 3/3, supporting a hydration-timing race in parallel fixture runs. The test now waits for the existing `data-nav-hydrated=true` marker and confirms `aria-selected=true` after clicking the tab.
NEXT_STEP=Run `npx playwright test --config=playwright.social-alpha.config.ts` in apps/web; this is the fixture-backed social/services suite (60 cases across 5 viewport projects).
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved; no remote operations)
TEST_STATUS=Responsive browser suite PASS 80 / 90 (10 skipped); fixture browser suite had 59 / 60 PASS, and the only failure passed isolated 3/3. Fixed test readiness wait is pending validation.
BLOCKERS=No browser host blocker in this run. Candidate-linked forward-outcome/rule-impact API projections and real matured labels remain unavailable. Fixture browser suite has not run yet.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome evidence projection
CURRENT_TASK=Expose persisted candidate-linked forward outcomes through the canonical read API and use them in the Outcomes/Missed Winners workflows without implying unavailable real-data findings
LAST_COMPLETED_STEP=Recovered current dirty-tree state at main/35274d2fd7ae07ef6446b66cef70ac6b93f5e84e. V6 full make verify is recorded PASS (1,721 passed / 27 skipped / 7 warnings); current frontend responsive browser suite passed 80 tests with 10 intentional skips across five viewport projects, fixture services/social suite passed 60/60, frontend Vitest 139/139, typecheck and production build PASS. Persisted research.outcome/research.missed_winner observations were found in the worker, superseding the older parity report's statement that outcome records do not exist.
NEXT_STEP=Finish the allow-listed read projection and add the bounded API route, persistence query, and outcome/missed-winner UI against persisted observations.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; 267 status entries, 101 untracked, 0 staged; extensively dirty tree preserved)
TEST_STATUS=Prior VNext browser/unit/type/build evidence as above; combined Playwright command was not rerun after the E2E-only hydration wait change, though both its constituent suites passed independently. Outcome projection tests pending.
BLOCKERS=No accepted real/mature outcomes, negative controls, rule-match attribution, or alpha validation. `.codex/CURRENT_TASK.md`, `.codex/VERIFICATION.md`, and `docs/STRATEGY_VALIDATION_LAB.md` are absent in this checkout. No current live PostgreSQL data evidence.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome evidence projection
CURRENT_TASK=Finish the candidate-linked persisted outcome read projection and connect Outcomes/Missed Winners
LAST_COMPLETED_STEP=Current read API test was attempted with system pytest but collection stopped before assertions because system Python lacks FastAPI. The checkout has a project `.venv`; `.codex` checkpoint files are not writable in this runtime, so this status file is the durable checkpoint.
NEXT_STEP=Run `.venv/bin/python -m pytest -q tests/unit/test_read_api_routes.py -k forward_outcomes_are_bounded_filtered_and_point_in_time` to verify the intended missing-route failure, then implement persistence and API route.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved; no remote operations)
TEST_STATUS=Outcome projection test not yet executed under project environment.
BLOCKERS=.codex is read-only in this environment. No current PostgreSQL/runtime data has been validated.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection backend
CURRENT_TASK=Validate the typed bounded forward-outcome route before frontend consumption
LAST_COMPLETED_STEP=Test-first failure confirmed `/v1/forward-outcomes` returned 404 under project `.venv`. Added allow-listed outcome view mapping, exact scalar threshold/boolean query filters, identity-safe candidate/token join, point-in-time filters, keyset pagination, typed API route/response and OpenAPI contract entry.
NEXT_STEP=Run focused route and schema tests; then add persistence query execution coverage and frontend fetch/page integration.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=Expected 404 observed before route implementation. Post-implementation focused tests pending.
BLOCKERS=PostgreSQL runtime availability not yet probed; `.codex` checkpoint directory is not writable.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome evidence projection
CURRENT_TASK=Verify allow-listed SQL persistence mapping, exact scalar target selection and canonical API contract
LAST_COMPLETED_STEP=The focused API regression now passes after adding the route. Persistence uses candidate/token-consistent joins, default/current as_of limits, event/observed/ingested timestamps, keyset cursor, and JSON scalar equality for `threshold` or `hit_10x`-style booleans; array containment is avoided.
NEXT_STEP=Run focused Python route, persistence-mapper, OpenAPI, and opt-in PostgreSQL integration tests; then fix failures before implementing UI consumers.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=Focused API regression PASS (1 passed); persistence mapper and exact PostgreSQL query tests pending.
BLOCKERS=PostgreSQL test URL not configured, psql missing; Docker command exists but daemon not yet probed.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection backend validation
CURRENT_TASK=Rerun the focused backend contracts after correcting a test placement error
LAST_COMPLETED_STEP=The first focused backend batch reached 30 passes and 2 opt-in PostgreSQL skips; one failure was a misplaced tail of the neighboring pre-existing route test, not the new route behavior. The new route returned 200, enforced as_of, excluded raw payload, and rejected target 110X with 422.
NEXT_STEP=Rerun the focused route/persistence/OpenAPI batch and check Docker daemon availability once for PostgreSQL integration acceptance.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty worktree preserved)
TEST_STATUS=Focused batch: 30 passed, 2 skipped, 1 failed from test edit placement; fix applied, rerun pending.
BLOCKERS=PostgreSQL URL absent; Docker daemon availability unknown.
UPDATED_AT=2026-10-08 local

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome workflows
CURRENT_TASK=Connect the canonical outcome projection to Token Outcomes and Missed Winners views
LAST_COMPLETED_STEP=Backend focus suite PASS: 31 passed, 2 opt-in PostgreSQL tests skipped, 5 deprecation warnings. Test-first UI evidence test was observed failing because the new component did not yet exist. Added shared outcome evidence table, bounded filters/pagination URLs, /outcomes route, Missed Winners query integration and navigation entry.
NEXT_STEP=Run focused Vitest suites for the new outcome table, missed-winner page and read API parsing; then run TypeScript typecheck and frontend lint.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e (main; dirty tree preserved)
TEST_STATUS=Backend projection tests PASS 31; PostgreSQL integration skipped because URL missing. Frontend outcome tests pending.
BLOCKERS=PostgreSQL exact query runtime test is host-blocked: docker daemon denied access to `/var/run/docker.sock`; `MEMERADAR_TEST_DATABASE_URL` absent. `.codex` checkpoint files are read-only.
UPDATED_AT=2026-10-08 local

## Frontend VNext checkpoint — outcome UI tests

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome workflows
CURRENT_TASK=Validate the candidate-linked forward outcome UI after aligning three test assertions with the actual contract
LAST_COMPLETED_STEP=Backend focus suite PASS: 31 passed, 2 skipped (PostgreSQL integration unavailable), 5 deprecation warnings. Outcome route, typed read model, exact scalar membership query, Outcomes and Missed Winners views are implemented.
NEXT_STEP=npm test -- --run src/app/components/outcomes.test.tsx src/app/components/missed-winners.test.tsx src/app/lib/read-api.test.ts
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend focused tests PASS; frontend test rerun pending
BLOCKERS=PostgreSQL runtime validation unavailable in this environment; no configured test database and Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome workflows
CURRENT_TASK=Run frontend typecheck and lint for the outcome projection integration
LAST_COMPLETED_STEP=Focused frontend suites PASS: 48 passed across Outcomes, Missed Winners, and read API tests. `git diff --check -- . ':!.env.example'` PASS.
NEXT_STEP=Run `npm run typecheck` and `npm run lint` from apps/web
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend focus 31 passed / 2 skipped; frontend focus 48 passed; typecheck/lint pending
BLOCKERS=PostgreSQL runtime validation unavailable in this environment; no configured test database and Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome workflows
CURRENT_TASK=Run frontend regression tests and production build for the candidate-linked outcome integration
LAST_COMPLETED_STEP=Frontend focused tests PASS (48/48); `npm run typecheck` PASS; `npm run lint` PASS.
NEXT_STEP=Run full frontend Vitest suite, then production build and browser outcome workflow checks
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend focus 31 passed / 2 skipped; frontend focus 48 passed; typecheck and lint PASS
BLOCKERS=PostgreSQL runtime validation unavailable in this environment; no configured test database and Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome workflows
CURRENT_TASK=Verify production compilation and Python quality gates for the canonical outcome API/persistence path
LAST_COMPLETED_STEP=Full frontend Vitest PASS: 32 files, 143 tests. Frontend typecheck and ESLint PASS. Persistence read query was inspected for candidate/token joins, observed/ingested/event-time cutoffs, allow-listed payload projection, exact scalar JSON filtering, and bounded cursor ordering.
NEXT_STEP=Run `npm run build` in apps/web and scoped Ruff/mypy checks on touched Python paths
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend 143 passed; backend focused 31 passed / 2 skipped (PostgreSQL unavailable)
BLOCKERS=PostgreSQL runtime validation unavailable in this environment; no configured test database and Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection validation
CURRENT_TASK=Finish backend lint/type validation after fixing outcome-path formatting
LAST_COMPLETED_STEP=Frontend production build PASS; `/outcomes` and `/missed-winners` appear as dynamic server-rendered routes. Initial scoped Ruff found formatting/import issues in this dirty outcome work; import order and overlong lines were fixed. PostgreSQL integration remains opt-in and skipped.
NEXT_STEP=Rerun scoped Ruff and mypy on outcome API/application/persistence modules, then rerun focused backend tests
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend Vitest 143 passed; typecheck/lint/build PASS; backend focused 31 passed/2 skipped; Ruff retry pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection validation
CURRENT_TASK=Run project-configured Python typecheck with source roots and final focused backend checks
LAST_COMPLETED_STEP=Frontend production build PASS; full frontend Vitest 143/143; typecheck and ESLint PASS. Scoped Ruff's initial report was fixed; final rerun has one overlong comment being corrected. A direct file-list mypy invocation was invalid for this src-layout repository because it omitted package source roots; it was stopped and is not treated as a project typecheck result.
NEXT_STEP=Run `make typecheck` with the repository src roots on PYTHONPATH, plus scoped Ruff and focused backend tests
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend PASS; backend focus 31 passed/2 skipped; full configured Python typecheck pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext browser acceptance and type repair
CURRENT_TASK=Resolve one outcome response typing issue and extend browser coverage to the new Outcomes/Missed Winners routes
LAST_COMPLETED_STEP=Scoped Ruff PASS; backend focused pytest PASS (31 passed, 2 PostgreSQL-only skipped, 5 deprecation warnings). Project-configured `make typecheck` surfaced 5 response-field type errors because the application view's numeric union annotation did not reflect its Decimal normalization. The model annotation was narrowed to Decimal; direct mypy invocation without src roots was invalid and stopped. The existing E2E missed-winner assertion was stale after the UI switched to explicit unverified-causality wording; it is updated, and Outcomes filter navigation plus axe route coverage were added.
NEXT_STEP=Rerun project-configured mypy and Playwright desktop operator workflow test for `/outcomes` and `/missed-winners`
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend/Frontend tests pass; typecheck repair and targeted browser test pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext browser acceptance
CURRENT_TASK=Verify Outcomes and Missed Winners page workflows and filter navigation in a real browser
LAST_COMPLETED_STEP=Project-configured backend typecheck PASS (177 source files); frontend TypeScript and ESLint PASS; backend focused tests PASS (31 passed, 2 PostgreSQL-only skipped); scoped Ruff PASS. Outcome response fields are Decimal-typed consistent with model normalization.
NEXT_STEP=npx playwright test e2e/operator-dashboard.spec.ts --project=desktop
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Full frontend Vitest 143 passed; frontend build PASS; targeted backend PASS; Playwright outcome workflow pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext browser acceptance
CURRENT_TASK=Rerun the corrected Outcomes/Missed Winners Playwright workflow assertion
LAST_COMPLETED_STEP=Project typecheck PASS: 177 source files; frontend typecheck, ESLint, Ruff and backend focus tests PASS. Desktop operator E2E ran 14 tests: 12 passed, 1 intentional skip, 1 assertion failed because it expected a data-present note in the intentionally unconfigured API state. The UI itself correctly rendered; assertion now checks the static provenance-scope note visible in all modes.
NEXT_STEP=npx playwright test e2e/operator-dashboard.spec.ts -g "pipeline and missed-winner workflows" --project=desktop
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Targeted E2E retry pending; no claim of prior failing run as PASS
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext browser acceptance
CURRENT_TASK=Rerun the Outcomes/Missed Winners browser workflow with the correct accessible label
LAST_COMPLETED_STEP=The desktop E2E reached the new route but timed out at the second select because its visible label text is overridden by `aria-label="Outcome horizon"`; this is a test locator mismatch, not a UI interaction failure. Updated the locator to the explicit accessible name. No route behavior has been counted as verified yet.
NEXT_STEP=npx playwright test e2e/operator-dashboard.spec.ts -g "pipeline and missed-winner workflows" --project=desktop
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Retry pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext full browser regression
CURRENT_TASK=Run the repository's complete Playwright command after adding Outcomes/Missed Winners route coverage
LAST_COMPLETED_STEP=Targeted desktop workflow E2E PASS (1/1) for Pipeline, Missed Winners, Outcomes, 10X/1h filtering, and explicit unverified causality. The earlier desktop operator run had 12 passed, 1 skipped, 1 failed due to test assertions; the corrected focused workflow passed. Project mypy, frontend typecheck/ESLint, scoped Ruff, and backend focused tests pass.
NEXT_STEP=npm run test:e2e
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Targeted browser workflow PASS; full responsive/accessibility + fixture browser suites pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext browser regression recovery
CURRENT_TASK=Verify the social call→token detail browser path after adding its missing hydration barrier
LAST_COMPLETED_STEP=Full main Playwright matrix PASS: 80 passed, 10 skipped across five viewport projects. Fixture social/services suite: 59 passed, 1 failed on desktop only in the recent-call tab navigation; same test passed on four other viewport projects. Its interaction lacked the existing `data-nav-hydrated=true` wait used by the adjacent claim workflow; added that wait and an `aria-selected` assertion. The focused Outcomes/Missed Winners desktop workflow passed.
NEXT_STEP=Run the recent-call→Token Detail Playwright test in isolation, then rerun the fixture suite if it passes
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Main E2E PASS; social fixture suite requires rerun after test hydration fix
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext full fixture browser acceptance
CURRENT_TASK=Rerun all social/services fixture browser tests after validating the hydration-race repair
LAST_COMPLETED_STEP=The exact previously failing desktop recent-call→Token Detail browser test now PASSes 1/1 in isolation after waiting for navigation hydration and asserting the selected tab.
NEXT_STEP=npm run test:e2e:social
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Main E2E PASS 80/90 (10 skips); isolated social navigation PASS; full fixture suite rerun pending
BLOCKERS=PostgreSQL exact-query runtime validation unavailable: MEMERADAR_TEST_DATABASE_URL absent, psql absent, Docker socket permission denied
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection recovery complete; remaining workflow acceptance
CURRENT_TASK=Continue from the verified outcome projection; next close the PostgreSQL query gate when a permitted test database is available, then reassess remaining VNext workflows against evidence
LAST_COMPLETED_STEP=Added the candidate-linked forward-outcome read path, typed API/client projections, Outcomes and Missed Winners pages, and browser coverage. Updated the recovery matrix, parity audit, delivery report, and change ledger with current results. Main Playwright matrix: 80 passed/10 skipped; full social/services fixture rerun remains host-blocked after an isolated hydration case passed.
NEXT_STEP=On a host with PostgreSQL 16 and MEMERADAR_TEST_DATABASE_URL, run `pytest -q tests/integration/test_dex_candidate_forward_outcomes_postgres.py`; independently rerun `npm run test:e2e:social` only after local listener binding is permitted
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend focus 31 passed/2 PostgreSQL skipped; frontend Vitest 143 passed; frontend lint/typecheck/build pass; project mypy 177 files and scoped Ruff pass; main Playwright 80 passed/10 skipped; focused outcome workflow 1 passed; social/services full rerun blocked by listener EPERM
BLOCKERS=PostgreSQL execution requires unavailable test database/Docker socket; real outcome rows and rule-causality require persisted data; social/services full E2E requires host permission to bind 127.0.0.1:13101
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome-to-replay workflow
CURRENT_TASK=Expose an explicit replay-at-signal action from persisted outcome rows, using only the validated signal timestamp
LAST_COMPLETED_STEP=As-of persistence replay excludes internal snapshots without independent availability timestamps and discloses this boundary. `REPLAY_UNAVAILABLE` covers missing token identity/history. The outcome table links the persisted signal timestamp to point-in-time replay. Full frontend Vitest 145/145, typecheck, ESLint, and production build pass.
NEXT_STEP=Run the main responsive/accessibility browser matrix `npm run test:e2e` in `apps/web` after the replay and outcome-link changes.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Full frontend Vitest 145/145, typecheck/lint/build PASS; focused outcome table 2/2 PASS; backend replay 32 passed/1 PostgreSQL-only skip, mypy 177 and Ruff PASS. Current browser matrix pending.
BLOCKERS=PostgreSQL runtime tests remain blocked by missing MEMERADAR_TEST_DATABASE_URL and denied Docker socket; real outcome data remains unverified
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext responsive browser failure investigation
CURRENT_TASK=Determine whether the mobile nav hydration assertion fails in the application or because the full visual matrix leaves inadequate hydration time
LAST_COMPLETED_STEP=Full Playwright command main matrix completed: 79 passed, 10 skipped, 1 failed. The sole failure was the mobile visual matrix observing `data-nav-hydrated=false` for five seconds after a route navigation; the combined command stopped before the social/services suite. Frontend 145 tests, typecheck, lint, build, backend focused 32 passed/1 skipped, Ruff, and mypy remain green.
NEXT_STEP=Run `npx playwright test e2e/visual-matrix.spec.ts --project=mobile --workers=1` with failure context to identify the route and reproduce the hydration state.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Source/unit/build gates PASS; responsive Playwright matrix FAIL 79/1/10; focused reproduction pending
BLOCKERS=PostgreSQL runtime remains unavailable; fixture browser suite did not start because main Playwright command failed; hydration failure root cause not yet established
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext full browser regression
CURRENT_TASK=Rerun the responsive matrix and social/services fixture suite after isolated mobile navigation passes
LAST_COMPLETED_STEP=The focused `npx playwright test e2e/visual-matrix.spec.ts --project=mobile --workers=1` passed 1/1 after the full matrix's transient hydration timeout, so no product-code change is warranted yet.
NEXT_STEP=Run `npm run test:e2e` in `apps/web` to rerun the five-viewport matrix and chained social/services fixture suite.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused visual matrix 1/1 PASS; full responsive matrix prior run 79 passed/10 skipped/1 failed; full chained browser rerun pending
BLOCKERS=PostgreSQL runtime remains unavailable; if the fixture server cannot bind, classify only the fixture browser gate as host-blocked
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext fixture navigation failure investigation
CURRENT_TASK=Reproduce the recent-call-to-token navigation failure outside the parallel fixture matrix
LAST_COMPLETED_STEP=Full `npm run test:e2e` rerun: main responsive matrix PASS (80 passed, 10 skipped); fixture matrix 59 passed/1 failed. Desktop recent-call row and action rendered with canonical token identity; no TOKEN DETAIL UNAVAILABLE status appeared, but URL remained `/social-alpha` past Playwright's 5-second route assertion.
NEXT_STEP=Run `npx playwright test --config=playwright.social-alpha.config.ts e2e/social-alpha.spec.ts -g "recent calls resolve canonical chain identity" --project=desktop --workers=1` to distinguish route regression from parallel-load timeout.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Full main E2E PASS 80/90; fixture E2E PARTIAL 59/60; focused browser reproduction pending
BLOCKERS=PostgreSQL runtime remains unavailable; one fixture navigation result is unverified under isolated rerun
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext fixture browser acceptance
CURRENT_TASK=Rerun the full social/services fixture matrix with a bounded wait for the token route's client-side transition
LAST_COMPLETED_STEP=The exact desktop recent-call-to-token test passes 1/1 in isolation. The full fixture failure is load-sensitive: the click and canonical result are present; the previous 5-second URL assertion expired only under parallel matrix load. Increased this one navigation assertion to 15 seconds; product behavior is unchanged.
NEXT_STEP=Run `npm run test:e2e:social` in `apps/web` and record the exact fixture matrix result.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Main E2E PASS 80 passed/10 skipped; isolated fixture case PASS 1/1; fixture matrix rerun pending
BLOCKERS=PostgreSQL runtime remains unavailable; fixture E2E acceptance pending bounded navigation wait
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext recovery evidence reconciliation
CURRENT_TASK=Update recovery, parity, and change-ledger records with verified replay behavior and the final browser outcomes
LAST_COMPLETED_STEP=Point-in-time replay now excludes internal snapshots without independent availability timestamps, discloses the limit, and shows REPLAY_UNAVAILABLE on unavailable reads. Outcome rows link signal time to replay. Main Playwright rerun PASS 80/90 (10 skips); fixture matrix 59/60 with one desktop navigation timeout; exact case PASS 1/1 isolated. After a bounded test timeout change, fixture rerun was blocked before execution by host `listen EPERM` on 127.0.0.1:13101.
NEXT_STEP=Reconcile the durable VNext reports, then run frontend `npm run typecheck`, `npm run lint`, and scoped `git diff --check`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend Vitest 145/145; frontend typecheck/lint/build pass before latest test-only timeout adjustment; backend 32 passed/1 PostgreSQL skip; main browser matrix pass; fixture browser matrix partial/host-blocked on rerun
BLOCKERS=PostgreSQL exact query execution unavailable; fixture server listener is currently denied; no real outcome rows or decision-to-outcome causality verified
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext point-in-time decision evidence gap
CURRENT_TASK=Determine whether internal state/score/risk history already has trustworthy availability timestamps that can be joined into replay without a schema change
LAST_COMPLETED_STEP=Recovery/parity/final/ledger reports now reconcile the 145-test Vitest result, 32-pass backend focus, clean main Playwright rerun, fixture partial result, replay omission semantics, signal-time replay link, and host-blocked fixture rerun. Frontend typecheck and ESLint pass after the test-only navigation timeout change; scoped diff check passes.
NEXT_STEP=Trace the existing timeline query and persistence write paths for state transitions, features, risk, scores, and alerts; only extend replay if the repository already records admissible observed/ingested timestamps.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend Vitest 145/145; typecheck/lint/build PASS; backend focus 32 passed/1 PostgreSQL-only skip; Ruff/mypy PASS; main Playwright 80 passed/10 skipped; fixture Playwright 59 passed/1 failed (isolated case 1/1 pass; timeout adjustment rerun blocked at fixture listener startup); diff-check PASS
BLOCKERS=PostgreSQL runtime/data validation unavailable; fixture host listener currently denied; existing internal snapshot availability-time semantics under audit before any replay expansion
UPDATED_AT=2026-10-08

## Frontend VNext recovery checkpoint — timeline provenance fix in progress (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Represent unavailable internal timeline observed/ingested timestamps as UNKNOWN and exclude such rows from point-in-time replay
LAST_COMPLETED_STEP=Recovery confirmed the failing regression tests and traced false availability timestamps to internal persistence mappers; source observations retain persisted timestamps.
NEXT_STEP=Update application/API/frontend timeline contracts and internal timeline mappers, then rerun focused regression tests.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Expected RED observed for persistence mapping and in-memory replay tests; implementation not yet applied.
BLOCKERS=.codex checkpoint files could not be written because that directory is host-mounted read-only; use this documentation checkpoint. PostgreSQL runtime is unavailable; internal snapshot replay remains unsupported without independent availability timestamps.
UPDATED_AT=2026-10-08

## Frontend VNext timeline provenance checkpoint — focused regressions green (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Run focused read contract/persistence regressions and static validation after making unknown availability explicit.
LAST_COMPLETED_STEP=Timeline read model/API/client accept NULL availability; internal history mappers set observed/ingested to unknown; replay excludes those rows. Focused backend regressions: 3 passed; typed frontend parser regression: 1 passed.
NEXT_STEP=Run complete focused read API/persistence modules and frontend read-api, token-detail, and compare tests, followed by type/lint checks.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused backend regressions PASS 3/3; frontend parser regression PASS 1/1. Broader targeted suites pending.
BLOCKERS=.codex checkpoint files are unavailable because .codex is host-mounted read-only; durable record is in docs/reports/agentic-loop/frontend-vnext-recovery-checkpoint.md and docs/STATUS.md. PostgreSQL runtime unavailable.
UPDATED_AT=2026-10-08

## Frontend VNext timeline provenance checkpoint — focused suites complete (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Finish static validation and reconcile reports for the timeline availability contract.
LAST_COMPLETED_STEP=Targeted read-path tests passed: backend 42/42 (`test_read_api.py`, `test_read_api_routes.py`, `test_read_persistence.py`); frontend 59/59 (`read-api`, `token-detail`, `compare`); scoped Ruff passed. Frontend `npm run typecheck` exited 0, with three host `Failed to create stream fd: Operation not permitted` notices.
NEXT_STEP=Run frontend lint and project Python typecheck; inspect scoped diff and update recovery/parity/final docs with the corrected timestamp semantics.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused suites and Ruff PASS; frontend typecheck exit 0 (host stream notices); frontend lint and Python mypy pending.
BLOCKERS=.codex is host-mounted read-only; documentation checkpoints are used. PostgreSQL remains unavailable for database execution acceptance.
UPDATED_AT=2026-10-08

## Frontend VNext timeline provenance checkpoint — source-observation caller correction (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Revalidate Python typing after changing wallet activity mapping to read its required availability timestamps from the non-null ObservationRow source.
LAST_COMPLETED_STEP=Project typecheck caught a caller using nullable TimelineEntryView availability in WalletActivityView. The mapping now uses non-null ObservationRow.observed_at/ingested_at; original source semantics are preserved.
NEXT_STEP=Rerun `make typecheck`, then run frontend lint/typecheck and update the parity/recovery report.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused backend 42 passed; frontend 59 passed; Ruff passed; frontend typecheck passed, lint passed; Python mypy fix pending validation.
BLOCKERS=.codex is host-mounted read-only; documentation checkpoints are used. PostgreSQL remains unavailable.
UPDATED_AT=2026-10-08

## Frontend VNext timeline provenance checkpoint — static checks complete (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Run the full frontend unit suite and production build for current-tree acceptance.
LAST_COMPLETED_STEP=Python typecheck now passes for 177 files; frontend typecheck exits 0 and lint exits 0; focused frontend 59 and backend 42 tests pass; Ruff passes. Wallet activity continues to take required non-null timestamps from ObservationRow directly.
NEXT_STEP=Run full `npm test -- --run` and `npm run build` in `apps/web`; then inspect scoped diffs and reconcile reports.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused backend 42/42; focused frontend 59/59; Ruff PASS; mypy 177 files PASS; frontend typecheck/lint PASS. Full frontend Vitest/build pending.
BLOCKERS=.codex is host-mounted read-only; documentation checkpoints are used. PostgreSQL remains unavailable.
UPDATED_AT=2026-10-08

## Frontend VNext timeline provenance checkpoint — full frontend tests pass (2026-10-08)

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext timeline provenance correctness
CURRENT_TASK=Run the production frontend build and reconcile final evidence.
LAST_COMPLETED_STEP=Full frontend Vitest PASS: 146 passed across 32 files after the nullable timeline availability change.
NEXT_STEP=Run `npm run build` in apps/web; then review scoped diff and update parity/recovery/final reports.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend 146/146; focused backend 42/42; scoped Ruff PASS; mypy 177 files PASS; frontend typecheck/lint PASS. Build pending.
BLOCKERS=.codex is host-mounted read-only; documentation checkpoints are used. PostgreSQL remains unavailable.
UPDATED_AT=2026-10-08

## Frontend VNext PostgreSQL acceptance environment changed — 2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection database acceptance
CURRENT_TASK=Use an isolated disposable PostgreSQL 16 container for the skipped outcome projection integration tests.
LAST_COMPLETED_STEP=Full frontend Vitest 146/146; production build, frontend lint/typecheck, Ruff, and mypy 177 files pass. Current host now reports Docker 29.1.3 usable, `/var/run/docker.sock` present, and local `postgres:16-alpine` image present. Existing Compose services, including the repository PostgreSQL container, are running and will not be changed.
NEXT_STEP=Start a unique ephemeral Postgres 16 container bound only to localhost with a tmpfs data directory; migrate it to current head and run the two outcome PostgreSQL integration cases.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Frontend full/build PASS; backend focused read suites 42/42 and contract tests 3 pass; PostgreSQL tests previously skipped only due unset URL.
BLOCKERS=.codex is host-mounted read-only; durable docs checkpoints used. Do not touch or migrate the existing Compose database.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection database acceptance
CURRENT_TASK=Run current Alembic head on disposable local PostgreSQL 16, then validate persisted outcomes and exact JSON equality.
LAST_COMPLETED_STEP=Started a separate PostgreSQL 16.15 container using tmpfs and local-only published port 32769; no existing Compose database/container was touched. Container is ready.
NEXT_STEP=Execute `MEMERADAR_DATABASE_URL='postgresql+asyncpg://mr_vnext:mr_vnext_ephemeral_only@127.0.0.1:32769/mr_vnext' .venv/bin/python -m alembic -c alembic.ini upgrade head`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current fresh PostgreSQL migration and outcome integration tests pending; previous test invocation skipped two cases due unset URL.
BLOCKERS=.codex is host-mounted read-only; use docs checkpoint. Existing Compose database remains out of scope and untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection database acceptance
CURRENT_TASK=Run current-tree migration and PostgreSQL tests in a throwaway container because host Python sockets are denied.
LAST_COMPLETED_STEP=Host migration attempt reached Python socket creation and failed with `PermissionError: [Errno 1] Operation not permitted`; this is a host sandbox restriction. Docker daemon/container execution works, and the existing API image has pytest 9.0.3.
NEXT_STEP=Attach only the disposable Postgres container to `compose_default`, then run Alembic and outcome tests inside throwaway `compose-api` image containers with current worktree mounted read-only. Do not connect to existing Compose Postgres.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current-tree DB migration not yet verified. All previously listed source/unit/frontend checks remain passing.
BLOCKERS=.codex is host-mounted read-only. Host-process TCP sockets are denied; container-local DB validation workaround is available.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome projection database acceptance
CURRENT_TASK=Run persisted outcome integration tests in the isolated PostgreSQL 16 database.
LAST_COMPLETED_STEP=Current-tree Alembic `upgrade head` succeeded when run in a disposable API-image container using the current repository mounted read-only and the tmpfs Postgres instance on a private Compose bridge network. Host Python socket restriction was worked around without touching repository Compose Postgres.
NEXT_STEP=Run the two candidate-linked outcome PostgreSQL integration tests against the migrated disposable database, then verify migration revision.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Fresh PostgreSQL migration PASS; outcome persistence/exact-target integration tests pending.
BLOCKERS=.codex is host-mounted read-only; use docs checkpoints. Existing Compose database/container remains untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome integration failure investigation
CURRENT_TASK=Determine whether the PostgreSQL idempotent outcome replay test failure is a projection bug or a stale test assumption.
LAST_COMPLETED_STEP=Disposable PostgreSQL 16 current-head migration PASS. PostgreSQL integration tests ran against the current read-only worktree: exact JSON target membership test PASS; outcome persistence/replay test failed at test line 284 because query returned 2 rows where test expected 1.
NEXT_STEP=Inspect the failing assertion and collector payload/horizon semantics, then make the smallest correct test or implementation fix and rerun this isolated integration file.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Fresh migration PASS; Postgres integration 1 passed/1 failed. Failure details preserved: `assert 2 == 1` in `_exercise` line 284.
BLOCKERS=.codex read-only. Disposable PostgreSQL is still available; existing Compose DB remains untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext point-in-time replay integrity
CURRENT_TASK=Validate processing-time provenance for runtime stage snapshots and fail-closed replay of legacy snapshots.
LAST_COMPLETED_STEP=PostgreSQL 16 current-head migration reached `0018_stream_gap_provider_id (head)`. Both candidate-linked outcome integration tests pass against the disposable database: exact JSON scalar equality and idempotent persistence of the 30s/1m horizons. A delayed-evaluation unit regression and PostgreSQL replay integration regression now cover runtime snapshot availability and legacy parser exclusion.
NEXT_STEP=Run the new EarlyRuntime unit regression and focused read persistence tests, then run both PostgreSQL integration files against a fresh isolated PostgreSQL 16 instance.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Fresh PostgreSQL 16 migration PASS; forward outcome PostgreSQL integration 2/2 PASS; new runtime/replay regressions pending execution.
BLOCKERS=.codex checkpoint files are absent/read-only. Host Python sockets are denied; Docker API-image workaround validated the database safely. No external live outcome data was read.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext outcome integration validation
CURRENT_TASK=Correct the PostgreSQL outcome fixture to cover every horizon due at its evaluation time and rerun the isolated integration tests.
LAST_COMPLETED_STEP=Confirmed the collector legitimately emits both 30s and 1m outcomes at `signal_at + 1m`; the integration fixture only had a 1m market endpoint. Exact JSON scalar membership remains validated on PostgreSQL.
NEXT_STEP=Add a timestamped 30s market observation and assert idempotent persistence for both due horizons, then run the isolated PostgreSQL integration file in a throwaway API image container.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Fresh PostgreSQL 16 migration PASS; exact JSON target membership PASS; persistence horizon fixture correction and rerun pending.
BLOCKERS=.codex checkpoint paths absent/read-only. Host Python TCP sockets are denied; use current existing Docker network and isolated tmpfs PostgreSQL only. Existing Compose PostgreSQL remains untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext point-in-time replay integrity
CURRENT_TASK=Fix the compatibility clock for out-of-order replay, then re-run the runtime and read-path regressions.
LAST_COMPLETED_STEP=The delayed-evaluation unit regression passes. The broader runtime suite found that an older out-of-order event may have a decision checkpoint behind the candidate's persisted state time; the default availability fallback now includes both detection first-seen and candidate state-change timestamps. Explicit earlier processed_at values still fail closed.
NEXT_STEP=Rerun `tests/unit/test_early_runtime.py`, `tests/unit/test_read_api.py`, `tests/unit/test_read_api_routes.py`, and `tests/unit/test_read_persistence.py`; then run isolated PostgreSQL replay integration.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=New delayed-evaluation test PASS; combined 60-test focused run had 1 existing out-of-order replay failure before the fallback correction. Full rerun pending.
BLOCKERS=.codex checkpoint files are absent/read-only. Database tests require the disposable container workaround; existing Compose PostgreSQL remains untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext PostgreSQL replay acceptance
CURRENT_TASK=Validate runtime snapshot availability and legacy-snapshot exclusion on PostgreSQL 16.
LAST_COMPLETED_STEP=The corrected focused read/runtime suite passed: 60 tests, 5 FastAPI/Starlette deprecation warnings. The delayed processed_at regression and out-of-order replay regression both pass.
NEXT_STEP=Start a dedicated tmpfs PostgreSQL 16 container, run Alembic upgrade head, then execute `tests/integration/test_early_runtime_persistence.py` and `tests/integration/test_dex_candidate_forward_outcomes_postgres.py` in throwaway API-image containers.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Python read/runtime suite PASS 60/60; current PostgreSQL integration pending.
BLOCKERS=.codex checkpoint paths are absent/read-only; host Python TCP remains denied. No application database will be touched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext PostgreSQL replay acceptance
CURRENT_TASK=Run the current-tree runtime timeline and forward-outcome integration tests on isolated PostgreSQL 16.
LAST_COMPLETED_STEP=Disposable PostgreSQL 16 is ready. Current Alembic migration `upgrade head` passed and `alembic current` reports `0018_stream_gap_provider_id (head)`.
NEXT_STEP=Run `tests/integration/test_early_runtime_persistence.py tests/integration/test_dex_candidate_forward_outcomes_postgres.py` in a throwaway API-image container with the current repository mounted read-only.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Fresh PostgreSQL current-head migration PASS; current-tree integration run pending.
BLOCKERS=.codex checkpoint files remain unavailable; current isolated PostgreSQL stays on tmpfs. Existing Compose PostgreSQL is untouched.
UPDATED_AT=2026-10-08

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext replay and outcome acceptance
CURRENT_TASK=Run static validation and the replay UI regression after the runtime availability fix.
LAST_COMPLETED_STEP=Disposable PostgreSQL 16 fresh migration passed at `0018_stream_gap_provider_id (head)`. Current-tree PostgreSQL integration passed 4/4 across early-runtime persistence/replay and candidate outcome persistence/exact target filtering. The current replay now includes only versioned early-stage observations whose observed/ingested times meet the cutoff; legacy v1 stage snapshots are excluded.
NEXT_STEP=Run focused Token Detail replay tests, Ruff on touched Python paths, `make typecheck`, frontend typecheck, and frontend lint.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused backend unit read/runtime 60/60 PASS; PostgreSQL integration 4/4 PASS; frontend replay-copy regression and static validation pending.
BLOCKERS=.codex checkpoint files are absent/read-only. Browser E2E was not rerun because the previous fixture listener denial condition has not changed. Real outcomes and causal evidence remain unavailable.
UPDATED_AT=2026-10-08

## Frontend VNext replay continuation — 2026-10-08

The interrupted recovery is continuing on `main` at `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`; the extensive pre-existing dirty worktree remains intact. This slice removes caller-sampled `processed_at` timestamps from four worker entry points so the shared runtime records stage-snapshot availability after feature/scoring/decision work; the idempotent restart unit fixture now supplies a stable processing timestamp. No database was changed. Validation is pending: focused early-runtime/read-path tests, scoped Ruff and project typecheck. The exact next command is recorded in `docs/reports/agentic-loop/frontend-vnext-recovery-checkpoint.md`.

## Frontend VNext replay verification — 2026-10-08

After moving worker availability sampling into `EarlyRuntimeService`, the focused current-tree command `.venv/bin/python -m pytest -q tests/unit/test_early_runtime.py tests/unit/test_read_api.py tests/unit/test_read_api_routes.py tests/unit/test_read_persistence.py --tb=short` passed **60 tests** with 5 FastAPI/Starlette deprecation warnings. PostgreSQL runtime acceptance is being rechecked in an isolated disposable database; no configured production/runtime DB was queried.

## Frontend VNext browser regression — 2026-10-08

On the current post-restart host, the configured main Playwright matrix completed instead of hitting the prior listener restriction: **78 passed, 10 skipped, 2 failed** across viewport projects in 7.5 minutes. Failures: tablet-width mobile navigation could not focus the first drawer link, and mobile visual-matrix waited for `data-nav-hydrated=true` but read `false`. The chained social-alpha suite did not run because the main suite exited nonzero. See the recovery checkpoint for the exact next action; this status is not an E2E pass.

## Frontend VNext navigation fix — 2026-10-08

The nav hydration marker used `useSyncExternalStore` with a no-op subscription and constant client/server snapshots. It now uses a mount effect/state flag. Current verification: shell unit **5/5**; isolated tablet focus-trap Playwright **1/1**; mobile responsive visual route matrix **1/1** across all listed routes and both themes. The full main matrix is not yet rerun after the fix; its prior two failures are individually passing. The independent social/services fixture suite is now being run.

## Frontend VNext recovery — final local verification — 2026-10-08

The interrupted candidate-linked outcome projection and point-in-time replay corrections are complete on the current dirty tree. Outcome target matching and persistence/replay passed four current-tree PostgreSQL 16 integration tests on a disposable database migrated to `0018_stream_gap_provider_id (head)`; no configured runtime/production database was queried. Token market small multiples now use timestamp-scaled shared UTC X coordinates and chronological ordering, with separate Y scales; a regression failed before the fix and passes after it.

Current frontend evidence: Vitest 147/147, ESLint PASS, TypeScript PASS (host emitted stream-fd `EPERM` notices but exited 0), production build PASS, main Playwright PASS 80 with 10 intentional skips and 0 failures across five viewport projects. The mobile responsive route/theme matrix passed 1/1. Focused backend read/runtime/API tests passed 60/60; runtime/worker passed 44/44; Ruff passed on touched Python paths; project mypy checked 177 files. The separate social/services fixture suite was blocked before execution on `127.0.0.1:13101` (`listen EPERM`). A bounded production-server smoke was also blocked before tests: the host denied its `127.0.0.1:13100` listener (`listen EPERM`); the production build itself passed.

Remaining product/data gaps: no real mature outcome rows or validated causal misses; no rule-impact/counterfactual or matched-control projections; no global REAL/MOCK switch; pipeline counts remain page-local; full replay cannot reconstruct standalone internal state/score/risk/alert rows without availability timestamps; the chart lacks selectable overlays and decision markers. VNext remains partially verified, not alpha-validated. Detailed matrix and evidence: `docs/reports/FRONTEND_VNEXT_RECOVERY.md`, `docs/reports/FRONTEND_VNEXT_FINAL.md`, and `docs/audits/FRONTEND_BACKEND_PARITY.md`.

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext shutdown recovery
CURRENT_TASK=Revalidate all frontend gates after the historical decision panel and resume the main browser matrix.
LAST_COMPLETED_STEP=Focused Token Detail passed 14/14; full Vitest passed 148/148 across 32 files; typecheck, ESLint, and production build passed (28 routes compiled).
NEXT_STEP=Run `npx playwright test` in `apps/web` and record exact passed/skipped/failed counts and viewport projects.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current Token Detail 14/14, full frontend 148/148, typecheck, lint, and build PASS. Typecheck output included host stream-fd EPERM notices but exited 0. Final-source main Playwright is now running; older 80/10 is not accepted for this tree.
BLOCKERS=Full main Playwright result unknown and must be rerun. Social/services and production-server E2E were previously host-blocked at ports 13101/13100; retry only after host permission changes. Real mature outcomes and causal misses remain unavailable.
UPDATED_AT=2026-10-08 21:00 UTC

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext shutdown recovery and Decision Inspector closure
CURRENT_TASK=Disclose unavailable historical thresholds in the Decision Inspector.
LAST_COMPLETED_STEP=Current-tree Playwright completed 80 passed, 10 intentionally skipped, 0 failed across five viewport projects; threshold regression failed first and passed with the one-row disclosure. Focused Token Detail is 14/14, full frontend Vitest 148/148, typecheck, lint and production build pass (28 routes).
NEXT_STEP=Run `npx playwright test` in `apps/web` against this exact UI tree and capture counts, skips, duration and projects.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail 14/14, full frontend 148/148, typecheck, lint, and build PASS after threshold disclosure. Typecheck exited 0 with host stream-fd EPERM notices. Final-tree browser gate pending; prior post-panel tree passed 80/10/0 Playwright.
BLOCKERS=Historical numeric decision thresholds are not persisted, so actual/required deltas cannot be truthfully displayed. No real mature outcome rows or causally proven missed winners are available. Rule-impact/matched-control projections remain unsupported.
UPDATED_AT=2026-10-08 21:05 UTC

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext final-tree verification and parity reconciliation
CURRENT_TASK=Reconcile all recovery, parity, ledger, status, and delivery evidence after the historical threshold disclosure.
LAST_COMPLETED_STEP=Threshold disclosure is covered by Token Detail 14/14 and full Vitest 148/148; typecheck, lint, build (28 routes), and final-tree Playwright 80 passed/10 intentional skips/0 failed across five projects in 7.9 minutes passed. Scoped diff check passed.
NEXT_STEP=Recompute the frontend parity gap matrix, inspect the next locally actionable evidence gap, and finish exact-tree status/hash verification.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current threshold-disclosure tree: Token Detail 14/14; frontend 148/148/32 files; typecheck, lint, build, and main Playwright PASS. Typecheck had host stream-fd EPERM notices but exited 0. Scoped `git diff --check -- . ':!.env.example'` PASS.
BLOCKERS=Separate social/services and standalone production-browser suites cannot bind host ports 13101/13100. Real mature outcomes, missed-winner causality, rule-impact/matched-control evidence, full global funnel, and complete historical thresholds are unavailable in persisted data.
UPDATED_AT=2026-10-08 21:18 UTC

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext score explainability
CURRENT_TASK=Expose persisted historical score-snapshot components and penalties in Token Detail.
LAST_COMPLETED_STEP=The Decision Inspector shows threshold UNAVAILABLE plus persisted config/score versions. A new test-first score-explainer regression fails because persisted `score.snapshot` details are hidden (1 failed, 14 passed).
NEXT_STEP=Add the allow-listed early-alpha score/penalty breakdown and rerun Token Detail.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Prior exact UI tree 14/14 focused, 148/148 frontend, typecheck/lint/build PASS, Playwright 80/10/0 PASS. New score-explainer regression is red as expected.
BLOCKERS=Real outcomes/cause/matched-controls unavailable; numeric historical policy thresholds absent; alert/state/score rows lack independent observed/ingested timestamps for point-in-time replay.
UPDATED_AT=2026-10-08 21:31 UTC

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext Decision Inspector provenance
CURRENT_TASK=Expose persisted decision-config and score versions in the historical decision snapshot.
LAST_COMPLETED_STEP=Threshold disclosure and version rows are implemented; Token Detail is 14/14, full Vitest 148/148, typecheck, lint, and production build pass (28 routes).
NEXT_STEP=Run `npx playwright test` in `apps/web` on the exact version-disclosure tree and record counts, skips, duration, and projects.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail 14/14, full frontend 148/148, typecheck, lint, and build PASS after version disclosure. Typecheck exited 0 with host stream-fd EPERM notices. Final-tree Playwright pending; previous tree passed 80/10/0.
BLOCKERS=Numeric historical thresholds are not persisted; show UNAVAILABLE. No real mature outcomes or causal miss/rule-impact/matched-control evidence.
UPDATED_AT=2026-10-08 21:18 UTC

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext historical score explanation
CURRENT_TASK=Verify the allow-listed historical early-alpha score-snapshot panel.
LAST_COMPLETED_STEP=Score component/penalty rendering was implemented after a focused regression failed as expected; it does not show arbitrary payload fields and does not imply probability calibration.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` from `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current score-snapshot patch pending focused validation. Prior exact UI tree passed 148/148 frontend tests and Playwright 80/10/0; prior typecheck, lint, and build passed.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext historical score explanation
CURRENT_TASK=Rerun Token Detail after aligning the score-component assertion with uppercase labels.
LAST_COMPLETED_STEP=The score panel rendered expected persisted evidence; first test run only disagreed on capitalization of an existing uppercase UI label. Adjusted the assertion.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` from `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Initial current focused run 14/15 due to label case expectation, not missing UI behavior. Rerun pending.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext historical score explanation
CURRENT_TASK=Verify explicit UNKNOWN and omitted-key behavior in the score panel.
LAST_COMPLETED_STEP=Token Detail passed 15/15; added assertions for an unavailable on-chain-safety component and for omitted unknown penalty keys.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` from `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current focused rerun pending after assertion-only coverage additions.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext score explanation verification
CURRENT_TASK=Run full frontend unit, TypeScript, and lint gates on the score snapshot change.
LAST_COMPLETED_STEP=Focused Token Detail 15/15 PASS, including persisted score versions, allow-listed component/penalty details, UNKNOWN missing inputs, and secret-like arbitrary payload omission.
NEXT_STEP=Run `npm test`, `npm run typecheck`, and `npm run lint` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail current-tree PASS 15/15. Full unit/type/lint/build/browser gates pending.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext score explanation verification
CURRENT_TASK=Run production frontend build after full unit/type/lint gates.
LAST_COMPLETED_STEP=Full Vitest 149/149 across 32 files; typecheck and lint exit 0. Typecheck included host stream-fd EPERM notices but succeeded.
NEXT_STEP=Run `npm run build` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail 15/15; full frontend 149/149; typecheck and lint PASS. Build and Playwright pending.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext score explanation browser acceptance
CURRENT_TASK=Run full main Playwright matrix on the score snapshot panel tree.
LAST_COMPLETED_STEP=Production build exit 0, with all 28 App Router routes generated.
NEXT_STEP=Run `npx playwright test` in `apps/web`; record exact counts, duration, projects, and exit status.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail 15/15, full frontend 149/149, typecheck, lint, build PASS. Exact-tree browser regression pending.
BLOCKERS=No real mature outcomes, confirmed miss causality, rule-impact aggregation, or matched controls. Historical numeric thresholds are not persisted.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext remaining evidence-surface audit
CURRENT_TASK=Recompute the next highest-value local UI gap after score explanation.
LAST_COMPLETED_STEP=Early-alpha score explanation verified: Token Detail 15/15; full Vitest 149/149; typecheck, lint, build exit 0; main Playwright 80/10/0 across five viewports.
NEXT_STEP=Inspect timeline read contracts, persistence mappings, and Token Detail chart series for safe additional selectable overlays.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Score explanation gates pass; final scoped diff-check after documentation updates remains pending.
BLOCKERS=Real mature outcomes, confirmed miss causality, rule impact, matched controls, historical numeric thresholds, and host-blocked social/production browser tests.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence disclosure
CURRENT_TASK=Verify a safe provenance disclosure in the token timeline.
LAST_COMPLETED_STEP=Timeline API already provides event/observed/ingested times, quality, evidence references, and provider/parser provenance. New test checks interaction and excludes raw payload.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` in `apps/web` to confirm the missing-disclosure failure.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Score-explainer gates pass as documented. New provenance-disclosure regression pending.
BLOCKERS=Other score families, global funnel, historical thresholds, causality, matched controls, real outcomes, and separate host-blocked browser suites remain.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence disclosure
CURRENT_TASK=Run focused Token Detail regression after adding typed provenance details.
LAST_COMPLETED_STEP=Red test confirmed the provider/time evidence control was missing; implemented a native disclosure for timestamps, data quality, evidence refs, provider/source IDs, and parser version. It does not access raw payload.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Provenance disclosure test is pending verification.
BLOCKERS=Source endpoints/latency are not provided by the current read model; mature outcomes and causal/matched analysis remain unavailable.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence disclosure
CURRENT_TASK=Rerun focused Token Detail suite after narrowing a duplicated source-ID assertion.
LAST_COMPLETED_STEP=Disclosure tests passed; one unrelated assertion became ambiguous because a source ID is now correctly shown in both timeline provenance and social evidence. Scoped it to the social panel.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=First run 15 passed/1 failed from ambiguous query; rerun pending.
BLOCKERS=No source endpoint/latency projection, real outcome maturity, or causal/matched data.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence verification
CURRENT_TASK=Run full frontend unit, type, and lint gates after timeline provenance disclosure.
LAST_COMPLETED_STEP=Focused Token Detail 16/16 PASS; disclosure interaction and safe-field checks pass.
NEXT_STEP=Run `npm test`, `npm run typecheck`, and `npm run lint` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused current tree 16/16; full frontend/type/lint/build/browser checks pending.
BLOCKERS=Provider endpoint/latency remains unprojected; real mature outcomes and causal/matched evidence unavailable; standalone browser gates host-blocked.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence verification
CURRENT_TASK=Run production build on the provenance disclosure tree.
LAST_COMPLETED_STEP=Focused Token Detail 16/16, full Vitest 150/150, typecheck exit 0, and ESLint exit 0.
NEXT_STEP=Run `npm run build` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Unit/type/lint PASS; build and exact-tree Playwright pending.
BLOCKERS=Provider endpoint/latency absent from current contract; real mature outcomes and causal/matched data unavailable; separate browser server gates host-blocked.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext provider evidence browser acceptance
CURRENT_TASK=Run full main Playwright after timeline provenance disclosure.
LAST_COMPLETED_STEP=Production build exit 0, all 28 routes generated.
NEXT_STEP=Run `npx playwright test` in `apps/web` and capture exact counts, duration, projects, and exit code.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Unit 150/150, focused 16/16, typecheck/lint/build pass; browser pending.
BLOCKERS=Separate production-server/social fixture browser gates remain host-blocked; real outcome and causal/matched evidence unavailable.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext post-recovery parity audit
CURRENT_TASK=Recompute remaining actionable gaps after score and provenance disclosure.
LAST_COMPLETED_STEP=Token Detail 16/16, full frontend 150/150, typecheck/lint/build exit 0, and Playwright 80 passed/10 intentional skips/0 failed across five viewport projects; current review of provider disclosure remains partial because endpoint/latency are absent.
NEXT_STEP=Inspect current parity and recovery matrix for another data-backed local workflow that can be closed safely.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=All current frontend code gates pass; scoped diff-check must be rerun after final docs.
BLOCKERS=Real mature outcomes, confirmed miss causality, rule impact/matched controls, numeric historic thresholds, missing API evidence fields, and host-blocked separate browser suites.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext trajectory evidence expansion
CURRENT_TASK=Add data-backed market-cap and five-minute volume trajectory series.
LAST_COMPLETED_STEP=Timeline observations expose normalized `market_cap` and `volume_5m_usd`; newest provenance-disclosure tree passed 150/150 frontend and Playwright 80/10/0.
NEXT_STEP=Run the focused Token Detail suite to observe the new optional-chart test fail before implementation.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current code green before new trajectory test; test now pending.
BLOCKERS=Other requested time-series (wallet independence, bundle remaining, risk and decisions) are unavailable as independently time-stamped chart fields; real outcomes/causality remain unavailable.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext trajectory evidence expansion
CURRENT_TASK=Verify optional market-cap and five-minute volume charts.
LAST_COMPLETED_STEP=Added collapsed overlay charts for persisted `market_cap` and normalized `volume_5m_usd`, using the same UTC event-time range as existing charts.
NEXT_STEP=Run `npm test -- src/app/components/token-detail.test.tsx` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current overlay implementation pending focused test.
BLOCKERS=Other requested overlays lack verified independently time-stamped chart fields; true outcomes and causality remain unavailable.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext trajectory verification
CURRENT_TASK=Run full frontend unit, type, and lint gates on market-cap/volume trajectory change.
LAST_COMPLETED_STEP=Token Detail 17/17 PASS with the new optional market-cap and 5m volume chart regression.
NEXT_STEP=Run `npm test`, `npm run typecheck`, and `npm run lint` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused suite PASS; full suite/type/lint/build/browser pending.
BLOCKERS=Other overlay families lack timestamped canonical values; real outcome/causality/matched analysis unavailable; separate server e2e host blocked.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext trajectory verification
CURRENT_TASK=Run the production frontend build on the market-cap/volume trajectory tree.
LAST_COMPLETED_STEP=Full Vitest 151/151, TypeScript exit 0, ESLint exit 0, focused Token Detail 17/17.
NEXT_STEP=Run `npm run build` in `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Unit/type/lint PASS; build and browser pending.
BLOCKERS=Only fields with available timestamped persistence were plotted; further requested metrics lack chart contract. Data/host blockers remain.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext trajectory browser acceptance
CURRENT_TASK=Run the main Playwright matrix after trajectory expansion.
LAST_COMPLETED_STEP=Production build exit 0 with all 28 routes generated.
NEXT_STEP=Run `npx playwright test` in `apps/web` and record exact matrix result.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused 17/17, full Vitest 151/151, typecheck/lint/build PASS; browser pending.
BLOCKERS=Social fixture and production standalone listeners remain host-blocked; real outcome/causality data unavailable.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext final parity and evidence reconciliation
CURRENT_TASK=Review remaining gaps and run final diff/checkpoint reconciliation.
LAST_COMPLETED_STEP=Token Detail 17/17; full Vitest 151/151; typecheck/lint/build pass; main Playwright 80 passed, 10 intentional skips, 0 failures across five viewports in 7.9 minutes. Added score, provider/time, market-cap and 5m-volume evidence disclosures.
NEXT_STEP=Review the current parity matrix for locally actionable gaps, then rerun scoped diff-check and finalize current-tree evidence.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=All current frontend code gates pass; run final `git diff --check -- . ':!.env.example'` after docs edits.
BLOCKERS=Real outcome maturity, causality, rule impact/matched controls, historical thresholds, remaining unsurfaced time-series fields, and host-blocked social/production browser suites.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext remaining evidence-surface audit
CURRENT_TASK=Inspect the next persisted trajectory metric with safe point-in-time semantics.
LAST_COMPLETED_STEP=Participant expansion trajectory overlay passed focused Token Detail 24/24, full frontend 158/158, typecheck/lint/build, and main Playwright 80 passed/10 intentional skips/0 failed across five viewport projects in 7.9 minutes with two workers.
NEXT_STEP=Audit persisted one-minute sell-absorption snapshot fields and add the overlay only if scope, missing-data, timing, and non-causal semantics are explicit.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused Token Detail 24/24; full frontend 158/158 across 32 files; typecheck/lint/build exit 0 (28 routes); final-tree Playwright 80 passed, 10 intentional skips, 0 failed in 7.9m, exit 0.
BLOCKERS=Legacy v1/v2 snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration is skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites remain blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext sell-absorption trajectory evidence
CURRENT_TASK=Add a guarded one-minute sell-retention overlay using existing persisted snapshot fields.
LAST_COMPLETED_STEP=Participant expansion trajectory overlay passed focused Token Detail 24/24, full frontend 158/158 across 32 files, typecheck/lint/build, and main Playwright 80 passed/10 intentional skips/0 failed across five viewport projects in 7.9 minutes with two workers.
NEXT_STEP=Run focused UI and runtime regressions to prove the overlay and explicit uncalibrated/non-causal metadata are missing before implementation.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Participant-expansion tree: focused Token Detail 24/24; full frontend 158/158 across 32 files; typecheck/lint/build exit 0 (28 routes); final-tree Playwright 80 passed, 10 intentional skips, 0 failed in 7.9m, exit 0. Sell-absorption regression pending.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext sell-absorption trajectory evidence
CURRENT_TASK=Validate the persisted metric metadata and guarded sell-retention chart.
LAST_COMPLETED_STEP=Implemented explicit sell-absorption version, uncalibrated, and non-causal metadata in the stage snapshot; added the guarded one-minute chart and a regression for unsupported/incomplete evidence.
NEXT_STEP=Run `python3 -m pytest tests/unit/test_early_runtime.py -q` and `npm test -- src/app/components/token-detail.test.tsx`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Participant-expansion tree: focused Token Detail 24/24; frontend 158/158; typecheck/lint/build exit 0, 28 routes; final-tree main Playwright 80 passed, 10 intentional skips, 0 failed in 7.9m, exit 0. Sell-absorption focused runtime and UI tests pending.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext sell-absorption trajectory evidence
CURRENT_TASK=Run full frontend unit/type/lint checks on the guarded sell-retention overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20 and Token Detail 25/25 pass. Regression tests verify explicit sell-absorption version, uncalibrated/non-causal flags, score scope, complete data, event time, and exclusion of v1, bad-version, incomplete, invalid, or causal-claimed values.
NEXT_STEP=Run `npm test`, `npm run typecheck`, and `npm run lint` from `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Sell-absorption focused runtime 20/20 and Token Detail 25/25 pass; full frontend/type/lint/build and exact-tree main Playwright pending. Prior participant-expansion tree passed 158 frontend tests and Playwright 80/10/0 in 7.9m.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext sell-absorption trajectory evidence
CURRENT_TASK=Run production build and Python lint/type gates on the sell-retention overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20, Token Detail 25/25, full frontend 159/159 across 32 files, TypeScript exit 0, and ESLint exit 0. Typecheck emitted three host stream-fd EPERM notices before success.
NEXT_STEP=Run `npm run build`, `ruff check` on touched Python files, and repository-configured mypy on the changed application module.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Sell-absorption focused runtime 20/20 and Token Detail 25/25 pass; full frontend 159/159, TypeScript, and ESLint pass. Build, touched Python Ruff/mypy, and exact-tree main Playwright pending. Prior participant-expansion tree passed Playwright 80/10/0 in 7.9m.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext sell-absorption browser acceptance
CURRENT_TASK=Run the five-viewport main Playwright matrix after the sell-retention overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20, Token Detail 25/25, full frontend 159/159 across 32 files, TypeScript/ESLint/build exit 0 (28 routes), touched Python Ruff PASS, and mypy PASS (177 files). Typecheck emitted three host stream-fd EPERM notices before success.
NEXT_STEP=Run `npx playwright test --workers=2` from `apps/web` and record exact counts, projects, duration, and exit status.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Sell-absorption focused runtime 20/20 and Token Detail 25/25 pass; frontend 159/159; TypeScript, ESLint, build (28 routes), Ruff, and mypy (177 files) pass. Exact-tree main Playwright pending. Prior participant-expansion tree passed Playwright 80/10/0 in 7.9m.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency trajectory evidence audit
CURRENT_TASK=Verify persisted price-efficiency version, calibration state, completeness, and point-time fields before deciding on a chart overlay.
LAST_COMPLETED_STEP=Sell-retention trajectory passed focused runtime 20/20, Token Detail 25/25, full frontend 159/159 across 32 files, TypeScript/ESLint/build (28 routes), Ruff, mypy (177 files), and main Playwright 80 passed/10 intentional skips/0 failed in 7.8 minutes.
NEXT_STEP=Audit the runtime stage-snapshot serializer and price-efficiency computation for an explicit versioned, uncalibrated, complete-data contract.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Sell-absorption exact-tree current pass: runtime 20/20; Token Detail 25/25; frontend 159/159; TypeScript, ESLint, build (28 routes), Ruff, mypy (177 files), and main Playwright 80/10/0 in 7.8m. Current code gates complete; next metric audit pending.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency trajectory evidence
CURRENT_TASK=Validate versioned price-efficiency metadata and its guarded one-minute chart.
LAST_COMPLETED_STEP=Audited price-efficiency computation: version, uncalibrated flag, and missing-data list exist in the canonical 1m feature window, but the stage-snapshot serializer omits them. Added runtime/UI regressions before implementation.
NEXT_STEP=Run focused runtime and Token Detail tests to record the expected missing-projection failures.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Sell-absorption exact-tree current pass: runtime 20/20; Token Detail 25/25; frontend 159/159; TypeScript, ESLint, build (28 routes), Ruff, mypy (177 files), and main Playwright 80/10/0 in 7.8m. Price-efficiency regression tests pending.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency trajectory evidence
CURRENT_TASK=Run focused runtime and Token Detail tests after adding guarded price-efficiency projection.
LAST_COMPLETED_STEP=Red runtime and UI tests confirmed version, uncalibrated state, completeness metadata, and the chart were omitted. Added explicit v1 price-efficiency version/policy/config/calibration/missing-data fields to snapshots and a strict 1m overlay requiring complete versioned evidence.
NEXT_STEP=Run `python3 -m pytest tests/unit/test_early_runtime.py -q` and `npm test -- src/app/components/token-detail.test.tsx`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Price-efficiency focused runtime and UI tests pending. Previous sell-retention exact tree passed runtime 20/20; Token Detail 25/25; frontend 159/159; type/lint/build; Ruff/mypy; and Playwright 80/10/0.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency trajectory verification
CURRENT_TASK=Run full frontend and Python quality gates for the price-efficiency overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20 and Token Detail 26/26 pass. Tests verify metric version/policy/config, uncalibrated state, complete-data semantics, event-time and parser requirements, and exclusions for incomplete/invalid evidence.
NEXT_STEP=Run full Vitest, TypeScript, ESLint, Ruff on touched Python files, and repository-configured mypy.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused runtime 20/20 and Token Detail 26/26 pass. Full frontend/type/lint, touched Python Ruff/mypy, build, and exact-tree main Playwright pending. Previous sell-retention tree passed all corresponding gates and Playwright 80/10/0.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency browser acceptance
CURRENT_TASK=Run production build and the main Playwright matrix on the price-efficiency overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20 and Token Detail 26/26; full frontend 160/160; TypeScript/ESLint pass; touched Python Ruff and mypy (177 files) pass. Typecheck emitted three host stream-fd EPERM notices before success.
NEXT_STEP=Run `npm run build` and then `npx playwright test --workers=2` from `apps/web`.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Focused runtime 20/20 and Token Detail 26/26; frontend 160/160; TypeScript/ESLint, Ruff, and mypy pass. Production build and exact-tree main Playwright pending. Previous sell-retention tree passed build and Playwright 80/10/0.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext price-efficiency browser acceptance
CURRENT_TASK=Run the five-viewport main Playwright matrix on the price-efficiency overlay.
LAST_COMPLETED_STEP=Focused runtime 20/20 and Token Detail 26/26; full frontend 160/160; TypeScript/ESLint; touched Python Ruff; mypy (177 files); and production build (28 routes) pass.
NEXT_STEP=Run `npx playwright test --workers=2` from `apps/web` and record exact counts, viewport projects, duration, and exit status.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current tests and static/build gates pass; exact-tree main Playwright pending. Prior sell-retention tree passed Playwright 80/10/0 in 7.8 minutes.
BLOCKERS=Legacy snapshots lack historical numeric thresholds; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked; internal alert/risk history lacks verified availability timestamps.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext decision/outcome history audit
CURRENT_TASK=Determine whether persisted records can support a canonical candidate decision-history projection without look-ahead.
LAST_COMPLETED_STEP=Persisted candidate lifecycle events are now included in replay when exact candidate identity and occurred/observed/ingested cutoffs pass. Persistence 12/12, read API routes 18/18, Token Detail 27/27, frontend 161/161, TypeScript/ESLint/Ruff/mypy/build pass, and final-tree main Playwright 80 passed/10 skipped/0 failed in 7.7 minutes.
NEXT_STEP=Audit the existing timestamped launch-footprint snapshot evidence for a defensible observed-bundle-cohort trajectory; retain UNKNOWN if its coverage or availability semantics are insufficient.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Candidate-lifecycle replay exact-tree pass: persistence 12/12; API routes 18/18; Token Detail 27/27; full frontend 161/161; TypeScript/ESLint/touched Ruff/mypy (177 files)/production build (28 routes); main Playwright 80 passed/10 skipped/0 failed in 7.7m across five viewports. Final scoped diff-check pending after report edits.
BLOCKERS=Full joined decision/score/risk/alert/outcome history unavailable because related standalone records lack independent availability timestamps; v3 PostgreSQL replay integration skipped because MEMERADAR_TEST_DATABASE_URL is unset; real mature outcomes and confirmed miss causality/rule impact/matched controls unavailable; separate host-listener browser suites blocked. Legacy threshold values remain unavailable in v1/v2 snapshots.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext canonical decision-history availability
CURRENT_TASK=Expose persisted, availability-stamped CandidateStateChanged events in the current Token Investigator timeline.
LAST_COMPLETED_STEP=Current timeline queries candidate-scoped lifecycle events under occurred/observed/ingested cutoffs and prefers the event over a matching legacy transition row. Regression first failed for missing live event data, then passed.
NEXT_STEP=Run final five-viewport `npx playwright test --workers=2` after the persistence read-query change and record exact results.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Persistence/read API routes 31/31 PASS; focused lifecycle regression PASS; Token Detail 29/29 PASS; Ruff PASS; mypy 177 files PASS. The prior frontend tree is 164/164, typecheck/lint/build pass and Playwright 80/10/0 in 7.6m; the current backend change requires a fresh browser run. Typecheck emitted three host stream-FD EPERM notices before exit 0.
BLOCKERS=Global pipeline entered/passed/blocked/unknown/deferred/expired history is not persisted for the full cohort; real mature outcomes, confirmed miss causality, rule impact and scientific matched controls are unavailable. Docker socket denied (`permission denied`) and MEMERADAR_TEST_DATABASE_URL unset; separate social/services and standalone-production browser listeners remain host-blocked.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Frontend VNext recovery evidence reconciliation
CURRENT_TASK=Reconcile the final current-tree browser result and update the parity/recovery records with the outcome timing and exact decision-snapshot link.
LAST_COMPLETED_STEP=Outcome duration UI tests 3/3; Token Detail exact-ID link tests 29/29; full frontend 164/164 across 32 files; typecheck/lint/build pass; five-viewport Playwright 80 passed/10 skipped/0 failed in 7.6 minutes.
NEXT_STEP=Update the final V7 recovery, parity, and change-ledger entries, then select the next locally actionable gap from current backend evidence.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Current exact tree: Outcomes 3/3; Token Detail 29/29; all frontend Vitest 164/164 across 32 files; typecheck/lint PASS; production build PASS (28 routes); five-viewport Playwright 80 passed / 10 skipped / 0 failed in 7.6 minutes. Typecheck emitted three host stream-FD EPERM notices before exiting 0. Backend: runtime 20/20; persistence/read API 31/31; PostgreSQL replay/outbox 2/2 at migration head `0018_stream_gap_provider_id`; Ruff PASS; mypy 177 files PASS.
BLOCKERS=Real mature outcomes, proven missed-winner causality, rule impact and scientific matched controls remain data-blocked. Standalone production/social-services browser gates remain host-listener blocked (EPERM); no real alpha claim is made. Direct host PostgreSQL port access remains denied; container-network disposable validation passed.
UPDATED_AT=2026-10-09

STATUS=IN_PROGRESS
CURRENT_PHASE=Exact-linked historical decision snapshot browser acceptance
CURRENT_TASK=Run the five-viewport browser matrix after adding exact-ID snapshot retrieval to the persisted timeline query.
LAST_COMPLETED_STEP=Focused persistence/read API/routes tests 47/47, Token Detail 29/29, Ruff, and mypy 177 files pass; frontend 166/166 and typecheck/lint/build pass on unchanged frontend sources.
NEXT_STEP=Run `npx playwright test --workers=2` from `apps/web`; the backend query changed after the previous matrix.
LAST_VERIFIED_HEAD=35274d2fd7ae07ef6446b66cef70ac6b93f5e84e
TEST_STATUS=Backend focused read/API/routes 47/47 (five deprecation warnings), Ruff PASS, mypy 177 files PASS, and Token Detail 29/29 PASS. Frontend full 166/166, TypeScript/lint/build PASS on unchanged frontend sources; final-tree Playwright pending after the persistence change. PostgreSQL execution remains unverified.
BLOCKERS=The current Docker socket is denied and MEMERADAR_TEST_DATABASE_URL is unset, so PostgreSQL execution for this query change is BLOCKED_HOST. Real mature outcomes, confirmed causal misses, global pipeline dispositions, rule impact, and scientific matched controls remain unavailable; separate social/services and standalone-production browser gates remain host-listener blocked.
UPDATED_AT=2026-10-09

## Frontend VNext V7 shutdown recovery — 2026-10-09

The shutdown's final `npx playwright test` had completed before the connection
failed: **80 passed, 10 skipped, 0 failed in 7.9 minutes**. After the exact-ID
stage-snapshot query change, the current-tree matrix was rerun and completed:
**90 total, 80 passed, 10 configured skips, 0 failed in 7.7 minutes** across
desktop, laptop, tablet, mobile, and mobile-wide. The latest run is accepted;
the disconnect was after the earlier completed result.

Current backend focused read/API/routes tests pass **47/47** (five existing
deprecation warnings); Token Detail passes **29/29**; Ruff and mypy
(**177 files**) pass. Frontend Vitest passes **166/166 across 32 files**;
TypeScript, ESLint and production build (**28 routes**) pass on the unchanged
frontend source. The current-query PostgreSQL integration remains
`BLOCKED_HOST`: Docker socket access is denied and
`MEMERADAR_TEST_DATABASE_URL` is unset. Earlier PostgreSQL outcomes and
outbox tests are historical evidence, not validation of this latest timeline
query.

The query can retrieve a candidate's exact linked v2/v3 stage snapshot by
persisted UUID even when it is outside the bounded timeline observation page,
but only after exact candidate/token/kind/version checks and event-relative
occurred/observed/ingested cutoffs. Invalid or future links are suppressed.
The larger lifecycle remains partial: standalone alert/score/risk records
lack independent availability timestamps; real mature outcomes, causal missed
winners, rule impact, matched controls, and global stage dispositions remain
unproven or unavailable.


## 2026-10-09 V7 candidate alert history and missed-winner navigation

Future candidate-linked alert saves now create allow-listed, idempotent state events in the existing domain-event table. The token timeline projects these with independent MemeRadar occurred/observed/ingested timestamps and cutoff filtering; mutable legacy alert rows are not backfilled. Missed Winners now links each persisted later-target row to the exact candidate's canonical timeline and retains replay at the signal cutoff.

Current evidence: backend alert/persistence/read/API/routes tests 64/64; Outcomes 3/3; Token Detail 30/30; frontend 167/167; typecheck, ESLint, production build (28 routes), touched Ruff, and mypy (177 files) pass. Main five-viewport Playwright after the UI link: 80 passed, 10 configured skips, 0 failed in 6.6m. The immediately preceding matrix's one failure traced to a local Next.js chunk request with `ERR_NETWORK_CHANGED`; isolated mobile reproduction passed, followed by a full matrix pass.

PostgreSQL execution for the current alert/timeline event path was skipped because `MEMERADAR_TEST_DATABASE_URL` is unset and Docker access is denied. Historical alert rows are not backfilled; the link and persisted state do not prove missed-winner causality. Real mature outcomes, rule impact, matched controls, counterfactuals, and a global stage-disposition funnel remain unavailable or unsupported.

## 2026-10-09 V7 point-in-time Missed Winners history

Missed Winners candidate-history links now replay the canonical token timeline
at the outcome row's persisted `signalAt`. When it is unknown, the page reports
replay unavailable rather than opening current history. The focused test first
failed against the old link (2 failures), then passed **5/5**.

Current frontend verification after this change: Vitest **172/172 across 32
files**; typecheck PASS (three host stream-FD `EPERM` notices before exit 0),
ESLint PASS, production build PASS (**28 routes**), and main five-viewport
Playwright **80 passed / 10 configured skips / 0 failed in 6.4m**. The
shutdown-supplied Playwright result had completed before disconnection at
80/10/0 in 7.9m; this later matrix covers the changed tree.

Branch remains `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`,
and the worktree remains extensively dirty. The exact-current token-filter SQL
has not been run against PostgreSQL because the test URL is unset and Docker
socket access is denied. Real mature outcomes, proven miss causality, rule
impact, matched controls, and the full global funnel remain unsupported.

## V7 mobile system-status visibility — 2026-10-09

Fixed a mobile header issue found during screenshot review: the provider/status
strip was horizontally scrollable with a hidden scrollbar, clipping chips at
the viewport edge. It now wraps on mobile, and the responsive visual-matrix
test asserts that the strip itself has no horizontal overflow. The assertion
reproduced the old bug before the fix; the mobile project passed 1/1 after the
fix and the screenshot shows all chips across two rows. The final five-project
Playwright matrix passed **80**, had **10 configured skips**, and had **0
failures** in **6.4 minutes**. No product source changed after this matrix.

Remaining evidence boundaries are unchanged: current-tree PostgreSQL execution
is unavailable; mature real outcomes, confirmed missed-winner causality, rule
impact, scientific matched controls, and complete global pipeline dispositions
are not demonstrated.

## 2026-10-09 V7 alert trajectory and browser acceptance

Token Detail now plots synchronized markers for persisted candidate alert
delivery-state events only when their occurred, observed, and ingested times
are valid and ordered. Each marker opens the canonical timeline evidence.
Token Detail tests: 33/33; frontend Vitest: 173/173 across 32 files;
typecheck, lint, and production build (28 routes): PASS.

The first current-tree five-project browser run finished 79 passed, 10
configured skips, 1 failed at four workers. Trace evidence shows two local
Next.js chunks failed with net::ERR_NETWORK_CHANGED; the mobile navigation
test therefore remained unhydrated. The same test passed in isolation, and the
full two-worker retry passed 80 passed / 10 configured skips / 0 failed in
7.2m. This is the latest accepted main Playwright result; both attempts are
recorded.

No numerical alert metric, missed-winner causality, rule impact,
counterfactual, matched control, or alpha claim is inferred. Current
PostgreSQL integration for the timeline path remains unverified because Docker
socket access is denied and MEMERADAR_TEST_DATABASE_URL is unset.


## V7 exact score/risk snapshot links — 2026-10-09

Candidate transition entries now link persisted score/risk references only when the exact ID, evidence kind, and token identity match a row already present in the bounded timeline response. Missing/mismatched rows remain explicit; legacy score/risk rows were not admitted to point-in-time replay because they lack independent availability timestamps.

Current-tree verification after this frontend change: Token Detail 34/34; frontend Vitest 174/174 across 32 files; typecheck, ESLint, and production build (28 routes) PASS; five-viewport Playwright 80 passed / 10 configured skips / 0 failed in 7.2m at two workers. The same-ID wrong-kind regression is covered. Real outcome maturity, causal misses, rule impact, matched controls, and global stage dispositions remain unproven or unavailable.


## V7 bounded score/risk evidence and final browser acceptance — 2026-10-09

The live Token Detail timeline now fetches an explicitly referenced score snapshot or risk assessment by exact UUID when the normal candidate-bounded timeline read omitted it. The query is restricted to the token's canonical candidate; rows are only added when their persisted as-of time is no later than the transition. The UI also checks exact ID, evidence kind, token identity, and transition-time ordering. Legacy score/risk rows remain excluded from point-in-time replay because they lack independent observed/ingested timestamps.

Regressions first reproduced both gaps (missing exact-linked rows outside the bounded response; score/risk evidence later than the transition). Persistence/read/API-route tests passed 50/50; focused persistence 18/18; Token Detail 35/35; full frontend Vitest 175/175; Ruff PASS; mypy 177 files PASS; typecheck and ESLint PASS.

The default Next.js TypeScript CLI build failed when the host denied a child Node spawn (EPERM), leaving no showConfig output for Next to parse. Direct tsc showConfig returned valid JSON. The configured documented in-process checker (experimental.useTypeScriptCli=false) retained the project type check and allowed the production build to complete with 28 routes. Current final main Playwright passed 80, skipped 10 configured cases, failed 0 in 7.1m at two workers across five viewport projects. The CLI failure is retained in the evidence; the in-process checker is experimental and is a build-path limitation to monitor.


## V7 creator-history read projection — 2026-10-10

The SQL read service no longer returns an empty in-memory creator-reputation
baseline. It reads the latest exact-creator `research.creator_history` row
only when the row is versioned `creator-history-v2`, marked `LIVE_SHADOW`,
and its event, observed, and ingested timestamps are no later than the read
cutoff. The worker now persists the required rates, sample state, and config
hash from its point-in-time creator analysis. The wallet graph shows
`UNKNOWN` when no creator profile can be read; it does not infer rates.

Verification on this tree: persistence and worker unit files **28 passed, 1
skipped**; Ruff passed; mypy passed across **177 files**; wallet graph focused
suite **5/5**; full frontend Vitest **177/177 across 32 files**; typecheck,
lint, and production build passed (**28 routes**); main five-viewport
Playwright **80 passed / 10 configured skips / 0 failed in 7.4 minutes**.
The PostgreSQL query was reviewed and compiled for PostgreSQL, but not executed
against a database in this environment. No real creator-history row or
creator outcome is claimed.

## 2026-10-10 V7 bounded creator prior-mint projection

The existing creator-history pipeline now projects at most 20 most recent
prior mint IDs with an explicit truncation flag through the worker, typed read
model, persistence query, API, client parser, and Wallet Graph. New records use
creator-history-v3; v2 aggregate rows remain compatible and show the
mint list as UNKNOWN. Invalid or inconsistent histories fail closed. Parser
exceptions now map to INVALID_RESPONSE, distinct from network/provider
UNAVAILABLE.

Current verification: backend focused 47 passed / 1 skipped / 5 warnings;
focused frontend 56/56; full frontend 181/181 across 32 files; Ruff
passed on touched paths; mypy 177 files PASS; typecheck and ESLint PASS;
production build PASS (27 app routes); five-project main Playwright 80
passed / 10 configured skips / 0 failed in 6.1m. PostgreSQL execution and
real creator-history rows remain unverified. Broader creator intelligence,
miss causality, rule impact, and matched controls remain incomplete or data
blocked. Next: audit persisted decision/outcome joins for the smallest
point-in-time candidate-history projection.

## V7 Pipeline inventory drilldown — 2026-10-10

Recognized persisted candidate-state rows now link to the existing Radar state filter. State names outside the read client's canonical filter allow-list remain plain text, avoiding a misleading link that would widen to all candidates. The population remains the persisted candidate table at one read time, not a global discovery funnel or stage-disposition ledger.

The regression passed 4/4 after failing first for the missing link. Full frontend Vitest passed **182/182 across 32 files**; typecheck and ESLint passed; production build passed with **27 routes**; current five-viewport Playwright completed **80 passed / 10 configured skips / 0 failed in 6.2 minutes**. No backend or scoring change was made. Current PostgreSQL runtime and real outcome availability remain unverified.

## V7 forward-outcome signal-time provenance — 2026-10-10

Forward-outcome observations now persist and project an allow-listed `signal_at_basis=CANDIDATE_DISCOVERY_TIME`. The Outcomes, Missed Winners, and Token Detail shared table identifies this as candidate discovery time, explicitly not a decision timestamp. Legacy rows with no basis and unrecognized basis values remain UNKNOWN. This prevents `signal_at` from being mistaken for a prior decision; miss causality is still unverified.

Verification: backend worker/persistence/API focused suites **47 passed, 1 skipped, 5 existing deprecation warnings**; focused frontend client/outcomes/token-detail **91/91**; full Vitest **183/183 across 32 files**; Ruff, mypy (**177 files**), typecheck, ESLint, production build (**27 routes**) PASS; main five-viewport Playwright **80 passed / 10 configured skips / 0 failed in 6.0m**. PostgreSQL runtime and real mature outcome evidence remain unverified.

The shared outcome table now labels missed-record reason codes as **OUTCOME REVIEW CODES · NOT A DECISION REASON** and uses “Targets / outcome codes” as the column header. The focused regression failed before the copy change and passes 5/5 afterward. After this latest text change, full Vitest remains 183/183, typecheck/ESLint/build pass, and the five-project responsive visual matrix passes 5/5 in 2.8m. The latest full Playwright 80/10/0 run preceded this copy-only change; its relevant geometry was checked by the visual matrix.

## V7 missed-winner history and timeline cursor — 2026-10-10

Missed Winners now opens the token's canonical timeline without using candidate discovery time as a decision cutoff. Token Detail follows the existing bounded timeline cursor, keeps `as_of` for replay pagination, offers a first-page reset, and labels trajectories as page-scoped. Current verification: focused Outcomes 6/6; focused read-client/Token Detail 89/89; frontend Vitest 187/187 across 32 files; typecheck, ESLint, build (28 routes), and five-project Playwright (80 passed / 10 configured skips / 0 failed in 6.1m) PASS.

This improves evidence navigation only. The persisted history query remains bounded, current PostgreSQL execution is unavailable, and full decision-to-alert joins, mature real outcomes, confirmed missed winners, rule impact, and matched controls remain unverified or unsupported.
## 2026-10-10 V7 timeline disclosure and current browser result

After the Missed Winners timeline-navigation and Token Detail cursor changes, both current and replay views now warn that persistence reads are bounded and complete stored history is not guaranteed. The new route-level cursor guard was exercised across the five viewport projects.

Current verification: full frontend Vitest **187/187 across 32 files**, typecheck PASS (three host stream-FD EPERM notices before exit 0), ESLint PASS, and production build PASS (**28 routes**) after the source change. The expanded current-tree Playwright matrix completed **85 passed / 10 configured skips / 0 failed in 6.3m** (95 tests). The supplied shutdown run of 80/10/0 in 7.9m completed before the disconnect and remains historical evidence; this newer matrix covers later changes.

The current cursor navigates the existing bounded timeline response; it does not remove persistence caps. Current PostgreSQL query execution, complete decision-to-alert/outcome history, mature real outcomes, confirmed missed-winner causality, rule impact, matched controls, and a global lifecycle funnel remain unverified, unavailable, or unsupported by persisted evidence. The worktree remains intentionally dirty.

## 2026-10-10 V7 deterministic timeline source window

Audit found that timeline source queries applied the existing 5,000-row per-source cap without deterministic ordering. They now select the newest source rows by event/as-of timestamp and ID before the merged timeline is sorted chronologically. A regression reproduced the missing `ORDER BY` before the fix.

Verification: `pytest tests/unit/test_read_persistence.py -q` **20 passed** (2 existing deprecation warnings); touched Ruff checks passed; `mypy` passed across **177 source files**. The timeline remains bounded and PostgreSQL query execution is still unavailable. No frontend source changed after the accepted five-viewport matrix (**85 passed / 10 configured skips / 0 failed in 6.3m**).

The same audit found that public `from_at`/`to_at` filters were applied only after the per-source cap. They are now pushed into broad source queries before the cap (`from_at` inclusive, `to_at` exclusive), matching the in-memory filter. The regression passed and compiled the bounded filter/order SQL with SQLite and PostgreSQL dialects. The full persistence unit file remains 20/20; live PostgreSQL execution remains unavailable.

## 2026-10-10 V8 recovery and project startup

V8 recovery began on branch `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`, with the V7 tree intentionally dirty (174 tracked changed paths, 106 untracked paths, 0 staged paths at first inspection). The scoped `git diff --check -- . ':!.env.example'` passed. Startup completed through `bash scripts/start.sh`: API, PostgreSQL 16, Redis, worker, and web containers started; the start script reported API liveness/readiness healthy. A direct API readiness request reported database and Redis reachable, and the web root returned HTTP 200.

`bash scripts/status.sh` still returned Docker socket `permission denied`, so status-command access is a host/runtime limitation even though startup and API/web health succeeded. `.codex` checkpoint writes are also rejected by the read-only workspace mount; V8 checkpoint evidence is maintained in `docs/reports/agentic-loop/V8_CURRENT.md`. The Docker web build's `npm ci` reported 8 vulnerabilities (7 high, 1 critical); exact package/advisory audit is pending. No V8 source change or test is yet claimed. Historical V7 tests remain historical only.

## 2026-10-10 V8 stage disposition evidence and exact snapshot navigation

Each runtime evaluation now appends two idempotent, future-only records to the existing observation store: `SAFETY_GATE` and `PAPER_ELIGIBILITY`. The rows retain candidate/token identity, event/observed/ingested timestamps, outcome/reason codes, policy versions/config hashes, and the exact v3 decision-snapshot UUID. No historical disposition is inferred.

The bounded Token timeline now follows a trusted disposition's exact snapshot UUID, fetching only that row when it falls outside the current observation page. It validates candidate/token identity, v2/v3 snapshot kind/version, and requires snapshot occurred/observed/ingested times to be no later than the disposition. Missing or invalid links are removed from the projected disposition. The Token Detail panel exposes allow-listed fields and labels the score as not a probability.

Current focused verification: `pytest -q tests/unit/test_read_persistence.py tests/unit/test_early_runtime.py` **46 passed, 2 existing deprecation warnings**; exact-link parametrization **2 passed**; scoped Ruff PASS; targeted mypy PASS for `read_queries.py` with workspace source paths. Token Detail had last passed **38/38** before this persistence-only change. No PostgreSQL runtime query, full V8 frontend suite, or browser suite was run for this slice. Stage dispositions are future runtime evidence, not a historical/global funnel; complete promotion/alert/outcome causality and real-data claims remain unverified.

## V8 seed intake and public RPC lookup boundary — 2026-10-10

The exact 25 user-provided seed strings are preserved in `data/seeds/solana_wallet_seeds_raw.csv`. The deterministic importer reuses the existing Solana address validator and produced 22 syntax-validated candidates, 2 `NEEDS_REVIEW` inputs with internal whitespace preserved, 1 invalid-length input, 0 duplicates, and 22 syntax-only monitoring-eligible rows. Syntax eligibility is not chain verification, wallet scoring, or smart-money classification. Importer outputs were repeatable; focused tests passed **3/3** and scoped Ruff passed.

The keyless public Solana RPC health doctor passed. A bounded `getAccountInfo` lookup attempt then returned 4 `ProviderUnavailableError` results and the adapter circuit rejected 18 remaining tasks; no account or signature response was accepted, and the generic provider wrapper does not distinguish transport failure from HTTP 5xx. No seed address or provider payload was logged. Per-seed RPC verification and history remain unresolved/UNKNOWN; the lookup blocker is recorded and will not be retried without a changed provider/network condition. This failure does not invalidate the syntax-validated inputs.

## V8 exact alert-to-decision linkage — 2026-10-10

The candidate timeline previously retained an alert's source decision link only when that decision event was in the bounded recent lifecycle-event page. It now reads the exact `source_decision_event_id` carried by a valid alert event and performs a bounded UUID lookup, requiring the same candidate aggregate, `CandidateStateChanged` kind, early-runtime producer, and occurred/observed/ingested timestamps no later than the replay cutoff. The existing alert projector also confirms the decision event was available before the alert. No broad history scan or raw payload projection was added.

The new regression failed before the change because the source decision event was missing from the result; it now passes. `pytest -q tests/unit/test_read_persistence.py tests/unit/test_early_runtime.py`: **47 passed**. Scoped Ruff and targeted mypy for `read_queries.py` pass. The source link is stronger evidence for an alert that exists; bounded history still cannot prove the absence of later promotion or alert, and this does not create a confirmed system-miss classification. PostgreSQL runtime remains unverified.

## V8 wallet data model audit — 2026-10-10

`docs/audits/WALLET_DATA_MODEL_AUDIT.md` maps wallet persistence concepts to
the current implementation. `WalletIdentity` exists as a domain value object,
but no general wallet identity ORM table exists. `WalletCandidateRow` is
token-scoped and is not a safe substitute for seed identity. Normalized wallet
activities, candidate lifecycle, derived graph edges, creator history, and
shared alert/outbox evidence have existing owners; no parallel tables are
planned for those concepts. Durable seed-source association, per-wallet sync
state, and point-in-time wallet reputation are absent. The next local slice
adds only canonical identity and traceable raw seed-source persistence, with
no classification or scoring inference.

This audit-time finding was addressed by the next V8 slice below; the earlier
paragraph records the state at the audit and is not the current schema state.

## 2026-10-10 V8 canonical wallet identity and seed persistence

Migration `0019_wallet_seed_identities` adds canonical wallet identity, preserves each raw seed source separately, and links existing token-scoped wallet candidates to that identity. The idempotent database command is `scripts/import_wallet_seeds.py`; it does not activate monitoring or assign wallet scores. The syntax-validation artifact/report generator now states this distinction explicitly. All 25 supplied rows remain represented: 22 syntax-validated, 2 internal-whitespace `NEEDS_REVIEW`, 1 invalid decoded length, 0 duplicates, and no chain/history verification. The 22 syntax-valid rows are syntax-only monitoring candidates, not classified wallets.

Current verification: wallet seed/candidate/migration tests **6 passed**; release identity tests **4 passed**; touched Ruff and targeted mypy passed; migration checker reports head `0019_wallet_seed_identities` and 34 ORM tables; PostgreSQL offline migration SQL compilation passed. A SQLite CLI import persisted all source rows across repeated imports. `bash scripts/start.sh` passed; API readiness reported PostgreSQL/Redis reachable, and the web root returned HTTP 200. No SQL migration/import was run on the Compose database: `docker compose exec` and a read-only loopback PostgreSQL query were denied by host permissions. Full backend unit tests and current PostgreSQL runtime acceptance remain pending.

## 2026-10-10 V8 SQLite and forward-poll regression closure

Enabling the SQLite-backed async tests exposed that SQLite removes timezone
metadata from `DateTime(timezone=True)` reads. Worker observation loads now
restore UTC at the SQLite boundary, timestamp comparisons normalize the
stored instant, and the service-conflict test checks the instant instead of
SQLite's absent tzinfo. These tests also exposed a DEX scheduler bug: it marked
the horizon complete once all *currently due* offsets existed, while later
configured offsets were still in the future. Completion now requires every
configured offset to be due and present; a terminal UNKNOWN marker is emitted
in the same cycle as the final no-pair poll. The new T+20m regression failed
before the change and passes afterward.

Current evidence: forward-evidence unit module **11 passed**; full backend
unit suite **1,526 passed, 8 deprecation warnings, 0 failed in 138.80s**.
The previously failing SQLite service-conflict persistence test also passes.
Scoped Ruff passes, targeted mypy passes for the worker/persistence files,
and `git diff --check -- . ':!.env.example'` passes. Runtime PostgreSQL migration/import remains blocked by host Docker and
loopback permissions. Startup had passed earlier, but a later direct health
probe was rejected by host socket permissions. This fix adds no real wallet
history or causal-miss claim.

## 2026-10-10 V8 missed-winner causal semantics

Audit of `MissedWinnerAnalyzer` found unsupported causal-sounding codes:
missing state snapshots became `MISSED_DISCOVERY`, absent alert timestamps
became `TELEGRAM_DELAY`, and later target evidence after `RISK_REJECTED`
became `FALSE_RISK_BLOCK` / `FALSE_BUNDLE_POSITIVE`. It now distinguishes
unobserved state from missing features, reports unavailable alert history,
keeps attribution UNKNOWN when only missing-history codes exist, and reserves
`TELEGRAM_DELAY` for a known alert age beyond its configured bound. Risk and
bundle codes report evidence present, not causal blame. Generic `LOW` and
`UNKNOWN` substrings no longer create low-score or critical-risk claims.

The new/updated regression failed before the change. Current verification:
analyzer tests **4 passed**; `tests/unit` **1,527 passed, 8 deprecation
warnings, 0 failed in 136.43s**; scoped Ruff, targeted mypy, and
`git diff --check -- . ':!.env.example'` pass. No confirmed system-miss
classification was added: complete promotion/alert absence and a versioned
opportunity cutoff are still missing.

## 2026-10-10 V8 same-state re-evaluation history

An audit found that `EarlyRuntimeService` cached stage snapshots only by
candidate/state. When the same candidate was evaluated later without changing
state, the runtime reused the first snapshot ID; a new immutable disposition
could then collide with the old source key instead of recording the later
evaluation. The cache now includes the event-time checkpoint. A regression
verifies the later snapshot and both stage dispositions, then replays the same
checkpoint to verify idempotency. Runtime, persistence timeline, and
missed-winner analyzer suites pass **53 tests**; the full backend unit suite
passes **1,529 passed, 8 deprecation warnings, 0 failed in 138.50s**. Scoped
Ruff, targeted mypy, and `git diff --check` pass. This adds future
evaluation evidence only; it does not create historical backfill, a global
funnel, or a confirmed miss.

## 2026-10-10 V8 wallet-score dependency correction and startup recheck

A dependency audit found that launch-path independent-wallet ratio was passed into both `WalletQuality` and `SmartMoneyConfluence`, while the generic scorer inferred `WalletQuality` from bundle concentration. The two values are distinct evidence types: wallet independence is now represented once in `SmartMoneyConfluence`, and `WalletQuality` remains UNKNOWN without historical wallet-reputation evidence. The score contract is versioned `early-score-v3` so the changed component semantics remain distinguishable from prior snapshots. The new regressions failed before these fixes.

Current backend verification: focused runtime/scoring **33 passed**; full `tests/unit` **1,531 passed, 8 deprecation warnings, 0 failed in 137.62s**; targeted Ruff and mypy pass. Token Detail component tests **38 passed** after the v3 fixture update. Full frontend Vitest/type/lint/build and Playwright have not been rerun for this V8 slice.

The requested project startup was retried after current process inspection found no app process. `bash scripts/start.sh` exited 1 before startup: Docker API socket `/var/run/docker.sock` permission denied. Earlier V8 startup/readiness success remains historical; current app health is not verified. Do not retry until host Docker/socket permissions change. The wallet seeds still have no chain/history verification; real mature outcomes, full causal miss/rule impact evidence, matched controls, and current-tree PostgreSQL runtime remain unavailable.


## 2026-10-11 V8 frontend and browser acceptance

After the early-score-v3 component semantics changed, the current frontend full suite passed **188/188 tests across 32 files**; typecheck and ESLint passed; the production build passed and compiled 28 routes. The standard five-viewport Playwright matrix initially completed with one mobile ERR_NETWORK_IO_SUSPENDED navigation failure (84 passed / 10 skipped / 1 failed). That exact mobile case then passed 1/1 in isolation, and the standard matrix rerun passed **85 passed / 10 configured skips / 0 failed in 7.5m**. No product source changed between runs. Classify the isolated first failure as non-reproducible browser/network load sensitivity, not a product fix.

Current full-stack project startup is not verified: current shell process inspection found no app process and the latest bash scripts/start.sh exited before launching services because access to /var/run/docker.sock was denied. A prior startup/readiness success is retained as historical evidence only. Current PostgreSQL migration/import, real provider data, mature outcomes, causal miss/rule-impact, and matched-control validation remain blocked or unavailable.

## 2026-10-11 V8 startup and final local gate reconciliation

The requested startup was checked again from the recovered shell. Full-stack `bash scripts/start.sh` cannot reach Docker because `/var/run/docker.sock` returns permission denied. A web-only `npm run dev -- --hostname 127.0.0.1` attempt also exited before startup with `listen EPERM` on port 3000. Current process inspection found no host-visible app process; container state cannot be queried through Docker. These are HOST blockers; current project service state is unverified.

Current key-safe local security review exited 0 and reported deterministic contract checks PASS, including its tracked/artifact/reachable-history secret-boundary scan. Optional npm, pip, and container scans were `NOT_RUN`; external acceptance remains blocked. `npm audit --offline --json` returned zero advisory entries, which conflicts with the earlier Docker `npm ci` report of 8 vulnerabilities (7 high, 1 critical). The dependency advisory state is unresolved; no dependency changes were made. The standalone secret-scan invocation was interrupted to avoid duplicating the full reachable-history scan; the embedded review scan completed and passed.

Current migration contract check reports head `0019_wallet_seed_identities` and 34 metadata tables. Full Ruff passed and mypy passed for 177 source files. Current unit/frontend/browser evidence remains: backend `tests/unit` 1,531 passed with 8 deprecation warnings; frontend Vitest 188/188, typecheck, ESLint, production build (28 routes) PASS; five-viewport Playwright 85 passed / 10 configured skips / 0 failed in 7.5m. The exact isolated mobile case passed 1/1 after the first matrix had one non-reproducible `ERR_NETWORK_IO_SUSPENDED` failure; no product source changed between the matrix runs.

Remaining V8 gaps include a complete immutable decision→promotion→alert→outcome join, all-stage lifecycle dispositions/global funnel, proven missed-winner causality and rule impact, wallet reputation as-of T and wallet/token decision attribution. Current PostgreSQL runtime, live seed history, mature real outcomes, and scientific matched/OOS validation remain unavailable or unverified. No alpha claim is made.

## 2026-10-11 V8.1 evidence-closure continuation

V8.1 preserved the inherited dirty tree and added four evidence-bound changes.
Wallet candidate evaluation excludes evidence that was not both observed and
ingested by the decision cutoff. The token timeline carries bounded read
coverage metadata through persistence, API, typed client, and Token Detail.
New state transitions now have availability-timestamped ENTERED_STAGE
dispositions linked to their exact snapshots. For those new transitions, the
runtime also records ALERT_PROJECTION with the projected alert identity/state
and lifecycle outbox configuration/enqueue state; this does not establish
Telegram delivery.

Current verification: backend tests/unit 1,536 passed, 8 deprecation
warnings, 0 failures in 133.85s; runtime and timeline persistence suites
50 passed; focused stage-disposition tests 2 passed. Ruff passes; mypy reports
no issues in 177 source files. Frontend Vitest 190/190 across 32 files,
frontend typecheck, ESLint, and production build (28 routes) passed on the
current frontend source. The main five-viewport Playwright result (85 passed,
10 configured skips, 0 failed) is historical V8 evidence and was not rerun
after V8.1 frontend changes. Current git diff check passes.

Current PostgreSQL/app runtime remains BLOCKED_HOST: Docker socket access was
denied and the web-only listener returned EPERM. Current-tree PostgreSQL
execution, real wallet history, mature real outcomes, complete causal miss
classification, rule impact, matched controls, and locked OOS remain
unverified or evidence-blocked. No alpha or confirmed system-miss claim is
made. See docs/reports/agentic-loop/V8_1_CURRENT.md,
docs/audits/MEMERADAR_V8_MASTER_GAP_MATRIX.md, and
docs/reports/MEMERADAR_V8_1_EVIDENCE_CLOSURE_FINAL.md.

## 2026-10-11 V8.1 wallet signature inventory

Added a default-off `SOLANA_WALLET_HISTORY_ENABLED` worker that polls one
bounded `getSignaturesForAddress` page for one syntax-validated,
monitoring-eligible Solana seed at a time. It uses the existing canonical
wallet identity, standard RPC adapter, observation store, and generic durable
collection checkpoint. The allow-listed inventory stores signature, slot,
block-time, confirmation-status, and error-presence metadata; it does not
decode trades or derive P&L/reputation. A page ending does not establish
complete wallet history: every inventory observation retains
`source_history_complete=false`.

Current verification: the focused config/wallet-history/seed-persistence suite
passed **21/21**; backend `tests/unit` passed **1,542 tests, 8 deprecation
warnings, 0 failures in 135.38s**; `make lint` passed; `make typecheck` passed
for **178 source files**. The test subprocess follows the existing test
`uvloop` policy because the managed default selector loop stalls `aiosqlite`
worker-thread wakeups. No production event-loop policy changed.

PostgreSQL and public-RPC history collection were not run in this host. The
signature inventory is an ingestion seam only; decoded transaction history,
wallet-wide reputation as-of T, wallet/token attribution, mature outcomes,
and alpha/OOS remain unverified. During recovery, populated credential-like
fields in `.env.example` were replaced with empty values. If any represented
an active provider credential, rotate it through that provider's external
control plane; no value is included in this report.

## 2026-10-12 V8.1 initial discovery disposition

The runtime already recorded exact `ENTERED_STAGE` dispositions for each new
candidate-state transition, plus per-evaluation safety and paper-eligibility
results and transition-time alert projection/outbox state. Audit found that the
candidate's initial `DISCOVERED` snapshot itself had no disposition row. The
runtime now persists that first `DISCOVERED / ENTERED_STAGE` event with the
original snapshot ID and event/observed/ingested timestamps. It is created only
for a newly created candidate; no history is backfilled. The existing Token
timeline safely projects the row through the allow-listed disposition path.

The RED test failed with only `DISCOVERED` absent. Focused stage/runtime/read
persistence tests passed **50/50**; full backend `tests/unit` passed **1,542**
with **8 deprecation warnings**, 0 failures in 135.39s; Ruff passed; mypy
passed for **178 source files**. The initial-state ledger gap is closed for
future runtime observations. Global funnel aggregation, additional stages
that the runtime does not currently evaluate, complete historical causality,
and PostgreSQL runtime acceptance remain open or blocked. No frontend files
changed in this slice. `git diff --check -- . ':!.env.example'` passed after
the report reconciliation.

## 2026-10-12 V8.1 observed wallet funding/transfer graph evidence

Extended the existing bounded wallet relationship projection to expose
persisted wallet.funding, wallet.transfer, and onchain.transfer observations
as directional graph edges. The read remains point-in-time: observed and
ingested timestamps must be available by the requested cutoff, conflicting
duplicate event identities and service endpoints are excluded, and each edge
carries quality/provider/source provenance with ownership_asserted=false.
Wallet Graph shows these details only when the edge is explicitly marked
OBSERVED; an inferred FUNDED graph edge is not labeled as an observed funding
event.

Focused Python relationship and persistence tests passed **37/37**; Wallet
Graph tests passed **7/7**; backend tests/unit passed **1,544** with
**8 deprecation warnings**, 0 failures in 136.86s. make lint and
make typecheck passed (178 source files). Full frontend Vitest passed
**192/192 across 32 files**; frontend typecheck, ESLint, and production build
passed. git diff --check -- . ':!.env.example' passed after this slice.

This is a projection seam, not creator-funder intelligence completion:
repository search found no production producer for these generic transfer
observations, and no token-linked creator role, verified asset/amount, or
bounded creator lineage is projected. Current PostgreSQL/runtime, RPC wallet
history, and the main Playwright matrix were not rerun; the latter remains
historical V8 evidence. Real wallet reputation, causal misses, rule impact,
and alpha/OOS remain unverified.

## 2026-10-12 V8.1 wallet scorer availability cutoff

A wallet-scoring regression showed that a completed trade with an old event
time could still affect a historical score when it came from a snapshot that
was not available until after the requested cutoff. The scorer now excludes
the entire future-available snapshot before grouping, since its aggregate
does not carry per-outcome availability. The RED regression passed after the
change; wallet scoring, wallet candidate discovery, and the score contract
suite passed **15/15**.

Current backend tests/unit passed **1,545**, with **8 deprecation warnings**
and 0 failures in 134.39s. make lint passed; make typecheck passed for
**178 source files**. Frontend source did not change in this slice; the
previously verified full frontend suite remains **192/192** with typecheck,
ESLint, and production build passing.

This closes the in-memory wallet snapshot cutoff only. There is still no
durable wallet-wide reputation snapshot, decoded multi-token history, verified
provider collection, or real wallet performance evidence. PostgreSQL and
Playwright were not rerun; host restrictions remain unchanged.

## 2026-10-12 V8.1 Wallet Graph provenance source-id redaction

Branch is `main`, HEAD remains
`35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`; current worktree is 302 status
entries (185 tracked dirty, 117 untracked, 0 staged).

The existing Wallet Graph projection now omits unconstrained raw provenance
`source_id` values. The UI retains provider/time/parser/quality fields and
shows a withheld-reference notice rather than displaying raw source text. A
credential-like source identifier regression is covered at the graph
projection and UI boundaries; this is scoped to Wallet Graph and does not
claim global redaction across all API surfaces.

Focused wallet relationship/read-persistence tests passed **37/37** and
Wallet Graph Vitest passed **7/7**. The full frontend Vitest suite passed
**192/192**; frontend lint/typecheck/build and `make lint`/`make typecheck`
(178 source files) passed. The full backend unit suite result of **1,545
passed / 8 warnings** predates this small change; focused backend regressions
passed afterward.

Runtime probes were inconsistent: `scripts/status.sh` reported healthy
services and one HTTP request returned 200, but direct Docker exec and later
loopback database probes were denied. No current PostgreSQL migration/query
or live seed import was verified. Real decoded wallet history, mature outcomes,
confirmed misses, rule impact, matched controls, and OOS remain unverified.

## 2026-10-12 V8.2 public read source-reference boundary

Public read serializers no longer return raw persisted provider source IDs in
timeline, forward-outcome, wallet-activity, provenance, position-mark, or
position-entry source fields. Timeline and token lifecycle/insider evidence
maps withhold `source_id`/`raw_source_id` values while preserving unrelated
fields. Position mark evidence references now use the local observation UUID.
Provider, timestamps, parser, quality, and raw payload hash remain available.
Stored provider source IDs are unchanged.

The regressions were observed failing before implementation and now pass.
`uv run pytest tests/unit/test_read_api_routes.py
tests/unit/test_read_persistence.py -q`: **48 passed**, 5 existing deprecation
warnings. `make typecheck` passes for **178 files**; targeted Ruff lint and
`git diff --check` pass. `ruff format --check` still reports formatting in
inherited dirty sections (some also fail when read from HEAD); those files were
not reformatted wholesale. This closes the direct source-field leak only:
arbitrary `evidence_refs` and other freeform projection fields still need a
surface-by-surface audit, so public provenance safety remains below 9/10.

No full backend suite, current-tree browser matrix, PostgreSQL runtime, real
wallet history, or mature-outcome validation was run in this slice. The
canonical decision/alert/outcome ledger and related causal features remain
open; PostgreSQL and real-data gates remain blocked or unverified as recorded
in the V8.2 scorecard.

## 2026-10-12 V8.2 candidate-linked timeline availability

The bounded token timeline now carries the persisted candidate ID on every
projected row and exposes `available_at` only when both provider observation
and system ingestion timestamps exist. Token Investigator shows these fields
in its provenance disclosure and keeps missing values UNKNOWN. The API client
rejects an explicit availability timestamp that disagrees with those inputs,
while tolerating older responses that omit the fields.

Current verification: focused backend read API/persistence tests **63/63**;
frontend parser and Token Detail tests **94/94**; mypy **178 source files**;
frontend typecheck and ESLint; targeted Ruff; and `git diff --check` all pass.
The full backend suite, current five-viewport Playwright, PostgreSQL runtime,
and real mature outcomes were not run/verified. This improves event identity
and availability but does not establish complete history, confirmed system
misses, Rule Impact, or 9+ causal-ledger maturity. Source-specific completeness
remains the next local gap.

## 2026-10-12 V8.2 bounded timeline completeness

The persisted token timeline now reports requested bounds, actual event-time
span, each source's cap state, known cap/replay omissions, and tri-state
candidate/promotion/alert/outcome completeness. Provider collection remains
UNKNOWN because this read projection has no provider-collection completeness
evidence. The Token Investigator shows those limits and distinguishes
NOT QUERIED from a source that was queried without reaching its cap.

Current verification: persistence/read API/API schema tests **67 passed**, with
5 deprecation warnings; frontend read parser and Token Detail tests **94
passed**; mypy **178 source files**; frontend typecheck and ESLint; targeted
Ruff; and `git diff --check` pass. A separate linked-event cap regression
proves dependent alert, promotion and candidate completeness are lowered when
the source-decision recovery query is capped. This closes source-cap disclosure only.
There is still no continuation beyond a source cap, full candidate
decision→promotion→alert→outcome ledger, confirmed miss classifier, or rule
impact aggregate. Full backend, production build, current-tree Playwright,
PostgreSQL runtime, and real outcomes were not verified in this slice.

## V8.2 finalized wallet balance-change evidence — 2026-10-12

The opt-in wallet worker now follows its persisted signature inventory with a
restart-safe finalized `getTransaction` decode cursor. It records exact
owner-linked SPL token account balance deltas and explicit unavailable,
failed, and unknown decode states. It does not infer BUY/SELL, price, PnL,
position, or full history. Wallet Detail projects only validated direction,
raw integer delta, and token decimals, rendering the exact scaled balance
change with a clear non-trade disclaimer.

Current focused verification: wallet decoder/persistence **57 passed**;
wallet read/API **50 passed**; Wallet Detail/read-client **56 passed**;
`make lint`, `make typecheck` (**178 files**), web typecheck, and ESLint pass.
This raises Wallet History engineering maturity to **7.0/10**, still below
the V8.2 9+ closure target. Provider-backed history, per-wallet coverage,
trade decoding, reputation as-of-T, current five-viewport Playwright,
production build, PostgreSQL runtime, mature real outcomes, and causal
research remain unverified or unavailable.

## V8.2 Wallet candidate scan cap — 2026-10-12

Wallet candidate discovery now fetches one row beyond its 5,000-observation
bound. When the persisted activity scan reaches that cap, candidate evaluations
are stored as `DEGRADED`, expose the observed sample/token counts only as lower
bounds, and suppress confidence, profitability, and copyability derived from
the truncated set. The worker logs whether the persisted scan reached its
bound, and Wallets labels degraded candidate history as incomplete. It does
not claim the provider's underlying wallet history is complete.

The pre-change regression failed because candidate evaluation had no source
completeness input. Focused backend tests pass **5/5**, focused Wallets tests
pass **4/4**, `make lint typecheck` passes (Ruff; mypy **178 files**), web
typecheck and ESLint pass, and `git diff --check` passes. This closes capped
candidate-metric handling only. Per-wallet inventory/decode coverage,
transaction classification, provider-history completeness, current-tree
Playwright, production build, PostgreSQL runtime, and real wallet outcomes
remain unverified or unavailable.

## V8.2 Wallet history cursor coverage — 2026-10-12

The canonical wallet profile now resolves persisted wallet identities even
when no in-memory reputation catalog entry exists, and keeps their reputation
UNKNOWN/unscored. It projects the existing signature-inventory and finalized
decode checkpoint states without exposing cursor values. Missing or
future-dated checkpoints remain UNKNOWN; exhausted cursors show only that the
stored paging sequence ended. Provider history completeness is false when
collection state exists and UNKNOWN when no state exists; it is never inferred
as complete from cursor exhaustion.

Current-tree verification for this slice: focused persistence/read/API tests
**66 passed** (5 existing deprecation warnings); wallet parser, detail, and
list tests **60 passed**; Ruff and mypy (**178 source files**) pass; web
typecheck and ESLint pass. The initial profile test found a missing
`timedelta` import, which was fixed before the passing rerun. Wallet History
engineering maturity is **7.6/10**, still below the 9+ target: page counts,
coverage ranges, decode totals/provider gaps, transaction classification, and
real provider completeness evidence remain absent. Current-tree Playwright,
production build, PostgreSQL runtime, and real wallet/outcome data are not
verified in this slice.

## V8.2 explicit reevaluation history — 2026-10-12

Repeated early-runtime evaluations now persist a `candidate.reevaluation`
observation linked to the exact immutable decision snapshot. It records the
prior and resulting candidate states, decision/safety/risk outcomes, advisory
score, policy/config identity, reasons, and independent event/observed/ingested
times. Deterministic identity makes retry idempotent. The existing bounded
timeline already filters generic observations by all three times at replay
cutoff, so no parallel ledger API or schema migration was added.

Token Detail shows the persisted reevaluation, unknown/block reasons, policy
identity, advisory score label, and snapshot link. It warns that absence from a
bounded page does not prove that reevaluation did not occur. The regression
failed before implementation and then passed. Runtime/persistence/cutoff tests
pass **3/3**; Token Detail passes **41/41**; Ruff, mypy (**178 files**), web
typecheck, ESLint, and `git diff --check -- . ':!.env.example'` pass. This
improves the investigation trail but does not
complete promotion/alert/outcome joins, prove missed-winner causality, or raise
the causal ledger to 9/10. Production build, full backend/frontend suites,
current-tree Playwright, PostgreSQL runtime, and real wallet/outcome data are
not verified in this slice.

## V8.2 Wallet history coverage summary — 2026-10-12

Wallet Detail now receives a bounded, as-of summary of persisted successful
signature pages and transaction decode observations. It shows observed signature
counts, the range of valid signature block times, signatures whose block time is
missing or after the read cutoff, decode-completed/unknown/error counts, and
whether either local read scan reached its 500-row cap. Rows observed or
ingested after the profile read time are excluded. A capped count is a lower
bound; cursor exhaustion and persisted rows do not prove complete provider
history. Failed signature-page requests are not yet persisted as attempt
observations, and SPL balance changes still do not establish trades or PnL.

Focused verification: persistence and API route files **52 passed** with 5
existing deprecation warnings; read API, Wallet Detail, Wallet Dashboard, and
parity-manifest Vitest **63 passed**; Ruff passed; mypy passed for **178 files**; web TypeScript
and ESLint passed; `git diff --check -- . ':!.env.example'` passed. Wallet
History engineering maturity is **8.0/10**, still below the 9+ target because
failed provider attempts, transaction/trade classification, durable as-of
reputation, and real provider completeness evidence remain open. Current-tree
production build/Playwright, PostgreSQL runtime, and real wallet outcomes were
not verified by this slice.

## V8.2 wallet signature request-failure coverage — 2026-10-12

The opt-in signature collector now persists a safe
`wallet.signature_inventory_attempt` observation when a request or page
validation fails, then re-raises the original exception. The checkpoint is
unchanged so retry behavior remains intact. The event stores only the wallet,
request state, an allow-listed failure code, and event/observed/ingested times;
provider exception text is not persisted. The canonical profile reports
attempted requests and failures separately from successfully persisted pages,
and the Wallet Detail labels each count explicitly.

Current verification: wallet worker + read persistence + read API test files
**60 passed** with 5 existing deprecation warnings; read API, Wallet Detail,
Wallet Dashboard, and parity-manifest Vitest **63 passed**; Ruff passed; mypy
passed for **178 files**; web TypeScript and ESLint passed; repository diff
check passed. This raises Wallet History engineering maturity to **8.2/10**.
Failure-code breakdown is not yet projected, and transaction/trade
classification, wallet reputation as-of-T, real provider history completeness,
PostgreSQL runtime, and current-tree browser acceptance remain open or
unverified.

## V8.3 alert delivery observability — 2026-10-13

The canonical alert timeline now distinguishes provider submission start,
acceptance, explicit rejection, and ambiguous send exceptions. The common
event handler records projection completion using the runtime clock only when
it does not precede source request or explicit decision time. Each attempt
emits a low-cardinality counter. Public Token Investigator output hides
provider errors and arbitrary provider message IDs. Queue/enqueue time is
UNKNOWN because dispatch is synchronous without a separate alert queue;
human delivery remains UNKNOWN without a receipt.

RED/GREEN projection timestamp: **1 passed** after expected RED. Telemetry
regressions: **2 passed** after expected RED. Alert, alert persistence, read
persistence, read API and route suites passed **127** tests with 7 existing
deprecation warnings; Token Detail passed **47**. Ruff passed; mypy passed for
**181 files**. Full current-tree backend/frontend/build and Playwright remain
pending after this UI change.

## V8.2 Wallet signature failure-code projection — 2026-10-12

The bounded wallet profile now reports counts for the worker's allow-listed
signature request failure categories (`RATE_LIMITED`, `TIMEOUT`, `UNAVAILABLE`,
`AUTHENTICATION_FAILED`, `UNSUPPORTED`, `REQUEST_FAILED`, `UNKNOWN`). Persisted
codes outside that vocabulary are grouped under `UNKNOWN`; exception text stays
out of storage and the public API. The parser rejects unknown category keys,
zero/invalid counts, and totals inconsistent with the failure count. A legacy
response that lacks the breakdown is represented as `UNKNOWN` for its known
failure total. The UI marks the category counts as bounded lower bounds when
the read scan is capped.

Current verification: wallet worker/read persistence/API tests **60 passed**
with 5 existing deprecation warnings; Wallet Detail/read API/Wallet Dashboard/
parity Vitest **63 passed**; Ruff passed; mypy passed for **178 files**; web
TypeScript and ESLint passed; `git diff --check -- . ':!.env.example'` passed.
Wallet History engineering maturity is **8.4/10**, not 9+: confirmed swap/trade
classification, durable as-of-T reputation, complete provider-history proof,
PostgreSQL runtime, current-tree Playwright, and real wallet outcomes remain
unavailable or unverified. The reported category totals reflect only the
bounded persisted attempt-observation window; capped scans are lower bounds.

## V8.2 token timeline reference projection — 2026-10-12

The token timeline API now keeps only an allow-listed reference category
(such as `score` or `observation`) and withholds each opaque reference value.
Unknown reference categories collapse to `SOURCE_REFERENCE_WITHHELD`. The
projection returns at most 32 references and marks a longer list as truncated.
This is a token-timeline boundary; other API evidence-reference projections
still need review.

Verification: the credential-shaped URL regression failed before the change
and passes after it; `tests/unit/test_read_api_routes.py` **21 passed** with 5
existing deprecation warnings; `make lint` passed; `make typecheck` passed for
**178 files**. Public Provenance Safety remains below 9 because this does not
close other projections or current-tree browser acceptance.

## V8.2 public API reference audit — 2026-10-12

The follow-up audit completed the typed evidence-reference boundary across
`apps/api` read serializers. Each projection retains only allow-listed
reference categories, replaces opaque IDs with `SOURCE_REFERENCE_WITHHELD`,
and caps nested and top-level reference lists at 32 plus a truncation marker.
The same recursive projection strips nested `source_id`/`raw_source_id` values
from timeline, token lifecycle/insider, social disclosure, and wallet-graph
maps. The social-source management API now emits only `kind=MANUAL` when that
is the persisted kind, otherwise `kind=UNKNOWN`; arbitrary provenance fields
are not returned. The first-party social-source UUID remains an intentional
resource identity for its bounded filter/route; it is not an upstream provider
source ID. Social post links remain credential-free HTTPS-normalized.

RED/GREEN source-ID and nested-reference tests pass. Current focused read-route
and social-source contracts: **25 passed**, **5 deprecation warnings**; Ruff,
mypy (**178 files**), and `git diff --check -- . ':!.env.example'` pass. No UI
behavior changed in this slice. Full frontend/browser acceptance, current
PostgreSQL runtime, and live provider data remain unverified.

## V8.2 risk-block recovery and exact replay — 2026-10-12

The early runtime no longer leaves a `RISK_REJECTED` candidate terminal when
later safety and risk evidence is fresh and passing. Unknown, stale, or blocked
evidence remains rejected. A fresh pass returns the candidate to a monitored
state with a distinct persisted transition and `RISK_BLOCK_CLEARED` reason.

Restart replay now uses the persisted candidate discovery time and, when the
original discovery observation is in the supplied history, rehydrates its
original source identity. Replaying the same recovery event preserves the
candidate state, decision snapshot, transition history, and persisted
observation rows. Runtime snapshot projection now writes snapshots for
transitions created in the current pass, avoiding reconstruction of older
transition snapshots from later feature state. No execution authority or live
mode changed.

Verification: the focused recovery test passed; lifecycle/runtime/repository/
property tests passed **42/42**; the full backend unit suite passed
**1,563/1,563** with **8 existing deprecation warnings** in **133.25s**. The
full suite's initial failure came from a test fake returning activity rows for
the checkpoint query; the fake now routes by selected table and the bounded
read file passes **3/3**. Ruff passed and mypy passed for **178 source files**.
The full causal ledger, complete stage coverage, durable PostgreSQL restart,
real wallet history, mature outcomes, and causal miss/rule-impact validation
remain open or blocked.

## V8.2 current-tree browser acceptance — 2026-10-12

The current V8.2 tree passed its focused Wallet Graph browser check across
laptop, tablet, desktop, mobile, and mobile-wide (**5 passed**, 22.6s). The
main Playwright matrix then passed **85**, skipped **10 configured cases**, and
failed **0** in **7.4 minutes** across the same five projects at that checkpoint.
The later wallet-profile run below supersedes it. The browser gate is locally
closed; this does not establish backend PostgreSQL runtime, live
provider history, mature outcome data, or causal miss validity.

## V8.2 durable wallet reputation snapshots — 2026-10-12

The existing no-lookahead wallet scorer now produces immutable, versioned
`wallet.reputation_snapshot` observations during candidate evaluation. The
worker writes each snapshot in the same unit of work as its wallet-candidate
update. The wallet read path returns at most 50 newest snapshots and excludes
rows whose event, observation, or ingestion time is after the read cutoff.
Wallet Detail displays the snapshot's as-of time, score policy/configuration,
sample and quality evidence, and scan-cap state. Source-history completeness
stays `UNKNOWN`; the score is advisory, is not attributed to a token decision,
and cannot authorize execution.

Verification: focused reputation backend/API tests **10 passed** (2 existing
warnings); wallet profile/parser/list tests **60 passed**; executable parity
manifest regression **3 passed**; worker entrypoint
tests **26 passed**; current-tree backend unit suite **1,566 passed** (8
existing deprecation warnings); frontend Vitest **195 passed** across 32 files;
Ruff, mypy (**178 files**), web TypeScript, ESLint, and production build (28
routes) passed. The desktop operator-route axe sweep passed **1/1**. The
current-tree five-viewport Playwright matrix passed **85**, skipped **10
configured tests**, and failed **0** in **7.5 minutes**. This closes current
browser acceptance for this tree, but not wallet reputation: snapshots are
currently emitted for candidate-discovery evaluations, not every tracked
wallet. PostgreSQL runtime, real wallet history, mature outcomes, and wallet
to token decision attribution remain unverified. The candidate causal ledger,
all-stage coverage, strict system-miss classification, and rule impact also
remain open.

## V8.2 persisted lifecycle stage summary — 2026-10-12

Pipeline now displays a bounded backend aggregate over candidate-linked,
persisted stage-disposition observations and a cursor-paged event drilldown.
The view is separate from current candidate inventory and the page-local radar
list. It enforces a non-future `as_of` and event/observed/ingested availability
cutoff. Malformed persisted stage observations are omitted from counts and
make the projection incomplete; the bounded SQL drilldown scans past malformed
rows and continues from the last scanned event when it reaches its source cap.
Provider collection completeness remains UNKNOWN; this is not an all-launch
discovery funnel.

Verification: focused lifecycle funnel/read API/persistence suite **61 passed**
(6 existing deprecation warnings); focused Pipeline/read-api Vitest **61
passed**; Ruff passed on touched Python, mypy passed on **178 source files**,
web typecheck and ESLint passed, and `git diff --check -- . ':!.env.example'`
passed. Five-viewport Playwright remains **85 passed / 10 configured skips / 0
failed in 7.5 minutes** from before the latest parser/read-path hardening; full
backend/frontend suites and production build have not been rerun after that
narrow change. PostgreSQL runtime, complete candidate/alert/outcome causality,
provider collection coverage, mature real outcomes, and confirmed system-miss
validation remain unverified or unavailable.

## V8.2 timeline causal-reference completeness — 2026-10-12

The bounded Token Investigator timeline now withholds missing or malformed
candidate lifecycle decision-snapshot references and marks the persisted
projection incomplete. It applies the same completeness state to invalid
stage-disposition links. An alert event with a missing, malformed, future, or
otherwise unresolved persisted decision-event reference remains visible, but
the source decision link is omitted and candidate/promotion/alert projection
completeness is false. Candidate lifecycle and alert delivery envelopes that
fail their allow-listed projector are also recorded as omissions and lower
projection completeness. Exact valid links still project normally. This prevents
an absent causal join from appearing complete; it does not create the missing
decision/snapshot event or prove provider collection completeness.

Verification: `uv run pytest tests/unit/test_read_persistence.py -q` passes
**40/40**; touched-file Ruff passes; `uv run mypy` passes for **178 source
files**; `git diff --check -- . ':!.env.example'` passes. The opt-in
`tests/integration/test_read_query_service.py` test is skipped because
`MEMERADAR_TEST_DATABASE_URL` is not configured. PostgreSQL runtime and full
decision→promotion→alert→outcome causality remain unverified; the causal ledger
and timeline completeness remain below the V8.2 9+ target.

## V8.2 ordinary timeline projection failure closure — 2026-10-12

The token timeline now omits a malformed ordinary persisted observation
without aborting the whole response, retains valid rows from the same query,
and lowers persistence/candidate/promotion/alert completeness with an explicit
projection omission. This is fail-closed display handling; it does not repair
source evidence, continue past the per-source cap, or establish collection
completeness.

Verification: the new malformed-row regression was RED before the fix and is
GREEN after it (**1 passed, 40 deselected**); the persistence suite passes
**41/41**, public read routes **24/24**, and current full backend unit suite
**1,578 passed** with **9 deprecation warnings**. Ruff passes on touched Python,
mypy passes for **178 source files**, and `git diff --check -- . ':!.env.example'`
passes after reconciliation. PostgreSQL runtime, current-tree Playwright for
this backend-only change, complete causal joins, real wallet history, and
mature real outcomes remain unverified or blocked.

The follow-up source audit found no active persisted OpportunityWindowPolicy
or backend Rule Impact aggregate. Existing `alpha_handoff_age_seconds=300`
and the safety liquidity threshold belong to separate runtime policies and
are not treated as a preregistered research cutoff. Robinhood's sequencer
adapter is a generic non-authoritative stream; launchpad decoding requires a
verified contract/selector plus canonical receipt/finality, and its verified
registry is empty. Existing cross-chain caller identity, bundle-footprint,
first-block concentration, and generic funding-graph evidence do not establish
Relay-order correlation, verified Jito membership/flow, per-wallet launch
chronology, or a token-linked creator-funder lineage. Those rows remain below
9; no provider, ownership, trade, or causal facts were inferred.

## V8.3 point-in-time wallet decision attribution — 2026-10-12

The existing `early.stage_snapshot` now carries bounded per-wallet evidence
only when candidate-matched, as-of trade observations exactly reconcile with
the wallet identity lists and counts supplied to the scored confluence input.
Missing identity lists, invalid/duplicate addresses, future events, truncation,
count mismatch, or score-component overrides leave the attribution UNKNOWN.
No score weights are invented. The existing timeline/API projects the evidence
and Token Investigator shows each wallet's decision-use state and timestamp.
Wallet reputation remains UNKNOWN because a persisted as-of reputation
snapshot is not joined to these decisions.

Verification: attribution/runtime/feature/read-route suite **108 passed** with
6 existing warnings; Token Detail **42 passed**; Ruff passed for touched Python;
mypy passed for **180 source files**; web typecheck and ESLint passed. Full
current-tree backend/frontend/build/browser acceptance is pending. PostgreSQL
runtime and real wallet data remain unverified.

## V8.3 preregistered opportunity-window policy — 2026-10-12

Added an immutable `OpportunityWindowPolicy` value with deterministic content
hash, validated token-age/liquidity/tradability/execution/fill assumptions,
allowed entry states, and ordered `DRAFT` → `PREREGISTERED` →
`ACTIVE_FOR_RESEARCH` → `RETIRED` status transitions. Lifecycle events reuse the
append-only observations table; history is bounded to four known status keys,
idempotent, and cutoff-filtered by event, observed, and ingested timestamps.
Policy definitions cannot be revised under the same ID/version. No migration,
default research policy, backfill, or historical policy assignment was added.

Verification: policy plus existing wallet persistence tests **8 passed**;
focused Ruff passed; mypy passed for **180 source files**. These tests use
SQLite and do not establish PostgreSQL runtime acceptance. No policy has yet
been bound to a causal outcome review; this capability remains below 9.

## V8.3 bounded timeline source-cap continuation — 2026-10-12

The existing token timeline now uses stable keyset cursors bound to token,
requested range, and as-of cutoff. SQL sources fetch at most the configured
source cap plus one sentinel row, report which sources hit the cap, and expose
a bounded resume cursor from the merged page frontier. This may reread buffered
rows safely; it does not skip past unreturned evidence or claim complete
history. Token Investigator shows each source's cap state, resume frontier,
continuation availability, and cap reason. Projection failures, legacy
availability gaps, and provider-collection UNKNOWN remain explicit.

Verification: read API, persistence, route, and schema regressions **90 passed**
with **6 deprecation warnings**; targeted parser and Token Detail tests **97
passed**; touched-file Ruff passed; mypy passed for **181 source files**; web
typecheck and ESLint exited 0. Current-tree Playwright has not yet been rerun
after this frontend change. PostgreSQL runtime, complete causal joins, provider
collection completeness, and mature real outcomes remain unavailable or
unverified.

## V8.3 condition recovery and re-evaluation evidence — 2026-10-12

The existing bounded candidate timeline now links a failed threshold check to
later persisted checks only for the same candidate, token, rule, and matching
decision or safety policy version plus config hash. The projection respects
event/availability cutoffs and the timeline's exclusive `to_at` bound. It
surfaces the recovered value and timestamp, the exact recovery snapshot and
reevaluation references when persisted, and UNKNOWN when history, policy
identity, a later check, or projection completeness is insufficient. A later
`paper_eligible` snapshot is accepted only when both decision and safety policy
identities match the original snapshot.

Token Investigator displays this evidence and states that recovery alone does
not establish an opportunity-window miss, promotion, or alert. This closes a
recovery visibility gap; it does not bind an opportunity cutoff or prove a
confirmed system miss.

Verification: `uv run pytest tests/unit/test_read_api.py
tests/unit/test_read_persistence.py tests/unit/test_read_api_routes.py -q`
passes **90 tests** with **6 existing deprecation warnings**; Token Detail
passes **42 tests**; touched-file Ruff and `git diff --check -- .
':!.env.example'` pass. Earlier checks on this same implementation passed
mypy (**181 files**), web typecheck, and ESLint. Current-tree five-viewport
Playwright remains pending after the Token Detail change. PostgreSQL runtime,
real wallet history, mature outcomes, and complete causal miss classification
remain blocked or unverified.

## V8.3 decision-time wallet reputation linkage — 2026-10-12

The existing token timeline now links a persisted wallet reputation snapshot to
per-wallet decision evidence only for an exact chain/address identity and only
when the snapshot's event, score-as-of, computed, observed, and ingested times
are all available by the decision timestamp. A capped snapshot scan or invalid
snapshot stays UNKNOWN; malformed rows lower completeness and produce an
explicit omission. Token Investigator displays the linked snapshot metadata
separately from the wallet evidence's score/gate use. Reputation is explicitly
`NOT_USED_IN_DECISION`; this is a read-time evidence link and did not recompute
or alter historical decisions.

Verification: the final affected backend read/runtime/API/persistence tests
pass **122/122** with **6 existing deprecation warnings**; Token Detail passes
**43/43**; focused Ruff passes; mypy reports no issues in **181 source files**;
web typecheck and ESLint exit 0. Current-tree full backend/frontend/browser
acceptance remains pending. PostgreSQL runtime is blocked by the host; real
wallet history, mature outcomes, and locked OOS remain unavailable or
unverified. Next local gate: bind the existing bounded Rule→Outcome
Association read model to an immutable opportunity policy only when the policy
was preregistered and active before the full cohort window.

## V8.3 opportunity-policy binding for rule/outcome association — 2026-10-12

The existing `/v1/rule-outcome-associations` read contract accepts an optional
exact OpportunityWindowPolicy ID/version and returns an explicit binding state.
The SQL adapter only reports `BOUND` when the full immutable status history is
valid as-of the query, the policy was already `ACTIVE_FOR_RESEARCH` and
effective by the cohort start, and no retirement event falls inside the
requested `[from_at, to_at)` cohort window. A policy created or activated later
cannot be retroactively applied. Missing, inactive, retired, invalid, and
in-memory-unavailable histories remain unbound with no policy hash. Results
remain `ASSOCIATION_ONLY`; policy binding does not evaluate a candidate's
opportunity eligibility or establish a causal miss.

Verification: the binding regression was RED before implementation; focused
policy/route tests pass **3/3**, and the broader persistence/read/API/opportunity
policy suite passes **98/98** with **6 existing deprecation warnings**. Ruff,
mypy (**181 source files**), and `git diff --check` pass. This slice uses SQLite
fixtures; PostgreSQL runtime remains blocked by host access. The association
aggregate still has no candidate-level drilldown or browser research surface,
so Rule→Outcome Association remains below 9.
## V8.3 Rule/Outcome Research Lab and current-tree acceptance — 2026-10-12

The existing bounded `/v1/rule-outcome-associations` read model now has a
Research Lab view on `/readiness`. It uses backend-computed cohort associations
and an exact candidate/rule drilldown, preserves threshold actual/required/delta
as strings, links to Token Investigator at the decision timestamp, and discloses
policy binding, source caps, and unknown/incomplete history. Browser code does
not calculate causal rates. The result remains `ASSOCIATION_ONLY` and
`CAUSALITY_UNKNOWN` where proof is incomplete. Opportunity policy eligibility
has not yet been evaluated against candidate snapshots; a bound policy is not
proof of a confirmed miss.

Current-tree evidence: focused association backend suite **104 passed**; full
backend unit suite **1,607 passed**, 9 existing deprecation warnings, 0 failed
in 139.78s; frontend Vitest **202 passed** across 32 files; ESLint, typecheck,
and production build passed (28 routes); five-viewport Playwright **85 passed,
10 configured skips, 0 failed in 7.5m**. These are engineering tests, not
PostgreSQL runtime or real-data research validation. PostgreSQL remains
`BLOCKED_HOST`; real wallet history, mature outcomes, and locked chronological
OOS remain unverified.

## V8.3 decision-time opportunity eligibility — 2026-10-12

The existing bounded Rule/Outcome drilldown can now evaluate each candidate's
opportunity eligibility only when an exact immutable OpportunityWindowPolicy
was active/effective before the cohort window and remained active across it.
Inputs come from the persisted candidate stage snapshot: token age, liquidity,
decision state, quote validity, and sellability. The evaluator checks event,
observed, and ingested times against the decision cutoff; stale, unavailable,
missing, malformed, or unbound evidence remains UNKNOWN. Late-entry state is
kept distinct from ineligibility. The Research Lab displays this backend result
with matching policy identity and decision time. The association remains
non-causal and does not establish a confirmed system miss.

Verification after the change: focused evaluator/persistence/API/runtime suite
**117 passed**; explicit non-null bound-policy API serialization regression
**1 passed**; focused Readiness/read API Vitest **59 passed**; full frontend
Vitest **202 passed**; typecheck, ESLint, production build, and current-tree
five-viewport Playwright **85 passed / 10 configured skips / 0 failed** in
**7.5m**. Full backend unit suite last passed **1,615** with **9 warnings** in
**140.93s** before final style/type narrowing and the serializer regression;
final-source full backend rerun is pending. Ruff, mypy (**181 files**), and
`git diff --check` pass after style/type corrections.

This closes local engineering for opportunity-policy candidate eligibility;
runtime and research maturity remain blocked/unverified. PostgreSQL runtime is
`BLOCKED_HOST`; real provider-backed wallet history and mature outcomes are
unverified. The next local P0 is binding these opportunity eligibility
observations into the existing Token Investigator condition-recovery and
reevaluation projection without claiming market recovery from an absent
reevaluation record.

## V8.3 policy-bound condition recovery — 2026-10-12

The canonical token timeline now accepts an exact opportunity policy ID and
version only with a bounded `from_at` / `to_at` / `as_of` query. The SQL read
adapter resolves policy lifecycle history with the existing append-only
repository, and evaluates failed/recovered candidate snapshots only when the
policy was active/effective at range start and not retired inside the
exclusive range. Eligibility uses each snapshot's own event, observed,
ingested, quality, token-age, liquidity, decision-state, quote-validity, and
sellability evidence. In-memory reads state `HISTORY_UNAVAILABLE`; missing or
unknown evidence does not become a negative result. Policy ID/version are
included in policy-bound timeline cursors while legacy unbound cursor shape is
preserved.

Token Investigator displays the bound policy, failure eligibility, and the
first later policy-eligible observed snapshot. Research Lab drilldown links to
that bounded token timeline only when the backend policy binding is `BOUND`.
This is observed eligibility, not proof of an absent reevaluation, promotion,
alert, or system miss.

Focused verification: backend application/persistence/API/cursor tests **5
passed**; frontend read API, Readiness, and Token Detail targeted tests **3
passed**. Full current-tree backend/static/frontend/browser checks are pending
after this source change. PostgreSQL runtime remains `BLOCKED_HOST`; real data,
mature outcomes, and locked OOS remain unverified.

## V8.3 policy-cutoff reevaluation-gap closure — 2026-10-12

The bounded policy-bound Token Investigator timeline now derives the exclusive
opportunity cutoff from the immutable active policy and the failed decision's
persisted token age. It records source-scoped completeness for the bounded
reevaluation and promotion-decision windows. The backend distinguishes a
persisted reevaluation, promotion before cutoff, and a reevaluation process
gap only when a later policy-eligible snapshot is observed before cutoff and
both relevant persisted source windows are complete. Capped, missing, or
unprojectable history remains `UNKNOWN`. This finding is explicitly not a
confirmed system miss; outcome, alert, and causal classification remain
separate.

Verification: focused backend/API/SQL regressions **3 passed**; affected
backend group **112 passed**; full backend unit **1,621 passed** with 10
deprecation warnings; focused Token Detail and read API timeline tests **9
passed**; full frontend Vitest **203 passed**; Ruff, mypy (**181 source
files**), web typecheck, ESLint, and production build (**28 routes**) passed.
The current five-viewport run on the preceding source was **84 passed, 10
configured skips, 1 failed**; the isolated global-search test passed **1/1**.
The latest source's browser rerun is `BLOCKED_HOST`: Playwright's web server
and direct Next startup could not bind `127.0.0.1:13100` (`listen EPERM`)
before tests began. PostgreSQL runtime is also `BLOCKED_HOST`; real wallet
history and mature outcomes remain unverified.

## V8.3 decision-anchored outcomes in rule association — 2026-10-12

The forward worker's policy-eligible outcomes already preserve the exact
decision snapshot and immutable opportunity-policy identity. The bounded
Rule/Outcome association previously rejected this basis and could therefore
omit those outcomes. It now accepts a decision-anchored outcome only when the
exact later snapshot is present for the same candidate/token, the immutable
policy ID/version/hash match the bound policy, the policy evaluator finds that
snapshot eligible, and the snapshot was available before the outcome was
observed. Candidate/rule representatives preserve the first blocked check
even if a later check passes, so recovery does not erase the earlier decision.
The Research Lab result remains `ASSOCIATION_ONLY`; this is not causal Rule
Impact.

RED was reproduced because the previous evidence contract rejected
`OPPORTUNITY_ELIGIBLE_ENTRY`. Pure and SQLite persistence regressions passed
(8 tests); the affected read/persistence/API suite passed **107 tests** with 7
existing deprecation warnings. Full Ruff, mypy (**181 source files**), and
`git diff --check` passed. The full backend suite is being rerun on this
source tree. No frontend source changed in this slice, so prior full frontend
Vitest (**206 tests**), typecheck, ESLint, and build (**28 routes**) remain the
latest applicable evidence. Current-source Playwright remains `BLOCKED_HOST`:
the Next server could not bind either `127.0.0.1:13100` or `:13001` (`listen
EPERM`) before collection. PostgreSQL runtime, real provider wallet history,
mature outcomes, and locked OOS remain unverified.

## V8.3 market-observed condition recovery — 2026-10-13

The existing policy-bound timeline now accepts positive liquidity recovery
evidence from a fresh exact candidate/token PRODUCTION market snapshot. It
uses `observed_at` because the provider snapshot's event-time quality can be
UNKNOWN, and the Token Investigator labels that basis. The projection keeps
market recovery separate from reevaluation, policy eligibility, promotion,
alert, and causal miss claims. MOCK or stale snapshots do not recover the
condition; incomplete reevaluation or promotion windows remain UNKNOWN.

Verification: new pure and SQLite persisted recovery tests **2 passed**;
affected read/API/policy/association group **120 passed** with 7 deprecation
warnings; focused Token Detail **1 passed**; Ruff, mypy (**181 files**), web
typecheck, ESLint, and `git diff --check` passed. Full final-source backend,
frontend, and build acceptance remain pending. Current-source browser binding
and PostgreSQL runtime remain `BLOCKED_HOST`; real wallet history/mature
outcomes remain unverified.

## V8.3 verified Pump.fun wallet swap evidence — 2026-10-13

Wallet history now reuses the existing pinned Pump.fun instruction/event
mapper. It labels a finalized owner-linked token balance change as
`DEX_SWAP_BUY` or `DEX_SWAP_SELL` only when the transaction signature, wallet,
mint, side, executed token amount, quote mint, and positive raw quote amount
agree. A mismatch remains `AMBIGUOUS`. The worker persists quote mint and raw
quote units with parser provenance; application, read API, and Wallet
Investigator validate and display these units without deriving price or PnL.
Other DEX/AMM and liquidity instruction identities remain unsupported or
unknown until verified.

RED/GREEN evidence: worker plus read-route tests **45 passed**; SQLite wallet
read projection **1 passed**; Wallet Investigator and read-client Vitest
**62 passed**; Ruff passed; mypy passed for **181 source files**; web typecheck
and ESLint passed. Full current-tree backend, frontend, build, and Playwright
acceptance remain pending. PostgreSQL is `BLOCKED_HOST`; real wallet history
and mature outcomes are unverified.

## V8.3 confirmed-miss promotion classification — 2026-10-13

The bounded timeline classifier now supports the reevaluated-but-not-promoted
case. It emits `CONFIRMED_SYSTEM_MISS / PROMOTION_MISS` only for a mature real
outcome bound to the exact policy-eligible decision snapshot and immutable
policy, with complete candidate/promotion/alert/outcome history, no promotion
or alert, and an explicit `paper_eligible=false`. Missing action state remains
`CAUSALITY_UNKNOWN`. A positive market recovery without a later eligible
decision remains `CAUSALITY_UNKNOWN`.

RED was reproduced in both pure and SQLite persisted paths. After the change,
exact-chain tests passed **2/2**, affected backend read/API/policy/association
suite passed **120** with 7 deprecation warnings, full Token Detail passed
**43**, Ruff and mypy (**181 files**) passed. Full backend/frontend/build and
current-source browser acceptance remain pending; PostgreSQL runtime is
`BLOCKED_HOST`, and real wallet history/mature outcomes remain unverified.

## V8.3 wallet transaction taxonomy — 2026-10-13

The finalized owner-linked SPL token balance delta remains the activity
record. The wallet decoder now classifies direct `transfer`/
`transferChecked`, `mintTo`/`mintToChecked`, and `burn`/`burnChecked` only when
the exact Token or Token-2022 program, instruction account, mint, raw amount,
checked decimals where present, and direction reconcile with finalized
owner-linked balance changes. Unsupported balance changes remain UNKNOWN or
AMBIGUOUS; no price, swap, or trade is inferred. Classification parser
provenance is `solana-wallet-activity-classification-v2`.

Regression tests exposed a malformed Token-2022 program ID in both wallet
decoding and holder-graph defaults; both now use the canonical ID already
present in provider fixtures. The worker, read-route, and holder-graph suite
passed **46 tests** with 7 existing deprecation warnings. Ruff passed and
mypy passed for **181 source files**; changed-file diff check passed. The
repository-wide diff check still reports an inherited trailing blank line in
`docs/FRONTEND_BACKEND_PARITY.md:444`. Swap/AMM, liquidity, ATA, and
first-block decoding remain open.
PostgreSQL runtime is `BLOCKED_HOST`; no real wallet history or profitability
evidence is claimed.

## V8.3 ATA_CREATE instruction activity — 2026-10-13

The wallet decoder also persists an exact successful Associated Token Program
`create`/`createIdempotent` instruction as separate `ATA_CREATE` activity.
It requires the tracked wallet in parsed instruction info and valid mint and
account keys. It does not create a token balance delta, amount, price, or trade
classification. Failed transactions and instructions for a different wallet
do not produce the activity. The wallet read model counts instruction-only
decodes as completed while provider source-history completeness stays
`UNKNOWN`/incomplete.

The Wallet Investigator displays `ATA CREATE INSTRUCTION` and leaves observed
balance change `UNKNOWN`. RED/GREEN verification: worker, persistence,
read-route, and holder-graph group **22 passed** with 2 existing deprecation
warnings; Wallet Detail component suite **3 passed**. Full Ruff/mypy and
broader current-tree tests after this slice remain pending. The overall wallet
transaction taxonomy remains below 9 because verified DEX swap/liquidity
instruction identities and first-block participant decoding are not yet
available. PostgreSQL remains `BLOCKED_HOST`; live wallet history and mature
outcomes remain unverified.


## V8.3 periodic wallet reputation refresh — 2026-10-13

Tracked monitoring wallets now receive checkpointed as-of reputation refreshes independently of new token candidates. The worker processes one eligible Solana wallet per existing cycle, reads at most 5,000 matching persisted activity rows through the new indexed `observations.wallet_address` projection, skips capped scans, and emits a snapshot only when an observed completed trade round trip exists. Repeated polls do not duplicate unchanged history; a later persisted trade delta triggers a new snapshot. SQLite timestamps are normalized as UTC before domain rehydration. Snapshot history completeness remains `UNKNOWN`; no real profitability or smart-money status is claimed.

Verification: wallet builder 2 passed; periodic SQLite refresh 1 passed including cap/idempotence/delta; related wallet family 43 passed; read/persistence/API wallet group 94 passed (7 existing warnings); migration and release identity contracts 7 passed; Ruff and mypy (181 files) passed; migration graph has one head `0020_wallet_activity_addr_idx` / 34 tables; Alembic offline SQL generation passed with a synthetic URL. PostgreSQL runtime is `BLOCKED_HOST`; real wallet history, mature outcomes, and OOS remain unverified.

Current-tree acceptance after decision-linked wallet timeline: `UV_CACHE_DIR=/tmp/memeradar-uv-cache uv run pytest tests/unit -q` completed with **1,641 passed**, 10 deprecation warnings, in 147.37 seconds. `apps/web` `npm test` completed with **210 passed** across **32 files** in 41.59 seconds; `npm run build` passed with 28 routes. Current-source five-viewport Playwright completed with **85 passed, 10 configured skips, 0 failed** in 7.6 minutes; the server bound successfully. Full Ruff, mypy (181 source files), web typecheck/ESLint, and `git diff --check -- . ':!.env.example'` passed. PostgreSQL runtime remains `BLOCKED_HOST`; provider-backed wallet history, mature outcomes, and locked OOS remain unverified.
## V8.3 canonical timeline — decision-linked wallet activity — 2026-10-13

The bounded Token Investigator timeline now projects exact `wallet.activity`
observations for wallet addresses recorded in a persisted candidate decision
snapshot, matching only the token's exact mint. The read uses the indexed
wallet identity projection and applies event-time range, stable cursor, and
event/observed/ingested cutoff predicates. It reports the new source in the
existing per-source cap contract. SQLite acceptance covers three-page
continuation, unrelated wallet/token exclusion, and activity not yet available
by the replay cutoff.

The projected payload is limited to the wallet/token identity, normalized
action/classification, raw token amount, and quote-side raw amount/mint only
when an exact Pump.fun trade event is persisted. Provider signatures and raw
source IDs are omitted. The frontend shows a decision-linked wallet activity
panel; balance-only activity is explicitly UNKNOWN as a trade, and no price or
PnL is inferred.

Verification: read API, persistence and route group **105 passed** with 7
existing deprecation warnings; Token Detail focused tests **2 passed**; Ruff,
mypy (**181 files**), web typecheck and ESLint passed. Full current-tree backend,
frontend, build and Playwright acceptance remain pending. PostgreSQL runtime is
`BLOCKED_HOST`; real wallet history, mature outcomes and locked OOS remain
unverified. Canonical timeline engineering maturity is rescored **8.4/10**,
still below 9 because creator/funder/bundle streams and complete legacy-source
availability remain unresolved.

## V8.3 exact creator and token-authority roles — 2026-10-13

The existing bounded Token Investigator timeline now projects CREATOR only
from a verified Pump.fun `create`/`create_v2` event and MINT_AUTHORITY /
FREEZE_AUTHORITY only from persisted Helius token metadata. The existing Token
Detail page renders those roles independently and labels unsupported roles
UNKNOWN. Invalid authority identities remain INVALID without an address.
This projection does not equate creator with deployer, fee payer, liquidity
provider, metadata authority, token-account owner, or common ownership.

Verification: exact-role persistence regressions **2 passed**; the complete
read-persistence unit file **53 passed**; complete Token Detail suite **46
passed**; Ruff, mypy (**181 source files**), web typecheck, and ESLint passed.
Full current-tree backend/frontend/build and Playwright acceptance remain
pending after this UI change. PostgreSQL is `BLOCKED_HOST`; real provider role
coverage, mature outcomes, and OOS remain unverified.

## V8.3 timeline evidence-domain completeness — 2026-10-13

The canonical bounded Token Investigator timeline now reports separate tri-state
persisted-read completeness for wallet evidence and creator/authority evidence.
Those states require an uncapped first-page source scan and valid projected
links; wallet evidence also requires uncapped wallet activity and reputation
reads when decision-linked wallets exist. This does not certify provider
collection. Bundle membership remains `UNKNOWN` because no canonical bundle
source is queried, with `BUNDLE_MEMBERSHIP_SOURCE_NOT_QUERIED` in omissions.
Generic candidate/alert completeness remains false where legacy sources lack
availability timestamps; strict causal-source completeness remains separate.

Verification: read API, persistence, and route suites **107 passed** with 7
existing deprecation warnings; read-client and Token Detail suites **104
passed**; Ruff passed; mypy passed for **181 source files**; web typecheck and
ESLint passed. PostgreSQL runtime remains `BLOCKED_HOST`; full current-tree
backend/frontend/build and Playwright remain pending after this source change.

## V8.3 exact native SOL transfer activity — 2026-10-13

The existing finalized wallet decoder now classifies a successful parsed
System Program `transfer` only when the requested signature, account keys,
tracked-wallet endpoint, distinct counterparty, and positive u64 lamport amount
all match. The persisted/API activity carries raw lamports, direction,
counterparty, instruction reference, timestamps, and parser provenance. It is
displayed separately from SPL balance deltas and makes no token-trade, price,
PnL, or creator-lineage claim. Other parsed/compiled System instruction forms
and unverified DEX/AMM/liquidity schemas remain unclassified.

RED/GREEN focused worker, persistence, and API tests passed **17**; web
read-client and Wallet Investigator tests passed **63**; Ruff, mypy (**181
files**), web typecheck, ESLint, and diff hygiene passed. Full current-tree
backend/frontend/build and five-viewport Playwright acceptance are the next
gate. PostgreSQL runtime is `BLOCKED_HOST`; real wallet history and mature
outcomes remain unverified.

The current-tree full backend unit suite has now completed: **1,645 passed, 10
existing deprecation warnings, 0 failed** in 143.76 seconds. Frontend full
suite, production build, and five-viewport Playwright remain pending.

The current-tree frontend Vitest suite has completed: **212 passed across 32
files** in 38.73 seconds. Typecheck, ESLint, production build, and
five-viewport Playwright are still separate pending gates.

Current-tree `npm run typecheck`, `npm run lint`, and `npm run build` passed;
the build emitted **28 routes**. Repository-wide Ruff passed, mypy passed for
**181 source files**, and `git diff --check -- . ':!.env.example'` exited 0.
Current-source `npx playwright test` passed **85 tests**, with **10
configured skips** and **0 failures**, in **7.5 minutes** across five
viewport projects. The wallet transaction taxonomy is locally verified for
the exact supported protocols; unverified DEX/liquidity schemas, PostgreSQL,
real wallet history, mature outcomes, and locked OOS remain blocked or
unverified.

## V8.3 Rule Impact V2 and current-tree acceptance — 2026-10-13

The existing bounded Rule/Outcome association now includes a separate strict
miss review. Counts are available only for complete candidate/rule/policy
cohorts with exact matured outcomes and complete bounded candidate, reevaluation,
promotion, alert, and outcome history. Otherwise the API returns
`INSUFFICIENT_DATA`; association is still explicitly non-causal. Failure/rug
filtered counts remain UNKNOWN without a complete typed denominator.

Current full verification: backend **1,652 passed** (10 existing deprecation
warnings); frontend **213 passed across 32 files**; web typecheck, ESLint,
production build (28 routes), Ruff, mypy (**182 source files**), diff check,
and five-viewport Playwright **85 passed / 10 configured skips / 0 failed** in
**7.5m**. PostgreSQL runtime remains `BLOCKED_HOST`; provider-backed wallet
history, mature real outcomes, and locked OOS remain unverified.

## V8.3 wallet source-history completeness semantics — 2026-10-13

Cursor exhaustion, short provider pages, request failures, and decode
observations do not prove provider-wide wallet history completeness. The
worker no longer records `source_history_complete=false` for those cases; the
bounded read projection remains UNKNOWN, and only an explicit TRUE may pass
through the API when separately proven. The TypeScript parser rejects legacy
FALSE values and the Wallet Investigator displays UNKNOWN unless the value is
TRUE. Focused backend read/API/worker tests passed **102** with 7 existing
deprecation warnings; read-client/Wallet Investigator Vitest passed **63**;
Ruff, mypy (**182 source files**), web typecheck, ESLint and diff hygiene
passed. Full backend/frontend/build/browser acceptance remains pending after
this final source/UI correction. Provider history, PostgreSQL runtime, mature
outcomes and locked OOS remain unverified.

## V8.3 decision-linked prelaunch creator transfer projection — 2026-10-13

The canonical bounded token timeline now links a finalized native SOL transfer
to a verified Pump.fun creator only when the sender appears in timestamp-valid
wallet evidence persisted in a candidate decision, the transfer predates the
exact launch, and event/observed/ingested times are available by the requested
cutoff. The Token Investigator shows raw lamports, wallet and creator, event
times, and source-specific projection completeness. It states that a transfer
does not prove funding purpose or common ownership and that this projection
covers only the persisted decision-linked wallet cohort. Provider collection
completeness remains UNKNOWN; no row is not proof that no other funder
existed. This is transfer evidence, not complete creator-funder lineage.

Focused verification: persistence + API-route files **86 passed**;
read-client + Token Detail Vitest **106 passed**; web typecheck and ESLint
passed; Ruff passed; mypy passed (**182 files**). The SQL regression checks
exact creator identity, transfer direction, prelaunch timing, as-of-observed
availability, and excludes wrong wallet/recipient/direction, post-launch, and
not-yet-observed transfers. Full backend/frontend/build and five-viewport
Playwright acceptance must be rerun after this source/UI change. PostgreSQL
runtime remains `BLOCKED_HOST`; provider history, mature outcomes, and locked
OOS remain unverified.

## V8.3 bounded timeline, wallet coverage, and provider-role audit — 2026-10-13

The canonical timeline's strict causal candidate/alert completeness is
separate from generic legacy history. Legacy sources without availability
timestamps remain explicitly omitted and incomplete; source caps provide
bounded continuation; bundle membership remains UNKNOWN when its source is
not queried. Wallet decode-attempt coverage already uses distinct signatures
and exact wallet/signature pairs, and withholds the ratio on empty or capped
scans. Provider-wide wallet history remains UNKNOWN.

The Token Investigator now includes the existing GMGN deployer label only as
`UNVERIFIED_PROVIDER_CLAIM`, requiring an explicit evidence flag, token link,
GMGN provider identity, and chain-valid address. Other provider fields are
not projected; the claim does not affect risk, score, ownership, or funding.
Verification: timeline persistence 2 passed + Token Detail 48; wallet
coverage persistence 2 + Wallet Detail 5; creator role backend 56 + API routes
33 + Token Detail 48; Ruff, mypy (182 files), web typecheck and touched-file
ESLint passed. Current full-tree backend/frontend/build/Playwright is pending.
PostgreSQL runtime is BLOCKED_HOST; provider-complete wallet/funder history,
mature outcomes, and locked OOS remain unverified.


## V8.3 Wallet Investigator graph navigation — 2026-10-13

Wallet Detail now links a valid canonical address into the existing Wallet Graph. The graph page accepts one valid wallet query and pre-fills its search input without automatically issuing a graph request. This is a navigation improvement only; it does not change graph API limits, wallet score semantics, or execution authority. Focused tests passed **15/15**; web typecheck and touched-file ESLint passed. Full current-tree frontend/build/Playwright acceptance remains pending, and Wallet Investigator still lacks a reverse list of persisted decision evidence associated with the wallet.

## V8.3 Wallet decision evidence and final current-tree acceptance — 2026-10-13

Wallet Investigator now shows a bounded reverse list of exact persisted
candidate/token decision evidence linked to the wallet. Rows include recorded
use state, score/gate flags, event/observed/ingested times, reason and quality.
Wallet reputation is shown only from a matching snapshot whose evidence and
availability timestamps precede the decision; it remains informational and no
numeric contribution is invented. Capped scans, truncated sources, omitted
rows, and empty matches are disclosed without treating absence as proof.

This supersedes the earlier pending/reverse-history statement above.

Current-tree verification: backend unit suite **1,658 passed**, 10 existing
warnings; frontend Vitest **218 passed across 33 files**; typecheck, ESLint,
production build (**28 routes**), Ruff, mypy (**182 files**), and diff check
passed. Five-viewport Playwright completed **85 passed, 10 configured skips,
0 failed** in **9.4 minutes**. PostgreSQL runtime remains `BLOCKED_HOST`; real
wallet history, provider-complete creator funding/bundle evidence, mature real
outcomes and locked OOS remain unverified.

## V8.3 Wallet Investigator creator-transfer trace — 2026-10-13

Wallet Detail now also shows a bounded reverse trace of persisted outgoing
native SOL transfers from the exact tracked wallet to a recipient whose next
Pump.fun create/create_v2 launch is verified, canonical, and finalized. The
read requires transfer event, observation, and ingestion times to precede the
launch event; transfers observed or ingested after launch are excluded. The
profile shows raw lamports, transfer and launch timestamps, provider/parser/
quality, token navigation, and bounded scan/omission disclosures. This is
`PRELAUNCH_TRANSFER_ONLY`: it does not prove funding purpose, common ownership,
or provider-complete creator funding. It complements the existing token-side
projection, which is restricted to decision-linked wallets.

Focused creator-transfer persistence/API regressions: **3 passed**; complete
read persistence/API suites: **93 passed**, 7 existing warnings. Wallet Detail
and read-client Vitest: **66 passed**; full frontend: **220 passed across 33
files**; full backend: **1,660 passed**, 10 existing warnings. Ruff, mypy (182
files), Python/web type checks, full `eslint .`, and diff-check passed.
Production build passed with 28 routes. The first four-worker browser attempt
reported 84 passed / 10 skipped / 1 tablet navigation hydration timeout; the
same test passed isolated, and the unchanged five-viewport matrix passed with
two workers: **85 passed / 10 configured skips / 0 failed** in **10.2m**.
This closes the browser gate for the current UI source. The initial transient
failure is retained in the verification ledger. PostgreSQL remains
`BLOCKED_HOST`; complete creator funding, provider-backed wallet history,
mature outcomes, and locked OOS are not verified.

## V8.3 closure report and remaining external gates — 2026-10-13

The final V8.3 scorecard and closure report distinguish local engineering from
runtime and research validation. Current-source evidence is backend unit
**1,660 passed**, frontend **220 passed across 33 files**, web typecheck/full
ESLint, Ruff, mypy (**182 files**), `make typecheck`, and production build
(**28 routes**) passed. The two-worker five-viewport Playwright matrix passed
**85**, skipped **10 configured tests**, and failed **0** in **10.2m**. The
first four-worker attempt had one tablet hydration timeout; its isolated rerun
and subsequent unchanged full matrix passed.

Repository-owned contracts for bounded wallet history/reputation, wallet
decision attribution, opportunity policy, causal timeline, recovery and
reevaluation, strict miss classification, rule/outcome association, alert
observability, persisted-candidate funnel, and Token/Wallet Investigator are
scored at 9.0 engineering maturity. Remaining sub-9 rows depend on missing
provider schema/data (complete creator funding, repeated funder outcomes,
verified Jito membership/distribution, complete first-block ordering, Robinhood
frame/ABI/receipt evidence, Relay legs), real mature outcomes, or PostgreSQL
host access. These are not represented as completed features. No real alpha,
real-data validation, or OOS claim is made. See
`docs/reports/MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md` and
`docs/audits/V8_3_9PLUS_SCORECARD.md` for the detailed evidence and retry
conditions.

## Documentation cleanup and Wallet Graph browser boundary — 2026-10-13

Documentation cleanup retained every existing documentation file. The docs
inventory grew from 173 files / 171 Markdown files at task recovery to 193 /
191 after adding indexes, the complete cleanup report, route/API/ObsidianUI audit
records, and resumable checkpoints; five superseded or conflicted documents
were archived with original-path pointers. The report lists all 193 retained
files and explains their retention reasons. A repository-local Markdown scan
checked 189 relative links and found no missing targets.

A browser-only Wallet Graph API boundary defect was fixed with a bounded
same-origin Next route that reuses existing authenticated readers. No backend
business logic or execution permissions changed. Current frontend verification:
Vitest 224/224, focused gateway/helper/component tests 12/12, typecheck, ESLint,
production build (28 routes), targeted Playwright 10/10, and full five-viewport
Playwright 90 passed / 10 configured skips / 0 failed in 8.2 minutes. Diff check
passed. ObsidianUI was audited at its published registry/index level and not
installed because its available components did not fit the evidence-first
workflows or would add overlapping styles/motion dependencies.

This is not a full visual redesign or production acceptance. Backend tests,
Ruff and mypy were not rerun for this frontend/docs-only change. PostgreSQL
runtime remains `BLOCKED_HOST`; live provider histories, mature real outcomes,
locked OOS, manual screen-reader review, performance benchmarking, and
screenshot-based visual regression remain unverified. See
`docs/DOCS_CLEANUP_REPORT.md` and `docs/ui-redesign/FINAL_REPORT.md`.

## VNext 2.0 research workflow continuation — 2026-10-14

Current frontend changes make Radar table-first with bounded loaded-page search,
add Ultra-Early evidence-column presets while retaining all 49 fields, expose
the same evidence drawer from Mission Control, add bounded identity search to
Wallets/Pipeline/Outcomes, and provide keyboard node selection plus scoped
responsive CSS for Wallet Graph. Missed Winners inherits the shared bounded
outcome search. Backend APIs, score/risk decisions, outcome denominators,
protected modes, and the same-origin Wallet Graph gateway are unchanged.

Current-tree verification: frontend Vitest **239/239**, typecheck PASS, ESLint
PASS, production build PASS (**28 emitted App Router entries**), and static
route gzip budgets PASS. Final-source browser screenshots, route E2E, runtime
accessibility, and Web Vitals remain blocked/unverified because the host has
previously returned `listen EPERM` for the local Next server and `Operation not
permitted` for Chromium. No retry or security workaround was attempted. See
`docs/ui-redesign-vnext/FINAL_REPORT.md` and `PAGE_ACCEPTANCE.md`.

## VNext UI implementation checkpoint — 2026-10-14

The first product-facing VNext slice is implemented: collapsible/persisted desktop navigation and analyst workflow groups, candidate-first Mission Control ordering, sticky Ultra-Early token identity with a horizontal-scroll cue, and copy-address actions for token and wallet profiles. Three ObsidianUI patterns were prototyped locally and selectively adapted; no upstream code or dependency was added. Backend read contracts and protected execution modes were not changed.

Historical frontend evidence (superseded by the VNext 5 acceptance record below): Vitest 230/230; typecheck PASS; ESLint PASS; production build PASS (28 app routes); `git diff --check` PASS. That checkpoint had browser E2E/screenshots blocked by host permissions, with Web Vitals and runtime accessibility unverified. See the VNext 5 report below for current evidence.

## VNext 5 final frontend acceptance — 2026-10-14

The V5 pass fixed five missing CSS selectors/utilities and replaced two
undefined Compare button class names with the shared submit style; it also
removed one redundant Wallet Graph legend modifier. The host acceptance runner
now classifies a zero-test loopback startup denial separately from an app/test
failure, and source identity includes the root CSS contract checker.

Verification: Node helper files 4/4 (23 individual tests), frontend Vitest
35/35 files / 240/240 tests, CSS contract 413 classes / 83 TSX files,
typecheck, ESLint, production build (28 App Router entries), and five static
route bundle budgets pass. Playwright collects 130 primary, 60 social/services,
20 visual fixture and 3 performance tests, but executes zero browser tests.
The actual runner records `BLOCKED_HOST_RUNTIME`, `local_server_bind`, and exits
2. No PNGs were captured; runtime accessibility and Web Vitals remain
unverified. Final state is `LOCAL_COMPLETE_EXTERNAL_BLOCKED`; no backend,
scoring, provider, alert, trading or execution behavior changed. Details and
the exact host handoff are in `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md`.

## VNext 3.0 visual refinement — 2026-10-14

Implemented a focused visual slice across Mission Control, Radar, Token
Investigation, Wallet Graph, Pipeline, Outcomes, Compare, and shared workspace
typography. Candidate investigation now precedes secondary operator metrics;
Radar's selected row is tied accessibly to its open evidence drawer; Token
Detail displays persisted score, confidence, risk, and freshness as distinct
states; Wallet Graph has a theme-aware explanation legend and static
selected-node highlight; Pipeline separates persisted totals from page-bounded
counts; Outcomes separates mark peaks from executable evidence; Compare uses
responsive same-age result/input grids. Main-workspace tables, key labels,
statuses, and compact controls now use more readable type sizes. No API,
score/risk semantics, provider behavior, protected mode, or
trading behavior changed.

Current-source evidence: core focused component suite 70/70; Pipeline/Outcomes
focused suite 16/16; Compare 2/2; full frontend Vitest 35 files / 239 tests; typecheck PASS;
ESLint PASS; final production build PASS
(28 dynamic App Router entries); final static gzip budgets PASS (`/` and
`/radar` 145,651 B, `/wallet-graph` 147,802 B, `/settings` 145,561 B,
`/readiness` 140,537 B); whitespace check PASS. Final screenshot/E2E,
runtime accessibility, and Web Vitals remain unverified. The previously
observed host restrictions are unchanged: Next bind returned `listen EPERM`
and Chromium returned `Operation not permitted`; this run did not repeat those
blocked attempts. Status remains partial. See
`docs/ui-redesign-vnext/PROGRESS.md`, `PAGE_ACCEPTANCE.md`, and
`FINAL_REPORT.md`.

## Upstream intelligence integration — resumed 2026-10-14

The current execution is continuing the wallet outcome read-path slice recorded in `docs/reports/upstream-intelligence-integration-matrix-2026-10-14.md`. A new frontend regression first reproduced that malformed `position_opened_at` was silently coerced to null (57 tests passed, the new case failed); the parser now accepts only explicit null or a valid timestamp. The follow-up frontend test command is recorded in the matrix checkpoint. `.codex` is read-only in this host, so that matrix and this status entry are the durable checkpoint. Outcome economics remain explicitly unknown because current normalized trade observations do not include a verified complete cash/cost vector. PostgreSQL and provider-backed acceptance remain unverified.

Wallet outcome projection verification update: frontend read API + Wallet Detail passed 68 tests. A new SQLite persistence query test now passes after its fixture was corrected to set the denormalized `wallet_address` field that production `observation_to_row` derives from the normalized payload. Next gate is API response serialization plus a repeat frontend run; source history and wallet economics remain conservative/UNKNOWN.

Wallet outcome API mapping now has a focused response test: inventory is serialized as decimal strings, null economics remain null, and the response remains non-executable. The focused API test passed (1; 2 existing dependency deprecation warnings); frontend read API and wallet UI passed 68 tests. The next command expands regression coverage across wallet tracking, worker refresh, persistence, and read API modules.

Wallet outcome projection regression expansion: **114 Python tests passed** across wallet FIFO, tracked-wallet discovery, worker refresh, read persistence and API routes; **68 frontend tests passed** for the read API and Wallet Detail. The Python suite emitted 7 existing FastAPI/Starlette deprecation warnings. Next verification is Ruff plus web typecheck and ESLint on touched frontend files. This does not verify PostgreSQL, live/provider history, or browser rendering.

The focused Ruff check initially found 8 formatting/import-order issues in this slice; the TypeScript checks did not run in that attempt. Those touched lines have been corrected. The next check repeats Ruff, then runs web typecheck and ESLint for the four touched frontend files.

Typecheck initially found one incomplete `WalletRecord` test fixture in `wallets.test.tsx`; the fixture now supplies empty bounded outcome history and an uncapped flag. The full web typecheck and touched-file ESLint are next.

The explicit creator role path is now complete at the current local evidence boundary: the existing Pump.fun forward collector emits typed `CREATOR` role evidence only from canonical `create`/`create_v2` launch records with a source creator address; it persists atomically with the existing creator-history observation. The wallet detail read returns at most 50 as-of role rows with provenance/quality, and the UI calls them observed roles while explicitly stating that they do not establish common ownership. Other role classes remain unproduced because a complete verified source is absent. A red worker integration assertion first confirmed the missing role row; after implementation, worker idempotency passed. SQLite as-of read, API provenance/ownership, and frontend parser/UI tests also passed.

Verification after this role slice: **137 Python tests passed** across forward evidence, wallet outcome/reputation, operator memory, read persistence, and API routes (7 pre-existing FastAPI/Starlette deprecation warnings); **74 frontend tests passed** across read API and wallet components; touched Python Ruff, web typecheck, and touched-file ESLint passed. The first role read attempt failed on a nonexistent helper name, fixed by projecting the existing `ProvenanceView` directly. Migration/PostgreSQL, external wallet-history completeness, verified router/Relay/Jito data, browser screenshots/accessibility, and live performance remain unverified or externally blocked; no claim is made for them. The durable current checkpoint remains in `docs/reports/upstream-intelligence-integration-matrix-2026-10-14.md` because `.codex` is host-read-only.

The upstream closure then added two narrowly scoped local contracts. Robinhood
`PendingTradeIntent` has deterministic transaction/index identity and a
fail-closed join to the existing receipt lifecycle; an intent can mature wallet
outcome only with matching finalized receipt and fill evidence. The provider-
neutral Relay correlation contract retains one-sided legs, expires incomplete
observations, correlates only exact Relay order IDs, and never asserts wallet
ownership. Their focused tests passed (6 total). These are not yet a persisted
worker/API/UI pipeline: verified sequencer/Relay source schemas and provider
data remain unavailable, so no operational capability is claimed. Ruff and
repository-wide validation are pending; see the matrix for the next exact gate.
