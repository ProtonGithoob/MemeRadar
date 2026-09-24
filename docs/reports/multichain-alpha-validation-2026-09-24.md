# Multi-chain alpha validation report — 2026-09-24

## Result

`LOCAL_VERIFY_PASS / EXTERNAL_ACCEPTANCE_BLOCKED`.

The implementation and safety contracts are locally verified. Real
PostgreSQL row counts, restart evidence, credentialed provider acceptance,
Telegram delivery, and mature forward outcomes were not fabricated when the
host or provider was unavailable.

Protected modes remain:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Local verification

| Check | Result |
|---|---|
| `make lint` | `PASS` |
| `make typecheck` | `PASS` — 161 source files |
| `make test` | `PASS` — 1492 passed, 21 skipped, 7 warnings |
| Total coverage | `79%`, delta `0` from the prior `79%` baseline |
| Frontend tests | `PASS` — 83 tests |
| Compose config | `PASS` |
| Migration graph | `PASS` — head `0012_stream_gap_diagnostics`, 27 tables in static check |
| Security review | `PASS`; external container/npm/pip scans `NOT_RUN` |
| SBOM | `PASS` — 582 components |
| Free-provider doctor | `PASS` — free Solana/Dex core ready |
| Paper-trading doctor | `PASS`; live execution disabled |
| Stream-integrity doctor | `BLOCKED_EXTERNAL` — stream/backfill URLs absent |
| Telegram doctor | `BLOCKED_EXTERNAL` — bot/chat configuration absent |

## Database and forward shadow

The repository-supported Compose attempt failed before container creation with
Docker socket permission denied. The host has no configured `DATABASE_URL`, so
no PostgreSQL launch, market-snapshot, early-feature, decision, outcome, or
restart/idempotency rows were inspected in this checkpoint. The existing
forward worker, scheduler, maturation horizons, and migration contracts remain
the owners for the next acceptance run; no second database was introduced.

The checked-in bounded Pump.fun artifact is prior evidence, not a new DB
acceptance:

| Measure | Observed value |
|---|---:|
| launches discovered | 1278 |
| legacy `create` / `create_v2` | 16 / 1262 |
| `WATCH` | 1275 |
| `EARLY_WATCH` | 0 |
| Dex first observations | 124 |
| MemeRadar-before-Dex leads | 121 |
| 1h report counter | 995 |
| 6h / 24h / 72h / 7d report counters | 0 / 0 / 0 / 0; no mature acceptance sample |
| measured 2x / 5x / 10x winners | 0 / 0 / 0; no mature executable labels |
| rug/dead counts | `NOT_MEASURED` |
| `UNKNOWN_OUTCOME_RATE` | `NOT_COMPUTABLE` — mature denominator absent |

The outcome implementation supports all requested horizons without zero-filling
missing values:

| Horizon | Current evidence |
|---|---|
| 1m, 5m, 15m, 30m | Implemented in the durable pipeline; not separately exposed by the checked-in summary artifact |
| 1h | 995 report rows/counter; not a mature alpha sample |
| 3h | Implemented; no separate checked-in mature count |
| 6h, 24h, 72h, 7d | Report counters are 0; no mature acceptance sample exists |

Real DB outcome rows, matured 6h/24h/72h/7d samples, recall, FPR, FNR,
ablation, and paper entries are `NOT_MEASURED` or
`INSUFFICIENT_SAMPLES`, not zero-filled.

## Stream-gap reliability

The legacy before value is `1408`, from the old Pump.fun health projection.
That projection merged global/sparse-slot continuity gaps into a
program-filtered stream and is not a valid current loss count. In the same
artifact, notifications were `1158`, queue max was `2`, dropped events,
stream errors, transaction-unavailable events, retries, and rate-limit
responses were all reported as `0`, and one connection attempt/reconnect was
recorded. Those counters do not prove current continuity.

The after value is `NOT_MEASURED` because the post-fix Compose/PostgreSQL run
could not start. The local implementation now durably records:

`gap_started_at`, `gap_resolved_at`, `missed_slot_start`, `missed_slot_end`,
`provider`, `connection_id`, `reconnect_reason`, `backfill_status`,
`events_recovered`, and `events_unrecoverable`.

Bounded finalized `getBlocks`/`getBlock` recovery uses the same canonical raw
decoder as live ingestion. Unresolved or unverified gaps stay fail-closed.
Synthetic and unit contract tests pass; the requested real target
`unresolved gaps ≈ 0` remains `BLOCKED_EXTERNAL`.

## Provider and operator surfaces

- Solana keeps the raw Pump.fun IDL decoder. Raydium pool identity, CPMM
  quote, executable-liquidity and CLMM-unknown handling are normalized behind
  the existing adapter. Jupiter Swap API V2 quote, route, impact, output and
  unsigned-order parsing is read-only; it cannot sign or submit.
- Helius remains optional. Missing Helius does not disable core Solana
  discovery. The default fallback remains raw/direct evidence, protocol
  state, Jupiter/Raydium, optional enrichment, then Dex enrichment.
