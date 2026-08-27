# Scoring, Risk and Exit Policy

All values here are initial hypotheses to be calibrated by Phase 10. They must be configuration-driven and versioned.

## 1. Decision order

```text
critical freshness -> hard risk gates -> component features -> AlphaScore -> confidence -> state transition -> paper/live risk policy
```

A high score never overrides a hard block.

## 2. Initial AlphaScore v1

Raw weighted score:

```text
SmartMoney        25%
OnChainSafety     20%
LiquidityQuality  15%
OrganicFlow       15%
SocialVelocity    10%
HolderQuality     10%
Momentum           5%
```

Each component is normalized 0..100. Base score is weighted average. Penalties are then subtracted and result clamped 0..100.

Suggested state bands before calibration:
- 0–39: REJECT/LOW
- 40–59: WATCH
- 60–74: EARLY_WATCH
- 75–84: STRONG_SETUP
- 85–100: HIGH_CONFLUENCE / potential ENTRY_READY

`ENTRY_READY` additionally requires all execution-eligibility gates, minimum confidence, sufficient evidence freshness and configured liquidity/price-impact thresholds.

## 3. Confidence

Score confidence is separate from score magnitude. Inputs include:
- critical feature completeness;
- independent provider agreement;
- wallet sample quality;
- social-author sample quality;
- observation recency;
- market sample size.

A score of 90 at confidence 0.35 is not equivalent to 90 at 0.90.

## 4. Hard blocks

Exact threshold values belong in config. Initial hard-block classes:

- malformed/non-canonical mint;
- known malicious/blocked token/address evidence;
- freeze authority active when policy requires revocation;
- mint authority active where uncontrolled future minting is possible and policy disallows it;
- critical sellability failure;
- liquidity below execution minimum;
- price impact above hard maximum for intended size;
- extreme effective holder concentration;
- creator/related-wallet active dump beyond policy;
- explicit security-provider severe finding corroborated by on-chain evidence;
- critical evidence stale/unknown in LIVE mode;
- provider conflict that prevents safe sizing/execution;
- system/provider kill switch active.

Do not treat token verification as proof of investment safety.

### Sprint 3.1 token-security rules

The deterministic `TokenSecurityEvaluator` consumes provider-independent Helius observations and optional `RiskFinding` values:

- `ACTIVE` mint authority produces `MINT_AUTHORITY_ACTIVE` and a hard block with an initial `mint_authority` penalty of 30.
- `ACTIVE` freeze authority produces `FREEZE_AUTHORITY_ACTIVE` and a hard block with an initial `freeze_authority` penalty of 30.
- Missing or `UNKNOWN` authority evidence, invalid normalized authority data, unknown token programs, conflicts and expired fresh evidence produce `UNKNOWN` critical state and are never execution-eligible.
- `spl-token-2022` is retained as a distinct program. Extension names are preserved by the on-chain adapter; transfer hooks, permanent delegates and other security-relevant extensions are explicit warnings. Unreported extension metadata is also a warning and cannot act as an endorsement.
- RugCheck `BLOCK` findings are advisory until an independent deterministic on-chain corroboration exists. They cannot create a sole-authority hard block, and stale/unknown third-party findings do not convert missing on-chain evidence into safety.
- RugCheck verification is an informational `VERIFICATION_STATUS` reason only. It cannot raise confidence, clear a hard block or make an assessment execution-eligible.

The initial token-security assessment is versioned as `token-security-v1`, uses a five-minute critical-evidence TTL, records all provider/source references and config hash, and preserves `PASS`, `WARN`, `BLOCK` and `UNKNOWN` as distinct outcomes. `RiskAssessment.execution_eligible()` remains true only for a fresh explicit `PASS`; warnings, unknowns and stale evidence remain fail-closed.

### Sprint 3.2 holder and wallet-graph rules

`HolderGraphAnalyzer` consumes only normalized `market.holder_data` and
allow-listed transfer/funding observations. It derives Decimal `top1`, `top5`
and `top10` ratios from descending holder percentages, using a normalized
provider top-ten summary only when fewer than ten valid rows are present. Pool,
program and system addresses are identified by configured/public address
lists, recorded as exclusions and removed from ownership concentration. The
creator is labeled explicitly when supplied and is never silently treated as
an unrelated holder.

The graph is a bounded evidence view around creator/top-holder seeds. Its
default limits are one hop, 100 holder rows, 500 edges and 500 nodes. Duplicate
edges aggregate amounts and transfer counts while preserving first/last event
times, provenance-derived source IDs, confidence and reason codes. Union-find
components identify shared-funder and related-wallet clusters; the largest
component percentage is exposed as `clustered_top` and must never be lower
than the raw top-holder value. Example reason codes include
`KNOWN_ADDRESSES_EXCLUDED`, `DIRECT_FUNDING_EDGE`, `TRANSFER_EDGE` and
`SHARED_FUNDER_CLUSTER`.

Holder and graph evidence has a five-minute default TTL. Missing, stale,
conflicted, future-dated or invalid observations produce explicit quality
states and nullable metrics rather than fabricated concentration. These
snapshots are explainability inputs only: they cannot grant execution
authority, clear a token-security hard block or change any operating mode.

