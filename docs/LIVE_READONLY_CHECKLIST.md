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

## Free-first readiness tiers

The core read-only path does not require Helius, Birdeye or any paid/keyed
provider. It uses the standard Solana JSON-RPC adapter, DexScreener market and
reference-quote data, and MemeRadar's local deterministic wallet/risk engines.

| Tier | Required for the tier | Honest success state |
| --- | --- | --- |
| `CORE_FREE_READINESS` | local stack as configured, protected modes, Solana RPC, DexScreener and local engines | `READY_FOR_FREE_READ_ONLY_SHADOW` |
| `OPTIONAL_ENRICHMENT_READINESS` | any configured Helius/Birdeye/RugCheck/social/wallet/Ollama/Telegram enhancement | `PASS`, `DEGRADED`, `BLOCKED_EXTERNAL` or `OPTIONAL_UNCONFIGURED` |
| `FULL_PROVIDER_READINESS` | configured and healthy Helius + Birdeye enhancement paths | `PASS`, `DEGRADED`, `BLOCKED_EXTERNAL` or `OPTIONAL_UNCONFIGURED` |

`READY_FOR_FREE_READ_ONLY_SHADOW` is not production-live readiness and never
authorizes live-money execution. Missing optional configuration is
`UNCONFIGURED_OPTIONAL`; rate limits and network outages remain external
blockers. Use `make free-provider-doctor` for the aggregate matrix and
`python3 scripts/free_provider_doctor.py --no-network` for the deterministic
keyless boot/configuration check.

---

## Complete Provider Path Audit (9 External Provider Paths)

| Provider Path | Status | Env Vars | Doctor Command | Fail-Closed / Fallback Behavior |
|---|---|---|---|---|
| 1. Standard Solana RPC | `IMPLEMENTED / FREE CORE` | `SOLANA_RPC_URL` (defaults to public RPC) | `make solana-rpc-doctor` | Bounded standard JSON-RPC reads; explicit external/degraded status. |
| 2. Helius RPC / Stream | `IMPLEMENTED / OPTIONAL` | `HELIUS_API_KEY`, `HELIUS_RPC_URL`, stream URL | `make helius-doctor` / `make early-live-doctor` | Preferred enhancement/fallback only when configured; DAS remains Helius-only. |
| 3. Yellowstone gRPC | `NOT_IMPLEMENTED / FIXTURE_ONLY` | `YELLOWSTONE_GRPC_URL`, `YELLOWSTONE_X_TOKEN` | `python3 scripts/stream_integrity_doctor.py` | Marks feed `UNKNOWN` / `FIXTURE_ONLY`; fails closed. |
| 4. Shyft API | `NOT_IMPLEMENTED / FIXTURE_ONLY` | `SHYFT_API_KEY` | `python3 scripts/provider_doctor.py` | Marks feed `UNKNOWN` / `FIXTURE_ONLY`; fails closed. |
| 5. DexScreener API | `IMPLEMENTED / FREE DEFAULT` | `DEXSCREENER_API_URL` (key optional) | `make dexscreener-doctor` | Market/pair/reference quote/declared metadata only; bounded stale/degraded behavior. |
| 6. Birdeye API | `IMPLEMENTED / OPTIONAL` | `BIRDEYE_API_URL`, `BIRDEYE_API_KEY` | `make birdeye-doctor` | Optional market/discovery fallback/enrichment; not required for core. |
| 7. Raydium API / SDK | `IMPLEMENTED` | `RAYDIUM_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Verified `(program_id, discriminator)` identity routing. |
| 8. Jupiter API | `IMPLEMENTED / LOCKED` | legacy quote variables | `make paper-trading-doctor` | No live swap execution; custom URL/key alone does not bypass normalized quote port. |
| 9. Pump.fun / Solana Indexer | `IMPLEMENTED` | `PUMPFUN_API_BASE_URL` | `python3 scripts/provider_doctor.py` | Verified bonding curve state & graduation continuity. |

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
| `SOLANA_RPC_URL` | Optional | `https://api.mainnet.solana.com` | Standard Solana JSON-RPC endpoint; public endpoint is rate-limited/non-guaranteed |
| `HELIUS_API_KEY` / `HELIUS_RPC_URL` | Optional | Unconfigured (`UNCONFIGURED_OPTIONAL`) | Helius standard/enhanced enhancement |
| `BIRDEYE_API_KEY` / `BIRDEYE_API_URL` | Optional | Unconfigured (`UNCONFIGURED_OPTIONAL`) | Birdeye fallback/enrichment |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Optional | Unconfigured (`UNCONFIGURED_OPTIONAL`) | Telegram alert delivery only |

---

## Diagnostic & Doctor Commands

Run these doctor commands to verify environment readiness before live read-only operation:

```bash
# 0. Free-first aggregate and individual core doctors
make free-provider-doctor
python3 scripts/free_provider_doctor.py --no-network
make solana-rpc-doctor
make dexscreener-doctor

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
   - Missing optional credentials are `UNCONFIGURED_OPTIONAL`, not a core application failure.
   - Data feeds cleanly return `QualityState.UNKNOWN` or empty pages without HTTP 500 crashes.
   - Core Solana/DexScreener network failures are `BLOCKED_EXTERNAL`/`DEGRADED` and remain visible.
2. **Stream Gaps & Connection Loss**:
   - `StreamIntegrityTracker` detects missing block numbers or sequence gaps.
   - Freshness degrades from `FRESH` to `DEGRADED` / `UNKNOWN`.
   - Gaps fail closed and will **never** increase `AlphaScore` or trigger `ENTRY_READY`.
3. **Unverified Solana Protocols**:
   - Solana protocol routing uses verified `(program_id, discriminator/tag)` tuples.
   - Unverified program IDs default to `TODO_VERIFY` and fail closed.
4. **Thin Liquidity Wicks**:
   - Mark-price wicks with liquidity < $1,000, `is_sellable=False`, or impact > 1,000 bps are marked non-executable in `ExtremeWinnerOutcomeSnapshot`.
