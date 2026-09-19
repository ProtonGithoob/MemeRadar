# Early Alpha Gap Audit

**Audit date:** 2026-09-19  
**Repository:** `Rasman1234/MemeRadar`  
**Audited checkout:** `3358705` (`main`, clean and synchronized with `origin/main`)  
**Scope:** repository code, tests, fixtures, migrations, worker wiring, API/UI read paths, and the current status/roadmap contracts.

## Executive finding

MemeRadar already contains unusually broad, provider-independent building blocks: canonical `chain + mint` identity, launchpad parsers, Solana stream contracts, event-time correlation, deterministic risk, creator/funder/holder graphs, wallet quality/confluence, signal hardening, paper execution, Telegram outbox delivery, replay/no-lookahead tests, extreme-winner labels, and an existing `/ultra-early` read surface.

The main early-alpha gap is integration, not another detector. The current worker starts notification delivery and optional MadeOnSol/GMGN shadow collectors, but does not run a durable Solana launch stream through `UltraEarlyDetector`, fast safety, early feature windows, EarlyScore/decision, lifecycle transitions, persistence, and staged Telegram alerts. The early projections are mostly immutable in-memory objects or injected read catalogs. Real provider verification and live-shadow samples are also unavailable in this checkout.

Therefore this audit does **not** treat a parser, analyzer, or UI field as a complete capability unless the runtime path can reach it and its evidence is durably measured. DexScreener remains a confirmation/benchmark source, not a primary early-discovery source.

## Status vocabulary

- **COMPLETE** — implementation and contract tests cover the capability at the repository/keyless level; live evidence may still be blocked.
- **PARTIAL** — a meaningful implementation exists, but required fields, semantics, stages, or validation are incomplete.
- **MISSING** — no suitable implementation was found.
- **PRESENT_BUT_NOT_CONNECTED** — the implementation exists, but the production-shaped application path does not consume it for this mission.
- **PRESENT_BUT_TOO_SLOW** — the capability exists only behind a latency path that is unsuitable for early capture.
- **PRESENT_BUT_NOT_MEASURED** — the path exists, but per-token or live latency/quality evidence is not persisted.
- **BLOCKED_EXTERNAL** — local contracts/seams exist, but the acceptance item requires unavailable credentials, network, provider access, or live samples.

## Capability matrix

