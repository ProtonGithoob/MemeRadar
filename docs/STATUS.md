# MemeRadar Status

Updated: 2026-11-11. This current checkpoint supersedes the chronological notes
below; those entries remain as historical evidence.

**CURRENT_PHASE:** P30 local verification and report reconciliation complete. Bounded stream-verification provenance is persisted and exposed; source completeness remains unknown.
**BRANCH / HEAD:** P30 was recorded on `main` / `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5` (dirty). The 2026-11-11 audit remediation (see `AUDIT_REMEDIATION_2026-11-11` below) is on `claude/exciting-brahmagupta-0k7pds` and is not yet merged to `main`.
**SOURCE CHECKPOINT:** P30 fingerprint `97e36f90571212c774b8827a2672a4f1a3137f5c39cdfaf3c12f4a1f2cbfe6e8` covers 641 source/config/test files (8,385,898 bytes); manifest: [`source-fingerprint-p30.json`](../artifacts/verification/2026-11-11-final/source-fingerprint-p30.json). The manifest was rechecked: 641 present, zero hash mismatches, zero missing files.
**LATEST TEST STATUS:** `COVERAGE_FILE=/tmp/memeradar-final-verify-p30.coverage make verify > artifacts/verification/2026-11-11-final/make-verify-p30.log 2>&1` exited 0: backend 1,650 passed / 34 integration deselected / 7 warnings in 406.61s; frontend 86 passed / 25 files; Ruff, mypy (187 files), CSS contract, frontend lint/typecheck, Compose config, secret scan, local security review and SBOM passed. Migration graph head `0015_stream_verification_provenance`, 27 ORM tables. Log SHA-256: `9ab4ced53531fc3a24b1e62c24e03d97bd4bf7a9fca566641a2f60168d352c15`.
**PERSISTENCE:** Verification rows now preserve provider, program scope, commitment, verification method and recovery attempt; the operations projection exposes those fields and evidence-reference counts. Migration graph check passes at `0015_stream_verification_provenance`. This is local code/migration-graph validation, not a PostgreSQL migration run. PostgreSQL integration remains blocked: test URL unset, local binaries absent, Docker API denied.
**OPEN P0:** Overall source/subscription coverage is still `UNKNOWN`; bounded local recovered ranges do not prove full provider or subscription completeness. Provider-backed recovery, complete observable-universe denominators, verified historical inventory and genuine Telegram receipt remain unaccepted. Caller-conduct remains shadow-only.
**OPEN P1:** Paper worker remains disabled unless explicit policy and a matching PAPER/SOL portfolio are configured. Current-source PostgreSQL worker recreation, portfolio concurrency and complete process restart remain unverified. Independent real alpha remains `NOT_PROVEN`.
**SECURITY / BLOCKERS:** P30 local secret/security checks passed; external container/npm/pip scans were NOT_RUN. Historical Trivy scans found 47 HIGH Debian OS findings in each API/worker image; no current rescan was performed. Browser E2E was blocked before test execution by sandbox listener `EPERM`; production build compiled but Next's TypeScript subprocess output was unavailable in the sandbox. No authorized provider or Telegram recipient was used.
**READINESS:** Local declared verification scope PASS; overall engineering/product readiness PARTIAL; operational acceptance BLOCKED where noted; predictive validation `NOT_PROVEN`. See [final readiness](audits/FINAL_PRODUCT_READINESS.md).
**SAFETY:** `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`; no signing or real transaction submission was added.

## Historical status entries

**ALERT_PIPELINE_2026-11-11:** Owner decision recorded: bonding-curve
liquidity is proven by executable Jupiter round-trip depth (USD 1000 within
1000 bps); buying and selling stay manual and execution modes are unchanged.
Added since the previous entry:
- depth-liquidity evidence;
- keyless Jupiter pacing (1.1 s);
- quotes spent only on tokens with at least 5 distinct tape buyers;
- backfill block concurrency and a size-scaled timeout;
- undecoded-create-only backfill guard;
- canonical chain rows win over stale re-saves.

