# MemeRadar Status

Last updated: 2026-09-13

This is the current authoritative project state. Historical checkpoint detail
was consolidated here; implementation contracts remain in the canonical
documents below.

## Current classification

| Dimension | Current state | Evidence / constraint |
|---|---|---|
| System stage | `ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION` | Local engineering gates pass; external acceptance and statistical alpha validation are separate. |
| Stack readiness | `STACK_READY` when the local Compose stack is running | API, web, Postgres and Redis contracts are verified locally. |
| Core provider readiness | `READY_FOR_FREE_READ_ONLY_SHADOW` | Core reads do not require Helius or Birdeye; optional enrichment is separate. |
| Shadow collection | `NOT_ACTIVE` | No live shadow evidence is claimed from fixtures or an unavailable stack. |
| Real-world alpha | `REAL_WORLD_ALPHA_NOT_YET_PROVEN` | Historical-real and matured live-shadow samples remain insufficient. |
| Production readiness | `NOT_PRODUCTION_READY` | See [Production Readiness](PRODUCTION_READINESS.md). |
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

## Current blockers

- Compliant historical-real X/Telegram data, CabalSpy-style wallet/KOL stream
  data, Chainlink feed identities, and matured live-shadow observations are
  unavailable; real-provider validation is `BLOCKED_EXTERNAL` and calibration
  is `INSUFFICIENT_SAMPLES`.
- Latest hosted CI run `34717510371` ran for final pushed SHA
  `732d3234c24c6223129f34d97f017e75de2e8a3d`. Backend quality, Frontend
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
- Latest hosted Actions state: run `34717510371`, HEAD
  `732d3234c24c6223129f34d97f017e75de2e8a3d`; Backend quality, Frontend
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
