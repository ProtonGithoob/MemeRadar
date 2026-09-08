# MemeRadar Production Readiness

**Current checkpoint:** Real Alpha Production Readiness Task 15 acceptance is evaluated; the staged production gates remain not accepted because real evidence and hosted operational gates are externally blocked.

**Current classification:** `NOT_PRODUCTION_READY` for real-alpha or live-money claims. Engineering verification is strong, but checked-in alpha evidence remains `SYNTHETIC_REDACTED` / `INSUFFICIENT_SAMPLES` and real X/Telegram/provider/live-shadow evidence is still externally incomplete.

Canonical spec: `docs/superpowers/specs/2026-09-07-real-alpha-production-readiness-design.md`

Execution plan: `docs/superpowers/plans/2026-09-07-real-alpha-production-readiness.md`

## Staged target

| Stage | Meaning | Current |
|---|---|---|
| `PROD_READ_ONLY` | Real providers/ingestion/API/dashboard/Telegram, no order creation | NOT ACCEPTED |
| `PROD_PAPER_AUTO` | Real-time fail-closed automated paper positions, no signing/live orders | NOT ACCEPTED |
| `LIVE_MONEY_CANDIDATE` | Evidence package may be reviewed under a separate future design | NOT ELIGIBLE |

Protected modes remain:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Acceptance gates

| Gate | Requirement | Current status | Evidence / what closes it |
|---|---|---|---|
| PR-1 Engineering/release | Canonical tests, lint/typecheck, migrations, security/SBOM, build, remote CI, release identity, rollback | `PARTIAL/BLOCKED_EXTERNAL` | Task 12 adds the gated release-identity artifact and rollback runbook. Local gates pass, but hosted GitHub Actions success for the exact candidate and a real deployment rollback remain externally unverified. |
| PR-2 Provider/evidence | Required real chain/market/social/Telegram capabilities with freshness/provenance and stable doctors | `BLOCKED_EXTERNAL/PARTIAL` | `make free-provider-doctor` reaches `READY_FOR_FREE_READ_ONLY_SHADOW`; social, Telegram and stream doctors report `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`. Configure compliant real access and prove bounded reads. |
| PR-3 Historical-real research | Leakage-safe real positive/negative dataset and real ablation | `INSUFFICIENT_SAMPLES` | `fixtures/research/opportunity_research_report.json` remains `SYNTHETIC_REDACTED`; the new `historical_real_dataset_validation.json` reports zero matured calls/outcomes and no historical-real evidence. Collect real calls/outcomes and rerun the canonical gate. |
| PR-4 Live-shadow | Sustained real observation, replayability, latency/freshness and matured paper outcomes | `INSUFFICIENT_SAMPLES` | Task 8 now provides restart-safe run identity, idempotent normalized-event fingerprints, unresolved-gap blocking, provider snapshots, closure and `14 days + 200 matured actionable signals` classification. No real shadow window or matured live evidence exists yet. |
| PR-5 Operations | Backups/restore, monitoring/alerts, soak/failure tests, deployment/rollback runbooks | `PARTIAL/BLOCKED_EXTERNAL` | Tasks 10 and 13 provide disposable restore evidence, telemetry contracts and a bounded synthetic failure matrix. Managed backup scheduling, real deployment restore objectives, dependency restarts and production-like soak acceptance remain unverified. |
| PR-6 PROD_READ_ONLY | PR-1 + PR-2 + PR-5 PASS | `NOT_ACCEPTED` | Complete its three prerequisite gates; PR-3/PR-4 may remain insufficient while collecting evidence. |
| PR-7 PROD_PAPER_AUTO | PR-1..PR-5 PASS plus real-environment paper-auto fail-closed acceptance | `NOT_ACCEPTED` | Complete all evidence and operational gates in a real deployment. |
| PR-8 LIVE_MONEY_CANDIDATE | Separate future operator-approved design plus all prior evidence | `OUT_OF_SCOPE` | Never auto-enable from this roadmap. |

## Task 1 evidence snapshot — 2026-09-07

The initial inventory was checked against the actual checkout after a safe
fast-forward from `2acf261` to `0dc07f8`. The local checkout and `origin/main`
are synchronized (`git rev-list --left-right --count origin/main...HEAD` =
`0 0`). The four unrelated pre-existing WIP files remain untracked and
untouched:

- `docs/superpowers/plans/2026-09-05-multichain-extreme-winner.md`

Observed evidence:

- `make verify` passed at the Alpha Caller checkpoint with `1080` Python tests
  passed, `11` skipped, `1` warning, and `54` Vitest tests passed. Ruff,
  strict mypy, Compose config, secret scan, migrations, security review and
  SBOM were green. SBOM identity is `581` components,
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- `make migration-check` reports head `0008_alpha_caller_intelligence` and
  `25` tables. `make security-review` reports `PASS`, but external container,
  npm and pip scans are `NOT_RUN` / `BLOCKED_EXTERNAL`.
- `make free-provider-doctor` reports core `PASS` and
  `CORE_FREE_READINESS=READY_FOR_FREE_READ_ONLY_SHADOW`; Solana RPC and
  DexScreener were reachable in this bounded check. Optional Helius, Birdeye,
  RugCheck, external wallet, social analytics and Telegram are
  `UNCONFIGURED_OPTIONAL`; Ollama is `OPTIONAL_UNAVAILABLE`.
- `make paper-trading-doctor` reports `PASS` with `paper_auto_gate=PASS`, live
  execution disabled and the exact protected modes. `make compose-config`
  passes.
- `make social-doctor`, `make telegram-doctor` and
  `make stream-integrity-doctor` each report `BLOCKED_EXTERNAL` because their
  configured endpoint/credential set is missing. `make reliability-doctor`
  reports keyless contracts `PASS` but `backup_restore=DOCUMENTED_ONLY` and
  `BLOCKED_EXTERNAL` because external acceptance was not run.
- `current_run.json` and `python3 scripts/shadow_status.py` show the latest
  shadow attempt as `START_FAILED` / `STACK_OFFLINE`, with collection
  `NOT_ACTIVE`, evidence `NOT_AVAILABLE` and matured outcomes `UNKNOWN`.
- `docs/RUNBOOKS/RELIABILITY.md` and `docs/DATA_RETENTION.md` document the
  non-destructive isolated `pg_dump`/`pg_restore` procedure, but no restore
  drill or production-like soak has been completed.
- The Alpha Caller artifact records `SYNTHETIC_REDACTED`, seven checked-in
  cases, `INSUFFICIENT_SAMPLES`, `promotion_allowed=false` and
  `execution_eligible=false`; no historical-real or live-shadow sample is
  claimed.

Required external inputs are compliant X/social historical/live access,
Telegram Bot API/channel access where authorized, any selected paid provider
credentials, a reachable production-like database/restore target, and a
hosted CI/release run. Secret values must remain outside reports and git.

### Task 2 evidence snapshot — 2026-09-07

The required-provider contract now has one provider-neutral status vocabulary:
`READY`, `DEGRADED`, `RATE_LIMITED`, `STALE`, `CONFIGURATION_MISSING`,
`BLOCKED_EXTERNAL`, `UNSUPPORTED`, plus explicit `UNKNOWN` for unprobed or
missing evidence. The shared `ProviderCapabilityStatus` normalizer is used by
the aggregate free-first doctor and read-only `/v1/providers/health`; the
legacy provider health state remains available for compatibility.

The application/evidence boundary is tested: `/health/live` and `/health/ready`
report only API/dependency health, while `/v1/providers/health` reports
capability status. Optional provider absence does not block application
readiness. Existing shared transport tests cover bounded deadlines, retries,
backoff, rate-limit waits, circuit-open behavior and freshness degradation for
the chain, market/reference quote, execution-quote, social and Telegram
adapter seams.

Evidence for this slice:

- focused provider/transport/health/doctor/read suites: `49 passed`, one
  existing Starlette deprecation warning;
- `make lint`: PASS;
- `make typecheck`: PASS, strict mypy over `119` source files;
- `./.venv/bin/python scripts/free_provider_doctor.py --no-network`: the free core remains
  `READY_FOR_FREE_READ_ONLY_SHADOW`; optional social, Telegram, stream and
  enrichment access remains unconfigured or externally blocked;
- `make verify`: PASS with `1081` Python tests, `11` skipped, `1` warning and
  `54` Vitest tests; Ruff, strict mypy over `119` source files, Compose config,
  secret scan, migration check, security review and the `581`-component SBOM
  also pass;
- no live provider, historical-real dataset or live-shadow success is claimed;
  PR-2 therefore remains `BLOCKED_EXTERNAL/PARTIAL`.

