# MemeRadar Frontend Modernization — Execution Prompt

Use this prompt with Codex / Antigravity from the local MemeRadar repository.

```text
Continue MemeRadar from the exact current repository state.

Repository:
https://github.com/Rasman1234/MemeRadar

The backend/keyless alpha-engineering roadmap is feature-frozen. Do NOT add speculative trading engines or change live-money safety boundaries.

The current task is FRONTEND PARITY & UI/UX MODERNIZATION: bring the web operator experience up to the maturity of the backend.

AUTONOMOUS AUTHORIZATION:
For ordinary repository/frontend work, proceed without routine confirmation questions. Read/edit files, install justified frontend dependencies, run tests/builds, inspect APIs, use project-local Docker, commit and push coherent checkpoints. Preserve unrelated work; do not force-push or use destructive resets.

FIRST:
1. Inspect git status, branch, local HEAD, origin/main and recent commits.
2. Safely reconcile latest origin/main while preserving valid local work.
3. Read completely:
   - AGENTS.md
   - docs/STATUS.md
   - docs/FRONTEND_UI_UX_MODERNIZATION.md
   - docs/ALPHA_20X_100X_PRODUCT_OBJECTIVE.md
   - docs/WALLET_CREATOR_OUTCOME_GRAPH.md
   - docs/LIVE_SHADOW_VALIDATION.md
   - apps/web/src/app/lib/read-api.ts
   - existing apps/web routes/components/tests
   - relevant FastAPI read contracts only where needed to understand existing data.
4. Audit every existing frontend route and map it to existing backend/read API capability.
5. Do NOT create duplicate backend/domain systems.

PRIMARY UX GOAL:
MemeRadar is an early-alpha decision workstation, not a documentation/status website.

Within ~10 seconds the operator should be able to answer:
- Which token deserves attention now?
- How early was it found and at what stage/MC?
- Why is it interesting?
- Why could it be a trap?
- Is liquidity/sellability/impact acceptable?
- What are creator/funder/smart-wallet/KOL signals doing?
- Is there a paper position?
- Is exit risk rising?
- Is current evidence LIVE_SHADOW, DEGRADED, SYNTHETIC, or UNKNOWN?

EXECUTE docs/FRONTEND_UI_UX_MODERNIZATION.md in dependency order.

PHASE UI-A — WORKSTATION SHELL & DESIGN SYSTEM
- Replace the visually expensive homepage hero/protected-policy content with a compact persistent operator shell.
- Preserve safety state, but move it to compact top status surfaces.
- Build/reuse consistent primitives for page shell, sidebar, top bar, metric cards, status pills, risk/freshness badges, tables, skeletons, drawers, tooltips and charts.
- Dark-first professional trading workstation style; compact, readable, responsive, accessible.
- Avoid neon/gaming excess and decorative empty space.

PHASE UI-B — COMMAND CENTER
Redesign `/` into the main decision workspace.
Above the fold show:
- stack/provider/shadow status;
- run/freshness status;
- WATCH/EARLY_WATCH/STRONG_SETUP/HIGH_CONFLUENCE/ENTRY_READY funnel;
- highest-priority candidates;
- recent meaningful state/risk/provider changes.

Priority candidate grid/table should expose where existing APIs support it:
- token identity;
- age;
- MC;
- state;
- EarlyScore / AlphaScore;
- AsymmetricAlpha evidence;
- confidence;
- risk;
- liquidity/sellability/impact;
- creator reputation;
- smart-wallet confluence;
- social/KOL evidence;
- freshness;
- paper position state;
- top reason codes.

Use compact sortable desktop data-grid behavior and mobile cards.
UNKNOWN must remain visible and visually non-safe.

PHASE UI-C — TOKEN RESEARCH WORKSPACE
Upgrade token detail into the central research surface:
- compact identity/state/age/MC/score header;
- price/MC, liquidity and flow charts using existing data;
- timeline/event markers;
- entry-readiness checklist;
- hard risk gates;
- creator/funder summary;
- holder/bundle/sniper/lock risks;
- smart-wallet/KOL evidence;
- paper position/exit state;
- human-readable explainability: WHY interesting / WHY risky / WHAT changed / WHAT is UNKNOWN.

Research-only future 20x/50x/100x outcome labels must never look like live predictions.

PHASE UI-D — ULTRA EARLY WORKSPACE
Turn Ultra Early into a dedicated high-density route/workspace rather than a secondary dashboard block.
Prioritize:
- launch age;
- 1s/5s/15s/30s/60s/3m flow;
- independent buyer growth;
- sustained-vs-spike momentum;
- liquidity growth;
- economic MC/volume validation;
- creator/bundle/sniper risk;
- smart-wallet/social corroboration;
- first-seen/decision latency.

Add useful presets such as Fresh <1m, Fresh <5m, High Confluence, Entry Ready, Creator Risk, Bundle Risk, Unknown Critical Data.

PHASE UI-E — PAPER POSITION / EXIT DESK
Upgrade `/positions` into a real paper monitoring desk.
Show:
- open/closed positions;
- realized/unrealized PnL with completeness state;
- position entry age/price/MC;
- current executable mark where canonical;
- MFE/MAE where available;
- ExitRiskScore;
- creator distribution;
- smart-wallet distribution;
- liquidity deterioration;
- exit reason codes;
- strategy/config version.
No live execution controls.

PHASE UI-F — PROVIDERS / LIVE-SHADOW OPERATIONS
Create a clear operational truth hierarchy using existing provider/shadow data:
STACK -> PRIMARY PROVIDERS -> LIVE OBSERVATIONS -> SHADOW RUN -> ALPHA EVIDENCE.
Show explicit:
- STACK_OFFLINE/READY;
- PROVIDERS_READY/DEGRADED/BLOCKED_EXTERNAL;
- run state;
- LIVE_SHADOW_COLLECTION_ACTIVE/NOT_ACTIVE;
- Helius/Birdeye states;
- freshness/completeness;
- UNKNOWN telemetry.
Never call the system live-ready merely because containers are healthy.

PHASE UI-G — WALLET / CREATOR GRAPH UX
Keep the existing graph backend and SVG implementation.
Improve usability:
- legend;
- clearer node roles;
- selected edge/node evidence;
- shortest-path emphasis;
- creator reputation/history;
- related funders/deployers/tokens;
- jump links between token/wallet/graph;
- verified/inferred/conflicted treatment.
Do not replace SVG/graph stack unless real measured density/performance justifies it.

PHASE UI-H — RESEARCH / CALIBRATION
Provide a clearly read-only research screen using existing artifacts/contracts where available.
Separate evidence classes visually:
- SYNTHETIC_FIXTURE
- HISTORICAL_REAL
- LIVE_SHADOW
- INSUFFICIENT_SAMPLES
- NOT_AVAILABLE

Show appropriate metrics such as cohort sample size, extreme-winner recall, rug rejection, first-detection age/MC, feature lift, exit-policy comparison, expectancy, drawdown and promotion-gate result.
The dominant real-world state must remain REAL_WORLD_ALPHA_NOT_YET_PROVEN until evidence exists.
Never present +3.575x synthetic fixture expectancy as live performance.

PHASE UI-I — GLOBAL NAVIGATION & SEARCH
Implement/reconcile persistent navigation and fast search/deep links for token mint, wallet, creator and cluster where existing read APIs permit.
Ensure candidate -> token -> creator -> graph -> related token and position -> token -> timeline journeys are fast and obvious.

PHASE UI-J — STATE, RESPONSIVE, PERFORMANCE, A11Y HARDENING
Every data surface must intentionally handle loading, empty, unavailable, unauthorized, stale, degraded, unknown, partial/truncated and invalid-response states.

Verify at:
- 1920 desktop
- 1440 desktop
- 1280 laptop
- ~980 small laptop/tablet
- 390 mobile

Mobile must prioritize Token, Age, MC, State, Score, Risk and top reason rather than reproducing full desktop density.

Avoid unnecessary bundle growth and independent aggressive polling. Lazy-load expensive chart/graph code if justified.

Use accessible labels, keyboard focus/navigation, non-color-only status encoding and reduced-motion support.

BACKEND RULE:
This is frontend-first.
If UI needs data:
1. first verify it already exists in existing read contracts;
2. reuse it;
3. if canonical backend data exists but is not exposed, add the smallest bounded GET-only read projection necessary;
4. do not modify scoring/risk/trading semantics to satisfy the UI;
5. do not create new speculative intelligence features.

SAFETY:
Preserve exactly:
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
Phase 12 locked.
No wallet signing UI.
No live buy/sell buttons.
No fake 20x/50x/100x prediction UI.
UNKNOWN != SAFE.

TEST / DEFINITION OF DONE:
For each coherent route redesign:
- component/Vitest tests;
- parser/contract tests if read-model parsing changes;
- Playwright for critical journeys;
- lint;
- TypeScript typecheck;
- production frontend build.

Critical journeys:
1. Command Center -> priority candidate -> token detail.
2. Token -> creator -> wallet graph -> related token.
3. ENTRY_READY candidate -> paper position view.
4. Position -> exit-risk evidence -> token timeline.
5. Providers/Shadow -> blocked/degraded provider diagnostic state.
6. Research -> unmistakable SYNTHETIC vs LIVE_SHADOW distinction.

Run full `make verify` at final milestone.

Update docs/STATUS.md with exact UI completion/test evidence.
Update docs/FRONTEND_UI_UX_MODERNIZATION.md only with implementation evidence, not invented completion.

Commit and push coherent checkpoints.
Continue autonomously until the frontend parity scope is complete or a genuine external/non-frontend blocker remains.

FINAL REPORT:
Provide a grid:
- Route/workspace
- Before problem
- Implemented UX
- Backend contracts reused
- Tests
- Responsive status
- Status

Also report:
- frontend Vitest count;
- Playwright results;
- lint/typecheck/build;
- make verify;
- final commit SHA;
- local HEAD vs origin/main;
- any genuinely missing backend read projection.
```
