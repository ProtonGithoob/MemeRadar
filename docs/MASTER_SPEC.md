# MemeRadar Master Specification

## 1. Mission

Build an evidence-first Solana memecoin intelligence platform that can detect new opportunities early, correlate social and on-chain behavior, eliminate obvious rugs/manipulation, rank candidates transparently, learn from outcomes through replay/paper trading, and only later execute trades behind strict controls.

This specification is implementation authority together with `ARCHITECTURE.md`, `ROADMAP.md`, `DATA_MODEL.md`, `SCORING_AND_RISK.md`, `PROVIDERS.md`, `SECURITY.md`, `TESTING.md` and `STATUS.md`.

## 2. User outcomes

The operator should be able to:

- see newly discovered Solana tokens/pools almost immediately after supported providers observe them;
- know *why* a token is interesting or unsafe;
- inspect social velocity, source quality, smart-wallet participation, liquidity, holder concentration, creator behavior, flow quality and momentum;
- receive Telegram alerts only for meaningful state changes;
- inspect a chronological evidence timeline;
- paper-trade candidates with realistic fees/slippage;
- evaluate historical signal performance and calibrate thresholds;
- manually approve an execution only after explicit unlock;
- eventually enable narrowly constrained auto-execution with kill switches and limits.

## 3. Non-goals for initial releases

- guaranteed-profit prediction;
- blind copying of KOLs or wallets;
- MEV/front-running functionality;
- custody of user funds;
- arbitrary autonomous live-money execution;
- using LLM output as a hard buy/sell oracle;
- dependence on one data provider.

## 4. Domain lifecycle

Each candidate moves through an explicit state machine:

```text
DISCOVERED
  -> ENRICHING
  -> RISK_REJECTED | WATCH
  -> STRONG_SETUP
  -> ENTRY_READY
  -> PAPER_OPEN | LIVE_PENDING_APPROVAL
  -> OPEN
  -> EXIT_SIGNALLED
  -> CLOSED
```

Transitions must be idempotent and recorded with reason codes. A score alone must never silently mutate trading state.

## 5. Core engines

### Discovery Engine

Inputs may include:
- Helius/RPC streams;
- Birdeye new listing/pool streams;
- DEX/launchpad feeds;
- X/social mentions containing contract addresses, tickers or canonical links;
- manually submitted mint addresses.

Responsibilities:
- normalize Solana mint/pool identity;
- deduplicate candidates;
- attach provenance;
- start bounded enrichment jobs;
- reject malformed/non-Solana identifiers.

### Social Intelligence Engine

Responsibilities:
- extract mint/ticker/URL references;
- deduplicate copied/spam content;
- calculate mention velocity over windows;
- distinguish unique authors from repeated posts;
- maintain `AuthorTrustScore`/KOL tiers from evidence;
- calculate engagement quality and bot/spam heuristics;
- optionally use an LLM to summarize narrative/novelty/sentiment;
- preserve source URLs/IDs where policy permits.

LLM outputs are advisory features only.

### On-chain / Wallet Intelligence

Responsibilities:
- enrich mint authorities, token program, metadata and pool state;
- build holder concentration snapshots;
- trace creator/related-wallet funding relationships within bounded depth;
- identify suspicious clustering;
- track watched wallets and realized outcomes;
- derive SmartWalletScore from reproducible metrics;
- detect multi-wallet confluence.

### Risk Engine

Hard gates and penalties are defined in `SCORING_AND_RISK.md`. It must distinguish:
- SAFE-enough-to-continue;
- WARN;
- BLOCK;
- UNKNOWN/STALE.

UNKNOWN on a critical feature is fail-closed for live execution.

### Flow & Market Engine

Features include:
- liquidity and liquidity change;
- price/market cap where available;
- buys/sells volume by 1m/5m/15m windows;
- unique buyers/sellers;
- buy/sell ratio;
- trade-size distribution;
- transaction-to-maker ratio;
- repeat/circular-wallet heuristics;
- price impact / quote depth;
- momentum and volatility;
- drawdown from local peak.

### Alpha Scoring Engine

- deterministic and versioned;
- returns score 0..100, confidence, component scores, penalties and reason codes;
- stores the scoring model/version and all material input feature references;
- supports shadow versions for calibration without changing production decisions.

Initial weighting and thresholds are defined in `SCORING_AND_RISK.md` and are configurable, not hard-coded magic constants.

### Paper Trading Engine

Must simulate:
- quote price and slippage;
- network/priority/DEX fees;
- partial/failed fills where practical;
- entry/exit timestamps;
- stop loss, take profit and trailing logic;
- PnL and MFE/MAE;
- position sizing from configured paper bankroll.

Paper mode must use the same decision/risk interface as future live mode.

### Position / Exit Engine

Continuously evaluates open positions using:
- smart-money selling;
- creator/large-holder selling;
- liquidity decay;
- buy-velocity collapse;
- increasing sell pressure;
- score degradation;
- peak drawdown;
- explicit SL/TP/trailing rules;
- time-based expiry.

