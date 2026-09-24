# Real multi-chain acceptance — 2026-09-24

## Result

`LOCAL_IMPLEMENTATION_PASS / REAL_ACCEPTANCE_BLOCKED`.

This checkpoint resumed from `e6cb628` and added the local certification and
data-quality seams in `6792c95`. No GitHub or other remote Git operation was
run. No live-money execution, signer, or MCP mutation capability was added.

Protected modes remained:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## A. Exact commits

| Commit | Meaning |
|---|---|
| `e6cb628` | starting local HEAD |
| `6792c95` | certification registry, `DataQualityConfidence`, tests, status and durable ledger |

The report itself is the report-only checkpoint following `6792c95`.

## B. Exact files changed

Implementation commit `6792c95` changed:

- `.superpowers/sdd/2026-09-24-multichain-alpha-validation/progress.md`
- `docs/STATUS.md`
- `packages/providers/src/memeradar_providers/protocol_registry.py`
- `packages/application/src/memeradar_application/early_alpha_alert.py`
- `packages/application/src/memeradar_application/early_runtime.py`
- `packages/application/src/memeradar_application/early_scoring.py`
- `packages/application/src/memeradar_application/read_api.py`
- `tests/unit/test_protocol_registry.py`
- `tests/unit/test_early_scoring.py`

Pre-existing `.env.example`, `.codex/`, `prompts/`, `scripts/nohup.out`, and
`scripts/run_codex_validation.sh` were not changed or staged.

## C. Migrations

No migration was required for this local seam. The migration head remains
`0012_stream_gap_diagnostics`; static migration validation reports 27 tables.

## D–F. Verification and coverage

| Check | Result |
|---|---|
| `make lint` | PASS |
| `make typecheck` | PASS — 161 source files |
| focused high-risk tests | PASS — 105 passed |
| `make test` | 1,491 passed, 3 failed, 21 skipped, 7 warnings |
| global coverage | 79% |
| frontend CSS contract | PASS — 290 classes / 59 files |
| frontend lint | PASS |
| frontend typecheck | PASS |
| frontend tests | PASS — 83 tests / 24 files |
| Compose config | PASS |
| migration check | PASS — head `0012_stream_gap_diagnostics` |
| SBOM | PASS — 582 components |
| `make verify` | BLOCKED by the same 3 security-review assertions |

The three failures are the existing security-review tests. Root-cause
inspection found one finding only: the pre-existing modified
`.env.example:171` matches the high-confidence Telegram-token rule. The file
was not printed, rewritten, or staged. The security scanner correctly fails
closed; no exclusion or weakening was introduced.

Changed-file coverage from the final local coverage database:

| File | Coverage |
|---|---:|
| `early_alpha_alert.py` | 85.7% |
| `early_runtime.py` | 75.4% |
| `early_scoring.py` | 90.0% |
| `read_api.py` | 80.2% |
| `protocol_registry.py` | 85.4% |
| changed-file total | 81.8% |

The focused 105-test run covers protocol identity/certification, EVM
normalization, Jupiter, MCP read-only boundaries, stream recovery, paper
gates, Telegram adapter contracts, and the changed score/alert paths.

## G–H. PostgreSQL and restart/idempotency acceptance

`BLOCKED_EXTERNAL`.

- `make compose-config`: PASS.
- `make integration-test`: skipped because `MEMERADAR_TEST_DATABASE_URL` is
  unset.
- Docker client is installed, but the daemon call fails with permission
  denied on `/var/run/docker.sock`; no host privileges were changed.
- No local PostgreSQL server/client harness or configured `DATABASE_URL` was
  available.
- No launch, market snapshot, early-feature snapshot, decision, outcome,
  maturation, stream-gap, reconnect, or Telegram-timing rows were inspected
  in this run.
- No worker restart/idempotency claim was made.

The repository’s PostgreSQL repositories, migration contracts, and keyless
integration tests remain locally present; they are not a substitute for this
runtime acceptance.

