# Opportunity Discovery & Narrative Alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend MemeRadar so it can discover the hottest opportunity set, causal narratives, canonical contracts and protocol-usage acceleration early enough to improve executable extreme-winner recall across Solana, BNB and Robinhood Chain.

**Architecture:** Add an Opportunity Discovery Layer before the existing scoring pipeline. Reuse chain/provider/event/wallet/graph/replay/alert primitives; add focused measurement-only projections that feed existing EarlyScore/Alpha only after replay/ablation and promotion gates prove incremental lift. Generic EVM primitives serve both BNB and Robinhood Chain.

**Tech Stack:** Python application/domain packages, FastAPI read APIs, existing provider adapters/transports, PostgreSQL/SQLAlchemy where persistence is needed, Next.js read-only UI, Telegram outbox/alerts, pytest/mypy/ruff/Vitest/Playwright, Docker Compose.

**Spec:** `docs/OPPORTUNITY_DISCOVERY_EXTENSION.md`

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- No live signing, swap submission, copy trading, KOL auto-follow or private-key handling.
- New evidence is measurement-only until no-lookahead replay and existing strategy promotion gates prove incremental value.
- Missing evidence remains UNKNOWN; never convert missing evidence to zero, safe or high confidence.
- Reuse existing event, chain, wallet, graph, scoring, replay, alert and UI systems; do not create duplicates.
- Add `.env.example` variables only atomically with validated runtime Settings and tests.
- Preserve Solana compatibility and chain-qualified idempotency.
- `REAL_WORLD_ALPHA_NOT_YET_PROVEN` remains unchanged until real out-of-sample live-shadow evidence is sufficient.

---

### Task 1: Audit and lock the integration seams

**Files:**
- Modify: `docs/STATUS.md`
- Inspect: `packages/domain/src/memeradar_domain/*`
- Inspect: `packages/application/src/memeradar_application/*`
- Inspect: provider/composition modules under `packages/`
- Inspect: `apps/api/src/memeradar_api/read.py`
- Inspect: `apps/web/src/app/*`

**Interfaces:**
- Consumes: existing chain identity, observation/event, provider capability, EarlyScore, smart-wallet, graph, replay and alert contracts.
- Produces: a short implementation-seam inventory in `docs/STATUS.md` naming exact files/classes to extend before code starts.

- [ ] Read `docs/OPPORTUNITY_DISCOVERY_EXTENSION.md`, `docs/SMART_MONEY_CONVERGENCE_EXTENSION.md`, `docs/MULTICHAIN_EXTREME_WINNER_IMPLEMENTATION_SPEC.md` and current `docs/STATUS.md`.
- [ ] Run `git status --short`, `git branch --show-current`, `git log -8 --oneline`, `git fetch origin`.
- [ ] Search for existing chain identity, EVM validation, provider capability routing, social/narrative evidence, correlation windows, wallet convergence, replay labels and Telegram rendering.
- [ ] Record exact reusable seams and any conflicting active work in `docs/STATUS.md`; do not create duplicate modules where an existing implementation can be extended.
- [ ] Commit the audit checkpoint.

### Task 2: Generalize chain identity for Robinhood without Solana regression

**Files:**
- Modify: exact domain identity/config files discovered in Task 1.
- Test: existing identity tests plus new Robinhood chain tests.

**Interfaces:**
- Produces: canonical `ROBINHOOD` chain identity, chain-qualified token/wallet canonical IDs, shared EVM address normalization.
- Consumes: existing Solana and BNB chain abstractions.

- [ ] Write failing tests asserting Robinhood mainnet identity is distinct from BNB/Solana and EVM addresses do not collide across chains.
- [ ] Add `ROBINHOOD` to canonical chain enumeration/registry using existing naming conventions.
- [ ] Reuse generic EVM validation; do not fork Robinhood-only address logic.
- [ ] Preserve Solana `mint_address` compatibility aliases where currently public.
- [ ] Run focused identity tests, Ruff and mypy for touched modules.
- [ ] Commit.

### Task 3: Add Robinhood read-only RPC provider route

**Files:**
- Modify: generic EVM JSON-RPC adapter/composition discovered in Task 1.
- Modify: validated Settings and `.env.example` atomically.
- Test: provider contract/unit tests.

**Interfaces:**
- Produces: read-only Robinhood `CHAIN_RPC` capability with chain-id verification.
- Network constants: chain id `4663`; default public RPC `https://rpc.mainnet.chain.robinhood.com`.

