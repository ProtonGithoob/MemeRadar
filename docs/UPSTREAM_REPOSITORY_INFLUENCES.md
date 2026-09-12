# Upstream Repository Influences and Adopted Capabilities

This document records external open-source repositories that were reviewed while evolving MemeRadar, which ideas/capabilities influenced MemeRadar, what was independently implemented or adapted into the existing architecture, and what was intentionally rejected to avoid duplicate or unsafe subsystems.

> Important: this is an architecture/provenance ledger, not a claim that upstream source code was copied verbatim. MemeRadar's integration policy is to prefer independent implementation of useful behavioral patterns and public protocol semantics inside MemeRadar's provider-neutral contracts. Upstream licenses must be verified before any direct code reuse.

Protected modes remain unchanged:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Phase 12 remains locked.

## Summary matrix

| Upstream repository | Useful upstream capability/pattern | MemeRadar adoption | MemeRadar implementation/result |
|---|---|---|---|
| `MadeOnSol/robinhood-chain-sdk` (MIT) | Robinhood token snapshots, KOL consensus, buyer quality, top traders, flow, holders, bundle, risk and LP-removal API surfaces | **Optional LIVE_SHADOW evidence only** | Independently implemented `MadeOnSolRobinhoodAdapter`; normalized observations are persisted through the existing observation repository, with no provider score or execution authority |
| `ultranumblol/solana-meme-analyzer` (license not identified) | Insider-pattern investigation concepts | **Concept only** | Existing `HolderGraphAnalyzer`/`InsiderAllocationAnalyzer` now treats explicit LP/burn/program/system flags as exclusions and low-native-balance as supporting evidence only; no source was reused |
| `MadeOnSol/madeonsol-sdk` | KOL/smart-wallet intelligence, deployer intelligence, coordination, bundle cohorts, transfer-delta/holdings, DEX tape, token risk and momentum/velocity concepts | **High-value patterns adopted; provider scores are not authoritative** | E11.4-E11.9 signal hardening: sustained surge/revival, economic move validation, deployer self-activity/transfer delta, sniper/bundle footprint, lock/vesting/unlock evidence, execution-vs-market price semantics |
| `yegor104/pumpfun-tracker` | Pump.fun bonding-curve → PumpSwap continuity, per-wallet realized PnL, live trade attribution | **Continuity pattern adopted** | E11.10 cross-venue wallet position continuity, canonical trade IDs, migration/transfer continuity and PnL/accounting integrity |
| `petershepherd/j33t-intel` | Reconstruct historical winners/rugs, early behavioral features, scanner-threshold optimization | **Research methodology adopted** | E10.3 Winner-vs-Rug optimizer, bounded grid search, early-detection vs safety metrics, TRAIN/VAL/TEST/no-lookahead discipline; existing risk engine retained |
| `VitalikCholan/solana-dynamic-indexer` | Anchor IDL-driven decoding/schema bootstrap, real-time + backfill indexing, reliability patterns | **Tooling/architecture ideas only** | Optional E8.5 IDL inspection/onboarding concept and E11.2 low-latency/provider-neutral ingestion seam; runtime dynamic DDL explicitly rejected |
| `Abdullateef1x/whale-sentinel` / Solana Whale Sentinel | Whale accumulation/distribution, smart-money reputation, buy/sell pressure, realtime trading-terminal UX, secure backend provider proxying | **Concepts compared with existing capabilities; duplicate engines rejected** | Existing SmartWalletScore, micro-flow/confluence, wallet graph, provider adapter boundaries and workstation UI direction cover these concepts; no second whale/risk engine created |

---

## 1. MadeOnSol / madeonsol-sdk

Repository: `MadeOnSol/madeonsol-sdk`

### Upstream capabilities reviewed

The SDK exposes/references a broad Solana intelligence surface including:

- KOL wallet trade feeds and leaderboards;
- multi-KOL coordination detection;
- deployer reputation/intelligence;
- early deploy/sniper feeds;
- alpha-wallet scoring and linked-wallet clustering;
- token risk factors;
- bundle cohorts and remaining supply held;
- universal wallet PnL;
- verified holdings and transfer-delta evidence;
- wallet tracking;
- Pump.fun graduation events;
- DEX trade streaming;
- market-cap/volume/MEV velocity concepts;
- price alerts and webhooks.

### What MemeRadar adopted

MemeRadar did **not** make MadeOnSol a required runtime dependency and does not accept a third-party score as trading authority. Instead, the most useful missing behavioral patterns were converted into deterministic, provider-independent MemeRadar evidence.

