# MemeRadar

MemeRadar is a Solana memecoin intelligence, risk, research, paper-trading, and live-shadow validation platform focused on one north-star objective:

> **Discover rare high-upside Solana memetokens as early as possible, reject rugs/manipulated launches, identify executable entries, and preserve asymmetric upside through disciplined exits.**

Future 20x/50x/100x outcomes are research labels and historical cohorts — never guaranteed predictions. The system optimizes for out-of-sample, risk-adjusted paper/shadow expectancy rather than alert count or synthetic backtest multiples.

## Current project status

The current source identity, actual test results, blockers and next action are
maintained only in [docs/STATUS.md](docs/STATUS.md). Historical results are linked
from that checkpoint; they are not current production acceptance.

The canonical path is discovery → normalized evidence → independent risk and
corroboration → alpha decision → paper observation → outcome maturation → validation.
See [architecture](docs/ARCHITECTURE.md) and the
[purpose/ownership audit](docs/reports/memeradar-purpose-refactor.md).

`REAL_WORLD_ALPHA_NOT_YET_PROVEN`; `PRODUCTION_READY=false`;
`PROD_READ_ONLY_NOT_ACCEPTED`. Analysis and paper remain enabled; manual/automatic
execution, CANARY and LIVE remain disabled. Current design is documented in
[apps/web/DESIGN.md](apps/web/DESIGN.md).

## Free-first provider architecture

MemeRadar is provider-independent and capability-based. The core application can
initialize with no paid API credentials: standard chain reads use the configured
Solana JSON-RPC endpoint (defaulting to the rate-limited public endpoint), market
snapshots and paper reference quotes use the keyless DexScreener public API, and
wallet/risk analysis remains local and deterministic. Helius and Birdeye are
optional enhancements or bounded fallbacks, not core boot requirements.

| Capability | Free/default | Optional enhancement |
| --- | --- | --- |
| Solana RPC | Solana public RPC | Helius standard/enhanced RPC |
| Enhanced Solana metadata | unavailable/degraded | Helius |
| Transaction history | Standard Solana RPC where supported | Helius enrichment |
| Realtime stream | Explicit stream/backfill seam only | Helius stream |
| Market data and pair discovery | DexScreener | Birdeye |
| Paper quote | DexScreener market reference | Reviewed custom/Birdeye adapter |
| Risk | Local deterministic checks + public RugCheck where available | Authenticated RugCheck enrichment |
| Wallet intelligence | MemeRadar local tracking/scoring/graphs/flows | External wallet enrichment |
| Social metadata | DexScreener declared websites/social links | Existing compliant social provider |
| Social analytics | Unavailable without a configured provider | Existing social analytics provider |
| Narrative | Ollama when locally configured, otherwise disabled | Explicit external narrative provider |
| Alerts | Telegram when configured | — |

Provider-specific JSON is normalized at the adapter boundary. DexScreener is not
used as a substitute for transaction history, holder graphs, wallet history,
blockchain streaming, Helius DAS, security auditing or social search/firehose.
Missing analytics are `UNKNOWN`/unavailable rather than fabricated as zero.

The core/optional/full readiness tiers and the key-safe aggregate doctor are
documented in [`docs/PROVIDERS.md`](docs/PROVIDERS.md) and can be checked with:

```bash
make free-provider-doctor
python3 scripts/free_provider_doctor.py --no-network
```

## What has been implemented

### 1. Ultra-early Solana token discovery

The early-detection pipeline is designed to observe launches before ordinary screeners become useful. It supports normalized launch/market/on-chain observations, early decision bands, freshness semantics, and replayable evidence.

Canonical decision progression includes:

```text
DISCOVERED
   ↓
WATCH
   ↓
EARLY_WATCH
   ↓
STRONG_SETUP
   ↓
HIGH_CONFLUENCE
   ↓
ENTRY_READY
   ↓
PAPER POSITION
```

`ENTRY_READY` is not a buy command. It still requires deterministic risk, confidence, quote freshness, liquidity, sellability and bounded-impact gates.

### 2. Early scoring and asymmetric-alpha research

