# MemeRadar deep refactor — current completion checkpoint

Current continuation: 2026-10-18. Everything below the explicit **historical report** marker is superseded evidence from the prior pass. Current verdict: **LOCAL_COMPLETION_IN_PROGRESS**. Git is writable and no longer a blocker; a protected inherited-prerequisite integration decision remains open. Do not confuse a passing mixed worktree with a clean committed checkout.

## Git correction and selective commits

The first normal Git refresh found an empty index lock dated September 26; no Git process was active. A sandbox move then returned `Read-only file system`. The approved host move succeeded and preserved that lock; host index updates and local commits succeeded. Therefore **LOCAL_GIT_WRITABLE** is proven. The old agent generalized a sandbox mount restriction into a repository-wide unrecoverable blocker. Its report does not establish the underlying host was unwritable; current host operations disprove that conclusion. It is not possible to prove the exact old internal reasoning from repository text alone.

No remote operation was performed. Local cached `origin/main` was already 20 commits behind the initial HEAD; compare locally again in the final binding. No remote synchronization is claimed.

Every source commit used an explicitly reviewed cached patch, never `git add .`, `git add -A`, or `git commit -a`. Mechanical projections start from actual HEAD definitions, not whole dirty files: **75 application + 84 API + 27 worker** class/function ASTs were preserved. Nine pure forward helpers were preserved after declared global renames and one local `metric` → `metric_value` collision avoidance. Original application scheduling/worker orchestration functions remained unchanged. The complete staged diffs, names and stats were inspected before each commit. The packaging safety contract is now committed too: it scans all split read modules and preserves every original forbidden-import/mutation/mode assertion. Its focused regression passed. No inherited unrelated hunk, credential or local runtime file was deliberately staged.

| Local commit | Purpose |
| --- | --- |
| `0b88d3107e6f1abc1c779875f920f128dc8664a6` | refactor(application): split existing read contracts by product owner |
| `020b25a368bdc2d2295b534eb161adb0a97dc7e3` | refactor(api): split existing read DTOs and serializers by domain |
| `5fb7ce92101a944f42a6e33160523f6029aace12` | refactor(worker): separate discovery and operations orchestration |
| `63b4650d805207d4a04978ffd6679266a313a1b8` | refactor(reads): migrate internal DTO imports to canonical owners |
| `3ca338dbefe0d4247640b83af7120f6bdf5cb529` | refactor(outcomes): move pure forward policy into application owner |
| `f24bfb745fd9e5284853b1db0695c75d0a7c95c6` | refactor(web): consolidate overview reads and group existing navigation |
| `4b010b88d819eb4420e94b0477771ef72e9a65f4` | chore(repo): narrowly ignore generated reports and operator runtime state |
| `4ada7421e303d1c2cc9a4e7fa0f3f1e1d309ba3b` | docs(repo): preserve historical visual evidence in verified archive |
| `82e9b7b821d0f9f639745ad70544906229ca3541` | refactor(imports): migrate remaining control and acceptance aliases |
| `d7bb1047ded2ac2505f7c1fa128b95c8eb45468e` | docs(repo): reconcile Git state, ownership audits and verification boundaries |
| `26e0765a37f0ce2533cbc08330f6ac3d375a9ead` | test(reads): check all split modules in packaging safety contract |

This is the ledger before the documentation checkpoint containing this report. The [final binding](../../artifacts/verification/memeradar-completion-loop-2026-10-18.json) records the complete commit count/list, literal final HEAD and final source identity, avoiding an impossible self-referential commit SHA inside its own content.

## Protected remaining integration boundary

The inherited worktree contains feature predecessors absent HEAD. For example, historical HEAD had a 2,213-line API read module; the prior refactor worked on a 4,229-line inherited module. The Outcomes page itself and extended forward/timeline models are absent historical HEAD. A small task hunk inside an untracked inherited component has no predecessor in Git to which that hunk alone can apply. Importing its full component/query/DTO/persistence prerequisites would also commit inherited feature work. A dependency alone does not establish task ownership of every predecessor hunk.

The safe HEAD-only relocations are committed; the dependent full-worktree refactor/coverage changes remain preserved and tested. The operator was asked to choose whether separately reviewed inherited prerequisites may enter history. A general continuation is not treated as permission to stage unrelated features. No blanket staging, alternative Git database, reset, clean, stash, force push or hidden prerequisite commit was used.

Reviewable [remaining backend dependency diff](../../artifacts/verification/memeradar-pending-backend.patch) and [Outcomes/UI dependency diff](../../artifacts/verification/memeradar-pending-outcome-ui.patch) are **review artifacts containing inherited prerequisites**, not authorized staging patches. The current scanner/serializer/control import migrations include a services.py hunk whose untracked predecessor is intentionally still uncommitted. This is a scope/ownership boundary from the user's Phase 2 protection, not an external-runtime or Git blocker. Completion of all requested commits is **not claimed**.

## Bounded audits and design decisions

- [518-path ledger](memeradar-remaining-path-audit.md): 516 concrete purpose classes, two protected UNKNOWN-type operator files; all 518 have disposition. 457 KEEP + 61 EXTERNAL_OWNED; zero unassigned disposition; zero source proven unused/deleted. The five new current paths were classified separately, not backdated into the old 518.
- Archive: all **1,508** members and **16** retained copies independently match size/SHA; **1,492** originals were already archived by the prior pass and are now durably represented in Git. No new unique bytes or generated files deleted. Sixteen indexes are eight intentional machine/human pairs (338,478 bytes); absence of a direct literal link does not make those historical pairs disposable. Restore from repository root with `tar -xzf docs/history/visual-evidence-2026-10-18.tar.gz -C .`.
- Archive commit safety: all tar members plus 1,761 files in 32 nested ZIPs inspected; 1,226 text entries / 250,142,317 text bytes, 676 JSON documents and 22,429 JSONL/trace records checked with repository secret scanner and structured header/cookie/credential checks. Zero findings, exemptions or scan failures. Binary image OCR was not performed. Archive SHA remains `b1591a7b1c77f4e7cb12ec611842e45857424cadb312854a0c7c12ea670dc02d`.
- Application `read_api.py`: **2,630 → 1,495 lines in the full worktree**. Eight unchanged token timeline/cursor/recovery/reputation helpers (1,121 implementation lines) move into existing `read_tokens.py`. Remaining ReadQueryPort, bounded in-memory orchestration and intent/relay query glue remain cohesive. The timeline move depends on inherited models absent HEAD and remains in the protected dependency diff.
- Worker `forward_evidence.py`: **2,097 → 2,073 lines in the full worktree** through import cleanup plus retained `_flag` alias; the nine pure policy helpers were previously extracted and are now committed for HEAD-owned behavior. Remaining code is one I/O owner: load normalized persisted rows, collect bounded market evidence and persist research outcomes. No further split by size is justified.
- Compatibility: **328** aliases (application 122, API 152, worker main 45, forward helpers 9). Final static reference scan includes relative imports and module.attribute uses, catching control.py, services.py and the acceptance script. 24 remaining internal consumer files under that definition; production files are none, with script/test scope recorded in the ledger below. Four production modules still import nine **facade-owned** port/service/query bindings; these are canonical facade responsibility rather than relocated aliases. External/dynamic consumers remain UNKNOWN; no alias removed.
- Four navigation groups are Discover / Investigate / Validate / Operate. All 22 full-worktree routes and deep links retained. The committed navigation projection retains all 13 historical HEAD destinations without importing inherited new routes. No new demotion, merge, redirect or removal. Research/detail surfaces have distinct scopes, so no speculative route consolidation.
- Same-render fetch proof: RootLayout and Home/Operations each request the same no-argument overview. The existing shared React request cache is now committed for historical HEAD behavior. Repeated gateway names on terminal sibling pages are not same-render duplicates; token detail's two outcome reads differ by missed-only filter. No additional duplicate found or removed. No process-wide/global cache added. [React cache documentation](https://react.dev/reference/react/cache) confirms per-server-request invalidation; focused tests confirm outside-render calls remain independent, not actual browser request counts.
- Current docs corrected: README's six-group map and paid-provider prerequisite wording; ARCHITECTURE's stale provider-health catalog/browser-mutation text and read owners; SECURITY's historical read-only browser language and Vitest 3.2.7 exception (current lock 5.0.2). Guarded user-Admin Settings writes remain as implemented. No fresh external vulnerability scan inferred from a version check.

## Outcome coverage contract

Coverage stays **LOADED_PAGE**. Existing SQL pushes identity/filter/as-of/cursor predicates then reads at most `limit + 1` raw rows; limit is at most 100. Coverage consumes only valid returned `page.items`. The port exposes no aggregate, population cap/completeness marker or lower time bound. Two arbitrarily different older populations can yield the same first page. Exact all-filter COUNT/DISTINCT still permits unbounded database work and would count malformed raw JSON differently from the existing validator unless another contract were introduced. Repeated pagination is also unbounded. A capped partial aggregate would need new explicit cap/truncation/invalid-row semantics; it is not an honest full-population result and was not added.

The full-worktree UI now explicitly shows **PAGE COVERAGE** and **POPULATION COVERAGE UNAVAILABLE**, with the bounded-page reason. No client recount, new persistence/query/metric engine or inferred independent samples. Unknown identity/maturity, mixed partial maturity and per-horizon counts remain backend-owned. `independence_state=NOT_ESTABLISHED` throughout. The copy-only UI patch remains dependent on its inherited untracked predecessor.

## Validation and limitations

Focused full-worktree backend: **221 PASS**, scoped mypy **205 files PASS**, Ruff PASS; later final-import checks and helper regression results are recorded in verification logs. Frontend focused **78 PASS**; TypeScript/ESLint PASS. Committed-snapshot focused checks: reads25 PASS, canonical-import reads30 PASS, worker7 PASS, web23 PASS, helper contracts4 PASS / isolated PG1 skip. Independent review found a stale integration fixture monkeypatch target; it is corrected in commit3ca338d. No remaining Critical/Important finding was reported for the reviewed range. Minor retained observations: worker snapshot docstrings say read contracts, and logger ownership changed to operations_jobs without a repository logger-name filter.

