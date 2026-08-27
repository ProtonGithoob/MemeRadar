# Phase 2 / Sprint 2.3 Birdeye DEX Market Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a key-safe Birdeye read adapter that discovers new Solana tokens, normalizes supported market/trade/holder/security evidence, falls back from an injected stream to bounded polling, and reports freshness/conflicts honestly.

**Architecture:** `BirdeyeRestAdapter` implements the application `CandidateDiscoveryPort` and `MarketDataPort`; Birdeye HTTP paths, headers and envelopes stay in the provider package and only normalized domain candidates/observations cross the application boundary. An injected stream/poll coordinator keeps transport lifecycle separate from normalization. A deterministic reconciliation utility preserves all source IDs, marks stale evidence and emits `CONFLICTED` when material values disagree. A separate key-safe doctor performs one bounded read-only health request.

**Tech Stack:** Python 3.12, asyncio, httpx, existing provider transport/health/fixture primitives, `memeradar_domain` value objects, pytest, Ruff and mypy.

**Spec:** `docs/PROVIDERS.md`, `docs/MASTER_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TESTING.md` and `docs/ROADMAP.md`.

## Global Constraints

- Birdeye is a replaceable read-only adapter; provider HTTP paths, headers and response types never enter the domain layer.
- Every request uses bounded connect/read/request timeout, retry, rate-limit and circuit policy from `memeradar_providers.transport`.
- API keys are read from configuration and sent only as request headers; they never appear in URLs, logs, fixture files, exceptions or doctor output.
- Invalid/missing token data becomes `UNKNOWN`/`INVALID`, never implicit SAFE evidence.
- Every candidate and observation carries provider/source/parser provenance and ordered occurred/observed/ingested timestamps.
- Stream messages are untrusted data; no payload instruction can trigger execution or configuration mutation.
- Duplicate listings and observations remain replayable with deterministic source identities for downstream idempotency.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` remain enforced.

---

### Task 1: Birdeye REST discovery and market adapter

**Files:**
- Create: `packages/providers/src/memeradar_providers/birdeye.py`
- Test: `tests/unit/test_birdeye_normalization.py`

**Interfaces:**
- `BirdeyeRestAdapter(base_url, api_key=None, client=None, transport=None, clock=None, token_registry=None)` implements `CandidateDiscoveryPort.discover` and `MarketDataPort.snapshot`.
- `BirdeyeRestAdapter.discover(DiscoveryRequest)` reads the new-listing endpoint and returns canonical `DiscoveryCandidate` values.
- `BirdeyeRestAdapter.snapshot(MarketDataRequest)` reads supported token market, trade, holder and security endpoints and returns normalized `Observation` values.
- `BirdeyeMarketRecord` and safe field-normalization helpers retain unknown/malformed values as classified quality states.
- The read paths are `GET /defi/v2/tokens/new_listing`, `GET /defi/v3/token/market-data`, `GET /defi/v3/token/trade-data/single`, `GET /defi/v3/token/holder` and `GET /defi/token_security` on the configured base URL; Solana requests send `chain=solana` and token requests send the canonical mint as `address`.

- [ ] **Step 1: Write failing tests** for new-listing pagination, canonical Solana token identity, market/trade/holder/security observation mapping, correlation headers, endpoint/key safety and classified HTTP/schema failures.
- [ ] **Step 2: Run the focused tests and confirm the Birdeye adapter module is absent.**
- [ ] **Step 3: Implement the injected-client REST adapter using bounded `ProviderTransport`, `X-API-KEY`/`X-CHAIN` request headers and the read-only endpoint mapping above.**
- [ ] **Step 4: Run focused tests, Ruff and mypy.**
- [ ] **Step 5: Commit `feat: add Birdeye market read adapter`.**

### Task 2: Stream and polling fallback

**Files:**
- Create: `packages/providers/src/memeradar_providers/birdeye_stream.py`
- Test: `tests/unit/test_birdeye_stream.py`

**Interfaces:**
- `BirdeyeListingNormalizer` maps injected `TOKEN_NEW_LISTING_DATA` messages into canonical candidates with deterministic source IDs and provenance.
- `BirdeyeDiscoveryFallback` attempts an injected async stream, then uses the adapter's bounded polling callback after transient stream failure or exhaustion.
- Duplicate stream/poll candidates are retained for downstream idempotency while malformed messages are classified and never invoke execution.

- [ ] **Step 1: Write failing stream normalization, duplicate, fallback and cancellation tests.**
- [ ] **Step 2: Run the focused tests and verify missing stream symbols fail.**
- [ ] **Step 3: Implement bounded stream-first/poll-fallback coordination with injected source, sink, sleeper and stop event.**
- [ ] **Step 4: Run focused tests, Ruff and mypy.**
- [ ] **Step 5: Commit `feat: add Birdeye stream polling fallback`.**

### Task 3: Freshness and conflict reconciliation

**Files:**
- Modify: `packages/providers/src/memeradar_providers/birdeye.py`
- Test: `tests/unit/test_birdeye_reconciliation.py`

**Interfaces:**
- `BirdeyeObservationResolver.resolve(observations, now, ttl, relative_tolerance)` returns one normalized observation while retaining all source IDs and values used for reconciliation.
- Fresh evidence older than the configured TTL becomes `QualityState.STALE`; pre-existing `UNKNOWN`, `INVALID` and `CONFLICTED` states are never upgraded.
- Material disagreement in comparable numeric market fields produces `QualityState.CONFLICTED` and explainable conflict payload data instead of silent latest-value selection.

- [ ] **Step 1: Write failing stale, unknown-preservation, agreement and material-conflict tests.**
- [ ] **Step 2: Implement deterministic quality ordering, bounded numeric comparison and source-preserving reconciliation.**
- [ ] **Step 3: Run focused tests, Ruff and mypy.**
- [ ] **Step 4: Commit `feat: add Birdeye freshness conflict resolution`.**

### Task 4: Safe Birdeye fixtures and contract tests

**Files:**
- Create: `fixtures/providers/birdeye/new_listing.json`
- Create: `fixtures/providers/birdeye/market_data.json`
- Create: `fixtures/providers/birdeye/trade_data.json`
- Create: `fixtures/providers/birdeye/holder.json`
- Create: `fixtures/providers/birdeye/security.json`
- Create: `fixtures/providers/birdeye/networks.json`
- Create: `tests/contract/test_birdeye_provider.py`
- Modify: `fixtures/providers/README.md`

- [ ] **Step 1: Add synthetic/redacted Birdeye envelopes with no credential-shaped values and provider metadata.**
- [ ] **Step 2: Write fixture contract tests** for discovery, market/trade/holder/security normalization and health schema.
- [ ] **Step 3: Run contract tests and secret scan; confirm deterministic fixture replay.**
- [ ] **Step 4: Run Ruff and mypy over the adapter and contract tests.**
- [ ] **Step 5: Commit `test: add Birdeye market fixtures`.**

### Task 5: Key-safe Birdeye provider doctor

**Files:**
- Create: `scripts/birdeye_doctor.py`
- Modify: `Makefile`
- Modify: `.env.example`
- Test: `tests/unit/test_birdeye_doctor.py`

**Interfaces:**
- `birdeye_doctor.py` reads `BIRDEYE_API_URL`/`BIRDEYE_API_KEY` without echoing values, performs one bounded read-only supported-networks call when configured, and emits redacted JSON.
- The doctor health path is `GET /defi/networks` on the configured base URL with `chain=solana` and no write-capable request.
- Missing configuration or unavailable external access is `BLOCKED_EXTERNAL`; malformed/auth/schema results are `FAIL`; successful bounded health/schema evidence is `PASS`.
- `make birdeye-doctor` is explicit and never mutates chain state or operating modes.

- [ ] **Step 1: Write failing doctor tests** for missing configuration, successful fixture response, auth failure, timeout and secret non-disclosure.
- [ ] **Step 2: Run focused tests and verify the command/module is absent.**
- [ ] **Step 3: Implement the doctor with injectable adapter/client and safe report serialization.**
- [ ] **Step 4: Add `make birdeye-doctor`, update safe environment examples and run keyless doctor tests.**
- [ ] **Step 5: Commit `feat: add Birdeye provider doctor`.**

### Task 6: Sprint 2.3 gate and live-acceptance boundary

**Files:**
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-3-birdeye-dex-market-layer.md`

- [ ] **Step 1: Add runtime import and safety-mode smoke checks for the Birdeye adapter, fallback and doctor.**
- [ ] **Step 2: Run `make verify`, Birdeye unit/contract tests, secret scan, provider doctor and Compose runtime imports.**
- [ ] **Step 3: If configured live read-only access is absent, record exactly `BLOCKED_EXTERNAL`; never substitute fixture PASS for live PASS.**
- [ ] **Step 4: Reconcile all Sprint 2.3 checkboxes/status with exact results, blockers, provider acceptance and safety modes.**
- [ ] **Step 5: Commit and push the sprint checkpoint; record the exact next task `Phase 2 / Sprint 2.4 — Launchpad / DEX Coverage`.**