The four pre-existing unrelated WIP files remain untracked and untouched. The
protected modes remain exactly `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.

### Task 3 evidence snapshot — 2026-09-07

The existing social and Telegram adapters now have a shared application
collector orchestration seam. Historical collection follows provider cursors
within a bounded page count; live collection is one bounded resumable batch.
Normalized calls are ordered by event time, exact duplicates are idempotently
ignored, explicit edited observations replace earlier content, conflicting
message identities fail closed, and unresolved ticker/name references remain
separate from chain-qualified addresses. Persistence is injected through the
existing social-call repository contract, retaining provider/source IDs,
timestamps, parser/provenance/freshness and edit/delete state without a new
storage or alert engine.

The collector report includes page/fetch/unique/duplicate/persist counts,
cursor state and ingestion lag. Social and Telegram doctors include a
collector status, but health probes never claim collection success: this
checkout reports `CONFIGURATION_MISSING` and `ingestion_lag_seconds=null` for
both because no compliant external access is configured.

Evidence for this slice:

- focused social/Telegram/provider/collector tests: `17 passed`;
- `make migration-check`: PASS, head `0008_alpha_caller_intelligence`, `25`
  tables;
- `make verify`: PASS with `1083` Python tests, `11` skipped, `1` warning and
  `54` Vitest tests; strict mypy covers `120` source files, and Ruff, Compose,
  secret scan, security review and the `581`-component SBOM pass;
- social and Telegram live/historical acceptance remains `BLOCKED_EXTERNAL`;
  no historical-real or live-shadow alpha evidence is claimed.

The four unrelated WIP files remain untouched and protected modes remain
exactly `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
`AUTO_EXECUTION=false`.

## Task 4 evidence snapshot — 2026-09-07

The existing opportunity case-study/replay path now has a versioned
`HistoricalDatasetValidator` and read-only `scripts/historical_dataset.py`
artifact. It reuses the existing chronological TRAIN/VALIDATION/TEST split,
preserves chain/archetype/market-regime/cohort counts and event-time bounds,
tracks caller/source concentration in TEST, and records explicit maturity and
negative-control counts. Future outcome targets remain outside event-time
samples; no scoring weight or replay engine was added.

The focused TDD suite passes `5 tests`: the initial validator import failed as
expected, then winner-only data remained `INSUFFICIENT_SAMPLES`, caller
concentration above the `10%` TEST cap was rejected, and chronological
metadata/no-lookahead artifact contracts passed. `make lint` passes and strict
`make typecheck` passes over `121 source files`. The generated
`fixtures/research/historical_real_dataset_validation.json` honestly reports
`INSUFFICIENT_SAMPLES`, `0` matured calls, `0` matured token outcomes, `0`
caller identities, evidence class `SYNTHETIC_REDACTED`, and missing required
historical-real cohorts. This is a validation contract, not real-data proof.

The external blocker is unchanged: compliant X/social and Telegram history/live
access is not configured, so no historical-real samples are fabricated.

## Task 5 evidence snapshot — 2026-09-07

The existing caller-discovery analyzer now derives its retrospective search
boundary from the earliest executable outcome crossing when available, rather
than treating the anchor message as the move boundary. Calls after that
event-time cutoff remain held out; late pre-move calls remain classified as
late. Deleted calls are excluded from caller selection, while deleted and
unresolved historical call evidence adds explicit UNKNOWN reason/quality state.
The implementation reuses `HistoricalCallerOutcome`,
`SocialCallObservation` and the existing caller profile/backfill path; no
second discovery or scoring engine was added.

Task 5 focused TDD passes `9 tests` across caller discovery and outcome
projection, including first-executable-move cutoff, post-move exclusion,
late-call retention, unresolved/deleted UNKNOWN handling and existing
winner/negative-control/future-call contracts. The full `make verify` gate
passes with `1091` Python tests, `11` skipped, `1` warning, `54` Vitest tests,
strict mypy over `121 source files`, Ruff, Compose, secret scan, migration
head `0008_alpha_caller_intelligence` / `25` tables, security review PASS and
the existing `581`-component SBOM digest. No real social/provider success,
historical-real evidence or production-ready classification is claimed;
compliant X/Telegram access remains external and the checked-in evidence is
still `SYNTHETIC_REDACTED` / `INSUFFICIENT_SAMPLES`.

## Task 6 evidence snapshot — 2026-09-07

The existing provider-independent caller outcome projector now separates
market/reference marks from executable prices. Executable MFE/MAE and 2x/5x/
10x/20x/50x/100x labels require explicit execution/effective/fill price
evidence at both entry and the later observation; a mark-only move remains
market evidence and cannot become an executable return. Missing entry evidence
adds `EXECUTABLE_ENTRY_UNKNOWN` and leaves executable returns nullable.

