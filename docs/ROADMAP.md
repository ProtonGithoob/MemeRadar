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

- [x] Configure ruff/formatter and static typing.
- [x] Configure pytest coverage structure.
- [x] Configure frontend lint/typecheck/unit tests.
- [x] Add GitHub Actions for backend, frontend, migration checks and secret scanning.
- [x] Add structured logging/correlation ID baseline.
- [x] Add configuration loader with validation and safe mode defaults.

**Gate P0:** `make verify` (or equivalent) passes keylessly in CI/local; modes default to analysis+paper only.

---

## Phase 1 — Domain Core and Persistence

**Goal:** provider-independent domain, data model and replayable decision primitives.

### Sprint 1.1 — Domain Model

- [x] Implement candidate/token/pool identities and lifecycle state machine.
- [x] Implement event envelope and reason-code model.
- [x] Implement observation provenance/freshness value objects.
- [x] Implement feature snapshot model.
- [x] Implement risk assessment, score snapshot, alert and position models.
- [x] Unit-test valid/invalid state transitions and idempotency.

### Sprint 1.2 — Persistence

- [x] Implement SQLAlchemy models/repositories/UoW.
- [x] Add initial Alembic migration for entities in `DATA_MODEL.md`.
- [x] Add unique/idempotency constraints and indexes.
- [x] Implement outbox table/publisher abstraction.
- [x] Add repository integration tests against Postgres.
- [x] Add migration upgrade/downgrade smoke tests.

### Sprint 1.3 — Internal Event Processing

- [x] Implement event dispatcher/worker contract.
- [x] Implement persisted event/outbox processing with retries/dead-letter semantics.
- [x] Add duplicate and out-of-order event tests.
- [x] Add event-processing telemetry.

**Gate P1:** deterministic domain tests + Postgres integration + replay of a synthetic candidate lifecycle pass.

---

## Phase 2 — Provider Framework and Market Discovery

**Goal:** real read-only candidate discovery and normalized market/on-chain observations.

### Sprint 2.1 — Provider Framework

- [x] Define all provider ports in `PROVIDERS.md`.
- [x] Implement common HTTP/WebSocket timeout, retry, jitter, rate-limit and circuit-breaker primitives.
- [x] Implement provider health/quota/freshness model.
- [x] Implement fixture recorder/redactor and fake providers.
- [x] Add contract tests proving adapters map into normalized domain models.

### Sprint 2.2 — Helius / Solana Read Layer

- [x] Implement Helius/RPC adapter for token/account/transaction enrichment.
- [x] Add websocket/webhook seam for relevant Solana observations.
- [x] Normalize token program, mint/freeze authorities and transaction identity.
- [x] Implement provider doctor command.
- [x] Add fixture-based contract tests.
- [x] Run live read-only acceptance when credentials/network permit — `BLOCKED_EXTERNAL` in this checkout because Helius endpoint/key configuration is absent; no live-provider success is claimed.

### Sprint 2.3 — Birdeye / DEX Market Layer

- [x] Implement candidate/new-pool discovery adapter.
- [x] Implement price/liquidity/trade/volume/holder/security observations as supported.
- [x] Implement stream/poll fallback strategy.
- [x] Add data freshness and conflict handling.
- [x] Add provider doctor and fixture/live read-only acceptance — keyless fixtures/contracts pass; live Birdeye acceptance is `BLOCKED_EXTERNAL` when endpoint/key configuration is absent.

### Sprint 2.4 — Launchpad / DEX Coverage

- [x] Add parsers/adapters needed for Pump.fun/PumpSwap, Raydium and Meteora identities/events without coupling domain code to protocol payloads.
- [x] Add canonical token/pool mapping and duplicate detection.
- [x] Add manual mint submission API — authenticated, analysis-only and fail-closed when operator authentication is not configured.

**Gate P2:** at least one real discovery path + one independent enrichment path work read-only; keyless fixtures reproduce the same normalized outputs.

Current gate state: keyless normalized discovery/enrichment seams and deterministic fixtures pass, including `tests/contract/test_phase2_gate.py`; live read-only acceptance is `BLOCKED_EXTERNAL` in this checkout because provider endpoints/credentials are not configured.

---

## Phase 3 — Risk and Manipulation Intelligence

**Goal:** aggressively reject obviously unsafe or manipulated candidates before ranking.

### Sprint 3.1 — Authority / Token Security

- [x] Implement mint/freeze authority checks.
- [x] Handle Token-2022/security-relevant metadata when applicable.
- [x] Integrate RugCheck/security-provider seam without making it sole authority.
- [x] Implement verification status as informational, never endorsement.
- [x] Add hard-gate/UNKNOWN/freshness tests.

