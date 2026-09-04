# External Repo Gap Integration Plan — 2026-09-04

This document records the latest focused gap analysis for MemeRadar after reviewing recent Solana/memecoin research references. It intentionally adds only small, high-value extensions that are not already covered by the existing architecture.

## Scope and design rule

Do not create a second ingestion stack, second holder-risk engine, second wallet-reputation engine, or second execution path. Extend existing seams only.

Protected modes remain mandatory:

- `ANALYSIS_ONLY=true`
- `PAPER_TRADING=true`
- `MANUAL_EXECUTION=false`
- `AUTO_EXECUTION=false`
- Phase 12 remains locked.

---

## Gap matrix

| Recent finding | Existing MemeRadar coverage | Gap | Decision |
|---|---|---|---|
| Rust/Yellowstone/Jito multi-DEX streaming patterns | E8.4 stream integrity and E11.1 latency measurement exist; no Rust sidecar is present | Need an explicit evidence-based go/no-go contract for an optional low-latency ingestion sidecar | **ADD as conditional E11.2 only** |
| gRPC/Shred latency benchmark methodology | p50/p95/p99 and stage metrics already exist | Need comparison criteria between current Python path and optional sidecar | **EXTEND benchmark contract, no new subsystem** |
| pre-mine/insider suspicion from large token balance + unusually low native SOL/funding history | Holder graph, launch risk, fresh-wallet/shared-funder/deployer evidence already exist | Missing a first-class corroborating imbalance feature | **ADD to existing LaunchRisk/HolderGraph** |

---

# Extension E11.2 — Optional Low-Latency Solana Ingestion Sidecar

**Priority:** P2 / conditional

**Goal:** provide a measurable path to reduce chain-event-to-ingest latency for ultra-early detection without moving scoring, risk, persistence authority, or execution into Rust.

This extension must not be implemented as a mandatory runtime dependency. It is authorized only if measured evidence shows material benefit over the existing path.

## Required architecture

Introduce only a provider-neutral boundary compatible with existing E8.4 normalized events, for example:

- `LowLatencyDexEventSource`
- or equivalent adapter contract behind the existing ingestion/application port.

The optional sidecar may consume one or more of:

- Yellowstone gRPC;
- Jito/Shred-style streams;
- documented Solana transaction/account streams.

It may decode only the protocols already approved by the canonical protocol registry, unless a separately reviewed protocol mapping is added.

The sidecar output must use the same normalized event contract consumed by the current Python ingestion path.

## Strict authority boundaries

The sidecar MUST NOT:

- calculate AlphaScore or EarlyScore;
- evaluate deterministic risk;
- authorize `ENTRY_READY`;
- size positions;
- sign or submit transactions;
- write directly to canonical domain tables except through the same application boundary used by existing normalized events;
- bypass E8.4 protocol verification, gap detection, reorg handling, freshness, dedupe, replay, or provenance requirements.

## Benchmark gate

Before production adoption, benchmark current path vs sidecar using the same event cohort.

Measure at minimum:

- `chain_event_to_ingest_ms` p50/p95/p99;
- `chain_event_to_feature_ms` p50/p95/p99;
- `chain_event_to_decision_ms` p50/p95/p99;
- duplicate rate;
- malformed/conflicting event rate;
- gap/recovery count;
- CPU and memory footprint;
- sustained events/sec;
- reconnect recovery time.

Use identical canonical events where possible and pin parser/registry/config versions.

## Go/no-go rule

Keep the current Python path as default unless the sidecar demonstrates a material and repeatable improvement in ultra-early latency without regression in correctness/replay determinism.

A suggested initial acceptance hypothesis (not a production promise):

- at least 25% improvement in p95 `chain_event_to_ingest_ms`, or
- a demonstrated throughput bottleneck in the existing path that the sidecar removes,

while maintaining zero semantic divergence on the golden replay cohort.

Codex may refine the threshold based on measured baseline evidence, but must document the decision.

## Keyless implementation scope

Codex may implement first:

1. interface/contract;
2. fixture/fake sidecar adapter;
3. normalized-event parity tests;
4. benchmark harness extension;
5. configuration flag that defaults OFF;
6. operations/read-only telemetry showing `DISABLED`, `SHADOW`, or `ACTIVE`.

Live Yellowstone/Jito acceptance remains `BLOCKED_EXTERNAL` when endpoints/credentials are absent.

## Acceptance

- Same canonical fixture stream produces logically identical normalized events through Python and sidecar adapters.
- Sidecar OFF leaves current behavior unchanged.
- Unknown/unverified program identities fail closed.
- Gap/reorg/replay semantics remain controlled by existing E8.4 behavior.
- No execution authority is introduced.

---

# Extension E6.4 — Pre-Mine / Insider Allocation Suspicion Feature

