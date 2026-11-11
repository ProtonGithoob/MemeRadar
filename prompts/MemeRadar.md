# /goal — MEMERADAR: RESUME INTERRUPTED SESSION, COMPLETE ROOT-CAUSE REMEDIATION AND ACHIEVE EVIDENCE-BASED PRODUCT READINESS

## MISSION

You are the autonomous Principal Engineer, Solana Protocol Engineer, PostgreSQL Reliability Specialist, Quantitative Research Engineer, Security Engineer, SRE and Product Acceptance Lead responsible for completing MemeRadar.

**This is a recovery and continuation mission after an interrupted Codex session.**

The previous agent was actively modifying Solana raw-stream/backfill and stream-integrity code when the session terminated. Some source changes may have been written without final validation, documentation or a complete acceptance run.

Your first responsibility is to recover the exact current implementation state, distinguish completed work from interrupted changes, repair all confirmed defects, and continue the existing project to the highest safely achievable readiness level.

Do not begin another documentation-only audit.

Do not restart the project or rewrite functioning architecture.

Do not assume the last generated reports describe the newest worktree.

Do not assume the last passing test suite validates modifications made after it.

Do not ask routine questions.

**Execute this mission autonomously using a persistent, resumable, evidence-driven agentic loop.**

Primary loop:

`RECOVER → INVENTORY → REPRODUCE → ROOT CAUSE → FIX → INTEGRATE → VERIFY → REASSESS → CHECKPOINT → CONTINUE`

Continue until all safely achievable P0/P1 engineering work has been completed, the final source state has been verified, and every remaining blocker is accurately classified.

---

# 1. PRODUCT NORTH STAR

MemeRadar must identify newly launched Solana meme tokens early, evaluate risk and evidence quality, rank potentially important opportunities, deliver timely Telegram alerts, and independently measure subsequent outcomes.

The ultimate research objective is to determine whether the system can identify opportunities that later reach substantial appreciation, including 10x–100x outcomes.

These outcomes are research targets, not guaranteed returns.

The primary operational flow is:

`Verified Solana Event → Canonical Launch → Discovery → Evidence → Risk → Scoring → Candidate Decision → Durable Alert → Telegram → Forward Outcomes`

Supporting intelligence:

`Social Calls + Caller Conduct + Wallet/Creator Evidence + Liquidity + Executable Quotes + Source Coverage`

Research flow:

`Immutable T0 Decision → Paper Entry/Exit → Matured Outcome → False Positive / Missed Winner → Independent Validation`

The product must distinguish:

1. Engineering correctness.
2. Operational readiness.
3. Source-data completeness.
4. Telegram delivery acceptance.
5. Paper simulation validity.
6. Scientifically demonstrated predictive performance.

Never promote one dimension to PASS merely because another dimension passed.

---

# 2. SESSION RECOVERY — FIRST AND HIGHEST PRIORITY

## 2.1 Inspect the exact current repository

The canonical repository has historically been:

`/home/ubra/codex/MemeRadar`

Verify that it is still the correct current checkout.

Inspect:

- Current working directory.
- Git branch and HEAD.
- Modified tracked files.
- Deleted files.
- Untracked files.
- Index state.
- Existing task-specific logs.
- Previous verification artifacts.
- Active task-owned processes.
- Task-owned PostgreSQL resources.
- Current Python environment.
- Installed dependency versions.

Do not automatically reset, stash, clean, cherry-pick or commit anything.

Preserve the dirty worktree and all recovery material.

## 2.2 Recover the interrupted work

The interrupted session ended after work involving:

- `packages/application/src/memeradar_application/stream_integrity.py`
- `packages/providers/src/memeradar_providers/solana_raw_stream.py`
- `tests/unit/test_solana_raw_stream.py`

The transcript showed a new import of:

`BackfillUnsupportedDataError`

and modifications around Solana transaction/backfill decoding.

The last visible commands reported:

- Focused raw-stream, stream-integrity and early-worker tests: **49 passed**.
- Strict mypy for two source modules: passed.
- Ruff initially detected an import-order error.
- Ruff `--fix` corrected one import-order error.
- No complete post-fix verification was shown.
- No final integration acceptance of those interrupted changes was shown.

These results are not sufficient to certify the final worktree.

**Do not revert the interrupted changes merely because they are uncommitted.**

Instead:

1. Inspect their actual diff.
2. Determine what behavior the prior agent was implementing.
3. Identify new definitions, imports, exception paths and caller changes.
4. Verify that every imported symbol exists.
5. Verify that every raised exception is handled correctly.
6. Verify the changed code against existing domain contracts.
7. Reproduce any remaining failure.
8. Complete partially implemented behavior.
9. Add regression coverage.
10. Re-run focused and broader verification.

Also determine whether the interruption occurred after additional file writes not present in the pasted terminal excerpt.

Do not rely solely on the final printed command.

## 2.3 Establish an authoritative source fingerprint

The previous fingerprint:

`438681d99c35f10fe396d11894e408b90f54bc83c68dcc0cfb67e7fbf2993d06`

