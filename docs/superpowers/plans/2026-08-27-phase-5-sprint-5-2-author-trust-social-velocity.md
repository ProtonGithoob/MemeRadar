# Phase 5 / Sprint 5.2 — Author Trust and Social Velocity

**Goal:** turn normalized `SocialMention` evidence into bounded, explainable
author-trust and token social-velocity snapshots without making social
activity an autonomous trading signal or adding provider dependencies to the
application layer.

**Roadmap source:** `docs/ROADMAP.md`, Sprint 5.2.

**Safety boundary:** this sprint is analysis-only. Every derived record keeps
provenance, evidence references, timestamps, freshness and config/version
metadata. Scores are advisory and expose an explicit non-authorizing execution
predicate. Missing, future, stale, conflicted or invalid evidence cannot
produce a fresh positive signal. Trusted/KOL labels are explicit configuration
and are never promoted automatically from mention activity.

## Design

- Add `packages/application/src/memeradar_application/social_intelligence.py`
  with provider-independent immutable contracts:
  - `AuthorTrustTier`, `AuthorRegistryEntry` and `SocialAuthorRegistry` for
    bounded canonical author IDs plus explicit `TRUSTED`, `KOL` and `BLOCKED`
    lists;
  - `AuthorTrustScore` with registry, engagement, originality and coordination
    components, penalties, confidence, quality, provenance and reasons;
  - `SocialVelocityPolicy` with the 1m/5m/15m windows, bounded count
    thresholds, quality/penalty ceilings and version;
  - `SocialVelocityScore` with per-window mention/unique-author counts,
    engagement quality, duplicate/spam ratios, coordination diagnostics,
    components, penalties, confidence, freshness and evidence.
- Use `SocialMention.posted_at` as the event time and reject future mentions;
  `observed_at`/`ingested_at` remain the observation timestamps. Group mentions
  by `token_id` when present and by canonical `referenced_mint` otherwise;
  unassociated mentions are retained for author trust but do not fabricate a
  token velocity bucket.
- Derive engagement quality only from bounded non-negative metrics. Missing
  impressions or engagement metrics remain nullable and reduce confidence;
  they are not treated as zero engagement.
- Detect coordination from copied-text clusters, same-fingerprint author
  breadth and short-window bursts. The heuristic is diagnostic, bounded and
  conservative; it never claims bot identity or common control from timing
  alone. Duplicate/copied-text and spam ratios are explicit penalties.

## Tasks

### 1. Contracts and registry (test first)

- Add validation tests for author IDs, tiers, duplicate registry entries,
  explicit trusted/KOL/blocked precedence, bounds and no automatic promotion.
- Implement immutable registry entries and a bounded registry with explicit
  list configuration and deterministic conflict handling.
- Add unit tests for score field bounds, freshness transitions, immutable
  mappings and `execution_eligible() is False`.

### 2. Author trust and velocity calculation (test first)

- Add unit tests for 1m/5m/15m counts, unique-author counts, cutoff/future
  handling, token grouping, missing metrics and deterministic replay.
- Implement author trust scoring from explicit registry tier, bounded
  engagement quality, originality and coordination diagnostics, with a
  confidence separate from score magnitude.
- Implement token social velocity scoring with configurable normalization,
  duplicate/spam/coordinated-promotion penalties and fail-closed quality
  handling.
- Keep all provider imports outside `social_intelligence.py` and preserve
  source IDs/provenance in each derived score.

### 3. Fixtures and contracts

- Add redacted synthetic author/mention replay fixtures covering trusted/KOL,
  unknown and blocked authors, copied text, metric-complete/incomplete posts,
  multiple windows and an excluded future post.
- Add deterministic replay contracts, credential scans, provider-independence
  assertions and Compose safe-mode checks.

### 4. Documentation and gate

- Reconcile `docs/DATA_MODEL.md`, `docs/SCORING_AND_RISK.md`,
  `docs/PROVIDERS.md`, `docs/SECURITY.md`, `docs/ROADMAP.md` and
  `docs/STATUS.md`.
- Run focused unit/contract/smoke tests, Ruff, mypy, full `make verify`,
  `make doctor`, social provider doctor (still expected to be
  `BLOCKED_EXTERNAL` without configuration), migration parity and Compose
  runtime import/safety probes.
- Commit and push implementation, fixture/contract and documentation/status
  checkpoints. Record the exact next task for Sprint 5.3.

## Acceptance criteria

- Author registry and trusted/KOL configuration are explicit, bounded,
  idempotent and provider-independent.
- 1m/5m/15m mention and unique-author counts replay deterministically with no
  future-data leakage.
- Engagement quality, duplicate ratio, spam ratio and coordination diagnostics
  are bounded, explainable and nullable when critical metrics are absent.
- `AuthorTrustScore` and `SocialVelocityScore` preserve evidence/freshness,
  separate confidence from score and can never authorize execution.
- Keyless fixtures and contracts pass; unavailable live social access is
  reported only as `BLOCKED_EXTERNAL`, never as fabricated provider success.