Sprint 3.1 keyless state: complete. Helius authority/Token-2022 normalization, provider-independent hard gates, RugCheck fixtures/adapter/doctor and freshness/UNKNOWN composition tests pass locally. Live RugCheck acceptance is `BLOCKED_EXTERNAL` when endpoint configuration is absent; no live-provider success is claimed.

### Sprint 3.2 — Holder Concentration / Wallet Graph

- [x] Snapshot top holders and concentration metrics.
- [x] Exclude/identify known pool/program/system addresses where appropriate.
- [x] Build bounded funding/transfer graph for creator/top holders.
- [x] Add cluster heuristics and concentration-after-clustering metrics.
- [x] Record explainable evidence edges.

Sprint 3.2 keyless state: complete. Bounded holder snapshots, known-address
classification, creator/top-holder transfer graphs, duplicate-edge evidence and
connected-wallet concentration replay deterministically from fixtures. Live
provider acceptance remains separate and is not claimed by this application
contract.

### Sprint 3.3 — Liquidity / Sellability / Wash Trading

- [x] Implement liquidity depth and liquidity-change checks.
- [x] Add quote-based sellability/price-impact checks where supported.
- [x] Implement unique-maker, transaction-maker ratio, repeated-size, circular-flow and rapid round-trip heuristics.
- [x] Produce `OrganicFlowScore` and reason codes.

Sprint 3.3 keyless state: complete. Liquidity/depth change, optional quote
sellability/impact, maker-diversity and wash-trading heuristics replay
deterministically from synthetic normalized observations. Live market/quote
provider acceptance remains separate and is not claimed by this application
contract.

**Gate P3:** curated safe/suspicious fixtures classify deterministically; critical UNKNOWN blocks execution eligibility.

Gate P3 keyless state: pass. Safe and suspicious flow fixtures classify
deterministically, missing/stale/invalid critical evidence remains non-fresh,
and the flow result has no execution authority. Live provider acceptance is
`BLOCKED_EXTERNAL` where endpoint/credential configuration is absent.

---

## Phase 4 — Smart Wallet Intelligence

**Goal:** identify wallets whose historical behavior adds useful, evidence-backed signal.

### Sprint 4.1 — Wallet Tracking

- [x] Create tracked-wallet registry and labels/tiers.
- [x] Ingest buys/sells for watched wallets.
- [x] Reconstruct realized positions/PnL conservatively.
- [x] Track token age at entry, hold duration and rug exposure.

Sprint 4.1 keyless state: complete. The bounded provider-independent registry,
activity normalizer and FIFO reconstruction replay deterministically from
credential-free fixtures. Unknown/stale/conflicted/invalid evidence remains
nullable or non-fresh, and the result has no execution authority. Live wallet
activity/rug-outcome acceptance remains `BLOCKED_EXTERNAL` without configured
read-only provider access.

### Sprint 4.2 — SmartWalletScore

- [x] Implement versioned wallet scoring from win rate, realized PnL, median return, early-entry rate, rug avoidance and manipulation penalties.
- [x] Define minimum sample/confidence thresholds.
- [x] Prevent tiny-sample wallets from becoming Tier A.
- [x] Add rolling-window recalculation.

Sprint 4.2 keyless state: complete. The versioned, neutral-shrunk
`SmartWalletScore` aggregates completed FIFO outcomes with deterministic
sample/confidence gates, duplicate suppression, future-data exclusion and
explicit manipulation penalties. Registry tiers remain unmodified and score
results cannot authorize execution. Live wallet-history acceptance remains
`BLOCKED_EXTERNAL` without configured read-only provider access.

### Sprint 4.3 — Confluence

- [x] Detect independent smart-wallet entries/exits.
- [x] Detect correlated/clustered wallets so one actor is not counted as many.
- [x] Emit confluence and distribution events.
- [x] Add token-level smart-money component score.

**Gate P4:** wallet score and confluence can be replayed from fixtures and explain every component.

Sprint 4.3 keyless state: complete. Fresh qualified wallet scores and FIFO
round trips replay independent entries/exits, transitive graph clusters,
confluence and distribution events, and a bounded token-level smart-money
component score. Missing/stale/future critical evidence fails closed and all
results remain advisory. Live wallet-history/graph acceptance remains
`BLOCKED_EXTERNAL` without configured read-only provider access.

---

## Phase 5 — Social / X Intelligence

**Goal:** use social activity as corroborating evidence, not an autonomous trading oracle.

### Sprint 5.1 — Social Provider Seam