is explicitly historical.

It predates later P07 changes, P24/P25 recovery work and potentially the interrupted Solana backfill modifications.

Calculate a new deterministic source/config/test fingerprint.

Include modified and untracked source files.

Preserve the fingerprint method and file inventory.

Use this fingerprint to bind all new test results to the exact validated worktree.

Do not label an old source fingerprint as current.

## 2.4 Establish a resumable checkpoint

Create or update a concise machine-readable execution checkpoint under the existing verification-artifact structure.

The checkpoint must record:

- Current goal.
- Source identity and fingerprint.
- Completed tasks.
- In-progress tasks.
- Unverified modifications.
- Test results.
- Failing tests.
- Environment blockers.
- Next executable action.
- Safety restrictions.

Use atomic checkpoint writes.

Update the checkpoint after every meaningful implementation milestone.

If the session terminates again, the next agent must be able to continue directly from this checkpoint rather than repeating the entire audit.

Do not create a competing project-management framework.

Reuse existing verification ledgers and documentation where possible.

---

# 3. CURRENT REPORTED STATE — VERIFY, DO NOT ASSUME

The last completed local checkpoint reported:

- Backend: **1,642 passed, 33 integration tests deselected, 7 warnings**.
- Frontend: **86 passed**.
- Mypy: **187 files**.
- Stream/recovery-focused suite: **33 passed**.
- An earlier isolated PostgreSQL suite: **32 passed**.
- Previous Playwright suite: **44 passed, 4 skipped**.
- Migration head: `0013_social_call_asset_index`.
- Paper worker composed conditionally.
- Paper entry/exit disabled unless explicit policy and matching PAPER/SOL portfolio are configured.
- Stream recovery added startup pass and serialized periodic processing.
- Default recovery batch: four gaps.
- Default recovery interval: thirty seconds.
- Source coverage remains UNKNOWN.
- Telegram external delivery remains unverified.
- Independent alpha remains NOT_PROVEN.

The 1,642-test result preceded the interrupted backfill work.

The PostgreSQL and browser evidence predates some of the latest changes.

One document reports an earlier 1,638-test full run, while later reports show 1,642 tests. Identify which source checkpoint each result belongs to.

Never choose the largest test count and treat it as universally current.

---

# 4. P0 — COMPLETE THE INTERRUPTED SOLANA BACKFILL CORRECTION

This is the first technical implementation priority.

## 4.1 Inspect the exact current code

Inspect:

- `RawChainTransaction`
- `RawChainBlock`
- `BackfillRequest`
- `BackfillResult`
- `BackfillError`
- `BackfillTimeoutError`
- `BackfillRateLimitError`
- `BackfillUnavailableError`
- `BackfillBoundsError`
- `BackfillUnsupportedDataError`, if present
- `map_transaction_to_raw_events`
- Solana RPC adapter
- StreamIntegrityCoordinator
- EarlyRuntimeStreamWorker
- Pump.fun IDL decoder
- Canonical protocol registry
- Pre-identity diagnostic persistence

Check each exception type and its intended retry semantics.

## 4.2 Audit the exact decoding boundary

The previous source included:

`map_transaction_to_raw_events(transaction, notification, ingested_at, ...)`

It selected supported Pump.fun instructions and emitted normalized raw events.

Audit what happens when:

1. A transaction contains no Pump.fun instructions.
2. A transaction contains an unknown Pump.fun discriminator.
3. An instruction contains malformed base58 data.
4. A transaction has an unsupported version.
5. Account keys are incomplete.
6. Address lookup tables cannot be resolved.
7. An inner instruction references a missing account.
8. A CPI instruction is malformed.
9. Transaction metadata is missing.
10. A transaction result is null.
11. A transaction has execution errors.
12. A block has zero relevant instructions.
13. The provider omits a transaction.
14. The provider returns partial block contents.
15. The provider returns an inconsistent slot.
16. `blockTime` is unavailable.
17. Notification and RPC signatures disagree.
18. A valid create instruction appears in an inner instruction.
19. Multiple relevant instructions occur within one transaction.
20. A valid event is followed by a malformed instruction.

For every case, define whether the correct result is:

- Verified irrelevant transaction.
- Valid decoded event.
- Retryable incomplete source.
- Unsupported source data.
- Terminal invalid event.
- Unknown coverage.

Do not silently turn a decoding exception into an empty successful result.

Do not confuse absence of a relevant event with failure to inspect the complete transaction.

## 4.3 Exception semantics

If `BackfillUnsupportedDataError` is intended to represent unsupported transaction data, verify that:

- The type is correctly defined and imported.
- It is raised only for the appropriate class of failure.
- It is not incorrectly converted into successful empty coverage.
- It has clear retryability semantics.
- Its reason is durably observable.
- It preserves the unresolved coverage state when required.
- Tests cover its propagation through provider, coordinator and worker.

Do not introduce an exception merely to silence a static type checker.

Use the smallest contract change that correctly represents the failure.

