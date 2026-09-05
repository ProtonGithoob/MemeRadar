# MemeRadar — Opportunity Discovery & Narrative Alpha Extension

Date: 2026-09-05
Status: APPROVED_FOR_IMPLEMENTATION
Priority: P0/P1/P2
Scope: provider-independent, read-only/shadow/paper only

## 1. Why this extension exists

Recent winner-case review exposed a structural weakness: MemeRadar is strong at asking **"is this token safe/interesting?"** after a candidate enters the radar, but it is weaker at asking **"where is capital/attention rotating, what causal event is creating a repricing opportunity, and which contract is the canonical expression of that event?"** early enough.

The reviewed examples include Robinhood Chain and BNB tokens whose upside was driven by different mechanisms:

- real-world viral meme -> tokenization;
- breaking-news / public-company narrative -> token expression;
- ecosystem/launchpad usage acceleration -> protocol token repricing;
- protocol fundamentals/TVL/borrow/users accelerating faster than valuation;
- ultra-fast community token attention/holder/turnover acceleration.

These are not one archetype and MUST NOT be forced through one static feature interpretation.

The extension therefore adds an **Opportunity Discovery Layer before normal token scoring**, while preserving all existing safety, replay, wallet, risk, execution-quality and promotion gates.

Protected modes remain invariant:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No live signing, private keys, swap submission, sniping, copy trading or live-money execution is permitted.

---

## 2. Core design correction

Old conceptual flow:

```text
TOKEN DISCOVERED
  -> TOKEN FEATURES
  -> RISK
  -> SCORE
  -> ALERT
```

Required flow:

```text
GLOBAL EVENT / CHAIN / PROTOCOL / SOCIAL STREAMS
  -> OPPORTUNITY DISCOVERY
  -> CHAIN / ECOSYSTEM HEAT
  -> NARRATIVE / CATALYST GRAPH
  -> NEW TOKEN / CONTRACT DISCOVERY
  -> ORIGINAL-vs-COPYCAT RESOLUTION
  -> HARD SAFETY / SELLABILITY
  -> EARLY UPSIDE EVIDENCE
  -> SMART-MONEY / HOLDER / LIQUIDITY CORROBORATION
  -> EXISTING EARLY SCORE / ALPHA / DECISION GATES
  -> TELEGRAM / SHADOW / PAPER
  -> REPLAY / ABLATION / PROMOTION
```

Important: this extension does **not** create a second production score engine. New evidence is measurement-only until no-lookahead replay and the existing strategy promotion gate prove incremental lift.

---

# 3. P0 — Chain Opportunity Engine

## Problem

A high-quality token model is useless if MemeRadar is not watching the chain where the strongest new opportunity set exists. The reviewed examples show that chain selection itself can dominate winner recall.

## Required capability

Add a provider-independent `ChainOpportunitySnapshot` / `ChainHeatSnapshot` that measures market opportunity by chain and time bucket.

Candidate fields, where available:

- chain;
- observed_at / as_of / expires_at;
- new_token_count_5m/1h/24h;
- new_pool_count_5m/1h/24h;
- active_wallet_count and acceleration;
- new_wallet_count and acceleration;
- transaction_count and acceleration;
- DEX volume and acceleration;
- liquidity inflow and acceleration;
- stablecoin/native capital inflow where measurable;
- launchpad launch count;
- launchpad graduation/success count;
- successful-launch ratio;
- median token age at first material volume;
- 2x/5x/10x future cohort frequency in replay only;
- protocol/project creation velocity;
- social mention velocity by chain;
- cross-chain attention share;
- provider/source diversity;
- quality/freshness/confidence;
- version/config hash.

Do not fabricate one magic heat score before calibration. Initially expose components plus a research-only projection.

## Routing behavior

Discovery resource allocation SHOULD be capable of prioritizing hotter chains without disabling baseline monitoring elsewhere.

Example policy concept only:

```text
baseline poll/stream coverage on all enabled chains
+
extra discovery budget for chains with measured opportunity acceleration
```

This must remain bounded and deterministic.

---

# 4. P0 — Robinhood Chain first-class read-only support

Robinhood Chain is no longer optional research scope. It is a mandatory read-only discovery chain because reviewed extreme-winner examples exist there.

Canonical network facts to encode in configuration/tests, not scattered literals:

