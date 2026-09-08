# Multichain Extreme-Winner Discovery Implementation Plan

## Goal

Extend the existing evidence-first MemeRadar system from Solana-only identity and
provider composition to a chain-neutral SOLANA + BNB CHAIN read-only research
platform. Preserve every existing Solana contract and make BNB capability,
security, discovery, wallet intelligence, alerting, and live-shadow reporting
available through normalized application-facing seams. Keep all outcome
probabilities uncalibrated until out-of-sample evidence proves them.

## Architecture and boundaries

- `memeradar_domain` owns chain-qualified identities, address validation, and
  provider-neutral evidence. It does not import transport, provider SDKs,
  FastAPI, or persistence.
- `memeradar_application` owns normalized provider ports, chain-aware routing,
  settings validation, BNB risk analysis, GMGN corroboration semantics,
  multichain wallet/outcome research, alert projections, and KPI aggregation.
- `memeradar_providers` owns HTTP/RPC adapters and parser-specific payloads.
  BNB adapters use standard JSON-RPC and read-only discovery/market/security
  contracts; no adapter exposes transaction submission, signing, swap, order,
  or cooking operations.
- Existing Solana adapters and Pump.fun/PumpSwap normalization remain the
  canonical Solana path. New BNB adapters are separate provider modules behind
  the same application-facing contracts rather than a parallel `bnb_app`.
- Live, backfill, fixture, and replay data retain provenance, observed/ingested
  timestamps, freshness, parser/version metadata, and explicit UNKNOWN or
  CONFLICTED states.
