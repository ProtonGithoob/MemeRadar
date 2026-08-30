# E6.0 Correlation and Launch Micro-Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-independent, replayable correlation window that joins social, protocol, market, wallet and risk evidence into bounded launch micro-features without creating execution authority.

**Architecture:** Add one focused application module, `correlation.py`, that accepts existing normalized domain/application records and emits immutable per-window feature data plus explainable provenance, freshness, source-diversity and risk metadata. It uses event time and deterministic tie-breakers for all windows, deduplicates equivalent source deliveries and actor clusters, and exposes `execution_eligible()` as permanently false. No provider SDK, transport, persistence migration, signer or score/decision transition is added in E6.0.

**Tech Stack:** Python 3.12, frozen dataclasses, `Decimal`, existing `Observation`/`SocialMention`/`WalletActivity`/`TokenSmartMoneyScore`/`RiskAssessment` contracts, pytest fixtures and Compose smoke checks.

**Spec:** `docs/ROADMAP_RESEARCH_EXTENSIONS.md` Extension E6.0 and `docs/ARCHITECTURE.md` correlated alpha/micro-feature path.

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Support exactly the default event-time windows `5s`, `15s`, `30s`, `60s`, `1m`, `5m`, `15m` in ascending order.
- Use inclusive event-time membership `(now - duration, now]` with the documented boundary and deterministic `(event_time, observed_at, ingested_at, source_id)` ordering.
- Future event, observed or ingested timestamps are excluded and produce `INVALID`/zero-confidence evidence; they never improve a feature.
- Sparse windows and fewer than the configured independent source/sample thresholds produce low confidence or `UNKNOWN`, never strong momentum.
- Distinct wallet addresses connected by the supplied confluence cluster ID count once; one social, wallet, protocol or market burst cannot authorize `ENTRY_READY`.
- Preserve source IDs, timestamps, parser/provenance, quality states, evidence references, configuration hash and version on the output.
- Do not add physical persistence or copy code from unclear-license upstream repositories.

---

### Task 1: Define policy and immutable correlation output contracts

**Files:**
- Create: `packages/application/src/memeradar_application/correlation.py`
- Test: `tests/unit/test_correlation.py`

**Interfaces:**
- `CorrelationWindowPolicy(window_durations=..., evidence_ttl=timedelta(minutes=15), minimum_sample_size=3, minimum_independent_sources=2, source_diversity_target=3, max_observations=10000, max_mentions=10000, max_wallet_activities=10000, max_smart_money_scores=1000, rapid_round_trip_window=timedelta(minutes=2), version="correlation-window-v1")`.
- `CorrelationWindowFeatures` stores the window bounds, event/source counts, buyer/seller and quote-flow metrics, net-flow/liquidity deltas and acceleration, wash/round-trip ratios, protocol lifecycle counts/curve progress, actor-cluster smart-money metrics, creator/related-wallet sell pressure, confidence, quality and reason codes.
- `CorrelationSnapshot(token, as_of, expires_at, windows, risk_disposition, risk_quality_state, source_independence_count, source_diversity_confidence, provenance, evidence_refs, reason_codes, confidence, config_hash, quality_state, version="correlation-window-v1")` is immutable and has `execution_eligible(at) -> bool` returning `False`.

- [ ] **Step 1: Write failing unit tests** for the required seven default window names/order, bounded policy validation, immutable output fields, `execution_eligible()` always false and confidence/quality validation.
- [ ] **Step 2: Run `./.venv/bin/pytest tests/unit/test_correlation.py -q`** and confirm collection fails because the module/contracts do not exist.
- [ ] **Step 3: Implement the policy, `CorrelationWindowFeatures` and `CorrelationSnapshot` validation** using existing freshness, reason-code, timestamp, provenance and decimal helpers; freeze nested mappings and deduplicate reason codes.
- [ ] **Step 4: Run the unit tests** and require the contract tests to pass before adding aggregation logic.

### Task 2: Implement deterministic event-time correlation aggregation

**Files:**
- Modify: `packages/application/src/memeradar_application/correlation.py`
- Test: `tests/unit/test_correlation.py`

**Interfaces:**
- `CorrelationWindowBuilder(policy: CorrelationWindowPolicy | None = None)`.
- `build(token, *, observations=(), mentions=(), wallet_activities=(), smart_money_scores=(), risk_assessment=None, creator_wallets=(), related_wallets=(), now, config_hash) -> CorrelationSnapshot`.
- Inputs are existing `Observation`, `SocialMention`, `WalletActivity`, `TokenSmartMoneyScore` and optional `RiskAssessment` values; wallet address sets are canonical Solana addresses.