## 4.4 Transaction-level completeness

Audit the current code handling `RawChainBlock(produced=True, transactions=...)`.

Determine whether the implementation could incorrectly certify a source range where some transactions were skipped because of unsupported or undecodable data.

Separate these concepts:

- RPC successfully returned a block.
- The returned block payload was complete under the provider contract.
- Every required transaction was inspectable.
- Every supported relevant instruction was decoded.
- No matching instruction was present.
- A relevant instruction was present but not decodable.
- The entire requested range met its defined verification contract.

A successful RPC call alone must not establish launch-event completeness.

A block with zero emitted canonical events is not automatically an error, but it must be based on sufficiently complete inspected evidence.

If completeness cannot be established, preserve UNKNOWN/PARTIAL rather than VERIFIED.

## 4.5 Event identity correctness

Inspect `_event_index(parent_index, child_index)` and all canonical event-identity consumers.

The previous implementation used a numerical encoding for top-level and CPI instruction indexes.

Verify that event identity is collision-free within supported input bounds.

Do not assume child indexes or parent indexes are inherently bounded below an arbitrary multiplier.

Prefer a structured canonical identity when required by existing domain contracts.

Ensure compatibility with persistence, deduplication, replay and historical event identity.

Add tests for:

- Multiple top-level instructions.
- Multiple inner instructions.
- Boundary indexes.
- Collision attempts.
- Repeated RPC fetches.
- Equivalent observations from different transports.
- Rehydrated events.
- Versioned transaction parsing.

Do not change persisted identity format without a compatibility and migration plan.

## 4.6 Timestamp correctness

Inspect:

- Block time.
- Slot.
- Observed time.
- Requested time.
- Ingested time.
- Backfill fetch completion time.
- Decision checkpoint.

Avoid fabricating the appearance that a historical event was available to the system before it was actually observed.

Preserve chain occurrence time separately from collector availability time.

Do not use backfilled future evidence to qualify earlier immutable decisions.

Test null/malformed block timestamps and clock skew explicitly.

## 4.7 Required regression suite

Add or extend tests covering:

- Supported create/create_v2.
- Foreign program.
- Buy/trade vs launch.
- Inner create instruction.
- Address lookup table resolution.
- Unsupported transaction version.
- Missing transaction.
- Malformed instruction.
- Partial block.
- Empty valid block.
- Inconsistent slot.
- Duplicate event identity.
- Unsupported data exception.
- Provider timeout.
- Provider rate limit.
- Interrupted backfill.
- Crash/replay.
- No false gap verification.

Do not mark P0 complete based on tests of the decoder alone.

Verify source → coordinator → persistence → worker composition.

---

# 5. P0 — P24/P25 RECOVERY SCHEDULING AND WORKER CORRECTNESS

Previous changes reportedly introduced:

- Recovery at startup.
- Recovery while the source is idle.
- Serialized recovery processing.
- Bounded batches.
- A thirty-second default cadence.
- Four gaps per batch.

These are useful changes, but they have not received full PostgreSQL/multi-worker acceptance on the latest source.

## 5.1 Verify startup ordering

Test:

1. Persist unresolved gaps.
2. Stop the worker.
3. Start a new worker instance.
4. Verify the persisted gaps are recovered before or alongside normal source processing according to the defined scheduler contract.
5. Ensure startup does not block indefinitely when the provider is unavailable.
6. Ensure startup does not wrongly mark gaps recovered.

## 5.2 Verify idle-source recovery

The worker must not require a new live event to trigger recovery.

Test an idle async source with:

- No new events.
- Existing persisted gaps.
- A new gap persisted by another component after worker startup.
- Repeated recovery intervals.
- Stop/cancellation signals.

Verify that the worker wakes correctly without busy spinning.

## 5.3 Verify recovery fairness

A four-gap batch limit is not enough by itself.

Inspect the selection order.

Prove that:

- A permanently failing gap does not starve all other gaps.
- A high-rate stream does not monopolize the coordinator.
- Older gaps eventually receive bounded attempts.
- Retryable errors respect backoff.
- Terminal failures are not retried endlessly.
- Provider quotas are honored.
- Consecutive timer and event wake-ups cannot create unbounded duplicate scans.

Where necessary, use persisted next-attempt times and fair scheduling.

Avoid introducing excessive configuration.

## 5.4 Multi-worker concurrency

The previous coordinator was serialized within one worker task, but that does not necessarily prevent two separate worker processes from claiming the same persisted gaps.

Inspect existing database claims, indexes, leases and fencing.

Implement minimal database-backed concurrency control if a reproducible race exists.

Test two independent workers sharing the same PostgreSQL database.

Required invariants:

- No conflicting gap transition.
- No lost recovery result.
- No duplicate canonical event.
- No premature VERIFIED.
- No stale worker overwriting newer verification.
- No unbounded provider retry storm.

## 5.5 Cancellation and shutdown

Test cancellation during:

- Provider request.
- Backfill decode.
- Persistence.
- Gap claim.
- Retry sleep.
- Timer wake-up.
- Worker shutdown.

