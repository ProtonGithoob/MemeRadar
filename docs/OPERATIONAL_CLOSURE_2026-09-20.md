# MemeRadar early-alpha operational closure

> Historical pre-ingestion-slice snapshot. The current keyless raw Solana
> source status is recorded in [STATUS.md](STATUS.md); the no-source claims
> below describe the baseline before that implementation checkpoint.

Date: 2026-09-20
Baseline inspected: `21f1c17f5bfdc5491bf221bd7581f64a03c0e909`
Evidence class: local engineering + bounded read-only provider checks

## Classification

| State | Result | Evidence |
|---|---|---|
| ENGINEERING_READY | YES | Full Python suite with PostgreSQL: `1419 passed`; lint, mypy, frontend gates and migration check pass. |
| LIVE_SHADOW_OPERATIONAL | NO | Compose services are healthy, but the worker has no configured canonical raw transaction source factory; no real launch entered the pipeline. |
| REAL_WORLD_ALPHA_VALIDATED | NO | Live launch count and matured sample count are both `0`; no alpha claim is made. |

## Local/Git state

At inspection, local `HEAD`, `origin/main`, and the accepted baseline were all
`21f1c17f5bfdc5491bf221bd7581f64a03c0e909`; branch `main` was synchronized.
The closure changes are preserved in the local working tree and committed as
part of this closure pass. No unrelated work was discarded.

## Fixes performed

- Runtime decision transitions now persist the existing `FeatureSnapshot`,
  `RiskAssessment`, and `ScoreSnapshot` before the candidate transition. This
  closes the PostgreSQL foreign-key failure and preserves UNKNOWN evidence
  instead of converting it to zero/safe.
- Snapshot IDs and transition keys are replay-idempotent; duplicate stages do
  not create duplicate immutable rows.
- Candidate rehydration now follows persisted lifecycle causal edges instead of
  UUID ordering when multiple transitions share one event timestamp. This
  closes restart/resume failures for same-checkpoint transitions.
- Worker composition binds the existing feature/risk/score repositories to the
  same unit of work; no detector, scorer, Telegram implementation, stream
  integrity layer, schema, or frontend was duplicated.
- `.env.example` now documents the isolated `MEMERADAR_TEST_DATABASE_URL`
  test-only key.

No migration was required: the existing head remains
`0011_collection_checkpoints` with 27 metadata tables.

## Database and restart evidence

The isolated test database was PostgreSQL 16 in a dedicated Compose project:

```text
postgres: 127.0.0.1:55432 / database memeradar_test
redis:    127.0.0.1:56379
```

`MEMERADAR_TEST_DATABASE_URL` was set only for the test process. Actual
PostgreSQL integration results:

```text
20 passed, 2 warnings
```

This includes checkpoint restore after restart, first-writer concurrency,
rollback, duplicate candidate/event handling, duplicate lifecycle snapshots,
duplicate outbox delivery, append-only snapshots, and persisted alert timing.
The focused early-runtime integration test also passed after the snapshot/FK
fix. A default-sandbox full run produced TCP `PermissionError [Errno 1]` for
all 20 DB tests; the identical command with host access passed, proving this
was the execution sandbox boundary rather than a database defect.

## Docker and stack

Docker evidence:

```text
client/server: 29.1.3/29.1.3
context:       default
daemon:        healthy
socket:        660, nobody:nogroup
```

The earlier `/var/run/docker.sock` denial was a host socket/session permission
issue. No daemon restart, group mutation, sudo command, or destructive cleanup
was performed. The closure stack was successfully started on free isolated
ports and passed:

```text
PostgreSQL healthy
Redis healthy
API /health/live: 200
API /health/ready: 200
worker container running
web endpoint reachable
protected modes asserted
```

The stack is infrastructure-ready, not collection-active: the worker log only
contains `worker_started` because the canonical raw source is intentionally
not fabricated from a URL.

## Provider matrix

| Capability | Result | Evidence / limitation |
|---|---|---|
| Solana HTTP RPC | PASS | Public `getHealth` doctor passed; 618.896 ms probe. Read-only chain RPC/history only. |
| Solana WebSocket transport | PASS / insufficient for collection | Public `logsSubscribe` accepted and unsubscribed; no repository adapter converts logs + transaction enrichment into `RawChainTransaction`. |
| Solana raw launch stream | BLOCKED_EXTERNAL | Worker source is injected-only; no configured source factory. |
| Helius | BLOCKED_EXTERNAL | URL/API key absent; existing normalizer is an injected seam, not a source constructor. |
| Birdeye | BLOCKED_EXTERNAL | Optional URL/key absent. |
| DexScreener HTTP | PASS | Public exact canonical SOL mint metadata/pair doctor passed; 344.259 ms probe. Secondary confirmation only. |
| Telegram | BLOCKED_EXTERNAL | API URL, bot token and chat ID absent; no API call claimed. |
| Paper execution | PASS | Paper doctor and contracts pass; live execution disabled. |

