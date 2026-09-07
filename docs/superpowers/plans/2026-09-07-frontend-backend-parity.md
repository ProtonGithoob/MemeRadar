# Frontend / Backend Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MemeRadar settings dynamically manageable where safe, restore full frontend/backend parity, and complete route-level UX/browser acceptance without weakening safety.

**Architecture:** Extend the existing control plane with one metadata-driven runtime settings registry, write-only secret handling, versioned/audited mutations and provider tests. Frontend consumes that schema/state and reuses existing read APIs; business logic remains server-side.

**Tech Stack:** Existing Python/FastAPI/PostgreSQL application, Next.js/TypeScript web app, Vitest/Playwright/pytest, existing audit/control/provider abstractions.

**Spec:** `docs/superpowers/specs/2026-09-07-frontend-backend-parity-design.md`

## Global Constraints

- Preserve current production-readiness work and four unrelated WIP files.
- Preserve protected modes exactly: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No secret value may be returned to the frontend.
- Do not duplicate provider, social, wallet, scoring, research or execution engines.
- Do not make every environment variable runtime-mutable; classify mutable vs restart-required vs bootstrap-only.
- Unknown/missing provider evidence remains `UNKNOWN`.
- Initial chains remain Solana + BNB + Robinhood through the existing chain-neutral architecture.

---

### Task 1: Backend/frontend parity inventory

**Files:** inspect runtime Settings, control plane, read APIs, web read types and every route listed in the spec; update `docs/STATUS.md`.

- [ ] Map each backend runtime setting/capability to current API + UI support.
- [ ] Record `PRESENT`, `READ_ONLY`, `MISSING_API`, `MISSING_UI`, `PROTECTED`, or `BOOTSTRAP_ONLY`.
- [ ] Map every frontend route to its backend data sources and stale/missing fields.
- [ ] Preserve existing production-readiness blocker/task state; add this UI sprint as the next local unblocked engineering work.
- [ ] Commit inventory checkpoint.

### Task 2: Runtime settings registry

**Files:** extend existing application config/control modules; add focused tests.

- [ ] Write failing tests for metadata fields: type/category/mutable/secret/restart-required/decision-affecting/constraints.
- [ ] Add definitions for existing General, Chains, Market, Social, Telegram notification, Wallet, Security, Narrative and Alert/Decision runtime fields.
- [ ] Mark protected modes immutable and bootstrap-only fields correctly.
- [ ] Ensure secret definitions never expose effective values.
- [ ] Run focused tests + lint/typecheck; update STATUS; commit.

### Task 3: Versioned settings read/mutation API

**Files:** extend existing `/v1/control` routes/service/persistence; matching API/control tests.

- [ ] Add safe schema/effective-state read contract.
- [ ] Add ADMIN-only partial mutation with reason, validation, version/hash/audit.
- [ ] Return restart-required state where applicable; never claim non-applied settings are effective.
- [ ] Add write-only secret replace/clear semantics and redacted audit payloads.
- [ ] Reject protected modes and unknown keys fail-closed.
- [ ] Run focused API/persistence/auth tests, migrations only if persistence changes, then lint/typecheck; commit.

### Task 4: Telegram/X/social capability completion

**Files:** reuse existing provider/social settings seam and registry.

- [ ] Separate Telegram notification configuration from Telegram/social ingestion capability.
- [ ] If compliant X/Telegram ingestion adapter configuration is already present, expose it through the registry; if missing, add only provider-neutral optional configuration required by the existing social/caller adapter boundary.
- [ ] Do not put raw MTProto/X SDK logic in domain/application code.
- [ ] Add tests for configured/unconfigured/degraded states and secret masking.
- [ ] Commit.

### Task 5: Safe provider connection test

**Files:** control/provider application + API + tests.

- [ ] Add bounded read-only provider test operation for supported provider settings.
- [ ] Require authorization, timeout, redacted diagnostics and audit event.
- [ ] Never reveal request credentials or secret-bearing URLs.
- [ ] Return exact state such as READY/DEGRADED/RATE_LIMITED/CONFIGURATION_MISSING/BLOCKED_EXTERNAL.
- [ ] Commit after focused tests.

### Task 6: Settings frontend workspace

**Files:** replace/extend current settings page/components/read-api types and tests.

- [ ] Render categories from backend schema rather than six hard-coded fields.
- [ ] Show effective/source/mutable/restart-required/decision-affecting metadata.
- [ ] Show secrets only as `CONFIGURED` / `NOT CONFIGURED`; support replace/clear without reading secret value.
- [ ] ADMIN gets validated edit flow + required reason; VIEWER stays read-only.
- [ ] Protected modes remain separate locked panel.
- [ ] Show version/hash/audit link and success/error/restart-required feedback.
- [ ] Run Vitest/lint/typecheck/build; commit.