**Priority:** P1 small extension

**Goal:** strengthen early launch-risk detection using a bounded corroborating feature for wallets that hold unusually large early token allocations while showing weak or suspicious native-SOL/funding history.

This must be implemented inside the existing holder graph / launch-risk model. Do not create a new risk engine.

## Evidence model

For top/early holders where data exists, derive provider-neutral evidence such as:

- token supply percentage held;
- native SOL balance at observation time;
- native SOL balance around first acquisition where reconstructable;
- wallet age / first-seen age;
- acquisition source: buy, transfer, mint-related, unknown;
- direct creator/deployer relationship;
- shared-funder relationship;
- funding-source cluster;
- initial token acquisition before/at/after launch;
- trade-derived net position vs observed token balance (`transfer_delta` where available);
- whether wallet has meaningful non-token transaction history;
- evidence freshness/quality/provenance.

## Derived signal

Create an advisory projection such as `InsiderAllocationSuspicion` rather than a binary insider accusation.

Suggested states:

- `LOW_EVIDENCE`
- `SUSPICIOUS`
- `HIGH_SUSPICION`
- `UNKNOWN`
- `CONFLICTED`

Example reason codes:

- `LARGE_ALLOCATION_LOW_NATIVE_SOL`
- `FRESH_WALLET_LARGE_ALLOCATION`
- `CREATOR_RELATED_LARGE_ALLOCATION`
- `SHARED_FUNDER_CLUSTER_ALLOCATION`
- `TRANSFER_DOMINATED_ALLOCATION`
- `PRE_LAUNCH_ALLOCATION_EVIDENCE`
- `INSUFFICIENT_WALLET_HISTORY`
- `INSIDER_EVIDENCE_CONFLICTED`

## Safety rules

1. Large token balance + low SOL alone is never enough to call a wallet an insider.
2. Exchange/custody/program/LP/burn/system accounts must remain excluded where the existing holder classifier can identify them.
3. Unknown labels are not clean labels.
4. Actor clustering applies before aggregate concentration is calculated.
5. Suspicion is corroborating evidence for existing `LaunchRiskAnalyzer`; it must not independently create `ENTRY_READY` or execution authority.
6. Hard blocking, if ever used, requires corroboration such as creator/shared-funder/pre-launch/transfer-delta evidence and must be versioned/configurable.
7. Historical balance data that cannot be reconstructed must remain `UNKNOWN` rather than approximated as fact.

## Integration points

Reuse:

- HolderGraph / holder concentration;
- LaunchRiskAnalyzer;
- deployer self-activity evidence;
- shared-funder / fresh-wallet logic;
- transfer-delta evidence;
- correlation/replay fixtures;
- reason-coded risk timeline.

Expose a compact projection to token detail / launch-risk diagnostics only if existing API schemas can be extended without creating a new UI page.

## Tests

Add deterministic fixtures for:

- legitimate whale with well-funded established wallet;
- fresh wallet with large transfer-based allocation and near-zero SOL;
- creator-related pre-launch allocation;
- several wallets funded by the same source;
- LP/program account that must be excluded;
- low SOL caused by post-purchase spend but with valid acquisition history;
- missing historical SOL balance;
- conflicting provider evidence.

## Acceptance

- No false `SAFE` state from missing history.
- The feature adds no independent positive AlphaScore.
- Existing launch-risk behavior remains backward compatible when the new evidence is absent.
- Replay is deterministic and no-lookahead.

---

# Execution order

Keep this simple and do not interrupt current unfinished work in `docs/STATUS.md`.

1. Finish current active Ultra-Early tasks first.
2. Complete already-approved P1 work in `docs/EXTERNAL_REPO_GAP_INTEGRATION_2026_09_02.md`:
   - E11.10 cross-venue wallet/PnL continuity;
   - E10.3 winner-vs-rug early filter optimization.
3. Implement **E6.4 Pre-Mine / Insider Allocation Suspicion** because it is small and directly improves early safety.
4. Keep **E11.2 Optional Low-Latency Sidecar** conditional. Implement keyless contract/benchmark seams only when current latency evidence or live-read-only work justifies it.
5. E8.5 Anchor IDL onboarding remains lower priority.
6. Run focused tests and full `make verify` at coherent checkpoints.
7. Update `docs/STATUS.md` with exact evidence and explicit `DONE`, `TODO`, or `BLOCKED_EXTERNAL` states.
8. Keep protected modes unchanged and Phase 12 locked.

## Explicit non-goals

Do not add:

- a generic new Rust trading bot;
- a second risk engine;
- a new database for the sidecar;
- automatic DEX execution;
- duplicate wallet/holder tracking;
- a separate insider dashboard;
- runtime dynamic DDL.
