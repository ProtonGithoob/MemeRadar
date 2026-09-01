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

### E11 signal-hardening corroboration

The provider-independent signal-hardening layer validates momentum and market
movement before they are used as feature evidence. A `SURGE` or `REVIVAL`
requires configuration-driven sustained samples, actual buy tape, buyer
evidence and liquidity context; a market-cap/price mark alone is never
economic momentum. `MoveFundingEvidence` retains quote units when USD is not
independently available, discounts explicit wash/bot evidence and degrades
thin-liquidity or non-fresh inputs.

Deployer self-activity, transfer deltas, bounded early sniper/bundle
footprints and token/vesting unlock schedules are corroborating risk evidence.
Transfer deltas do not prove intent, absence of sniper labels is not a clean
launch, token locks are distinct from LP locks, and a lock is not a safety
verdict. Missing, stale, conflicted or unverified hardening evidence remains
`UNKNOWN`/non-fresh and cannot clear a hard risk gate.

Hardening snapshots are carried through correlation, existing feature-family
diagnostics, timeline, exit evidence, replay and calibration identity. They do
not create a new AlphaScore component, and healthy stream/hardening status
does not add score. Any configured confidence or penalty effect must remain
versioned and be calibrated against MemeRadar replay outcomes. Execution and
market/reference price semantics are separate: effective execution prices are
for cost basis/PnL, while market/reference prices are for market series and
movement analytics. All hard gates remain authoritative and every hardening
snapshot is advisory-only.

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

### E5.4 historical caller outcome rules

`SocialCall` is normalized author/token-call evidence with event-time and
provenance metadata. `CallPerformanceAnalyzer` evaluates only market and risk
observations strictly after each call and no later than the replay `now`; input
delivery order must not affect the result. The default fixed horizons are 5m,
15m, 1h, 6h and 24h. Each horizon retains nullable forward return, maximum
favorable excursion and maximum adverse excursion values. No observation is
treated as a zero return merely because a horizon is missing.

Rug and liquidity-collapse flags require fresh, valid post-call risk evidence.
Missing evidence remains nullable/`UNKNOWN`, and conflicting flags remain
conflicted rather than being resolved optimistically. Future observations make
the outcome invalid and cannot improve an author snapshot. Equivalent duplicate
calls are idempotently collapsed with `DUPLICATE_CALL_DEDUPED`; conflicting
source reuse fails closed.

Per-author `CallPerformanceSnapshot` values use sample shrinkage toward neutral
50, explicit minimum sample/confidence gates, bounded uncertainty, provenance,
reason codes, config hash and version. A sparse or missing history therefore
does not become a positive or negative trust fact. `AuthorTrustScorer` consumes
this history only through an opt-in non-zero `performance_weight`; the default
weight is zero, insufficient history lowers confidence, and no call history can
promote a registry tier, clear a deterministic risk block or make any result
execution-eligible.

### E2.5 protocol lifecycle evidence rules

Rich Pump.fun/PumpSwap events are provider-neutral `protocol.lifecycle`
observations, not direct score or transition inputs. The normalized event
types are `LAUNCH`, `TRADE`, `BONDING_CURVE_PROGRESS`, `GRADUATION`,
`MIGRATION`, `POOL_CREATED`, `CREATOR_FEE_CLAIM` and
`FEE_RECIPIENT_CHANGE`; a flagged `WHALE_TRADE` is explicitly `DERIVED` and
cannot be presented as a native protocol fact. Reliable bonding-curve progress
is retained as validated basis points and can be converted into a feature only
when the source supplies state, otherwise it remains missing evidence.

Timeline and later Phase 6 correlation consumers sort by occurred time with
observed/ingested/source tie-breakers, preserve duplicate deliveries for
idempotent storage and keep all source/provenance references. Graduation,
migration, pool, creator-fee and fee-recipient events are neither inherently
safe nor inherently malicious: they are corroborating lifecycle evidence for
risk/exit analysis and must be interpreted with market, on-chain, wallet and
social evidence. A single lifecycle event, including a whale classification,
cannot clear a hard block or produce `ENTRY_READY`; missing, stale, conflicted
or malformed critical evidence remains fail-closed. Stream reconnect and poll
fallback status affects freshness/confidence and never grants execution
authority.

### E6.0 correlation and launch micro-feature rules

The provider-independent `CorrelationWindowBuilder` joins normalized social,
protocol, market, wallet, smart-money and risk evidence in the seven ordered
event-time windows `5s`, `15s`, `30s`, `60s`, `1m`, `5m` and `15m`.
Membership is `(as_of - duration, as_of]`; delivery order never changes the
result. `60s` and `1m` are retained as separate named views for
compatibility with micro-flow and normal rolling-window consumers.

