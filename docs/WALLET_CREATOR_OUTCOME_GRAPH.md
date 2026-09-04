# Wallet Creator Outcome Graph — Executable Codex Specification

## Purpose

Add a first-class graph view that explains **which wallets repeatedly create, fund, receive, buy, dump, profit from, or are otherwise linked to memetokens**, and how those tokens subsequently perform.

This is not a generic blockchain explorer and not a second wallet/risk engine. It is a projection over MemeRadar's existing canonical token, wallet, holder-graph, deployer, trade, replay, risk, SmartWalletScore, launch-risk and outcome evidence.

The primary operator questions are:

1. Which wallets repeatedly create tokens that pump?
2. Which wallets repeatedly create tokens that dump, rug, lose liquidity or trigger severe risk?
3. Which deployers/creators are historically profitable, neutral, unproven or dangerous?
4. Which funder / side-wallet / bundle clusters repeatedly appear behind successful or failed launches?
5. Which wallets buy before or immediately after launch and later distribute to followers?
6. Does a wallet's reputation come from real out-of-sample outcomes or from too few samples?
7. For the current token, what is the shortest explainable path back to its creator/funder/related-wallet cluster and their prior outcomes?

## Architectural rule

Reuse existing MemeRadar evidence. Do not build a parallel graph database unless measured scale proves PostgreSQL projections inadequate.

Initial implementation should use existing relational persistence plus bounded graph projections. A specialized graph database is explicitly out of scope for v1.

All nodes/edges must carry provenance, event-time semantics and evidence quality. `UNKNOWN != SAFE` remains mandatory.

The graph is read-only/advisory and can never authorize execution.

---

# E8.6 — Wallet / Creator Outcome Graph

**Priority:** P1 after currently active Ultra-Early and already-approved P1 research extensions.

## 1. Graph node types

Implement a normalized read model with at least these node kinds:

- `WALLET`
- `ACTOR_CLUSTER`
- `TOKEN`
- `POOL`
- `LAUNCH`
- `SOCIAL_AUTHOR` when a durable mapping exists

Do not invent a new canonical identity system. Reuse current Solana wallet/mint/pool identities and actor-cluster IDs.

### Wallet node projections

Expose, when available:

- wallet address;
- role labels derived from evidence: creator, deployer, funder, early buyer, sniper, bundler, smart wallet, KOL wallet, dumper;
- first_seen_at / last_seen_at;
- current internal SmartWalletScore and confidence;
- number of created/deployed tokens;
- number of funded launch wallets;
- number of launches participated in early;
- realized historical PnL where current accounting supports it;
- median/mean outcome statistics only with sufficient sample counts;
- creator/deployer reputation score described below;
- explicit `UNKNOWN` values when data is unavailable.

### Token node projections

Expose:

- mint;
- symbol/name when available;
- launch venue;
- launch/first-seen timestamp;
- launch market cap/liquidity where available;
- peak market cap / MFE horizons from replay/outcome evidence;
- severe drawdown / rug / liquidity-collapse outcome;
- current/final risk state;
- AlphaScore/EarlyScore snapshot identity when appropriate;
- outcome classification.

---

## 2. Graph edge types

Implement only evidence-backed edges.

Required edge kinds:

- `CREATED`
- `DEPLOYED`
- `FUNDED`
- `TRANSFERRED_TO`
- `BOUGHT`
- `SOLD`
- `EARLY_BOUGHT`
- `SNIPED`
- `BUNDLED_WITH`
- `SAME_ACTOR_CLUSTER`
- `CREATOR_RELATED`
- `MIGRATED_TO_POOL`
- `KOL_CALLED` when mapping is evidenced

Each edge must preserve enough fields for explanation:

- occurred_at;
- observed_at;
- ingested_at;
- source/provider;
- source_event/signature;
- token/mint context when applicable;
- raw amount / SOL value where safely modeled;
- supply percentage where available;
- evidence quality: PASS/UNKNOWN/CONFLICTED/INVALID or existing equivalent;
- reason/evidence references.

Do not infer ownership/control from one transfer alone. `FUNDED`, `CREATOR_RELATED`, or actor-cluster membership requires current holder/funding graph evidence and confidence rules.

---

## 3. Token outcome taxonomy

Create one reusable provider-independent outcome classification used by graph statistics and historical calibration.

Suggested classes:

- `STRONG_WINNER`
- `WINNER`
- `MIXED`
- `FAILED`
- `SEVERE_DUMP`
- `RUG_OR_LIQUIDITY_COLLAPSE`
- `UNKNOWN`

Do not label from arbitrary current price alone.

Classification must use existing future-only replay/outcome evidence such as:

- MFE / MAE;
- 1m/3m/5m/15m/30m/1h/6h/24h outcomes as available;
- 50K / 100K / 250K market-cap crossings;
- time-to-1.5x/2x/3x;
- severe drawdown;
- liquidity survival/collapse;
- creator dump;
- rug/security events;
- shadow/paper exit executability.

Thresholds must be configuration-driven and versioned. No production threshold changes automatically from graph statistics.

---

## 4. Creator / Deployer Reputation

Add a `CreatorReputationSnapshot` or equivalent read/research model. Do not overload SmartWalletScore because creating tokens and trading tokens are different behaviours.

Suggested deterministic components:

- launches_total;
- sufficient_outcome_samples;
- winner_rate;
- strong_winner_rate;
- severe_failure_rate;
- rug/liquidity-collapse rate;
- median peak multiple / MFE;
- median MAE;
- median time to major drawdown;
- median launch liquidity;
- creator initial-buy behaviour;
- creator sell/dump behaviour;
- creator transfer-delta anomalies;
- bundle/sniper footprint associated with launches;
- shared-funder / side-wallet recurrence;
- percentage of launches with valid sellability/liquidity survival;
- confidence/sample-size shrinkage.

Output should be bounded and versioned, e.g. `0-100`, but confidence must be separate from reputation.

Suggested classes:

- `PROVEN_POSITIVE`
- `POSITIVE`
- `NEUTRAL`
- `UNPROVEN`
- `HIGH_RISK`
- `REPEATED_SEVERE_FAILURE`

Critical rules:

- one successful token cannot create a high reputation;
- one failed token alone cannot permanently mark a creator malicious;
- known deterministic scam/rug evidence may still cause a separate hard risk block for a specific token;
- creator reputation is corroborating evidence, not an execution authority;
- use neutral shrinkage / minimum samples just like current AuthorTrust/SmartWallet calibration patterns.

---

## 5. Recurring creator/funder cluster intelligence

Add graph queries/projections to detect recurring structures across multiple launches:

- same creator wallet creating many mints;
- rotating fresh creator wallets funded by the same wallet/cluster;
- same side-wallet set receiving early allocations across launches;
- recurring first-block buyers;
- recurring bundle/sniper clusters;
- same funder → multiple deployers → multiple failed tokens;
- same funder/actor cluster → historically successful launches;
- creator wallet transferring tokens to related wallets before public distribution;
- creator/funder wallets that exit before large follower/KOL inflows.

This should reuse actor clustering and E6.4 insider-allocation evidence rather than creating duplicate clustering logic.

Add reason codes such as:

- `RECURRING_CREATOR_CLUSTER`
- `RECURRING_FUNDER_CLUSTER`
- `ROTATING_FRESH_DEPLOYERS_SHARED_FUNDER`
- `REPEATED_EARLY_ALLOCATION_CLUSTER`
- `REPEATED_CREATOR_DUMP_PATTERN`
- `REPEATED_SUCCESSFUL_LAUNCH_PATTERN`
- `INSUFFICIENT_CREATOR_HISTORY`
- `CREATOR_HISTORY_CONFLICTED`

---

## 6. Profitability and manipulation views

The graph must distinguish at least three different concepts:

1. **Token outcome** — did the token perform well or fail?
2. **Creator/deployer profit behaviour** — did creator/related wallets make money, transfer, dump, or retain?
3. **Follower/public outcome** — did later entrants have a viable sellable market or suffer severe drawdown/liquidity loss?

Do not equate creator profitability with token quality. A creator can profit from a rug.

Where current data permits, derive:

- creator realized PnL;
- related-cluster realized PnL;
- early buyer cluster PnL;
- public/shadow entry outcome;
- creator exit lead time before major dump;
- percentage of supply distributed before/after peak;
- creator/cluster retained supply at important horizons.

Unknown accounting must remain null/UNKNOWN.

---

## 7. UI / Graph explorer

Add a new read-only route such as:

`/wallet-graph`

and optionally token-scoped embedding on token detail.

The visualization should support:

- node-link graph;
- creator/deployer wallet nodes;
- funder / related actor-cluster nodes;
- token nodes;
- pool/migration nodes only when useful;
- directional edges;
- click-to-inspect side panel;
- bounded graph depth;
- filters for date, venue, outcome, role and risk;
- search by wallet or mint;
- expand-neighbours action that remains bounded and server-authorized read-only.

Do not send raw provider payloads or credentials to the browser.

### Essential visual encodings

Use distinct visual states for:

- creator/deployer;
- smart-money buyer;
- funder;
- related/side wallet;
- winner token;
- failed/rug token;
- UNKNOWN token outcome;
- verified vs inferred/conflicted relationships.

Never represent UNKNOWN as green/safe.

### Required summary panels

When selecting a wallet, show:

- Creator Reputation + confidence;
- tokens created;
- winners / severe failures / rugs;
- median MFE/MAE;
- realized PnL if available;
- creator dump frequency;
- recurring funder/side-wallet relationships;
- recent launches;
- common launch venues;
- evidence freshness.

