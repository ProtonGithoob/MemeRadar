# MemeRadar — Frontend UI/UX Modernization

## Objective

Bring the web frontend up to the maturity of the backend without changing the product safety model or creating duplicate systems.

The operator should be able to answer, within seconds:

1. What is happening now?
2. Which tokens deserve attention first?
3. Why is a candidate interesting?
4. Why is it risky?
5. How early was it found and at what market cap?
6. What are smart wallets / creator / funder / KOL signals doing?
7. Is the candidate actually executable with current liquidity/impact?
8. What paper position exists and what is the current exit risk?
9. Are providers/shadow collection healthy enough to trust current observations?

The redesign is **frontend-first**. Reuse the existing read API and contracts. Only add backend read projections if a required UI datum already exists canonically but is not exposed.

## Product design principle

MemeRadar is not a generic analytics dashboard. It is an **early-alpha decision workstation**.

The visual hierarchy should prioritize:

`NOW -> CANDIDATE PRIORITY -> EARLYNESS -> ALPHA EVIDENCE -> RISK -> EXECUTABILITY -> POSITION/EXIT -> PROVENANCE`

Avoid large decorative hero sections that consume above-the-fold space without helping a decision.

## UI style direction

Use a professional crypto trading workstation aesthetic:

- dense but readable;
- dark-first with optional light mode if already supported;
- strong typography hierarchy;
- compact cards and data tables;
- low visual noise;
- subtle motion only for state transitions / fresh data;
- semantic colors, never decorative colors as meaning;
- red = hard/critical risk, amber = degraded/warn, green = verified positive state, gray = unknown/unavailable;
- UNKNOWN must never look safe;
- avoid neon-gaming excess;
- responsive from 390px mobile through 1440px+ desktop;
- keyboard-friendly operator workflows;
- WCAG-minded contrast and focus states.

## Information architecture

Use a persistent workstation shell with:

### Left navigation

- Radar
- Ultra Early
- Token Research
- Wallet / Creator Graph
- Paper Positions
- Providers / Shadow
- Research / Calibration
- Audit
- Settings

The exact route structure may reuse existing routes; do not create duplicates simply for naming.

### Top operator bar

Always surface:

- shadow/stack status;
- provider readiness;
- active run state;
- ANALYSIS_ONLY / PAPER status;
- search by mint / wallet;
- current time/freshness indicator;
- quick link to provider/shadow diagnostics.

Do not place execution buttons in the browser.

---

# UI-01 — Design system cleanup

Audit `globals.css` and existing components.

Create/reuse consistent primitives:

- PageShell
- AppSidebar
- TopBar
- SectionHeader
- MetricCard
- StatusPill
- ScoreGauge
- RiskChip
- FreshnessIndicator
- DataTable
- EmptyState
- ErrorState
- Skeleton
- Tabs
- Drawer / inspector
- Tooltip
- Sparkline / small chart wrapper

Prefer existing CSS/Tailwind approach already used by the repo; do not add a heavy component framework unless it materially reduces code and bundle complexity.

Define consistent spacing, radius, typography, semantic state tokens and chart styles.

---

# UI-02 — Replace homepage hero with Command Center

Current homepage spends significant space on protected-mode explanation. Keep the safety state visible but compress it into the top bar / small system card.

Above the fold should become a **Command Center**.

Required first viewport:

### A. Market/Shadow Status strip

Show compact metrics where available:

- Stack status
- Provider readiness
- Shadow collection ACTIVE / NOT_ACTIVE
- Helius state
- Birdeye state
- Stream freshness
- Run duration
- Last observation age

Unknown values remain UNKNOWN.

### B. Early Alpha Funnel

Show counts:

- WATCH
- EARLY_WATCH
- STRONG_SETUP
- HIGH_CONFLUENCE
- ENTRY_READY

Use compact funnel/segmented visualization.

### C. Priority Candidates

Show the highest-priority candidates immediately.

Each row/card should include:

- symbol/name;
- mint short form + copy;
- age since first seen;
- market cap if available;
- current state;
- EarlyScore/AlphaScore;
- asymmetric alpha evidence;
- confidence;
- liquidity;
- sellability/impact;
- creator reputation;
- smart-wallet confluence;
- KOL/social signal;
- risk disposition;
- top 2-3 reason codes;
- freshness;
- paper position badge if any.

Use sortable columns and quick filters.

Default ordering should prioritize decision usefulness, not alphabetic order.

### D. Alerts / Changes rail

Display recent meaningful changes:

- state transition;
- creator sell;
- smart-wallet accumulation/distribution;
- liquidity deterioration;
- provider degradation;
- entry-ready transition;
- exit risk transition.

Use existing timeline/audit data where canonical.

---

# UI-03 — Ultra Early workspace

Upgrade the existing UltraEarlyPanel from a secondary section into a dedicated high-density operator workspace.

