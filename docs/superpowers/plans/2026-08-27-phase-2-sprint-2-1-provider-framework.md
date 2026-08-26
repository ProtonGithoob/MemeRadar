# Phase 2 / Sprint 2.1 Provider Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish provider-independent ports, resilient transport policies, health/freshness/quota models and safe keyless fixtures/fakes for every provider capability named in `docs/PROVIDERS.md`.

**Architecture:** Application-facing protocols live in `packages/application` and expose normalized domain-facing values without importing provider SDKs. Reusable transport, health and fixture infrastructure lives in `packages/providers`; it accepts injected clocks/sleep/randomness so timeout, retry, rate-limit and circuit-breaker behavior is deterministic and keyless-testable. No real provider adapter or execution side effect is enabled in this sprint.

**Tech Stack:** Python 3.12, asyncio, dataclasses/typing Protocol, existing `memeradar_domain` value objects, pytest, Ruff and mypy.

**Spec:** `docs/PROVIDERS.md`, with boundaries from `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TESTING.md` and `docs/ROADMAP.md`.

## Global Constraints

- Provider adapters are replaceable and domain code never imports provider response types or SDKs.
- Every network operation has explicit timeout, bounded retry, jitter, rate-limit and circuit-breaker policy.
- Provider health distinguishes `HEALTHY`, `DEGRADED`, `DOWN` and `UNKNOWN`; missing/stale critical evidence never becomes safe evidence.
- Fixtures are committed only after recursive secret redaction and carry provider, capability, endpoint, capture date, parser/schema version and redaction metadata.
- LLM output remains advisory and execution/transaction signing remains outside this sprint.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` remain enforced.

---

### Task 1: Application provider ports and normalized request/result contracts

**Files:**
- Create: `packages/application/src/memeradar_application/provider_contracts.py`
- Modify: `packages/application/src/memeradar_application/__init__.py` only if exports do not trigger standalone doctor imports
- Test: `tests/unit/test_provider_contracts.py`

**Interfaces:**
- Define `ProviderCapability`, `ProviderRequestContext`, `DiscoveryRequest`, `MarketDataRequest`, `OnChainRequest`, `RiskDataRequest`, `SocialDataRequest`, `NarrativeInput`, `QuoteRequest`, `ExecutionRequest` and typed normalized result records.
- Define `CandidateDiscoveryPort`, `MarketDataPort`, `OnChainPort`, `RiskDataPort`, `SocialDataPort`, `NarrativePort`, `QuotePort`, `ExecutionPort` and `NotificationPort` as async application-facing protocols.
- Normalized read results carry `Observation`/`Provenance` or typed immutable records with source IDs and ordered timestamps; quote/execution records contain no signing secret.

- [x] **Step 1: Write failing contract tests** for all nine ports, request bounds, normalized observation provenance and safe quote/execution result fields.
- [x] **Step 2: Run `pytest tests/unit/test_provider_contracts.py -q` and confirm the missing-module failure.**
- [x] **Step 3: Implement the immutable request/result records and async `Protocol` signatures.**
- [x] **Step 4: Run the focused tests, Ruff and mypy.**
- [x] **Step 5: Commit `feat: define provider application ports`.**

### Task 2: Deterministic transport resilience primitives

**Files:**
- Create: `packages/providers/src/memeradar_providers/transport.py`
- Modify: `pyproject.toml`, `tests/conftest.py`
- Test: `tests/unit/test_provider_transport.py`

**Interfaces:**
- `TransportTimeouts` validates bounded connect/read/write/websocket idle/overall timeout values.
- `RetryPolicy` calculates bounded exponential delay with injected jitter and classifies retryable failures; authentication/schema failures are never retried.
- `RateLimitSnapshot` and `RateLimiter` enforce `retry_after`/reset timing without retry storms.
- `CircuitBreaker` implements closed/open/half-open transitions with a failure threshold and recovery window.
- `ProviderTransport.execute(operation, ...)` composes timeout, rate-limit, retry and circuit behavior around an async callback.

- [x] **Step 1: Write failing tests** for timeout validation, retryable vs non-retryable errors, bounded jitter, rate-limit waiting, circuit opening/recovery and cancellation propagation.
- [x] **Step 2: Run the focused transport tests and verify the expected missing-symbol failures.**
- [x] **Step 3: Implement the smallest callback-based asyncio primitives with injected clock/sleeper/random source.**
- [x] **Step 4: Run focused tests plus Ruff/mypy and add no HTTP/WebSocket SDK coupling.**
- [x] **Step 5: Commit `feat: add provider transport resilience`.**

### Task 3: Provider health, quota and freshness model

**Files:**
- Create: `packages/providers/src/memeradar_providers/health.py`
- Test: `tests/unit/test_provider_health.py`

**Interfaces:**
- `ProviderHealthState`, `ProviderQuota`, `ProviderFreshness` and `ProviderHealth` are immutable, validated records.
- Health records preserve provider/capability, check time, bounded latency, redacted error class, quota/reset metadata and domain `QualityState` freshness.
- `ProviderHealthTracker` records successes/failures and computes health without treating missing data as healthy.

- [x] **Step 1: Write failing tests** for health-state transitions, unknown/stale freshness, quota reset, latency bounds and error-class redaction.
- [x] **Step 2: Run the focused tests and verify they fail because the model is absent.**
- [x] **Step 3: Implement validated health/quota/freshness records and an in-memory tracker.**
- [x] **Step 4: Run focused tests, Ruff and mypy.**
- [x] **Step 5: Commit `feat: model provider health and freshness`.**

### Task 4: Safe fixture recorder, redactor and fake provider seam

**Files:**
- Create: `packages/providers/src/memeradar_providers/fixtures.py`
- Create: `fixtures/providers/README.md`
- Test: `tests/unit/test_provider_fixtures.py`
- Test: `tests/contract/test_provider_adapters.py`

**Interfaces:**
- `FixtureMetadata` and `FixtureRecord` carry provider, capability, endpoint, capture time, schema/parser versions and `redacted=true`.
- `FixtureRedactor` recursively redacts credential-shaped keys and sensitive URL/header text before storage/export.
- `FixtureRecorder` records only redacted immutable payloads and exports deterministic JSON.
- `FakeProvider` returns configured normalized fixtures or typed failures and records bounded calls for contract tests.
- Contract fixtures prove fake adapter outputs preserve canonical identities, provenance, timestamp ordering and quality state.

- [x] **Step 1: Write failing redaction, deterministic export and normalized fake-provider contract tests.**
- [x] **Step 2: Run focused tests and confirm the absent fixture/fake symbols fail.**
- [x] **Step 3: Implement recursive redaction, fixture metadata/recording and the generic fake provider.**
- [x] **Step 4: Add synthetic discovery/market/on-chain fixtures that contain no credentials and run contract tests.**
- [x] **Step 5: Run secret scan, focused tests, Ruff and mypy; commit `feat: add provider fixtures and fakes`.**

### Task 5: Package/runtime contracts and Sprint 2.1 gate

**Files:**
- Modify: `infra/docker/api.Dockerfile`
- Modify: `infra/docker/worker.Dockerfile`
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `tests/unit/test_package_layout.py`
- Modify: `docs/PROVIDERS.md` only for implementation clarifications
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`

- [x] **Step 1: Add package-copy/import smoke tests and verify both Compose Python images include provider framework code.**
- [x] **Step 2: Run `make verify`, provider-focused tests, migration checks and bounded Compose runtime imports.**
- [x] **Step 3: Run `make doctor`; record provider live checks as `NOT_RUN` unless a key-safe, read-only doctor exists and succeeds.**
- [x] **Step 4: Reconcile Sprint 2.1 checkboxes/status with exact test results, blockers, provider acceptance and safety modes.**
- [x] **Step 5: Commit and push the Sprint 2.1 checkpoint; record the exact next task `Phase 2 / Sprint 2.2 — Helius / Solana Read Layer`.**
