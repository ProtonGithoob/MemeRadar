# Phase 8 / Sprint 8.1 Dashboard Design System / Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive evidence-first operator shell with reusable typed status primitives, safe-mode badges, theme selection and a bounded reconnecting realtime lifecycle seam.

**Architecture:** Keep `apps/web/src/app/page.tsx` as a server component that composes server-safe shell and badge components. Isolate browser APIs in `theme-toggle.tsx` and `realtime-status.tsx`; keep transport lifecycle in a provider-neutral `lib/realtime.ts` with injectable socket and timer seams so failure behavior is deterministic in Vitest. No frontend component will authorize, score, persist or submit anything.

**Tech Stack:** Next.js 16.3.3 App Router, React 19, TypeScript 5.7, CSS custom properties, Vitest 3, Testing Library and jsdom.

**Spec:** `docs/superpowers/specs/2026-08-31-phase-8-sprint-8-1-dashboard-shell-design.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/SECURITY.md` and `docs/TESTING.md`.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` visible and unchanged.
- The browser receives no API token, cookie, provider credential, wallet material or raw persisted provider payload.
- Missing `NEXT_PUBLIC_REALTIME_URL` is an explicit `DISABLED` state; it is never a fabricated healthy/live state.
- Realtime code owns connection lifecycle only; it cannot change candidate state, risk, score, alerts, config or execution controls.
- Scores are bounded display projections; risk and freshness `UNKNOWN`, `STALE` and `INVALID` remain visibly non-safe.
- Use App Router server/client boundaries: only components needing `useEffect`, `localStorage`, `window` or `WebSocket` use `"use client"`.
- Do not add a dependency; use existing Next.js, React, CSS and test tooling.

---

### Task 1: Define failing component and transport tests

**Files:**
- Modify: `apps/web/src/app/page.test.tsx`
- Create: `apps/web/src/app/components/status-badges.test.tsx`
- Create: `apps/web/src/app/lib/realtime.test.ts`
- Create: `apps/web/src/app/components/theme-toggle.test.tsx`

**Interfaces:**
- Tests will consume `SafetyBadge`, `ScoreBadge`, `RiskBadge`, `FreshnessBadge`, `ConnectionBadge` from `./status-badges`.
- Tests will consume `RealtimeTransport`, `RealtimeStatus`, `RealtimeSocket`, `RealtimeScheduler` and `DEFAULT_RECONNECT_POLICY` from `../lib/realtime`.
- Tests will consume `ThemeToggle` from `./theme-toggle`.

- [ ] **Step 1: Extend the page test with the Sprint 8.1 acceptance language.** Assert the rendered page contains `LIVE DATA`, `ADVISORY OUTPUT`, `STREAM DISABLED`, the four protected mode labels and a `Theme` button. Keep the existing identity assertions.

- [ ] **Step 2: Write status primitive tests before creating the components.** Cover a score of `84` as an accessible `84 / 100` state, a missing score as `UNAVAILABLE`, `UNKNOWN` risk with a non-safe state, `STALE` freshness with text, a connected stream label and a paper/advisory safety badge. Assert `data-state` and accessible labels so color cannot be the only signal.

- [ ] **Step 3: Write transport lifecycle tests with injected fakes.** Use a fake socket with assignable `onopen`, `onerror`, `onclose` and `onmessage` handlers plus a fake scheduler that records delays. Assert:
  - no URL publishes `DISABLED` and creates no socket;
  - a successful open publishes `CONNECTING` then `CONNECTED` and resets retries;
  - a close schedules bounded delays `1000`, `2000`, then `4000` with a policy cap;
  - exhausting `maxAttempts` publishes `DEGRADED` and schedules no further retry;
  - `stop()` clears the timer, closes the socket and publishes `STOPPED`;
  - an incoming message is not parsed or emitted as application data.

- [ ] **Step 4: Write the theme toggle test.** Assert the initial server-safe label is stable, clicking cycles `system -> light -> dark -> system`, light/dark writes only the `data-theme` attribute and `memeradar-theme` storage key, and returning to system removes both overrides. No network or API call is involved.

- [ ] **Step 5: Run the new web tests and verify the expected red state.** Run `npm test -- --run src/app/page.test.tsx src/app/components/status-badges.test.tsx src/app/lib/realtime.test.ts src/app/components/theme-toggle.test.tsx` from `apps/web`. Expected failure is missing component/transport modules, not a test-environment crash.

### Task 2: Implement reusable display primitives

**Files:**
- Create: `apps/web/src/app/components/status-badges.tsx`
- Create: `apps/web/src/app/components/status-badges.test.tsx` (from Task 1)

**Interfaces:**
- `SafetyBadge({ label, value, tone }: { label: string; value: string; tone: "safe" | "paper" | "disabled" | "advisory" })` returns a text-first badge with `data-state={tone}`.
- `ScoreBadge({ value }: { value: number | null | undefined })` accepts only finite values in `0..100` and renders `UNAVAILABLE` otherwise.
- `RiskBadge({ value }: { value: "PASS" | "WARN" | "BLOCK" | "UNKNOWN" })` renders the value and a descriptive accessible suffix.
- `FreshnessBadge({ value }: { value: "FRESH" | "STALE" | "UNKNOWN" | "INVALID" })` renders the value and a descriptive accessible suffix.
- `ConnectionBadge({ state, reason }: { state: RealtimeStatus["state"]; reason?: string })` renders the lifecycle state and a bounded reason.

- [ ] **Step 1: Create the typed component module with allow-listed display mappings.** Keep all labels and descriptions in local constants; do not infer a safe state from unknown or missing input.

- [ ] **Step 2: Add stable semantic attributes and accessible text.** Every badge uses `role="status"` where appropriate, `data-state` with a lower-case allow-listed value and an explicit visible label. Never rely only on CSS color.

- [ ] **Step 3: Run the component test until green.** Run the focused Vitest command from Task 1 and confirm the tests pass without changing their assertions.

- [ ] **Step 4: Commit the display primitive checkpoint.** Run `git add apps/web/src/app/components/status-badges.tsx apps/web/src/app/components/status-badges.test.tsx` and commit with `feat: add dashboard status primitives`.

### Task 3: Implement bounded realtime lifecycle and client status component

**Files:**
- Create: `apps/web/src/app/lib/realtime.ts`
- Create: `apps/web/src/app/components/realtime-status.tsx`
- Modify: `apps/web/src/app/lib/realtime.test.ts` (from Task 1)
- Modify: `apps/web/src/app/page.test.tsx` (from Task 1)

**Interfaces:**
- `type RealtimeState = "DISABLED" | "CONNECTING" | "CONNECTED" | "RECONNECTING" | "DEGRADED" | "STOPPED"`.
- `interface RealtimeStatus { state: RealtimeState; attempt: number; reason?: string }`.
- `interface RealtimeSocket { onopen: (() => void) | null; onerror: (() => void) | null; onclose: (() => void) | null; onmessage: ((event: { data: unknown }) => void) | null; close(): void }`.
- `interface RealtimeScheduler { setTimeout(task: () => void, delayMs: number): unknown; clearTimeout(handle: unknown): void }`.
- `class RealtimeTransport` constructor accepts `{ url?: string; socketFactory?: (url: string) => RealtimeSocket; scheduler?: RealtimeScheduler; policy?: { maxAttempts: number; baseDelayMs: number; maxDelayMs: number }; onStatus?: (status: RealtimeStatus) => void }`, and exposes `start(): void` and `stop(): void`.
- `useRealtimeStatus(url?: string): RealtimeStatus` creates one transport per URL, subscribes status changes, starts on mount and stops on cleanup.
- `RealtimeStatus` renders a `ConnectionBadge` and never exposes message data.

- [ ] **Step 1: Implement the transport state machine with browser adapters.** Use a lazy `new WebSocket(url)` factory and `window.setTimeout` scheduler only inside callable functions. Publish `DISABLED` immediately when no URL exists; otherwise publish `CONNECTING`, then handle open/close/error transitions.

- [ ] **Step 2: Implement bounded reconnect behavior.** Increment the retry count only for a scheduled retry, calculate `min(baseDelayMs * 2 ** (attempt - 1), maxDelayMs)`, prevent duplicate scheduling when both error and close fire, reset the count after open, and publish `DEGRADED` once the retry budget is exhausted.

- [ ] **Step 3: Implement clean shutdown and ignore messages.** Clear pending timers, detach handlers before closing, publish `STOPPED`, and do not call `JSON.parse` or forward `onmessage` data.

- [ ] **Step 4: Implement `useRealtimeStatus` and `RealtimeStatus`.** Read only the compile-time `NEXT_PUBLIC_REALTIME_URL` public value, pass it to the hook, and render explicit disabled/degraded copy. Keep the component’s initial markup deterministic for hydration.

- [ ] **Step 5: Run transport and page tests until green.** Run the focused Vitest command from Task 1 and confirm the reconnect delay, retry exhaustion, cleanup and page status assertions pass.

- [ ] **Step 6: Commit the realtime checkpoint.** Run `git add apps/web/src/app/lib/realtime.ts apps/web/src/app/lib/realtime.test.ts apps/web/src/app/components/realtime-status.tsx apps/web/src/app/page.test.tsx` and commit with `feat: add dashboard realtime lifecycle seam`.

### Task 4: Build the responsive themed operator shell

**Files:**
- Create: `apps/web/src/app/components/theme-toggle.tsx`
- Create: `apps/web/src/app/components/theme-toggle.test.tsx` (from Task 1)
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/app/layout.tsx`
- Modify: `apps/web/src/app/page.test.tsx`