Final 9.5-minute live run (publicnode HTTP, mainnet-beta WebSocket, local
SQLite): 39 launches, 1,003 trade events, 156/156 reevaluations executed
with 0 errors, organic momentum differentiated on 42.

No candidate reached PASS or an alert in this sandbox. Jupiter's keyless
tier still answered 429 to 23 of 71 paced requests (the egress IP is
shared), so sellability stayed UNKNOWN. Two of three gaps did not verify
(one BACKFILL_TIMEOUT, one BACKFILL_UNAVAILABLE).

Not yet verified: a real Telegram delivery, and behaviour on the operator's
own IP or with a keyed RPC/WebSocket. Unit suite: 1,710 passed.

**ALERT_READINESS_2026-11-11:** Goal is to find correct early tokens and send
Telegram alerts, with buying and selling done manually (execution modes
unchanged).

Keyless Jupiter (`https://lite-api.jup.ag/swap/v1`) now supplies executable
buy/sell quotes. It routes fresh Pump.fun bonding-curve tokens, and
`priceImpactPct` was verified as a fraction. Stream gaps are scoped to a
token's own slots. Fixed fixed-identity collisions:
- Jupiter quotes failed 19/48 reevaluations;
- forward research stalled every cycle (343 failures in 8 minutes).

An 8-minute live run (publicnode HTTP, mainnet-beta WebSocket, local SQLite)
had 0 failed reevaluations, 38 executable quotes and real safety decisions
(28 BLOCK, 20 RISK_REJECTED).

Blocker for alerts: `LIQUIDITY_UNKNOWN` on about 97% of snapshots, because
DexScreener publishes no liquidity for Pump.fun bonding-curve pairs. The
trade event's real SOL reserve field failed independent verification (3 of 7
consistent) and is not used. An owner decision is needed: accept
executable-quote depth as bonding-curve liquidity evidence, or alert only
after migration.

Jupiter's free tier returned 429 on 25 of 68 calls, so quote probes need
gating to promising candidates.

**PUMP_TRADE_TAPE_STAGE2_LIVE_2026-11-11:** Trade tape is wired end to end.
The protocol registry routes the verified `trade_event`. The live source
decodes trade events from logs for mints launched within 20 minutes (capped
per mint). Backfill uses the same log decoder. The stream worker persists
tape without a runtime pass, and lifecycle reevaluation feeds tape to the
feature engine. Bounded live mainnet runs (read-only, public RPC, local
SQLite worker) found and fixed:
- launch misclassification from other programs' `Create*` logs;
- `create_v2` 4/8-account extensions rejected as invalid;
- zero-signature notices forcing reconnects;
- account and DexScreener snapshot source identities that crashed the worker
  with `IdempotencyConflict` (46% of reevaluations failed);
- single-event failures stopping ingestion;
- persisted chain events discarded as non-production evidence.

Measured over 4 minutes, before → after:

| Metric | Before | After |
| --- | --- | --- |
| Launches | 7 | 85 |
| Decoder failures | 10 | 0 |
| Trade events | 41 | 3,851 |

A 6-minute full-worker run had 0 crashes and 0 failed reevaluations, with
organic momentum ranging 35–87 from real tape. Remaining external blockers:
- `early_score` stays 0 because no executable quote provider is configured
  (DexScreener reference cannot prove sellability) and public WebSocket
  disconnects every 15–35 s keep stream gaps open, which fail protocol
  identity closed;
- `solana-rpc.publicnode.com` does not deliver `logsSubscribe` notifications.

Protected modes are unchanged; no credentials were used or stored.

