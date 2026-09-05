# MemeRadar — Smart Money Convergence Extension

## Purpose

Extend the existing MemeRadar wallet, replay, graph, scoring, alerting and provider-neutral infrastructure with higher-value smart-money evidence inspired by observed whale/KOL/wallet products, without copying their chain-specific assumptions, scraping fragile pages, creating a second wallet engine, or adding execution authority.

This extension exists only if it improves one or more current product KPIs: earlier detection, extreme-winner recall, rug/severe-dump rejection, executable entry quality, or risk-adjusted paper/shadow expectancy.

## Source audit and scope decision

The following external products are useful only as feature references or optional seed sources:

- FOMO/top-wallet lists: useful as operator-imported seed data for wallet research, never as trusted truth or an execution signal.
- Wind-style real-time monitoring: useful for bounded event rules, wallet/KOL/market convergence windows and alert latency design.
- Hoodwatch-style whale intelligence: useful for whale inflow, conviction, position-change and wallet-overlap concepts; do not import EVM-specific assumptions into Solana logic.
- Stalkchain-style KOL views: useful for historical KOL quality, wallet/KOL linkage and anti-copy-trade warnings; Robinhood-chain-specific logic is out of scope.

Do not add hard runtime dependencies on any of these websites. Do not scrape authenticated/private pages. Do not treat external ranking, PnL or win-rate as authoritative. All imported evidence must retain source, observation time, quality state and evidence refs.

## Reuse existing MemeRadar primitives

Do not create duplicate engines. Extend or compose the existing:

- `TrackedWalletRegistry`, `TrackedWallet`, `WalletActivity`, `WalletTrackingAnalyzer`, `WalletTrackingSnapshot`;
- creator/wallet outcome graph and wallet graph APIs;
- EarlyScore / AlphaScore / asymmetric-alpha projection;
- event-time correlation windows and micro-flow features;
- no-lookahead replay, extreme-winner labels, separability/ablation research and promotion gate;
- bounded alerts/outbox/Telegram path;
- provider capability routing, provenance, freshness and UNKNOWN != SAFE semantics.

## E11.11 — Smart Wallet Historical Quality

Add a measurement-only wallet historical quality projection built from existing wallet activity/outcome evidence.

Required fields where evidence permits:

- sample_count and matured_sample_count;
- realized_pnl and realized_roi coverage;
- win_rate with sample-size/confidence metadata;
- median and distributional return metrics;
- early_entry_rate using token age and market-cap-at-entry when available;
- `hit_2x/5x/10x/20x/50x/100x` participation counts using future-only research labels, never leaked into live-event time;
- severe-failure/rug exposure rate;
- median hold duration;
- repeatability/consistency across independent tokens;
- source diversity and provenance confidence;
- quality state, freshness, version and config hash.

Do not produce a magic wallet score from unsupported data. If a composite is introduced, every component and weight must be versioned, replayable and ablation-tested. Insufficient samples must return `INSUFFICIENT_SAMPLES`, not a low or high score.

## E11.12 — External Wallet Seed Import

Add a provider-independent, bounded import path for operator-supplied wallet seed files. First implementation should support a simple local CSV/JSON file and not require any external website.

Suggested normalized input fields:

- chain;
- wallet_address;
- external_label;
- source_name;
- source_rank optional;
- observed_at;
- evidence_ref optional.

Rules:

1. Validate canonical chain/address identity.
2. Deduplicate idempotently by chain + wallet + source observation identity.
3. External rank/PnL/win-rate metadata is advisory only and must not auto-promote wallet tier.
4. Imported seeds land in WATCH/CANDIDATE unless an operator-configured policy explicitly says otherwise.
5. Never overwrite locally measured wallet history with external claims.
6. Keep a complete provenance trail.
7. Add strict row/file bounds and malformed-record reporting.

This enables optional use of public top-wallet lists without coupling MemeRadar to a webpage or scraper.

## E11.13 — Multi-Wallet Convergence

Add an event-time-bounded convergence projection for a token using existing normalized wallet activities.

Required windows should reuse canonical correlation windows where possible, especially 15s/30s/60s/3m/5m.

Candidate measurements:

- unique tracked buyers;
- unique high-quality tracked buyers;
- cluster-adjusted independent buyer count;
- gross smart-wallet buy notional;
- net smart-wallet inflow;
- new entrants vs add-to-position wallets;
- first smart-wallet entry age;
- first smart-wallet entry market cap;
- median entry age/market cap;
- wallet-quality-weighted inflow as research-only evidence;
- concentration of inflow in one wallet/cluster;
- simultaneous sell/distribution pressure;
- provider/source diversity;
- event freshness and confidence.

Critical anti-manipulation rule: ten addresses controlled by one actor must not count as ten independent smart wallets. Reuse actor-cluster/shared-funder/creator/side-wallet evidence and expose both raw and cluster-adjusted counts.

Convergence is corroborating evidence only. It cannot override launch-risk BLOCK/UNKNOWN, sellability, liquidity, impact or protected-mode gates.

## E11.14 — Wallet Overlap / Cohort Recurrence