A committed-snapshot SQLite collector fixture already failed in original historical HEAD: naive observed_at/row_time is rejected by ensure_utc. The broader inherited worktree contains additional UTC persistence behavior and passes its collector tests. A scratch-only lazy-fallback experiment exposed the deeper unchanged row_time dependency; no partial persistence fix or unrelated feature prerequisite was committed. **A green full-worktree check is not evidence of a wholly green clean HEAD checkout.**

The first aggregate continuation stopped at36% when the execution turn was interrupted; it produced no exit result and is neither PASS nor FAIL. One fresh complete final aggregate, production build, budgets, migration graph and identity binding are run after source slices. The [binding](../../artifacts/verification/memeradar-completion-loop-2026-10-18.json) is authoritative for actual exit codes/results; no historical test total is substituted. Verification outputs remain ignored artifacts, not committed runtime files. Source identity includes HEAD; final identity is recorded after documentation commits and compared using the same scoped file-content manifest to prevent hidden source drift.

No protected mode, score arithmetic/threshold, provider authority, immutable T0 or no-lookahead semantics changed. No new provider, chain, score, execution capability, persistence owner or migration.

## All 40 requested answers

| # | Answer |
| ---: | --- |
| 1 | YES: local Git is writable through approved host operations; commits are real. |
| 2 | Prior report overgeneralized the sandbox read-only mount and treated a stale observation as a project-wide blocker; historical internal reasoning is not fully recoverable. |
| 3 | 11 source/archive/hygiene commits before this documentation checkpoint; exact final count in binding. |
| 4 | Full SHA/purpose ledger above and final binding. |
| 5 | No inherited unrelated hunk deliberately staged; HEAD-only AST reconstruction protected mixed files. Dependent prerequisites remain unstaged. |
| 6 | Literal final HEAD in binding (`finalHead`). |
| 7 | Literal final source identity in binding (`finalSourceIdentity`); it is distinct from commit SHA and includes HEAD salt. |
| 8 | 516 purpose-typed; all518 sufficiently audited for explicit disposition. |
| 9 | 2 UNKNOWN in file type, both protected EXTERNAL_OWNED;0 unassigned dispositions. |
| 10 | 0 source files proved unused. |
| 11 | 0 unused source files deleted; old API path is relocation. |
| 12 | 1,492 historical originals previously archived;1,508 preserved members;16 retained indexes. No additional originals removed this continuation. |
| 13 | 0 generated files removed; seven narrow future-noise/operator-state ignores. |
| 14 | 328 explicit relocated-symbol aliases in the current worktree. |
| 15 | Final static consumer count/scope above and per-alias ledger below; all external/dynamic consumers UNKNOWN. Facade-owned contracts/glue are separate. |
| 16 | YES in full worktree: eight timeline helpers moved; facade2,630→1,495. Protected inherited prerequisites prevent standalone staging of that additional move. |
| 17 | Pure policy extraction now committed for existing HEAD behavior; remaining worker stays one I/O owner. |
| 18 | Facade retains query-port/catalog composition; worker retains persisted collection orchestration. Further size-only splitting has no distinct owner. |
| 19 | No additional same-render duplicate found in round2. |
| 20 | Existing overview layout/page duplication is consolidated via shared request cache, now committed. |
| 21 | YES: Discover / Investigate / Validate / Operate. |
| 22 | No new route demotion this continuation. |
| 23 | No routes removed/redirected/merged;22 full-worktree routes remain. |
| 24 | YES: LOADED_PAGE only. |
| 25 | No bounded population/cap/completeness contract; exact aggregation/iteration is unbounded and raw-count validation differs. |
| 26 | Not added. Page uses current filters, as-of, cursor and at most100 valid rows; independence NOT_ESTABLISHED. |
| 27 | Scoring semantics unchanged. |
| 28 | Safety/auth/secret/mode semantics unchanged. |
| 29 | Provider authority unchanged. |
| 30 | No-lookahead and immutable T0 unchanged. |
| 31 | Actual final make verify exit/results in binding; interrupted attempt is not acceptance. |
| 32 | Actual final production-build exit/results in binding. |
| 33 | Actual final route-budget exit/results in binding. |
| 34 | Existing0022_cross_chain_evidence /40 tables; final migration check in binding. |
| 35 | Current Docker available, but prior PostgreSQL container no longer visible after runtime reset; isolated target unset: NEEDS_DATABASE_RUNTIME. No substitute DB created. |
| 36 | Host Chrome launch PASS; final-source credentialed browser acceptance unverified. |
| 37 | Provider acceptance unverified; no fabricated evidence. |
| 38 | READ_ONLY_SHADOW_READY = NOT ACCEPTED. |
| 39 | ALPHA_VALIDATED = NO; REAL_WORLD_ALPHA_NOT_YET_PROVEN; PRODUCTION_READY=false. |
| 40 | LOCAL_COMPLETION_IN_PROGRESS: safe slices committed; protected inherited prerequisite integration remains unresolved. |

## Per-alias compatibility ledger

This is a current-worktree static ledger, including tests and facade glue. Each row's external consumers remain UNKNOWN. Removal requires zero runtime/API/DI/worker/CLI/MCP/test/replay/serialization/documentation consumers and a compatibility policy explicitly permitting removal. Zero static consumers alone does not permit deletion.

