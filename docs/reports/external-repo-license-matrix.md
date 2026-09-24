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
