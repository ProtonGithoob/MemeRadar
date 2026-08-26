# Roadmap — Phases, Sprints and Tasks

Status legend: `TODO`, `IN_PROGRESS`, `BLOCKED_EXTERNAL`, `DONE`.

Codex must execute this roadmap in order unless a task is externally blocked and another independent task can proceed. Update `docs/STATUS.md` after each sprint.

## Phase 0 — Repository and Engineering Foundation

**Goal:** reproducible local development, CI, contracts, safe defaults and an executable skeleton.

### Sprint 0.1 — Scaffold

- [x] Create Python workspace/package layout from README.
- [x] Create FastAPI app and worker entrypoints.
- [x] Create Next.js/TypeScript web app.
- [x] Add pinned dependency management and lockfiles.
- [x] Add `.env.example`, `.gitignore`, editor/tool configs.
- [x] Add Dockerfiles and local Docker Compose for API, worker, web, Postgres, Redis.
- [x] Add make/task commands: bootstrap, lint, typecheck, test, verify, up, down, migrate, doctor.
- [x] Implement `/health/live` and `/health/ready` with honest dependency state.

**Acceptance:** fresh clone can bootstrap locally; API/worker/web start; no secret required; smoke tests pass.

### Sprint 0.2 — Quality and CI

- [ ] Configure ruff/formatter and static typing.
- [ ] Configure pytest coverage structure.
- [ ] Configure frontend lint/typecheck/unit tests.
- [ ] Add GitHub Actions for backend, frontend, migration checks and secret scanning.
- [ ] Add structured logging/correlation ID baseline.
- [ ] Add configuration loader with validation and safe mode defaults.

**Gate P0:** `make verify` (or equivalent) passes keylessly in CI/local; modes default to analysis+paper only.

---

## Phase 1 — Domain Core and Persistence

**Goal:** provider-independent domain, data model and replayable decision primitives.

### Sprint 1.1 — Domain Model

- [ ] Implement candidate/token/pool identities and lifecycle state machine.
- [ ] Implement event envelope and reason-code model.
- [ ] Implement observation provenance/freshness value objects.
- [ ] Implement feature snapshot model.
- [ ] Implement risk assessment, score snapshot, alert and position models.
- [ ] Unit-test valid/invalid state transitions and idempotency.

### Sprint 1.2 — Persistence

- [ ] Implement SQLAlchemy models/repositories/UoW.
- [ ] Add initial Alembic migration for entities in `DATA_MODEL.md`.
- [ ] Add unique/idempotency constraints and indexes.
- [ ] Implement outbox table/publisher abstraction.
- [ ] Add repository integration tests against Postgres.
- [ ] Add migration upgrade/downgrade smoke tests.

### Sprint 1.3 — Internal Event Processing

- [ ] Implement event dispatcher/worker contract.
- [ ] Implement persisted event/outbox processing with retries/dead-letter semantics.
- [ ] Add duplicate and out-of-order event tests.
- [ ] Add event-processing telemetry.

**Gate P1:** deterministic domain tests + Postgres integration + replay of a synthetic candidate lifecycle pass.

---

## Phase 2 — Provider Framework and Market Discovery

**Goal:** real read-only candidate discovery and normalized market/on-chain observations.

### Sprint 2.1 — Provider Framework

- [ ] Define all provider ports in `PROVIDERS.md`.
- [ ] Implement common HTTP/WebSocket timeout, retry, jitter, rate-limit and circuit-breaker primitives.
- [ ] Implement provider health/quota/freshness model.
- [ ] Implement fixture recorder/redactor and fake providers.
- [ ] Add contract tests proving adapters map into normalized domain models.

### Sprint 2.2 — Helius / Solana Read Layer

- [ ] Implement Helius/RPC adapter for token/account/transaction enrichment.
- [ ] Add websocket/webhook seam for relevant Solana observations.
- [ ] Normalize token program, mint/freeze authorities and transaction identity.
- [ ] Implement provider doctor command.
- [ ] Add fixture-based contract tests.
- [ ] Run live read-only acceptance when credentials/network permit.

### Sprint 2.3 — Birdeye / DEX Market Layer

- [ ] Implement candidate/new-pool discovery adapter.
- [ ] Implement price/liquidity/trade/volume/holder/security observations as supported.
- [ ] Implement stream/poll fallback strategy.
- [ ] Add data freshness and conflict handling.
- [ ] Add provider doctor and fixture/live read-only acceptance.

### Sprint 2.4 — Launchpad / DEX Coverage

