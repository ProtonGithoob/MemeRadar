# Phase 6 / Sprint 6.3 — Decision State Machine

## Objective

Complete the provider-independent decision layer that consumes immutable
`ScoreSnapshot` and `RiskAssessment` values and produces idempotent candidate
lifecycle transitions up to `ENTRY_READY`. The layer must remain advisory and
must never open a position or authorize execution.

## Acceptance criteria

- Map score, confidence, score freshness and risk evidence to `WATCH`,
  `STRONG_SETUP`, `ENTRY_READY` or fail-closed `RISK_REJECTED` transitions.
- Reapply the hard risk and critical freshness gates even when a score is high.
- Use explicit, versioned thresholds, confidence minimums, hysteresis floors,
  cooldowns and protected operating modes.
- Hold state inside hysteresis bands and suppress repeated transitions during a
  cooldown without mutating the candidate.
- Emit deterministic score-delta and risk-escalation events with reason codes,
  timestamps, snapshot references and config identity.
- Project candidate transitions, normalized events and score/risk/feature
  evidence into a deterministic chronological timeline using occurred time,
  observed time and ingested time as separate fields.
- Reject candidate/reference/config/future-time mismatches and preserve
  `UNKNOWN`, `STALE`, `CONFLICTED` and `INVALID` as unsafe quality states.
- Demonstrate identical decisions, transitions and event identities from
  identical inputs/configuration, including reversed event delivery order.
- Keep the application module free of provider SDK, persistence and execution
  imports; retain all four protected modes.

## Implementation sequence

1. [x] Add unit and contract tests for policy validation, upward/downward mapping,
   fail-closed risk, hysteresis, cooldown, deterministic events and timeline
   ordering.
2. [x] Implement the immutable decision result/policy and candidate application
   seam, with stable transition/event identities.
3. [x] Implement the full evidence timeline projection and replay fixtures.
4. [x] Run focused tests, lint/type checks and the Phase 6 quality gate.
5. [x] Reconcile roadmap, architecture, scoring/security/testing documentation and
   `docs/STATUS.md`, then commit and push the coherent checkpoint.

## Completion evidence (2026-08-31)

- `15` decision unit/contract tests pass; `23` Compose smoke tests pass.
- `make typecheck` passes with mypy reporting `57 source files`.
- `make verify` passes with `378 passed, 3 skipped`, branch-aware coverage
  `80%`, frontend checks, secret scan and migration parity at
  `0003_score_strategy_identity` / 13 tables.
- The opt-in Postgres integration suite passes `3 tests`, including stable
  decision transition persistence and multi-transition candidate rehydration.
- No provider, persistence or execution dependency was added to the decision
  module; protected modes remain analysis-only/paper-only with execution
  disabled.

## Safety and blockers

The implementation does not enable live providers or trading. Missing external
credentials remain `BLOCKED_EXTERNAL`; keyless replay and contract acceptance
must remain complete. The decision layer may recommend `ENTRY_READY`, but
`PAPER_OPEN`, live approval, signing and execution remain separate later
workflow boundaries.