| # | Capability | Status | Repository evidence and current gap |
|---:|---|---|---|
| 1 | Launch discovery | PRESENT_BUT_NOT_CONNECTED | `early_detection.py`, `discovery_collection.py`, `launchpad_dex.py`, and `protocol_stream.py` provide discovery contracts/parsers. The worker does not run a first-class always-on launch stream into the early decision path. |
| 2 | Solana stream ingestion | PRESENT_BUT_NOT_CONNECTED | `helius_stream.py`, `birdeye_stream.py`, `protocol_stream.py`, and E8.4 `stream_integrity.py` cover normalization, cursors, gaps, recovery, and verification. No configured worker consumes them into the normal candidate lifecycle. |
| 3 | Pump.fun discovery | PARTIAL | `PumpFunAdapter` and lifecycle aliases exist in `providers/launchpad_dex.py`; protocol identity entries remain `TODO_VERIFY`/reverify and there is no verified, active live route in the worker. |
| 4 | PumpSwap discovery | PARTIAL | `PumpSwapAdapter` exists and is tested structurally; verified full-key routing and a running live source are not available. |
| 5 | Raydium discovery | PARTIAL | Raydium AMM/CPMM/CLMM adapters and registry seams exist; authoritative program/discriminator verification and active runtime ingestion remain incomplete. |
| 6 | Meteora discovery | PARTIAL | Meteora adapter/registry seams exist; the relevant program identities are planned or need re-verification and are not active in the runtime path. |
| 7 | Jupiter-related market discovery | MISSING | No Jupiter discovery adapter or launch/pair event source was found. Existing Jupiter-like quote/execution concerns do not provide a discovery feed. Do not add one until an actual provider contract and use case are justified. |
| 8 | DexScreener new-pair discovery | PRESENT_BUT_NOT_CONNECTED | `providers/dexscreener.py` can normalize market/pair data, but it is not a primary launch stream and is not wired into early candidate processing. |
| 9 | DexScreener market confirmation | PRESENT_BUT_NOT_CONNECTED | Market quote/metadata adapters and the `/v1/early-radar` boundary exist; confirmation is not connected to durable stage snapshots or benchmark milestones. |
| 10 | Discovery latency | PRESENT_BUT_NOT_MEASURED | `EarlyLatencySnapshot` and `early_observability.py` measure synthetic stage timings, but the required per-token provider/ingestion/decision/Telegram timestamps are not durably recorded. |
| 11 | Event-time correctness | COMPLETE | `event_time.py`, `early_features.py`, `correlation.py`, replay cutoff tests, and E8.4 contracts exclude future observations and use bounded half-open windows. Live stream acceptance is a separate external blocker. |
| 12 | Mint/freeze authority checks | COMPLETE | Solana RPC/token-security evidence and fail-closed risk contracts exist and are tested. A live provider run is not presently available. |
| 13 | Creator/deployer analysis | PRESENT_BUT_NOT_CONNECTED | `creator_graph.py`, `CreatorReputationAnalyzer`, `launch_risk.py`, and signal hardening produce evidence, but early-stage runtime orchestration does not consume it before staged alerts. |
| 14 | Creator funding graph | PRESENT_BUT_NOT_CONNECTED | `creator_graph.py`, `holder_graph.py`, wallet relationship/funding evidence exist; they are not part of a fast-path or persisted early-stage projection. |
| 15 | Holder concentration | PARTIAL | `holder_graph.py` and `feature_windows.py` provide top-holder/top10 evidence. Early windows do not consistently expose top10 delta, accumulation, or distribution as immutable per-stage fields. |
| 16 | Fresh-wallet analysis | PARTIAL | Launch-risk and holder graph parsing recognize fresh wallets, but the early microstructure snapshot lacks a complete event-time fresh-wallet ratio and quality/unknown semantics. |
| 17 | Bundle/sniper detection | PRESENT_BUT_NOT_CONNECTED | `signal_hardening.py`, `kol_bundle.py`, `launch_risk.py`, and E11 fixtures cover bundle/sniper/footprint evidence. It is not wired into the fast safety decision and staged early alerts. |
| 18 | Wallet independence | PRESENT_BUT_NOT_CONNECTED | `confluence.py`, wallet relationship/holder graph modules, and shared-funder logic can distinguish clusters. `EarlyScorer` is not connected to that independent evidence in the live path. |
| 19 | Smart-wallet scoring | COMPLETE | Wallet scoring, shrinkage/sample-size handling, confluence, and provider-independent quality contracts exist with tests. Real-world quality calibration remains unmeasured. |
| 20 | Smart-wallet early entry | PARTIAL | Early/confluence models can carry smart-money evidence, but first-N-block timing, independent count, and early decision persistence are not end-to-end connected. |
| 21 | Buyer/seller acceleration | PARTIAL | `early_features.py` has buy acceleration and basic counts; `correlation.py` has richer flow fields. Seller growth, bounded normalization, and a single connected early snapshot are incomplete. |
| 22 | Unique buyer growth | PARTIAL | Early feature windows expose unique buyers/growth in limited form; unique sellers, rate normalization, and stage persistence are missing. |
| 23 | Volume acceleration | PRESENT_BUT_NOT_CONNECTED | `early_features.py` and `correlation.py` compute volume/net-flow acceleration, but the worker does not feed them into the live early score/alert path. |
| 24 | Liquidity acceleration | PRESENT_BUT_NOT_CONNECTED | Correlation and signal-hardening features include liquidity deltas/acceleration; no connected fast-path projection or durable per-stage value exists. |
| 25 | Market-cap acceleration | PARTIAL | Market-cap observations and signal-hardening growth exist, but the early window model does not expose a complete bounded market-cap velocity/acceleration series. |
| 26 | Trade-size distribution | MISSING | Repeated-size/circular-flow ratios exist, but median trade size, p90, and justified entropy are not a complete early feature contract. |
| 27 | Wash-trading detection | PRESENT_BUT_NOT_CONNECTED | `flow_analysis.py` and E11 signal hardening detect repeated/circular/wash behavior. They are not on the synchronous early safety/organic momentum path. |
| 28 | Coordinated-wallet detection | PRESENT_BUT_NOT_CONNECTED | Funding, cluster, same-block, and relationship evidence exists; no connected early risk projection or alert reason path was found. |
| 29 | Sellability | PRESENT_BUT_NOT_CONNECTED | Quote/sellability checks and `shadow_entry.py`/flow analysis exist; they are not invoked as a fast pre-WATCH gate in the early runtime path. |
| 30 | Slippage/price impact | PRESENT_BUT_NOT_CONNECTED | Quote, impact, and paper execution models exist, but staged early observations do not persist executable buy/sell impact and no connected alert projection uses them. |
| 31 | Liquidity quality | PRESENT_BUT_NOT_CONNECTED | Liquidity/depth/sellability evidence exists in flow/quote/risk modules; a single fast quality gate and per-stage executable notional assessment are missing. |
| 32 | Organic vs manipulated momentum | PARTIAL | Flow analysis, signal hardening, and correlation provide component evidence, but there is no connected, explicit `OrganicMomentumScore` with independent-demand penalties. |
| 33 | Social velocity | PRESENT_BUT_NOT_CONNECTED | Social intelligence/attention modules exist and are advisory; no connected early social-velocity field or live source is available. |
| 34 | Telegram alert latency | PRESENT_BUT_NOT_MEASURED | Alert outbox/provider delivery and bounded observability exist. Required `telegram_queued_at`/`telegram_sent_at` per token and live distribution are not persisted/reported. |
| 35 | Alert deduplication | COMPLETE | `AlertDeliveryService`, outbox identity, early-alpha fingerprinting, retries, and dedup tests exist. Staged early states are not yet projected into this path. |
| 36 | `EARLY_WATCH` | PARTIAL | `EarlyDecisionState`/`EarlyScorer` support it and UI types mention it; the canonical `CandidateState`, persistence transition allow-list, worker, and alert projector do not. |
| 37 | `STRONG_SETUP` | PARTIAL | Generic candidate lifecycle and alerting support it, and early score bands produce it; the early score is not connected to the canonical lifecycle, persisted stage snapshot, or early alert payload. |
| 38 | `HIGH_CONFLUENCE` | PARTIAL | Early score/decision projection and UI support it; canonical lifecycle/outbox mapping and independent-smart-money evidence are not connected. |
| 39 | `ENTRY_READY` | PARTIAL | `EarlyDecisionEngine`, risk/quote gates, shadow entry, and existing lifecycle support it; no end-to-end early discovery-to-paper-entry path is running. |
| 40 | Paper entry | PRESENT_BUT_NOT_CONNECTED | Paper execution and locked shadow entry are implemented and tested. They receive no connected early-stage candidate stream. |
| 41 | Outcome labeling | PARTIAL | `early_replay.py` has future-only forward labels and extreme-winner structures; full per-token stage/timestamp/market-cap persistence and required 1h/6h/24h/72h/7d maturity windows are incomplete. |
| 42 | 2x/5x/10x/20x/50x/100x tracking | PARTIAL | `ExtremeWinnerOutcomeLabeler` has the thresholds, but stage-specific labels and strict executable semantics are incomplete; missing liquidity/impact currently does not always remain UNKNOWN. |
| 43 | Time-to-multiple | PARTIAL | Extreme labels record time-to-threshold from one checkpoint; all requested lifecycle stages and full maturity windows are not represented. |
| 44 | MFE/MAE | PARTIAL | Mark MFE and drawdown fields exist; executable MFE/MAE per stage/notional and explicit market-vs-executed price semantics are incomplete. |
| 45 | Rug/failure labels | PARTIAL | Replay/risk labels cover rug/dump/sellability concepts, but required `rug_detected`, liquidity failure, creator dump, holder dump, and stage-linked failure persistence are not a single contract. |
| 46 | No-lookahead validation | COMPLETE | Replay cutoff, future-feature exclusion, future-label isolation, E8.4 replay equivalence, and related tests are present. |
| 47 | Live-shadow persistence | PARTIAL | Protected modes, shadow scripts, provider health, and database persistence exist; early-stage observations/outcomes are not persisted by a connected live-shadow pipeline. |
| 48 | Missed-winner analysis | MISSING | No `MissedWinnerAnalyzer` or equivalent reason-coded discovery/stage/provider-latency analyzer was found. |
| 49 | False-positive analysis | MISSING | No `FalsePositiveAnalyzer` or equivalent reason-coded post-alert failure attribution was found. |
| 50 | DexScreener benchmark comparison | PARTIAL | `EarlyCallBenchmark` measures an external call timestamp, and DexScreener market adapters exist. There is no exact-mint benchmark record for new-pair/volume/visibility milestones, and historical Trending timestamps must remain UNKNOWN when not authoritative. |