- Generic EVM RPC is read-only and validates expected chain IDs. Robinhood
  mainnet/testnet identities are `4663`/`46630`; BNB is `56`; extra EVM
  adapters are disabled unless explicitly configured.
- Four.meme, PancakeSwap, Uniswap, Aerodrome, OpenLaunch, Par and the
  Robinhood protocol candidates normalize events only as non-authoritative
  evidence until on-chain identity is complete.
- Blockscout is optional enrichment/fallback, never the real-time trade
  transport. EVM sellability uses an `eth_call` seam and has explicit unknown
  and failure outcomes.
- `memeradar-mcp` exposes only read-only tools and delegates to existing API
  routes. Missing research projections return explicit `NOT_EXPOSED`; no MCP
  tool signs, submits, mutates, or duplicates business logic.

## Exact chain status

Each cell uses `IMPLEMENTED`, `PARTIAL`, `BLOCKED_EXTERNAL`,
`NOT_IMPLEMENTED`, or `INSUFFICIENT_SAMPLES`. `PARTIAL` means a local seam or
shared owner exists but live protocol/provider evidence is incomplete.

| Chain | Transport | Launch discovery | Pool discovery | Trade stream | Wallet intelligence | Security | Quote | Sell simulation | Historical replay | Shadow | Paper | Live |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Solana | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT_IMPLEMENTED |
| Robinhood | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| BNB | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Base | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Ethereum | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Arbitrum | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Avalanche | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Polygon | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Sui | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |

Interpretation: Solana is the only chain with bounded real forward evidence.
Robinhood, BNB, Base, and Ethereum have local read-only seams but no
credentialed/live protocol acceptance in this session. Arbitrum, Avalanche,
Polygon, and Sui remain architecture seams only. The protocol registry keeps
unverified deployments `TODO_VERIFY`; it does not activate them from README
claims.

## Telegram and alpha metrics

Telegram acceptance for `WATCH`, `EARLY_ALPHA`, `HIGH_CONFIDENCE_ALPHA`,
`PAPER_ELIGIBLE`, `RISK_BLOCK`, and `EXIT` was not run. The artifact contains
`N=0` decision, outbox, and sent timestamps. Therefore Telegram p50/p95/p99
are `NOT_MEASURED`, and end-user delivery is not claimed.

Early-winner recall, FPR, FNR, ablation, and provider disagreement rates are
`NOT_MEASURED` for real mature data. The existing replay/recall/ablation
infrastructure and disagreement/fail-closed contracts are locally covered;
the sample gate prevents them from being presented as alpha results.

## Required answers

1. Solana real-data alpha validation operational? **PARTIAL** — bounded raw
   Pump.fun shadow is operational, but DB acceptance and mature alpha evidence
   are blocked/insufficient.
2. Robinhood real launch discovery operational? **NO** — **PARTIAL** local
   decoder/RPC seam; live verified protocol discovery is `BLOCKED_EXTERNAL`.
3. BNB Four.meme discovery operational? **NO** — **PARTIAL** parser seam;
   deployment identity remains `TODO_VERIFY`.
4. Base discovery operational? **NO** — **PARTIAL** generic RPC/protocol
   seam; no verified live deployment acceptance.
5. Ethereum read-only intelligence operational? **PARTIAL** locally — generic
   read-only RPC, enrichment and sellability seams exist; live acceptance is
   `BLOCKED_EXTERNAL`.
6. Telegram real sends proven? **NO** — credentials/configuration absent.
7. PAPER entries proven? **NO** — contracts and doctor pass, but no real
   paper entry was observed.
8. Stream gaps controlled? **PARTIAL** — diagnostics, bounded recovery and
   fail-closed transitions are implemented; real post-fix unresolved count is
   not measured.
9. Live-money execution enabled? **NO** — protected modes remain enforced.
10. Before `PAPER_AUTO` production acceptance: complete the PostgreSQL/
    restart run, prove bounded gaps, verify protocol identities and providers,
    collect mature 6h/24h/72h/7d outcomes with an explicit unknown rate,
    measure recall/FPR/FNR/ablation and provider conflict behavior, prove
    Telegram sends/timings, and observe real paper entries under fresh quote,
    sell-route, impact, and no-gap gates. Keep `AUTO_EXECUTION=false`.

## Remaining external blockers

- Docker socket/database/Redis access for the repository Compose acceptance,
  row counts, worker restart, and real gap reconciliation.
- Configured stream/backfill endpoints and, where needed, provider API keys.
- Credentialed Telegram bot/chat for send and latency acceptance.
- On-chain verification of every candidate deployment and sample transaction.
- Elapsed time and real candidates for mature 6h/24h/72h/7d labels.
- Compliant historical cases and external intelligence data for the named
  case studies.

The requested `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` files
could not be written because `.codex/` is host-mounted read-only. The active
plan and durable progress ledger are retained under the writable repository
tree.
