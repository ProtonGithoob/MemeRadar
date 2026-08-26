# AGENTS.md — Codex Autonomous Execution Contract

This repository is designed for autonomous implementation by Codex.

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

## Git behavior

- Treat `main` as source of truth unless repository policy says otherwise.
- Never force-push shared history.
- Never discard unrelated user changes.
- Before final handoff run `git status`, compare local HEAD/origin when possible, and document sync state.