Preserve safe checkpoints and avoid abandoned tasks.

Do not swallow cancellation exceptions or leave leaked background recovery tasks.

---

# 6. P0 — COMPLETE SOURCE-COVERAGE ACCOUNTING

P04/P06 remain incomplete even when individual gaps can be recovered.

Implement independently achievable coverage infrastructure using the existing stream owner.

The system must distinguish:

- Known observed ranges.
- Known unresolved gaps.
- Provider-incomplete ranges.
- Successfully fetched ranges.
- Canonically decoded ranges.
- Verified recovery ranges.
- Unsupported transaction data.
- Unknown total subscription completeness.

Do not create a fake global launch denominator.

Coverage must be bound to:

- Chain.
- Provider.
- Transport.
- Stream ID.
- Program scope.
- Slot/range.
- Provider commitment.
- Verification method.
- Evidence references.

A `VERIFIED` local backfill range must not imply that the full live subscription captured every launch.

## Acceptance

Demonstrate:

- Deterministic coverage-state transitions.
- Bounded recovery.
- Replay idempotency.
- Cross-stream isolation.
- Complete failure classification.
- PostgreSQL durability.
- No false source-completeness claim.

Add the missing provider-backed source verification only when actual supported capabilities make it possible.

Otherwise retain `COVERAGE_UNKNOWN`.

---

# 7. P1 — P07 PAPER WORKER: FINAL-SOURCE POSTGRESQL ACCEPTANCE

The prior execution implemented a disabled-by-default paper worker.

Reported composition:

`EarlyRuntimeService → durable paper_execution outbox → _run_paper_auto → ShadowEntryService → PaperExecutionEngine → SQL Ledger → ExitEngine`

The implementation reportedly requires:

- Explicit typed policy.
- A pre-provisioned matching PAPER/SOL portfolio.
- Exact-unit execution quotes.
- Decimal metadata.
- Transactional exposure caps.
- Restart-safe handoff.
- Persisted-position exit monitoring.

However, the latest final-source PostgreSQL worker-recreation test was not executed.

**Do not mark this task completed merely because 92 focused tests passed.**

## 7.1 Verify exact amount semantics

Inspect all paths using:

- RAW_UNITS.
- DISPLAY_UNITS.
- UNKNOWN units.
- Base-token decimals.
- Quote-token decimals.
- Jupiter quote amounts.
- Entry sizing.
- Exit sizing.
- Fees.
- Slippage.
- Portfolio exposure.

Confirm that:

- Executable paper paths accept only valid raw-unit semantics.
- Synthetic research replay may use explicitly declared display units.
- Conversion is exact.
- No unknown unit is silently accepted.
- Decimal metadata belongs to the correct token mint.
- Rounding is conservative and deterministic.
- Recorded PnL uses consistent units.

## 7.2 Preserve the P07 backtest fix

The previous regression showed synthetic backtest quotes being rejected after raw-unit execution requirements were introduced.

The correction uses:

`paper-fill-v2`

and explicitly marks replay amounts as `DISPLAY_UNITS`.

Verify that this behavior is still intact.

Run research and paper tests against the current source.

Ensure synthetic display-unit replay cannot accidentally be reused as executable paper quote evidence.

## 7.3 PostgreSQL portfolio concurrency

Run tests against real PostgreSQL for:

- Two workers entering the same candidate.
- Two candidates competing for remaining exposure.
- Concurrent position-count limit.
- Failed entry after exposure reservation.
- Transaction rollback.
- Duplicate outbox delivery.
- Worker crash after claim.
- Worker crash after ledger commit.
- Portfolio reconciliation after restart.
- Exit releasing exposure.
- No-fill preserving correct available exposure.

Required invariants:

`reserved_exposure + committed_open_exposure <= configured_max_exposure`

`reserved_positions + open_positions <= configured_max_positions`

Use the existing transaction/locking design.

Do not enforce portfolio caps only with pre-transaction application reads.

## 7.4 Durable entry handoff

Prove that a committed eligible candidate decision is not lost if the process crashes before the paper worker starts.

Test persisted outbox replay, claim expiration and idempotent entry.

Do not create fills from a non-eligible candidate or stale decision.

## 7.5 Durable exit lifecycle

Verify:

- Existing open positions are discovered after restart.
- Exit decisions are idempotent.
- Fresh sell quote is required.
- Quote direction and mint identity match.
- Quote TTL is enforced.
- Unavailable sell route produces NO_FILL or UNKNOWN.
- Realized PnL is not recorded without a valid simulated exit.
- Closed positions cannot be closed twice.
- Portfolio exposure is released exactly once.

## 7.6 Opt-in runtime smoke

Use an isolated test database, fake quote provider, synthetic candidate and explicit test policy.

Provision a matching synthetic PAPER/SOL portfolio within that isolated test environment.

Do not use real funds or authorize trading.

Run the actual worker composition, not only individual service methods.

Verify the full decision → entry → exit → outcome lifecycle.

