# External repository license matrix

Reviewed: 2026-09-24.  This is a local-audit record.  Remote Git operations
were intentionally not used, so a row marked `NOT_LOCALLY_VERIFIED` is not a
license assertion.  MemeRadar copied no source from any row and added no
upstream dependency.

| Repository / reference | License status | Usage | Copied code? | Dependency? | Reference only? | Risk / next check |
|---|---|---|---:|---:|---:|---|
| `raydium-io/raydium-sdk-V2` | `RESTRICTIVE_REFERENCE_ONLY` (project policy identifies GPL; exact upstream ref not locally rechecked) | Protocol/API concepts for Raydium pool normalization | No | No | Yes | Reverify exact license and isolate any future dependency; current adapter is independent. |
| `jup-ag/docs` / Jupiter Swap API | `NOT_LOCALLY_VERIFIED` | Current Swap API V2 request/response contract | No | No | Yes | Reverify repository license and endpoint terms before source reuse; provider URL/key still external. |
| `MadeOnSol/robinhood-chain-sdk` | `MIT` (recorded local audit, commit `241d63978f35458ecac85507098278cdb2f1440d`) | Read-only Robinhood intelligence contract ideas | No | No | Yes | Revalidate upstream API before production use; no signing or provider authority. |
| `0xfnzero/rbh-trade-sdk` | `NOT_LOCALLY_VERIFIED` | Read-only route/capability reference only | No | No | Yes | Do not import signing or transaction code; reverify license before any source reuse. |
| `nirholas/robinhood-chain-sdk` | `NOT_LOCALLY_VERIFIED` | Protocol/lifecycle reference only | No | No | Yes | Reverify license and deployment identities before use. |
| `pardotfamily/par` | `NOT_LOCALLY_VERIFIED` | Par launch/pool lifecycle reference | No | No | Yes | Contract identity, license and sample transaction remain external. |
| `pardotfamily/par-sdk` | `NOT_LOCALLY_VERIFIED` | Par quote/lifecycle reference only | No | No | Yes | Do not vendor SDK; reverify license and route semantics. |
| `Gitlawb/openlaunch` | `NOT_LOCALLY_VERIFIED` | Candidate launch-source reference | No | No | Yes | No address/bytecode/sample transaction accepted yet. |
| `0xfnzero/bsc-trade-sdk-nodejs` | `NOT_LOCALLY_VERIFIED` | BNB route/quote reference only | No | No | Yes | No source reuse; Four.meme/Pancake identities remain TODO_VERIFY. |
| `four-meme-community/four-meme-ai` | `NOT_LOCALLY_VERIFIED` | Four.meme lifecycle vocabulary reference | No | No | Yes | Never trust README addresses without on-chain verification. |
| `Uniswap/sdks` | `NOT_LOCALLY_VERIFIED` | Current V2/V3/V4 SDK concepts via current documentation | No | No | Yes | Verify package licenses and deployed interfaces before dependency use. |
| `Uniswap/liquidity-launcher` | `NOT_LOCALLY_VERIFIED` | Launch-event/deployment reference only | No | No | Yes | Chain, bytecode, interface and license still require external verification. |
| `Blockscout/docs` | `NOT_LOCALLY_VERIFIED` | Read-only v2 explorer endpoint reference | No | No | Yes | Adapter is optional enrichment; verify current API terms before production rollout. |

## Decision

The implementation uses MemeRadar-owned adapters and contracts.  It does not
copy, vendor, or depend on these repositories.  A future source-level reuse
requires an exact commit, root license file, security review, and a new entry
that changes both `Copied code?` and the corresponding integration record.

## 2026-09-26 task-specific audit

The exact root license text was checked where the public repository view or
raw license was available.  `HEAD_NOT_LOCALLY_VERIFIED` is intentional: the
browser audit exposed the repository history and license but not a stable full
HEAD hash for that repository.  Those rows are not eligible for source reuse.
The task explicitly forbids remote Git operations, so no clone, fetch, or
remote Git command was used.

| repo | commit | license | files considered | copy permitted? | attribution required? | dependency permitted? | reference-only? |
|---|---|---|---|---:|---:|---:|---:|
| `CodeMuscle/solbeam` | `HEAD_NOT_LOCALLY_VERIFIED` (public `main`, 72 commits observed) | MIT | root `LICENSE`, `README.md`, repository layout | Yes, only after exact commit capture | Yes | No dependency adopted | Yes until exact commit is captured |
| `nktkass/pumpr-bot` (user URL redirects from `Coinvoro/pumpr-bot`) | `HEAD_NOT_LOCALLY_VERIFIED` (public `master`, 4 commits observed) | MIT | root `LICENSE`, `README.md`, `src/` layout | Yes, only after exact commit capture | Yes | No; execution code rejected | Yes until exact commit is captured |
| `SoCloseSociety/WhalegodTG` | `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6` | MIT | root `LICENSE`, `README.md`, `bot/` layout | Yes, with notice preservation | Yes | No dependency adopted | Yes; concepts only |
| `MadeOnSol/robinhood-chain-sdk` | `241d63978f35458ecac85507098278cdb2f1440d` | MIT | root `LICENSE`, `README.md`, `src/`, `test/` layout | Yes, with notice preservation | Yes | No dependency adopted | Yes; concepts only |
| `pardotfamily/par` | `d2c1f44ce3096d6b80185eeb524c11bedda44e4a` | MIT | root `LICENSE` indicator, `README.md`, `contracts/` layout | Yes, with notice preservation | Yes | No dependency adopted | Yes; protocol reference only |
| `pardotfamily/par-sdk` | `bcbeda5b177e0b764654a663bd9c55f2a40142ba` | MIT | root `LICENSE`, `README.md`, `src/`, `abi/` layout | Yes, with notice preservation | Yes | No; `viem` SDK not adopted | Yes; protocol reference only |
| `bitgrass/Launchpad` | `2d3840ccdc86232009ff363f6be481ea7f73887a` | MIT | root `LICENSE`, `README.md`, application/test layout | Yes, with notice preservation | Yes | No dependency adopted | Yes; runtime claims require verification |
| `nirholas/robinhood-trading-bot` | `HEAD_NOT_LOCALLY_VERIFIED` (public `main`, 8 commits observed) | Apache-2.0 | root `LICENSE`, `README.md`, `src/`, `test/` layout | Yes, with license/notice preservation | Yes | No; signer/executor code rejected | Yes until exact commit is captured |
| `nirholas/robinhood-chain-trading-bot` | `HEAD_NOT_LOCALLY_VERIFIED` (public `main`, 27 commits observed) | Proprietary / All Rights Reserved | exact root `LICENSE`, `README.md`, `src/`, `tests/` layout | No | No reuse permitted | No | Yes |
| `nirholas/robinhood-toolkit` | `HEAD_NOT_LOCALLY_VERIFIED` (public `main`, 23 commits observed) | All Rights Reserved / proprietary | exact root `LICENSE`, package README, `packages/` layout | No | No reuse permitted | No | Yes |

### Security and supply-chain decision

No private-key, signer, live-executor, shell-loader, credential, or remote
binary code was copied.  No external package was added.  Licensed upstream
repositories are still treated as references because adapting their source
would add avoidable supply-chain and architecture coupling.  MemeRadar's P0
organic-flow extension is independently implemented from its normalized event
contract, with provenance and fail-closed unknown semantics retained.