- [ ] Write failing tests for `eth_chainId == 4663`, timeout, malformed JSON, 429, 5xx, wrong-chain response and provider-unconfigured states.
- [ ] Route Robinhood through the generic EVM adapter rather than copying BNB code.
- [ ] Add validated settings for `ROBINHOOD_RPC_URL`, optional fallback and `ROBINHOOD_CHAIN_ID=4663`.
- [ ] Ensure no transaction submission methods are exposed.
- [ ] Add provider health/readiness classification with explicit PASS/DEGRADED/BLOCKED_EXTERNAL/RATE_LIMITED/AUTH_FAILED or existing canonical equivalents.
- [ ] Run focused provider tests and config tests.
- [ ] Commit.

### Task 4: Add Robinhood market/discovery enrichment

**Files:**
- Modify: existing DexScreener adapter and chain routing.
- Create/modify: optional Blockscout read-only adapter only if existing provider abstractions justify it.
- Test: pair selection and normalization tests.

**Interfaces:**
- Produces: Robinhood token/pair/market discovery evidence with provenance.

- [ ] Write failing tests for exact chain/address pair selection, deterministic liquidity/quote ranking and UNKNOWN when coverage is absent.
- [ ] Generalize existing DexScreener chain filtering to include Robinhood without changing Solana/BNB behavior.
- [ ] If Blockscout is added, restrict it to read-only token/address/transaction enrichment and preserve provider provenance.
- [ ] Do not make Robinhood core boot depend on DexScreener or Blockscout availability.
- [ ] Run adapter contract tests and Solana/BNB regressions.
- [ ] Commit.

### Task 5: Implement provider-neutral Global Event contracts

**Files:**
- Create/modify: focused domain/application event module following existing event patterns.
- Test: event normalization, timestamps, dedupe and provenance.

**Interfaces:**
- Produces: normalized event carrying source id, event id, `occurred_at`, `observed_at`, `ingested_at`, entities, URLs/contract addresses, quality/freshness and evidence refs.

- [x] Write failing tests for timestamp ordering, idempotency, duplicate events, missing author/entity fields, stale/conflicted evidence and future-time rejection.
- [x] Implement provider-neutral event contracts; keep provider SDK/raw payload types outside domain logic.
- [x] Add bounded normalization for text/entities/contract addresses without unrestricted raw-payload propagation.
- [x] Ensure provider failure only degrades that evidence family.
- [x] Run unit/type tests.
- [x] Commit.

### Task 6: Implement Chain Opportunity projections

**Files:**
- Create: focused `chain_opportunity.py`-style application module using actual repository naming patterns.
- Test: `tests/unit/test_chain_opportunity.py` and contract/replay tests.

**Interfaces:**
- Produces: `ChainOpportunitySnapshot` with raw opportunity components, confidence/freshness/version; no production magic score required.

- [ ] Write failing tests for token/pool/wallet/volume/liquidity/launch acceleration, missing-data UNKNOWN semantics and deterministic time windows.
- [ ] Reuse canonical correlation/time-window helpers where possible.
- [ ] Compute components per chain with no future data.
- [ ] Add source diversity and confidence coverage.
- [ ] Add read-only API projection; do not alter production scoring weights.
- [ ] Run focused tests.
- [ ] Commit.

### Task 7: Implement Narrative Catalyst and Pre-Token Attention

**Files:**
- Create: focused narrative/catalyst application module(s), split if one file becomes unwieldy.
- Test: narrative timing and no-lookahead tests.

**Interfaces:**
- Produces: `NarrativeCatalystSnapshot` plus pre-token attention timing metrics.

- [ ] Write failing tests covering organic attention before token creation, token-first promotional attention, mixed evidence, UNKNOWN, duplicate source events and future-leak rejection.
- [ ] Implement catalyst-first-seen, token-created-at, narrative lead time, attention slope and pre/post-token attention components.
- [ ] Preserve source quality/diversity and exact evidence refs.
- [ ] Keep LLM classification optional/advisory and retain deterministic raw evidence.
- [ ] Add reason codes `ORGANIC_ATTENTION_PRECEDES_TOKEN` and `EXTERNAL_CATALYST_HIGH_CONFIDENCE` only when requirements are satisfied.
- [ ] Run focused tests.
- [ ] Commit.

### Task 8: Implement Narrative-to-Token Matcher

**Files:**
- Create/modify: narrative matching application module.
- Test: canonical contract and ambiguous-match cases.

**Interfaces:**
- Produces: `NarrativeTokenMatch` per chain-qualified token/narrative pair.