If Docker or PostgreSQL remains unavailable, preserve the exact blocker and continue all independent testing. Do not claim final-source integration PASS.

---

# 8. P1 — SOLVE POSTGRESQL AND DOCKER ACCEPTANCE BLOCKERS SAFELY

The latest documentation reports:

- The isolated database URL was unavailable.
- Docker API access was denied.
- Earlier PostgreSQL evidence predates some final changes.
- The user session terminated during additional code work.

Determine whether the environment restriction still exists.

Do not assume it does.

Check supported, non-destructive local capabilities.

Use the existing task-owned PostgreSQL resources when safely accessible.

If necessary, discover whether the repository supports a temporary isolated database using available local tools.

Do not modify unknown existing databases or volumes.

Do not disable security isolation to make Docker work.

Do not alter host-wide permissions without authorization.

If PostgreSQL genuinely cannot run:

1. Record the exact failing operation.
2. Preserve its exit code and environment.
3. Complete all provider-independent/unit tests.
4. Prepare exact integration test commands.
5. Identify the minimal environment capability required.
6. Keep PostgreSQL acceptance BLOCKED_ENVIRONMENT.

Never count deselected integration tests as passed integration tests.

---

# 9. P1 — COMPLETE APPLICATION-WORKER RESTART DRILL

The project needs an actual worker lifecycle test, not only a database restart.

Use task-owned isolated resources.

Exercise:

- Stream worker.
- Gap recovery coordinator.
- Social collector.
- Caller-conduct projection.
- Pre-identity reconciler.
- Telegram outbox processor.
- Paper entry worker.
- Paper exit monitor.

Test:

1. Initial worker startup.
2. Known persisted pending work.
3. Bounded processing.
4. Controlled worker termination.
5. Restart with the same database.
6. Idempotent processing.
7. Lease recovery.
8. Pending work continuation.
9. No duplicate logical alerts.
10. No duplicate paper entries.
11. No false gap verification.
12. No lost social cursor.
13. No inconsistent pre-identity diagnostics.
14. No incorrect portfolio exposure.
15. Clean worker shutdown.

Distinguish process restart, database restart and full-stack restart.

Do not terminate unknown host services.

---

# 10. P0 — TELEGRAM DELIVERY AND ELIGIBILITY

Preserve existing typed delivery outcomes and `DELIVERY_UNKNOWN` behavior.

Investigate:

- Definitively unsent.
- Explicit 429.
- Definite rejection.
- Ambiguous send.
- Successful acknowledgement.
- Crash before request.
- Crash after request submission.
- Crash after acknowledgement before persistence.
- Concurrent worker claims.
- Lease expiry.
- Five-minute freshness gate.
- Suppression persistence.

Do not restore blind retries after ambiguous POST outcomes.

Do not fabricate Telegram idempotency guarantees.

Verify that a qualified fresh candidate traverses:

`Candidate → Durable Outbox → Delivery Service → Telegram Adapter → Persisted Result`

Use mocked HTTP and PostgreSQL for local acceptance.

Only send a real Telegram test message when an already authorized test bot and recipient are configured.

Do not send exploratory messages to production recipients.

If no authorized recipient is configured, mark external delivery BLOCKED_EXTERNAL and continue other tasks.

---

# 11. P0/P1 — HISTORICAL DATA AND MISSED-WINNER RECONCILIATION

Inspect:

- Historical Pump.fun source data.
- `reconcile_pumpfun_launches.py`.
- Forward research reports.
- Pre-identity rejection records.
- Stream gaps.
- Candidate decisions.
- Alert statuses.
- Outcome observations.

Preserve original observations.

Use exact program and instruction classification.

Produce versioned corrected cohorts.

Do not retroactively change immutable T0 decisions.

Distinguish:

- Verified launch.
- Foreign program.
- Non-create instruction.
- Missing program.
- Missing instruction.
- Decode failure.
- Provider coverage gap.
- Valid rejected candidate.
- Scoring rejection.
- Alert expiration.
- Successful notification.

A missed-winner count requires an independently defined observable universe and mature outcome evidence.

Do not infer total launches or recall from only recorded candidates.

When authorized historical data is unavailable, complete deterministic tooling and isolated tests but report actual inventory as unperformed.

---

# 12. P1 — SCIENTIFIC 10x–100x VALIDATION INFRASTRUCTURE

The current research result is:

`NOT_PROVEN`

Preserve this classification unless sufficient real independent evidence becomes available.

Complete feasible research infrastructure for:

- Canonical launch cohorts.
- Verified provider coverage.
- Independent setup identity.
- Immutable decision snapshots.
- Point-in-time features.
- Feature availability time.
- Risk and scoring version.
- Telegram alert status.
- Matured outcomes.
- Correct price and quote units.
- Entry/exit executability.
- Censoring.
- Matched baselines.
- Chronological splits.
- Confidence intervals.

Evaluate, when data permits:

- 2x.
- 5x.
- 10x.
- 20x.
- 50x.
- 100x.

Separate:

- Observed mark-price peaks.
- Hypothetical executable return.
- Actual simulated paper outcome.

Do not use synthetic backtest performance as proof of predictive alpha.

Keep caller-conduct features in shadow mode until independent evaluation demonstrates whether they add measurable value.

---

# 13. SECURITY AND RELEASE READINESS

The previous source reports:

- API image: 47 HIGH OS findings.
- Worker image: 47 HIGH OS findings.
- Web image: zero findings in the earlier scan.
- No fixed version for those Python image findings in that scanner feed.
- Eight moderate development-only npm findings in an earlier audit.

These results may no longer match the current image build.

Re-scan if tools and network access permit.

For API/worker vulnerabilities:

1. Extract exact affected packages.
2. Group duplicate shared-base findings.
3. Determine fix availability.
4. Compare compatible supported base images.
5. Evaluate package reachability.
6. Apply safe supported patches.
7. Rebuild images.
8. Re-run relevant tests and scans.
9. Record residual findings.

Do not switch to an image with worse critical vulnerabilities solely to reduce the HIGH count.

Do not hide findings or weaken scanner thresholds.

Maintain the distinction between clean application tests and container security readiness.

Preserve protected execution modes:

`ANALYSIS_ONLY=true`

`PAPER_TRADING=true`

`MANUAL_EXECUTION=false`

`AUTO_EXECUTION=false`

No signing or real-money transaction submission.

---

# 14. FRONTEND AND OPERATIONAL OBSERVABILITY

Verify the latest backend changes are accurately reflected in the operations API and Scan Monitor.

Required observable states:

- Open stream gaps.
- Recovery backlog.
- Verified local recovery ranges.
- Source coverage UNKNOWN.
- Pre-identity failures.
- Reconciled identities.
- Candidate risk and scoring.
- Caller-conduct shadow evidence.
- Telegram pending/delivered/rejected/suppressed/unknown.
- Oldest unknown delivery age.
- Paper worker enabled/disabled.
- Paper entry and exit state.
- Portfolio exposure.
- Data freshness.
- Worker errors and restart state.

Use actual persisted API fields.

Do not show synthetic production data.

Do not display a recovered backfill range as 100% source coverage.

Add frontend/API regression tests only for missing or broken contracts.

Preserve the existing passing responsive layout and hydration behavior.

Run final-source Playwright tests if the browser environment is available.

---

# 15. DOCUMENTATION CONSISTENCY AND ISSUE REGISTER

The uploaded reports contain historical entries and some newer current-state summaries.

After source verification, reconcile them.

Pay particular attention to:

- P07 implementation versus operational activation.
- P08 historical PostgreSQL results versus final-source testing.
- P04 recovery scheduling versus verified source completeness.
- P06 diagnostic/reconciliation implementation versus full observable universe.
- P23 operations visibility.
- P24/P25 recovery work and whether these have canonical issue-register entries.
- Interrupted backfill changes not reflected in final reports.
- Test-count discrepancies: 1,638 versus 1,642 versus any new count.
- Historical source fingerprint versus current source fingerprint.
- Historical browser and container-scan results versus current source.
- Roadmap checkboxes that describe implemented code but not accepted runtime behavior.

Use one authoritative active status per issue.

Preserve older evidence as historical.

Do not delete the history to make reports look consistent.

Update only after code and verification establish the actual state.

---

# 16. RECURSIVE AGENTIC LOOP — EXECUTION RULES

For each issue:

### STEP 1 — INSPECT

Read the current source and all relevant call paths.

### STEP 2 — REPRODUCE

Create a failing test or demonstrate a missing runtime path.

### STEP 3 — TRACE

Identify the complete producer → consumer → persistence boundary.

### STEP 4 — ROOT CAUSE

Separate symptom, triggering condition, code defect, architectural cause and product consequence.

### STEP 5 — FIX

Apply the smallest complete correction.

### STEP 6 — TEST LOCALLY

Run focused unit and contract tests.

### STEP 7 — TEST PERSISTENCE

Use isolated PostgreSQL when required and available.

### STEP 8 — TEST COMPOSITION

Verify the actual worker entry point invokes the intended service.

### STEP 9 — TEST FAILURE

Exercise crash, timeout, retry, replay, concurrency and restart as relevant.

### STEP 10 — SWEEP RELATED CODE

Inspect adjacent paths for the same confirmed assumption or defect.

### STEP 11 — VERIFY BEFORE/AFTER

Record exact failure evidence and corrected behavior.

### STEP 12 — CHECKPOINT

Update the resumable execution ledger.

### STEP 13 — CONTINUE

Move to the next achievable P0/P1 issue.

Do not abandon the mission when one external dependency is unavailable.

Do not repeatedly rewrite audit documents instead of fixing code.

Avoid overengineering, duplicate abstractions and speculative features.

---

# 17. MANDATORY FINAL-SOURCE VERIFICATION

After completing all changes, calculate a new source fingerprint.

Run appropriate checks against that exact source.

## Backend