MemeRadar includes deterministic early scoring and a measurement-only `AsymmetricAlphaProjection` combining early quality, upside evidence, rug/dump risk, execution quality, confidence, launch age and decision market cap.

The projection cannot override critical `BLOCK`, stale, missing, or `UNKNOWN` evidence and does not emit guaranteed-multiple predictions.

### 3. 2x / 5x / 10x / 20x / 50x / 100x outcome research

`ExtremeWinnerOutcomeLabeler` records future executable outcome cohorts for replay/research, including:

- 2x, 5x, 10x, 20x, 50x and 100x hit labels;
- time-to-multiple;
- MFE and MAE;
- peak market cap;
- post-peak drawdown;
- market cap and token age at each early decision state;
- distinction between thin-liquidity mark-price wicks and liquid/executable multiples.

Future labels never enter live features. They exist only to answer whether early information could have separated future extreme winners from rugs, failures and ordinary tokens without look-ahead leakage.

### 4. Winner-vs-rug optimization

The `WinnerVsRugOptimizer` performs controlled grid-search research over early micro-features and evaluates precision/recall trade-offs using replay data. Thresholds are research candidates rather than hard-coded production truths.

### 5. Rug, manipulation and insider-risk detection

Risk analysis includes deterministic/fail-closed evidence for launch and holder anomalies, including:

- authority and token safety checks;
- holder concentration;
- liquidity/sellability/impact gates;
- creator/deployer relationships;
- shared funders;
- pre-mine/insider allocation suspicion;
- fresh-wallet and suspicious acquisition patterns;
- deployer self-activity and transfer deltas;
- launch sniper/bundle footprint;
- token lock/vesting/unlock evidence;
- sustained surge/revival validation;
- economic market-move/tape validation.

Missing critical evidence is `UNKNOWN`, never implicitly safe.

### 6. Smart-wallet and cross-venue continuity

Wallet intelligence tracks activity, venue, canonical trade identity and position continuity. `CrossVenuePositionTracker` handles transfer detection, bridge/cross-DEX migration and duplicate trade-ID idempotency so wallet/PnL history is not naively reset when activity moves across venues such as Pump.fun/PumpSwap or other DEX paths.

### 7. Wallet / creator outcome graph

The creator graph models creator, funder, wallet, token and cluster relationships and computes creator reputation from historical outcomes.

Implemented capabilities include:

- wallet graph lookup;
- token graph lookup;
- cluster lookup;
- shortest-path explanations;
- fresh-deployer cluster detection;
- creator/funder/token relationship evidence;
- date, venue, wallet-role, risk-outcome and evidence-quality filters;
- creator reputation with 20 audited metrics including winner/rug/dump rates, score/confidence, MFE/MAE, realized PnL, bundle/sniper risk and shared-funder recurrence.

Read API routes include:

```text
GET /v1/wallet-graph/wallets/{address}
GET /v1/wallet-graph/tokens/{mint}
GET /v1/wallet-graph/clusters/{cluster_id}
GET /v1/wallet-graph/shortest-path
```

The web application includes an interactive SVG node-link explorer with zoom, pan, fit-to-view, directional edges, node inspection and shortest-path highlighting.

### 8. Paper execution and position lifecycle

The platform supports simulated/paper entries and positions with fees/slippage/impact-aware research semantics. Browser-side live-order controls remain absent and signing/submission paths remain locked.

Paper/shadow metrics include open/closed position counts, measured realized/unrealized PnL coverage and explicit `UNKNOWN` handling when canonical PnL is unavailable.

### 9. Exit and winner-retention research

`ConvexExitEvaluator` compares versioned candidate exit policies using metrics such as:

- realized paper multiple;
- net PnL;
- executable peak multiple;
- exit capture ratio;
- giveback from peak;
- maximum drawdown;
- profit factor;
- expectancy per signal cohort;
- premature exit rate for future extreme-winner cohorts.

