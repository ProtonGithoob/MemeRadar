# Extension E8.4 — Stream Integrity and Protocol Verification Design

## Status

Approved for autonomous implementation on 2026-08-31 after Gate P8. This is a
provider-independent retrofit over the existing normalized observation,
provenance, protocol lifecycle and replay seams. It does not replace the
completed Phase 2 adapters or add a second event schema.

## Goal

Make Solana event ingestion auditable, restartable and repairable before Phase
9 paper-trading evidence depends on it. The extension separates transport,
protocol identity/decoding and completeness, while preserving one canonical
decoder path for live, backfill and replay traffic.

## Scope and acceptance criteria

- Add immutable domain contracts for commitment/finality, cursor progress,
  explicit stream gaps, recovery state, normalized chain events and range
  verification.
- Add an application orchestration seam for slot-gap detection, bounded
  backfill, durable normalized-event handoff, duplicate/conflict handling,
  restart/resume and observable backpressure.
- Add a versioned provider-local protocol registry keyed by
  `(program_id, discriminator_or_tag)`. Anchor discriminator derivation and
  native tags are explicit; unknown or unverified identities fail closed.
- Preserve the existing Pump.fun, PumpSwap, Raydium and Meteora parser behavior
  unless a concrete routing/correctness defect is found. Audit additional
  venues without silently claiming support.
- Normalize commitment progression and explicit revert/correction evidence;
  processed observations never masquerade as finalized evidence.
- Apply unresolved, unverified or conflicting stream evidence as a data-quality
  reduction only. Stream health can never raise AlphaScore or authorize
  `ENTRY_READY`.
- Persist cursors, gaps, verification runs and chain metadata on normalized
  observations with reversible migration(s), while keeping raw transport
  payloads bounded and out of the public read surface.
- Add deterministic keyless tests for the complete E8.4 matrix, including
  same-decoder live/backfill/replay equivalence and provider-independence.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`; no signer, execution port,
  AlphaScore authority or Rust/Yellowstone sidecar is introduced.

## Architecture

```text
transport envelope
      |
      v
cursor + gap detector -----> explicit gap/recovery state
      |
      v
versioned protocol registry
      |
      v
one canonical decoder/normalizer
      |
      v
normalized chain event -> durable observation/event log
      |                         |
      +--> feature/correlation/score (quality-aware)
      |
