# External feature gap matrix

Reviewed: 2026-09-26.  This is an audit of the exact candidate capabilities
named in the MemeRadar external-repository integration task.  The repository
and its provider-independent contracts remain authoritative.  No external
source is copied by this report.

Status values are deliberately conservative:

- `ALREADY_BETTER` — MemeRadar already owns a stronger or safer equivalent.
- `ALREADY_EQUIVALENT` — the capability exists with equivalent semantics.
- `EXTEND_EXISTING` — an existing owner needs a bounded extension.
- `NEW_FEATURE_REQUIRED` — a useful capability is not present locally.
- `REFERENCE_ONLY` — use concepts only; do not reuse source.
- `REJECTED` — unsafe or architecturally incompatible.
- `BLOCKED_EXTERNAL` — implementation requires an unverified provider,
  credential, contract identity, or real-data acceptance.

## Solana

| EXTERNAL REPO | CAPABILITY | MEMERADAR EXISTING OWNER | CURRENT MEMERADAR STATUS | BETTER/WORSE/EQUIVALENT | MISSING? | INTEGRATION VALUE | LICENSE | COPY PERMITTED? | IMPLEMENTATION DECISION |
|---|---|---|---|---|---:|---|---|---:|---|
| `CodeMuscle/solbeam` | Helius webhook push ingestion | `wallet_tracking.py`, Helius provider seam | `EXTEND_EXISTING` | Equivalent architecture, missing push adapter | Yes | High for low-latency watched-wallet evidence | MIT | Yes, subject to notice | Extend existing wallet normalization; no second wallet store |
| `CodeMuscle/solbeam` | Smart-wallet watchlists | `wallet_tracking.py`, `wallet_scoring.py` | `ALREADY_EQUIVALENT` | Equivalent | No | Medium | MIT | Yes, subject to notice | Reuse existing watchlist and scoring contracts |
| `CodeMuscle/solbeam` | Buy/sell/transfer classification | canonical event normalizers | `EXTEND_EXISTING` | Existing provider-independent taxonomy is safer, needs coverage | Yes | High | MIT | Yes, subject to notice | Extend canonical classification only |
| `CodeMuscle/solbeam` | DEX classification | protocol registry and normalized events | `ALREADY_BETTER` | Better provider-independent boundary | No | Medium | MIT | Yes, subject to notice | Do not import dashboard classifier |
| `CodeMuscle/solbeam` | Wallet leaderboard | `wallet_scoring.py`, read projections | `NEW_FEATURE_REQUIRED` | Existing statistics, missing explainable projection | Yes | Medium | MIT | Yes, subject to notice | Add a projection only after P0 evidence path |
| `CodeMuscle/solbeam` | Whale alerts | `alert_pipeline.py` | `ALREADY_EQUIVALENT` | Equivalent outbox boundary | No | Low | MIT | Yes, subject to notice | Reuse existing alerts |
| `CodeMuscle/solbeam` | Multi-source price fallback | `price_integrity.py`, `provider_routing.py` | `EXTEND_EXISTING` | Existing quality-aware sources; consensus needs audit | Yes | Medium | MIT | Yes, subject to notice | Extend existing price semantics, never blind fallback |
| `CodeMuscle/solbeam` | Holder/risk presentation | `read_api.py`, token-security projections | `ALREADY_BETTER` | Stronger fail-closed semantics | No | Low | MIT | Yes, subject to notice | No external presentation code |
| `nktkass/pumpr-bot` | Pump.fun create/trade processing | `pumpfun_forward.py`, Pump.fun decoder | `ALREADY_BETTER` | Existing canonical decoder and replay path | No | High | MIT | Yes, subject to notice | Do not copy bot execution code |
| `nktkass/pumpr-bot` | Unique-buyer counting | `correlation.py`, `early_features.py` | `EXTEND_EXISTING` | Existing per-window buyers, missing explicit quality fields | Yes | High | MIT | Yes, subject to notice | Extend current window builder |
| `nktkass/pumpr-bot` | Anti-wash detection | `flow_analysis.py`, `organic_momentum.py` | `EXTEND_EXISTING` | Existing heuristics, missing organic-volume accounting | Yes | Very high | MIT | Yes, subject to notice | Extend `OrganicFlowScore`; no second score engine |
| `nktkass/pumpr-bot` | Buy/sell ratio and net volume | `correlation.py`, `early_features.py` | `ALREADY_EQUIVALENT` | Equivalent, with stronger event-time contracts | No | High | MIT | Yes, subject to notice | Reuse current metrics |
| `nktkass/pumpr-bot` | Short-window momentum | `ULTRA_EARLY_CORRELATION_WINDOWS`, `early_features.py` | `EXTEND_EXISTING` | Existing 1s/5s/15s/30s/60s/3m/5m, missing 10s and explicit velocity aliases | Yes | High | MIT | Yes, subject to notice | Add 10s and derived fields |
| `nktkass/pumpr-bot` | Multiple-wallet confirmation | `smart_money_convergence.py`, wallet graph | `EXTEND_EXISTING` | Existing convergence, needs cluster-adjusted buyers | Yes | Very high | MIT | Yes, subject to notice | Add independence evidence to existing features |
| `nktkass/pumpr-bot` | Autonomous launch/buy/sell execution | `paper_execution.py`, `control.py` | `REJECTED` | MemeRadar is analysis/paper only | No | Negative | MIT | No | Never import or enable execution code |
| `SoCloseSociety/WhalegodTG` | Transaction taxonomy | `event_processing.py`, normalized event models | `EXTEND_EXISTING` | Existing normalized events need canonical category coverage | Yes | High | MIT | Yes, subject to notice | Extend event taxonomy in application layer |
| `SoCloseSociety/WhalegodTG` | CEX/DEX/LP/bridge/MEV labels | provider metadata and evidence policy | `NEW_FEATURE_REQUIRED` | Labels are not yet a first-class registry | Yes | Medium | MIT | Yes, subject to notice | Add only as corroborating evidence |
| `SoCloseSociety/WhalegodTG` | Anti-flood/digest alerts | `alert_pipeline.py`, durable outbox | `EXTEND_EXISTING` | Existing delivery path, missing storm state | Yes | Medium | MIT | Yes, subject to notice | Extend outbox controller; no second bot |
| `SoCloseSociety/WhalegodTG` | Duplicate suppression | durable alert/outbox idempotency | `ALREADY_BETTER` | Stronger durable semantics | No | Medium | MIT | Yes, subject to notice | Reuse current dedupe |
| `SoCloseSociety/WhalegodTG` | API rate-limit semaphores | provider health/routing | `ALREADY_EQUIVALENT` | Existing bounded provider controls | No | Low | MIT | Yes, subject to notice | No copied semaphore code |
| `SoCloseSociety/WhalegodTG` | Multi-source price fallback | `price_integrity.py` | `EXTEND_EXISTING` | Existing source routing, disagreement needs explicit projection | Yes | Medium | MIT | Yes, subject to notice | Extend current service |

