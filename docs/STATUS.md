# MemeRadar Status

Last updated: 2026-08-27

## Current verdict

`PHASE_5_SPRINT_5_2_COMPLETE_NEXT_SPRINT_5_3`

Phase 0 and Phase 1 / Sprints 1.1, 1.2 and 1.3 are implemented and locally verified. Phase 2 / Sprints 2.1 through 2.4 and the keyless Gate P2 composition acceptance are complete and locally verified with fixtures and contracts. Phase 3 / Sprints 3.1, 3.2 and 3.3, Phase 4 / Sprints 4.1 through 4.3 and Phase 5 / Sprints 5.1 and 5.2 are complete for their keyless implementation and replay gates; live provider acceptance remains externally blocked because provider endpoints/credentials are unavailable. The repository has a keyless API, worker, web shell, local Compose topology, protected operating-mode defaults, developer commands, quality gates, structured request and event-processing telemetry, application-facing provider ports, resilient transport policies, provider health/freshness/quota models, redacted fixtures and deterministic fakes. No live provider integration, LLM integration or live-money execution has been enabled.

## Current phase and sprint

- Completed: `Phase 2 / Gate P2 — Read-only discovery and independent enrichment acceptance` (keyless portion)
- Completed: `Phase 3 / Sprint 3.1 — Authority / Token Security` (keyless portion)
- Completed: `Phase 3 / Sprint 3.2 — Holder Concentration / Wallet Graph` (keyless portion)
- Completed: `Phase 3 / Sprint 3.3 — Liquidity / Sellability / Wash Trading` (keyless portion)
- Completed: `Phase 4 / Sprint 4.1 — Wallet Tracking` (keyless portion)
- Completed: `Phase 4 / Sprint 4.2 — SmartWalletScore` (keyless portion)
- Completed: `Phase 4 / Sprint 4.3 — Confluence` (keyless portion)
- Completed: `Phase 5 / Sprint 5.1 — Social Provider Seam` (keyless portion)
- Completed: `Phase 5 / Sprint 5.2 — Author Trust and Social Velocity` (keyless portion)
- Next: `Phase 5 / Sprint 5.3 — Narrative LLM`

## Current operating policy

- `ANALYSIS_ONLY=true` — required/default
- `PAPER_TRADING=true` — required/default
- `MANUAL_EXECUTION=false` — disabled
- `AUTO_EXECUTION=false` — disabled

The configuration loader rejects attempts to override these protected values.

## Completed work

