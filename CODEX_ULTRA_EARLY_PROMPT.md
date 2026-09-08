# Codex Ultra-Early Execution Handoff

Use this prompt from the MemeRadar working directory after syncing `main`.

```text
You are the principal engineer continuing Rasman1234/MemeRadar.

The operator has explicitly approved the Ultra-Early Detection and Shadow Execution design, Option A. Your job is to implement it autonomously, test-first, checkpoint-by-checkpoint, and push every coherent checkpoint to GitHub.

DO NOT START PHASE 12 LIVE TRADING.
DO NOT ENABLE REAL-MONEY EXECUTION.
DO NOT CREATE OR USE A WALLET SIGNER.

Mandatory protected modes throughout this work:
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false

FIRST ACTIONS — DO THEM NOW, WITHOUT ASKING ROUTINE QUESTIONS:
1. `git status --short --branch`
2. Fetch/pull the latest `main` safely and confirm local/remote state before editing. Preserve unrelated local work; do not force-push.
3. Read `AGENTS.md` completely.
4. Read `README.md`, `docs/STATUS.md`, `docs/SCORING_AND_RISK.md`, `docs/PROVIDERS.md`, `docs/SECURITY.md`, `docs/TESTING.md` and relevant architecture/data-model docs.
5. Read the current canonical contracts completely:
   `docs/SCORING_AND_RISK.md`, `docs/PROVIDERS.md`, `docs/SECURITY.md`,
   `docs/TESTING.md`, and `docs/STATUS.md`.
6. Inspect the existing implementation before editing, especially:
   - packages/application/src/memeradar_application/correlation.py
   - packages/application/src/memeradar_application/alpha_strategy.py
   - packages/application/src/memeradar_application/decision_engine.py
   - packages/application/src/memeradar_application/paper_execution.py
   - packages/application/src/memeradar_application/backtesting.py
   - packages/application/src/memeradar_application/calibration.py
   - packages/application/src/memeradar_application/call_performance.py
   - packages/application/src/memeradar_application/read_api.py
   - packages/providers/src/memeradar_providers/protocol_stream.py
   - packages/providers/src/memeradar_providers/protocol_registry.py
   - packages/providers/src/memeradar_providers/helius_stream.py
   - packages/providers/src/memeradar_providers/birdeye_stream.py
   - packages/providers/src/memeradar_providers/launchpad_dex.py
   - packages/persistence/src/memeradar_persistence/*
   - apps/api/src/memeradar_api/read.py
   - apps/web/src/app/components/radar.tsx
   - apps/web/src/app/tokens/[tokenId]/page.tsx
8. Audit what is already implemented. Reuse it. Do not duplicate existing E6/E8/E11 hardening merely because the new plan names a capability again.

EXECUTION ORDER:
Implement the approved plan task-by-task from Task 1 through Task 13. Use TDD. For every task:
- inspect the affected current code/tests first;
- write or update a focused failing test;
- verify RED for the intended missing behavior;
- implement the smallest coherent provider-independent change;
- run focused tests;
- run lint/typecheck for touched areas;
- update documentation/status when behavior or checkpoint changes;
- commit with a small coherent commit;
- push to origin/main when authenticated access is available;
- continue immediately to the next unblocked task.

DO NOT STOP FOR ROUTINE APPROVAL.
Normal repository actions are pre-approved under AGENTS.md: file reads/writes, tests, package-local installs, Docker/local test resources, builds, migrations, benchmarks, read-only provider doctors, git add/commit/fetch/pull/push and documentation updates. If the runtime UI itself forces an approval boundary, use the broadest safe persistent approval available, then continue.

CORE PRODUCT OBJECTIVE:
MemeRadar should identify new Solana meme launches at the earliest trustworthy event boundary and determine whether they are worth WATCH/EARLY_WATCH/STRONG_SETUP/ENTRY_READY before downstream social-call channels report the move, without sacrificing fail-closed risk controls.

Implement/reconcile these capabilities:
- verified direct Solana/protocol first detection;
- Pump.fun/PumpSwap launch/migration detection;
- Raydium/Meteora pool lifecycle detection where the verified registry already supports it;
- Helius/stream-first ingestion and Birdeye fallback/corroboration;
- first-seen and stage latency measurements;
- 1s/5s/15s/30s/60s/3m/5m event-time micro-windows;
- buy velocity and acceleration;
- quote/SOL inflow velocity and acceleration;
- unique-buyer acceleration/repeat-buyer behavior;
- market/volume/liquidity/bonding-curve acceleration;
- creator/deployer, first-block bundle, sniper/fresh-wallet and shared-funder evidence;
- existing holder/flow/sellability/smart-wallet/confluence integration;
- deterministic `early-score-v1` with version/config hash/evidence/reason codes;
- confidence separate from score magnitude;
- hard risk gates authoritative over score;
- gated ENTRY_READY state;
- automatic SHADOW/PAPER entry only, using the existing paper ledger and QuotePort;
- no signer and no ExecutionPort submit call from the shadow path;
- forward labels at +1m/+3m/+5m/+15m/+30m/+1h;
- $50K/$100K/$250K market-cap milestone research labels where market-cap evidence exists;
- no-lookahead replay/backtesting/calibration;
- external/public call timestamp benchmark with MemeRadar lead-time measurement;
- API/UI/Telegram ultra-early projection;
- explicit `AUTO EXECUTION: LOCKED` operator status;
- detection/decision/shadow latency observability;
- live read-only `early-live-doctor` that reports exactly PASS/FAIL/BLOCKED_EXTERNAL without exposing secrets.

CRITICAL ARCHITECTURE RULES:
- Reuse the existing canonical decoder, protocol registry and stream-integrity system.
- Live/replay/backfill must converge through the same decoder/normalizer path.
- Route protocols by verified `(program_id, discriminator/tag)`, never discriminator-only.
- Unknown/unverified identity, unresolved gap, revert/conflict or stale critical evidence must fail closed.
- Provider SDKs/raw payload models stay outside domain/application.
- LLM is not in the latency-critical decision path and can never authorize ENTRY_READY.
- Social evidence is corroboration and may be missing without being fabricated as safe.
- Do not interpret absent sniper/bundle labels as clean launch evidence.
- Do not infer launch time from arrival time when launch time is unknown.
- Do not use future observations in feature windows.
- Do not claim production latency/SLO from synthetic benchmarks.

EARLY SCORE BASELINE:
OrganicFlowAcceleration 25%
WalletQuality 20%
OnChainSafety 20%
LiquidityAndSellability 15%
LaunchMomentum 10%
SmartMoneyConfluence 5%
SocialCorroboration 5%

Treat these as versioned/configurable initial hypotheses and preserve calibration rather than hard-coding undocumented magic numbers.

STATE BANDS:
0-39 REJECT/LOW
40-59 WATCH
60-74 EARLY_WATCH
75-84 STRONG_SETUP
85-100 HIGH_CONFLUENCE

ENTRY_READY is NOT just score >= 85. It additionally requires minimum confidence, all hard gates passed, critical fresh evidence, sellability/quote for intended paper size, acceptable liquidity/price impact and intact protected modes.

SHADOW ENTRY SAFETY TEST:
Create tests with poison signer/execution stubs that throw if invoked. A successful shadow/paper ENTRY_READY path must prove those stubs are never touched.

LIVE PROVIDER BLOCKERS:
If Helius/Birdeye/Telegram/market/provider credentials or endpoints are absent, complete every fixture/fake/contract/doctor/replay task anyway. Mark only the real external acceptance `BLOCKED_EXTERNAL`. Never fabricate PASS and never stop all work because of one external blocker.

QUALITY GATE BEFORE FINAL COMPLETION:
- focused unit/integration/replay tests for each task;
- no-lookahead replay tests;
- property/invariant checks that protected modes remain locked;
- frontend lint/typecheck/test and targeted Playwright;
- `make verify`;
- `make integration-test` when DB is available, otherwise report its existing skip accurately;
- `make early-live-doctor` and record PASS/FAIL/BLOCKED_EXTERNAL;
- secret scan/security review;
- `git diff --check`;
- deterministic replay/benchmark repeated-run equality where applicable;
- final git local/remote SHA comparison and clean working tree.

STATUS / CHECKPOINT RULE:
Update `docs/STATUS.md` after every material task/checkpoint so a new Codex session can resume without chat history. During this extension, Phase 12 remains locked. Do not advance to Phase 12 when this plan completes.

FINAL EXPECTED VERDICT, ONLY IF EVIDENCE SUPPORTS IT:
`ULTRA_EARLY_DETECTION_READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING_AUTO_EXECUTION_LOCKED`

If external live provider evidence is unavailable, keep the appropriate live acceptance item `BLOCKED_EXTERNAL` while still completing all keyless work.

At the end, report a compact table with:
- each Task 1-13 status;
- focused/full verification result;
- protected mode values;
- live provider doctor verdict;
- any true external blockers;
- final commit SHA;
- origin/main SHA;
- working-tree cleanliness.

BEGIN NOW. Do not wait for another user message and do not ask routine implementation questions.
```
