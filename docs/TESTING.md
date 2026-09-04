# Testing and Verification Strategy

## Principle

MemeRadar must be testable without external credentials and verifiable against real providers when credentials/network are available. External outages must never be disguised as application success.

## Free-first provider acceptance

The keyless acceptance contract covers the standard `SolanaRpcAdapter`,
`DexScreenerAdapter`, `OllamaNarrativeAdapter`/disabled narrative seam, the
provider-neutral composition layer and the three readiness tiers. Optional
Helius, Birdeye, RugCheck authentication, social analytics, external wallet,
Telegram and external narrative credentials are empty in the core scenario.

Focused commands:

```bash
./.venv/bin/python -m pytest -q \
  tests/unit/test_solana_rpc.py tests/contract/test_solana_rpc_provider.py \
  tests/unit/test_dexscreener.py tests/contract/test_dexscreener_provider.py \
  tests/unit/test_ollama_narrative.py tests/contract/test_ollama_narrative_provider.py \
  tests/unit/test_provider_composition.py tests/contract/test_contract_provider_composition.py \
  tests/contract/test_provider_capability_boundaries.py
./.venv/bin/python -m pytest -q \
  tests/unit/test_config.py tests/unit/test_provider_routing.py \
  tests/unit/test_early_live_doctor.py tests/unit/test_shadow_tooling.py \
  tests/unit/test_paper_trading_doctor.py tests/unit/test_free_provider_doctors.py \
  tests/unit/test_ollama_doctor.py
python3 scripts/free_provider_doctor.py --no-network
```

Deterministic fixtures cover malformed/null prices, wrong chains, zero or
missing liquidity, multiple and duplicate pairs, stale/freshness boundaries,
invalid JSON, 404/5xx, timeout, 429/`Retry-After`, declared social links and
provider provenance. Pair selection is independent of API order: Solana and
token identity are filtered first, valid positive price and liquidity are
required for quotes, preferred USDC/USDT/wSOL quote assets rank before other
pairs, then liquidity descends, pair creation time descends, and pair address
plus DEX ID provide stable tie-breaks. Duplicate pair addresses retain the
best deterministic record.

The no-network aggregate must report the free core as
`READY_FOR_FREE_READ_ONLY_SHADOW`, optional providers as unconfigured or
disabled, and the protected modes exactly as
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
`AUTO_EXECUTION=false`. Network doctor failures are recorded as
`BLOCKED_EXTERNAL`, `RATE_LIMITED` or `DEGRADED`, never as a fabricated PASS.

## Test layers

### Unit
Cover provider-independent domain/application behavior:
- state transitions;
- scoring and penalties;
- hard risk gates;
- confidence/freshness;
- wallet scoring;
- feature windows;
- sizing/exit policies;
- idempotency/reason codes.

### Property / fuzz
Use where valuable for:
- AlphaScore always 0..100;
- hard blocks cannot be bypassed by score;
- stale critical evidence never becomes execution-eligible;
- duplicate events/orders never duplicate side effects;
- state machine invariants;
- money/quantity arithmetic.

### Integration
Real local dependencies via containers:
- PostgreSQL repositories/UoW;
- migrations;
- outbox/retry/recovery;
- Redis coordination fallback behavior;
- API composition/auth.

### Provider contract
Each provider adapter gets recorded/synthetic fixtures for:
- normal response;
- missing/null fields;
- schema change/error;
- 401/403;
- 429;
- timeout;
- malformed data;
- reconnect for streams.

### Replay
A fixed event dataset must reproduce identical:
- observations/features;
- risk decisions;
- AlphaScores;
- state transitions;
- paper trades/exits,
given identical code/config/model versions.

### End-to-end
Run API + worker + DB + Redis + web using fake providers:
- candidate discovered;
- enrichment;
- score/risk;
- alert;
- dashboard appearance;
- paper entry/exit;
- audit trail.

### Browser
Critical UI flows:
- Radar filtering;
- token detail/timeline;
- wallet/provider pages;
- paper positions;
- auth/RBAC;
- settings validation;
- kill-switch controls.

