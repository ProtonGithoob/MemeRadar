# Upstream Repository Influences Supplement — 2026-09-14

This supplement records the Option A external-alpha audit while preserving the full historical `docs/UPSTREAM_REPOSITORY_INFLUENCES.md` ledger.

## Cross-cutting principles

- MemeRadar's canonical provider contracts, observations, provenance, quality semantics, scoring, risk, wallet graph, lifecycle, readiness and delivery remain authoritative.
- External repositories may supply data contracts, evidence ideas or testable invariants; they must not create parallel domain systems.
- Vendor output is an observation from that vendor. `smart_money`, `KOL`, `suspected_insider`, `rug`, `wash_trading` and similar labels are not automatically MemeRadar facts.
- Missing, empty, unavailable and unsupported are distinct states and must not silently become zero, `false`, neutral confidence or safe verdicts.
- Research/intelligence providers remain read-only and receive no signing keys, wallet custody, swap/order endpoints or autonomous execution authority.
- Source-level reuse requires a fresh license check. When license state is ambiguous, only independently implemented architectural ideas are allowed.

## GMGNAI/gmgn-skills

**Pinned audit ref:** `4a48b8a31e19b62c96ee57ba76b46310f84043f0`  
**License state:** root MIT LICENSE verified during the 2026-09-14 audit.

### Useful influence

GMGN exposes a dense early-token intelligence surface across relevant chains, including:

- new/trending token discovery;
- market/token context;
- Smart Money and KOL activity;
- top holders/traders;
- smart-degen counts;
- rat-trader, bundler, sniper, fresh-wallet and suspected-insider measures;
- creator/dev holdings;
- wash-trading, honeypot and rug-risk evidence;
- bonding-curve state.

### MemeRadar boundary

GMGN may become an optional read-only evidence provider only if a stable, auditable server-side read contract is verified. Initial state is disabled by default, LIVE_SHADOW, non-required for application health and scoring weight 0.

Do not use GMGN private-key, wallet-management, swap, cooking, market-order, limit-order, strategy-order or copy-trading surfaces. Do not run `gmgn-cli` as a worker subprocess merely to obtain data. If no suitable backend read contract exists, report `BLOCKED_EXTERNAL` instead of guessing or scraping an endpoint.

## SoCloseSociety/WhalegodTG

**Pinned audit ref:** `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6`  
**License state:** root MIT LICENSE verified during the 2026-09-14 audit.

### Useful influence

The reusable idea is factual on-chain activity taxonomy plus practical bounded-ingestion/deduplication patterns.

### MemeRadar boundary

MemeRadar already has Helius stream normalization and alert/delivery architecture. Extend the existing normalizer only with factual subtypes such as:

```text
SWAP
LIQUIDITY_ADD
LIQUIDITY_REMOVE
BRIDGE
TRANSFER
TOKEN_LAUNCH
MEV_ARBITRAGE
UNKNOWN
```

Do not import Whalegod's Telegram bot architecture, SQLite model or directional `bullish/bearish/degen` semantics.

## numi-ai/numi-trading-agent

**Pinned audit ref:** `cb460ff96508c8fdae64ac169b4fc6cc2703f4ff`  
**License state:** README/package declare MIT, but root `LICENSE` was not found during the audit.

### Useful influence

Numi's Robinhood Chain architecture reinforces separation between bonding state, graduation, DEX liquidity and executable routing.

### MemeRadar boundary

MemeRadar already has `LaunchLifecycleState`, route state, verified-liquidity timestamps and first-swap evidence. Numi contributes only independently implemented regression invariants:

- bonding does not prove a DEX route;
- graduation does not prove verified liquidity;
- DEX-live state requires evidence consistent with canonical route policy;
- first verified liquidity is not the same event as first verified swap.

Do not copy source/tests/comments. Do not introduce Numi's risk manager, signer, 1inch execution or a second Robinhood lifecycle.

## CodeMuscle/solbeam

**Pinned audit ref:** `234423a8f0180deffc6b9d83fa84e35687049670`  
**License state:** README declares MIT, but root `LICENSE` was not found during the audit.

### Useful influence

Solbeam provides product/reference ideas for clean live-feed and wallet-intelligence UX.

### MemeRadar boundary

No production dependency or source reuse is approved by this audit. MemeRadar already owns its provider, wallet graph, alert and frontend architecture, and several Solbeam README features were roadmap-heavy during audit.

## Revalidation workflow

Before implementing any new external influence:

1. pin the exact upstream commit;
2. verify current license from repository files;
3. verify actual implementation/API contracts rather than README marketing only;
4. map the feature against current MemeRadar architecture;
5. classify it `EXISTING`, `PARTIAL`, `MISSING` or `NOT_NEEDED`;
6. extend existing canonical modules whenever possible;
7. add failing tests before production behavior changes;
8. keep new provider evidence read-only and unweighted until real out-of-sample evaluation;
9. update the historical registry plus a dated audit supplement if needed.
