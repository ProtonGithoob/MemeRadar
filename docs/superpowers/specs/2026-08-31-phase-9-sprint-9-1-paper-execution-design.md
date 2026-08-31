# Phase 9 Sprint 9.1 Paper Execution Design

## Goal

Build a deterministic, append-oriented paper-trading ledger that consumes the
existing quote/risk boundary, simulates conservative fills, and can be
replayed and reconciled after a restart without introducing signing or live
submission authority.

## Scope and invariants

This sprint implements the five Sprint 9.1 roadmap items: a paper
portfolio/cash ledger, conservative position sizing, quote/fill/slippage/fee
simulation, idempotent paper orders, and paper position lifecycle plus
reconciliation. It does not implement the Phase 12 execution adapter, wallet
signing, a live provider, or an API mutation route.

The protected modes are constructor invariants in every paper application
service:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

The paper engine accepts only a normalized `QuoteSnapshot` and immutable
decision/risk references. It cannot accept a signer, transaction bytes,
private key, execution port, or live mode. A stale/unknown/conflicted/invalid
quote rejects the order and never changes cash, fills or positions.

## Architecture

The domain layer receives new provider-neutral records in
`memeradar_domain.paper`: `PaperPortfolio`, `CashLedgerEntry`, `PaperOrder`,
`PaperFill`, and their allow-listed side/state values. The existing `Position`
aggregate remains the canonical position snapshot and gains narrow fill
application methods for weighted entry, partial reduction, and full close.

The application layer in `paper_execution.py` owns policy and orchestration:

```text
decision/risk references + QuoteSnapshot
        -> PaperSizingPolicy
        -> PaperFillModel
        -> PaperOrder / PaperFill
        -> cash ledger + Position
        -> atomic PaperLedgerStore
        -> reconciliation/replay projection
```

`PaperLedgerStore` is an application protocol. `InMemoryPaperLedgerStore`
supports deterministic fixtures and restart tests; the SQLAlchemy adapter is
implemented separately in persistence. Both stores persist the same records
and use the same application calculation path.

## Deterministic accounting rules

- A BUY request amount is the input quote-currency amount; a SELL request
  amount is the input token quantity.
- The quoted unit price is `input_amount / output_amount` for either side.
- Configured adverse fill slippage is applied to that unit price: BUY price is
  increased and SELL price is decreased.
- The fill model computes a positive base quantity, gross quote-currency
  notional, fee amount (`notional * fee_bps / 10_000`) and signed cash delta.
  BUY cash delta is `-(notional + fee)`; SELL cash delta is
  `notional - fee`.
- A fill is rejected if the quote is not fresh at the request time, output is
  non-positive, cash would cross the configured reserve, a sell exceeds the
  current position, or the policy returns zero size.
- A partial fill ratio is bounded and deterministic. The order is
  `PARTIALLY_FILLED` when the ratio is below one; no unfilled amount is
  silently treated as filled.
- A successful order appends one order, one or more fills, and one cash ledger
  entry atomically before exposing the updated portfolio/position.
- Reusing an idempotency key with the same canonical request is a no-op that
  returns the original result. Reusing it with different material input raises
  an explicit conflict and cannot change state.
- Position realized PnL is net sell proceeds less average-entry cost for the
  sold quantity. Partial sells retain an open position; a zero remaining
  quantity closes it and records close metadata.

## Persistence and replay

Migration `0006_paper_execution` adds `orders`, `fills`, and the append-only
`cash_ledger` table. Existing `portfolios` and `positions` remain compatible;
order idempotency, fill/order identity, ledger balance sequence and useful
lookup indexes are physical constraints. A reconciliation service recomputes
cash from the initial balance plus ledger deltas, checks each ledger
`balance_after`, checks order fill totals, and reconstructs position quantities
from the persisted paper fills. Any mismatch is `CONFLICTED`, never silently
repaired.

Replay uses the same request ordering and canonical fill model with a pinned
paper policy version/config hash and an event-time `as_of` boundary. Future
quotes/orders are excluded. The result includes the policy version, config
hash, quote provenance and source timestamps needed to reproduce paper
outcomes without a live provider.

## Acceptance

Keyless tests cover protected modes, risk-budget sizing, quote freshness,
deterministic slippage/fee arithmetic, insufficient cash/position rejection,
partial fills, duplicate and conflicting idempotency keys, position open/
add/reduce/close, restart/resume, reconciliation mismatch, same-input replay,
future-data exclusion, SQL round-trip/migration reversibility, and the absence
of provider SDK/signing/execution imports in the domain/application paper
modules. All live-provider or live-execution checks remain
`BLOCKED_EXTERNAL`; the repository remains analysis-only and paper-only.