Sprint 8.1 browser coverage also asserts all four protected-mode labels,
explicit `LIVE DATA`/`ADVISORY OUTPUT` boundaries, accessible status text and
stable non-safe `UNKNOWN`/`STALE`/`UNAVAILABLE` states. The realtime unit seam
uses injected sockets/timers to verify disabled operation, successful open,
bounded exponential reconnect, duplicate error/close suppression, retry
exhaustion, clean stop and ignored message data. The theme test verifies that
only the local `memeradar-theme` preference and root data attribute change.

Sprint 8.2 frontend coverage verifies the server read gateway's bounded URL,
authorization, timeout/status mapping and strict record parsers; malformed
records and error bodies never escape. Radar tests preserve API ranking order,
allow only the documented GET filters and render explicit empty/unavailable/
invalid states. Token detail tests cover UUID route validation, API-provided
event-time order, freshness/risk/score visibility, bounded provenance,
allow-listed SVG metric projections, holder concentration/cluster bars and
social/narrative source panels without raw payload or secret-shaped text.
Frontend lint, typecheck, build, Vitest, repository `make verify`, Compose
configuration and a rebuilt web runtime probe are required before Sprint 8.2
is marked complete; live provider acceptance remains `BLOCKED_EXTERNAL` when
credentials/endpoints are absent.

Sprint 8.3 frontend coverage verifies strict wallet/provider/control/audit
parsers, bounded queries, private-token containment, canonical wallet-address
validation and allow-listed display projections. Component tests preserve API
order and cover degradation, empty, unavailable, invalid, permission-matrix
and protected-mode behavior. The Gate P8 Playwright suite runs against the
rebuilt keyless Compose web service and covers the operator shell/navigation,
all four operator intelligence routes, invalid wallet fail-closed behavior,
protected labels and absence of forms or execution/mutation buttons. The
environment uses `MEMERADAR_E2E_BASE_URL` for an existing server and an
optional `MEMERADAR_E2E_EXECUTABLE_PATH` when the host supplies its own Chrome;
`make frontend-e2e` remains separate from the credential-free repository gate.

## E8.4 stream integrity and protocol verification

The keyless E8.4 suite covers contiguous slots, exact and overlapping gaps,
skipped/non-produced slots, persisted-cursor restart, duplicate live/recovered
events, conflicting normalized evidence, bounded timeout/rate-limit recovery,
observable backpressure, same-decoder live/backfill/replay equivalence,
deterministic event-time replay and no future-data leakage. It also covers
processed-to-confirmed-to-finalized progression, append-only revert
correction, Anchor/native routing, discriminator collisions, unknown and
unverified protocols, quality-only stream impact, migration/persistence
round-trip and protected provider/application boundaries.

The required focused command is:

```text
./.venv/bin/pytest tests/unit/test_chain_domain.py tests/unit/test_stream_integrity.py tests/unit/test_protocol_registry.py tests/unit/test_stream_integrity_doctor.py tests/unit/test_feature_windows.py tests/contract/test_extension_e8_4_stream_integrity.py tests/unit/test_stream_persistence_contract.py tests/unit/test_migration_contract.py tests/unit/test_persistence_contract.py -q
```

`make stream-integrity-doctor` performs only local contract validation and
reports external stream/RPC access as `BLOCKED_EXTERNAL` when it is not
verified. It must never print endpoint values or claim a provider PASS from
configuration presence. Migration parity, full repository quality gates and
the opt-in Postgres stream-state round trip are required before E8.4 is
marked complete.

## Phase 11.1 reliability and E11.1 measurement

The keyless reliability suite covers bounded percentile histograms and
provider-labelled counters, stream disconnect/reconnect and fallback behavior,
malformed and duplicate visibility, provider rate-limit/retry behavior,
bounded backpressure, outbox retry/dead-letter telemetry and persistence
connection-pool restart recovery. The opt-in
`tests/integration/test_phase11_reliability_postgres.py` verifies that a
pending outbox row survives disposal and reopening of the database connection
pool before it is delivered exactly once.

Focused command:

```text
./.venv/bin/pytest tests/unit/test_reliability.py tests/unit/test_provider_transport.py tests/unit/test_helius_stream.py tests/unit/test_birdeye_stream.py tests/unit/test_protocol_stream.py tests/unit/test_event_processing.py tests/unit/test_stream_integrity.py tests/contract/test_phase11_sprint11_1.py -q
```

