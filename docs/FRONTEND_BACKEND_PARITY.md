# MemeRadar Frontend / Backend Parity Contract

This is a compact, reviewable inventory of the current operator read surfaces.
`apps/web/src/app/lib/parity-manifest.ts` is the executable companion. Every
backend field group is either owned by a frontend surface or listed as an
explicit omission; omissions never authorize a browser-side calculation.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `DISPLAYED` | Rendered as a canonical value/state in the named surface. |
| `FORMATTED_ONLY` | Rendered after formatting/truncation only; no business meaning is added. |
| `MISSING_FRONTEND` | Canonical backend field exists but is not yet rendered; follow-up work is required. |
| `BACKEND_NOT_EXPOSED` | The bounded application/read model does not expose the concept. |
| `RAW_EVIDENCE_ONLY` | Retained for audit/replay but intentionally not rendered as raw payload. |
| `INTENTIONALLY_OMITTED` | The field belongs to another canonical route or is outside this surface's purpose. |
| `SECRET` | Write-only or masked; configured state may be rendered, value may not. |
| `EXECUTION_OUT_OF_SCOPE` | Protected execution authority is deliberately absent from the browser. |
| `UNSUPPORTED` | The backend/provider does not claim the concept for this surface. |

## Route ownership matrix

| Surface | Backend route(s) | Frontend owner | Canonical field groups rendered | Explicit omissions |
| --- | --- | --- | --- | --- |
| `/` | `/candidates`, `/early-radar`, `/operations/overview` | `CommandCenter` | system state, provider summary, alerts, funnel, ranked radar rows, execution boundary | raw payload (`RAW_EVIDENCE_ONLY`); positions (`INTENTIONALLY_OMITTED`, dedicated route) |
| `/radar` | `/candidates`, `/early-radar` | `RadarExplorer` / `RadarTable` | identity, chain, state, score, confidence, risk, freshness, liquidity, reasons, navigation | lifecycle (`INTENTIONALLY_OMITTED`, token detail); raw provider payload (`RAW_EVIDENCE_ONLY`) |
| `/ultra-early` | `/early-radar` | `UltraEarlyWorkspace` | early state/score, velocity, buyers, liquidity, creator/bundle/holder risk, smart money, sellability, hard blocks, latency, evidence quality | lifecycle (`INTENTIONALLY_OMITTED`, token detail); raw payload (`RAW_EVIDENCE_ONLY`) |
| `/opportunities` | `/chain-opportunities` | `ChainOpportunitiesDashboard` | chain, 5m/1h/24h activity, acceleration, launchpad counts, provenance, quality, confidence, reasons | per-token lifecycle, narrative attention, reference-price integrity, risk/security (`BACKEND_NOT_EXPOSED`) |
| `/positions` | `/positions` | `PositionsDashboard` | paper mode/state, mark freshness, PnL, MFE/MAE, exit risk, evidence refs | live submission (`EXECUTION_OUT_OF_SCOPE`) |
| `/wallets` | `/wallets` | `WalletsDashboard` | chain, address, tier, score, confidence, sample/outcome counts, freshness | external label authority (`INTENTIONALLY_OMITTED`; labels are corroborating evidence) |
| `/wallets/[address]` | `/wallets/{address}` | `WalletDetailView` | identity, outcomes, freshness, reasons, evidence refs | relationship graph (`INTENTIONALLY_OMITTED`, graph route); execution authority (`EXECUTION_OUT_OF_SCOPE`) |
| `/wallet-graph` | `/wallet-graph/*`, creator reputation | `WalletGraphExplorer` | root, nodes/edges, candidate-only relationship evidence, ownership flag, quality, dimensions, event count, reasons, refs, provenance, filters | unsupported graph metrics (`UNSUPPORTED`) |
| `/callers` | `/caller-profiles`, `/social-calls`, `/caller-convergence` | `CallersDashboard` | platform/chain, evidence class, samples, confidence/uncertainty, outcomes, early-entry quality, KOL bundle, provenance | unsupported browser-derived failure rate (`BACKEND_NOT_EXPOSED`) |
| `/tokens/[tokenId]` | `/tokens/{tokenId}`, `/tokens/{tokenId}/timeline` | `TokenDetailView` | identity, pools, candidate, lifecycle, alpha timeline, insider-pattern evidence, quality, reasons, refs, provenance, time | raw provider payload (`RAW_EVIDENCE_ONLY`) |
| `/providers` | `/providers/health`, `/config/runtime-settings` | `ProvidersDashboard` | provider metadata, chains/capabilities/capability status, config/credential state, runtime health, latency, freshness, quota, failures/errors, doctor guidance | external stream/sequencer/reference-price counters (`BACKEND_NOT_EXPOSED`) |
| `/operations` | `/operations/overview` | `OperationsDashboard` | overall state/SLO, provider runtime, alerts, bounded counters, early detection, modes | unbounded telemetry (`UNSUPPORTED`) |
| `/audit` | `/audit/events`, `/config/versions` | `AuditDashboard` | time, actor, action, target, correlation, allow-listed before/after fields | secret content (`SECRET`) |
| `/settings` | `/state`, `/config`, `/runtime-settings` | `SettingsDashboard` | dynamic categories, typed values, pending/effective state, restart/protected/mutable flags, bounds, version conflicts, masked secret state | secret values (`SECRET`) |
| `/readiness` | `/readiness` | `ReadinessDashboard` | engineering gates, alpha-validation status/counts, first/latest real observation, labels, rate/error counts, blockers, modes, production classification | live-money enablement (`EXECUTION_OUT_OF_SCOPE`) |
| `Telegram/EarlyAlpha` | token timeline / persisted alert projection | backend renderer + delivery service | token identity, chain, state, score/confidence, risk quality, evidence changes, cohort similarity, reasons, correlation | raw payload (`RAW_EVIDENCE_ONLY`), public URL (`UNSUPPORTED`), unavailable fields (`BACKEND_NOT_EXPOSED`) |

## Backend/API inventory

| Backend route family | Owner | Browser status |
| --- | --- | --- |
| `/health/live`, `/health/ready` | deployment/health checks | `INTENTIONALLY_OMITTED` from operator pages; deployment probes are not analytical evidence |
| `/operations/overview` | shell, command center, operations | `DISPLAYED` |
| `/search/resolve` | global `SearchForm` | `DISPLAYED` with explicit ambiguous/not-found/unavailable states |
| `/candidates`, `/early-radar` | overview, radar, ultra-early | `DISPLAYED` |
| `/tokens/*`, `/wallets/*`, `/caller-*`, `/social-calls` | token, wallet, caller surfaces | `DISPLAYED` |
| `/providers/health` | providers / operations | `DISPLAYED` |
| `/readiness` | readiness | `DISPLAYED` |
| `/audit/*`, `/config/versions` | audit | `DISPLAYED` with allow-listing |
| `/state`, `/config`, `/runtime-settings` | settings | `DISPLAYED` with write-only secrets |
| `/control/*` mutations | server control gateway/settings | `EXECUTION_OUT_OF_SCOPE` for browser alpha/read surfaces; protected admin workflow only |
| `/positions/*` | positions | `DISPLAYED` read-only; no submission authority |

## Review rules

1. A new backend field must be added to `frontendFields` or an omission with
   a status/reason before the change is considered complete.
2. A parser may return `null`/`UNKNOWN`; it may not default missing evidence to
   a successful number or state.
3. A browser component may format, sort, filter, expand, and group only.
4. Any new UI must preserve the protected mode boundary and avoid raw secrets,
   provider payloads, and execution authority.
