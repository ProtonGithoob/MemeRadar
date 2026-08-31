# Phase 8 / Sprint 8.2 — Radar and Token Detail

## Status

Approved for autonomous implementation on 2026-08-31. This sprint consumes
the existing bounded Sprint 7.2 read API and does not add provider calls,
execution controls or live trading behavior.

## Goal

Turn the shell into an operational read surface by showing ranked candidates,
bounded filters, token detail, event-time evidence and explainable market,
holder, social and narrative projections.

## Scope and acceptance criteria

- The root App Router page renders a server-fetched Radar view with ranked
  candidate rows/cards and URL-backed state/risk/minimum-score filters.
- The Radar handles missing API configuration, `401`/`5xx`, timeout and
  malformed responses as explicit unavailable states; it never fabricates a
  candidate, score or healthy provider.
- Candidate rows link to `/tokens/{token_id}` using the API’s canonical token
  UUID and show symbol/name, bounded mint identity, state, score/confidence,
  risk disposition/quality and freshness.
- The token detail route uses the async dynamic `params` contract, fetches the
  token and timeline server-side, and renders overview data, pools, score/risk
  status, evidence timeline, provenance and no-lookahead event timestamps.
- Detail pages render dependency-free market, liquidity and flow SVG charts
  from an allow-list of normalized timeline metrics. Missing metrics are
  visibly unavailable rather than zero.
- Detail pages render a holder concentration/cluster panel and a social /
  narrative panel with source/provenance metadata. Both remain explicit
  `UNKNOWN`/empty when evidence is absent.
- All displayed values are bounded read projections. Raw payloads, raw provider
  references, bearer tokens and private environment variables never cross into
  client components or browser markup.
- Existing theme, realtime, four protected operating-mode badges and advisory
  boundary remain present on Radar and detail routes. No UI action mutates
  candidates, risk, config, kill switches or execution.

## Design

### Server-side read gateway

`apps/web/src/app/lib/read-api.ts` is a server-only-by-convention module. It
reads `MEMERADAR_API_BASE_URL` first and falls back to the existing public base
URL for keyless local development. An optional `MEMERADAR_VIEWER_API_TOKEN`
is sent only in a server-side `Authorization` header; it is never a
`NEXT_PUBLIC_` variable and is never returned in a DTO. Every request uses
`cache: "no-store"`, a short timeout, and a bounded allow-listed path/query.

The gateway parses only the fields needed by the UI into small TypeScript
records. It rejects malformed page, candidate, token or timeline entries and
maps transport/status failures to stable display reasons without including
response bodies. The UI receives `ReadResult<T>`, a success DTO or an explicit
unavailable reason.

### Radar

`app/page.tsx` remains a Server Component with the Next.js 16 async
`searchParams` prop. `parseRadarFilters` accepts only `state`,
`risk_disposition` and `min_score` within the read API bounds. A GET form
submits those values back to `/`, preserving a shareable, refreshable filter
state without client-side credentials or a stateful data cache.

`components/radar.tsx` renders the page header, filter controls, page status,
and a responsive table that becomes stacked candidate cards on small screens.
The table’s sort order is the API’s ranked order; the browser does not
re-score or reorder candidates. A candidate link contains only the canonical
token ID.

### Token detail and evidence projections

`app/tokens/[tokenId]/page.tsx` awaits the dynamic route params, validates the
UUID shape before building a request path, then fetches token and timeline in
parallel. `components/token-detail.tsx` renders:

- token identity, chain/program, creator and pools;
- score, risk and freshness status primitives;
- event-time timeline entries with quality, reason codes and provenance;
- three SVG evidence charts (price, liquidity, net flow) from known metric
  keys only;
- holder concentration/cluster bars from known holder keys only;
- social/narrative evidence references with provider, source ID and observed
  time, without rendering raw post/provider payloads.

The timeline is rendered in the API-provided event-time order. No client-side
wall-clock or arrival-time sort is used, and no future event is synthesized.

### Shared shell

`components/operator-header.tsx` shares product identity, local-analysis
environment, realtime status and theme controls between Radar and detail
routes. It imports only the already isolated client leaves from Sprint 8.1.
The page and detail route pass only serializable, parsed read DTOs to the
server-safe display components.

## Failure and safety behavior

- No API base URL: show `READ API NOT CONFIGURED`, an empty Radar and explicit
  unavailable detail state.
- `401`: show `READ API AUTHORIZATION UNAVAILABLE`; never suggest placing a
  token in browser code.
- timeout/`5xx`: show `RADAR UNAVAILABLE` or `DETAIL UNAVAILABLE` with a retry
  link; do not label the source healthy.
- malformed response: show `INVALID READ RESPONSE`; do not partially display
  an unvalidated record.
- empty collection: show `NO CANDIDATES MATCH FILTERS` or `NO EVIDENCE YET`,
  not a fake sample row.
- unknown/stale/invalid risk or freshness remains visibly non-safe.
- Charts, holder bars and social/narrative labels are explanatory projections;
  no score or external label changes a decision or control.

## Testing and quality gate

- Read-gateway tests cover bounded query construction, private server token
  headers, no-token output, timeout/status/malformed failures and validated
  DTO parsing.
- Radar tests cover ranked rendering, GET filter controls, candidate detail
  links, empty/error states, explicit unavailable/unknown badges and safe-mode
  labels.
- Detail tests cover token overview, pools, event-time ordering, provenance,
  allow-listed chart metrics, holder/social empty states and no raw payload
  rendering.
- Source/contract tests verify only server modules read private environment
  variables and browser leaves contain no API token or raw payload forwarding.
- `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, `make
  verify`, repository Compose config and the rebuilt web runtime probe remain
  required. Provider credentials remain unnecessary and live acceptance stays
  externally blocked.
