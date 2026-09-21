# Pump.fun Launch Decoding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the current authoritative Pump.fun IDL locally, decode `create` and `create_v2` through the existing raw-to-canonical-to-early-runtime path, and attempt one bounded public read-only launch acceptance.

**Architecture:** Reuse `SolanaRawTransactionSource`, `CanonicalProtocolDecoder`, `StreamIntegrityCoordinator`, `EarlyRuntimeStreamWorker`, and the existing persistence/DexScreener adapters. Add only a small local IDL schema/decoder and metadata checks at the current provider boundary; do not add a second event stream, scoring path, or execution capability.

**Tech Stack:** Python 3.12, existing provider/application contracts, Borsh-compatible stdlib decoding, pytest, SQLAlchemy persistence, public Solana JSON-RPC/WebSocket, DexScreener exact-mint HTTP.

**Spec:** `docs/MASTER_SPEC.md`, `docs/SOLANA_RAW_INGESTION_FIELD_MAPPING.md`, `docs/DATA_MODEL.md`, and the user-supplied Pump.fun `COIN_CREATION.md`/`pump.json` sources.

## Global Constraints

- Pin Pump.fun docs revision `81091419e4457566469d4e2a27f64ed84d42419c` and IDL SHA-256 `ffe966c42f1af41652ee7532fe1e3f7cd4077d7e6f49faf3138959c8b56064b`.
- Runtime decoding must not fetch GitHub; changed pin metadata must fail closed with `PROTOCOL_DRIFT_DETECTED` and never auto-promote.
- `create` and `create_v2` are `LAUNCH`; `buy`, `buy_v2`, and `sell` variants are `TRADE`; trade records never increment launch counts.
- `create_v2` uses mint account 0, user account 5, token program account 7; creator comes only from instruction data.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and `AUTO_EXECUTION=false`.
- Real provider evidence is read-only, bounded, provenance-bearing, and may remain blocked without fabricating success; `REAL_WORLD_ALPHA_VALIDATED` remains `NO`.

## Review Focus

- EOF-tolerant trailing `create_v2` optional arguments must preserve false/zero semantics without shifting creator or account indexes.
- A non-native quote mint must be read from the exact optional remaining-account layout; missing or wrapped SOL must remain explicitly SOL semantics.
- A token-program address at account index 7 must never be emitted as `creator`.
- Protocol metadata drift must fail before canonical routing rather than silently using a changed decoder.
- A real launch may be observed but not yet present in DexScreener; the benchmark must record that UNKNOWN state rather than invent a timestamp.

### Task 1: Local Pump.fun IDL schema and Borsh decoder

**Files:**
- Create: `packages/providers/src/memeradar_providers/pump_fun_idl.py`
- Test: `tests/unit/test_pump_fun_idl.py`

**Interfaces:**
- Produces `decode_pump_fun_instruction(instruction_type: str, data: bytes, accounts: Sequence[str]) -> Mapping[str, object]`.
- Produces pinned constants for source, revision, IDL SHA-256, and local schema version.
- Produces a pin-check function that returns `PROTOCOL_DRIFT_DETECTED` for mismatched revision/hash/schema values.

- [ ] **Step 1: Write failing fixture tests** for authoritative `create` and `create_v2` account names, discriminators, strings, pubkey creator, mayhem flag, holder-reward flag, SOL/USDC quote semantics, exact account indexes, and drift status.
- [ ] **Step 2: Run `pytest tests/unit/test_pump_fun_idl.py -q` and observe the expected import/decoder failure.**
- [ ] **Step 3: Implement the compact checked-in schema descriptors and one bounded Borsh reader for strings, pubkeys, bools, `OptionBool`, and `OptionU64`; reject wrong discriminators, truncated values, malformed optional remaining accounts, and trailing bytes.
- [ ] **Step 4: Run the focused fixture tests and verify they pass.**
- [ ] **Step 5: Commit `feat: add pinned pumpfun idl decoder`.**

### Task 2: Wire raw events, protocol pin metadata, and launch/trade semantics

