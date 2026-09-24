# Stream-gap root-cause report — 2026-09-24

## Verdict

The reported `1408` value was a measurement bug in the prior Pump.fun health
projection, not evidence that 1408 relevant Pump.fun launches were missed.
The old health row used schema `pumpfun-ingestion-health-v1` and merged all
durable stream gaps into a program-filtered logs subscription. Commit
`af97de1` removed that merge and made the current schema explicit:
`program_mentioned_logs_subscription` plus
`EXPLICIT_RELEVANT_EVENT_GAP_ONLY`.

The current code now also preserves reconnect markers, bounded recovery
results, and unresolved state. A real before/after acceptance count remains
`BLOCKED_EXTERNAL` because the host Docker socket is inaccessible and no live
database was available in this session.

The local verification after the implementation passed `1463` tests with
`21` skips and `79%` total coverage. This validates the contracts and replay
path, not a live unresolved-gap rate.

## Evidence from the checked-in run

The previous artifact `artifacts/research/pumpfun-forward/report.json` had:

| Signal | Value | Interpretation |
| --- | ---: | --- |
| notifications received | 1158 | program-filtered WebSocket notifications |
| launches observed | 1 | one `create_v2` in the health sample |
| stream reconnects | 1 | connection-attempt counter, including initial connect |
| stream errors | 0 | no source-level transport error recorded |
| transactions unavailable | 0 | no launch-shaped HTTP fetch missed |
| get-transaction retries | 0 | no indexing-race retry |
| rate-limit responses | 0 | no provider throttling observed |
| dropped events | 0 | bounded queue did not drop |
| queue depth max | 2 | far below queue capacity 256 |
| old `stream_gaps` | 1408 | invalid global-slot/merged-gap health measurement |

These counters do not identify a provider outage, queue overflow, RPC 429, or
transaction-indexing delay. The only supported root cause for the 1408 figure
is the old scope mismatch: a sparse program-scoped stream was compared to
global slot continuity and/or all stream-integrity rows.

## Bounded recovery changes

- `StreamGap` now exposes durable extension fields for start/resolution,
  missed slot range, provider, connection, reconnect reason, backfill status,
  recovered events, and unrecoverable-event unknowns.
- Alembic `0012_stream_gap_diagnostics` backfills the new fields from the
  existing gap state without changing event identity or cursor semantics.
- `SolanaRpcBackfillAdapter` uses finalized `getBlocks` and full-transaction
  `getBlock` reads, then calls `map_transaction_to_raw_events`, the same raw
  Pump.fun decoder used by the live WebSocket path.
- The early worker invokes the existing coordinator recovery path when a
  bounded backfill port is configured. A failed/incomplete verification keeps
  the gap non-verified and therefore fail-closed.
- Ordinary program-scoped slot jumps still create no gap. Only an explicit
  reconnect marker can create `RECONNECT_BOUNDARY` in that mode.

## Cause matrix

| Candidate cause | Local evidence | Status |
| --- | --- | --- |
| Public RPC limits | rate-limit counter was 0 in the artifact | not indicated by the 1408 value |
| WebSocket reconnects | one initial connection attempt; no stream error | not proven as loss |
| Queue overflow/backpressure | dropped 0; max depth 2/256 | ruled out for the artifact window |
| Cursor/checkpoint logic | old health merged unrelated gaps; current cursor is durable | root cause of the metric scope error |
| Slot discontinuity | invalid when applied to sparse program logs | root cause of old false inference |
| Transaction indexing delay | unavailable/retries both 0 | not indicated |
| Provider throttling | 429 counter 0 | not indicated |
| Worker backpressure | no dropped raw events | not indicated |
| Dex enrichment latency | separate forward scheduler, not stream transport | not a stream-gap cause |

## Acceptance still outstanding

The target `unresolved gaps ≈ 0` is not claimed. It requires a bounded
PostgreSQL/Compose run with a real configured stream, a forced/reproduced
reconnect, finalized backfill, and a persisted `VERIFIED` gap plus zero active
unresolved gaps. The local contract suite covering the new paths is green;
the runtime evidence is blocked by Docker access, not silently treated as
success.