## 5. Initial penalties

Illustrative v1 penalty classes, calibrated later:
- active mint authority: up to -30 or hard block;
- active freeze authority: up to -30 or hard block;
- creator selling/distribution: up to -40 or hard block;
- suspicious holder/funding clustering: up to -25;
- strong wash-trading evidence: up to -20;
- sniper/bundle concentration: up to -15;
- coordinated/fake social evidence: up to -15;
- rapidly decaying liquidity: up to -25;
- severe provider disagreement/staleness: confidence reduction and possibly block.

Penalties require reason codes and evidence references.

## 6. Component definitions

### SmartMoney
Derived from independent tracked-wallet entries, wallet score/tier, entry timing, realized-history confidence and clustering independence. Prevent one operator controlling many wallets from multiplying the signal.

### OnChainSafety
Authorities, token-program/extension risks, creator behavior, security-provider findings, sellability and other chain evidence.

### LiquidityQuality
Absolute liquidity, liquidity/market-cap relation, quote depth, price impact, persistence and liquidity change. Raw liquidity alone is insufficient.

### OrganicFlow
Unique buyers/sellers, buy/sell volume, maker diversity, transaction/maker ratio, repeated trade-size patterns, circular flows and funding overlap.

### SocialVelocity
Unique-author mention acceleration, trusted-author quality, engagement quality, duplication/spam ratio and narrative novelty. Follower count alone must not dominate.

### HolderQuality
Top1/top5/top10 effective concentration after identifying pools, programs and system addresses, plus `clustered_top`, creator-related holdings and bounded funding/transfer relationships. Suspicious clustering is an evidence-backed penalty (up to -25), not an execution permission.

### Momentum
Multi-window return/volume acceleration adjusted for volatility and parabolic-extension risk. Pure price increase is not automatically positive.

## 7. SmartWalletScore v1

Inputs should include:
- realized win rate;
- realized PnL/return distribution;
- median return rather than only mean;
- early-entry rate;
- rug-avoidance rate;
- hold-duration behavior;
- sample count/recency;
- suspicious creator/funding relationship penalties;
- follower-dump / exit-liquidity behavior if measurable.

Apply Bayesian/shrinkage or another confidence method so tiny samples regress toward neutral. Tier A requires a configurable minimum sample and confidence.

## 8. Social trust

AuthorTrustScore should use evidence such as:
- historical token calls and forward outcomes where reconstructable;
- account/activity age and consistency;
- engagement quality;
- duplicate promotion behavior;
- deleted/changed-call handling where permitted;
- suspicious coordination;
- mint-address correctness;
- relation to creators/paid promotion if known.

Never infer trust from follower count alone.

## 9. ENTRY_READY policy

An initial candidate may become ENTRY_READY only if:
- no hard block;
- critical risk evidence fresh;
- AlphaScore >= configured entry threshold;
- confidence >= configured threshold;
- minimum token/pool age policy satisfied if enabled;
- minimum liquidity/quote depth satisfied;
- price impact/slippage within limits;
- organic-flow minimum satisfied;
- configured confluence requirement satisfied;
- no global/token cooldown/kill switch.

Paper mode may deliberately evaluate lower-score cohorts for research, but must label them distinctly.

## 10. Position sizing

Initial paper sizing should be conservative and configurable. Use risk-budget sizing rather than a fixed percentage solely because score is high. Inputs may include:
- bankroll;
- max risk per trade;
- stop distance;
- liquidity/price impact;
- score confidence;
- token age/volatility;
- concurrent exposure.

Live sizing remains disabled until Phase 12.

## 11. Exit engine

Exit signals are composable and versioned.

### Protective exits
- hard stop loss;
- max adverse move / quote degradation;
- liquidity collapse;
- critical risk change;
- creator dump;
- sellability deterioration;
- provider/data integrity failure in live mode when safe handling requires flattening or blocking new actions.

### Profit management
- configurable TP ladder;
- partial profit taking;
- break-even transition;
- trailing stop based on peak/high-water mark;
- optional volatility-aware trailing logic.

### Evidence exits
- Tier-A/independent smart wallets distributing;
- buy velocity collapsing;
- sell/buy ratio sharply worsening;
- unique buyer growth stalling;
- AlphaScore degradation across hysteresis threshold;
- social velocity collapse after extreme expansion;
- time stop / thesis expiry.

Do not exit solely because one noisy feature ticks down once. Use severity, persistence and hysteresis.

## 12. Explainability contract

Every risk/score/transition/exit result must include:
- version;
- timestamp;
- inputs or snapshot reference;
- component scores;
- penalties/hard blocks;
- reason codes;
- evidence references;
- confidence;
- config hash.

## 13. Calibration rules

- No lookahead leakage.
- Use time-based train/validation splits.
- Track performance by launch venue/liquidity/token age/regime.
- Prefer robust metrics (expectancy, drawdown, precision by score bucket) over cherry-picked wins.
- Keep previous score versions replayable.
- New model runs in shadow before promotion.
- Codex must never auto-promote a live trading model based solely on backtest performance.