Required sections:

- newest launches ordered by age;
- 1s/5s/15s/30s/60s/3m flow summary;
- independent buyers / buyer acceleration;
- sustained momentum vs spike indication;
- liquidity growth;
- bundle/sniper exposure;
- creator/deployer confidence;
- smart-wallet confirmation;
- social/KOL timing where available;
- price/MC economic validation;
- first-seen latency;
- ENTRY_READY latency if reached.

Add compact sparklines only if data already exists.

Allow operator presets:

- Fresh < 1m
- Fresh < 5m
- High Confluence
- Entry Ready
- Creator Risk
- Bundle/Sniper Risk
- Unknown Critical Data

Do not imply a token will 20x/50x/100x.

---

# UI-04 — Token Detail becomes the central research workspace

Token detail must visually consolidate backend intelligence rather than spreading important evidence across disconnected pages.

Recommended desktop layout:

### Header

- Token identity
- mint copy/open explorer
- state
- age
- current MC/price where available
- EarlyScore / AlphaScore
- AsymmetricAlphaProjection
- risk disposition
- freshness

### Main 2-column workspace

Left/main:

1. price / market-cap chart;
2. liquidity chart;
3. net-flow/buyer-arrival chart;
4. evidence timeline with important transitions;
5. smart-wallet/KOL/creator event markers over time where available.

Right inspector:

- Entry readiness checklist;
- hard risk gates;
- liquidity/sellability/impact;
- creator reputation;
- funder/actor cluster summary;
- bundle/sniper summary;
- holder concentration;
- token authority/lock/unlock risk;
- smart-wallet confluence;
- social/KOL confidence;
- current paper position / exit state.

### Explainability section

Show:

- Why WATCH / STRONG_SETUP / ENTRY_READY?
- Why rejected?
- What evidence is UNKNOWN?
- What changed in the last 1m/5m/15m?

Reason codes should be human-readable with raw code available on hover/click.

### Research-only section

If viewing replay/historical research, show 2x/5x/10x/20x/50x/100x outcome labels clearly marked as **future research labels**, never live predictions.

---

# UI-05 — Candidate table / radar ergonomics

Replace large vertically expensive candidate cards with a dense data-grid on desktop and cards on mobile.

Desktop columns should be configurable and may include:

- Token
- Age
- MC
- State
- Early/Alpha Score
- Upside Evidence
- Risk
- Confidence
- Liquidity
- Buy Flow
- Smart Wallet
- Creator Rep
- Social/KOL
- Freshness
- Paper Position

Support:

- sorting;
- column visibility;
- sticky header;
- row hover inspector;
- keyboard navigation;
- query-string filters;
- pagination/continuation;
- saved local view preference if safe.

Do not hide UNKNOWN rows by default.

---

# UI-06 — Wallet / Creator graph UX refinement

Keep the existing node-link graph backend and SVG renderer.

Improve operator usability rather than replacing the graph stack unless measured performance requires it.

Add/refine:

- legend;
- clearer node shapes by role;
- edge labels on selection/hover;
- selected-path emphasis;
- mini overview/count summary;
- creator reputation panel;
- token outcome history;
- related deployers/funders;
- quick filters;
- one-click jump from token detail to graph;
- one-click jump from graph node to token/wallet detail;
- explicit VERIFIED / INFERRED / CONFLICTED state treatment.

If concentric layout becomes unreadable beyond realistic dataset size, evaluate a force-directed layout only after measuring real graph density.

---

# UI-07 — Paper Positions / Exit Desk

Make `/positions` a real paper-trading monitoring desk.

Required summary:

- open positions;
- closed positions;
- realized PnL;
- unrealized PnL;
- PnL coverage/completeness;
- current drawdown if available;
- win/loss count where measurable;
- unknown metrics explicitly marked.

For each open position show:

- token;
- entry time / age;
- entry price/MC;
- current executable mark;
- size;
- realized/unrealized PnL;
- MFE/MAE if available;
- ExitRiskScore;
- creator distribution;
- smart-wallet distribution;
- liquidity deterioration;
- current exit reason codes;
- strategy/config version.

No live execution controls.

---

# UI-08 — Providers / Shadow Operations workspace

Unify operational truth in one screen.

Show:

- STACK_READY/OFFLINE;
- PROVIDERS_READY/DEGRADED/BLOCKED_EXTERNAL;
- shadow run lifecycle;
- collection ACTIVE/NOT_ACTIVE;
- run ID/start time;
- Helius/Birdeye health;
- optional provider states;
- pagination/data completeness where relevant;
- latest shadow status report;
- provider freshness;
- errors/rate limits where available;
- links/copyable doctor commands from docs if appropriate.

Use a clear hierarchy:

`Stack -> Primary Providers -> Live Observations -> Shadow Run -> Alpha Evidence`

