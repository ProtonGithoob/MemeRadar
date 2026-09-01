# MadeOnSol-Derived Signal Hardening — Executable Research Extension

This extension incorporates only the high-value patterns from `MadeOnSol/madeonsol-sdk` that are not already covered by MemeRadar. It does **not** make MadeOnSol a required runtime dependency and does not copy provider score outputs as trading authority.

## Current insertion point

MemeRadar is currently `READY_FOR_PRODUCTION_ANALYSIS_ONLY` through Gate P11, while Phase 12 manual-live execution is intentionally locked. Implement this extension **before any Phase 12 work**, while preserving all protected modes.

Protected defaults remain:

- `ANALYSIS_ONLY=true`
- `PAPER_TRADING=true`
- `MANUAL_EXECUTION=false`
- `AUTO_EXECUTION=false`

## Why this extension exists

MemeRadar already covers:

- 5s/15s/30s/60s/1m/5m/15m flow windows;
- smart-wallet and KOL confluence;
- holder/wallet clustering;
- wash-trading diagnostics;
- liquidity/sellability checks;
- creator distribution exit evidence;
- replay/backtesting/calibration;
- external wallet corroboration;
- stream integrity and protocol verification.

The remaining high-value gaps identified from recent MadeOnSol releases are:

1. sustained surge/revival classification instead of one-tick momentum;
2. economic validation that a market-cap move is supported by real buy volume;
3. deployer self-activity and transfer-without-swap evidence;
4. sniper/bundle footprint as a bounded launch-quality diagnostic;
5. token lock/vesting/unlock risk as first-class evidence;
6. explicit separation between executed trade price and market/reference price in trade-derived analytics.

These are deterministic evidence features. They are not provider scores and cannot bypass MemeRadar risk gates.

---

## Extension E11.4 — Sustained Surge / Revival Validation

### Goal

Prevent thin-liquidity one-tick marks, stale revival prints and social-only bursts from being treated as real momentum.

### Required model

Add a provider-independent `MomentumRegimeSnapshot` or equivalent existing application model with:

- `kind`: `SURGE`, `REVIVAL`, `NONE`, `UNKNOWN`;
- `tier`: configuration-driven classification, never hard-coded as provider truth;
- `started_at`;
- `confirmed_at`;
- `sustained_for_ms`;
- launch/reference market cap;
- current market cap;
- market-cap delta;
- buy/sell trade count;
- buy/sell quote volume;
- unique buyers when wallet evidence exists;
- liquidity and liquidity/market-cap ratio;
- evidence quality/confidence;
- provenance/reason codes;
- model/config version.

### Sustained confirmation

A momentum event must not be emitted from a single observation.

Implement configurable minimum duration and sample-count requirements. Initial fixtures should include a 10-second sustained confirmation case, but the threshold must be configuration-driven and calibrated from MemeRadar replay data.

A candidate that spikes and immediately reverses before the minimum duration must receive a reason such as:

- `MOMENTUM_NOT_SUSTAINED`
- `ONE_TICK_PRICE_SPIKE`

and must not gain positive momentum confidence.

### Revival detection

Add a provider-independent revival pattern:

- token previously inactive for a configurable minimum duration;
- new trading resumes;
- revival requires actual BUY activity and buy volume;
- price movement alone is insufficient;
- missing prior-trade history becomes `UNKNOWN`, not `REVIVAL=false` evidence.

Initial replay fixtures should include a 24-hour inactivity example, but production thresholds must remain configurable and subject to calibration.

### Acceptance

- same event log/config -> same regime snapshot;
- no future leakage;
- one-tick movement cannot become sustained surge;
- price-only revival cannot be confirmed;
- social-only or wallet-only evidence cannot produce a surge/revival classification;
- result is advisory and has no execution authority.

---

## Extension E11.5 — Economic Move Validation

### Goal

Detect market-cap/price movement that is economically unsupported by actual buying pressure.

### Core metric

Add a deterministic `MoveFundingEvidence` or equivalent feature with:

- `market_cap_delta_usd`;
- `buy_volume_usd` or canonical quote-volume equivalent;
- `sell_volume_usd`;
- `buy_volume_to_mc_move_ratio`;
- `liquidity_usd`;
- `liquidity_to_mc_ratio`;
- source/evidence completeness;
- confidence;
- reason codes.