Run `make reliability-benchmark RELIABILITY_ITERATIONS=1000` for the six
latency histograms and `make reliability-doctor` for the keyless readiness
check. The benchmark does not contact a provider and does not establish a
production SLO; configured live access must be separately verified and remains
`BLOCKED_EXTERNAL` when unavailable. See
[`docs/RUNBOOKS/RELIABILITY.md`](RUNBOOKS/RELIABILITY.md) for outage,
retention and isolated backup/restore procedures.

## Phase 11.2 observability and operations

The keyless operations suite covers normalized provider operational records,
healthy/degraded/down/unknown precedence, low/exhausted quota, cost-budget
pressure, synthetic-versus-runtime SLO evidence, stream/queue/outbox alerts,
stable redacted serialization and protected modes. API contracts verify the
injected `GET /v1/operations/overview` route is bounded and read-only. Web
tests cover the `/operations` dashboard, empty/unavailable states, provider
degradation, quota/cost visibility and alert presentation.

Focused commands:

```text
./.venv/bin/pytest tests/unit/test_observability.py tests/contract/test_phase11_sprint11_2.py -q
cd apps/web && npm test -- --run src/app/components/operations.test.tsx src/app/lib/read-api.test.ts
```

The operations dashboard does not convert synthetic/keyless evidence into a
production SLO or provider PASS. Use
[`docs/RUNBOOKS/OPERATIONS.md`](RUNBOOKS/OPERATIONS.md) for provider outage,
database pressure, queue lag, alert failure and quota/cost response.

## Phase 11.3 security review

The keyless security suite verifies exact Python/npm lock metadata, rejection
of unpinned dependencies, versioned container bases, non-root image runtime
users, tracked-file secret scanning, protected modes, constant-time bearer
RBAC, explicit permission denial, and the strict advisory narrative/prompt
boundary. The review emits separate external scanner states and never treats
missing pip-audit, npm advisory access or Trivy/registry access as a clean
result.

Focused command:

```text
./.venv/bin/pytest tests/unit/test_security_review.py tests/contract/test_phase11_sprint11_3.py -q
```

Quality/review commands:

```text
make security-review
make security-review-external
make sbom
make verify
make frontend-build
docker compose -f infra/compose/docker-compose.yml build api worker web
```

`make security-review` is the deterministic gate and returns `PASS` only for
local contracts. `make security-review-external` returns `BLOCKED_EXTERNAL`
when a scanner or vulnerability database is unavailable, and returns failure
for a concrete external finding. See
[`docs/RUNBOOKS/SECURITY_REVIEW.md`](RUNBOOKS/SECURITY_REVIEW.md) and
[`docs/THREAT_MODEL.md`](THREAT_MODEL.md).

## Cross-cutting hardening contracts

The keyless hardening suite also covers the generated API version/OpenAPI
surface, retention/privacy/terms/ADR records, fixed-seed score/lifecycle/stream
invariants and normalized provider-health selection:

```text
./.venv/bin/pytest tests/contract/test_api_schema.py tests/contract/test_cross_cutting_documents.py tests/unit/test_sbom.py tests/property/test_invariants.py tests/unit/test_provider_routing.py -q
```

Provider-health routing is evidence-only. A missing, stale, unknown or
conflicted candidate never becomes a safe fallback, and the suite does not
claim live-provider or contractual acceptance.

## Phase 10.1 replay harness

The keyless replay suite covers normalized dataset round trips, deterministic
event-time ordering, source deduplication/conflict rejection, partition
metadata, malformed/secret-shaped input rejection and manifest identity
pinning. It verifies that the same correlation/feature path is used for
reverse-delivered events, that future events are excluded from feature input,
and that outcome labels alone may inspect later prices, liquidity, security,
creator and paper-exit evidence. Cohort dimensions, stable JSON/CSV artifact
digests, alternate-strategy comparison on identical event boundaries and
protected non-execution modes are covered. A bounded profile command records
local throughput before any Rust/Yellowstone decision.

Focused command:

```text
./.venv/bin/pytest tests/unit/test_replay_harness.py tests/contract/test_phase10_sprint10_1.py -q
```

Fixture commands:

```text
make replay-dataset
make profile-replay PROFILE_ITERATIONS=25
```

