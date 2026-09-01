# MemeRadar

MemeRadar is a Solana memecoin intelligence, risk, paper-trading and eventually guarded execution platform.

The system is designed to discover newly emerging Solana tokens early, correlate social/X activity with on-chain evidence, reject unsafe or manipulated launches, rank opportunities with explainable scoring, simulate entries/exits, and only later enable tightly constrained manual or automated execution.

## Product principles

1. **Evidence before execution** — no trade is allowed from a single social or price signal.
2. **Deterministic risk gates** — LLM output can enrich narratives but cannot bypass hard safety rules.
3. **Explainability** — every score, alert, entry and exit must have an evidence timeline.
4. **Paper first** — real execution remains disabled until paper-trading acceptance gates pass.
5. **Provider abstraction** — Helius/Birdeye/DexScreener/Jupiter/X and other providers are adapters, not domain dependencies.
6. **Fail closed** — stale, missing or contradictory critical data blocks execution.
7. **Replayability** — raw/normalized events must support deterministic replay and backtesting.
8. **No secret material in git** — secrets are referenced through environment/secret-manager bindings only.

## Target pipeline

```text
Social / X ─────┐
Launchpads ─────┼─> Discovery -> Normalize -> Risk Gate -> Feature Engine
DEX feeds ──────┤                                      |
Helius/on-chain ┘                                      v
                                               Alpha Scoring
                                                    |
                                      ┌─────────────┴─────────────┐
                                      v                           v
                                    Reject                       Watch
                                                                  |
                                                          Entry Candidate
                                                                  |
                                                   Paper/Risk Manager
                                                                  |
                                                    Position Monitor
                                                                  |
                                                         Exit Engine
                                                                  |
                                                  Alerts / Execution
```

## Architecture

MemeRadar starts as a **modular monolith with event-driven workers**. Domain boundaries are explicit so hot paths can later be extracted into independent services without rewriting the core model.

Primary modules:

- `discovery` — new-token/new-pool/social candidate ingestion.
- `market` — price, liquidity, volume, trades and momentum normalization.
- `onchain` — Solana transaction/account enrichment and wallet relationships.
- `social` — X/KOL/narrative ingestion, deduplication and author trust.
- `risk` — authorities, holder concentration, clustering, liquidity/sellability and manipulation gates.
- `wallets` — smart-wallet profiles, realized performance and confluence.
- `features` — time-window features used by ranking and decisions.
- `scoring` — deterministic AlphaScore and confidence/reason codes.
- `paper` — simulated orders, fills, slippage, fees, position lifecycle and PnL.
- `positions` — live/paper position monitoring and exit signals.
- `execution` — guarded Jupiter quote/swap adapter; disabled by default.
- `alerts` — Telegram-first alert delivery with dedupe/rate limiting.
- `research` — replay, backtest, calibration and outcome labeling.
- `api` — authenticated read/control API.
- `web` — operator dashboard.

## Source of truth

Codex must read these files before implementation:

1. [`AGENTS.md`](AGENTS.md) — operating contract for autonomous implementation.
2. [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) — complete product and technical specification.
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — boundaries, data flow and deployment model.
4. [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases, sprints, tasks and acceptance gates.
5. [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — persistence/event schema.
6. [`docs/SCORING_AND_RISK.md`](docs/SCORING_AND_RISK.md) — scoring, risk and exit rules.
7. [`docs/PROVIDERS.md`](docs/PROVIDERS.md) — provider contracts and fallbacks.
8. [`docs/SECURITY.md`](docs/SECURITY.md) — security and execution controls.
9. [`docs/TESTING.md`](docs/TESTING.md) — test strategy and quality gates.
10. [`docs/STATUS.md`](docs/STATUS.md) — live implementation state and next task.

## Intended repository layout

```text
MemeRadar/
├── AGENTS.md
├── README.md
├── docs/
├── apps/
│   ├── api/                  # FastAPI composition/API surface
│   ├── worker/               # background/event workers
│   └── web/                  # Next.js operator UI
├── packages/
│   ├── domain/               # provider-independent business model
│   ├── application/          # use-cases/orchestration
│   ├── providers/            # Helius/Birdeye/X/Jupiter/etc adapters
│   ├── persistence/          # SQLAlchemy repositories/migrations
│   ├── telemetry/            # logs/metrics/traces
│   └── testkit/              # fixtures/fakes/replay helpers
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── replay/
│   └── e2e/
├── fixtures/
├── scripts/
├── infra/
│   ├── docker/
│   └── compose/
└── .github/workflows/
```

## Recommended baseline stack

- Python 3.13+
- FastAPI + Pydantic v2
- SQLAlchemy 2 + Alembic
- PostgreSQL 16+
- Redis for ephemeral coordination/rate limiting/queues where appropriate
- `asyncio`-first provider adapters
- Next.js + TypeScript for operator UI
- OpenTelemetry-compatible telemetry
- Docker Compose for local development
- `pytest`, `ruff`, `mypy`/`pyright`, frontend lint/typecheck/tests

Exact versions are to be pinned during Phase 0 after compatibility verification.

## Initial operating mode

```text
ANALYSIS_ONLY = true
PAPER_TRADING = true
MANUAL_EXECUTION = false
AUTO_EXECUTION = false
```

Real-money execution is out of scope until the roadmap explicitly unlocks it through acceptance gates.

The ultra-early detector and shadow-entry path are also analysis-only and
paper-only. `ENTRY_READY` may revalidate a quote and create a paper/shadow
record, but it cannot reach a signer or submit a transaction. The future
execution boundary is exposed as `LOCKED` in control-state diagnostics and
remains unavailable until a separate, explicit Phase 12 acceptance.

For bounded read-only provider acceptance, run `make early-live-doctor`.
Missing Helius/Birdeye access is reported as `BLOCKED_EXTERNAL`; synthetic
replay and latency benchmarks never establish live-provider or production-SLO
evidence.

## Codex start command

After cloning the repository, give Codex the prompt in [`CODEX_START_PROMPT.md`](CODEX_START_PROMPT.md). Codex should then execute the roadmap autonomously, update `docs/STATUS.md`, verify each increment, and sync coherent checkpoints to GitHub.
