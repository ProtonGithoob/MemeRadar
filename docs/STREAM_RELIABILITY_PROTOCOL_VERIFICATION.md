# Stream Reliability and Protocol Verification Extension

## Purpose

This document captures the high-value patterns from the latest Solana streaming/indexer research and converts them into MemeRadar-specific implementation requirements.

This is an accepted supplementary specification. It does not invalidate completed phases and must not interrupt the currently active Phase 8 dashboard work. Codex/Kimi must finish the current Phase 8 sprint and Gate P8 first, then implement this extension before Phase 9 paper-trading work unless the repository has already advanced beyond that point. If the repository is already beyond Phase 8, implement the missing items at the next safe backend hardening checkpoint without rewriting completed behavior.

The reference patterns come from:

- `shaurya35/solana-realtime-indexer` — durable slot progress, independent gap detection, RPC backfill, verification and a shared live/replay decoder path.
- `mahfuz67/solana-stream-skill` — transport abstraction, verified Solana program-ID/instruction-discriminator registry, Anchor-vs-native decoding rules, protocol coverage and explicit reorg/commitment handling.

Do not blindly copy upstream code. Preserve MemeRadar's provider-independent architecture and verify license compatibility before any code reuse. MIT-licensed reference material may still be reimplemented where that better preserves the current architecture.

---

## 1. Architectural decision

MemeRadar must distinguish three concerns that are currently easy to conflate:

1. **Transport** — how Solana events arrive: Helius WebSocket/webhook, Yellowstone gRPC, LaserStream-compatible endpoint, QuickNode/Triton Yellowstone, standard RPC/WebSocket, or future Jito ShredStream.
2. **Protocol decoding** — how a transaction/instruction/account becomes a Pump.fun, PumpSwap, Raydium, Meteora, Orca, LaunchLab, Moonshot or other normalized protocol lifecycle event.
3. **Reliability/completeness** — whether the observed stream has gaps, whether gaps were repaired, and whether repaired data agrees with canonical chain data.

These layers must remain independently replaceable.

Target data path:

```text
Solana transport
    |
    v
slot/signature checkpoint
    |
    v
protocol decoder registry
    |
    v
normalized protocol event
    |
    +--> durable event log
    |
    +--> gap detector
    |       |
    |       v
    |   missing-slot range
    |       |
    |       v
    |   RPC/LaserStream backfill
    |       |
    |       v
    |   SAME decoder pipeline
    |       |
    |       v
    |   reconciliation/verification
    |
    v
existing MemeRadar correlation/micro-features/AlphaScore
```

A recovered event must pass through the same normalization and decoding path as a live event. Do not create a second 'backfill decoder'.

---

## 2. Execution timing

Current repository status on 2026-08-31 reports `PHASE_8_SPRINT_8_1_COMPLETE_KEYLESS_PASS`, with Sprint 8.2 next.

Execution rule:

- Do not interrupt Sprint 8.2 or 8.3 to retrofit backend streaming reliability.
- Finish Phase 8 and Gate P8 first.
- Then implement this specification as **Extension E8.4 — Solana Stream Integrity and Protocol Verification**, before Phase 9.
- If local repository state has advanced beyond Phase 8, do not roll back. Insert E8.4 at the next safe backend checkpoint before relying on real-time paper-trading signals.

Reason: Phase 9 paper trading depends on reliable event chronology. Missing or incorrectly decoded on-chain events would contaminate simulated entry/exit results and later Phase 10 calibration.

---

## 3. Extension E8.4 — Solana Stream Integrity and Protocol Verification

### Goal

Make Solana ingestion auditable, replayable and repairable so MemeRadar can distinguish:

- no event occurred;
- an event occurred but was not observed yet;
- stream data is incomplete;
- an event was recovered by backfill;
- a recovered event conflicts with previously normalized evidence;
- a protocol decoder is unknown/unverified;
- an event came from unconfirmed/pre-confirmation transport and may be reverted.

### 3.1 `ChainCursor` / progress model

Add a provider-independent progress contract. Suggested fields:

```text
chain
transport
stream_id
commitment
last_observed_slot
last_contiguous_slot
last_finalized_slot
last_signature? 
updated_at
parser_registry_version
```

Requirements:

- persistence-backed;
- monotonic for contiguous/finalized progress;
- transactionally consistent with durable normalized event writes where practical;
- must not advance a durable contiguous marker past an unrecorded gap;
- duplicate observations are idempotent;
- out-of-order observations do not incorrectly move contiguous progress;
- restart resumes from persisted progress, never from an in-memory assumption.

### 3.2 Independent gap detection

Implement at least two independent gap-evidence paths when the chosen transport exposes enough information:

1. slot-sequence discontinuity detection;
2. provider/reconnect/resume boundary detection or periodic canonical slot-range comparison.

Normalized gap record:

```text
id
chain
transport
from_slot
to_slot
detected_at
detection_method
status: OPEN | RECOVERING | RECOVERED | VERIFIED | FAILED | SUPERSEDED
attempt_count
last_error_class?
recovered_event_count?
verified_event_count?
```

Do not store raw secrets/error payloads.

Overlapping/adjacent gaps should be deterministically mergeable without losing provenance.

### 3.3 Backfill port

Add a provider-independent `ChainBackfillPort`.

The first implementation may use standard Solana RPC or a documented replay-capable provider already approved in MemeRadar.

Preferred canonical flow:

```text
getBlocks(from_slot, to_slot)
for each produced slot:
    getBlock(slot)
    -> raw chain envelope
    -> SAME protocol decoder used by live traffic
```

Reason: querying the actual produced block set avoids treating skipped/non-produced slots as missing data.

Requirements:

- bounded concurrency;
- bounded ranges;
- timeout/retry/rate-limit policy;
- no silent drop when a processing queue is full;
- backpressure is preferred over completeness loss;
- every recovered event is marked with recovery provenance while retaining its original chain `occurred_at`/slot/signature;
- recovery is idempotent by canonical event identity;
- recovered data cannot directly grant execution authority.

### 3.4 Verification / reconciliation

Add `StreamIntegrityVerifier` or equivalent application service.

It must be able to compare a slot range against durable normalized chain events and report:

```text
expected_blocks
fetched_blocks
expected_relevant_events
persisted_relevant_events
missing_event_ids
extra_event_ids
conflicting_event_ids
verification_status
```

Statuses:

- `PASS`
- `INCOMPLETE`
- `CONFLICTED`
- `BLOCKED_EXTERNAL`
- `FAIL`

Do not call a range `PASS` merely because the backfill job returned successfully.

A gap may become `VERIFIED` only after reconciliation confirms completeness under the currently supported protocol/decoder registry.

### 3.5 Unified live/capture/replay/repair path

Implement or preserve one canonical decoder/normalizer pipeline usable from:

- live transport;
- recorded fixture/JSONL replay;
- RPC block backfill;
- repair/rebuild from stored raw envelopes where raw retention policy permits.

The following must produce logically equivalent normalized events for the same transaction and parser version:

```text
live_decode(tx) == replay_decode(tx) == backfill_decode(tx)
```

Add golden tests to enforce this.

---

## 4. Verified protocol identity registry

Create an internal, versioned registry for Solana programs and instruction/account discriminators used for protocol detection.

Suggested implementation location:

- provider package data/config for concrete program identities;
- application-visible immutable registry metadata/version;
- no protocol IDs hard-coded throughout business logic.

Suggested record:

```text
protocol
program_id
program_kind: ANCHOR | NATIVE
instruction_name
instruction_discriminator_or_tag
account_discriminators?
verification_status
verified_at
verification_sources[]
registry_version
```

### Mandatory rule: match program ID AND discriminator

Instruction discriminator alone is not unique across the ecosystem. Examples from independently checked reference material include shared Anchor discriminators such as `initialize_pool` and `create_pool` across different programs.

Therefore decoder routing must always key on:

```text
(program_id, discriminator/tag)
```

Never on discriminator alone.

### Anchor vs native rule

For Anchor programs:

```text
instruction discriminator = first 8 bytes of sha256("global:<instruction_name>")
account discriminator     = first 8 bytes of sha256("account:<AccountName>")
```

For native programs, use the protocol's native enum/u8 tag/serialization contract. Never fabricate an 8-byte Anchor discriminator for a native program.

### Verification workflow for every registry entry

Before marking an entry `VERIFIED`:

1. obtain current IDL/decoder/official program documentation or another authoritative source;
2. classify the program as Anchor or native;
3. independently derive the discriminator/tag when derivation is possible;
4. cross-check program identity against recent real chain transactions or authoritative explorer data;
5. record verification date and evidence source;
6. add a keyless fixture proving the intended transaction/instruction routes to the expected protocol decoder.

If any step cannot be completed:

```text
verification_status = TODO_VERIFY
```

and the value must not be treated as authoritative merely because a third-party README lists it.

---

## 5. Initial protocol coverage audit

Audit the existing `launchpad_dex.py` / protocol parser implementation against the versioned registry.

Required coverage audit targets:

- Pump.fun;
- PumpSwap;
- Raydium AMM v4;
- Raydium CPMM;
- Raydium CLMM;
- Raydium LaunchLab / LetsBonk migration path;
- Meteora DLMM;
- Meteora DAMM v2;
- Meteora DBC / Believe migration path;
- Orca Whirlpools;
- Moonshot migration path.

Do not automatically implement all venues if the product roadmap does not need them yet. The audit output must classify each as:

- `SUPPORTED_VERIFIED`;
- `SUPPORTED_NEEDS_REVERIFY`;
- `NOT_SUPPORTED_PLANNED`;
- `NOT_SUPPORTED_OUT_OF_SCOPE`.

Pump.fun/PumpSwap/Raydium/Meteora functionality already completed in Phase 2/E2.5 must be preserved rather than rewritten unless the audit exposes a real defect.

---

## 6. Commitment and reorg semantics

Normalized chain evidence must expose commitment/finality when known.

Suggested states:

- `PROCESSED_UNCONFIRMED`
- `CONFIRMED`
- `FINALIZED`
- `REVERTED`
- `UNKNOWN`

Rules:

- pre-confirmation/processed observations may contribute to low-latency diagnostics but must carry reduced confidence;
- an observation later missing/replaced due to fork/reorg must become explicit `REVERTED`/superseded evidence rather than silently disappearing;
- finalized confirmation may increase evidence confidence but must not override risk hard gates;
- future Jito ShredStream support is diagnostic/early-signal only until a later confirmed/finalized observation corroborates it;
- paper/live decisions must preserve which commitment state was visible at decision time for replay.

---

## 7. Transport abstraction

The existing Helius/provider abstractions remain valid. Extend them only where needed so a future stream source can be swapped without changing correlation/scoring code.

Candidate transport capabilities:

```text
HELIUS_WEBSOCKET
HELIUS_LASERSTREAM
YELLOWSTONE_GRPC
QUICKNODE_YELLOWSTONE
TRITON_YELLOWSTONE
SOLANA_WEBSOCKET
SOLANA_RPC_BACKFILL
JITO_SHREDSTREAM_PRECONFIRMATION
```

No provider name belongs in domain scoring logic.

Yellowstone/Rust remains conditional on measured need under E11.1/E11.2. This E8.4 work must make the reliability contracts usable from the current Python/provider stack first.

---

## 8. Data quality integration

Introduce stream-integrity quality into feature confidence without turning transport health into a trading signal.

Examples:

- unresolved gap intersects a feature window -> that chain-derived feature window cannot be considered fully `FRESH`;
- repaired but not verified gap -> `RECOVERED_UNVERIFIED` diagnostic / reduced confidence;
- verified repaired gap -> data may become complete again, but provenance still records recovery;
- decoder registry entry `TODO_VERIFY` -> affected protocol evidence is `UNKNOWN` or reduced-confidence, never authoritative;
- conflicting live vs backfill decode -> `CONFLICTED`, requires investigation/reconciliation.

An unresolved integrity problem can reduce confidence or block execution eligibility where critical, but integrity health itself never raises AlphaScore.