- The exact operating-mode lock remains
  `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
  `AUTO_EXECUTION=false`.

## Implementation slices

### Slice 1 — Chain-neutral identity, requests, configuration, and routing

1. Add failing domain tests for SOLANA regression, canonical EVM address
   validation, BNB token and wallet identities, chain-qualified canonical IDs,
   cross-chain collision prevention, and pool/quote identity validation.
2. Refactor identities with a backwards-compatible `mint_address` surface and
   generic address aliases. Add `Chain.BNB`, `ChainId`, EVM normalization, and
   `WalletIdentity`; generalize chain integrity contracts without relaxing
   existing Solana validation.
3. Add failing application tests for chain-qualified requests, documented
   capability names, and per-chain routes. Implement capability enums/routes
   with a chain dimension while preserving the existing Solana route API.
4. Add failing settings tests for `ENABLED_CHAINS`, BNB RPC/fallback/chain ID,
   per-chain model versions, GMGN flags, PancakeSwap/Four.meme flags, defaults,
   invalid values, and protected modes. Implement validated settings parsing.
5. Run identity/config/routing tests and commit the coherent slice.

### Slice 2 — Read-only BNB JSON-RPC and provider health

1. Add failing adapter tests for HTTPS endpoint validation, BNB `eth_chainId`
   verification, normalized success results, JSON-RPC errors, timeouts, 429
   Retry-After, 5xx retry/failure, bounded concurrency, and the absence of any
   transaction-submission or signing capability.
2. Implement `BnbRpcAdapter` using the existing bounded transport policy and
   standard read methods: chain ID, block number/block, transaction,
   transaction receipt, logs, `eth_call`, code, and balance. Normalize results
   into provider-neutral observations or typed read contracts with provenance.
3. Add a keyless BNB RPC doctor, composition-root construction, fallback URL
   status, and Make target. Missing endpoints remain an honest external state;
   the application still boots.
4. Run focused and existing Solana RPC/provider-contract tests and commit.

### Slice 3 — Multichain market and launch discovery

1. Add failing DexScreener SOL regression and BNB fixture tests for chain
   filtering, address normalization, positive-price/liquidity handling,
   quote ranking, depth/freshness/pair-age preference, and deterministic
   address/DEX tie-breaks.
2. Generalize the DexScreener adapter to SOLANA and BNB (`bsc` upstream chain
   mapping) without leaking provider JSON or changing Solana outputs.
3. Add failing PancakeSwap normalization tests for factory/pair provenance,
   WBNB/stable quote eligibility, reserves, liquidity add/remove and trade-flow
   evidence, pair age, and deterministic new-pool ranking. Implement a read-only
   adapter/parser with no swap surface.
4. Add failing Four.meme parser/status tests. Normalize only the explicitly
   supported fixture contract; keep the live discovery capability
   `NOT_IMPLEMENTED` unless a public/on-chain interface is verified, with no
   fabricated events.
5. Add composition/routing status for PancakeSwap and Four.meme and commit.

### Slice 4 — BNB risk intelligence and chain-specific calibration seams

1. Add failing tests covering honeypot and buy/sell/transfer tax, blacklist and
   trading controls, max transaction/wallet, owner privileges and renouncement,
   mint/pause/proxy/upgradeability, implementation/bytecode evidence, LP
   lock/burn/concentration, holder/deployer concentration, creator dumping,
   fresh-wallet/shared-funder clusters, wash/self-transfer, and first-block
   sniper concentration. Test that UNKNOWN never becomes safe.
2. Implement normalized BNB contract-security and market-structure evidence
   plus a deterministic `BnbRiskAnalyzer` with configurable thresholds and a
   versioned BNB risk model independent of Solana thresholds.
3. Expose risk reason codes, freshness/provenance, hard blocks, and optional
   provider corroboration without allowing third-party scores to replace local
   risk authority. Commit after focused risk/security tests.

### Slice 5 — Optional GMGN read-only corroboration

1. Add failing tests for absent configuration boot, doctor states
   (`PASS`, `OPTIONAL_UNCONFIGURED`, `AUTH_FAILED`, `RATE_LIMITED`,
   `BLOCKED_EXTERNAL`, `DEGRADED`), normalized token/launch/market/holder/
   trader/wallet/smart-money/KOL/dev-history/security evidence, and malformed
   or disagreeing responses.
2. Implement a provider adapter with only read-only methods and normalized
   evidence. Gate it at composition time; local MemeRadar evidence remains
   canonical and GMGN disagreement is explicit. Do not import or expose any
   execution port, key, signing, swap, limit-order, cooking, or submission
   functionality.
3. Add the GMGN doctor and documentation of the source audit, then commit.

### Slice 6 — Pump protocol audit and multichain wallet/outcome research

1. Add failing tests for the missing/needed Pump lifecycle evidence only:
   bonding-curve progress/velocity, graduation, migration timing/gap,
   canonical PumpSwap pool verification, pre/post liquidity, creator fees and
   fee sharing. Confirm existing features are not duplicated.
2. Implement only missing deterministic normalized evidence in the existing
   Pump.fun/PumpSwap path. Record the trusted `pump-fun-sdk` audit and the
   explicit rejection of `PumpFun-RugPool`; no code, installer, binary, URL,
   or dependency from the rejected repository enters the tree.
3. Add failing tests for chain-separated wallet outcome histories, 2x/5x/10x/
   20x/50x/100x hit counts, rug exposure, entry age/market cap, executable vs
   mark performance, creator/funder overlap, coordination suspicion, recency,
   consistency, and explicit evidence-required cross-chain linkage.
4. Implement multichain wallet scoring and an uncalibrated extreme-winner
   projection containing P(2x), P(5x), P(10x), P(20x), P(50x), P(100x), rug
   probability, confidence, and evidence quality as absent/UNCALIBRATED until
   real observations exist. Add per-chain and combined KPI aggregation for
   required decision states and coverage metrics. Commit.

### Slice 7 — Multichain Telegram alerting and shadow validation

1. Add failing tests for SOLANA/BNB alert rendering, all required risk and
   provenance fields, transition-tier alert types, deduplication, state-change
   suppression, rate limiting, and source/first-seen/scored/enqueued/delivered
   timestamps with end-to-end latency.
2. Extend the existing ULTRA EARLY alert pipeline minimally, preserving current
   text and delivery behavior. Add chain-aware normalized payload fields and a
   latency projection; paper entry/exit remains paper-only.
3. Add per-chain/combined shadow cohort collection/reporting, decision-state
   KPI schemas, 7-day smoke and 30-day OOS readiness metadata, and explicit
   `OFFLINE_CONTRACT_TESTS` → `HISTORICAL_REAL_REPLAY` →
   `LIVE_READ_ONLY_SHADOW` → `PAPER_AUTO_ENTRY` →
   `OUT_OF_SAMPLE_CALIBRATION` gates without claiming alpha.
4. Add only minimal read surfaces for chain/provenance/BNB risk/wallet,
   Telegram/readiness, and SOL-vs-BNB metrics if existing schemas need them.
   Do not redesign the frontend. Commit.

### Slice 8 — Documentation, full verification, and handoff

1. Update README, architecture, provider, security, testing,
   `LIVE_READONLY_CHECKLIST`, `LIVE_SHADOW_VALIDATION`, external provider/
   security audit documentation, configuration examples, and STATUS with
   implemented capabilities, unknown/blocked states, and evidence.
2. Run focused provider/chain/security/doctor tests, existing Solana regression
   tests, lint, typecheck, tests, frontend checks, security and migration
   checks, and the authoritative `make verify`.
3. Inspect the diff and status for secrets, unsafe-repository artifacts,
   execution capability, unprotected modes, or accidental concurrent UI
   changes. Commit only scoped implementation/docs/tests.
4. Push the final commits to `origin/main`, verify local HEAD equals
   `origin/main`, and preserve the named concurrent UI stash. Report exact
   blockers before `REAL_WORLD_ALPHA_PROVEN`.

## Verification commands

- Focused red/green tests after every TDD behavior group with
  `.venv/bin/python -m pytest -q <tests>`.
- `.venv/bin/ruff check apps packages tests scripts`
- `.venv/bin/python -m mypy`
- `make test`
- `make verify`
- `make bnb-rpc-doctor`, `make gmgn-doctor`, and relevant existing doctors
  under keyless configuration.
- `rg` checks proving no unsafe PumpFun-RugPool artifacts, no private-key or
  signing integration, and exact protected-mode defaults.

## Acceptance invariants

- Solana tests and behavior remain green.
- BNB adapters are read-only and fail closed on unknown or stale critical
  evidence.
- Provider payloads stop at provider adapters; domain/application contracts are
  normalized and provenance-bearing.
- GMGN is optional and cannot block free-core boot or add execution capability.
- Four.meme remains explicitly unimplemented when public verification is absent.
- Extreme-winner probabilities are never fabricated; alpha remains
  `REAL_WORLD_ALPHA_NOT_YET_PROVEN` until objective out-of-sample gates pass.
- No live-money trading, signing, keys, swaps, sniping, Jito, or automatic
  transaction submission is introduced.
