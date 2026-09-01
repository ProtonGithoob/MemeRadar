# Provider-independent signal hardening implementation plan

> Approved research-derived E11.9 → E11.4 → E11.5 → E11.6 → E11.7 → E11.8
> extension.  MadeOnSol is a research pattern only; no MadeOnSol adapter or
> Phase 12 work is in scope.  Protected modes remain analysis-only and paper
> trading.

## Current-state audit

- [x] Reconciled `main` with `origin/main` using a fast-forward merge at
  `526e691`; the worktree was clean and no local changes were discarded.
- [x] Confirmed existing `PaperFillModel` calculates and accounts with an
  adverse effective fill price, while `PaperFill`, `WalletActivity` and replay
  price labeling do not expose an unambiguous market/reference-price contract.
- [x] Confirmed there is no existing sustained-regime, economic move-funding,
  deployer transfer-delta, bounded launch-footprint, or token lock/vesting
  implementation.  Existing flow, wallet, holder, liquidity, external-wallet,
  replay, calibration and timeline primitives will be extended.

## Task 1: E11.9 explicit price semantics (TDD first)

- [x] Add deterministic contract tests for `EXECUTION_EFFECTIVE`,
  `MARKET_REFERENCE`, and `UNKNOWN` price roles, including missing values,
  provenance/freshness, and the rule that a quote/fill price is not a market
  reference by implication.
- [x] Add a provider-neutral price-semantics value object/resolver.  Make
  `PaperFill` expose explicit execution/effective aliases and optional market
  reference metadata without changing ledger accounting; keep position cost
  basis/PnL on the effective price.
- [x] Update replay outcome labeling to consume market/reference prices only,
  preserve legacy market snapshot aliases, and record an explicit unknown
  baseline when only execution data exists.
- [x] Focused tests pass; commit and push the E11.9 checkpoint.

## Task 2: E11.4 sustained surge/revival validation

- [x] Add tests first for sustained multi-sample surge, one-tick reversal,
  revival requiring prior inactivity and real buy flow, insufficient history,
  stale/unknown/conflicted observations, and no future-data leakage.
- [x] Implement versioned `SignalHardeningPolicy`, `MomentumRegimeSnapshot`
  and deterministic event-time analyzer.  All durations, sample counts and
  quality thresholds are configuration-driven hypotheses, not MadeOnSol truth.
- [x] Ensure a price/market-cap mark cannot produce a positive regime without
  actual buy flow, quote volume, liquidity and buyer evidence.

## Task 3: E11.5 economic market-move/tape validation

- [x] Add tests for market-cap movement funded by actual buy volume, thin
  liquidity, wash-adjusted flow, partial/missing quote units, stale/conflicted
  market data, and neutral healthy-stream behavior.
- [x] Implement `MoveFundingEvidence` in the same analyzer, preserving quote
  units where USD conversion is unavailable and producing explicit reason
  codes/quality/confidence rather than zero-filling unknowns.

## Task 4: E11.6 deployer activity and transfer delta

- [x] Add tests for trade-derived holdings, on-chain balance snapshots,
  transfer-in/out deltas, missing transfer evidence, stale/conflicted input,
  and evidence-only interpretation.
- [x] Implement bounded `DeployerActivitySnapshot` and integrate it with the
  existing wallet/creator sell-pressure evidence; transfer delta remains a
  discrepancy and never an automatic maliciousness proof.

## Task 5: E11.7 launch sniper/bundle footprint

- [ ] Add tests for first-N-slot/first-duration bounded footprint, internal
  actor clustering, optional external corroboration, concentration, missing
  launch history and unknown/stale/conflict behavior.
- [ ] Implement `LaunchFootprintSnapshot` using normalized events and existing
  holder/wallet graph inputs where available.  Absence of evidence is never a
  clean-launch assertion.

## Task 6: E11.8 token lock/vesting/unlock evidence

- [ ] Add tests for token locks versus LP locks, scheduled unlock windows,
  cancelable/unknown metadata, unlock events, stale/conflicted evidence and
  the rule that a lock is not a safety verdict.
- [ ] Implement provider-neutral `TokenLockSnapshot` and `TokenUnlockEvent`
  parsing with bounded schedules, provenance, expiry and explicit quality.

## Task 7: Architecture integration

- [ ] Carry typed hardening snapshots into `CorrelationWindowFeatures` without
  creating a new AlphaScore component or provider dependency.
- [ ] Project the evidence into existing market/momentum/wallet/
  on-chain-safety feature families.  Only configured corroboration/quality
  penalties may affect momentum confidence; stream health never adds score.
- [ ] Wire the same analyzer into `ReplayHarness` before correlation/features,
  persist hardening/parser/registry/schema/config identity in replay artifacts,
  and keep calibration consumption deterministic.
- [ ] Add evidence-timeline projection for hardening summaries while retaining
  read-only/no-execution guarantees.
- [ ] Add fixture README/data, provider-independent doctor/contract coverage
  where useful, and import-boundary/protected-mode tests.

## Task 8: Verification and handoff

- [ ] Run focused E11.9–E11.8 tests, replay/no-lookahead tests, and relevant
  existing correlation/feature/paper/timeline tests.
- [ ] Run `make verify`, and run the frontend build if changed contracts require
  it.  Fix failures without weakening tests.
- [ ] Reconcile the roadmap/extension documentation and update `docs/STATUS.md`
  with exact evidence, blockers, protected modes, and Phase 12 lock.
- [ ] Run diff/secret checks, commit coherent final changes, push, and verify
  clean local/origin synchronization.
