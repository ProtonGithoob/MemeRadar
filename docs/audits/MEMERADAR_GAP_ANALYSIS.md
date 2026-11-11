# MemeRadar gap analysis

| Area | Existing implementation | Verified gap / disposition |
| --- | --- | --- |
| Early discovery | Worker normalizes raw Solana transactions into canonical stream integrity and early-alpha persistence. | No live provider/database run or measured discovery latency in this environment. |
| Stream integrity | Gap coordinator, backfill seam, persistence models and deterministic replay contracts exist. | Recovery against a real stream/RPC and durable PostgreSQL is not accepted. |
| Risk | Local deterministic risk and optional RugCheck/GoPlus-style contracts exist. | GoPlus adapter is tested but unwired; no provider promotion performed. |
| Wallet intelligence | Wallet tracking/scoring and creator graph are existing application owners. | No live wallet history/economic cohort; labels cannot be called smart money without observed history. |
| Social calls / caller conduct | `SocialRestAdapter.search_calls`, `SocialCallCollector`, `SocialCallObservationRepository` and bounded social-call read exist. | No current worker/composition invokes the collector. Stored calls have a read path, but `CallerMarketConductAnalyzer` has no production caller, persistence owner or read projection. Live caller-wallet conduct is not operational. Wiring requires a bounded candidate-query, cursor/cadence and provider quota policy; no such policy is currently defined. |
| Outcomes / missed winners | Forward-evidence worker, `ExtremeWinnerOutcomeLabeler`, `MissedWinnerAnalyzer`, `FalsePositiveAnalyzer` and replay contracts exist. | No current real matured cohort or quantitative missed-winner rate. Fixtures are not live evidence. |
| Paper execution | Quote-based `PaperExecutionEngine`, gate, shadow-entry service and SQL ledger exist. | `ShadowEntryService`/engine are not instantiated in worker composition; default DexScreener data is a reference quote. Paper-auto runtime is not operationally accepted. |
| Database | Alembic graph and 27-table metadata validate at `0012_stream_gap_diagnostics`. | PostgreSQL integration, migration runtime and restart recovery are blocked by unavailable isolated DB/daemon. |
| Frontend | Existing operator routes and bounded API components; Vitest, lint and typecheck passed. | Browser workflows/accessibility/performance not run; production build blocked by sandbox child-process capture. |
| Dependencies | Lockfile install and local security-review/SBOM gates passed. | npm production advisories remain; external pip/container scans not run. |
| Pre-identity misses | Candidate-level decision transitions keep reason codes after canonical identity exists. | No durable rejection/reconciliation event for raw observations rejected before token identity was established; current false-negative analysis cannot claim complete pre-identity coverage. |
| New provider candidates | Existing capability seams are available. | Not added: stabilization scope explicitly prohibited provider expansion. |

No scoring threshold, provider authority, execution permission, migration, or
no-lookahead behavior was changed by this task.

## Paper quote point-in-time correction — 2026-11-06

| Capability | Before | After | Evidence / status |
| --- | --- | --- | --- |
| Paper quote causality | A quote observed after order time could be marked fresh and filled. | Paper, auto gate, shadow and discovery require the quote to have been observed by the checkpoint. | Regression reproduced a fill before the change; 103 related tests passed. |
| Full backend verification | Previous run interrupted. | Diagnostic exit 124 while the Git-history security scan was active. | Not accepted; stack trace in `artifacts/verification/product-pytest-diagnostic.log`. |
| Type checking | Prior run incomplete. | Full mypy timed out without output. | Not accepted. |
| Historical external reference audit | Registry records a 2026-09-12 MadeOnSol review. | No fresh upstream verification performed. | Current instruction prohibits GitHub access; no external code adopted this run. |
| Discovery, wallet, risk, alpha and realistic PAPER performance | NOT_MEASURED | NOT_MEASURED | No accepted real chronological outcomes or comparable live baseline. |