Do not assume USD exists. If only SOL/quote units are reliable, retain quote-unit evidence and only compute USD when a fresh independent price conversion exists.

### Principle

A market-cap move must be corroborated by real tape volume. A large MC increase produced by tiny volume in a thin pool is suspicious evidence, not positive momentum.

Do **not** hard-code MadeOnSol's thresholds as production truth. Implement them only as initial fixture/reference hypotheses, configuration-driven and explicitly pending calibration.

Examples of reason codes:

- `MC_MOVE_UNDERFUNDED_BY_BUY_VOLUME`
- `THIN_LIQUIDITY_MARK`
- `MOVE_VOLUME_EVIDENCE_MISSING`
- `MOVE_VOLUME_CORROBORATED`

This evidence should feed:

- Momentum confidence;
- OrganicFlow diagnostics;
- AlphaScore confidence/penalties where configured;
- replay/calibration artifacts.

It must never create a hard execution PASS by itself.

### Acceptance

Fixtures must distinguish:

1. genuine sustained buy-driven move;
2. large price/MC jump from tiny volume;
3. missing tape data;
4. stale liquidity data;
5. wash/bot volume that should not count as fully organic funding.

---

## Extension E11.6 — Deployer Self-Activity and Transfer-Delta Evidence

### Goal

Improve creator/deployer risk by detecting self-buying, dumping and token movement that occurred without an observed swap.

### Deployer activity snapshot

Extend existing creator/wallet evidence or introduce a provider-independent snapshot containing, when supported by evidence:

- deployer wallet;
- launch timestamp;
- create-transaction initial buy amount;
- initial acquired supply percentage;
- post-launch buys;
- post-launch sells;
- first/last sell timestamp;
- current token holdings;
- current holdings percentage;
- expected trade-derived holdings;
- observed on-chain holdings;
- `transfer_delta = on_chain_holdings - trade_derived_position`;
- tokens transferred out without an observed swap;
- wallet-empty state;
- evidence quality/provenance.

Never infer theft, insider activity or malicious intent solely from transfer delta. It is a deterministic discrepancy signal that requires explanation/corroboration.

Reason codes may include:

- `DEPLOYER_SELF_BUY`
- `DEPLOYER_SELLING`
- `DEPLOYER_HOLDINGS_DRAINED`
- `DEPLOYER_TRANSFER_DELTA_NEGATIVE`
- `DEPLOYER_TRANSFER_DELTA_POSITIVE`
- `DEPLOYER_ACTIVITY_UNKNOWN`

### Integration

Feed this evidence into:

- existing creator/related-wallet risk diagnostics;
- holder graph;
- exit-risk correlation;
- AlphaScore penalties only through versioned configuration;
- replay/calibration.

Do not let external deployer reputation labels replace this internal evidence.

### Acceptance

Replay fixtures must cover:

- normal creator holding behavior;
- creator self-buy then hold;
- creator selling;
- token transfer out without swap;
- token transfer in without swap/airdrop;
- stale or incomplete wallet census;
- duplicate provider observations.

---

## Extension E11.7 — Launch Sniper / Bundle Footprint

### Goal

Quantify early supply capture by sniper/bundled wallets without treating a third-party label as authoritative truth.

Add bounded features such as:

- first-N-slot/first-N-second buys;
- early buyer count;
- identified sniper-wallet count;
- identified bundle actor-cluster count;
- SOL/quote value acquired;
- percentage of supply acquired;
- percentage still held when current holdings evidence exists;
- actor-cluster-adjusted concentration;
- `data_available` / quality state.

Use internal wallet graph/cluster evidence first. External labels may corroborate only.

Suggested reason codes:

- `SNIPER_FOOTPRINT_HIGH`
- `BUNDLED_LAUNCH_EVIDENCE`
- `EARLY_BUYERS_EXITING`
- `EARLY_BUYER_DATA_INCOMPLETE`

No binary `false = clean` assumption. Absence of observed sniper evidence is not proof of safety.

### Acceptance

- actor-cluster dedupe prevents one controller from counting as many independent wallets;
- missing wallet labels lower confidence;
- external classification disagreement becomes explicit conflict evidence;
- no single footprint feature can authorize or reject a trade without the configured risk/score policy.