## Robinhood Chain and EVM

| EXTERNAL REPO | CAPABILITY | MEMERADAR EXISTING OWNER | CURRENT MEMERADAR STATUS | BETTER/WORSE/EQUIVALENT | MISSING? | INTEGRATION VALUE | LICENSE | COPY PERMITTED? | IMPLEMENTATION DECISION |
|---|---|---|---|---|---:|---|---|---:|---|
| `MadeOnSol/robinhood-chain-sdk` | Named WebSocket subscriptions | `provider_contracts.py`, stream integrity | `EXTEND_EXISTING` | Existing stream contracts lack named independent descriptors | Yes | High | MIT | Yes, subject to notice | Extend provider abstraction; preserve provider guarantees |
| `MadeOnSol/robinhood-chain-sdk` | Subscription-specific filters | provider stream ports | `EXTEND_EXISTING` | Missing first-class per-subscription filters | Yes | High | MIT | Yes, subject to notice | Add descriptor/filter contract |
| `MadeOnSol/robinhood-chain-sdk` | Per-subscription resume | stream integrity/recovery | `EXTEND_EXISTING` | Existing gap/recovery is canonical but not named-sub scoped | Yes | High | MIT | Yes, subject to notice | Extend cursor scope without inventing guarantees |
| `MadeOnSol/robinhood-chain-sdk` | `(sub_id,event_id)` deduplication | event idempotency and canonical identity | `EXTEND_EXISTING` | Canonical dedupe exists; provider context is missing | Yes | High | MIT | Yes, subject to notice | Keep provider and chain identities separate |
| `MadeOnSol/robinhood-chain-sdk` | Stream quality metadata | `stream_integrity.py`, data quality | `ALREADY_BETTER` | Existing fail-closed gap/freshness model | No | High | MIT | Yes, subject to notice | Reuse current quality states |
| `MadeOnSol/robinhood-chain-sdk` | Token-price stream | Robinhood provider seam, price semantics | `EXTEND_EXISTING` | Contract seam exists; live source is external | Yes | Medium | MIT | Yes, subject to notice | Extend read-only adapter, mark blocked without credentials |
| `MadeOnSol/robinhood-chain-sdk` | Enriched DEX trade payload | canonical trade model | `EXTEND_EXISTING` | Raw/decimal-safe model exists, fields need coverage | Yes | High | MIT | Yes, subject to notice | Extend normalized fields, never infer decimals |
| `MadeOnSol/robinhood-chain-sdk` | KOL/smart-wallet evidence | `smart_money_convergence.py`, provider evidence | `ALREADY_BETTER` | Internal graph remains authoritative | No | Medium | MIT | Yes, subject to notice | Keep labels corroborating only |
| `MadeOnSol/robinhood-chain-sdk` | Liquidity-removal evidence | `signal_hardening.py`, token security | `ALREADY_EQUIVALENT` | Equivalent evidence seam | No | High | MIT | Yes, subject to notice | Reuse current diagnostics |
| `MadeOnSol/robinhood-chain-sdk` | Deployer intelligence | creator graph and signal hardening | `ALREADY_EQUIVALENT` | Equivalent measurement-only evidence | No | Medium | MIT | Yes, subject to notice | No provider score authority |
| `pardotfamily/par` | Launch discovery | `evm_protocols.py::ParLaunchAdapter` | `EXTEND_EXISTING` | Adapter seam exists; verified deployment/live evidence absent | Yes | High | MIT | Yes, subject to notice | Finish only after on-chain verification |
| `pardotfamily/par` | Immediate Uniswap V4 lifecycle | lifecycle normalizer | `EXTEND_EXISTING` | Existing lifecycle can model it, but must not use Pump.fun bonding assumptions | Yes | High | MIT | Yes, subject to notice | Add protocol-specific lifecycle tests after verification |
| `pardotfamily/par` | Token-to-market and multi-market mapping | `evm_protocols.py`, normalized markets | `EXTEND_EXISTING` | Mapping seam exists, multi-market evidence incomplete | Yes | High | MIT | Yes, subject to notice | Extend existing adapter |
| `pardotfamily/par` | PoolKey/PoolId and live trades | EVM log reader and protocol registry | `BLOCKED_EXTERNAL` | Contract/event identities require independent verification | Yes | High | MIT | Yes, subject to notice | Keep candidate adapter disabled until verified |
| `bitgrass/Launchpad` | HoodiePad/Doppler V4 launch detection | EVM protocol registry | `NEW_FEATURE_REQUIRED` | No verified HoodiePad adapter | Yes | Medium | MIT | Yes, subject to notice | Candidate read-only adapter only after verification |
| `bitgrass/Launchpad` | CHILD/HOODIE canonical market and PoolKey/PoolId | EVM protocol registry | `BLOCKED_EXTERNAL` | README claims are not authoritative | Yes | Medium | MIT | Yes, subject to notice | Require chain ID, bytecode hash, hook, sample tx |
| `bitgrass/Launchpad` | Rehype hook, limits, locks and fees | token-security/lifecycle evidence | `BLOCKED_EXTERNAL` | External runtime evidence missing | Yes | Medium | MIT | Yes, subject to notice | Keep evidence unknown, never safe-by-default |
| `nirholas/robinhood-trading-bot` | NOXA launch/pool observation | `robinhood.py`, EVM protocol registry | `NEW_FEATURE_REQUIRED` | No verified NOXA identity | Yes | High | Apache-2.0 | Yes, subject to notice | Read-only adapter blocked on independent verification |
| `nirholas/robinhood-trading-bot` | Odyssey curve, graduation and DEX pool | lifecycle and EVM logs | `NEW_FEATURE_REQUIRED` | No verified Odyssey decoder | Yes | High | Apache-2.0 | Yes, subject to notice | Protocol-specific adapter, no NOXA assumptions |
| `nirholas/robinhood-trading-bot` | Holders, concentration, dev and trade flow | supply quality and creator evidence | `EXTEND_EXISTING` | Existing fields, launch-source wiring missing | Yes | High | Apache-2.0 | Yes, subject to notice | Extend normalized launch evidence after verification |
| `nirholas/robinhood-trading-bot` | Real-quote paper fills | `paper_execution.py`, price semantics | `ALREADY_BETTER` | Existing protected paper path is provider-independent | No | High | Apache-2.0 | Yes, subject to notice | Do not copy executor or signer |
| `nirholas/robinhood-trading-bot` | Smart-wallet copy observation | wallet graph and shadow entry | `ALREADY_EQUIVALENT` | Existing research/shadow path | No | Medium | Apache-2.0 | Yes, subject to notice | Keep copy trading disabled |
| `nirholas/robinhood-chain-trading-bot` | Observe → decide → simulate → risk → paper lifecycle | decision engine, paper execution, control | `ALREADY_BETTER` | Stronger protected separation | No | High | Custom/proprietary | No | Concept only; no source reuse |
| `nirholas/robinhood-chain-trading-bot` | Decision/refusal journal | `decision_engine.py`, decision evidence | `ALREADY_BETTER` | Existing replayable reason/evidence contracts | No | High | Custom/proprietary | No | Reuse current journal |
| `nirholas/robinhood-chain-trading-bot` | Strategy failure-mode metadata | strategy promotion/research reports | `NEW_FEATURE_REQUIRED` | No first-class registry found | Yes | Medium | Custom/proprietary | No | Add metadata only; do not affect score by default |
| `nirholas/robinhood-chain-trading-bot` | Kill-switch semantics | `control.py` | `ALREADY_BETTER` | Fail-closed protected kill switch exists | No | High | Custom/proprietary | No | No change |
| `nirholas/robinhood-chain-trading-bot` | Live signed swaps/private keys | `paper_execution.py` | `REJECTED` | Violates task safety boundary | No | Negative | Custom/proprietary | No | Never import |
| `nirholas/robinhood-toolkit` | Verified constants and exact address identity | `evm_chains.py`, protocol registry | `REFERENCE_ONLY` | Useful concept, source is proprietary | Yes | Medium | All Rights Reserved | No | Independently implement only where needed |
| `nirholas/robinhood-toolkit` | Adaptive `eth_getLogs` windows | `evm_rpc.py` | `NEW_FEATURE_REQUIRED` | No adaptive scanner found | Yes | Medium | All Rights Reserved | No | Independent bounded scanner if backfill needs it |
| `nirholas/robinhood-toolkit` | Ticker-collision protection | EVM token identity seams | `NEW_FEATURE_REQUIRED` | Contract keying needs explicit regression coverage | Yes | High | All Rights Reserved | No | Independent identity validation |
| `nirholas/robinhood-toolkit` | Multicall3 read batching | `evm_rpc.py` | `NEW_FEATURE_REQUIRED` | Optional batch-read port not present | Yes | Low/medium | All Rights Reserved | No | Add only if measured RPC cost justifies it |
| `nirholas/robinhood-toolkit` | Read-only MCP security boundary | existing MemeRadar MCP | `ALREADY_BETTER` | Canonical MCP is already read-only and bounded | No | High | All Rights Reserved | No | Do not replace MemeRadar MCP |

