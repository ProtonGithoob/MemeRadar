# Codex Handoff — Real Alpha Evidence & Production Readiness

First resume from the exact current repository state. Do not restart completed Alpha Caller tasks.

Read in order:

1. `AGENTS.md`
2. `docs/STATUS.md`
3. `docs/PRODUCTION_READINESS.md`
4. `docs/superpowers/specs/2026-09-07-real-alpha-production-readiness-design.md`
5. `docs/superpowers/plans/2026-09-07-real-alpha-production-readiness.md`
6. `docs/CODEX_ALPHA_CALLER_EXECUTION.md`
7. every canonical architecture/provider/security/testing/research document referenced by those files.

Mission: move MemeRadar from `SYNTHETIC_REDACTED / INSUFFICIENT_SAMPLES` into measurable real-data production readiness. Prioritize compliant X/Telegram historical/live ingestion, historical-real positive+negative datasets, winner-first reverse caller discovery, executable event-time outcome reconstruction, durable live-shadow collection, real-data ablation, provider reliability, observability, backup/restore, security, remote CI, soak/failure testing and staged production acceptance.

Do not add speculative scoring features merely to create activity. Reuse existing chain identity, generic EVM, social/caller, wallet, opportunity, replay, Telegram and paper-execution engines.

Keep protected modes exactly:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No signer, swap submission, private key, sniper or live copy trading. This roadmap may only reach `PRODUCTION_READY_READ_ONLY` or `PRODUCTION_READY_PAPER_AUTO`. `LIVE_MONEY_CANDIDATE` requires a separate future operator-approved design and must never auto-change modes.

For every task:

```text
inspect current consumers/state
-> write/confirm failing deterministic tests where feasible
-> implement the smallest coherent change
-> run focused verification
-> run lint/typecheck/security/migrations as relevant
-> update docs/STATUS.md and docs/PRODUCTION_READINESS.md with exact evidence
-> commit/push coherent checkpoint
-> continue
```

Real-data rules:

- never fabricate provider success;
- never treat missing evidence as zero/safe;
- preserve occurred/observed/ingested timestamps, provenance, freshness and chain-qualified identity;
- future outcomes must never enter event-time features;
- headline ATH/mark-price multiples are not executable outcomes without liquidity/impact evidence;
- include winners, ordinary outcomes, severe failures, rugs, false positives, late calls and failed caller calls;
- if sample adequacy is not met, report `INSUFFICIENT_SAMPLES` and continue all keyless/operational work;
- do not tune TEST/live-shadow results into production weights.

Resume-first rule: if `docs/STATUS.md` shows any unfinished coherent task from before this roadmap, complete/verify it first, record evidence, commit/push, then start Production Readiness Task 1. Preserve the four pre-existing unrelated WIP files and any other concurrent user work.

Run `make verify` at major checkpoints and final acceptance. Verify doctors, migrations, security/SBOM, remote CI, backup/restore, soak/failure evidence and git sync before any production-ready classification. Classify external access/network/provider failures honestly and continue all independent work autonomously.

Before stopping, record the exact next unfinished task, blocker, evidence class/sample counts, provider states, protected modes and production gate matrix in `docs/STATUS.md` and `docs/PRODUCTION_READINESS.md`.