## Gap details and implementation routing

The following are the actionable gaps. Existing components should be extended in place unless a genuinely new responsibility is named.

### A. Discovery and runtime connection (#1–#9, #47)

**What exists:** `packages/application/src/memeradar_application/early_detection.py`, `discovery_collection.py`, `protocol_stream.py`, E8.4 stream integrity, and `packages/providers/src/memeradar_providers/{launchpad_dex,helius_stream,birdeye_stream,protocol_registry}.py` provide parser/normalizer/stream seams. DexScreener is a market adapter. The worker (`apps/worker/src/memeradar_worker/main.py`) currently starts alert delivery and optional MadeOnSol/GMGN collection only.

**Missing:** an application-owned, checkpointed launch stream consumer that passes canonical `chain + mint` candidates through the same decoder/normalizer used by replay, then invokes fast safety and early scoring. Default protocol registry entries also need independently verified full identities before being authoritative. Jupiter discovery is genuinely absent and should remain absent until a supported discovery contract is defined.

**Why it matters:** polling a screener after pair visibility is exactly the late-detection failure this mission targets. Without a durable stream-to-decision path, existing ultra-early code cannot affect alerts or evidence.

**Routing:** extend the existing protocol-stream/worker composition and `UltraEarlyDetector`; do not create a second detector or provider-specific scoring system.