The fixture is redacted and provider-free; missing external market/Telegram
acceptance remains `BLOCKED_EXTERNAL`.

## Phase 9.1 paper execution

The keyless paper suite covers Decimal risk-budget sizing, quote freshness and
risk rejection, deterministic BUY/SELL slippage and fee arithmetic, partial
fills, weighted position open/add/reduce/close behavior, duplicate and
conflicting idempotency keys, restart/resume, append-only reconciliation and
SQLAlchemy migration/round-trip persistence. Replay tests pin policy/config/
fill-model identity, sort event time deterministically, produce stable IDs and
exclude future requests or future-observed quotes. Domain/application source
contracts forbid SQLAlchemy, FastAPI, persistence, signing and transaction
submission dependencies. `make paper-trading-doctor` runs only local contracts;
without external quote configuration it returns `BLOCKED_EXTERNAL`, and even
with configuration it never fabricates a provider or live-execution PASS.

The focused command is:

```text
./.venv/bin/pytest tests/unit/test_paper_domain.py tests/unit/test_paper_execution.py tests/unit/test_paper_trading_doctor.py tests/contract/test_phase9_sprint9_1.py tests/unit/test_paper_persistence_contract.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q
```

## Phase 9.2 exit engine

The keyless exit suite covers fixed stops and take-profit ladders, trailing and
break-even rules, independent wallet/creator/holder distribution evidence,
micro/macro flow collapse, liquidity and quote deterioration, score/time rules,
freshness/UNKNOWN fail-closed behavior, external-only corroboration,
deterministic IDs, append-idempotent in-memory and SQL timeline persistence,
before/after evidence references and event-time/no-lookahead replay. Application
and persistence boundary contracts forbid provider SDK, signing and
transaction-submission dependencies.

The focused command is:

```text
./.venv/bin/pytest tests/unit/test_exit_engine.py tests/unit/test_exit_persistence_contract.py tests/contract/test_phase9_sprint_9_2.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q
```

The opt-in Postgres command is:

```text
MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://... ./.venv/bin/pytest tests/integration/test_exit_persistence_postgres.py -q
```

Live market-data and execution acceptance remains `BLOCKED_EXTERNAL`; no exit
test may grant execution authority or change the protected operating modes.

## Phase 9.3 position UI / Telegram

The keyless Sprint 9.3 suite covers bounded position views, fresh/stale/unknown
mark behavior, event-time/no-lookahead filtering, deterministic ordering and
pagination, observed mark provenance, derived PnL/MFE/MAE, exit-risk reason and
evidence projection, closed-trade explanation, persisted exit-event
rehydration, GET-only API routes, bounded frontend parsing/rendering and the
absence of browser execution authority. Exit alert contracts cover
non-HOLD/core-trigger routing for `ExitSignal`, `ExitEvaluation` and
`PaperExit`, persisted reason-object handling, payload allow-listing,
external-only corroboration suppression and safe concise rendering. The
existing notification outbox and Telegram adapter remain the delivery path;
live Telegram and live market-data acceptance are `BLOCKED_EXTERNAL`.

The focused backend command is:

```text
./.venv/bin/pytest tests/contract/test_phase9_sprint9_3.py tests/unit/test_position_read.py tests/unit/test_alert_pipeline.py tests/unit/test_read_persistence.py tests/contract/test_phase7_sprint7_2.py -q
```

The opt-in persistence command is:

```text
MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://... ./.venv/bin/pytest tests/integration/test_position_read_postgres.py -q
```

The web checks include the full Vitest suite, lint, typecheck and production
build. The build must expose `/positions` as a server-rendered route, and the
position gateway must remain server-only with no browser credential or mutation
path.

## Live provider acceptance

Live tests are opt-in and read-only until Phase 12. They must be clearly marked and never make CI depend on paid credentials.

A live provider acceptance report records:
- timestamp;
- provider capability;
- redacted environment;
- request/stream success;
- schema parse;
- latency/freshness;
- rate-limit metadata;
- result PASS / BLOCKED_EXTERNAL / FAIL.

## Execution testing progression

1. fake quote/execution provider;
2. recorded Jupiter quote fixtures;
3. live read-only quotes;
4. transaction simulation/dry run;
5. explicit tiny-size manual acceptance;
6. failure and duplicate-submission tests;
7. auto execution remains locked pending explicit later approval.

