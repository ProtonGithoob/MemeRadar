# AGENTS.md — Codex Autonomous Execution Contract

This repository is designed for autonomous implementation by Codex.

## Operator authorization and no-prompt policy

The repository owner explicitly authorizes Codex to execute the entire currently feasible MemeRadar roadmap without asking for routine confirmation between commands or tasks.

Treat ordinary implementation work as pre-approved. Do **not** stop to ask questions such as “Would you like to run this command?” when the command is part of normal repository work and the execution environment permits it.

The following classes of work are pre-authorized for the duration of the project:

- reading any repository file or directory with commands such as `cat`, `sed`, `head`, `tail`, `grep`, `rg`, `find`, `ls`, `tree`, `git show`, `git diff`, and equivalents;
- inspecting source code, specifications, logs, configuration, environment metadata, git history/status, generated artifacts, schemas, migrations, and tests;
- creating, editing, moving, or deleting project files when required by the accepted roadmap;
- installing normal project dependencies and toolchains required by this repository;
- creating local virtual environments, package caches, build directories, containers, Docker volumes/networks, test databases, fixtures, and generated code;
- running formatters, linters, static analysis, type checks, unit/integration/e2e tests, coverage, builds, migrations, seeds, replay jobs, benchmarks, doctor checks, security checks, and bounded local smoke tests;
- starting/stopping/restarting project-local development services, Docker Compose stacks, workers, schedulers, APIs, databases, caches, and frontends;
- using authenticated development/provider APIs when credentials already exist and the action is read-only, analysis-only, paper-trading, or otherwise explicitly permitted by the repository safety mode;
- git add/commit/fetch/pull/rebase/merge/push operations required to keep the intended branch synchronized, provided unrelated user work is preserved and shared history is not force-pushed;
- resolving implementation details autonomously when the specification already defines intent and safety boundaries.

When a tool or shell UI offers an option equivalent to “Yes, and don't ask again for commands that start with …”, prefer the persistent approval option for safe recurring command families when available rather than requesting one-off approval repeatedly.

Do not ask the operator to approve commands merely because they read large files, access the local filesystem, run tests, build the project, inspect git state, or modify files required by the roadmap.

This authorization does **not** override the execution host's non-bypassable security controls. If the Codex product/runtime itself enforces an approval dialog that repository instructions cannot suppress, select/use the broadest safe persistent approval already available in that UI; otherwise continue immediately after the enforced boundary is cleared.

### Actions that remain intentionally protected

Do not infer authorization for actions outside the repository's safety policy. In particular:

- never expose, print, commit, transmit, rotate, delete, or otherwise mishandle secrets, wallet private keys, seed phrases, API tokens, session cookies, or credentials;
- never enable live-money trading merely to progress the roadmap;
- never transfer funds, sign arbitrary wallet transactions, change live execution permissions, or bypass trading/risk controls unless an explicit future operator instruction and the repository acceptance gates both authorize it;
- never force-push shared history, intentionally destroy unrelated user data, wipe arbitrary host directories, weaken host security, or disable security controls to avoid an approval boundary;
- never fabricate provider success when credentials/network/provider access are unavailable.

A genuine external or protected blocker must be documented and isolated. Continue every independent task instead of stopping the whole project to ask the user what to do.

## Mandatory startup sequence

Before changing code, read in order:

1. `README.md`
2. `docs/MASTER_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/ROADMAP.md`
5. `docs/ROADMAP_RESEARCH_EXTENSIONS.md`
6. `docs/RESEARCH_REUSE_REGISTRY.md`
7. `docs/STREAM_RELIABILITY_PROTOCOL_VERIFICATION.md`
8. `docs/DATA_MODEL.md`
9. `docs/SCORING_AND_RISK.md`
10. `docs/PROVIDERS.md`
11. `docs/SECURITY.md`
12. `docs/TESTING.md`
13. `docs/STATUS.md`

Then inspect the actual repository and environment. Repository truth overrides assumptions.

## Roadmap precedence and extension execution

- `docs/ROADMAP.md` remains the core product roadmap.
- `docs/ROADMAP_RESEARCH_EXTENSIONS.md` is an accepted supplementary executable backlog derived from later repository/protocol research.
- `docs/STREAM_RELIABILITY_PROTOCOL_VERIFICATION.md` is an accepted Phase-8-post-gate reliability extension derived from Solana stream/indexer research. It must not interrupt active Phase 8 UI work; execute it after Gate P8 and before Phase 9 unless actual repository state has already advanced, in which case insert it at the next safe backend checkpoint before relying on real-time paper-trading evidence.
- Completed core tasks must not be restarted or rewritten merely to fit a new idea.
- Finish the exact current task from `docs/STATUS.md` first, then execute research extensions at the insertion points documented in the accepted extension specifications.
- `docs/RESEARCH_REUSE_REGISTRY.md` explains the upstream pattern and licensing constraints; it is a reference registry, not permission to copy restricted code.
- When a researched pattern conflicts with a safety, deterministic-scoring, provider-independence or no-live-money invariant, the invariant wins.
- Low-latency/Rust/Yellowstone work is conditional on measured need and must not distract from unfinished core intelligence, replay or safety work. Stream integrity, gap recovery and protocol verification contracts must be implemented provider-independently before any optional Rust extraction.

