# Phase 10 / Sprint 10.3 — Score Calibration Plan

1. Reconcile the Phase 10.2 pushed checkpoint and inspect existing strategy,
   replay, backtest, author and wallet contracts. Preserve the protected modes
   and document the current E10.2 insertion point.
2. Add red contract/unit tests for UTC time splits, candidate validation,
   feature neutralization, weight/threshold search, train-only selection,
   validation/test isolation, shadow identity, attribution metrics, safe
   promotion blocking and protected boundaries.
3. Implement the provider-free calibration contracts in
   `packages/application/src/memeradar_application/calibration.py` by
   rebuilding candidate strategy snapshots from event-time feature/risk
   evidence and delegating all trade metrics to `BacktestHarness`.
4. Implement deterministic JSON/CSV CLI and Make target for bounded calibration
   runs over the redacted replay fixture. Keep candidate reports descriptive;
   no production config write or score promotion path is allowed.
5. Add the E10.2 attribution analyzer for author-trust, internal smart-money,
   external-label incremental value and bundle/side-wallet false-confluence
   measurements. Require explicit future outcome labels and time-split output.
6. Run focused tests, Ruff, strict mypy, the calibration CLI and the full
   repository quality gate. Fix real defects without weakening safety tests.
7. Reconcile ROADMAP, architecture, data model, scoring/risk, testing,
   security, provider and research-extension documentation. Update STATUS with
   exact evidence, blockers and protected modes.
8. Commit and push the coherent Sprint 10.3 checkpoint. Only then continue to
   the next unblocked Phase 11 reliability task; Rust/Yellowstone remains
   conditional on E11.1 measurement.
