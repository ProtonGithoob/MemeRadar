# Codex Start Prompt

Use this short prompt after opening/cloning `Rasman1234/MemeRadar`.

```text
You are the principal engineer for MemeRadar. Continue autonomously from the repository's exact current state. Do not rely on this prompt as the full specification; the repository documents are the source of truth.

FIRST, WITHOUT EDITING CODE:
1. Run: git status --short; git branch --show-current; git log -8 --oneline; git fetch origin.
2. Read AGENTS.md completely.
3. Read docs/STATUS.md and preserve the exact active checkpoint/concurrent work.
4. Read these canonical implementation documents in order:
   - docs/OPPORTUNITY_DISCOVERY_EXTENSION.md
   - docs/superpowers/plans/2026-09-05-opportunity-discovery.md
   - docs/SMART_MONEY_CONVERGENCE_EXTENSION.md
   - docs/CODEX_MULTICHAIN_EXTREME_WINNER_EXECUTION.md
   - docs/MULTICHAIN_EXTREME_WINNER_IMPLEMENTATION_SPEC.md
   - docs/ALPHA_20X_100X_PRODUCT_OBJECTIVE.md
   - docs/ARCHITECTURE.md
   - docs/SCORING_AND_RISK.md
   - docs/PROVIDERS.md
5. Inspect existing consumers before creating any module. Reuse existing chain/event/wallet/graph/scoring/replay/alert/UI primitives and avoid duplicate engines.

PRIMARY OBJECTIVE:
Implement the Opportunity Discovery roadmap task-by-task so MemeRadar can detect extreme-winner candidates earlier through chain opportunity, causal narratives, pre-token attention, correct original-vs-copycat contract resolution, protocol/fundamental velocity and smart-money corroboration.

MANDATORY DISCOVERY CHAINS FOR THIS ROADMAP:
SOLANA + BNB + ROBINHOOD.
Robinhood must reuse generic EVM primitives. Mainnet chain id is 4663. Runtime must verify chain id and remain read-only.

EXECUTION RULE:
Follow docs/superpowers/plans/2026-09-05-opportunity-discovery.md from the first genuinely unfinished task recorded in docs/STATUS.md. For every task: failing tests -> confirm failure -> smallest coherent implementation -> focused tests -> lint/typecheck -> STATUS evidence -> commit -> continue. Run make verify at coherent phase checkpoints.

DO NOT CHANGE PRODUCTION SCORING WEIGHTS merely because a new feature looks promising. New chain/narrative/attention/KOL/smart-money evidence remains measurement-only until no-lookahead TRAIN/VALIDATION/TEST replay, ablation and the existing human-reviewed promotion gate prove incremental out-of-sample value.

MANDATORY RESEARCH RULES:
- future 2x/5x/10x/20x/50x/100x labels never leak into live features;
- use negative controls, not only winner examples;
- missing evidence is UNKNOWN, never zero/safe;
- mark-price wicks in thin liquidity are not executable winners;
- keep upside evidence separate from market-integrity/contract/liquidity risk;
- strong narrative/smart-money evidence can never override hard BLOCK/UNKNOWN risk or non-sellability;
- REAL_WORLD_ALPHA_NOT_YET_PROVEN remains until real out-of-sample live-shadow evidence clears the existing gate.

PROTECTED MODES MUST REMAIN EXACTLY:
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false

NEVER ADD:
live signing/swaps/private keys/sniping/copy trading/KOL auto-follow; guaranteed 10x-100x predictions; ticker/name-only token identity; required website scraping dependencies; duplicate wallet/social/graph/score/alert/dashboard engines; opaque LLM production scores; dead env variables.

External/network blockers do not stop independent work. Finish keyless contracts/fixtures/tests/doctors and classify the external item honestly as BLOCKED_EXTERNAL/RATE_LIMITED/DEGRADED/etc. Never fabricate PASS.

At completion, update docs/STATUS.md with exact evidence and the exact next unfinished task, commit/push coherent checkpoints, and verify repository sync. Return a compact support/implementation/test/blocker matrix.

BEGIN NOW. Do not stop after planning and do not ask routine approval questions.
```