## Autonomous working rules

- Continue from `docs/STATUS.md`; do not restart completed work.
- Do not ask routine implementation questions when the specification already resolves them.
- Do not pause after each command, file, test, sprint, or phase for user confirmation. Continue automatically to the next unblocked task.
- Choose technically sound defaults when a minor implementation detail is unspecified and document the decision.
- Never invent external-provider success. If credentials/network/provider access are absent, use fakes/fixtures and mark live verification as blocked.
- Do not enable live-money trading merely because code exists.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` until an explicit roadmap acceptance gate changes them.
- Never commit API keys, wallet private keys, seed phrases, Telegram tokens, cookies, session tokens or personal access tokens.
- Do not weaken tests, risk gates, auth, secret handling or execution controls to make a check pass.
- Prefer small coherent commits. Push meaningful checkpoints when GitHub credentials/network are available.
- Update `docs/STATUS.md` after every completed sprint or material blocker.
- Preserve provider independence in domain/application code.
- All externally sourced events must carry provenance, timestamps and freshness state.
- All decisions must carry reason codes and enough inputs for replay/explanation.
- Third-party wallet labels, KOL signals, GMGN-like risk/market signals and protocol-derived classifications are evidence only; they do not become execution authority.
- Do not directly copy code from upstream repositories until license compatibility is explicitly verified. When license is unclear/restrictive, independently implement the documented behavior/pattern.
- Solana protocol routing must use verified `(program_id, discriminator/tag)` identity, never discriminator-only matching.
- Live, replay and backfill chain data must converge through the same canonical decoder/normalizer path.
- An unresolved stream gap or unverified decoder identity must reduce data quality/freshness fail-closed; it must never increase AlphaScore.

## Implementation discipline

For each task:

1. Confirm current task and acceptance criteria from `docs/ROADMAP.md` and, when applicable, accepted research-extension specifications.
2. Inspect related existing code/tests before editing.
3. Add or update tests first where practical.
4. Implement the minimum coherent change.
5. Run focused checks.
6. Run the phase-level quality gates before marking a sprint complete.
7. Update documentation if behavior/contracts changed.
8. Update `docs/STATUS.md` with evidence.
9. Commit and push if available.
10. Continue to the next unblocked task without waiting for user confirmation.

## Architecture invariants

- Domain logic must not import provider SDKs, FastAPI, SQLAlchemy or frontend code.
- Provider adapters implement application-facing ports.
- Persistence is behind repositories/unit-of-work abstractions.
- Raw external payloads may be retained for audit/replay but domain logic operates on normalized models.
- Queue/event semantics must be idempotent; duplicates are expected.
- Event timestamps distinguish `occurred_at`, `observed_at` and `ingested_at`.
- Critical risk evidence has TTL/freshness semantics.
- Missing critical evidence is not equivalent to safe evidence.
- LLM narrative output is advisory and can never override a deterministic hard gate.
- External KOL/smart-money labels are corroborating evidence; internal wallet scoring/graph independence remains authoritative for MemeRadar's own component calculations.
- A social-only, wallet-only, provider-only or launch-event-only burst cannot independently authorize `ENTRY_READY`.
- Real execution uses a separate permission boundary from analysis/paper modes.
- Optional low-latency sidecars may ingest/decode only; they cannot score risk, change modes, sign or authorize trades.
- Chain backfill/recovery must use the same decoder registry and normalized event contracts as live ingestion.
- Durable chain progress must not advance past an unresolved gap as if data were contiguous.
- Pre-confirmation/processed chain evidence must retain commitment/finality state and may not silently become finalized truth.

## Definition of Done

A task is done only when:

- implementation exists;
- relevant automated tests pass;
- lint/type checks pass for touched areas;
- error/timeout/retry behavior is covered where relevant;
- telemetry is adequate for operational diagnosis;
- docs are reconciled;
- `docs/STATUS.md` records evidence and remaining blockers;
- no secret or unsafe live default was introduced.

For research-extension tasks, Definition of Done also requires:

- upstream license/reuse decision documented when relevant;
- fixtures/replay demonstrate deterministic behavior;
- no-lookahead tests where historical/rolling windows are involved;
- third-party disagreement/UNKNOWN behavior tested;
- feature/strategy/parser version and config hash persisted where specified;
- for stream-integrity work, synthetic gap detection, recovery, same-decoder replay equivalence and verification tests pass;
- protocol identity entries used for authoritative routing are independently verified or explicitly remain `TODO_VERIFY`.

## Blockers

If a task is blocked by external access:

- finish all keyless/local work;
- implement the seam and contract tests;
- add a provider doctor/check command;
- document exact required credential/access and expected success evidence;
- mark only the external acceptance item blocked;
- continue with other independent work.

Do not stop merely because one provider, credential, rate limit, paid feature, Apple/Android toolchain, optional service, or external acceptance test is unavailable. Continue all independent work to completion.

## Git behavior

- Treat `main` as source of truth unless repository policy says otherwise.
- Never force-push shared history.
- Never discard unrelated user changes.
- Before final handoff run `git status`, compare local HEAD/origin when possible, and document sync state.
