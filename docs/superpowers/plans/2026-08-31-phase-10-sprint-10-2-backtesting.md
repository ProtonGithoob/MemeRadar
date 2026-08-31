# Phase 10 / Sprint 10.2 — Backtesting Implementation Plan

## Checkpoint 1 — contracts and tests

- Add contract tests for the backtest policy, report identity, protected modes,
  no-provider boundary, metric fields, segmentation and deterministic export.
- Add unit fixtures that construct immutable replay results with fresh advisory
  strategy snapshots and future-only outcome labels.
- Cover profitable/losing target and stop exits, fee/slippage, horizon exits,
  unknown evidence, score buckets, drawdown/profit factor and all segments.

## Checkpoint 2 — provider-free backtest application module

- Implement `BacktestPolicy`, `BacktestManifest`, `BacktestTrade`,
  `BacktestMetrics`, `BacktestScoreBucket`, `BacktestSegmentKey`,
  `BacktestSegment`, and `BacktestReport`.
- Reuse `PaperFillModel` with deterministic `QuoteSnapshot` values rather than
  duplicating fill arithmetic.
- Select entries only from fresh advisory PASS strategy snapshots and evaluate
  exits independently from the entry threshold.
- Reduce trades into deterministic aggregate, calibration and segment metrics.
- Emit canonical JSON/CSV projections with version/config/dataset identities.

## Checkpoint 3 — CLI and fixture evidence

- Add a keyless `scripts/backtest_replay.py` command and Makefile target.
- Run the command against the redacted replay fixture; an input with no
  strategy signals must produce an explicit empty/unknown-safe report.
- Keep all protected modes asserted and report external acceptance separately.

## Checkpoint 4 — quality gate and handoff

- Run focused unit/contract tests, Ruff and strict mypy.
- Run the repository `make verify` quality gate.
- Reconcile roadmap and architecture/research/testing documentation.
- Update `docs/STATUS.md` with exact evidence and blockers, commit a coherent
  checkpoint, push `main`, and continue to Sprint 10.3 if unblocked.
