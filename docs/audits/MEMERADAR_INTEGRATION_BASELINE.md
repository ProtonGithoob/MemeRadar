# Integration baseline

## Repository snapshot

- Branch `main`; HEAD `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`.
- The tracked tree was clean before this task. It now contains the task's
  source/test/runbook and audit-document changes. Three untracked operator files
  were preserved.
- A release source identity is not bound: the worktree is dirty and no release
  artifact was generated for these edits.
- Migration `0012_stream_gap_diagnostics`; 27 ORM tables. Static migration
  graph passes; PostgreSQL execution was unavailable.

## Existing architecture and runtime entry points

| Capability | Code evidence | Current evidence boundary |
| --- | --- | --- |
| API | `apps/api/src/memeradar_api` composes read, control and health routers. | Local tests; no production-like API runtime. |
| Worker | `apps/worker/src/memeradar_worker/main.py::run_worker` starts configured alert, provider-shadow, early-alpha and Pump.fun forward-evidence tasks. | Deterministic tests and composition inspection; no worker runtime. |
| Chain ingest | `early_discovery._run_early_alpha_shadow` wires `SolanaRawTransactionSource`, canonical decoding, `StreamIntegrityCoordinator`, `EarlyRuntimeService`, SQLAlchemy repositories and outbox. | Code/test wiring established; no live transaction was processed here. |
| Persistence | `packages/persistence/src/memeradar_persistence/models.py`; Alembic under `infra/alembic/versions`. | Metadata/migration graph only; no PostgreSQL acceptance. |
| Web | `apps/web/src/app`; existing Discover, Investigate, Validate and Operate surfaces. | Vitest/lint/typecheck; no browser endpoint or E2E acceptance. |
| Research | `early_replay.py`, `early_failure_analysis.py`, `convex_exit.py`, `strategy_promotion.py`; worker forward-evidence collection. | Deterministic contracts; no current real outcome cohort. |
| Paper | `PaperExecutionEngine`, `PaperAutoExecutionGate`, `ShadowEntryService`, and SQL ledger exist. | Engine/service contracts exist; no production worker wiring or live-like fill validation. |

## Implementation evidence index

| Claim | Exact owner / symbol | Runtime entry or consumer | Test evidence |
| --- | --- | --- | --- |
| API app composition | `apps/api/src/memeradar_api/main.py::create_app` | API startup calls `create_app`. | `tests/unit/test_read_api_routes.py` |
| Solana discovery persistence | `packages/application/src/memeradar_application/early_runtime.py::EarlyRuntimeService` | `apps/worker/src/memeradar_worker/early_discovery.py::_run_early_alpha_shadow`, called by `run_worker`. | `tests/unit/test_early_runtime.py`, `tests/unit/test_early_worker_pipeline.py`; PostgreSQL integration `tests/integration/test_early_runtime_persistence.py` was deselected/unrun. |
| Stream integrity | `packages/application/src/memeradar_application/stream_integrity.py::StreamIntegrityCoordinator` | Same early-alpha worker path; state store is SQLAlchemy-backed. | `tests/unit/test_stream_integrity.py`, `tests/contract/test_extension_e8_4_stream_integrity.py` |
| Provider composition | `packages/providers/src/memeradar_providers/composition.py::build_provider_bundle` | Worker calls it to construct adapter bundle. | `tests/unit/test_provider_composition.py`, `tests/contract/test_contract_provider_composition.py` |
| Wallet/creator intelligence | `wallet_scoring.py::SmartWalletScorer`, `wallet_tracking.py::WalletTrackingAnalyzer`, `creator_graph.py::CreatorReputationAnalyzer` | Application read/use-case consumers; not live provider evidence by themselves. | `tests/unit/test_wallet_scoring.py`, `tests/unit/test_wallet_tracking.py`, `tests/unit/test_creator_graph.py` |
| Forward outcomes / false negatives | `apps/worker/src/memeradar_worker/forward_evidence.py::PumpFunForwardEvidenceCollector`; `early_replay.py::ExtremeWinnerOutcomeLabeler`; `early_failure_analysis.py::{MissedWinnerAnalyzer,FalsePositiveAnalyzer}` | Pump.fun forward-evidence worker task; research projections consume persisted observations. | `tests/unit/test_pumpfun_forward_evidence.py`, `tests/unit/test_extreme_winner_labels.py`, `tests/unit/test_early_failure_analysis.py` |
| Social calls / caller conduct | `social_call_collection.py::SocialCallCollector`; `correlation.py::CallerMarketConductAnalyzer`; persistence `SocialCallObservationRepository` | No worker/composition call site for the collector/analyzer; persisted-call read path exists but no live ingestion was accepted. | `tests/unit/test_social_call_collection.py`, `tests/unit/test_caller_conduct.py` |
| Paper execution | `paper_execution.py::{PaperAutoExecutionGate,PaperExecutionEngine}`, `shadow_entry.py::ShadowEntryService` | No worker/API composition instantiates shadow entry; integration coverage is test/replay-owned. | `tests/unit/test_paper_auto_gate.py`, `tests/unit/test_paper_execution.py`, `tests/unit/test_shadow_entry.py` |
| Web operator surfaces | `apps/web/src/app/{radar,ultra-early,providers,readiness,settings}/page.tsx` and components | Browser routes consume web API gateway. | `apps/web/src/app/components/{radar,ultra-early,providers,readiness,settings}.test.tsx` (Vitest); browser E2E not run. |

The free-first composition is
`packages/providers/src/memeradar_providers/composition.py::build_provider_bundle`;
constructing it does not itself make requests. The no-network doctor reports
network/auth/schema as `not_checked`.

See [provider capabilities](PROVIDER_CAPABILITY_MATRIX.md),
[gap analysis](MEMERADAR_GAP_ANALYSIS.md), and
[runtime acceptance](RUNTIME_ACCEPTANCE.md).
