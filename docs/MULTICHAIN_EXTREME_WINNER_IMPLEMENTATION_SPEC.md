# Multi-Chain Extreme Winner Discovery — Implementation Specification

Date: 2026-09-05
Status: APPROVED_FOR_IMPLEMENTATION
Scope: SOLANA + BNB CHAIN, read-only/shadow/paper first

## Objective

Evolve MemeRadar from a Solana-centric early-memecoin research system into a provider-neutral, chain-aware extreme-winner discovery platform capable of detecting and ranking candidates before large price expansion while preserving evidence quality and fail-closed safety.

The system MUST NOT claim that it can reliably predict 10x/20x/50x/100x outcomes until real out-of-sample shadow evidence supports those claims.

Protected modes remain invariant during this phase:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No live wallet signing, swap submission, private-key handling, sniper/Jito execution, or live-money order path belongs in this phase.

---

## Current baseline that must be preserved

MemeRadar already contains substantial early-alpha research and risk infrastructure:

- early detection / early decision / early scoring
- WATCH -> EARLY_WATCH -> STRONG_SETUP -> HIGH_CONFLUENCE -> ENTRY_READY state progression
- winner-vs-rug optimization
- extreme-winner 2x/5x/10x/20x/50x/100x outcome labeling
- market-cap and launch-age-at-decision evidence
- smart-wallet / creator / holder / funder graphs
- insider allocation and deployer behavior
- bundle/sniper and launch-risk features
- liquidity / flow / tape / revival features
- replay, calibration, separability and convex-exit research
- provider-neutral free-first composition
- Solana RPC + DexScreener + optional Helius/Birdeye/RugCheck/social/Ollama/Telegram
- Telegram ULTRA EARLY SIGNAL rendering
- paper execution and protected execution gates

The current status `REAL_WORLD_ALPHA_NOT_YET_PROVEN` MUST remain until live evidence is sufficient.

---

# 1. Architectural target

The next architecture is chain-neutral at the domain/application boundary and chain-specific only in adapters and feature extractors.

```text
                    MemeRadar Core
                         |
                Chain Capability Layer
                 /                  \
             SOLANA                 BNB
               |                     |
      Solana RPC / Helius       BNB JSON-RPC
      Pump.fun / PumpSwap       Four.meme
      Raydium / Jupiter         PancakeSwap
               |                     |
               +----------+----------+
                          |
                    Normalization
                          |
                 Chain-aware Features
                          |
                    Risk / Wallet
                          |
                     EarlyScore
                          |
                 Extreme Winner Model
                          |
                  Telegram / Paper
```

Do not implement BNB by spreading `if chain == ...` branches across unrelated business logic. Use explicit chain primitives, capability routing and chain-specific feature/risk modules.

---

# 2. Required domain refactor

## ADD

Introduce a canonical chain identifier, for example:

```text
ChainId.SOLANA
ChainId.BNB
```

Extend canonical token and wallet identities to carry chain context.

Conceptually:

```text
TokenIdentity
- chain
- address
- token_standard
- canonical_id

WalletIdentity
- chain
- address
- canonical_id
```

## UPDATE

Replace Solana-only assumptions at domain/application boundaries where appropriate:

- `mint_address` terminology may remain as compatibility API for Solana, but canonical internals should support generic token `address`.
- Solana address validators MUST stay Solana-specific.
- Add EVM address validation for BNB (`0x` + 20-byte address, normalized consistently).
- Preserve existing UUID/idempotency semantics by incorporating chain into canonical identity keys.

## DO NOT DELETE

Do not remove existing Solana models or compatibility fields merely to make the design generic. Migrate incrementally with compatibility aliases and explicit deprecation where needed.

---

# 3. Chain capability model

Extend the provider capability model so routing is chain-aware.

Capabilities should include at least:

```text
CHAIN_RPC
BLOCK_STREAM
TRANSACTION_HISTORY
TOKEN_METADATA
TOKEN_DISCOVERY
NEW_LAUNCH_DISCOVERY
MARKET_SNAPSHOT
MARKET_QUOTE
PAIR_DISCOVERY
HOLDER_DATA
WALLET_ACTIVITY
SMART_MONEY
SECURITY_ANALYSIS
LAUNCHPAD_STATE
LIQUIDITY_STATE
SOCIAL_METADATA
SOCIAL_ANALYTICS
NARRATIVE
ALERT_DELIVERY
```