| Legacy symbol | Canonical symbol | Internal static consumers | Facade references | External/unknown |
| --- | --- | --- | ---: | --- |
| `memeradar_application.read_api.CallerConvergenceQuery` | `memeradar_application.read_callers.CallerConvergenceQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.CallerConvergenceView` | `memeradar_application.read_callers.CallerConvergenceView` | `tests/contract/test_alpha_caller_read_api.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.CallerProfileQuery` | `memeradar_application.read_callers.CallerProfileQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.CallerProfileView` | `memeradar_application.read_callers.CallerProfileView` | `tests/contract/test_alpha_caller_read_api.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.SocialCallQuery` | `memeradar_application.read_callers.SocialCallQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.SocialCallView` | `memeradar_application.read_callers.SocialCallView` | `tests/unit/test_read_api_routes.py`; `tests/contract/test_alpha_caller_read_api.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.caller_convergence_view` | `memeradar_application.read_callers.caller_convergence_view` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.caller_profile_view` | `memeradar_application.read_callers.caller_profile_view` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.social_call_view` | `memeradar_application.read_callers.social_call_view` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.CandidateQuery` | `memeradar_application.read_candidates.CandidateQuery` | `tests/unit/test_read_api.py`; `tests/integration/test_read_query_service.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.CandidateStateSummaryView` | `memeradar_application.read_candidates.CandidateStateSummaryView` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.CandidateView` | `memeradar_application.read_candidates.CandidateView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/contract/test_phase7_sprint7_2.py` | 7 | UNKNOWN; retain |
| `memeradar_application.read_api.EarlyRadarQuery` | `memeradar_application.read_candidates.EarlyRadarQuery` | `tests/unit/test_early_read_projection.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.EarlyRadarView` | `memeradar_application.read_candidates.EarlyRadarView` | `tests/unit/test_early_read_projection.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.PoolView` | `memeradar_application.read_candidates.PoolView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._CONTROL` | `memeradar_application.read_common._CONTROL` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._CURSOR_TOKEN` | `memeradar_application.read_common._CURSOR_TOKEN` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._ERROR_CLASS` | `memeradar_application.read_common._ERROR_CLASS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._SAFETY_THRESHOLD_RULES` | `memeradar_application.read_common._SAFETY_THRESHOLD_RULES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._SECRET_KEY` | `memeradar_application.read_common._SECRET_KEY` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._SECRET_VALUE` | `memeradar_application.read_common._SECRET_VALUE` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._STAGE_DISPOSITIONS` | `memeradar_application.read_common._STAGE_DISPOSITIONS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._STREAM_ERROR_CLASS` | `memeradar_application.read_common._STREAM_ERROR_CLASS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.DEFAULT_PAGE_LIMIT` | `memeradar_application.read_common.DEFAULT_PAGE_LIMIT` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.FORWARD_OUTCOME_HORIZONS` | `memeradar_application.read_common.FORWARD_OUTCOME_HORIZONS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.FORWARD_OUTCOME_TARGETS` | `memeradar_application.read_common.FORWARD_OUTCOME_TARGETS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_CREATOR_HISTORY_MINTS` | `memeradar_application.read_common.MAX_CREATOR_HISTORY_MINTS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_CURSOR_LENGTH` | `memeradar_application.read_common.MAX_CURSOR_LENGTH` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_PAGE_LIMIT` | `memeradar_application.read_common.MAX_PAGE_LIMIT` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_QUERY_WINDOW` | `memeradar_application.read_common.MAX_QUERY_WINDOW` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_STAGE_FUNNEL_ROWS` | `memeradar_application.read_common.MAX_STAGE_FUNNEL_ROWS` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_TOKEN_SIMILARITIES` | `memeradar_application.read_common.MAX_TOKEN_SIMILARITIES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.MAX_WALLET_ROLE_EVIDENCE` | `memeradar_application.read_common.MAX_WALLET_ROLE_EVIDENCE` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.READ_API_VERSION` | `memeradar_application.read_common.READ_API_VERSION` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WALLET_SIGNATURE_REQUEST_FAILURE_CODES` | `memeradar_application.read_common.WALLET_SIGNATURE_REQUEST_FAILURE_CODES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WALLET_TRANSACTION_CLASSIFICATIONS` | `memeradar_application.read_common.WALLET_TRANSACTION_CLASSIFICATIONS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.CursorCodec` | `memeradar_application.read_common.CursorCodec` | `tests/unit/test_read_api.py` | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.CursorError` | `memeradar_application.read_common.CursorError` | `tests/unit/test_read_api.py` | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.Page` | `memeradar_application.read_common.Page` | `tests/unit/test_read_api_routes.py` | 31 | UNKNOWN; retain |
| `memeradar_application.read_api.ProvenanceView` | `memeradar_application.read_common.ProvenanceView` | `tests/unit/test_read_api_routes.py`; `tests/contract/test_alpha_caller_read_api.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.T` | `memeradar_application.read_common.T` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.TimelineHistoryCoverage` | `memeradar_application.read_common.TimelineHistoryCoverage` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.TimelineSourceContinuation` | `memeradar_application.read_common.TimelineSourceContinuation` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletHistoryCursorState` | `memeradar_application.read_common.WalletHistoryCursorState` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletSignatureRequestFailureCode` | `memeradar_application.read_common.WalletSignatureRequestFailureCode` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletTransactionClassification` | `memeradar_application.read_common.WalletTransactionClassification` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._bounded_limit` | `memeradar_application.read_common._bounded_limit` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_cursor` | `memeradar_application.read_common._optional_cursor` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_decimal` | `memeradar_application.read_common._optional_decimal` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_nonnegative_decimal` | `memeradar_application.read_common._optional_nonnegative_decimal` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_nonnegative_int` | `memeradar_application.read_common._optional_nonnegative_int` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_quality` | `memeradar_application.read_common._optional_quality` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._optional_text` | `memeradar_application.read_common._optional_text` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._page` | `memeradar_application.read_common._page` | 0 | 13 | UNKNOWN; retain |
| `memeradar_application.read_api._provenance_views` | `memeradar_application.read_common._provenance_views` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._safe_text` | `memeradar_application.read_common._safe_text` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._safe_value` | `memeradar_application.read_common._safe_value` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._time_range` | `memeradar_application.read_common._time_range` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.safe_read_payload` | `memeradar_application.read_common.safe_read_payload` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.AuditEventView` | `memeradar_application.read_operations.AuditEventView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api.AuditQuery` | `memeradar_application.read_operations.AuditQuery` | `tests/integration/test_control_plane_postgres.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api.ConfigQuery` | `memeradar_application.read_operations.ConfigQuery` | `tests/integration/test_control_plane_postgres.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api.ConfigVersionView` | `memeradar_application.read_operations.ConfigVersionView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/contract/test_phase7_sprint7_2.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api.ProviderHealthQuery` | `memeradar_application.read_operations.ProviderHealthQuery` | `tests/unit/test_read_api.py`; `tests/integration/test_madeonsol_readiness_postgres.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.ProviderHealthView` | `memeradar_application.read_operations.ProviderHealthView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/contract/test_phase7_sprint7_2.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api.ReadProviderHealthState` | `memeradar_application.read_operations.ReadProviderHealthState` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/contract/test_phase7_sprint7_2.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.ServiceConflictView` | `memeradar_application.read_operations.ServiceConflictView` | 0 | 6 | UNKNOWN; retain |
| `memeradar_application.read_api.StreamSubscriptionHealthView` | `memeradar_application.read_operations.StreamSubscriptionHealthView` | `tests/unit/test_read_api_routes.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.service_conflict_view` | `memeradar_application.read_operations.service_conflict_view` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.ForwardOutcomeQuery` | `memeradar_application.read_outcomes.ForwardOutcomeQuery` | `tests/unit/test_read_persistence.py`; `tests/integration/test_dex_candidate_forward_outcomes_postgres.py` | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.ForwardOutcomeView` | `memeradar_application.read_outcomes.ForwardOutcomeView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py` | 4 | UNKNOWN; retain |
| `memeradar_application.read_api._forward_outcome_cursor` | `memeradar_application.read_outcomes._forward_outcome_cursor` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.ClosedTradeExplanationView` | `memeradar_application.read_positions.ClosedTradeExplanationView` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionEntryEvidenceView` | `memeradar_application.read_positions.PositionEntryEvidenceView` | `tests/unit/test_position_read.py`; `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionExitRiskView` | `memeradar_application.read_positions.PositionExitRiskView` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionMarkView` | `memeradar_application.read_positions.PositionMarkView` | `tests/unit/test_position_read.py`; `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionPerformanceView` | `memeradar_application.read_positions.PositionPerformanceView` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionQuery` | `memeradar_application.read_positions.PositionQuery` | `tests/unit/test_position_read.py`; `tests/integration/test_position_read_postgres.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.PositionView` | `memeradar_application.read_positions.PositionView` | 0 | 7 | UNKNOWN; retain |
| `memeradar_application.read_api._closed_trade_view` | `memeradar_application.read_positions._closed_trade_view` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._exit_risk_view` | `memeradar_application.read_positions._exit_risk_view` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._position_evidence_refs` | `memeradar_application.read_positions._position_evidence_refs` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._position_reasons` | `memeradar_application.read_positions._position_reasons` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.build_position_view` | `memeradar_application.read_positions.build_position_view` | `tests/unit/test_position_read.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.ChainOpportunityQuery` | `memeradar_application.read_research.ChainOpportunityQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.StageDispositionFunnelQuery` | `memeradar_application.read_research.StageDispositionFunnelQuery` | `tests/unit/test_lifecycle_funnel.py`; `tests/unit/test_read_persistence.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.StageDispositionFunnelStage` | `memeradar_application.read_research.StageDispositionFunnelStage` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.StageDispositionFunnelView` | `memeradar_application.read_research.StageDispositionFunnelView` | 0 | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.StageDispositionQuery` | `memeradar_application.read_research.StageDispositionQuery` | `tests/unit/test_lifecycle_funnel.py`; `tests/unit/test_read_persistence.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api._stage_disposition_cursor` | `memeradar_application.read_research._stage_disposition_cursor` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.build_stage_disposition_funnel` | `memeradar_application.read_research.build_stage_disposition_funnel` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.stage_disposition_parts` | `memeradar_application.read_research.stage_disposition_parts` | 0 | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.stage_disposition_window` | `memeradar_application.read_research.stage_disposition_window` | 0 | 2 | UNKNOWN; retain |
| `memeradar_application.read_api.TimelineEntryView` | `memeradar_application.read_tokens.TimelineEntryView` | `tests/unit/test_lifecycle_funnel.py`; `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/contract/test_phase7_sprint7_2.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.TimelineQuery` | `memeradar_application.read_tokens.TimelineQuery` | `tests/unit/test_read_api.py`; `tests/unit/test_read_persistence.py`; `tests/integration/test_persistence_postgres.py`; `tests/integration/test_early_runtime_persistence.py`; `tests/integration/test_read_query_service.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.TokenSimilarityEvidenceView` | `memeradar_application.read_tokens.TokenSimilarityEvidenceView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.TokenView` | `memeradar_application.read_tokens.TokenView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/unit/test_search_api.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api._condition_value` | `memeradar_application.read_tokens._condition_value` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._system_miss_evidence` | `memeradar_application.read_tokens._system_miss_evidence` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._timeline_cursor` | `memeradar_application.read_tokens._timeline_cursor` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api._timeline_query_binding` | `memeradar_application.read_tokens._timeline_query_binding` | 0 | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.encode_timeline_cursor` | `memeradar_application.read_tokens.encode_timeline_cursor` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.project_timeline_condition_recovery` | `memeradar_application.read_tokens.project_timeline_condition_recovery` | `tests/unit/test_read_api.py` | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.project_timeline_wallet_reputation_at_decision` | `memeradar_application.read_tokens.project_timeline_wallet_reputation_at_decision` | 0 | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.timeline_cursor_position` | `memeradar_application.read_tokens.timeline_cursor_position` | `tests/unit/test_read_api.py` | 1 | UNKNOWN; retain |
| `memeradar_application.read_api.ClusterGraphQuery` | `memeradar_application.read_wallets.ClusterGraphQuery` | `tests/integration/test_operator_memory_graph_projection.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.CreatorReputationView` | `memeradar_application.read_wallets.CreatorReputationView` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.ShortestPathQuery` | `memeradar_application.read_wallets.ShortestPathQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.TokenGraphQuery` | `memeradar_application.read_wallets.TokenGraphQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletActivityView` | `memeradar_application.read_wallets.WalletActivityView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletCandidateQuery` | `memeradar_application.read_wallets.WalletCandidateQuery` | 0 | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletCandidateView` | `memeradar_application.read_wallets.WalletCandidateView` | `tests/unit/test_read_api_routes.py` | 5 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletCreatorTransferView` | `memeradar_application.read_wallets.WalletCreatorTransferView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletDecisionEvidenceView` | `memeradar_application.read_wallets.WalletDecisionEvidenceView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletGraphQuery` | `memeradar_application.read_wallets.WalletGraphQuery` | `tests/unit/test_read_persistence.py`; `tests/unit/test_wallet_relationship.py`; `tests/integration/test_operator_memory_graph_projection.py`; `tests/integration/test_read_query_service.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletGraphView` | `memeradar_application.read_wallets.WalletGraphView` | `tests/unit/test_read_api_routes.py` | 9 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletHistoryCoverageView` | `memeradar_application.read_wallets.WalletHistoryCoverageView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletQuery` | `memeradar_application.read_wallets.WalletQuery` | `tests/unit/test_read_api.py` | 3 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletRealizedOutcomeView` | `memeradar_application.read_wallets.WalletRealizedOutcomeView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletReputationSnapshotView` | `memeradar_application.read_wallets.WalletReputationSnapshotView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletRoleEvidenceView` | `memeradar_application.read_wallets.WalletRoleEvidenceView` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_application.read_api.WalletView` | `memeradar_application.read_wallets.WalletView` | `tests/unit/test_read_api.py`; `tests/unit/test_read_api_routes.py`; `tests/unit/test_read_persistence.py`; `tests/unit/test_wallet_history_worker.py`; `tests/unit/test_search_api.py`; `tests/unit/test_bounded_read_extensions.py` | 7 | UNKNOWN; retain |
| `memeradar_api.read.CallerConvergenceQueryParams` | `memeradar_api.read.callers.CallerConvergenceQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.CallerConvergenceResponse` | `memeradar_api.read.callers.CallerConvergenceResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.CallerProfileQueryParams` | `memeradar_api.read.callers.CallerProfileQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.CallerProfileResponse` | `memeradar_api.read.callers.CallerProfileResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.SocialCallQueryParams` | `memeradar_api.read.callers.SocialCallQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.SocialCallResponse` | `memeradar_api.read.callers.SocialCallResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.SocialClaimResponse` | `memeradar_api.read.callers.SocialClaimResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._caller_convergence_response` | `memeradar_api.read.callers._caller_convergence_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._caller_profile_response` | `memeradar_api.read.callers._caller_profile_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._social_call_response` | `memeradar_api.read.callers._social_call_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read.AsymmetricAlphaProjectionResponse` | `memeradar_api.read.candidates.AsymmetricAlphaProjectionResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.CandidateQueryParams` | `memeradar_api.read.candidates.CandidateQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.CandidateResponse` | `memeradar_api.read.candidates.CandidateResponse` | 0 | 4 | UNKNOWN; retain |
| `memeradar_api.read.CandidateStateSummaryResponse` | `memeradar_api.read.candidates.CandidateStateSummaryResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.EarlyRadarQueryParams` | `memeradar_api.read.candidates.EarlyRadarQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.EarlyRadarResponse` | `memeradar_api.read.candidates.EarlyRadarResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.PoolResponse` | `memeradar_api.read.candidates.PoolResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._candidate_response` | `memeradar_api.read.candidates._candidate_response` | `tests/unit/test_read_api_routes.py` | 2 | UNKNOWN; retain |
| `memeradar_api.read._candidate_state_summary_response` | `memeradar_api.read.candidates._candidate_state_summary_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._early_radar_response` | `memeradar_api.read.candidates._early_radar_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._pool_response` | `memeradar_api.read.candidates._pool_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._MAX_PUBLIC_EVIDENCE_REFS` | `memeradar_api.read.common._MAX_PUBLIC_EVIDENCE_REFS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._PUBLIC_EVIDENCE_REFERENCE_KINDS` | `memeradar_api.read.common._PUBLIC_EVIDENCE_REFERENCE_KINDS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._RISK_DISPOSITIONS` | `memeradar_api.read.common._RISK_DISPOSITIONS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._SOURCE_REFERENCE_WITHHELD` | `memeradar_api.read.common._SOURCE_REFERENCE_WITHHELD` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.BuildT` | `memeradar_api.read.common.BuildT` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.PageResponse` | `memeradar_api.read.common.PageResponse` | 0 | 28 | UNKNOWN; retain |
| `memeradar_api.read.ProvenanceResponse` | `memeradar_api.read.common.ProvenanceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ResponseT` | `memeradar_api.read.common.ResponseT` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.SourceT` | `memeradar_api.read.common.SourceT` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._mapping` | `memeradar_api.read.common._mapping` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._materialize` | `memeradar_api.read.common._materialize` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._optional_mapping_decimal` | `memeradar_api.read.common._optional_mapping_decimal` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._page_response` | `memeradar_api.read.common._page_response` | 0 | 14 | UNKNOWN; retain |
| `memeradar_api.read._provenance_response` | `memeradar_api.read.common._provenance_response` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_api.read._public_evidence_mapping` | `memeradar_api.read.common._public_evidence_mapping` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._public_evidence_refs` | `memeradar_api.read.common._public_evidence_refs` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._public_evidence_value` | `memeradar_api.read.common._public_evidence_value` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._StrictModel` | `memeradar_api.read.common._StrictModel` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._SEARCH_KINDS` | `memeradar_api.read.operations._SEARCH_KINDS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.AuditEventResponse` | `memeradar_api.read.operations.AuditEventResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.AuditQueryParams` | `memeradar_api.read.operations.AuditQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ConfigQueryParams` | `memeradar_api.read.operations.ConfigQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ConfigVersionResponse` | `memeradar_api.read.operations.ConfigVersionResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.PendingTradeIntentEventResponse` | `memeradar_api.read.operations.PendingTradeIntentEventResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PendingTradeIntentHistoryQueryParams` | `memeradar_api.read.operations.PendingTradeIntentHistoryQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.PendingTradeIntentHistoryResponse` | `memeradar_api.read.operations.PendingTradeIntentHistoryResponse` | 0 | 3 | UNKNOWN; retain |
| `memeradar_api.read.ProviderHealthQueryParams` | `memeradar_api.read.operations.ProviderHealthQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ProviderHealthResponse` | `memeradar_api.read.operations.ProviderHealthResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.RelayLegEvidenceResponse` | `memeradar_api.read.operations.RelayLegEvidenceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.RelayLegHistoryQueryParams` | `memeradar_api.read.operations.RelayLegHistoryQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.RelayLegHistoryResponse` | `memeradar_api.read.operations.RelayLegHistoryResponse` | 0 | 3 | UNKNOWN; retain |
| `memeradar_api.read.SearchResolveResponse` | `memeradar_api.read.operations.SearchResolveResponse` | 0 | 13 | UNKNOWN; retain |
| `memeradar_api.read.ServiceConflictResponse` | `memeradar_api.read.operations.ServiceConflictResponse` | 0 | 4 | UNKNOWN; retain |
| `memeradar_api.read.StreamSubscriptionHealthResponse` | `memeradar_api.read.operations.StreamSubscriptionHealthResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read._audit_response` | `memeradar_api.read.operations._audit_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._config_response` | `memeradar_api.read.operations._config_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._pending_trade_intent_event_response` | `memeradar_api.read.operations._pending_trade_intent_event_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._provider_health_response` | `memeradar_api.read.operations._provider_health_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._relay_leg_evidence_response` | `memeradar_api.read.operations._relay_leg_evidence_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._service_conflict_response` | `memeradar_api.read.operations._service_conflict_response` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read._stream_subscription_response` | `memeradar_api.read.operations._stream_subscription_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._POSITION_MODES` | `memeradar_api.read.outcomes._POSITION_MODES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._POSITION_STATES` | `memeradar_api.read.outcomes._POSITION_STATES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ClosedTradeExplanationResponse` | `memeradar_api.read.outcomes.ClosedTradeExplanationResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ForwardOutcomeQueryParams` | `memeradar_api.read.outcomes.ForwardOutcomeQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ForwardOutcomeResponse` | `memeradar_api.read.outcomes.ForwardOutcomeResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.OpportunityEligibilityResponse` | `memeradar_api.read.outcomes.OpportunityEligibilityResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.OpportunityPolicyBindingResponse` | `memeradar_api.read.outcomes.OpportunityPolicyBindingResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PositionEntryEvidenceResponse` | `memeradar_api.read.outcomes.PositionEntryEvidenceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PositionExitRiskResponse` | `memeradar_api.read.outcomes.PositionExitRiskResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PositionMarkResponse` | `memeradar_api.read.outcomes.PositionMarkResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PositionPerformanceResponse` | `memeradar_api.read.outcomes.PositionPerformanceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PositionQueryParams` | `memeradar_api.read.outcomes.PositionQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.PositionResponse` | `memeradar_api.read.outcomes.PositionResponse` | 0 | 4 | UNKNOWN; retain |
| `memeradar_api.read.RuleImpactSummaryResponse` | `memeradar_api.read.outcomes.RuleImpactSummaryResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.RuleOutcomeAssociationItemResponse` | `memeradar_api.read.outcomes.RuleOutcomeAssociationItemResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.RuleOutcomeAssociationQueryParams` | `memeradar_api.read.outcomes.RuleOutcomeAssociationQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.RuleOutcomeAssociationResponse` | `memeradar_api.read.outcomes.RuleOutcomeAssociationResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.RuleOutcomeDrilldownItemResponse` | `memeradar_api.read.outcomes.RuleOutcomeDrilldownItemResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.RuleOutcomeDrilldownResponse` | `memeradar_api.read.outcomes.RuleOutcomeDrilldownResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.StageDispositionFunnelQueryParams` | `memeradar_api.read.outcomes.StageDispositionFunnelQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.StageDispositionFunnelResponse` | `memeradar_api.read.outcomes.StageDispositionFunnelResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.StageDispositionFunnelStageResponse` | `memeradar_api.read.outcomes.StageDispositionFunnelStageResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.StageDispositionQueryParams` | `memeradar_api.read.outcomes.StageDispositionQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._closed_trade_response` | `memeradar_api.read.outcomes._closed_trade_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._forward_outcome_response` | `memeradar_api.read.outcomes._forward_outcome_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read._position_entry_evidence_response` | `memeradar_api.read.outcomes._position_entry_evidence_response` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_api.read._position_exit_risk_response` | `memeradar_api.read.outcomes._position_exit_risk_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._position_mark_response` | `memeradar_api.read.outcomes._position_mark_response` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_api.read._position_performance_response` | `memeradar_api.read.outcomes._position_performance_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._position_response` | `memeradar_api.read.outcomes._position_response` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read._rule_outcome_association_response` | `memeradar_api.read.outcomes._rule_outcome_association_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read._stage_disposition_funnel_response` | `memeradar_api.read.outcomes._stage_disposition_funnel_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._POLICY_PARAMETER_TYPES` | `memeradar_api.read.research._POLICY_PARAMETER_TYPES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._POLICY_STAGES` | `memeradar_api.read.research._POLICY_STAGES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._PROMOTION_STAGES` | `memeradar_api.read.research._PROMOTION_STAGES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._PROMOTION_STATUSES` | `memeradar_api.read.research._PROMOTION_STATUSES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._READINESS_STATUSES` | `memeradar_api.read.research._READINESS_STATUSES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.AlphaValidationResponse` | `memeradar_api.read.research.AlphaValidationResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ChainOpportunityQueryParams` | `memeradar_api.read.research.ChainOpportunityQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ChainOpportunityResponse` | `memeradar_api.read.research.ChainOpportunityResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.ExternalProviderReadinessResponse` | `memeradar_api.read.research.ExternalProviderReadinessResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.LiveReadinessParameterResponse` | `memeradar_api.read.research.LiveReadinessParameterResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.PromotionStageResponse` | `memeradar_api.read.research.PromotionStageResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ReadinessGateResponse` | `memeradar_api.read.research.ReadinessGateResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ReadinessResponse` | `memeradar_api.read.research.ReadinessResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.StrategyFailureModeEntryResponse` | `memeradar_api.read.research.StrategyFailureModeEntryResponse` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.StrategyFailureModesResponse` | `memeradar_api.read.research.StrategyFailureModesResponse` | 0 | 3 | UNKNOWN; retain |
| `memeradar_api.read._alpha_validation_response` | `memeradar_api.read.research._alpha_validation_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._chain_opportunity_response` | `memeradar_api.read.research._chain_opportunity_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._external_provider_readiness_response` | `memeradar_api.read.research._external_provider_readiness_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._readiness_projection` | `memeradar_api.read.research._readiness_projection` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._TOKEN_SIMILARITY_MATCH_TYPES` | `memeradar_api.read.tokens._TOKEN_SIMILARITY_MATCH_TYPES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.TimelineEntryResponse` | `memeradar_api.read.tokens.TimelineEntryResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.TimelineHistoryCoverageResponse` | `memeradar_api.read.tokens.TimelineHistoryCoverageResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.TimelinePageResponse` | `memeradar_api.read.tokens.TimelinePageResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.TimelineQueryParams` | `memeradar_api.read.tokens.TimelineQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.TimelineSourceContinuationResponse` | `memeradar_api.read.tokens.TimelineSourceContinuationResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.TokenResponse` | `memeradar_api.read.tokens.TokenResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.TokenSimilarityResponse` | `memeradar_api.read.tokens.TokenSimilarityResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._timeline_page_response` | `memeradar_api.read.tokens._timeline_page_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read._timeline_response` | `memeradar_api.read.tokens._timeline_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read._token_response` | `memeradar_api.read.tokens._token_response` | `tests/unit/test_read_api_routes.py` | 1 | UNKNOWN; retain |
| `memeradar_api.read._token_similarity_response` | `memeradar_api.read.tokens._token_similarity_response` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._WALLET_HISTORY_STATES` | `memeradar_api.read.wallets._WALLET_HISTORY_STATES` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._WALLET_TIERS` | `memeradar_api.read.wallets._WALLET_TIERS` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ClusterGraphQueryParams` | `memeradar_api.read.wallets.ClusterGraphQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.CreatorReputationResponse` | `memeradar_api.read.wallets.CreatorReputationResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.GraphEdgeResponse` | `memeradar_api.read.wallets.GraphEdgeResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.GraphNodeResponse` | `memeradar_api.read.wallets.GraphNodeResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.ShortestPathQueryParams` | `memeradar_api.read.wallets.ShortestPathQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.ShortestPathResponse` | `memeradar_api.read.wallets.ShortestPathResponse` | 0 | 3 | UNKNOWN; retain |
| `memeradar_api.read.TokenGraphQueryParams` | `memeradar_api.read.wallets.TokenGraphQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.WalletActivityResponse` | `memeradar_api.read.wallets.WalletActivityResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletCandidateQueryParams` | `memeradar_api.read.wallets.WalletCandidateQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.WalletCandidateResponse` | `memeradar_api.read.wallets.WalletCandidateResponse` | 0 | 2 | UNKNOWN; retain |
| `memeradar_api.read.WalletCreatorTransferResponse` | `memeradar_api.read.wallets.WalletCreatorTransferResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletDecisionEvidenceResponse` | `memeradar_api.read.wallets.WalletDecisionEvidenceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletGraphQueryParams` | `memeradar_api.read.wallets.WalletGraphQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.WalletGraphResponse` | `memeradar_api.read.wallets.WalletGraphResponse` | 0 | 6 | UNKNOWN; retain |
| `memeradar_api.read.WalletHistoryCoverageResponse` | `memeradar_api.read.wallets.WalletHistoryCoverageResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletQueryParams` | `memeradar_api.read.wallets.WalletQueryParams` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read.WalletRealizedOutcomeResponse` | `memeradar_api.read.wallets.WalletRealizedOutcomeResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletReputationSnapshotResponse` | `memeradar_api.read.wallets.WalletReputationSnapshotResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read.WalletResponse` | `memeradar_api.read.wallets.WalletResponse` | 0 | 4 | UNKNOWN; retain |
| `memeradar_api.read.WalletRoleEvidenceResponse` | `memeradar_api.read.wallets.WalletRoleEvidenceResponse` | 0 | 0 | UNKNOWN; retain |
| `memeradar_api.read._creator_reputation_response` | `memeradar_api.read.wallets._creator_reputation_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._wallet_activity_response` | `memeradar_api.read.wallets._wallet_activity_response` | `tests/unit/test_read_api_routes.py` | 0 | UNKNOWN; retain |
| `memeradar_api.read._wallet_candidate_response` | `memeradar_api.read.wallets._wallet_candidate_response` | 0 | 1 | UNKNOWN; retain |
| `memeradar_api.read._wallet_graph_response` | `memeradar_api.read.wallets._wallet_graph_response` | `tests/unit/test_read_api_routes.py` | 3 | UNKNOWN; retain |
| `memeradar_api.read._wallet_response` | `memeradar_api.read.wallets._wallet_response` | `tests/unit/test_read_api_routes.py` | 2 | UNKNOWN; retain |
| `memeradar_worker.main._DEXSCREENER_DISCOVERY_STATE_LIMIT` | `memeradar_worker.early_discovery._DEXSCREENER_DISCOVERY_STATE_LIMIT` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._DEXSCREENER_ENRICHMENT_BATCH_SIZE` | `memeradar_worker.early_discovery._DEXSCREENER_ENRICHMENT_BATCH_SIZE` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_CURVE_REFRESH_INTERVAL` | `memeradar_worker.early_discovery._EARLY_CURVE_REFRESH_INTERVAL` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_CURVE_REFRESH_LIMIT` | `memeradar_worker.early_discovery._EARLY_CURVE_REFRESH_LIMIT` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_SOCIAL_CALL_LOOKBACK` | `memeradar_worker.early_discovery._EARLY_SOCIAL_CALL_LOOKBACK` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_SOCIAL_CALL_QUERY_LIMIT` | `memeradar_worker.early_discovery._EARLY_SOCIAL_CALL_QUERY_LIMIT` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_WALLET_BALANCE_REFRESH_INTERVAL` | `memeradar_worker.early_discovery._EARLY_WALLET_BALANCE_REFRESH_INTERVAL` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_WALLET_BALANCE_REFRESH_LIMIT` | `memeradar_worker.early_discovery._EARLY_WALLET_BALANCE_REFRESH_LIMIT` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._EARLY_WALLET_BALANCE_SAMPLE_LIMIT` | `memeradar_worker.early_discovery._EARLY_WALLET_BALANCE_SAMPLE_LIMIT` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._BoundRuntimeRepositories` | `memeradar_worker.early_discovery._BoundRuntimeRepositories` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._collection_health` | `memeradar_worker.early_discovery._collection_health` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._dexscreener_candidate_discovery_row` | `memeradar_worker.early_discovery._dexscreener_candidate_discovery_row` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._dexscreener_candidate_with_pair_created_at` | `memeradar_worker.early_discovery._dexscreener_candidate_with_pair_created_at` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._dexscreener_discovery_observation` | `memeradar_worker.early_discovery._dexscreener_discovery_observation` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._dexscreener_health_observation` | `memeradar_worker.early_discovery._dexscreener_health_observation` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._early_bonding_curve_targets` | `memeradar_worker.early_discovery._early_bonding_curve_targets` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._early_runtime_signal_time` | `memeradar_worker.early_discovery._early_runtime_signal_time` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._early_social_call_evidence` | `memeradar_worker.early_discovery._early_social_call_evidence` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._early_social_token_identity` | `memeradar_worker.early_discovery._early_social_token_identity` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._early_wallet_balance_targets` | `memeradar_worker.early_discovery._early_wallet_balance_targets` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._load_dexscreener_discovery_state` | `memeradar_worker.early_discovery._load_dexscreener_discovery_state` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._load_early_reevaluation_rows` | `memeradar_worker.early_discovery._load_early_reevaluation_rows` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._madeonsol_collection_health` | `memeradar_worker.early_discovery._madeonsol_collection_health` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._madeonsol_health_state` | `memeradar_worker.early_discovery._madeonsol_health_state` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._observation_from_row` | `memeradar_worker.early_discovery._observation_from_row` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._pumpfun_launch_row` | `memeradar_worker.early_discovery._pumpfun_launch_row` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._reason_code_values` | `memeradar_worker.early_discovery._reason_code_values` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._reevaluation_observation` | `memeradar_worker.early_discovery._reevaluation_observation` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._refresh_early_bonding_curve_states` | `memeradar_worker.early_discovery._refresh_early_bonding_curve_states` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._refresh_early_wallet_balances` | `memeradar_worker.early_discovery._refresh_early_wallet_balances` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._row_timestamp` | `memeradar_worker.early_discovery._row_timestamp` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_dexscreener_early_discovery` | `memeradar_worker.early_discovery._run_dexscreener_early_discovery` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_early_alpha_shadow` | `memeradar_worker.early_discovery._run_early_alpha_shadow` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_early_lifecycle_reevaluation` | `memeradar_worker.early_discovery._run_early_lifecycle_reevaluation` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_gmgn_shadow` | `memeradar_worker.early_discovery._run_gmgn_shadow` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_madeonsol_shadow` | `memeradar_worker.early_discovery._run_madeonsol_shadow` | `tests/unit/test_worker_entrypoint.py`; `tests/integration/test_madeonsol_runtime_postgres.py` | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_provider_shadow` | `memeradar_worker.early_discovery._run_provider_shadow` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._select_dexscreener_enrichment_batch` | `memeradar_worker.early_discovery._select_dexscreener_enrichment_batch` | `tests/unit/test_worker_entrypoint.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_robinhood_intent_reconciliation` | `memeradar_worker.intent_jobs._run_robinhood_intent_reconciliation` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.main.reconcile_robinhood_intent_batch` | `memeradar_worker.intent_jobs.reconcile_robinhood_intent_batch` | `tests/unit/test_robinhood_intent_reconciliation.py` | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_alert_outbox` | `memeradar_worker.operations_jobs._run_alert_outbox` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_service_conflicts` | `memeradar_worker.operations_jobs._run_service_conflicts` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_solana_ingestion_health` | `memeradar_worker.operations_jobs._run_solana_ingestion_health` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.main._run_solana_wallet_history` | `memeradar_worker.wallet_jobs._run_solana_wallet_history` | `tests/unit/test_wallet_history_worker.py` | 1 | UNKNOWN; retain |
| `memeradar_worker.main._run_wallet_candidate_discovery` | `memeradar_worker.wallet_jobs._run_wallet_candidate_discovery` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._endpoint_record` | `memeradar_application.pumpfun_forward.endpoint_record` | 0 | 2 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._flag` | `memeradar_application.pumpfun_forward.flag` | 0 | 0 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._horizon_matured` | `memeradar_application.pumpfun_forward.horizon_matured` | `tests/unit/test_pumpfun_forward_evidence.py` | 2 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._initial_market_values` | `memeradar_application.pumpfun_forward.initial_market_values` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._market_metrics` | `memeradar_application.pumpfun_forward.market_metrics` | 0 | 1 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._metric` | `memeradar_application.pumpfun_forward.metric` | 0 | 3 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._multiple_at_endpoint` | `memeradar_application.pumpfun_forward.multiple_at_endpoint` | 0 | 2 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._outcome_flags` | `memeradar_application.pumpfun_forward.outcome_flags` | 0 | 2 | UNKNOWN; retain |
| `memeradar_worker.forward_evidence._valid_market_record` | `memeradar_application.pumpfun_forward.valid_market_record` | 0 | 1 | UNKNOWN; retain |