**Tests required:** duplicate and out-of-order events, restart/resume cursor behavior, synthetic gap/backfill, full-key protocol routing, same-decoder replay equivalence, canonical mint deduplication, and provider-unavailable fail-closed behavior. External provider acceptance remains blocked until read-only credentials/network access are available.

### B. Fast safety and early evidence connection (#12–#20, #29–#32)

**What exists:** `launch_risk.py`, `token_security.py`, `flow_analysis.py`, `shadow_entry.py`, creator/holder/wallet graph modules, `confluence.py`, `signal_hardening.py`, and price semantics already preserve evidence provenance and UNKNOWN states.

**Missing:** a small orchestration boundary for the fast path. It must return `PASS`, `CAUTION`, `BLOCK`, or `UNKNOWN` plus `CRITICAL_UNKNOWN`/`NONCRITICAL_UNKNOWN`, use cheap evidence first, and leave deep graph/social enrichment asynchronous. It must connect independent smart-wallet counts, creator/funder links, bundle/sniper evidence, sellability and impact to the early state transition without allowing raw volume or raw wallet count to authorize a signal.

**Why it matters:** expensive enrichment can make an early alert late, while treating UNKNOWN as safe creates false confidence. The current analyzers are individually useful but not a fast gate consumed before WATCH.