The ultra-early shadow-entry regression suite additionally injects poison
signer and live-execution stubs. A successful `ENTRY_READY` path must call
only the provider-neutral quote port and canonical paper execution engine;
the poison stubs fail the test if touched. Forward outcome labels, external
social-call lead time and latency benchmarks are measurement-only. Run the
read-only acceptance check with `make early-live-doctor`; without configured
provider access it must return `BLOCKED_EXTERNAL`, never a fabricated PASS.

The future execution boundary is tested as a locked diagnostic with
`execution_eligible=false`, `signer_available=false` and
`submission_available=false`. No Phase 12 test or local gate may enable a
manual/automatic live mode.

## Backtest integrity

- Event-time processing only; no future feature leakage.
- Time-based train/validation/test splits.
- Include failed/dead/rugged tokens, not only survivors.
- Include realistic fees/slippage and liquidity constraints.
- Record dataset manifest, code commit and config hash.
- Report distribution, drawdown and score-bucket calibration, not only total return.

Phase 10.2 adds `tests/unit/test_backtesting.py` and
`tests/contract/test_phase10_sprint10_2.py`. The deterministic fixture covers
target/stop and safety/horizon exits, separate entry thresholds, adverse
two-leg fee/slippage arithmetic, unknown future/safety evidence, empty
denominators, drawdown/profit factor, score buckets, all required segment
dimensions, canonical artifact identity and protected modes. The contract
also checks the application/CLI boundary for provider, persistence, signer and
submission dependencies.

Run the keyless projection with:

```text
make backtest-replay
```

The default redacted replay fixture has no strategy snapshot, so the command
must emit an explicit empty report with an entry rejection rather than invent a
trade. A configured strategy still has to be reconstructed through
`ReplayHarness`; backtesting never adds a replay-only decoder or provider call.

## Phase 10.3 score calibration

The keyless calibration suite covers UTC half-open train/validation/test
boundaries, candidate weight validation, named feature ablation, train-only
selection, validation/test isolation, shadow strategy identity, deterministic
candidate/report digests, explicit promotion blocking, attribution lift,
external-label incremental value and bundle/side-wallet false-confluence
measurement. It also checks that the calibration module and CLI do not import
provider, persistence, frontend, signer or transaction-submission authority.

Run the bounded fixture projection with:

```text
make calibrate-score
```

The fixture intentionally lacks sufficient positive strategy evidence, so the
report must retain empty/unknown partition metrics and
`BLOCKED_INSUFFICIENT_EVIDENCE`. A report is never a production config and
the four protected operating modes must remain unchanged. The focused checks
are:

```text
./.venv/bin/pytest tests/unit/test_calibration.py tests/contract/test_phase10_sprint10_3.py -q
```

## Quality gates

Phase 0 should expose a single command such as `make verify` that eventually includes:

```text
backend format/lint
backend static typing
backend unit/integration tests
migration validation
frontend lint
frontend typecheck
frontend unit tests
security/secret checks
```

Browser/live-provider/soak tests may be separate commands but must be documented and invoked at relevant phase gates.

## Coverage

Do not chase a vanity global percentage. Require strong coverage around high-risk deterministic domain code and regression tests for every production bug. Critical risk/execution modules should have branch/edge-case coverage materially higher than presentation code.

## Performance verification

Measure:
- event ingestion throughput/lag;
- score computation latency;
- provider fan-out latency;
- DB query p95 for Radar/timeline;
- replay throughput;
- queue/outbox backlog recovery.

Phase 11.1 adds bounded p50/p95/p99 reports for chain/social ingest, feature,
decision and candidate-alert stages, with explicit provider-network versus
internal attribution and no silent sample eviction. The report includes a
synthetic-local method marker and defers SLO/Rust decisions until real
analysis-only provider measurements are available.

Sprint 6.1 adds credential-free feature-window replay and persistence checks:
the fixture must reproduce identical `1m`/`5m`/`15m` snapshot IDs, values,
provenance, quality and config identity regardless of delivery order; future
evidence must produce `INVALID`/zero-confidence snapshots; and the opt-in
Postgres repository test must round-trip JSON-safe values and provenance while
accepting an equivalent duplicate and rejecting conflicting snapshot reuse.

