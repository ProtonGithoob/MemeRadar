# Phase 9 Sprint 9.2 Exit Engine Design

## Goal

Build a deterministic, evidence-bearing paper exit evaluator for open
positions. It must cover protective price rules, profit management, correlated
distribution/liquidity/flow/score/time deterioration and configured partial
exits without adding signing, live execution or hidden strategy state.

## Scope and invariants

Sprint 9.2 implements the six core Phase 9.2 roadmap items and the keyless
portion of the approved E9.4 exit-correlation extension:

- fixed stop loss and take profit;
- trailing stop and break-even activation;
- smart-money/creator/related-wallet distribution evidence;
- liquidity decay, quote deterioration and buy-velocity/sell-pressure collapse;
- score-degradation and time-stop rules;
- configured partial take-profit sizing.

The protected modes remain constructor/runtime invariants:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

The engine returns a recommendation and an explainable `ExitRiskScore`. It
does not submit a paper order itself, change `Position` state, change
AlphaScore, clear risk, or authorize a transaction. A caller may pass the
recommendation to the existing paper order boundary only after independently
constructing a normalized sell quote and decision reference.

## Provider-independent evidence contract

`ExitEvidenceSnapshot` is an immutable application value object. It carries an
event/observation time, freshness/quality, source/provenance and bounded
evidence references plus current price, liquidity, buy velocity, sell pressure,
distribution, score and quote deterioration measurements. Micro and macro flow
values are explicit fields; derived ratios are calculated only from values in
the snapshot and its immediately supplied prior snapshot. An external wallet
distribution value can add corroborating evidence but cannot trigger an exit
alone.

Missing, stale, conflicted or invalid price evidence yields an explicit
`UNKNOWN` evaluation. Missing optional corroborating families reduce confidence
and add reason codes; they do not become positive or negative facts by default.
The stream-integrity state is quality evidence only and never raises the exit
score.

## Rule policy and score

`ExitRulePolicy` is versioned and config-hashed. It validates bounded basis-point
thresholds, time limits, pressure/decay ratios, score floors/deltas and a
deterministic ordered take-profit ladder. A ladder level has a stable key,
trigger profit in basis points and exit fraction. Already-consumed level keys
are supplied in the evaluation context and are not held in process memory;
partial exits therefore remain restart/replay deterministic.

The independent `ExitRiskScore` contains bounded components, confidence,
quality, reason codes, evidence references, policy/config identity and the
recommended action/fraction. It is not an AlphaScore adjustment. Protective
stop, invalidation, severe quote/liquidity failure and explicit time-stop rules
can recommend `CLOSE`; profit levels and ordinary deterioration recommend
`REDUCE` according to the policy. Multiple triggers are unioned in stable rule
order and the strongest action wins.

## Timeline and paper handoff

An `ExitEvaluation` records the before/after evidence references, rule keys,
score and optional `ExitSignal`. The evaluation is append-oriented and can be
persisted through an application port; the in-memory implementation is used by
keyless replay/tests, while SQL callers can use the existing domain-event and
audit persistence boundary. No raw provider response is required or exposed.

The paper handoff remains explicit: an exit signal is converted to a sell
`PaperOrderRequest` by the caller with a fresh normalized quote. The paper
ledger remains the sole cash/position mutation path, so duplicate requests,
stale quotes and over-sells retain Sprint 9.1 fail-closed behavior.

## Acceptance

Keyless tests cover fixed SL/TP, trailing and break-even rules, partial
take-profit ladders, distribution/creator/holder evidence, micro/macro
velocity and sell-pressure deterioration, liquidity/quote decay, score/time
exits, missing/stale/invalid evidence, external-only non-trigger behavior,
stable reason/evidence ordering, restart-safe consumed-level context,
event-time/no-lookahead evaluation, deterministic replay and protected paper
boundaries. All live market/execution acceptance remains `BLOCKED_EXTERNAL`.