- [ ] Add parsers/adapters needed for Pump.fun/PumpSwap, Raydium and Meteora identities/events without coupling domain code to protocol payloads.
- [ ] Add canonical token/pool mapping and duplicate detection.
- [ ] Add manual mint submission API.

**Gate P2:** at least one real discovery path + one independent enrichment path work read-only; keyless fixtures reproduce the same normalized outputs.

---

## Phase 3 — Risk and Manipulation Intelligence

**Goal:** aggressively reject obviously unsafe or manipulated candidates before ranking.

### Sprint 3.1 — Authority / Token Security

- [ ] Implement mint/freeze authority checks.
- [ ] Handle Token-2022/security-relevant metadata when applicable.
- [ ] Integrate RugCheck/security-provider seam without making it sole authority.
- [ ] Implement verification status as informational, never endorsement.
- [ ] Add hard-gate/UNKNOWN/freshness tests.

### Sprint 3.2 — Holder Concentration / Wallet Graph

- [ ] Snapshot top holders and concentration metrics.
- [ ] Exclude/identify known pool/program/system addresses where appropriate.
- [ ] Build bounded funding/transfer graph for creator/top holders.
- [ ] Add cluster heuristics and concentration-after-clustering metrics.
- [ ] Record explainable evidence edges.

### Sprint 3.3 — Liquidity / Sellability / Wash Trading

- [ ] Implement liquidity depth and liquidity-change checks.
- [ ] Add quote-based sellability/price-impact checks where supported.
- [ ] Implement unique-maker, transaction-maker ratio, repeated-size, circular-flow and rapid round-trip heuristics.
- [ ] Produce `OrganicFlowScore` and reason codes.

**Gate P3:** curated safe/suspicious fixtures classify deterministically; critical UNKNOWN blocks execution eligibility.

---

## Phase 4 — Smart Wallet Intelligence

**Goal:** identify wallets whose historical behavior adds useful, evidence-backed signal.

### Sprint 4.1 — Wallet Tracking

- [ ] Create tracked-wallet registry and labels/tiers.
- [ ] Ingest buys/sells for watched wallets.
- [ ] Reconstruct realized positions/PnL conservatively.
- [ ] Track token age at entry, hold duration and rug exposure.

### Sprint 4.2 — SmartWalletScore

- [ ] Implement versioned wallet scoring from win rate, realized PnL, median return, early-entry rate, rug avoidance and manipulation penalties.
- [ ] Define minimum sample/confidence thresholds.
- [ ] Prevent tiny-sample wallets from becoming Tier A.
- [ ] Add rolling-window recalculation.

### Sprint 4.3 — Confluence

- [ ] Detect independent smart-wallet entries/exits.
- [ ] Detect correlated/clustered wallets so one actor is not counted as many.
- [ ] Emit confluence and distribution events.
- [ ] Add token-level smart-money component score.

**Gate P4:** wallet score and confluence can be replayed from fixtures and explain every component.

---

## Phase 5 — Social / X Intelligence

**Goal:** use social activity as corroborating evidence, not an autonomous trading oracle.

### Sprint 5.1 — Social Provider Seam

- [ ] Define compliant X/social ingestion adapter(s).
- [ ] Extract mint addresses, tickers and canonical links.
- [ ] Normalize post/author metrics and timestamps.
- [ ] Implement dedupe and copied-text fingerprinting.
- [ ] Add provider doctor and fixtures.

### Sprint 5.2 — Author Trust and Social Velocity

- [ ] Build author registry and configurable trusted/KOL lists.
- [ ] Compute 1m/5m/15m mention velocity and unique-author counts.
- [ ] Compute engagement-quality and duplicate/spam ratios.
- [ ] Implement `AuthorTrustScore` and `SocialVelocityScore` with confidence.
- [ ] Add coordinated-promotion/bot heuristics.

### Sprint 5.3 — Narrative LLM

- [ ] Define provider-neutral `NarrativePort`.
- [ ] Add strict structured-output schema.
- [ ] Summarize narrative, novelty, organic-vs-promo evidence and sentiment uncertainty.
- [ ] Add cost/token budgets, caching and timeouts.
- [ ] Ensure LLM outage never blocks deterministic analysis.
- [ ] Prompt-injection harden untrusted social content.

**Gate P5:** social features work without LLM; LLM results are visibly advisory and cannot bypass risk gates.

---

## Phase 6 — Feature, Alpha Score and Decision Engine