**PUMP_TRADE_TAPE_STAGE1_2026-11-11:** A cloud environment with free public
Solana RPC (`api.mainnet-beta.solana.com`, `solana-rpc.publicnode.com`) and
DexScreener access was created for read-only verification. The Pump.fun
Anchor `TradeEvent` (`bddb7fd34ee661ee`) was observed on mainnet, and its
prefix fields were cross-checked against user token balance deltas and block
time (51/60 single-trade transactions; the remaining 9 were router trades).
`memeradar_providers.pump_fun_events` decodes it from logs, accepting a line
only while Pump.fun is the executing program. Verified mainnet fixtures and 8
tests were added. Stage 2 is still open: live and backfill wiring, a registry
entry, tracked-mint gating and a trade-only runtime path that skips
per-event quote collection.

**AUDIT_REMEDIATION_PHASE2_2026-11-11:** Research validity and paper
realism fixes, each with a regression test verified failing before the
change:
- unexecutable paper positions are written off at total loss after the
  time stop plus `PAPER_AUTO_UNEXECUTABLE_GRACE_SECONDS`;
- backtest `worst_case_expectancy` books unresolved exits as losses, and
  calibration ranks on it with a minimum-sample guard;
- calibration splits support an embargo (24h default in `calibrate_score.py`);
- outcome horizons past the dataset end are `OUTCOME_HORIZON_TRUNCATED`;
- timed exits precede horizon safety labels, and stop/label drawdown
  fractions must match;
- one simulated position per token;
- `OrganicFlowAcceleration` is fed from tape-corroborated organic momentum.

Ruff, mypy (187 files) and the non-integration suite (1,673 passed) passed.
Live `ENTRY_READY` still requires live trade tape, which is not ingested
(only launches are). Large-gap recovery needs signature-based backfill.
Protected modes are unchanged.

**AUDIT_REMEDIATION_2026-11-11:** Independent SWOT/defect audit recorded in
[SWOT and defect audit](audits/SWOT_AND_DEFECT_AUDIT_2026-11-11.md). A clean
bootstrap from `requirements.lock` failed the unit suite because `aiosqlite`
was undeclared; it is now locked. Fixed with regression tests (each verified
failing before the change):
- protocol identity forced unverified during gaps and outages;
- reconnect boundary cleared after the first event;
- backfill refused beyond the finalized tip;
- worker restart downtime recorded as a gap;
- paper positions marked so trailing and break-even exits fire;
- unassessed creator/fresh-wallet evidence is UNKNOWN;
- Jupiter quotes without price impact are rejected;
- zero first price no longer crashes features;
- candidate and position reads are ordered.

Ruff, mypy (187 files) and the non-integration suite (1,664 passed, 34
deselected) passed. PostgreSQL integration, browser E2E and live providers
were not run. Open P0/P1 items are listed in section 9 of the audit: zombie
paper positions, knowledge-time checkpoints, backtest/calibration bias,
oversized gap chunking and unreachable `ENTRY_READY`. Protected modes are
unchanged.


**OPEN_SOURCE_WATCH_2026-11-03:** MadeOnSol bundle-cluster completeness is now
preserved and incomplete/unknown cluster shares remain null. Provider notes
record why PumpData, CabalSpy ID, Pythia-specific tuning, Hood Synapse and Sol
Parser were not wired into runtime. Checks were not run for this small delta.

**OPEN_SOURCE_WATCH_2026-10-31:** Solana RPC block backfill now requests
transaction version 1, matching the transaction read path. The focused Solana
RPC and raw-stream suites passed (22 tests). Relay router identities, payout
matching, ShredStream ALT recovery, external risk adapters and real-data model
comparisons remain unverified and are not claimed as implemented.

**LAUNCH_RISK_POINT_IN_TIME:** Launch-risk observation and supply calculations
now exclude observations occurring, observed or ingested after the checkpoint;
the supply calculation also respects the existing shadow-evidence filter.
Focused launch-risk, fast-safety and Solana provider suites passed (35 tests).
Externally supplied aggregate snapshots still require their own point-in-time
guarantees; live provider and real-data validation remain outstanding.