The feature set includes buyer/seller arrival, quote flow and acceleration,
maker/transaction and wash diagnostics, liquidity deltas, protocol lifecycle
counts/curve progress, social/market/wallet counts, actor-cluster smart-money
entry quality, tracked supply and creator/related-wallet sell pressure. Quote-
or row-dependent values remain nullable when the input does not support them.
Distinct smart-money events sharing a cluster ID count as one independent
entry cluster; third-party or protocol labels remain corroborating evidence.

Source diversity counts distinct evidence categories rather than raw records
and caps confidence at the configured target. Fewer than the minimum sample
size or independent source count produces low confidence/`UNKNOWN`. Missing,
stale, conflicted, malformed or future critical evidence never becomes safe
evidence; future/conflicting data makes the correlation snapshot `INVALID`.
The snapshot retains source IDs, timestamps, parser provenance, evidence
references, quality, reason codes, version and config hash. Correlation
features cannot clear a hard risk block, create `ENTRY_READY` or authorize
execution; the later AlphaStrategy/AlphaScore layer must reapply all hard
gates.

### E6.1 versioned AlphaStrategy rules

`AlphaStrategy` is a provider-free application protocol over immutable
`FeatureSnapshot` and `RiskAssessment` inputs plus an explicit mode-safe
`StrategyPolicy`. `AlphaScoreV1Strategy` uses the initial weights exactly as
documented above: `SmartMoney` 25%, `OnChainSafety` 20%, `LiquidityQuality`
15%, `OrganicFlow` 15%, `SocialVelocity` 10%, `HolderQuality` 10% and
`Momentum` 5%. Components are bounded to 0..100; the weighted average is the
raw score, risk penalties are subtracted, and the suggestion is clamped to
0..100.

Missing component values may use a configured neutral 50 only as an explicit
unknown-evidence fallback and reduce confidence. Malformed, out-of-range or
conflicting aliases become invalid/zero-confidence evidence. Confidence is
separate from score magnitude and combines feature/risk confidence with
freshness and completeness adjustments. Stale, unknown, conflicted or future
inputs never become fresh.

Hard risk assessment disposition and hard-block codes remain above the
strategy. A `BLOCK` or `UNKNOWN` assessment is retained in the strategy
snapshot; no score, penalty or strategy version can clear it. Strategy output
is always advisory and `execution_eligible()` is permanently false. Every
projection records strategy name/version, model version/config hash, feature
and risk references, components, penalties, reason codes and provenance so
changing strategy versions is explicit in audit/replay. The keyless
`ReferenceStrategy` is test-only and is not a production ranking strategy.

### E6.2 external wallet cross-validation rules

`ExternalWalletReconciler` treats external wallet labels and token signals as
corroborating evidence only. A fresh positive external label contributes to
the bounded `confidence_bonus` only when the same canonical wallet has a fresh,
qualified internal `SmartWalletScore` (Tier A/B, score and confidence above
the configured thresholds). The external source confidence is preserved
separately as `external_label_confidence`; it is not substituted for the
internal score. The default total agreement bonus is capped at `0.10`.

Different fresh labels for one wallet, conflicting reuse of a source ID, or an
external negative label that conflicts with a qualified internal score produce
`CONFLICTED_EXTERNAL_WALLET_LABEL` and zero agreement bonus. Stale labels are
retained for audit but are ignored for positive confidence. Future, invalid,
unknown and conflicted evidence never becomes safe evidence. When multiple
wallets are present, the existing fresh holder graph is unioned before
`independent_external_wallet_clusters` is counted; no graph-derived or
external label can promote internal wallet authority.

Fresh token signals may expose bounded `tracked_supply_pct`,
`bundle_confidence` and `side_wallet_cluster_confidence` features. Security or
rug flags are emitted as `EXTERNAL_SECURITY_CORROBORATION_ONLY`; they do not
become hard blocks or replace deterministic on-chain authority evaluation.
Removing the external provider therefore leaves internal wallet scores and
`RiskAssessment` values unchanged and only removes corroborating features or
confidence. Every external-wallet result remains advisory and has
`execution_eligible() == false`.

### Core Sprint 6.1 feature windows