<!-- HISTORICAL_DEEP_REFACTOR_REPORT -->

# Historical report — superseded by current checkpoint above

# MemeRadar deep refactor

## Scope and baseline

Resume the verified purpose refactor, not the upstream feature roadmap.
Baseline: `main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`,
source `sha256:9ecdd5c2a46e5cd6ddd766875e13bd31cd496a3d8c6f2c9bee4cbeb18e13edfc`, 710 files.
Previous exact-source full verify/build/budgets passed. Those are baseline,
not acceptance of the changes in this report. No new provider, score, lifecycle,
persistence owner, migration, scheduler, execution mode or generic framework.

The [prior semantic inventory](memeradar-purpose-refactor.md) covers 184 Python
modules/classes, their static consumers, metric authority and all 22 routes.
It remains the baseline ownership graph; this pass deepens the mixed read/worker
and outcome surfaces instead of repeating it. The canonical Alpha Core remains
`EarlyRuntimeService` → immutable T0 → forward/paper outcome → validation.

## Hotspot measurements before

| File | Lines | Top-level classes | Top-level functions | Import statements |
| --- | ---: | ---: | ---: | ---: |
| `apps/api/src/memeradar_api/read.py` | 4229 | 90 | 52 | 26 |
| `packages/application/src/memeradar_application/read_api.py` | 7581 | 66 | 47 | 32 |
| `apps/worker/src/memeradar_worker/main.py` | 2843 | 1 | 49 | 42 |
| `apps/worker/src/memeradar_worker/forward_evidence.py` | 2304 | 2 | 45 | 26 |
| `packages/providers/src/memeradar_providers/composition.py` | 798 | 9 | 4 | 27 |

