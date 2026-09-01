# MemeRadar Ultra-Early Detection and Shadow Execution Design

Date: 2026-09-01
Status: APPROVED DESIGN DIRECTION — implementation plan pending user review

## 1. Goal

Extend MemeRadar so it can detect and rank newly launched Solana meme tokens as close to launch time as practical, ideally before downstream social-call channels publish them, while preserving the existing fail-closed risk model and keeping all real-money execution disabled by default.

The target is not simply to detect tokens that are already pumping. The target is to estimate, with explainable evidence and calibrated uncertainty, which launches have unusually strong probability of meaningful forward appreciation before the large move has already occurred.

## 2. Chosen operating mode

The selected design is **Option A**:

- implement the complete ultra-early detection, scoring, shadow-entry and guarded execution architecture;
- keep `AUTO_EXECUTION=false` and `MANUAL_EXECUTION=false` by default;
- do not permit automatic real-money transaction submission during this phase;
- require live read-only provider acceptance and paper/shadow evidence before any later live-execution unlock;
- preserve all current kill switches, RBAC, freshness checks, risk blocks and execution boundaries.

This design does not authorize Phase 12 live trading.

## 3. Success criteria

The feature is successful when MemeRadar can produce a deterministic, replayable and explainable decision timeline for a newly launched token that answers:

1. When was the launch first observed?
2. How old was the token when MemeRadar detected it?
3. How long did normalization, risk evaluation, feature extraction and scoring take?
4. What evidence justified REJECT, WATCH, EARLY_WATCH, STRONG_SETUP or ENTRY_READY?
5. What would a configured paper/shadow order have done at that moment?
6. What happened to the token afterward at defined forward horizons?
7. Did MemeRadar identify the opportunity before a configured external/social reference signal, when such a benchmark is available?

No success claim may be made from synthetic latency alone. Production SLOs require live provider evidence.

## 4. Architectural principle

Reuse the current modular-monolith/event-driven architecture. Add focused ultra-early components behind existing provider-independent boundaries instead of creating a second trading stack.

Hot path:

```text
Solana / Launchpad / DEX stream
        |
        v
Ultra-Early Candidate Detector
        |
        v
Canonical Normalize + Deduplicate
        |
        +-----------------------------+
        |                             |
        v                             v
Critical Risk Gate              Micro-Feature Engine
        |                             |
        +-------------+---------------+
                      v
               EarlyScore v1
                      |
           +----------+-----------+
           |                      |
         REJECT                 WATCH
                                  |
                           EARLY_WATCH
                                  |
                          STRONG_SETUP
                                  |
                           ENTRY_READY
                                  |
                         Shadow Entry
                                  |
                     Paper Position / Exit
                                  |
                         Outcome Labels
                                  |
                    Replay / Calibration
```

The LLM remains outside the latency-critical decision path. Narrative generation may enrich alerts after the deterministic decision is already available.

## 5. Detection sources

The detector should use the existing provider abstractions and launchpad/DEX parsing layers. Priority is:

1. direct verified Solana/protocol stream where available;
2. Helius/WebSocket or equivalent streaming source;
3. Pump.fun/PumpSwap lifecycle events;
4. Raydium/Meteora pool creation and migration events;
5. bounded provider fallback such as Birdeye new listings;
6. DEX Screener or similar market source only as enrichment/corroboration, not primary first-detection authority.

The detector must retain source, slot/signature, event time, observed time, ingested time, transport, parser version, protocol registry version and confidence/freshness state.

## 6. Ultra-early latency measurements

Persist and expose the following durations for every candidate where timestamps are available:

- `launch_to_first_observed_ms`
- `first_observed_to_ingested_ms`
- `ingested_to_normalized_ms`
- `normalized_to_risk_complete_ms`
- `normalized_to_features_complete_ms`
- `features_to_score_ms`
- `first_observed_to_decision_ms`
- `first_observed_to_entry_ready_ms`
- `entry_ready_to_shadow_quote_ms`
- `entry_ready_to_shadow_fill_ms`

All latency values must retain measurement quality and provenance. Unknown launch time must remain unknown rather than inferred from provider arrival time.

## 7. Micro-feature engine

Introduce launch-age-aware feature windows optimized for the first seconds and minutes of a token lifecycle.

Required windows:

- 1 second
- 5 seconds
- 15 seconds
- 30 seconds
- 60 seconds
- 3 minutes
- 5 minutes

Required feature families:

### 7.1 Buy velocity

- buys per second;
- quote/SOL inflow per second;
- acceleration between adjacent windows;
- unique buyer growth;
- repeat-buyer ratio;
- buy-to-sell count and volume ratios.

### 7.2 Market acceleration

- price/market-cap return by window;
- volume acceleration;
- liquidity growth/decay;
- bonding-curve progress velocity where available;
- migration/graduation proximity and state;
- price impact for configured paper size.

### 7.3 Wallet quality

- independent smart-wallet entries;
- creator-related wallet activity;
- shared-funder clusters;
- fresh-wallet / sniper concentration;
- bundled first-block or near-simultaneous participation;
- early holder concentration;
- known blocked or malicious wallet evidence.