`FeatureWindowAggregator` emits exactly three immutable snapshots at the
correlation event-time boundary: `1m`, `5m` and `15m`. The correlation builder
owns event membership; this layer only projects its normalized output and
already-derived risk, holder, wallet, social and flow evidence. Each snapshot
retains the seven bounded families `market`, `liquidity`, `holder`, `wallet`,
`social`, `momentum` and `on_chain_safety`, plus the AlphaStrategy-compatible
components `SmartMoney`, `OnChainSafety`, `LiquidityQuality`, `OrganicFlow`,
`SocialVelocity`, `HolderQuality` and `Momentum` when their evidence is
available.

Family availability, completeness and confidence are explicit. A missing or
non-fresh family remains unknown and reduces completeness; it is never
converted into a neutral safe value at this layer. Evidence after the
correlation `as_of`, a pre-boundary evaluation, missing canonical windows or
incorrect window boundaries produces `INVALID` snapshots with zero confidence
and reason codes. Stable IDs include candidate, window, event time, feature
version and config hash, making replay independent of delivery order.

External-wallet values remain nested corroboration under the wallet family and
cannot replace internal SmartMoney, on-chain risk or holder-graph authority.
Feature snapshots have no execution predicate or transition authority;
AlphaScore and decision layers must reapply every hard risk and freshness gate.

### Core Sprint 6.2 AlphaScore recomputation

`AlphaScoreRecomputer` delegates to the configured `AlphaStrategy` and
projects its immutable result into `ScoreSnapshot`. The initial strategy uses
the exact seven weights above; `StrategyPolicy` validates configurable positive
weights summing to `1`, and the recomputation preserves bounded components,
penalties, confidence, reason codes, risk disposition evidence and strategy /
model identity. Penalties are subtracted from the raw weighted score and the
stored AlphaScore is clamped to `0..100`.

Hard blocks and `UNKNOWN`/stale/conflicted/invalid risk remain in the linked
`RiskAssessment` and score reason codes. A high or clamped score cannot clear
them; future evaluation before either input boundary fails closed. Stable score
IDs include candidate, feature/risk IDs, strategy name/version, evaluation time
and config hash, so reverse mapping replay produces one idempotent result.
`RiskAssessmentRepository` and `ScoreSnapshotRepository` preserve JSON-safe
components/penalties, reasons, freshness, model/strategy identity and config
hash. The score remains advisory and has no execution or state-transition
authority.

### Core Sprint 6.3 DecisionEngine

`DecisionEngine` re-applies the risk and freshness gates above the score before
mapping one lifecycle step. Its initial versioned `DecisionPolicy` defaults to
watch/strong/entry thresholds of `40`/`75`/`85`, downward hysteresis floors of
`35`/`70`/`80`, minimum decision confidence `0.60` and a 30-second cooldown.
Candidates advance sequentially from `ENRICHING` to `WATCH`, then
`STRONG_SETUP`, then `ENTRY_READY`; a score cannot skip lifecycle states.

`BLOCK`, `UNKNOWN`, hard-blocked or non-fresh critical risk, and config
identity mismatch fail closed to `RISK_REJECTED` where the lifecycle allows
it. `WARN` risk, low confidence, non-fresh scores and failed execution gates
cannot produce `ENTRY_READY`. Hysteresis holds a current state until its
configured floor is crossed; safety downgrades and risk rejection bypass the
cooldown. The engine never creates `PAPER_OPEN`, `OPEN` or a live approval.

Each evaluation carries reason codes, evidence references, score/risk IDs,
confidence, policy version and config hash. Non-zero score changes emit an
`AlphaScoreDelta` event; worsening disposition/quality or an initial unsafe
risk emits `RiskEscalation`. Both are advisory, deterministic and replayable.

### E8.4 stream integrity quality

Stream integrity is data-quality evidence, never a positive AlphaScore input.
`StreamQualityImpact` leaves healthy transport neutral; an unresolved gap,
failed recovery, unverified recovery, unknown protocol or decoder conflict
reduces the affected feature window's completeness/confidence and preserves
explicit reason codes. Critical missing or unverified chain evidence remains
`UNKNOWN`/non-fresh and cannot become `ENTRY_READY`. Verified recovery may
restore completeness while retaining recovery provenance. Reverted chain
observations remain explicit correction evidence and do not silently improve
the score. The bounded `ReplayManifest` applies the same quality and
event-time/no-lookahead rules during historical replay.

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

The Phase 9.1 `PaperSizingPolicy` applies these inputs through explicit
max-risk, position-fraction, liquidity-fraction, total-exposure, reserve,
confidence and concurrent-position caps. A zero/insufficient result is an
explicit non-eligible paper outcome. Healthy stream state or a high score does
not increase the size by itself; stale, unknown, conflicted or invalid quote or
risk evidence rejects the simulated order. The `PaperFillModel` records
configured adverse slippage, quote-currency fees and source/version details so
paper cash and position outcomes remain explainable and replayable.

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

