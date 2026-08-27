# Phase 5 / Sprint 5.3 — Narrative LLM

**Goal:** add an optional, provider-neutral narrative analysis seam that
turns bounded normalized evidence into strict advisory output without allowing
an LLM, untrusted social text or a provider outage to affect deterministic
risk decisions or execution.

**Roadmap source:** `docs/ROADMAP.md`, Sprint 5.3.

**Safety boundary:** this sprint remains keyless and analysis-only. No LLM
credential is required, no prompt may contain secrets, no adapter has tools or
execution capability, and `NarrativeSnapshot` is evidence only. All four
protected modes remain unchanged. Missing, timed-out, malformed, stale or
injection-tainted narrative evidence degrades to an explicit unavailable
result and never blocks deterministic analysis.

## Design

- Evolve the existing provider-independent `NarrativeInput`/
  `NarrativeSnapshot` contracts with bounded evidence bundles, strict enums,
  schema/version/config metadata, usage accounting, cache identity and
  reason/evidence fields while preserving the asynchronous `NarrativePort`.
- Add an application `NarrativeAnalyzer`/gateway that canonicalizes and
  delimits untrusted content, strips instruction-like control text from the
  model view, computes a deterministic cache key, enforces input/output
  limits, timeout/budget policy and fail-closed fallback behavior. It must
  never import a provider SDK or expose tools.
- Add a keyless deterministic/fake narrative adapter in the provider package
  for fixture replay and a safe doctor command. A configured live provider is
  optional; missing URL/key is reported as `BLOCKED_EXTERNAL` without a live
  request or fabricated success.
- Preserve the distinction between narrative unavailability and deterministic
  evidence. Cache entries are keyed by normalized evidence/config/schema and
  can only be reused while fresh; provider/model usage is bounded and
  redacted.
- Add redacted fixtures and contracts for valid structured output, malformed
  output, timeout/outage, cache hit/expiry, oversized/injection-shaped social
  content, freshness and safety-mode behavior.

## Tasks

### 1. Contract hardening (test first)

- Add validation tests for strict narrative enums, bounded narrative/topic/
  evidence text, score/uncertainty/confidence ranges, usage limits, schema and
  provider metadata, cache keys and advisory/non-authorizing behavior.
- Implement immutable normalized input/output contracts while preserving
  provenance, timestamps, freshness and evidence references.

### 2. Application gateway (test first)

- Add deterministic input canonicalization and prompt-injection boundaries;
  untrusted post text is data only and cannot provide instructions/tools.
- Implement bounded token/character budgets, timeout handling, cache lookup
  and fresh-entry reuse, deterministic fallback snapshots and reason codes.
- Ensure provider errors, malformed structured output and unavailable LLMs
  never raise into the deterministic analysis path.

### 3. Provider seam and doctor

- Add a provider-local fixture/fallback adapter implementing `NarrativePort`
  with no network or credentials.
- Add `narrative-doctor` configuration/status tooling that reports presence
  only, redacts credentials, preserves safe modes and returns
  `BLOCKED_EXTERNAL` when live configuration is absent.

### 4. Fixtures, contracts and documentation

- Add redacted deterministic fixtures for valid narrative, malformed output,
  provider outage/timeout, cache behavior and prompt-injection-shaped content.
- Add unit/contract/smoke tests for provider independence, replay identity,
  strict output, graceful degradation, cache/budget/timeout behavior and all
  four safe modes.
- Reconcile `DATA_MODEL.md`, `PROVIDERS.md`, `SCORING_AND_RISK.md`,
  `SECURITY.md`, `TESTING.md`, `ROADMAP.md` and `STATUS.md`.

### 5. Gate

- Run focused tests, Ruff, mypy, full `make verify`, `make doctor`,
  `narrative-doctor`, migration/secret checks and rebuilt Compose runtime
  imports.
- Record Gate P5 evidence: deterministic social features still work with the
  narrative provider unavailable; narrative output is visibly advisory and
  cannot bypass risk gates.
- Commit and push coherent implementation, fixture/contract and documentation
  checkpoints. Record the exact next task for Phase 6 / Sprint 6.1.

## Acceptance criteria

- `NarrativePort` accepts bounded normalized evidence and returns only strict,
  validated structured advisory output.
- Prompt injection in social/token content cannot mutate configuration, invoke
  tools, reveal secrets or authorize execution.
- Budgets, caching, timeouts and malformed/outage fallback are deterministic
  and observable; narrative unavailability never blocks deterministic scores.
- Keyless fixtures/contracts and provider doctor checks pass; absent live
  access is reported only as `BLOCKED_EXTERNAL`.
- No live-money execution permission or protected mode default changes.
