# Extension E5.4 — Historical Caller/KOL Outcome Evidence

**Goal:** improve `AuthorTrustScore` with measurable historical token-call
outcomes instead of static labels or follower counts, without giving any
caller history execution authority or automatic registry promotion.

**Roadmap source:** `docs/ROADMAP_RESEARCH_EXTENSIONS.md`, Extension E5.4
(inserted after Sprint 5.3 / Gate P5, before Phase 6 feature scoring).

**Safety boundary:** keyless, warm-path, provider-independent application
contract. No provider SDK, network, persistence model or execution path enters
the new module. All results are advisory (`execution_eligible()` is always
false), never mutate the explicit `SocialAuthorRegistry`, and default policy
preserves the existing `author-trust-v1` scoring behavior unless a caller
explicitly supplies performance evidence and a non-zero performance weight.

**Implementation status (2026-08-30):** complete for the keyless acceptance;
live social/provider access is intentionally a separate external gate.

**Upstream/license decision:** the PumpKit-style "caller performance tracking"
pattern from `docs/RESEARCH_REUSE_REGISTRY.md` has unclear licensing; this
sprint independently implements the documented behavior only. No upstream
source is copied.

## Design

- New module `packages/application/src/memeradar_application/call_performance.py`
  following the `social_intelligence.py` conventions: frozen dataclasses,
  bounded Decimal metrics, `Provenance`/`QualityState`/`Freshness`, reason
  codes, config hash and version on every result.
- `SocialCall`: normalized author token-call evidence with `author_id`,
  optional `token_id` UUID and/or validated `referenced_mint`, `called_at`/
  `observed_at` event timestamps, source post IDs, `Provenance` and quality
  state. Duplicate source post IDs are idempotent; conflicting duplicates fail
  closed. Calls referencing no token identity are rejected.
- `SocialCallOutcome`: per-call forward outcome reconstructed only from market
  price observations with `occurred_at` strictly after `called_at` and not
  after `now` (no lookahead). Fixed configured horizons (default
  `5m/15m/1h/6h/24h`) each carry nullable forward return, MFE and MAE; a
  horizon with no post-call observation inside it stays null with an explicit
  reason, never zero. Post-call rug/liquidity-collapse evidence flags are
  nullable and require fresh valid risk evidence; missing evidence is
  `UNKNOWN`, never a clean outcome. Data-quality state distinguishes
  complete/partial/unknown horizons.
- `CallPerformanceSnapshot`: per-author aggregation with `sample_count`,
  hit rate at the reference horizon, median forward return, median MFE, median
  MAE, rug-avoidance rate, median token age at call (when token creation
  evidence exists), shrinkage toward neutral using `sample / (sample + prior)`
  like `SmartWalletScorer`, uncertainty, confidence, quality state, provenance,
  evidence references, reason codes, config hash and version.
- `CallPerformanceAnalyzer`: deterministic pure analysis over bounded call and
  market/risk observation sequences. Identical event logs reproduce identical
  snapshots (stable ordering, quantized Decimals). Bounded inputs reject
  over-limit batches.
- `AuthorTrustScorer` integration: optional
  `performance: Mapping[str, CallPerformanceSnapshot] | None = None` argument.
  When supplied, a `performance` component (shrunk, `0..100`) blends into the
  score with configurable `performance_weight` that defaults to `0`, and the
  remaining weights are renormalized only when the weight is non-zero. Missing
  or insufficient-sample history adds `CALL_HISTORY_INSUFFICIENT` reason and
  reduces confidence slightly instead of moving the score up or down.
  Blocked authors still score zero; no author tier changes.

## Tasks

### 1. Contracts (test first)

- Unit tests for `SocialCall`/`SocialCallOutcome`/`CallPerformanceSnapshot`
  validation: identity rules, timestamp ordering, horizon bounds, Decimal
  ranges, provenance, advisory-only execution predicate.
- Duplicate/conflicting call handling and bounded input tests.

### 2. Outcome reconstruction (test first)

- Forward-return/MFE/MAE derivation per horizon from post-call observations
  only; incomplete horizons stay nullable; future observations are excluded
  and mark data invalid; out-of-order delivery produces identical results.
- Rug/liquidity-collapse flags only from fresh valid post-call risk evidence;
  missing risk evidence is `UNKNOWN` with a reason code.

### 3. Author aggregation and trust integration (test first)

- `CallPerformanceSnapshot` aggregation with shrinkage, minimum-sample and
  confidence gates, and deterministic reason codes.
- `AuthorTrustScorer` optional performance consumption: default policy output
  unchanged; enabled policy blends shrunk performance, insufficient samples
  lower confidence without sign change, no automatic promotion.

### 4. Fixtures, contracts, docs and gate

- Synthetic credential-free fixtures under
  `fixtures/providers/call_performance/` for good, poor, rug-heavy,
  duplicated and insufficient-sample callers plus a manifest.
- Contract test `tests/contract/test_extension_e5_4_call_performance.py`
  replaying fixtures deterministically; smoke Compose contract updated for the
  new module import and protected modes.
- Reconcile `DATA_MODEL.md`, `SCORING_AND_RISK.md`, `PROVIDERS.md` (if the
  evidence surface changes), `ROADMAP_RESEARCH_EXTENSIONS.md` checkboxes and
  `docs/STATUS.md`.
- Run focused tests, Ruff, mypy, full `make verify`, `make doctor`, migration
  and secret checks, and rebuilt Compose runtime imports.
- Commit and push coherent checkpoints; record the exact next task (E2.5).

## Acceptance criteria

- Identical social/market event logs reproduce identical author-performance
  snapshots (deterministic replay).
- Missing outcome history lowers confidence instead of becoming a negative or
  positive fact.
- No future observation can influence a call outcome; out-of-order input is
  order-independent.
- No call-performance result can promote an author tier, clear a risk gate or
  authorize execution; all four protected modes are unchanged.