**Interfaces:**
- `ThemeToggle` is a Client Component with no props. It cycles local `system`, `light` and `dark` preferences and writes only `memeradar-theme`.
- `Home` remains a default Server Component and imports `ThemeToggle` and `RealtimeStatus` as isolated interactive leaves.
- `metadata` remains the existing safe product metadata with a dashboard-oriented description.

- [ ] **Step 1: Add the client-only theme toggle.** Initialize to `system`, read local storage in `useEffect`, apply/remove the root `data-theme` attribute, and render a stable button before hydration. Use a button label and `aria-label` that identify the current preference.

- [ ] **Step 2: Replace the placeholder page composition with the shell layout.** Add a top bar with product identity, environment badge, `RealtimeStatus` and theme button; a hero explaining evidence-before-execution; mode cards for all four protected modes; a signal-quality grid using score/risk/freshness primitives; and a radar queue empty state that states normalized observations are not loaded.

- [ ] **Step 3: Update the CSS system.** Add dark defaults, light `prefers-color-scheme` variables and explicit `[data-theme="light"]`/`[data-theme="dark"]` overrides. Add responsive desktop grid/single-column mobile rules, focus-visible controls, reduced-motion handling and state styles for safe/paper/disabled/advisory/risk/freshness/connection badges.

- [ ] **Step 4: Keep layout metadata and server/client boundaries valid.** Do not add `"use client"` to `page.tsx` or `layout.tsx`; ensure all browser globals remain inside the two client leaves.