The current candidate dimensions also cover partial TP, trailing protection,
liquidity collapse, deployer/caller-linked distribution, smart-wallet
distribution and drawdown circuit breakers. `replay_candidates` uses the
existing `CalibrationTimeSplit`: selection is based on VALIDATION (TRAIN only
when validation is unavailable), while TEST is evaluated and reported without
affecting selection. Out-of-range/future records are excluded. Current exit
policies are research candidates only; synthetic replay winners are explicitly
labeled `BEST_SYNTHETIC_CANDIDATE`, not production-proven strategies.

### 10. No-lookahead research and strategy promotion

`ExtremeWinnerSeparabilityAnalyzer` evaluates whether early features separate future extreme winners from rugs/failures using TRAIN/VALIDATION/TEST splits and feature ablation.

`StrategyPromotionGate` requires deterministic replay, no-lookahead compliance, sample adequacy, out-of-sample evidence, risk/drawdown bounds, execution feasibility and explicit human review before any strategy can be promoted.

### 11. Evidence provenance

Research and operational outputs distinguish evidence classes such as:

```text
SYNTHETIC_FIXTURE
HISTORICAL_REAL
LIVE_SHADOW
INSUFFICIENT_SAMPLES
```

Synthetic replay is never represented as live-market proof. Runtime provenance includes run identity, collection window, provider state/version where known, parser/strategy/config versioning and git revision.

### 12. Live-shadow operational tooling

The repository includes safe tooling for real read-only observation:

```bash
make shadow-start
make shadow-status
```

`scripts/start-shadow.sh`:

- validates inherited operating modes fail-closed;
- explicitly exports protected modes;
- starts the local stack;
- establishes durable run identity;
- tracks `PENDING`, `ACTIVE`, `BLOCKED_EXTERNAL`, `START_FAILED`, and `CLOSED` lifecycle states;
- separates stack readiness from provider readiness;
- permits the free Solana RPC + DexScreener core to enter read-only shadow readiness;
- keeps optional Helius/Birdeye/full-provider acceptance separately visible.

`scripts/shadow_status.py`:

- traverses paginated API data using `next_cursor`;
- marks counts `EXACT`, `PARTIAL_TRUNCATED`, or `FAILED`;
- preserves `UNKNOWN != ZERO` semantics;
- reports provider states separately from provider versions;
- reports early decision-band counts and paper-position KPIs;
- tracks realized/unrealized PnL coverage;
- does not substitute audit-event counts for unmeasured alert metrics;
- emits structured provenance-aware JSON reports.

Operational classifications are intentionally explicit:

```text
STACK_OFFLINE
STACK_READY / BLOCKED_EXTERNAL
STACK_READY / DEGRADED
STACK_READY / LIVE_SHADOW_COLLECTION_ACTIVE
```

Real-world alpha remains `NOT YET PROVEN` until sufficient live-shadow observations and matured outcomes exist.

### 13. Provider architecture and health

Provider integrations are isolated behind adapters rather than domain dependencies. The small composition layer builds bounded capability routes: configured Helius standard RPC falls back to generic Solana RPC, DexScreener is the default market/quote/metadata path with configured Birdeye as an optional fallback, local wallet/risk engines remain primary, and Ollama is advisory narrative enrichment with a disabled fallback. Existing Jupiter, Pump.fun and conditional Yellowstone/Shyft/Raydium seams remain separate.

Provider availability is never fabricated. Missing optional credentials are
`UNCONFIGURED_OPTIONAL`; network failures are `BLOCKED_EXTERNAL` or
`DEGRADED`; unsupported capabilities are explicit. Keyless tests, fixtures and
local analysis continue independently. No provider or narrative can authorize
execution, and the protected modes remain locked.

### 14. API and operator web application

The Next.js operator application already exposes surfaces for:

- Radar / ranked candidates;
- Ultra-Early intelligence;
- token research;
- wallet/creator graph;
- wallets;
- paper positions;
- provider status;
- operations;
- audit;
- settings.

The old 2026-09-04 frontend modernization proposal was explicitly reverted and
is retained only as history. Current frontend evidence and design decisions are
recorded in:

- [`apps/web/DESIGN.md`](apps/web/DESIGN.md)
- [`docs/FRONTEND_BACKEND_PARITY.md`](docs/FRONTEND_BACKEND_PARITY.md)
- [`docs/ui-redesign/README.md`](docs/ui-redesign/README.md)

The target is an operator-grade early-alpha workstation rather than a static status dashboard. The primary screen should make it possible to quickly answer: which token deserves attention now, how early it was detected, why it is interesting, what can invalidate it, whether entry is executable, what creator/smart-wallet evidence exists, and what the current paper/exit state is.

Current integrated workstation routes include:

```text
MemeRadar Workstation
├── Discover          /, /radar, /ultra-early
├── Investigate       /tokens/[tokenId], /wallets, /wallet-graph, /callers, /social-alpha
├── Validate          /pipeline, /missed-winners, /outcomes, /compare, /positions, /opportunities
└── Operate           /readiness, /providers, /services, /operations, /audit, /settings
```

The UI modernization must reuse existing read APIs and does not weaken the backend feature freeze or protected execution modes.

## Product principles

1. **Evidence before execution** — no trade decision from a single social, wallet or price signal.
2. **Early but executable** — detecting a token early is useful only when liquidity/sellability/impact make the opportunity actionable.
3. **Extreme-upside research without prediction claims** — 20x/50x/100x cohorts are outcome labels, not promises.
4. **Deterministic risk gates** — LLM output may enrich narratives but cannot bypass safety rules.
5. **Explainability** — scores, state transitions, entries and exits must retain evidence/reason codes.
6. **Paper/shadow first** — real execution remains locked until separately accepted.
7. **Provider abstraction** — external SDKs remain outside domain logic.
8. **Fail closed** — stale, missing, contradictory or unknown critical evidence cannot silently become safe.
9. **Replayability** — decisions must be reproducible against versioned observations/configuration.
10. **No look-ahead** — future outcome labels never leak into live scoring.
11. **UNKNOWN != ZERO** — absence of measurement is not a zero-valued measurement.
12. **No secrets in git** — credentials/private keys are never committed.

## End-to-end architecture

```text
X / Social ─────────┐
Pump.fun / Launches ├──> Discovery / Normalization
DEX / Market ───────┤            │
Solana / Helius ────┘            ▼
                           Correlation / Timeline
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        Holder/Creator        Smart Wallet          Market Flow
           Graphs              Intelligence          Features
              └────────────────────┼────────────────────┘
                                   ▼
                           Deterministic Risk
                                   │
                                   ▼
                       EarlyScore / AlphaStrategy
                                   │
                         Asymmetric Projection
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
               REJECT/WATCH                  ENTRY_READY
                                                  │
                                                  ▼
                                          Paper/Shadow Entry
                                                  │
                                                  ▼
                                         Position Monitoring
                                                  │
                                                  ▼
                                             Exit Risk
                                                  │
                                                  ▼
                                      Replay / Outcome Labels
                                                  │
                                                  ▼
                                  Calibration / Promotion Gate
```

## Repository architecture

MemeRadar uses a modular-monolith/event-driven architecture with explicit boundaries:

- `apps/api` — FastAPI composition and authenticated read/control surface.
- `apps/worker` — background/event processing.
- `apps/web` — Next.js/TypeScript operator workstation.
- `packages/domain` — provider-independent business model.
- `packages/application` — use cases, scoring, graphs, research and orchestration.
- `packages/providers` — external provider adapters.
- `packages/persistence` — SQLAlchemy persistence/read models/migrations.
- `packages/telemetry` — logs, metrics and traces.
- `packages/testkit` — deterministic fixtures/fakes/replay helpers.
- `tests` — unit, contract, integration, replay and E2E verification.
- `fixtures` — version-controlled synthetic/replay evidence.
- `artifacts/research/live-shadow` — non-version-controlled live-shadow operational datasets.
- `scripts` — doctors, research CLIs, start/status and operational utilities.
- `infra/compose` — local Docker Compose stack.

## Baseline technology stack