---

## Extension E11.8 — Token Lock / Vesting / Unlock Risk Evidence

### Goal

Make future token supply release visible to risk, timeline and research layers.

Define a provider-independent `TokenLockSnapshot` / `TokenUnlockEvent` seam capable of representing:

- locker/program identifier;
- deposited/locked amount;
- unlocked amount;
- withdrawn amount;
- claimable amount;
- next unlock timestamp;
- cliff/period/tranche/final unlock type;
- amount scheduled inside 1h/24h/7d/30d windows as evidence permits;
- cancelable-by-sender flag;
- source/provenance/quality;
- snapshot timestamp/expiry.

Important:

- token/vesting locks are not the same as LP locks;
- do not call a token safe merely because it has a lock;
- cancelable locks should be represented distinctly;
- missing lock data is `UNKNOWN`, not `NO_LOCK_RISK`.

Potential reason codes:

- `LARGE_UNLOCK_IMMINENT`
- `LOCK_CANCELABLE_BY_SENDER`
- `LOCK_DATA_UNKNOWN`
- `VESTING_SCHEDULE_PRESENT`

Integrate into:

- token detail timeline;
- risk diagnostics;
- paper exit-risk evidence;
- Phase 10/11 calibration data.

Do not make an external lock provider mandatory; provide a port/fixture seam and only add a live adapter when a documented/legal source is configured.

---

## Extension E11.9 — Executed Price vs Market Price Semantics

### Goal

Avoid mixing trader all-in execution prices with independent market/reference prices in PnL, momentum and replay analytics.

Audit existing normalized trade observations and paper/backtest calculations.

Where not already explicit, distinguish:

- `execution_price` / `effective_price`: derived from actual amounts paid/received for the trade and used for cost basis/PnL;
- `market_price`: pool/reference price independent of that trade size/direction and used for price series/momentum/market-cap calculations;
- price source/provenance/freshness.

Never silently substitute one for the other.

If only one price is available, preserve the type/source explicitly and lower confidence for calculations that require the missing semantic.

### Acceptance

Add regression fixtures where execution price materially differs from market/reference price and verify:

- PnL uses execution/effective price;
- momentum/MC track uses market/reference price;
- missing semantic does not fabricate a value;
- replay remains deterministic.

---

## MadeOnSol provider policy

MadeOnSol may be added later as an **optional corroboration/research adapter** because the upstream SDK is MIT licensed and exposes useful KOL/deployer/risk/holder/tape data. However:

- free-tier live feeds are delayed and are not suitable as MemeRadar's primary early-entry source;
- paid/provider labels or risk scores are never authoritative trading gates;
- MemeRadar must normalize provider data into its own contracts;
- `null` means unknown and must never be converted to zero/false-safe;
- external provider outage must not disable deterministic internal analysis;
- any live provider acceptance is `BLOCKED_EXTERNAL` until credentials/endpoints and terms are verified;
- do not send wallet signing keys or execution authority to MadeOnSol.

## Implementation order

Codex should execute this extension in the following order while Phase 12 remains locked:

1. audit existing feature/risk/trade contracts for semantic overlap;
2. E11.9 price semantics audit/fix first because later evidence depends on correct price semantics;
3. E11.4 sustained surge/revival model;
4. E11.5 economic move validation;
5. E11.6 deployer self-activity/transfer delta;
6. E11.7 sniper/bundle footprint;
7. E11.8 lock/vesting/unlock evidence;
8. wire only missing features into existing correlation/risk/timeline/replay/calibration seams;
9. add deterministic fixtures and no-lookahead tests;
10. run full quality gates;
11. update `docs/STATUS.md` with evidence;
12. keep Phase 12 locked unless separately and explicitly authorized.

## Definition of Done

Each task is done only when:

- existing implementation was audited first to avoid duplication;
- provider-independent model/port/feature exists where needed;
- UNKNOWN/stale/conflicted semantics are explicit;
- deterministic replay/no-lookahead tests pass;
- external labels do not become sole risk authority;
- all new thresholds are configuration-driven/versioned;
- no live-money capability is enabled;
- documentation/status are reconciled;
- full project verification remains green.
