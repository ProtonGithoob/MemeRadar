# Plan: Frontend and Early Alpha presentation hardening

> **Execution note:** The user supplied the design constraints and explicit
> implementation authorization. Execute this plan in the current `main`
> worktree; do not create a new feature branch or ask for routine approval.

## 1. Lock PR #3 behavior with failing contracts

1. Add/replace `tests/unit/test_early_alpha_alert.py` with fixtures for the
   five states, explicit risk conflict, real prior snapshots, UNKNOWN values,
   cohort wording, bounded/secret-safe output, and ordinary `AlertRenderer`
   parity. Run the file and observe the missing state-machine/snapshot behavior.
2. Add alert-pipeline tests for explicit transitions, same-state dedupe,
   transport retry identity, persisted-state restart behavior, follow-up
   correlation, and telemetry names. Run those focused tests and observe
   failures before implementation.

## 2. Implement one canonical Early Alpha projection and delivery path

1. Add `EARLY_ALPHA` to the existing alert type and implement the smallest
   provider-independent projection/state module. Normalize only existing score,
   risk, lifecycle, market, wallet, holder, freshness, provenance, reason, and
   version fields; never compute AlphaScore or risk.
2. Correct the PR renderer to consume that projection, use `UNKNOWN`, render
   `previous → current` from persisted snapshots, label all multiple references
   `COHORT SIMILARITY`, and map confirmation/risk incompatibility to CONFLICT.
3. Teach `AlertEventProjector`/`AlertDeliveryService` to select the Early Alpha
   renderer only for Early Alpha payloads, use stable identity and evidence
   version in dedupe keys, retrieve the latest persisted alert snapshot, enforce
   the transition table, and persist bounded correlation/snapshot metadata.
4. Reuse `SqlAlchemyAlertStore`/`AlertRepository` for latest Early Alpha lookup;
   update the worker only to register the canonical event kinds and inject both
   renderers into the existing `AlertDeliveryService`.
5. Add best-effort allow-listed Early Alpha counters through existing telemetry.
   Re-run the focused Python tests and the ordinary alert regression tests.

## 3. Fix canonical backend/frontend read seams

1. Add stable provider metadata to provider health/operations views and use it
   for provider settings and chain aggregation; implement required DOWN →
   DEGRADED → UNKNOWN → all-explicit-healthy semantics.
2. Add graph `root_id`, policy metadata, observed facet metadata, and complete
   quality-state values through domain/read/API/TypeScript; make the graph use
   the explicit root and semantic relationship CSS classes.
3. Preserve UNKNOWN for operations counters, remove settings hard-coded runtime
   fields and unused legacy panel, validate raw number drafts before submit, and
   make search failures visible.
4. Reconcile token-detail lifecycle duplication, expose the already available
   opportunity evidence, and expand the parity manifest with the Telegram
   Early Alpha contract and documented omissions.
5. Add a dependency-free static CSS class regression script and focused frontend
   tests. Run focused Vitest/lint/typecheck/build checks.

## 4. Fresh gates and status handoff

1. Run Telegram-focused tests separately and record the exact count.
2. Run the full Python suite, frontend Vitest, lint/typecheck/build, browser
   matrix and authenticated settings flow when safe local credentials exist;
   list skips with reasons.
3. Run migrations, security, SBOM, diff check, and fresh `make verify`.
4. Inspect latest hosted Actions state by API, run id, HEAD SHA, job state, and
   executed-step count; never reuse the old documented run id.
5. Update `docs/STATUS.md` with PR state, transition model, parity result,
   exact evidence, blockers, real-data count, protected modes, classification,
   implementation/final SHA, and the next unfinished task. Commit and push
   meaningful checkpoints without force-pushing; verify `HEAD == origin/main`.
