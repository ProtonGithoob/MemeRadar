# MemeRadar Status

Last updated: 2026-09-20

This is the current authoritative project state. Historical checkpoint detail
was consolidated here; implementation contracts remain in the canonical
documents below.

## Current classification

| Dimension | Current state | Evidence / constraint |
|---|---|---|
| System stage | `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION` | The canonical stream-to-alert/research path and PostgreSQL-backed restart/idempotency contracts are locally verified; external source and statistical alpha validation are separate. |
| Stack readiness | `PASS` (`STACK_READY / DEGRADED`) | A bounded Compose run passed PostgreSQL, Redis, API liveness/readiness, worker startup, web reachability and protected-mode checks on isolated ports. |
| Core provider readiness | `READY_FOR_FREE_READ_ONLY_SHADOW` (HTTP/raw transport) / `BLOCKED_EXTERNAL` (launch acceptance) | Public Solana RPC, parsed versioned transaction enrichment and WebSocket transport are available; a keyless Pump.fun raw source and verified create/create_v2 registry routes are now present, but no accepted live launch has reached durable runtime evidence. |
| Shadow collection | `BLOCKED_EXTERNAL` (`NOT_ACCEPTED_LIVE`) | The worker now has a bounded public-RPC source factory. Live acceptance still requires a real launch to traverse source, gap/decoder checks and persistence; no alpha claim is made. |
| Real-world alpha | `REAL_WORLD_ALPHA_NOT_YET_PROVEN` | Historical-real and matured live-shadow samples remain insufficient. |
| Production readiness | `NOT_PRODUCTION_READY` | See [Production Readiness](PRODUCTION_READINESS.md). |
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

The source intentionally fetches launch-shaped notifications only. Trade-window
collection, creator instruction-data decoding, and accepted live-shadow launch
counts remain separate work. The protected modes remain unchanged and the
source cannot authorize paper or live execution.

## 2026-09-20 early-alpha integration and operational closure

The approved early-alpha integration was implemented through commit `a522c99`
(`feat: persist staged alert delivery timing`); this closure pass adds the
PostgreSQL-backed runtime snapshot and restart fixes described below. The
authoritative baseline audit is [EARLY_ALPHA_GAP_AUDIT.md](EARLY_ALPHA_GAP_AUDIT.md);
the design and execution record are [the design spec](superpowers/specs/2026-09-19-early-alpha-runtime-integration-design.md),
[the implementation plan](superpowers/plans/2026-09-19-early-alpha-runtime-integration.md),
and [the source matrix](EARLY_ALPHA_SOURCE_MATRIX.md).

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

The report artifact is [early-alpha/report.md](../artifacts/research/early-alpha/report.md)
with machine-readable [report.json](../artifacts/research/early-alpha/report.json).
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
- Pump.fun `create`, `create_v2` and `buy_v2` now have exact authoritative
  registry entries; other protocol rows remain `TODO_VERIFY`,
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
[closure gap matrix](PROD_READ_ONLY_CLOSURE_GAP_MATRIX_2026-09-15.md).

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
matrix](GMGN_ROOT_CAUSE_HARDENING_GAP_MATRIX_2026-09-14.md). The committed
requirements and plan remain the [integration specification](superpowers/specs/2026-09-14-external-alpha-intelligence-integration.md)
and [implementation plan](superpowers/plans/2026-09-14-external-alpha-intelligence-integration.md).

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

The canonical UI contract is now [apps/web/DESIGN.md](../apps/web/DESIGN.md),
and the route/field inventory is
[FRONTEND_BACKEND_PARITY.md](FRONTEND_BACKEND_PARITY.md). The audit covered
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

- [Master specification](MASTER_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Research extensions](ROADMAP_RESEARCH_EXTENSIONS.md)
- [Data model](DATA_MODEL.md)
- [Scoring and risk](SCORING_AND_RISK.md)
- [Provider contracts](PROVIDERS.md)
- [Security](SECURITY.md)
- [Testing](TESTING.md)
- [Production readiness](PRODUCTION_READINESS.md)
- [Live read-only checklist](LIVE_READONLY_CHECKLIST.md)
- [Live-shadow validation](LIVE_SHADOW_VALIDATION.md)
- [Release runbook](RUNBOOKS/RELEASE.md)
- [Free-first migration report](FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md)
- [Alpha caller extension](ALPHA_CALLER_INTELLIGENCE_EXTENSION.md)
- [Current opportunity-discovery plan](superpowers/plans/2026-09-05-opportunity-discovery.md)
- [Current alpha-caller design](superpowers/specs/2026-09-07-alpha-caller-multichain-design.md)
- [Current real-alpha readiness plan](superpowers/plans/2026-09-07-real-alpha-production-readiness.md)

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
