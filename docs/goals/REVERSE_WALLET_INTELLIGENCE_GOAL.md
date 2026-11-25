# Goal: MemeRadar Reverse Wallet Intelligence, Extreme Winner Discovery & PAPER Validation

> **Source.** The owner referenced `GOAL.md` on the local machine, which is not in the repository. The text below is the full goal the owner pasted into the session's `/goal` command (2026-11-25), reproduced as received. If `GOAL.md` differs, `GOAL.md` wins.

## Primary objective

- Extend the existing MemeRadar system with a comprehensive reverse wallet intelligence research capability.
- Do not rely exclusively on newly launched tokens. Reverse-analyze historical extreme winners to discover wallets that repeatedly showed early, profitable and independently reproducible trading behavior.
- Monitor their later public on-chain activity, and evaluate newly discovered token opportunities through the existing Alpha, Risk and PAPER research pipelines.
- Treat suspected pump-and-dump operators primarily as manipulation-risk indicators, not as automatically trusted trading signals.
- Do not build a separate application. Reuse and extend the existing MemeRadar architecture:
  - wallet intelligence;
  - creator graph;
  - canonical event model;
  - discovery workers;
  - risk engine;
  - decision journal;
  - outcome maturation;
  - PAPER execution engine.

## M0 — Existing capability audit

- Inspect the entire existing repository.
- Identify all current wallet scoring, creator analysis, transaction parsing, historical replay, missed-winner, provider and PAPER execution capabilities.
- Resolve previously documented runtime wiring gaps.
- Do not duplicate existing services or databases.
- Preserve all uncommitted work, existing data, backups and execution restrictions.

## M1 — DexScreener extreme winner registry

Implement or extend historical winner research using verified market data sources.

**Outcome classes:** 2x, 5x, 10x, 20x, 50x, and 100x and above.

**Evaluation horizons:** configurable, including 1 hour, 6 hours, 24 hours, 7 days and 30 days.

**Fields to preserve for every token:**
- chain and canonical token address;
- launch and pool creation timestamp;
- initial observable market capitalization;
- price and liquidity history;
- maximum observed multiplier;
- drawdown;
- pool migration history;
- time to peak;
- trading volume;
- executable liquidity evidence;
- creator identity;
- final outcome classification.

**Rules:**
- Include failed, abandoned, rugged and non-performing tokens. Do not train exclusively on winners.
- DexScreener serves as a market discovery and enrichment source. Do not assume its documented public API provides historical wallet trades or OHLC data.
- Use verified historical blockchain providers for missing information.
- Where historical data is unavailable, begin collecting point-in-time market snapshots.

## M2 — Reverse wallet discovery

For historical winner and control tokens, reconstruct actual confirmed transaction histories.

**Identify:**
- verified early buyers;
- verified sellers;
- creator-linked wallets;
- independent wallet participants;
- historical wallet positions;
- funding relationships;
- liquidity providers;
- potential wash-trading behavior;
- potential coordinated manipulation.

**Rules:**
- Distinguish actual swaps from transfers, airdrops, internal routing, liquidity operations and failed transactions.
- Never infer BUY solely because a wallet received tokens.
- Use canonical transaction identity and balance reconciliation.

## M3 — Wallet behavioral fingerprint

Build or extend existing wallet profiles.

**Calculate:**
- total analyzed tokens;
- total verified trades;
- realized PnL;
- unrealized PnL;
- net returns after fees;
- win rate;
- extreme winner participation rate;
- failed-token exposure;
- entry market capitalization distribution;
- entry timing;
- holding duration;
- drawdown;
- exit timing;
- sample size;
- historical data completeness;
- cross-token repeatability;
- copyability.

**Rules:**
- Preserve unknown cost basis as UNKNOWN.
- Exclude future information from every historical wallet ranking.
- A wallet discovered through future outcomes must not be treated retroactively as a known successful wallet before those outcomes became observable.

## M4 — Wallet graph and manipulation detection

Extend the existing wallet graph to analyze:
- shared funding sources;
- repeated cross-token associations;
- creator and deployer relationships;
- temporal synchronization;
- supply concentration;
- coordinated transaction patterns;
- repeated wash-trading indicators;
- liquidity withdrawal evidence;
- distribution and exit risk.

Do not claim that common funding proves common ownership.

**Evidence-based wallet categories:**
- `EARLY_SMART_MONEY_CANDIDATE`
- `MOMENTUM_TRADER`
- `CREATOR_LINKED`
- `POTENTIAL_INSIDER`
- `POTENTIAL_WASH_TRADER`
- `POTENTIAL_MANIPULATION_CLUSTER`
- `MARKET_MAKER`
- `LOW_EVIDENCE`
- `UNKNOWN`

Wallets associated with suspected manipulation must contribute to risk assessment. They must not automatically qualify for copy-trading or entry signals.

## M5 — Real-time public wallet monitoring

Monitor the publicly observable activity of validated wallet research candidates through the existing Solana and EVM provider infrastructure.

