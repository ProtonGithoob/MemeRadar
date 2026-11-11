# Product completion plan — current checkpoint

| Priority / dependency | Current work and files | Acceptance and verification | Risk / rollback / evidence |
| --- | --- | --- | --- |
| P0 / P01–P02 → P11 | Keep exact Pump.fun program and create-instruction checks; run `scripts/reconcile_pumpfun_launches.py` read-only against a verified history source. | Decoder/forward-report fixtures and isolated PostgreSQL reconciliation pass; production inventory is still blocked because no verified historical database was supplied. | Preserve original rows and decisions; report ambiguous identity as unknown. Evidence: issue grid P01/P02/P11. |
| P0 / P04, P16–P18, P24–P26 → P09 | Preserve canonical decoder, failed-slot diagnostics, scoped gaps, bounded recovery scheduling, fenced recovery claims and unsupported-data semantics; obtain authorized provider coverage evidence. | P30 `make verify` passed: 1,650 backend / 34 integration deselected / 7 warnings; migration graph head 0015. No PostgreSQL run on this source. | Recovery is implemented locally; source coverage remains UNKNOWN. Evidence: P04/P16–P18/P24–P26 and P30 verification ledger. |
| P0 / P03 → P05 | Persisted social calls feed the caller-conduct analyzer, a versioned point-in-time research projection, and the existing feature snapshot in shadow mode. | Focused caller/research tests and P30 `make verify` pass; the 31-test PostgreSQL suite is historical and was not rerun on P30. No dedicated production-weight test exists because the feature is not weighted. | No production score weight is added; live provider availability and real-cohort usefulness remain unaccepted. Evidence: P03/P05. |
| P0 / P06 | Persist the failed-slot gap and its pre-identity diagnostic in one transaction; preserve repeat/merge idempotency and exact late-identity linking. | P30 `make verify` passes locally; 34 PostgreSQL integration tests were deselected. Historical PostgreSQL evidence predates the current migration and was not rerun. | Provider re-fetch, verified source ranges and a complete observable-universe denominator are still missing; unresolved coverage remains UNKNOWN. Evidence: P06/P30. |
| P0 / P09/P20 | Keep durable outbox and pre-send `DELIVERY_UNKNOWN`; retry only proven-not-sent and explicit rate-limit outcomes, and expose unknown age/reasons. | Adapter/service and operations API/UI have local coverage; focused PostgreSQL worker tests (2) and the 31-test integration suite are historical, not P30 acceptance. | Never blindly retry ambiguous sends. Real delivery is blocked without an authorized bot/chat; pre-send crash remains ambiguous. Evidence: P09/P20. |
| P1 / P07–P08/P19 | Opt-in paper consumer composes the durable eligible-decision outbox with existing shadow entry, paper ledger and bounded executable-quote exit monitor. Policy has no implicit bankroll; a matching PAPER/SOL portfolio must already exist. | P30 local `make verify`: 1,650 backend passed / 34 integration deselected, 7 warnings; 86 frontend passed. The 92-test P07-focused suite and 32-test PostgreSQL run are historical, not current-source PostgreSQL acceptance. | Implementation is present but final-source PostgreSQL worker recreation, portfolio concurrency and full process restart remain unaccepted; use explicit test policy and synthetic portfolio only. No signer or transaction submission exists. Evidence: P07/P08/P19 and verification ledger. |
| P1 / P10–P11 | Build independent point-in-time cohorts after identity and source coverage are established; keep decision snapshots immutable and outcomes separately matured. | Replay engineering tests pass; no real independent setup or matured-outcome denominator was measured. | Report `NOT_PROVEN`; never infer alpha from fixtures or mark-price peaks. Evidence: research report. |
| P1 / P12/P22 and operational gates | Preserve dirty worktree and recovery records; retain the task-owned PostgreSQL container. Web runtime image drops npm tooling; API/worker images apply available package updates. | Final `make verify`, external dependency/config review, Trivy image scans, web image startup, migration and browser checks are recorded in E2E acceptance. | API/worker still have 47 HIGH OS findings each with no fixed version in the scanner feed; production Compose needs real variables; no cleanup or volume removal. Evidence: E2E report and STATUS. |

## P30 current-source gate

P30 `make verify` passed against fingerprint `97e36f90571212c774b8827a2672a4f1a3137f5c39cdfaf3c12f4a1f2cbfe6e8` (641 files): 1,650 backend passed / 34 integration deselected / 7 warnings, 86 frontend passed, migration graph head `0015_stream_verification_provenance`. Stream verification rows retain bounded provider/scope/commitment/method/attempt provenance, while global coverage remains UNKNOWN. PostgreSQL integration remains blocked; browser E2E could not bind its local server, and the current build stopped after compilation when Next.js could not capture TypeScript child-process output in the sandbox. See `artifacts/verification/VERIFICATION.md` for exact commands and limits. Older entries below are historical.

