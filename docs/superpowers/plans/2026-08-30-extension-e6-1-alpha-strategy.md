# E6.1 Versioned AlphaStrategy Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Add a provider-independent, deterministic strategy seam that consumes immutable feature/risk evidence and emits a replayable AlphaScore v1 suggestion without weakening hard risk gates or creating execution authority.

**Architecture:** Add one application-layer `alpha_strategy.py` module.  The
strategy input is an immutable `FeatureSnapshot` plus `RiskAssessment` and an
explicit mode-safe `StrategyPolicy`.  The output is an immutable
`StrategySnapshot` carrying strategy identity, weighted components, raw score,
penalties, confidence adjustment, reason codes, evidence/provenance and config
hash.  `AlphaScoreV1Strategy` implements only deterministic arithmetic and
metadata handling; risk disposition and hard blocks remain outside/above the
strategy.  A small reference strategy is test-only framework evidence.  The
existing `ScoreSnapshot`/persistence contracts receive explicit strategy name
and version fields so replay/audit identity is not hidden in `model_version`.

**Tech Stack:** Python 3.12, frozen dataclasses, `Decimal`, existing domain
`FeatureSnapshot`/`RiskAssessment`/`ScoreSnapshot` contracts, pytest golden
fixtures and Compose smoke checks.  No provider SDK, transport, database
session, signer, execution port or live credential is introduced.

**Spec:** `docs/ROADMAP_RESEARCH_EXTENSIONS.md` Extension E6.1,
`docs/SCORING_AND_RISK.md` sections 1–4 and 9/12, and the Phase 6 pipeline in
`docs/ARCHITECTURE.md`.

## Global constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Implement the documented AlphaScore v1 weights exactly: SmartMoney 25%,
  OnChainSafety 20%, LiquidityQuality 15%, OrganicFlow 15%, SocialVelocity
  10%, HolderQuality 10% and Momentum 5%.
- Components are normalized to `0..100`; the weighted raw score and each
  penalty are bounded and the suggested score clamps to `0..100`.
- Missing, stale, unknown, conflicted or invalid feature evidence never turns
  into a positive safe fact.  Missing values use an explicit neutral component
  only where the strategy policy permits it and reduce confidence with a
  reason code.
- Hard risk blocks are copied as evidence/metadata and cannot be cleared or
  converted into execution eligibility by strategy output.  `UNKNOWN` risk is
  never treated as `PASS`.
- Same input, policy and config produce deterministic logical output
  independent of mapping/delivery order.  Strategy identity/version and config
  hash are explicit and auditable.
- Strategy snapshots and score/decision records remain advisory; no strategy
  result may return or imply `ENTRY_READY`, sign, submit or authorize a trade.
- Do not expose secrets or add live provider acceptance claims.  Use synthetic
  fixtures and keyless tests; keep physical schema migration reversible.

## Task 1: Define strategy policy, input and immutable output contracts

**Files:**
- Create: `packages/application/src/memeradar_application/alpha_strategy.py`
- Create: `tests/unit/test_alpha_strategy.py`

**Interfaces:**
- `ALPHA_SCORE_V1_VERSION = "alpha-score-v1"`.
- `ALPHA_SCORE_V1_WEIGHTS` with the seven documented component weights.
- `StrategyPolicy` containing weights, penalty bounds, missing-component
  confidence adjustment, evidence TTL, protected modes and versioned config
  identity.
- `StrategyInput(feature_snapshot, risk_assessment, policy/config)` with strict
  `FeatureSnapshot`/`RiskAssessment` validation.
- `StrategySnapshot(strategy_name, strategy_version, candidate_id, as_of,
  expires_at, raw_score, suggested_score, components, weighted_components,
  penalties, confidence, confidence_adjustment, risk_disposition,
  hard_blocks, reason_codes, evidence_refs, provenance, feature_snapshot_id,
  risk_assessment_id, config_hash, quality_state, execution_eligible=False)`.
- `AlphaStrategy` as a provider-free `Protocol` with `evaluate(...)`.

- [x] Write failing unit tests for policy weight normalization/bounds, frozen
  mappings, output identity/version/config fields and permanent no-execution.
