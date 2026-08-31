# Phase 8 / Sprint 8.2 Radar and Token Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the operator shell to the bounded read API through server-side fetching and render ranked Radar candidates, token detail, event-time evidence, allow-listed charts and provenance-aware intelligence panels.

**Architecture:** Keep all API fetches in the server-only-by-convention `lib/read-api.ts` module, using `MEMERADAR_API_BASE_URL` and an optional server-only viewer token. The root page and dynamic token page await Next.js 16 async request props, validate/parse read results and pass only serializable display records to server-safe components. Use plain GET forms, HTML links, CSS and SVG; no browser token, client-side data cache or chart dependency is introduced.

**Tech Stack:** Next.js 16.3.3 App Router, React 19, TypeScript 5.7, native `fetch`, CSS, SVG, Vitest 3, Testing Library and jsdom.

**Spec:** `docs/superpowers/specs/2026-08-31-phase-8-sprint-8-2-radar-detail-design.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/SCORING_AND_RISK.md`, `docs/SECURITY.md`, `docs/TESTING.md` and `docs/ROADMAP.md`.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` visible and unchanged.
- `MEMERADAR_VIEWER_API_TOKEN` is server-only; never name it `NEXT_PUBLIC_*`, render it, serialize it or put it in a URL.
- Never display raw provider payloads, response bodies, raw provider URLs or secret-shaped fields; render only validated bounded records and allow-listed metric projections.
- Missing, stale, unknown, invalid, unauthorized, timed-out and empty data remain explicit non-safe/unavailable states.
- The UI reads API data only; it cannot score, reorder, mutate, authorize `ENTRY_READY`, clear a kill switch, sign or submit transactions.
- Candidate ranking and timeline ordering come from the read API; do not invent client-side ranking or wall-clock ordering.
- No new dependency is allowed; use existing Next.js/React/test packages and native SVG/CSS.

---

### Task 1: Define failing server read-gateway and display tests

**Files:**
- Create: `apps/web/src/app/lib/read-api.test.ts`
- Create: `apps/web/src/app/components/radar.test.tsx`
- Create: `apps/web/src/app/components/token-detail.test.tsx`
- Modify: `apps/web/src/app/page.test.tsx`

**Interfaces:**
- Tests will consume `fetchCandidates`, `fetchToken`, `fetchTimeline`, `parseRadarFilters`, `ReadResult`, `RadarFilters`, `CandidateRecord`, `TokenRecord` and `TimelineRecord` from `./lib/read-api`.
- Tests will consume `RadarDashboard` from `./components/radar` and `TokenDetailView` from `./components/token-detail`.
- Test fixtures will use only normalized fields and synthetic safe IDs; no credential or raw-provider fixture is permitted.

- [x] **Step 1: Write read-gateway tests before implementation.** Stub `globalThis.fetch` and assert:
  - `parseRadarFilters` accepts only `state`, `risk_disposition` and `min_score`, ignores arrays/invalid ranges and never returns arbitrary query keys;
  - `fetchCandidates` sends `limit=50` plus only valid filter parameters;
  - an optional `MEMERADAR_VIEWER_API_TOKEN` is sent in an `Authorization` header but never appears in the result;
  - missing base URL returns `NOT_CONFIGURED` without calling fetch;
  - `401`, `503`, timeout/rejection and malformed JSON/records return stable failure reasons without response-body text;
  - a valid page parses bounded candidate fields and converts score values to finite `number | null`.

- [x] **Step 2: Write Radar rendering tests.** Render a successful page with two candidates and assert API order is preserved, score/risk/freshness badges are visible, each row links only to `/tokens/{token_id}`, the GET form has state/risk/min-score controls, and protected/advisory shell labels remain visible. Add tests for empty, unavailable and invalid-result states.

- [x] **Step 3: Write token-detail rendering tests.** Render a token plus timeline fixture containing score, market, holder, social and narrative entries. Assert token identity/pool/creator overview, event-time order, provenance/source labels, three chart labels, holder concentration/cluster panel and social/narrative panel. Assert raw payload text, bearer-like values and execution-authority fields are not rendered. Add empty/unknown and unavailable detail cases.

- [x] **Step 4: Run the new tests and verify the expected red state.** Run from `apps/web`:

```bash
npm test -- --run src/app/lib/read-api.test.ts src/app/components/radar.test.tsx src/app/components/token-detail.test.tsx src/app/page.test.tsx
```

Expected failure is missing gateway/component modules or the page import contract, not a test-environment or network failure.

### Task 2: Implement the bounded server-side read gateway and shared header

**Files:**
- Create: `apps/web/src/app/lib/read-api.ts`
- Create: `apps/web/src/app/components/operator-header.tsx`
- Modify: `apps/web/src/app/lib/read-api.test.ts` (from Task 1)
- Modify: `.env.example`
- Modify: `infra/compose/docker-compose.yml`

**Interfaces:**
- `type ReadFailureReason = "NOT_CONFIGURED" | "UNAUTHORIZED" | "UNAVAILABLE" | "INVALID_RESPONSE"`.
- `type ReadResult<T> = { ok: true; data: T } | { ok: false; reason: ReadFailureReason; status?: number }`.
- `interface ReadPage<T> { items: T[]; limit: number; hasMore: boolean; nextCursor: string | null }`.
- `interface RadarFilters { state?: string; riskDisposition?: "PASS" | "WARN" | "BLOCK" | "UNKNOWN"; minScore?: number }`.
- `interface CandidateRecord { id: string; tokenId: string; mintAddress: string; symbol: string | null; name: string | null; state: string; discoveredAt: string; discoverySource: string; stateChangedAt: string; score: number | null; scoreConfidence: number | null; riskDisposition: "PASS" | "WARN" | "BLOCK" | "UNKNOWN"; riskQualityState: "FRESH" | "STALE" | "UNKNOWN" | "INVALID"; riskReasonCodes: string[]; evidenceRefs: string[] }`.
- `interface TokenRecord { id: string; chain: string; mintAddress: string; tokenProgram: string; symbol: string | null; name: string | null; decimals: number | null; status: string; creatorWallet: string | null; pools: Array<{ id: string; venue: string; poolAddress: string; quoteMint: string }>; candidate: CandidateRecord | null }`.
- `interface TimelineRecord { id: string; tokenId: string; kind: string; sourceId: string; occurredAt: string; observedAt: string; ingestedAt: string; qualityState: "FRESH" | "STALE" | "UNKNOWN" | "INVALID" | "CONFLICTED"; reasonCodes: string[]; evidenceRefs: string[]; payload: Record<string, unknown>; provenance: Array<{ provider: string; sourceId: string; observedAt: string; parserVersion: string }> }`.
- `parseRadarFilters(input: Record<string, string | string[] | undefined>): RadarFilters`.
- `fetchCandidates(filters: RadarFilters): Promise<ReadResult<ReadPage<CandidateRecord>>>`.
- `fetchToken(tokenId: string): Promise<ReadResult<TokenRecord>>`.
- `fetchTimeline(tokenId: string): Promise<ReadResult<ReadPage<TimelineRecord>>>`.
- `OperatorHeader()` shares product identity, `LOCAL ANALYSIS`, `RealtimeStatus` and `ThemeToggle` between root and detail routes.

- [x] **Step 1: Implement environment and request helpers.** Read `MEMERADAR_API_BASE_URL` first and fall back to `NEXT_PUBLIC_API_BASE_URL`; reject absent/invalid HTTP(S) bases as `NOT_CONFIGURED`. Read `MEMERADAR_VIEWER_API_TOKEN` only in this module, build relative allow-listed paths with `URL`, use `cache: "no-store"`, set a bounded abort timer, and map status classes without reading error bodies.

- [x] **Step 2: Implement bounded parsers.** Parse pages only when `items`, `limit`, `has_more` and `next_cursor` have safe shapes. Parse candidates, tokens, pools and timeline entries with finite numeric bounds, bounded strings/arrays, valid ISO timestamps and safe payload objects. Reject the complete result on a malformed record; never pass through unknown objects.

- [x] **Step 3: Implement filter parsing and endpoint helpers.** Allow only the documented candidate state/risk values and `0..100` finite minimum score. Serialize snake-case API parameters, always include the default bounded limit, and validate dynamic token IDs as UUID-shaped strings before constructing token paths.

- [x] **Step 4: Implement and test `OperatorHeader`.** Keep it server-safe by importing only the existing client leaves; ensure no token/environment secret is passed as a prop. Re-run `read-api.test.ts` and confirm private-token assertions pass.

- [x] **Step 5: Configure the internal Compose URL without exposing secrets.** Add `MEMERADAR_API_BASE_URL=http://api:8000` to the web service and a blank server-only `MEMERADAR_VIEWER_API_TOKEN=` example/comment. Retain the existing public base URL only for local browser-safe metadata.

