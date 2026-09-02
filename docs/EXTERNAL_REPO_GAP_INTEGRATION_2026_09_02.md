# External Repo Gap Integration Plan — 2026-09-02

This document records the gap analysis against four external repositories and defines only the missing, high-value implementation work for MemeRadar. It is an executable Codex contract, not permission to copy source blindly.

Sources reviewed:

- `yegor104/pumpfun-tracker`
- `petershepherd/j33t-intel`
- `VitalikCholan/solana-dynamic-indexer`
- `Abdullateef1x/whale-sentinel`

## Integration rules

1. Preserve the existing MemeRadar architecture, event-time semantics, replay determinism, protected modes and provider-independent boundaries.
2. Do not create parallel scoring, wallet, risk, execution or indexing systems when the capability already exists.
3. Verify upstream licenses before copying any code. Prefer independent implementation of behavioral patterns and public protocol semantics.
4. Every new derived signal must preserve provenance, occurred/observed/ingested timestamps, freshness, evidence quality, reason codes and version/config identity.
5. `UNKNOWN != SAFE` remains mandatory.
6. No new work may enable live execution, signing, `MANUAL_EXECUTION`, or `AUTO_EXECUTION`.
7. Phase 12 remains locked.

---

## Gap matrix

| Upstream | Useful capability | MemeRadar current coverage | Decision |
|---|---|---|---|
| pumpfun-tracker | Pump.fun bonding-curve → PumpSwap migration continuity for the same mint | Lifecycle/migration events already exist, but explicit cross-venue wallet position/PnL continuity invariant is not a first-class acceptance contract | **IMPLEMENT** |
| pumpfun-tracker | per-wallet realized PnL ledger | SmartWalletScore, paper ledger and wallet history already exist | **EXTEND existing wallet accounting only where continuity evidence is missing** |
| j33t-intel | historical winner reconstruction + scanner-setting optimization | Replay/backtest/calibration exist, but there is no explicit winner-vs-rug threshold-search contract aimed at earliest safe detection under a target MC/age | **IMPLEMENT** |
| j33t-intel | rug/scam early behavioral signatures | Deterministic risk, launch risk, holder/bundle/dev/liquidity/wash evidence already exist | **NO parallel risk engine**; reuse as calibration labels/features only |
| solana-dynamic-indexer | generic Anchor IDL → dynamic schema generation | E8.4 has verified protocol routing, replay/backfill and durable stream integrity. Dynamic DDL would weaken typed domain contracts if used as canonical storage | **DO NOT replace canonical ingestion** |
| solana-dynamic-indexer | IDL-assisted decoder/bootstrap for unknown Anchor programs | Useful as optional research/tooling seam for faster protocol onboarding | **IMPLEMENT only as offline/dev tool, not runtime authority** |
| whale-sentinel | whale/smart-money accumulation, buy/sell pressure, reputation | SmartWalletScore, micro-flow, actor-cluster dedupe, confluence and exit pressure already exist | **NO parallel engine** |
| whale-sentinel | live UI stream of whale events | Existing Radar/wallet/operations UI and realtime seam already cover this | **NO duplicate UI** |

---

# Extension E11.10 — Cross-Venue Wallet Position Continuity

**Priority:** P1

**Goal:** ensure a wallet's token position, cost basis and realized PnL remain logically continuous when a Pump.fun token graduates/migrates from the bonding curve to PumpSwap or another explicitly mapped successor venue.

This is an accounting/data-integrity capability. It is not an execution capability.

## Required implementation

### Domain contracts

Add/extend provider-neutral records sufficient to represent:

- canonical mint/token identity;
- source venue/protocol;
- successor venue/protocol;
- migration/graduation event reference;
- migration event time;
- wallet identity;
- pre-migration token quantity;
- pre-migration quote/SOL cost basis;
- post-migration carried quantity;
- post-migration realized/unrealized PnL inputs;
- continuity quality: `VERIFIED`, `PARTIAL`, `UNKNOWN`, `CONFLICTED`, `INVALID`;
- evidence/provenance references;
- parser/schema/config version.