#### E11.4 — Sustained Surge / Revival Validation

Inspired by the need to distinguish meaningful momentum from transient price marks.

MemeRadar added/strengthened:

- `SURGE`, `REVIVAL`, `NONE`, `UNKNOWN` regimes;
- sustained-duration/sample requirements;
- real buy/sell activity and volume confirmation;
- unique-buyer/liquidity evidence where available;
- one-tick spike rejection;
- revival only after actual trading resumes;
- freshness, confidence, provenance and reason codes.

Purpose: prevent a thin-liquidity wick or social-only burst from being promoted as real momentum.

#### E11.5 — Economic Market-Move / Tape Validation

MemeRadar added evidence connecting market-cap movement to actual economic buying pressure:

- market-cap delta;
- buy/sell quote volume;
- buy-volume-to-MC-move ratio;
- liquidity-to-MC ratio;
- organic/wash/bot evidence quality;
- reasons such as underfunded MC move, thin-liquidity mark and corroborated move.

Purpose: a large displayed price/MC jump generated by tiny volume must not be treated like a well-funded organic move.

#### E11.6 — Deployer Self-Activity / Transfer Delta

MemeRadar added creator/deployer evidence covering:

- initial creator acquisition;
- post-launch buys/sells;
- current holdings;
- trade-derived expected holdings;
- observed on-chain holdings;
- `transfer_delta`;
- transfers occurring without an observed swap;
- drained creator holdings;
- freshness/provenance/conflict handling.

Purpose: detect unexplained creator token movement and self-activity without falsely asserting malicious intent from one signal.

#### E11.7 — Launch Sniper / Bundle Footprint

MemeRadar added bounded launch-footprint features such as:

- first-N-slot/first-N-second buyers;
- early buyer count;
- sniper-wallet count where evidence exists;
- bundle/actor-cluster count;
- early acquired supply;
- amount still held;
- actor-cluster-adjusted concentration;
- explicit incomplete/unknown evidence.

Purpose: quantify coordinated early supply capture without allowing a provider's binary label to become the canonical truth.

#### E11.8 — Token Lock / Vesting / Unlock Risk

MemeRadar added a provider-neutral evidence seam for:

- locked/unlocked/withdrawn/claimable amounts;
- next unlock time;
- cliff/period/tranche/final unlock semantics;
- upcoming 1h/24h/7d/30d release windows where evidence permits;
- cancelable locks;
- lock provenance/quality.

Purpose: future token-supply release becomes visible to risk and exit analysis. Token vesting locks are kept distinct from LP locks.

#### E11.9 — Execution Price vs Market Price

MemeRadar explicitly separates:

- actual `execution_price` / effective price used for cost basis and PnL;
- independent `market_price` / reference price used for market-cap and momentum analysis;
- source/freshness/provenance of each price.

Purpose: avoid false PnL and momentum conclusions when trade impact makes effective execution price differ materially from the pool/reference price.

### What was deliberately not adopted

- MadeOnSol risk scores as hard trading gates;
- provider KOL/deployer labels as authoritative truth;
- mandatory dependency on MadeOnSol for core scoring;
- wallet signing/execution authority;
- copying provider-specific thresholds directly into production configuration.

See: `docs/MADEONSOL_SIGNAL_HARDENING.md`.

---

## 2. yegor104 / pumpfun-tracker

Repository: `yegor104/pumpfun-tracker`

### Upstream capabilities reviewed

Useful patterns included:

- real-time Pump.fun/PumpSwap trade observation;
- trade attribution to signing wallets;
- per-wallet realized PnL ledger;
- Pump.fun bonding-curve reserve awareness;
- continuous tracking when a mint graduates from bonding curve to PumpSwap;
- whale/dev activity alerts.

### What MemeRadar adopted

The important gap was not another Pump.fun decoder or another wallet ledger. MemeRadar already had lifecycle, wallet and paper-accounting capabilities. The missing invariant was **cross-venue continuity**.

#### E11.10 — Cross-Venue Wallet Position Continuity

MemeRadar implemented:

- canonical mint identity across venue migration;
- `venue` and `canonical_trade_id` on wallet activity;
- wallet position continuity across Pump.fun → PumpSwap and explicitly mapped venue transitions;
- transfer detection;
- bridge/cross-DEX migration handling;
- duplicate canonical trade-ID idempotency;
- continuity quality states;
- no artificial PnL creation on migration;
- deterministic handling of out-of-order events;
- preservation of cost basis and wallet history across venue changes.