Extend the existing graph layer to measure whether wallets that previously co-appeared around successful or failed launches recur together around a new token.

Research outputs may include:

- pairwise wallet co-occurrence count;
- cluster recurrence count;
- winner-cohort recurrence;
- rug/failure-cohort recurrence;
- Jaccard/overlap similarity between the current buyer set and historical cohorts;
- independence-adjusted recurrence;
- temporal recency/decay;
- evidence confidence and sample size.

Do not infer collusion solely from co-occurrence. Shared-funder/transfer/creator/cluster evidence must remain separate and explicit.

## E11.15 — KOL Historical Quality and Wallet/KOL Linkage

Reuse existing social/KOL evidence instead of creating a parallel social engine.

Measurement-only fields may include:

- call sample count and matured sample count;
- historical post-call outcome distribution;
- median token age and market cap at first mention;
- severe-failure/rug-call rate;
- early-call rate;
- repeatability/consistency;
- wallet linkage confidence when a KOL-associated wallet is supported by explicit evidence;
- buy-before-post / buy-after-post timing where evidence is legally and technically available;
- freshness, provenance, quality state and confidence.

Never assume an identity linkage from username similarity. Never auto-copy a KOL trade. Paid-promotion probability or suspicious-call heuristics must be evidence-based and independently testable.

## E11.16 — Cross-Signal Convergence Projection

Create one measurement-only `SmartMoneyConvergenceProjection` (or equivalent existing projection extension), not a second production scoring engine.

It may summarize:

- smart-wallet convergence;
- wallet historical quality;
- wallet-cluster independence;
- KOL corroboration quality;
- social velocity;
- liquidity/market micro-flow confirmation;
- deployer/insider/bundle/sniper risk context;
- provider/source diversity;
- confidence, freshness, reason codes, version/config hash.

The production EarlyScore/AlphaScore may consume only components that pass the existing replay/ablation/promotion process. Until then, the projection is visible for research/operator explanation only.

## E11.17 — Smart Money Distribution / Exit Evidence

Extend existing exit research with smart-money distribution measurements:

- count/quality of tracked wallets reducing positions;
- net tracked-wallet outflow;
- concentration of exits;
- top-quality wallet exit timing;
- coordinated/cluster-adjusted exit count;
- liquidity deterioration occurring with distribution.

Do not directly force paper/live exits from one external wallet action. Evaluate incremental lift through the existing convex-exit replay framework.

## Alerting

Extend existing Telegram/read-only alert projections, do not create a second alert system.

When evidence is available, expose concise reason codes such as:

- `SMART_WALLET_CONVERGENCE_HIGH`;
- `SMART_WALLET_INDEPENDENCE_LOW`;
- `ELITE_WALLET_EARLY_ENTRY`;
- `SMART_MONEY_NET_INFLOW_ACCELERATING`;
- `SMART_MONEY_DISTRIBUTION`;
- `KOL_WALLET_CORROBORATED`;
- `KOL_EVIDENCE_UNVERIFIED`.

UI/Telegram must show counts, timing, quality/confidence and freshness instead of only a single opaque score.

## Replay and acceptance

Every promoted signal must be evaluated with existing no-lookahead infrastructure.

Required cohort analysis:

- future 2x/5x/10x/20x/50x/100x winners;
- rugs/severe failures;
- ordinary winners/non-winners;
- launch-age buckets;
- market-cap-at-decision buckets;
- chain/venue where applicable.

Required metrics:

- incremental precision/recall lift vs current baseline;
- first-detection age and market cap improvement;
- false-positive cost;
- rug/severe-dump exposure;
- executable-entry coverage;
- paper/shadow expectancy after fees/slippage/impact;
- confidence intervals and sample counts;
- ablation per new feature family.

No feature enters production weights because it looks intuitively strong. Promotion requires the existing TRAIN/VALIDATION/TEST separation and human-reviewed strategy promotion gate.

## Explicit exclusions

Do not add:

- copy trading;
- automatic wallet following;
- live-money execution, signing or private keys;
- Robinhood-specific execution logic;
- EVM-only whale assumptions inside Solana models;
- website scraping as a required runtime dependency;
- hard-coded external top-100 wallet rankings as trusted truth;
- duplicate wallet, KOL, social, graph, score, alert or dashboard engines;
- opaque LLM-created wallet/KOL scores;
- guaranteed 10x/20x/50x/100x predictions.

Protected operating modes remain:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Implementation order

Implement only after inspecting current consumers and preserving active multichain work.

1. E11.11 wallet historical quality projection using existing data.
2. E11.12 bounded local seed importer.
3. E11.13 multi-wallet convergence with cluster-adjusted independence.
4. E11.14 wallet overlap/cohort recurrence over existing graph primitives.
5. E11.15 KOL historical quality/linkage by extending current social evidence.
6. E11.16 cross-signal research projection and read-only surfaces.
7. E11.17 distribution/exit evidence.
8. Replay/ablation/promotion evaluation before any production scoring weight change.

For each slice: failing tests -> smallest implementation -> targeted tests -> full `make verify` -> docs/status update. Preserve all existing Solana behavior and keep multichain identities explicit.