API read mixes candidate/token/wallet/caller/outcome/operations/research DTOs,
serializers and routing. Application read mixes those typed contracts, temporal
recovery analysis, pagination and in-memory query orchestration. Worker main
mixes registry/supervision with discovery, wallet, receipts and reliability.
Forward worker contains pure horizon/market/outcome classification alongside SQL
polling. These are proven responsibility boundaries, not size-only extraction.
Provider composition is already bounded transport selection; no rewrite justified.

## Ownership / consumer proof boundary

| Surface | Owner | Runtime/API/DI | Tests/replay/compatibility | Action |
| --- | --- | --- | --- | --- |
| API product DTO/serializers | existing read boundary | create_app → build_read_router; all routes preserved | API/schema tests, main/read imports; JSON not pickle | SIMPLIFY into product modules; facade re-exports |
| Application read models | existing ReadQueryPort | SQL query adapter / API / MCP | in-memory, contract, persistence and temporal replay; public imports retained | SIMPLIFY focused product contracts; facade retained |
| In-memory forward query | outcome read owner | ReadQueryPort method | bounded as-of/sort/cursor tests | Delegate to focused existing-query function |
| Worker receipt/wallet jobs | worker orchestration | run_worker task registry | checkpoint/reorg and scheduler tests, legacy main imports | Separate orchestration modules; retain aliases |
| Forward horizon math | application forward-outcome owner | canonical ReplayEventRecord inputs | forward worker tests and replay contracts | Move pure calculations to existing application module |
| Provider adapters | source normalization | provider bundle / protocol registry / ports | fixture/doctor/protocol/replay consumers | CORE_KEEP; no scoring authority found |
| Compatibility imports | canonical new product module | facade exports legacy symbol/path | old tests/scripts/DI import paths | COMPATIBILITY_ONLY; no duplicate implementation |
| Outcome coverage | existing persisted forward-outcome projection | bounded read result, no second query/store | duplicate horizons, missing identity/maturity, as-of tests | Distinct token/decision counts, independence UNKNOWN |
| Primary navigation | existing SidebarNav | four groups / existing deep links | shell/route/component tests | Discover / Investigate / Validate / Operate |
| Artifact runs | existing runner output | referenced reports/acceptance metadata | reference/identity evidence | Retention manifest; only proven disposable files removed |

