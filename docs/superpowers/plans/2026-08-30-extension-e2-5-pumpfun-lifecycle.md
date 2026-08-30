# Extension E2.5 / E6.3 Rich Pump.fun Lifecycle Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing launchpad/DEX parser with versioned Pump.fun/PumpSwap lifecycle events, deterministic stream/fallback consumption and replayable provider-neutral observations without changing existing Phase 2 discovery behavior.

**Architecture:** Keep protocol payload parsing in `packages/providers` and preserve the existing v1 discovery parser contract. Add a typed rich-event schema with explicit native-versus-derived origin, emit provider-neutral `protocol.lifecycle` observations for the application timeline, and consume an injected stream before a bounded polling fallback. No network client, signer, persistence model or execution authority enters the parser or stream seam.

**Tech Stack:** Python 3.12, frozen dataclasses, `Enum`, provider-neutral domain `Observation`, existing `ProviderSchemaError`/`ProviderRequestContext` contracts, async iterables, deterministic UUID5 IDs, pytest fixtures and Compose smoke checks.

**Spec:** `docs/ROADMAP_RESEARCH_EXTENSIONS.md` Extension E2.5 / E6.3 and `docs/ARCHITECTURE.md` Pump.fun / launchpad event semantics.

## Global Constraints

- Preserve all existing Phase 2 parser and canonical identity contracts.
- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Native protocol facts and derived classifications must be represented separately.
- Every normalized event retains source ID, occurred/observed/ingested timestamps, provenance, parser version and schema version.
- Future, malformed, duplicate and out-of-order input must remain deterministic and fail closed where ambiguous.
- `WHALE_TRADE` is a derived classification and cannot be presented as a protocol-native fact.
- Rich lifecycle events are evidence only; they cannot trigger a candidate transition, risk clearance, quote, signing or submission.
- No unclear-license upstream code is copied; implementation is based on the repository contract and public event semantics.

---

### Task 1: Add typed rich event schema while preserving v1 discovery parsing

**Files:**
- Modify: `packages/providers/src/memeradar_providers/launchpad_dex.py`
- Test: `tests/unit/test_launchpad_dex.py`

**Interfaces:**
- Produce `ProtocolEventType`, `ProtocolEventOrigin`, `PROTOCOL_EVENT_SCHEMA_VERSION` and `RICH_LAUNCHPAD_PARSER_VERSION`.
- Extend `ParsedProtocolEvent` with `protocol_event_type`, `event_origin`, `schema_version`, `is_derived` and `to_observation(token_id=...)` while retaining existing `event_type`, v1 parser values and `normalize()` behavior for old fixtures.

- [x] **Step 1: Write failing unit tests** for `launch`, `trade`, `bonding_curve_progress`, `graduation`, `migration`, `pool_created`, `creator_fee_claim`, `fee_recipient_change` and a derived `whale_trade`; assert the existing `token_created` fixture still reports parser v1 and that rich events expose schema v2, provenance and origin.
- [x] **Step 2: Run the focused tests** with `./.venv/bin/pytest tests/unit/test_launchpad_dex.py -q`; expect failures because the typed fields and rich event aliases do not yet exist.
- [x] **Step 3: Implement the schema** with an enum alias map and per-venue allow-list expansion. Keep the raw normalized `event_type` string for compatibility, infer unknown legacy instructions as `OTHER`, and mark whale/large-trade classifications as `DERIVED`.
- [x] **Step 4: Implement `ParsedProtocolEvent.to_observation()`** using deterministic UUID5 source identity, `kind="protocol.lifecycle"`, the event type/origin/schema in the normalized payload, the event provenance and the optional canonical token ID.
- [x] **Step 5: Run the focused tests** again and require the old and new unit cases to pass.

### Task 2: Add stream-first protocol consumer with bounded polling fallback

**Files:**
- Create: `packages/providers/src/memeradar_providers/protocol_stream.py`
- Modify: `packages/providers/src/memeradar_providers/__init__.py` only if package exports require it
- Test: `tests/unit/test_protocol_stream.py`

