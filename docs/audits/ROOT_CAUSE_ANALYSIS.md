# Root cause analysis — 2026-11-09

## P30 bounded stream-verification provenance — 2026-11-11

Before P30, persisted recovery verification did not retain enough source metadata to distinguish the provider, scoped program, commitment, verification method and attempt that produced a bounded range. `StreamVerification`, backfill results, SQL persistence and the operations projection now carry those fields where known; absent provider guarantees remain `UNKNOWN`. The migration graph check passes at `0015_stream_verification_provenance`. This improves traceability only: a recovered range does not establish complete subscription coverage, which remains `UNKNOWN`. Current-source `make verify` passed; PostgreSQL execution is blocked in this environment.


1. **Launch identity:** Both research and reevaluation had inferred a Pump.fun launch from event names, permitting another program to enter the cohort. The earlier repair shares a predicate that checks the canonical program ID. Existing observations were not altered; retrospective cohort reconciliation remains open.
2. **Conflicting launch label:** The shared predicate accepted `protocol_event_type=launch` even when the specific `instruction_type` was `buy_v2`. The new regression failed on that input; the predicate now requires a create instruction. It also fails closed for records lacking a specific create instruction, so historical incomplete records require explicit reconciliation rather than inferred identity.
3. **Social checkpoint ordering:** With a checkpoint and deferred persistence, the collector advanced its cursor before calling the sink. A failing sink reproduced the skip. Checkpointed batches now write each page before advancing the cursor. The caller must commit sink and checkpoint together for database crash atomicity; this ordering alone does not prove transaction durability.

Focused results and unresolved runtime integration are in [the issue register](PRODUCT_ISSUE_GRID_LATEST.md). No real provider or PostgreSQL acceptance is inferred from unit tests.

4. **Future liquidity:** A negative observation age passed the previous freshness comparison. A future-dated observation reproduced the failure. The worker now requires occurred, observed and ingested timestamps not to exceed its evaluation checkpoint.
5. **Qualified read omission:** The safety assessment held valid liquidity but stage serialization read a null feature metric instead. The PostgreSQL round-trip regression exposed the mismatch. The stage snapshot now retains assessed liquidity; the existing qualified-read test passes.
6. **Type gate:** SQLAlchemy Core row selection was interpreted as ORM objects in a PostgreSQL test, and normalized fields had broader declared types than their runtime values. Test row mappings and explicit type narrowing restored the gate.

7. **Stream decode loss:** Signature deduplication occurred before parsing; errors were skipped. Source now records an explicit failed-slot gap and bounded diagnostic, reconnects, and remembers signatures only after successful parsing. Reconnection alone is no longer reported as successful recovery.
8. **False slot completion:** One live event caused an entire missing slot to be superseded, without proving all relevant events were present. Gaps remain until verified recovery.
9. **Cross-stream recovery:** The active-gap query returned gaps for other stream identities. Isolated PostgreSQL testing reproduced the issue; selection now filters chain, transport and stream ID.
10. **Paper quote causality:** The pre-request time was reused to check a post-request quote. The response-time checkpoint now gates freshness and the paper order.
11. **Alert state:** Skipped projectable events previously had no durable suppression record. The worker now records reasons and preserves delivered receipts. External timeout ambiguity remains.

12. **Social polling starvation:** Selection rotated only by successful cursor writes. A provider failure left an old candidate at the head of every batch. A deterministic batch fixture reproduced the starvation. A separate poll-attempt checkpoint now records failed and successful attempts; the provider cursor remains independent and is advanced only in the observation transaction. Unit and PostgreSQL tests cover rotation, failed marker writes, rollback, replay and cursor preservation.

13. **Ambiguous Telegram sends:** The generic provider retry loop retried `sendMessage` after a read timeout even though Telegram could already have accepted it. A mock transport reproduced three POST attempts. POST retries are disabled, and the delivery record is durably set to `DELIVERY_UNKNOWN` before the external request. A timeout or malformed acknowledgement leaves that state terminal for automatic replay; the operations API/dashboard expose its count. Unit and isolated PostgreSQL restart tests verify one attempt. A narrow risk remains: a crash after the pre-send state commit but before the HTTP request can leave a notification unattempted and unresolved; automatic retry is unsafe without external idempotency or reconciliation.

