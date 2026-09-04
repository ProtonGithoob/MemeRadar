# MemeRadar — Real-World Read-Only Validation & Calibration Runbook

**Version**: `v1.0.0`  
**Scope**: 7-Day Initial Read-Only Smoke Test & 30-Day Out-of-Sample Shadow Calibration  
**Operating Modes**: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`  
**Phase 12 Live Execution**: **HARD-LOCKED**

---

## 1. Pre-Flight Verification Checklist

Before initiating live read-only shadow ingestion:

1. **Verify Operating Invariants**:
   ```bash
   grep -E "^(ANALYSIS_ONLY|PAPER_TRADING|MANUAL_EXECUTION|AUTO_EXECUTION)" .env || true
   ```
   Ensure `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.

2. **Verify Host Ports & Services**:
   - PostgreSQL: `localhost:55432` (container port 5432)
   - Redis: `localhost:56379` (container port 6379)
   - API: `http://localhost:18000` (container port 8000)
   - Web: `http://localhost:13000` (container port 3000)

3. **Run All Diagnostic Doctors**:
   ```bash
   python3 scripts/provider_doctor.py
   python3 scripts/early_live_doctor.py
   python3 scripts/birdeye_doctor.py
   python3 scripts/stream_integrity_doctor.py
   python3 scripts/paper_trading_doctor.py
   ```

4. **Verify Health Endpoints**:
   - Live check: `curl -fsS http://localhost:18000/health/live`
   - Ready check: `curl -fsS http://localhost:18000/health/ready`

---

## 2. 7-Day Initial Read-Only Smoke Test Protocol

**Objective**: Verify system stability, stream gap detection, provider rate limits, and shadow paper order logging over a 7-day continuous window without live order submission.

### Daily Procedures (Days 1–7)

- **Day 1: Stream & Credential Verification**
  - Check Helius and Birdeye provider health: `curl -fsS http://localhost:18000/v1/provider-health`
  - Verify `QualityState.FRESH` vs `DEGRADED` transitions.
  - Confirm `StreamIntegrityTracker` detects block gaps and fails closed (`AlphaScore` never inflated on gaps).

- **Day 2–3: Early Signal & Candidate Auditing**
  - Inspect `/v1/early-radar` candidate signals.
  - Confirm `ENTRY_READY` and `HIGH_CONFLUENCE` signals log paper positions in `positions` database table with mode `PAPER`.
  - Confirm `execution_eligible` remains `False` across all responses.

- **Day 4–5: Graph & Creator Reputation Verification**
  - Search newly observed creators on `/wallet-graph`.
  - Verify `CreatorOutcomeGraph.get_subgraph` filters by date range, venue, and outcome class cleanly.
  - Check `CreatorReputationSnapshot` displays all 20 evidence fields and flags unproven creators (`UNPROVEN`, sample count < 3).

- **Day 6–7: 7-Day Smoke Sign-Off Audit**
  - Compile 7-day telemetry summary (`consecutive_failures`, quota remaining, stream gap log).
  - Verify zero HTTP 500 crashes and zero unhandled exceptions.
  - Confirm zero live wallet transaction signatures attempted.

---

## 3. 30-Day Out-of-Sample Calibration Runbook

**Objective**: Accumulate live shadow trade signals across a 30-day rolling window to conduct out-of-sample feature separability and convex exit policy calibration.

### Calibration Sequence (Day 30)

1. **Export Shadow Trade Cohort**:
   ```bash
   python3 scripts/replay_dataset.py --output fixtures/research/live_shadow_dataset.json
   ```

2. **Run Separability Study on Live Shadow Data**:
   ```bash
   python3 scripts/separability_study.py --dataset fixtures/research/live_shadow_dataset.json --output fixtures/research/live_shadow_separability.json
   ```
   - Verify sample adequacy (`sample_count >= 30`).
   - Check out-of-sample precision and rug rejection rate.

3. **Run Convex Exit Policy Replay**:
   ```bash
   python3 scripts/convex_exit_research.py --dataset fixtures/research/live_shadow_trade_dataset.json --output fixtures/research/live_shadow_exit_results.json
   ```
   - Evaluate `balanced-convex-v1`, `aggressive-runner-v1`, `conservative-protection-v1`.
   - Identify `BEST_SYNTHETIC_CANDIDATE` or live candidate version with highest risk-adjusted paper expectancy.

4. **Strategy Promotion Gate Evaluation**:
   ```bash
   python3 scripts/winner_vs_rug_optimizer.py
   ```
   - Evaluate promotion criteria: TRAIN/VAL/TEST split, out-of-sample expectancy lift >= +0.5x, fail-closed security invariants intact.
   - Require explicit human operator sign-off before strategy promotion.

---

## 4. Emergency Procedures & Incident Response

- **Provider Outage or Rate Limit (HTTP 429)**:
  - Provider transitions to `DEGRADED` / `DOWN`.
  - Ingestion falls back to `QualityState.UNKNOWN` or `BLOCKED_EXTERNAL`.
  - System remains operational in fail-closed state.

- **Stream Gap Detection**:
  - `StreamIntegrityTracker` flags missing slot/block sequence.
  - Freshness set to `UNKNOWN`. All early candidate scores default to `REJECT/LOW` until gap recovery completes.

- **Unwanted Execution Attempt Alert**:
  - If any component attempts live wallet transaction signing, `ControlAction` immediately aborts process with exit code 1.