**Files:**
- Modify: `packages/providers/src/memeradar_providers/solana_raw_stream.py`
- Modify: `packages/providers/src/memeradar_providers/protocol_registry.py`
- Test: `tests/unit/test_solana_raw_stream.py`
- Test: `tests/unit/test_protocol_registry.py`
- Test: `tests/unit/test_chain_opportunity.py`

**Interfaces:**
- Consumes Task 1's decoder and pinned metadata.
- Adds pinned source/revision/hash/local-schema fields to verified Pump.fun registry entries.
- Raw create payloads contain decoded fields, `instruction_type`, canonical `protocol_event_type`, observation timestamps, and drift metadata.

- [ ] **Step 1: Add failing tests** for raw `create`/`create_v2` decoded payloads, pinned registry metadata, drift fail-closed routing, and a chain-opportunity window containing one launch plus trades whose launch count remains one.
- [ ] **Step 2: Run the focused tests and observe failures against the current account-only payload/metadata.**
- [ ] **Step 3: Replace create account-only extraction with the local IDL decoder; preserve exact program-plus-discriminator routing; add pin metadata to registry entries and reject mismatches as `PROTOCOL_DRIFT_DETECTED`; keep existing trade mapping and explicit launch/trade aliases.
- [ ] **Step 4: Run the focused provider/application tests and verify pass.**
- [ ] **Step 5: Commit `feat: decode pumpfun launches through canonical stream`.**

### Task 3: End-to-end acceptance runner and exact-mint benchmark record

**Files:**
- Create: `scripts/pumpfun_live_acceptance.py`
- Test: `tests/unit/test_pumpfun_live_acceptance.py`
- Modify: `docs/SOLANA_RAW_INGESTION_FIELD_MAPPING.md`

**Interfaces:**
- Consumes the existing public `SolanaRawTransactionSource`, canonical decoder, stream worker, SQLAlchemy UoW, and `DexScreenerAdapter`; it does not create a new application architecture.
- Runs for a bounded timeout, stops on the first verified create/create_v2, records signature/slot/program/discriminator/instruction and decoded fields plus provider/MemeRadar times, checks the persisted `DISCOVERED` candidate, then performs one exact-mint DexScreener lookup and records first successful observation or UNKNOWN.
- Preserves the four protected operating-mode flags and writes a JSON evidence artifact under `artifacts/research/pumpfun-live/` only when the acceptance is run.

- [ ] **Step 1: Write failing offline tests** for protected-mode validation, output fields, no EARLY_WATCH threshold changes, and UNKNOWN DexScreener handling.
- [ ] **Step 2: Run `pytest tests/unit/test_pumpfun_live_acceptance.py -q` and observe the missing runner failure.**
- [ ] **Step 3: Implement the bounded runner by composing existing services; use the existing runtime persistence path and call DexScreener with the exact decoded mint immediately after the first persisted launch.
- [ ] **Step 4: Run the focused offline tests and verify pass.**
- [ ] **Step 5: Commit `feat: add bounded pumpfun live acceptance runner`.**

### Task 4: Bounded public observation, documentation, and final verification

**Files:**
- Modify: `docs/STATUS.md`
- Create when observed: `artifacts/research/pumpfun-live/<timestamp>.json`

- [ ] **Step 1: Run the full relevant unit/contract checks, stream doctor, and mode checks.**
- [ ] **Step 2: Run the acceptance runner for the bounded period against public finalized/confirmed read-only Solana RPC/WebSocket; do not weaken scoring thresholds or modes.**
- [ ] **Step 3: If a launch arrives, verify raw/canonical/normalized/persisted gates and immediately run exact-mint DexScreener lookup; if no launch or a provider gate is unavailable, record the precise blocker and UNKNOWN fields.
- [ ] **Step 4: Update `docs/STATUS.md` with pin metadata, test evidence, observation result, benchmark timestamps, and the required alpha boundary.**
- [ ] **Step 5: Run final verification, inspect `git diff`/`git status`, commit `docs: record pumpfun launch acceptance evidence`, and report the required status fields.**
