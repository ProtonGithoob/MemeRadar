# MemeRadar Status

Last updated: 2026-09-01

## Latest port reconciliation

On 2026-09-01, local `main` was fast-forwarded to `origin/main` at
`2216058f453b9981826dd83168ebe3d96cb55f61`, which contains the committed
non-default host-port changes in `infra/compose/docker-compose.yml` and
`scripts/start.sh`. Compose validation, shell syntax, whitespace checks and
the full `make verify` gate pass. The exact `bash scripts/start.sh` runtime
attempt is currently `BLOCKED_EXTERNAL`: an unrelated unlabeled
`onemillionseconds-postgres-test` container owns host port `55432` on IPv4 and
IPv6. Its state and volume were not changed. Stale MemeRadar Compose
containers were stopped/removed with `docker compose down` without
`--volumes`; the requested PostgreSQL/Redis volumes remain present. Releasing
that unrelated port is required before the complete stack can run on the
requested host ports. Protected modes remain unchanged.

## Ultra-Early Option A progress

Task 1 is complete for the keyless domain contract: immutable candidate timing,
stage latency, early decision-band and external-call benchmark values are
implemented with UTC/order validation, nullable unknown launch time, frozen
evidence and measurement-only execution semantics. Event dispatch now exposes
optional provider-neutral stage timing hooks. Focused evidence: 15 tests pass
in `tests/unit/test_early_domain.py` and `tests/unit/test_event_processing.py`;
ruff and mypy pass for the touched modules. Task 2 is complete for the
keyless detector: canonical direct-chain/launchpad lifecycle evidence is
preferred over Birdeye fallback listings, duplicate delivery is idempotent,
and unverified/recovered/reverted evidence degrades to UNKNOWN/CONFLICTED.
Canonical decoder output now carries its full-key verification marker for the
provider-neutral detector. Focused evidence: 45 stream/detector tests pass and
the full application mypy check is clean. Tasks 3-13 remain in progress.

## Current verdict

`PHASE_11_SPRINT_11_3_COMPLETE_CROSS_CUTTING_HARDENING_COMPLETE_KEYLESS_ANALYSIS_ONLY_GATE_P9_BLOCKED_EXTERNAL`

Phase 0 and Phase 1 / Sprints 1.1, 1.2 and 1.3 are implemented and locally verified. Phase 2 / Sprints 2.1 through 2.4 and the keyless Gate P2 composition acceptance are complete and locally verified with fixtures and contracts. Phase 3 / Sprints 3.1, 3.2 and 3.3, Phase 4 / Sprints 4.1 through 4.3, Phase 5 / Sprints 5.1, 5.2 and 5.3, Gate P5, research extensions E5.4, E2.5, E6.0, E6.1 and E6.2, and core Phase 6 / Sprints 6.1, 6.2 and 6.3 are complete for their keyless implementation and replay gates. Live provider acceptance remains externally blocked because provider endpoints/credentials are unavailable. The repository has a keyless API, worker, web shell, local Compose topology, protected operating-mode defaults, developer commands, quality gates, structured request and event-processing telemetry, application-facing provider ports, resilient transport policies, provider health/freshness/quota models, redacted fixtures and deterministic fakes. No live provider integration, LLM integration or live-money execution has been enabled.
Phase 7 / Sprint 7.1 is now also complete for its keyless implementation and replay gate: decision/risk/provider-health events project to durable, explainable alerts; Telegram delivery is bounded, deduplicated, rate-limited and retryable through the leased outbox; and provider/system degradation is explicit. Live provider acceptance remains externally blocked because provider endpoints/credentials are unavailable. No live provider integration, LLM integration or live-money execution has been enabled.
Phase 7 / Sprint 7.2 is now complete for its keyless implementation and replay gate: the bounded application read port, persisted core-record adapter, injectable non-persisted catalogs and typed GET-only FastAPI surface are implemented. Cursor pagination, event-time/no-lookahead timelines, strict query bounds, safe redaction, unknown-state preservation, missing-resource errors and unconfigured-storage fail-closed behavior are covered. No read response grants execution authority. Live provider and Telegram acceptance remains externally blocked; no live-money execution has been enabled.
Phase 7 / Sprint 7.3 is now complete for its keyless implementation and replay gate: role-scoped bearer authentication, explicit viewer/operator/admin/execution permissions, durable control state, immutable validated config versions, paired audit events and emergency restrictive controls are implemented. Configured role credentials also protect the existing read surface; no control endpoint changes protected operating modes, creates a decision, authorizes `ENTRY_READY`, signs or submits a transaction. Live provider and Telegram acceptance remains externally blocked; no live-money execution has been enabled.
Phase 8 / Sprint 8.1 is now complete for its keyless implementation and frontend gate: the responsive App Router operator shell, local-only light/dark preference, typed score/risk/freshness/status primitives, explicit paper/live/advisory boundaries and bounded realtime lifecycle seam are implemented. Missing stream configuration is visibly `DISABLED`; failed connections reconnect with bounded backoff and degrade honestly. The browser receives no credentials or raw provider payload, and the UI has no decision or execution authority. Live provider and Telegram acceptance remains externally blocked; no live-money execution has been enabled.
Phase 8 / Sprint 8.2 is now complete for its keyless implementation and frontend gate: the server-side bounded read gateway, ranked Radar filters/cards, token detail overview, event-time evidence timeline, allow-listed market/liquidity/net-flow charts, holder concentration/cluster projections and provenance-aware social/narrative panels are implemented. API ranking/order is preserved, missing/empty/unavailable/unknown/stale/invalid data remains explicit, and the browser receives no viewer credential, raw provider payload or execution authority. Live provider acceptance remains externally blocked; no live-money execution has been enabled.
Phase 8 / Sprint 8.3 and Gate P8 are now complete for their keyless implementation and browser acceptance: server-rendered wallet leaderboard/detail, provider health/quota/freshness, read-only validated settings/control projections and immutable audit/config history are implemented over the bounded read gateway. API order, freshness and non-safe states remain explicit; secret-shaped fields and raw provider responses are withheld; Playwright browser acceptance covers the operator shell/routes, invalid wallet fail-closed behavior and absence of browser mutation/execution authority. Live provider acceptance remains externally blocked.
Research extension E8.4 is now complete for its keyless implementation and gate: provider-independent cursor/gap/recovery/verification/backpressure contracts, durable SQLAlchemy state, canonical full-key protocol routing, commitment/revert correction, event-time bounded replay, stream-quality reduction and safe telemetry are implemented. Live stream/RPC acceptance remains `BLOCKED_EXTERNAL`; unknown or unverified protocol identities fail closed, and no Rust/Yellowstone extraction was introduced.
Phase 9 / Sprint 9.1 is complete for its keyless implementation and gate: the
deterministic paper-only portfolio/order/fill/cash ledger, conservative sizing,
quote freshness checks, adverse fee/slippage model, idempotent persistence,
position lifecycle, reconciliation, event-time replay and key-safe paper doctor
are implemented and verified. Live quote and live execution acceptance remains
`BLOCKED_EXTERNAL`; no wallet signing or execution authority was introduced.
Phase 9 / Sprint 9.2 is complete for its keyless implementation and gate: the
provider-independent deterministic exit evidence, versioned rule policy,
independent ExitRiskScore, fixed/protective and correlation rule evaluator,
partial take-profit context, append-oriented in-memory timeline, durable SQL
timeline adapter and event-time replay contracts are implemented and verified.
Live read-only market-data acceptance remains `BLOCKED_EXTERNAL`; no exit
recommendation mutates a position or grants execution authority.
Phase 9 / Sprint 9.3 is complete for its keyless implementation: the
provider-free position read projection, observed-mark provenance, derived
performance fields, advisory exit-risk and closed-trade explanation are
available through GET-only API routes and a server-rendered `/positions`
dashboard. Exit and paper-exit events reuse the existing alert/outbox/Telegram
path with persisted-reason handling, core-trigger filtering and external-only
corroboration suppression. Live market-data and Telegram acceptance remains
`BLOCKED_EXTERNAL`; no browser, alert or notification path grants execution
authority.
Phase 10 / Sprint 10.1 and research extension E10.1 are complete for their
keyless implementation and replay gate: the provider-free normalized replay
dataset, event-time checkpoint harness, pinned parser/registry/schema/strategy/
config manifest, future-only outcome labels, date/venue/token partitions,
cohort summaries, alternate-strategy comparison, deterministic JSON/CSV
artifacts and bounded throughput profiler are implemented. The same
correlation/feature path is reused for replay, future evidence is excluded
from feature input, and no provider, signer or execution authority is
available. Live market-data and Telegram acceptance remains
`BLOCKED_EXTERNAL`.
Phase 10 / Sprint 10.2 is now complete for its keyless implementation and
backtesting gate: the provider-free versioned backtest policy/manifest/harness
reuses the replay contract and paper fill model, enforces fresh advisory entry
evidence and future-only exits, applies deterministic fees/slippage, emits
trade/skip/metric/score-bucket/segment/calibration artifacts, and exposes a
bounded JSON/CSV CLI. The redacted fixture correctly produces an explicit
zero-trade result because no strategy snapshot is present; no execution,
signing, provider or live-money authority was added. Live market-data and
Telegram acceptance remains `BLOCKED_EXTERNAL`.
Phase 10 / Sprint 10.3 and research extension E10.2 are now complete for their
keyless calibration implementation and gate: the provider-free calibration
harness validates named feature ablations and threshold/weight shadow
candidates, selects only on train metrics across half-open UTC time splits,
and reports unchanged validation/test evidence, baseline deltas, pinned
identities, candidate hashes and deterministic JSON/CSV artifacts. The
attribution seam measures author-trust/internal-smart-money lift,
external-label incremental value and bundle/side-wallet false confluence from
explicit future-outcome samples. Insufficient fixture evidence blocks
promotion; no production config was changed or automatically frozen, and no
execution, signing, provider or live-money authority was added. Live
market-data and Telegram acceptance remains `BLOCKED_EXTERNAL`.
Phase 11 / Sprint 11.1 and research extension E11.1 are now complete for
their keyless reliability and measurement seams: bounded percentile
histograms, provider-labelled reconnect/fallback/duplicate/conflict/malformed
counters, classified transport and outbox telemetry, deterministic
disconnect/rate-limit/backpressure contracts, persistence connection-pool
restart recovery, retention/index review and an isolated backup/restore
runbook are implemented. The synthetic local benchmark reports p50/p95/p99
for all six required stages and identifies provider-network versus internal
attribution, but it does not establish production SLOs or justify Rust/
Yellowstone extraction. Live provider acceptance remains `BLOCKED_EXTERNAL`.

Phase 11 / Sprint 11.2 is now complete for its keyless observability and
operations seam: the provider-independent `OperationsProjector` consumes
normalized provider-health inputs and the bounded reliability snapshot to
produce a versioned read-only overview with explicit provider/SLO states,
degradation alerts, stream/queue/outbox signals, quota and cost-budget
visibility, and protected modes. The API and server-rendered `/operations`
dashboard remain GET-only; synthetic or insufficient provider-network timing
is `UNVERIFIED`, operational health is neutral to AlphaScore and execution,
and no production SLO is claimed without live evidence. Live provider,
Telegram and execution acceptance remains `BLOCKED_EXTERNAL`.

Phase 11 / Sprint 11.3 is now complete for its keyless security review. The
versioned `security-review-v1` diagnostic verifies exact Python/npm lock
metadata, versioned Docker bases, non-root image users, tracked-file secret
absence, RBAC/bearer/session boundaries, strict advisory narrative prompt and
output handling, and protected modes. The npm advisory finding for Playwright
below `1.55.1` was remediated by pinning `@playwright/test` and its Playwright
packages to `1.62.1`; the follow-up npm audit reports zero vulnerabilities.
Pip-audit and Trivy are unavailable locally, so external vulnerability-scan
acceptance remains `BLOCKED_EXTERNAL` and no complete production scan is
claimed. The threat model and security-review runbook are recorded, and Gate
P11 is ready for the keyless analysis-only deployment; live provider,
Telegram and live-money acceptance remains externally blocked.

## Current phase and sprint

- Completed: `Phase 2 / Gate P2 — Read-only discovery and independent enrichment acceptance` (keyless portion)
- Completed: `Phase 3 / Sprint 3.1 — Authority / Token Security` (keyless portion)
- Completed: `Phase 3 / Sprint 3.2 — Holder Concentration / Wallet Graph` (keyless portion)
- Completed: `Phase 3 / Sprint 3.3 — Liquidity / Sellability / Wash Trading` (keyless portion)
- Completed: `Phase 4 / Sprint 4.1 — Wallet Tracking` (keyless portion)
- Completed: `Phase 4 / Sprint 4.2 — SmartWalletScore` (keyless portion)
- Completed: `Phase 4 / Sprint 4.3 — Confluence` (keyless portion)
- Completed: `Phase 5 / Sprint 5.1 — Social Provider Seam` (keyless portion)
- Completed: `Phase 5 / Sprint 5.2 — Author Trust and Social Velocity` (keyless portion)
- Completed: `Phase 5 / Sprint 5.3 — Narrative LLM` (keyless portion)
- Completed: `Gate P5` (keyless acceptance: social features work without an LLM; narrative output is advisory and cannot bypass risk gates)
- Completed: `Research extension E5.4 — Historical Caller/KOL Outcome Evidence` (keyless portion)
- Completed: `Research extension E2.5 / E6.3 — Rich Pump.fun Protocol Lifecycle Events` (keyless portion)
- Completed: `Research extension E6.0 — Correlation and Launch Micro-Features` (keyless portion)
- Completed: `Research extension E6.1 — Versioned AlphaStrategy Interface` (keyless portion)
- Completed: `Research extension E6.2 — External Wallet Intelligence / Cross Validation` (keyless portion)
- Completed: `Phase 6 / Sprint 6.1 — Feature Windows` (keyless portion)
- Completed: `Phase 6 / Sprint 6.2 — AlphaScore v1` (keyless portion)
- Completed: `Phase 6 / Sprint 6.3 — Decision State Machine` (keyless portion)
- Completed: `Phase 7 / Sprint 7.1 — Alert Pipeline` (keyless portion)
- Completed: `Phase 7 / Sprint 7.2 — Read API` (keyless portion)
- Completed: `Phase 7 / Sprint 7.3 — Auth / Control API` (keyless portion)
- Completed: `Phase 8 / Sprint 8.1 — Dashboard Design System / Shell` (keyless portion)
- Completed: `Phase 8 / Sprint 8.2 — Radar and Token Detail` (keyless portion)
- Completed: `Phase 8 / Sprint 8.3 — Wallets, Providers, Settings and Audit` (keyless portion)
- Completed: `Gate P8` (keyless browser acceptance: operator intelligence is visible/explainable and browser execution/mutation authority is absent)
- Completed: `Research extension E8.4 — Stream Integrity / Protocol Verification` (keyless implementation and replay/persistence gate)
- Completed: `Phase 9 / Sprint 9.1 — Paper Execution` (keyless portion and sprint gate)
- Completed: `Phase 9 / Sprint 9.2 — Exit Engine` (keyless implementation and sprint gate)
- Completed: `Phase 9 / Sprint 9.3 — Position UI / Telegram` (keyless portion)
- Completed: `Phase 10 / Sprint 10.1 — Replay Harness` (keyless implementation and gate)
- Completed: `Research extension E10.1 — High-Fidelity Event Replay Dataset` (keyless implementation and replay gate)
- Completed: `Phase 10 / Sprint 10.2 — Backtesting` (keyless implementation and gate)
- Completed: `Phase 10 / Sprint 10.3 — Score Calibration` (keyless implementation and gate)
- Completed: `Research extension E10.2 — Author and Wallet Calibration` (keyless measurement and safety seam)
- Completed: `Phase 11 / Sprint 11.1 — Reliability` (keyless implementation and gate)
- Completed: `Research extension E11.1 — Latency SLO and Stream Benchmarking` (keyless measurement seam; no production SLO declared)
- Completed: `Phase 11 / Sprint 11.2 — Observability / Operations` (keyless implementation and gate)
- Completed: `Phase 11 / Sprint 11.3 — Security Review` (keyless implementation and gate P11)
- Completed: `Gate P11 — READY_FOR_PRODUCTION_ANALYSIS_ONLY` (keyless evidence; external acceptance remains blocked)
- Completed: `Research extension E11.4–E11.9 — MadeOnSol-derived signal hardening` (keyless implementation, focused integration and full repository gate)
- Completed: `Cross-cutting hardening / Task 1 — API version and OpenAPI contract` (keyless contract)
- Completed: `Cross-cutting hardening / Task 2 — deterministic SBOM and dependency evidence` (keyless contract)
- Completed: `Cross-cutting hardening / Task 3 — data handling and architecture records` (keyless policy/ADR contract; legal/provider acceptance remains external)
- Completed: `Cross-cutting hardening / Task 4 — deterministic invariants` (keyless fixed-seed property-style contract)
- Completed: `Cross-cutting hardening / Task 5 — provider health comparison/routing seam` (keyless normalized evidence contract; live acceptance remains external)
- Completed: `Cross-cutting hardening / Task 6 — final quality gate and checkpoint` (keyless gate)
- Next checkpoint: `Phase 12 — Manual Live Execution (locked by default)` only
  after an explicit operator decision and the separate P9–P11 acceptance
  evidence. No Phase 12 work is started here; preserve Gate P9 live
  read-only market-data and Telegram acceptance `BLOCKED_EXTERNAL`, all
  protected modes, and the conditional E11.2 Rust/Yellowstone rule.

## Current operating policy

- `ANALYSIS_ONLY=true` — required/default
- `PAPER_TRADING=true` — required/default
- `MANUAL_EXECUTION=false` — disabled
- `AUTO_EXECUTION=false` — disabled

The configuration loader rejects attempts to override these protected values.

## Active implementation checkpoint

- Task: maintain the completed E11.4–E11.9 provider-independent hardening
  checkpoint; Phase 12 manual-live work remains locked pending explicit
  operator decision plus P9-P11 acceptance evidence.
- Sprint 11.3 design and plan are recorded in
  `docs/superpowers/specs/2026-09-01-phase-11-sprint-11-3-security-review-design.md`
  and `docs/superpowers/plans/2026-09-01-phase-11-sprint-11-3-security-review.md`.
- Cross-cutting hardening design and plan are recorded in
  `docs/superpowers/specs/2026-09-01-cross-cutting-hardening-design.md` and
  `docs/superpowers/plans/2026-09-01-cross-cutting-hardening.md`.
- Current state: `security-review-v1` passes all deterministic local checks;
  exact dependency metadata, non-root image construction, secret scan, RBAC/
  bearer/session contracts, narrative prompt/data handling and protected
  modes are verified. The npm audit is clean after the Playwright remediation.
  Pip-audit and Trivy remain external blockers, and the review does not claim
  vulnerability-free production images or deployed configuration.