```text
chain: robinhood
EVM compatible: yes
mainnet chain id: 4663
native gas: ETH
public RPC default: https://rpc.mainnet.chain.robinhood.com
public sequencer feed: wss://feed.mainnet.chain.robinhood.com
block explorer: robinhoodchain.blockscout.com
```

## Required implementation

Reuse the generic EVM capability layer planned for BNB. Do not fork an entirely separate Robinhood stack.

Add:

- `ChainId.ROBINHOOD` or equivalent canonical chain identity;
- EVM address validation reused from generic EVM primitives;
- chain-aware canonical token/wallet IDs;
- standard read-only JSON-RPC route;
- explicit `eth_chainId == 4663` verification;
- optional bounded sequencer-feed/read-only stream adapter if it measurably improves first-seen latency;
- Blockscout read-only enrichment behind provider contracts where useful;
- DexScreener/market discovery support when provider coverage exists;
- provider health/readiness states;
- replay/shadow cohort segmentation by Robinhood chain;
- Telegram rendering of Robinhood chain/address/provenance.

Do not introduce Robinhood brokerage-account logic. Robinhood Chain is a permissionless EVM chain and must remain separate from brokerage-account concepts.

---

# 5. P0 — Narrative Catalyst Engine

## Problem

`SocialCorroboration` cannot treat all mentions equally. A causal external event that predates token creation is qualitatively different from thousands of promotional posts after deployment.

## Required model

Add a provider-independent `NarrativeCatalystSnapshot` / `NarrativeEvidence` projection.

Required fields where evidence permits:

- narrative_id;
- canonical entities/keywords;
- catalyst_type;
- catalyst_first_seen_at;
- catalyst_source_type;
- catalyst_source_quality;
- external_vs_crypto_native;
- event originality / duplicate status;
- engagement/view/repost velocity, not only totals;
- independent-author growth;
- cross-community propagation;
- cross-language propagation;
- crypto-community penetration time;
- token_created_at;
- `narrative_lead_time = token_created_at - catalyst_first_seen_at`;
- pre-token attention volume;
- post-token attention volume;
- `pre_token_attention_ratio`;
- token/narrative semantic fit;
- chain-cultural fit;
- novelty;
- narrative competition count;
- freshness/confidence/provenance/reason codes;
- version/config hash.

## Important distinction

Model and UI must distinguish:

```text
ORGANIC_ATTENTION_PRECEDES_TOKEN
TOKEN_PRECEDES_PROMOTIONAL_ATTENTION
MIXED / UNKNOWN
```

The first may be valuable upside evidence. The second may be promotional/manipulation risk. Neither state alone authorizes entry.

---

# 6. P0 — Pre-Token Attention Engine

This is a focused subprojection of narrative evidence because it is especially important for real-world memes and breaking events.

Measure:

- first reliable external-source timestamp;
- first crypto mention timestamp;
- token deployment timestamp;
- first liquidity timestamp;
- first tracked-wallet entry timestamp;
- first high-quality KOL/researcher mention;
- first large retail propagation point;
- attention slope before deployment;
- attention slope after deployment;
- attention source diversity;
- organic-source confidence.

Replay must explicitly measure whether alerting during the **researcher/smart-money phase** provides better executable outcomes than waiting for broad retail virality.

Do not use future viral totals in live-time features.

---

# 7. P0 — Narrative-to-Token Semantic Matcher

## Problem

A trending narrative can have many contracts. Detecting the theme without resolving the correct contract creates false positives and scam exposure.

## Required projection

Add `NarrativeTokenMatch` with:

- token identity / chain / address;
- narrative_id;
- symbol/name overlap;
- description/metadata semantic match;
- official/reference-link match;
- deployment timing relative to catalyst;
- liquidity timing;
- social posts containing the exact contract address;
- known original-source linkage;
- creator/deployer linkage evidence where legitimate;
- market/liquidity dominance within narrative;
- holder-growth dominance within narrative;
- tracked-wallet dominance within narrative;
- confidence and evidence refs.

LLM may assist classification but cannot be the only evidence source and cannot create execution authority.

---

# 8. P0/P1 — Narrative Competition & Copycat Resolver

For each narrative cluster, group candidate contracts and expose both the cluster and ranked evidence.

Add `NarrativeCompetitionSnapshot` fields:

- narrative_id;
- candidate_contract_count;
- earliest_deployment;
- earliest_meaningful_liquidity;
- first credible contract-address references;
- market/liquidity share;
- holder-growth share;
- independent smart-wallet share;
- source diversity;
- suspicious coordinated-promotion indicators;
- canonical/original confidence;
- UNKNOWN when evidence cannot identify an original.

Never use ticker/name equality as identity.

Do not automatically call later contracts scams; classify evidence separately.

---

# 9. P1 — Attention Quality-Weighted Velocity

Raw mention counts are inadequate.

Add research features approximating:

```text
sum(author_quality
    * engagement_velocity
    * originality
    * audience_independence
    * narrative_relevance)
/ elapsed_time
```

The exact formula must not be hard-coded as production truth without replay/ablation.

Required raw components:

- unique author count;
- independent author-cluster count;
- engagement acceleration;
- repost-to-original ratio;
- duplicate-text ratio;
- bot/suspicious-author rate where evidence exists;
- audience overlap;
- source-category diversity;
- researcher/KOL/general-public propagation stage;
- exact-CA mention velocity;
- narrative-only mention velocity.

Preserve UNKNOWN when author/bot evidence is unavailable.

---

# 10. P1 — Cross-Community Propagation Graph

Add graph evidence for how a narrative moves across communities:

```text
external source -> general public -> niche community -> crypto researcher
-> smart money -> KOLs -> retail
```

Track:

- source-category transitions;
- first-seen time per community;
- propagation delay;
- independent-community count;
- language/region transitions where lawful/available;
- source diversity;
- amplification concentration.

The system should prefer early independent propagation over one-account amplification, subject to calibration.

---

# 11. P1 — Protocol / Fundamental Velocity Engine

Not every extreme winner is a meme. Infrastructure/protocol tokens require fundamental acceleration evidence.

Add `ProtocolVelocitySnapshot` fields where available:

- TVL level and d(TVL)/dt;
- borrow amount and acceleration;
- deposits/supply and acceleration;
- active users/wallets and acceleration;
- transaction count and acceleration;
- protocol volume and acceleration;
- fees/revenue and acceleration;
- market count/pool count/product count;
- launch count/graduation count for launchpads;
- protocol market share;
- ecosystem share;
- usage growth vs market-cap growth;
- usage-growth/valuation-growth ratio;
- freshness/source diversity/confidence.

Do not mix meme-only and protocol-only evidence into one mandatory schema. Missing fundamental data on a pure meme must not be treated as a negative score.

---

# 12. P1 — Winner Archetype Classifier

Before interpreting features, classify the candidate into one or more versioned archetypes:

```text
PURE_MEME
REAL_WORLD_MEME
BREAKING_NEWS_MEME
CULTURAL_MEME
PROTOCOL_TOKEN
LAUNCHPAD_TOKEN
CHAIN_BETA
RWA_ADJACENT
AI_TOKEN
CELEBRITY_EVENT
POLITICAL_EVENT
OTHER / UNKNOWN
```

Requirements:

- multi-label allowed;
- evidence/provenance required;
- confidence separate from class;
- UNKNOWN supported;
- LLM may assist but deterministic metadata/event evidence must be retained;
- archetype must not directly authorize trading.

The initial production EarlyScore weights remain unchanged until replay demonstrates archetype-conditioned weighting improves out-of-sample performance.

---

# 13. P1 — Regime / Archetype-conditioned research

Current fixed EarlyScore weights must not be replaced impulsively.

Instead, replay/ablation must compare:

1. current fixed baseline;
2. added opportunity/narrative features with fixed weights;
3. archetype-specific candidate models;
4. chain/regime-specific candidate models.

Promotion criteria:

- TRAIN / VALIDATION / TEST separation;
- minimum sample count;
- no lookahead;
- improved executable expectancy or winner recall without unacceptable rug/severe-loss increase;
- confidence intervals;
- version/config hash;
- human-reviewed strategy promotion record.

---

# 14. P1 — KOL / Researcher specialization

Extend `docs/SMART_MONEY_CONVERGENCE_EXTENSION.md` KOL work.

Required historical profile fields:

- call count / matured call count;
- median market cap and token age at first mention;
- 2x/5x/10x/20x/50x participation labels in research only;
- median time-to-multiple;
- MFE/MAE;
- rug/severe-failure rate;
- early-call vs post-breakout-call rate;
- deleted/edited-post evidence where legally/technically available;
- paid-promotion evidence only when explicit/testable;
- chain specialization;
- archetype specialization;
- narrative specialization;
- researcher vs promoter profile classification;
- wallet-before-post / wallet-after-post evidence only when explicit wallet linkage exists.

