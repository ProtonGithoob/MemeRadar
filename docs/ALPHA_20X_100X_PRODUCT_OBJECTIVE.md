# MemeRadar — Early Asymmetric Alpha Product Objective

## North-star objective

MemeRadar exists to identify rare Solana memetokens with credible asymmetric upside **before** large repricing (including eventual 20x/50x/100x outcomes), reject rugs/manipulated launches early, produce a defensible paper/shadow entry while liquidity still permits entry, and protect/capture upside with an evidence-driven exit policy.

20x/50x/100x are **outcome labels, not promises or entry criteria**. The system must never predict a guaranteed multiple. Optimization is for risk-adjusted expected value and early capture of future extreme winners without materially increasing rug/dump exposure.

## Product loop

`DISCOVER -> VERIFY -> EARLY RISK -> ORGANIC FLOW -> CORROBORATE -> EARLY ENTRY DECISION -> SHADOW/PAPER POSITION -> CONTINUOUS EXIT MONITOR -> REALIZED PAPER PNL -> REPLAY/CALIBRATION`

Every new feature must measurably improve at least one of:

1. earlier first-seen / earlier decision;
2. winner recall, especially future 20x/50x/100x cohort recall;
3. rug/severe-dump rejection;
4. executable entry quality (liquidity, impact, drift, sellability);
5. exit capture / loss containment;
6. net risk-adjusted paper PnL.

Features that do not improve one of these objectives should not be promoted into production scoring.

## E10.4 — Extreme-winner outcome labels

Extend the existing no-lookahead replay/outcome model. For each candidate, derive future-only labels from the event-time decision anchor:

- `hit_2x`, `hit_5x`, `hit_10x`, `hit_20x`, `hit_50x`, `hit_100x`;
- `time_to_2x/5x/10x/20x/50x/100x`;
- market cap at first-seen, WATCH, EARLY_WATCH, STRONG_SETUP, HIGH_CONFLUENCE and ENTRY_READY;
- age at those states;
- MFE and MAE before each multiple;
- maximum executable multiple before liquidity failure;
- liquidity survival and sellability at each milestone;
- severe-dump/rug-before-multiple flags;
- peak market cap and time-to-peak;
- post-peak drawdown;
- shadow/paper realized multiple after fees, slippage and impact.

A mark-price wick in thin liquidity is not a valid 20x/50x/100x success. A milestone requires the repository's existing market/tape/liquidity integrity rules and must distinguish observed mark multiple from executable outcome.

## E10.5 — Early-winner separability study

Use existing replay/calibration infrastructure to answer: **what evidence was available before future extreme winners repriced?**

Compare future 20x/50x/100x cohorts against rugs, severe failures, ordinary winners and non-winners using only evidence available at each historical decision timestamp.

Candidate dimensions include existing features only unless ablation proves a missing feature is necessary:

- launch age and first-seen latency;
- 1s/5s/15s/30s/60s/3m micro-flow;
- unique independent buyers and actor-cluster-adjusted buyer growth;
- buy volume relative to liquidity/market-cap movement;
- sustained vs one-tick momentum;
- liquidity growth/depth/sellability/impact;
- creator/deployer history and creator outcome graph;
- funder/side-wallet/pre-mine/insider evidence;
- bundle/sniper concentration and retained supply;
- smart-wallet quality, independence and timing;
- KOL/social velocity and author historical quality;
- holder concentration/graph evolution;
- token lock/unlock evidence;
- Pump.fun lifecycle/bonding-curve/graduation/migration state;
- provider/source diversity, freshness and stream quality.

Required outputs:

- feature distributions by outcome cohort;
- incremental lift/ablation, not raw correlation alone;
- winner recall and rug rejection at each launch-age bucket;
- precision-recall curves for extreme-winner cohorts;
- false-positive cost;
- first detection age and market cap;
- sample counts/confidence intervals;
- explicit `INSUFFICIENT_SAMPLES` where appropriate.

Do not optimize on future TEST data. TRAIN proposes candidates, VALIDATION selects, TEST reports final out-of-sample performance.

## E6.5 — Asymmetric Alpha candidate projection

Do not create a second scoring engine. Extend the existing EarlyScore/AlphaStrategy output with a measurement-only `AsymmetricAlphaProjection` derived from existing evidence.

It should expose:

- `early_quality_score`;
- `upside_evidence_score`;
- `rug_dump_risk`;
- `execution_quality`;
- `evidence_confidence`;
- `launch_age_ms`;
- `market_cap_at_decision`;
- reason codes;
- strategy/config version.

This projection must **not** output `will_20x`, `will_50x`, `will_100x` or a fake probability without statistically calibrated evidence. If probability calibration is later justified, it must be cohort-specific, out-of-sample, sample-size-aware and allowed to return UNKNOWN.

ENTRY_READY remains governed by the existing deterministic risk/execution-quality gates. Extreme-upside evidence cannot override BLOCK/UNKNOWN critical risk.

## E9.4 — Convex exit / winner-retention research

The exit objective is not merely avoiding loss; it must test whether MemeRadar can retain exposure to rare extreme winners while systematically reducing downside.

Use paper/shadow only. Reuse the existing ExitRiskScore and position engine to compare versioned exit policies such as:

- hard invalidation/risk exit;
- liquidity/sellability emergency exit;
- creator/deployer distribution exit;
- smart-wallet distribution exit;
- partial de-risk after configurable milestones;
- trailing protection based on executable marks rather than thin-liquidity wicks;
- runner retention for high-confidence positions;
- time-based decay when expected follow-through fails.

Do not hard-code a universal take-profit ladder as production truth. Evaluate candidate policies through replay and out-of-sample paper/shadow evidence.

Required metrics:

- realized paper multiple;
- realized PnL after fees/slippage/impact;
- `exit_capture_ratio = realized_profit / executable_peak_profit` where defined;
- giveback from executable peak;
- max drawdown;
- profit factor;
- expectancy per trade and per 100 signals;
- fraction of 20x/50x/100x future winners exited before major expansion;
- fraction of severe failures exited before major drawdown.

## E10.6 — Strategy promotion gate

No threshold, weight, feature or exit policy may be promoted because it improves in-sample 20x/50x/100x recall alone.

Promotion requires:

- no-lookahead deterministic replay;
- adequate sample size;
- TRAIN/VALIDATION/TEST separation;
- improvement over current baseline on risk-adjusted paper expectancy;
- acceptable rug/severe-dump exposure;
- acceptable liquidity/execution feasibility;
- no material degradation in operational latency/reliability;
- explicit version/config hash;
- human-reviewed promotion record.

Primary product KPI hierarchy:

1. net paper/shadow expectancy after costs;
2. max drawdown / severe-loss rate;
3. extreme-winner recall (20x/50x/100x future cohorts);
4. first-detection age and market cap;
5. ENTRY_READY precision;
6. rug/severe-dump rejection;
7. exit capture ratio;
8. latency only where it changes executable outcomes.

## Dashboard requirements

Extend existing read-only surfaces rather than creating a second dashboard.

Radar/token/position views should be able to show, when available:

- first seen age and market cap;
- current EarlyScore/AlphaScore and confidence;
- asymmetric-alpha evidence breakdown;
- creator/funder historical outcomes;
- smart-wallet/KOL corroboration;
- launch/bundle/sniper/insider risk;
- liquidity/sellability/impact;
- shadow/paper entry and current executable PnL;
- future outcome labels only in replay/research views, never leaked into live scoring;
- strategy version and reason codes.

Research views should include cohort grids for 2x/5x/10x/20x/50x/100x and failure/rug cohorts.

## Explicit non-goals

- No promise of profit or guaranteed multiple.
- No LLM prediction of future price multiples used as trading authority.
- No automatic promotion of backtest winners.
- No new duplicate score, wallet engine, rug engine or dashboard.
- No live-money execution in this extension.
- No weakening of `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No optimizing latency, Rust or provider count unless it improves measured executable outcomes.

## Implementation order

Preserve the exact active task in `docs/STATUS.md`. After current Ultra-Early Tasks 11-13 and already-approved higher-priority continuity/replay work reach a safe checkpoint, integrate these extensions using existing primitives:

1. E10.4 extreme-winner labels;
2. E10.5 early-winner separability/ablation;
3. E6.5 AsymmetricAlphaProjection;
4. E9.4 convex exit/winner-retention research;
5. E10.6 out-of-sample strategy promotion gate;
6. UI/research projections after backend contracts stabilize.

The goal is not to maximize the number of alerts. The goal is to find rare high-upside candidates early enough to be executable, reject destructive launches, and retain enough of the upside in paper/shadow evidence to demonstrate positive risk-adjusted expectancy before any live-money phase is considered.