## I. Post-fix Solana stream result

`NOT_MEASURED`.

The corrected semantics remain in force: program-filtered sparse logs do not
infer generic global-slot gaps. The historical `1408` value is the old scope
mismatch and is not a Pump.fun missed-launch count.

Fresh probes produced:

- Solana HTTP RPC doctor: `PASS`, public RPC reachable, approximately 563 ms.
- bounded public Solana WebSocket probe: transport errors/reconnects, zero
  notifications, no event reconciliation.
- configured stream/backfill URLs: absent; stream-integrity doctor
  `BLOCKED_EXTERNAL`.

Therefore the required sequence—persist cursor, deliberate reconnect,
`RECONNECT_BOUNDARY`, finalized bounded backfill, same-decoder reconciliation,
`VERIFIED` resolution, and active unresolved relevant gaps—was not completed.
Genuine unresolved relevant gaps: `UNKNOWN`, not zero. Unrecoverable events:
`NOT_MEASURED`.

## J. Solana provider certification

The existing Pump.fun decoder and full-key routing were preserved. A new
`ProtocolCertificationRecord` projection is stricter than decoder identity
pinning and includes chain ID, contract/program address, bytecode hash,
interface identity, event signatures/discriminators, known block and
transaction, decoded sample, provider timestamp, normalized output, protocol
version, sources, and last verification time.

`DEFAULT_PROTOCOL_CERTIFICATION_REGISTRY` contains 27 machine-readable
records:

```text
27 TODO_VERIFY
```

This includes Pump.fun, PumpSwap, Raydium, Raydium CPMM/CLMM, BNB candidates,
Base/Ethereum/Robinhood candidates, and other tracked EVM candidates. The
existing Pump.fun `VERIFIED` decoder identity is not silently promoted to
`VERIFIED_READ_ONLY` because live bytecode, known live sample, provider
timestamp, and normalized live output are missing.

Raydium’s current documentation distinguishes CPMM and CLMM pool models, but
no current deployment bytecode/sample record was obtained in this runtime.
The local Raydium adapter therefore remains `TODO_VERIFY` for certification.

Jupiter’s local adapter remains read-only quote/route/order parsing with no
signing or submission. The bounded real SOL/USDC quote probe timed out; live
quote, sell-route, impact, output, stale, and no-route acceptance is not
claimed. Helius is optional and unconfigured; free-core discovery does not
depend on it.

## K. Robinhood certification

Official Robinhood documentation currently lists mainnet chain ID `4663` and
testnet chain ID `46630`, with public RPC endpoints. The local generic EVM
identity records retain those IDs. A bounded read-only RPC probe timed out in
this environment, and no launch protocol had all required bytecode/event/
sample evidence. Robinhood launch discovery is therefore `PARTIAL` locally,
not live verified. All candidate protocols remain `TODO_VERIFY`.

## L. BNB certification

BNB chain ID `56` remains configured. Four.meme’s public site is reachable in
the research record and describes its BNB launchpad, while candidate
TokenManager/TokenManager2 references remain non-authoritative until a live
bytecode, event, TokenCreate, purchase, sale, and migration sample is decoded.
No such bounded on-chain acceptance was possible here. Four.meme and
PancakeSwap remain `TODO_VERIFY`/`PARTIAL`; no trade submission was attempted.

## M. Base certification

Base has generic EVM read-only seams and Uniswap/Aerodrome candidate records,
but the public Base RPC probe timed out and no real new pool, trade, pool-state,
quote, or sellability evidence was collected. Base remains `PARTIAL` with
shadow `BLOCKED_EXTERNAL` and no paper/live capability.

## N. Ethereum certification

Ethereum has generic read-only transport, wallet/provenance, and Uniswap
candidate seams. The bounded public RPC probe timed out. No live pool event,
trade, or wallet enrichment acceptance was collected; Ethereum remains
`PARTIAL`, not operational for real acceptance.