---

## 9. Persistence requirements

Add migrations only if the existing event/observation schema cannot represent the required data cleanly.

Likely persistent entities:

- `chain_cursors`;
- `stream_gaps`;
- `stream_verifications` or compact verification-run records;
- optional `raw_chain_envelopes` only if justified by retention/cost policy;
- protocol registry may be code/config-backed rather than mutable DB state, but registry version must be persisted with normalized events/replay metadata.

Required indexes should support:

- chain + slot;
- open gap ranges;
- signature/event identity;
- verification status/time;
- replay by slot/token/protocol.

All migrations must be reversible and migration/metadata parity tests must continue to pass.

---

## 10. Telemetry

Add metrics/log fields for:

- current observed slot;
- last contiguous slot;
- slot lag;
- open gap count;
- oldest open gap age;
- recovered slots/events;
- verification pass/incomplete/conflict counts;
- decoder unknown-program/unknown-discriminator counts;
- live vs backfill duplicate count;
- live vs backfill conflict count;
- reorg/reverted event count;
- backfill RPC latency/rate-limit/retry counts.

Do not log raw credentials, full provider responses or unbounded transaction payloads.

These measurements later feed E11.1 latency/reliability SLO work.

---

## 11. Keyless test matrix

At minimum add deterministic tests for:

1. contiguous slot sequence — no false gap;
2. missing range — one exact gap;
3. overlapping detections — deterministic merge;
4. skipped/non-produced Solana slot — not treated as missing block;
5. restart from persisted cursor;
6. live duplicate after recovered event — idempotent;
7. live event conflicts with recovered normalized event — `CONFLICTED`;
8. backfill timeout/rate limit — bounded retry and resumable gap;
9. queue/backpressure — no silent event loss;
10. backfill uses the same decoder as live;
11. replay ordering remains deterministic;
12. Anchor discriminator derivation fixture;
13. native-program tag fixture;
14. discriminator collision across two program IDs routes correctly;
15. unknown program/discriminator fails closed;
16. processed -> confirmed -> finalized progression;
17. simulated reverted/forked observation;
18. no execution/signing/provider-SDK dependency enters domain/application scoring layers.

---

## 12. Acceptance gate E8.4

E8.4 is complete keylessly only when:

- stream cursor persistence works across restart;
- gap detection and deterministic merging pass;
- a synthetic missing-slot range is recovered through `ChainBackfillPort`;
- recovered data passes through the exact same protocol decoder path as live data;
- verification proves expected vs persisted event equivalence for the fixture range;
- protocol identity registry is versioned and tested;
- discriminator collision test proves routing requires `(program_id, discriminator)`;
- unresolved gaps affect freshness/confidence fail-closed;
- no new execution authority exists;
- `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` remain enforced;
- docs, tests, migrations and `docs/STATUS.md` are reconciled;
- `make verify` or the repository's full equivalent passes.

Live Yellowstone/LaserStream acceptance is not required for the keyless gate. If credentials/network are unavailable, mark only live acceptance `BLOCKED_EXTERNAL` and continue.

---

## 13. Explicit non-goals

Do not during E8.4:

- enable live trading;
- add wallet signing;
- make Jito ShredStream a trading authority;
- replace the completed Helius/Birdeye architecture wholesale;
- move AlphaScore/risk logic into an indexer/sidecar;
- optimize in Rust before E11.1 measurements justify it;
- treat a third-party program-ID table as authoritative without independent verification;
- create a second incompatible event schema for backfill.

---

## 14. Codex execution instruction

After Gate P8, Codex must inspect the actual existing implementation before creating new abstractions. Reuse existing event envelope, provenance, quality-state, provider transport, persistence, replay and telemetry primitives wherever they already satisfy these requirements.

Implement the smallest compatible extension rather than parallel infrastructure.

For every task:

1. inspect current code/tests;
2. write/update focused tests first where practical;
3. implement;
4. run focused checks;
5. run relevant integration/migration/replay checks;
6. update docs and `docs/STATUS.md`;
7. commit and push a coherent checkpoint;
8. continue autonomously.
