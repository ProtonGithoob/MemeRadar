# Upstream Repository Influences

This document records why external repositories influenced MemeRadar and, equally importantly, where their influence stops.

## Principles

### 1. Influence is not architecture ownership

MemeRadar's canonical provider contracts, observations, provenance, quality semantics, scoring, risk, wallet graph, lifecycle, readiness and delivery remain authoritative. External repositories may supply data contracts, evidence ideas or testable invariants; they must not create parallel domain systems.

### 2. Preserve uncertainty

Vendor output is an observation from that vendor. A provider's `smart_money`, `KOL`, `suspected_insider`, `rug`, `wash_trading` or similar label is not automatically a MemeRadar fact. Preserve provider identity, event time, quality and evidence provenance.

### 3. Do not convert absence into safety

Missing, empty, unavailable and unsupported are distinct states. Do not convert them to numeric zero, `false`, neutral confidence or a safe verdict unless the upstream contract explicitly defines that semantic and MemeRadar independently accepts it.

### 4. Research providers are read-only

External intelligence integrations must not introduce signing keys, wallet custody, swap/order endpoints or autonomous execution merely because an upstream project supports them.

### 5. License-aware independent implementation

- If a usable root license is verified, source-level reuse is still optional and should be minimized.
- If license state is ambiguous, use independently implemented architectural ideas only; do not copy source, tests, comments, names or implementation structure.
- Re-check license status before every new source-level reuse decision.

## GMGNAI/gmgn-skills

**Pinned audit ref:** `4a48b8a31e19b62c96ee57ba76b46310f84043f0`  
**License state:** root MIT LICENSE verified during the 2026-09-14 audit.

### Useful influence

GMGN demonstrates a dense multi-chain intelligence surface for early-token discovery and due diligence. Useful categories include:

- new/trending token discovery;
- live market/token context;
- Smart Money and KOL activity;
- top holders/traders;
- smart-degen counts;
- rat-trader/bundler/sniper/fresh-wallet measures;
- suspected-insider hold rate;
- creator/dev holdings;
- wash-trading, honeypot and rug-risk evidence;
- bonding-curve state.

### MemeRadar boundary

GMGN may become an optional read-only evidence provider only if a stable server-side read contract is verified. It remains disabled by default, LIVE_SHADOW and unweighted initially.

Do not use GMGN's private-key, wallet-management, swap, cooking, market-order, limit-order, strategy-order or copy-trading surfaces.

Do not run `gmgn-cli` as an application subprocess merely to obtain data. If a suitable backend read contract is unavailable, report `BLOCKED_EXTERNAL` rather than inventing or scraping an endpoint.

## SoCloseSociety/WhalegodTG

**Pinned audit ref:** `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6`  
**License state:** root MIT LICENSE verified during the 2026-09-14 audit.

### Useful influence

The useful contribution is a concrete vocabulary for factual on-chain activity and operational ideas around bounded ingestion/deduplication.

### MemeRadar boundary

MemeRadar already has Helius stream normalization and delivery architecture. Reuse only the concept of factual subtypes inside the existing path:

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

Numi's Robinhood Chain architecture emphasizes a useful separation between bonding state, graduation, DEX liquidity and executable routing.

### MemeRadar boundary

MemeRadar already has `LaunchLifecycleState`, route state, verified-liquidity timestamps and first-swap evidence. Numi therefore contributes only regression invariants:

- bonding does not prove a DEX route;
- graduation does not prove verified liquidity;
- DEX-live state requires evidence consistent with canonical route policy;
- first verified liquidity is not the same event as first verified swap.

Do not copy source. Do not introduce Numi's risk manager, signer, 1inch execution or a second Robinhood lifecycle.

## CodeMuscle/solbeam

**Pinned audit ref:** `234423a8f0180deffc6b9d83fa84e35687049670`  
**License state:** README declares MIT, but root `LICENSE` was not found during the audit.

### Useful influence

Solbeam provides product/reference ideas for a clean live-feed and wallet intelligence UX.

### MemeRadar boundary

No production dependency or source reuse is approved. Several advertised features were roadmap-heavy at audit time, while MemeRadar already has its own provider, wallet graph, alert and frontend architecture.

## Revalidation workflow

Before implementing a new external influence:

1. pin the exact upstream commit;
2. verify current license from the repository, not a remembered claim;
3. verify the actual implementation/API contract, not only README marketing;
4. map the feature against current MemeRadar architecture;
5. mark it `EXISTING`, `PARTIAL`, `MISSING`, or `NOT_NEEDED`;
6. prefer extending existing canonical modules;
7. add failing tests before production code;
8. keep new provider evidence read-only and unweighted until real OOS evaluation;
9. update `docs/RESEARCH_REUSE_REGISTRY.md` with the decision.
