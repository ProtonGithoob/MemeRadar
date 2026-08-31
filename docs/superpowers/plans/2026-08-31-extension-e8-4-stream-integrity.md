# Extension E8.4 Stream Integrity / Protocol Verification Implementation Plan

> **For agentic workers:** use TDD/contract-first implementation with focused
> verification after each task and keep the checkout resumable at every
> checkpoint.

**Goal:** retrofit provider-independent Solana stream completeness,
canonical protocol verification and replay-safe normalized evidence before
Phase 9 paper trading.

**Spec:** `docs/superpowers/specs/2026-08-31-extension-e8-4-stream-integrity-design.md`
and `docs/STREAM_RELIABILITY_PROTOCOL_VERIFICATION.md`, together with the
existing domain, architecture, data-model, scoring, provider, security and
testing contracts.

## Global constraints

- Preserve every completed Phase 2/E2.5 parser and Phase 8 UI contract.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No provider SDK, HTTP client, FastAPI, SQLAlchemy, signer or execution port
  enters domain/application stream-integrity logic.
- Live, replay and backfill use one canonical decoder/normalizer path.
- Unknown/unverified/conflicted/missing evidence fails closed and never raises
  AlphaScore or `ENTRY_READY`.
- Keyless fixtures and fakes establish all acceptance behavior; live RPC or
  stream access is separately `BLOCKED_EXTERNAL` when unavailable.
- No Rust/Yellowstone extraction before E11.1 profiling.

## Task 1: Freeze contracts with failing tests

**Files:** `tests/unit/test_chain_domain.py`,
`tests/unit/test_stream_integrity.py`, `tests/contract/test_extension_e8_4_stream_integrity.py`,
`tests/unit/test_protocol_registry.py`.

- [ ] Add domain tests for commitment/recovery/gap/verification states,
  cursor monotonicity, gap merge and normalized event identity/provenance.
- [ ] Add application tests for contiguous/missing/overlapping/skipped slots,
  restart, duplicate/conflict handling, bounded timeout/rate-limit recovery,
  backpressure and telemetry.
- [ ] Add registry tests for Anchor/native identity, discriminator collision,
  unknown/unverified fail-closed routing and decoder equivalence.
- [ ] Add replay/no-lookahead/quality-impact and protected-mode/provider-
  independence tests.
- [ ] Run the focused tests and record expected red failures before code.

## Task 2: Implement provider-independent domain contracts

**Files:** `packages/domain/src/memeradar_domain/chain.py`,
`packages/domain/src/memeradar_domain/__init__.py`.

- [ ] Implement validated immutable `CommitmentState`, `RecoveryState`,
  `StreamGapStatus`, `StreamVerificationStatus`, `ChainCursor`, `StreamGap`,
  `StreamVerification` and `NormalizedChainEvent`.
- [ ] Preserve separate occurred/observed/ingested/recovery timestamps and
  provenance; expose deterministic canonical event IDs and explicit correction
  state.
- [ ] Make cursor progress monotonic and reject contiguous/finalized movement
  across unresolved gaps.

## Task 3: Implement the application integrity coordinator

**Files:** `packages/application/src/memeradar_application/stream_integrity.py`.

- [ ] Define raw transaction/block envelopes, bounded backfill request/result,
  `ChainBackfillPort`, canonical decoder port, state-store port and telemetry
  port with only provider-neutral types.
- [ ] Implement deterministic gap detector/merger, in-memory state store,
  bounded event handoff and safe timeout/rate-limit/backfill error classes.
- [ ] Implement live ingest and recovery orchestration. Persist normalized
  events before advancing durable cursor; use the exact decoder for live,
  backfill and replay; verify expected produced slots/events before marking a
  gap verified.
- [ ] Implement duplicate provenance merge, explicit conflict state, restart
  resume, commitment updates/revert correction and required telemetry.

## Task 4: Add protocol registry and canonical provider decoder

**Files:** `packages/providers/src/memeradar_providers/protocol_registry.py`,
  `launchpad_dex.py` only if a concrete adapter seam is required.

- [ ] Add versioned `ProtocolIdentityRegistry`, Anchor/native identity helpers,
  verification/support classifications and required protocol audit output.
- [ ] Route only by `(program_id, discriminator/tag)`; reject discriminator-
  only or unknown/unverified input with explicit unsupported evidence.
- [ ] Adapt the existing parser once behind `CanonicalProtocolDecoder` and
  make `decode_live`, `decode_backfill` and `decode_replay` delegate to the
  same method. Do not rewrite existing Phase 2 adapters.
- [ ] Mark production identities `TODO_VERIFY` unless authoritative evidence
  is recorded; use synthetic verified identities only for keyless routing
  fixtures.

## Task 5: Persist chain state and normalized metadata

**Files:** `packages/persistence/src/memeradar_persistence/models.py`,
`packages/persistence/src/memeradar_persistence/stream.py`,
`infra/alembic/versions/0005_stream_integrity.py`, repositories/UoW only as
needed, plus migration/integration tests.

- [ ] Add nullable chain/slot/signature/program/transport/commitment/recovery/
  registry fields and indexes to `observations`.
- [ ] Add durable cursor, gap and verification models with safe error fields,
  uniqueness/index constraints and a SQLAlchemy state-store implementation.
- [ ] Keep writes append-oriented/transactional and migration reversible;
  update metadata/table-count parity and opt-in Postgres coverage.

## Task 6: Integrate quality, replay and operational visibility

**Files:** `feature_windows.py` or a narrow quality helper, telemetry/config/
  doctor/Makefile/docs as needed.

- [ ] Add stream-quality impact that reduces completeness/confidence for
  affected windows and never contributes positive score/decision authority.
- [ ] Expose safe counters/lag/open-gap/backfill/verification/decoder/reorg/
  backpressure metrics; add a key-safe provider doctor/check seam for live
  acceptance without claiming access.
- [ ] Pin parser/registry/event-schema/strategy/config identities in normalized
  event/replay metadata and prove deterministic no-lookahead replay.

## Task 7: E8.4 gate and handoff

**Files:** E8.4 docs, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`,
`docs/DATA_MODEL.md`, `docs/PROVIDERS.md`, `docs/SCORING_AND_RISK.md`,
`docs/SECURITY.md`, `docs/TESTING.md`, `docs/STATUS.md`.

- [ ] Run focused domain/application/provider/persistence/replay tests.
- [ ] Run Ruff, mypy, full backend/frontend tests, migration parity, secret
  scan, Compose config and relevant keyless runtime probes.
- [ ] Record exact E8.4 keyless PASS evidence and any live RPC/stream
  `BLOCKED_EXTERNAL` state; preserve all protected modes.
- [ ] Commit/push coherent checkpoints and mark E8.4 complete only after the
  full quality gate. Then begin Phase 9 Sprint 9.1 without restarting earlier
  phases.

## Resumability checkpoint

At each task checkpoint update `docs/STATUS.md` with the active task, exact
tests/evidence, migration head, blockers, protected modes and next step. Never
leave the repository dependent on chat context alone.