- [x] **Step 6: Commit the gateway checkpoint.** Run `git add apps/web/src/app/lib/read-api.ts apps/web/src/app/lib/read-api.test.ts apps/web/src/app/components/operator-header.tsx .env.example infra/compose/docker-compose.yml` and commit with `feat: add server-side dashboard read gateway`.

### Task 3: Implement the ranked Radar view and root route

**Files:**
- Create: `apps/web/src/app/components/radar.tsx`
- Modify: `apps/web/src/app/components/radar.test.tsx` (from Task 1)
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/page.test.tsx`
- Modify: `apps/web/src/app/globals.css`

**Interfaces:**
- `RadarDashboard({ filters, result }: { filters: RadarFilters; result: ReadResult<ReadPage<CandidateRecord>> })` renders the shared header, existing protected-mode/data-boundary shell and Radar content.
- `CandidateRow({ candidate }: { candidate: CandidateRecord })` renders only bounded display fields and links to `/tokens/${candidate.tokenId}`.

- [x] **Step 1: Implement `RadarDashboard` states.** Render `RADAR UNAVAILABLE`, `READ API AUTHORIZATION UNAVAILABLE`, `READ API NOT CONFIGURED`, `INVALID READ RESPONSE`, `NO CANDIDATES MATCH FILTERS` and a successful result without substituting a sample candidate or “healthy” status.

- [x] **Step 2: Implement the GET filter form.** Use `method="get"`, named `state`, `risk_disposition` and `min_score` controls, current values from `RadarFilters`, bounded number attributes and a reset link to `/`. Do not add client state or fetch calls.

- [x] **Step 3: Implement ranked table/card projection.** Preserve the API item order, render symbol/name/mint, state, `ScoreBadge`, confidence text, `RiskBadge`, `FreshnessBadge` and reason-code count, and link by canonical token UUID only. Use a responsive wrapper that becomes stacked cards on narrow screens.

- [x] **Step 4: Convert `app/page.tsx` to an async Next.js 16 Server Component.** Await `searchParams: Promise<Record<string, string | string[] | undefined>>`, call `parseRadarFilters` and `fetchCandidates`, then render `RadarDashboard`. Keep `"use client"` out of the page and preserve `OperatorHeader`/safe-mode labels.

- [x] **Step 5: Add Radar styles and run tests.** Add table/filter/empty/error styles and responsive rules without removing Sprint 8.1 theme/state styles. Run the Radar/page tests until green.

- [x] **Step 6: Commit the Radar checkpoint.** Run `git add apps/web/src/app/components/radar.tsx apps/web/src/app/components/radar.test.tsx apps/web/src/app/page.tsx apps/web/src/app/page.test.tsx apps/web/src/app/globals.css` and commit with `feat: add ranked radar view`.

### Task 4: Implement token detail, evidence timeline and explainable panels

**Files:**
- Create: `apps/web/src/app/components/token-detail.tsx`
- Create: `apps/web/src/app/tokens/[tokenId]/page.tsx`
- Modify: `apps/web/src/app/components/token-detail.test.tsx` (from Task 1)
- Modify: `apps/web/src/app/globals.css`

**Interfaces:**
- `TokenDetailView({ tokenResult, timelineResult }: { tokenResult: ReadResult<TokenRecord>; timelineResult: ReadResult<ReadPage<TimelineRecord>> })` renders the detail states and safe overview.
- `MetricChart({ label, points }: { label: string; points: Array<{ at: string; value: number }> })` renders an accessible SVG chart or explicit `NO DATA` state.
- `TokenTimeline({ entries }: { entries: TimelineRecord[] })` renders API event-time order, quality, reason codes and provenance without raw payload.

- [x] **Step 1: Implement detail failure/empty states.** Map gateway failure reasons to `DETAIL UNAVAILABLE`, `READ API AUTHORIZATION UNAVAILABLE`, `READ API NOT CONFIGURED` or `INVALID READ RESPONSE`; render `TOKEN NOT FOUND` for a valid empty token result and `NO EVIDENCE YET` for an empty timeline.

- [x] **Step 2: Implement token overview.** Render bounded name/symbol/status, chain/program, truncated mint/creator identities, pool venue/address/quote identity, `ScoreBadge`, `RiskBadge` from candidate risk or `UNKNOWN`, and `FreshnessBadge` from candidate quality or `UNKNOWN`. Keep the `execution_eligible` concept out of interactive controls and show the advisory boundary instead.

- [x] **Step 3: Implement the event-time timeline.** Iterate the API-provided order without sorting by browser time; render occurred/observed times, kind, quality badge, reason codes and bounded provider/source/parser provenance. Never render `payload`, `raw_payload_ref`, response text or credentials.

- [x] **Step 4: Implement allow-listed metric extraction and SVG charts.** Read only numeric keys `price`, `liquidity`, `liquidity_usd`, `buy_volume`, `buyVolume24h`, `sell_volume`, `sellVolume24h`, `alpha_score` and `holder_supply_pct` from known payload/value containers. Derive net flow only from paired buy/sell numbers, reject non-finite/out-of-range values, cap points to 24 and render price/liquidity/net-flow charts with labels and timestamped accessible point text.

- [x] **Step 5: Implement holder and social/narrative projections.** Show bounded concentration/cluster percentages as horizontal bars from known holder keys; show `UNKNOWN` when absent. For social/narrative entries, render kind, provider, source ID and observed time plus reason codes; do not display post text or raw provider payload.

- [x] **Step 6: Implement the dynamic route.** Await `params: Promise<{ tokenId: string }>`, validate UUID shape, fetch token/timeline in parallel on the server, render `OperatorHeader` and `TokenDetailView`, and provide a plain link back to `/` for invalid/missing routes.

- [x] **Step 7: Add detail styles and run tests.** Add overview/timeline/chart/holder/social layout styles with mobile stacking, then run Radar/detail/page tests and confirm raw payload/secret assertions remain green.

- [x] **Step 8: Commit the detail checkpoint.** Run `git add apps/web/src/app/components/token-detail.tsx apps/web/src/app/components/token-detail.test.tsx apps/web/src/app/tokens/[tokenId]/page.tsx apps/web/src/app/globals.css` and commit with `feat: add token detail evidence view`.

### Task 5: Reconcile documentation and complete the Sprint 8.2 quality gate

**Files:**
- Modify: `.env.example`
- Modify: `infra/compose/docker-compose.yml`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/SECURITY.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

**Interfaces:**
- Documentation must state that Radar/detail data is fetched server-side through bounded read contracts, the optional viewer token stays server-only, and missing data remains explicit.
- Sprint 8.2 is complete only after frontend tests/lint/typecheck/build, `make verify`, Compose config and rebuilt web runtime evidence pass without credentials.

- [x] **Step 1: Run all frontend and repository gates.** Run `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` from `apps/web`, then `make verify` and `docker compose -f infra/compose/docker-compose.yml config --quiet`. Record exact results and preserve external blockers honestly.

- [x] **Step 2: Rebuild and probe the web image.** Rebuild the temporary Compose web service, wait for normal Next readiness, request `/` and a known invalid token route, and assert HTTP `200` plus Radar protected/advisory markers. Confirm no credential value or raw provider body appears in the HTML/log probe.

- [x] **Step 3: Reconcile roadmap/security/testing/status docs.** Mark all Sprint 8.2 checkboxes complete, document server-only fetch/auth, candidate/detail empty/error behavior, event-time/no-lookahead rendering, chart allow-list and remaining Sprint 8.3 work. Add exact gate/runtime evidence and keep all four protected modes recorded.

- [x] **Step 4: Mark this plan complete, commit and push.** Check every plan item, run `git diff --check`, commit documentation with `docs: complete Sprint 8.2 radar detail checkpoint`, push `main` without force and verify local HEAD equals `origin/main`.

- [x] **Step 5: Continue automatically to Phase 8 / Sprint 8.3 Wallets, Providers, Settings and Audit** after the checkpoint, treating missing catalogs as explicit empty/unavailable state.

## Completion evidence

Implemented in commits `39aa7e0` (bounded server read gateway), `5e2387d`
(ranked Radar) and `68aa88b` (token detail). The final keyless gate passed
frontend Vitest (`23 passed`), lint, typecheck, build, `make verify` and the
isolated Compose web runtime probe. The remote documentation merge
`8837637` was preserved; no execution, signing, provider or secret authority
was introduced.

## Protected modes

Every Radar/detail render, server fetch, chart, timeline and runtime probe must
preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, and `AUTO_EXECUTION=false`. The browser is an
observability surface only. Read data, external labels, LLM narratives,
realtime events and theme preference cannot grant role permission, authorize
`ENTRY_READY`, clear a kill switch, sign a transaction or submit an order.
