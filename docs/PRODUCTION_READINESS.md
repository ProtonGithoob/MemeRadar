# MemeRadar Production Readiness

**Current checkpoint:** Real Alpha Production Readiness Task 6 complete; the repository remains synchronized on `main` with protected modes unchanged.

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
| PR-1 Engineering/release | Canonical tests, lint/typecheck, migrations, security/SBOM, build, remote CI, release identity, rollback | `PARTIAL` | Task 6 checkpoint `make verify` passed with `1093` Python tests, `11` skipped and `54` Vitest tests; migration/security/SBOM gates pass locally. `.github/workflows/ci.yml` exists, but no hosted run, release artifact or tested rollback is evidenced yet. |
| PR-2 Provider/evidence | Required real chain/market/social/Telegram capabilities with freshness/provenance and stable doctors | `BLOCKED_EXTERNAL/PARTIAL` | `make free-provider-doctor` reaches `READY_FOR_FREE_READ_ONLY_SHADOW`; social, Telegram and stream doctors report `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`. Configure compliant real access and prove bounded reads. |
| PR-3 Historical-real research | Leakage-safe real positive/negative dataset and real ablation | `INSUFFICIENT_SAMPLES` | `fixtures/research/opportunity_research_report.json` remains `SYNTHETIC_REDACTED`; the new `historical_real_dataset_validation.json` reports zero matured calls/outcomes and no historical-real evidence. Collect real calls/outcomes and rerun the canonical gate. |
| PR-4 Live-shadow | Sustained real observation, replayability, latency/freshness and matured paper outcomes | `INSUFFICIENT_SAMPLES` | `python3 scripts/shadow_status.py` reports `STACK_OFFLINE`, `START_FAILED`, `NOT_ACTIVE`, `NOT_AVAILABLE` evidence and unknown matured outcomes; run a durable real shadow window. |
| PR-5 Operations | Backups/restore, monitoring/alerts, soak/failure tests, deployment/rollback runbooks | `PARTIAL/NOT_VERIFIED` | Runbooks and keyless contracts exist; `reliability-doctor` reports `backup_restore=DOCUMENTED_ONLY`. Execute restore, soak and failure acceptance. |
| PR-6 PROD_READ_ONLY | PR-1 + PR-2 + PR-5 PASS | `NOT_ACCEPTED` | Complete its three prerequisite gates; PR-3/PR-4 may remain insufficient while collecting evidence. |
| PR-7 PROD_PAPER_AUTO | PR-1..PR-5 PASS plus real-environment paper-auto fail-closed acceptance | `NOT_ACCEPTED` | Complete all evidence and operational gates in a real deployment. |
| PR-8 LIVE_MONEY_CANDIDATE | Separate future operator-approved design plus all prior evidence | `OUT_OF_SCOPE` | Never auto-enable from this roadmap. |

## Task 1 evidence snapshot — 2026-09-07

The initial inventory was checked against the actual checkout after a safe
fast-forward from `2acf261` to `0dc07f8`. The local checkout and `origin/main`
are synchronized (`git rev-list --left-right --count origin/main...HEAD` =
`0 0`). The four unrelated pre-existing WIP files remain untracked and
untouched:

- `apps/web/e2e-screenshots.mjs`
- `apps/web/mock-api.mjs`
- `apps/web/overflow-debug.mjs`
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