**Routing:** compose existing analyzers in one application boundary (prefer `launch_risk.py` or a small adjacent module); reuse existing graph/flow/quote outputs. Do not duplicate wallet, creator, or sellability algorithms.

**Tests required:** PASS/CAUTION/BLOCK/UNKNOWN, critical vs noncritical missing evidence, mint/freeze authority, shared funder, creator-linked wallet, bundle/sniper, wash-volume, thin liquidity, sellability failure, and incomplete optional enrichment fixtures.

### C. Event-time microstructure and organic momentum (#21–#28, #32–#33)

**What exists:** `early_features.py` provides exact-time half-open launch windows and basic buy/sell/flow/unique-wallet/acceleration metrics. `correlation.py` and `feature_windows.py` already have richer unique buyer/seller, net-flow, liquidity acceleration, maker diversity, repeated-size, circular-flow, holder, and signal-hardening fields. `flow_analysis.py` detects manipulated flow.

**Missing:** one connected early snapshot with configurable 30s/1m/2m/5m/10m/15m-style windows (while preserving the existing compatibility windows), buyer/seller rates, volume/liquidity/market-cap second-order changes, trade-size percentiles, fresh-wallet ratio, independent smart-wallet counts, creator-linked ratios, holder deltas, and a bounded `OrganicMomentumScore`. Tiny denominators and evidence quality must stay UNKNOWN or bounded rather than become artificial acceleration.

**Why it matters:** static volume/buyer thresholds reward coordinated launches and fail to distinguish acceleration from a completed pump. Organic momentum must discount wash, same-funder and creator-controlled flow.

**Routing:** extend `EarlyFeatureEngine` to consume/reuse `CorrelationWindowFeatures` and existing flow/graph snapshots. Do not create a parallel `EarlyWinnerDetector` or a second correlation engine.

**Tests required:** event-time boundaries, out-of-order input sorting, no-lookahead, small-denominator normalization, buyer/volume/liquidity acceleration, seller growth, trade-size distribution, wash/circular flow, coordinated clusters, and missing optional evidence.

### D. Staged lifecycle, persistence, and alerts (#10, #34–#40, #47)

**What exists:** `EarlyDecisionState` and `EarlyDecisionEngine` project early states; `CandidateState`/`DecisionEngine` implement the canonical lifecycle; `AlertEventProjector`/`AlertDeliveryService`/outbox implement alert dedup, retry, and Telegram delivery; `EarlyRadarView` and `/ultra-early` already provide an operator surface.

**Missing:** early states in the canonical lifecycle transition allow-list, durable immutable stage snapshots, first-seen/alert timestamps and market-cap/liquidity values, risk invalidation transitions, and alert projection for `EARLY_WATCH` and `HIGH_CONFLUENCE`. The worker must feed these paths. Per-token latency fields need to survive restart and appear in the report.

**Why it matters:** a score displayed in an injected read catalog is not an actionable, auditable early alert. Without immutable transitions and deduped escalation, the system either alerts late or spams.

**Routing:** extend lifecycle/alert projector and reuse generic observations, feature/risk/score snapshots, state transitions, alerts, and outbox. Add only the minimum new durable early-stage projection needed for required fields; do not build another frontend or alert engine.

**Tests required:** monotonic escalation, explicit risk downgrade/invalidation, alert dedup, material escalation, retry/restart, queued-vs-sent latency, idempotent stage snapshot writes, protected modes, and paper-only `ENTRY_READY`.

### E. Outcomes and executable research (#41–#45)