- [x] Python package layout for domain, application, API and worker source roots.
- [x] FastAPI composition root with `/health/live` and dependency-aware `/health/ready`.
- [x] Cancellable worker entrypoint, including `python -m memeradar_worker` support and SIGTERM handling.
- [x] Next.js 16.3.3 / React 19 / TypeScript operator shell with visible analysis-only, paper-trading and disabled-execution labels.
- [x] Pinned Python dependency lock and npm lockfile; Next.js was upgraded to 16.3.3 and ESLint to 9.39.5 after audit advisories.
- [x] Safe `.env.example`, `.gitignore`, root `.dockerignore` and editor configuration.
- [x] API, worker and web Dockerfiles plus Postgres 16 / Redis 7 Compose services with health checks.
- [x] Make targets: `bootstrap`, `lint`, `typecheck`, `test`, `verify`, `up`, `down`, `migrate`, `doctor`, `provider-doctor`, `birdeye-doctor`, `rugcheck-doctor`, `social-doctor`.
- [x] Redacted local doctor and high-confidence tracked-file secret scan.
- [x] GitHub Actions workflow for backend, frontend, Compose and secret-scan checks.
- [x] Branch-aware pytest coverage configuration and frontend Vitest/Testing Library baseline.
- [x] Correlation-aware JSON request logging with bounded incoming-ID validation and redaction.
- [x] API image regression fix ensuring the telemetry package is present at runtime.
- [x] Roadmap checkboxes reconciled for Sprints 0.1 and 0.2.
- [x] Canonical Solana token/pool identities with validated base58 public-key addresses.
- [x] Candidate lifecycle aggregate with explicit allow-listed transitions, reason codes and idempotent replay behavior.
- [x] Event envelope, observation provenance and freshness quality states preserving occurred/observed/ingested timestamps.
- [x] Versioned feature, risk, score, alert and position models with confidence, penalties, evidence references and config hashes.
- [x] Fail-closed risk execution-eligibility predicate for stale, unknown, warned or blocked evidence.
- [x] Roadmap checkboxes reconciled for Sprint 1.1.
- [x] SQLAlchemy 2 async persistence models for the core Phase 1 entities, with domain-independent repositories and explicit unit-of-work transactions.
- [x] Initial Alembic revision `0001_initial` for 13 core tables, including provenance, explainability, event and outbox fields.
- [x] Database uniqueness/idempotency constraints and event-time/queue indexes, with metadata and migration parity checks.
- [x] Candidate aggregate rehydration and atomic domain-event/outbox enqueue seam with deterministic duplicate handling.
- [x] Opt-in Postgres repository integration fixture and reversible migration smoke path.
- [x] Roadmap checkboxes reconciled for Sprint 1.2.
- [x] Provider-independent event dispatcher with deterministic event-time ordering, equivalent dedupe and conflicting-key rejection.
- [x] Leased Postgres outbox processing with durable delivery, deterministic retries, lease recovery and terminal dead-letter state.
- [x] Safe event-processing telemetry with allowlisted outcome, event identity, attempt and latency fields; handler exception text is never persisted or logged.
- [x] Duplicate, out-of-order, retry, lease-expiry, dead-letter, persistence idempotency-conflict and synthetic candidate lifecycle replay tests.
- [x] Reversible migration `0002_outbox_processing` and migration-head/metadata parity checks.
- [x] Roadmap checkboxes reconciled for Sprint 1.3.
- [x] Sprint 2.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-1-provider-framework.md`.
- [x] Async application-facing ports for discovery, market, on-chain, risk, social, narrative, quote, execution and notification capabilities.
- [x] Bounded HTTP/WebSocket timeout fields, retry classification with jitter, rate-limit waits and closed/open/half-open circuit breaker.
- [x] Provider health, quota and freshness projection with UNKNOWN/STALE fail-closed distinctions and safe error classes.
- [x] Recursive fixture redaction, deterministic JSON export, fake provider failures and normalized discovery/market adapter contracts.
- [x] Roadmap checkboxes reconciled for Sprint 2.1.
- [x] Sprint 2.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-2-helius-solana-read-layer.md`.
- [x] Helius/RPC read adapter for token metadata, account info and transaction enrichment with canonical identities and classified failures.
- [x] Helius token-program, mint/freeze authority, timestamp and transaction identity normalization with explicit UNKNOWN/INVALID quality states.
- [x] Injected Helius webhook/WebSocket observation seam with redaction, deterministic duplicate IDs, bounded reconnects and cancellation propagation.
- [x] Synthetic Helius JSON-RPC fixtures and contract tests for token, account and transaction reads.
- [x] Key-safe `make provider-doctor` with one bounded read-only `getHealth` call, safe status/latency/quota reporting and protected modes.
- [x] Roadmap checkboxes reconciled for Sprint 2.2; live Helius acceptance isolated as `BLOCKED_EXTERNAL` because endpoint/key configuration is absent.
- [x] Sprint 2.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-3-birdeye-dex-market-layer.md`.
- [x] Birdeye REST discovery and market adapter for new listings plus normalized market, trade, holder and security observations with bounded transport, correlation and key-safe error handling.
- [x] Birdeye stream-first listing normalizer with bounded reconnects, cancellation-safe polling fallback and duplicate-preserving candidate delivery.
- [x] Birdeye freshness/conflict resolver retaining source evidence, preserving unsafe quality states and marking stale/conflicted observations explicitly.
- [x] Synthetic Birdeye REST fixtures, deterministic fixture contracts and provider-specific fixture metadata; fixture content contains no credentials.
- [x] Key-safe `make birdeye-doctor` with bounded read-only `/defi/networks` health/schema check and `BLOCKED_EXTERNAL` handling when configuration is absent.
- [x] Sprint 2.3 roadmap, provider documentation and runtime smoke checks reconciled; live Birdeye acceptance remains isolated as `BLOCKED_EXTERNAL`.
- [x] Protocol-local Pump.fun, PumpSwap, Raydium and Meteora event parsers/adapters with allow-listed event types, alias normalization and classified malformed-input handling.
- [x] Deterministic canonical token/pool mapping and duplicate detector retaining token/pool keys and prior source IDs without dropping repeated deliveries.
- [x] Authenticated `POST /v1/manual/mints` analysis-only API with canonical Solana validation, deterministic manual identity, duplicate reporting and fail-closed operator auth configuration.
- [x] Synthetic launchpad/DEX fixtures and replay contracts for all four protocol adapters with no credentials or provider SDK dependency.
- [x] Sprint 2.4 roadmap, provider/security documentation and Compose runtime smoke checks reconciled; live protocol acceptance remains isolated as `BLOCKED_EXTERNAL`.
- [x] Gate P2 keyless composition contract connecting Birdeye discovery to independent Helius enrichment with shared canonical token identity and separate provenance.
- [x] Sprint 3.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-1-token-security.md` and completed.
- [x] Provider-independent `TokenSecurityEvaluator` with deterministic mint/freeze authority hard gates, explicit `PASS`/`WARN`/`BLOCK`/`UNKNOWN` outcomes, reason codes, penalties, evidence references, confidence and config hash.
- [x] Helius Token-2022 normalization preserves extension names and reported/unreported state in the on-chain observation without coupling provider code to application policy.
- [x] Independent read-only `RugCheckRestAdapter` maps official report-summary risks into provider-neutral findings, keeps verification informational and applies shared bounded transport/error handling.
- [x] Redacted RugCheck fixtures, adapter/provider contracts, security composition tests, key-safe `make rugcheck-doctor`, safe environment placeholders and Compose smoke coverage.
- [x] Sprint 3.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-2-holder-graph.md` and completed.
- [x] Provider-independent holder concentration snapshots derive bounded top1/top5/top10 metrics with explicit freshness, nullable incomplete evidence and Decimal range validation.
- [x] Known creator, configured pool, SPL Token/Token-2022/associated-token program and system addresses are classified, audited and excluded from ownership concentration where appropriate.
- [x] Bounded creator/top-holder funding and transfer graphs aggregate duplicate evidence, retain first/last times, provenance/source references, confidence and deterministic reason codes.
- [x] Union-find wallet clustering produces explainable shared-funder/related-wallet components and concentration-after-clustering metrics without execution authority.
- [x] Synthetic wallet-graph fixtures, credential-free replay contracts and Compose safe-mode smoke coverage are committed and pass.
- [x] Sprint 3.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-3-flow-analysis.md` and completed.
- [x] Provider-independent liquidity snapshots derive current depth and signed change from bounded fresh market evidence with nullable/fail-closed quality states.
- [x] Optional application quote evidence evaluates token sellability and price impact while preserving quote freshness separately from unsupported evidence.
- [x] Bounded organic-flow analysis derives maker diversity, transaction/maker ratio, repeated-size, circular-flow and rapid-round-trip heuristics with deterministic penalties and reason codes.
- [x] Safe/suspicious flow fixtures, replay contracts, no-provider/execution-surface checks and Compose safe-mode coverage are committed and pass.
- [x] Sprint 4.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-1-wallet-tracking.md` and completed.
- [x] Provider-independent tracked-wallet registry validates canonical addresses, explicit labels/tiers, idempotent duplicates and bounded active entries without automatic tier promotion.
- [x] Watched-wallet BUY/SELL observations normalize aliases, preserve provenance and all event timestamps, deduplicate equivalent deliveries and reject unknown/conflicting activity.
- [x] Bounded FIFO position reconstruction records open quantity/cost basis, conservative realized PnL, unmatched sells, hold duration, token age at entry and rug exposure with nullable/non-fresh evidence states.
- [x] Synthetic registry/activity/risk fixtures, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 4.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-2-smart-wallet-score.md` and completed.
- [x] Versioned `SmartWalletScore` aggregates completed FIFO outcomes for win rate, realized PnL, median return, early-entry rate and rug avoidance with explicit component values.
- [x] Rolling-window scoring excludes old outcomes, marks future outcomes invalid, deduplicates replayed round trips and applies bounded explicit manipulation penalties.
- [x] Neutral shrinkage, sample/confidence thresholds and non-mutating Tier-A/Tier-B recommendations prevent tiny or non-fresh samples from becoming Tier A.
- [x] Synthetic score snapshots/penalties, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 4.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-3-confluence.md` and completed.
- [x] Provider-independent confluence analysis joins qualified wallet scores to fresh FIFO entry/exit evidence with bounded windows and no-lookahead handling.
- [x] Existing holder-graph relationships are unioned transitively, including intermediary nodes, so correlated wallets count as one independently evidenced actor cluster.
- [x] Explainable `ENTRY`, `EXIT`, `CONFLUENCE` and `DISTRIBUTION` events plus bounded `TokenSmartMoneyScore` components/penalties preserve timestamps, provenance, evidence and no-execution authority.
- [x] Synthetic correlated-wallet/stale-graph fixtures, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 5.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-1-social-provider.md` and completed.
- [x] Provider-independent `SocialMention` contract and read-only compliant social/X adapter normalize post/author identity, UTC timestamps, bounded metrics, mint/ticker/link references and provenance.
- [x] Exact duplicate source IDs are idempotently collapsed; URL/mention-insensitive text fingerprints identify copied-text clusters and conflicting duplicate IDs fail closed.
- [x] Key-safe `make social-doctor`, redacted social replay fixtures, deterministic contract/unit tests and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 5.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-2-author-trust-social-velocity.md` and completed.
- [x] Explicit `SocialAuthorRegistry` trusted/KOL/blocked configuration resolves author tiers without automatic promotion or follower-count trust inference.
- [x] Provider-independent `AuthorTrustScore` and `SocialVelocityScore` calculate 1m/5m/15m mention and unique-author windows, engagement quality, duplicate/spam/coordination ratios, bounded confidence, reason codes and replay evidence.
- [x] Copied-text coordination and named bot-like burst heuristics remain advisory diagnostics; future/stale/invalid/conflicted critical evidence fails closed, fixtures/contracts/smoke pass and no result has execution authority.

## Current sprint progress

- Sprint 1.3 plan recorded in `docs/superpowers/plans/2026-08-27-phase-1-sprint-1-3-event-processing.md` and completed.
- Gate P1 evidence: deterministic domain/dispatcher tests, three Postgres outbox integration tests, persisted processor delivery, lease recovery/dead-letter behavior and synthetic candidate lifecycle replay all pass.
- Sprint 2.1 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-1-provider-framework.md` and completed.
- Sprint 2.1 gate evidence: all documented provider ports are typed and async; keyless transport, health, fixture/fake and normalized adapter contract tests pass; API/worker runtime imports pass in rebuilt Compose images.
- Sprint 2.2 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-2-helius-solana-read-layer.md`.
- Sprint 2.2 gate evidence: Helius unit/stream/doctor and fixture contract tests pass; full repository quality gates pass; rebuilt API/worker images import the Helius adapter and stream seam while retaining all four safe modes.
- Sprint 2.3 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-3-birdeye-dex-market-layer.md`.
- Sprint 2.3 implementation checkpoint: adapter, stream/poll fallback, reconciliation, fixtures, doctor and smoke/runtime contracts are complete and pushed in coherent checkpoints.
- Sprint 2.3 gate evidence: full backend/frontend/Compose quality gates pass; keyless Birdeye fixture and doctor contracts pass; rebuilt API/worker images import the Birdeye adapter and fallback seam while retaining all four safe modes.
- Sprint 2.4 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-4-launchpad-dex-coverage.md` and completed.
- Sprint 2.4 gate evidence: protocol parser/identity tests, manual service/API tests, fixture contracts and runtime smoke checks pass; rebuilt API/worker images import all four protocol adapters and the manual API while retaining all four safe modes.
- Gate P2 keyless acceptance evidence: `tests/contract/test_phase2_gate.py` composes a Birdeye new-listing discovery fixture with an independent Helius token-enrichment fixture; both preserve the same canonical token UUID and separate provider provenance.
- Sprint 3.1 plan evidence: the implementation plan defines the provider-independent authority evaluator, independent RugCheck seam, key-safe doctor, fixture contracts, freshness/hard-gate tests, and final sprint quality gate.
- Sprint 3.1 gate evidence: Helius authority/Token-2022 normalization, deterministic token-security evaluation, RugCheck summary normalization, provider doctor classifications, keyless composition and safe-mode smoke checks pass; live RugCheck acceptance remains externally blocked without endpoint configuration.
- Sprint 3.2 plan evidence: the implementation plan defines bounded holder normalization, known-address classification, creator/top-holder graph traversal, union-find clustering, concentration-after-clustering, fixture replay and the synchronized keyless gate.
- Sprint 3.2 gate evidence: holder/graph unit tests, redacted fixture replay, canonical-address exclusion, repeated-edge aggregation, out-of-depth filtering, clustering and Compose safe-mode smoke contracts pass; no provider SDK or live execution path enters the application module.
- Sprint 3.3 plan evidence: the implementation plan defines bounded liquidity/depth snapshots, optional quote sellability, maker/trade heuristics, deterministic penalties, safe/suspicious fixture replay and the synchronized keyless gate.
- Sprint 3.3 gate evidence: liquidity change/depth, quote impact/sellability, maker diversity, repeated sizes, reciprocal flow, rapid round trips, score bounds, freshness states, fixture replay, source evidence and Compose runtime imports pass; `OrganicFlowScore.execution_eligible()` is explicitly non-authorizing.
- Sprint 4.1 plan evidence: the implementation plan defines explicit registry tiers, normalized wallet activity, duplicate/conflict handling, bounded FIFO reconstruction, nullable financial evidence, token age/hold/rug semantics, replay fixtures and the synchronized keyless gate.
- Sprint 4.1 gate evidence: registry/activity unit tests, FIFO partial-close and unmatched-sell tests, stale/future/missing-evidence tests, deterministic fixture replay, provider-independence checks and Compose safe-mode smoke/runtime imports pass; wallet snapshots have no execution authority.
- Sprint 4.2 plan evidence: the implementation plan defines versioned component aggregation, rolling-window/no-lookahead behavior, neutral shrinkage, explicit manipulation penalties, sample/confidence gates, tiny-sample Tier-A prevention, fixture replay and the synchronized keyless gate.
- Sprint 4.2 gate evidence: score unit tests, rolling/future/duplicate handling, nullable unknown metrics, threshold/recommendation tests, deterministic fixture replay, provider-independence checks and Compose safe-mode smoke/runtime imports pass; score results have no execution authority.
- Sprint 4.3 plan evidence: the implementation plan defines score/timestamp/event contracts, fresh graph clustering, independent entry/exit windows, confluence/distribution derivation, component scoring, fixture replay and fail-closed acceptance.
- Sprint 4.3 gate evidence: qualified-wallet entry/exit extraction, transitive correlated-wallet deduplication, missing/stale graph withholding, future-activity invalidation, deterministic event replay, component/penalty explanations, provider-independence and Compose safe-mode/runtime imports pass; smart-money results have no execution authority.
- Sprint 5.1 plan evidence: the implementation plan defines the normalized social contract extension, compliant read-only adapter, mint/ticker/link extraction, metric/timestamp normalization, exact dedupe, copied-text clustering, redacted fixtures, key-safe doctor and final keyless gate.
- Sprint 5.1 gate evidence: social adapter/doctor unit tests, deterministic health/search fixture replay, credential-free contracts, conflicting-duplicate and unsafe URL handling, provider-independence checks and Compose safe-mode/runtime imports pass; social evidence remains advisory and has no execution authority.
- Sprint 5.2 plan evidence: the implementation plan defines explicit author registry/list policy, 1m/5m/15m velocity and unique-author windows, engagement quality, duplicate/spam/coordination penalties, trust/velocity scores with confidence, copied-text bot-like heuristics, fixtures, fail-closed evidence handling and the final quality gate.
- Sprint 5.2 gate evidence: deterministic author registry/scorer unit tests, redacted replay fixtures, future/stale fail-closed contracts, credential/provider-independence checks, safe-mode assertions and rebuilt Compose runtime imports pass; social intelligence remains advisory and has no execution authority.

## Verification evidence

All commands below were run in the current checkout on 2026-08-27.

- `.venv/bin/pytest tests/unit/test_event_processing.py tests/unit/test_telemetry.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q` — `18 passed` before the final synthetic replay/idempotency additions; the final full gate below includes those additions.
- `.venv/bin/pytest tests/unit/test_event_processing.py -q` — `7 passed`; dispatcher ordering/dedupe/conflict, synthetic candidate replay, retry/backoff, dead-letter redaction and worker cancellation pass.
- `MEMERADAR_TEST_DATABASE_URL`-configured `.venv/bin/pytest tests/integration/test_persistence_postgres.py -q` — `3 passed`; candidate persistence/idempotency conflict, lease recovery/dead-letter and transactional processor delivery pass.
- `make verify` — exit `0`; Ruff, mypy (`32 source files`), `97 passed, 3 skipped`, total branch-aware coverage `74%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_birdeye_doctor.py tests/unit/test_birdeye_normalization.py tests/unit/test_birdeye_stream.py tests/unit/test_birdeye_reconciliation.py tests/contract/test_birdeye_provider.py -q` — `21 passed`; Birdeye normalization, stream fallback/cancellation, reconciliation, fixture replay and doctor classifications pass keylessly.
- `make verify` after Sprint 2.3 — exit `0`; Ruff, mypy (`34 source files`), `119 passed, 3 skipped`, total branch-aware coverage `75%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_launchpad_dex.py tests/unit/test_launchpad_dex_identity.py tests/unit/test_manual_submission.py tests/unit/test_manual_api.py tests/contract/test_launchpad_dex_provider.py tests/smoke/test_compose_contract.py -q` — `36 passed`; Sprint 2.4 parser, identity, manual API, fixture and smoke contracts pass keylessly.
- `make verify` after Sprint 2.4 — exit `0`; Ruff, mypy (`37 source files`), `150 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make verify` after Gate P2 — exit `0`; Ruff, mypy (`37 source files`), `151 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_token_security.py tests/unit/test_helius_normalization.py -q` — `16 passed`; authority hard blocks, UNKNOWN/stale/conflicted freshness, Token-2022 extension handling, provider-advisory semantics and Helius normalization pass.
- `.venv/bin/pytest tests/unit/test_rugcheck.py -q` — `8 passed`; official summary-path mapping, severity normalization, verification information, bearer-header safety, schema rejection and classified transport failures pass.
- `.venv/bin/pytest tests/unit/test_rugcheck_doctor.py tests/contract/test_rugcheck_provider.py tests/contract/test_phase3_sprint3_1.py -q` — `10 passed`; optional-key `/ping` doctor behavior, redacted classifications, fixture replay and Helius+RugCheck composition pass.
- `.venv/bin/pytest tests/smoke/test_compose_contract.py -q` — `7 passed`; local topology, provider imports, RugCheck doctor wiring and all four protected modes pass.
- `make verify` after Sprint 3.1 — exit `0`; Ruff, mypy (`39 source files`), `180 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_holder_graph.py tests/contract/test_phase3_sprint3_2.py tests/smoke/test_compose_contract.py -q` — `16 passed`; holder normalization, address exclusion, freshness, bounded graph traversal, duplicate-edge aggregation, fixture replay, clustering and all-four-mode Compose smoke contracts pass.
- `make verify` after Sprint 3.2 — exit `0`; Ruff, mypy (`40 source files`), `189 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 3.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 3.2 — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 3.2 — exit `0`; holder-graph fixtures and documentation contain no tracked secret material.
- `.venv/bin/pytest tests/unit/test_flow_analysis.py tests/contract/test_phase3_sprint3_3.py tests/smoke/test_compose_contract.py -q` — `17 passed`; safe/suspicious fixture replay, liquidity/depth change, optional quote sellability/impact, maker-flow heuristics, score penalties, no-execution surface and protected modes pass.
- `make verify` after Sprint 3.3 — exit `0`; Ruff, mypy (`41 source files`), `198 passed, 3 skipped`, total branch-aware coverage `77%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 3.3 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 3.3 — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 3.3 — exit `0`; flow-analysis fixtures and documentation contain no tracked secret material.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 3.3 — exit `0`; rebuilt API/worker images include the flow-analysis module.
- Compose Sprint 3.3 runtime probes — worker `flow_worker_runtime_import_ok FlowAnalyzer 100`; API `flow_api_runtime_import_ok OrganicFlowScore`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy and web/worker were running.
- `.venv/bin/pytest tests/unit/test_wallet_tracking.py -q` — `7 passed`; registry identity/idempotency, aliases, FIFO matching, nullable PnL, token age, rug exposure, unmatched sells and freshness fail-closed behavior pass.
- `make lint typecheck` after Sprint 4.1 application work — exit `0`; Ruff passes and mypy reports `Success: no issues found in 42 source files`.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_1.py tests/smoke/test_compose_contract.py tests/unit/test_wallet_tracking.py -q` — `19 passed`; credential-free registry/activity/risk fixture replay, deterministic FIFO/rug reconstruction, provider-independence and all-four-mode Compose contracts pass.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 4.1 fixture wiring — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 4.1 fixture wiring — exit `0`; wallet-tracking fixtures and docs contain no tracked secret material.
- `make verify` after Sprint 4.1 — exit `0`; Ruff, mypy (`42 source files`), `208 passed, 3 skipped`, total branch-aware coverage `77%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.1 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.1 — exit `0`; rebuilt API/worker images include wallet-tracking code and both containers started.
- Compose Sprint 4.1 runtime probes — worker `wallet_tracking_worker_runtime_import_ok WalletTrackingAnalyzer 5000`; API `wallet_tracking_api_runtime_import_ok TrackedWalletRegistry WalletTrackingSnapshot`; both asserted all four protected mode values. Compose API was healthy, Postgres/Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_wallet_scoring.py -q` — `6 passed`; component aggregation, penalties, rolling-window duplicate/future handling, shrinkage, minimum sample/confidence and non-mutating tier recommendations pass.
- `make lint typecheck` after Sprint 4.2 application work — exit `0`; Ruff passes and mypy reports `Success: no issues found in 43 source files`.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_2.py tests/unit/test_wallet_scoring.py tests/smoke/test_compose_contract.py -q` — `19 passed`; credential-free score snapshot/penalty replay, deterministic decomposition, provider-independence and all-four-mode Compose contracts pass.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 4.2 fixture wiring — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 4.2 fixture wiring — exit `0`; wallet-scoring fixtures and docs contain no tracked secret material.
- `make verify` after Sprint 4.2 — exit `0`; Ruff, mypy (`43 source files`), `217 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.2 — exit `0`; rebuilt API/worker images include wallet scoring and both containers started.
- Compose Sprint 4.2 runtime probes — worker `wallet_scoring_worker_runtime_import_ok SmartWalletScorer smart-wallet-v1`; API `wallet_scoring_api_runtime_import_ok SmartWalletScore`; both asserted all four protected mode values. Compose API was healthy, Postgres/Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_confluence.py tests/contract/test_phase4_sprint4_3.py -q` — `6 passed`; qualification gates, transitive graph clustering, event derivation, component scoring, stale/missing graph handling and future-data invalidation pass.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_3.py tests/smoke/test_compose_contract.py -q` — `14 passed`; fresh/stale fixture replay, credential-free contract checks, provider-independent application seam and all four protected modes pass.
- `make lint typecheck secret-scan` after Sprint 4.3 — exit `0`; Ruff, mypy (`44 source files`) and tracked-file secret scan pass.
- `make verify` after Sprint 4.3 — exit `0`; Ruff, mypy (`44 source files`), `224 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.3 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make provider-doctor` after Sprint 4.3 — exit `2` as expected; Helius status is `BLOCKED_EXTERNAL` with `CONFIGURATION_MISSING`, network/auth/schema are `not_checked`, and no credential values are emitted.
- `docker compose -f infra/compose/docker-compose.yml config --quiet && .venv/bin/python scripts/check_migrations.py` after Sprint 4.3 — exit `0`; Compose config is valid and migration parity reports `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.3 — exit `0`; rebuilt API/worker images include confluence analysis and both containers started healthy/running.
- Compose Sprint 4.3 runtime probes — worker `confluence_worker_runtime_import_ok ConfluenceAnalyzer TokenSmartMoneyScore`; API `confluence_api_runtime_import_ok smart-money-confluence-v1 CONFLUENCE`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_social.py tests/unit/test_social_doctor.py tests/contract/test_social_provider.py tests/smoke/test_compose_contract.py -q` — `23 passed`; social normalization, extraction, copied-text clustering, duplicate conflict handling, unsafe URL/transport classification, doctor redaction/classification, fixture replay, provider independence and all four protected modes pass.
- `make lint` — exit `0`; Ruff passed for all applications, packages, tests and scripts.
- `make typecheck` — exit `0`; mypy reported `Success: no issues found in 45 source files`.
- `.venv/bin/python scripts/secret_scan.py` — exit `0`; social adapter, doctor, fixtures and documentation contain no tracked secret material.
- `make verify` after Sprint 5.1 — exit `0`; Ruff, mypy (`45 source files`), `235 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_helius_normalization.py::test_malformed_rpc_response_is_a_classified_schema_failure -q` — `1 passed`; the synthetic `NOW` clock is injected so the test deterministically reaches schema classification instead of expiring against the host clock.
- `.venv/bin/pytest tests/unit/test_social_intelligence.py tests/contract/test_phase5_sprint5_2.py tests/smoke/test_compose_contract.py -q` — `21 passed`; registry/tier policy, trust and velocity replay, windows, metric quality, coordination/bot-like diagnostics, future/stale handling, provider independence, fixture determinism and protected modes pass.
- `make verify` after Sprint 5.2 — exit `0`; Ruff, mypy (`46 source files`), `243 passed, 3 skipped`, total branch-aware coverage `79%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 5.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make social-doctor` with no social configuration after Sprint 5.2 — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, configuration presence only, all four protected modes and no credential values.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 5.2 — exit `0`; Compose topology and protected service modes remain valid.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 5.2 — exit `0`; rebuilt API/worker images include the social intelligence module and both containers started.
- Compose Sprint 5.2 runtime probes — worker `social_intelligence_worker_runtime_import_ok AuthorTrustScorer SocialVelocityScorer`; API `social_intelligence_api_runtime_import_ok AuthorTrustScorer SocialVelocityScorer`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `./.venv/bin/python scripts/secret_scan.py` after Sprint 5.2 — exit `0`; social intelligence fixtures, code and documentation contain no tracked secret material.
- `./.venv/bin/python scripts/check_migrations.py` after Sprint 5.2 — exit `0`; `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `make doctor` after Sprint 5.1 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make social-doctor` with no social configuration — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, configuration presence only, all four protected modes and no credential values.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 5.1 — exit `0`; Compose topology and protected service modes remain valid.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 5.1 — exit `0`; rebuilt API/worker images include the social adapter and both containers started.
- Compose Sprint 5.1 runtime probes — worker `social_worker_runtime_import_ok SocialRestAdapter social-search-v1`; API `social_api_runtime_import_ok social /v1/search`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/contract/test_phase2_gate.py -q` — `1 passed`; keyless discovery/enrichment composition is deterministic and provider-independent at the application boundary.
- `.venv/bin/mypy` — `Success: no issues found in 32 source files`.
- `.venv/bin/pytest tests/unit/test_provider_contracts.py tests/unit/test_provider_transport.py tests/unit/test_provider_health.py tests/unit/test_provider_fixtures.py tests/contract/test_provider_adapters.py -q` — `23 passed`; provider ports, resilience, health/freshness/quota, redaction/fakes and normalized adapter contracts pass.
- `.venv/bin/mypy` after the provider package was included in the configured source roots — `Success: no issues found in 30 source files`.
- `.venv/bin/pytest tests/unit/test_helius_normalization.py tests/unit/test_helius_stream.py tests/unit/test_provider_doctor.py tests/contract/test_helius_provider.py -q` — `19 passed`; Helius normalization, stream/reconnect/cancellation, doctor classification and fixture replay contracts pass.
- `make lint typecheck secret-scan` after Sprint 2.2 — exit `0`; Ruff, mypy (`32 source files`) and tracked-file secret scan pass.
- `make provider-doctor` with no Helius configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with no credential values emitted.
- `make birdeye-doctor` with no Birdeye configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with `api_url`/`api_key` presence only and no credential values emitted.
- `make rugcheck-doctor` with no RugCheck configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with `api_url`/`api_key` presence only and no credential values emitted.
- `make doctor` — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and all four protected modes are reported safely.
- `./.venv/bin/pytest tests/smoke/test_compose_contract.py -q` — `6 passed`; Compose topology, safe modes, Helius, Birdeye, launchpad/DEX and manual API wiring pass.
- `alembic downgrade base && alembic upgrade head && alembic check` against local Compose Postgres — exit `0`; reversible migration cycle passed and `No new upgrade operations detected.`
- `scripts/check_migrations.py` — exit `0`; `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `make integration-test` with the local Compose Postgres URL — exit `0`; `3 passed`.
- `npm audit --omit=dev` — `found 0 vulnerabilities`.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` — exit `0`.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` — exit `0`; rebuilt API/worker images include the event-processing, persistence and telemetry packages.
- Compose runtime import probe — `worker_event_processing_import_ok`; application event processing, `SqlAlchemyOutboxStore` and structured event telemetry import in the worker image.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after provider packaging — exit `0`; API/worker images include `packages/providers/src`.
- Compose provider runtime probes — `provider_framework_import_ok 9` in worker and `provider_package_import_ok 0.1.0` in API; all nine provider capabilities import without credentials.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.2 — exit `0`; API/worker images rebuilt with Helius read/stream code.
- Compose Helius runtime probes — worker `helius_runtime_import_ok helius helius-stream-v1 True`; API `helius_api_runtime_import_ok helius helius`; both probes asserted all four safe-mode environment values.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.3 — exit `0`; API/worker images rebuilt with Birdeye adapter, stream fallback and reconciliation code.
- Compose Birdeye runtime probes — worker `birdeye_worker_runtime_import_ok birdeye birdeye-stream-v1`; API `birdeye_api_runtime_import_ok birdeye`; both probes asserted all four safe-mode environment values. Compose status reported API healthy, Postgres healthy, Redis healthy, web running and worker running.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 3.1 — exit `0`; API/worker images rebuilt with token-security, Helius extension and RugCheck modules.
- Compose Sprint 3.1 runtime probes — worker `phase3_worker_runtime_import_ok TokenSecurityEvaluator rugcheck`; API `phase3_api_runtime_import_ok token-security-v1 rugcheck`; both probes asserted all four safe-mode environment values. Compose API, Postgres and Redis were healthy; web and worker were running.
- `GET http://127.0.0.1:8000/health/live` — HTTP `200`, `{"status":"alive","service":"api","version":"0.1.0"}`; `GET /health/ready` — HTTP `200` with database and Redis reachable.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.4 — exit `0`; API/worker images rebuilt with launchpad/DEX adapters and manual submission service.
- Compose Sprint 2.4 runtime probes — worker `launchpad_worker_runtime_import_ok ['pump.fun', 'pumpswap', 'raydium', 'meteora']`; API `manual_api_runtime_import_ok /v1/manual/mints`; both probes asserted all four safe-mode environment values. A host probe returned `/health/live` HTTP `200` and unauthenticated manual submission HTTP `503` with `manual submission authentication is not configured`.
- Compose status — API healthy, Postgres healthy, Redis healthy, web running and worker running after the event-processing image rebuild.
- `GET http://127.0.0.1:8000/health/live` — `{"status":"alive","service":"api","version":"0.1.0"}`.
- `GET http://127.0.0.1:8000/health/ready` — HTTP `200`; database and Redis both reported `required: true, state: reachable` inside Compose.
- `GET http://127.0.0.1:3000` — page contains `MemeRadar`, `ANALYSIS ONLY` and `PAPER TRADING`.
- Worker log includes `worker_started`.
- API logs — structured JSON `request_completed` records include a generated correlation ID, HTTP method/path/status and duration.
- `make doctor` — safe modes reported, local dependencies `not_required` when no URLs are configured, external provider checks `not_run`.
- CI YAML parse check — `CI workflow parsed: 4 jobs`.