## Protocol verification matrix

| Venue | Program/event identity | Decoder/fixture | Status |
|---|---|---|---|
| Pump.fun | Registry provisional program + Anchor trade tag | `PumpFunAdapter`; unit/contract fixtures | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` |
| PumpSwap | Registry provisional program + Anchor swap tag | `PumpSwapAdapter`; unit/contract fixtures | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` |
| Raydium AMM v4 | Registry provisional program + native initialize tag | `RaydiumAdapter`; unit/contract fixtures | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` |
| Raydium CPMM | Registry provisional program + Anchor swap tag | shared Raydium adapter; unit/contract fixtures | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` |
| Raydium CLMM | Registry provisional program + Anchor swap tag | shared Raydium adapter; unit/contract fixtures | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` |
| Meteora DLMM | No authoritative registry route | adapter exists; fail-closed | `TODO_VERIFY` / not connected |
| Meteora DAMM v2 | No authoritative registry route | adapter exists; fail-closed | `TODO_VERIFY` / not connected |
| Jupiter-related launch discovery | No launch identity | no primary launch decoder | `NOT_SUPPORTED_PLANNED` |

The public WebSocket smoke test does not promote any row. Canonical routing
still requires the complete verified `(program_id, discriminator_or_tag)` key;
unverified input is rejected by `CanonicalProtocolDecoder`.

## DexScreener and benchmark

The provider is reachable and the exact-mint market adapter passes its doctor.
No forward benchmark row was collected because no real token entered the
canonical discovery path. Trending/Top Volume historical timestamps remain
`UNKNOWN`; no reconstruction was attempted. Reference examples FLEX, JUPCAT,
URANUS, KMS, wildebeest and BLESS are `NOT OBSERVED / INSUFFICIENT HISTORICAL
EVIDENCE` in this checkout because exact mint-time evidence was not captured.

## Telegram

The existing AlertEventProjector → AlertDeliveryService → outbox path remains
the only delivery path and its fixture/dedupe tests pass. Operational delivery
is not verified because all three runtime settings are absent:

```text
TELEGRAM_API_URL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

No token was printed or transmitted. `telegram_sent_at`, when eventually
available, means `SENT_TO_TELEGRAM_API`; user delivery is not inferred.

## Live evidence and latency

```text
real launches observed:       0
EARLY_WATCH:                   0
STRONG_SETUP:                  0
HIGH_CONFLUENCE:               0
ENTRY_READY:                   0
Telegram alerts:               0
matured 1h / 6h / 24h / 72h / 7d: 0 / 0 / 0 / 0 / 0
missed winners:                0 eligible matured observations
false positives:               0 eligible matured observations
```

No live per-event latency percentile is reported because `N=0`. The only
external timing samples are provider doctor calls, not event-to-alert samples:

```text
Solana HTTP health: 618.896 ms (N=1)
DexScreener metadata: 344.259 ms (N=1)
provider→ingestion→normalization→safety→decision→outbox→Telegram: UNKNOWN (N=0)
```

Synthetic replay/test timings are not mixed with live-shadow measurements.

## Maturity and research

`ExtremeWinnerOutcomeLabeler`, stage outcome structures,
`MissedWinnerAnalyzer`, `FalsePositiveAnalyzer`, and the exact-mint benchmark
remain research-only and are covered by deterministic tests. Their future
labels cannot enter runtime scoring. No matured live row exists to label. The
worker currently has no usable source-connected maturity sweep to run; this is
therefore an operational blocker behind the missing raw event path, not a
claim of zero performance.

## Test evidence

```text
focused post-fix unit tests: 13 passed
PostgreSQL integration:      20 passed, 2 warnings
full Python suite:           1419 passed, 7 warnings
Ruff:                        PASS
mypy:                        PASS (140 source files)
frontend lint:               PASS
frontend typecheck:          PASS
frontend unit:               83 passed
frontend build:              PASS
migration check:             PASS
```

The protected-mode contract remained:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Minimum operator actions

1. Provide a read-only Solana stream source that emits the repository’s
   `RawChainTransaction` contract, or configure an existing Helius stream in a
   deployment that includes a verified source factory. A stream URL alone is
   insufficient.
2. Independently verify each required venue’s current program ID,
   discriminator/instruction identity and payload decoder, then update the
   versioned registry only with authoritative evidence. Until then, the worker
   must remain fail-closed.
3. Configure `TELEGRAM_API_URL`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`,
   then run `make telegram-doctor` and send a clearly marked shadow test through
   the existing outbox path.
4. If direct host Docker use still denies the socket outside this managed
   session, have an administrator ensure the socket is owned by the Docker
   group, add the operator account to that group, and start a new login
   session. No such privilege change was performed here.

Until actions 1–2 are complete, `LIVE_SHADOW_OPERATIONAL` must remain `NO`.
Until enough live observations mature, `REAL_WORLD_ALPHA_VALIDATED` must remain
`NO`.