**What exists:** `EarlyOutcomeLabeler`, `ExtremeWinnerOutcomeLabeler`, replay harnesses, no-lookahead tests, paper execution, and signal/price semantics.

**Missing:** stage-specific labels for `FIRST_SEEN`, `EARLY_WATCH`, `STRONG_SETUP`, `HIGH_CONFLUENCE`, `ENTRY_READY`, and first Telegram; 1h/6h/24h/72h/7d peak fields; raw versus executable peak; configurable paper notionals; explicit `time_to_2x` through `time_to_100x`, MFE/MAE, drawdown, liquidity/sellability/creator/holder failure labels. The current extreme labeler treats absent liquidity/impact as executable in some cases, which violates UNKNOWN semantics and can count a thin wick.

**Why it matters:** detection counts alone cannot answer whether an alert preserved executable upside. The research label must only use future data and must not feed live scoring.

**Routing:** extend `early_replay.py` and existing price/quote semantics. Add tests before changing label behavior; retain current protected execution modes.

**Tests required:** future-label isolation, missing liquidity/impact UNKNOWN, thin-liquidity wick rejection, executable entry/exit price distinction, each multiple and horizon, each stage baseline, MFE/MAE, rug/failure labels, and no-lookahead replay.

### F. Research attribution and benchmark (#48–#50)

**What exists:** `WinnerVsRugOptimizer`, `ExtremeWinnerSeparabilityAnalyzer`, calibration and replay/research modules, plus an external-call-only `EarlyCallBenchmark`.

**Missing:** `MissedWinnerAnalyzer`, `FalsePositiveAnalyzer`, reason-code attribution, and an exact-mint DexScreener benchmark record. Historical Trending timestamps must remain UNKNOWN when the provider does not expose authoritative history.

**Why it matters:** a missed future winner and a false positive explain opposite failure modes; hit rate alone will hide both. The benchmark must show whether MemeRadar preceded later visibility without claiming unavailable timestamps.

**Routing:** add one compact research analysis module that consumes existing immutable snapshots/outcomes, and extend `early_benchmark.py` for exact-mint DexScreener observations. Reuse existing separability/calibration metrics.

**Tests required:** no discovery, provider delay, stream gap, late market data, low score, critical UNKNOWN, false bundle positive, smart-wallet/creator data late, Telegram delay; wash/fake wallet/creator dump/liquidity spoof/bundle/sniper/holder concentration/late-alert false positives; exact mint identity and UNKNOWN benchmark evidence.

## Deliberate non-work

- No ticker/name-based matching; reference cases are not hard-coded.
- No Jupiter discovery adapter without a real supported discovery contract.
- No new AlphaScore component merely because E11 evidence exists; signal hardening remains corroboration until replay/calibration justifies promotion.
- No Rust/Yellowstone extraction before measured latency need and provider-independent integrity contracts are complete.
- No live-money execution, mode changes, provider-success claims, or fabricated real-world sample counts.

## Recommended implementation order after Phase 0 approval

1. Add tests for strict executable outcome semantics and staged lifecycle/alert contracts.
2. Add the minimal fast safety orchestration and complete event-time early feature projection by reusing correlation/flow/graph evidence.
3. Connect canonical lifecycle, durable immutable early snapshots, and staged outbox alerts.
4. Connect the existing stream/provider seams in live-shadow mode, with gaps and UNKNOWN fail-closed.
5. Extend future-only labels, missed/false-positive analysis, and exact-mint benchmark/report generation.
6. Extend `/ultra-early` using the existing API/read path, then run local gates and external doctor checks.

## External acceptance blockers

The checkout is engineering-ready for real-data validation but has no sufficient live-shadow sample. Read-only provider credentials/network access are needed for Helius/Birdeye/stream acceptance, real Solana launch observations, Telegram latency, and a matured outcome sample. DexScreener does not legally/technically provide authoritative historical Trending timestamps through the current adapter; those milestones must remain UNKNOWN unless separately sourced and provenance-recorded.