- [x] Define compliant X/social ingestion adapter(s).
- [x] Extract mint addresses, tickers and canonical links.
- [x] Normalize post/author metrics and timestamps.
- [x] Implement dedupe and copied-text fingerprinting.
- [x] Add provider doctor and fixtures.

Sprint 5.1 keyless state: complete. The read-only social adapter, normalized
`SocialMention` contract, redacted deterministic replay fixtures, provider
doctor and contract/smoke tests pass without credentials or an LLM. Social
evidence remains corroborating/advisory, copied-text and conflicting-duplicate
handling is deterministic, and live social acceptance is
`BLOCKED_EXTERNAL` when endpoint/key configuration is absent.

### Sprint 5.2 — Author Trust and Social Velocity

- [x] Build author registry and configurable trusted/KOL lists.
- [x] Compute 1m/5m/15m mention velocity and unique-author counts.
- [x] Compute engagement-quality and duplicate/spam ratios.
- [x] Implement `AuthorTrustScore` and `SocialVelocityScore` with confidence.
- [x] Add coordinated-promotion/bot heuristics.

Sprint 5.2 keyless state: complete. Explicit author registry policy,
provider-independent trust and velocity scores, bounded engagement and
duplicate/spam metrics, copied-text coordination diagnostics, future/stale
fail-closed handling, redacted replay fixtures and deterministic contracts
pass without credentials or an LLM. Live social acceptance remains
`BLOCKED_EXTERNAL` when endpoint/key configuration is absent.

### Sprint 5.3 — Narrative LLM

- [x] Define provider-neutral `NarrativePort`.
- [x] Add strict structured-output schema.
- [x] Summarize narrative, novelty, organic-vs-promo evidence and sentiment uncertainty.
- [x] Add cost/token budgets, caching and timeouts.
- [x] Ensure LLM outage never blocks deterministic analysis.
- [x] Prompt-injection harden untrusted social content.

**Gate P5:** social features work without LLM; LLM results are visibly advisory and cannot bypass risk gates.

Sprint 5.3 keyless state: complete. The provider-neutral `NarrativePort`, strict
`NarrativeInput`/`NarrativeSnapshot` contracts, application `NarrativeAnalyzer`
gateway with prompt-injection sanitization, deterministic cache/budget/timeout
policy and fail-closed fallback, fixture/REST provider seams and the key-safe
`make narrative-doctor` pass without credentials or a live LLM. Narrative
output is advisory-only (`execution_eligible` is always false) and a missing,
timed-out, malformed or injection-tainted result degrades to an explicit
unavailable snapshot while deterministic analysis continues. Live narrative
provider acceptance is `BLOCKED_EXTERNAL` when `NARRATIVE_API_URL`/
`NARRATIVE_API_KEY` are not configured.

Gate P5 keyless state: pass. Deterministic social features (Sprints 5.1/5.2)
work with the narrative provider unavailable, narrative output is visibly
advisory and cannot clear hard risk gates or change operating modes. Live
narrative acceptance remains `BLOCKED_EXTERNAL` without a configured safe
read-only endpoint/credential.

---

## Phase 6 — Feature, Alpha Score and Decision Engine

**Goal:** create a versioned, explainable candidate ranking and transition engine.

### Sprint 6.1 — Feature Windows

Research extension E6.0 supplies the provider-independent, keyless correlation
seam for these windows and the launch micro-features. Research extension E6.1
now supplies the provider-independent, versioned AlphaStrategy and AlphaScore
v1 arithmetic seam. Research extension E6.2 now supplies an advisory,
provider-independent external-wallet cross-validation seam; it cannot replace
internal SmartWalletScore/graph authority or deterministic risk gates.
Feature-snapshot orchestration is complete for the keyless Sprint 6.1
acceptance. Core Sprint 6.2 now adds repository-backed AlphaScore
recomputation; decision-state wiring remains Sprint 6.3 work.

- [x] Implement 1m/5m/15m rolling feature aggregation.
- [x] Add market, liquidity, holder, wallet, social and momentum feature families.
- [x] Persist snapshots with provenance/freshness.
- [x] Prevent future-data leakage in replay.

### Sprint 6.2 — AlphaScore v1

- [x] Implement configurable component weights from `SCORING_AND_RISK.md`.
- [x] Implement penalties and hard blocks.
- [x] Return score, confidence, components, penalties and reason codes.
- [x] Persist model version/config hash.
- [x] Add golden fixtures and boundary tests.

Research extension E6.1 provides the keyless strategy arithmetic, golden
fixtures and explicit strategy identity used by this sprint. Core Sprint 6.2
now wires that strategy through deterministic repository-backed score
recomputation; candidate state transitions and decision hysteresis remain
Sprint 6.3 work.

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