- External blockers: live quote/market, stream/RPC, Telegram and all live
  execution acceptance are `BLOCKED_EXTERNAL`; pip-audit/Trivy and local
  advisory-database access are also `BLOCKED_EXTERNAL`. Gate P11 is ready for
  the keyless analysis-only deployment, but Phase 12 remains locked until an
  explicit operator decision and P9-P11 acceptance evidence.
- Protected modes: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
  `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.

## Completed work

- [x] Python package layout for domain, application, API and worker source roots.
- [x] FastAPI composition root with `/health/live` and dependency-aware `/health/ready`.
- [x] Cancellable worker entrypoint, including `python -m memeradar_worker` support and SIGTERM handling.
- [x] Next.js 16.3.3 / React 19 / TypeScript operator shell with visible analysis-only, paper-trading and disabled-execution labels.
- [x] Pinned Python dependency lock and npm lockfile; Next.js was upgraded to 16.3.3 and ESLint to 9.39.5 after audit advisories.
- [x] Safe `.env.example`, `.gitignore`, root `.dockerignore` and editor configuration.
- [x] API, worker and web Dockerfiles plus Postgres 16 / Redis 7 Compose services with health checks.
- [x] Make targets: `bootstrap`, `lint`, `typecheck`, `test`, `verify`, `up`, `down`, `migrate`, `doctor`, `provider-doctor`, `birdeye-doctor`, `rugcheck-doctor`, `social-doctor`, `external-wallet-doctor`, `telegram-doctor`, `stream-integrity-doctor`, `paper-trading-doctor`, `backtest-replay`, `calibrate-score`.
- [x] Redacted local doctor and high-confidence tracked-file secret scan.
- [x] GitHub Actions workflow for backend, frontend, Compose and secret-scan checks.
- [x] Branch-aware pytest coverage configuration and frontend Vitest/Testing Library baseline.
- [x] Correlation-aware JSON request logging with bounded incoming-ID validation and redaction.
- [x] API image regression fix ensuring the telemetry package is present at runtime.
- [x] Roadmap checkboxes reconciled for Sprints 0.1 and 0.2.
- [x] Canonical Solana token/pool identities with validated base58 public-key addresses.
- [x] Candidate lifecycle aggregate with explicit allow-listed transitions, reason codes and idempotent replay behavior.
- [x] Event envelope, observation provenance and freshness quality states preserving occurred/observed/ingested timestamps.
- [x] Versioned feature, risk, score, alert and position models with confidence, penalties, evidence references and config hashes.
- [x] Core Phase 6 / Sprint 6.1 feature-window aggregation for exact `1m`, `5m` and `15m` snapshots, including market, liquidity, holder, wallet, social, momentum and on-chain safety families with bounded AlphaStrategy components.
- [x] Provider-independent `FeatureSnapshotRepository` and unit-of-work seam with JSON-safe value/provenance round trips, deterministic identity idempotency and conflicting-reuse rejection; no migration was required because the Phase 1 table already contains the contract.
- [x] Core Phase 6 / Sprint 6.2 `AlphaScoreRecomputer` with repository-backed feature/risk loading, deterministic score identity, configurable strategy delegation, bounded penalties, hard-risk reason preservation and advisory-only output.
- [x] Provider-independent `RiskAssessmentRepository` and `ScoreSnapshotRepository` with JSON-safe component/penalty mappings, reason-code round trips, explicit model/strategy/config identity and conflicting-replay rejection.
- [x] Fail-closed risk execution-eligibility predicate for stale, unknown, warned or blocked evidence.
- [x] Core Phase 6 / Sprint 6.3 `DecisionEngine` with versioned thresholds, one-step lifecycle mapping, fail-closed risk/config/freshness gates, hysteresis, cooldowns, deterministic score-delta/risk-escalation events and caller-owned persistence ports.
- [x] Core Phase 6 / Sprint 6.3 `EvidenceTimelineProjector` with separate event timestamps, provenance, quality, reasons, references, deterministic ordering and an optional no-lookahead `as_of` boundary.
- [x] Core Phase 7 / Sprint 7.1 alert pipeline with provider-independent event projection/rendering, bounded reason/evidence text, durable alert dedupe/suppression, per-destination rate limiting and leased notification outbox delivery.
- [x] HTTPS-only Telegram `sendMessage`/`getMe` adapter, deterministic fixture adapter, safe provider error classification and key-safe `make telegram-doctor`; notification state has no candidate, risk or execution authority.
- [x] Provider-independent Sprint 7.2 read contracts with immutable candidate/token/timeline/wallet/provider-health/audit/config views, strict bounded filters, recursive safe payload redaction and versioned resource-scoped cursors.
- [x] SQLAlchemy read adapter over persisted token/pool/candidate/observation/feature/risk/score/transition/alert records; non-persisted wallet/provider-health/audit/config catalogs remain explicit injectable empty state with no fabricated health.
- [x] Typed GET-only Sprint 7.2 FastAPI routes with strict Pydantic query/response models, correlation propagation, safe `404`/`422`/`503` errors and app-composed database lifecycle disposal; all read views remain non-authorizing.
- [x] Sprint 7.2 persistence, route, replay, application-boundary and Compose contracts; no migration or provider dependency was introduced.
- [x] Sprint 7.3 provider-independent control contracts with immutable safe defaults, explicit role/action authorization, allow-listed bounded config validation, canonical hashes and protected-mode enforcement.
- [x] Sprint 7.3 SQLAlchemy control persistence with singleton state, immutable config/audit history, migration `0004_control_plane`, transactional mutations, rehydration and physical read projections.
- [x] Sprint 7.3 FastAPI role authentication/control routes with constant-time bearer comparison, fail-closed `503`/`401`/`403` handling, authenticated configured read routes, auditable pause/kill/config controls and no execution authority.
- [x] Sprint 7.3 replay, RBAC, migration, provider-boundary, secret-scan, Compose and protected-mode contracts; no live-money or provider authority was introduced.
- [x] Sprint 8.1 responsive App Router shell with system/light/dark presentation, local-only theme override, mobile layout, focus-visible controls and reduced-motion handling.
- [x] Sprint 8.1 reusable typed score, risk, freshness, safety, advisory and realtime status primitives with accessible labels and explicit unavailable/unknown/stale/invalid states.
- [x] Sprint 8.1 browser-only realtime transport with optional public WebSocket endpoint, bounded exponential reconnect, retry exhaustion degradation, clean stop and ignored event payloads.
- [x] Sprint 8.1 frontend page, transport, theme, protected-mode and browser-boundary tests; no API credential, provider payload or execution capability was added to the web bundle.
- [x] Sprint 8.2 server-side read gateway with bounded timeout/status handling, strict normalized-record parsing, server-only viewer authentication and internal Compose URL support.
- [x] Sprint 8.2 ranked Radar route with API-order-preserving candidate cards, allow-listed GET filters, score/risk/freshness visibility, canonical token links and explicit empty/unavailable/invalid states.
- [x] Sprint 8.2 token detail route with validated UUID boundary, bounded overview/pools, API-order event-time timeline, provenance/reason-code projection, allow-listed SVG market/liquidity/net-flow charts and holder/social/narrative panels.
- [x] Sprint 8.2 browser-boundary tests prove no viewer credential, raw provider payload, response body or execution authority reaches rendered UI.
- [x] Sprint 8.3 strict server gateway reads for wallet intelligence, provider health/quota, control state/configuration and audit/config history, including safe secret-shaped field handling and address validation.
- [x] Sprint 8.3 server-rendered wallet, provider, settings and audit pages preserve API order, explicit empty/unavailable/invalid/degraded states and read-only permission boundaries.
- [x] Gate P8 Playwright browser acceptance for protected modes/navigation, operator intelligence routes, invalid wallet fail-closed behavior and no browser mutation/sign/submit/execute authority.
- [x] E8.4 provider-independent `ChainCursor`, explicit gap lifecycle, bounded backfill/recovery, range verification, restart/resume and observable bounded handoff; unresolved progress cannot cross an open gap.
- [x] E8.4 canonical normalized chain event contract with provenance, commitment/finality, recovery state, parser/registry/schema/strategy/config metadata and append-only revert correction.
- [x] E8.4 versioned `(program_id, discriminator_or_tag)` protocol registry, Anchor/native helpers, coverage audit and fail-closed unknown/unverified routing; completed Phase 2 adapters remain unchanged.
- [x] E8.4 durable `chain_cursors`, `stream_gaps`, `stream_verifications` state plus nullable observation metadata in reversible migration `0005_stream_integrity`.
- [x] E8.4 feature quality integration, deterministic no-lookahead replay manifest, safe stream telemetry and key-safe `stream-integrity-doctor`; live stream/RPC acceptance remains `BLOCKED_EXTERNAL`.
- [x] Phase 9.1 paper-only portfolio/cash ledger with Decimal sizing, normalized quote freshness/provenance, deterministic fee/slippage fills, explicit partial/rejected order states and append-only cash sequence.
- [x] Phase 9.1 idempotent order/fill/position persistence through `PaperLedgerStore` and SQLAlchemy migration `0006_paper_execution`; concurrent stale cash projections fail closed instead of overwriting ledger state.
- [x] Phase 9.1 `PaperReplayManifest` event-time/no-lookahead replay with policy/config/fill-model identity, deterministic replay IDs and future-observation exclusion.
- [x] Phase 9.1 `paper-trading-doctor` keyless contract check; missing/configured external quote paths remain `BLOCKED_EXTERNAL` and no endpoint/credential values are emitted.
- [x] Phase 9.2 deterministic paper exit evidence/policy, fixed SL/TP, trailing,
  break-even, distribution, liquidity/flow, score/time and partial-exit evaluator
  contracts; independent distribution-cluster support and external-only
  corroboration remain fail-closed.
- [x] Phase 9.2 append-oriented in-memory and SQLAlchemy exit-evaluation timeline
  with before/after evidence references, idempotency/conflict handling,
  deterministic event-time replay and no-lookahead contracts.
- [x] Phase 9.3 provider-free position projection over persisted paper positions
  and market observations, with observed-mark provenance, derived performance,
  advisory exit risk and closed-trade explanations.
- [x] Phase 9.3 GET-only position API and server-rendered `/positions` dashboard;
  missing, stale, invalid and future evidence remain explicit and no browser
  mutation or execution authority is exposed.
- [x] Phase 9.3 exit and paper-exit alert projection through the existing
  alert/outbox/Telegram seam, including persisted reason-code rehydration,
  core-trigger filtering, external-only suppression and bounded payloads.
- [x] Phase 10.1 normalized replay dataset and manifest contracts with stable
  date/venue/token partitions, event-time checkpoints, parser/registry/schema
  identity pinning and protected-mode preservation.
- [x] Phase 10.1 deterministic replay through the existing correlation and
  feature builders with strict occurred/observed/ingested no-lookahead
  filtering and explicit excluded future-event IDs.
- [x] Phase 10.1 future-only outcome labels for six horizons, MFE/MAE,
  forward return, time-to-target/drawdown, liquidity collapse, rug/security,
  creator dump and paper exit evidence.
- [x] Phase 10.1 cohort summaries, alternate-strategy comparison with shared
  event boundaries, redacted canonical JSON/flat CSV artifacts and bounded
  replay throughput profiler.
- [x] Phase 10.2 provider-free backtesting with deterministic paper-fill
  arithmetic, future-only exits, score-bucket/segment metrics, redacted
  JSON/CSV reports and explicit unknown/skip evidence.
- [x] Phase 10.3 score calibration with feature ablation, validated
  threshold/weight shadow candidates, train-only selection, time-split
  validation/test evidence, deterministic artifacts and non-authorizing
  promotion assessment.
- [x] E10.2 author/wallet attribution seam for forward-outcome lift,
  shrinkage/sample thresholds, external-label incremental value and
  bundle/side-wallet false-confluence measurement.
- [x] Phase 11.1 `ReliabilityMetrics` collector with bounded nearest-rank
  histograms, explicit sample-eviction counts, safe provider labels, source
  attribution and protected-mode serialization.
- [x] Phase 11.1 optional telemetry instrumentation for provider transport,
  Helius/Birdeye/protocol stream fallback, canonical chain ingest and outbox
  delivery/retry/dead-letter paths; telemetry errors cannot change business
  outcomes.
- [x] Phase 11.1 deterministic reliability tests for reconnect/fallback,
  malformed/duplicate/rate-limit behavior, bounded backpressure, outbox
  recovery and the opt-in Postgres connection-pool restart.
- [x] Phase 11.1 retention/index review and safe isolated backup/restore
  runbook at `docs/RUNBOOKS/RELIABILITY.md`; no destructive retention job or
  physical partitioning was introduced.
- [x] E11.1 keyless `reliability-benchmark-v1` report/doctor with p50/p95/p99
  for all six required stages, provider-network/internal attribution and an
  explicit decision to defer Rust/Yellowstone until real measurement.
- [x] Phase 11.2 provider-independent operations projection with versioned
  SLO policy, deterministic provider/degradation state precedence, quota/cost
  alerts, reliability counters and protected-mode serialization.
- [x] Phase 11.2 injected GET-only operations API and server-rendered
  `/operations` dashboard with bounded provider, SLO, quota, cost, alert and
  backpressure visibility; no browser mutation or execution authority.
- [x] Phase 11.2 operations runbook for provider outage, DB pressure, queue
  lag, alert delivery failure and quota/cost response; synthetic/keyless SLO
  evidence remains explicitly unverified.
- [x] Phase 11.3 `security-review-v1` keyless diagnostic for exact dependency
  locks, versioned/non-root Docker images, tracked-file secrets, RBAC/bearer
  and advisory LLM boundaries, external scan classification and protected
  modes.
- [x] Phase 11.3 Playwright advisory remediation: `@playwright/test` and its
  Playwright packages are pinned to `1.62.1`; npm audit subsequently reports
  zero vulnerabilities.
- [x] Phase 11.3 threat model and security-review runbook at
  `docs/THREAT_MODEL.md` and `docs/RUNBOOKS/SECURITY_REVIEW.md`; no signing,
  wallet, provider or live-money authority was introduced.
- [x] Roadmap checkboxes reconciled for Sprint 1.1.
- [x] SQLAlchemy 2 async persistence models for the core Phase 1 entities, with domain-independent repositories and explicit unit-of-work transactions.
- [x] Initial Alembic revision `0001_initial` for 13 core tables, including provenance, explainability, event and outbox fields.
- [x] Database uniqueness/idempotency constraints and event-time/queue indexes, with metadata and migration parity checks.
- [x] Candidate aggregate rehydration and atomic domain-event/outbox enqueue seam with deterministic duplicate handling.
- [x] Opt-in Postgres repository integration fixture and reversible migration smoke path.
- [x] Roadmap checkboxes reconciled for Sprint 1.2.
- [x] Provider-independent event dispatcher with deterministic event-time ordering, equivalent dedupe and conflicting-key rejection.
- [x] Leased Postgres outbox processing with durable delivery, deterministic retries, lease recovery and terminal dead-letter state.
- [x] Safe event-processing telemetry with allowlisted outcome, event identity, attempt and latency fields; handler exception text is never persisted or logged.
- [x] Duplicate, out-of-order, retry, lease-expiry, dead-letter, persistence idempotency-conflict and synthetic candidate lifecycle replay tests.
- [x] Reversible migration `0002_outbox_processing` and migration-head/metadata parity checks.
- [x] Roadmap checkboxes reconciled for Sprint 1.3.
- [x] Sprint 2.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-1-provider-framework.md`.
- [x] Async application-facing ports for discovery, market, on-chain, risk, social, narrative, quote, execution and notification capabilities.
- [x] Bounded HTTP/WebSocket timeout fields, retry classification with jitter, rate-limit waits and closed/open/half-open circuit breaker.
- [x] Provider health, quota and freshness projection with UNKNOWN/STALE fail-closed distinctions and safe error classes.
- [x] Recursive fixture redaction, deterministic JSON export, fake provider failures and normalized discovery/market adapter contracts.
- [x] Roadmap checkboxes reconciled for Sprint 2.1.
- [x] Sprint 2.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-2-helius-solana-read-layer.md`.
- [x] Helius/RPC read adapter for token metadata, account info and transaction enrichment with canonical identities and classified failures.
- [x] Helius token-program, mint/freeze authority, timestamp and transaction identity normalization with explicit UNKNOWN/INVALID quality states.
- [x] Injected Helius webhook/WebSocket observation seam with redaction, deterministic duplicate IDs, bounded reconnects and cancellation propagation.
- [x] Synthetic Helius JSON-RPC fixtures and contract tests for token, account and transaction reads.
- [x] Key-safe `make provider-doctor` with one bounded read-only `getHealth` call, safe status/latency/quota reporting and protected modes.
- [x] Roadmap checkboxes reconciled for Sprint 2.2; live Helius acceptance isolated as `BLOCKED_EXTERNAL` because endpoint/key configuration is absent.
- [x] Sprint 2.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-3-birdeye-dex-market-layer.md`.
- [x] Birdeye REST discovery and market adapter for new listings plus normalized market, trade, holder and security observations with bounded transport, correlation and key-safe error handling.
- [x] Birdeye stream-first listing normalizer with bounded reconnects, cancellation-safe polling fallback and duplicate-preserving candidate delivery.
- [x] Birdeye freshness/conflict resolver retaining source evidence, preserving unsafe quality states and marking stale/conflicted observations explicitly.
- [x] Synthetic Birdeye REST fixtures, deterministic fixture contracts and provider-specific fixture metadata; fixture content contains no credentials.
- [x] Key-safe `make birdeye-doctor` with bounded read-only `/defi/networks` health/schema check and `BLOCKED_EXTERNAL` handling when configuration is absent.
- [x] Sprint 2.3 roadmap, provider documentation and runtime smoke checks reconciled; live Birdeye acceptance remains isolated as `BLOCKED_EXTERNAL`.
- [x] Protocol-local Pump.fun, PumpSwap, Raydium and Meteora event parsers/adapters with allow-listed event types, alias normalization and classified malformed-input handling.
- [x] Deterministic canonical token/pool mapping and duplicate detector retaining token/pool keys and prior source IDs without dropping repeated deliveries.
- [x] Authenticated `POST /v1/manual/mints` analysis-only API with canonical Solana validation, deterministic manual identity, duplicate reporting and fail-closed operator auth configuration.
- [x] Synthetic launchpad/DEX fixtures and replay contracts for all four protocol adapters with no credentials or provider SDK dependency.
- [x] Sprint 2.4 roadmap, provider/security documentation and Compose runtime smoke checks reconciled; live protocol acceptance remains isolated as `BLOCKED_EXTERNAL`.
- [x] Gate P2 keyless composition contract connecting Birdeye discovery to independent Helius enrichment with shared canonical token identity and separate provenance.
- [x] Sprint 3.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-1-token-security.md` and completed.
- [x] Provider-independent `TokenSecurityEvaluator` with deterministic mint/freeze authority hard gates, explicit `PASS`/`WARN`/`BLOCK`/`UNKNOWN` outcomes, reason codes, penalties, evidence references, confidence and config hash.
- [x] Helius Token-2022 normalization preserves extension names and reported/unreported state in the on-chain observation without coupling provider code to application policy.
- [x] Independent read-only `RugCheckRestAdapter` maps official report-summary risks into provider-neutral findings, keeps verification informational and applies shared bounded transport/error handling.
- [x] Redacted RugCheck fixtures, adapter/provider contracts, security composition tests, key-safe `make rugcheck-doctor`, safe environment placeholders and Compose smoke coverage.
- [x] Sprint 3.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-2-holder-graph.md` and completed.
- [x] Provider-independent holder concentration snapshots derive bounded top1/top5/top10 metrics with explicit freshness, nullable incomplete evidence and Decimal range validation.
- [x] Known creator, configured pool, SPL Token/Token-2022/associated-token program and system addresses are classified, audited and excluded from ownership concentration where appropriate.
- [x] Bounded creator/top-holder funding and transfer graphs aggregate duplicate evidence, retain first/last times, provenance/source references, confidence and deterministic reason codes.
- [x] Union-find wallet clustering produces explainable shared-funder/related-wallet components and concentration-after-clustering metrics without execution authority.
- [x] Synthetic wallet-graph fixtures, credential-free replay contracts and Compose safe-mode smoke coverage are committed and pass.
- [x] Sprint 3.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-3-sprint-3-3-flow-analysis.md` and completed.
- [x] Provider-independent liquidity snapshots derive current depth and signed change from bounded fresh market evidence with nullable/fail-closed quality states.
- [x] Optional application quote evidence evaluates token sellability and price impact while preserving quote freshness separately from unsupported evidence.
- [x] Bounded organic-flow analysis derives maker diversity, transaction/maker ratio, repeated-size, circular-flow and rapid-round-trip heuristics with deterministic penalties and reason codes.
- [x] Safe/suspicious flow fixtures, replay contracts, no-provider/execution-surface checks and Compose safe-mode coverage are committed and pass.
- [x] Sprint 4.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-1-wallet-tracking.md` and completed.
- [x] Provider-independent tracked-wallet registry validates canonical addresses, explicit labels/tiers, idempotent duplicates and bounded active entries without automatic tier promotion.
- [x] Watched-wallet BUY/SELL observations normalize aliases, preserve provenance and all event timestamps, deduplicate equivalent deliveries and reject unknown/conflicting activity.
- [x] Bounded FIFO position reconstruction records open quantity/cost basis, conservative realized PnL, unmatched sells, hold duration, token age at entry and rug exposure with nullable/non-fresh evidence states.
- [x] Synthetic registry/activity/risk fixtures, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 4.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-2-smart-wallet-score.md` and completed.
- [x] Versioned `SmartWalletScore` aggregates completed FIFO outcomes for win rate, realized PnL, median return, early-entry rate and rug avoidance with explicit component values.
- [x] Rolling-window scoring excludes old outcomes, marks future outcomes invalid, deduplicates replayed round trips and applies bounded explicit manipulation penalties.
- [x] Neutral shrinkage, sample/confidence thresholds and non-mutating Tier-A/Tier-B recommendations prevent tiny or non-fresh samples from becoming Tier A.
- [x] Synthetic score snapshots/penalties, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 4.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-4-sprint-4-3-confluence.md` and completed.
- [x] Provider-independent confluence analysis joins qualified wallet scores to fresh FIFO entry/exit evidence with bounded windows and no-lookahead handling.
- [x] Existing holder-graph relationships are unioned transitively, including intermediary nodes, so correlated wallets count as one independently evidenced actor cluster.
- [x] Explainable `ENTRY`, `EXIT`, `CONFLUENCE` and `DISTRIBUTION` events plus bounded `TokenSmartMoneyScore` components/penalties preserve timestamps, provenance, evidence and no-execution authority.
- [x] Synthetic correlated-wallet/stale-graph fixtures, deterministic replay contracts and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 5.1 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-1-social-provider.md` and completed.
- [x] Provider-independent `SocialMention` contract and read-only compliant social/X adapter normalize post/author identity, UTC timestamps, bounded metrics, mint/ticker/link references and provenance.
- [x] Exact duplicate source IDs are idempotently collapsed; URL/mention-insensitive text fingerprints identify copied-text clusters and conflicting duplicate IDs fail closed.
- [x] Key-safe `make social-doctor`, redacted social replay fixtures, deterministic contract/unit tests and Compose safe-mode/runtime import checks are committed and pass.
- [x] Sprint 5.2 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-2-author-trust-social-velocity.md` and completed.
- [x] Explicit `SocialAuthorRegistry` trusted/KOL/blocked configuration resolves author tiers without automatic promotion or follower-count trust inference.
- [x] Provider-independent `AuthorTrustScore` and `SocialVelocityScore` calculate 1m/5m/15m mention and unique-author windows, engagement quality, duplicate/spam/coordination ratios, bounded confidence, reason codes and replay evidence.
- [x] Copied-text coordination and named bot-like burst heuristics remain advisory diagnostics; future/stale/invalid/conflicted critical evidence fails closed, fixtures/contracts/smoke pass and no result has execution authority.
- [x] Sprint 5.3 implementation plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-3-narrative-llm.md` and completed.
- [x] Strict provider-neutral `NarrativeInput`/`NarrativeSnapshot` contracts enforce bounded evidence, strict organic/sentiment enums, `0..1` probability/uncertainty/confidence ranges with a capped organic+promotional sum, validated token/cost usage and input-restricted evidence references.
- [x] Application `NarrativeAnalyzer` gateway strips secret/instruction/tool-shaped text, delimits untrusted content, enforces evidence/character/token/cost budgets, caches validated output by deterministic `sha256` content keys and degrades timeout/schema/outage/non-fresh states to zero-confidence fallback snapshots with explicit reason codes.
- [x] Keyless `FixtureNarrativeAdapter`, bounded `NarrativeRestAdapter` seam, redacted fixtures, key-safe `make narrative-doctor`, contract/unit/smoke tests and Compose safe-mode coverage pass; narrative output is advisory-only and never execution-eligible.
- [x] Research extension E5.4 implementation plan recorded at `docs/superpowers/plans/2026-08-30-extension-e5-4-call-performance.md` and completed.
- [x] Provider-independent `SocialCall` and `SocialCallOutcome` contracts reconstruct fixed forward-horizon returns/MFE/MAE, nullable rug/liquidity outcomes and token age with no-lookahead, bounded inputs and explicit quality/reason/version metadata.
- [x] `CallPerformanceSnapshot` aggregates per-author historical outcomes with neutral shrinkage, minimum sample/confidence gates, uncertainty and replay evidence; duplicate calls are idempotent with `DUPLICATE_CALL_DEDUPED`, while conflicts fail closed.
- [x] `AuthorTrustScorer` consumes caller performance only through an opt-in non-zero weight; default trust output is unchanged, insufficient history lowers confidence without moving score, and registry tiers/execution authority remain unchanged.
- [x] Credential-free E5.4 fixture replay, contract tests, Compose safe-mode smoke coverage and provider-independence checks pass for good, poor, rug-heavy, duplicated and insufficient-sample callers.
- [x] Research extension E2.5 implementation plan recorded at `docs/superpowers/plans/2026-08-30-extension-e2-5-pumpfun-lifecycle.md` and completed.
- [x] Schema-v2 rich Pump.fun/PumpSwap lifecycle events normalize launch, trade, bonding-curve progress, graduation/migration, pool creation, creator-fee and fee-recipient events with parser/version/provenance metadata.
- [x] Native protocol facts remain distinct from `DERIVED` whale-trade classifications; reliable `bonding_curve_progress_bps` evidence is validated and retained for later feature windows.
- [x] Stream-first `ProtocolEventStreamFallback` provides bounded reconnects, malformed-message counting, event-time ordering, duplicate preservation, cancellation propagation and one bounded poll fallback without a network or execution client.
- [x] Credential-free rich lifecycle replay fixture/contracts cover Pump.fun/PumpSwap ordering, duplicate delivery, malformed input, deterministic `protocol.lifecycle` observations, provider independence and all four protected modes.
- [x] Research extension E6.1 implementation plan recorded at `docs/superpowers/plans/2026-08-30-extension-e6-1-alpha-strategy.md` and completed.
- [x] Provider-independent `AlphaStrategy` protocol, mode-safe `StrategyPolicy`, immutable `StrategySnapshot` and deterministic `AlphaScoreV1Strategy` implement the documented seven-component weights, bounded penalties, confidence adjustments and fail-closed freshness/config semantics.
- [x] Hard risk disposition/blocks remain above strategy output; every strategy result is advisory and permanently not execution-eligible. The neutral `ReferenceStrategy` is test-only and not production ranking.
- [x] Keyless E6.1 replay fixtures/contracts cover exact weighted score arithmetic, reverse mapping determinism, sparse/malformed evidence, penalty clamping, blocked/unknown risk, strategy switching, score projection and provider-independence.
- [x] `ScoreSnapshot`/`ScoreSnapshotRow` retain explicit strategy name/version alongside model version and config hash through reversible migration `0003_score_strategy_identity`.
- [x] Research extension E6.2 implementation plan recorded at `docs/superpowers/plans/2026-08-30-extension-e6-2-external-wallet-intelligence.md` and completed.
- [x] Provider-independent `ExternalWalletLabel` and `ExternalWalletTokenSignal` preserve source confidence, observed/expiry TTL, raw source IDs, provenance, evidence references and quality state.
- [x] `ExternalWalletIntelligencePort`, bounded fixture adapter and replay fixtures provide a network-free external-wallet seam; no undocumented or brittle GMGN/CabalSpy scraper was added.
- [x] Fresh external labels receive only bounded agreement confidence when they match qualified internal `SmartWalletScore`; stale labels are ignored for positive confidence and disagreement is `CONFLICTED_EXTERNAL_WALLET_LABEL`.
- [x] Existing holder-graph clustering collapses external wallet actor clusters; tracked-supply, bundle, side-wallet and security flags remain corroborating features and cannot mutate internal risk/score authority or authorize execution.
- [x] Key-safe `make external-wallet-doctor`, provider-independent contract tests and protected-mode smoke coverage pass; live external-wallet acceptance remains `BLOCKED_EXTERNAL` without a documented/legal endpoint and adapter.

## Current sprint progress

- Sprint 1.3 plan recorded in `docs/superpowers/plans/2026-08-27-phase-1-sprint-1-3-event-processing.md` and completed.
- Gate P1 evidence: deterministic domain/dispatcher tests, three Postgres outbox integration tests, persisted processor delivery, lease recovery/dead-letter behavior and synthetic candidate lifecycle replay all pass.
- Sprint 2.1 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-1-provider-framework.md` and completed.
- Sprint 2.1 gate evidence: all documented provider ports are typed and async; keyless transport, health, fixture/fake and normalized adapter contract tests pass; API/worker runtime imports pass in rebuilt Compose images.
- Sprint 2.2 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-2-helius-solana-read-layer.md`.
- Sprint 2.2 gate evidence: Helius unit/stream/doctor and fixture contract tests pass; full repository quality gates pass; rebuilt API/worker images import the Helius adapter and stream seam while retaining all four safe modes.
- Sprint 2.3 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-3-birdeye-dex-market-layer.md`.
- Sprint 2.3 implementation checkpoint: adapter, stream/poll fallback, reconciliation, fixtures, doctor and smoke/runtime contracts are complete and pushed in coherent checkpoints.
- Sprint 2.3 gate evidence: full backend/frontend/Compose quality gates pass; keyless Birdeye fixture and doctor contracts pass; rebuilt API/worker images import the Birdeye adapter and fallback seam while retaining all four safe modes.
- Sprint 2.4 plan recorded in `docs/superpowers/plans/2026-08-27-phase-2-sprint-2-4-launchpad-dex-coverage.md` and completed.
- Sprint 2.4 gate evidence: protocol parser/identity tests, manual service/API tests, fixture contracts and runtime smoke checks pass; rebuilt API/worker images import all four protocol adapters and the manual API while retaining all four safe modes.
- Gate P2 keyless acceptance evidence: `tests/contract/test_phase2_gate.py` composes a Birdeye new-listing discovery fixture with an independent Helius token-enrichment fixture; both preserve the same canonical token UUID and separate provider provenance.
- Sprint 3.1 plan evidence: the implementation plan defines the provider-independent authority evaluator, independent RugCheck seam, key-safe doctor, fixture contracts, freshness/hard-gate tests, and final sprint quality gate.
- Sprint 3.1 gate evidence: Helius authority/Token-2022 normalization, deterministic token-security evaluation, RugCheck summary normalization, provider doctor classifications, keyless composition and safe-mode smoke checks pass; live RugCheck acceptance remains externally blocked without endpoint configuration.
- Sprint 3.2 plan evidence: the implementation plan defines bounded holder normalization, known-address classification, creator/top-holder graph traversal, union-find clustering, concentration-after-clustering, fixture replay and the synchronized keyless gate.
- Sprint 3.2 gate evidence: holder/graph unit tests, redacted fixture replay, canonical-address exclusion, repeated-edge aggregation, out-of-depth filtering, clustering and Compose safe-mode smoke contracts pass; no provider SDK or live execution path enters the application module.
- Sprint 3.3 plan evidence: the implementation plan defines bounded liquidity/depth snapshots, optional quote sellability, maker/trade heuristics, deterministic penalties, safe/suspicious fixture replay and the synchronized keyless gate.
- Sprint 3.3 gate evidence: liquidity change/depth, quote impact/sellability, maker diversity, repeated sizes, reciprocal flow, rapid round trips, score bounds, freshness states, fixture replay, source evidence and Compose runtime imports pass; `OrganicFlowScore.execution_eligible()` is explicitly non-authorizing.
- Sprint 4.1 plan evidence: the implementation plan defines explicit registry tiers, normalized wallet activity, duplicate/conflict handling, bounded FIFO reconstruction, nullable financial evidence, token age/hold/rug semantics, replay fixtures and the synchronized keyless gate.
- Sprint 4.1 gate evidence: registry/activity unit tests, FIFO partial-close and unmatched-sell tests, stale/future/missing-evidence tests, deterministic fixture replay, provider-independence checks and Compose safe-mode smoke/runtime imports pass; wallet snapshots have no execution authority.
- Sprint 4.2 plan evidence: the implementation plan defines versioned component aggregation, rolling-window/no-lookahead behavior, neutral shrinkage, explicit manipulation penalties, sample/confidence gates, tiny-sample Tier-A prevention, fixture replay and the synchronized keyless gate.
- Sprint 4.2 gate evidence: score unit tests, rolling/future/duplicate handling, nullable unknown metrics, threshold/recommendation tests, deterministic fixture replay, provider-independence checks and Compose safe-mode smoke/runtime imports pass; score results have no execution authority.
- Sprint 4.3 plan evidence: the implementation plan defines score/timestamp/event contracts, fresh graph clustering, independent entry/exit windows, confluence/distribution derivation, component scoring, fixture replay and fail-closed acceptance.
- Sprint 4.3 gate evidence: qualified-wallet entry/exit extraction, transitive correlated-wallet deduplication, missing/stale graph withholding, future-activity invalidation, deterministic event replay, component/penalty explanations, provider-independence and Compose safe-mode/runtime imports pass; smart-money results have no execution authority.
- Sprint 5.1 plan evidence: the implementation plan defines the normalized social contract extension, compliant read-only adapter, mint/ticker/link extraction, metric/timestamp normalization, exact dedupe, copied-text clustering, redacted fixtures, key-safe doctor and final keyless gate.
- Sprint 5.1 gate evidence: social adapter/doctor unit tests, deterministic health/search fixture replay, credential-free contracts, conflicting-duplicate and unsafe URL handling, provider-independence checks and Compose safe-mode/runtime imports pass; social evidence remains advisory and has no execution authority.
- Sprint 5.2 plan evidence: the implementation plan defines explicit author registry/list policy, 1m/5m/15m velocity and unique-author windows, engagement quality, duplicate/spam/coordination penalties, trust/velocity scores with confidence, copied-text bot-like heuristics, fixtures, fail-closed evidence handling and the final quality gate.
- Sprint 5.2 gate evidence: deterministic author registry/scorer unit tests, redacted replay fixtures, future/stale fail-closed contracts, credential/provider-independence checks, safe-mode assertions and rebuilt Compose runtime imports pass; social intelligence remains advisory and has no execution authority.
- Sprint 5.3 plan recorded at `docs/superpowers/plans/2026-08-27-phase-5-sprint-5-3-narrative-llm.md` and pushed as `2c21b4b`; the sprint is complete.
- Sprint 5.3 gate evidence: strict contract, sanitization, budget/cache/timeout, deterministic fallback, fixture/REST seam, doctor, replay, provider-contract and safe-mode smoke tests pass; `make verify` is green (`259 passed, 3 skipped`, branch-aware total coverage `79%`, Ruff, mypy `48 source files`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity); documentation reconciliation is complete. Gate P5 keyless acceptance passes: deterministic social features work with the narrative provider unavailable, and narrative output is visibly advisory with `execution_eligible()` always false.
- E5.4 plan recorded at `docs/superpowers/plans/2026-08-30-extension-e5-4-call-performance.md` and completed for the keyless acceptance; the implementation is independent of the unclear-license upstream caller-performance pattern.
- E5.4 gate evidence: focused unit, replay contract and Compose smoke tests pass; fixed `5m`/`15m`/`1h`/`6h`/`24h` horizons, no-lookahead exclusion, reversed-delivery determinism, nullable missing evidence, risk flags, token age, duplicate/conflict handling, neutral shrinkage, trust opt-in and all four protected modes are covered. E5.4 results remain advisory and have no execution authority.
- E2.5 plan recorded at `docs/superpowers/plans/2026-08-30-extension-e2-5-pumpfun-lifecycle.md` and completed; no unclear-license upstream code was copied.
- E2.5 gate evidence: schema/alias/origin unit tests, stream reconnect/fallback/cancellation tests, rich Pump.fun/PumpSwap fixture replay, deterministic event-time ordering, duplicate preservation, malformed rejection, curve-progress validation, lifecycle observation mapping, provider-independence checks and Compose safe-mode smoke tests pass.
- E2.5 live protocol acceptance remains isolated from the keyless seam; no provider SDK, network client, endpoint or credential was introduced.
- E6.1 plan recorded at `docs/superpowers/plans/2026-08-30-extension-e6-1-alpha-strategy.md` and completed for the keyless acceptance; the strategy module is provider/persistence/execution-port free.
- E6.1 gate evidence: focused strategy unit/contract/Compose smoke tests pass; AlphaScore v1 weights and penalty/clamp arithmetic, immutable explanations, candidate/config identity checks, stale/unknown/invalid handling, hard-risk preservation, reference-strategy switching, score projection and protected modes are covered.
- E6.2 plan recorded at `docs/superpowers/plans/2026-08-30-extension-e6-2-external-wallet-intelligence.md` and completed for the keyless acceptance; the application reconciliation module is provider/persistence/execution-port free.
- E6.2 gate evidence: immutable label/token-signal validation, source-ID dedupe/conflict handling, stale/future fail-closed behavior, internal SmartWalletScore agreement/disagreement, holder-graph actor-cluster collapse, bounded token features, security corroboration, provider removal and protected modes are covered by focused tests and fixtures.
- Environment note (2026-08-30): the local `.venv` had been rebuilt with host Python 3.14.4, which is incompatible with the pinned SQLAlchemy 2.0.37; the venv was recreated with the pinned `.python-version` (3.12.13) from `requirements.lock`, restoring `scripts/check_migrations.py` and the full gate. No dependency or source change was required.
- Verification note (2026-08-30): sandboxed test execution cannot wake the AnyIO/TestClient event-loop socket (`EPERM`) and stalls on pre-existing API TestClient tests; the same pinned environment passes the complete gate when run at the permitted external execution boundary. No application workaround was introduced for this host restriction.

