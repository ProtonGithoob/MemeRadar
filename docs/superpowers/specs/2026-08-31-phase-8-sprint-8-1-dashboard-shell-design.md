# Phase 8 / Sprint 8.1 — Dashboard Design System / Shell

## Status

Approved for autonomous implementation on 2026-08-31. This sprint establishes
the frontend foundation only; it does not claim that the backend read API or a
live event stream is configured in a deployment.

## Goal

Make the operator web shell responsive, evidence-oriented and honest about
runtime state while providing reusable visual primitives for later Radar,
Token Detail, Providers and Settings pages.

## Scope and acceptance criteria

- The root page remains an App Router Server Component and renders a responsive
  operator shell without requiring browser APIs or credentials.
- The shell works in dark mode and light mode selected from the system
  preference, with a small client-side theme toggle for operators who need an
  explicit override. The selected override is local UI preference only and is
  never sent to the API.
- Reusable typed components render score, risk, freshness, connection and
  safety/advisory states with accessible text, not color alone.
- The shell always shows `ANALYSIS ONLY`, `PAPER TRADING`, `MANUAL EXECUTION`
  and `AUTO EXECUTION` badges, plus an explicit advisory/data boundary. No UI
  state implies that live execution is enabled.
- A browser-only realtime seam accepts a public WebSocket URL only when
  configured. It reports `DISABLED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`,
  `DEGRADED` or `STOPPED`; it never invents data when no endpoint exists.
- The transport reconnects with bounded exponential backoff, resets its
  attempt counter after a successful connection, closes cleanly on unmount and
  degrades after the configured retry budget. A malformed or unavailable
  stream is an operational status, not an authorization or risk decision.
- No API token, cookie, provider secret, wallet material or raw event payload
  is exposed to the browser by this sprint.

## Design

### Composition

`apps/web/src/app/page.tsx` remains the server-rendered composition root. It
uses server-safe presentational primitives from `components/status-badges.tsx`
and `components/operator-shell.tsx`. Browser-only behavior is isolated in
`components/theme-toggle.tsx` and `components/realtime-status.tsx`, following
the Next.js App Router server/client boundary.

The reusable primitive vocabulary is deliberately small:

- `SafetyBadge` — protected operating mode or advisory/data classification;
- `ScoreBadge` — bounded 0–100 score with explicit unavailable state;
- `RiskBadge` — `PASS`, `WARN`, `BLOCK` or `UNKNOWN` with severity text;
- `FreshnessBadge` — `FRESH`, `STALE`, `UNKNOWN` or `INVALID`;
- `ConnectionBadge` — transport state and human-readable degradation reason.

Each primitive exposes its meaning in text and uses a stable `data-state`
attribute for later styling and testing. The values are display projections;
they do not create or alter domain decisions.

### Realtime seam

`apps/web/src/app/lib/realtime.ts` defines a provider-neutral
`RealtimeTransport` and `RealtimeTransportFactory`. The default factory reads
the public `NEXT_PUBLIC_REALTIME_URL` value at the client boundary and returns
`DISABLED` when absent. Tests inject a connector and scheduler so reconnect
behavior is deterministic without a browser server.

The transport owns only connection lifecycle:

```text
DISABLED (no public URL)
    |
    v
CONNECTING -> CONNECTED -> RECONNECTING -> CONNECTED
    |              |
    +--------------+----> DEGRADED -> STOPPED
```

It forwards opaque, bounded status metadata to the UI but does not parse,
score, persist or authorize incoming events. A future API stream adapter can
translate normalized backend events into page data behind this seam.

### Theme behavior

CSS variables define the dark default and a light `prefers-color-scheme`
variant. The client toggle applies `data-theme="light"` or
`data-theme="dark"` to the document and stores only `memeradar-theme` in
`localStorage`; `system` removes the override. Theme initialization is
hydration-safe by rendering a stable button label until the component mounts.

### Responsive shell

The shell uses a two-column desktop layout that collapses to a single column
under the existing mobile breakpoint. A compact top bar carries product,
environment, connection and theme controls; the main grid presents operating
modes, signal-quality primitives and a radar placeholder. The placeholder is
intentionally explicit that candidate data is not yet loaded, rather than
showing fabricated market values.

## Failure and safety behavior

- Missing `NEXT_PUBLIC_REALTIME_URL` is `DISABLED`, not `CONNECTED` or `PASS`.
- Connector failure is visible as `RECONNECTING` and eventually `DEGRADED`;
  no stale event is relabeled as current.
- `STOPPED` is only a lifecycle state after explicit shutdown/unmount.
- Realtime status cannot modify protected operating modes, candidate state,
  risk, score, alerts or execution controls.
- Theme preference and public endpoint metadata are the only browser-local
  configuration introduced by this sprint; secrets remain server-side.

## Testing and quality gate

- Component tests assert accessible labels, stable state attributes, safe-mode
  badges and unavailable/unknown display states.
- Transport tests inject a fake connector and scheduler to assert disabled
  mode, successful connection, bounded reconnect delays, retry exhaustion,
  clean stop and no event parsing.
- Page tests assert the shell identity, all four protected mode badges,
  advisory boundary and realtime degraded/disabled copy.
- `npm run lint`, `npm run typecheck`, `npm test` and the repository `make
  verify` remain required. A production build and Compose web image probe must
  continue to pass without credentials.
