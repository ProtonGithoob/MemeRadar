# Phase 2 / Sprint 2.2 Helius Solana Read Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a key-safe Helius/RPC read adapter that normalizes token authorities, token programs, accounts and transaction identities, with webhook/WebSocket seams, fixture contracts and an honest provider doctor.

**Architecture:** `HeliusRpcAdapter` implements the application `OnChainPort` and owns only transport/auth/payload mapping. It returns normalized `Observation` values plus typed token/transaction records; domain code remains unaware of Helius or JSON-RPC response types. Stream/webhook normalization is an independent provider seam using the same provenance/timestamp rules. The doctor performs one bounded read-only health call only when configuration is present and reports `PASS`, `BLOCKED_EXTERNAL` or `FAIL` without printing secrets.

**Tech Stack:** Python 3.12, asyncio, httpx, existing provider transport/health/fixture primitives, `memeradar_domain` value objects, pytest, Ruff and mypy.

**Spec:** `docs/PROVIDERS.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TESTING.md` and `docs/ROADMAP.md`.

## Global Constraints

- Helius/RPC is a replaceable read-only adapter; provider SDK/JSON-RPC payloads never enter the domain layer.
- Every request uses bounded timeout, retry, rate-limit and circuit policy from `memeradar_providers.transport`.
- API keys are read from configuration only, never included in logs, fixture files, exceptions or command output.
- Invalid/missing authorities and malformed provider data become `UNKNOWN`/`INVALID`, never implicit SAFE evidence.
- Every normalized observation includes provider/source/parser provenance and ordered timestamps.
- Webhook/WebSocket inputs are untrusted data; no payload instruction can trigger execution or configuration mutation.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` remain enforced.

---

### Task 1: Typed Helius normalization and read adapter contract

**Files:**
- Create: `packages/providers/src/memeradar_providers/helius.py`
- Test: `tests/unit/test_helius_normalization.py`

**Interfaces:**
- `AuthorityState`, `NormalizedTokenProgram`, `NormalizedAuthority`, `HeliusTokenMetadata` and `HeliusTransaction` are immutable provider-neutral records.
- `HeliusRpcAdapter(endpoint, api_key=None, client=None, transport=None, clock=None)` implements `OnChainPort.enrich` and exposes bounded `fetch_token_metadata`, `fetch_account`, and `fetch_transaction` reads.
- JSON-RPC status/auth/rate-limit/schema failures map to the existing classified provider errors and raw response text is not retained.

- [ ] **Step 1: Write failing tests** for authority null/missing/valid normalization, SPL/Token-2022/unknown program mapping, transaction identity, malformed responses and safe endpoint/key handling.
- [ ] **Step 2: Run the focused tests and confirm the adapter module is absent.**
- [ ] **Step 3: Implement normalization records and injected-client JSON-RPC adapter using `ProviderTransport`.**
- [ ] **Step 4: Run focused tests, Ruff and mypy.**
- [ ] **Step 5: Commit `feat: add Helius Solana read adapter`.**

### Task 2: Webhook and WebSocket observation seam

**Files:**
- Create: `packages/providers/src/memeradar_providers/helius_stream.py`
- Modify: `packages/application/src/memeradar_application/provider_contracts.py` if a stream protocol is needed by the adapter boundary
- Test: `tests/unit/test_helius_stream.py`

**Interfaces:**
- `HeliusObservationNormalizer` maps untrusted webhook/stream envelopes to normalized `Observation` values with source IDs, parser version, quality state and ordered timestamps.
- `HeliusStreamConsumer` consumes an injected async message source, supports cancellation and bounded reconnect delay, and never invokes execution code.
- Duplicate source IDs remain replayable/idempotent; malformed messages become classified schema failures or INVALID observations.

- [ ] **Step 1: Write failing stream/webhook normalization, duplicate, malformed-payload and cancellation tests.**
- [ ] **Step 2: Run the focused tests and verify missing stream symbols fail.**
- [ ] **Step 3: Implement the injected source/sink seam and normalization/reconnect behavior.**
- [ ] **Step 4: Run focused tests, Ruff and mypy.**
- [ ] **Step 5: Commit `feat: add Helius observation stream seam`.**

### Task 3: Safe Helius fixtures and provider contract tests

**Files:**
- Create: `fixtures/providers/helius/get_asset_token.json`
- Create: `fixtures/providers/helius/get_account_info.json`
- Create: `fixtures/providers/helius/get_transaction.json`
- Create: `tests/contract/test_helius_provider.py`
- Modify: `fixtures/providers/README.md`

- [ ] **Step 1: Add synthetic/redacted JSON-RPC responses with no credential-shaped values.**
- [ ] **Step 2: Write fixture contract tests** for token/account/transaction reads and normalized outputs.
- [ ] **Step 3: Run the tests and secret scan; confirm fixture exports are deterministic and safe.**
- [ ] **Step 4: Run Ruff and mypy over the adapter and contract tests.**
- [ ] **Step 5: Commit `test: add Helius read fixtures`.**

### Task 4: Key-safe provider doctor

**Files:**
- Create: `scripts/provider_doctor.py`
- Modify: `Makefile`
- Modify: `.env.example`
- Test: `tests/unit/test_provider_doctor.py`

**Interfaces:**
- `provider_doctor.py` reads `HELIUS_RPC_URL`/`HELIUS_API_KEY` without echoing values, performs one bounded `getHealth` read-only call when configured, and emits deterministic redacted JSON.
- Missing configuration or unavailable external access is reported as `BLOCKED_EXTERNAL`; malformed/auth/schema responses are `FAIL`; observed successful health/schema evidence is `PASS`.
- The doctor never mutates chain state and never changes operating modes.

- [ ] **Step 1: Write failing doctor tests** for missing configuration, successful fixture response, auth failure, timeout and secret non-disclosure.
- [ ] **Step 2: Run focused tests and verify the command/module is absent.**
- [ ] **Step 3: Implement the doctor with injectable adapter/client and safe report serialization.**
- [ ] **Step 4: Add `make provider-doctor`, update safe environment examples and run keyless doctor tests.**
- [ ] **Step 5: Commit `feat: add Helius provider doctor`.**

### Task 5: Sprint 2.2 gate and live-acceptance boundary

**Files:**
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-2-helius-solana-read-layer.md`

- [ ] **Step 1: Add runtime import and safety-mode smoke checks for the Helius adapter/doctor.**
- [ ] **Step 2: Run `make verify`, Helius unit/contract tests, secret scan, provider doctor and Compose runtime imports.**
- [ ] **Step 3: If configured live read-only access is absent, record exactly `BLOCKED_EXTERNAL`; never substitute fixture PASS for live PASS.**
- [ ] **Step 4: Reconcile all Sprint 2.2 checkboxes/status with exact results, blockers, provider acceptance and safety modes.**
- [ ] **Step 5: Commit and push the sprint checkpoint; record the exact next task `Phase 2 / Sprint 2.3 — Birdeye / DEX Market Layer`.**