- [x] Run the focused unit test file and confirm the expected missing-module
  collection failure.
- [x] Implement the contracts using existing UTC/freshness/Decimal/reason-code
  helpers and recursive immutable mappings.
- [x] Re-run unit tests before adding score arithmetic.

## Task 2: Implement deterministic AlphaScore v1 arithmetic and risk boundary

**Files:**
- Modify: `packages/application/src/memeradar_application/alpha_strategy.py`
- Modify: `tests/unit/test_alpha_strategy.py`

**Interfaces:**
- `AlphaScoreV1Strategy(policy=None).evaluate(feature_snapshot, risk_assessment,
  *, now, config_hash) -> StrategySnapshot`.
- `ReferenceStrategy` implements the same protocol only for framework tests.

- [x] Add failing golden tests for exact weighted components, raw weighted
  average, penalty subtraction/clamping and confidence calculation.
- [x] Add failing tests for feature-key aliases, missing component evidence,
  non-finite/out-of-range values, stale/invalid feature snapshots and future
  evaluation timestamps.
- [x] Add failing tests proving BLOCK, UNKNOWN, stale critical evidence and
  hard-block penalties remain visible and cannot become PASS or execution
  eligible; strategy output must remain advisory.
- [x] Implement deterministic component extraction from `FeatureSnapshot.values`
  without importing providers or runtime settings.  Keep all seven component
  keys present in stable order, preserve explicitly supplied penalties and add
  only policy-bounded strategy penalties.
- [x] Implement confidence as feature confidence × risk confidence × quality
  factor, then apply bounded missing/staleness adjustments with explicit
  reason codes; do not make score magnitude stand in for confidence.
- [x] Ensure policy/config and strategy identity are retained on every output,
  and validate candidate/risk/feature identity alignment.
- [x] Run focused unit tests and static checks.

## Task 3: Add score persistence identity and golden replay contracts

**Files:**
- Modify: `packages/domain/src/memeradar_domain/snapshots.py`
- Modify: `packages/persistence/src/memeradar_persistence/models.py`
- Modify: `infra/alembic/versions/0003_score_strategy_identity.py`
- Modify: `tests/unit/test_domain_models.py`
- Create: `tests/contract/test_extension_e6_1_alpha_strategy.py`
- Create: `fixtures/providers/alpha_strategy/README.md`
- Create: `fixtures/providers/alpha_strategy/replay.json`

- [x] Extend `ScoreSnapshot` and `ScoreSnapshotRow` with explicit
  `strategy_name` and `strategy_version` while retaining backward-compatible
  `model_version` semantics; update the initial logical model documentation.
- [x] Add a reversible migration with bounded non-null defaults that preserves
  existing rows and passes migration parity.
- [x] Build keyless golden scenarios for strong correlated evidence, sparse
  evidence, penalty clamp, blocked risk and unknown risk.
- [x] Assert original/reversed feature mapping equality, exact weighted score,
  stable reason/evidence ordering, strategy-switch visibility and no-lookahead
  rejection.
- [x] Assert the reference strategy is callable through the protocol but is not
  registered as production ranking.

## Task 4: Reconcile docs, Compose smoke and phase gate

**Files:**
- Modify: `tests/smoke/test_compose_contract.py`
- Modify: `docs/ROADMAP_RESEARCH_EXTENSIONS.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/SCORING_AND_RISK.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/STATUS.md`

- [x] Add Compose/import smoke coverage for strategy identity, protected modes,
  fixture presence and no-provider imports.
- [x] Document strategy inputs/outputs, hard-gate ordering, missing evidence,
  score weights, version/config persistence and no-execution boundary.
- [x] Run focused unit/contract/smoke checks, `make lint`, `make typecheck`,
  `make secret-scan`, migration parity, Compose config and full `make verify`.
- [x] Rebuild API/worker images and run import/mode/health probes without
  claiming live provider success.
- [x] Update `docs/STATUS.md` with exact evidence, protected modes, external
  blockers and the next uncompleted task; commit and push coherent checkpoints.