When selecting a token, show:

- creator/deployer;
- funder/related cluster;
- first-block/early buyers;
- bundle/sniper cluster;
- current and historical creator reputation;
- prior tokens from same creator/funder cluster;
- token outcome/risk/timeline;
- links to existing token-detail and wallet-detail views.

---

## 8. API / backend projection

Prefer bounded GET-only endpoints, for example:

- `GET /v1/wallet-graph/wallets/{address}`
- `GET /v1/wallet-graph/tokens/{mint}`
- `GET /v1/wallet-graph/clusters/{cluster_id}`
- `GET /v1/creator-reputation/{address}`

Use current auth/read-gateway conventions.

All graph endpoints must support strict bounds:

- max nodes;
- max edges;
- max depth;
- bounded date range;
- cursor pagination where appropriate.

Fail closed on invalid wallet/mint IDs.

No graph endpoint may mutate control state or create an execution decision.

---

## 9. Expert additions

### A. Creator launch chronology

For each creator/funder cluster expose an ordered launch timeline:

`token created → initial allocation → early wallet activity → KOL/social attention → peak → creator sells/transfers → severe drawdown / survival`

This helps distinguish repeatable organic success from repeated pump-and-dump behaviour.

### B. Pre-social positioning

Measure whether creator-related, funder-related or recurring cluster wallets buy/receive allocations before the first meaningful social/KOL burst.

Create advisory measurements such as:

- `related_positioning_before_social_ms`;
- `related_supply_before_social_pct`;
- `cluster_exit_before_social_peak_ms`.

Do not call this insider trading as a factual label without sufficient evidence. Use `PRE_SOCIAL_RELATED_POSITIONING` as a reason/evidence code.

### C. Creator-funder bipartite reputation

A fresh deployer can hide history. Therefore reputation must also be computable at actor/funder cluster level.

Show both:

- raw creator wallet reputation;
- related actor/funder cluster reputation.

The cluster reputation must use confidence and graph-quality penalties.

### D. Outcome-adjusted creator score

Creator reputation should penalize a pattern where the creator makes money but public/shadow entrants systematically lose or liquidity collapses.

Add explicit divergence metrics:

- `creator_profit_public_loss_rate`;
- `creator_exit_before_major_drawdown_rate`;
- `creator_profit_rug_rate`.

These are high-value risk indicators but still require sufficient samples.

### E. Counterparty recurrence

Detect recurring destination wallets for creator token/SOL flows across different mints. Repeated counterparties should strengthen actor-cluster evidence, subject to common exchange/program-address exclusions.

### F. Explainable shortest-path queries

For any token support a bounded explanation such as:

`TOKEN_X <- CREATED_BY WALLET_A <- FUNDED_BY WALLET_B -> FUNDED WALLET_C -> CREATED TOKEN_Y -> RUG_OR_LIQUIDITY_COLLAPSE`

Return the evidence behind every hop.

---

## 10. Testing

Add deterministic tests for:

- creator with repeated winners;
- creator with repeated rugs/severe failures;
- one winner with insufficient history;
- rotating deployers sharing a funder;
- creator/funder cluster with mixed outcomes;
- duplicate transfers/trades;
- out-of-order events;
- reverted/reorged launch;
- creator profitable while public/shadow outcome fails;
- missing wallet history;
- conflicted actor clustering;
- graph max-depth/max-node enforcement;
- no-lookahead creator reputation at historical `as_of` time;
- browser/API cannot mutate or execute;
- deterministic graph projection from identical normalized evidence.

Historical reputation queries must support `as_of` semantics so replay cannot use future launches to evaluate an earlier token.

---

## 11. Definition of Done

E8.6 is complete only when:

- creator/funder/token graph projection exists;
- Creator Reputation is versioned, confidence-aware and no-lookahead;
- recurring creator/funder/side-wallet patterns are exposed;
- token outcomes reuse existing replay labels;
- creator profitability and public/token outcome remain separate concepts;
- bounded GET-only API exists;
- read-only graph UI exists;
- tests cover replay/order/conflict/UNKNOWN/bounds;
- `make verify` passes;
- docs/STATUS.md records exact evidence;
- protected modes remain unchanged;
- Phase 12 remains locked.

## Execution order

Do not interrupt an active implementation task. At the next safe checkpoint:

1. finish the exact active task from `docs/STATUS.md`;
2. finish already-approved P1 extensions ahead of this task if they are still incomplete;
3. implement E6.4 insider-allocation evidence if still incomplete, because this graph consumes it;
4. implement **E8.6 Wallet / Creator Outcome Graph**;
5. keep E11.2 Rust/Yellowstone conditional on measured need;
6. run full verification and update status/docs;
7. commit and push.
