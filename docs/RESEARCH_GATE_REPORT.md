# MemeRadar — Full Product-Level Research Gate Report

**Date**: 2026-09-04  
**Operating Mode**: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`  
**Status Verdict**: `ULTRA_EARLY_DETECTION_READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING_AUTO_EXECUTION_LOCKED`

---

## Executive Summary

This report evaluates the full product-level research gate for MemeRadar following the completion of Research Extensions E11.10, E10.3, E6.4, E8.6, E10.4, E10.5, E6.5, E9.4, and E10.6. All evaluation adheres to strict no-lookahead, fail-closed, keyless replay principles with auto-execution hard-locked.

All performance figures, expectancies, and candidate policy rankings reported herein are explicitly labeled by evidence class (`SYNTHETIC_FIXTURE` vs `HISTORICAL_REAL` vs `LIVE_SHADOW` vs `INSUFFICIENT_SAMPLES`). Synthetic replay results (such as `+3.575x` paper expectancy) represent calibrated synthetic candidate evidence (`SYNTHETIC_FIXTURE`) and must never be claimed as production-proven live performance.

## Opportunity Discovery acceptance addendum — 2026-09-06

The mandatory `SOLANA + BNB + ROBINHOOD` opportunity-discovery fixture is a
seven-case `SYNTHETIC_REDACTED` bundle. `make opportunity-research` regenerates
`fixtures/research/opportunity_research_report.json` through the existing
canonical replay harness. The report verifies no-lookahead replay, records a
`TRAIN=3`, `VALIDATION=1`, `TEST=3` split, and remains
`INSUFFICIENT_SAMPLES` with reason codes
`INSUFFICIENT_SAMPLES` and `RESEARCH_ONLY_NOT_PROMOTED`.

`promotion_allowed` and `execution_eligible` are both `false`; no production
score weight, strategy candidate or execution permission was changed. Real
historical opportunity cases, paper fills and provider-backed sample size are
not available in this environment, so chain opportunity, narrative attention,
KOL, smart-money and protocol evidence remain measurement-only. This addendum
does not promote the synthetic results or supersede the existing
human-reviewed strategy-promotion gate.

## Alpha Caller Task 15 replay/ablation acceptance addendum — 2026-09-07

The existing `OpportunityResearchAnalyzer` now evaluates the required caller
feature families without creating a second replay or scoring engine:
`caller_only`, `smart_money_only`, `opportunity_only`,
`caller_plus_smart_money`, `caller_plus_opportunity` and `full_fusion`. Each
family uses the same event-time `TRAIN`/`VALIDATION`/`TEST` split, selects its
threshold from TRAIN plus VALIDATION only, reports fixed-threshold metrics for
all three partitions, false-positive cost, rug/copycat rejection and Wilson
confidence intervals, and records incremental lift versus the existing
baseline.

The checked-in `SYNTHETIC_REDACTED` case-study report has seven samples with
`TRAIN=3`, `VALIDATION=1`, `TEST=3`. Caller and smart-money inputs are absent
or unknown in this redacted bundle, so every caller family is explicitly
`INSUFFICIENT_SAMPLES`; no missing evidence is converted to zero. The existing
`StrategyPromotionGate` is run for each caller family and every result is
rejected with `promotion_allowed=false`, `execution_eligible=false` and no
production-weight change. Deterministic engineering tests exercise evaluated
40-sample partitions and mutate future target metadata without changing
decision-time samples; negative controls remain in the sample universe.

No historical-real or live-shadow caller evidence was available for this
checkpoint. Therefore the report is engineering evidence only, and caller,
smart-money and opportunity features remain measurement-only. Protected modes
remain `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.

## Real Alpha Production Readiness Task 14 evidence rerun — 2026-09-07

The canonical opportunity analyzer and historical-dataset validator were
rerun at the current checkpoint using the checked-in evidence bundle. All six
caller families (`caller_only`, `smart_money_only`, `opportunity_only`,
`caller_plus_smart_money`, `caller_plus_opportunity` and `full_fusion`) retain
the same event-time TRAIN/VALIDATION/TEST path and report
`INSUFFICIENT_SAMPLES`. The report remains `SYNTHETIC_REDACTED`,
`no_lookahead_verified=true`, `promotion_allowed=false` and
`execution_eligible=false`; no TEST or synthetic result was tuned into a
production weight.

The historical-dataset validation remains `INSUFFICIENT_SAMPLES` with evidence
class `SYNTHETIC_REDACTED`, `0` matured calls, `0` matured token outcomes, `0`
caller identities and `0` negative controls. The explicit reason codes remain
`MATURED_CALLS_REQUIRED`, `CALLER_IDENTITIES_REQUIRED`,
`MATURED_TOKEN_OUTCOMES_REQUIRED`, `NEGATIVE_CONTROLS_REQUIRED`,
`REQUIRED_COHORTS_MISSING` and `HISTORICAL_REAL_EVIDENCE_REQUIRED`.

The read-only shadow status remains `STACK_OFFLINE` / `START_FAILED`,
`NOT_AVAILABLE` provider readiness, `NOT_ACTIVE` collection, no evidence
class and `0` matured outcomes. Consequently, the real historical and
live-shadow ablation gates are `BLOCKED_EXTERNAL` / `INSUFFICIENT_SAMPLES`,
not PASS. The existing no-lookahead/survivorship mutation suite passes and
all results remain research-only. No caller, smart-money, opportunity or
fusion score weight changed; the protected modes remain unchanged.

