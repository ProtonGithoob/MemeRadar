# Codex handoff — External Alpha Gaps

Read `AGENTS.md`, `docs/STATUS.md`, then `docs/EXTERNAL_REPO_ALPHA_GAPS.md`.

Implement only gaps proven absent in current code. Reuse existing generic-EVM, Robinhood, opportunity, ultra-early, wallet graph, KOL/caller, provider, read-model and frontend parity seams.

Priority: P0 Robinhood launch lifecycle + graduation-aware route discovery; P1 wallet funding/bridge relationship evidence; P2 Solana live-launch fallback only if a focused audit proves a real gap.

TDD: focused failing test -> minimal implementation -> focused verification -> update API/frontend/parity manifest if needed -> coherent commit/push. Run full `make verify` only at major/final checkpoint.

Preserve UNKNOWN/no-lookahead/provenance semantics and protected modes. No new live execution, signer, copy trading, duplicate scoring engine, or unverified launchpad identities. Keep `NOT_PRODUCTION_READY` unless independent real-data gates change.

Preserve unrelated WIP. Update `docs/STATUS.md` with exact implemented gaps, tests, blockers, commit SHA and next task. Finish all locally feasible work before stopping on `BLOCKED_EXTERNAL` items.