- [ ] Write failing tests for exact-CA references, semantic metadata match, deployment timing, official/reference links, ambiguous matches and spoofed ticker/name copycats.
- [ ] Never use symbol/name equality alone as identity.
- [ ] Combine deterministic CA/reference/timing evidence with optional semantic classification.
- [ ] Return explicit UNKNOWN/ambiguous state where original contract cannot be established.
- [ ] Run focused tests.
- [ ] Commit.

### Task 9: Implement Narrative Competition / Copycat Resolver

**Files:**
- Create/modify: narrative competition module and graph integration.
- Test: multi-contract narrative cohorts.

**Interfaces:**
- Produces: `NarrativeCompetitionSnapshot` with candidate count, earliest deployment/liquidity, liquidity share, holder-growth share, smart-wallet share and canonical confidence.

- [ ] Write failing fixtures with one likely canonical token, several copycats, an ambiguous case and a later contract that legitimately becomes dominant.
- [ ] Implement clustering by narrative plus chain-qualified contract identity.
- [ ] Rank evidence without automatically labeling later contracts as scams.
- [ ] Add `NARRATIVE_COPYCAT_COMPETITION_HIGH` and `NARRATIVE_DOMINANCE_HIGH` reason codes when justified.
- [ ] Run tests.
- [ ] Commit.

### Task 10: Implement Attention Quality-Weighted Velocity

**Files:**
- Create/modify: social/narrative feature module reusing current social evidence.
- Test: author independence, duplicate-text and velocity cases.

**Interfaces:**
- Produces: raw weighted-attention components, not an unvalidated universal production formula.

- [ ] Write tests distinguishing one-account amplification, duplicate bot-like promotion, independent author acceleration and broad cross-source propagation.
- [ ] Compute unique authors, independent author clusters, engagement acceleration, duplicate-text ratio, source diversity and exact-CA mention velocity.
- [ ] Keep unavailable bot/audience-overlap evidence UNKNOWN.
- [ ] Expose components for replay/ablation.
- [ ] Commit.

### Task 11: Implement Cross-Community Propagation Graph

**Files:**
- Modify: existing graph primitives where reusable; create a focused projection layer rather than another graph engine.
- Test: temporal propagation paths.

**Interfaces:**
- Produces: source-category transition graph and propagation delays.

- [ ] Write tests for external->general->researcher->smart-money->KOL->retail progression, concentrated amplification and missing communities.
- [ ] Reuse graph node/edge abstractions where practical.
- [ ] Preserve first-seen timestamp per community and source-category diversity.
- [ ] Do not infer identity from usernames alone.
- [ ] Commit.

### Task 12: Implement Protocol / Fundamental Velocity

**Files:**
- Create: focused protocol-velocity module.
- Test: protocol, launchpad and pure-meme cases.

**Interfaces:**
- Produces: `ProtocolVelocitySnapshot` with TVL/borrow/users/volume/fees/market-share acceleration where available.

- [ ] Write tests for accelerating fundamentals, flat fundamentals, missing fundamentals and pure memes where missing protocol evidence must not be penalized.
- [ ] Compute first derivatives/relative acceleration from event-time-bounded observations.
- [ ] Add usage-growth vs market-cap-growth comparison as research evidence.
- [ ] Preserve provider provenance and freshness.
- [ ] Commit.

### Task 13: Implement Winner Archetype classification

**Files:**
- Create/modify: candidate classification module.
- Test: multi-label and UNKNOWN cases.

**Interfaces:**
- Produces: versioned multi-label archetypes such as `REAL_WORLD_MEME`, `PROTOCOL_TOKEN`, `LAUNCHPAD_TOKEN`, `CHAIN_BETA`, `RWA_ADJACENT`, `BREAKING_NEWS_MEME`.

- [ ] Write deterministic fixtures for the core archetypes plus ambiguous/UNKNOWN cases.
- [ ] Require evidence refs and confidence independent of class label.
- [ ] Keep optional LLM output advisory and bounded.
- [ ] Do not dynamically alter production score weights in this task.
- [ ] Commit.

### Task 14: Extend KOL/Researcher historical specialization

**Files:**
- Modify: existing social/KOL modules identified in Task 1.
- Modify: smart-money convergence research projection as needed.
- Test: researcher-vs-promoter cohort behavior.

**Interfaces:**
- Produces: chain/archetype/narrative-specialized historical quality profile.

- [ ] Write tests for early calls, post-breakout calls, insufficient samples, severe-failure rate and explicit wallet-linkage boundaries.
- [ ] Add matured sample counts, median call MC/age, research-only outcome labels, MFE/MAE and specialization dimensions.
- [ ] Never infer wallet ownership from username similarity.
- [ ] Keep KOL output measurement-only until promotion.
- [ ] Commit.

