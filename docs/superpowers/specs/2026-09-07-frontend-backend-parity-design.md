# Frontend / Backend Parity & Dynamic Settings Design

**Date:** 2026-09-07
**Status:** APPROVED

## Goal

Bring the MemeRadar web application to full parity with the current backend without duplicating business logic. The frontend must expose every safe operator-facing runtime capability, especially dynamic settings for providers, chains, social/X, Telegram, website/social metadata, wallet intelligence, narrative/LLM selection, alerts and decision thresholds. Secrets remain write-only/masked; protected execution modes remain immutable.

## Core problem

The current runtime `Settings` model already contains many parameters (Telegram, Solana/Helius, streams/backfill, DexScreener/Birdeye, RugCheck, external wallet, social provider, narrative provider/model, BNB and Robinhood RPC settings), but the control plane allows dynamic mutation of only six fields. The Settings UI therefore shows only those six fields and is read-only. This is a backend capability gap, not only a frontend rendering bug.

## Architectural decision

Introduce one canonical metadata-driven runtime settings registry. Do not hard-code another parallel settings model in the browser.

Each setting definition must include:

```text
key
category
value_type
mutable
secret
restart_required
decision_affecting
allowed_values
min_value
max_value
description
current/effective state
```

The registry must distinguish:

- runtime-mutable settings;
- restart-required settings;
- protected immutable settings;
- secret/write-only settings;
- environment/bootstrap-only settings.

No secret value may ever be returned by the API. Secret read state is only `CONFIGURED` / `NOT_CONFIGURED` plus optional last-updated metadata. Secret mutation supports replace/clear only through authenticated ADMIN control.

## Settings groups

### General
- APP_ENV (read-only at runtime)
- LOG_LEVEL
- worker poll interval
- readiness timeout
- DB/Redis readiness requirements

### Chains
- enabled chains
- Solana RPC/stream/backfill selection/status
- BNB RPC/fallback/chain ID
- Robinhood RPC/fallback/sequencer/blockscout/chain ID

### Market Data / Quotes
- market data provider
- DexScreener URL/key state
- Birdeye URL/key state
- paper quote provider/url/key state

### Social / X / Website Intelligence
- social metadata provider
- social API URL/key state
- compliant X/social ingestion provider configuration exposed by the existing adapter seam
- website/social metadata capability status

### Telegram
Treat ingestion and notification as separate capabilities.

Notification:
- Telegram API URL
- bot token state
- chat ID
- alert rate limits

Ingestion:
- expose only supported backend fields/adapters; if MTProto/API ID/hash/session do not yet exist in the runtime model, add them as optional provider-specific secret-safe settings behind the existing social/caller provider abstraction rather than scattering raw Telegram logic through domain code.

### Wallet Intelligence
- local/external provider choice
- external wallet URL/key state

### Security
- RugCheck URL/key state
- future optional security providers through the same capability registry, not hard-coded UI branches

### AI / Narrative
- provider (`ollama`, `external`, `disabled` or future validated registry choices)
- API URL
- API key state
- model

### Alerts / Decision
- alert max messages/window
- alert window seconds
- watch threshold
- strong setup threshold
- entry-ready threshold
- minimum confidence

### Protected Modes
Read-only, always visible:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Never allow these through the dynamic registry mutation path.

## API contract

Prefer extending the existing authenticated control plane rather than creating an unrelated settings service.

Required safe contract:

```text
GET   /v1/control/settings/schema
GET   /v1/control/settings
PATCH /v1/control/settings
GET   /v1/control/settings/history
POST  /v1/control/settings/test-provider
```

Exact route names may follow existing project conventions if a more natural extension already exists.

Rules:
- VIEWER may read non-secret schema/effective state.
- ADMIN may mutate only fields marked mutable.
- restart-required changes must report `RESTART_REQUIRED` and never pretend they are effective immediately.
- mutation must be versioned, audited, config-hashed and reason-required.
- partial updates are validated server-side.
- provider test is bounded, read-only and never exposes credentials.
- protected modes and execution permissions remain outside this mutation path.

## Frontend Settings workspace

Replace the current six-value read-only list with a metadata-driven workspace grouped by the categories above.

Each row/card shows:
- label + technical key;
- effective value or masked status;
- source (`runtime override`, `env/bootstrap`, `default` where safe to expose);
- mutable/read-only/restart-required badge;
- validation constraints/help text;
- provider status/deep-link where relevant.

ADMIN edit flow:
- client validates basic UX only;
- server remains authoritative;
- user supplies a reason;
- PATCH returns new version/hash and restart requirement;
- UI refreshes canonical state;
- audit link is shown.

Protected modes get a separate locked panel.

## Provider page boundary

`/settings` owns configuration.
`/providers` owns live runtime health.

Provider cards should show:
- provider + capability;
- configured state without secrets;
- current health;
- latency;
- freshness;
- quota/rate-limit state;
- last success/error;
- active fallback if known;
- `Test connection` when authorized and supported;
- link to the relevant Settings section.