Purpose: a wallet that buys on the Pump.fun curve and later sells after PumpSwap migration must remain one logical token position rather than two unrelated histories.

### What was deliberately not adopted

- a second Pump.fun/PumpSwap decoder stack;
- a second standalone wallet PnL database;
- threshold alerts as alpha authority;
- live execution.

See: `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md`.

---

## 3. petershepherd / j33t-intel

Repository: `petershepherd/j33t-intel`

### Upstream capabilities reviewed

The repository's useful research pattern is to reconstruct successful launches and known rugs, analyze early features, and ask what scanner configuration could have detected winners early while rejecting scams.

Signals considered upstream include concepts such as:

- buy/sell ratio;
- bundles;
- holder concentration;
- dev selling;
- liquidity lock;
- mint/freeze authority;
- volume/market-cap relationship;
- momentum;
- transaction timing;
- unique early wallets;
- liquidity growth.

### What MemeRadar adopted

MemeRadar already had most of the underlying deterministic risk/features, so it did not add a competing 0-100 rug engine.

#### E10.3 — Historical Winner-vs-Rug Early Filter Optimization

MemeRadar implemented a deterministic optimizer/research path over its existing features and policy dimensions:

- bounded grid search;
- winner/rug/severe-failure cohorts;
- no-lookahead outcome labels;
- minimum score/confidence/liquidity dimensions;
- price-impact and concentration limits;
- bundle/sniper/deployer-risk dimensions;
- unique-buyer/flow evidence;
- token-age/market-cap early-detection objectives;
- precision/recall and false-positive/false-negative metrics;
- first-detection age/market-cap metrics;
- MFE/MAE and paper outcome evaluation;
- TRAIN/VALIDATION/TEST stability checks.

Purpose: answer *which existing MemeRadar policy configuration historically detected good launches earlier while rejecting rugs*, without automatically rewriting production thresholds.

### What was deliberately not adopted

- a parallel `Potential Score` / `Rug Risk Score` engine;
- future outcome leakage into live scoring;
- automatic promotion of the best backtest configuration;
- token/community reward mechanics unrelated to MemeRadar's alpha objective.

See: `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md`.

---

## 4. VitalikCholan / solana-dynamic-indexer

Repository: `VitalikCholan/solana-dynamic-indexer`

### Upstream capabilities reviewed

Useful architecture/tooling patterns include:

- Anchor IDL parsing;
- automatic schema/decoder generation concepts;
- slot/signature batch indexing;
- real-time `logsSubscribe` ingestion;
- cold-start backfill;
- retry/backoff and graceful shutdown;
- REST/indexer observability.

### What MemeRadar adopted or retained as conditional work

#### E8.5 — Optional Anchor IDL Onboarding Tool

The useful idea is faster development-time onboarding of new Anchor programs. MemeRadar's design keeps this as offline/dev tooling only:

- inspect/validate Anchor IDL;
- enumerate instructions/events/accounts/discriminators;
- normalize type metadata;
- identify unsupported/ambiguous types;
- generate a proposed decoder/protocol-registry scaffold;
- generate fixture skeletons where useful;
- require explicit reviewed program/discriminator mapping before runtime acceptance.

#### E11.2 — Optional Low-Latency Ingestion Sidecar / Benchmark Contract

Related external low-latency Solana indexing patterns motivated a conditional provider-neutral ingestion seam and benchmark methodology:

- Yellowstone/Jito/Shred-style sources may be evaluated behind the existing normalized-event contract;
- compare chain-event-to-ingest/feature/decision p50/p95/p99;
- measure duplicates, malformed events, gaps, recovery, throughput and resource usage;
- adopt a sidecar only when measured latency/throughput benefit justifies it.

### What was deliberately rejected

The dynamic indexer's runtime auto-DDL model is **not** used as MemeRadar's canonical persistence architecture. MemeRadar retains typed domain contracts, reviewed protocol routing and deterministic replay semantics.

Specifically rejected:

- runtime dynamic PostgreSQL DDL as canonical ingestion;
- unreviewed IDL auto-registration;
- a second generic indexing database;
- moving scoring/risk/execution authority into a low-latency sidecar.

See: `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md` and `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_04.md`.

---

## 5. Abdullateef1x / whale-sentinel

Repository family reviewed: `Abdullateef1x/whale-sentinel` / Solana Whale Sentinel.

### Upstream capabilities reviewed

Useful concepts include:

- real-time whale transaction monitoring;
- smart-money accumulation/distribution;
- large-swap detection;
- wallet reputation/classification;
- buy/sell pressure;
- realtime WebSocket UI updates;
- Birdeye-backed market/security data;
- server-side provider proxying so frontend does not expose API keys;
- trading-terminal/Bloomberg-style operator UX.