No deletion follows from import absence alone. The separate dead-code report
records reference/DI/CLI/router/test/migration/replay/serialization/documentation
checks and retains uncertain or externally exposed symbols.

## Plan / ledger

- [x] Recovery, baseline identity and prior ownership graph inspected.
- [x] Product-oriented API contract/serializer split; preserve legacy imports and schema/default outputs.
- [x] Application product read-contract split; keep ReadQueryPort facade/repositories; isolate forward query.
- [x] Worker orchestration separation and pure forward-outcome calculations into application owner.
- [x] Provider/compatibility audit; explicit alias/removal conditions.
- [x] Four navigation groups, shared investigation/validation entry points; no arbitrary route deletion.
- [x] Backend-owned bounded outcome coverage and UI; no statistical independence inferred from row counts.
- [x] Architecture drift correction; dead-code/retention proof and narrow ignore rules.
- [x] Final aggregate/build/budgets/migrations/diff and exact identity binding passed (after recorded failure recovery).

Review constraints: immutable six safe modes, protected Admin mutations/secret state,
no-lookahead and all bounded query/cursor behavior unchanged; row counts !=
independent samples. Class/model moves retain API titles and legacy exports.
No PostgreSQL/browser/provider retry loop; prior external restrictions remain.

## Verification

Final corrected aggregate **EXIT 0**, production build **EXIT 0**, route budgets
**5/5 PASS**, migration graph/diff **EXIT 0**, root Node helpers **4/4 PASS**.
Python **1,963 passed / 25 skipped / 0 failed / 8 warnings**, 431.70s, coverage 80%.
Frontend **256 passed / 36 files**. Ruff, mypy (**205 files**), frontend lint and
typecheck, CSS (**443 classes / 83 files**), Compose config, secret scan, local
security review and SBOM (**565 components**) PASS. External vulnerability scans
NOT_RUN; PG/browser/provider/real-OOS acceptance NOT VERIFIED.

Final source: `sha256:29e7990941ba3a3f078fe34f80f51af37c90b09cf62d4f25038948e6251ac5e3`, **731 files**,
`main`, HEAD `35274d2fd7ae07ef6446b66cef70ac6b93f5e84e`. Pre-verify,
post-verify and post-build identities match. No source edits afterward.

[Aggregate log](../../artifacts/verification/memeradar-deep-refactor-2026-10-18.log) ·
[Build](../../artifacts/verification/memeradar-deep-refactor-build-2026-10-18.log) ·
[Budgets](../../artifacts/verification/memeradar-deep-refactor-routes-2026-10-18.log) ·
[Identity/exit binding](../../artifacts/verification/memeradar-deep-refactor-2026-10-18.json) ·
[Failed first attempt](../../artifacts/verification/memeradar-deep-refactor-2026-10-18-attempt1.log).

Final verdict: **PURPOSE_ALIGNED_DEEP_REFACTOR_WITH_EXTERNAL_BLOCKERS**.
No production, read-only-shadow or real-alpha acceptance is promoted.


## Before / root cause / after