bounded backfill -> same decoder -> verification/reconciliation
```

The application module owns transport-neutral raw envelopes, orchestration
ports and deterministic state-machine behavior. The provider module owns
concrete protocol registry definitions and adapts the existing launchpad/DEX
parser behind a canonical decoder. The domain module owns immutable evidence
contracts and has no provider or persistence imports. Persistence implements
the application state-store port and never becomes a decoding dependency.

Live, RPC backfill and replay entry points all call the same decoder method.
Only transport/provenance metadata differs. The canonical event identity uses
chain, transaction signature, event index and verified protocol instruction
identity; equivalent live/recovered deliveries merge provenance, while
materially different normalized payloads retain a conflict rather than
silently replacing evidence.

## Reliability state model

`ChainCursor` stores observed, contiguous and finalized progress separately.
Observed progress may move forward with out-of-order events, but contiguous
progress advances only through durably appended slots and never crosses an
open/recovering gap. Finalized progress is monotonic and cannot exceed
contiguous progress. A persisted cursor is loaded on restart before ingest
continues.

`StreamGap` records every detected missing range. Slot discontinuity and
reconnect/resume boundaries are distinct detection methods. Overlapping or
adjacent ranges merge deterministically and retain member IDs. Recovery is
bounded and resumable: `OPEN -> RECOVERING -> RECOVERED -> VERIFIED`, with
explicit `FAILED` or `SUPERSEDED` outcomes. Skipped/non-produced Solana slots
are represented by the backfill result's produced-slot set and are not false
gaps.

Recovered events retain original occurred slot/signature plus source transport,
backfill source, parser/registry versions, observed/ingested/recovery times,
commitment and recovery state. Successful fetch is not verification. A range
becomes verified only when expected produced blocks/relevant events and
persisted normalized events reconcile without missing, extra or conflicting
identities.

The durable handoff is bounded. Saturation raises an explicit backpressure
error and increments telemetry; it never drops an event or advances a cursor
as if the event were persisted. Duplicate live/recovered observations are
idempotent; conflicting observations preserve the first normalized evidence
and attach a conflict record/state for later correction.

## Protocol identity and registry

`ProtocolIdentityRegistry` maps a full `(program_id, discriminator_or_tag)`
key to one immutable entry. The registry records protocol, program kind,
instruction/tag, account discriminators where applicable, supported event
types, decoder version, registry version, verification state, verification
date and sources. Anchor values are independently derived as the first eight
bytes of `sha256("global:<name>")` / `sha256("account:<name>")`; native values
are explicit protocol tags and are never presented as Anchor hashes.

Production protocol entries whose authoritative identity is not independently
verified remain `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` and cannot route
authoritative evidence. Keyless tests use clearly synthetic, fixture-only
verified identities. The audit classifies Pump.fun, PumpSwap, Raydium AMM v4,
Raydium CPMM/CLMM/LaunchLab, Meteora DLMM/DAMM v2/DBC/Believe, Orca
Whirlpools and Moonshot as supported/reverify, planned or out of scope; it
does not auto-implement missing adapters or rewrite completed Phase 2 code.

## Commitment, quality and replay

The normalized event carries `PROCESSED_UNCONFIRMED`, `CONFIRMED`,
`FINALIZED`, `REVERTED` or `UNKNOWN`. Commitment updates are monotonic except
for explicit `REVERTED` correction evidence. A revert retains the earlier
observation and emits an append-only correction projection. The replay
identity includes parser version, protocol registry version, event schema
version, strategy/config identity and source provenance. Historical replay
uses persisted normalized evidence and the same canonical decoder; it has no
provider dependency or future-data access.

Stream integrity is fed into feature quality as `StreamQualityImpact`. Open or
unverified ranges intersecting a feature boundary reduce completeness and
confidence and make critical evidence non-fresh/unknown. Verified recovery may
restore completeness without erasing recovery provenance. Healthy transport is
neutral and contributes no score points. Unknown protocol, decoder conflict,
revert or unresolved gap is fail-closed for affected evidence.

## Persistence and telemetry

The existing append-only `observations` table gains nullable chain metadata;
dedicated `chain_cursors`, `stream_gaps` and `stream_verifications` tables
retain progress and reconciliation history. Migration `0005_stream_integrity`
is reversible and metadata parity remains enforced. No raw chain payload table
is added in this slice; a future retention decision may add one only with a
bounded redaction policy.

The in-memory telemetry implementation exposes counters for reconnects, gaps,
missing slots, backfill attempts/success/failure, duplicates, live/recovered
conflicts, malformed/unsupported/decoder-conflict events, verification
outcomes, reverts and queue saturation. Backfill latency/retries/rate limits
are retained as safe metrics. No credential or unbounded provider response is
logged.

## Testing and safety gate

Tests use synthetic envelopes and a fake bounded backfill port. They cover
contiguous/overlapping/skipped ranges, restart, duplicate/conflict recovery,
timeouts/rate limits, backpressure, commitment progression/revert, registry
routing/collision/unknown identities, same-decoder replay and deterministic
no-lookahead quality impact. Boundary scans prove domain/application modules
do not import provider SDKs, FastAPI, SQLAlchemy or execution/signing code.

Reference implementations were studied for architectural patterns only. No
upstream code is copied; the repository's reuse registry and license note are
retained as references. Yellowstone/Rust remains expressly deferred until
E11.1 measures a material bottleneck or reliability benefit.