### 7.4 Organic-flow quality

- unique makers;
- transaction-to-maker ratio;
- repeated-size patterns;
- reciprocal/circular flow;
- rapid buy-then-sell round trips;
- concentration of volume in top buyers;
- suspicious self-funding or creator self-activity.

### 7.5 Social/context features

Social data must not block the critical path. When fresh data is available, add:

- unique-author mention acceleration;
- trusted-author/KOL corroboration;
- duplicate-promotion ratio;
- narrative novelty;
- website/X/Telegram metadata presence;
- external-call timestamp for benchmark comparison.

Missing social evidence must reduce confidence where appropriate, not automatically reject a strong on-chain candidate.

## 8. Hard safety filters

The current deterministic risk system remains authoritative. Ultra-early scoring must never override:

- active or unsafe mint/freeze authority policy;
- sellability failure;
- hard liquidity/price-impact limits;
- severe creator dumping;
- extreme holder or related-wallet concentration;
- stale/conflicted critical evidence;
- system/provider kill switch;
- malformed/unverified protocol identity;
- explicit execution-mode lock.

Add launch-specific hardening for:

- suspicious first-block bundle concentration;
- creator/deployer participation inconsistent with configured policy;
- unverifiable pool or migration identity;
- critical unknown state when intended shadow position cannot be quoted safely.

A missing sniper/bundle label is never proof of a clean launch.

## 9. EarlyScore v1

Do not replace AlphaScore. Add a launch-stage score optimized for very young tokens, then hand off to the normal AlphaScore as the sample matures.

Recommended initial weighted structure, fully configuration-driven and subject to calibration:

```text
OrganicFlowAcceleration     25%
WalletQuality               20%
OnChainSafety               20%
LiquidityAndSellability     15%
LaunchMomentum              10%
SmartMoneyConfluence         5%
SocialCorroboration          5%
```

Penalties are applied after the weighted score and can include:

- bundle/sniper concentration;
- creator-related suspicious funding;
- excessive first-wallet concentration;
- wash/circular flow;
- parabolic extension;
- rapidly decaying liquidity;
- provider disagreement;
- evidence incompleteness.

The score must be versioned, e.g. `early-score-v1`, and every component must retain evidence references and reason codes.

## 10. Confidence and state machine

Score magnitude and confidence remain separate.

Initial states:

```text
0-39   REJECT / LOW
40-59  WATCH
60-74  EARLY_WATCH
75-84  STRONG_SETUP
85-100 HIGH_CONFLUENCE
```

`ENTRY_READY` is a state, not merely a score band. It requires:

- score threshold met;
- minimum confidence met;
- all hard risk gates passed;
- critical evidence fresh;
- sellability/quote available for configured paper size;
- liquidity and price impact within policy;
- protected operating modes intact.

## 11. Predictive forward-outcome labels

For research and calibration, label each candidate at fixed future horizons without leaking future data into features.

At minimum record:

- max return at +1m, +3m, +5m, +15m, +30m, +1h;
- drawdown before reaching each target;
- whether market cap crossed configured milestones such as $50K, $100K and $250K;
- time-to-milestone;
- liquidity survival;
- rug/severe-dump outcome;
- whether a quoted/shadow exit remained executable.

Forward labels are research-only and must never be visible to the live decision path at decision time.

## 12. External-call benchmark

Introduce an optional benchmark record for external/public call timestamps such as an operator-supplied social alert source.

Metrics:

- `memeradar_first_seen_at`
- `memeradar_first_watch_at`
- `memeradar_entry_ready_at`
- `external_call_at`
- `lead_time_to_external_call_ms`

This benchmark is for measurement only. External call sources do not receive authority to raise scores or bypass risk rules unless separately normalized as evidence under existing policy.

## 13. Shadow-entry engine

When a candidate reaches `ENTRY_READY`, create a **shadow order intent** instead of a real transaction.

The shadow engine must:

- request a quote using the existing provider-independent quote boundary;
- apply configured paper position sizing;
- model fees, slippage and price impact conservatively;
- persist the intended entry timestamp and quote provenance;
- feed the existing paper ledger/position/exit engine;
- measure missed-fill and price-drift scenarios;
- remain functional when no signer is present.

A shadow order must never call a signing method or submit a transaction.

## 14. Guarded auto-execution architecture

Prepare, but do not unlock, the future auto-execution path.

Required future boundary:

```text
ENTRY_READY
   |
Execution Eligibility Gate
   |
Operator/Policy Unlock
   |
Quote Revalidation
   |
Unsigned Execution Plan
   |
Isolated Signer
   |
Submit
   |
Finality/Reconciliation
```

For the current phase:

```text
AUTO_EXECUTION=false
MANUAL_EXECUTION=false
```

The configuration loader must continue to reject attempts to turn these on unless a later explicit phase changes the protected policy and its acceptance gates.

No private key, seed phrase or wallet secret may be stored in git, logs, fixtures, browser code, database rows or ordinary application configuration.

## 15. Unlock gates for future auto-buy

