# Phase 7 / Sprint 7.1 — Alert Pipeline

## Objective

Complete the Telegram-first, analysis-only alert path around the existing
decision events and durable outbox. Alerts must be explainable, deduplicated,
rate-limited and retryable without coupling domain/application logic to
Telegram or allowing notification state to authorize execution.

## Acceptance criteria

- `NotificationPort` has a keyless fixture implementation and a bounded,
  HTTPS-only Telegram Bot API adapter using `sendMessage`/`getMe`.
- Provider responses classify authentication, rate-limit, timeout, transport
  and schema failures without persisting response bodies, tokens or raw error
  text.
- Decision/risk/provider-health events project to typed `Alert` records only
  for meaningful operator changes; alert text is deterministic, concise,
  reason/evidence-bearing and safely bounded.
- Alert persistence preserves the existing `alerts` table contract and
  deduplicates equivalent alert requests by `dedupe_key`.
- Delivery runs through the existing leased outbox processor, retries
  transient failures, honors bounded retry timing, suppresses noisy duplicates
  and rate-limits per destination without blocking candidate processing.
- Provider/system degradation alerts are explicit and do not claim provider
  health when health is `UNKNOWN` or unavailable.
- Fixture replay, provider contracts, persistence integration and Compose
  smoke checks pass with all four protected modes unchanged.

## Implementation sequence

1. Add red domain/application tests for suppression, renderer/projector,
   dedupe/rate-limit behavior and outbox retry timing.
2. Implement the provider-independent alert projector, renderer, policy,
   limiter and delivery handler.
3. Add `AlertRepository`/UoW wiring and Telegram plus fixture adapters.
4. Add provider doctor/configuration and keyless replay/runtime contracts.
5. Run focused checks and the full quality gate, reconcile docs/status, commit
   and push the checkpoint.

## Protected modes

The alert path remains `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`. Notifications are external
side effects only; they cannot transition candidates, clear risk, invoke an
execution port or sign transactions.
