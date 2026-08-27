# Phase 2 / Sprint 2.4 Launchpad and DEX Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add keyless, protocol-isolated Solana launchpad/DEX event adapters for Pump.fun, PumpSwap, Raydium and Meteora, canonical identity/deduplication utilities, and a protected manual mint-submission API.

**Architecture:** Protocol adapters accept only injected, untrusted event envelopes and normalize them into application `DiscoveryCandidate` values carrying canonical `TokenIdentity`/`PoolIdentity`, timestamps and provenance. A provider-package identity mapper and duplicate detector preserve source evidence without dropping duplicate deliveries. The API delegates manual mint validation to a provider-independent application service and requires a configured operator bearer token; it creates analysis candidates only and has no execution or network side effect.

**Tech Stack:** Python 3.12, existing stdlib/domain/application/FastAPI/Pydantic dependencies, pytest, httpx, Ruff, mypy and synthetic JSON fixtures. No protocol SDK or live credential is required.

**Spec:** `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DATA_MODEL.md`, `docs/PROVIDERS.md`, `docs/SECURITY.md` and `docs/TESTING.md`.

## Global Constraints

- Protocol payloads are untrusted and remain inside `packages/providers`; domain/application code receives only normalized contracts.
- Every normalized candidate preserves canonical Solana addresses, provider/protocol provenance, parser version, source identity and ordered occurred/observed/ingested timestamps.
- Missing or malformed mint/pool identity is rejected as a classified schema error; it is never treated as safe evidence.
- Duplicate protocol deliveries are reported with canonical token/pool keys and prior source IDs, not silently discarded.
- Manual submission is authenticated, bounded and analysis-only; it never signs, submits or enables a transaction.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false` remain enforced.
- No API token, wallet secret, provider credential or raw authorization header may appear in fixtures, logs, exceptions, API responses or commits.
- Live protocol/provider acceptance is optional and must be recorded as `BLOCKED_EXTERNAL` when credentials or network access are unavailable.

---

### Task 1: Protocol event parsers and adapters

**Files:**
- Create: `packages/providers/src/memeradar_providers/launchpad_dex.py`
- Test: `tests/unit/test_launchpad_dex.py`

**Interfaces:**
- `ProtocolVenue` exposes `PUMP_FUN = "pump.fun"`, `PUMP_SWAP = "pumpswap"`, `RAYDIUM = "raydium"` and `METEORA = "meteora"`.
- `ParsedProtocolEvent` stores the normalized venue, allow-listed event type, mint/pool/quote addresses, token program, source ID, payload and ordered timestamps before canonical object mapping.
- `LaunchpadDexAdapter(venue)` exposes `parse(message, context) -> ParsedProtocolEvent` and `normalize(message, context) -> DiscoveryCandidate`.
- `PumpFunAdapter`, `PumpSwapAdapter`, `RaydiumAdapter` and `MeteoraAdapter` specialize the adapter with per-venue event allow-lists and parser version `launchpad-dex-v1`.

- [ ] **Step 1: Write failing parser tests** for one synthetic create/pool event per venue, accepted field aliases, deterministic source IDs, timestamp ordering, unsupported event types, malformed/non-Solana addresses and credential-shaped payload rejection.
- [ ] **Step 2: Run the focused parser tests and confirm the launchpad/DEX module and adapter symbols are absent.**
- [ ] **Step 3: Implement a provider-local parser** that accepts an envelope with `type`/`event_type`, optional `signature`/`event_id`, and a `data` mapping; validates an allow-listed event type; extracts mint, optional pool, quote and token-program aliases; redacts credential-shaped payload values; and emits `ParsedProtocolEvent` with `Provenance`-ready timestamps.
- [ ] **Step 4: Add venue-specific adapter classes** with no SDK imports and make `normalize` use the canonical mapper interface defined in Task 2.
- [ ] **Step 5: Run focused tests, Ruff and configured mypy; commit `feat: add launchpad and DEX event adapters`.**

### Task 2: Canonical token/pool mapping and duplicate detection

**Files:**
- Modify: `packages/providers/src/memeradar_providers/launchpad_dex.py`
- Test: `tests/unit/test_launchpad_dex_identity.py`

**Interfaces:**
- `CanonicalIdentityMapper.token(mint_address, token_program="spl-token") -> TokenIdentity` deterministically maps one canonical mint to one UUID.
- `CanonicalIdentityMapper.pool(token, venue, pool_address, quote_mint) -> PoolIdentity` deterministically maps one canonical pool address/venue/quote tuple to one UUID.
- `CanonicalIdentityMapper.candidate(parsed_event) -> DiscoveryCandidate` attaches the optional pool and protocol provenance while preserving source/timestamps.
- `DuplicateResult` contains `is_duplicate`, `duplicate_keys` and ordered `prior_source_ids`.
- `CanonicalDuplicateDetector.inspect(candidate) -> DuplicateResult` is read-only; `record(candidate) -> DuplicateResult` records canonical token and optional pool keys while retaining duplicate deliveries for downstream idempotency.

- [ ] **Step 1: Write failing identity tests** for stable IDs across parser instances, token/pool relationship validation, venue normalization, same-token/different-source duplicates, same-pool duplicates, distinct-pool non-collision and source-order preservation.
- [ ] **Step 2: Run the focused identity tests and confirm the mapper/detector symbols are absent.**
- [ ] **Step 3: Implement deterministic UUID5 mapping** under a repository-owned namespace; require canonical Solana addresses and complete pool quote identity; return normalized `DiscoveryCandidate` values with protocol/provider/parser provenance.
- [ ] **Step 4: Implement duplicate inspection/recording** keyed by canonical mint and pool address, returning prior source IDs without filtering or mutating the candidate.
- [ ] **Step 5: Run parser plus identity tests, Ruff and configured mypy; commit `feat: add canonical launchpad identities`.**

### Task 3: Protected manual mint-submission API

**Files:**
- Create: `packages/application/src/memeradar_application/manual_submission.py`
- Create: `apps/api/src/memeradar_api/manual.py`
- Modify: `packages/application/src/memeradar_application/config.py`
- Modify: `apps/api/src/memeradar_api/main.py`
- Modify: `.env.example`
- Test: `tests/unit/test_manual_submission.py`
- Test: `tests/unit/test_manual_api.py`

**Interfaces:**
- `ManualMintRequest(context, mint_address, token_program="spl-token")` is a validated application request.
- `ManualMintSubmissionService.submit(request) -> ManualMintResult` returns a deterministic, provider-independent `DiscoveryCandidate` plus an in-process duplicate flag; repeated submissions retain the same `manual:<mint>` source identity.
- `build_manual_router(settings, service=None) -> APIRouter` exposes `POST /v1/manual/mints`; it requires `Authorization: Bearer <OPERATOR_API_TOKEN>` when configured and returns `503` when operator authentication is not configured.
- The request accepts `mint` or `mint_address`; the response contains only canonical mint, token UUID, source ID, duplicate flag, provider and `execution_enabled: false`.

- [ ] **Step 1: Write failing service/API tests** for canonical mint acceptance, invalid/oversized mint rejection, deterministic duplicate behavior, missing-token `503`, wrong-token `401`, valid-token `200`, correlation propagation, extra-field rejection and no secret echo.
- [ ] **Step 2: Run focused tests and confirm the manual submission module/route is absent.**
- [ ] **Step 3: Implement `ManualMintSubmissionService`** with deterministic UUID5 token identity, `manual` provenance, bounded context timestamps and no provider/network dependency.
- [ ] **Step 4: Add the authenticated FastAPI router**, optional `OPERATOR_API_TOKEN` configuration presence handling, request/response Pydantic schemas and composition-root wiring; leave all four safety modes enforced by `Settings.from_env`.
- [ ] **Step 5: Run focused tests, API tests, Ruff and configured mypy; commit `feat: add protected manual mint submission`.**

### Task 4: Protocol fixtures and contract coverage

**Files:**
- Create: `fixtures/providers/launchpad_dex/README.md`
- Create: `fixtures/providers/launchpad_dex/pump_fun_create.json`
- Create: `fixtures/providers/launchpad_dex/pumpswap_pool_created.json`
- Create: `fixtures/providers/launchpad_dex/raydium_pool_created.json`
- Create: `fixtures/providers/launchpad_dex/meteora_pool_created.json`
- Create: `tests/contract/test_launchpad_dex_provider.py`
- Modify: `fixtures/providers/README.md`

**Interfaces:**
- Fixtures use a synthetic `launchpad-dex-v1` envelope with public-looking but synthetic canonical Solana addresses, no credential-shaped values and metadata marked `redacted: true`.
- Contract tests replay all four fixtures through their concrete adapter and assert identical canonical identity/provenance/timestamp behavior across repeated reads.

- [ ] **Step 1: Add safe synthetic protocol envelopes and metadata** for Pump.fun create, PumpSwap pool creation, Raydium pool creation and Meteora pool creation.
- [ ] **Step 2: Write contract tests** for all adapters, pool/token linkage, duplicate detection and deterministic replay.
- [ ] **Step 3: Run contract tests and secret scan; verify no fixture/API token leakage.**
- [ ] **Step 4: Commit `test: add launchpad and DEX fixtures`.**

### Task 5: Sprint 2.4 gate, documentation and synchronization

**Files:**
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-4-launchpad-dex-coverage.md`

- [ ] **Step 1: Add runtime smoke checks** for all four protocol adapters, canonical duplicate detection, manual router composition and protected mode configuration.
- [ ] **Step 2: Run `make verify`, focused protocol/API/contract tests, secret scan, `make doctor`, and Compose API/worker runtime imports.**
- [ ] **Step 3: Record live protocol acceptance as `BLOCKED_EXTERNAL` unless an actual configured read-only provider check succeeds; never substitute fixtures for live evidence.**
- [ ] **Step 4: Reconcile Sprint 2.4 roadmap checkboxes, provider documentation, plan checkboxes, exact verification evidence, blockers, safety modes, provider acceptance and Git state.**
- [ ] **Step 5: Commit and push the Sprint 2.4 checkpoint; record the exact next task `Phase 2 / Gate P2 — Read-only discovery and independent enrichment acceptance`.**
