# Codex Handoff — Frontend / Backend Parity

Resume from the exact current repository state. Do not restart completed production-readiness or Alpha Caller work.

Read only these first:

1. `AGENTS.md`
2. `docs/STATUS.md`
3. `docs/CODEX_FRONTEND_BACKEND_PARITY.md`
4. `docs/superpowers/specs/2026-09-07-frontend-backend-parity-design.md`
5. `docs/superpowers/plans/2026-09-07-frontend-backend-parity.md`

Then inspect only the existing files required by the active task.

Mission: fix backend/frontend parity with minimum duplication and minimum context usage. The current key gap is that runtime Settings contains many provider/chain/social/Telegram/narrative parameters while the control plane dynamically exposes only six fields and the web Settings page is read-only/hard-coded.

Execute the plan exactly task-by-task with TDD.

Priorities:
- metadata-driven safe runtime settings registry;
- ADMIN dynamic mutation with version/hash/audit;
- write-only/masked secrets;
- Telegram notification + ingestion configuration;
- X/social/website capability configuration;
- Solana/Helius, DexScreener/Birdeye, RugCheck, wallet provider, narrative/LLM, BNB/Robinhood settings;
- provider health/config parity;
- multichain shell + universal search;
- route-by-route frontend/backend parity;
- `/readiness` and canonical research surface where backend projection exists;
- complete desktop/mobile browser acceptance.

Do not create duplicate engines or browser business logic. Settings owns configuration; Providers owns runtime health. Never return or render raw secrets.

Keep protected modes exactly unchanged:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Do not change current `NOT_PRODUCTION_READY` merely because UI work passes; real-data/live-shadow production gates remain independent.

For each task:

```text
inspect minimum required files
-> failing focused tests
-> smallest coherent implementation
-> focused verification
-> STATUS evidence
-> commit/push
-> continue
```

Use existing components/contracts before adding new ones. Avoid broad repo rereads after startup; use `rg`, targeted files and current STATUS checkpoints to minimize token/context cost.

Run `make verify` only at major/final checkpoints; use focused tests between tasks. Preserve the four unrelated WIP files and all concurrent work. Before stopping, record exact parity gaps remaining, tests, blockers and next unfinished task in `docs/STATUS.md`.