- [ ] **Step 1: Add failing unit tests** for token matching, inclusive event-time windows, reversed delivery order, future exclusion, stale/unknown quality, duplicate source handling, malformed payload fail-closed behavior and configuration/message bounds.
- [ ] **Step 2: Add failing feature tests** for unique buyers/sellers, buyer arrival rate, buy/sell quote volume and ratio, net flow, net-flow acceleration, transaction/maker ratio, liquidity delta/acceleration, repeated-size/circular/rapid-round-trip diagnostics and nullable missing quote/row evidence.
- [ ] **Step 3: Add failing cross-source tests** for protocol lifecycle counts/curve progress, social mention counts, wallet activity, risk disposition/quality, distinct source categories/provider provenance, smart-money entry clusters after cluster dedupe, weighted entry quality, tracked supply percentage and creator/related-wallet sell pressure.
- [ ] **Step 4: Implement bounded normalization** into an internal event record with category, source/provider, event time, observed/ingested times and safe payload. Deduplicate equivalent source IDs, reject conflicting reuse, exclude future evidence and sort by event time rather than delivery order.
- [ ] **Step 5: Implement per-window flow calculations** using only the current window and the immediately preceding equal-duration band for acceleration. Keep quote-dependent outputs nullable when quote fields are absent; derive repeated sizes, reciprocal buyer/seller flow and maker buy-then-sell ratios only from valid row-level evidence.
- [ ] **Step 6: Implement protocol/social/wallet/risk joins** and actor-cluster dedupe. Count source categories rather than raw records, cap source-diversity confidence, keep external lifecycle evidence advisory, and never return an execution-eligible result.
- [ ] **Step 7: Run all correlation unit tests** and require deterministic equality for original versus reversed input order.

### Task 3: Add golden E6.0 replay fixtures and contracts

**Files:**
- Create: `fixtures/providers/correlation/README.md`
- Create: `fixtures/providers/correlation/replay.json`
- Create: `tests/contract/test_extension_e6_0_correlation.py`
- Modify: `tests/smoke/test_compose_contract.py`

**Interfaces:**
- Fixture scenarios are `organic_acceleration`, `bot_wash_burst`, `smart_wallet_only_burst`, `social_only_burst` and `creator_dump`.
- Contract helpers construct normalized existing records from the fixture and compare logical snapshots from original/reversed delivery order.

- [ ] **Step 1: Add failing fixture/replay contracts** with keyless synthetic social, protocol, market, wallet, smart-money and risk evidence, duplicate records, an out-of-order delivery and future evidence.
- [ ] **Step 2: Assert golden behavior**: organic acceleration has multiple independent sources and bounded positive flow acceleration; bot/wash has repeated-size/circular/rapid diagnostics; smart-wallet-only and social-only scenarios remain source/sample-limited; creator dump exposes creator/related sell pressure; future evidence never appears in any window.
- [ ] **Step 3: Assert no-lookahead and advisory boundaries**: reversed delivery produces equal snapshots, missing critical evidence is not safe, a single burst cannot become `ENTRY_READY`, and `execution_eligible()` is false.
- [ ] **Step 4: Add Compose smoke assertions** for the module, fixture, required seven windows, and all four protected service modes.
- [ ] **Step 5: Run unit, contract and smoke tests** together.

### Task 4: Reconcile Phase 6 documentation and run the gate

**Files:**
- Modify: `docs/ROADMAP_RESEARCH_EXTENSIONS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/STATUS.md`

- [ ] **Step 1: Document** the seven event-time windows, correlation inputs, feature names, source-diversity confidence, actor-cluster dedupe, missing-evidence semantics and no-execution boundary; retain physical persistence and final AlphaScore/decision wiring for later tasks.
- [ ] **Step 2: Mark E6.0 complete only after** `make lint`, `make typecheck`, focused/unit/contract/smoke tests, `make secret-scan`, migration parity and Compose config pass.
- [ ] **Step 3: Run `make verify`** at the permitted runtime boundary if the restricted sandbox reproduces the documented AnyIO/TestClient socket limitation.
- [ ] **Step 4: Rebuild API/worker images** and run the E6.0 import/mode/health probes without printing secrets or claiming live provider success.
- [ ] **Step 5: Update `docs/STATUS.md`** with exact counts, coverage, protected modes, external blockers and the next task E6.1; commit and push coherent implementation and documentation checkpoints.