### Task 7: Providers page parity

**Files:** providers page/components/read-api/API only if missing safe projection.

- [ ] Keep configuration editing in Settings.
- [ ] Show configured state, health, latency, freshness, quota, last success/error and fallback where available.
- [ ] Add `Test connection` and `Open settings` actions when supported.
- [ ] Ensure missing health never renders as healthy.
- [ ] Test desktop/mobile states; commit.

### Task 8: Shell + universal search

**Files:** shell/search components + backend resolver/read route if needed + tests.

- [ ] Replace `SOLANA INTELLIGENCE` with chain-neutral product language.
- [ ] Add compact chain/provider readiness only from real read state.
- [ ] Replace browser-only Solana regex routing with canonical resolver/search path.
- [ ] Support token UUID, Solana/EVM address, caller identity and ambiguous symbol/name results without guessing.
- [ ] Add tests for Solana, EVM, caller and ambiguous cases; commit.

### Task 9: Intelligence route parity

**Routes:** `/`, `/radar`, `/ultra-early`, `/tokens/[id]`.

- [ ] Compare backend projections to rendered fields; add missing chain, caller/smart-money, risk, freshness, provenance, liquidity/executable context.
- [ ] Remove stale/mock-only data.
- [ ] Add useful chain/status/filter/sort controls without duplicating scoring in browser.
- [ ] Ensure synthetic/insufficient evidence cannot look production-proven.
- [ ] Focused tests + responsive review; commit.

### Task 10: Research route parity

**Routes:** `/positions`, `/wallets`, `/wallets/[address]`, `/callers`, `/wallet-graph`.

- [ ] Add chain/status/evidence filters where backend supports them.
- [ ] Positions clearly distinguish paper/shadow and reference vs executable metrics.
- [ ] Wallet views expose smart-money/cluster/cross-chain evidence without asserting weak links.
- [ ] Callers add source/chain/evidence/sample/confidence/hit-rate/rug filters/sort and detailed historical/conduct/linkage evidence.
- [ ] Preserve graph usability and cross-links.
- [ ] Tests + responsive review; commit.

### Task 11: System route parity

**Routes:** `/operations`, `/audit`.

- [ ] Operations: API/worker/DB/Redis/provider/stream/social/Telegram/shadow state, lag/backlog/freshness/errors and restart-required config state where available.
- [ ] Audit: filters for config mutations/provider tests/kill switches/actor/correlation ID; secrets always redacted.
- [ ] Tests; commit.

### Task 12: Production readiness/research surfaces

**Files:** add `/readiness`; add `/research` only if canonical backend projection can be cleanly exposed.

- [ ] Build backend read projection from canonical production gate state, not Markdown parsing in browser.
- [ ] Show PR-1..PR-7 state/evidence/blockers and protected modes.
- [ ] If research report projection is available, show ablation/sample adequacy/no-lookahead/promotion state without recalculating in frontend.
- [ ] Add nav entries only when routes are backed by real APIs.
- [ ] Tests; commit.

### Task 13: UI consistency and density cleanup

**Files:** shared components/CSS only where needed.

- [ ] Normalize page headings, status badges, empty/error states, cards/tables/forms and spacing.
- [ ] Reduce repeated safety/boundary blocks when persistent shell status already conveys the invariant, without hiding critical warnings.
- [ ] Ensure tables use contained scrolling/sticky headers or mobile cards as appropriate.
- [ ] No horizontal page overflow at supported viewports.
- [ ] Commit after frontend gates.

### Task 14: Full browser acceptance

- [ ] Exercise every route in the spec at 1440x900, 1280x800, 1024x768, 768x1024, 390x844.
- [ ] Test loading, empty, unauthorized, invalid, degraded, UNKNOWN and mutation success/failure/restart-required states.
- [ ] Test keyboard navigation, labels, focus behavior and mobile nav.
- [ ] Ensure no secret values appear in DOM/test snapshots/logs.
- [ ] Fix all P0/P1 visual/functionality defects found.
- [ ] Run full Vitest/Playwright/lint/typecheck/build; commit.

### Task 15: Final backend/frontend acceptance

- [ ] Run focused backend control/provider/settings tests.
- [ ] Run migrations if changed, security/secret scans and `git diff --check`.
- [ ] Run `make verify` and all web gates.
- [ ] Verify all protected modes unchanged.
- [ ] Reconcile `docs/STATUS.md`, frontend docs and production-readiness docs without falsely changing `NOT_PRODUCTION_READY` unless real-data gates independently changed.
- [ ] Record route parity matrix, exact tests, remaining external blockers and next task.
- [ ] Commit/push coherent final checkpoint; preserve unrelated WIP.