## Verification evidence

All commands below were run in the current checkout on 2026-08-30 unless they record earlier dated evidence.

- `.venv/bin/pytest tests/unit/test_narrative.py tests/unit/test_narrative_provider.py tests/unit/test_narrative_doctor.py tests/contract/test_phase5_sprint5_3.py -q` — `15 passed`; strict narrative contracts, gateway sanitization/fallback, fixture/REST adapters, doctor and sprint contracts pass after the environment repair.
- `make verify` after Sprint 5.3 completion — exit `0`; Ruff, mypy (`48 source files`), `259 passed, 3 skipped`, total branch-aware coverage `79%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 5.3 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make narrative-doctor` with no narrative configuration — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, `api_url`/`api_key` presence only, model defaulted, no network/auth/schema check and all four protected modes preserved.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 5.3 — exit `0`; Compose topology and protected service modes remain valid.
- `./.venv/bin/python scripts/check_migrations.py` after Sprint 5.3 — exit `0`; `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `./.venv/bin/pytest tests/unit/test_call_performance.py tests/unit/test_social_intelligence.py tests/contract/test_extension_e5_4_call_performance.py tests/smoke/test_compose_contract.py -q` — `29 passed`; E5.4 contracts, fixture replay, trust integration, provider independence and all four protected modes pass.
- `make lint`, `make typecheck`, `make secret-scan`, `./.venv/bin/python scripts/check_migrations.py` and `docker compose -f infra/compose/docker-compose.yml config --quiet` after E5.4 implementation — all exit `0`; Ruff passes, mypy reports no issues in `49 source files`, the tracked-file secret scan is clean, migration parity reports `{"heads": ["0002_outbox_processing"], "table_count": 13}`, and Compose config is valid.
- `docker compose -p memeradar -f /tmp/memeradar-compose.yml up -d --build api worker` after Sprint 5.3 — exit `0`; rebuilt API/worker images include the narrative gateway and provider seam. The unmodified repository Compose file conflicts with unrelated host projects already publishing `5432`/`6379`, so an untracked temporary copy with remapped host ports (`15432`/`16379`) and identical service topology/modes was used; no repository Compose or user workload was changed.
- Compose Sprint 5.3 runtime probes — worker `narrative_worker_runtime_import_ok NarrativeAnalyzer narrative-gateway-v1 FixtureNarrativeAdapter`; API `narrative_api_runtime_import_ok narrative-v1`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and worker was running.
- `GET http://127.0.0.1:8000/health/live` after Sprint 5.3 — HTTP `200`, `{"status":"alive","service":"api","version":"0.1.0"}`; `GET /health/ready` — HTTP `200` with database and Redis reachable.
- `make verify` after E5.4 implementation — exit `0`; `269 passed, 3 skipped`, total branch-aware coverage `79%`, Ruff, mypy (`49 source files`), frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed.
- `make doctor` after E5.4 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make social-doctor` and `make narrative-doctor` after E5.4 with no provider configuration — exit `2` as expected; both report `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, configuration presence only, no network/auth/schema check, no credential values and all four protected modes.
- `docker compose -p memeradar -f /tmp/memeradar-compose.yml up -d --build api worker` after E5.4 — exit `0`; rebuilt API/worker images include `call_performance.py` and the trust integration while retaining the protected modes. The temporary Compose copy remaps host ports to `15432`/`16379` because unrelated host projects publish `5432`/`6379`.
- Compose E5.4 runtime probes — worker `e5_4_worker_runtime_import_ok CallPerformanceAnalyzer SocialCall SocialCallOutcome CallPerformanceSnapshot call-performance-v1`; API `e5_4_api_runtime_import_ok AuthorTrustScorer call-performance-v1`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and worker was running.
- `GET http://127.0.0.1:8000/health/live` after E5.4 — HTTP `200`, `{"status":"alive","service":"api","version":"0.1.0"}`; `GET /health/ready` — HTTP `200` with database and Redis reachable.
- `.venv/bin/pytest tests/unit/test_launchpad_dex.py tests/unit/test_launchpad_dex_identity.py tests/unit/test_protocol_stream.py tests/contract/test_extension_e2_5_pumpfun_lifecycle.py tests/contract/test_launchpad_dex_provider.py tests/smoke/test_compose_contract.py -q` — `54 passed`; rich schema, stream fallback, backward-compatible v1 parser, all venue contracts, fixture replay, malformed/duplicate handling and protected modes pass.
- `make lint` after E2.5 — exit `0`; Ruff passed for all applications, packages, tests and scripts.
- `make typecheck` after E2.5 — exit `0`; mypy reported `Success: no issues found in 50 source files`.
- `make secret-scan`, `./.venv/bin/python scripts/check_migrations.py` and `docker compose -f infra/compose/docker-compose.yml config --quiet` after E2.5 — all exit `0`; no tracked secrets, migration parity reports `{"heads": ["0002_outbox_processing"], "table_count": 13}`, and Compose config is valid.
- `make verify` after E2.5 — exit `0`; `287 passed, 3 skipped`, total branch-aware coverage `79%`, Ruff, mypy (`50 source files`), frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed. The gate ran at the permitted external execution boundary because the restricted sandbox cannot wake the pre-existing AnyIO/TestClient event-loop socket.
- `docker compose -p memeradar -f /tmp/memeradar-compose.yml up -d --build api worker` after E2.5 — exit `0`; rebuilt API/worker images include the rich lifecycle parser and stream fallback while retaining all four protected modes. The temporary Compose copy remaps host ports to `15432`/`16379` because unrelated host projects publish `5432`/`6379`.
- Compose E2.5 runtime probes — worker `e2_5_worker_runtime_import_ok launchpad-dex-v2 2 whale_trade DERIVED ProtocolEventStreamFallback`; API `e2_5_api_runtime_import_ok pump.fun pumpswap 1000`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and worker was running.
- `GET http://127.0.0.1:8000/health/live` after E2.5 — HTTP `200`, `{"status":"alive","service":"api","version":"0.1.0"}`.

