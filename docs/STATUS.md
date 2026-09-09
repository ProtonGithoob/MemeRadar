# MemeRadar Status

Last updated: 2026-09-09

This is the current authoritative project state. Historical checkpoint detail
was consolidated here; implementation contracts remain in the canonical
documents below.

## Current classification

| Dimension | Current state | Evidence / constraint |
|---|---|---|
| System stage | `FREE_FIRST_PROVIDER_ARCHITECTURE_IMPLEMENTED` | Local engineering gates pass; external acceptance is separate. |
| Stack readiness | `STACK_READY` when the local Compose stack is running | API, web, Postgres and Redis contracts are verified locally. |
| Core provider readiness | `READY_FOR_FREE_READ_ONLY_SHADOW` | Core reads do not require Helius or Birdeye; optional enrichment is separate. |
| Shadow collection | `NOT_ACTIVE` | No live shadow evidence is claimed from fixtures or an unavailable stack. |
| Real-world alpha | `REAL_WORLD_ALPHA_NOT_YET_PROVEN` | Historical-real and matured live-shadow samples remain insufficient. |
| Production readiness | `NOT_PRODUCTION_READY` | See [Production Readiness](PRODUCTION_READINESS.md). |
| Live-money eligibility | `OUT_OF_SCOPE` / not eligible | No live-money workflow is enabled or authorized. |

Protected modes are unchanged and enforced:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

There is no wallet signer, live order submission, automatic execution, or
execution authority in the web client. Missing, stale, conflicted, invalid,
unverified, and unresolved-gap evidence remains fail-closed and distinct from
zero or safe evidence.

## Current blockers

- Compliant historical-real X/Telegram data, CabalSpy-style wallet/KOL stream
  data, Chainlink feed identities, and matured live-shadow observations are
  unavailable; real-provider validation is `BLOCKED_EXTERNAL` and calibration
  is `INSUFFICIENT_SAMPLES`.
- Hosted CI triggered for the pushed commit but its jobs failed before any
  steps executed (runner/API state unavailable); managed backup/restore and
  production-like dependency restart/soak remain externally unverified. The
  browser gateway remains fail-closed when server credentials are absent; with
  injected test-only server credentials, authenticated acceptance is covered
  without exposing tokens to browser JavaScript.
- Optional Helius, Birdeye, social, Telegram, stream, narrative, and external
  wallet enrichment may report unavailable or degraded; the free core remains
  provider-independent.

No blocker changes the readiness classification or authorizes a mode change.

## Latest engineering evidence

The latest local full gate recorded after the evidence hardening and parity
completion:

- `make verify`: 1146 Python tests passed, 11 skipped, 1 warning; 21 frontend
  test files and 61 Vitest tests passed.
- Ruff, strict mypy across 126 source files, frontend lint/typecheck,
  production build, Compose validation, tracked-file secret scan, migrations,
  security review, SBOM, and `git diff --check`: passed.
- Migration head: `0009_runtime_settings`; metadata tables: 26.
- SBOM: 581 components, digest
  `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`.
- Backend/API/frontend parity is closed for the current routes: canonical
  runtime-settings mutation with restart-required and secret-safe semantics,
  protected-mode enforcement, authenticated server gateways, universal
  multichain search, multichain shell state, readiness projection, provider
  configuration/runtime-health views, caller/opportunity evidence, and a
  generated route parity manifest are covered by focused tests.
- Browser acceptance across 1440x900, 1024x768, 768x1024, and 390x844: the
  unconfigured run was `32 passed, 4 skipped`; the authenticated run was
  `29 passed, 7 skipped`, including the desktop ADMIN settings mutation.
  Skips are credential/stateful-duplicate cases, not passes for blocked
  journeys; the explicit missing-credentials failure-state test passed.
- Release identity and synthetic soak evidence remain local/measurement-only;
  external acceptance remains `BLOCKED_EXTERNAL`.

