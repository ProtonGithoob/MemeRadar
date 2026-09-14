# External Alpha Intelligence Integration — Implementation Plan

> Execute test-first from the **current** `origin/main`. Do not assume the baseline in this document is still HEAD when execution begins.

**Goal:** Implement approved Option A with minimal new code: optional read-only GMGN evidence if a safe read contract exists, Helius factual activity taxonomy, Numi-derived lifecycle regression invariants, and LIVE_SHADOW/readiness evidence without changing execution or production scoring weights.

**Architecture:** Reuse MemeRadar's existing provider contracts, transport/reliability, canonical observations, wallet/caller/security/distribution evidence, launch lifecycle, readiness and alert paths. Add no parallel scoring/risk/lifecycle/alert systems.

---

## Task 0 — Synchronize and build the gap matrix

1. Fetch/sync `origin/main` and record baseline HEAD.
2. Read repository instructions (`AGENTS.md` or equivalents), current status docs and active plans.
3. Read:
   - this plan;
   - `docs/superpowers/specs/2026-09-14-external-alpha-intelligence-integration.md`;
   - `docs/EXTERNAL_REPO_SWOT_2026-09-14.md`;
   - `docs/RESEARCH_REUSE_REGISTRY.md`;
   - `docs/UPSTREAM_REPOSITORY_INFLUENCES.md`.
4. Inspect current provider contracts/metadata/config/composition/worker bootstrap, Helius stream, lifecycle, readiness/live-shadow paths and relevant tests.
5. Re-verify current upstream refs, advertised contracts and license state before source-level reuse.
6. Produce a compact matrix before code:

```text
requirement | EXISTING | PARTIAL | MISSING | NOT_NEEDED | target files | reason
```

7. Remove any planned code change that is already solved by current canonical architecture.

**Checkpoint:** no code yet; architecture/reuse boundaries are explicit.

## Task 1 — GMGN contract tests first

Only proceed to a GMGN adapter if Task 0 verifies a stable, auditable server-side read contract suitable for direct backend integration.

1. Locate current provider-test conventions rather than inventing a new test directory.
2. Add failing tests for the smallest verified read surface needed for:
   - candidate discovery;
   - market enrichment;
   - wallet/KOL/Smart Money evidence;
   - holder/distribution evidence;
   - token security/risk evidence.
3. Test canonical failures:
   - disabled/missing config;
   - auth/403;
   - 429;
   - timeout;
   - 5xx/unavailable;
   - malformed schema;
   - valid empty.
4. Test semantic correctness:
   - missing numeric != zero;
   - missing boolean/label != safe;
   - event time vs observed time;
   - SOL/BSC normalization;
   - provenance/parser version;
   - API secret redaction;
   - bounded concurrency/deadline behavior.
5. Run focused tests and confirm they fail for the intended missing behavior.

**STOP condition for GMGN only:** If no stable read API/HTTP contract can be verified, do **not** fabricate tests around guessed endpoints. Record `BLOCKED_EXTERNAL`, do not implement the adapter, and continue Tasks 4–8.

## Task 2 — Implement the minimal GMGN read-only adapter

If Task 1 precondition is satisfied:

1. Prefer one provider module under the existing provider package; candidate path is `packages/providers/src/memeradar_providers/gmgn.py`, but adapt to current repo conventions.
2. Reuse existing transport/error/deadline/reliability helpers.
3. Implement only verified read capabilities. Do not mirror every GMGN endpoint.
4. Normalize provider data into existing request/result/observation contracts and canonical evidence destinations.
5. Preserve provider-native fields and labels as provenance-backed evidence.
6. Implement bounded concurrency and existing retry policy.
7. Ensure repr/log/public projection cannot expose API keys.
8. Do not add `gmgn-cli` subprocess usage, shell execution, private key, swap/order or wallet-management code.
9. Run focused tests until green.

**Commit checkpoint:** logical adapter-only commit after focused verification.

## Task 3 — Wire GMGN without changing weights

1. Extend the existing provider metadata registry; do not create a second registry.
2. Add config fields only for actually verified runtime needs and follow existing config naming/validation conventions.
3. Update `.env.example` only with non-secret placeholders and explanatory comments if repository convention uses it.
4. Wire composition/bootstrap/worker only through existing provider mechanisms.
5. Initial state:

```text
optional = true
enabled_by_default = false
required_for_health = false
LIVE_SHADOW = true
scoring_weight = 0
```

6. Add no frontend secret projection.
7. Test disabled-by-default and app-health independence.
8. Verify enabling the provider changes evidence availability only, not production score weights or execution gates.

**Commit checkpoint:** provider wiring/config commit.

## Task 4 — Add Helius factual activity taxonomy with TDD