A technical protocol researcher must not be calibrated using the same historical expectations as a meme caller.

---

# 15. P1 — Upside evidence and risk must remain separate

Explosive upside and high manipulation/liquidity risk can coexist.

Do not collapse them too early into one scalar.

Read-only projections should expose at least:

```text
upside_evidence
market_integrity_risk
contract/deployer_risk
liquidity_exit_risk
execution_quality
confidence
```

Existing hard gates remain authoritative for ENTRY_READY. Strong upside evidence cannot override critical BLOCK/UNKNOWN risk or non-sellability.

This prevents both failure modes:

- rejecting every explosive high-turnover winner before research can measure it;
- allowing narrative hype to bypass safety.

---

# 16. P1 — Smart-money convergence integration

Keep the existing `SMART_MONEY_CONVERGENCE_EXTENSION.md` canonical.

Opportunity/narrative evidence must integrate with, not replace:

- tracked-wallet historical quality;
- cluster-adjusted wallet independence;
- net smart-wallet inflow;
- first smart-wallet entry age/market cap;
- wallet cohort recurrence;
- KOL/wallet corroboration;
- smart-money distribution/exit evidence.

Critical combined research question:

> Does a causal/organic narrative + early independent smart-wallet convergence produce materially better executable winner recall than either signal family alone?

---

# 17. P1 — Global Event Ingestion contracts

Do not hard-depend on one social site.

Create provider-neutral event contracts capable of ingesting, subject to provider availability and terms:

- X/social posts;
- news/event feeds;
- Telegram public-channel observations where configured;
- Reddit/community events where available;
- chain-native protocol announcements;
- official project/organization feeds;
- market/on-chain events.

Every event must preserve:

- source;
- source event id;
- occurred_at / observed_at / ingested_at;
- author/entity identity where available;
- raw-reference pointer, not unrestricted raw data propagation;
- normalized text/entities/URLs/contract addresses;
- quality/freshness;
- provenance/evidence refs.

Provider outages must degrade evidence, not crash the core.

---

# 18. P1 — Alert redesign: explain the opportunity

Extend the existing Telegram/read-only alert path. Do not create another alert system.

When available, show:

```text
chain / token / address
age / market cap / liquidity
winner archetype
catalyst summary + catalyst age
pre-token attention state
attention velocity / source diversity
narrative-token match confidence
copycat count / narrative dominance
chain heat / ecosystem acceleration
smart-wallet independent buyer count
first elite-wallet entry age/market cap
holder and liquidity acceleration
protocol/fundamental velocity where applicable
hard risk / market integrity / sellability
provider corroboration/disagreement
confidence / freshness / reason codes
```

Reason-code examples:

```text
ORGANIC_ATTENTION_PRECEDES_TOKEN
EXTERNAL_CATALYST_HIGH_CONFIDENCE
NARRATIVE_TOKEN_MATCH_HIGH
NARRATIVE_COPYCAT_COMPETITION_HIGH
NARRATIVE_DOMINANCE_HIGH
CHAIN_OPPORTUNITY_ACCELERATING
PROTOCOL_USAGE_ACCELERATING
SMART_WALLET_CONVERGENCE_HIGH
ATTENTION_VELOCITY_ACCELERATING
CROSS_COMMUNITY_PROPAGATION
MARKET_INTEGRITY_RISK_HIGH
```

Do not replace transparent evidence with a single opaque `91/100` display.

---

# 19. P0/P1 — No-lookahead replay case-study framework

The reviewed token examples should be used as historical research fixtures/case studies only when event-time data can be reconstructed honestly.

For each case, collect or derive, without future leakage:

- deployment/first-liquidity time;
- first-seen by MemeRadar-equivalent providers;
- catalyst first-seen time;
- pre-token attention evidence;
- first tracked-wallet entries;
- holder/liquidity/volume trajectories;
- narrative competitors/copycats;
- protocol-usage trajectory if relevant;
- external/KOL mention timeline;
- executable quotes/liquidity where available;
- future-only 2x/5x/10x/20x/50x/100x outcomes;
- severe drawdown/rug/liquidity-failure outcomes.

Negative controls are mandatory. Do not build a dataset containing only winners.

Suggested cohorts:

