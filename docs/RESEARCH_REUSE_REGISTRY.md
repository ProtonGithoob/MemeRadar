# Research Reuse Registry

This file captures externally researched open-source patterns that are useful to MemeRadar. It is a design/reference registry, not a blanket license to copy source code. Codex must verify each upstream license before reusing code. When license status is unclear or restrictive, use only independently implemented architectural ideas and protocol behavior.

## Integration principles

1. Preserve MemeRadar's provider-independent domain/application boundaries.
2. Do not replace deterministic risk gates with third-party scores or LLM opinions.
3. Treat third-party smart-money/KOL labels as corroborating evidence, not unquestioned truth.
4. Prefer native/on-chain verification when available.
5. Every imported signal must retain provenance, observed/occurred/ingested timestamps, freshness and confidence.
6. New low-latency paths must not bypass risk, position sizing or execution policy.
7. New execution code remains disabled while `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.

## High-value references and patterns

### moonbags
Useful patterns:
- common `SignalSource` abstraction across heterogeneous feeds;
- smart-money/KOL WebSocket signals;
- cross-source deduplication and cooldowns;
- dev-wallet/smart-money distribution as exit evidence;
- Jupiter-style execution boundary plus trailing-stop lifecycle.

MemeRadar adaptation:
- introduce a provider-neutral `ExternalSignalPort`/signal normalization layer only if existing ports cannot represent the evidence cleanly;
- map smart-money/KOL signals into existing wallet/confluence observations rather than creating a parallel decision system;
- implement source-level dedupe and correlation IDs before feature aggregation;
- consume smart-money distribution in Exit Engine as one reason-coded signal.

### slightlyuseless/memecoin-trading-bot
Useful patterns:
- strategy plug-in interface decoupled from discovery/wallet/safety/execution;
- launch/migration discovery separation;
- replaceable entry strategies.

MemeRadar adaptation:
- add a versioned `AlphaStrategy` interface above feature snapshots so scoring/decision variants can be replayed and A/B tested;
- strategies must be pure/deterministic for a fixed snapshot/config;
- strategy output cannot override hard risk gates.

### WhiteOwl
Useful patterns:
- unified operator UX for social, holder, launchpad, paper/live and copy-trading evidence;
- modular capability/skills concept.

MemeRadar adaptation:
- use the UX idea only: one evidence timeline for X/KOL, on-chain, smart-wallet, market and exits;
- maintain explicit badges separating observed facts, derived scores, external labels, LLM narrative, paper and live states.

### meme-coins-analyzer
Useful patterns:
- smart-money + Twitter/KOL + launchpad/event monitoring in one event architecture;
- time-series observability and alert taxonomy.

MemeRadar adaptation:
- expand metrics for ingest latency, signal latency, feature latency and decision latency;
- preserve PostgreSQL as durable truth while using Redis only for ephemeral windows/dedupe.

### Solana Trading Lab / replayer-rust
Useful patterns:
- compact historical Pump.fun event storage;
- deterministic event replay for strategy/backtest evaluation.

MemeRadar adaptation:
- Phase 10 must implement event-log replay with no-lookahead protection;
- enable bulk cohort analysis such as `AlphaScore>=X` outcome distributions and signal precision by token age/launch venue;
- optionally extract high-throughput replay into Rust only after profiling proves Python is insufficient.

### pumpr-bot
Useful patterns:
- very short 30-second launch momentum windows;
- unique-buyer and SOL-volume acceleration;
- sell pressure as fast exit evidence.

MemeRadar adaptation:
- add micro-windows `5s/15s/30s/60s` for launch-time features in addition to `1m/5m/15m`;
- derive unique buyers, buy volume, sell volume, buy/sell ratio, net-flow acceleration and buyer-arrival rate;
- these features are advisory components only and must obey minimum-liquidity/security evidence requirements.

### CabalSpy-style labeled wallet intelligence
Useful patterns:
- large labeled KOL/smart-money/whale wallet sets;
- wallet PnL/win-rate ranking;
- multi-wallet cluster signals;
- KOL side-wallet/bundle detection.

MemeRadar adaptation:
- add provider-neutral external wallet-label ingestion with provenance and TTL;
- compare external labels against MemeRadar's own `SmartWalletScore`;
- expose `smart_wallet_confluence`, `tracked_supply_pct`, `external_label_confidence`, `bundle_confidence` and `side_wallet_cluster_confidence` as separate features;
- correlated wallets must still count as one actor cluster in confluence.

### PumpKit / Pump.fun protocol trackers
Useful patterns:
- typed protocol event decoding;
- WebSocket-first lifecycle with HTTP polling fallback;
- launch, graduation, whale trade, creator fee and CTO/fee-redirection events;
- bonding-curve state and progression;
- caller/KOL performance tracking.

Important licensing note:
- do not copy source code where upstream licensing is restrictive/unclear;
- independently implement protocol decoders from official/public protocol contracts and transaction evidence.

MemeRadar adaptation:
- extend Pump.fun protocol normalization with `launch`, `trade`, `graduation`, `creator_fee_claim`, `fee_recipient_change/CTO`, `bonding_curve_progress` and `whale_trade` event kinds where reliably derivable;
- WebSocket/stream is preferred, bounded polling is fallback;
- use caller outcome history to improve `AuthorTrustScore`, but never infer trust from follower count alone.

### yegor104/pumpfun-tracker
Useful patterns:
- wallet-attributed Pump.fun trade decoding;
- per-wallet realized PnL accounting;
- continuity of the same mint across bonding-curve graduation into PumpSwap;
- preserving acquisition history across the migration boundary.

MemeRadar adaptation:
- do not add a second tracker or second wallet ledger;
- extend the canonical wallet/accounting path with a cross-venue continuity invariant keyed by mint and verified migration evidence;
- preserve pre-migration quantity and execution-price cost basis when the same mint moves to PumpSwap;
- reject/downgrade conflicting successor pools, duplicate migration evidence and missing pre-migration state;
- feed continuous history into existing SmartWalletScore/outcome evidence only after policy-appropriate finality;
- implement through `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md` E11.10.

### petershepherd/j33t-intel
Useful patterns:
- historical reconstruction of successful launches and known rugs;
- search for scanner/filter settings that would have detected winners earlier;
- simultaneous evaluation of upside capture and rug rejection;
- explicit early-launch behavioral features such as holder, dev, bundle, authority, liquidity and flow evidence.

MemeRadar adaptation:
- do not create a parallel Potential Score or Rug Risk Score;
- use the existing replay/backtest/calibration stack to evaluate current EarlyScore/AlphaScore/risk policy candidates;
- create time-split winner-vs-rug cohorts and optimize only on TRAIN while reporting VALIDATION/TEST unchanged;
- compare early detection age/market cap against false-positive/rug-acceptance costs;
- never auto-promote the winning configuration;
- implement through `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md` E10.3.

### VitalikCholan/solana-dynamic-indexer
Useful patterns:
- Anchor IDL parsing and validation;
- automatic discovery of instructions/events/accounts;
- IDL-assisted decoder/schema scaffolding;
- real-time plus backfill operational model.

MemeRadar adaptation:
- do not replace typed canonical persistence with dynamic runtime DDL;
- E8.4 remains the authority for verified `(program_id, discriminator/tag)` routing, gaps, backfill and replay;
- optionally add an offline developer tool that parses an Anchor IDL and emits a reviewable protocol-registry/decoder scaffold plus fixture skeletons;
- unreviewed IDLs must never auto-register into production runtime;
- implement through `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md` E8.5 only after higher-priority validation work.

### Abdullateef1x/whale-sentinel
Useful patterns:
- realtime whale activity presentation;
- wallet reputation/classification;
- accumulation/distribution and buy/sell-pressure interpretation;
- DEX swap-centric smart-money monitoring.

MemeRadar adaptation:
- no second whale/smart-money engine is warranted because SmartWalletScore, actor-cluster dedupe, micro-flow, confluence and ExitRisk already cover the core capability;
- use this repository only as a regression/reference source when reviewing wallet reputation and accumulation/distribution features;
- Jupiter/DFlow execution ideas are explicitly out of scope for this research integration and must not unlock execution.

### Yellowstone gRPC / Solana-Sniper-Rust-Bot pattern
Useful patterns:
- sub-second account/transaction streaming;
- native Pump.fun/PumpSwap/Raydium/LaunchLab decoding;
- separate low-latency hot path;
- blockhash refresh, signature dedupe and routing concerns in execution systems.

MemeRadar adaptation:
- define an optional future `LowLatencyDexEventSource` using Yellowstone gRPC;
- keep normalized events identical to the existing provider contracts;
- if performance requires it, implement a Rust sidecar only for ingestion/decoding, communicating over a versioned internal contract;
- never let the sidecar score risk or authorize trades;
- measure `chain_event_to_ingest_ms` and `chain_event_to_decision_ms` before/after extraction.

### native Pump.fun SDK pattern
Useful patterns:
- deterministic instruction construction;
- bonding-curve and AMM migration state;
- fee and creator-fee mechanics.

MemeRadar adaptation:
- first use this knowledge for transaction decoding/simulation and fee-model accuracy;
- future execution transaction construction belongs behind `ExecutionPort` and remains disabled until Phase 12 acceptance.

### GMGN-style token / smart-money signal APIs
Useful patterns:
- smart-money/KOL positions;
- holders/traders/dev-wallet information;
- token risk indicators and social links;
- real-time event triggers including smart-money buy, large buy, CTO and bundler sell.

MemeRadar adaptation:
- use as a secondary `CrossValidationProvider`, never primary authority;
- reconcile GMGN-style evidence with Helius/Birdeye/native on-chain evidence;
- agreement may increase confidence, disagreement must generate explicit `CONFLICTED` state/reason code;
- external rug/security claims never replace deterministic authority/holder/flow checks.

## Target correlation pipeline

The desired high-value correlation path is:

```text
X/KOL mention
    +
Pump/DEX protocol event
    +
smart-wallet / whale entry
    +
micro-flow acceleration
    +
holder / bundle / side-wallet checks
    +
liquidity / sellability
    +
deterministic security gate
            |
            v
      FeatureSnapshot
            |
      AlphaStrategy
            |
       AlphaScore
            |
    DecisionStateMachine
            |
      alert / paper entry
            |
 position + creator/smart-money distribution monitoring
            |
        Exit Engine
```

The key product differentiator is correlation: no single X mention, wallet label, third-party token score, launch event or LLM output should independently authorize an entry.