The current checkpoint hardens the reused canonical seams: KOL evidence now
requires independent strong dimensions for above-weak confidence and exposes
measurement-only precision/recall/FPR/calibration by dimension; external
wallet streams fail closed on unresolved gaps and preserve provider event-time
quality; historical social backfill is resumable, deduplicated and cohort
counted; Robinhood sequencer observations remain non-authoritative until RPC
verification/finality; the verified launchpad registry and Robinhood
Chainlink-feed registry remain empty until authoritative identities are
verified; and reference prices remain risk evidence, never executable fills.
Existing caller/wallet/graph, social outcome/replay, provider-health,
opportunity and read-model surfaces were extended without a second intelligence
engine. KOL evidence remains `execution_eligible=false` and production weights
are unchanged.

Real external samples: 0. Calibration: `INSUFFICIENT_SAMPLES`, promotion
false. CabalSpy-compatible stream, X/Telegram compliant backfill, Robinhood
sequencer runtime, launchpad identity verification and Chainlink feed runtime
are `BLOCKED_EXTERNAL`; deterministic transport, gap, no-lookahead, negative
control, dedupe, resume and failure tests pass. No unverified launchpad or
external provider score is authoritative.

## Current operational references

- [Master specification](MASTER_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Research extensions](ROADMAP_RESEARCH_EXTENSIONS.md)
- [Data model](DATA_MODEL.md)
- [Scoring and risk](SCORING_AND_RISK.md)
- [Provider contracts](PROVIDERS.md)
- [Security](SECURITY.md)
- [Testing](TESTING.md)
- [Production readiness](PRODUCTION_READINESS.md)
- [Live read-only checklist](LIVE_READONLY_CHECKLIST.md)
- [Live-shadow validation](LIVE_SHADOW_VALIDATION.md)
- [Release runbook](RUNBOOKS/RELEASE.md)
- [Free-first migration report](FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md)
- [Alpha caller extension](ALPHA_CALLER_INTELLIGENCE_EXTENSION.md)
- [Current opportunity-discovery plan](superpowers/plans/2026-09-05-opportunity-discovery.md)
- [Current alpha-caller design](superpowers/specs/2026-09-07-alpha-caller-multichain-design.md)
- [Current real-alpha readiness plan](superpowers/plans/2026-09-07-real-alpha-production-readiness.md)

## Historical summary

- Phases 0–7 established the provider-independent domain, persistence,
  normalized read paths, deterministic scoring/risk contracts, alerting,
  control boundaries, and authenticated read APIs.
- Phases 8–9 established the operator UI, bounded graph/radar surfaces,
  paper execution, exit/replay contracts, Telegram boundaries, and protected
  execution semantics.
- Phases 10–11 established replay/backtesting/calibration, stream-integrity
  and provenance hardening, caller and cross-venue research, operational
  telemetry, release identity, security review, and synthetic soak evidence.
- The free-first provider migration made standard Solana RPC and DexScreener
  the keyless core while retaining optional provider-specific capabilities.
- The 2026-09-05 to 2026-09-07 frontend/backend parity work completed the
  remaining read-only opportunities projection and browser acceptance.
- The 2026-09-08 evidence-hardening checkpoint reused the canonical wallet,
  social, provider-health, generic-EVM, read-model and quote semantics seams;
  external provider runtime validation remains blocked without compliant
  credentials/data.
- The 2026-09-09 parity checkpoint made Settings an audited ADMIN workspace,
  added the server-side browser control gateway, universal multichain search,
  readiness projection, provider configuration/runtime parity, and route
  parity coverage without changing scoring, production classification, or
  protected modes.
- Real-alpha production-readiness evaluation retained
  `NOT_PRODUCTION_READY`; the next meaningful acceptance step is external
  evidence collection and replay-cohort maturation, not a code or mode change.

Exact next unfinished task: obtain compliant real X/Telegram and optional
wallet/KOL provider data plus verified Robinhood feed identities, populate all
winner/ordinary/flat/severe-loser/rug/fake-hype/late/failed cohorts, then run
the existing no-lookahead ablation/promotion gates without changing protected
modes or production weights. Latest implementation commit SHA: `PENDING_COMMIT`.

Historical plans and checkpoint logs are intentionally archived from this
status file. The canonical documents and the current plans above are the
source of truth for active work.
