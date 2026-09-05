# Codex Execution Handoff — Extreme Winner Discovery

## Read these first — canonical source of truth

Do not try to hold the whole roadmap in prompt context. Read and follow these repository files in this order:

1. `AGENTS.md`
2. `docs/STATUS.md`
3. `docs/OPPORTUNITY_DISCOVERY_EXTENSION.md`
4. `docs/superpowers/plans/2026-09-05-opportunity-discovery.md`
5. `docs/SMART_MONEY_CONVERGENCE_EXTENSION.md`
6. `docs/MULTICHAIN_EXTREME_WINNER_IMPLEMENTATION_SPEC.md`
7. `docs/ALPHA_20X_100X_PRODUCT_OBJECTIVE.md`
8. `docs/ARCHITECTURE.md`
9. `docs/SCORING_AND_RISK.md`
10. `docs/PROVIDERS.md`

If two documents conflict, prefer the newer, more specific extension document and record the conflict in `docs/STATUS.md` before implementation.

## Mission

Evolve MemeRadar into a provider-independent **opportunity discovery + extreme-winner research system** that can detect promising candidates early enough to remain executable, while rejecting destructive launches and proving every promoted feature through no-lookahead replay and out-of-sample shadow/paper evidence.

The system is no longer conceptually limited to SOLANA + BNB. The mandatory discovery set for this roadmap is:

```text
SOLANA
BNB
ROBINHOOD
```

Robinhood Chain must use generic EVM primitives, not a parallel duplicated architecture.

The long-term architecture must remain chain-extensible; do not hard-code assumptions that make adding another EVM/non-EVM chain require redesigning core domain logic.

## Highest-priority correction

Do not begin by adding more weights to EarlyScore.

First build the **Opportunity Discovery Layer** described in `docs/OPPORTUNITY_DISCOVERY_EXTENSION.md`:

```text
chain/ecosystem opportunity
-> external catalyst / narrative
-> pre-token attention
-> token/narrative semantic match
-> original-vs-copycat resolution
-> hard safety/sellability
-> attention + smart-money + holder/liquidity corroboration
-> existing EarlyScore/Alpha/decision gates
```

New evidence stays measurement-only until replay/ablation/promotion proves incremental value.

## P0 execution order

Use the exact task order in `docs/superpowers/plans/2026-09-05-opportunity-discovery.md` unless `docs/STATUS.md` records an already-active safe checkpoint that must be completed first.

The P0 product priorities are:

1. preserve/finish generic chain-aware identity and capability routing;
2. add Robinhood Chain read-only support using generic EVM JSON-RPC;
3. implement Chain Opportunity / Chain Heat evidence;
4. implement provider-neutral Global Event contracts;
5. implement Narrative Catalyst + Pre-Token Attention;
6. implement Narrative-to-Token matching;
7. implement Narrative Competition / Copycat resolution;
8. integrate read-only API/Telegram reason evidence;
9. build historical winner + negative-control no-lookahead fixtures;
10. run separability/ablation before changing production scoring.

Then execute P1/P2 exactly as defined in the spec/plan.

## Robinhood Chain required facts

Treat these as configuration with tests, not scattered literals:

```text
CHAIN=robinhood
EVM=true
CHAIN_ID=4663
NATIVE_GAS=ETH
PUBLIC_RPC=https://rpc.mainnet.chain.robinhood.com
PUBLIC_SEQUENCER_FEED=wss://feed.mainnet.chain.robinhood.com
BLOCK_EXPLORER=robinhoodchain.blockscout.com
```

Verify `eth_chainId` at runtime. Public/provider outages must degrade readiness honestly and must not crash the keyless/free core.

## Smart-money integration

`docs/SMART_MONEY_CONVERGENCE_EXTENSION.md` remains mandatory. Reuse existing wallet/social/graph primitives and implement:

- historical wallet quality;
- bounded external seed import;
- cluster-adjusted multi-wallet convergence;
- wallet cohort recurrence;
- KOL/researcher historical quality;
- explicit wallet-linkage boundaries;
- smart-money distribution evidence.

Opportunity/narrative and smart-money signals must be tested both independently and jointly.

## Critical research rules

- Future 2x/5x/10x/20x/50x/100x labels are research targets only.
- Never leak future outcomes, later viral totals or later liquidity into event-time features.
- Do not train only on winners; negative controls are mandatory.
- Mark-price wicks in thin liquidity are not executable winners.
- `INSUFFICIENT_SAMPLES` is a valid result and is preferable to fake confidence.
- Do not dynamically change production weights because an idea looks intuitive.
- TRAIN proposes; VALIDATION selects; TEST reports final out-of-sample evidence.
- Strategy promotion requires the existing human-reviewed promotion gate.

## Risk / upside separation

Keep these concepts distinct in read/research models:

```text
upside_evidence
market_integrity_risk
contract/deployer_risk
liquidity_exit_risk
execution_quality
confidence
```

High narrative/upside evidence must never override critical BLOCK/UNKNOWN risk, honeypot/non-sellability, insufficient liquidity or protected-mode gates.

## Explicit exclusions

Do not add:

- copy trading or automatic KOL/wallet following;
- live signing, swaps, private keys, snipers or live-money execution;
- ticker/name equality as token identity;
- required runtime scraping of FOMO/Hoodwatch/Stalkchain/X pages;
- opaque LLM-created production scores;
- duplicate wallet/social/graph/score/alert/dashboard engines;
- guaranteed-multiple predictions;
- dead `.env.example` settings not parsed/validated by runtime.

## Protected modes — immutable

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

`REAL_WORLD_ALPHA_NOT_YET_PROVEN` must remain until real out-of-sample live-shadow evidence clears the existing research gate.

## Engineering workflow

For every task:

```text
inspect existing consumers
-> write failing deterministic tests
-> run and confirm failure
-> implement the smallest coherent change
-> run focused tests
-> lint/typecheck as relevant
-> update STATUS with evidence
-> commit coherent checkpoint
-> continue
```

At phase checkpoints run `make verify` and available doctors. Classify external failures honestly as BLOCKED_EXTERNAL/RATE_LIMITED/DEGRADED/etc.; never fabricate PASS.

Never destructive-reset concurrent/uncommitted work. Never force-push shared history.

## Completion report

Return a compact implementation matrix with:

- starting/final commits and sync state;
- tasks completed vs blocked;
- Solana/BNB/Robinhood support matrix;
- chain opportunity implementation;
- narrative/pre-token/copycat implementation;
- smart-money/KOL integration;
- API/Telegram changes;
- replay/negative-control datasets;
- ablation/promotion result;
- test counts and `make verify` result;
- provider doctor results/blockers;
- exact protected-mode evidence;
- exact next unfinished task written to `docs/STATUS.md`.

Proceed autonomously. Do not stop after planning, and do not ask routine approval questions.