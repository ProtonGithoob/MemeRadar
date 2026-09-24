# Early-alpha validation implementation checkpoint

Date: 2026-09-24
Implementation commit: `6113083`

This checkpoint implements the locally executable portion of the early-alpha
validation roadmap. It does not promote thresholds, enable execution, or claim
statistical alpha validation. The report uses `IMPLEMENTED`, `PARTIAL`,
`BLOCKED_EXTERNAL`, `NOT_IMPLEMENTED`, and `INSUFFICIENT_SAMPLES` as
status values.

## Acceptance status

| Area | Status | Evidence |
|---|---|---|
| Counterfactual outcome pipeline | IMPLEMENTED | Every Pump.fun launch is eligible for continued observation regardless of funnel stage; horizons are persisted through 7d; outcome rows use provider/kind/source identity and idempotent upserts. |
| Explicit outcome labels | IMPLEMENTED | Versioned labels include `WINNER_2X` through `WINNER_50X`, `RUG`, `HONEYPOT`, `DEAD`, `SEVERE_DRAWDOWN`, `NEUTRAL`, and `INSUFFICIENT_HORIZON`. |
| Unified turnover | IMPLEMENTED | 1m/3m/5m/15m/30m/1h turnover, velocity, acceleration, effective-liquidity source, and provider provenance are part of the existing early-feature path. |
| Age-cohort normalization | IMPLEMENTED | Ten required age cohorts and liquidity-scoped progressive cohort normalization return `INSUFFICIENT_COHORT_DATA` below the minimum sample size. |
| Smart-wallet copyability | IMPLEMENTED | Explainable PnL, win rate, sample count, latency, holding time, rug exposure, early entry, liquidity/impact, MEV/insider, penalty, and copyability components are exposed. |
| Smart-wallet convergence | IMPLEMENTED | Wallet quality, time dispersion, funding independence, cluster independence, and copyability-weighted convergence reuse the existing wallet graph. Shared funding clusters do not count as independent confirmations. |
| Supply quality | IMPLEMENTED | Holder concentration, developer/creator/insider/sniper/bundler/fresh-wallet shares, LP/locked LP, authorities, and dangerous Token-2022 extensions are exposed as evidence. |
| Alpha/safety separation | IMPLEMENTED | Existing projection exposes `AlphaIgnitionScore`, `SafetyConfidence`, and `OpportunityConfidence`; high alpha does not clear risk gates. |
| Telegram state flow | PARTIAL | Existing renderer/outbox now supports WATCH, EARLY_ALPHA, HIGH_CONFIDENCE_ALPHA, PAPER_ELIGIBLE, RISK_BLOCK, and EXIT transitions with deduplication and timing fields. Credentialed external delivery remains `BLOCKED_EXTERNAL`. |
| Durable forward shadow | IMPLEMENTED | Restart-safe forward snapshots, horizon-gated outcome rows, label methodology/version, and report aggregation are implemented. The current local evidence remains `INSUFFICIENT_SAMPLES`. |
| Historical case replay | IMPLEMENTED | The replay report consumes the required state/price/outcome schema. Named cases remain `BLOCKED_EXTERNAL` because compliant historical rows are absent locally. |
| Matched controls | IMPLEMENTED | Chain/launchpad/age/liquidity/market-cap/time-period matching is implemented; current paired sample is `INSUFFICIENT_SAMPLES`. |
| Early-winner recall | IMPLEMENTED | Future-only 2x/5x/10x recall before 20%/50%/100% moves, lead-time percentiles, false-positive/negative rates, rug capture, and precision are emitted; current measurements are `INSUFFICIENT_SAMPLES`. |
| Ablation | IMPLEMENTED | Baseline, turnover, age, smart-wallet, convergence, supply, and all-feature contributions are emitted; promotion is disabled and current results are `INSUFFICIENT_SAMPLES`. |
| BNB read-only/shadow adapter | PARTIAL | Generic EVM RPC, chain identity, and account-read seams are available; Four.meme/PancakeSwap verified lifecycle decoding and replay remain absent. |
| Base read-only/shadow adapter | BLOCKED_EXTERNAL | Verified Base identities, Aerodrome/Uniswap lifecycle decoding, and provider acceptance evidence are absent. |

## Exact files changed

Implementation and tests in `6113083`:

- `apps/worker/src/memeradar_worker/forward_evidence.py`
- `packages/application/src/memeradar_application/age_cohorts.py`
- `packages/application/src/memeradar_application/alert_pipeline.py`
- `packages/application/src/memeradar_application/config.py`
- `packages/application/src/memeradar_application/confluence.py`
- `packages/application/src/memeradar_application/early_alpha_alert.py`
- `packages/application/src/memeradar_application/early_features.py`
- `packages/application/src/memeradar_application/early_replay.py`
- `packages/application/src/memeradar_application/early_runtime.py`
- `packages/application/src/memeradar_application/early_scoring.py`
- `packages/application/src/memeradar_application/launch_risk.py`
- `packages/application/src/memeradar_application/pumpfun_forward_report.py`
- `packages/application/src/memeradar_application/wallet_scoring.py`
- `packages/persistence/src/memeradar_persistence/repositories.py`
- `tests/unit/test_age_cohorts.py`
- `tests/unit/test_alert_pipeline.py`
- `tests/unit/test_confluence.py`
- `tests/unit/test_control_api.py`
- `tests/unit/test_early_alpha_alert.py`
- `tests/unit/test_early_features.py`
- `tests/unit/test_early_replay.py`
- `tests/unit/test_early_runtime.py`
- `tests/unit/test_early_scoring.py`
- `tests/unit/test_launch_risk.py`
- `tests/unit/test_pumpfun_forward_report.py`
- `tests/unit/test_read_persistence.py`
- `tests/unit/test_wallet_scoring.py`

No migration was added. The implementation reuses the existing `observations`
table and JSON normalized payload. Migration head remains
`0011_collection_checkpoints` and the schema check reports 27 tables.

## Persisted evidence and metrics

Research outcome payloads now carry:

- `price_at_detection`, `liquidity_at_detection`,
  `market_cap_at_detection`;
- `return_1m`, `return_5m`, `return_15m`, `return_30m`, `return_1h`,
  `return_3h`, `return_6h`, and `return_24h`;
- `max_return_1h`, `max_return_6h`, `max_return_24h` and corresponding
  maximum drawdowns;
- rug, honeypot, liquidity-removed, dead-token, and migration-completed flags;
- `time_to_2x`, `time_to_5x`, and `time_to_10x` where observable;
- outcome label, label version, methodology version, maturity state, freshness,
  and provider provenance.

Early-feature payloads now expose `turnover_1m`, `turnover_3m`,
`turnover_5m`, `turnover_15m`, `turnover_30m`, `turnover_1h`, turnover
velocity/acceleration, buyer/holder/trade velocities, liquidity growth, cohort
percentiles, and provider provenance. Runtime snapshots expose `contract`,
`AlphaIgnitionScore`, `SafetyConfidence`, `OpportunityConfidence`,
`paper_eligible`, and `execution_status`.

Research settings are dynamic and explicitly shadow-only: discovery liquidity
30K, preferred liquidity 75K, maximum age 24h, priority age 6h, minimum buyers
20, 15m turnover 0.20, 1h turnover 1.0, acceleration thresholds 0.5, and
minimum smart-wallet convergence 2. They are not production thresholds.

## Telegram renderer examples

These are renderer contract examples, not observed external sends:

```text
[EARLY_WATCH] MEME
Severity: INFO
State: WATCH
Signal state: WATCH
Chain: solana
Contract: <mint>
Age: 2m
Market cap: UNKNOWN
Liquidity: UNKNOWN
Turnover: UNKNOWN
Unique buyers: UNKNOWN
AlphaIgnitionScore: UNKNOWN
SafetyConfidence: UNKNOWN
OpportunityConfidence: UNKNOWN
Execution: EXECUTION_BLOCKED
Provider confidence: UNKNOWN
```

```text
[EARLY_WATCH] MEME
Severity: HIGH
State: HIGH_CONFLUENCE
Signal state: HIGH_CONFIDENCE_ALPHA
Chain: solana
Contract: <mint>
Age: 4m
Turnover: 0.42
Unique buyers: 12
AlphaIgnitionScore: 94
SafetyConfidence: 31
OpportunityConfidence: 88
Execution: EXECUTION_BLOCKED
Provider confidence: FRESH
```

Equivalent transition states are deduplicated; a meaningful WATCH to
EARLY_ALPHA escalation is emitted. Delivery timing persists
`signal_created_at`, `telegram_enqueued_at`, and `telegram_sent_at`, with
p50/p95/p99 aggregation.