- extreme winner;
- ordinary winner;
- high-virality non-winner;
- copycat failure;
- rug/severe failure;
- protocol with fundamentals but no repricing;
- repricing with weak fundamentals.

Any missing historical timestamp must remain UNKNOWN rather than reconstructed from future knowledge.

---

# 20. Measurement targets

Per chain, archetype, launch-age bucket and market-cap bucket measure:

- discovery recall before 1m/3m/5m/15m/30m;
- first-detection age;
- market cap at first detection;
- lead time to 2x/5x/10x;
- executable 2x/5x/10x/20x/50x/100x recall;
- ENTRY_READY precision;
- severe-failure/rug rate;
- copycat false-selection rate;
- narrative-canonical-contract accuracy;
- alert latency;
- smart-wallet lead time;
- catalyst lead time;
- chain-opportunity lead time;
- paper/shadow expectancy after costs;
- max drawdown;
- exit capture ratio;
- sample counts/confidence intervals.

Do not optimize for alert count.

---

# 21. Configuration principles

Do not add dead `.env.example` values. Add config only in the same change as validated runtime parsing/tests.

Conceptual targets include:

```env
ENABLED_CHAINS=solana,bnb,robinhood

ROBINHOOD_RPC_URL=https://rpc.mainnet.chain.robinhood.com
ROBINHOOD_RPC_FALLBACK_URL=
ROBINHOOD_CHAIN_ID=4663
ROBINHOOD_SEQUENCER_FEED_URL=wss://feed.mainnet.chain.robinhood.com
ROBINHOOD_BLOCKSCOUT_API_URL=

CHAIN_OPPORTUNITY_ENABLED=true
NARRATIVE_CATALYST_ENABLED=true
PRETOKEN_ATTENTION_ENABLED=true
NARRATIVE_COMPETITION_ENABLED=true
PROTOCOL_VELOCITY_ENABLED=true
```

Defaults must preserve safe boot when optional social/news providers are not configured.

---

# 22. Explicit non-goals

Do not add:

- guaranteed 10x/20x/50x/100x predictions;
- future-data leakage into live features;
- static ticker/name identity matching;
- one hard-coded universal narrative score;
- automatic social scraping that violates provider terms;
- dependence on X/FOMO/Hoodwatch/Stalkchain pages for core boot;
- copy trading;
- KOL auto-follow;
- live wallet execution;
- new duplicate score, wallet, graph, social, alert or dashboard engines;
- arbitrary dynamic production weights without promotion-gate evidence.

---

# 23. Priority execution order

## P0 — must be implemented first

1. generic chain-aware identity/capability work already approved;
2. Robinhood Chain read-only support using generic EVM primitives;
3. Chain Opportunity Engine;
4. provider-neutral Global Event contract;
5. Narrative Catalyst + Pre-Token Attention;
6. Narrative-to-Token Matcher;
7. Narrative Competition/Copycat Resolver;
8. read-only projections/API/Telegram reason codes;
9. no-lookahead fixtures and negative-control case studies;
10. full replay/measurement gate before production-score changes.

## P1 — after stable P0 contracts

11. attention quality-weighted velocity;
12. cross-community propagation graph;
13. protocol/fundamental velocity;
14. winner archetype classifier;
15. KOL/researcher specialization;
16. integrate with smart-money convergence;
17. archetype/regime-conditioned research;
18. chain opportunity resource allocation research.

## P2 — only if measured benefit justifies it

19. Robinhood sequencer-feed optimization;
20. advanced graph/entity resolution;
21. additional chain auto-discovery/ranking;
22. heavier NLP/LLM enrichment;
23. performance/Rust optimizations only when measured latency changes executable outcomes.

---

# 24. Acceptance rules

A feature is not complete because code exists.

Each implementation slice requires:

1. failing deterministic tests first;
2. minimal implementation;
3. unit + contract tests;
4. no-lookahead coverage where applicable;
5. UNKNOWN != ZERO/SAFE checks;
6. provider failure/degraded-state tests;
7. chain collision/idempotency tests;
8. focused tests pass;
9. full `make verify` pass;
10. docs/STATUS.md exact evidence and next task;
11. coherent commit/push;
12. local HEAD and origin synchronization check.

`REAL_WORLD_ALPHA_NOT_YET_PROVEN` remains until real live-shadow out-of-sample evidence satisfies the existing research/promotion gate.
