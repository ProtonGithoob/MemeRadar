# Phase 8 / Sprint 8.3 — Wallets, Providers, Settings and Audit

## Status

Approved for autonomous implementation on 2026-08-31 after the completed
Sprint 8.2 keyless checkpoint. This sprint connects already-existing bounded
GET contracts to the operator surface; it does not add provider calls,
execution controls or a second data model.

## Goal

Make the remaining operational intelligence visible and explainable through
server-rendered pages for smart-wallet evidence, provider health, validated
control configuration and immutable audit history.

## Scope and acceptance criteria

- Extend the server-side read gateway with strict bounded parsers and GET
  helpers for wallets, wallet detail, provider health, audit events, config
  versions and control state/config.
- Add `/wallets`, `/wallets/[address]`, `/providers`, `/settings` and `/audit`
  routes. Every page preserves the operator header, protected mode labels and
  advisory/read-only boundary.
- Preserve API order for wallet ranking, provider health and audit/config
  history. The browser does not score, sort, poll, mutate or authorize.
- Render wallet score, confidence, tier, sample/outcome counts, win rate,
  realized PnL, freshness, reason codes and evidence references only as
  bounded display projections. External labels remain corroborating evidence.
- Render provider state, capability, checked time, bounded latency, known
  quota counters, freshness and safe error class. Empty or unavailable health
  is explicit and never becomes healthy.
- Render settings as a validated control-plane read projection. Show the
  protected modes, current restrictive control state, immutable config version,
  config hash and an explicit role-permission matrix. Do not add mutation
  buttons or accept arbitrary browser configuration; changes remain behind the
  authenticated API control boundary.
- Render audit events and config history with bounded action/target/actor/time,
  correlation identity and allow-listed before/after/config values. Never
  render raw payloads, response bodies, credentials or arbitrary secret-shaped
  keys.
- Valid wallet-address and UUID route boundaries fail closed before a fetch.
  Missing catalogs show an explicit empty state; missing API/auth/provider
  access shows a stable unavailable state.

## Architecture

```text
bounded GET API contracts
          |
  server-only read gateway
          |
  server-rendered pages/components
          |
  browser display only
```

The gateway continues to use `MEMERADAR_API_BASE_URL` for internal server
fetches, falls back to the existing browser-safe base only for local
development, and sends `MEMERADAR_VIEWER_API_TOKEN` only as a server-side
Bearer header. New control reads use the same bounded server boundary. No
server action, client fetch, WebSocket payload or form mutation is introduced
by this sprint.

The settings permission matrix is explanatory. It reflects the API's explicit
viewer/operator/admin/execution roles, but the page cannot mint a role,
change a protected mode, clear the execution kill switch, sign or submit a
transaction. `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` remain visible and
unchanged.

## Failure and safety behavior

- Gateway status mapping remains `UNAUTHORIZED`, `UNAVAILABLE`,
  `INVALID_RESPONSE` or `NOT_CONFIGURED`; response error bodies are never
  read for display.
- A malformed item invalidates its complete page. Unknown fields are not
  rendered. Numeric values outside bounded ranges become invalid rather than
  safe.
- `UNKNOWN`, `STALE`, `CONFLICTED` and `INVALID` remain visibly non-safe.
- A wallet score, provider `HEALTHY` label, control state or config version is
  evidence of current read state only; none can produce `ENTRY_READY` or
  execution authority.

## Testing and quality gate

- Gateway tests cover request paths/queries, private-token containment, strict
  parsing, malformed records, status mapping, control reads and route-boundary
  validation.
- Component/page tests cover API-order preservation, canonical links,
  empty/unavailable/invalid states, provider degradation, permission matrix,
  protected modes and absence of raw/secret fields.
- Run focused Vitest, full frontend test/lint/typecheck/build, `make verify`,
  Compose config and a keyless runtime probe before marking Sprint 8.3 done.
- Live providers remain `BLOCKED_EXTERNAL` when credentials/endpoints are not
  configured. E8.4 stream integrity/protocol verification begins only after
  Gate P8, not during this UI sprint.