**Supported sources:**
- Yellowstone gRPC;
- existing Solana RPC;
- Helius transaction history and parsed-event services;
- Bitquery historical and live data;
- existing Robinhood Chain RPC/indexing adapters, where verified.

**Implement, reusing existing ingestion and canonical event processing:**
- bounded subscriptions;
- persistent cursors;
- deduplication;
- reconnect and gap recovery;
- provider health;
- rate-limit handling;
- stale-event detection;
- evidence completeness.

Do not add multiple providers unless incremental value is demonstrated.

## M6 — Independent early accumulation research

Analyze newly discovered tokens for:
- verified independent buyers;
- repeatable historical wallet quality;
- organic net demand;
- wallet diversity;
- liquidity growth;
- bonding curve behavior;
- creator history;
- social confirmation;
- contract restrictions;
- sellability;
- market regime.

**Rules:**
- Distinguish organic demand from potentially coordinated or manipulated trading.
- Do not generate actionable entry signals solely from suspected pump-and-dump activity.
- Reject or quarantine candidates with critical manipulation, liquidity or contract risks.

## M7 — Chronological copyability backtesting

For every wallet research candidate, evaluate whether historical signals would have been independently useful after realistic observation and execution delays.

**Include:**
- signal availability time;
- provider latency;
- decision latency;
- quote availability;
- slippage;
- price impact;
- protocol fees;
- failed fills;
- exit liquidity;
- token migration;
- complete losses.

**Compare against:**
- the existing MemeRadar baseline;
- random selection;
- a simple momentum baseline;
- the existing smart-wallet baseline.

**Rules:**
- Use chronological walk-forward validation.
- Include matched non-winning tokens.
- Do not use future price peaks to calculate hypothetical executable profits.
- Do not claim that a wallet's historical success can be reliably replicated without evidence.

## M8 — Integration with existing Alpha and Risk engines

- Integrate verified wallet features into the existing Alpha Scoring Engine.
- Measure their incremental value using feature ablation.
- Keep the Risk Engine independent.
- Do not allow a high alpha score to override critical safety gates.
- Do not treat hardcoded arbitrary scoring weights as validated parameters.

**Required before a wallet feature can affect a decision:**
- fresh evidence;
- valid token identity;
- sufficient data coverage;
- no unresolved critical stream gap;
- independent risk assessment;
- executable PAPER quote;
- conservative liquidity assessment.

## M9 — PAPER research and notification integration

Connect qualified, independently validated opportunities to the existing PAPER execution pipeline.

**Implement or verify:**
- point-in-time quote causality;
- simulated order creation;
- idempotent simulated fills;
- ledger persistence;
- position lifecycle;
- risk monitoring;
- outcome maturation;
- Telegram research alerts.

**Restrictions:**
- Do not add LIVE execution, automatic wallet signing or real copy trading.
- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.
- The system must not participate in coordinated market manipulation, or use other traders as exit liquidity through manipulative strategies.

## M10 — Wallet intelligence dashboard

Extend the existing operator dashboards with:
- Extreme Winner Registry;
- Historical Wallet Leaderboard;
- Wallet Research Profiles;
- Wallet Funding Graph;
- Wallet Activity Stream;
- Token Accumulation Analysis;
- Manipulation Risk Monitor;
- Wallet Copyability Reports;
- Missed Winner Analysis;
- Data Coverage and Provider Health;
- PAPER Performance.

**Clearly distinguish:**
- verified observations;
- heuristic classifications;
- suspected manipulation;
- missing evidence;
- unvalidated predictions;
- realized PAPER results.

Never present heuristic scores as calibrated probabilities without statistical validation.

## M11 — Acceptance and testing

Create deterministic and integration tests for:
- historical winner reconstruction;
- wallet trade classification;
- cost-basis reconciliation;
- future-data leakage;
- duplicate trades;
- independent wallet clustering;
- false-positive manipulation detection;
- provider reconnect;
- PostgreSQL persistence;
- restart recovery;
- PAPER execution;
- Telegram fake-transport delivery;
- dashboard API contracts.

**Test infrastructure rules:**
- Use isolated PostgreSQL infrastructure.
- Do not reuse unknown production volumes.
- Do not disable security tests to obtain passing results.

## Required output

1. Existing capability audit.
2. Verified missing functionality.
3. Implemented changes.
4. Data source contracts.
5. Database and migration changes.
6. Runtime wiring proof.
7. Historical evaluation methodology.
8. Before/after metrics.
9. Wallet signal precision and coverage.
10. Realistic PAPER outcomes.
11. Test results.
12. Remaining blockers.

## Execution rules

- If live or historical data is unavailable, continue implementing and validating independent components with deterministic fixtures, and mark fixture-only results accordingly.
- Do not invent performance metrics.
- Do not stop after creating documentation. Implement, integrate, test and validate every feasible in-scope component.

The objective is to discover genuine, independently validated early-market opportunities while detecting and avoiding manipulative trading patterns. It is not merely to identify wallets associated with historical price pumps.