Earlier dated evidence:
- `.venv/bin/pytest tests/unit/test_event_processing.py tests/unit/test_telemetry.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q` — `18 passed` before the final synthetic replay/idempotency additions; the final full gate below includes those additions.
- `.venv/bin/pytest tests/unit/test_event_processing.py -q` — `7 passed`; dispatcher ordering/dedupe/conflict, synthetic candidate replay, retry/backoff, dead-letter redaction and worker cancellation pass.
- `MEMERADAR_TEST_DATABASE_URL`-configured `.venv/bin/pytest tests/integration/test_persistence_postgres.py -q` — `3 passed`; candidate persistence/idempotency conflict, lease recovery/dead-letter and transactional processor delivery pass.
- `make verify` — exit `0`; Ruff, mypy (`32 source files`), `97 passed, 3 skipped`, total branch-aware coverage `74%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_birdeye_doctor.py tests/unit/test_birdeye_normalization.py tests/unit/test_birdeye_stream.py tests/unit/test_birdeye_reconciliation.py tests/contract/test_birdeye_provider.py -q` — `21 passed`; Birdeye normalization, stream fallback/cancellation, reconciliation, fixture replay and doctor classifications pass keylessly.
- `make verify` after Sprint 2.3 — exit `0`; Ruff, mypy (`34 source files`), `119 passed, 3 skipped`, total branch-aware coverage `75%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_launchpad_dex.py tests/unit/test_launchpad_dex_identity.py tests/unit/test_manual_submission.py tests/unit/test_manual_api.py tests/contract/test_launchpad_dex_provider.py tests/smoke/test_compose_contract.py -q` — `36 passed`; Sprint 2.4 parser, identity, manual API, fixture and smoke contracts pass keylessly.
- `make verify` after Sprint 2.4 — exit `0`; Ruff, mypy (`37 source files`), `150 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make verify` after Gate P2 — exit `0`; Ruff, mypy (`37 source files`), `151 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_token_security.py tests/unit/test_helius_normalization.py -q` — `16 passed`; authority hard blocks, UNKNOWN/stale/conflicted freshness, Token-2022 extension handling, provider-advisory semantics and Helius normalization pass.
- `.venv/bin/pytest tests/unit/test_rugcheck.py -q` — `8 passed`; official summary-path mapping, severity normalization, verification information, bearer-header safety, schema rejection and classified transport failures pass.
- `.venv/bin/pytest tests/unit/test_rugcheck_doctor.py tests/contract/test_rugcheck_provider.py tests/contract/test_phase3_sprint3_1.py -q` — `10 passed`; optional-key `/ping` doctor behavior, redacted classifications, fixture replay and Helius+RugCheck composition pass.
- `.venv/bin/pytest tests/smoke/test_compose_contract.py -q` — `7 passed`; local topology, provider imports, RugCheck doctor wiring and all four protected modes pass.
- `make verify` after Sprint 3.1 — exit `0`; Ruff, mypy (`39 source files`), `180 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_holder_graph.py tests/contract/test_phase3_sprint3_2.py tests/smoke/test_compose_contract.py -q` — `16 passed`; holder normalization, address exclusion, freshness, bounded graph traversal, duplicate-edge aggregation, fixture replay, clustering and all-four-mode Compose smoke contracts pass.
- `make verify` after Sprint 3.2 — exit `0`; Ruff, mypy (`40 source files`), `189 passed, 3 skipped`, total branch-aware coverage `76%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 3.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 3.2 — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 3.2 — exit `0`; holder-graph fixtures and documentation contain no tracked secret material.
- `.venv/bin/pytest tests/unit/test_flow_analysis.py tests/contract/test_phase3_sprint3_3.py tests/smoke/test_compose_contract.py -q` — `17 passed`; safe/suspicious fixture replay, liquidity/depth change, optional quote sellability/impact, maker-flow heuristics, score penalties, no-execution surface and protected modes pass.
- `make verify` after Sprint 3.3 — exit `0`; Ruff, mypy (`41 source files`), `198 passed, 3 skipped`, total branch-aware coverage `77%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 3.3 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 3.3 — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 3.3 — exit `0`; flow-analysis fixtures and documentation contain no tracked secret material.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 3.3 — exit `0`; rebuilt API/worker images include the flow-analysis module.
- Compose Sprint 3.3 runtime probes — worker `flow_worker_runtime_import_ok FlowAnalyzer 100`; API `flow_api_runtime_import_ok OrganicFlowScore`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy and web/worker were running.
- `.venv/bin/pytest tests/unit/test_wallet_tracking.py -q` — `7 passed`; registry identity/idempotency, aliases, FIFO matching, nullable PnL, token age, rug exposure, unmatched sells and freshness fail-closed behavior pass.
- `make lint typecheck` after Sprint 4.1 application work — exit `0`; Ruff passes and mypy reports `Success: no issues found in 42 source files`.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_1.py tests/smoke/test_compose_contract.py tests/unit/test_wallet_tracking.py -q` — `19 passed`; credential-free registry/activity/risk fixture replay, deterministic FIFO/rug reconstruction, provider-independence and all-four-mode Compose contracts pass.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 4.1 fixture wiring — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 4.1 fixture wiring — exit `0`; wallet-tracking fixtures and docs contain no tracked secret material.
- `make verify` after Sprint 4.1 — exit `0`; Ruff, mypy (`42 source files`), `208 passed, 3 skipped`, total branch-aware coverage `77%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.1 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.1 — exit `0`; rebuilt API/worker images include wallet-tracking code and both containers started.
- Compose Sprint 4.1 runtime probes — worker `wallet_tracking_worker_runtime_import_ok WalletTrackingAnalyzer 5000`; API `wallet_tracking_api_runtime_import_ok TrackedWalletRegistry WalletTrackingSnapshot`; both asserted all four protected mode values. Compose API was healthy, Postgres/Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_wallet_scoring.py -q` — `6 passed`; component aggregation, penalties, rolling-window duplicate/future handling, shrinkage, minimum sample/confidence and non-mutating tier recommendations pass.
- `make lint typecheck` after Sprint 4.2 application work — exit `0`; Ruff passes and mypy reports `Success: no issues found in 43 source files`.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_2.py tests/unit/test_wallet_scoring.py tests/smoke/test_compose_contract.py -q` — `19 passed`; credential-free score snapshot/penalty replay, deterministic decomposition, provider-independence and all-four-mode Compose contracts pass.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 4.2 fixture wiring — exit `0`; Compose topology and protected service modes remain valid.
- `.venv/bin/python scripts/secret_scan.py` after Sprint 4.2 fixture wiring — exit `0`; wallet-scoring fixtures and docs contain no tracked secret material.
- `make verify` after Sprint 4.2 — exit `0`; Ruff, mypy (`43 source files`), `217 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.2 — exit `0`; rebuilt API/worker images include wallet scoring and both containers started.
- Compose Sprint 4.2 runtime probes — worker `wallet_scoring_worker_runtime_import_ok SmartWalletScorer smart-wallet-v1`; API `wallet_scoring_api_runtime_import_ok SmartWalletScore`; both asserted all four protected mode values. Compose API was healthy, Postgres/Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_confluence.py tests/contract/test_phase4_sprint4_3.py -q` — `6 passed`; qualification gates, transitive graph clustering, event derivation, component scoring, stale/missing graph handling and future-data invalidation pass.
- `.venv/bin/pytest tests/contract/test_phase4_sprint4_3.py tests/smoke/test_compose_contract.py -q` — `14 passed`; fresh/stale fixture replay, credential-free contract checks, provider-independent application seam and all four protected modes pass.
- `make lint typecheck secret-scan` after Sprint 4.3 — exit `0`; Ruff, mypy (`44 source files`) and tracked-file secret scan pass.
- `make verify` after Sprint 4.3 — exit `0`; Ruff, mypy (`44 source files`), `224 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 4.3 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make provider-doctor` after Sprint 4.3 — exit `2` as expected; Helius status is `BLOCKED_EXTERNAL` with `CONFIGURATION_MISSING`, network/auth/schema are `not_checked`, and no credential values are emitted.
- `docker compose -f infra/compose/docker-compose.yml config --quiet && .venv/bin/python scripts/check_migrations.py` after Sprint 4.3 — exit `0`; Compose config is valid and migration parity reports `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 4.3 — exit `0`; rebuilt API/worker images include confluence analysis and both containers started healthy/running.
- Compose Sprint 4.3 runtime probes — worker `confluence_worker_runtime_import_ok ConfluenceAnalyzer TokenSmartMoneyScore`; API `confluence_api_runtime_import_ok smart-money-confluence-v1 CONFLUENCE`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/unit/test_social.py tests/unit/test_social_doctor.py tests/contract/test_social_provider.py tests/smoke/test_compose_contract.py -q` — `23 passed`; social normalization, extraction, copied-text clustering, duplicate conflict handling, unsafe URL/transport classification, doctor redaction/classification, fixture replay, provider independence and all four protected modes pass.
- `make lint` — exit `0`; Ruff passed for all applications, packages, tests and scripts.
- `make typecheck` — exit `0`; mypy reported `Success: no issues found in 45 source files`.
- `.venv/bin/python scripts/secret_scan.py` — exit `0`; social adapter, doctor, fixtures and documentation contain no tracked secret material.
- `make verify` after Sprint 5.1 — exit `0`; Ruff, mypy (`45 source files`), `235 passed, 3 skipped`, total branch-aware coverage `78%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `.venv/bin/pytest tests/unit/test_helius_normalization.py::test_malformed_rpc_response_is_a_classified_schema_failure -q` — `1 passed`; the synthetic `NOW` clock is injected so the test deterministically reaches schema classification instead of expiring against the host clock.
- `.venv/bin/pytest tests/unit/test_social_intelligence.py tests/contract/test_phase5_sprint5_2.py tests/smoke/test_compose_contract.py -q` — `21 passed`; registry/tier policy, trust and velocity replay, windows, metric quality, coordination/bot-like diagnostics, future/stale handling, provider independence, fixture determinism and protected modes pass.
- `make verify` after Sprint 5.2 — exit `0`; Ruff, mypy (`46 source files`), `243 passed, 3 skipped`, total branch-aware coverage `79%`, frontend lint, frontend typecheck, Vitest (`1` test passed), Compose config, secret scan and migration contract all completed.
- `make doctor` after Sprint 5.2 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make social-doctor` with no social configuration after Sprint 5.2 — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, configuration presence only, all four protected modes and no credential values.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 5.2 — exit `0`; Compose topology and protected service modes remain valid.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 5.2 — exit `0`; rebuilt API/worker images include the social intelligence module and both containers started.
- Compose Sprint 5.2 runtime probes — worker `social_intelligence_worker_runtime_import_ok AuthorTrustScorer SocialVelocityScorer`; API `social_intelligence_api_runtime_import_ok AuthorTrustScorer SocialVelocityScorer`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `./.venv/bin/python scripts/secret_scan.py` after Sprint 5.2 — exit `0`; social intelligence fixtures, code and documentation contain no tracked secret material.
- `./.venv/bin/python scripts/check_migrations.py` after Sprint 5.2 — exit `0`; `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `.venv/bin/pytest tests/unit/test_narrative.py tests/unit/test_narrative_provider.py tests/unit/test_narrative_doctor.py tests/contract/test_phase5_sprint5_3.py tests/unit/test_provider_contracts.py tests/smoke/test_compose_contract.py -q` — `36 passed`; the current Sprint 5.3 keyless narrative contracts, sanitization, fallback/cache behavior, fixture/REST seam, doctor, provider contracts and safe-mode smoke checks pass.
- `make lint` — exit `0`; Ruff passed for all applications, packages, tests and scripts after the current Sprint 5.3 slice.
- `make typecheck` — exit `0`; mypy reported `Success: no issues found in 48 source files` after the current Sprint 5.3 slice.
- `make secret-scan` — exit `0`; the current narrative implementation, doctor, fixtures and documentation contain no tracked secret material.
- `make narrative-doctor` with no narrative configuration — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, `api_url`/`api_key` presence only, model defaulted, no network/auth/schema check and all four protected modes preserved.
- `git diff --check` — exit `0`; the saved in-progress Sprint 5.3 working-tree patch has no whitespace errors.
- `make doctor` after Sprint 5.1 — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and `analysis_only=true`, `paper_trading=true`, `manual_execution=false`, `auto_execution=false` are reported.
- `make social-doctor` with no social configuration — exit `2` as expected; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, configuration presence only, all four protected modes and no credential values.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` after Sprint 5.1 — exit `0`; Compose topology and protected service modes remain valid.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 5.1 — exit `0`; rebuilt API/worker images include the social adapter and both containers started.
- Compose Sprint 5.1 runtime probes — worker `social_worker_runtime_import_ok SocialRestAdapter social-search-v1`; API `social_api_runtime_import_ok social /v1/search`; both asserted all four protected mode values. Compose API, Postgres and Redis were healthy, and web/worker were running.
- `.venv/bin/pytest tests/contract/test_phase2_gate.py -q` — `1 passed`; keyless discovery/enrichment composition is deterministic and provider-independent at the application boundary.
- `.venv/bin/mypy` — `Success: no issues found in 32 source files`.
- `.venv/bin/pytest tests/unit/test_provider_contracts.py tests/unit/test_provider_transport.py tests/unit/test_provider_health.py tests/unit/test_provider_fixtures.py tests/contract/test_provider_adapters.py -q` — `23 passed`; provider ports, resilience, health/freshness/quota, redaction/fakes and normalized adapter contracts pass.
- `.venv/bin/mypy` after the provider package was included in the configured source roots — `Success: no issues found in 30 source files`.
- `.venv/bin/pytest tests/unit/test_helius_normalization.py tests/unit/test_helius_stream.py tests/unit/test_provider_doctor.py tests/contract/test_helius_provider.py -q` — `19 passed`; Helius normalization, stream/reconnect/cancellation, doctor classification and fixture replay contracts pass.
- `make lint typecheck secret-scan` after Sprint 2.2 — exit `0`; Ruff, mypy (`32 source files`) and tracked-file secret scan pass.
- `make provider-doctor` with no Helius configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with no credential values emitted.
- `make birdeye-doctor` with no Birdeye configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with `api_url`/`api_key` presence only and no credential values emitted.
- `make rugcheck-doctor` with no RugCheck configuration — exit `2`; report status `BLOCKED_EXTERNAL`, reason `CONFIGURATION_MISSING`, with `api_url`/`api_key` presence only and no credential values emitted.
- `make doctor` — exit `0`; local dependencies are `not_required`, external provider checks are `not_run`, and all four protected modes are reported safely.
- `./.venv/bin/pytest tests/smoke/test_compose_contract.py -q` — `6 passed`; Compose topology, safe modes, Helius, Birdeye, launchpad/DEX and manual API wiring pass.
- `alembic downgrade base && alembic upgrade head && alembic check` against local Compose Postgres — exit `0`; reversible migration cycle passed and `No new upgrade operations detected.`
- `scripts/check_migrations.py` — exit `0`; `{"heads": ["0002_outbox_processing"], "table_count": 13}`.
- `make integration-test` with the local Compose Postgres URL — exit `0`; `3 passed`.
- `npm audit --omit=dev` — `found 0 vulnerabilities`.
- `docker compose -f infra/compose/docker-compose.yml config --quiet` — exit `0`.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` — exit `0`; rebuilt API/worker images include the event-processing, persistence and telemetry packages.
- Compose runtime import probe — `worker_event_processing_import_ok`; application event processing, `SqlAlchemyOutboxStore` and structured event telemetry import in the worker image.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after provider packaging — exit `0`; API/worker images include `packages/providers/src`.
- Compose provider runtime probes — `provider_framework_import_ok 9` in worker and `provider_package_import_ok 0.1.0` in API; all nine provider capabilities import without credentials.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.2 — exit `0`; API/worker images rebuilt with Helius read/stream code.
- Compose Helius runtime probes — worker `helius_runtime_import_ok helius helius-stream-v1 True`; API `helius_api_runtime_import_ok helius helius`; both probes asserted all four safe-mode environment values.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.3 — exit `0`; API/worker images rebuilt with Birdeye adapter, stream fallback and reconciliation code.
- Compose Birdeye runtime probes — worker `birdeye_worker_runtime_import_ok birdeye birdeye-stream-v1`; API `birdeye_api_runtime_import_ok birdeye`; both probes asserted all four safe-mode environment values. Compose status reported API healthy, Postgres healthy, Redis healthy, web running and worker running.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 3.1 — exit `0`; API/worker images rebuilt with token-security, Helius extension and RugCheck modules.
- Compose Sprint 3.1 runtime probes — worker `phase3_worker_runtime_import_ok TokenSecurityEvaluator rugcheck`; API `phase3_api_runtime_import_ok token-security-v1 rugcheck`; both probes asserted all four safe-mode environment values. Compose API, Postgres and Redis were healthy; web and worker were running.
- `GET http://127.0.0.1:8000/health/live` — HTTP `200`, `{"status":"alive","service":"api","version":"0.1.0"}`; `GET /health/ready` — HTTP `200` with database and Redis reachable.
- `docker compose -f infra/compose/docker-compose.yml up -d --build api worker` after Sprint 2.4 — exit `0`; API/worker images rebuilt with launchpad/DEX adapters and manual submission service.
- Compose Sprint 2.4 runtime probes — worker `launchpad_worker_runtime_import_ok ['pump.fun', 'pumpswap', 'raydium', 'meteora']`; API `manual_api_runtime_import_ok /v1/manual/mints`; both probes asserted all four safe-mode environment values. A host probe returned `/health/live` HTTP `200` and unauthenticated manual submission HTTP `503` with `manual submission authentication is not configured`.
- Compose status — API healthy, Postgres healthy, Redis healthy, web running and worker running after the event-processing image rebuild.
- `GET http://127.0.0.1:8000/health/live` — `{"status":"alive","service":"api","version":"0.1.0"}`.
- `GET http://127.0.0.1:8000/health/ready` — HTTP `200`; database and Redis both reported `required: true, state: reachable` inside Compose.
- `GET http://127.0.0.1:3000` — page contains `MemeRadar`, `ANALYSIS ONLY` and `PAPER TRADING`.
- Worker log includes `worker_started`.
- API logs — structured JSON `request_completed` records include a generated correlation ID, HTTP method/path/status and duration.
- `make doctor` — safe modes reported, local dependencies `not_required` when no URLs are configured, external provider checks `not_run`.
- CI YAML parse check — `CI workflow parsed: 4 jobs`.