- Full non-integration pytest.
- Focused Solana decoder/backfill tests.
- Stream integrity tests.
- Early worker pipeline tests.
- Pre-identity reconciliation tests.
- Social/caller tests.
- Telegram delivery tests.
- Paper entry/exit tests.
- Backtest and replay tests.
- Ruff.
- Mypy.

## PostgreSQL

- Migration upgrade.
- Full integration suite.
- Stream worker restart.
- Gap-recovery concurrency.
- Paper worker recreation.
- Portfolio concurrency limits.
- Durable outbox replay.
- Pre-identity transaction rollback.
- Paper exit/ledger consistency.

## Frontend

- Lint.
- Typecheck.
- Unit tests.
- Production build.
- CSS contract.
- Browser E2E.
- Scan Monitor state projections.

## Security

- Secret scan.
- Untracked-file secret scan.
- Local security review.
- SBOM.
- Dependency audits.
- Container vulnerability scan where available.

## Infrastructure

- Compose configuration.
- Safe production configuration validation.
- Worker startup/shutdown.
- Runtime health checks.
- Task-owned restart drill.

Do not claim a test PASS unless it actually executed successfully.

Do not silently convert missing environment support into a successful check.

For every executed gate record:

- Command.
- Exit code.
- Passed.
- Failed.
- Skipped/deselected.
- Warnings.
- Duration.
- Environment.
- Source fingerprint.
- Evidence location.

If final source changes invalidate earlier checks, rerun the affected tests.

---

# 18. ACCEPTANCE MATRIX

Produce a final matrix:

| Capability | Implementation | Unit | PostgreSQL | Composed E2E | Restart | External | Final State |
|---|---|---|---|---|---|---|---|

Include:

1. Canonical launch detection.
2. Solana transaction decoding.
3. Backfill completeness semantics.
4. Stream recovery scheduling.
5. Cross-worker gap isolation.
6. Source coverage.
7. Pre-identity persistence.
8. Pre-identity reconciliation.
9. Social collection.
10. Caller-conduct projection.
11. Risk/scoring.
12. Telegram delivery.
13. Telegram ambiguity.
14. Paper quote units.
15. Portfolio concurrency.
16. Durable paper entry.
17. Paper exit.
18. Paper outcome.
19. PostgreSQL recovery.
20. Full worker restart.
21. Historical reconciliation.
22. Frontend.
23. Container security.
24. Alpha validation.

Use:

- PASS
- PARTIAL
- FAIL
- BLOCKED_ENVIRONMENT
- BLOCKED_EXTERNAL
- NOT_PROVEN

Be explicit about which scope passed.

---

# 19. BEFORE/AFTER AND ROOT-CAUSE REPORT

Provide:

| Issue ID | Before | Root Cause | Modified Files | Fix | Verification | After | Remaining Risk |
|---|---|---|---|---|---|---|---|

Also report:

- Session recovery changes.
- Interrupted backfill resolution.
- P24/P25 recovery acceptance.
- P07 PostgreSQL and restart acceptance.
- New bugs discovered.
- Source coverage changes.
- Telegram pipeline status.
- Paper simulation status.
- Security status.
- Research readiness.

Do not present proposed work as implemented work.

---

# 20. REQUIRED CANONICAL ARTIFACTS

Update existing canonical reports:

- `docs/STATUS.md`
- `docs/ROADMAP.md`
- `docs/PRODUCTION_READINESS.md`
- `docs/ARCHITECTURE.md`
- `docs/audits/PRODUCT_ISSUE_GRID_LATEST.md`
- `docs/audits/PRODUCT_COMPLETION_PLAN.md`
- `docs/audits/ROOT_CAUSE_ANALYSIS.md`
- `docs/audits/BEFORE_AFTER_REPORT.md`
- `docs/audits/MEMERADAR_PRODUCT_ARCHITECTURE.md`
- `docs/audits/FINAL_PRODUCT_READINESS.md`
- `docs/audits/E2E_ACCEPTANCE_REPORT.md`
- `docs/audits/RECURSIVE_ACCEPTANCE_REPORT.md`
- `docs/research/ALPHA_VALIDATION_REPORT.md`

Also update the existing machine-readable verification ledger.

Do not create multiple competing final reports.

Keep historical evidence intact.

Ensure every current claim is bound to the correct source checkpoint.

---

# 21. SESSION INTERRUPTION RESILIENCE

This is especially important because the previous execution ended unexpectedly.

Make the mission resumable without requiring a second full audit.

After every significant milestone:

1. Flush source changes.
2. Finish focused tests.
3. Record their outcomes.
4. Record the current source fingerprint.
5. Update the implementation checkpoint.
6. Record the next task.
7. Preserve exact failure commands.
8. Avoid leaving temporary source edits unexplained.

A resumed agent must be able to determine:

- What was completed.
- What is partially implemented.
- What was tested.
- What remains untested.
- Which files changed.
- What to execute next.

Prefer short, independently verifiable implementation increments.

Do not rely on a long, uncommitted internal reasoning narrative as the only progress record.

---

