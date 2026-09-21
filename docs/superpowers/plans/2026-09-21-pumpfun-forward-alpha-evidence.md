# Pump.fun forward alpha evidence collection

## Goal

Turn the existing verified Pump.fun launch stream into a durable, unbiased,
event-time research dataset without changing the decoder, detector, score
thresholds, or execution modes.

## Constraints

- Reuse the canonical `chain.event` launch observations and existing runtime,
  outbox, repository, and report contracts.
- Use one bounded polling loop, not one unbounded task per mint.
- Persist UNKNOWN when a provider has no observation; never infer market data.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, and `AUTO_EXECUTION=false`.
- The pinned Pump.fun IDL remains production-only and is never auto-updated.

## Tasks

1. Add failing unit tests for the bounded forward schedule, exact-mint lead
   calculation, UNKNOWN Dex observations, report denominators, and the
   non-destructive protocol drift command.
2. Implement the smallest forward-evidence domain helpers and a single worker
   loop that durably records DexScreener exact-mint polls, immutable market
   snapshots, horizon outcome checkpoints, and creator-history evidence.
3. Make the initial DISCOVERED snapshot contain the existing feature, safety,
   score, and version evidence; extend raw-stream counters and persist health
   observations without creating another ingestion path.
4. Add a reproducible database report and the read-only upstream drift check;
   cover funnel, lead, maturity, outcome, missed-winner, false-positive,
   Telegram timing, and protected-mode status fields.
5. Run focused tests, full quality gates, the pinned upstream check, and a
   bounded live-shadow verification. Update `docs/STATUS.md`, commit, and
   push the evidence.

## Acceptance evidence

- Every verified create/create_v2 launch remains queryable from the canonical
  launch observation and initial stage snapshot.
- Dex first-observation timestamps and lead seconds are based on MemeRadar's
  own exact-mint query timestamps.
- Future-only outcome rows are horizon-gated and do not label unavailable or
  non-executable values.
- Health and report rows are reproducible from durable observations.
- Protocol drift is reported explicitly and cannot change production decoding.
