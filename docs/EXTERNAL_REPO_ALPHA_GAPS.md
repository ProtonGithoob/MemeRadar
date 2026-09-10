# External Repo Alpha Gaps

Purpose: add only high-value capabilities that are still absent from MemeRadar after the latest parity/evidence work. This is a delta plan, not a new architecture.

## P0 — Robinhood launch lifecycle intelligence

Add a reusable `LaunchLifecycleEvidence` on top of existing generic-EVM + Robinhood seams.

Required states:
- `CREATED`
- `BONDING`
- `GRADUATING`
- `DEX_LIVE`
- `UNKNOWN`

Track when available:
- chain-qualified token identity
- launchpad/protocol
- creator
- bonding-curve state/progress
- quote asset
- graduation threshold/state
- graduated_at
- first verified DEX liquidity
- first verified swap
- liquidity-lock/permanent-liquidity evidence
- provenance/freshness/reason codes

Important: bonding-stage tokens must not be misclassified as `NO_ROUTE` merely because a normal DEX pair does not exist yet. Route semantics must distinguish `BONDING_ROUTE`, `DEX_ROUTE`, `NO_ROUTE`, `UNKNOWN`.

Use existing opportunity/ultra-early/read models. Do not create a separate Robinhood scoring engine. Unverified launchpad contracts/events stay `UNKNOWN`.

## P0 — Graduation-aware market discovery

Extend opportunity discovery so a candidate can transition:

`launch -> bonding market -> graduation -> verified DEX market`

On graduation, reconcile canonical RPC state and discover supported V2/V3/V4-style liquidity only through verified adapters/contracts. Preserve event-time ordering and no-lookahead.

Expose lifecycle + route state in Opportunities, Ultra-Early, token detail and provider/operations evidence where useful.

## P1 — Wallet funding/bridge relationship evidence

Extend existing wallet graph / KOL side-wallet evidence with independent relationship dimensions that are currently not first-class:
- shared funding source
- repeated common funding source
- funding-time proximity
- bridge-origin correlation where provenance is available
- repeated same-token/cohort participation
- cross-chain funding continuity

Create/reuse `WalletRelationshipEvidence`; do not assert common ownership from one weak signal.

Suggested confidence rule:
- one weak dimension -> `UNKNOWN/WEAK`
- two independent dimensions -> at most `MEDIUM`
- repeated multi-event funding + behavioral correlation -> `HIGH` candidate evidence
- contradictory evidence -> downgrade/`CONFLICTED`

Never make bridge/exchange deposit heuristics authoritative. Exchange/aggregator/shared-service addresses must be treated as high-collision entities and heavily down-weighted or excluded.

Feed this evidence into existing wallet graph, caller conduct, smart-money convergence and KOL-bundle calibration only as measurement evidence.

## P2 — Free-first live launch aggregation fallback

Audit whether the current Solana free-first discovery path has a real gap before implementing.

Only if missing, add a provider-neutral fallback that can merge normalized launch/event observations from existing free/read-only sources for Pump.fun/PumpSwap/Raydium/Jupiter-style discovery.

Requirements:
- dedupe by canonical event/token identity
- source priority + provenance
- no duplicate scoring engine
- provider disagreement -> `CONFLICTED/UNKNOWN`
- stale source does not overwrite fresher canonical evidence

Do not copy external bot/trading logic and do not add live execution.

## Acceptance

For each capability:
1. focused gap audit against current code
2. reuse existing domain/provider/read-model seams
3. failing deterministic tests first
4. minimal implementation
5. frontend/API projection only for operator-useful evidence
6. update parity manifest if backend response fields change
7. focused verification, then final `make verify`

Required tests:
- bonding token is not falsely `NO_ROUTE`
- lifecycle transitions preserve ordering/no-lookahead
- unverified Robinhood contract/event -> `UNKNOWN`
- graduation discovery dedupes RPC/feed duplicates
- shared exchange/bridge service does not create false wallet ownership
- weak funding-only correlation cannot become HIGH
- contradictory wallet-link evidence degrades confidence
- provider fallback preserves provenance/freshness

Protected modes remain exactly:
`ANALYSIS_ONLY=true`
`PAPER_TRADING=true`
`MANUAL_EXECUTION=false`
`AUTO_EXECUTION=false`

These additions are measurement/discovery capabilities only. They do not change `NOT_PRODUCTION_READY`, production weights, or live-money eligibility.