Automatic real-money execution may only be considered after all of the following are true:

- live read-only provider gate passes;
- stream integrity verified against real network traffic;
- latency metrics measured in production-like conditions;
- shadow/paper dataset reaches a configured minimum sample size;
- calibration demonstrates acceptable precision/recall and drawdown/rug behavior;
- quote/sellability acceptance passes with real provider evidence;
- execution adapter passes simulation/dry-run tests;
- signer isolation and secret-management review passes;
- explicit operator decision unlocks a later execution phase;
- kill switch, max position size, daily loss and exposure limits are active.

No single backtest result can unlock execution.

## 16. Observability

Add metrics and dashboards for:

- candidates detected per minute;
- detection source distribution;
- first-seen latency percentiles;
- decision latency percentiles;
- score distribution by launch age;
- hard-block reason distribution;
- ENTRY_READY rate;
- shadow-fill rate;
- quote failure and sellability failure rate;
- forward-milestone precision by score bucket;
- false-positive/rug rate by score bucket;
- benchmark lead time versus external calls;
- provider reconnect/gap/backpressure counts.

Synthetic and live measurements must be visibly distinguished.

## 17. Replay and backtest requirements

The implementation must reuse the existing deterministic replay architecture.

Replay must reproduce:

- exact candidate ordering;
- event-time windows;
- risk state transitions;
- EarlyScore values;
- confidence;
- ENTRY_READY timestamp;
- shadow order intent;
- paper fills/exits;
- forward outcome labels.

No future observation may enter a feature window before its event-time boundary.

## 18. UI and alerts

Extend the operator UI and Telegram alert payload with a dedicated ultra-early view containing:

- token age;
- first-seen source and latency;
- EarlyScore and confidence;
- buy velocity and acceleration;
- unique buyer growth;
- SOL/quote inflow;
- liquidity and price impact;
- creator/holder/bundle risk summary;
- smart-money confluence;
- state and hard-block reasons;
- shadow-entry status;
- benchmark lead time when available.

Example semantic output:

```text
ULTRA EARLY SIGNAL
Age: 34s
EarlyScore: 91/100
Confidence: 0.84
State: ENTRY_READY
Buy velocity: accelerating
Unique buyers: accelerating
Creator risk: low
Bundle risk: medium
Sellability: pass
Shadow entry: queued
Auto execution: LOCKED
```

The UI must never imply that `ENTRY_READY` guarantees a profitable trade.

## 19. Provider and protocol constraints

Provider SDKs and payload schemas remain outside domain/application layers.

Direct protocol parsing must route only through verified `(program_id, discriminator/tag)` registry entries. Unknown or stale protocol identity fails closed.

DEX Screener/Birdeye-style polling may enrich evidence but should not define the primary launch timestamp if a verified direct-chain event exists.

## 20. Testing strategy

Implementation must be test-driven and include:

- deterministic unit tests for every micro-feature;
- boundary tests for event-time windows;
- duplicate/conflict/reorg/revert tests;
- holder/bundle/creator manipulation fixtures;
- hard-gate precedence tests;
- EarlyScore/config-version tests;
- confidence tests for missing/stale evidence;
- ENTRY_READY eligibility tests;
- shadow order no-sign/no-submit tests;
- replay no-lookahead tests;
- benchmark lead-time tests;
- API/UI projection tests;
- browser acceptance for LOCKED execution status;
- provider-doctor/live-read-only checks that remain `BLOCKED_EXTERNAL` without real credentials.

## 21. Suggested implementation decomposition

The implementation plan should be split into independently reviewable tasks in this order:

1. latency/event model extensions;
2. ultra-early detector and launch timestamps;
3. micro-feature windows;
4. bundle/sniper/creator launch hardening;
5. EarlyScore v1 and confidence;
6. decision-state integration;
7. shadow-entry orchestration;
8. replay/outcome labeling;
9. external-call benchmark;
10. API/UI/Telegram projections;
11. observability and latency dashboards;
12. live read-only provider acceptance tooling;
13. final cross-cutting quality gate and documentation.

Real-money auto execution is explicitly excluded from these implementation tasks. Only its locked interfaces and future eligibility boundaries may be prepared.

## 22. Non-goals

This phase will not:

- automatically enable a wallet signer;
- submit real-money swaps;
- weaken current safety gates to gain speed;
- use an LLM as the primary trade trigger;
- promise a specific hit rate or profit level without measured evidence;
- infer unknown launch timestamps or safety states;
- treat social popularity as proof of quality;
- treat a missing rug/sniper flag as proof of safety.

## 23. Final acceptance gate

The completed phase should end in a state similar to:

`ULTRA_EARLY_DETECTION_READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING_AUTO_EXECUTION_LOCKED`

Required final evidence:

- deterministic tests pass;
- replay reproduces scores and state transitions;
- shadow trading works without signer access;
- all execution flags remain locked/off;
- live provider acceptance is reported honestly as PASS, FAIL or BLOCKED_EXTERNAL;
- benchmark and latency metrics are observable;
- docs and status identify the next unlock requirements.