The worker container initially exited because `__main__.py` was missing. The failure was reproduced from container logs, covered by a regression test, fixed, rebuilt and reverified as running.

## External provider acceptance

- Phase 0 and Phase 1 provider acceptance: `NOT_APPLICABLE` — no provider credentials are required for the completed foundation/domain work.
- Sprint 2.1 keyless provider framework/fixture acceptance: `PASS` — contract tests and fake providers pass without external credentials.
- Sprint 2.2 Helius fixtures, normalization, stream seam and doctor contract acceptance: `PASS` — all keyless tests and redacted fixtures pass.
- Sprint 2.2 live Helius read-only acceptance: `BLOCKED_EXTERNAL` — `make provider-doctor` found both `HELIUS_RPC_URL` and `HELIUS_API_KEY` missing, so no live call was attempted and no live success is claimed.
- Sprint 2.3 Birdeye fixtures, normalization, stream fallback, reconciliation and doctor contract acceptance: `PASS` — synthetic/redacted fixtures, keyless adapter tests, doctor classifications and runtime imports pass.
- Sprint 2.3 live Birdeye read-only acceptance: `BLOCKED_EXTERNAL` — `make birdeye-doctor` found both `BIRDEYE_API_URL` and `BIRDEYE_API_KEY` missing, so no live call was attempted and no live success is claimed.
- Sprint 2.4 protocol fixture and manual API acceptance: `PASS` — all keyless parser, canonical identity, duplicate, fixture replay, API auth and runtime checks pass.
- Sprint 2.4 live Pump.fun/PumpSwap/Raydium/Meteora acceptance: `BLOCKED_EXTERNAL` — no live protocol endpoint/credential configuration is present, so no live call was attempted and no live success is claimed.
- Gate P2 keyless acceptance: `PASS` for normalized discovery/enrichment seams and deterministic fixtures; live read-only acceptance remains `BLOCKED_EXTERNAL` for missing provider access.
- Gate P2 overall live acceptance: `BLOCKED_EXTERNAL` — the required real provider calls could not be attempted without configured read-only endpoint/credential access; the keyless composition evidence is not substituted for live success.
- Sprint 3.1 Helius authority/Token-2022 and RugCheck fixture/contract acceptance: `PASS` — deterministic keyless evaluation, redacted fixtures, provider seam and doctor classifications pass.
- Sprint 3.1 live RugCheck read-only acceptance: `BLOCKED_EXTERNAL` — `make rugcheck-doctor` found `RUGCHECK_API_URL` missing; no live call was attempted and no live success is claimed.
- Sprint 3.2 holder concentration/wallet graph fixture and contract acceptance: `PASS` — deterministic normalized observations, bounded graph/cluster analysis, canonical-address exclusions and all protected modes pass without live credentials.
- Sprint 3.2 live holder/graph provider acceptance: `BLOCKED_EXTERNAL` — Helius and Birdeye endpoint/credential configuration remains absent; no live holder or wallet-graph call was attempted and no live-provider success is claimed.
- Sprint 3.3 liquidity/flow fixture and contract acceptance: `PASS` — deterministic safe/suspicious market, trade and quote replay, freshness behavior, penalties, reason codes and no-execution surface pass without live credentials.
- Sprint 3.3 live market/quote provider acceptance: `BLOCKED_EXTERNAL` — Birdeye and Jupiter endpoint/credential configuration is absent; no live liquidity, trade or quote call was attempted and no live-provider success is claimed.
- Sprint 4.1 wallet registry/activity/FIFO fixture and contract acceptance: `PASS` — deterministic tracked-wallet replay, duplicate delivery handling, partial FIFO close, unmatched sell, token-age/rug evidence and all protected modes pass without credentials.
- Sprint 4.1 live wallet activity/rug-outcome acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/risk provider endpoint or credential is available; no live wallet call was attempted and no live-provider success is claimed.
- Sprint 4.2 wallet-score fixture and contract acceptance: `PASS` — deterministic SmartWalletScore aggregation, rolling/future/duplicate handling, threshold gates, explicit penalties and all protected modes pass without credentials.
- Sprint 4.2 live wallet-history acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/provider endpoint or credential is available; no live wallet-history call was attempted and no live-provider success is claimed.
- Sprint 4.3 confluence fixture and contract acceptance: `PASS` — deterministic qualified-wallet entry/exit replay, transitive graph clustering, confluence/distribution events, token component score, stale/missing graph fail-closed behavior and all protected modes pass without credentials.
- Sprint 4.3 live wallet-history/graph acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/graph provider endpoint or credential is available; no live wallet-history/graph call was attempted and no live-provider success is claimed.
- Sprint 5.1 social/X fixture, adapter and doctor acceptance: `PASS` — deterministic credential-free health/search replay, normalization, extraction, dedupe, copied-text clustering, redaction and protected-mode contracts pass.
- Sprint 5.1 live social/X read-only acceptance: `BLOCKED_EXTERNAL` — `SOCIAL_API_URL` and `SOCIAL_API_KEY` are missing; `make social-doctor` did not attempt a live call and no live-provider success is claimed.
- Sprint 5.2 author trust/velocity fixture and contract acceptance: `PASS` — deterministic explicit registry policy, trust/velocity scores, 1m/5m/15m windows, quality/duplicate/spam/coordination diagnostics, fail-closed future/stale handling and protected-mode contracts pass without credentials or an LLM.
- Sprint 5.2 live social/X read-only acceptance: `BLOCKED_EXTERNAL` — `SOCIAL_API_URL` and `SOCIAL_API_KEY` remain missing; `make social-doctor` did not attempt a live call and no live-provider success is claimed.
- Birdeye, Jupiter and Telegram checks: `NOT_RUN`; no live-provider PASS is claimed.

