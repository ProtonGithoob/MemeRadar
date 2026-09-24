# External integration matrix

Reviewed: 2026-09-24.  The matrix records what is implemented locally and what
still needs a verified live contract or external acceptance.  `VERIFIED` is
reserved for a chain ID, address, runtime bytecode, event identity and sample
transaction proven together; README claims are insufficient.

| Repository / reference | Capability | Chain | Protocol | License | Last reviewed commit | MemeRadar reuses | Explicitly does NOT reuse | Verification status |
|---|---|---|---|---|---|---|---|---|
| `raydium-io/raydium-sdk-V2` | Pool identity, CPMM/CLMM concepts, read-only quote semantics | Solana | Raydium | Restrictive/GPL policy note; exact ref not locally reverified | `NOT_LOCALLY_VERIFIED` | Public protocol concepts; independent `RaydiumAdapter` | SDK source, signing, execution | `TODO_VERIFY` (no live deployment evidence) |
| `jup-ag/docs` / Jupiter Swap API | Quote/order response parsing, route quality, impact, sell-route check | Solana | Jupiter Swap API V2 | `NOT_LOCALLY_VERIFIED` | `NOT_LOCALLY_VERIFIED` | Current documented V2 HTTP shape; independent `JupiterAdapter` | Signing, submission, Jupiter as authority | `PARTIAL / BLOCKED_EXTERNAL` (URL/acceptance absent) |
| `MadeOnSol/robinhood-chain-sdk` | KOL, wallet, tape, holder and risk evidence | Robinhood | MadeOnSol intelligence | MIT; commit `241d63978f35458ecac85507098278cdb2f1440d` | `241d63978f35458ecac85507098278cdb2f1440d` | Existing bounded read-only provider contract | Provider labels as truth, scoring, execution | `PARTIAL / BLOCKED_EXTERNAL` (credentials/live sample absent) |
| `0xfnzero/rbh-trade-sdk` | V3/V4 route and capability concepts | Robinhood | Uniswap/Pons/Bags/o1/Pools.trade | `NOT_LOCALLY_VERIFIED` | `NOT_LOCALLY_VERIFIED` | Route semantics only | Local signing, order submission, SDK source | `TODO_VERIFY` |
| `nirholas/robinhood-chain-sdk` | Chain/protocol lifecycle reference | Robinhood | Robinhood ecosystem | `NOT_LOCALLY_VERIFIED` | Contract ideas only | Source and execution flows | `TODO_VERIFY` |
| `pardotfamily/par` | Launch, pool, trade, multi-market lifecycle | Robinhood | Par / Uniswap V4 | `NOT_LOCALLY_VERIFIED` | Adapter shape and normalized fields | Bonding-curve assumptions, unverified addresses | `TODO_VERIFY` |
| `pardotfamily/par-sdk` | Read-only quote and route concepts | Robinhood | Par | `NOT_LOCALLY_VERIFIED` | None beyond independent field names | SDK source/signing | `TODO_VERIFY` |
| `Gitlawb/openlaunch` | Candidate launch discovery | Robinhood/Base | OpenLaunch | `NOT_LOCALLY_VERIFIED` | Candidate registry entry only | Address/ABI claims and authority | `TODO_VERIFY` |
| `0xfnzero/bsc-trade-sdk-nodejs` | BNB route/quote concepts | BNB | BNB DEX routes | `NOT_LOCALLY_VERIFIED` | None beyond independent adapter seam | Source, signing, execution | `TODO_VERIFY` |
| `four-meme-community/four-meme-ai` | TokenCreate/Purchase/Sale/LiquidityAdded vocabulary | BNB | Four.meme | `NOT_LOCALLY_VERIFIED` | Independent lifecycle aliases | README deployment addresses | `TODO_VERIFY` |
| `Uniswap/sdks` | V2/V3/V4 pool and quote concepts | Ethereum/Base/Robinhood | Uniswap | `NOT_LOCALLY_VERIFIED` | Current SDK concepts; generic `UniswapAdapter` | Archived router SDKs, signing, execution | `TODO_VERIFY` (deployments absent) |
| `Uniswap/liquidity-launcher` | Launch/deployment event reference | Ethereum/Base | Liquidity Launcher | `NOT_LOCALLY_VERIFIED` | Candidate protocol concept only | Deployment authority and source | `TODO_VERIFY` |
| `Blockscout/docs` | Contract metadata, transactions, token transfers | EVM (configured chain) | Blockscout explorer | `NOT_LOCALLY_VERIFIED` | `NOT_LOCALLY_VERIFIED` | Documented read endpoint shapes; independent `BlockscoutAdapter` | Real-time trade transport, scoring, execution | `PARTIAL / BLOCKED_EXTERNAL` (optional URL absent) |

## Local implementation boundary

The generic EVM adapter, named chain identities, protocol deployment registry,
Blockscout enrichment and EVM sellability seam are implemented read-only.  A
protocol remains `TODO_VERIFY` until the deployment evidence contract above is
complete.  The BNB, Base, Ethereum, Arbitrum, Avalanche, Polygon and Unichain
RPC adapters are disabled unless explicitly configured; Sui has only a
non-EVM interface seam.