**SCAN_MONITOR:** `/scan-monitor` displays bounded candidate records, recorded
early-radar rejected/blocked decisions and provider health with timestamps.
It refreshes every 30 seconds while visible. Pre-identity discarded events have
no durable producer and are explicitly excluded from the displayed record.
Focused frontend tests (4), TypeScript and touched-file ESLint passed; browser
and live-provider validation were not performed.

**LIVE_DISPLAY_REMEDIATION:** Candidate, token and position reads can recover
missing names and symbols from fresh canonical create-event observations at or
before the read checkpoint. The Solana stream now records subscription state;
the operations API projects the latest bounded snapshot and leaves overall
stack status UNKNOWN. Provider backfill errors are translated into the existing
recovery contract. Local live reads showed 10 of 13 candidates with symbols;
unavailable metadata remains unknown. Reevaluation no longer emits an alert for
an already-existing WATCH transition, preventing the observed idempotency
conflict; earlier failed reevaluation records remain preserved and were not
replayed. Many risk/market fields lack live evidence.

**TELEGRAM_DISCOVERY_FOCUS:** Candidate state changes now persist a separate
notification outbox job only for EARLY_WATCH or stronger signals with passing,
fresh safety evidence, available providers and no unresolved stream gap. The
delivery worker independently enforces the same explicit eligibility marker
and does not send ordinary WATCH, rejected, operational or legacy unmarked
events; signals older than five minutes are also skipped. Existing rate limits
and deduplication remain active. Telegram HTTP
request logs no longer expose bot-token URLs. Scan Monitor displays configured
status and database-backed delivery/queue counts without revealing credentials.
The local Telegram bot and chat passed read-only checks; prior to the stricter
filter two alerts were recorded delivered. No message has yet been verified
under the stricter filter. Public Solana RPC returned 429 and unresolved gaps
remain, so signal coverage is not accepted. Auto and manual execution remain
disabled. Earlier failed reevaluation records were not replayed.

Replay now restores previously persisted stage snapshots rather than generating
new identities from timing measurements. Verified stream-gap recovery persists
the required RECOVERED transition before VERIFIED. Null-score pagination and
the Settings read contract were corrected. Focused Python checks (63 tests),
PostgreSQL checks (3 tests), frontend tests (86 tests before the last focused
22-test run), TypeScript, lint, and desktop browser checks (8 passed, 1 skipped)
passed. These do not constitute complete acceptance of every page or live
strategy; chain opportunities still has no persisted projection.

**EARLY_RADAR_READ_PATH:** The database read service now projects persisted
early-stage snapshots for current Solana candidates. Stale snapshot risk is
UNKNOWN rather than PASS. Two focused PostgreSQL integration tests passed;
the local API returned 50 early-radar records and the page rendered successfully.
The 30-second frontend refresh remains a polling fallback, not a WebSocket.

The full frontend suite was rerun with two workers: 86 passed. Local worker
shutdown did not complete promptly while recovery was active, so the local
worker was terminated and restarted with the five-minute notification filter;
the durable recovery gap remains subject to reconciliation.

Detailed evidence: [CI causes](audits/CI_ROOT_CAUSE_ANALYSIS.md),
[stabilization changes](audits/STABILIZATION_CHANGES.md),
[provider capabilities](audits/PROVIDER_CAPABILITY_MATRIX.md), and
[runtime acceptance](audits/RUNTIME_ACCEPTANCE.md), plus the
[duplicate-workspace audit](audits/DUPLICATE_WORKSPACE_AUDIT.md) and
[2026-11-06 consolidation report](repository-consolidation/09_FINAL_EXECUTIVE_REPORT.md)
and [recursive acceptance report](audits/RECURSIVE_ACCEPTANCE_REPORT.md). The
machine-readable issue ledger is at
[`artifacts/verification/RECURSIVE_ACCEPTANCE_LEDGER.json`](../artifacts/verification/RECURSIVE_ACCEPTANCE_LEDGER.json).

