# Alpha Caller Intelligence Extension

Canonical design: `docs/superpowers/specs/2026-09-07-alpha-caller-multichain-design.md`.

## Mission

Detect not only promising assets but also historically useful *early discoverers*: X/social researchers, Telegram callers/channels, smart wallets and related clusters. Verify every call against event-time market/execution evidence, measure later outcomes in the research plane, detect suspicious pre-position/distribution correlations, and fuse independent caller evidence with MemeRadar's existing opportunity/risk/smart-money system.

This extension is chain-neutral. Initial mandatory chains are `SOLANA`, `BNB`, `ROBINHOOD`; EVM chains reuse generic EVM identity/capability routing.

## P0 contracts

Implement or reuse canonical types for:

- `CallerIdentity`
- `SocialCallObservation`
- `CrossChainIdentityEvidence`
- `HistoricalCallerOutcome`
- `CallerPerformanceProfile`
- `CallerMarketConductEvidence`
- `CallerConvergenceEvidence`

Identity is always chain-qualified by namespace + chain ID + address. Symbols/names are discovery hints, never asset identity.

## P0 ingestion

Add provider-neutral social-call ingestion. Telegram and configured/compliant X/social providers normalize into `SocialCallObservation`; providers are optional and independently degradable. Preserve source ID, published/observed time, edit/delete evidence where available, resolved asset, raw unresolved references, call intent, disclosure evidence, parser version and provenance.

## P0 verification

At call time persist/reconstruct only evidence available at or before the timestamp. Later horizons (5m/15m/1h/6h/24h/7d) produce research labels including executable MFE/MAE and 2x..100x cohorts. Do not count illiquid mark-price wicks as executable outcomes.

## P0 caller quality

Build measurement-only caller profiles from historical outcomes. Include sample adequacy, early-entry quality, executable wins, MFE/MAE, rug avoidance, consistency, specialization, smart-wallet confirmation, linkage confidence and uncertainty. Do not introduce intuitive production weights without replay/ablation/promotion.

## P0 conduct correlation

Detect evidence patterns for linked/related-wallet accumulation before a public call and distribution after it. Report correlations with confidence and provenance; do not convert weak wallet linkage into an accusation or asserted identity.

## P0 discovery loop

Use matured winners and negative controls to identify earliest historical callers, backfill their earlier calls, create research cohorts, then evaluate future calls out-of-sample. Avoid survivorship bias by retaining failures, rugs, late calls and contradictory calls.

## P0 convergence and alerts

Combine independent caller evidence with existing smart-money/opportunity evidence without allowing it to bypass hard risk/execution gates. Telegram should expose caller quality band, caller convergence, earliest-call context, smart-money state, security/liquidity/execution quality, decision band and provenance.

## P0 paper automation

Add only a fail-closed `PaperAutoExecutionGate`. Live signing/copy trading remains excluded. Any required `UNKNOWN`, critical risk block, stale quote, non-sellability, insufficient liquidity or excessive impact blocks paper-auto entry.

## External pattern audit

Evaluate, do not blindly copy:

- `hypnogaba/solana-signal-trader` — Telegram source parsing/calibration/replay; AGPL means reimplement patterns, no code copy.
- `MadeOnSol/robinhood-chain-sdk` — KOL/smart-money/deployer/cross-chain identity concepts; verify license before reuse.
- `SoCloseSociety/WhalegodTG` — normalized multi-chain event/dedupe/fallback patterns.
- `GoPlusSecurity/goplus-mcp` — optional normalized security provider.
- `AFKmoney/pumpfun-agent` — paper exit/circuit-breaker research ideas only.
- `bitlock-wallet/tg-token-scan-bot` — address/chain resolution ideas.
- `pumpfun-tracker` — wallet PnL and Pump.fun/PumpSwap continuity comparison.

Record provenance/license/design decision for every adopted concept.

## Immutable safety

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

New evidence remains measurement-only until the existing human-reviewed promotion process proves incremental out-of-sample value.
