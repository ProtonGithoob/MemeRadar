# Phase 8 / Sprint 8.3 Operator Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Connect the existing bounded read/control contracts to server-rendered wallet, provider, settings and audit pages without adding browser authority.

**Architecture:** Extend the server-only-by-convention `lib/read-api.ts` gateway. Keep pages as async App Router Server Components. Use bounded parsers, allow-listed display projections, plain links and CSS; do not add client fetching, mutation forms or provider SDKs. The Playwright test runner is a dev-only Gate P8 dependency; it adds no runtime authority.

**Spec:** `docs/superpowers/specs/2026-08-31-phase-8-sprint-8-3-operator-intelligence-design.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/SCORING_AND_RISK.md`, `docs/SECURITY.md`, `docs/TESTING.md` and `docs/ROADMAP.md`.

## Global constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` visible and unchanged.
- Keep viewer/control credentials server-only; never put them in props, URLs, browser code, markup or error text.
- Preserve API order and explicit `UNKNOWN`/`STALE`/`CONFLICTED`/`INVALID`/unavailable states.
- Never render raw payloads, response bodies, secret-shaped fields or arbitrary config keys.
- Wallet/provider/audit/config reads are observations; no page scores, mutates, authorizes, signs or submits.

## Task 1: Define failing gateway and display tests

**Files:** `apps/web/src/app/lib/read-api.test.ts`, new wallet/provider/settings/audit component tests and route/page tests.

- [x] Add deterministic fixtures and tests for wallet/page parsing, provider health, audit/config, control state/config, request query bounds, private-token containment and invalid UUID/address rejection.
- [x] Add component tests for wallet ranking/detail, provider degradation, settings permission gates/protected modes and audit/config allow-listed projections.
- [x] Run the focused tests and confirm only expected missing-module/interface failures occur.

## Task 2: Extend the bounded server read gateway

**Files:** `apps/web/src/app/lib/read-api.ts` and its tests.

- [x] Add strict record types/parsers for `WalletRecord`, `ProviderHealthRecord`, `AuditEventRecord`, `ConfigVersionRecord`, `ControlStateRecord` and `ControlConfigRecord`.
- [x] Add `fetchWallets`, `fetchWallet`, `fetchProviderHealth`, `fetchAuditEvents`, `fetchConfigVersions`, `fetchControlState` and `fetchControlConfig` with bounded allow-listed query parameters and the existing status/timeout/auth behavior.
- [x] Validate canonical UUIDs and safe Solana-address path segments; reject malformed items/pages and true `execution_eligible` values.
- [x] Test control config field bounds/allow-list and protected-mode response shape without exposing private environment values.

## Task 3: Build wallet leaderboard and detail

**Files:** new `components/wallets.tsx`, `components/wallet-detail.tsx`, `wallets/page.tsx`, `wallets/[address]/page.tsx`, tests and styles.

- [x] Render API-ranked wallet cards with score/confidence/tier/outcome/freshness evidence and canonical detail links.
- [x] Render wallet detail with bounded metrics, reason/evidence references and explicit advisory/non-execution copy.
- [x] Render empty, unavailable, invalid-address and not-found states without sample data.

## Task 4: Build provider health/quota page

**Files:** new `components/providers.tsx`, `providers/page.tsx`, tests and styles.

- [x] Render provider/capability/state/checked time/latency/freshness, known quota counters and safe error class in API order.
- [x] Make `UNKNOWN`, `DEGRADED`, `DOWN`, stale and missing health prominent; never infer health from an empty page.
- [x] Render explicit read/auth/configuration failure states.

## Task 5: Build settings and audit explorers

**Files:** new `components/settings.tsx`, `components/audit.tsx`, `settings/page.tsx`, `audit/page.tsx`, tests and styles.

- [x] Render control state/config reads, protected-mode values, immutable config metadata, allow-listed config fields and explicit role-permission matrix.
- [x] Keep settings read-only and state that mutations require the authenticated API control boundary; do not introduce arbitrary config inputs or execution controls.
- [x] Render audit events/config history in API order with bounded metadata and allow-listed before/after values only.
- [x] Render partial failure/empty states independently for state/config and audit/config sections.

## Task 6: Navigation, verification and documentation

**Files:** `operator-header.tsx`, `globals.css`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TESTING.md`, `docs/STATUS.md`, this plan.

- [x] Add accessible server-safe navigation to all operator pages and responsive styles without changing Sprint 8.1/8.2 contracts.
- [x] Run focused Vitest, full frontend tests/lint/typecheck/build, `make verify`, Compose config and a rebuilt keyless runtime probe.
- [x] Mark Sprint 8.3 complete, record exact evidence and external blockers, commit/push a coherent checkpoint, then run Gate P8.
- [x] Do not begin E8.4 until Gate P8 passes; leave the repository resumable with the next task documented.

Checkpoint evidence: source implementation `1e4df5f`, followed by the Gate P8
test harness and documentation reconciliation. Focused operator tests pass 18;
full Vitest passes 34; `make verify` passes with 454 backend tests and 6
skips; and Playwright passes 3 browser tests against the rebuilt isolated
Compose runtime. The next task is E8.4, not a Phase 8 restart.

## Protected modes

Every page, gateway read, test and runtime probe preserves
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and
`AUTO_EXECUTION=false`. The web UI is an observability surface only; wallet
labels, provider health, configuration metadata and audit history cannot grant
role permission, clear a kill switch, authorize `ENTRY_READY`, sign or submit
an order.
