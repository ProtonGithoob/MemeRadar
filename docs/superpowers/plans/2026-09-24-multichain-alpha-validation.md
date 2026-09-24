# Multi-Chain Alpha Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the existing forward-outcome pipeline against the repository PostgreSQL stack, make stream gaps durable and recoverable, and add only locally verifiable read-only provider seams for the requested chains.

**Architecture:** Reuse the existing worker, `ForwardEvidenceCollector`, stream-integrity coordinator, provider ports, generic EVM adapter, decision/security/paper owners, and API read services. Extend existing contracts only where a missing diagnostic or protocol boundary prevents acceptance; do not add a second scorer, lifecycle engine, execution engine, provider registry, or database.

**Tech Stack:** Python 3.12, SQLAlchemy async + Alembic, PostgreSQL/Redis Compose, pytest, existing Solana RPC/WebSocket and EVM adapters, FastAPI application services.

**Spec:** `docs/MASTER_SPEC.md`, `docs/ROADMAP.md`, `docs/ROADMAP_RESEARCH_EXTENSIONS.md`, `docs/STREAM_RELIABILITY_PROTOCOL_VERIFICATION.md`, `docs/MADEONSOL_SIGNAL_HARDENING.md`, and the user-supplied autonomous execution contract.

## Global Constraints

- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Do not use GitHub or remote Git operations; the local repository is authoritative.
- Live, backfill, and replay chain data use the same canonical decoder/normalizer path.
- Unresolved gaps, unknown evidence, provider conflicts, and unverified protocol identities fail closed.
- External provider evidence never becomes trade authority.
- No zero-filled outcomes; immature horizons remain unknown/not-yet-matured.
- Preserve unrelated user files and do not print or read secrets.

## Review Focus

- A program-scoped Solana stream must not turn unrelated slot skips into false missing-event gaps; `slot_continuity_expected=False` remains explicit and tested.
- A reconnect gap must persist its connection/reason, bounded recovery result, and unresolved state even when backfill returns no relevant events.
- A matured outcome must be idempotent across worker restart and must not downgrade an already matured row.
- Same ticker and same symbol on different chains/contracts must remain distinct canonical identities.
- Unverified external protocol addresses must remain `TODO_VERIFY`/`BLOCKED_EXTERNAL` and must not enable runtime discovery.

### Task 1: Database-backed forward-shadow acceptance

**Files:**
- Modify: `docs/STATUS.md`
- Create: `.codex/CURRENT_TASK.md`, `.codex/VERIFICATION.md`
- Evidence: `docs/reports/forward-shadow-live-acceptance-2026-09-24.md`

**Interfaces:** Consumes the existing Compose service definitions and `ForwardEvidenceCollector`; produces a repeatable local acceptance record with row counts, horizon states, and restart comparison.

- [ ] Inspect Compose health, migration state, worker logs, and current provider configuration without printing secrets.
- [ ] Start/reuse the repository PostgreSQL/Redis/API/worker stack through its existing scripts and run migrations through the existing target.
- [ ] Run the existing Pump.fun read-only forward worker and outcome/maturation loop for a bounded acceptance window; query launch, market snapshot, early-feature, decision, and outcome rows from PostgreSQL.
- [ ] Restart the worker once, rerun the same read-only loop, and prove source-id uniqueness and matured-row non-downgrade.
- [ ] Record whether each required horizon (`1m`, `5m`, `15m`, `30m`, `1h`, `3h`, `6h`, `24h`, `72h`, `7d`) is mature, immature, or absent; report unknowns instead of zero-filling.
- [ ] Commit only evidence/docs or the smallest production fix required by a reproduced failure.

### Task 2: Stream-gap root cause, durable diagnostics, and bounded recovery

**Files:**
- Modify: `packages/domain/src/memeradar_domain/stream_integrity.py`, `packages/application/src/memeradar_application/stream_integrity.py`, `packages/persistence/src/memeradar_persistence/models.py`, `packages/persistence/src/memeradar_persistence/stream.py`
- Create: `infra/alembic/versions/0012_stream_gap_diagnostics.py`
- Modify: `apps/worker/src/memeradar_worker/main.py` and existing Solana RPC/raw-stream adapters as required
- Test: `tests/unit/test_stream_integrity.py`, `tests/unit/test_stream_persistence_contract.py`, new focused recovery/diagnostic tests
- Evidence: `docs/reports/stream-gap-root-cause-2026-09-24.md`

**Interfaces:** Consumes existing `RawChainTransaction`, `BackfillRequest`, `ChainBackfillPort`, and `StreamStateStore`; produces durable `gap_started_at`, `gap_resolved_at`, missed-slot range, provider/connection/reconnect data, backfill status, recovered/unrecoverable event counts, plus bounded Solana finalized-slot backfill using the existing decoder.