Sprint 6.2 adds golden score replay for correlated, sparse/unknown,
penalty-clamp and blocked-risk inputs. It verifies stable score identity under
reversed component/penalty delivery, exact weighted arithmetic, bounded
penalties, strategy/model/config identity, hard-risk reason preservation and
pre-boundary rejection. The opt-in Postgres path persists feature, risk and
score rows together and verifies duplicate acceptance plus JSON-safe
round-trips.

Sprint 6.3 adds decision-state replay for sequential `WATCH`, `STRONG_SETUP`
and `ENTRY_READY` transitions, fail-closed blocked/unknown/stale risk,
confidence caps, hysteresis floors, cooldown suppression, deterministic
score-delta/risk-escalation events and an event-time timeline projection. The
contract compares repeated fixture replay and reversed timeline delivery,
checks separate occurred/observed/ingested timestamps, provenance and an
`as_of` no-lookahead boundary, and verifies that the application seam has no
provider/persistence/execution imports. The opt-in Postgres suite also
rehydrates a multi-transition candidate with stable decision identity.

Sprint 7.1 adds alert-pipeline contracts for deterministic projection of
meaningful decision/risk/provider-health events, bounded reason/evidence
rendering, secret-shaped text redaction, alert dedupe, suppression and
per-destination rate limiting. Telegram provider tests use an injected HTTP
client and cover `sendMessage`, `getMe`, authentication, rate-limit, timeout,
transport/schema failures and HTTPS/credential boundaries. The fixture replay
exercises the `NotificationPort` without credentials; the opt-in Postgres
suite verifies alert round-trip plus notification outbox delivery/dedupe, and
Compose smoke/runtime checks verify the worker import and health seam. Missing
Telegram configuration is a key-safe `BLOCKED_EXTERNAL` doctor result, not a
fabricated provider PASS.

Sprint 7.2 adds strict TestClient coverage for all eleven read routes, response
page envelopes, ranking/filter conversion, cursor traversal, correlation
headers, missing-resource `404`, unconfigured-storage `503`, invalid UUID or
address `422`, extra-query rejection, bounded time windows, unknown provider
health and permanent non-authorizing response fields. Application and
persistence contract tests assert that FastAPI/SQLAlchemy/provider imports do
not cross the application read boundary, all read routes are GET-only, and
secret-shaped values/raw references do not escape. The opt-in Postgres test
round-trips a candidate, latest score/risk, transition, feature, observation
and alert through the read adapter and verifies event-time timeline pagination
and no-lookahead. Replay repeats identical output and cursor traversal.
Keyless focused evidence before the full gate: route regression `29 passed`,
Sprint 7.2 replay/Compose contracts `29 passed`, read application/persistence
unit tests `14 passed`, and the opt-in Postgres read adapter test `1 passed`.

Sprint 7.3 adds role-token/RBAC coverage for viewer, operator, admin and
execution principals, including `503` unconfigured auth, `401` malformed or
wrong bearer values, `403` permission separation, strict mutation bodies,
correlation IDs and secret non-disclosure. Control replay covers safe defaults,
idempotent kill activation, protected clear refusal, allow-listed config
validation, canonical hashes and audit pairing. The opt-in Postgres suite
round-trips the singleton state, immutable config version and audit rows,
rehydrates them through a new adapter and projects them through the read API;
the `0003` to `0004` downgrade/upgrade path is verified. Configured role
credentials also protect existing read routes while keyless local development
remains available. No control test can change the four protected modes or
introduce signing/submission authority.

Add regression thresholds only after a stable baseline exists.

## Failure tests

Before production analysis acceptance test:
- provider 429/outage;
- websocket disconnect/reconnect;
- DB restart;
- Redis outage;
- Telegram outage;
- malformed provider payload;
- duplicate/reordered events;
- LLM outage/malformed structured result;
- stale risk evidence.

Before any live trading acceptance additionally test:
- stale/changed quote;
- insufficient balance;
- slippage/impact breach;
- duplicate order request;
- submission timeout with unknown chain status;
- transaction failure;
- reconciliation after restart;
- kill switch during active monitoring.

## Completion evidence

`docs/STATUS.md` must state exact commands and results. Never write “all tests pass” unless they were actually run in the current relevant environment.