The worker container initially exited because `__main__.py` was missing. The failure was reproduced from container logs, covered by a regression test, fixed, rebuilt and reverified as running.

## External provider acceptance

- Phase 0 and Phase 1 provider acceptance: `NOT_APPLICABLE` — no provider credentials are required for the completed foundation/domain work.
- Sprint 2.1 keyless provider framework/fixture acceptance: `PASS` — contract tests and fake providers pass without external credentials.
- Sprint 2.2 Helius fixtures, normalization, stream seam and doctor contract acceptance: `PASS` — all keyless tests and redacted fixtures pass.
- Sprint 2.2 live Helius read-only acceptance: `BLOCKED_EXTERNAL` — `make provider-doctor` found both `HELIUS_RPC_URL` and `HELIUS_API_KEY` missing, so no live call was attempted and no live success is claimed.
- Sprint 2.3 Birdeye fixtures, normalization, stream fallback, reconciliation and doctor contract acceptance: `PASS` — synthetic/redacted fixtures, keyless adapter tests, doctor classifications and runtime imports pass.
- Sprint 2.3 live Birdeye read-only acceptance: `BLOCKED_EXTERNAL` — `make birdeye-doctor` found both `BIRDEYE_API_URL` and `BIRDEYE_API_KEY` missing, so no live call was attempted and no live success is claimed.
- Sprint 2.4 protocol fixture and manual API acceptance: `PASS` — all keyless parser, canonical identity, duplicate, fixture replay, API auth and runtime checks pass.
- Sprint 2.4 live Pump.fun/PumpSwap/Raydium/Meteora acceptance: `BLOCKED_EXTERNAL` — no live protocol endpoint/credential configuration is present, so no live call was attempted and no live success is claimed.
- Gate P2 keyless acceptance: `PASS` for normalized discovery/enrichment seams and deterministic fixtures; live read-only acceptance remains `BLOCKED_EXTERNAL` for missing provider access.
- Gate P2 overall live acceptance: `BLOCKED_EXTERNAL` — the required real provider calls could not be attempted without configured read-only endpoint/credential access; the keyless composition evidence is not substituted for live success.
- Sprint 3.1 Helius authority/Token-2022 and RugCheck fixture/contract acceptance: `PASS` — deterministic keyless evaluation, redacted fixtures, provider seam and doctor classifications pass.
- Sprint 3.1 live RugCheck read-only acceptance: `BLOCKED_EXTERNAL` — `make rugcheck-doctor` found `RUGCHECK_API_URL` missing; no live call was attempted and no live success is claimed.
- Sprint 3.2 holder concentration/wallet graph fixture and contract acceptance: `PASS` — deterministic normalized observations, bounded graph/cluster analysis, canonical-address exclusions and all protected modes pass without live credentials.
- Sprint 3.2 live holder/graph provider acceptance: `BLOCKED_EXTERNAL` — Helius and Birdeye endpoint/credential configuration remains absent; no live holder or wallet-graph call was attempted and no live-provider success is claimed.
- Sprint 3.3 liquidity/flow fixture and contract acceptance: `PASS` — deterministic safe/suspicious market, trade and quote replay, freshness behavior, penalties, reason codes and no-execution surface pass without live credentials.
- Sprint 3.3 live market/quote provider acceptance: `BLOCKED_EXTERNAL` — Birdeye and Jupiter endpoint/credential configuration is absent; no live liquidity, trade or quote call was attempted and no live-provider success is claimed.
- Sprint 4.1 wallet registry/activity/FIFO fixture and contract acceptance: `PASS` — deterministic tracked-wallet replay, duplicate delivery handling, partial FIFO close, unmatched sell, token-age/rug evidence and all protected modes pass without credentials.
- Sprint 4.1 live wallet activity/rug-outcome acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/risk provider endpoint or credential is available; no live wallet call was attempted and no live-provider success is claimed.
- Sprint 4.2 wallet-score fixture and contract acceptance: `PASS` — deterministic SmartWalletScore aggregation, rolling/future/duplicate handling, threshold gates, explicit penalties and all protected modes pass without credentials.
- Sprint 4.2 live wallet-history acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/provider endpoint or credential is available; no live wallet-history call was attempted and no live-provider success is claimed.
- Sprint 4.3 confluence fixture and contract acceptance: `PASS` — deterministic qualified-wallet entry/exit replay, transitive graph clustering, confluence/distribution events, token component score, stale/missing graph fail-closed behavior and all protected modes pass without credentials.
- Sprint 4.3 live wallet-history/graph acceptance: `BLOCKED_EXTERNAL` — no configured read-only chain/graph provider endpoint or credential is available; no live wallet-history/graph call was attempted and no live-provider success is claimed.
- Sprint 5.1 social/X fixture, adapter and doctor acceptance: `PASS` — deterministic credential-free health/search replay, normalization, extraction, dedupe, copied-text clustering, redaction and protected-mode contracts pass.
- Sprint 5.1 live social/X read-only acceptance: `BLOCKED_EXTERNAL` — `SOCIAL_API_URL` and `SOCIAL_API_KEY` are missing; `make social-doctor` did not attempt a live call and no live-provider success is claimed.
- Sprint 5.2 author trust/velocity fixture and contract acceptance: `PASS` — deterministic explicit registry policy, trust/velocity scores, 1m/5m/15m windows, quality/duplicate/spam/coordination diagnostics, fail-closed future/stale handling and protected-mode contracts pass without credentials or an LLM.
- Sprint 5.2 live social/X read-only acceptance: `BLOCKED_EXTERNAL` — `SOCIAL_API_URL` and `SOCIAL_API_KEY` remain missing; `make social-doctor` did not attempt a live call and no live-provider success is claimed.
- Sprint 5.3 keyless narrative acceptance: `PASS` — strict structured output, bounded prompt/input sanitization, budget/cache/timeout behavior, deterministic fallback, fixture/REST seams, doctor classifications, replay contracts and protected-mode checks pass without credentials or a live LLM.
- Gate P5 keyless acceptance: `PASS` — deterministic social features (Sprints 5.1/5.2) work with the narrative provider unavailable; narrative output is visibly advisory with `execution_eligible()` always false and cannot bypass risk gates.
- Sprint 5.3 live narrative provider acceptance: `BLOCKED_EXTERNAL` — `NARRATIVE_API_URL` and `NARRATIVE_API_KEY` are missing; `make narrative-doctor` did not attempt a live call and no live-provider success is claimed.
- E5.4 keyless historical caller-performance acceptance: `PASS` — deterministic credential-free fixture replay, no-lookahead and duplicate/conflict contracts, neutral shrinkage, opt-in trust integration and protected-mode checks pass.
- E2.5 keyless rich protocol lifecycle acceptance: `PASS` — schema-v2 typed events, native/derived origin separation, validated curve-progress evidence, deterministic stream/fallback replay, malformed/duplicate/order contracts, lifecycle observation mapping and protected-mode checks pass without credentials or protocol SDKs.
- E2.5 live Pump.fun/PumpSwap/Raydium/Meteora acceptance: `BLOCKED_EXTERNAL` — no documented read-only protocol endpoint/credential configuration is present; no live call was attempted and no live-provider success is claimed.
- E6.2 keyless external-wallet acceptance: `PASS` — deterministic label/token-signal replay, internal-score agreement/disagreement, stale/future/conflict handling, holder-graph actor collapse, bounded token features, security corroboration, provider removal and permanent non-execution behavior pass without credentials or network calls.
- E6.2 live external-wallet acceptance: `BLOCKED_EXTERNAL` — no documented/legal GMGN/CabalSpy-style endpoint and reviewed adapter is configured; `make external-wallet-doctor` reports configuration presence only and does not probe arbitrary URLs.
- Sprint 7.1 keyless alert/Telegram acceptance: `PASS` — deterministic decision/risk/provider-health projection, bounded reason/evidence rendering, secret redaction, fixture delivery, dedupe, suppression, rate limiting, retry timing, safe provider error classification and protected-mode contracts pass without credentials.
- Sprint 7.1 live Telegram acceptance: `BLOCKED_EXTERNAL` — `TELEGRAM_API_URL`, `TELEGRAM_BOT_TOKEN` and/or `TELEGRAM_CHAT_ID` are not configured; `make telegram-doctor` reports configuration presence only and no live Telegram call or provider success is claimed.
- Sprint 6.1 keyless feature-window acceptance: `PASS` — exact `1m`/`5m`/`15m` snapshots, seven bounded family maps, normalized AlphaStrategy components, sparse/unknown handling, future/pre-boundary invalidation, provenance/freshness, reverse-delivery determinism and permanent non-execution behavior pass with the redacted fixture.
- Sprint 6.1 persistence acceptance: `PASS` — feature snapshot values and provenance round-trip through the existing table contract; equivalent snapshot replay is idempotent and conflicting identity reuse raises `IdempotencyConflict`. No migration was required.
- Birdeye and Jupiter live checks: `NOT_RUN`; no live-provider PASS is claimed.

## Blockers

- No blocker affects E2.5, E5.4, E6.2, Sprint 5.3, Sprint 6.1, Sprint 6.2, Sprint 6.3, Sprint 7.1, Sprint 9.3 or the keyless Gate P5/Gate P6 acceptance. Helius, Birdeye, E2.5 live protocol acceptance, the live portion of Gate P2, Sprint 3.1 live RugCheck acceptance, Sprint 3.2 live holder/graph acceptance, Sprint 3.3 live market/quote acceptance, Sprint 4.1 live wallet/rug acceptance, Sprint 4.2 live wallet-history acceptance, Sprint 4.3 live wallet-history/graph acceptance, Sprint 5.1/Sprint 5.2 live social/X acceptance, Sprint 5.3 live narrative acceptance, E6.2 live external-wallet acceptance, Sprint 7.1 live Telegram acceptance, Sprint 9.1/9.2 live quote acceptance and Sprint 9.3 live market/Telegram acceptance remain externally blocked for missing endpoint/credential configuration; no live-provider success is claimed.
- The GitHub Actions workflow is committed but its hosted run result has not been independently observed in this session; local equivalents are green.

## Migration and schema state