Sprint 9.2 implements this exit contract with an independent
`ExitRiskScore`; it is not an AlphaScore adjustment and stream health is never
a positive exit/entry signal. Missing, stale, conflicted or invalid critical
evidence produces an explicit non-safe exit result. The evaluator supports
independent distribution-cluster corroboration, creator/holder pressure,
micro/macro flow collapse, liquidity/quote deterioration, score degradation,
time stops, trailing/break-even and configured partial take-profit levels.

Sprint 9.3 projects position performance separately from AlphaScore. Observed
market marks retain provider/source/parser and all observation timestamps;
current value and unrealized/total PnL are derived only from fresh valid marks.
Stale, unknown, invalid or conflicted marks reduce data quality and leave
current PnL unknown rather than creating a safe or zero value. Realized PnL,
MFE and MAE remain visible with explicit quality. Position exit alerts reuse
the deterministic exit reason/evidence contract; healthy or fresh stream state
does not increase AlphaScore and external-only exit corroboration cannot create
an alert or authorize an exit.

## 13. Calibration rules

- No lookahead leakage.
- Use time-based train/validation splits.
- Track performance by launch venue/liquidity/token age/regime.
- Prefer robust metrics (expectancy, drawdown, precision by score bucket) over cherry-picked wins.
- Keep previous score versions replayable.
- New model runs in shadow before promotion.
- Codex must never auto-promote a live trading model based solely on backtest performance.

## Phase 10.1 replay and calibration boundary

The research replay harness reconstructs features at event-time checkpoints
through the same normalized observation/correlation/feature contracts used by
the application. Future observations are retained only by the independent
outcome labeler; they cannot enter the earlier feature snapshot, risk
assessment or strategy input. Parser, registry, event-schema, strategy,
configuration and outcome-policy identities are pinned in the replay manifest.

Replay cohort dimensions and forward-outcome metrics are descriptive research
projections. Healthy stream completeness does not add score, an unresolved or
non-fresh evidence state remains non-safe, and every replay strategy snapshot
is advisory with `execution_eligible() == false`. Positive backtest or cohort
results cannot change protected modes or authorize `ENTRY_READY`.

## Phase 10.2 backtest boundary

`BacktestHarness` treats the strategy snapshot as an advisory entry hypothesis,
not execution authority. It requires fresh feature/risk evidence, explicit
`RiskDisposition.PASS`, configured score/confidence thresholds and a known
liquidity constraint when one is configured. Exit policy selection is
independent and uses only the selected future outcome horizon. Fee and adverse
slippage are applied on both legs through `PaperFillModel`.

Reports expose precision, end-to-end hit rate, net-return/PnL expectancy,
fixed-notional maximum drawdown, profit factor and calibration by score bucket.
They also segment by launch venue, liquidity band, token age, event-time market
regime, social velocity and smart-wallet confluence. Unknown future price or
critical safety labels create explicit skips and reduce measurable coverage;
they never count as safe evidence or increase AlphaScore. A positive report is
research evidence only and cannot promote a score version or enable trading.

## Phase 10.3 score-calibration boundary

`ScoreCalibrationHarness` compares validated `AlphaStrategy` candidates in
shadow mode over half-open event-time train/validation/test partitions. It
recomputes candidate scores from the checkpoint-bounded feature and risk
snapshots and delegates fills/metrics to the existing provider-free
`BacktestHarness`; it does not create a replay-only decoder or inspect future
events. Feature ablation sets only the named component to the neutral value,
while the strategy's existing missing, quality, confidence and hard-risk
behavior remains authoritative. Candidate selection is train-only and
validation/test are reported unchanged as out-of-sample evidence.

The calibration report pins parser/registry/schema/strategy/config/dataset
identities, candidate hashes, policy assumptions and artifact digests.
Promotion checks require sufficient documented evidence but can return only
`BLOCKED_INSUFFICIENT_EVIDENCE` or `MANUAL_REVIEW_REQUIRED`; there is no
automatic promotion or production-config write. The E10.2 attribution seam
measures forward-outcome lift for author trust and internal smart-money
components, external-label incremental value and bundle/side-wallet false
confluence. These are descriptive research measurements; external labels do
not replace internal score authority, and no calibration result raises
AlphaScore, clears a risk gate or authorizes `ENTRY_READY`.
