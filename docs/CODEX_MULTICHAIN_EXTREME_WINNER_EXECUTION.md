# Codex Execution Handoff — Multi-Chain Extreme Winner Discovery

Use this document together with:

- `docs/MULTICHAIN_EXTREME_WINNER_IMPLEMENTATION_SPEC.md`
- `docs/EXTERNAL_REPOSITORY_AUDIT_2026_09_05.md`

## Instruction

Continue from the current `main` branch. Treat the two documents above as the canonical requirements for the next MemeRadar phase.

Do not stop after design or planning. Inspect the repository first, preserve any concurrent/uncommitted work, then implement incrementally with TDD, verify, document, commit and push.

### Primary objective

Make MemeRadar a chain-aware SOLANA + BNB early-token intelligence system optimized for detecting extreme-winner candidates as early as possible, without making unproven 10x/20x/50x/100x claims.

### Mandatory scope

1. Introduce chain-aware canonical token/wallet identity while preserving Solana compatibility.
2. Add BNB/EVM address validation and chain-aware idempotency.
3. Extend capability routing/composition with a chain dimension.
4. Add read-only BNB JSON-RPC support.
5. Generalize DexScreener from Solana-only pair handling to SOLANA + BNB with deterministic chain-specific pair selection.
6. Add read-only PancakeSwap discovery/evidence for BNB.
7. Add Four.meme launch discovery/evidence only where interfaces can be verified; otherwise classify missing capability honestly.
8. Add BNB-specific EVM risk features: honeypot/tax/owner/proxy/mint/pause/max-wallet/LP/holder/deployer/cluster risk.
9. Keep Solana and BNB risk/scoring model versions and thresholds separately calibratable.
10. Add optional read-only GMGN adapter for token, market, holder, wallet, smart-money, dev-history and discovery corroboration on SOLANA + BNB.
11. Explicitly exclude all GMGN swap/order/cooking/private-key functionality.
12. Audit current Pump.fun/PumpSwap decoding against trusted `nirholas/pump-fun-sdk` protocol references and add only genuinely missing deterministic lifecycle/migration/creator-fee features.
13. Never integrate or execute code/scripts from observed `PumpFun-RugPool` repositories. Treat their generic heuristic descriptions only as ideas to independently re-derive from trusted on-chain data.
14. Extend multi-chain smart-wallet reputation and provider corroboration/disagreement evidence.
15. Extend Telegram ULTRA EARLY alerts with chain, token address, market/liquidity, wallet/risk/corroboration/provenance and alert-latency evidence.
16. Extend live-shadow/replay/calibration/outcome reporting with separate SOLANA and BNB cohorts and decision-state KPIs.
17. Preserve paper execution and all existing safety barriers.

### Protected modes — immutable

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Do not add live wallet signing, swap submission, Jito/sniping, private keys, live-money order paths or auto-buy unlocking.

### Extreme-winner measurement policy

Preserve and extend 2x/5x/10x/20x/50x/100x outcome labels. Do not manufacture probability values. Any `P(10x)` style projection must remain absent/UNCALIBRATED/research-only until sufficient real out-of-sample data exists.

Measure per chain and per decision state:

- precision/recall for 10x/20x and precision for rarer 50x/100x cohorts
- post-alert rug rate
- market cap and token age at alert
- lead time to 2x/5x/10x
- false-positive rate
- executable vs mark multiple
- liquidity/price/outcome maturity coverage
- end-to-end Telegram alert latency

Keep `REAL_WORLD_ALPHA_NOT_YET_PROVEN` until the live research gate is actually satisfied.

### GMGN requirements

Implement as an optional provider behind existing contracts. Missing credentials must never fail core boot. Add a doctor and normalized errors/statuses. Provider disagreement must be recorded as evidence rather than silently overwriting canonical values.

Never expose execution capabilities from GMGN.

### Pump protocol audit requirements

Compare existing MemeRadar features with trusted protocol documentation for:

- bonding curve state/progress
- graduation/completion
- Pump -> PumpSwap migration
- canonical pool derivation
- creator vault / creator fees / fee sharing
- fee tiers where relevant to executable-return modeling
- Token-2022 handling
- migration/liquidity transition timing

Only add features that are genuinely missing and measurable.

### Supply-chain rule

Do not vendor/copy/execute `PumpFun-RugPool` code or install scripts. Do not use remote loaders or disable security software. Add no dependency without license/dependency/install-script/network/security review.

### Required tests

Add/extend deterministic unit/contract/integration tests for:

- chain identity and collision prevention
- BNB RPC and chain-id verification
- BNB DexScreener pair selection
- PancakeSwap/Four.meme normalization
- BNB risk scenarios including UNKNOWN != SAFE
- GMGN optional/keyless behavior, normalization, rate limits, auth and corroboration
- Pump lifecycle/migration/fee evidence
- multi-chain smart-wallet features
- Telegram SOL/BNB rendering, dedupe and latency
- protected modes and absence of signing/execution capabilities
- no Solana regressions

### Configuration

Only add env variables atomically with validated `Settings` support and tests. Do not add dead `.env.example` variables that runtime does not parse.

Conceptual targets include:

```env
ENABLED_CHAINS=solana,bnb
BNB_RPC_URL=
BNB_RPC_FALLBACK_URL=
BNB_CHAIN_ID=56
GMGN_ENABLED=false
GMGN_API_URL=
GMGN_API_KEY=
GMGN_READ_ONLY=true
PANCAKESWAP_DISCOVERY_ENABLED=true
FOURMEME_DISCOVERY_ENABLED=true
```

Preserve all existing legacy/provider compatibility that remains valid.

### Workflow

Before edits:

```bash
git status --short
git branch --show-current
git log -8 --oneline
git fetch origin
```

Never destructive-reset concurrent work.

Then:

```text
audit current consumers
-> write failing tests
-> implement smallest coherent slice
-> targeted tests
-> repeat
-> full make verify
-> live/keyless doctors where possible
-> docs/status update
-> commit
-> push
-> verify local HEAD == origin/main
```

Do not redesign the frontend. Update UI only where needed for chain/provenance/risk/alert visibility and keep existing design work intact.

### Final acceptance report

Return:

- starting/final commit
- branch and git sync status
- changed/new/deleted files
- SOLANA regression status
- BNB support matrix
- GMGN integration matrix
- Pump protocol audit findings
- external repository rejection/security evidence
- config changes
- Telegram changes
- risk/scoring changes
- shadow/research KPI changes
- test counts and `make verify` result
- live doctors and blockers
- exact protected-mode evidence
- remaining gaps before real-world alpha can be considered proven

Do not ask for design approval. Proceed end-to-end unless a genuine external blocker prevents repository work.