`HistoricalExecutionTimeline` records signal-to-decision time, decision-to-quote
time, evaluation-time quote age, optional decision market cap/token age,
call-time liquidity/impact, modeled fee/slippage/priority cost, partial-fill
ratio and explicit `OBSERVED`/`NOT_OBSERVED`/`UNKNOWN` MEV exposure. Missing
priority/MEV or cost evidence remains `UNKNOWN`; no provider claim is inferred.
The timeline is attached to the existing outcome model and does not add a
paper/execution engine or alter production scoring weights.

Task 6 focused TDD passes `35 tests` across caller outcomes, discovery,
performance, KOL and provider contracts; the initial mark-only tests failed as
expected before the projector change. `make lint`, strict `make typecheck` over
`121 source files` and `git diff --check` pass. Full `make verify` exits `0`
with `1093` Python tests passed, `11` skipped, `1` warning and `54` Vitest
tests passed; migration head is `0008_alpha_caller_intelligence` / `25`
tables, security review is PASS and the existing `581`-component SBOM passes.
The bare-system focused API collection lacked FastAPI, but the repository
`.venv` full gate passed. Real historical/provider/live-shadow evidence is not
claimed; compliant access remains `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`.

## Task 7 evidence snapshot — 2026-09-07

The existing caller profile read model now exposes an explicit `evidence_class`
without inferring realness from provider names or confidence. Profiles preserve
`HISTORICAL_REAL`, `SYNTHETIC_REDACTED`, `MIXED` or `UNKNOWN`, alongside the
existing sample/maturity counts, executable 2x/5x/10x/20x/50x/100x rates,
rug/failure counts, executable MFE/MAE, specialization, confidence intervals,
no-lookahead state, provenance and reason codes. The endpoint remains the
existing bounded, confidence-sorted, filterable and cursor-paginated
`/v1/caller-profiles` read path.

The existing callers surface is now a read-only caller leaderboard: it renders
sample adequacy, evidence class, executable multiple rates, MFE/MAE,
rug/failure counts, specialization, confidence and provenance while retaining
explicit UNKNOWN values and the locked execution boundary. No second caller
score, persistence engine, production weight or follow/copy control was added.

Task 7 focused TDD passes `8 backend profile/read tests`, `2 gateway tests` and
`3 UI tests`; the initial evidence-class contract failed at the missing read
field before the minimal extension. Full `make verify` exits `0` with `1094`
Python tests passed, `11` skipped, `1` warning and `55` Vitest tests passed;
strict mypy covers `121 source files`, migration head is
`0008_alpha_caller_intelligence` / `25` tables, security review is PASS and
the existing `581`-component SBOM digest passes. No historical-real or
live-shadow success is claimed; the checked-in fixture remains
`SYNTHETIC_REDACTED` / `INSUFFICIENT_SAMPLES`, and compliant X/Telegram access
remains `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`.

## Task 8 evidence snapshot — 2026-09-07

The existing `scripts/start-shadow.sh` and `scripts/shadow_status.py` seam now
resumes an open run only when its pinned git SHA and configuration hash still
match; incompatible or terminal runs are archived before a new identity is
created. The run record persists provider states/versions, start/end times,
canonical live-normalize/decide/paper-replay path, `execution_eligible=false`,
event coverage, duplicate/conflict fingerprints and unresolved stream gaps.

Matured actionable signals are counted only once by normalized event identity,
and are not matured while an unresolved gap exists. Provider degradation,
unknown capability state and unresolved gaps classify the run fail-closed;
`LIVE_SHADOW_ACCEPTED` requires both `14` elapsed calendar days and `200`
matured actionable signals. A closed run records its end time and rejects
late events. These are keyless contracts; they do not claim real provider or
live-shadow success.

Evidence for this slice:

- The initial TDD run failed on the missing resume/event/gap/closure APIs with
  `5` failures; after implementation, the focused shadow tooling suite passes
  `24 tests` and the adjacent shadow-entry/reliability suite passes `35 tests`.
- The current read-only status command exits `0` with
  `STACK_READY / BLOCKED_EXTERNAL`, run state `START_FAILED`, collection
  `NOT_ACTIVE`, evidence `NOT_AVAILABLE` and `0` matured outcomes. This is
  not a live-shadow success claim.
- Ruff, Python compilation and `git diff --check` pass for the touched files.
- Real provider snapshots, historical-real calls and matured live-shadow
  outcomes remain unavailable; PR-2/PR-4 therefore remain externally blocked
  or `INSUFFICIENT_SAMPLES` as recorded above.
