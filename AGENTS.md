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
5. `docs/DATA_MODEL.md`
6. `docs/SCORING_AND_RISK.md`
7. `docs/PROVIDERS.md`
8. `docs/SECURITY.md`
9. `docs/TESTING.md`
10. `docs/STATUS.md`

Then inspect the actual repository and environment. Repository truth overrides assumptions.

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

## Implementation discipline

For each task:

1. Confirm current task and acceptance criteria from `docs/ROADMAP.md`.
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
- Real execution uses a separate permission boundary from analysis/paper modes.

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