**QUALIFIED ULTRA-EARLY VIEW:** Ultra-Early requests only current snapshots
with a recent notification-eligible state transition and fresh PASS safety
assessment. The Telegram column shows delivered only when a delivery record
exists. The default grid now emphasizes available decision data. The live API
and page returned HTTP 200 with zero qualified candidates at verification;
no new delivery was verified under the stricter gate. Public RPC rate limits
and unresolved stream gaps still limit timely coverage.

**EARLY_CANDIDATE_EVIDENCE_REPAIR:** The live worker now gathers parsed SPL
mint authority data, current liquidity and executable buy/sell quote evidence
before evaluating a verified launch; the lifecycle reevaluator repeats the
same evidence collection and rewrites the current stage snapshot when evidence
changes without a state transition. Jupiter quote routing is configured only
when both URL and API key are present. The 0.01 SOL route probe is read-only;
DexScreener's market reference cannot satisfy sellability or impact gates.
FastSafety now preserves direct evidence references and reports missing
critical fields as reasons; the Ultra-Early inspection panel shows authority,
protocol, quote and evidence-reference values. An unavailable raw transaction
now forces a reconnect without marking its signature completed, so the stream
coordinator can attempt gap recovery. These source changes were not executed
or live-validated in this task; no test command was run. Public RPC rate limits,
missing quote configuration, unresolved gaps and Telegram delivery remain
external readiness constraints. Execution modes remain unchanged.

**EARLY_CANDIDATE_FOLLOWUP:** Restored standard RPC account observations, imported
worker event normalization, and kept snapshot identity stable across latency-only
changes. Focused backend suite: 46 passed; web typecheck passed and focused web
suite: 24 passed; Ruff passed for touched backend areas. Live RPC, Jupiter and
Telegram delivery remain unverified and require configured provider access.
Targeted mypy was interrupted after reporting unresolved local package imports;
its result is incomplete and requires the repository's configured module path.

**PRODUCT_BUG_AUDIT_2026-11-06:** MadeOnSol bundle normalization now marks conflicting nested and top-level completeness flags UNKNOWN, preventing incomplete cluster evidence from being reported complete. A Jupiter provider composition test now supplies the required fixture API key; a separate regression confirms missing-key configuration remains unavailable. Focused provider suite: 65 passed; launch-risk/safety suite: 61 passed; touched-file Ruff and `git diff --check` passed. The broader non-integration pytest run and mypy were interrupted after stalling without a final result; PostgreSQL, live providers and browser acceptance were not run. This is not a complete product audit.

**PAPER_QUOTE_CAUSALITY_2026-11-06:** A fresh quote observed after the paper order time previously produced a fill. Quote consumers now require observation at or before their checkpoint; paper auto, shadow entry and discovery use the same check. The reproducing test failed before the change and passes afterward. Related paper, discovery, stream, wallet and provider suites: 103 passed; touched-file Ruff and `git diff --check` passed. The full non-integration pytest diagnostic timed out (exit 124) inside the Git-history secret scan; full mypy timed out (exit 124) without output. No runtime, live provider, PostgreSQL or alpha-performance acceptance is implied.

**VERIFICATION_REMEDIATION_2026-11-06:** Git-history secret scanning now reads one object at a time, propagates Git/read failures, and keys its cache by refs. Regressions reproduced the previous false-clean results and now pass. The release-identity test now compares the SBOM count and digest to the actual lock-derived SBOM instead of a stale fixed count. The current dirty-worktree non-integration backend suite exited 0: 1,546 passed, 22 deselected, 7 warnings; frontend Vitest passed 86 tests, lint and typecheck exited 0. Current production build exited 1 after compilation: direct TypeScript `--showConfig` succeeded but Node synchronous child invocation reported EPERM and no output. Migration static check reports one head `0012_stream_gap_diagnostics` and 27 tables. PostgreSQL, browser, live providers, full mypy and worker wiring remain unaccepted.