- Protected modes remain exact and no signer, live execution capability,
  scoring weight or duplicate replay/decoder engine was added.

## Task 9 evidence snapshot — 2026-09-07

The existing bounded `ReliabilityMetrics` collector now exposes allow-listed
provider success/error/rate-limit/stale counters plus ingestion, parser,
normalization, social-resolution, alert-delivery, Telegram, DB, Redis, API,
worker and migration counters. It also accepts bounded ingestion lag, queue
age/depth, DB storage, social-resolution and quote-freshness gauges. The
existing `OperationsProjector` emits deterministic advisory alerts for
sustained ingestion lag, stale market/reference or execution quote evidence,
provider loss/degradation, unresolved stream/recovery failures, queue growth,
DB storage pressure, migration mismatch and Telegram/alert delivery failure.
Provider capability health remains separate from API/dependency health, and
the operations projection remains `execution_eligible=false`.

Initial keyless thresholds are versioned in `ProviderSloPolicy`: 300 seconds
ingestion lag, queue depth 1,000 or oldest age 300 seconds, and 90% DB storage
usage. These are targets only; no production SLO PASS is claimed without
measured real-environment evidence.

Evidence for this slice:

- The initial telemetry run failed on missing gauges and alert codes with
  `2` failures; after implementation, the focused observability/reliability/
  alert suite passes `28 tests`.
- `make lint` and strict `make typecheck` pass over `121 source files`.
- Full `make verify` exits `0` with `1101` Python tests passed, `11` skipped,
  `1` warning and `55` Vitest tests passed; Compose, secret scan, migrations,
  security review and SBOM pass. External scans remain `NOT_RUN`/
  `BLOCKED_EXTERNAL`.
- External provider, Telegram, database, Redis and soak measurements remain
  unavailable; PR-5 remains `PARTIAL/NOT_VERIFIED`.

## Task 10 evidence snapshot — 2026-09-07

The existing persistence engine now applies explicit bounded PostgreSQL
defaults: pool size `5`, max overflow `5`, pool timeout `30s`, pool recycle
`1800s`, asyncpg command timeout `30s`, server statement timeout `30s` and
idle-in-transaction timeout `60s`. Caller/social/observation and replay
indexes remain in the existing schema; research work is documented as a
separate process/connection budget from live ingestion/API transactions.

Evidence for this slice:

- The new engine contract first failed on absent pool/timeout kwargs; after
  implementation it passes, and the focused database/persistence/runbook
  suite passes `12 tests`.
- A disposable `postgres:16-alpine` instance applied migration head
  `0008_alpha_caller_intelligence`, was dumped in custom format and restored
  to an isolated database. The restore has the same head and `26` public
  tables including `alembic_version`; the restored integration suite passes
  `11 tests`.
- The restored query checks found the required caller/social,
  cross-chain-identity and observation indexes, and `EXPLAIN` used backward
  index scans for bounded BNB social-call and market-observation queries.
- The final `make verify` exits `0` with `1102` Python tests passed, `11`
  skipped, `1` warning and `55` Vitest tests passed; Compose, secret scan,
  migrations, security review and SBOM pass. External scans remain `NOT_RUN`/
  `BLOCKED_EXTERNAL`.
- Migration recovery is documented as forward-first; managed backup schedule,
  off-host retention/encryption, production RPO/RTO and soak/failure evidence
  remain deployment-specific and unverified. No secrets or credentials were
  recorded.

## Task 11 evidence snapshot — 2026-09-07

The release security boundary now reuses the existing secret scanner and
security-review report. It scans tracked content, `.env.example` and other
tracked configuration examples, bounded release/artifact/log roots, the
release-relevant frontend output (`.next/static`, `.next/server` and bounded
Next logs), and reachable git history blobs. Reports contain only rule/path
metadata and never secret values. The history scan is cached per checkout so
repeated review checks do not rescan the same object graph.

The local deployment contract binds Compose-published ports to loopback and
fails on privileged containers, host networking, added capabilities or
public `0.0.0.0` bindings. The API has no wildcard CORS middleware; if CORS is
introduced, the review rejects wildcard origins. Existing role-token RBAC,
bounded control request fields, bounded runtime configuration, protected-mode
startup validation and allow-listed redaction remain required review markers.

Evidence for this slice:

- The focused secret/security suite passes `11 tests`, including synthetic
  release-bundle and reachable-history leaks, public-port/wildcard-origin
  rejection, protected-mode failure and the existing RBAC boundary tests.