- `packages/persistence` contains the provider-independent SQLAlchemy 2 async models, candidate/outbox repositories and explicit unit-of-work boundary.
- `infra/alembic/versions/0001_initial.py` creates the 13 core Phase 1 tables represented by the current metadata; `0002_outbox_processing.py` adds leased processing/dead-letter columns and indexes. Social, wallet, extended market, research and execution tables remain later roadmap extensions.
- `infra/alembic/versions/0003_score_strategy_identity.py` adds bounded non-null `strategy_name` and `strategy_version` columns to `score_snapshots`, backfilling existing rows as `legacy`; migration parity now reports head `0003_score_strategy_identity` with 13 tables.
- Local Postgres upgrade/downgrade/upgrade, migration parity and repository integration checks pass. The API and worker images include the persistence and event-processing packages plus the feature-snapshot repository, but the current API/worker composition still does not write candidate, feature or other business state automatically.
- Sprint 4.1 remains a provider-independent warm-path application contract; no physical wallet migration is introduced. The existing future wallet tables remain the persistence target for a later roadmap task, and the current API/worker composition still does not write wallet business state automatically.
- Sprint 4.2 remains a provider-independent warm-path score contract; no physical wallet-performance migration is introduced. The existing future `wallet_performance_snapshots` table remains the persistence target for a later roadmap task, and scoring does not write business state automatically.
- Sprint 4.3 remains a provider-independent warm-path confluence contract; no physical smart-money migration is introduced. The logical `smart_money_confluence_snapshots` target remains for a later persistence task, and event/score analysis does not write business state automatically.
- Sprint 5.1 remains a provider-independent warm-path social contract; no physical social migration is introduced. The existing `social_authors`/`social_mentions` targets remain for a later persistence task, and social normalization does not write business state automatically.
- Sprint 5.2 remains a provider-independent warm-path social intelligence contract; no physical migration is introduced. Logical `author_trust_snapshots` and `social_velocity_snapshots` targets remain for a later persistence task, and trust/velocity scoring does not write business state automatically.
- The Sprint 5.3 keyless narrative slice remains a provider-independent warm-path advisory contract; no physical migration is introduced. Narrative evidence/snapshot persistence remains a later roadmap task, and narrative analysis does not write business state or authorize execution automatically.
- The E5.4 caller-performance slice remains a provider-independent warm-path advisory contract; no physical migration is introduced. `SocialCall`, outcomes and author snapshots are replay/application records only, and the analyzer does not write business state, mutate registry tiers or authorize execution.
- The E2.5 rich protocol slice remains a provider-independent warm-path observation contract; no physical protocol migration is introduced. Schema-v2 `protocol.lifecycle` observations and stream results are replay/application records only, and lifecycle evidence does not write business state, clear risk, transition candidates or authorize execution.
- The E6.1 strategy slice is a provider-independent warm-path score contract. It projects to the existing score snapshot identity fields but does not wire automatic candidate recomputation or decision transitions; strategy output remains advisory and cannot authorize execution.
- The E6.2 external-wallet slice remains a provider-independent warm-path corroboration contract; no physical migration is introduced. Labels/signals are replay/application records only, do not mutate internal wallet or risk records, and cannot authorize execution. Live provider acceptance is isolated behind the key-safe doctor.
- Core Sprint 6.1 adds the provider-independent feature-window aggregator and persistence repository over the existing `feature_snapshots` table; no physical migration is introduced. Sprint 6.2 supplies repository-backed AlphaScore recomputation over those feature/risk records, and Sprint 6.3 supplies the provider-independent decision/timeline seams; the API/worker composition still does not automatically mutate business state, and all snapshots/decisions remain advisory/non-executable.
- Core Sprint 6.2 adds no physical migration: existing `risk_assessments` and `score_snapshots` tables, including migration `0003_score_strategy_identity`, contain the required persistence contract. The API/worker composition exposes the seam but does not automatically mutate business state.
- E6.2 documentation reconciliation updated `ROADMAP.md` (Phase 6 seam note), `ROADMAP_RESEARCH_EXTENSIONS.md` (E6.2 completion), `DATA_MODEL.md` (external label/signal and reconciliation snapshot contract), `PROVIDERS.md` (fixture adapter/doctor seam), `SCORING_AND_RISK.md` (cross-validation rules), `SECURITY.md` (external evidence boundary) and `.env.example`/`Makefile` (safe doctor configuration); no unsafe live-provider behavior was introduced.
- Sprint 6.2 documentation reconciliation updated `ROADMAP.md`, `DATA_MODEL.md`, `ARCHITECTURE.md`, `PROVIDERS.md`, `SCORING_AND_RISK.md`, `SECURITY.md`, `TESTING.md` and `STATUS.md`; no migration or unsafe execution behavior was introduced.
- Sprint 6.3 adds no physical migration: existing candidate/state-transition persistence is sufficient, and `CandidateRepository` now rehydrates multi-transition history from the discovery boundary before checking final denormalized state. Decision event/outbox writes remain caller-owned.
- Sprint 7.1 adds no physical migration: the existing `alerts` table and leased `outbox` contract are sufficient. `AlertRepository` preserves typed alert state and dedupe identity; notification claims are filtered by `side_effect_kind=notification`, and provider delivery remains downstream of advisory decisions.
- Sprint 9.1 and Sprint 9.2 use migration `0006_paper_execution` and its
  append-oriented paper ledger/exit timeline; no additional schema change was
  required for Sprint 9.3.
- Sprint 9.3 reads the existing `positions`/`market_observations` records and
  persisted domain-event timeline through provider-independent projections; it
  does not create a second position store or mutate business state. Observed
  marks retain provider/source/parser and occurred/observed/ingested timestamps,
  while derived PnL is withheld for missing, non-fresh, invalid, conflicted or
  future marks.

## Git state