| AREA | BEFORE | ROOT_CAUSE | CHANGE | AFTER | FILES | TESTS | RISK | PRODUCT_IMPACT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| API read layer | 4,229-line mixed DTO/router/serializer | unrelated product contracts share one file | move contracts and serializers by product, keep router facade | 981-line facade; common contains shared validation/redaction/page, product literals local | API read package | existing 50 paths/schemas equal; 71 read/schema tests PASS | public import/JSON compatibility retained | evidence owners easier to trace |
| application read layer | 7,581-line mixed models/query/temporal analysis | product contracts mixed with query orchestration | 9 focused read modules; existing ReadQueryPort/InMemory facade; delegate forward page query | 2,630-line facade; repositories unchanged | application read_* | 70 initial / 71 final read tests PASS | temporal/cursor checks preserved | bounded outcome owner obvious |
| worker composition | 2,843-line main | registration mixed with unrelated job orchestration | move discovery/wallet/receipt/operations jobs; explicit legacy aliases | main 326 lines; existing registry/supervisor remains | worker main and 4 job modules | 33 worker/receipt tests PASS | no scheduler/worker capability added | failure ownership by job family |
| providers | transport adapters/composition | no proven embedded ranking violation | audit; retain | 798-line composition unchanged | providers unchanged | provider/full gates | no authority increase | provider independence preserved |
| compatibility | external imports of monolith names | moving symbols could break scripts/replay/API/MCP | facade re-exports to canonical modules; no duplicate implementation | legacy import identity retained | API/app/worker facades | exact class identity and old imports | remove only after all consumers migrate | safe incremental extraction |
| scores/confidence | distinct promise/safety/quality/copyability/outcome owners | similar names do not imply equivalent semantics | retain prior authority matrix | no score, threshold or gate change | unchanged score owners | existing score/decision/full tests | no merged quantities | honest dimensions |
| frontend navigation | Overview + Discover + Investigate + Evaluate + Operate | attention split between overlapping primary headings | home enters Discover, Evaluate becomes Validate, Opportunities enters Validate | four groups; all 22 routes/deep links preserved | shell-client / shell tests | focused shell PASS | labels/hrefs preserved | Discover → Investigate → Validate → Operate |
| frontend fetching | layout and Home/Operations call same no-argument overview with distinct abort signals | native fetch memoization cannot be relied on across those signals | one shared React cache wrapper on existing operations read | request-scoped result, no cross-request cache | read-api.ts | gateway/auth tests; outside-render calls remain independent | rendered request count not runtime measured | removes structurally duplicate overview work in a server render |
| frontend components | UI locally recounts maturity rows | row counts obscure distinct identities/unknown decisions | consume typed backend coverage; reject malformed scope/count/independence | presentational summary + existing table/search/replay | outcomes / read gateway | frontend focused 90 PASS | no client readiness/business authority | mature evidence easier to inspect |
| Settings | guarded runtime editor; prior pass removed inert policy summary | no remaining duplicate registry/research read proved | retain canonical registry/RBAC/pending/audit | Settings remains operational | unchanged Settings owners | Settings gateway/editor focused tests PASS | no Admin service token/secret persistence | secondary safe operations |
| Readiness | backend ENGINEERING/SHADOW diagnostics + alpha evidence | low-level gates have distinct authority | retain three reporting dimensions; clarify separation | no new enums/evaluator; no promotion | current architecture/readiness docs | readiness/API focused PASS | blocked acceptance stays blocked | implementation ≠ operational acceptance |
| Outcomes | bounded horizon rows, local maturity tally | row/horizon count ≠ token/decision sample count | opt-in backend coverage over returned as-of page, no new query/store | distinct and mature identities, mixed-record maturity, unknown/unresolved counts, five horizons | read_outcomes / API / web | duplicate identity/horizon, missing maturity/T0, as-of, default response and parser tests | distinct ≠ statistical independence | real-alpha validation visibility without inflated claims |
| Docs | current owner graph plus stale Sprint 8.3 Settings language | historical contract reads as current | mark historical/superseded and point to current guarded security contract | current owner boundaries first; short STATUS | ARCHITECTURE/STATUS/reports | current links/reference review | original history retained | operator truth easier to find |
| Tests | imports/monkeypatch targets tied to main globals | function globals move with canonical module | patch canonical discovery globals, retain calls through main aliases; add identity/coverage checks | behavioral/security/schema tests retained | 7 Python / 3 TS test files | focused evidence below | no test removed/xfail/weakened | contract-preserving refactor |
| dead code | no complete orphan proof | import absence insufficient | retain uncertain/external consumers | 0 source/test deletions | dead-code report | static/re-export/DI/CLI/replay/schema audit | avoid losing compatibility/user work | no file-count target |
| artifacts | 1,508 loose historical files, 172,280,982 bytes | reproducible run tree obscures source ownership | verified full archive; keep 16 cited/index copies | 1,492 originals archived, no unique bytes discarded | history archive/manifest + runs README | all member SHA-256 comparisons PASS | restore nested historical attachments before browsing | source/noise separation |
| gitignore | future local reports/transcript visible | disposable output lacks narrow ignores | add four exact output paths | required evidence remains visible | .gitignore | diff/status review | no broad docs/source ignore | less future noise |
| repository hygiene | inherited thousands of dirty entries | changes not attributable to one task | bounded 47-file task surface + artifact manifest | preserve all unrelated source and inherited provider-actions deletion | explicit manifest below | Git snapshots; diff check | .git/.codex host read-only | safe future recovery |

### Coverage semantics / unchanged authority

`include_coverage=true` extends only the existing forward-outcomes endpoint.
Default response, ordering, bounds, filters/cursor and temporal checks remain
unchanged. All other paths and existing response schemas compare exactly with
the pre-refactor OpenAPI. There is no second DB query or new persistence owner.

Coverage scope is LOADED_PAGE, including current filters/as-of/pagination. A
mature distinct token/decision means at least one recorded horizon is explicitly
mature; it does not mean all horizons or economics are complete. Partially mature
tokens have both mature and pending records in this page. Missing relevant
identity/maturity makes corresponding aggregates UNKNOWN. No rows for a horizon
means UNKNOWN horizon maturity, not a measured zero population. Missing T0 IDs
never fall back to candidate IDs. `independence_state=NOT_ESTABLISHED` always;
no statistical independence, complete population, cash economics, OOS acceptance
or real-world alpha is inferred. Future outcomes never rewrite T0 evidence.

### Workspace and fetch audit

Home ranks immediate candidates and status; Radar screens a bounded candidate
query plus early/social corroboration; Ultra Early is the existing 49-field
early projection. Home/Radar already share RadarWorkspace and joinRadarRows.
These are DATA/COMPONENT overlap, not proven true product duplication. Validation
routes differ by persisted outcome, missed-target, same-age comparison, stage
funnel, chain opportunity or paper-position scope; retain their deep links and
existing primitives rather than introduce new workspace wrappers.