**VERIFICATION_FOLLOWUP_2026-11-06:** Standalone secret scan exited 0 with no findings; replay/backtesting/calibration fixture suite passed 27 tests. The social-call collector, caller conduct analyzer, shadow PAPER orchestration and pre-identity rejection/reconciliation still lack the requested operational path. No runtime wiring was added in this verification slice. PostgreSQL acceptance remains blocked by the missing isolated test URL and denied Docker socket; browser and live-provider acceptance remain unverified.

**PRODUCT_AUDIT_2026-11-09:** The Pump.fun forward research and lifecycle reevaluation filters now require the canonical Pump.fun program ID instead of accepting a generic create/launch label alone. The new regression failed before the fix; focused worker tests passed (18), and touched-file Ruff passed. Previously collected research data was not reconciled. A fresh full non-integration test run and mypy were interrupted without final results; PostgreSQL, browser, providers and live shadow remain unaccepted. The [issue grid](audits/PRODUCT_ISSUE_GRID_2026-11-09.md) and [remediation plan](superpowers/plans/2026-11-09-product-audit-remediation.md) record open capability and evidence gaps. Existing uncommitted work and recovery material remain untouched.

**PRODUCT_COMPLETION_AUDIT_2026-11-09:** A conflicting launch label could classify a Pump.fun trade as a launch; the shared predicate now requires the create instruction. Checkpointed social collection now saves calls before advancing its cursor; shared transaction atomicity and worker integration remain open. The live evidence path rejects future-dated market liquidity, and early stage snapshots retain safety-assessed liquidity, restoring qualified PostgreSQL reads. Reproducing tests failed before fixes. Focused suite: 42 passed; isolated PostgreSQL migrations succeeded and integration suite: 22 passed, 2 warnings; full mypy: 183 files clean; Ruff, frontend lint/typecheck and 86 frontend unit tests passed. Full non-integration diagnostic timed out after 240 seconds; live providers, browser E2E, operational crash recovery, social/paper worker composition and predictive validation remain unaccepted. Dedicated task test container `memeradar-codex-audit-pg-20261109` and its databases remain preserved; TCP access was set to reject after testing. See [issue register](audits/PRODUCT_ISSUE_GRID_LATEST.md) and [acceptance report](audits/E2E_ACCEPTANCE_REPORT.md).

**BACKEND_VERIFICATION_FOLLOWUP_2026-11-09:** `timeout 600 .venv/bin/python -m pytest -q -m "not integration" --no-cov` exited 0: 1,550 passed, 22 deselected, 7 warnings. The separate PostgreSQL integration suite passed 22 tests. Standalone secret scan and security-review runs were interrupted and are not accepted for this checkpoint.

**P0_P1_CONTINUATION_2026-11-09:** Added read-only launch identity inventory and fail-closed forward report filtering, opt-in bounded social worker with atomic page/cursor persistence, mock Telegram outbox integration and suppression reasons, bounded pre-identity rejection diagnostics, and paper quote response-time correction. The stream now reconnects rather than marking failed decodes seen, does not equate reconnect with recovery, retains gaps on late event receipt, records known failed slots, and scopes active gaps by chain/transport/stream. Full isolated PostgreSQL integration: 27 passed; non-integration suite: 1,566 passed, 26 deselected before final gap edits; final focused stream/pre-identity suite: 39 passed including the additional cross-stream regression. Ruff, mypy (185 files), SBOM and standalone secret scan passed. Social caller-conduct/scoring integration, fair polling, durable pre-identity reconciliation, paper worker wiring, live-provider recovery, real Telegram delivery and real alpha remain unaccepted. No production observations or prior volumes were modified.

The task-owned `memeradar-p0-validation-20261109` PostgreSQL container and test database remain preserved; TCP authentication was changed to reject after testing. Standalone secret scan and an additional scan of new untracked source files reported no findings. Local HEAD and locally recorded `origin/main` matched (0/0); remote state was not fetched.

**SECURITY_CONTINUATION_2026-11-09:** Standalone secret scan and local security review passed; SBOM check passed. A separate targeted scan found no high-confidence material in the new untracked source/test files. External container, npm and Python vulnerability scans remain unaccepted.