- Intended branch: `main`.
- Sprint 9.3 focused verification: `./.venv/bin/pytest tests/contract/test_phase7_sprint7_2.py tests/contract/test_phase9_sprint9_3.py tests/unit/test_position_read.py tests/unit/test_alert_pipeline.py tests/unit/test_read_persistence.py -q` passes `24 tests`; position projections, persisted reason codes, GET-only routes, future-mark exclusion, exit-alert filtering and browser-boundary contracts pass.
- Sprint 9.3 Postgres verification: with the isolated local database at migration `0006_paper_execution`, `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://... ./.venv/bin/pytest tests/integration/test_position_read_postgres.py -q` passes `1 test`; persisted position/observation/exit projections round-trip and the `as_of` boundary excludes future marks.
- Sprint 9.3 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`75 source files`), `566 passed, 10 skipped`, branch-aware coverage (`78%`), frontend lint/typecheck/Vitest (`13 files / 37 tests`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`.
- Sprint 9.3 frontend/runtime verification: `make frontend-build` exits `0` and exposes `/positions` alongside the existing operator routes; `make doctor` exits `0` with all four protected modes unchanged. `make telegram-doctor` exits `2` as expected with `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, no credential values and no live call.
- Sprint 9.3 safety acceptance: `PASS` for observed-versus-derived position data, event-time/no-lookahead marks, GET-only/server-rendered read boundaries, advisory exit notifications, allow-listed alert payloads and permanent absence of signing, submission or execution authority. Live read-only market-data and Telegram acceptance remain `BLOCKED_EXTERNAL`.
- Latest pushed Sprint 9.2 checkpoint: `312b642` (`feat: complete Phase 9.2 exit intelligence`).
- Latest pushed Sprint 9.3 checkpoint: `63fbbe9` (`feat: complete Phase 9.3 position dashboard`); this checkpoint includes the keyless implementation, contracts, verification evidence and reconciled roadmap documentation.
- Latest pushed Sprint 2.2 checkpoint: `039bb06` (`docs: synchronize sprint 2.2 status`), including the Helius implementation, smoke/runtime checks and completion documentation.
- Latest pushed Sprint 2.3 implementation checkpoints: `d1bb83a` (adapter), `337e60d` (stream fallback), `38cb4de` (reconciliation), `f804011` (fixtures/contracts) and `68c96ed` (doctor).
- Latest pushed Sprint 2.3 gate/status documentation checkpoint: `2233125` (`docs: complete Sprint 2.3 Birdeye checkpoint`); this status synchronization follows it.
- Latest pushed Sprint 2.4 checkpoints: `84eee38` (plan), `0261ac4` (protocol adapters and canonical identities), `680d009` (manual API), `6b2cab0` (protocol fixtures/contracts), and `ea5ae4e` (gate/documentation); this status synchronization follows the gate checkpoint.
- Latest pushed Gate P2 keyless contract checkpoint: `573bf6c` (`test: add Phase 2 gate composition`); latest pushed Gate P2 status checkpoint: `b774c54` (`docs: record Phase 2 gate status`); this status synchronization follows it.
- Latest pushed Sprint 3.1 plan checkpoint: `4ad685a` (`docs: refine Sprint 3.1 implementation plan`).
- Latest pushed Sprint 3.1 evaluator checkpoint: `6ec3ed7` (`feat: add fail-closed token security evaluation`).
- Latest pushed Sprint 3.1 RugCheck provider checkpoint: `8d13136` (`feat: add RugCheck risk provider seam`).
- Latest pushed Sprint 3.1 doctor/composition checkpoint: `e36c8e3` (`test: add RugCheck doctor and token security contracts`). The final Sprint 3.1 documentation/status synchronization follows this checkpoint.
- Latest pushed Sprint 3.1 documentation checkpoint: `3844c8b` (`docs: complete Sprint 3.1 token security checkpoint`). The status synchronization follows this checkpoint.
- Latest pushed Sprint 3.2 application checkpoint: `a355dd4` (`feat: add bounded holder concentration graph analysis`).
- Latest pushed Sprint 3.2 clustering correction: `5345f4a` (`fix: classify holder funding clusters`).
- Latest pushed Sprint 3.2 fixture/contract checkpoint: `f7590d0` (`test: add holder graph replay contracts`).
- Latest pushed Sprint 3.2 documentation checkpoint: `048d811` (`docs: complete Sprint 3.2 holder graph checkpoint`); this status synchronization records the exact keyless gate evidence above.
- Latest pushed Sprint 3.3 plan checkpoint: `659ebff` (`docs: plan Sprint 3.3 flow analysis`).
- Latest pushed Sprint 3.3 application checkpoint: `3957adb` (`feat: add liquidity and organic flow analysis`).
- Latest pushed Sprint 3.3 fixture/contract checkpoint: `95901ca` (`test: add organic flow replay contracts`).
- Latest pushed Sprint 3.3 documentation checkpoint: `609ca0e` (`docs: complete Sprint 3.3 flow analysis checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.1 plan checkpoint: `3126bd5` (`docs: plan Sprint 4.1 wallet tracking`); plan interface correction checkpoint: `6425f80` (`docs: clarify Sprint 4.1 plan interface`).
- Latest pushed Sprint 4.1 application checkpoint: `28bb0f7` (`feat: add conservative wallet tracking`).
- Latest pushed Sprint 4.1 fixture/contract checkpoint: `478cfe1` (`test: add wallet tracking replay contracts`).
- Latest pushed Sprint 4.1 documentation checkpoint: `51013a1` (`docs: complete Sprint 4.1 wallet tracking checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.2 plan checkpoint: `7172772` (`docs: plan Sprint 4.2 smart wallet score`).
- Latest pushed Sprint 4.2 application checkpoint: `8f644cb` (`feat: add versioned smart wallet scoring`).
- Latest pushed Sprint 4.2 fixture/contract checkpoint: `d281496` (`test: add smart wallet score replay contracts`).
- Latest pushed Sprint 4.2 documentation checkpoint: `79583d9` (`docs: complete Sprint 4.2 smart wallet score checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 4.3 plan checkpoint: `1393cca` (`docs: plan Sprint 4.3 confluence`).
- Latest pushed Sprint 4.3 application checkpoint: `b56b543` (`feat: add smart money confluence analysis`).
- Latest pushed Sprint 4.3 fixture/contract checkpoint: `dd8c367` (`test: add confluence replay contracts`).
- Latest pushed Sprint 4.3 documentation checkpoint: `f76b533` (`docs: complete Sprint 4.3 confluence checkpoint`); this status synchronization records the exact keyless gate and Compose runtime evidence above.
- Latest pushed Sprint 5.1 plan checkpoint: `dc30b36` (`docs: plan Sprint 5.1 social provider`).
- Latest pushed Sprint 5.1 application checkpoint: `1809c69` (`feat: add social provider read seam`).
- Latest pushed Sprint 5.1 fixture/contract checkpoint: `5fb3542` (`test: add social provider replay contracts`).
- Latest pushed Sprint 5.1 documentation checkpoint: `09efaa7` (`docs: complete Sprint 5.1 social checkpoint`).
- Latest pushed Sprint 5.1 status synchronization: `bb4d8e2` (`docs: synchronize Sprint 5.1 status`).
- Latest pushed Sprint 5.2 plan checkpoint: `1f01b07` (`docs: plan Sprint 5.2 social intelligence`).
- Latest pushed Sprint 5.2 application checkpoint: `13b4f01` (`feat: add social trust and velocity scoring`).
- Latest pushed Sprint 5.2 fixture/contract checkpoint: `92b62f0` (`test: add social intelligence replay contracts`).
- Latest pushed Sprint 5.2 deterministic test correction: `17818ed` (`test: freeze Helius schema test clock`).
- Latest pushed Sprint 5.2 documentation checkpoint: `f39d100` (`docs: complete Sprint 5.2 social intelligence checkpoint`).
- Sprint 5.2 status synchronization is reflected in the completed evidence above.
- Latest pushed Sprint 5.3 plan checkpoint: `2c21b4b` (`docs: plan Sprint 5.3 narrative LLM`).
- Latest pushed Sprint 5.3 keyless implementation/fixture/doctor checkpoint: `2bf7338` (`feat: add narrative analysis safety seam`).
- Sprint 5.3 stop-state record: `738b28b` (`docs: synchronize Sprint 5.3 stop state`).
- Latest pushed research-docs checkpoints: `abefc21` (research reuse registry), `36be4dd` (architecture extensions), `22ebc96` (research extension roadmap), `19214bb` (Codex backlog instructions).
- Latest research extension E5.4 plan checkpoint: `6e6e012` (`docs: plan extension E5.4 call performance`).
- Latest pushed E5.4 implementation/fixture/contract/documentation checkpoint: `f8aa710` (`feat: add historical caller performance evidence`); full verification and Compose runtime evidence are recorded above.
- Latest pushed E2.5 implementation/fixture/contract/documentation checkpoint: `a06ae95` (`feat: add rich protocol lifecycle events`); full verification and Compose runtime evidence are recorded above.
- Latest pushed E6.0 implementation/fixture/contract checkpoint: `8ae2391` (`feat: add launch correlation micro-features`).
- E6.0 verification: focused correlation unit/contract/Compose smoke `31 passed`; full backend test `301 passed, 3 skipped`, branch-aware coverage `79%`; `make lint`, `make typecheck`, `make secret-scan`, migration parity (head `0002_outbox_processing`, 13 tables), Compose config, frontend lint/typecheck/test/build all pass. The frontend Makefile recipes now execute from `apps/web` so Next receives the correct project root.
- E6.0 replay evidence: seven named event-time windows `5s`, `15s`, `30s`, `60s`, `1m`, `5m`, `15m`; reverse-delivery equality; duplicate-source collapse; future evidence exclusion with `INVALID`/zero confidence; source/sample-limited social and wallet bursts; wash diagnostics; smart-money actor-cluster dedupe; creator/related-wallet pressure; and permanent `execution_eligible() == false`.
- Latest pushed E6.1 plan checkpoint: `4b1bce9` (`docs: plan E6.1 alpha strategy interface`).
- Latest pushed E6.1 implementation checkpoint: `81b0c74` (`feat: add versioned alpha strategy seam`), including the provider-free strategy module, replay fixtures/contracts, explicit score identity fields and migration.
- Latest pushed E6.1 documentation checkpoint: `b644646` (`docs: complete E6.1 alpha strategy checkpoint`); this status synchronization records the final gate, migration and rebuilt-runtime evidence above.
- E6.1 verification before documentation reconciliation: focused unit/contract/Compose smoke `34 passed`; backend `make test` `318 passed, 3 skipped`, branch-aware coverage `79%`; `make lint` and `make typecheck` pass with mypy reporting `52 source files`; migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- E6.1 replay evidence: `AlphaScoreV1Strategy` calculates exact 25%/20%/15%/15%/10%/10%/5% components, preserves risk penalties and hard blocks, lowers confidence for sparse evidence, fails closed for malformed/stale/unknown/config-conflicted inputs, clamps penalties, and keeps strategy switching explicit through `strategy_name`/`strategy_version`; all outputs have `execution_eligible() == false`.
- E6.1 full repository gate: `make verify` exit `0`; Ruff, mypy (`52 source files`), `318 passed, 3 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully.
- E6.1 rebuilt runtime: temporary Compose API/worker images rebuilt successfully; worker import probe `e6_1_worker_runtime_import_ok alpha-score-v1 alpha-score ... True True False False`, API probe `e6_1_api_runtime_import_ok 7 True True True True False False`, and `/health/live` plus `/health/ready` both returned HTTP `200` with Postgres/Redis reachable. Temporary host ports were `18000`/`25432`/`26379` because unrelated local projects occupy the default ports; no provider or live-money call was made.
- E6.1 migration runtime check: temporary Postgres completed `upgrade head`, `downgrade 0002_outbox_processing`, and `upgrade head` successfully, confirming the new strategy-identity revision is reversible and leaves the database at the current head.
- Latest pushed E6.2 plan checkpoint: `9a28469` (`docs: plan E6.2 external wallet intelligence`).
- Latest pushed E6.2 implementation checkpoint: `ca3ca18` (`feat: add external wallet intelligence seam`), including normalized contracts, fixture adapter, replay data, doctor, protected-mode configuration and tests.
- Latest pushed core Sprint 6.1 implementation checkpoint: `c3811ca` (`feat: add feature window snapshots`), including the provider-independent aggregator, replay fixture/contracts and feature-snapshot persistence seam.
- Latest pushed core Sprint 6.2 implementation checkpoint: `958b928` (`feat: wire AlphaScore recomputation`), including the provider-independent recomputation service, risk/score repositories and golden replay fixture/contracts.
- Latest pushed core Sprint 6.3 implementation checkpoint: `2a2ce56` (`feat: add decision state machine`), including the provider-independent DecisionEngine, EvidenceTimelineProjector, deterministic replay fixture/contracts, persistence rehydration correction and safe-mode/runtime contracts.
- Latest pushed Sprint 7.1 implementation checkpoint: `980e785` (`feat: add Telegram alert pipeline`), including provider-independent alert projection/rendering, alert persistence, notification outbox delivery, Telegram/fixture adapters, doctor tooling and keyless contracts.
- Latest pushed Sprint 7.2 plan checkpoint: `83ad277` (`docs: plan Sprint 7.2 read API`).
- Latest pushed Sprint 7.2 application contract checkpoint: `2db97d6` (`feat: define read API contracts`).
- Latest pushed Sprint 7.2 persistence checkpoint: `9e2f34b` (`feat: add persisted read query adapter`).
- Latest pushed Sprint 7.2 FastAPI checkpoint: `7515aca` (`feat: expose bounded read API`).
- Latest pushed Sprint 7.3 design checkpoint: `c770567` (`docs: design Sprint 7.3 auth control`).
- Latest pushed Sprint 7.3 plan checkpoint: `5975430` (`docs: plan Sprint 7.3 auth control`).
- Latest pushed Sprint 7.3 application checkpoint: `6b88714` (`feat: define control plane contracts`).
- Latest pushed Sprint 7.3 persistence checkpoint: `930595b` (`feat: persist control plane audit state`).
- Latest pushed Sprint 7.3 API checkpoint: `cc8c442` (`feat: add authenticated control API`).
- Latest pushed Sprint 8.1 design checkpoint: `69ef9c5` (`docs: design Sprint 8.1 dashboard shell`).
- Latest pushed Sprint 8.1 plan checkpoint: `391a01c` (`docs: plan Sprint 8.1 dashboard shell`).
- Latest pushed Sprint 8.1 status/realtime checkpoint: `0a7a00f` (`feat: add dashboard status and realtime seam`).
- Latest pushed Sprint 8.1 shell checkpoint: `9afffbc` (`feat: build responsive operator shell`).
- E6.2 focused verification: `.venv/bin/pytest tests/unit/test_external_wallet.py tests/contract/test_extension_e6_2_external_wallet.py tests/unit/test_external_wallet_doctor.py tests/smoke/test_compose_contract.py tests/unit/test_provider_contracts.py -q` — `38 passed`; immutable contracts, deterministic replay, fixture adapter, doctor, provider capability and protected-mode checks pass.
- E6.2 full repository gate: `make verify` exit `0`; Ruff, mypy (`54 source files`), `331 passed, 3 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- E6.2 provider doctor: `make external-wallet-doctor` exit `2` as expected; status is `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, only configuration presence and protected modes are reported, and no network call or credential output occurs.
- E6.2 rebuilt runtime: temporary Compose API/worker images rebuilt successfully; worker probe `e6_2_worker_runtime_import_ok external-wallet-v1 ... fixture.external_wallet True True False False`, API probe `e6_2_api_runtime_import_ok ExternalWalletTokenSignal ExternalWalletReconciliationSnapshot ... True True False False`, and `/health/live` plus `/health/ready` on port `18000` returned HTTP `200` with Postgres/Redis reachable. No external provider or live-money call was made.
- E6.2 keyless fixture/contract acceptance: `PASS` — deterministic external-wallet labels/signals replay in reverse delivery order; agreement, disagreement, stale evidence, graph clustering, token features, security corroboration, provider removal and permanent non-execution behavior pass without credentials or network calls.
- Sprint 6.1 focused verification: `39 passed` across feature-window, feature-persistence, persistence-contract, sprint-contract and Compose smoke tests; `make lint` and `make typecheck` pass with mypy reporting `55 source files`.
- Sprint 6.1 full repository gate: `make verify` exit `0`; Ruff, mypy (`55 source files`), `344 passed, 3 skipped`, branch-aware coverage `80%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- Sprint 6.1 Postgres/runtime verification: the opt-in `tests/integration/test_persistence_postgres.py` run passed `3 tests`; temporary Compose API/worker images rebuilt successfully, worker/API feature-window and repository import probes passed, and `/health/live` plus `/health/ready` on port `18000` returned HTTP `200` with Postgres/Redis reachable.
- Sprint 6.1 safe doctor state: `make doctor` exited `0` with all protected modes asserted; `make external-wallet-doctor` exited `2` as expected with `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, no network probe and no credential output.
- Sprint 6.1 replay acceptance: `PASS` — redacted synthetic feature-window evidence reproduces stable IDs, values, provenance, quality and config identity for exact `1m`/`5m`/`15m` windows independent of delivery order; future evidence fails closed as `INVALID` with zero confidence.
- Sprint 6.2 keyless AlphaScore acceptance: `PASS` — repository-backed recomputation delegates to the versioned strategy, preserves exact configurable weights, bounded penalties, hard-risk/UNKNOWN reasons, score/confidence/components and strategy/model/config identity, with stable reverse-replay output and no execution authority.
- Sprint 6.2 persistence acceptance: `PASS` — risk and score rows round-trip normalized penalties/components, reasons, freshness, references and strategy identity; equivalent IDs are idempotent and conflicting reuse raises `IdempotencyConflict`.
- Sprint 6.2 focused verification: `46 passed`; `make lint` and `make typecheck` pass with mypy reporting `56 source files`.
- Sprint 6.2 full repository gate: `make verify` exit `0`; Ruff, mypy (`56 source files`), `362 passed, 3 skipped`, branch-aware coverage `80%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- Sprint 6.2 Postgres/runtime verification: the opt-in `tests/integration/test_persistence_postgres.py` run passed `3 tests`; temporary Compose API/worker images rebuilt successfully, score/repository import probes passed, and `/health/live` plus `/health/ready` on port `18000` returned HTTP `200` with Postgres/Redis reachable.
- Sprint 6.3 focused verification: `tests/unit/test_decision_engine.py`, `tests/contract/test_phase6_sprint6_3.py`, persistence regressions and Compose contracts pass (`15` decision unit/contract tests, `29` combined decision/persistence tests and `23` Compose smoke tests); Ruff and mypy (`57 source files`) pass.
- Sprint 6.3 replay acceptance: `PASS` — the redacted decision fixture deterministically progresses `ENRICHING -> WATCH -> STRONG_SETUP -> ENTRY_READY` one step at a time; repeated replay produces identical transition/event IDs, while blocked/unknown/stale risk, low confidence, config mismatch, score freshness, hysteresis and cooldown tests remain fail-closed.
- Sprint 6.3 event/timeline acceptance: `PASS` — non-zero score deltas emit `AlphaScoreDelta`, worsening/initial unsafe risk emits `RiskEscalation`, and the timeline projection preserves separate event timestamps, provenance, quality, reason/evidence references, deterministic ordering and an `as_of` future boundary.
- Sprint 6.3 persistence acceptance: `PASS` — `DecisionEngine.decide_from_persistence` uses caller-owned application ports; the opt-in Postgres suite passes `3 tests` including stable decision transition persistence and multi-transition candidate rehydration.
- Sprint 6.3 full repository gate: `make verify` exit `0`; Ruff, mypy (`57 source files`), `378 passed, 3 skipped`, branch-aware coverage `80%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- Sprint 6.3 documentation reconciliation is included in the next pushed status checkpoint; no migration, provider dependency or execution behavior was introduced.
- Sprint 7.1 focused verification: `57 passed` across alert pipeline, Telegram provider/doctor, event-processing, persistence contract, worker and Compose smoke tests; Ruff and mypy (`59 source files`) pass.
- Sprint 7.1 Postgres verification: the opt-in `tests/integration/test_persistence_postgres.py` run passed `4 tests`, including alert round-trip, duplicate dedupe and persisted notification outbox delivery.
- Sprint 7.1 full repository gate: `make verify` exit `0`; Ruff, mypy (`59 source files`), `396 passed, 4 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- Sprint 7.1 doctor/runtime verification: `make doctor` and Compose config exited `0`; `make telegram-doctor` exited `2` as expected with `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, no credential output and no live call. Temporary Compose worker/API import probes passed and `/health/live` plus `/health/ready` on port `18000` returned HTTP `200` with Postgres/Redis reachable.
- Sprint 7.1 documentation reconciliation updates `ROADMAP.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `PROVIDERS.md`, `SECURITY.md`, `TESTING.md`, `STATUS.md` and the completed plan; no migration or unsafe execution behavior was introduced.
- Sprint 7.2 focused verification: route/API regression `29 passed`; application/persistence read unit tests `14 passed`; replay and route-boundary/Compose contracts `29 passed`; opt-in read-adapter Postgres test `1 passed`. Ruff and mypy (`62 source files`) pass.
- Sprint 7.2 full repository gate: `make verify` exit `0`; Ruff, mypy (`62 source files`), `426 passed, 5 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all completed successfully. Migration parity reports `{"heads": ["0003_score_strategy_identity"], "table_count": 13}`.
- Sprint 7.2 Postgres verification: the full opt-in `tests/integration` suite passed `5 tests` at the permitted local-network boundary; persisted candidate/token projections, latest score/risk explainability, timeline event families and cursor pagination passed with cleanup.
- Sprint 7.2 runtime/doctor verification: `make doctor` and Compose config remain expected-safe; `make telegram-doctor` remains `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING` without credentials. The read routes are included in the API image composition and preserve all four protected modes; no external provider or live-money call was made.
- Sprint 7.2 documentation reconciliation updates `ROADMAP.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `PROVIDERS.md`, `SECURITY.md`, `TESTING.md`, `STATUS.md` and the completed plan; no migration, secret, provider authority or execution behavior was introduced.
- Sprint 7.3 plan/design checkpoints: `5975430` (`docs: plan Sprint 7.3 auth control`) and `c770567` (`docs: design Sprint 7.3 auth control`).
- Sprint 7.3 focused verification: control contracts `15 passed`, health regression `9 passed`, control API `8 passed`, control/manual/read/health regression `32 passed`, and replay/route-boundary/Compose contracts `29 passed`; Ruff and mypy (`66 source files`) pass.
- Sprint 7.3 persistence verification: migration metadata reports `{"heads": ["0004_control_plane"], "table_count": 16}`; the full opt-in `tests/integration` suite passes `6 tests`; migration upgrade from `0003_score_strategy_identity`, downgrade to `0003_score_strategy_identity`, and upgrade back to head all pass.
- Sprint 7.3 full repository gate: `make verify` exits `0`; Ruff, mypy (`66 source files`), `454 passed, 6 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest, Compose config, secret scan and migration parity all complete successfully.
- Sprint 7.3 runtime verification: temporary Compose API/worker images rebuild successfully; API probe `sprint7_3_api_runtime_import_ok control-api-v1`, worker probe `sprint7_3_worker_runtime_import_ok control-api-v1 SqlAlchemyControlPlane`, and `/health/live` plus `/health/ready` return HTTP `200` with Postgres/Redis reachable. Without role credentials, `/v1/control/state` returns HTTP `503` with `control authentication is not configured`.
- Sprint 7.3 doctor verification: `make doctor` and repository Compose config exit `0`; `make telegram-doctor` exits `2` as expected with `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, configuration presence only, no credential output or live provider call. All four protected modes remain unchanged.
- Sprint 7.3 documentation reconciliation records versioned control config and the current startup-only consumer semantics; no hot reload, provider dependency, secret, signing path or execution authority was introduced.
- Sprint 8.1 focused frontend verification: `npm test -- --run src/app/page.test.tsx src/app/components/status-badges.test.tsx src/app/lib/realtime.test.ts src/app/components/theme-toggle.test.tsx` passes `12 tests`; `npm run lint`, `npm run typecheck` and `npm run build` all exit `0`. Next.js reports the root route as statically prerendered.
- Sprint 8.1 full repository gate: `make verify` exits `0`; Ruff, mypy (`66 source files`), `454 passed, 6 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest (`12 passed`), Compose config, secret scan and migration parity all complete successfully. Migration parity remains `{"heads": ["0004_control_plane"], "table_count": 16}`.
- Sprint 8.1 Compose web verification: the temporary local Compose web image rebuilds successfully; after normal Next startup, `GET http://127.0.0.1:13000/` returns HTTP `200` with a `22876`-byte response containing `MemeRadar`, `ANALYSIS ONLY`, `PAPER TRADING`, `LIVE DATA`, `ADVISORY OUTPUT` and `NO LIVE ORDERS`. The first immediate probe hit a startup reset and was not counted as a pass; the retry after readiness succeeded.
- Sprint 8.1 safety verification: the rendered page shows `STREAM DISABLED` when no public endpoint is configured, theme state changes only the local root attribute/storage key, realtime tests ignore message payloads, and no provider credential, API token, wallet material or execution authority was added to the browser.
- Sprint 8.2 focused frontend verification: the server read gateway, Radar, token-detail and page suites pass `12 tests`; `npm run lint`, `npm run typecheck` and `npm run build` all exit `0`. The build exposes only the root and dynamic token-detail routes; no client-side API fetch or credential bundle was introduced.
- Sprint 8.2 full repository gate: `make verify` completes successfully with Ruff, mypy (`66 source files`), `454 passed, 6 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest (`23 passed`), Compose config, secret scan and migration parity. Migration parity remains `{"heads": ["0004_control_plane"], "table_count": 16}`.
- Sprint 8.2 Compose/runtime verification: a temporary Compose copy with isolated host ports (`18000`, `25432`, `26379`, `13000`) rebuilt the web/API dependency successfully. `GET /` returned HTTP `200` (`25282` bytes) and contained `MemeRadar`, `ANALYSIS ONLY`, `PAPER TRADING`, `LIVE DATA`, `ADVISORY OUTPUT`, `NO LIVE ORDERS`, `STREAM DISABLED`, `RADAR` and the honest empty-catalog state. A known invalid token route returned HTTP `200` (`13520` bytes) with `INVALID TOKEN IDENTIFIER`, protected labels and no provider response body or credential value. No external provider call was made.
- Sprint 8.2 safety acceptance: `PASS` for server-only internal API routing, optional server-only viewer bearer handling, bounded parser rejection, explicit unavailable/invalid/empty/unknown states, API-order-preserving Radar/timeline projection, allow-listed charts, bounded provenance, raw-payload/secret non-rendering and permanent non-execution behavior. All four protected modes remain unchanged.
- Sprint 8.3 focused frontend verification: gateway and operator component suites pass `18 tests`; full frontend Vitest passes `12 files / 34 tests`; `npm run lint`, `npm run typecheck` and `npm run build` exit `0`. The build exposes `/`, `/audit`, `/providers`, `/settings`, `/wallets`, `/tokens/[tokenId]` and `/wallets/[address]`; no browser fetch or credential bundle was introduced.
- Sprint 8.3 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`66 source files`), `454 passed, 6 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest (`34 passed`), Compose config, secret scan and migration parity all complete successfully. Migration parity remains `{"heads": ["0004_control_plane"], "table_count": 16}`.
- Sprint 8.3 Compose/runtime verification: the isolated temporary Compose web image rebuilt successfully after adding the operator routes. `GET /` returned HTTP `200` (`25282` bytes); `/wallets` `200` (`23107` bytes), `/providers` `200` (`23077` bytes), `/settings` `200` (`27537` bytes), `/audit` `200` (`24928` bytes) and invalid `/wallets/not-a-wallet` `200` (`21487` bytes). Rendered output included protected mode/advisory labels, `NO WALLET CATALOG AVAILABLE`, `NO PROVIDER HEALTH EVIDENCE` and `INVALID READ RESPONSE`; settings showed `CONTROL STATE UNAVAILABLE`/`CONTROL CONFIG UNAVAILABLE` without configured role credentials. No external provider call was made.
- Gate P8 browser verification: `MEMERADAR_E2E_BASE_URL=http://127.0.0.1:13000 MEMERADAR_E2E_EXECUTABLE_PATH=/usr/bin/google-chrome npm run test:e2e` passes `3 tests` in `16.1s` against the rebuilt isolated Compose service. The suite checks protected labels/navigation, all operator intelligence routes, absence of forms and execute/sign/submit/save/mutate buttons, invalid wallet fail-closed output, and no credential/private-key text. The first host browser attempt was blocked by the environment's unsupported bundled Chromium; the successful run used the installed system Chrome without changing application behavior.
- Sprint 8.3 safety acceptance: `PASS` for server-only gateway/control reads, address/record validation, API-order-preserving projections, explicit missing/degraded/invalid states, allow-listed audit/config values, read-only settings and permanent non-execution behavior. All four protected modes remain unchanged. Live provider acceptance remains `BLOCKED_EXTERNAL`.
- E8.4 focused verification: `.venv/bin/pytest tests/unit/test_chain_domain.py tests/unit/test_stream_integrity.py tests/unit/test_protocol_registry.py tests/unit/test_stream_integrity_doctor.py tests/unit/test_feature_windows.py tests/contract/test_extension_e8_4_stream_integrity.py tests/unit/test_stream_persistence_contract.py tests/unit/test_migration_contract.py tests/unit/test_persistence_contract.py -q` passes `60 tests`; cursor/gap/recovery/duplicate/conflict/timeout/rate-limit/backpressure/commitment/revert, protocol identity, replay/no-lookahead, quality reduction, doctor, persistence and migration contracts pass.
- E8.4 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`70 source files`), `500 passed, 7 skipped`, branch-aware coverage `79%`, frontend lint/typecheck/Vitest (`34 passed`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0005_stream_integrity"], "table_count": 19}`.
- E8.4 replay/persistence verification: canonical live/backfill/replay decoding uses one decoder path; `ReplayManifest` filters evidence at its event-time boundary and pins parser/registry/schema/strategy/config identity. The opt-in Postgres stream state-store round trip passes `1 test` after upgrade to `0005_stream_integrity`; cursor/gap/verification/event provenance metadata rehydrate without provider access.
- E8.4 migration verification: `scripts/check_migrations.py` reports `{"heads": ["0005_stream_integrity"], "table_count": 19}`; temporary Postgres upgrade/downgrade/upgrade and stream persistence integration pass. `0005_stream_integrity` is reversible.
- E8.4 doctor/safety verification: `make stream-integrity-doctor` reports `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING` with `keyless_contracts: PASS` and no endpoint values; no live stream/RPC call was made. The four protected modes remain `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- E8.4 safety acceptance: `PASS` for provider-independent application/domain boundaries, full program-ID plus discriminator/tag routing, explicit unknown/unverified/conflict states, no silent backpressure drop, data-quality-only stream impact and permanent absence of signing/execution authority. Required protocol identities remain `TODO_VERIFY`/`SUPPORTED_NEEDS_REVERIFY` until authoritative corroboration is available; Rust/Yellowstone remains deferred until E11.1 measurement.
- Sprint 9.1 plan/design evidence: `docs/superpowers/plans/2026-08-31-phase-9-sprint-9-1-paper-execution.md` and `docs/superpowers/specs/2026-08-31-phase-9-sprint-9-1-paper-execution-design.md` define the provider-independent paper boundary, protected modes, append-only accounting and replay identity contract.
- Sprint 9.1 focused verification: `./.venv/bin/pytest tests/unit/test_paper_domain.py tests/unit/test_paper_execution.py tests/unit/test_paper_trading_doctor.py tests/contract/test_phase9_sprint9_1.py tests/unit/test_paper_persistence_contract.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q` passes `29 tests`; domain/application/persistence boundaries, Decimal sizing/fill arithmetic, lifecycle, idempotency, reconciliation, replay/no-lookahead and doctor contracts pass.
- Sprint 9.1 static verification: Ruff passes for the repository; mypy passes for `73 source files`; domain/application paper modules contain no SQLAlchemy, FastAPI, persistence or signing/submission dependency.
- Sprint 9.1 migration/persistence verification: `scripts/check_migrations.py` reports `{"heads": ["0006_paper_execution"], "table_count": 22}`; temporary Postgres downgrade to `0005_stream_integrity`, upgrade to `0006_paper_execution`, and `tests/integration/test_paper_persistence_postgres.py` pass `1 test` with restart/idempotency and cleanup.
- Sprint 9.1 full repository gate: `make verify` exits `0`; Ruff, mypy (`73 source files`), `521 passed, 8 skipped`, branch-aware coverage `78%`, frontend lint/typecheck/Vitest (`34 passed`), Compose config, secret scan and migration parity complete successfully.
- Sprint 9.1 doctor/safety verification: `make paper-trading-doctor` exits `2` as expected with `BLOCKED_EXTERNAL`/`CONFIGURATION_MISSING`, `paper_contracts: PASS`, `external_network: not_checked` and no endpoint/credential values. With redacted configured quote presence it remains `BLOCKED_EXTERNAL`/`LIVE_EXECUTION_DISABLED`; protected modes remain unchanged.
- Sprint 9.1 safety acceptance: `PASS` for normalized-quote-only input, deterministic adverse fee/slippage simulation, protected paper-only modes, append-only/idempotent cash/order/fill evidence, no-lookahead replay and permanent absence of signing or live-money authority. Live quote and live execution acceptance remain `BLOCKED_EXTERNAL`.
- Sprint 9.2 focused verification: `./.venv/bin/pytest tests/unit/test_exit_engine.py tests/unit/test_exit_persistence_contract.py tests/contract/test_phase9_sprint9_2.py tests/unit/test_persistence_contract.py tests/unit/test_migration_contract.py -q` passes `42 tests`; fixed SL/TP, trailing/break-even, distribution/creator/holder, independent distribution-cluster support, micro/macro flow, liquidity/quote, score/time, partial ladder, freshness/UNKNOWN, external-only corroboration, deterministic IDs, append-idempotent in-memory/SQL timeline, before/after evidence references, event-time replay and paper-boundary contracts are covered.
- Sprint 9.2 Postgres verification: with an isolated local Postgres database upgraded to migration `0006_paper_execution`, `MEMERADAR_TEST_DATABASE_URL=postgresql+asyncpg://... ./.venv/bin/pytest tests/integration/test_exit_persistence_postgres.py -q` passes `1 test`; duplicate append is idempotent, full evaluation evidence rehydrates and cleanup preserves the shared event log.
- Sprint 9.2 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`75 source files`), `555 passed, 9 skipped`, branch-aware coverage (`78%`), frontend lint/typecheck/Vitest (`34 passed`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`.
- Sprint 9.2 safety acceptance: `PASS` for provider/persistence/signing boundaries, immutable evidence-bearing recommendations, append-only timeline/idempotency, deterministic no-lookahead replay and permanent absence of execution authority. Live read-only market-data acceptance remains `BLOCKED_EXTERNAL`; the four protected modes remain unchanged.
- Sprint 10.1 focused verification: `./.venv/bin/pytest tests/unit/test_replay_harness.py tests/contract/test_phase10_sprint10_1.py -q` passes `11 tests`; dataset round-trip, partition validation, deterministic reverse-delivery replay, no-lookahead, future-only outcomes, malformed/secret-shaped input rejection, cohorts, CSV export, strategy comparison and protected modes pass.
- Sprint 10.1 static verification: Ruff passes for `apps packages tests scripts`; strict mypy passes for `76 source files`; the replay application module and scripts contain no provider SDK, HTTP, persistence, database, signer or transaction-submission dependency.
- Sprint 10.1 fixture verification: `make replay-dataset` exits `0` with dataset digest `sha256:9edddf7f5062e6fefe2ff2810acde6f0dfb1274cebfc306e3b9dd819ded66ad8`, artifact digest `sha256:31398a2d6f07c0648257e6a29384a4ec291cd2cd1ab71fa5e47ef115b331ec84`, one checkpoint, four events, two future events excluded and all six outcome horizons emitted. `scripts/replay_dataset.py --format csv` also exits `0`.
- Sprint 10.1 throughput verification: `make profile-replay PROFILE_ITERATIONS=25` exits `0`; the redacted fixture measured `4` events over `25` iterations at `238.736` events/second in the recorded run. Timing is diagnostic only; Rust/Yellowstone remains deferred until the Phase 11 latency benchmark demonstrates a material need.
- Sprint 10.1 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`76 source files`), `577 passed, 10 skipped`, branch-aware coverage (`78%`), frontend lint/typecheck/Vitest (`13 files / 37 tests`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`.
- Sprint 10.1 safety acceptance: `PASS` for provider-free normalized replay, pinned parser/registry/schema/strategy/config identities, future-only outcome labeling, redacted exports, advisory strategy output and permanent absence of signing/execution authority. Gate P9 live read-only market-data and Telegram acceptance remains `BLOCKED_EXTERNAL`; the four protected modes remain unchanged.
- Sprint 10.2 focused verification: `./.venv/bin/pytest tests/unit/test_backtesting.py tests/contract/test_phase10_sprint10_2.py -q` passes `10 tests`; target/stop/horizon exits, adverse fee/slippage, freshness and unknown-state rejection, safety evidence, deterministic segments/calibration, redacted policy input and protected modes pass.
- Sprint 10.2 static verification: Ruff passes for `apps packages tests scripts`; strict mypy passes for `77 source files`; backtesting and CLI code contains no provider SDK, HTTP, persistence, database, signer or transaction-submission dependency.
- Sprint 10.2 fixture verification: `make backtest-replay BACKTEST_OUTPUT=/tmp/memeradar-backtest-report.json` exits `0` with schema `research-backtest-v1`, artifact digest `sha256:46d67abeb9db82ffaa54fe1511b0a7724076cd8a0cbb5beeaa4ca81a911178dc`, one checkpoint, one explicitly rejected entry and zero trades/signals because the redacted fixture has no strategy snapshot; protected modes remain exact.
- Sprint 10.2 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`77 source files`), `587 passed, 10 skipped`, branch-aware coverage (`78%`), frontend lint/typecheck/Vitest (`13 files / 37 tests`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`.
- Sprint 10.2 safety acceptance: `PASS` for provider-free deterministic backtesting, pinned replay/policy/fill identities, future-only no-lookahead exits, explicit skip reasons and UNKNOWN handling, redacted artifacts, permanent absence of signing/execution authority and unchanged protected modes. Live market-data and Telegram acceptance remains `BLOCKED_EXTERNAL`.
- Sprint 10.3 focused verification: `./.venv/bin/pytest tests/unit/test_calibration.py tests/contract/test_phase10_sprint10_3.py -q` passes `7 tests`; UTC half-open partitions, validated candidate weights, feature ablation, train-only selection, shadow identity, deterministic report identity, attribution lift, external-label incremental value, bundle false-confluence and promotion blocking pass.
- Sprint 10.3 static verification: Ruff passes for `apps packages tests scripts`; strict mypy passes for `78 source files`; calibration module and CLI contain no provider SDK, HTTP, persistence, database, signer, transaction-submission or live-money dependency.
- Sprint 10.3 fixture verification: `make calibrate-score CALIBRATION_OUTPUT=/tmp/memeradar-calibration-report.json` exits `0` with schema `score-calibration-v1`, artifact digest `sha256:929d4516c2a1cd8ede17934179bbabc96d5b7e2db422a3234d7396f1f1947d0b`, selected shadow candidate `author-ablation`, explicit `BLOCKED_INSUFFICIENT_EVIDENCE`, empty train/validation/test checkpoint counts for the intentionally bounded fixture, and exact protected modes.
- Sprint 10.3 full repository quality gate: `make verify` exits `0`; Ruff, mypy (`78 source files`), `594 passed, 10 skipped`, branch-aware coverage (`78%`), frontend lint/typecheck/Vitest (`13 files / 37 tests`), Compose config, secret scan and migration parity all complete successfully. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`.
- Sprint 10.3 safety acceptance: `PASS` for provider-free time-split calibration, same replay/backtest evidence boundary, train-only candidate selection, redacted deterministic artifacts, explicit unknown/insufficient evidence, attribution-as-evidence-only and permanent absence of promotion, signing or execution authority. No production score config was changed or frozen; Gate P9 live market-data and Telegram acceptance remains `BLOCKED_EXTERNAL`.
- Sprint 11.1 focused verification: `./.venv/bin/pytest tests/contract/test_phase11_sprint11_1.py tests/unit/test_reliability.py tests/unit/test_provider_transport.py tests/unit/test_helius_stream.py tests/unit/test_birdeye_stream.py tests/unit/test_protocol_stream.py tests/unit/test_event_processing.py tests/unit/test_stream_integrity.py -q` passes `60 tests`; bounded histogram/percentile semantics, provider-labelled reconnect/fallback/duplicate/malformed/rate-limit/retry counters, outbox telemetry, stream backpressure and protected-mode contracts pass.
- Sprint 11.1 persistence verification: the opt-in `tests/integration/test_phase11_reliability_postgres.py` passes `1 test` against the local Postgres service; a pending outbox row survives disposal/reopening of the connection pool and is delivered once, then isolated fixture cleanup succeeds. The integration test is skipped when `MEMERADAR_TEST_DATABASE_URL` is absent.
- Sprint 11.1 static verification: Ruff passes for `apps packages tests scripts`; strict mypy passes for `79 source files`; reliability code remains provider/persistence/frontend-free and optional telemetry is best-effort at adapter boundaries.
- E11.1 benchmark verification: `./.venv/bin/python scripts/reliability_benchmark.py --iterations 16 --output /tmp/memeradar-reliability.json` exits `0` and emits `reliability-benchmark-v1` with all six required p50/p95/p99 histograms, provider-network/internal attribution, a bounded counter snapshot and `external_provider_acceptance: BLOCKED_EXTERNAL`; runtime timing is synthetic/keyless evidence and no production SLO is declared.
- Sprint 11.1 doctor/safety verification: `./.venv/bin/python scripts/reliability_doctor.py` reports `BLOCKED_EXTERNAL` with `keyless_contracts: PASS`, `external_network: not_run` and exact protected modes. `docs/RUNBOOKS/RELIABILITY.md` documents provider/queue/DB incidents, current no-partition/index posture and a non-destructive isolated `pg_dump`/`pg_restore` drill. No live provider, signing or execution path was added.
- Sprint 11.2 focused verification: `./.venv/bin/pytest tests/unit/test_observability.py tests/contract/test_phase11_sprint11_2.py tests/unit/test_health.py tests/unit/test_read_api.py tests/unit/test_read_api_routes.py -q` passes `41 tests`; provider normalization, SLO evidence requirements, state precedence, quota/cost pressure, alert projection, protected modes, GET-only API and unknown/unavailable behavior pass.
- Sprint 11.2 static verification: Ruff passes for `apps packages tests scripts`; strict mypy passes for `81 source files`; the operations application module remains provider SDK, persistence, HTTP, AlphaScore and execution free. Frontend lint/typecheck pass and Vitest passes `14 files / 41 tests`.
- Sprint 11.2 build/gate verification: `make verify` exits `0`; the full repository suite passes `617 tests, 11 skipped` with branch-aware coverage `78%`, frontend lint/typecheck/Vitest `14 files / 41 tests`, Compose config, secret scan and migration parity. Migration parity reports `{"heads": ["0006_paper_execution"], "table_count": 22}`. `make frontend-build` exits `0` and includes the static `/operations` route.
- Sprint 11.2 safety acceptance: `PASS` for explicit UNKNOWN/UNVERIFIED/DEGRADED/DOWN states, provider-network-only SLO evaluation, quota/cost and reliability alerts, neutral operational health, read-only API/dashboard boundaries and unchanged protected modes. Live provider/Telegram acceptance remains `BLOCKED_EXTERNAL`; no production SLO, signing or execution authority was introduced. `docs/RUNBOOKS/OPERATIONS.md` records safe response procedures without secret logging.
- Sprint 11.3 focused verification: `./.venv/bin/pytest tests/unit/test_security_review.py tests/contract/test_phase11_sprint11_3.py -q` passes `8 tests`; exact lock rejection, versioned/non-root image contracts, external-tool blocking, protected-mode fail-closed behavior, bearer/RBAC permission scoping and narrative prompt/output boundary checks pass.
- Sprint 11.3 security review verification: `make security-review` exits `0` with all six deterministic local checks `PASS`, schema `security-review-v1`, exact protected modes and `external_acceptance: BLOCKED_EXTERNAL`. `make security-review-external` exits `2` as expected because pip-audit and Trivy are unavailable and local npm registry access is blocked; no missing scan is reported as clean.
- Sprint 11.3 dependency verification: after npm identified the high-severity Playwright `<1.55.1` advisory, `@playwright/test`, `playwright` and `playwright-core` were pinned to `1.62.1`; escalated read-only `npm audit --json --audit-level=high` reports zero vulnerabilities. No `npm audit fix --force` or unreviewed installer was used.
- Sprint 11.3 container verification: `docker compose -f infra/compose/docker-compose.yml build api worker web` exits `0`; API/worker run as `memeradar` and web runs as non-root `node`, while existing commands and protected modes remain unchanged.
- Sprint 11.3 full repository quality gate: `make verify` exits `0`; Ruff, strict mypy (`81 source files`), `625 passed, 11 skipped`, branch-aware coverage `78%`, frontend lint/typecheck/Vitest (`14 files / 41 tests`), Compose config, secret scan, migration parity and keyless security review complete successfully. `make frontend-build` remains green after the dependency remediation.
- Sprint 11.3 safety acceptance: `PASS` for no secret exposure, exact dependency declarations, non-root image runtime, constant-time role authentication, explicit RBAC/session boundaries, sanitized untrusted LLM data, advisory-only narrative output, versioned threat model and unchanged protected modes. Gate P11 is `READY_FOR_PRODUCTION_ANALYSIS_ONLY` for keyless evidence; live provider, Telegram, pip-audit/Trivy and live-money acceptance remain `BLOCKED_EXTERNAL`. Phase 12 remains locked by explicit operator decision and safety policy.
- Cross-cutting hardening Task 1 verification: `./.venv/bin/pytest tests/contract/test_api_schema.py -q` passes `3 tests`; generated OpenAPI is reproducible, business routes are versioned under `/v1`, health probes remain operational endpoints, and mutation methods are explicitly allow-listed. `docs/API.md` records compatibility, authentication and safe-data rules.
- Cross-cutting hardening Task 2 verification: `./.venv/bin/pytest tests/unit/test_sbom.py -q` passes `2 tests`; `make sbom` exits `0` with `security-sbom-v1`, 581 deterministic components and digest `sha256:baffabf73a73ed3b5565e8caac547f505aab6f92f232f950bcb34efba1a20e95`. The Make/CI quality gates now run the exporter; no external scanner result is fabricated.
- Cross-cutting hardening Task 3 verification: `./.venv/bin/pytest tests/contract/test_cross_cutting_documents.py -q` passes `3 tests`; `data-handling-v1`, `privacy-provider-terms-v1` and ADR 0001/0002 preserve non-destructive retention, minimization, compliant-source rules, provider independence and protected paper-first execution. Legal, provider-contract and production retention approval remain `BLOCKED_EXTERNAL`.
- Cross-cutting hardening Task 4 verification: `./.venv/bin/pytest tests/property/test_invariants.py -q` passes `3 tests`; fixed-seed property-style cases exercise 128 score evaluations, lifecycle random walks and 64 unresolved-gap/resume cases without weakening existing unit/contract suites.
- Cross-cutting hardening Task 5 verification: `./.venv/bin/pytest tests/unit/test_provider_routing.py -q` passes `6 tests`; `ProviderHealthRouter` deterministically selects only fresh healthy candidates, preserves degraded/unknown/unavailable alternatives, fails closed on conflict and has no score or execution authority.
- Cross-cutting hardening final gate: `make verify` exits `0`; Ruff, strict mypy (`82 source files`), `642 passed, 11 skipped`, branch-aware coverage `78%`, frontend lint/typecheck/Vitest (`14 files / 41 tests`), Compose config, secret scan, migration parity, `security-review-v1` and `security-sbom-v1` all pass. `make frontend-build` exits `0` with the expected operator routes.
- Cross-cutting hardening external review: `make security-review-external` exits `2` with `container_scan`, `npm_audit` and `pip_audit` all `BLOCKED_EXTERNAL`; direct read-only npm audit evidence remains clean after the Playwright remediation, but no complete production vulnerability scan is claimed.
- Approved E11.9 signal-hardening checkpoint: `tests/unit/test_price_semantics.py`, paper-domain/paper-execution regressions and replay contracts pass (`26` focused tests; `42` combined correlation/feature/replay/paper/price tests). The provider-neutral price resolver distinguishes `EXECUTION_EFFECTIVE`, `EXECUTION_QUOTE`, `MARKET_REFERENCE` and `UNKNOWN`, preserves provenance/freshness, rejects non-positive values, treats future data as `INVALID`, and never uses a generic execution-only trade price as a replay market baseline. `PaperFillModel` remains deterministic and paper-only; fill accounting/PnL continues to use the effective execution amount, while paper fills and wallet activities expose explicit execution/effective aliases and optional independent market marks. `make typecheck` passes. Protected modes remain `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`; no provider adapter, signing or live-money capability was added.
- E11.4–E11.8 implementation checkpoint: `uv run pytest tests/unit/test_signal_hardening.py tests/contract/test_extension_e11_signal_hardening.py -q` passes `26 tests` after mixed stale-critical-evidence, missing-liquidity and policy-controlled wash-volume regressions. The provider-independent analyzer now emits sustained SURGE/REVIVAL evidence only with event-time multi-sample market movement, actual buy tape, quote volume, buyer and liquidity evidence; economic move funding preserves quote units, applies configured wash adjustment and validates liquidity; deployer self-activity and transfer deltas, bounded first-N launch sniper/bundle footprints with actor-cluster deduplication and explicit external-label conflict, and token-versus-LP lock/vesting/unlock snapshots with schedules/cancelability are explicit. Missing, stale, conflicted and future evidence remain explicit and confidence cannot be positive for non-fresh critical inputs; every snapshot is advisory with `execution_eligible() == false`.
- E11.4–E11.9 integration checkpoint: `uv run pytest tests/unit/test_decision_engine.py tests/unit/test_exit_engine.py tests/unit/test_calibration.py tests/unit/test_replay_harness.py tests/contract/test_extension_e6_0_correlation.py tests/contract/test_phase6_sprint6_1.py -q` passes `66 tests`; the E11.9 price/replay regression set passes `30 tests`. Hardening snapshots are typed correlation values, projected into existing market/momentum/on-chain feature diagnostics and OrganicFlow validation, timeline and exit evidence, and built by replay from the same normalized event boundary. Replay manifests pin `signal_hardening_version`; calibration preserves the identity; no new AlphaScore component or execution path was added. Repository Ruff and mypy pass (`84 source files`).
- E11.4–E11.9 full quality gate: `make verify` exits `0`; backend passes `678 tests, 11 skipped` with `79%` branch-aware coverage, frontend lint/typecheck/Vitest passes (`14 files / 41 tests`), Compose config, tracked-file secret scan, migration parity (`0006_paper_execution`, `22` tables), `security-review-v1` (`PASS`) and deterministic SBOM (`581` components, existing digest) pass. `make frontend-build` exits `0` with the expected operator routes. The completed checkpoint is pushed as `2d6a811`; local `HEAD` and `origin/main` are synchronized and the worktree is clean.
- Current E11.4–E11.9 state: `DONE` for keyless implementation and verification. Live market/stream/RPC, Telegram, external vulnerability scans and all live-money acceptance remain `BLOCKED_EXTERNAL`; E11.2 remains conditional, and Phase 12 remains locked.

## Next task

Maintain the completed E11.4–E11.9 hardening checkpoint. Do not implement or
enable manual-live execution without the explicit operator decision and P9-P11
acceptance evidence required by `docs/ROADMAP.md`; preserve
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, and
`AUTO_EXECUTION=false`. E11.2 Rust/Yellowstone remains conditional on measured
need and is not started; Phase 12 remains locked.
