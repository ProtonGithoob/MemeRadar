# Phase 10 / Sprint 10.3 — Score Calibration Design

## Goal

Add a provider-free, reproducible research projection for feature ablation,
threshold/weight search and shadow comparison of versioned `AlphaStrategy`
implementations. The projection must use the existing event-time replay result
and Phase 10.2 backtest harness without changing production scoring, decision
bands, risk gates or operating modes.

The same report also supplies the approved E10.2 author/wallet research seam:
social-author and internal smart-money components can be neutralized and
compared against the baseline, while an explicit attribution contract can
measure external-label incremental value and bundle/side-wallet false
confluence. These are research observations, never new score authority.

## Scope and invariants

- Consume only `ResearchReplayResult`, immutable feature/risk snapshots and
  future-only outcome projections.
- Candidate scores are recomputed at each replay checkpoint from the checkpoint
  feature/risk snapshot. Candidate strategies never inspect events after the
  checkpoint.
- Split checkpoints by deterministic time intervals:
  train, validation, then test. Candidate selection uses train metrics only;
  validation and test are out-of-sample evidence.
- Reuse `BacktestHarness` and `PaperFillModel` for all candidate metrics.
- Candidate snapshots are explicitly `is_production=False`, advisory and
  permanently execution-ineligible.
- Feature ablation neutralizes a named AlphaScore component to the configured
  neutral value while retaining the existing policy's safety and confidence
  behavior. It cannot make missing/unknown evidence safe.
- Weight candidates use validated, normalized component weights. No candidate
  can modify hard risk disposition, freshness, provider identity or protected
  modes.
- Promotion is never automatic. A report may say that evidence is sufficient
  for manual review, but it cannot mutate production config, promote a score
  version, authorize `ENTRY_READY` or enable trading.
- Reports contain pinned dataset/replay/candidate/policy identities, split
  boundaries, metrics, ablation deltas, reason-coded promotion blockers and a
  deterministic digest. Secret-shaped fields and raw provider payloads are
  rejected.

## Proposed contracts

### `CalibrationTimeSplit`

An immutable UTC interval with `train_end`, `validation_end` and `test_end`
boundaries (and an optional start). Intervals are half-open and map a
checkpoint's `as_of` timestamp to `TRAIN`, `VALIDATION`, `TEST` or
`OUT_OF_RANGE`. Boundaries must be strictly increasing and may not exceed the
replay manifest's event-time ceiling.

### `CalibrationCandidate`

An immutable candidate identity, description, validated component weights,
optional neutralized component names, entry score threshold and minimum
confidence. It derives a stable shadow strategy version and policy identity.
Candidate weights are normalized through the existing `StrategyPolicy`; the
production AlphaScore v1 policy remains unchanged.

### `CalibrationCandidateEvaluation`

Contains the candidate's train/validation/test backtest metrics and artifact
digests, the train-only selection objective, deterministic rank, and deltas
against the baseline candidate for each split. Metrics are explicit when empty
or unknown; they are never imputed as positive performance.

### `PromotionAssessment`

Checks minimum out-of-sample evidence, finite metrics, drawdown limits and
documented evidence references. The result is either blocked with reason codes
or `MANUAL_REVIEW_REQUIRED`; there is no `PROMOTED` state or write path.

### `ScoreCalibrationReport`

Pins the replay dataset digest, split, candidate set, backtest assumptions,
baseline/selected candidate IDs, candidate evaluations, promotion assessment,
protected modes and an artifact digest. JSON is canonical and CSV is a stable
flat projection.

### E10.2 attribution seam

`AttributionCalibrationSample` records an event-time baseline/augmented score,
the known future outcome label when available, sample/confidence metadata and
optional external-label/bundle-confluence annotations. A provider-free
`AttributionCalibrationAnalyzer` calculates baseline-vs-augmented lift,
external incremental lift and false-confluence rates by the same time split.
Insufficient or unknown labels remain explicit and cannot be used to promote a
policy.

## Selection and evidence policy

Within the train interval, candidates sort deterministically by:

1. non-null net-return expectancy, descending;
2. precision, descending;
3. maximum drawdown, ascending;
4. candidate ID, ascending.

The selected candidate is then measured unchanged on validation and test.
Default promotion evidence requires a configurable minimum number of executed
trades in train, validation and test, finite validation/test expectancy,
non-negative out-of-sample expectancy, bounded drawdown, and non-empty
documented evidence references. Even when all conditions pass, the report only
returns `MANUAL_REVIEW_REQUIRED` and remains non-production.

## Failure behavior

- Invalid split, candidate identity or weight map: reject the run.
- Missing feature/risk/strategy evidence: preserve an explicit backtest skip.
- Empty interval or unknown future outcome: retain empty/unknown metrics and
  block promotion for insufficient evidence.
- Candidate disagreement is represented by separate shadow evaluations; no
  candidate silently replaces the baseline.
- Secret-shaped or non-finite artifact input: reject before output.

## Acceptance evidence

- baseline, one neutralized feature and one weight candidate share identical
  checkpoint/event boundaries;
- train selection does not inspect validation/test metrics;
- reverse delivery and future events do not change candidate scores;
- threshold/weight candidates produce deterministic metrics and digests;
- ablation and external/bundle attribution remain descriptive;
- insufficient evidence blocks promotion;
- canonical JSON/CSV artifacts round-trip without secrets;
- no provider SDK, persistence, signer, execution, frontend or mode mutation
  dependency enters the calibration module or CLI;
- focused tests, strict typing/lint and the full repository gate pass.