- `make secret-scan`, `make compose-config`, `make security-review`, `make
  lint`, `make typecheck` and `git diff --check` pass. The local security
  report is `PASS` with checks for dependency locks, non-root/versioned
  containers, tracked/artifact/history secret boundaries, RBAC/auth,
  advisory LLM handling, deployment security and protected modes.
- External `pip-audit`, npm audit and container vulnerability scans remain
  `NOT_RUN`/`BLOCKED_EXTERNAL` when the required tools or vulnerability
  databases are unavailable. The checked-in SBOM remains the existing 581
  component artifact; no external vulnerability success is claimed.
- No provider, Telegram or operator credential was printed or committed. The
  protected modes remain exactly `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`, and no execution authority
  was added. The four pre-existing unrelated WIP files remain untouched.

## Task 12 local evidence snapshot — 2026-09-07

The existing CI workflow now runs on pull requests, `main` pushes and `v*`
release-candidate tags. Backend, frontend, Compose and secret-scan jobs remain
separate mandatory gates; the new release-identity job is gated on all four
and checks out full history before uploading a SHA-named
`release-identity.json` artifact.

The repository-owned `make release-identity` command composes the existing
migration check and deterministic SBOM with the full Git SHA, app/API versions,
runtime configuration hash, migration heads/table count and exact protected
modes. It never reads provider credentials or raw data. The rollback runbook
uses the existing forward-first migration and isolated-restore rules and does
not authorize a mode change.

Evidence for this slice:

- The focused release-identity suite passes `3 tests`, including reproducible
  metadata, workflow gating/artifact assertions and direct CLI artifact
  creation. The generated local identity reports app/API `0.1.0`, migration
  head `0008_alpha_caller_intelligence`, `25` metadata tables, `581` SBOM
  components and the existing SBOM digest.
- `make lint`, strict `make typecheck` over `121 source files`,
  `make migration-check`, `make sbom`, `make compose-config`,
  `make release-identity`, CI YAML parsing and `git diff --check` pass.