Prefer extending the existing wallet-position/accounting model rather than adding an unrelated ledger.

### Continuity invariants

1. The mint is the canonical asset identity across migration.
2. A venue migration must not reset wallet acquisition history or cost basis.
3. Duplicate migration events are idempotent.
4. Out-of-order trades around the migration boundary must replay deterministically.
5. A trade may belong to exactly one canonical venue event after normalization; no double counting across Pump.fun and PumpSwap.
6. Migration itself is not a buy/sell and must not manufacture PnL.
7. Unknown or conflicting migration evidence must mark continuity `UNKNOWN/CONFLICTED`; never silently stitch incompatible histories.
8. Realized PnL uses actual execution/effective trade prices, not market/reference price.
9. Market/reference price remains for valuation/momentum only.
10. Reorg/revert corrections must be able to retract a migration boundary and recompute the wallet ledger deterministically.

### Application behavior

- Add a `CrossVenuePositionContinuity`/equivalent service in the existing wallet/accounting application layer.
- Reuse canonical normalized lifecycle events from E2.5/E8.4.
- Reuse existing wallet actor-cluster identity where appropriate, but preserve raw wallet-level accounting.
- Feed the continuous history into SmartWalletScore outcome statistics only after evidence is final enough for the current policy.
- Ensure smart-money entry/exit behavior spanning migration is represented as one token lifecycle.
- Do not let migration continuity itself add AlphaScore points.

### Persistence / replay

- Persist only additional fields/entities that cannot be reconstructed safely from current durable events.
- If a migration is needed, make it reversible.
- Replay must produce identical wallet quantity, cost basis and realized PnL for forward and shuffled delivery orders after canonical event sorting.
- Add JSON fixture covering at least:
  - normal Pump.fun → PumpSwap migration;
  - wallet buys before and sells after migration;
  - partial sell before and after migration;
  - duplicate migration event;
  - migration delivered after first PumpSwap trade;
  - conflicting successor pool;
  - reorg/reverted migration;
  - missing pre-migration state.

### Acceptance

- No quantity or PnL discontinuity at migration for a valid same-mint lifecycle.
- No duplicate trade/PnL counting.
- Same canonical event set produces the same ledger regardless of delivery order.
- Missing/conflicting evidence is explicit.
- Existing SmartWalletScore remains backward compatible.
- Protected modes unchanged.

---

# Extension E10.3 — Historical Winner-vs-Rug Early Filter Optimization

**Priority:** P1

**Goal:** use the existing deterministic replay/backtest/calibration stack to answer:

> Which threshold/policy configuration would have detected historically successful launches as early as possible while rejecting known rugs and manipulation patterns, without look-ahead?

Do not create a second scoring engine. This extension evaluates existing EarlyScore/AlphaScore/risk features and candidate policy configurations.

## Required implementation

### Dataset/cohort contract

Create a provider-free research dataset schema that can identify labeled historical cohorts:

- `WINNER`
- `RUG_OR_SEVERE_FAILURE`
- `NEUTRAL/UNKNOWN`

Labels must be generated only from future outcome windows and must never be available to feature calculation at decision time.

Each sample should preserve:

- mint;
- launch venue;
- launch/first-seen time;
- candidate decision timestamps;
- market-cap/liquidity bands;
- EarlyScore/AlphaScore components;
- launch-risk/rug/security evidence;
- bundle/sniper/dev/holder/liquidity/flow features;
- outcome label and future-only evidence;
- parser/strategy/config identities.

### Threshold-search harness

Add a deterministic optimizer/evaluator over bounded, explicit candidate configurations. Candidate knobs may include only existing policy dimensions such as:

- minimum EarlyScore/AlphaScore;
- minimum confidence;
- minimum liquidity;
- max price impact;
- max holder/cluster concentration;
- max bundle/sniper/deployer-risk thresholds;
- minimum unique buyers / buyer-arrival evidence;
- buy/sell ratio and flow requirements;
- minimum buy-volume-to-MC-move ratio;
- maximum token age / target early-detection window.

