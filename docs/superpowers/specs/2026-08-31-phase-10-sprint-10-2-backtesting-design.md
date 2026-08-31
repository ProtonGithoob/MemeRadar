# Phase 10 / Sprint 10.2 — Backtesting Design

## Objective

Add a provider-free, reproducible backtesting projection over the Phase 10.1
`ResearchReplayResult`. The projection evaluates versioned entry and exit
policies, applies the existing deterministic paper fill model, and emits
metrics that are useful for research without creating an execution request or
changing any operating mode.

The backtester is deliberately downstream of replay. It does not fetch data,
decode provider payloads, rebuild features, or label outcomes. The replay
harness remains the only path that turns normalized evidence into feature,
strategy and future-outcome projections.

## Acceptance criteria

- entry signals are selected only from advisory, fresh strategy snapshots with
  an explicit score/confidence threshold and `RiskDisposition.PASS`;
- exit policy evaluation is independent of entry policy selection and supports
  take-profit, stop-loss, rug/security, liquidity-collapse, creator-dump,
  paper-exit and horizon exits;
- every result identifies dataset, replay manifest, strategy, policy, fill
  model, config and artifact versions/hashes;
- fee and adverse slippage assumptions are bounded, explicit and reused from
  the paper `PaperFillModel` contract;
- unavailable baseline/future prices, non-fresh outcome evidence and unknown
  critical safety labels produce a skipped/unknown trade outcome, never a
  positive result;
- metrics include signal count, executed/ skipped count, precision/hit rate,
  expectancy, net PnL/return, max drawdown, profit factor and score-bucket
  calibration;
- results segment deterministically by launch venue, liquidity, token age,
  market regime, social velocity and smart-wallet confluence;
- future evidence is read only from the selected outcome horizon and is never
  used to select an entry or segment a signal;
- the artifact is deterministic JSON/CSV-safe data with protected modes and no
  secrets/raw provider payloads;
- no API, persistence, provider SDK, signer, wallet or transaction-submission
  dependency is introduced.

## Input and identity boundary

`BacktestHarness.run(result, policy)` accepts one immutable
`ResearchReplayResult`. The result's dataset digest and replay manifest are
copied into a `BacktestManifest`. A policy carries its own version and stable
config hash. The fill model identity is `paper-fill-v1`, the existing
`PaperFillModel.version`.

The policy pins one outcome horizon (default `24h`) and requires that horizon
to be present on every checkpoint. It also pins a deterministic notional,
fee/slippage rates and entry/exit thresholds. It cannot be constructed with
unsafe modes. A positive aggregate result never changes the protected
configuration:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Entry policy

For each replay checkpoint, the backtester considers only the checkpoint's
strategy snapshot. A signal is eligible for simulation when all of the
following hold:

1. the snapshot exists and is advisory;
2. the snapshot is `FRESH` at the checkpoint time and the checkpoint outcome
   has a valid baseline price;
3. score is at least `entry_score_threshold`;
4. confidence is at least `min_confidence`;
5. risk disposition is `PASS` and has no hard blocks;
6. the outcome horizon has sufficient, fresh future price evidence.

Otherwise a deterministic skip reason is recorded. A skip is not counted as a
win or loss and cannot improve metrics.

## Exit policy and fill arithmetic

Exit selection is independent of entry selection. The selected horizon is
examined for the earliest available policy event:

- configured take-profit multiple, using `time_to_multiple`;
- configured stop-loss fraction, using `time_to_drawdown`;
- configured safety exits (rug/security, liquidity collapse, creator dump and
  paper exit), when their label is explicitly true;
- horizon close, using `forward_return`, when no earlier policy event wins.

If a safety event has no usable price/return at its event boundary, the trade
is recorded as `UNKNOWN`/skipped rather than assigning a fabricated zero or
recovery price. A target exit uses the configured target multiple; a stop exit
uses `1 - stop_loss_fraction`; a horizon exit uses `1 + forward_return`. A
policy requiring an unknown safety label cannot silently treat it as false.

Entry and exit cash movements are simulated through the existing
`PaperFillModel`: entry is a BUY quote at the baseline price and exit is a SELL
quote at the selected exit price. The model applies fee and adverse slippage
to both legs. A fixed notional is used per independent signal; positions do
not compound and no overlapping trade may alter another signal's notional.

## Metrics

Metrics are calculated over simulated trades only, in deterministic signal and
checkpoint order:

- `signals`: eligible entry signals;
- `executed_trades`: trades with known, usable entry and exit prices;
- `skipped_signals`: eligible signals whose outcome cannot be safely priced;
- `wins`/`losses`, precision and hit rate;
- total/average net PnL and net return, and expectancy per executed trade;
- gross winning and losing PnL and profit factor;
- fixed-notional cumulative equity and maximum peak-to-trough drawdown;
- score-bucket count, wins, hit rate, mean net return and expectancy.

Ratios are `null` when their denominator is unavailable. This avoids treating
an empty or all-unknown sample as safe or profitable. `profit_factor` is also
`null` when no losing trade exists; an infinite ratio would overstate a tiny
or censored sample.

## Segmentation

Each signal receives a stable `BacktestSegmentKey` with:

- launch venue, liquidity band, token-age band and social velocity band from
  the replay cohort;
- smart-wallet confluence from the replay cohort;
- market regime derived only from the checkpoint's event-time correlation
  window: `positive`, `negative`, `flat` or `unknown`, based on known net flow.

Segment metrics use the same metric reducer as the overall result. No segment
is allowed to resample or re-label the dataset.

## Determinism and safety

Trade IDs are UUID5 values derived from dataset digest, checkpoint ID and
policy identity. Ordering ties use signal timestamp then checkpoint UUID.
JSON and CSV projections use canonical ordering and decimal strings. Secret-
shaped keys and non-finite values are rejected. The module imports only domain,
paper-fill and replay contracts; it must never import an external provider,
FastAPI, persistence, signer or execution submission implementation.

## Verification

Contract and unit tests cover profitable and losing trades, fee/slippage
impact, independent exit selection, unknown safety/price evidence, score
calibration, all required segmentation dimensions, deterministic artifact
hashes, empty samples, no-lookahead boundary preservation and protected mode
absence of execution authority. The focused tests run before the repository
quality gate, followed by the full `make verify` gate.