- GitHub Actions run `34117264094`
  ([workflow run](https://github.com/Rasman1234/MemeRadar/actions/runs/34117264094))
  observed the exact pushed SHA `5d18935993281ff427cca85926360db019a945f5`
  but completed `failure` with zero executed steps in Backend quality,
  Frontend quality, Compose contract and Secret scan; Release candidate
  identity was skipped. This is classified
  `BLOCKED_EXTERNAL_GITHUB_ACTIONS` (runner/account restriction), not an
  internal test PASS or FAIL. A real deployment rollback remains unverified.
  PR-1 therefore stays `PARTIAL/BLOCKED_EXTERNAL`; no remote-CI PASS is
  claimed.

## Task 13 evidence snapshot — 2026-09-07

The existing reliability benchmark now exposes a bounded
`production-soak-v1` report rather than adding another provider, stream or
alert engine. It reuses `ReliabilityMetrics` and records eight deterministic
failure/recovery scenarios: provider timeout/retry/recovery, provider
rate-limit recovery, Redis restart, database interruption,
duplicate/delayed/out-of-order events, stale quote fail-closed behavior, stream
gap recovery and Telegram outage/retry/dedupe. The report separates synthetic
throughput/headroom from alpha quality and records one-process, no-database,
no-Redis, synthetic-provider and fixture-only Telegram assumptions.

Evidence for this slice:

- The new production-soak contract initially failed at collection because the
  report entry point and Make target were absent. After the minimal extension,
  the focused contract suite passes `2 tests`; the existing reliability,
  transport, Telegram, stream, alert and Phase 11 contract suite passes `53
  tests`.
- `make production-soak SOAK_ITERATIONS=1000 SOAK_EXPECTED_RATE=100` reports
  `schema_version=production-soak-v1`, eight scenarios,
  `measured_rate_per_second=3054.806`, `headroom_ratio=30.548` and artifact
  digest `sha256:00dfef6825ca25f28eb88a0f23fc2a314765d7e04f340c955e8663811f5f2ddb`.
  These are bounded synthetic-local measurements, not production capacity or
  provider SLO claims.
- `make lint`, strict `make typecheck` over `121 source files`, the full
  `make verify` gate (`1111` Python tests passed, `11` skipped, `1` warning;
  `55` Vitest tests passed), Compose, secret scan, migrations, security review
  and the existing `581`-component SBOM pass. The protected modes remain
  exactly `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No real provider, Redis, database or Telegram restart/outage was executed by
  this keyless checkpoint. External soak acceptance remains
  `BLOCKED_EXTERNAL`; managed backup scheduling, deployment restore objectives,
  resource headroom under real load and remote CI remain unverified. No
  production-ready classification is claimed and the four pre-existing
  unrelated WIP files remain untouched.

## Task 14 evidence snapshot — 2026-09-07

The canonical `make opportunity-research` and `make historical-dataset`
generators were rerun against the checked-in bundle, and the existing
`shadow_status.py` report was inspected. The six Alpha Caller ablation
families remain present and no-lookahead verified, but the available evidence
is not historical-real or live-shadow evidence.

Evidence for this slice:

- The focused opportunity/historical/shadow suite passes `39 tests`, including
  the new report contract. The initial report contract failed because the
  Task 14 evidence addendum was absent; it now verifies explicit
  `HISTORICAL_REAL`, `LIVE_SHADOW`, `INSUFFICIENT_SAMPLES`,
  `BLOCKED_EXTERNAL` and `promotion_allowed=false` language.
- The regenerated opportunity report is `opportunity-research-v1`,
  `SYNTHETIC_REDACTED`, `INSUFFICIENT_SAMPLES`,
  `no_lookahead_verified=true`, `promotion_allowed=false` and
  `execution_eligible=false`. Each six-family caller ablation has `sample_count=3`
  and no precision, recall, executable expectancy or false-positive estimate.
- Historical validation remains `INSUFFICIENT_SAMPLES` with `0` matured calls,
  `0` matured token outcomes, `0` caller identities, `0` negative controls and
  `HISTORICAL_REAL_EVIDENCE_REQUIRED`. Shadow status remains
  `STACK_OFFLINE`/`START_FAILED`, provider readiness `NOT_AVAILABLE`,
  collection `NOT_ACTIVE`, evidence class `NOT_AVAILABLE` and `0` matured
  outcomes.
- The full `make verify` gate passes with `1113` Python tests passed, `11`
  skipped, `1` warning and `55` Vitest tests passed; Ruff, strict mypy over
  `121 source files`, Compose, secret scan, migrations, security review and
  the existing `581`-component SBOM also pass.
- No real X/Telegram/provider historical backfill or matured live-shadow
  run is available in this environment. Real-data ablation and promotion are
  therefore `BLOCKED_EXTERNAL`/`INSUFFICIENT_SAMPLES`; no production score
  weight or promotion record changed. Task 14 remains the exact unfinished
  evidence task until compliant access and sufficient real samples exist.

## Task 15 acceptance snapshot — 2026-09-07

The final staged acceptance was evaluated without changing execution modes or
claiming live-money readiness. The only allowed roadmap classifications remain
`PRODUCTION_READY_READ_ONLY` and `PRODUCTION_READY_PAPER_AUTO`; neither is
declared. Current classification is `NOT_PRODUCTION_READY`.

| Gate | Evidence at current candidate | Classification |
|---|---|---|
| PR-1 Engineering/release | Local `make verify`, release identity, migration/security/SBOM/Compose gates pass; hosted CI run `34119948144` for candidate SHA `d49b8a3c687bb0a6e637d06847c238df05042ed7` failed with zero executed steps in all prerequisite jobs, and rollback is not deployed/tested | `PARTIAL/BLOCKED_EXTERNAL` |
| PR-2 Provider/evidence | Free provider doctor reaches `READY_FOR_FREE_READ_ONLY_SHADOW`; social, Telegram and stream doctors are `CONFIGURATION_MISSING`/`BLOCKED_EXTERNAL` | `BLOCKED_EXTERNAL/PARTIAL` |
| PR-3 Historical-real research | `SYNTHETIC_REDACTED`, zero matured calls/outcomes/identities/negative controls; all six caller families remain `INSUFFICIENT_SAMPLES` | `INSUFFICIENT_SAMPLES` |
| PR-4 Live-shadow | `STACK_OFFLINE`/`START_FAILED`, `NOT_ACTIVE`, `NOT_AVAILABLE`, zero matured outcomes | `INSUFFICIENT_SAMPLES` |
| PR-5 Operations | Restore is `DOCUMENTED_ONLY`; local telemetry and synthetic soak pass, but real dependency failure/restore and managed backup evidence are absent | `PARTIAL/BLOCKED_EXTERNAL` |
| PR-6 `PROD_READ_ONLY` | PR-1 + PR-2 + PR-5 are not all PASS | `NOT_ACCEPTED` |
| PR-7 `PROD_PAPER_AUTO` | Real-environment paper-auto acceptance and PR-1..PR-5 are not all PASS | `NOT_ACCEPTED` |
| PR-8 `LIVE_MONEY_CANDIDATE` | Separate future operator-approved design is required | `OUT_OF_SCOPE` |

The accepted code candidate release identity is Git SHA
`d49b8a3c687bb0a6e637d06847c238df05042ed7`, app/API `0.1.0`, migration head
`0008_alpha_caller_intelligence` with `25` metadata tables, config hash
`sha256:e6d23c5553553dd7ec228b73851fd71bd6d26ed22856ec800bcfefea897bd865`,
and the `581`-component SBOM digest
`sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
Local and `origin/main` are synchronized (`0 0`); the four unrelated WIP
files remain untracked and untouched. Protected modes remain exactly
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
`AUTO_EXECUTION=false`. The exact next unfinished task is Task 14 real-data
collection and rerun once compliant historical access and a durable shadow
environment are available.

## Minimum evidence targets

These are initial versioned guardrails for sample adequacy, not profitability promises:

- target >=1000 matured historical real calls;
- target >=50 distinct caller/source identities;
- target >=500 matured chain-qualified token outcomes;
- target >=40% negative controls in final evaluation dataset;
- no caller/source >10% of TEST partition;
- target >=14 consecutive calendar days live-shadow;
- target >=200 matured actionable live-shadow signals, otherwise remain `INSUFFICIENT_SAMPLES`;
- chronological/leakage-safe TRAIN/VALIDATION/TEST split;
- executable outcomes after modeled fees/slippage/impact rather than headline ATH;
- no future-label mutation or survivorship test failure;
- promotion requires human review and never changes protected modes automatically.

## Production data capability checklist

Required/expected production capability classes:

- Solana RPC/read stream with gap/freshness handling;
- BNB generic-EVM reads;
- Robinhood generic-EVM reads;
- market/liquidity reference data;
- execution-quote semantics for paper realism;
- compliant historical/live X/social source where configured;
- configured Telegram historical/live source;
- wallet/security enrichment where selected;
- durable PostgreSQL/Redis and queue state;
- Telegram notification delivery.

Each capability must report `READY`, `DEGRADED`, `RATE_LIMITED`, `STALE`, `CONFIGURATION_MISSING`, `BLOCKED_EXTERNAL` or `UNSUPPORTED`. Application health and provider capability health are separate.

## Deployment checklist

Before `PRODUCTION_READY_READ_ONLY`:

- production environment configuration validates and unsafe mode combinations fail startup;
- secrets are environment/secret-manager injected, never repository/image/frontend/log values;
- DB migration path tested on production-like data;
- backup policy configured and restore drill objectively succeeds;
- retention/privacy rules for raw social/provider data reviewed;
- PostgreSQL pool/timeout/index assumptions validated at realistic volume;
- Redis/queue recovery behavior verified;
- live/replay/backfill share canonical normalization/identity semantics;
- observability covers ingestion lag, provider health, queue age, stream gaps, parsing, resolution, quote freshness, decision/alert latency, DB/Redis/API/worker health;
- alerts exist for ingestion stop, stale critical evidence, provider loss, stream gaps, queue growth, DB pressure/migration mismatch and Telegram delivery failure;
- production-like soak and provider/DB/Redis/Telegram failure tests completed;
- remote CI succeeds against exact release candidate;
- release artifact records git SHA, app/schema/migration/config identity and SBOM;
- rollback/forward-fix runbook is tested/documented.

## Alpha acceptance checklist

Before any caller/social/smart-money/opportunity promotion:

- historical real and live-shadow evidence use the same canonical event-time semantics;
- winner-first reverse caller discovery includes negative controls and late/failed calls;
- call timestamp -> decision -> quote -> paper entry timeline is measurable;
- mark-price multiple cannot substitute for executable multiple;
- ablations compare baseline, caller-only, smart-money-only, opportunity-only, caller+smart-money, caller+opportunity and full fusion;
- false-positive costs, precision/recall, confidence intervals, executable expectancy and drawdown are reported;
- chain/caller/archetype/regime segmentation is explicit;
- insufficient confidence remains `INSUFFICIENT_SAMPLES`;
- TEST/live-shadow results are not tuned back into the candidate.

## Release naming rule

Allowed final classifications for this roadmap:

- `PRODUCTION_READY_READ_ONLY`
- `PRODUCTION_READY_PAPER_AUTO`

Forbidden without a separate future approved design/evidence package:

- generic `PRODUCTION_READY` implying live-money readiness;
- `LIVE_TRADING_READY`;
- automatic changes to `MANUAL_EXECUTION` or `AUTO_EXECUTION`.