14. **Scan Monitor CSS contract:** The page root acquired a static `scan-monitor` class without a stylesheet selector. The repository CSS contract reproduced the missing style. A root `min-width: 0` rule now matches the class; the CSS contract and responsive browser E2E pass. This closes the local styling-contract issue and does not imply provider or API operational acceptance.

The current-source non-integration, isolated PostgreSQL, frontend unit, browser E2E and local security evidence is in [E2E acceptance](E2E_ACCEPTANCE_REPORT.md). No production database, real Solana provider, or real Telegram recipient was used for those tests.

## Continuation findings — 2026-11-10

15. **Caller identity rehydration:** `CallerMarketConductAnalyzer` keyed part of its history by `TokenIdentity` dataclass equality, which includes a random storage UUID. Rehydrating the same canonical mint from persistence can produce a different UUID and split history. The analyzer now compares normalized chain/mint identities, and the social worker persists a versioned `caller-conduct-research-v1` projection with source provenance, point-in-time cutoffs, sample size and UNKNOWN coverage. The early shadow feature consumer receives the projection; there is no production scoring weight. Focused social/caller/research/runtime tests pass.

16. **Pre-identity split write:** A rejected raw event could write its stream gap and diagnostic through separate sessions. A process/database failure between commits could preserve only one side. The rejection callback now supplies the bounded diagnostic to the coordinator, and the SQL stream store flushes both records in one transaction. An injected diagnostic-write failure rolls both records back; repeated observation across a merged gap is idempotent. This does not prove provider coverage or an observable-universe denominator.

17. **Telegram error retry ambiguity:** The service treated request rejection and arbitrary adapter exceptions like transient failures, while a Telegram 429 delay was not carried into durable retry scheduling. Connect failures, explicit rate limits, definite HTTP rejection and uncertain send outcomes now have distinct provider-neutral types. Only proven pre-submit failures and explicit 429 responses retry; ambiguous outcomes remain `DELIVERY_UNKNOWN`, and definite rejection is terminal. Scan Monitor shows the age of the oldest unknown and a bounded sample of persisted reason codes. Focused PostgreSQL worker cases pass (2), and the full isolated suite passes (31). A crash after committing pre-send state but before HTTP initiation remains indistinguishable from an ambiguous attempt and cannot be safely retried automatically.

Exact current commands and limits are in [the continuation acceptance report](E2E_ACCEPTANCE_REPORT.md). No external provider, Telegram recipient, or production database was accessed.

18. **Paper consumer gap (historical, superseded 2026-11-10):** `ShadowEntryService`, quote validation, paper ledger and SQL persistence existed without a durable consumer. The current `run_worker` now conditionally composes `_run_paper_auto` over the durable candidate outbox and existing entry/exit services when a complete explicit policy is configured. Runtime activation and full restart acceptance remain open.
19. **Runtime image findings:** Final Trivy scans on rebuilt images found 47 HIGH Debian OS package findings in each API/worker image, with no fixed version listed in the current scanner feed. `apt-get upgrade` reduced each from 49 to 47, and the web runtime now removes unused npm/npx and scans with zero findings. The current Python image source is Debian 13.7; changing to the available Bookworm image was rejected because its separate scan contained 40 HIGH and 2 CRITICAL findings. Remaining findings need vendor fixes and package-specific reachability review; they are not accepted as clean.
20. **Theme hydration warning:** The old browser log showed a theme-switch hydration warning. The saved-light-theme hydration regression and final multi-viewport Playwright suite reproduced no React hydration error, so no warning suppression or speculative theme code change was applied. The older warning remains historical and non-reproducible in current verification.

### Final-source continuation — 2026-11-11