## Blockers

- No current implementation blocker. Helius, Birdeye, Sprint 2.4 live protocol acceptance, the live portion of Gate P2, Sprint 3.1 live RugCheck acceptance, Sprint 3.2 live holder/graph acceptance, Sprint 3.3 live market/quote acceptance, Sprint 4.1 live wallet/rug acceptance, Sprint 4.2 live wallet-history acceptance, Sprint 4.3 live wallet-history/graph acceptance and Sprint 5.1/Sprint 5.2 live social/X acceptance remain externally blocked for missing endpoint/credential configuration; all keyless implementation and gate evidence is green. No live-provider success is claimed.
- The GitHub Actions workflow is committed but its hosted run result has not been independently observed in this session; local equivalents are green.

## Migration and schema state

- `packages/persistence` contains the provider-independent SQLAlchemy 2 async models, candidate/outbox repositories and explicit unit-of-work boundary.
- `infra/alembic/versions/0001_initial.py` creates the 13 core Phase 1 tables represented by the current metadata; `0002_outbox_processing.py` adds leased processing/dead-letter columns and indexes. Social, wallet, extended market, research and execution tables remain later roadmap extensions.
- Local Postgres upgrade/downgrade/upgrade, migration parity and repository integration checks pass. The API and worker images include the persistence and event-processing packages, but the current API/worker composition still does not write business state automatically.
- Sprint 4.1 remains a provider-independent warm-path application contract; no physical wallet migration is introduced. The existing future wallet tables remain the persistence target for a later roadmap task, and the current API/worker composition still does not write wallet business state automatically.
- Sprint 4.2 remains a provider-independent warm-path score contract; no physical wallet-performance migration is introduced. The existing future `wallet_performance_snapshots` table remains the persistence target for a later roadmap task, and scoring does not write business state automatically.
- Sprint 4.3 remains a provider-independent warm-path confluence contract; no physical smart-money migration is introduced. The logical `smart_money_confluence_snapshots` target remains for a later persistence task, and event/score analysis does not write business state automatically.
- Sprint 5.1 remains a provider-independent warm-path social contract; no physical social migration is introduced. The existing `social_authors`/`social_mentions` targets remain for a later persistence task, and social normalization does not write business state automatically.
- Sprint 5.2 remains a provider-independent warm-path social intelligence contract; no physical migration is introduced. Logical `author_trust_snapshots` and `social_velocity_snapshots` targets remain for a later persistence task, and trust/velocity scoring does not write business state automatically.

