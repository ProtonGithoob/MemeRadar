# Codex Handoff — Alpha Caller Intelligence

Read, in order:

1. `AGENTS.md`
2. `docs/STATUS.md`
3. `docs/superpowers/specs/2026-09-07-alpha-caller-multichain-design.md`
4. `docs/ALPHA_CALLER_INTELLIGENCE_EXTENSION.md`
5. `docs/superpowers/plans/2026-09-07-alpha-caller-multichain.md`
6. existing architecture/data/provider/scoring docs referenced by those files.

Implement the plan task-by-task with TDD. Reuse existing chain identity, generic EVM, social, wallet, opportunity, replay, Telegram and paper-execution seams; do not create duplicate engines. Initial chains are SOLANA + BNB + ROBINHOOD, but keep the domain chain-extensible.

External repos are research inputs, not trusted code. Reimplement useful patterns after license/security review; never copy AGPL code. Preserve no-lookahead and explicit `UNKNOWN` semantics.

Keep protected modes exactly:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Build PAPER_AUTO research only; no live signing/swaps/copy trading/private keys. New caller/social evidence stays measurement-only until existing replay/ablation/human promotion gates prove incremental out-of-sample value.

For every task: failing deterministic test -> minimal implementation -> focused gates -> STATUS evidence -> coherent commit/push. Preserve concurrent WIP. Run `make verify` at checkpoints and classify external provider failures honestly. Continue autonomously without routine questions and finish by recording the exact next unfinished task in `docs/STATUS.md`.