**Goal:** create a versioned, explainable candidate ranking and transition engine.

### Sprint 6.1 — Feature Windows

- [ ] Implement 1m/5m/15m rolling feature aggregation.
- [ ] Add market, liquidity, holder, wallet, social and momentum feature families.
- [ ] Persist snapshots with provenance/freshness.
- [ ] Prevent future-data leakage in replay.

### Sprint 6.2 — AlphaScore v1

- [ ] Implement configurable component weights from `SCORING_AND_RISK.md`.
- [ ] Implement penalties and hard blocks.
- [ ] Return score, confidence, components, penalties and reason codes.
- [ ] Persist model version/config hash.
- [ ] Add golden fixtures and boundary tests.

### Sprint 6.3 — Decision State Machine

- [ ] Map score+risk+confidence to WATCH/STRONG_SETUP/ENTRY_READY transitions.
- [ ] Add hysteresis/cooldowns to prevent alert thrash.
- [ ] Add score-delta and risk-escalation events.
- [ ] Implement full evidence timeline projection.

**Gate P6:** deterministic replay reproduces identical decisions from identical event log/config.

---

## Phase 7 — Telegram Alerts and Operator API

**Goal:** make intelligence operational before trading.

### Sprint 7.1 — Alert Pipeline

- [ ] Implement Telegram notification adapter.
- [ ] Implement outbox delivery, retries, dedupe and rate limiting.
- [ ] Render concise alerts with reasons and score delta.
- [ ] Add provider/system degradation alerts.

### Sprint 7.2 — Read API

- [ ] Candidate ranking/filter API.
- [ ] Token detail/timeline API.
- [ ] Wallet intelligence API.
- [ ] Provider health API.
- [ ] Audit/config read API.
- [ ] Cursor pagination and bounded query controls.

### Sprint 7.3 — Auth / Control API

- [ ] Implement operator auth/RBAC.
- [ ] Separate viewer/operator/admin/execution permissions.
- [ ] Add validated config mutation with audit events.
- [ ] Add emergency analysis/execution kill-switch controls.

**Gate P7:** analysis-only deployment can run continuously and deliver deduplicated explainable alerts.

---

## Phase 8 — Web Dashboard

**Goal:** operationally useful, real-time observability and investigation UI.

### Sprint 8.1 — Design System and Shell

- [ ] Responsive dark/light-capable operator shell.
- [ ] Reusable score/risk/freshness/status components.
- [ ] Real-time update transport with reconnect/degrade behavior.
- [ ] Explicit paper/live/advisory badges.

### Sprint 8.2 — Radar and Token Detail

- [ ] Ranked Radar table/cards and filters.
- [ ] Token detail overview.
- [ ] Evidence timeline.
- [ ] Market/liquidity/flow charts.
- [ ] Holder concentration/cluster visualization.
- [ ] Social/narrative panel with provenance.

### Sprint 8.3 — Wallets, Providers, Settings and Audit

- [ ] Smart-wallet leaderboard/detail.
- [ ] Provider health/quota/freshness panel.
- [ ] Settings with safe validation and permission gates.
- [ ] Audit event explorer.

**Gate P8:** all backend intelligence required for operation is visible and explainable in frontend; browser e2e passes.

---

## Phase 9 — Paper Trading and Exit Intelligence

**Goal:** validate whether signals produce useful outcomes before any real-money execution.

### Sprint 9.1 — Paper Execution

- [ ] Paper portfolio/cash ledger.
- [ ] Position sizing policy.
- [ ] Simulated quote/fill/slippage/fee model.
- [ ] Idempotent paper orders.
- [ ] Paper position lifecycle and reconciliation.

### Sprint 9.2 — Exit Engine

- [ ] Fixed SL/TP support.
- [ ] Trailing stop and break-even rules.
- [ ] Smart-money/creator distribution exit signals.
- [ ] Liquidity decay and flow-collapse exits.
- [ ] Score-degradation and time-based exits.
- [ ] Partial take-profit policy support.

### Sprint 9.3 — Position UI / Telegram

- [ ] Positions dashboard.
- [ ] Live MFE/MAE/PnL evidence.
- [ ] Exit-risk alerts and reason codes.
- [ ] Closed-trade explanation.

**Gate P9:** paper engine runs on real read-only market data, survives restarts, and reconciles positions deterministically.

---

## Phase 10 — Research, Backtesting and Calibration

**Goal:** replace intuition with measured evidence.

### Sprint 10.1 — Replay Harness