A provider route MUST include a chain dimension.

Example:

```text
(SOLANA, MARKET_SNAPSHOT) -> DexScreener -> Birdeye
(BNB, MARKET_SNAPSHOT)    -> DexScreener -> optional GMGN
(SOLANA, CHAIN_RPC)       -> public Solana RPC -> optional Helius
(BNB, CHAIN_RPC)          -> configured BNB RPC -> optional fallback
```

Fallbacks must be bounded, deterministic and observable.

---

# 4. BNB Chain — mandatory additions

## 4.1 BNB JSON-RPC adapter

ADD a standard EVM/BNB JSON-RPC provider adapter behind the existing provider abstraction.

Read-only capabilities only, using standard methods where required, such as:

- `eth_chainId`
- `eth_blockNumber`
- `eth_getBlockByNumber`
- `eth_getTransactionByHash`
- `eth_getTransactionReceipt`
- `eth_getLogs`
- `eth_call`
- `eth_getCode`
- `eth_getBalance`

Requirements:

- timeout
- bounded retry
- 429 / Retry-After handling
- bounded concurrency
- circuit protection if the existing transport supports it
- provenance
- secret-safe logging
- explicit chain-id verification for BNB mainnet

No private keys or transaction submission.

## 4.2 DexScreener BNB support

UPDATE the existing DexScreener adapter so chain handling is generic rather than Solana-only.

Required deterministic pair selection per chain:

1. exact chain match
2. exact token-address match
3. valid positive price
4. valid positive liquidity preferred
5. preferred quote asset ranking
6. meaningful liquidity depth
7. freshness / pair age
8. deterministic address/DEX tie-break

Solana and BNB ranking thresholds MUST be separately configurable/calibrated.

## 4.3 PancakeSwap discovery/read-only market evidence

ADD a BNB launch/DEX discovery adapter or decoder for PancakeSwap read-only evidence.

Required evidence classes:

- new pair/pool creation
- liquidity additions/removals
- token/WBNB or approved stable quote pools
- reserves / liquidity depth
- trade-flow observations when available from logs/events
- pair age
- pool address
- factory/router provenance

Do not build swap execution.

## 4.4 Four.meme launch discovery

ADD a Four.meme read-only launch adapter/decoder if public/on-chain interfaces can be validated.

Required outputs should normalize into existing discovery/launch evidence:

- token address
- creator/deployer
- launch timestamp/block
- launchpad state
- bonding/curve or migration state where derivable
- liquidity transition
- early buys/sells
- creator and funder evidence

If a capability cannot be verified from an official/public interface, classify it as `NOT_IMPLEMENTED` rather than fabricating data.

---

# 5. BNB-specific risk engine

Do NOT reuse Solana risk rules blindly.

ADD BNB/EVM-specific deterministic risk features:

```text
honeypot suspicion
buy tax
sell tax
transfer tax
blacklist/whitelist capability
trading enable/disable controls
maxTx / maxWallet constraints
owner privileges
ownership renounced / not renounced
mint capability
pause capability
proxy / upgradeability
implementation-contract risk
contract bytecode present
source verification evidence when available
liquidity lock/burn evidence
LP-holder concentration
creator/deployer token concentration
holder concentration
fresh-wallet clusters
shared funder clusters
rapid creator dump
wash/self-transfer suspicion
sniper/first-block concentration
```

All unknown evidence must remain UNKNOWN, never converted to safe/zero.

Separate:

- `SOLANA_RISK_MODEL_VERSION`
- `BNB_RISK_MODEL_VERSION`

Calibration thresholds must be chain-specific.

---

# 6. Extreme-winner discovery improvements

The goal is not to create an uncalibrated `100x predictor` score.

ADD a calibrated outcome projection structure that can eventually expose:

```text
P_2X
P_5X
P_10X
P_20X
P_50X
P_100X
RUG_PROBABILITY
CONFIDENCE
EVIDENCE_QUALITY
```

Until sufficient real out-of-sample samples exist, probability fields MUST be:

- absent,
- explicitly `UNCALIBRATED`, or
- research-only values clearly labeled as synthetic/historical.

Never invent precision.

## Required real-world KPIs

Per chain and combined:

```text
candidate_count
alert_count
10x_precision
10x_recall
20x_precision
20x_recall
50x_precision
100x_precision
rug_rate_after_alert
median_alert_age
median_market_cap_at_alert
median_lead_time_to_2x/5x/10x
false_positive_rate
executable_multiple_vs_mark_multiple
liquidity_coverage
price_coverage
outcome_maturity_coverage
```

Segment all metrics by decision state:

- WATCH
- EARLY_WATCH
- STRONG_SETUP
- HIGH_CONFLUENCE
- ENTRY_READY

---

# 7. Smart-wallet intelligence — multi-chain

Upgrade wallet reputation from chain-local observations toward a chain-qualified multi-chain model.

Do not assume the same address controls the same entity across Solana and EVM. Cross-chain entity linkage requires evidence.

ADD:

```text
ChainWalletReputation
CrossChainEntityHypothesis
WalletOutcomeHistory
WalletEntryTimingProfile
WalletExtremeWinnerHitRate
WalletRugExposureRate
WalletCopyabilityScore
WalletFreshness/Recency weighting
```

Useful early features:

- number of historically successful early entries
- 10x/20x/50x hit rates
- median entry age after launch
- median entry market cap
- realized/executable outcomes where known
- rug exposure
- cluster/funder overlap
- creator relationship
- coordinated entry suspicion

GMGN may enrich these features, but local evidence remains canonical where available.

---

# 8. GMGN integration — HIGH PRIORITY, READ-ONLY ONLY

Repository research candidate: `GMGNAI/gmgn-skills`.

Integrate concepts/API capabilities, not agent execution behavior.

ADD an optional provider adapter, e.g. `provider-gmgn`, behind MemeRadar contracts.

Allowed read-only capabilities:

```text
TOKEN_METADATA
TOKEN_SECURITY_ENRICHMENT
MARKET_SNAPSHOT
TOKEN_DISCOVERY
NEW_LAUNCH_DISCOVERY
HOLDER_DATA
WALLET_ACTIVITY
SMART_MONEY
KOL/PROFESSIONAL_WALLET metadata
WALLET_PERFORMANCE
DEV_CREATED_TOKEN_HISTORY
TRENDING/HOT_SEARCH corroboration
```

Use cases:

1. corroborate DexScreener/Birdeye market evidence
2. enrich smart-wallet scoring
3. wallet-token relationship evidence
4. dev/creator historical outcome evidence
5. multi-chain discovery on Solana and BNB
6. detect disagreement between independent providers

DO NOT integrate:

- GMGN swap
- limit orders
- cooking orders
- private-key/wallet-management execution
- automated trading commands

GMGN must be optional. Missing API key/provider must never fail core boot.

Add configuration later through validated settings, for example:

```env
GMGN_API_URL=
GMGN_API_KEY=
GMGN_ENABLED=false
GMGN_READ_ONLY=true
```

Do not add environment variables until code parses and validates them in the same implementation change.

Add a `gmgn-doctor` that can classify:

- PASS
- OPTIONAL_UNCONFIGURED
- BLOCKED_EXTERNAL
- RATE_LIMITED
- AUTH_FAILED
- DEGRADED

Provider disagreement should become evidence, not silent overwrite.

---

# 9. Pump protocol audit — MEDIUM/HIGH PRIORITY

Reference candidate: `nirholas/pump-fun-sdk`.

Use it as a protocol-reference/audit source only. Do not import trading bots or execution paths.

Audit current MemeRadar Pump.fun/PumpSwap decoding against:

- bonding curve account/state
- graduation/completion state
- canonical PumpSwap migration
- Pump/PumpAMM program separation
- creator-vault / creator-fee evidence
- fee-sharing configuration
- fee tiers / market-cap fee behavior where relevant to executable-return modeling
- token program / Token-2022 handling
- Mayhem-mode metadata if relevant
- canonical pool/PDA derivation
- migration timing and liquidity transition

ADD deterministic features only when they provide new evidence beyond existing canonical features.