### MemeRadar decision

Most of these capabilities already existed or were more advanced in MemeRadar:

- `SmartWalletScore` and wallet outcome evidence;
- micro-flow/buy-sell pressure;
- actor-cluster dedupe;
- smart-wallet/KOL confluence;
- creator/wallet outcome graph;
- deterministic risk gates;
- provider abstraction and server-side credential handling;
- realtime/operator UI seams;
- paper positions and exit-risk monitoring.

Therefore MemeRadar intentionally **did not create a second whale engine or second realtime dashboard**.

The main useful influence is architectural/UX confirmation: the operator surface should behave like a dense trading-intelligence workstation where wallet activity, flow, risk and token state can be correlated quickly. This aligns with `docs/FRONTEND_UI_UX_MODERNIZATION.md`.

### What was deliberately not adopted

- duplicate whale classification engine;
- duplicate buy/sell pressure engine;
- duplicate token safety score;
- duplicate realtime whale-only UI;
- new Jupiter/DFlow execution path;
- frontend exposure of provider credentials.

---

## 6. Broader external low-latency Solana patterns

During later repository research, Rust/Yellowstone/Jito-style multi-DEX streaming and gRPC/Shred benchmark patterns were also reviewed.

MemeRadar's response is intentionally conservative:

- keep Python/current ingestion as the default;
- expose a provider-neutral low-latency event-source boundary only if needed;
- benchmark using the same canonical event cohort;
- require zero semantic divergence in normalized events/replay;
- keep risk, scoring, persistence authority and execution outside any optional sidecar;
- keep sidecar disabled unless measurements demonstrate a material benefit.

This prevents premature architecture complexity while preserving a future latency optimization path.

---

## Capability lineage map

```text
MadeOnSol
  ├─ momentum/velocity ideas ─────────────> E11.4 sustained surge/revival
  ├─ economic tape/market evidence ──────> E11.5 move funding validation
  ├─ deployer/holdings/transfer delta ───> E11.6 deployer activity evidence
  ├─ bundle/sniper cohorts ──────────────> E11.7 launch footprint
  ├─ lock/vesting intelligence ──────────> E11.8 unlock-risk evidence
  └─ trade/tape semantics ───────────────> E11.9 execution vs market price

pumpfun-tracker
  ├─ curve → PumpSwap continuity ────────> E11.10 cross-venue continuity
  └─ wallet PnL continuity ──────────────> canonical wallet accounting

j33t-intel
  ├─ winner reconstruction ──────────────> E10.3 winner-vs-rug optimizer
  ├─ rug historical cohorts ─────────────> calibration/replay labels
  └─ scanner threshold search ───────────> bounded TRAIN/VAL/TEST research

solana-dynamic-indexer
  ├─ IDL-driven decoding ────────────────> E8.5 offline IDL onboarding concept
  ├─ realtime/backfill patterns ─────────> existing E8.4 integrity seams
  └─ indexing reliability ideas ─────────> E11.2 conditional benchmark seam

whale-sentinel
  ├─ whale/smart money ──────────────────> existing SmartWalletScore confirmed
  ├─ buy/sell pressure ──────────────────> existing micro-flow confirmed
  ├─ realtime terminal UX ───────────────> frontend workstation direction
  └─ server-side provider proxy ─────────> existing provider boundary confirmed
```

## Integration philosophy

External repositories are used as research references, not as reasons to duplicate subsystems.

For every upstream idea MemeRadar follows this order:

1. identify the useful behavior;
2. audit whether MemeRadar already implements it;
3. if already covered, do not duplicate it;
4. if partially covered, extend the canonical subsystem;
5. preserve provider-independent contracts;
6. preserve provenance/freshness/UNKNOWN semantics;
7. add deterministic replay/tests;
8. keep thresholds versioned/configurable;
9. never grant an external score execution authority;
10. never weaken protected operating modes.

## Related documentation

- `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md`
- `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_04.md`
- `docs/MADEONSOL_SIGNAL_HARDENING.md`
- `docs/ALPHA_20X_100X_PRODUCT_OBJECTIVE.md`
- `docs/WALLET_CREATOR_OUTCOME_GRAPH.md`
- `docs/FRONTEND_UI_UX_MODERNIZATION.md`
- `docs/STATUS.md`

`docs/STATUS.md` remains the canonical ledger for what is actually implemented, verified, TODO, conditional, or BLOCKED_EXTERNAL.