Do not show `READY` if only the local stack is healthy.

---

# UI-09 — Research / Calibration screen

Create or improve a read-only research surface for:

- synthetic vs historical vs live-shadow evidence class;
- cohort sample sizes;
- 2x/5x/10x/20x/50x/100x recall;
- rug/severe failure rejection;
- precision;
- first-detection age/MC;
- feature ablation/lift;
- exit-policy comparison;
- expectancy;
- drawdown;
- exit capture ratio;
- promotion gate result.

If real-world samples are insufficient, the dominant UI state must say:

`REAL-WORLD ALPHA NOT YET PROVEN`

Never make synthetic +3.575x look like a live performance metric.

---

# UI-10 — Global search and context navigation

Provide a fast operator search for:

- token mint;
- token symbol/name where supported;
- wallet address;
- creator/deployer;
- actor cluster.

Results should deep-link directly to token/wallet/graph views.

Add contextual links throughout:

- candidate -> token detail;
- creator -> wallet graph;
- wallet -> wallet detail;
- paper position -> token detail;
- provider issue -> operations/provider page.

---

# UI-11 — Loading/error/unknown/freshness states

Every network-backed surface must have intentional states:

- loading/skeleton;
- empty;
- unavailable;
- unauthorized;
- stale;
- degraded;
- unknown;
- partial/truncated;
- invalid response.

Do not replace missing data with zero.

Do not render stale/unknown evidence with positive visual treatment.

---

# UI-12 — Responsive behavior

Desktop target: operator workstation at 1440px.

Also verify:

- 1920px wide desktop;
- 1280px laptop;
- ~980px tablet/small laptop;
- 390px mobile.

On mobile:

- use bottom/compact navigation where practical;
- collapse data grids to prioritized cards;
- keep Token, State, Risk, Score, Age, MC and key reason visible;
- do not attempt to fit full desktop graph/table.

---

# UI-13 — Performance

Avoid large client bundles.

Use server components/read API patterns already in the project where appropriate.

Lazy-load expensive graph/chart code.

Avoid polling every component independently.

If adding live refresh, centralize bounded refresh behavior and respect provider/API load.

Do not add WebSocket complexity unless existing backend contracts already support it or measured UX requires it.

---

# UI-14 — Accessibility / operator ergonomics

Required:

- visible keyboard focus;
- semantic labels;
- no color-only status encoding;
- accessible tables;
- tooltips/descriptions for score/risk metrics;
- keyboard navigation for filters and candidate rows;
- reduced-motion support.

---

# UI-15 — Testing / Definition of Done

For every redesigned route:

- Vitest/component tests;
- existing contract parser tests;
- Playwright smoke/journey coverage for critical flows;
- 1440px and 390px screenshots or visual inspection evidence if project tooling supports it;
- lint;
- TypeScript typecheck;
- production build.

Critical journeys:

1. Dashboard -> priority candidate -> token detail.
2. Token -> creator -> wallet graph -> related token.
3. Dashboard -> ENTRY_READY candidate -> paper position.
4. Position -> exit-risk evidence -> token timeline.
5. Providers/Shadow -> blocked provider -> clear diagnostic state.
6. Research -> distinguish SYNTHETIC_FIXTURE vs LIVE_SHADOW.

Do not change backend semantics merely to make tests easier.

---

## Execution order

Recommended implementation order:

1. UI-01 design primitives / shell
2. UI-02 Command Center
3. UI-05 Radar data grid
4. UI-04 Token research workspace
5. UI-03 Ultra-Early workspace
6. UI-07 Paper Position / Exit Desk
7. UI-08 Providers / Shadow Operations
8. UI-06 Wallet/Creator graph refinement
9. UI-09 Research / Calibration
10. UI-10 global search/context navigation
11. UI-11/12/13/14 hardening
12. UI-15 final journey/visual verification

Do not block UI modernization on external provider credentials. Implement UNKNOWN/BLOCKED/fixture states honestly and verify keyless behavior.

## Safety invariants

The redesign must preserve:

- `ANALYSIS_ONLY=true`
- `PAPER_TRADING=true`
- `MANUAL_EXECUTION=false`
- `AUTO_EXECUTION=false`
- no wallet signing UI;
- no live order buttons;
- no fake 20x/50x/100x predictions;
- no synthetic replay result presented as live PnL;
- UNKNOWN is never SAFE.

## Final product test

The redesigned frontend is successful when a trader can open MemeRadar and, without reading documentation, answer in under ~10 seconds:

- Which candidate deserves attention now?
- How early are we?
- Why is it interesting?
- What could make it a trap?
- Can it actually be bought/sold at current liquidity?
- What are creator/smart-wallet/social actors doing?
- Is there already a paper position?
- Is exit risk rising?
- Is the current data live, degraded, synthetic, or unknown?
