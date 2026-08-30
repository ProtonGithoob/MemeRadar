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

### Sprint 3.3 liquidity, sellability and organic-flow rules

`FlowAnalyzer` selects the latest matching normalized market snapshot and, when
available, compares it with the previous fresh snapshot. It exposes liquidity,
depth and signed liquidity-change ratios. Missing depth or prior evidence is
represented as a nullable metric with an explicit reason code; missing or
malformed liquidity evidence is `UNKNOWN` or `INVALID`, never zero-valued
evidence.

Trade-row evidence derives unique makers, transaction count, the non-negative
transaction-to-maker ratio, exact repeated-size participation, reciprocal
buyer/seller flow and maker-level rapid buy-then-sell round trips. When only a
provider summary is available, counts and buy/sell volumes may be retained but
row-level heuristics remain nullable and `TRADE_ROWS_MISSING` is recorded.

An optional application `QuoteSnapshot` evaluates token-to-quote sellability
and price impact. Missing or expired quotes retain a separate
`quote_quality_state`; they are not interpreted as a successful sellability
check. The initial deterministic penalty ceilings are: low liquidity 25,
shallow depth 15, liquidity decay 20, high price impact 20, failed sellability
25, transaction/maker concentration 15, repeated sizes 15, circular flow 20
and rapid round trip 15. The score is `max(0, 100 - sum(penalties))`, carries
all evidence references/reason codes, and is advisory only.

The default analysis TTL is five minutes with bounded market/trade rows and
size buckets. `FRESH`, `STALE`, `UNKNOWN`, `CONFLICTED` and `INVALID` remain
distinct; any non-fresh critical market/trade state yields a zero-confidence,
non-fresh advisory result and cannot make any execution path eligible.

### Sprint 4.1 wallet-tracking rules

`WalletTrackingAnalyzer` consumes only normalized, allow-listed wallet
activity and rug-outcome observations plus an explicit bounded tracked-wallet
registry. Registry labels and tiers are configuration/evidence, not a score
computed from the current activity batch; the analyzer never promotes a
wallet to Tier A and a blocked/inactive wallet cannot be analyzed.

BUY/SELL activity requires a canonical wallet and token, positive quantity and
distinct occurred/observed/ingested timestamps. Equivalent duplicate source
deliveries are idempotent; conflicting source IDs are rejected. Position
reconstruction sorts by occurred time and consumes FIFO lots. A matched slice
gets realized PnL only when both its cost basis and proceeds are known from a
quote amount or positive effective price. Unmatched sells, missing financial
values, stale/unknown/conflicted/invalid activity and over-bound lots remain
explicit reason-coded evidence and make the aggregate non-fresh or nullable.

Token age is measured from an explicitly supplied creation timestamp to the
first entry; an entry before creation is invalid and missing creation time is
unknown. Hold duration is retained per matched FIFO slice and summarized by
the median. Rug exposure requires a valid fresh normalized rug outcome after
entry; missing risk evidence is `UNKNOWN`, never a clean result. The snapshot
retains provenance, source references, confidence, expiry, quality state and
config hash, and its execution-eligibility predicate is always false. These
are inputs for the later SmartWalletScore, not a live-money permission.

### Sprint 4.2 SmartWalletScore rules

`SmartWalletScorer` groups Sprint 4.1 `WalletTrackingSnapshot` records by
canonical wallet and uses only completed FIFO round trips whose sell time is
inside the configured rolling window and no later than the score's `now`.
Equivalent round trips delivered through multiple snapshots are counted once;
old outcomes are excluded and future outcomes produce an `INVALID` quality
state and are never scored. Optional manipulation penalties are explicit,
bounded inputs and are capped by policy rather than inferred from a provider.

The default `smart-wallet-v1` policy uses a 30-day rolling window, equal 20%
weights for win rate, aggregate realized-PnL return, median return, early-entry
rate and rug-avoidance rate, and a five-minute evidence TTL. Return-derived
components clamp returns to `-1..1` and map them to `0..100`; all sparse
components shrink toward neutral `50` using `sample / (sample + prior)` with a
default prior of one outcome. The final score is the shrunk weighted score
minus the bounded manipulation penalty, clamped to `0..100`.

Confidence is separate from score magnitude: it multiplies sample confidence,
the lowest source snapshot confidence and the quality-state factor. The
default minimum sample/confidence is `5`/`0.70`; a Tier-B recommendation needs
`5`/`0.60`, while Tier A needs `20`/`0.85` and `FRESH` evidence. A blocked
registry tier remains blocked, and no small or non-fresh sample can receive a
Tier-A recommendation. Recommendations are returned as immutable explainable
data and never mutate the registry or authorize execution.

### Sprint 4.3 confluence and smart-money component rules

`ConfluenceAnalyzer` qualifies only fresh `SmartWalletScore` records whose
recommendation is `TIER_A` or `TIER_B`, score is at least `60`, confidence is
at least `0.60`, and matching wallet-tracking snapshots are fresh. Completed
FIFO round trips within the default 15-minute entry/exit windows produce
wallet-level `ENTRY` and `EXIT` events with the wallet, cluster, quantity,
timestamps, provenance and evidence references intact.