## O. Additional-chain state

Arbitrum, Avalanche, Polygon, and Unichain remain generic EVM seams without a
verified target DEX, pool discovery, sellability path, or measurable shadow.
Sui remains a non-EVM seam only; no opportunity-density, launch-protocol, DEX,
wallet, or security research acceptance was performed. Blockscout remains an
optional enrichment source and was not used as a trade stream.

## P. MCP acceptance

The read-only MCP tests pass. The server delegates through existing API
routes, exposes no signer or execution token, and has no write/settings/shell
surface. Tools without an available canonical projection return explicit
`NOT_EXPOSED`, `BLOCKED_EXTERNAL`, or `INSUFFICIENT_SAMPLES` rather than
pretending a null value is success. No MCP DB-table bypass or live trade tool
was added.

## Q. Telegram acceptance

`BLOCKED_EXTERNAL`; no user-visible delivery is claimed.

The local credential file contains a bot token and chat ID, but no API URL.
Supplying the canonical Telegram API URL only in-process caused the bounded
health call to time out. No test message was sent. Decision/outbox/sent timing
sample size is `N=0`; p50/p95/p99 are all `NOT_MEASURED`.

## R. PAPER acceptance

The paper-trading doctor and paper contracts pass, with live execution
disabled. No genuine real-market candidate traversed
`DISCOVERY → EARLY_ALPHA → SECURITY → QUOTE → RISK → PAPER ENTRY → POSITION →
PAPER EXIT`. Paper lifecycle acceptance is `INSUFFICIENT_SAMPLES`, not PASS.

## S–W. Outcomes and metrics

The prior bounded Pump.fun artifact is not a fresh PostgreSQL acceptance but
is the only available forward sample:

| Measure | Value |
|---|---:|
| discovered launches | 1,278 |
| WATCH | 1,275 |
| EARLY_WATCH | 0 |
| PAPER_ELIGIBLE / entry-ready | 0 |
| 1h-due observations | 995 |
| mature 6h / 24h / 72h / 7d | 0 / 0 / 0 / 0 |
| measured 2x / 5x / 10x labels | 0 / 0 / 0 |
| `UNKNOWN_OUTCOME_RATE` | `NOT_COMPUTABLE` — mature denominator absent |
| RUG / HONEYPOT / DEAD / SEVERE_DRAWDOWN / NEUTRAL | `INSUFFICIENT_SAMPLES` or `NOT_MEASURED` |
| recall / precision / FPR / FNR / lead time / MFE / MAE | `NOT_MEASURED` |

The zero winner counters mean no mature executable labels were measured; they
do not mean the candidates were safe or that no winners existed. The outcome
implementation supports the requested 1m, 5m, 15m, 30m, 1h, 3h, 6h, 24h,
72h, and 7d horizons with explicit unknown handling, but the elapsed and
database-backed samples are insufficient for evaluation.

Feature ablation and provider ablation are both `INSUFFICIENT_SAMPLES`. No
external provider has proven incremental value for lead time, recall,
precision, or rug rejection; no provider can be declared unnecessary from
this run. Rate-limit/cost totals and provider conflict rates are
`NOT_MEASURED`.

`DataQualityConfidence` is now exposed as a separate projection. It reuses
existing evidence coverage/confidence and becomes zero when critical risk
quality is not fresh; it does not replace deterministic risk gates or invent
provider agreement data. Full provider-agreement, evidence-class freshness
budget, and conflict-rate calibration remain external/runtime work.

## X. Exact chain matrix

`PARTIAL` means a local provider-independent seam or bounded historical
artifact exists; it does not mean live acceptance. `BLOCKED_EXTERNAL` means
the next evidence requires unavailable runtime/provider access.