## Historical continuation state — 2026-11-09

Social page and provider cursor writes are transactional. Candidate scheduling uses a separate poll marker, including failed attempts, so repeated provider errors do not keep the same candidates at the head of every bounded batch. Provider cursor values remain unchanged on failed attempts. Caller-conduct projection/scoring is still disconnected.

Telegram POST retries are disabled because a timeout can follow a successful external send. The alert is durably marked `DELIVERY_UNKNOWN` before the request; restart/replay does not resend it. This avoids automatic duplicate messages but can leave an alert uncertain when the process stops before sending. The operations API and Scan Monitor expose the unresolved count. Real Telegram delivery remains externally unaccepted.

Pre-identity diagnostics are durable and bounded identity linking is composed beside early discovery. It links only one registry-verified create observation at the as-of cutoff, leaves the original rejection untouched and never verifies slot coverage. A complete observable universe, provider-side retry, retention policy, and atomic gap-plus-diagnostic commit remain open.

The historical inventory is read-only and fixture-verified; it was not run on a verified production history. Paper quote/freshness corrections are tested, but there is still no paper worker. Portfolio sizing defaults are not accepted as operational policy, and no real wallet or signing path is enabled. Independent alpha remains `NOT_PROVEN`.

See the [latest issue grid](PRODUCT_ISSUE_GRID_LATEST.md) and [operational matrix](E2E_ACCEPTANCE_REPORT.md) for acceptance evidence and external blockers.

## Final continuation state — 2026-11-10

The social worker feeds persisted calls through a canonical-identity caller analyzer and a versioned point-in-time projection into the early shadow feature snapshot. It remains unweighted in production. PostgreSQL tests cover the persistence boundaries, but real source timestamps and predictive value require a forward cohort.

Pre-identity diagnostics and their companion failed-slot gaps now commit atomically and remain replayable. The exact-identity reconciler does not claim source coverage. No provider-backed bounded re-fetch or independent observable-universe denominator is available, so missed-winner recall remains unknown.

Telegram HTTP outcomes distinguish proven not-sent, explicit 429, definite rejection and ambiguous delivery. Ambiguous sends remain durable and visible with age/reasons, and are never blindly retried. The 31-test PostgreSQL suite and two focused worker-path cases pass against the task-owned database; no real recipient was contacted. PostgreSQL and Telegram still cannot share an atomic commit, and pre-send crash ambiguity remains.

Paper quote/ledger logic is locally verified, but no durable restart-safe worker consumes eligible decisions, and no exit/outcome loop is composed. P07 remains open until that path exists; missing runtime policy values are an activation gate, not the sole implementation blocker.

### P07 continuation — 2026-11-11

The disabled-by-default paper worker is now composed in `run_worker` when a
complete typed policy is explicitly configured. It consumes the durable
`paper_execution` candidate outbox, requires an already provisioned matching
PAPER/SOL portfolio, writes idempotent entry evaluations, and monitors persisted
open positions using fresh exact-unit Jupiter execution quotes and the existing
ExitEngine/ledger. On this source, focused tests passed (102 passed, 1
database-gated skip), the touched Ruff and strict mypy checks passed, and all 32
PostgreSQL integration tests passed after migration `0013_social_call_asset_index`.
The paper worker was not started against a runtime portfolio/provider; full
worker restart, live quotes and policy activation remain open.

### Final local verification — 2026-11-11

The final `make verify` run found three replay tests failing because synthetic
backtest quotes had UNKNOWN amount units after executable paper quotes began
requiring explicit raw units and mint decimals. `BacktestHarness` now labels
its human-unit quotes as `DISPLAY_UNITS`; `PaperFillModel` preserves Decimal
display quantities for replay, while `PaperExecutionEngine` and
`ShadowEntryService` continue to reject display-unit quotes. The fill model
version is `paper-fill-v2`. TDD regression, focused paper/backtest/worker suite
(92 passed), and full local `make verify` (1,638 backend passed, 33 deselected,
86 frontend passed) succeeded. PostgreSQL, browser E2E and runtime restart were
not rerun against this final source.

The saved-theme hydration regression found no React hydration warning. Current browser suite: 44 passed, 4 skipped. Full `make verify` passed 1,607 backend tests and 86 frontend tests. External dependency/config scanners passed, while separate Trivy image scans found 47 HIGH Debian OS findings in each Python runtime image and none in the web image. The final image/build and remaining external blockers are recorded in [E2E acceptance](E2E_ACCEPTANCE_REPORT.md).
