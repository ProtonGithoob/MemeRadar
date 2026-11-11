# Alpha validation — 2026-11-11

**Result: NOT_PROVEN / INSUFFICIENT_EVIDENCE.** This checkpoint has no verified production launch inventory or independently matured real outcome cohort. Do not interpret passing code tests, fixture replay, observed mark-price peaks, or candidate scores as evidence of predictive alpha or a 10x–100x probability.

## P30 2026-11-11 engineering checkpoint

The caller-conduct feature is connected from persisted social calls through a versioned, point-in-time projection into the early shadow `FeatureSnapshot`. It retains provenance, sample/missingness state and the decision cutoff, and has no production score weight. P30 local `make verify` passed (1,650 backend, 34 integration deselected, 7 warnings; 86 frontend). Migration graph head is `0015_stream_verification_provenance`; persisted bounded stream-verification provenance improves evidence traceability but does not prove source completeness. No production launch inventory, independent setup cohort, matured outcomes, measured recall or predictive lift is added by these engineering checks. P30 browser and build environment limits are recorded in the verification ledger.

Pre-identity diagnostics share an atomic persistence transaction with their failed-slot gap, and a bounded exact-identity reconciliation projection is composed; the worker now attempts persisted recovery at startup and on a serialized timer. Neither gap recovery nor the read projection proves source coverage or a complete observable-universe denominator. The opt-in paper entry/exit worker is composed but was not started against a runtime portfolio/provider, and no executable paper outcome cohort is available. Therefore all target multiples and predictive statistics below remain unmeasured.

## Cohort and provenance

| Requirement | Current evidence |
| --- | --- |
| Observable launch universe | NOT_MEASURED. No authorized provider coverage range or verified production historical database was available for this run. |
| Canonically verified production launches | NOT_MEASURED. Reconciliation was verified only against isolated PostgreSQL fixtures. |
| Independent setup count | NOT_MEASURED. Fixture rows are not real setups and are excluded from research claims. |
| Matured real outcomes | NOT_MEASURED. No production outcome source was reconciled or matured. |
| Decision-time evidence snapshots | Immutable early stage snapshots exist; persisted social calls now contribute a versioned caller-conduct shadow feature only when available by the checkpoint. No accepted independent forward cohort has been collected. |
| Executable outcome prices | NOT_MEASURED. No real buy/sell quote replay or executable paper outcome cohort was available. |

The read-only `scripts/reconcile_pumpfun_launches.py` inventory classifies exact program/instruction evidence and the forward report excludes unverified launch-linked rows. It was not run against a verified production history, and no fixture count is promoted to a production denominator. Caller-conduct projections retain their version, provenance, sample/missingness state and point-in-time cutoff; they have no production scoring weight pending real chronological evaluation. Original decisions remain unchanged.

## Evaluation contract

For a valid future cohort, freeze a decision snapshot at time `T`, including source references and each feature's occurred/observed/ingested timestamps. Use only evidence available by `T`. Deduplicate by canonical launch/event identity. Split chronologically, purge overlapping label windows, and compare against matched eligible-launch, simple-volume, liquidity/risk, current-baseline and same-cohort random baselines.

Measure theoretical observed mark-price and executable paper outcomes separately. Define entry reference, executable quote, fee/slippage/impact assumptions, liquidity, holding horizon, token inactivity, missing prices and right-censoring before evaluation. Attach outcomes after maturity without editing earlier snapshots. Report denominators, coverage and uncertainty; do not report calibrated probabilities unless calibration has been demonstrated.

## Target report status

| Target multiple | Eligible/matured denominator | Precision / recall / lift | State |
| --- | --- | --- | --- |
| 2x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |
| 5x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |
| 10x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |
| 20x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |
| 50x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |
| 100x | NOT_MEASURED | NOT_COMPUTED | NOT_PROVEN |

There are no defensible values for precision, recall, lift, PR-AUC, calibration error, Brier score, time-to-target, drawdown or expectancy in this report. No probabilities are asserted.

## Next evidence required

1. A verified provider/source coverage contract and read-only historical inventory with row counts by launch classification.
2. Immutable, point-in-time decisions over a prospectively defined observable universe, including rejected/pre-identity events and unresolved gaps.
3. Independent matured outcomes with explicit censoring and executable-price semantics.
4. Chronological out-of-sample evaluation against matched baselines with sample sizes and uncertainty intervals.

Engineering evidence and unresolved operational gates are recorded in [E2E acceptance](../audits/E2E_ACCEPTANCE_REPORT.md) and [product readiness](../audits/FINAL_PRODUCT_READINESS.md).