21. **Synthetic backtest quote unit mismatch:** After P07 made executable raw-unit quotes require explicit decimals, the synthetic backtest still emitted UNKNOWN amount units. Three full-suite failures showed zero trades because rejected synthetic quotes were counted as EXIT skips. The replay harness now explicitly emits `DISPLAY_UNITS`; the fill model keeps Decimal display quantities for research only, while the paper execution engine and shadow entry require raw units with explicit decimals. `paper-fill-v2` versions the changed behavior. The regression was observed failing before the fix; the focused paper/backtest/worker suite passed 92 tests and final local `make verify` passed 1,638 backend tests, 86 frontend tests and declared static/security gates. PostgreSQL, browser E2E and worker restart were not rerun after this backtest-only fix.

The final verification log is `/tmp/memeradar-p07-final-verify.log`. It does not establish real provider coverage, Telegram receipt, clean release identity, process restart, API/worker image remediation or statistical alpha. See [E2E acceptance](E2E_ACCEPTANCE_REPORT.md).

## Current recovery scheduling follow-up — 2026-11-11

**Before:** `EarlyRuntimeStreamWorker` only called the existing backfill coordinator after receiving a live event. A process restart with persisted gaps and a quiet source did not attempt recovery. Also, each incoming event could trigger a scan/retry across every active gap, with no recovery batch cap or inter-pass cadence.

**Root cause:** recovery was coupled to event arrival and `recover_active_gaps()` iterated the full active set. Per-gap RPC range, timeout and retry bounds existed, but the aggregate work per worker pass and frequency across repeated events were not bounded.

**Change:** the existing coordinator selects at most four least-attempted/oldest active gaps per batch by default. The existing stream worker runs one recovery pass before source consumption, then waits on the next event, stop signal or configured recovery interval; timer recovery runs in the same task as event processing. The default interval is 30 seconds. Recovered events use the existing processor and decoder. Total source completeness remains UNKNOWN.

**Regression evidence:** before implementation, the startup and batch/cadence tests failed because the worker did not recover idle persisted gaps and policy batch/cadence fields did not exist. A further idle-source test timed out when a new gap was persisted after startup. After implementation, `tests/unit/test_early_worker_pipeline.py` and `tests/unit/test_stream_integrity.py`: 33 passed; touched Ruff and strict mypy passed. Exact final-source `COVERAGE_FILE=/tmp/memeradar-final-verify-p25.coverage make verify` exited 0: 1,642 backend passed / 33 integration deselected / 7 warnings, 86 frontend passed, 187 mypy files and declared local gates passed.

**Limits:** no PostgreSQL multi-worker claim fencing or process/container restart drill ran on this source; no real provider recovery was executed. A PASS verification for one fetched range is not full program-subscription coverage. See [issue grid P04/P06/P23](PRODUCT_ISSUE_GRID_LATEST.md) and [E2E acceptance](E2E_ACCEPTANCE_REPORT.md).

## P28/P29 — cross-worker claim and lease-expiry fencing — 2026-11-11

**Before:** Two coordinators could enter `recover_gap` for the same gap and both call the provider. The read-then-save recovery transition did not atomically claim ownership. A follow-up review found that even a recorded owner could renew or finalize at the exact lease deadline before another worker had taken over.

**Root cause:** gap state tracked only `RECOVERING`; it had no durable owner token or expiry check on writes. Concurrent workers duplicated work, and stale workers could extend/finalize beyond their lease.

**Change:** migration `0014_stream_gap_recovery_claims` adds claim UUID/expiry. SQL conditional updates and the in-memory store now require matching owner and unexpired lease for renewal/finalization. Gap state and verification are committed together. Coordinator claims before provider work and skips already owned gaps. Provider completeness remains separate.

**Evidence:** the simultaneous-call regression failed before implementation with two provider calls. Exact-expiry renewal regressions failed on both stores before the P29 fix and passed after. Recovery slice passed 62 tests / 2 PostgreSQL skips; final P29 `make verify` passed 1,648 backend tests / 34 integration deselected / 7 warnings plus all declared local gates. Fingerprint and logs are in `artifacts/verification/VERIFICATION.md`.

**Limits:** two-engine PostgreSQL concurrency, migration execution against PostgreSQL, worker restart, and provider-backed completeness remain unverified because test PostgreSQL and Docker access are unavailable. P29/P30 browser E2E and production build are separately blocked by sandbox process/network restrictions; no application workaround was applied.