- [ ] Deterministic event replay CLI/job.
- [ ] Historical feature reconstruction without lookahead.
- [ ] Outcome labeling: forward returns, MFE, MAE, liquidity failure/rug labels.
- [ ] Reproducible dataset manifests.

### Sprint 10.2 — Backtesting

- [ ] Backtest signal and exit policies.
- [ ] Include realistic fee/slippage assumptions.
- [ ] Calculate precision, hit rate, expectancy, drawdown, profit factor and calibration by score bucket.
- [ ] Segment by launch venue, liquidity, token age, market regime and social/smart-wallet conditions.

### Sprint 10.3 — Score Calibration

- [ ] Feature ablation.
- [ ] Threshold/weight search with train/validation time splits.
- [ ] Compare candidate score versions in shadow mode.
- [ ] Require documented evidence before promoting score version.

**Gate P10:** a versioned research report demonstrates reproducible performance; no live trading unlocked merely because aggregate PnL is positive.

---

## Phase 11 — Production Analysis-Only Hardening

**Goal:** dependable 24/7 intelligence operation.

### Sprint 11.1 — Reliability

- [ ] Soak tests, disconnect/reconnect tests, provider rate-limit tests.
- [ ] Queue/outbox recovery and DB restart tests.
- [ ] Retention/partition/index review.
- [ ] Backup/restore runbook.

### Sprint 11.2 — Observability / Operations

- [ ] Metrics dashboards and alerts.
- [ ] Provider SLOs and degradation policy.
- [ ] Runbooks for provider outage, DB pressure, queue lag and alert failure.
- [ ] Cost/quota dashboard.

### Sprint 11.3 — Security Review

- [ ] Dependency/container scanning.
- [ ] Secret-scan verification.
- [ ] RBAC/auth/session review.
- [ ] LLM prompt-injection/data handling review.
- [ ] Threat model update.

**Gate P11:** `READY_FOR_PRODUCTION_ANALYSIS_ONLY` documented with evidence.

---

## Phase 12 — Manual Live Execution (Locked by Default)

**Prerequisite:** explicit operator decision plus P9-P11 acceptance evidence.

### Sprint 12.1 — Jupiter Quote/Execution Adapter

- [ ] Implement quote adapter with price-impact/slippage/freshness checks.
- [ ] Implement transaction build/sign/submit/reconcile seam.
- [ ] Keep signing secret isolated from analysis runtime.
- [ ] Add simulation/dry-run mode and fixture tests.

### Sprint 12.2 — Live Risk Manager

- [ ] Per-trade and total exposure caps.
- [ ] Daily loss cap.
- [ ] token/liquidity minimums.
- [ ] balance reserve and fee cap.
- [ ] duplicate-order prevention.
- [ ] circuit breakers and global kill switch.
- [ ] mandatory manual approval workflow.

### Sprint 12.3 — Tiny-Size Acceptance

- [ ] Operator explicitly enables manual mode.
- [ ] Run tiny-size controlled trades only.
- [ ] Verify quote->signature->confirmation->position reconciliation.
- [ ] Verify failure/retry/non-duplication paths.
- [ ] Produce acceptance report.

**Gate P12:** `READY_FOR_MANUAL_LIVE_ONLY`; auto execution remains false.

---

## Phase 13 — Guarded Auto Execution (Future / Explicit Approval Only)

Prerequisites include sufficient paper/manual sample, calibrated risk, reliability evidence and explicit user approval.

- [ ] Define eligible signal/risk/confidence envelope.
- [ ] Add low exposure caps and staged rollout.
- [ ] Add continuous drift/performance monitoring.
- [ ] Auto-disable on provider degradation, stale risk data, anomalous fill behavior, loss cap, calibration drift or reconciliation failure.
- [ ] Add canary execution mode.
- [ ] Produce go/no-go review.

**Gate P13:** never self-approved by Codex. Requires explicit operator authorization.

---

## Cross-cutting backlog

Execute where relevant, not as an isolated final cleanup:

- [ ] API schema/versioning and OpenAPI docs.
- [ ] Data retention/partition policies.
- [ ] Privacy and provider ToS compliance.
- [ ] Property/fuzz tests for scoring/state transitions.
- [ ] Benchmark hot-path processing.
- [ ] ADRs for material architecture decisions.
- [ ] SBOM/dependency audit.
- [ ] Disaster-recovery documentation.
- [ ] Multi-provider comparison/health routing.
- [ ] Optional future multi-chain abstraction only after Solana product fit is validated.