# 22. PRIORITY ORDER

Execute in this order unless a verified dependency requires adjustment:

**Priority 0 — Recover interrupted changes**

1. Inspect current worktree.
2. Complete Solana backfill changes.
3. Fix any current Ruff/mypy/test regressions.
4. Verify decoder and coordinator contracts.

**Priority 1 — Stream reliability**

5. Verify P24/P25 startup/timer recovery.
6. Add multi-worker PostgreSQL recovery/fencing tests.
7. Complete source-coverage accounting as far as the available provider contracts support.

**Priority 2 — Paper acceptance**

8. Verify P07 quote-unit semantics.
9. Verify transactional portfolio caps.
10. Run PostgreSQL worker-recreation tests.
11. Run synthetic end-to-end paper entry/exit.
12. Complete process restart evidence.

**Priority 3 — User-facing product**

13. Verify discovery-to-Telegram E2E.
14. Validate operations API and Scan Monitor.
15. Fix any confirmed regressions.

**Priority 4 — Research and security**

16. Complete historical reconciliation tooling.
17. Complete available missed-winner research infrastructure.
18. Review unresolved container vulnerabilities.
19. Verify independent cohort/evaluation infrastructure.

**Priority 5 — Final acceptance**

20. Run final-source verification.
21. Update canonical reports.
22. Produce exact Before/After and remaining-blocker matrices.

Do not let unavailable external providers stop the completion of local engineering tasks.

---

# 23. DEFINITION OF DONE

The mission is engineering-complete only when:

- The interrupted source changes have been inspected and correctly finalized.
- No unverified new import or exception path remains.
- Solana decoding and backfill semantics are consistent.
- Recovery does not falsely certify incomplete data.
- P24/P25 recovery is verified at the available integration level.
- P07 paper worker passes relevant final-source tests.
- Exact unit/decimal behavior is correct.
- Portfolio limits are transactionally enforced.
- Durable entry/exit behavior survives restart where test infrastructure permits.
- Telegram local E2E is reliable and truthfully classified.
- Full local verification passes on the final source.
- Current documentation agrees with actual code.
- All achievable P0/P1 defects are closed.
- Remaining external blockers are precisely documented.
- No data or recovery material is destroyed.
- No live-money execution is enabled.

Operational acceptance must remain separate when real providers, credentials or infrastructure are unavailable.

Scientific alpha must remain NOT_PROVEN until independent real evidence is sufficient.

---

# 24. FINAL RESPONSE FORMAT

Return these sections:

## A. Interrupted Session Recovery

What was found in the worktree, what was incomplete, and what was completed?

## B. Executive Outcome

What is now actually operational?

## C. Root-Cause Closure

Which defects were reproduced and fixed?

## D. Before/After Matrix

Show every significant implementation change.

## E. Solana Backfill and Stream Integrity

Explain decode completeness, exception handling, gap verification and recovery.

## F. P24/P25 Recovery Scheduling

Show startup, idle-source, batch, fairness, concurrency and restart evidence.

## G. P07 Paper Acceptance

Show unit correctness, portfolio caps, durable entry/exit and PostgreSQL results.

## H. Telegram Acceptance

Distinguish mock delivery from real Telegram receipt.

## I. Source Coverage and Missed Winners

Report observable denominators and missing coverage.

## J. Research Validation

Report only scientifically justified results.

## K. Security

Show real image findings, fixes and remaining risks.

## L. Test Verification

Exact commands, counts, exit codes and final-source fingerprint.

## M. Final Readiness

Separate engineering, operational and scientific states.

## N. Remaining Blockers

List only genuinely unresolved dependencies, with exact next actions.

## O. Resumable Checkpoint

Provide the saved checkpoint path and the exact continuation point if further external acceptance is required.

---

# FINAL DIRECTIVE

The previous session terminated during active Solana backfill and stream-integrity work.

**Do not restart the audit from zero. Do not blindly trust old acceptance reports. Do not discard uncommitted work.**

First recover and complete the interrupted implementation.

Then verify and close the remaining integration gaps, particularly:

- Solana transaction/backfill decoding and unsupported-data handling.
- Accurate stream-gap recovery and source-completeness semantics.
- P24/P25 startup/timer recovery and multi-worker safety.
- P07 paper-worker PostgreSQL, concurrency and restart acceptance.
- Telegram delivery-state correctness.
- Historical/source-coverage infrastructure.
- Final-source regression testing.
- Documentation and evidence consistency.

Operate continuously:

**RECOVER → REPRODUCE → ROOT CAUSE → FIX → TEST → INTEGRATE → VERIFY → CHECKPOINT → CONTINUE**

Keep all real-money execution disabled.

Preserve all user work and recovery data.

Never fabricate alpha or delivery success.

Never mark a blocked test as passed.

Do not finish with another implementation plan while safely achievable code work remains.

**Deliver the most complete and verifiably correct MemeRadar implementation possible from the actual current worktree, with a durable continuation checkpoint that survives another session interruption.**

BEGIN EXECUTION NOW.