## Local evidence counts

The checked-in baseline artifact is
`artifacts/research/pumpfun-forward/report.json`, generated at
`2026-09-21T10:45:55.491446+00:00`, before the label-aware report
extension:

| Measure | Local evidence |
|---|---:|
| launches observed | 1,278 |
| legacy `create` / `create_v2` | 16 / 1,262 |
| MemeRadar-before-Dex leads | 121 |
| lead median / p90 / p95 | 76.815456s / 1071.072466s / 6604.977256s |
| 1h-due observations | 995 |
| 6h/24h/72h/7d-due observations | 0 / 0 / 0 / 0 |
| measured executable winners | 0 at 2x/5x/10x/20x/50x/100x |
| Telegram delivery rows | 0 |
| stream gaps in latest health row | 1,408 |

The new report requires normalized observation rows (or an offline row array).
No local `DATABASE_URL` or `MEMERADAR_DATABASE_URL` was configured, and the
checked-in artifact contains aggregate fields rather than the new outcome rows.
Therefore the label-specific forward-shadow counts are:

- winner count: `0` in the checked-in baseline artifact;
- matured rug count: `INSUFFICIENT_SAMPLES`;
- matured dead/honeypot/neutral counts: `INSUFFICIENT_SAMPLES`;
- label-aware immature count: `INSUFFICIENT_SAMPLES`;
- current forward-shadow maturity status: `INSUFFICIENT_SAMPLES`.

The 995 one-hour-due observations and 0 measured winners are evidence of
pipeline history, not evidence that rejected candidates were safe or that
alpha was validated. The report does not zero-fill absent labels.

## Recall, controls, ablation, and latency

| Metric | Result | Status |
|---|---:|---|
| EARLY_WINNER_RECALL 2x/5x/10x | no label-aware sample | INSUFFICIENT_SAMPLES |
| false-positive rate | no eligible alert/outcome pairs | INSUFFICIENT_SAMPLES |
| false-negative rate | no eligible winner cohort | INSUFFICIENT_SAMPLES |
| median lead time / p90 lead time | unavailable from label-aware rows | INSUFFICIENT_SAMPLES |
| p95 Telegram latency | no delivery rows | INSUFFICIENT_SAMPLES |
| matched control pairs | no local outcome/control rows | INSUFFICIENT_SAMPLES |
| ablation contribution | fewer than 30 eligible samples | INSUFFICIENT_SAMPLES |

## Historical replay status

| Case | Status | Reason |
|---|---|---|
| HITBUY | BLOCKED_EXTERNAL | No compliant historical row locally. |
| Agrippa | BLOCKED_EXTERNAL | No compliant historical row locally. |
| MONITOR | BLOCKED_EXTERNAL | No compliant historical row locally. |
| GENIUS | BLOCKED_EXTERNAL | No compliant historical row locally. |
| familiars | BLOCKED_EXTERNAL | No compliant historical row locally. |
| astro | BLOCKED_EXTERNAL | No compliant historical row locally. |
| SPIKE | BLOCKED_EXTERNAL | No compliant historical row locally. |
| JEANPHIL | BLOCKED_EXTERNAL | No compliant historical row locally. |
| musebook | BLOCKED_EXTERNAL | No compliant historical row locally. |

## Verification

Post-commit local checks:

- `git diff --check`: PASS;
- `make lint`: PASS;
- `make typecheck`: PASS, 147 source files;
- `make test`: PASS, 1,456 passed, 21 skipped, 7 warnings;
- focused persistence regression: PASS, 5 passed;
- `make verify`: PASS, including lint, mypy, 1,456 tests, frontend
  lint/typecheck and 83 frontend tests, CSS contract, Compose config, secret
  scan, migration check, security review, and SBOM check.

Protected modes remain exactly:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Blockers

- `BLOCKED_EXTERNAL`: no compliant historical case datasets;
- `BLOCKED_EXTERNAL`: no configured Telegram credentials or external send
  acceptance;
- `INSUFFICIENT_SAMPLES`: elapsed 6h/24h/72h/7d outcome horizons and mature
  label rows are not locally available in the checked-in artifact;
- `BLOCKED_EXTERNAL`: Base protocol/provider identities and acceptance;
- `PARTIAL`: BNB Four.meme/PancakeSwap protocol identities and lifecycle
  replay remain to be verified.

No live execution setting was changed.