## Git state

- Intended branch: `main`.
- Latest pushed Sprint 2.2 checkpoint: `039bb06` (`docs: synchronize sprint 2.2 status`), including the Helius implementation, smoke/runtime checks and completion documentation.
- Latest pushed Sprint 2.3 implementation checkpoints: `d1bb83a` (adapter), `337e60d` (stream fallback), `38cb4de` (reconciliation), `f804011` (fixtures/contracts) and `68c96ed` (doctor).
- Latest pushed Sprint 2.3 gate/status documentation checkpoint: `2233125` (`docs: complete Sprint 2.3 Birdeye checkpoint`); this status synchronization follows it.
- Latest pushed Sprint 2.4 checkpoints: `84eee38` (plan), `0261ac4` (protocol adapters and canonical identities), `680d009` (manual API), `6b2cab0` (protocol fixtures/contracts), and `ea5ae4e` (gate/documentation); this status synchronization follows the gate checkpoint.
- Latest pushed Gate P2 keyless contract checkpoint: `573bf6c` (`test: add Phase 2 gate composition`); latest pushed Gate P2 status checkpoint: `b774c54` (`docs: record Phase 2 gate status`); this status synchronization follows it.
- Latest pushed Sprint 3.1 plan checkpoint: `4ad685a` (`docs: refine Sprint 3.1 implementation plan`).
- Latest pushed Sprint 3.1 evaluator checkpoint: `6ec3ed7` (`feat: add fail-closed token security evaluation`).
- Latest pushed Sprint 3.1 RugCheck provider checkpoint: `8d13136` (`feat: add RugCheck risk provider seam`).
- Latest pushed Sprint 3.1 doctor/composition checkpoint: `e36c8e3` (`test: add RugCheck doctor and token security contracts`). The final Sprint 3.1 documentation/status synchronization follows this checkpoint.
- Latest pushed Sprint 3.1 documentation checkpoint: `3844c8b` (`docs: complete Sprint 3.1 token security checkpoint`). The status synchronization follows this checkpoint.
- Latest pushed Sprint 3.2 application checkpoint: `a355dd4` (`feat: add bounded holder concentration graph analysis`).
- Latest pushed Sprint 3.2 clustering correction: `5345f4a` (`fix: classify holder funding clusters`).
- Latest pushed Sprint 3.2 fixture/contract checkpoint: `f7590d0` (`test: add holder graph replay contracts`).
- Latest pushed Sprint 3.2 documentation checkpoint: `048d811` (`docs: complete Sprint 3.2 holder graph checkpoint`); this status synchronization records the exact keyless gate evidence above.
- Latest pushed Sprint 3.3 plan checkpoint: `659ebff` (`docs: plan Sprint 3.3 flow analysis`).
- Latest pushed Sprint 3.3 application checkpoint: `3957adb` (`feat: add liquidity and organic flow analysis`).
- Latest pushed Sprint 3.3 fixture/contract checkpoint: `95901ca` (`test: add organic flow replay contracts`).
- Latest pushed Sprint 3.3 documentation checkpoint: `609ca0e` (`docs: complete Sprint 3.3 flow analysis checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.1 plan checkpoint: `3126bd5` (`docs: plan Sprint 4.1 wallet tracking`); plan interface correction checkpoint: `6425f80` (`docs: clarify Sprint 4.1 plan interface`).
- Latest pushed Sprint 4.1 application checkpoint: `28bb0f7` (`feat: add conservative wallet tracking`).
- Latest pushed Sprint 4.1 fixture/contract checkpoint: `478cfe1` (`test: add wallet tracking replay contracts`).
- Latest pushed Sprint 4.1 documentation checkpoint: `51013a1` (`docs: complete Sprint 4.1 wallet tracking checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.2 plan checkpoint: `7172772` (`docs: plan Sprint 4.2 smart wallet score`).
- Latest pushed Sprint 4.2 application checkpoint: `8f644cb` (`feat: add versioned smart wallet scoring`).
- Latest pushed Sprint 4.2 fixture/contract checkpoint: `d281496` (`test: add smart wallet score replay contracts`).
- Latest pushed Sprint 4.2 documentation checkpoint: `79583d9` (`docs: complete Sprint 4.2 smart wallet score checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.3 plan checkpoint: `1393cca` (`docs: plan Sprint 4.3 confluence`).
- Latest pushed Sprint 4.3 application checkpoint: `b56b543` (`feat: add smart money confluence analysis`).
- Latest pushed Sprint 4.3 fixture/contract checkpoint: `dd8c367` (`test: add confluence replay contracts`).
- Latest pushed Sprint 4.3 documentation checkpoint: `f76b533` (`docs: complete Sprint 4.3 confluence checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 5.1 plan checkpoint: `dc30b36` (`docs: plan Sprint 5.1 social provider`).
- Latest pushed Sprint 5.1 application checkpoint: `1809c69` (`feat: add social provider read seam`).
- Latest pushed Sprint 5.1 fixture/contract checkpoint: `5fb3542` (`test: add social provider replay contracts`).
- Latest pushed Sprint 5.1 documentation checkpoint: `09efaa7` (`docs: complete Sprint 5.1 social checkpoint`).
- Latest pushed Sprint 5.1 status synchronization: `bb4d8e2` (`docs: synchronize Sprint 5.1 status`).
- Latest pushed Sprint 5.2 plan checkpoint: `1f01b07` (`docs: plan Sprint 5.2 social intelligence`).
- Latest pushed Sprint 5.2 application checkpoint: `13b4f01` (`feat: add social trust and velocity scoring`).
- Latest pushed Sprint 5.2 fixture/contract checkpoint: `92b62f0` (`test: add social intelligence replay contracts`).
- Latest pushed Sprint 5.2 deterministic test correction: `17818ed` (`test: freeze Helius schema test clock`).
- Latest pushed Sprint 5.2 documentation checkpoint: `f39d100` (`docs: complete Sprint 5.2 social intelligence checkpoint`).
- Sprint 5.2 status synchronization: pending this synchronization.

## Next task

Start `Phase 5 / Sprint 5.3 — Narrative LLM`: define provider-neutral `NarrativePort`; add strict structured output for narrative, novelty, organic-vs-promo evidence and sentiment uncertainty; add bounded cost/token budgets, caching and timeouts; ensure LLM outage never blocks deterministic analysis; and harden prompts against untrusted social-content injection. Preserve all four safety modes, keep LLM output visibly advisory, fail closed on critical UNKNOWN evidence and do not enable live-money execution.