- Python 3.13+
- FastAPI + Pydantic v2
- SQLAlchemy 2 + Alembic
- PostgreSQL
- Redis
- asyncio-first provider adapters
- Next.js + TypeScript
- OpenTelemetry-compatible telemetry
- Docker Compose
- pytest
- Ruff
- Mypy
- Vitest
- Playwright

## Local ports

Current documented host-port convention:

| Service | Host port |
|---|---:|
| PostgreSQL | `55432` by default; local conflict handling may use documented override such as `55433` |
| Redis | `56379` |
| API | `18000` |
| Web | `13000` |

Always prefer the current Compose/env configuration and `docs/STATUS.md` over stale shell history when a local override is in use.

## Running the project

Use the repository scripts/Make targets rather than manually reproducing service commands where possible.

Typical local workflow:

```bash
git pull --ff-only
./scripts/start.sh
./scripts/status.sh
```

Stop the local stack without removing its PostgreSQL or Redis volumes:

```bash
./scripts/stop.sh
```

Equivalent Make targets are `make start`, `make status`, and `make stop`.

For safe live-shadow operation after configuring the core read-only provider path
(paid provider credentials are optional):

```bash
make shadow-start
make shadow-status
```

Provider/readiness doctors are documented in [`docs/LIVE_READONLY_CHECKLIST.md`](docs/LIVE_READONLY_CHECKLIST.md) and [`docs/LIVE_SHADOW_VALIDATION.md`](docs/LIVE_SHADOW_VALIDATION.md).

## Verification

The repository uses focused tests during implementation and a full repository gate at coherent checkpoints:

```bash
make verify
```

The gate includes, as applicable:

- Python unit/contract tests;
- Ruff lint;
- Mypy type checking;
- frontend Vitest tests;
- frontend lint/typecheck/build checks;
- Docker Compose validation;
- secret scanning;
- migration parity checks;
- security review;
- SBOM validation.

The latest verified status and exact test counts belong in [`docs/STATUS.md`](docs/STATUS.md), which is the canonical implementation ledger.

## Real-world validation protocol

Engineering completion is not proof of profitable alpha.

The next evidence phase is:

```text
Core read-only provider/runtime acceptance (paid enhancements separately)
        ↓
provider acceptance
        ↓
7-day operational live-shadow smoke
        ↓
30-day out-of-sample shadow collection
        ↓
mature outcome labeling
        ↓
20x/50x/100x separability analysis
        ↓
ENTRY_READY precision / rug rejection
        ↓
paper expectancy / drawdown / exit capture
        ↓
strategy promotion review
```

The key business question is not whether tests pass, but whether MemeRadar can repeatedly identify future extreme winners early enough for executable entry while controlling severe losses and retaining enough upside after exits.

## Source of truth

Agents should read `AGENTS.md` and then the startup sequence it defines. Use
[`docs/README.md`](docs/README.md) as a short index and
[`docs/STATUS.md`](docs/STATUS.md) as the current implementation ledger. The
latest recorded engineering report is
[`MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md`](docs/reports/MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md).

## Autonomous agent execution

For Codex/Antigravity continuation:

- [`CODEX_START_PROMPT.md`](CODEX_START_PROMPT.md) — general autonomous implementation contract.
- [`FRONTEND_EXECUTION_PROMPT.md`](FRONTEND_EXECUTION_PROMPT.md) — pointer to an archived, superseded prompt; do not execute it.

Agents should inspect the local branch and worktree, resume from the exact
unfinished task in `docs/STATUS.md`, preserve unrelated changes, and record
verification before making claims. Remote Git operations are not required by
this repository handoff.

Routine repository reads, edits, tests, local project services and safe git reconciliation are expected to proceed autonomously where the execution environment permits. Product/host security boundaries must never be weakened to bypass platform-enforced approvals.

## Safety boundary

MemeRadar is currently an intelligence/research/paper/shadow system, not a proven profitable live trading system.

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Phase 12 remains locked. No current roadmap work may enable wallet signing or live transaction submission merely because a token reaches `ENTRY_READY`.

---

For the exact latest commit-level implementation evidence, blockers and next task, see [`docs/STATUS.md`](docs/STATUS.md).