**Interfaces:**
- `ProtocolStreamPolicy(max_reconnects=3, reconnect_delay_seconds=1.0, max_reconnect_delay_seconds=30.0, max_messages=1000)`.
- `ProtocolStreamResult(events, used_fallback, received, emitted, malformed, reconnects)`.
- `ProtocolEventStreamFallback(adapter, stream_factory, poller, policy=..., sleeper=...).collect(context, stop_event=None) -> ProtocolStreamResult`.
- Pollers receive the existing `ProviderRequestContext` and return raw envelopes; the adapter performs the same validation as direct parsing.

- [x] **Step 1: Write failing tests** for successful stream normalization, malformed-message counting, cancellation, one bounded reconnect, out-of-order event sorting, duplicate preservation for downstream idempotency and fallback poll normalization.
- [x] **Step 2: Run `./.venv/bin/pytest tests/unit/test_protocol_stream.py -q`** and confirm collection/behavior fails before the new module exists.
- [x] **Step 3: Implement the consumer** using injected async sources only; bound reconnects, delays, messages and poll output; propagate cancellation; classify only `ProviderSchemaError` as malformed and use polling only after the stream retry budget is exhausted.
- [x] **Step 4: Sort emitted `ParsedProtocolEvent` values** by `(occurred_at, observed_at, ingested_at, source_id)` before returning while retaining equal source deliveries, and mark fallback use explicitly.
- [x] **Step 5: Run focused stream tests** and require all cases to pass without any provider/network import.

### Task 3: Add deterministic rich lifecycle fixtures and contracts

**Files:**
- Create: `fixtures/providers/launchpad_dex/rich_pumpfun_replay.json`
- Modify: `fixtures/providers/launchpad_dex/README.md`
- Create: `tests/contract/test_extension_e2_5_pumpfun_lifecycle.py`
- Modify: `tests/smoke/test_compose_contract.py`

**Interfaces:**
- Fixture contains a Pump.fun launch/trade/bonding-curve/graduation/migration/fee-claim/recipient-change sequence, a PumpSwap pool/trade event, a derived whale trade, duplicate delivery and one malformed envelope.
- Contract parses all valid records in original and reversed delivery order, converts them to observations, verifies stable logical ordering/source IDs, preserves duplicate deliveries, rejects malformed input, and checks credential-free/provider-independent/safe-mode boundaries.

- [x] **Step 1: Add the synthetic fixture and failing contract** with no credentials, wallet keys or live URLs.
- [x] **Step 2: Run the contract** and confirm it fails until the stream/schema behavior is complete.
- [x] **Step 3: Complete fixture documentation** with schema/parser versions, native/derived semantics and the no-live-capture warning.
- [x] **Step 4: Add a smoke assertion** that imports the rich event enum/consumer and checks the two fixture files and all four Compose modes.
- [x] **Step 5: Run unit, contract and smoke tests** together.

### Task 4: Reconcile provider/data/roadmap status and run the E2.5 gate

**Files:**
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/ROADMAP_RESEARCH_EXTENSIONS.md`
- Modify: `docs/STATUS.md`

**Interfaces:**
- Document `protocol.lifecycle` observations, schema v2, native/derived origin, stream-first/fallback behavior and evidence-only semantics.
- Mark E2.5 tasks complete only after tests and quality gates pass; record live protocol access as `BLOCKED_EXTERNAL` if configuration is absent and set the next task to E6.0.

- [x] **Step 1: Reconcile docs** without changing completed Phase 2 claims or enabling live execution.
- [x] **Step 2: Run `make lint`, `make typecheck`, focused tests, `make secret-scan`, `./.venv/bin/python scripts/check_migrations.py` and Compose config.**
- [x] **Step 3: Run `make verify` at the permitted runtime boundary** if sandboxed TestClient sockets reproduce the documented host restriction.
- [x] **Step 4: Rebuild API/worker images and run rich-event import/mode/health probes.**
- [x] **Step 5: Commit the implementation checkpoint, push it, then record the pushed hash in a status synchronization commit and advance to E6.0.**