Potential additions:

```text
bonding_curve_progress
bonding_curve_velocity
seconds_to_graduation
migration_detected_at
pre_migration_liquidity_state
post_migration_liquidity_state
creator_fee_rate
creator_fee_sharing_detected
creator_fee_claim_velocity
canonical_pool_verified
migration_gap_seconds
```

Execution instruction builders from the SDK are out of scope.

---

# 10. PumpFun-RugPool repository — SECURITY REJECTION

Candidate repository name observed during research: `PumpFun-RugPool`.

DO NOT vendor, clone into the project, execute install scripts, copy deployment commands, or depend on it.

Reason: the observed README instructs users to run a remote PowerShell loader from a non-GitHub domain and even suggests disabling antivirus/SmartScreen protections. This is unacceptable supply-chain behavior for MemeRadar.

The following *ideas only* may be independently re-derived and tested from first principles or trusted on-chain sources:

- bonding-curve velocity
- developer wallet clusters
- holder-distribution risk
- liquidity transition anomalies
- pre-migration creator dumping

No source code, binaries, scripts, install commands or network endpoints from that repository should enter MemeRadar.

Add this repository/domain to any local dependency review denylist documentation if the project maintains one.

---

# 11. Telegram early-warning upgrade

The existing Telegram adapter and `ULTRA EARLY SIGNAL` renderer must be preserved and extended to multi-chain evidence.

ADD/UPDATE alert payload fields:

```text
chain
contract/token address
symbol/name
launch age
market cap
liquidity
price source
EarlyScore
confidence
state
buy velocity
buy acceleration
unique buyers
quote inflow
smart-wallet score
smart-wallet count
creator risk
bundle/sniper risk
holder risk
sellability/honeypot status
provider corroboration count
provider disagreement flags
extreme-winner research projection status
hard-block reasons
DexScreener/GMGN/Pancake/Four.meme provenance when applicable
```

Suggested alert tiers:

```text
EARLY_WATCH
HIGH_CONFLUENCE
ENTRY_READY
RISK_ESCALATION
PAPER_ENTRY
PAPER_EXIT
```

Do not flood Telegram. Preserve dedupe/rate limiting and add state-transition suppression so the same token does not spam repeated equivalent messages.

Alert latency must become a KPI:

```text
source_event_at
first_seen_at
scored_at
alert_enqueued_at
telegram_delivered_at
end_to_end_alert_latency_ms
```

---

# 12. Execution / autobuy policy

DELETE nothing from existing paper execution.

DO NOT unlock `AUTO_EXECUTION` in this phase.

Future live execution, if ever implemented, must be a separate explicitly approved roadmap after statistically credible shadow/paper evidence.

Prerequisites before even designing live execution:

- sufficient mature live samples per chain
- measured precision/recall
- acceptable post-alert rug rate
- executable-return evidence, not only mark-price multiples
- slippage/liquidity modeling
- failure and provider-outage tests
- position/risk limits
- kill switch
- wallet isolation
- explicit user approval

---

# 13. Configuration design

When implementation reaches the corresponding adapters, extend `.env.example` and `Settings` atomically.

Expected conceptual variables:

```env
# CHAINS
ENABLED_CHAINS=solana,bnb

# BNB
BNB_RPC_URL=
BNB_RPC_FALLBACK_URL=
BNB_CHAIN_ID=56

# GMGN OPTIONAL READ-ONLY
GMGN_ENABLED=false
GMGN_API_URL=
GMGN_API_KEY=
GMGN_READ_ONLY=true

# MARKET/DISCOVERY
DEXSCREENER_ENABLED=true
PANCAKESWAP_DISCOVERY_ENABLED=true
FOURMEME_DISCOVERY_ENABLED=true

# CALIBRATION
SOLANA_RISK_MODEL_VERSION=
BNB_RISK_MODEL_VERSION=
SOLANA_EARLY_MODEL_VERSION=
BNB_EARLY_MODEL_VERSION=
```

Do not commit secrets.

---

# 14. Tests required

## Domain/identity

- Solana address accepted/rejected correctly
- BNB EVM address accepted/rejected correctly
- chain included in canonical identity/idempotency
- same textual address on different chains never collides

