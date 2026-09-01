# ADR 0002: analysis-only and paper-first execution boundary

- Status: Accepted
- Date: 2026-09-01

## Context

The product needs useful discovery, risk, scoring, alerting and position
research before any live-money capability is trusted. A mistaken provider,
stale observation or manipulated signal must not become an irreversible trade.

## Decision

The protected defaults remain:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Deterministic hard risk gates own execution eligibility. LLM narratives,
external labels, provider health and social or wallet signals are advisory or
corroborating evidence only. Paper orders and fills use a provider-free ledger.
Any future live transaction builder, signer or submitter must remain behind a
separate permission boundary and require the explicit Phase 12 gate.

## Consequences

All current routes, workers, research artifacts and sidecars can be tested
without signing or funds. Missing, stale, unknown or conflicting evidence
reduces quality or blocks safely. Live acceptance and manual operator review
remain real prerequisites, so local fixtures cannot claim production readiness.

## Alternatives rejected

- Enabling automatic execution after code exists would bypass the acceptance
  gates and is permanently out of scope for the current phase.
- Treating a successful provider response or an LLM recommendation as a safe
  trade signal would violate the evidence and replay model.