### Task 15: Integrate opportunity evidence with existing smart-money convergence

**Files:**
- Modify: implementation generated from `SMART_MONEY_CONVERGENCE_EXTENSION.md` or its current equivalents.
- Test: joint-vs-single-signal ablation fixtures.

**Interfaces:**
- Consumes: narrative/catalyst, chain opportunity, smart-wallet convergence, liquidity/holder/risk evidence.
- Produces: one transparent research projection, not a duplicate production score.

- [ ] Write tests where narrative alone is strong, wallet convergence alone is strong, both agree, they conflict, or evidence is stale.
- [ ] Preserve raw and cluster-adjusted wallet counts.
- [ ] Expose joint reason codes and confidence without bypassing hard risk gates.
- [ ] Keep ENTRY_READY requirements unchanged.
- [ ] Commit.

### Task 16: Separate upside evidence from risk in read models

**Files:**
- Modify: read projections/API types/frontend DTOs.
- Test: API schema and UI rendering tests.

**Interfaces:**
- Produces separate fields for upside evidence, market-integrity risk, contract/deployer risk, liquidity/exit risk, execution quality and confidence.

- [ ] Write failing API schema tests asserting these concepts are not collapsed into one opaque scalar.
- [ ] Extend existing read-only response models.
- [ ] Ensure critical BLOCK/UNKNOWN risk still prevents ENTRY_READY.
- [ ] Render UNKNOWN/stale/degraded explicitly.
- [ ] Commit.

### Task 17: Extend Telegram/read-only opportunity alerts

**Files:**
- Modify: existing alert renderer/outbox/Telegram projection.
- Test: Telegram formatting, dedupe, rate limit and latency.

**Interfaces:**
- Produces: explainable opportunity alerts with catalyst, narrative match, copycat competition, chain heat, wallet convergence and risks.

- [ ] Add tests for Robinhood, BNB and Solana alert payloads.
- [ ] Show evidence counts/timing/confidence instead of only a scalar score.
- [ ] Preserve state-transition dedupe and bounded alert volume.
- [ ] Preserve existing end-to-end alert latency fields and measure added processing latency.
- [ ] Commit.

### Task 18: Build historical case-study and negative-control replay fixtures

**Files:**
- Create: bounded fixtures/research manifests under existing replay fixture conventions.
- Create/modify: research CLI/report only if current replay infrastructure requires it.
- Test: no-lookahead fixture integrity.

**Interfaces:**
- Produces: winner and non-winner cohorts with event-time-bounded evidence.

- [ ] Add the user-supplied token cases only where reliable historical timestamps/data can be sourced; mark unavailable data UNKNOWN.
- [ ] Add mandatory negative controls: high-virality non-winner, copycat failure, rug/severe failure, strong-fundamental/no-repricing and weak-fundamental/repricing examples.
- [ ] Store future 2x/5x/10x/20x/50x/100x labels strictly as future outcome targets.
- [ ] Add fixture validation proving live features cannot read future labels.
- [ ] Commit.

### Task 19: Run separability/ablation and archetype/regime research

**Files:**
- Modify/create: existing separability/research scripts and artifacts.
- Test: deterministic report generation.

**Interfaces:**
- Produces comparative evidence for baseline vs opportunity/narrative feature families.

- [ ] Compare current baseline against each feature family independently.
- [ ] Measure incremental winner recall, copycat false-selection, rug/severe-loss rate, executable entry coverage, first-detection age/MC and paper expectancy.
- [ ] Segment by chain, archetype, age bucket and market-cap bucket.
- [ ] Return `INSUFFICIENT_SAMPLES` instead of overfitting sparse cohorts.
- [ ] Do not promote any production weight automatically.
- [ ] Commit research artifacts/results.

### Task 20: Strategy promotion gate and full acceptance

**Files:**
- Modify: existing strategy promotion records/config only if evidence warrants a candidate change.
- Modify: `docs/STATUS.md`, provider docs, API docs and research report.

**Interfaces:**
- Produces: verified implementation matrix and exact remaining blockers.

- [ ] Run all focused tests, `make lint`, `make typecheck`, frontend gates and full `make verify`.
- [ ] Run keyless/provider doctors; classify real external failures honestly.
- [ ] Confirm protected modes exactly.
- [ ] Confirm no signing/swap/private-key path was added.
- [ ] If out-of-sample evidence is insufficient, keep new evidence measurement-only and record that explicitly.
- [ ] Update `docs/STATUS.md` with final commit/evidence and the exact next task.
- [ ] Commit, push and verify local HEAD equals `origin/main` after merge/reconciliation.
