# Alpha Caller & Multi-Chain Intelligence Design

**Date:** 2026-09-07
**Status:** APPROVED
**Baseline:** `e82aa2b7a3a4543fec1935a79a7a525af2ba7534`

## Objective

Extend MemeRadar from token-first opportunity discovery into a provider-neutral system that also discovers and measures *who finds opportunities early*: X/social researchers, Telegram channels/callers, smart wallets, wallet clusters and cross-chain identities. Fuse that evidence with existing opportunity, risk, liquidity, execution and outcome research without introducing look-ahead leakage or unlocking live-money execution.

Mandatory initial ecosystems remain `SOLANA`, `BNB`, and `ROBINHOOD`. The domain model must remain extensible to Base, Ethereum, Arbitrum and other EVM chains through generic EVM primitives, and to future non-EVM chains through capability adapters.

## External repository research translated into requirements

Do not vendor or blindly copy third-party code. Reimplement only useful patterns behind MemeRadar-owned contracts after license/security review.

- `hypnogaba/solana-signal-trader`: adopt the architectural ideas of per-source Telegram ingestion/parsing, source-specific calibration, historical signal verification, replay and rollback. Do not copy AGPL code.
- `MadeOnSol/robinhood-chain-sdk`: evaluate MIT-compatible KOL/smart-money/deployer/launch-bundle concepts and cross-chain identity evidence, especially Solana-to-EVM correlation. External linkage remains evidence with confidence/provenance, never asserted identity.
- `SoCloseSociety/WhalegodTG`: use the pattern of normalized multi-chain event taxonomy, deduplication, anti-flood handling and provider fallback where it fits existing seams.
- `GoPlusSecurity/goplus-mcp`: evaluate a provider adapter for normalized token/address security on supported EVM/Solana chains. It is enrichment only; missing data stays `UNKNOWN`.
- `AFKmoney/pumpfun-agent`: use only execution-policy research ideas such as TP ladders, trailing exits, developer-distribution exits and drawdown circuit breakers. No live signing/copy-trading is imported.
- `bitlock-wallet/tg-token-scan-bot`: use chain/address resolution ideas only where they improve canonical identity resolution.
- `pumpfun-tracker`: compare wallet-PnL and Pump.fun/PumpSwap continuity semantics with existing MemeRadar wallet continuity before adding anything.

Every adopted external idea must be recorded with source repository, license, capability, local replacement/design decision, and whether code was reused (`NO` by default).

## Canonical identities

Never use ticker/name equality as identity.

```text
AssetId = (chain_namespace, chain_id, asset_address)
WalletId = (chain_namespace, chain_id, wallet_address)
```

EVM addresses are normalized according to existing EVM identity rules. Solana addresses retain Solana semantics. Social identities are separate from wallets.

`CallerIdentity` represents a public/social source identity. `CrossChainIdentityEvidence` links caller/social identities, wallets and clusters only with explicit evidence type, confidence, provider/source, observed_at and provenance. Weak/ambiguous evidence must not become a hard link.

## SocialCallObservation

Normalize X, Telegram and future compliant sources into a common immutable observation:

- source/provider and source-specific message/post ID;
- caller identity;
- original published timestamp plus observed/ingested timestamp;
- edit/delete state where observable;
- exact chain-qualified asset when resolved;
- raw symbol/name only as unresolved evidence, never canonical identity;
- referenced contract/mint/address;
- call intent (`DISCOVERY`, `BULLISH`, `BEARISH`, `WATCH`, `UNKNOWN`);
- declared entry/targets where present;
- disclosure/promotion evidence where observable;
- parser version, confidence and provenance.

Provider adapters may fail independently. Runtime scraping of arbitrary X/Telegram pages must not become a required boot dependency. Compliant/configured providers are optional capabilities.

## Historical caller outcome verification

For every resolved call, capture an event-time market/execution snapshot using data available at or before the call timestamp. Evaluate forward outcomes only in the label/research plane at bounded horizons such as 5m, 15m, 1h, 6h, 24h and 7d.

Research labels include 2x/5x/10x/20x/50x/100x, time-to-multiple, executable MFE/MAE, drawdown, peak executable market cap and liquidity/impact quality. Thin-liquidity mark-price wicks do not count as executable winners. Future outcomes never enter event-time caller features.

## CallerPerformanceProfile

Caller quality is measurement-only until promoted. At minimum measure:

- sample size and evidence coverage;
- early-entry percentile/market-cap/age quality;
- executable win rates by multiple and horizon;
- median executable MFE/MAE;
- rug/failure avoidance;
- consistency and recency stability;
- chain/venue/narrative specialization;
- smart-wallet confirmation rate;
- caller-to-linked-wallet temporal alignment;
- edit/delete survivorship evidence when observable;
- paid/promotion disclosure evidence when observable;
- uncertainty/confidence intervals.

Do not hard-code an intuitive production `CallerScore` weighting. Candidate scoring formulas belong in TRAIN/VALIDATION/TEST research and require ablation/promotion evidence.

## Manipulation and pre-positioning evidence

Add deterministic evidence for suspicious caller behavior without declaring wrongdoing from correlation alone:

```text
linked/related wallet accumulates before public call
-> public call occurs
-> follower/market activity expands
-> linked/related wallet distributes
```

Represent this as `CallerMarketConductEvidence` with temporal deltas, wallet-link confidence, net flows, distribution timing, liquidity context and provenance. Distinguish `PRE_POSITIONING_CORRELATION`, `POST_CALL_DISTRIBUTION`, `COORDINATED_CALL_CLUSTER`, `CALLER_SMART_MONEY_CONFIRMATION` and `INSUFFICIENT_EVIDENCE`.

No accusation or hard identity inference may be generated from weak linkage.

## Caller discovery feedback loop

The system must discover useful callers rather than rely only on a static watchlist:

```text
matured extreme winner/negative control
-> search available historical social observations before the move
-> identify earliest resolved callers
-> backfill their prior calls
-> compute historical profile without future leakage
-> add eligible sources to research watch cohorts
-> measure future calls out-of-sample
```

Caller discovery must include negative controls, late callers, failed calls and rugs. Deleted/edited content is recorded only where a configured provider supplies reliable evidence.

## Alpha convergence

Create measurement-only `CallerConvergenceEvidence` and integrate it with existing smart-money/opportunity evidence. Useful dimensions include independent high-quality callers, cluster-adjusted caller count, time dispersion, smart-wallet convergence, narrative alignment and contradictory/distribution evidence.

Caller evidence cannot override:

- critical contract/security blocks;
- honeypot/non-sellability;
- stale/missing executable quote;
- insufficient liquidity/excessive impact;
- critical deployer/holder/manipulation risk;
- protected operating modes.

## Multi-chain provider architecture

Reuse existing chain-qualified identity and capability routing. Robinhood Chain stays generic EVM (`chain_id=4663`), not a parallel domain architecture. BNB is generic EVM. Add Base/Ethereum/Arbitrum later through configuration/capabilities rather than duplicated engines.

Provider-neutral capabilities should include:

- `social_calls`
- `caller_history`
- `wallet_activity`
- `cross_chain_identity_evidence`
- `token_security`
- `market_quote`
- `execution_quote`

Each provider response is normalized at the adapter boundary with provenance/freshness. Unsupported/missing evidence is `UNKNOWN`, not safe/zero.

## Telegram product surface

Extend Telegram alerts with concise evidence, not hype:

- chain + contract/mint;
- caller convergence and caller historical-quality band;
- earliest-call timestamp and event-time market cap where known;
- smart-wallet convergence/distribution;
- security/liquidity/execution quality;
- MemeRadar decision band;
- explicit research/provenance state.

Never send guaranteed-multiple language. Alerts remain informational/paper while protected modes are locked.

## Paper-auto execution research

Implement a fail-closed `PaperAutoExecutionGate`, not live auto execution. It consumes promoted/approved existing decision evidence plus caller convergence, security, sellability, quote freshness, liquidity, impact and risk evidence. Any critical `BLOCK`, stale evidence, unsupported chain execution, or required `UNKNOWN` returns no paper order.

Exit-policy candidates may research partial TP ladders, trailing protection, liquidity-collapse exits, deployer/caller-linked distribution exits, smart-wallet distribution and drawdown circuit breakers. They remain versioned replay candidates until independently promoted.

## Protected modes

These remain immutable throughout this extension:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No private keys, signing, swaps, snipers, live copy trading or browser live-order controls are introduced. Live-money execution is a separate future design requiring sufficient historical/live-shadow evidence and explicit human-reviewed promotion.

## Research and promotion

All new caller/social/cross-chain features begin measurement-only. Extend canonical replay with historical-real cases when available plus deterministic synthetic fixtures for engineering only. Preserve TRAIN/VALIDATION/TEST separation, negative controls, no-lookahead mutation tests, feature-family ablation, sample adequacy and Wilson/confidence reporting.

Required ablations include caller-only, smart-money-only, opportunity-only, caller+smart-money, caller+opportunity and full fusion versus the existing baseline. `INSUFFICIENT_SAMPLES` is an acceptable result and must not promote weights or execution.

## API/UI boundaries

Add read-only API projections for caller profiles, calls and convergence only after domain/repository contracts exist. Existing authenticated control/manual surfaces remain unchanged. UI may display evidence and provenance but must not introduce live order controls.

## Success criteria

The extension is complete only when:

1. canonical caller/social/cross-chain contracts are deterministic and chain-qualified;
2. Telegram and at least one social-provider seam normalize calls without becoming boot requirements;
3. caller historical outcomes are verified with strict no-lookahead separation;
4. pre-positioning/distribution evidence is explainable and confidence-bounded;
5. caller discovery can find and evaluate new sources using winners *and* negative controls;
6. Solana/BNB/Robinhood share one domain model with generic EVM reuse;
7. Telegram exposes concise caller/smart-money/risk evidence;
8. PAPER_AUTO is fail-closed and live execution remains impossible;
9. replay/ablation reports incremental value or `INSUFFICIENT_SAMPLES` honestly;
10. `make verify` and relevant doctors pass or external blockers are explicitly classified.
