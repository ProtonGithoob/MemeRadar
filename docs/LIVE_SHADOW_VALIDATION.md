# MemeRadar — Real-World Read-Only Validation & Calibration Runbook

**Version**: `v1.0.0`  
**Scope**: 7-Day Initial Read-Only Smoke Test & 30-Day Out-of-Sample Shadow Calibration  
**Operating Modes**: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`  
**Phase 12 Live Execution**: **HARD-LOCKED**

## Free-first shadow readiness

The read-only shadow path is intentionally usable with approximately $0 in
mandatory external API spend. Core readiness uses the generic Solana RPC
adapter, DexScreener market/reference data and MemeRadar's local deterministic
wallet/risk engines. Helius, Birdeye, RugCheck authentication, social
analytics, external wallet enrichment, Ollama and Telegram remain optional.

The doctor and shadow status surfaces keep these tiers separate:

| Tier | Meaning |
| --- | --- |
| `CORE_FREE_READINESS` | Solana RPC, DexScreener, local engines, protected modes and local stack checks satisfy the free read-only contract |
| `OPTIONAL_ENRICHMENT_READINESS` | Configured optional providers are healthy, degraded, rate-limited or unavailable |
| `FULL_PROVIDER_READINESS` | Helius and Birdeye enhancement paths are both configured and healthy |

`READY_FOR_FREE_READ_ONLY_SHADOW` permits observation and paper analysis only.
It never means production-live or live-money readiness. A public RPC/API
failure is reported as `BLOCKED_EXTERNAL` or `DEGRADED`; absent optional
credentials are `OPTIONAL_UNCONFIGURED`.

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
   make free-provider-doctor
   make solana-rpc-doctor
   make dexscreener-doctor
   python3 scripts/provider_doctor.py
   python3 scripts/early_live_doctor.py
   python3 scripts/birdeye_doctor.py
   python3 scripts/stream_integrity_doctor.py
   python3 scripts/paper_trading_doctor.py
   ```

4. **Verify Health & Provider Readiness**:
   - Live check: `curl -fsS http://localhost:18000/health/live`
   - Provider health: `curl -fsS http://localhost:18000/v1/providers/health`
   - Shadow status report: `python3 scripts/shadow_status.py` (`make shadow-status`)

### Provider Set & Operational States

- **Free core provider set**:
  - **Standard Solana RPC Adapter** (`SolanaRpcAdapter`): bounded standard JSON-RPC reads and transaction-history primitives where the endpoint supports them.
  - **DexScreener Adapter** (`DexScreenerAdapter`): normalized Solana market snapshots, deterministic pair discovery, paper reference quotes and declared project links.
  - **Local MemeRadar analysis**: wallet tracking/scoring/graphs/flows and deterministic token-risk checks.
- **Optional enhancement set**:
  - **Helius RPC / Stream Adapter** (`HeliusRpcAdapter`): configured standard/enhanced chain reads and optional stream; Helius-only DAS is never emulated by public RPC.
  - **Birdeye REST Adapter** (`BirdeyeRestAdapter`): optional market/discovery fallback or enrichment; its stream remains a separate capability.
  - RugCheck public/authenticated evidence, existing compliant social analytics, injected external wallet enrichment, Ollama/external narrative and Telegram alerts.

- **Explicit Readiness & Collection Classifications**:
  - `STACK_READY`: Local containers (PostgreSQL, Redis, API, Web) are healthy and responding.
  - `CORE_FREE_READINESS`: Standard Solana RPC and DexScreener are available, with local engines and protected modes intact.
  - `OPTIONAL_ENRICHMENT_READINESS`: Optional providers are reported separately and never required for the core.
  - `FULL_PROVIDER_READINESS`: Helius and Birdeye are both active and `FRESH` when the full enhancement tier is explicitly needed.
  - `DEGRADED`: Partial provider degradation; candidate scoring degrades fail-closed.
  - `BLOCKED_EXTERNAL`: Provider keys missing or provider endpoints returning error codes.
  - `LIVE_SHADOW_COLLECTION_ACTIVE`: Stack is ready, free core readiness is satisfied and real provider-originated observations are flowing.
  - `NOT_ACTIVE`: Free core is `BLOCKED_EXTERNAL` or the stack is offline.

- **Durable Shadow Run Identity & Invariants**:
  - Initiating `make shadow-start` creates a durable run identity (`run_id`, `run_started_at`) stored in `artifacts/research/live-shadow/current_run.json`. Existing run files are preserved in `artifacts/research/live-shadow/runs/`.
  - **Telemetry Invariant (`UNKNOWN != ZERO`)**: Unqueried or unmeasured telemetry (stream gaps, recovery failures, matured outcome horizons) are explicitly reported as `UNKNOWN` / `NOT_AVAILABLE` (`null` in JSON), never fabricated as `0`.

---

## 2. 7-Day Initial Read-Only Smoke Test Protocol

**Objective**: Verify system stability, stream gap detection, provider rate limits, and shadow paper order logging over a 7-day continuous window without live order submission.

### Daily Procedures (Days 1–7)

- **Day 1: Core, Stream & Credential Verification**
  - Check free core and optional provider health: `curl -fsS http://localhost:18000/v1/providers/health`
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

> [!NOTE]
> Research Candidate Status: `balanced-convex-v1`, `aggressive-runner-v1`, and `conservative-protection-v1` are unvalidated research candidates derived from synthetic replay. `balanced-convex-v1` is `BEST_SYNTHETIC_CANDIDATE` only (not production optimal or automatically selected for live execution). Live shadow data collection may reject all three candidates.

### Calibration Sequence (Day 30)

1. **Export Shadow Trade Cohort**:
   ```bash
   python3 scripts/replay_dataset.py --output artifacts/research/live-shadow/dataset.json
   ```

2. **Run Separability Study on Live Shadow Data**:
   ```bash
   python3 scripts/separability_study.py --dataset artifacts/research/live-shadow/dataset.json --output artifacts/research/live-shadow/separability.json
   ```
   - Verify sample adequacy (`sample_count >= 30`).
   - Check out-of-sample precision and rug rejection rate.

3. **Run Convex Exit Policy Replay**:
   ```bash
   python3 scripts/convex_exit_research.py --dataset artifacts/research/live-shadow/dataset.json --output artifacts/research/live-shadow/convex_exit_results.json
   ```
   - Evaluate `balanced-convex-v1`, `aggressive-runner-v1`, `conservative-protection-v1`.
   - Identify candidate policy with highest risk-adjusted paper expectancy on real shadow trade history.

4. **Strategy Promotion Gate Evaluation**:
   ```bash
   python3 scripts/winner_vs_rug_optimizer.py
   ```
   - Evaluate 7-point promotion criteria:
     1. Baseline Expectancy Lift: Statistically significant positive lift over default baseline strategy.
     2. Out-of-Sample Sample Adequacy: `sample_count >= 30` independent live shadow trade outcomes.
     3. Drawdown & Rug Bounds: Max paper drawdown within defined risk parameters; zero unhandled severe rugs.
     4. Execution Feasibility: Realized paper impact <= 100 bps; slippage-adjusted paper execution validated.
     5. Time-Cohort Stability: Consistent positive expectancy across distinct 7-day time sub-cohorts.
     6. Safety Invariants Intact: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
     7. Human Review: Required explicit operator sign-off and signed approval record prior to promotion.

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