- [x] Reproduce and classify the reported gap counter by transport, stream id, slot-continuity mode, reconnects, queue saturation, throttling, cursor state, and enrichment latency before editing code.
- [x] Write failing tests for diagnostic persistence, unresolved no-event recovery, and program-scoped slot-skip behavior.
- [x] Add the smallest compatible domain/ORM/migration fields and state transitions; preserve legacy fields and existing idempotency keys.
- [x] Add bounded `getBlocks`/`getBlock` finalized reads behind the existing Solana RPC adapter and feed returned transactions through the canonical decoder only.
- [x] Wire safe automatic recovery for explicit reconnect/known ranges; leave gaps unresolved when provider data cannot prove continuity.
- [x] Run focused tests, full tests, and a bounded local doctor/acceptance run; record before/after evidence without claiming external recovery.

### Task 3: Solana read-only protocol coverage

**Files:**
- Modify: existing protocol registry/provider metadata and Solana provider composition
- Create only if missing: focused Raydium/PumpSwap/Jupiter provider modules and fixtures
- Test: focused parser/quote/provenance tests

**Interfaces:** Consumes canonical Solana normalized events and existing quote/provider ports; produces capability-scoped Raydium/PumpSwap pool observations and Jupiter Swap API V2 quote/order parsing, with source/provenance and no signing.

- [x] Inspect existing Raydium/PumpSwap/protocol registry and current configuration before writing adapters.
- [x] Write failing fixture tests for pool identity, liquidity/reserve/tick normalization, Jupiter route/impact/output/sell-route parsing, timeout/rate-limit behavior, and provider fallback ordering.
- [x] Implement only the missing read-only parsing/transport behavior through existing provider transport and capability metadata.
- [x] Keep Helius optional and ensure its absence does not disable Pump.fun discovery.
- [x] Verify protected modes and run focused/full checks.

### Task 4: Generic EVM read-only chain and protocol seams

**Files:**
- Modify: existing EVM chain/config/provider metadata/composition files
- Create only if missing: focused BNB/Four.meme/Pancake, Base/Uniswap/Aerodrome, Ethereum/Blockscout/sellability modules
- Test: fixtures for chain identity, lifecycle/event parsing, pool identity, sellability unknown/conflict, and same-ticker identity

**Interfaces:** Consumes existing generic EVM RPC/log/quote/security ports; produces disabled-by-default read-only adapters for Robinhood (4663), BNB (56), Base, Ethereum, and architecture-only Arbitrum/Avalanche/Polygon/Unichain plus a non-EVM Sui seam.

- [x] Write fixture-first tests before implementation; use no unverified deployment address as authoritative.
- [x] Reuse the generic EVM adapter for chain identity and logs; implement Four.meme lifecycle and Pancake pool normalization only where ABI/event identity is locally verified or explicitly marked `TODO_VERIFY`.
- [x] Add Base/Uniswap/Aerodrome and Ethereum/Uniswap read-only discovery seams, Blockscout enrichment, and provider-neutral EVM sellability evidence without signing.
- [x] Keep Robinhood protocol candidates disabled until chain/address/bytecode/event/sample-transaction verification exists.
- [x] Run provider contract tests and ensure default enabled chains remain unchanged.

### Task 5: Read-only API/MCP operator surface

**Files:**
- Modify: existing API read routes/services only where endpoints are absent
- Create: minimal `memeradar-mcp` package/server using existing application read services
- Test: MCP read-only boundary and route/service contract tests

**Interfaces:** Consumes application/API read services; produces the requested read-only opportunity, evidence, health, outcome, replay, ablation, Telegram, position, and paper-performance tools. No MCP tool may submit, sign, mutate, or duplicate domain logic.

- [x] Inventory existing routes/services and write failing read-only boundary tests.
- [x] Add a thin stdio/JSON-RPC MCP wrapper over existing read routes; leave unavailable research projections explicit.
- [x] Reject unknown/mutating tool names and prove no execution dependency is imported.
- [x] Run focused checks; full checks remain in Task 6.

### Task 6: Integration records and final verification

**Files:**
- Create/update: `docs/reports/external-repo-license-matrix.md`, `docs/reports/external-integration-matrix.md`, `docs/STATUS.md`, `.codex/CURRENT_TASK.md`, `.codex/VERIFICATION.md`
- Test/verify: repository lint, typecheck, tests, verify, coverage report

- [x] Record each requested upstream repo’s locally verified license/commit status; mark unavailable external verification instead of inventing it.
- [x] Record exact per-chain capability status, real DB counts, stream-gap evidence, telemetry percentiles, recall/FPR/FNR/ablation and provider disagreements, preserving `NOT_MEASURED`/`INSUFFICIENT_SAMPLES` where external evidence is absent.
- [x] Run `git diff --check`, `make lint`, `make typecheck`, `make test`, and `make verify`; record coverage percentage and delta from the 79% baseline when available.
- [x] Perform a separate whole-branch self-review, commit coherent local phases, and leave protected modes unchanged.