- [ ] **Step 5: Run the complete web test cycle.** Run `npm test`, `npm run lint`, `npm run typecheck` and `npm run build` from `apps/web`; fix implementation issues without weakening safety assertions.

- [ ] **Step 6: Commit the shell checkpoint.** Run `git add apps/web/src/app/page.tsx apps/web/src/app/globals.css apps/web/src/app/layout.tsx apps/web/src/app/components/theme-toggle.tsx apps/web/src/app/components/theme-toggle.test.tsx apps/web/src/app/page.test.tsx` and commit with `feat: build responsive operator shell`.

### Task 5: Reconcile documentation and complete the Sprint 8.1 quality gate

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/SECURITY.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/STATUS.md`
- Modify: this plan

**Interfaces:**
- Documentation must describe the public-only realtime URL seam, visible degraded/disabled state, client/server boundary, theme preference scope and non-authorizing UI behavior.
- Sprint 8.1 is complete only after frontend checks, `make verify`, a production build, and the Compose web image/runtime probe pass without credentials.

- [ ] **Step 1: Run the frontend and repository gates.** Record exact results for `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, `make verify`, `docker compose -f infra/compose/docker-compose.yml config --quiet` and the existing temporary Compose web probe. Preserve any external/provider blockers as `BLOCKED_EXTERNAL`.

- [ ] **Step 2: Reconcile the roadmap and architecture docs.** Mark all four Sprint 8.1 checkboxes complete and document that the shell is operationally useful but candidate/detail data remains pending Sprint 8.2. State that realtime is disabled when no public URL is configured and degraded after bounded retries.

- [ ] **Step 3: Update security/testing/status evidence.** Record that the browser receives no secrets/raw provider data, all protected badges remain visible, UNKNOWN/STALE/INVALID are non-safe display states, and the transport cannot authorize execution. Add exact command outputs and remaining external blockers to `docs/STATUS.md`.

- [ ] **Step 4: Mark this plan complete and commit the documentation checkpoint.** Run `git add docs/ROADMAP.md docs/ARCHITECTURE.md docs/SECURITY.md docs/TESTING.md docs/STATUS.md docs/superpowers/plans/2026-08-31-phase-8-sprint-8-1-dashboard-shell.md`, commit with `docs: complete Sprint 8.1 dashboard shell checkpoint`, and push `main` without force.

- [ ] **Step 5: Continue automatically to Phase 8 / Sprint 8.2 Radar and Token Detail** after the checkpoint, preserving all protected modes and treating missing backend/provider data as explicit unavailable state.

## Protected modes

Every page, component, transport test and runtime probe must preserve
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`. The web UI is an observability surface only. Realtime
events, theme preference, display scores, external labels and LLM narratives
cannot grant control permission, clear a kill switch, authorize `ENTRY_READY`,
sign a transaction or submit an order.
