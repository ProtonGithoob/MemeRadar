# Phase 10 / Sprint 10.1 Replay Harness Design

## Outcome

Add a provider-independent research replay boundary that can reproduce
historical feature snapshots from compact normalized observations, label future
outcomes, and export a deterministic artifact. The runner composes the current
`CorrelationWindowBuilder`, `FeatureWindowAggregator` and `AlphaStrategy`
contracts; it does not add a second decoder, provider client, persistence
model, scoring authority or execution path.

## Dataset contract

`ReplayDataset` contains stable `TokenIdentity` values, immutable
`ReplayEventRecord` values and explicit `ReplayCheckpoint` signal times.
`ReplayEventRecord` wraps the existing normalized `Observation` contract with
the registry/schema/venue metadata required for research provenance. Its JSON
form contains no raw provider response or credential-shaped field and records
provider, source ID, parser version, occurred/observed/ingested timestamps,
quality and normalized payload. Events expose a deterministic partition key of
`date / venue / token` for compact export and can be rehydrated without a live
provider.

Checkpoints identify the candidate/token and the event-time signal boundary.
They may carry an already-normalized risk assessment for advisory strategy
comparison; missing risk evidence means the harness reconstructs features but
does not invent a strategy input or score.

## Replay contract

`ResearchReplayManifest` pins dataset ID/version, event boundary, parser
version, protocol registry version, event schema, strategy name/version,
config hash and outcome policy version. The harness validates every event
against those identities, sorts by `(occurred_at, observed_at, ingested_at,
kind, source_id, id)`, and includes an event in feature reconstruction only
when all three timestamps are at or before the checkpoint. Events after that
boundary are recorded as excluded evidence. The same normalized `Observation`
is passed into the existing correlation/feature builders; there is no
replay-only decoder.

The replay result contains correlation/features for each checkpoint, optional
advisory strategy snapshots, excluded future-event IDs and a canonical digest.
Running the same dataset, manifest and code produces byte-equivalent JSON
material and stable IDs. A malformed event, version mismatch, duplicate source
with conflicting payload or secret-shaped normalized field fails closed.

Each checkpoint also receives stable cohort dimensions for launch venue,
liquidity, token age, AlphaScore, confidence, internal smart-wallet confluence
and social velocity. Cohort summaries report sample/labeled counts and
descriptive forward-return/rug rates without changing any feature or score.
`ReplayStrategyComparison` reruns alternate strategies against the same dataset
digest and checkpoint inclusion/exclusion boundaries. Canonical JSON is the
nested artifact; a deterministic flat CSV projection is available for simple
outcome analysis, while a separate bounded profiler records local throughput
before any optional Rust extraction is considered.

## Outcome labels

Outcome labeling is intentionally separate from feature reconstruction. A
labeler first selects the last valid pre-signal price as the baseline, then
uses only post-signal event-time market observations inside each configured
horizon. It emits forward return, MFE, MAE, time-to-1.5x/2x/3x,
time-to-50%-drawdown, liquidity-collapse, rug/security, creator-dump and
paper-exit labels when evidence exists; unknown values remain `null` with
reason codes. Default horizons are `1m`, `5m`, `15m`, `1h`, `6h` and `24h`.
Outcome evidence is never fed back into correlation, features or strategy
inputs.

## CLI and safety

`scripts/replay_dataset.py` loads a normalized JSON dataset and writes a
redacted JSON research artifact. It has no network/provider imports, never
loads secrets, never signs/submits transactions and always reports the four
protected modes. `make replay-dataset` is the bounded local entrypoint; an
absent input is a usage error rather than a fabricated result.

The runner is research/advisory only. Healthy data does not increase a score,
strategy output remains permanently non-executable, and all missing,
non-fresh, invalid or conflicted evidence remains explicit.