## Priority decisions

The first local implementation slice is the P0 extension of the existing
`FlowAnalyzer`/window builders: unique-buyer velocity, cluster-adjusted buyer
count, wallet entropy, wash-suspected volume, and raw versus organic turnover.
It is independently implemented from the normalized event contract; no source
is copied or vendored.  Named Robinhood streams and protocol-specific launch
adapters remain contract extensions until their provider identities and real
read-only samples are independently verified.

## 2026-09-26 implementation delta

The original audit above records the pre-change gap.  The following is the
after-state for this local checkpoint; it does not promote unverified live
providers or claim out-of-sample alpha.

| CAPABILITY | AFTER STATUS | EVIDENCE | DECISION |
|---|---|---|---|
| Helius push wallet tracking | `IMPLEMENTED_LOCAL` | `HeliusWalletWebhookAdapter` authenticates, replays safely, matches watched wallets, and emits existing observations | Extend existing wallet path; live webhook acceptance remains external |
| Smart-wallet leaderboard | `IMPLEMENTED_LOCAL` | `SmartWalletLeaderboardProjection` ranks existing `SmartWalletScore` records with confidence and reasons | Reuse existing wallet statistics |
| Unique buyer velocity | `IMPLEMENTED_LOCAL` | 10s/30s/1m/3m windows include unique buyers, velocity, acceleration and cluster-adjusted count | Extend existing early features |
| Wash trading / organic volume | `IMPLEMENTED_LOCAL` | `OrganicFlowScore` now exposes suspected and organic volume, entropy, sibling, repeat and round-trip metrics | Existing score engine extended; thresholds remain policy configuration |
| Transaction taxonomy / wallet labels | `IMPLEMENTED_LOCAL` | `event_taxonomy.py` and `WalletLabelRegistry` are provider-independent and evidence-only | No external labels become authority |
| Alert storm control | `IMPLEMENTED_LOCAL` | Existing outbox accepts `AlertStormController` with priority bypass and digest metrics | No second Telegram system |
| Price consensus | `IMPLEMENTED_LOCAL` | `PriceConsensusService` preserves source, freshness, disagreement and confidence | No blind source fallback |
| Robinhood named subscriptions | `IMPLEMENTED_LOCAL` | `SubscriptionDescriptor` carries independent filters, cursors, health, gaps and provider-scoped identity | Provider-specific resume semantics remain external |
| Par / HoodiePad / NOXA / Odyssey | `BLOCKED_EXTERNAL` | Read-only candidate parsers exist, but unverified deployment identities are refused by the log reader | Require chain ID, bytecode/hash and sample-transaction verification |
| Adaptive EVM logs / ticker identity / Multicall3 | `IMPLEMENTED_LOCAL` | Bounded scanner, `(chain_id,address)` metadata registry and explicit chain-configured read-only Multicall3 port have focused tests | No proprietary source reused |
| Strategy failure metadata | `IMPLEMENTED_LOCAL` | `StrategyFailureModeRegistry` is report-only and outside scoring | Promotion still requires replay evidence |
