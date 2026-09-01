# Phase 11 / Sprint 11.1 — Reliability and Latency Measurement Design

## Status

Approved for autonomous implementation on 2026-09-01. This sprint hardens the
existing provider-independent stream, outbox and persistence seams. It does not
add a second ingest path, alter protected modes or introduce a Rust/Yellowstone
sidecar.

## Goal

Make analysis-only operation diagnosable and restartable under transient stream,
provider, queue and database failures, while measuring the hot path before any
optimization or service extraction decision.

## Scope and acceptance

- Add bounded, redaction-safe percentile histograms for the six E11.1 latency
  stages: `chain_event_to_ingest_ms`, `social_event_to_ingest_ms`,
  `ingest_to_feature_ms`, `feature_to_decision_ms`,
  `chain_event_to_decision_ms` and `candidate_to_alert_ms`.
- Retain provider-labelled counters for reconnects, fallbacks, duplicates,
  conflicts, malformed drops, rate limits, timeouts, retries and queue
  saturation. Existing E8.4 stream counters remain the canonical names for
  stream-integrity events.
- Provide deterministic local contracts for reconnect/fallback, rate-limit,
  bounded outbox retry/dead-letter and database restart behavior. No external
  provider PASS is inferred from these tests.
- Provide an analysis-only benchmark artifact with p50/p95/p99, sample counts,
  provider/network versus internal attribution and an explicit dominant
  bottleneck. SLOs are not declared until measured evidence exists.
- Document current retention/index posture and a safe backup/restore runbook.
  Backup restoration is performed only into an isolated target and never
  deletes or overwrites the source database.
- Keep the existing canonical decoder, durable cursor/gap state and outbox
  contracts intact. Reliability telemetry is observational and can never raise
  AlphaScore or create `ENTRY_READY`.

## Design

`ReliabilityMetrics` is an in-memory, bounded collector in the application
layer. It accepts only allow-listed metric names and normalized provider/source
labels, keeps a fixed number of latency samples per histogram and returns a
deterministically ordered immutable snapshot. Percentiles use the nearest-rank
definition over sorted retained samples. Eviction is counted explicitly so a
bounded collector cannot silently claim complete history.

Provider adapters receive the collector through an optional structural
telemetry port. They report only classified outcomes (for example `rate_limit`
or `dropped_malformed`) and never raw response bodies, URLs, credentials or
exception text. The transport reports transient failures and retries; stream
consumers report reconnects, fallback use and malformed drops; the outbox
processor reports delivery/retry/dead-letter latency and counters.

The benchmark uses synthetic, provider-free samples and labels its method
explicitly. Its output includes the protected modes and `BLOCKED_EXTERNAL`
for live acceptance. Synthetic evidence is a measurement seam, not a provider
health assertion.

## Failure and safety behavior

- Bounded queues raise explicit backpressure errors and increment saturation;
  events are never silently dropped.
- Provider timeouts/rate limits remain classified and bounded by the existing
  retry/circuit policies.
- Database restart tests reopen the same durable store and verify that pending
  outbox truth survives connection/process loss.
- Missing credentials or provider access remain `BLOCKED_EXTERNAL`.
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and
  `AUTO_EXECUTION=false` are asserted by tests and tooling.

## Non-goals

- No live-money execution, signing, credential provisioning or mode change.
- No production SLO claim before baseline measurement.
- No deletion/retention job, physical table partition or destructive restore
  operation in this sprint; the review and runbook define safe follow-up work.
- No Rust/Yellowstone extraction. E11.2 remains conditional on measured need.