| Chain | Transport | Launch | Pool | Trade stream | Wallet | Security | Quote | Sell sim | Replay | Shadow | Paper | Live |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Solana | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | BLOCKED_EXTERNAL | INSUFFICIENT_SAMPLES | NOT_IMPLEMENTED |
| Robinhood | BLOCKED_EXTERNAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| BNB | BLOCKED_EXTERNAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Base | BLOCKED_EXTERNAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Ethereum | BLOCKED_EXTERNAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Arbitrum | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Avalanche | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Polygon | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Unichain | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |
| Sui | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | INSUFFICIENT_SAMPLES | BLOCKED_EXTERNAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED |

## Y. Remaining blockers before PAPER_AUTO

1. Remove/rotate the pre-existing token-like `.env.example` value through the
   operator’s credential workflow; it is intentionally not modified here.
2. Provide Docker socket access or a repository-supported PostgreSQL instance
   and run migrations, forward rows, restart/idempotency checks, and outcome
   maturation.
3. Provide usable Solana stream/backfill transport and complete the explicit
   reconnect/recovery scenario.
4. Obtain live bytecode, event/discriminator, known block/transaction,
   decoded sample, provider timestamp, and normalized output for every
   protocol promoted from `TODO_VERIFY`.
5. Complete Raydium/Jupiter/Solana sellability, Telegram delivery, and a real
   paper candidate lifecycle.
6. Collect mature controls and temporal OOS samples before reporting recall,
   FPR, FNR, ablation, provider conflict, or cost conclusions.

## Z. Mandatory questions

1. **Is post-fix Solana stream continuity proven with real data?** No;
   `NOT_MEASURED`.
2. **How many genuine unresolved relevant gaps remain?** Unknown;
   PostgreSQL/reconciliation was blocked. The historical 1408 is not used.
3. **Is PostgreSQL forward maturation proven through restart?** No.
4. **Are 6h outcomes mature?** No; insufficient samples.
5. **Are 24h outcomes mature?** No; insufficient samples.
6. **Are 72h outcomes mature?** No; insufficient samples.
7. **Are 7d outcomes mature?** No; insufficient samples.
8. **Is Raydium live read-only acceptance proven?** No; local seam only.
9. **Is Jupiter quote/sell acceptance proven?** No; real probe timed out.
10. **Is Robinhood launch discovery live and verified?** No.
11. **Which Robinhood protocols are VERIFIED?** None; all remain
    `TODO_VERIFY`.
12. **Is Four.meme launch discovery live and verified?** No.
13. **Is Pancake migration/pool discovery live and verified?** No.
14. **Is Base Uniswap/Aerodrome live read-only discovery proven?** No.
15. **Is Ethereum intelligence live read-only acceptance proven?** No;
    local seam only.
16. **Are real Telegram sends proven?** No.
17. **What are Telegram p50/p95/p99 latencies?** All `NOT_MEASURED`;
    `N=0`.
18. **Has a real-market PAPER candidate completed full lifecycle?** No;
    `INSUFFICIENT_SAMPLES`.
19. **What is `UNKNOWN_OUTCOME_RATE`?** `NOT_COMPUTABLE` because the mature
    denominator is absent.
20. **What are winner recall / FPR / FNR?** `NOT_MEASURED`.
21. **Which external provider adds measurable incremental value?** None
    proven; ablation is `INSUFFICIENT_SAMPLES`.
22. **Which providers are unnecessary?** None can be concluded unnecessary
    from this sample; optional providers are unconfigured.
23. **Is MCP demonstrably read-only?** Yes, locally: focused tests pass and
    no signer/write/execution surface exists.
24. **Is any live-money execution enabled?** No.
25. **What exact evidence is still missing before `PAPER_AUTO` acceptance?**
    Real PostgreSQL rows and restart/idempotency, post-fix stream recovery
    with zero unresolved relevant gaps, verified protocol/provider evidence,
    fresh quote/sell/security/data-quality gates, mature temporal-OOS controls,
    real Telegram timing evidence, and one real eligible paper candidate
    completing entry/position/exit. `AUTO_EXECUTION` must remain `false`.
