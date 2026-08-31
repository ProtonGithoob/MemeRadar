# Phase 10 / Sprint 10.1 Replay Harness Implementation Plan

**Design:** `docs/superpowers/specs/2026-08-31-phase-10-sprint-10-1-replay-harness-design.md`

## Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Reuse the existing normalized observation, correlation, feature, strategy,
  exit and paper replay seams; do not create replay-only decoding.
- Future observations may label outcomes only and must never affect features,
  scores or decisions at the earlier checkpoint.
- Export normalized evidence and provenance only; reject raw secrets and
  provider/network dependencies.

### Task 1: Freeze contracts with red tests

- [x] Add dataset/manifest serialization and partition-contract tests.
- [x] Add deterministic event ordering, duplicate/version and no-lookahead
  replay tests.
- [x] Add outcome-label tests for returns, MFE/MAE, thresholds, liquidity/rug
  and paper-exit evidence.
- [x] Add strategy-comparison and protected-boundary tests.

### Task 2: Implement the provider-free harness

- [x] Add normalized replay dataset/checkpoint/manifest/result contracts.
- [x] Compose existing correlation and feature builders at each checkpoint.
- [x] Add optional advisory AlphaStrategy evaluation with pinned identities.
- [x] Add independent outcome labeling and deterministic artifact digest.

### Task 3: Add the local artifact CLI

- [x] Add safe JSON load/export with date/venue/token partition metadata.
- [x] Add `scripts/replay_dataset.py` and `make replay-dataset`.
- [x] Add a redacted deterministic fixture and smoke/doctor-style contracts.

### Task 4: Gate and checkpoint

- [x] Run focused replay tests, Ruff and mypy.
- [x] Run the full repository quality gate and CLI fixture replay.
- [x] Reconcile roadmap, architecture, data model, scoring/risk, providers,
  security, testing and STATUS.
- [x] Commit and push the Sprint 10.1 keyless checkpoint.

## Resumability checkpoint

At each task boundary update `docs/STATUS.md` with exact active work,
verification, protected modes, external blockers and next action. Live provider
acceptance remains independently `BLOCKED_EXTERNAL`.

## Completed checkpoint

The provider-free harness, redacted fixture, JSON/CSV artifact CLI, cohort
summaries, alternate-strategy comparison and bounded throughput profiler are
implemented. Focused replay contracts pass `11 tests`; repository verification
passes with `577 passed, 10 skipped`; `make replay-dataset` and
`make profile-replay PROFILE_ITERATIONS=25` pass. The next checkpoint is Phase
10 / Sprint 10.2 backtesting; protected modes and Gate P9 external blockers
remain unchanged.
