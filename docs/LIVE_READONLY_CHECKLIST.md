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
.venv/bin/python scripts/provider_doctor.py

# 2. Early-Live Ingestion and Provider Doctor
.venv/bin/python scripts/early_live_doctor.py

# 3. Birdeye Specific Read-Only Doctor
.venv/bin/python scripts/birdeye_doctor.py

# 4. Stream Integrity and Gap Recovery Doctor
.venv/bin/python scripts/stream_integrity_doctor.py

# 5. Paper Trading Engine Doctor
.venv/bin/python scripts/paper_trading_doctor.py
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