1. Locate the existing `HeliusObservationNormalizer` tests.
2. First add failing tests for:

```text
SWAP
LIQUIDITY_ADD
LIQUIDITY_REMOVE
BRIDGE
TRANSFER
TOKEN_LAUNCH
MEV_ARBITRAGE
UNKNOWN
```

3. Include synonym/shape cases actually emitted by Helius fixtures or documented payloads already used by this repository.
4. Add ambiguity tests proving no guess is made.
5. Implement the smallest deterministic classifier inside or adjacent to the current Helius normalizer.
6. Keep the existing broad observation kind and provenance semantics compatible unless a failing test proves a contract change is required.
7. Do not encode bullish/bearish/rug/execution recommendations.
8. Run focused Helius tests.

**Commit checkpoint:** Helius taxonomy commit.

## Task 5 — Harden launch lifecycle through regression tests

1. Locate current lifecycle tests.
2. Add tests proving:
   - BONDING != DEX_ROUTE;
   - GRADUATING/upstream graduated != verified liquidity;
   - DEX_LIVE requires evidence consistent with current verified-route policy;
   - first verified liquidity != first verified swap;
   - weak GMGN lifecycle corroboration cannot override stronger canonical/reconciled evidence.
3. Run tests.
4. If tests pass against current production code, make **no** production lifecycle change.
5. If a test exposes a real gap, make the narrowest change and rerun all lifecycle tests.

**Commit checkpoint:** lifecycle regression/hardening commit.

## Task 6 — LIVE_SHADOW and real-sample readiness

1. Inspect the existing readiness/live-shadow reporting model before adding fields.
2. Reuse existing counters and projections where possible.
3. Add only missing visibility needed to distinguish real GMGN data from test/fixture data.
4. Track/derive, where meaningful in current architecture:
   - real GMGN observations;
   - unique real tokens;
   - candidate observations;
   - caller/KOL observations;
   - smart-wallet observations;
   - holder/distribution observations;
   - security/risk observations;
   - first/last real timestamps;
   - provider error/rate-limit summary;
   - real winner/rug labeled sample counts;
   - sample sufficiency.
5. Add tests showing fixtures, mocks, synthetic and replay-only samples do not increment real promotion counters.
6. Insufficient data must produce `INSUFFICIENT_SAMPLES` rather than a neutral score.
7. Verify GMGN remains weight 0.

**Commit checkpoint:** readiness/evidence-accounting commit.

## Task 7 — Promotion-analysis hooks, not production promotion

1. Reuse existing historical/event-time research and ablation infrastructure.
2. Ensure future baseline vs baseline+GMGN comparison can measure:
   - lead time;
   - precision;
   - false-positive rate;
   - rug avoidance;
   - 2x/5x/10x/20x/50x/100x capture;
   - extreme-winner capture;
   - calibration.
3. Add no production weight promotion in this task.
4. Add/extend no-look-ahead and survivorship protections only if a current gap is proven.

## Task 8 — Full verification and truth audit

Run repository-native commands after inspecting current scripts/Makefile/CI; do not guess obsolete commands. At minimum cover all applicable gates:

1. focused GMGN tests if adapter exists;
2. focused Helius tests;
3. focused lifecycle/readiness tests;
4. full Python tests;
5. Telegram/alert tests;
6. frontend tests;
7. lint;
8. Python/static typecheck;
9. frontend typecheck/build;
10. migration checks;
11. security checks;
12. SBOM/dependency checks;
13. `git diff --check`;
14. repository `make verify` or current equivalent;
15. browser journeys where environment permits.

For external/runtime tests, classify blockers explicitly. `BLOCKED_EXTERNAL`, missing DB credentials, CI billing or unavailable provider data must not be reported as PASS.

## Task 9 — Final diff audit and status

Before completion:

- confirm no private keys, tokens or secrets in diff/logs;
- confirm no execution/trading GMGN code;
- confirm no second scorer/risk/lifecycle/wallet/alert/reliability subsystem;
- confirm production weights unchanged;
- confirm protected modes unchanged;
- confirm real vs synthetic accounting;
- confirm docs/provenance match actual implementation;
- confirm final HEAD and `origin/main` relationship.

Expected truthful classification without sufficient real OOS samples:

```text
ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION
NOT_PRODUCTION_READY
```

## Execution order

```text
sync
-> gap/reuse audit
-> failing tests
-> GMGN contract decision
-> minimal GMGN implementation if verified
-> GMGN wiring
-> Helius taxonomy
-> lifecycle regression tests
-> readiness/live-shadow accounting
-> promotion-analysis hooks
-> full verification
-> diff/security audit
-> status documentation
-> commit/push
```

Do the implementation; do not stop after restating this plan.