The analyzer consumes the existing bounded `WalletGraphSnapshot` relationship
evidence. Its union-find clustering includes non-qualifying intermediary nodes
and is transitive, so two qualified wallets connected through one observed
funder count as one actor cluster. Timing alone never creates a cluster. When
multiple qualified wallets have no matching graph snapshot, or graph evidence
is stale/unknown/conflicted/invalid, independent counts are not trusted and a
fresh `CONFLUENCE` event is withheld. Graph-linked exits still produce
non-fresh distribution diagnostics, never a positive execution permission.

For a fresh token result, the published components are bounded to `0..100`:

```text
entry_breadth = min(100, 100 * entry_cluster_count / minimum_independent_wallets)
entry_quality = mean(score of unique wallets with a recent entry)
independence = 100 * entry_cluster_count / qualified_wallet_count
exit_pressure = 100 * exit_cluster_count / max(entry_cluster_count, 1)
distribution_penalty = min(25, 25 * exit_pressure / 100)
smart_money_component = clamp(
    0.40 * entry_breadth
  + 0.30 * entry_quality
  + 0.30 * independence
  - distribution_penalty,
  0,
  100,
)
```

At least two independent entry clusters inside the entry window emit one
`CONFLUENCE` event. Exits emit one `DISTRIBUTION` event per exit cluster.
Future activity is invalid and excluded; duplicate snapshots/outcomes are
idempotent and conflicting duplicates are rejected. Any critical non-fresh
state forces the published component score and confidence to zero while
retaining diagnostic components, events, provenance, evidence and reason
codes. `TokenSmartMoneyScore` is advisory and its execution predicate is
always false.

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
Unique buyers/sellers, buy/sell volume, maker diversity, transaction/maker ratio, repeated trade-size patterns, circular flows, rapid round trips, liquidity/sellability corroboration and funding overlap. Missing maker/quote evidence remains explicit and lowers confidence rather than being called organic.

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

### Sprint 5.2 author trust and social velocity rules

`SocialAuthorRegistry` is explicit operator/configuration evidence. Its
trusted, KOL and blocked lists are bounded and conflict-checked; an unlisted
author remains `UNKNOWN`, and mention activity never promotes an author. The
provider-independent `AuthorTrustScorer` uses the following initial base
components: KOL `100`, trusted `80`, unlisted `30` and blocked `0`. For a
fresh evidence set it combines registry base (`80%`), engagement quality
(`10%`) and originality (`10%`), then subtracts bounded duplicate, spam and
coordination penalties. Blocked authors always score zero. Follower counts are
retained as provider metrics but do not by themselves increase trust.

`SocialVelocityScorer` groups mentions by canonical `token_id` or, when no
identity is attached, by validated `referenced_mint`. It counts event-time
mentions and unique authors in `(now - window, now]` for 1m, 5m and 15m
windows. The initial normalized components are velocity in each window,
15m author breadth, engagement quality and originality:

```text
velocity_1m       20%    velocity_5m       25%    velocity_15m      25%
author_breadth    15%    engagement        10%    originality        5%
```

Duplicate ratio is the share of copied/fingerprint-clustered mentions. Spam
ratio is the share with an explicit high spam probability/flag. A coordination
cluster requires the same normalized text fingerprint, at least two distinct
authors and a bounded five-minute posting spread. Its bounded source ratio is
also exposed as `bot_heuristic_ratio`; this is a bot-like burst diagnostic and
never proof of bot identity or shared control. The initial penalty ceilings
are duplicate `25`, spam `20` and coordination `25` points.

Engagement quality is the bounded interaction-to-impression percentage only
when those metrics are present; missing metrics remain nullable and reduce
confidence rather than becoming zero engagement. Confidence is separate from
score and reflects sample size, metric completeness and evidence quality. Any
future, stale, unknown, conflicted or invalid critical social evidence forces
the published score and confidence to zero while retaining diagnostics,
provenance, evidence references and reason codes. `AuthorTrustScore` and
`SocialVelocityScore` are advisory and their execution predicates are always
false.

### Sprint 5.3 narrative rules

The optional `NarrativeAnalyzer` gateway consumes bounded `NarrativeInput`
evidence and returns only strict `NarrativeSnapshot` output: bounded
narrative/topic text, `0..1` novelty, organic/promotional probabilities that
never sum above one, strict organic-assessment and sentiment enums, `0..1`
uncertainty and confidence, validated token/cost usage and evidence references
limited to supplied input IDs. The default policy bounds 100 evidence items,
2,000 characters per item, 12,000 total characters, 3,000 input tokens, 500
output tokens and a $0.05 per-call cost ceiling, with a two-second request
timeout and five-minute evidence/snapshot/cache TTLs.

Untrusted content is delimited as data after secret-shaped and
instruction/tool-shaped text is stripped; non-fresh input evidence, provider
timeouts, schema violations, budget breaches and outages all degrade to a
deterministic zero-confidence `UNKNOWN` fallback snapshot with explicit reason
codes and never raise into deterministic scoring. Fresh validated results are
cached by a deterministic `sha256` key over the canonical sanitized input.
Narrative values are never AlphaScore inputs that bypass hard gates: every
snapshot is advisory, `execution_eligible()` is always false, and an
unavailable LLM changes nothing about deterministic evidence evaluation.

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