Server pages fetch typed projections and pass them to presentational children.
Settings has no Readiness fetch (removed in the prior baseline); provider health,
control state/config and runtime settings have distinct contracts. The only
newly proved same-render endpoint overlap is operations overview from layout
and Home/Operations. Existing requests use distinct AbortControllers, so the
shared server function is wrapped once with React `cache`, not a process-global
map or TTL. Official React documentation checked through Context7:
[cache](https://react.dev/reference/react/cache) invalidates per server request;
outside-render tests confirm no persistent cache. Browser/request latency and
runtime request-count acceptance remain unmeasured. No other cache, N+1 rewrite
or optimization was justified by evidence. Backend coverage reuses one page.

### Explicit compatibility boundary

These are aliases, not alternative owners. Keep canonical implementations in
product modules; keep legacy imports until API, SQL adapter, MCP, CLI, scripts,
tests and replay consumers migrate. JSON/schema names and current migration
imports remain stable; no Python pickle compatibility is claimed for moved classes.

| Legacy module | Canonical targets | Relocated symbols | Current consumers / removal condition |
| --- | --- | ---: | --- |
| memeradar_api.read | read.common/candidates/tokens/wallets/callers/outcomes/operations/research | 151 | create_app and tests; remove aliases only after known/external imports migrate |
| memeradar_application.read_api | read_common/candidates/tokens/wallets/callers/outcomes/positions/operations/research | 114 | API, SQLReadQueryService, MCP, tests/research; retain facade/ReadQueryPort |
| memeradar_worker.main | early_discovery / wallet_jobs / intent_jobs / operations_jobs | 45 | CLI registration, test imports, pumpfun_live_acceptance; retain legacy aliases |
| memeradar_worker.forward_evidence private helpers | existing application pumpfun_forward | 9 | collector/scripts/tests; retain aliases while callers exist |

No duplicate business owner was discovered that could safely be deleted in this
pass. Responsibility mixing was reduced by relocation, not replacing mature
specialist owners with generic services. The previous purpose refactor's shared
freshness/risk-reader consolidation remains intact.

### Product alignment review (subjective 0–10)

| Dimension | Before | After | Basis |
| --- | ---: | ---: | --- |
| Purpose alignment | 8 | 9 | four workflow groups and honest outcome coverage |
| Architecture simplicity | 8 | 8 | same owners; more focused modules, no new abstraction |
| Ownership clarity | 8 | 9 | read and job responsibilities local |
| Provider independence | 9 | 9 | transport/normalization authority unchanged |
| Evidence traceability | 9 | 9 | schema/import/time/lineage preserved |
| Outcome validation | 5 | 5 | distinct maturity visible; real independent economics/OOS still absent |
| Operational clarity | 8 | 9 | current Settings contract, explicit archive recovery |
| Frontend workflow clarity | 7 | 8 | four groups; detail/research routes remain reachable |
| Safety | 9 | 9 | no gate/mode/auth changes |
| Maintainability | 8 | 9 | mixed hotspots reduced, compatibility intentional |
| Repository hygiene | 4 | 7 | loose artifact noise archived; inherited dirty source retained |

These are review judgments, not measured product/performance scores.

### Bounded task-owned surface

Only this pass's hunks/relocations are owned, not entire inherited file diffs:

- API: `apps/api/src/memeradar_api/read/{__init__,common,candidates,tokens,wallets,callers,outcomes,operations,research}.py` (old read.py relocated).
- Application: `read_api.py`, new `read_{common,candidates,tokens,wallets,callers,outcomes,positions,operations,research}.py`, existing `pumpfun_forward.py`.
- Worker: `main.py`, `early_discovery.py`, `wallet_jobs.py`, `intent_jobs.py`, `operations_jobs.py`, `forward_evidence.py`.
- Python tests: `test_read_api.py`, `test_read_api_routes.py`, `test_worker_entrypoint.py`, `test_pumpfun_forward_evidence.py`, `test_wallet_history_worker.py`, smoke `test_compose_contract.py`, integration `test_madeonsol_runtime_postgres.py`.
- Web: `lib/read-api.{ts,test.ts}`, `components/{outcomes,shell-client}.tsx`, `components/{outcomes,shell}.test.tsx`.
- Docs: STATUS, ARCHITECTURE, this report, dead-code report, runs README; archive/manifest; `.gitignore`.

39 Python/TS files, 5 current docs, 2 archival files and .gitignore = 47 physical
files, plus the old API file relocation and 1,492 preserved artifact moves.
No migration, dependency, scorer, safety mode, provider or execution code added.
No Git mutation or remote operation; host read-only .git/.codex preserved. The
STATUS checkpoint substitutes for absent/read-only .codex checkpoint paths.

### Remaining debt / external acceptance

The application facade still composes many typed reads; discovery orchestration
and SQL forward polling remain substantial modules. Their responsibilities are
now explicit; further subdivision without a distinct owner is deferred. Legacy
re-exports and research schemas remain deliberately compatible. No other orphan
passed deletion proof. No runtime performance improvement is claimed without
browser/provider measurement.

External: authorized PostgreSQL fresh/legacy/concurrency/atomicity/restart
acceptance; credentialed browser workflows/screenshots/axe/performance; verified
provider source/deployment/frame/receipt evidence; complete economics/benchmark;
real independent mature cohorts and leakage-safe chronological OOS.
READ_ONLY_SHADOW_READY remains NOT ACCEPTED, ALPHA_VALIDATED=NO,
REAL_WORLD_ALPHA_NOT_YET_PROVEN, PRODUCTION_READY=false.


### Mechanical relocation check

AST comparison against preserved pre-refactor files: API 150/151 moved definitions
identical; only ForwardOutcomeQueryParams intentionally gains opt-in coverage.
Application 114/114 and worker 45/45 moved definitions identical. Imports, file
locations and formatting differ; this supplements, not replaces, behavioral tests.
Initial extraction caught/restored a private serializer re-export and corrected
one helper/local name collision. A new identity test initially named a nonexistent
WalletProfileView; corrected to the established WalletView (no production contract
changed). No security/scoring assertion was weakened.


### Aggregate failure recovery (not hidden)

First aggregate attempt on source `sha256:669a34b0180b7ba35a5d3ad8394a47b50a8f392e49439da01b0cfddcf59516cf`
exited 2: Python 1,961 passed / 2 failed / 25 skipped / 8 warnings (439.69s).
Lint and mypy passed; make stopped at Python, so later gates were NOT_RUN.

1. `tests/smoke/test_compose_contract.py::test_read_api_surface_is_packaged_and_safe`:
   stale filesystem expectation opened old `read.py`. It now checks every API
   product file and every application read contract, retaining all original
   forbidden-provider/framework/mutation and safe-mode assertions.
2. `tests/unit/test_wallet_history_worker.py::test_wallet_history_worker_closes_provider_bundle_when_stopped`:
   the fixture patched old `main` globals, not moved function globals. Patch the
   canonical `wallet_jobs` dependencies; retain the call through the main alias and
   identical shutdown/close assertions. Restore four legacy main wallet-poll helper
   re-exports. The analogous external PG fixture now patches early_discovery; its
   actual PG acceptance remains skipped/unverified.

Both exact failing tests pass (2 PASS). Broader recovery regression passed **135 / 1 external PG skip**, followed by the
successful final aggregate; no scoring/safety change or weakened assertion. Scoped
formatter diff for the three newly touched test files contains only unrelated
inherited lines; intentionally retained. No whole-file format write there.


## Acceptance answers

1. Shortest Alpha Core: provider observation → normalized evidence/token discovery → EarlyFeatureSnapshot + independent risk/corroboration → EarlyScorer/EarlyDecisionEngine in EarlyRuntimeService → immutable T0 → forward/paper mature outcomes → copyability/economics → replay/calibration/OOS.
2. Split API read.py, application read_api.py and worker main; move pure forward math out of the worker.
3. Proven product-contract and orchestration/policy responsibility mixing; file length alone was not the reason.
4. No additional duplicate business owner removed; existing owners retained with focused modules. No replacement scoring/config/persistence owner introduced.
5. API/application/worker facade aliases remain; legacy wallet-poll imports also retained. Removal requires all runtime/MCP/CLI/script/test/replay consumers to migrate.
6. No provider ranking/promotion/risk-authority violation proved; providers unchanged.
7. Discovery/wallet/receipt/operations job orchestration leaves main; nine pure market/horizon/outcome helpers move to existing application pumpfun_forward.
8. No proven duplicate DB query removed. Coverage consumes the existing single bounded/as-of page and issues no additional read.
9. Layout and Home/Operations share a single React request-scoped operations function; outside-render gateway calls remain uncached. Runtime request reduction is not measured.
10. Discover / Investigate / Validate / Operate.
11. Home joins Discover; Opportunities moves to Validate. Dynamic token/wallet/caller detail remains a deep link. No supported destination hidden or arbitrarily demoted.
12. Zero routes merged, redirected or removed; all 22 preserved.
13. Outcomes displays backend coverage instead of computing business maturity totals; shell navigation groups simplified. Other presentational components retained where no overlap justified a new wrapper.
14. Prior Settings readiness fetch/inert proposal summary removal retained. No new config/readiness owner or duplicated research summary.
15. Yes: returned-page distinct/mature token and exact decision counts are separate from rows, with missing identity/maturity UNKNOWN. Distinct identity does not establish independence.
16. No additional current doc relocated; prior STATUS/readiness history preserved byte-for-byte. Historical visual attachments archived with a per-file manifest.
17. Old Sprint 8.3 read-only Settings paragraph marked HISTORICAL/SUPERSEDED; current guarded Admin write contract and source boundaries documented first.
18. Zero source files proved unused after consumer/registration/compatibility checks.
19. Zero unused source files deleted (one API source relocation).
20. Zero source files archived.
21. Zero test files removed; assertions retained/extended.
22. 1,492 loose artifact originals archived; all 1,508 original files present in a hash-verified archive; 16 cited/index copies remain. Zero evidence bytes discarded without preservation.
23. Four narrow ignore paths: web playwright-report, web coverage, visual-evidence/tmp, scripts/nohup.out.
24. No migration or table change; current head remains 0022_cross_chain_evidence, 40 tables.
25. Existing paths/default payloads/response schemas preserved. One additive opt-in include_coverage query/response on forward-outcomes; no breaking change intended.
26. No score arithmetic, thresholds or promotion semantics changed.
27. No safety/auth/secret/protected-mode semantics changed.
28. No provider authority increased.
29. No-lookahead/as-of/immutable T0 preserved; later evidence only evaluates the decision.
30. Final corrected make verify PASS / exit 0; first attempt exit 2 retained, both regressions repaired and verified. Python 1,963 PASS / 25 skip / 8 warnings; frontend 256 PASS.
31. Production build PASS / exit 0, 28 App Router entries including all 22 UI routes.
32. Route budgets PASS 5/5 / exit 0; static budgets are not Web Vitals.
33. Verified final source sha256:29e7990941ba3a3f078fe34f80f51af37c90b09cf62d4f25038948e6251ac5e3, 731 files; pre/post aggregate and post-build identities equal.
34. Intentional debt: facade compatibility, substantial but focused discovery/SQL polling and research diagnostics. No proven unsafe orphan remains within this bounded refactor. Further split without responsibility evidence is deferred.
35. External PG/browser/provider/economics/benchmark/Jito/OOS acceptance remains unavailable/unverified; no repeated probes or speculative implementation.
36. READ_ONLY_SHADOW_READY is NOT ACCEPTED.
37. ALPHA_VALIDATED remains NO.
38. Real-world alpha remains NOT YET PROVEN.
39. Production/read-only production acceptance remains false/unaccepted; live money out of scope.
40. **PURPOSE_ALIGNED_DEEP_REFACTOR_WITH_EXTERNAL_BLOCKERS**. Local refactor/verification closed; external acceptance remains blocked.


### After hotspot measurements

Static fan-in below counts direct runtime-module imports in apps/packages only;
tests, scripts, dynamic registrations and external consumers are recorded in the
consumer tables rather than treated as zero. Fan-out counts distinct imported
module names, not a runtime call graph. Higher facade fan-out from explicit
compatibility re-exports is expected and is not presented as reduced coupling.

| Surface | Lines | Classes | Top-level functions | Runtime static fan-in | Import-module fan-out |
| --- | ---: | ---: | ---: | ---: | ---: |
| `apps/api/src/memeradar_api/read/__init__.py` | 981 | 0 | 8 | 2 | 35 |
| `packages/application/src/memeradar_application/read_api.py` | 2630 | 4 | 20 | 17 | 29 |
| `apps/worker/src/memeradar_worker/main.py` | 326 | 0 | 14 | 1 | 18 |
| `apps/worker/src/memeradar_worker/forward_evidence.py` | 2097 | 2 | 36 | 1 | 26 |
| `packages/providers/src/memeradar_providers/composition.py` | 798 | 9 | 4 | 5 | 27 |

Scoped formatter: 26 refactor-owned Python files PASS; unrelated inherited test drift retained.


### Worktree snapshot after archive/recovery

Final recursive porcelain snapshot: 582 entries = 226 tracked dirty + 356 untracked,
0 staged. Two Git deletions: inherited provider-actions.tsx remains absent;
old API read.py is relocated into the package, not discarded. The 48 task status paths (47 physical files plus old API relocation)
and 16 retained artifact copies are explicit; 518 other paths remain outside
this task's ownership claim. Prior baseline report recorded 2,045 entries; that
is historical evidence, not a reconstructed fresh pre-pass recursive snapshot.
The preserved pre-pass short-status snapshot has 389 collapsed entries (not
comparable to recursive counts). No reset/clean/stash/Git commit/remote operation.


## Active fullstack goal completion audit

This turn made implementation and verification progress; it was not a no-progress
or unsupported completion claim. The requested local deep refactor is verified
above. The broader active goal also requests coherent local commits and real
isolated PostgreSQL where available. Those are not silently counted as done.

One bounded current capability check: MEMERADAR_TEST_DATABASE_URL is unset;
psql/postgres/initdb/pg_ctl are absent, no PostgreSQL binary directory exists,
and Docker info exited 1. No authorized PostgreSQL runtime is available through
these existing mechanisms. No fresh/legacy/concurrency/persistence test is
promoted from static or SQLite evidence. Use the existing DB acceptance handoff
when the runtime becomes available; do not add another database/harness.

The active host permission contract explicitly grants read-only access to .git
(and .codex). A main-worktree commit requires Git metadata writes and cannot be
made under that contract. No alternate Git directory or security bypass was
created, no unrelated changes staged, and no commit success claimed. Git HEAD
remains unchanged. Coherent local commit creation remains an unmet goal item;
the broader goal initially stayed active rather than marked complete. Local safety stays
fail-closed; provider/sample/runtime blockers remain external and documented.


Third consecutive goal audit: source and six final successful gate exits remain
unchanged. The prior continuation was revalidation without implementation
progress, not a live-process wait. Git metadata remains host read-only; no
configured test PostgreSQL or installed PostgreSQL binaries are available.
Provider/browser/real-sample acceptance remains unverified. There is no safe
repository-only action that can create the requested main-worktree commit or
supply these missing external acceptances. The broader goal is now BLOCKED,
not complete; the local refactor verdict and verified work remain preserved.
Resume when Git metadata is writable and/or authorized runtime/evidence exists.