## BNB RPC

- chain-id verification
- successful read
- timeout
- invalid JSON
- JSON-RPC error
- 429
- 5xx
- malformed logs
- reorg-aware observation handling where needed

## DexScreener

- Solana pair selection unchanged
- BNB pair selection
- chain mismatch rejection
- exact token match
- wrong quote asset
- zero liquidity
- stale pair
- deterministic ties

## BNB risk

- honeypot/unknown states
- high sell tax
- privileged owner
- renounced ownership evidence
- proxy implementation
- LP concentration
- creator dump
- fresh-wallet cluster
- unknown != safe

## GMGN

- optional keyless boot
- normalized token data
- wallet stats
- smart-money data
- dev history
- rate limit
- auth failure
- disagreement/corroboration
- no execution capability exposed

## Pump protocol audit

- bonding curve state
- graduation
- PumpSwap migration
- creator fee evidence
- canonical pool verification
- Token-2022 cases where supported

## Telegram

- SOL and BNB alert rendering
- chain/address shown
- dedupe
- state-transition suppression
- secret redaction
- latency evidence

## Safety

Exact protected modes remain enforced.

Add tests proving no adapter exposes transaction signing or live swap submission.

---

# 15. Live validation protocol

Do not promote multi-chain alpha using fixture results.

Required stages:

```text
OFFLINE_CONTRACT_TESTS
-> HISTORICAL_REAL_REPLAY
-> LIVE_READ_ONLY_SHADOW
-> PAPER_AUTO_ENTRY
-> OUT_OF_SAMPLE_CALIBRATION
-> only then future execution review
```

Minimum initial validation:

- 7-day smoke collection
- 30-day out-of-sample run
- separate SOL and BNB cohorts
- mature outcome windows
- provider provenance completeness

Status must remain honest:

```text
REAL_WORLD_ALPHA_NOT_YET_PROVEN
```

until thresholds defined by the research gate are met.

---

# 16. ADD / UPDATE / DELETE summary

## ADD

- chain identifiers and generic token/wallet identity primitives
- BNB/EVM validator
- BNB JSON-RPC read-only adapter
- BNB capability routes
- DexScreener BNB support
- PancakeSwap discovery/evidence
- Four.meme discovery/evidence
- BNB risk feature module
- chain-specific calibration/versioning
- GMGN optional read-only adapter + doctor
- provider corroboration/disagreement evidence
- multi-chain smart-wallet reputation projections
- Pump protocol migration/fee/bonding-curve gap features where genuinely missing
- multi-chain Telegram fields and latency KPIs
- SOL/BNB shadow metrics and outcome cohorts

## UPDATE

- provider contracts/routing/composition to be chain-aware
- token/wallet identity consumers
- discovery pipeline
- market normalization
- early scoring input model
- risk composition
- wallet/creator graph projections
- replay/calibration/separability research
- Telegram renderer
- read APIs and frontend only where necessary to expose chain/provenance
- docs/architecture/provider/live-shadow/testing/status files

## DELETE / REJECT

- do not delete valid existing Solana functionality
- remove any newly introduced duplicated chain-specific business logic instead of maintaining parallel copies
- reject any execution/sniper/private-key code from external repos
- reject `PumpFun-RugPool` code/scripts/deployment commands because of unsafe supply-chain behavior
- do not import GMGN swap/cooking/order execution
- do not import pump-fun-sdk transaction execution builders

---

# 17. Acceptance criteria

Implementation is accepted only when:

1. `make verify` passes.
2. Existing Solana behavior has no regression.
3. BNB chain can boot read-only without private keys.
4. BNB market discovery and risk evidence are normalized.
5. GMGN absence does not block boot/readiness.
6. GMGN, when configured, is read-only and provenance-audited.
7. Telegram can render and deliver SOL and BNB early alerts when configured.
8. Protected modes are exact and hard-locked.
9. Multi-chain shadow tooling reports per-chain counts and evidence class.
10. No fake probability/alpha claims are added.
11. Real-world alpha status remains unproven until real samples mature.
12. No unsafe external repository code or execution path enters the runtime.

This specification is the canonical implementation target for the next MemeRadar phase.