Do not mutate production config automatically.

### Objective metrics

Report at minimum:

- winner recall;
- rug/severe-failure rejection rate;
- precision;
- false-positive rate;
- false-negative rate;
- median first-detection age;
- p90 first-detection age;
- median market cap at first detection;
- % detected before configurable MC thresholds (e.g. 50K/100K/250K where data permits);
- MFE/MAE by accepted/rejected cohort;
- expected paper-trade outcome under existing fill model;
- stability across train/validation/test time splits.

### Optimization safety

1. Select candidate configurations on TRAIN only.
2. VALIDATION and TEST are immutable out-of-sample checks.
3. No threshold is promoted solely because it maximizes raw return.
4. Penalize configurations that materially increase rug/severe-failure acceptance.
5. Report sample size/confidence and `INSUFFICIENT_SAMPLES` where applicable.
6. Do not optimize against labels unavailable at decision time.
7. Do not automatically modify production EarlyScore/AlphaScore weights or risk gates.

### Artifacts

Produce deterministic JSON/CSV research artifacts with:

- candidate configuration hash;
- train/validation/test metrics;
- Pareto-style shortlist for early detection vs safety;
- reason-coded rejection breakdown;
- cohort breakdown by venue, liquidity band, token age and score band;
- comparison against current baseline configuration.

### Acceptance

- Byte/logically deterministic output from identical dataset/config.
- Demonstrated no-lookahead.
- Baseline is always included.
- A winning candidate is advisory only until explicitly reviewed.
- No automatic promotion to production.

---

# Extension E8.5 — Optional Anchor IDL Onboarding Tool

**Priority:** P2 / conditional

**Goal:** accelerate development-time onboarding of new Anchor programs without weakening MemeRadar's canonical typed protocol registry.

This is inspired by generic IDL-driven indexers but must remain a tooling path only.

## Required implementation

Create an offline/dev command such as:

`python scripts/inspect_anchor_idl.py --idl <file> --program-id <pubkey>`

It should:

- parse and validate an Anchor IDL;
- list instruction/event/account discriminators;
- normalize field/type metadata;
- identify unsupported/ambiguous types;
- generate a proposed protocol-registry manifest or decoder scaffold;
- optionally generate fixture skeletons;
- never auto-register a protocol into production runtime;
- never generate/apply runtime PostgreSQL DDL automatically;
- require an explicit reviewed full-key `(program_id, discriminator/tag)` mapping before canonical ingestion accepts the program.

### Acceptance

- malformed/untrusted IDLs fail closed;
- SQL/code identifiers are sanitized if any scaffold is emitted;
- generated output is deterministic;
- runtime protocol verification remains E8.4's canonical authority;
- no network is required for the base tool.

---

# Explicitly rejected duplicate work

Codex must NOT create:

- a second SmartWalletScore implementation based on whale-sentinel;
- a second buy/sell pressure engine;
- a second rug-risk score that competes with deterministic MemeRadar risk;
- a second realtime dashboard just for whale events;
- a generic dynamic-schema database that replaces current typed persistence;
- a second Pump.fun/PumpSwap decoder stack;
- a new execution/Jupiter/DFlow path as part of this research integration.

Existing MemeRadar subsystems remain the source of truth.

---

# Execution order

The current `docs/STATUS.md` reports Ultra-Early Option A work still in progress. Therefore Codex must NOT interrupt or roll back the current active task.

Execute in this order at the next safe checkpoint:

1. finish the currently active Ultra-Early Option A task(s) recorded in `docs/STATUS.md`;
2. implement **E11.10 Cross-Venue Wallet Position Continuity**;
3. implement **E10.3 Historical Winner-vs-Rug Early Filter Optimization**;
4. implement **E8.5 Optional Anchor IDL Onboarding Tool** only if it does not delay live-read-only validation work;
5. run full verification;
6. update `docs/STATUS.md`, this file, and the research registry with exact evidence;
7. commit/push coherent checkpoints.

Live provider acceptance remains a separate `BLOCKED_EXTERNAL` concern. These extensions must be fully keyless-testable.
