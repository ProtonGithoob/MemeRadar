# MemeRadar — Live Read-Only Acceptance Checklist

## Operating Modes (Hard Invariants)

```bash
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

> [!IMPORTANT]
> Live transaction submission, wallet signing, and real-money execution are permanently locked. `auto_execution` is hard-coded to `"LOCKED"` and `execution_eligible` remains `False` across all read models and API endpoints.

---

## Complete Provider Path Audit (8 External Provider Paths)

| Provider Path | Status | Env Vars | Doctor Command | Fail-Closed / Fallback Behavior |
|---|---|---|---|---|
| 1. Helius RPC / Stream | `IMPLEMENTED` | `HELIUS_API_KEY`, `HELIUS_RPC_URL` | `python3 scripts/early_live_doctor.py` | Falls back to synthetic fixtures (`BLOCKED_EXTERNAL`). |
| 2. Yellowstone gRPC | `NOT_IMPLEMENTED / FIXTURE_ONLY` | `YELLOWSTONE_GRPC_URL`, `YELLOWSTONE_X_TOKEN` | `python3 scripts/stream_integrity_doctor.py` | Marks feed `UNKNOWN` / `FIXTURE_ONLY`; fails closed. |
| 3. Shyft API | `NOT_IMPLEMENTED / FIXTURE_ONLY` | `SHYFT_API_KEY` | `python3 scripts/provider_doctor.py` | Marks feed `UNKNOWN` / `FIXTURE_ONLY`; fails closed. |
| 4. Birdeye API | `IMPLEMENTED` | `BIRDEYE_API_KEY` | `python3 scripts/birdeye_doctor.py` | Returns `QualityState.UNKNOWN` on missing key or 429. |
| 5. DexScreener API | `IMPLEMENTED` | `DEXSCREENER_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Keyless public read; degrades freshness on timeout. |
| 6. Raydium API / SDK | `IMPLEMENTED` | `RAYDIUM_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Verified `(program_id, discriminator)` identity routing. |
| 7. Jupiter API | `IMPLEMENTED` | `JUPITER_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Paper trade quote routing only; no live swap execution. |
| 8. Pump.fun / Solana Indexer | `IMPLEMENTED` | `PUMPFUN_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Verified bonding curve state & graduation continuity. |

---

## Required Environment Variables

| Variable | Required | Default / Fallback | Description |
|---|---|---|---|
| `ANALYSIS_ONLY` | Yes | `true` | Enforces read-only analysis mode |
| `PAPER_TRADING` | Yes | `true` | Enables paper trading simulation only |
| `MANUAL_EXECUTION` | Yes | `false` | Disables manual live trade execution |
| `AUTO_EXECUTION` | Yes | `false` | Disables automated live trade execution |
| `DATABASE_URL` | Optional | `sqlite:///:memory:` | Local PostgreSQL database URI |
| `REDIS_URL` | Optional | `memory://` | Local Redis URI |
| `HELIUS_API_KEY` | Optional | None (`BLOCKED_EXTERNAL`) | Helius RPC/WebSocket API key |
| `BIRDEYE_API_KEY` | Optional | None (`BLOCKED_EXTERNAL`) | Birdeye Market API key |
| `TELEGRAM_BOT_TOKEN` | Optional | None (`DISABLED`) | Telegram alert bot token |

---

## Diagnostic & Doctor Commands

Run these doctor commands to verify environment readiness before live read-only operation:

```bash
# 1. General Environment and Provider Doctor
python3 scripts/provider_doctor.py

# 2. Early-Live Ingestion and Provider Doctor
python3 scripts/early_live_doctor.py

# 3. Birdeye Specific Read-Only Doctor
python3 scripts/birdeye_doctor.py

# 4. Stream Integrity and Gap Recovery Doctor
python3 scripts/stream_integrity_doctor.py

# 5. Paper Trading Engine Doctor
python3 scripts/paper_trading_doctor.py

# 6. Safe Live Shadow Startup (Enforces Invariants & Creates Run Identity)
bash scripts/start-shadow.sh  # or make shadow-start

# 7. Shadow Status & Daily Telemetry Report
python3 scripts/shadow_status.py  # or make shadow-status
```

---

## Degraded Mode & Fail-Closed Behavior

1. **Missing Provider Credentials**:
   - Status transitions to `BLOCKED_EXTERNAL`.
   - Data feeds cleanly return `QualityState.UNKNOWN` or empty pages without HTTP 500 crashes.
2. **Stream Gaps & Connection Loss**:
   - `StreamIntegrityTracker` detects missing block numbers or sequence gaps.
   - Freshness degrades from `FRESH` to `DEGRADED` / `UNKNOWN`.
   - Gaps fail closed and will **never** increase `AlphaScore` or trigger `ENTRY_READY`.
3. **Unverified Solana Protocols**:
   - Solana protocol routing uses verified `(program_id, discriminator/tag)` tuples.
   - Unverified program IDs default to `TODO_VERIFY` and fail closed.
4. **Thin Liquidity Wicks**:
   - Mark-price wicks with liquidity < $1,000, `is_sellable=False`, or impact > 1,000 bps are marked non-executable in `ExtremeWinnerOutcomeSnapshot`.