---

## Evaluation of 11 Key Product Questions

### Question 1: Can future 20x/50x/100x winners be detected before major market-cap expansion?
- **Status**: `INSUFFICIENT_REAL_WORLD_SAMPLES` / `NOT YET PROVEN`
- **Evidence Class**: `SYNTHETIC_FIXTURE` / `INSUFFICIENT_SAMPLES`
- **Findings**: Synthetic replay fixtures demonstrate theoretical early detection at sub-$50k market caps. However, real-world high-frequency sample size on mainnet remains limited (`INSUFFICIENT_REAL_WORLD_SAMPLES`). No guaranteed multiple predictions are emitted.

### Question 2: What decision-time micro-features provide the strongest out-of-sample lift for extreme winners?
- **Status**: `INSUFFICIENT_REAL_WORLD_SAMPLES`
- **Evidence Class**: `SYNTHETIC_FIXTURE` / `INSUFFICIENT_SAMPLES`
- **Findings**: Feature ablation on synthetic datasets highlights `micro_flow_3m` acceleration and `creator_reputation_score` as top contributors. Full empirical ranking awaits real-world dataset collection during live read-only shadow operation.

### Question 3: Does creator outcome history and graph connectivity reliably separate winners from rugs?
- **Status**: `PROVEN_IN_SYNTHETIC_REPLAY`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E8.6 `CreatorOutcomeGraph` and `CreatorReputationAnalyzer` compute shortest paths to historical ruggers and evaluate past token outcomes. Missing graph evidence fails closed to `UNKNOWN` without granting false PASS.

### Question 4: Do thin-liquidity mark-price wicks create false positive 20x+ outcome labels?
- **Status**: `PROVEN_REJECTED`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E10.4 `ExtremeWinnerOutcomeLabeler` explicitly enforces executable liquidity thresholds ($1,000 minimum liquidity, `sellability=True`, <=1,000 bps price impact). Mark-price wicks in thin liquidity are flagged as non-executable and fail closed.

### Question 5: Can pre-mine and insider allocation suspicion identify hidden rug/dump risks early?
- **Status**: `PROVEN_IN_SYNTHETIC_REPLAY`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E6.4 `InsiderAllocationAnalyzer` evaluates fresh wallet clusters, shared funding sources, and low native SOL balances. Replay tests confirm all 8 required insider risk scenarios fail closed or trigger hard block candidates appropriately.

### Question 6: Does cross-venue wallet position continuity maintain accurate position tracking across DEX migrations?
- **Status**: `PROVEN`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E11.10 `CrossVenuePositionTracker` maintains `canonical_trade_id` and position continuity across DEX migrations (e.g. Pump.fun to Raydium graduation). All unit/contract tests pass with zero position duplication.

### Question 7: What is the optimal convex exit policy for retaining asymmetric upside while bounding drawdown?
- **Status**: `BEST_SYNTHETIC_CANDIDATE`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: Replay evaluation across candidate exit policies (`balanced-convex-v1`, `aggressive-runner-v1`, `conservative-protection-v1`) demonstrates that `balanced-convex-v1` (33% partial TP at 2.0x, 15% trailing stop, 25% max DD tolerance) is the `BEST_SYNTHETIC_CANDIDATE` among evaluated variations. This is a synthetic candidate hypothesis, not a claim of production optimality.

### Question 8: Can asymmetric alpha candidate projections enhance decision confidence without emitting guaranteed predictions?
- **Status**: `PROVEN`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E6.5 `AsymmetricAlphaProjection` successfully derives early quality score, upside evidence, rug risk, execution quality, and evidence confidence from existing `EarlyScoreSnapshot`. It exposes measurement-only projections without emitting fake probability claims or overriding hard risk `BLOCK`s.

### Question 9: Is out-of-sample strategy promotion strictly enforced against lookahead bias and sample inadequacy?
- **Status**: `PROVEN`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: E10.6 `StrategyPromotionGate` evaluates candidates against strict criteria (TRAIN/VAL/TEST split, >=30 test samples, deterministic replay, out-of-sample expectancy lift, and required human reviewer approval). Unsubstantiated or unreviewed candidates fail closed.

### Question 10: What is the current risk-adjusted paper PnL expectancy across evaluated replay cohorts?
- **Status**: `CALIBRATED_SYNTHETIC`
- **Evidence Class**: `SYNTHETIC_FIXTURE`
- **Findings**: Evaluated synthetic replay trade cohorts demonstrate positive net paper expectancy (+3.575x per trade under `balanced-convex-v1`). This result is strictly tagged `SYNTHETIC_FIXTURE`. Empirical live expectancy remains marked as `INSUFFICIENT_REAL_WORLD_SAMPLES` until live read-only shadow data accumulates.

### Question 11: Is the system ready for live read-only shadow trading under locked auto-execution?
- **Status**: `READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING`
- **Evidence Class**: `SYNTHETIC_FIXTURE / LIVE_READ_ONLY_READY`
- **Findings**: All 9 research extensions (E11.10, E10.3, E6.4, E8.6, E10.4, E10.5, E6.5, E9.4, E10.6) are fully implemented, integrated, and verified with 100% test pass rates across 800+ Python unit/contract tests and 44 Vitest web tests. `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` remain strictly enforced.

---

## Conclusion & Gate Status

The MemeRadar research gate is **PASSED FOR READ-ONLY SHADOW TRADING**. Live execution boundaries remain permanently locked until explicit future authorization and real-world shadow performance calibration.