Do not duplicate editable config forms on Providers.

## Shell and navigation parity

The shell currently says `SOLANA INTELLIGENCE` although the backend supports Solana + BNB + Robinhood. Replace with chain-neutral product language such as `MULTICHAIN MEME INTELLIGENCE`.

Add visible compact chain/provider readiness when supported by existing operations/read APIs; UNKNOWN must stay UNKNOWN.

## Universal search

Current browser-side search understands only token UUID and Solana base58 wallet addresses. Replace business-logic regex routing with a backend resolver/read endpoint where feasible.

Support:
- token UUID;
- Solana mint/address;
- Solana wallet;
- EVM `0x` token contract;
- EVM wallet;
- caller handle/ID where resolvable;
- ticker/name only as ambiguous search results, never canonical identity.

Ambiguous results must show a chooser with chain/address, never guess.

## Route-by-route parity audit

Audit these existing routes against backend capabilities:

```text
/
/radar
/ultra-early
/tokens/[id]
/positions
/wallets
/wallets/[address]
/callers
/wallet-graph
/providers
/operations
/audit
/settings
```

For each route verify:
- real API data source exists;
- frontend type matches backend contract;
- no stale mock/fake data;
- loading/empty/error/unauthorized/degraded/UNKNOWN states;
- freshness/provenance where relevant;
- cross-chain identity displayed;
- filters/sort/search appropriate to the data;
- cross-links to related token/wallet/caller/provider/audit views;
- responsive behavior;
- accessibility;
- tests.

## Specific page requirements

### Overview
Show real stack/provider status, chain coverage, top actionable evidence, real sample/evidence class, and production-readiness state. Do not imply profitability from synthetic evidence.

### Radar / Ultra Early
Expose chain filters, decision band, freshness, risk dimensions, caller/smart-money convergence and executable/liquidity context already present in read APIs. UNKNOWN remains explicit.

### Token Detail
Surface chain-qualified identity, market/liquidity, risk, caller history/convergence, smart wallets, provenance/timeline and paper position/exit evidence when available.

### Positions
Clearly distinguish paper/shadow position state; add filters for chain/status/strategy/evidence class and executable-vs-reference metrics.

### Wallets / Wallet Detail / Graph
Add chain-aware filters and links; show smart-money quality, cluster/convergence and cross-chain evidence without asserting weak identity links.

### Callers
Add filters/sort for source, chain, evidence class, sample size, confidence, executable hit-rate cohorts, rug/failure rate and earliest-call quality. Add caller detail navigation or expandable detail with historical calls, linked-wallet evidence and conduct correlation.

### Operations
Expose API/worker/DB/Redis/provider/stream/social/Telegram/shadow status, queue/lag/freshness, latest errors and restart-required config state.

### Audit
Add filters for config mutations, provider tests, kill switches and actor/correlation ID. Secret values must remain redacted.

## Production readiness UI

Add `/readiness` (preferred) or a clearly separated Operations section backed by a safe read projection of the existing production gate state:

```text
PR-1 Engineering/release
PR-2 Providers/evidence
PR-3 Historical-real research
PR-4 Live-shadow
PR-5 Operations
PR-6 Read-only production
PR-7 Paper-auto production
```

Do not parse Markdown in the browser as source of truth; create/read a backend projection if needed.

Add `/research` only if the backend already exposes or can cleanly expose canonical research reports. Show ablation families, evidence class, sample adequacy, no-lookahead state and promotion state. Do not duplicate research engines in frontend.

## Visual / UX rules

- Preserve the workstation visual language but simplify dense cards.
- One primary hierarchy per page; avoid repeated boundary banners when a compact persistent safety status suffices.
- Responsive targets: 1440x900, 1280x800, 1024x768, 768x1024, 390x844.
- No horizontal overflow at supported viewports except intentional data tables with contained scroll.
- Tables should support sticky headers where useful and compact mobile cards where table density fails.
- All mutations need success/error/restart-required feedback.
- Never render raw secrets or auth tokens.

## Testing and acceptance

Backend:
- registry schema/validation;
- role authorization;
- secret masking/write-only behavior;
- protected mode rejection;
- restart-required semantics;
- version/hash/audit history;
- provider connection-test safety.

Frontend:
- settings categories render from schema;
- ADMIN mutation success/failure;
- VIEWER read-only behavior;
- masked secret status;
- protected modes locked;
- providers/settings boundary;
- universal search ambiguity;
- route empty/error/UNKNOWN states;
- responsiveness/accessibility.

Browser acceptance must cover every listed route at desktop + mobile and the layout matrix above. No fake production data may be introduced.

## Non-goals

- live-money execution;
- browser-side secret storage;
- browser-side business scoring;
- duplicating provider/domain engines;
- making every environment variable dynamically mutable;
- weakening current protected modes or promotion gates.
