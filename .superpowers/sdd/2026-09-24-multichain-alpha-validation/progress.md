# SDD ledger — plan: docs/superpowers/plans/2026-09-24-multichain-alpha-validation.md

Pre-flight: Task 1 produces Compose/PostgreSQL evidence consumed by Task 6 reporting; Task 2 produces durable stream diagnostics consumed by Task 6 reporting; Tasks 3–5 produce provider/API surfaces consumed by Task 6 verification. These interfaces are sequentially independent except for shared provider metadata and protected-mode configuration, which remain unchanged.

Ruling: `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` cannot be written because the host-mounted `.codex` directory is read-only; use this ledger plus `docs/reports/` as the durable fallback and report the limitation.

Task 1: BLOCKED_EXTERNAL — `make compose-config` and migration graph passed, but `MEMERADAR_START_TIMEOUT_SECONDS=180 bash scripts/start.sh` stopped before container creation with Docker socket permission denied; no DB row or restart evidence was fabricated. Evidence: `docs/reports/forward-shadow-live-acceptance-2026-09-24.md`.

Task 2: COMPLETE LOCALLY — commit `09f850b` adds durable stream-gap diagnostics, reconnect metadata, bounded finalized Solana `getBlocks`/`getBlock` recovery through the existing decoder, and persistence migration `0012_stream_gap_diagnostics`. Focused reliability tests pass; live unresolved-gap counts remain externally unverified.

Task 3: COMPLETE LOCALLY / EXTERNAL ACCEPTANCE BLOCKED — Raydium CPMM/CLMM pool normalization and bounded CPMM quote, Jupiter Swap API V2 quote/order parsing, explicit fallback routing, and optional Helius behavior are covered by focused tests. No protocol deployment or credentialed Jupiter acceptance was claimed.

Task 4: COMPLETE LOCALLY / DEPLOYMENTS TODO_VERIFY — generic read-only EVM identities include Robinhood mainnet `4663` and testnet constant `46630`, BNB, Base, Ethereum, Arbitrum, Avalanche, Polygon and Unichain; Four.meme/Pancake/Uniswap/Aerodrome/Par/OpenLaunch candidates remain non-authoritative until on-chain evidence is supplied. Blockscout and eth_call sellability are optional read-only seams.

Task 5: COMPLETE LOCALLY / PARTIAL API PROJECTION — `apps/mcp/src/memeradar_mcp` provides the requested read-only tool names over existing `/v1` API routes using stdlib JSON-RPC stdio. Research/report projections not present in the API return explicit `NOT_EXPOSED`; no mutation or execution tool exists. Focused MCP tests pass.

Task 6: COMPLETE LOCALLY / EXTERNAL ACCEPTANCE BLOCKED — license and integration matrices, exact per-chain status, horizon/sample evidence, stream-gap before/after limits, provider disagreements, and Telegram/alpha metric limits are recorded in `docs/reports/multichain-alpha-validation-2026-09-24.md`. `git diff --check`, `make lint`, `make typecheck`, `make test`, and `make verify` pass; coverage is 79% with zero-point delta from the prior 79% baseline. Database, credentialed providers, Telegram, protocol deployment verification, and mature outcome evidence remain external blockers.

Task 7: COMPLETE LOCALLY / EXTERNAL ACCEPTANCE BLOCKED — added the strict machine-readable `ProtocolCertificationRecord` projection without changing the proven Pump.fun decoder route; decoder-only and EVM candidate records remain `TODO_VERIFY`. Added the separate `DataQualityConfidence` projection by reusing existing evidence coverage/freshness confidence and exposed it through early runtime, alert and read API projections. Focused registry/score/alert tests and Ruff pass. PostgreSQL, live stream continuity, Jupiter, and Telegram probes remain blocked by host/provider reachability; no external success was fabricated.

Task 8: COMPLETE LOCALLY / EXTERNAL ACCEPTANCE BLOCKED — recorded the exact acceptance boundary, test evidence, chain matrix, mandatory answers, and remaining blockers in `docs/reports/real-multichain-acceptance-2026-09-24.md`. The report does not promote fixture evidence to live/provider/Telegram/PAPER acceptance.
