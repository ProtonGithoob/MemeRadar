# External Repository Integration Audit — 2026-09-05

Scope: external repositories reviewed as potential MemeRadar intelligence/capability sources.

Decision rule: reuse concepts and verified read-only interfaces only when they close a real capability gap. Do not copy trading/execution code, private-key flows, unsafe installers, or duplicate MemeRadar functionality.

## Summary

| Repository | Priority | Decision | MemeRadar use |
|---|---:|---|---|
| `GMGNAI/gmgn-skills` | HIGH | ADOPT READ-ONLY CAPABILITIES | Optional token/wallet/market/smart-money corroboration provider for Solana + BNB |
| `nirholas/pump-fun-sdk` | MEDIUM/HIGH | AUDIT PROTOCOL MODEL, SELECTIVE REIMPLEMENTATION | Pump.fun/PumpSwap lifecycle, bonding curve, migration, creator-fee and canonical pool evidence |
| `PumpFun-RugPool` variants observed in GitHub search | REJECT | DO NOT INTEGRATE CODE OR INSTALLER | Independently re-derive only generic heuristic ideas from trusted data sources |

---

## 1. GMGNAI/gmgn-skills

### Verified useful capability surface

The repository exposes GMGN OpenAPI-backed agent/CLI skills for token research, market discovery, wallet analytics and smart-money tracking across multiple chains including Solana and BSC/BNB.

Useful read-only capability categories for MemeRadar:

- token metadata and pool information
- token security/risk enrichment
- holders and traders
- market/K-line information
- trending and newly launched tokens
- wallet holdings/activity/stats
- developer-created token history
- smart-money/KOL/professional-wallet observations
- wallet scoring / copyability-style evidence
- multi-chain discovery/corroboration

### Why it adds value

MemeRadar already has canonical local wallet, creator, holder, flow and market analysis. GMGN is useful as an **independent enrichment/corroboration provider**, not as a replacement.

Highest-value integrations:

1. smart-wallet evidence corroboration
2. dev/creator historical token outcomes
3. wallet-token relationship enrichment
4. Solana + BNB new-token discovery corroboration
5. provider disagreement detection
6. token/security evidence cross-checking

### Explicit exclusions

Do not expose or import:

- swap submission
- limit orders
- strategy/cooking orders
- wallet private-key management
- automatic trade execution

MemeRadar remains read-only/shadow/paper.

### Implementation direction

Create an optional `GmgnReadOnlyAdapter` behind existing provider contracts.

Recommended normalized capabilities:

```text
TOKEN_METADATA
TOKEN_DISCOVERY
NEW_LAUNCH_DISCOVERY
MARKET_SNAPSHOT
HOLDER_DATA
WALLET_ACTIVITY
SMART_MONEY
WALLET_PERFORMANCE
SECURITY_ANALYSIS
DEV_CREATED_TOKEN_HISTORY
```

GMGN must never become a boot dependency.

---

## 2. nirholas/pump-fun-sdk

### Verified useful protocol surface

The SDK documents and models Pump.fun and PumpSwap lifecycle mechanics, including:

- Pump bonding-curve token creation/trading lifecycle
- graduation/completion
- migration to PumpAMM/PumpSwap
- canonical AMM pool derivation
- Pump vs PumpAMM program separation
- creator-fee vaults
- fee sharing
- market-cap-based fee tiers
- Token / Token-2022 distinctions
- additional protocol modes/metadata

### Why it adds value

MemeRadar already has launchpad, migration, liquidity and creator-risk logic. The useful action is a **capability-gap/protocol-decoder audit**, not dependency adoption.

Potential missing deterministic evidence to compare against current MemeRadar implementation:

```text
bonding_curve_progress
bonding_curve_velocity
seconds_to_graduation
graduation_detected_at
migration_detected_at
canonical_pumpswap_pool_verified
pre/post migration liquidity delta
creator_fee_rate
creator_fee_sharing_detected
creator_fee_claim behavior
migration_gap_seconds
```

Only add features that are not already represented by canonical MemeRadar features and that can be derived deterministically from trusted protocol/on-chain data.

### Explicit exclusions

Do not import:

- transaction signing
- buy/sell instruction builders
- trading bots
- Telegram trading bots
- private-key flows
- automatic execution

---

## 3. PumpFun-RugPool — rejected

A repository variant observed under the name `PumpFun-RugPool` describes potentially useful ideas such as:

- bonding curve monitoring
- developer wallet cluster analysis
- liquidity transition analysis
- holder-distribution risk
- transaction-log parsing

However, the observed README contains unsafe supply-chain instructions: it tells users to execute a remote PowerShell loader from `easy-soft.su` and suggests disabling Windows security protections.

### Decision

**DO NOT USE THE REPOSITORY CODE, INSTALLER, BINARIES, SCRIPTS OR NETWORK ENDPOINTS.**

Do not clone it into MemeRadar's runtime/dependency tree.

If any described heuristic is useful, re-derive and implement it independently from trusted Solana RPC/protocol data and cover it with deterministic tests.

Candidate ideas that may be independently evaluated:

- bonding-curve velocity anomaly
- creator/developer wallet cluster recurrence
- pre-migration creator dumping
- holder concentration transitions
- liquidity migration anomalies

These ideas are not evidence that the repository implementation itself is trustworthy.

---

## Integration precedence

1. GMGN read-only capability-gap implementation
2. BNB Chain core support and chain-aware normalization
3. Pump protocol decoding/gap audit using trusted protocol references
4. Independently derived additional Pump.fun risk heuristics
5. Live shadow validation and outcome calibration

Do not delay live evidence collection by importing low-value duplicate bot repositories.

---

## Supply-chain policy for this phase

All third-party repository adoption must pass:

- license review
- dependency review
- secret/private-key review
- install-script review
- network endpoint review
- malicious/obfuscated code review
- execution capability review
- provenance and data-quality review

External repositories are research inputs; MemeRadar's domain logic remains canonical.

No external trading bot is allowed to bypass MemeRadar protected modes.
