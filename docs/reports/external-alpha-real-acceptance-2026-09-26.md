# External Alpha Real Acceptance Report

Date: 2026-09-26
Baseline: `5e396663a0ee6a9daa46a01fb9169d34929e4486`
Local closure commit: `b0c3636` (`test: close alpha acceptance gaps`)
Modes: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`

This is a root-cause closure report. It does not promote a score, claim a
provider guarantee, or turn fixture data into live evidence.

## A. Commits

- Baseline inspected: `5e39666`.
- Local implementation checkpoint: `b0c3636`.
- No GitHub or remote Git operation was run. The branch remains local and
  ahead of its existing tracking ref.
- The pre-existing dirty `.env.example` was deliberately not staged.

## B. Files changed

The local checkpoint changes seven application modules and eight focused test
modules:

- `flow_analysis.py`: cluster/repeated-size evidence remains corroborating;
  only structural round-trip/rapid/explicit evidence contributes to suspected
  wash volume; `wash_confidence` is exposed.
- `early_features.py`, `alert_pipeline.py`: raw/organic volume evidence and
  high-priority alert rendering.
- `early_scoring.py`, `early_runtime.py`: seven-dimension
  `DataQualityConfidence` decomposition with reason codes.
- `reliability.py`, `price_consensus.py`: typed provider-conflict metrics,
  provider-pair rates, and optional price-consensus telemetry.
- Focused tests cover flow shapes, runtime quality, alert evidence, provider
  event identity, named subscriptions, price disagreement, and conflict rates.

No migration or dependency was added.

## C. Migrations

`make migration-check` passed. Current migration head is
`0012_stream_gap_diagnostics`; table count is `27`.

## D. `make verify`

Final local backend evidence was `1518 passed, 21 skipped, 7 warnings`.
`make lint`, `make typecheck`, frontend CSS/lint/typecheck/tests, Compose
syntax, migration check, and SBOM passed. The verification gate remains
`FAIL` because three security-review tests correctly observe the unresolved
user-owned `.env.example` finding. No test or scanner was weakened.

`make secret-scan` reports only a Telegram-token-shaped value at
`.env.example:171`; the value is intentionally not reproduced.

## E. Global coverage

Generated from the final backend run and `/tmp/memeradar-coverage.json`:

- combined line/branch: `78.69%`;
- statement/line: `83.22%` (`42,086 / 50,570`);
- branch: `66.34%` (`12,299 / 18,540`);
- missing statements: `8,484`.

The combined percentage is the repository-wide engineering metric, not an
alpha-validation metric.

## F. Changed-file coverage

Statement/line and branch coverage from the final artifact:

| module | line | branch |
|---|---:|---:|
| `alert_pipeline.py` | 87.98% | 76.67% |
| `early_features.py` | 91.32% | 74.56% |
| `early_runtime.py` | 80.93% | 59.29% |
| `early_scoring.py` | 90.59% | 81.25% |
| `flow_analysis.py` | 84.96% | 70.93% |
| `price_consensus.py` | 84.44% | 61.54% |
| `reliability.py` | 87.86% | 69.12% |

## G. Critical-path coverage

| critical module | line | branch | status |
|---|---:|---:|---|
| `flow_analysis.py` | 84.96% | 70.93% | `VERIFIED_FIXTURE` |
| `organic_momentum.py` | 94.33% | 82.35% | `VERIFIED_FIXTURE` |
| `early_features.py` | 91.32% | 74.56% | `VERIFIED_FIXTURE` |
| `helius_stream.py` | 78.18% | 55.84% | `VERIFIED_FIXTURE` |
| `wallet_labels.py` | 88.89% | 50.00% | `VERIFIED_FIXTURE` |
| `event_taxonomy.py` | 86.36% | 64.29% | `VERIFIED_FIXTURE` |
| `price_consensus.py` | 84.44% | 61.54% | `VERIFIED_FIXTURE` |
| `alert_pipeline.py` | 87.98% | 76.67% | `VERIFIED_FIXTURE` |
| `provider_contracts.py` | 86.44% | 61.47% | `VERIFIED_FIXTURE` |
| `evm_rpc.py` | 75.62% | 56.11% | `VERIFIED_FIXTURE` |
| `evm_protocols.py` | 86.05% | 61.70% | `VERIFIED_FIXTURE` |
| `strategy_promotion.py` | 94.85% | 85.71% | `VERIFIED_FIXTURE` |

High-risk negative paths covered locally include malformed payloads, invalid
signatures, duplicate deliveries, provider conflicts, stale evidence,
reconnects, canonical identity overlap, unverified protocol identity, and
fail-closed quality states.

## H. `.env.example` security resolution

The worktree file is a user-owned modification relative to `HEAD`. Its token
field matches the scanner's high-confidence Telegram-token shape, contains no
placeholder marker, and was classified `SECURITY_ACTION_REQUIRED` / likely
real. The value was not printed, changed, committed, or excluded from scans.
`HEAD:.env.example` has no matching finding. The operator should revoke/rotate
the credential if it is active, then normalize the example file separately.

## I. Helius real acceptance

| capability | result |
|---|---|
| local adapter contract | `IMPLEMENTED_LOCAL` |
| fixture HMAC, watched-wallet, BUY/SELL, token/amount/USD/provenance mapping | `VERIFIED_FIXTURE` |
| duplicate event ID and malformed/invalid-signature handling | `VERIFIED_FIXTURE` |
| real Helius webhook | `BLOCKED_EXTERNAL` |

`make helius-doctor` reports missing Helius configuration. No real webhook was
sent or received, so observed/received/normalized/evidence-available latency,
old-delivery behavior, and provider-side replay semantics are not claimed.
Future event timestamps are sanitized locally; a provider-issued delivery
timestamp was not available to prove first-delivery age rejection.

## J. Robinhood named stream real acceptance

Named `launches` and `dex-trades` descriptors, cursors, subscription identity,
and provider-versus-canonical event identity are `VERIFIED_FIXTURE`. A bounded
read-only probe of the public RPC and WebSocket timed out/unavailable from the
runtime. Stable subscription IDs, resume semantics, ordering, overlap, and gap
behavior are therefore `BLOCKED_EXTERNAL`, not assumed from documentation.

## K. Par verification

The parser/lifecycle seam is `IMPLEMENTED_LOCAL`; the registry state remains
`TODO_VERIFY` / `BLOCKED_EXTERNAL`. The local lifecycle preserves
`TOKEN_CREATED -> POOL_CREATED -> DEX_ACTIVE` and models PoolKey/PoolId and
first-trade fields, but no live deployment bytecode, launch transaction, or
multi-market sample was captured.

## L. HoodiePad / Doppler verification

The read-only candidate contract is `IMPLEMENTED_LOCAL`; activation is
`TODO_VERIFY` / `BLOCKED_EXTERNAL`. No authoritative chain, factory, runtime
hash, hook, PoolKey/PoolId, launch, or swap sample was available. README
addresses were not promoted.

## M. NOXA verification

The parser contract is `IMPLEMENTED_LOCAL`; deployment and event identity remain
`TODO_VERIFY` / `BLOCKED_EXTERNAL`. No authoritative on-chain launch, pool,
holder, developer-allocation, or buy/sell sample was captured.

## N. Odyssey verification

The parser contract is `IMPLEMENTED_LOCAL`; deployment and lifecycle identity
remain `TODO_VERIFY` / `BLOCKED_EXTERNAL`. No authoritative launch, curve
state, trade, graduation, or post-graduation pool transaction was captured.
Odyssey lifecycle assumptions were not shared with NOXA.

## O. Adaptive log live acceptance

Range shrink/growth, provider-limit classification, retry, checkpoint,
duplicate-log, and reorg/finality policy are `VERIFIED_FIXTURE`. The accessible
EVM RPC probe was unavailable, so blocks/sec, live RPC calls, live error rate,
and production range behavior are `BLOCKED_EXTERNAL`.

## P. Multicall benchmark

Multicall3 encoding/decoding and chain-configuration guards are
`VERIFIED_FIXTURE`. No accessible target RPC permitted an individual-call
versus Multicall3 benchmark; latency, request count, payload size, and failure
isolation are `BLOCKED_EXTERNAL`. Multicall remains optional and disabled when
no measured provider benefit exists.

## Q. Price-consensus real test

Median, stale exclusion, configurable disagreement threshold, confidence, and
conflicted quality are `VERIFIED_FIXTURE`. Public DexScreener and Jupiter price
probes were DNS-blocked, so two-source real agreement/outlier evidence is
`BLOCKED_EXTERNAL`; no production threshold promotion occurred.

## R. Provider conflicts

The local telemetry seam is `IMPLEMENTED_LOCAL` / `VERIFIED_FIXTURE` and
exposes:

- `provider_conflict_total`;
- `provider_conflict_rate`;
- `price_conflict`, `liquidity_conflict`, `market_cap_conflict`,
  `identity_conflict`, and `security_conflict`;
- canonical provider-pair buckets with comparison counts and conflict rates.

`DataQualityConfidence` now decomposes organic flow, wallet independence,
stream quality, price quality, provider agreement, protocol identity, and
holder data. The local conflict/missing-evidence fixture produces
`42.85714285714285714285714286` versus `100` for seven clean dimensions. Real
provider-pair rates are not measured because no two live sources were
available. Critical identity/security conflicts remain fail-closed through the
existing safety gate.

## S. Telegram real acceptance

Alert rendering and storm-control transitions are `VERIFIED_FIXTURE`. The
credentialed health probe could not resolve `api.telegram.org`; no message was
sent. Real WATCH through EXIT sends and decision-to-API p50/p95/p99 are
`BLOCKED_EXTERNAL` / not measured. Priority bypass remains local behavior.

## T. Forward-shadow sample counts

The checked-in Pump.fun forward artifact is bounded real shadow evidence,
classified `VERIFIED_SHADOW`, not mature alpha validation:

| measure | count/status |
|---|---:|
| launches discovered | 1,278 |
| MemeRadar-before-DEX leads | 121 |
| DEX first observations | 124 |
| 1h-due rows | 995 |
| 6h / 24h / 72h / 7d due rows | 0 / 0 / 0 / 0 |
| measured 2x / 5x / 10x / 20x / 50x / 100x winners | 0 / 0 / 0 / 0 / 0 / 0 |

The report marks real-world alpha as `NO` and statistical sufficiency as
`NO`. The legacy `1408` stream-gap value in the artifact is not used as the
current loss metric; current scoped gap acceptance remains unmeasured.

## U. Outcome maturity

Mature 6h/24h/72h/7d samples are `0/0/0/0`. `UNKNOWN_OUTCOME_RATE` is
`NOT_COMPUTABLE` because there is no mature denominator. Winner/rug/dead/
honeypot/neutral maturity is `INSUFFICIENT_SAMPLES`.

## V. Organic-flow ablation

`make opportunity-research` ran against seven synthetic/redacted rows. Baseline,
raw turnover, organic turnover, unique buyers, cluster-adjusted buyers, wallet
entropy, and fusion families remain `INSUFFICIENT_SAMPLES`; no real lift,
precision, recall, MFE, MAE, FPR, or FNR was measured. No production promotion
was made.

## W. Winner recall

Real temporal-OOS winner recall is `INSUFFICIENT_SAMPLES` / `NOT_MEASURED`.
Synthetic training-only values are not reported as acceptance evidence.

## X. FPR/FNR

Real false-positive and false-negative rates are `NOT_MEASURED` because the
mature winner/rug control cohort is absent. The temporal split and no-lookahead
contracts are locally tested.

## Y. Real paper lifecycle

No naturally qualifying real candidate completed
`DISCOVERED -> EARLY_ALPHA -> SECURITY -> DATA QUALITY -> QUOTE -> SELLABILITY
-> RISK -> PAPER ENTRY -> POSITION -> PAPER EXIT`. Result:
`INSUFFICIENT_SAMPLES`. No synthetic candidate was admitted to manufacture a
paper result. No live order or signer path exists.

## Z. Remaining blockers

- `SECURITY_ACTION_REQUIRED`: operator-owned `.env.example` token-shaped value.
- Helius, Telegram, Robinhood named stream, public EVM RPC, DexScreener, and
  Jupiter access are unavailable or unconfigured in this runtime.
- Par, HoodiePad/Doppler, NOXA, and Odyssey remain `TODO_VERIFY`.
- Real paper lifecycle, mature outcomes, temporal OOS, ablation, winner recall,
  FPR/FNR, and provider-value comparisons remain `INSUFFICIENT_SAMPLES` or
  `BLOCKED_EXTERNAL`.
- `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` could not be updated:
  the host-mounted `.codex/` directory is read-only. This report and
  `docs/STATUS.md` are the durable checkpoints.
- Public browser lookup confirmed the referenced repositories and advertised
  licenses, but immutable HEAD hashes for
  [CodeMuscle/solbeam](https://github.com/CodeMuscle/solbeam),
  [nktkass/pumpr-bot](https://github.com/nktkass/pumpr-bot), and
  [nirholas/robinhood-trading-bot](https://github.com/nirholas/robinhood-trading-bot)
  were not exposed by the available lookup. They remain
  `HEAD_NOT_LOCALLY_VERIFIED`; no source was reused.

## Explicit answers

1. `make verify` PASS? **No**; it fails on the preserved user-owned secret finding.
2. `.env.example` safely resolved? **No**; preserved as `SECURITY_ACTION_REQUIRED`.
3. Helius live acceptance proven? **No — `BLOCKED_EXTERNAL`.**
4. Robinhood named stream live acceptance proven? **No — `BLOCKED_EXTERNAL`.**
5. Par `VERIFIED_READ_ONLY_LIVE`? **No — `TODO_VERIFY`.**
6. HoodiePad `VERIFIED_READ_ONLY_LIVE`? **No — `TODO_VERIFY`.**
7. NOXA `VERIFIED_READ_ONLY_LIVE`? **No — `TODO_VERIFY`.**
8. Odyssey `VERIFIED_READ_ONLY_LIVE`? **No — `TODO_VERIFY`.**
9. Raw vs organic volume impact? Local explicit-wash fixture: `600 -> 300`; raw turnover `0.6 -> 0.3`. No OOS impact measured.
10. Cluster-adjusted buyer impact? Three same-cluster buyers reduce to one adjusted buyer in the fixture; no OOS impact measured.
11. Organic-flow features improved OOS metrics? **Not established — `INSUFFICIENT_SAMPLES`.**
12. DataQualityConfidence on conflict? It averages explicit dimensions and lowers on conflict/unknown; local fixture `100 -> 42.857...`; live rate unavailable.
13. Telegram sends proven? **No — `BLOCKED_EXTERNAL`.**
14. Telegram p50/p95/p99? **Not measured.**
15. Real paper candidate completed lifecycle? **No — `INSUFFICIENT_SAMPLES`.**
16. Mature 6h/24h/72h/7d counts? **`0/0/0/0`.**
17. Winner recall/FPR/FNR? **Not measured.**
18. External provider with measurable value? **None proven in this sprint;** bounded core Solana/Pump.fun shadow is the only real provider evidence.
19. Provider to remove/disable? **No permanent removal;** optional Helius/Multicall remain disabled when unavailable or unproven.
20. Live-money execution enabled? **NO.**