Every exit recommendation must be explainable.

### Execution Engine

Phase-gated. Jupiter is the primary planned Solana route/quote adapter.

Live execution requirements:
- independent mode flag and permission boundary;
- quote freshness check;
- max slippage and max price-impact checks;
- per-trade/per-token/daily exposure limits;
- duplicate-order prevention/idempotency key;
- balance reserve;
- priority-fee cap;
- kill switch;
- human approval in manual mode;
- signed transactions never logged with secret material;
- reconciliation of submitted signature to final chain status.

## 6. Alert model

Telegram-first alerts. Alerts are events, not raw logs.

Primary alert types:
- NEW_WATCH;
- STRONG_SETUP;
- ENTRY_READY;
- RISK_ESCALATION;
- CREATOR_SELL;
- SMART_MONEY_CONFLUENCE;
- EXIT_RISK;
- PAPER_ENTRY/PAPER_EXIT;
- PROVIDER_DEGRADED;
- SYSTEM_KILL_SWITCH.

Alert payload should contain:
- token symbol/name/mint;
- age and major market metrics;
- AlphaScore and delta;
- top positive evidence;
- top risk evidence;
- current state/action;
- dashboard deep link where configured.

Deduplicate and rate-limit alerts.

## 7. Operator web app

Initial pages:

1. **Radar** — ranked live candidates with filters and score/risk deltas.
2. **Token Detail** — metrics, holder/creator evidence, social narrative and evidence timeline.
3. **Smart Wallets** — tracked wallets, tier, realized PnL/win metrics and recent actions.
4. **Positions** — paper/live positions and exit evidence.
5. **Research** — backtests, score cohorts, threshold calibration and outcome labels.
6. **Providers** — health, quota/rate-limit and freshness status.
7. **Settings** — modes, thresholds, alert preferences and execution guardrails.
8. **Audit** — decisions, config changes and execution events.

UI must clearly distinguish real-time facts, derived scores, LLM summaries, paper data and live data.

## 8. Explainable evidence timeline

A first-class timeline is required. Example:

```text
17:01:03 candidate discovered via provider X
17:01:08 liquidity observed at $61k
17:01:14 Tier-A wallet bought 5.2 SOL
17:01:27 trusted social mention observed
17:02:03 unique buyers crossed configured threshold
17:02:11 social velocity increased 4.0x
17:02:26 critical risk checks passed
17:02:31 AlphaScore v1 = 71
17:03:10 second Tier-A wallet entered
17:03:12 AlphaScore v1 = 84
17:03:15 state -> ENTRY_READY
```

The exact values are examples, not fixed thresholds.

## 9. Configuration

All tunable thresholds live in validated config with source and version. Minimum groups:

- discovery;
- provider timeouts/retries/rate limits;
- evidence TTLs;
- risk hard gates;
- score weights;
- watch/strong/entry thresholds;
- paper bankroll/position sizing;
- live execution limits;
- alerts;
- LLM budget/provider/model;
- retention.

Config changes affecting decisions must be audit logged.

## 10. Data quality requirements

Every normalized external observation carries:
- provider;
- source identifier;
- occurred/observed/ingested timestamps where available;
- raw payload reference/hash;
- parser version;
- freshness/quality state.

Provider conflicts must be represented rather than silently overwritten.

## 11. Observability

Minimum:
- structured JSON logs with correlation IDs;
- metrics for discovery lag, enrichment latency, provider errors/rate limits, queue lag, candidates by state, score distribution, alert delivery, paper PnL and execution failures;
- tracing across ingestion -> decision -> alert/execution;
- provider doctor commands/endpoints;
- health/readiness checks that reflect dependencies honestly.

## 12. Performance targets

Targets are service-level objectives, not promises:
- internal ingestion/normalization p95 < 1s after provider event receipt;
- score recomputation p95 < 500ms once required features are available;
- idempotent event processing under duplicate/reordered delivery;
- dashboard API p95 < 500ms for normal indexed queries;
- bounded provider calls and explicit timeouts.

Measure before optimizing. No premature microservice split.

## 13. Retention and replay

Store enough raw/normalized observations to reconstruct a decision. Provide deterministic replay using recorded provider observations without network access. Historical datasets should support:
- forward-return labeling;
- MFE/MAE;
- rug/failure labeling;
- score-cohort analysis;
- threshold calibration;
- provider-feature ablation.

## 14. Acceptance philosophy

Progression to live features is controlled by evidence, not implementation completeness.

Minimum philosophy:
- keyless unit/contract/replay tests first;
- real provider read-only acceptance second;
- paper trading with statistically useful sample third;
- manual live execution in tiny size only after explicit approval;
- auto-execution only after further acceptance and an explicit operator decision.

See `ROADMAP.md` for exact phase gates.
