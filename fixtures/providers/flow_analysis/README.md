# Flow-analysis fixtures

These files are synthetic, redacted normalized observations for Phase 3 Sprint
3.3. They are not live captures and contain no credentials, private keys,
session material or execution instructions.

| File | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|
| `market_safe.json` | liquidity/depth | `memeradar-market-flow-v1` | `flow-analysis-fixture-v1` | `2026-08-27T14:59:00Z` | `true` |
| `market_suspicious.json` | liquidity decay | `memeradar-market-flow-v1` | `flow-analysis-fixture-v1` | `2026-08-27T14:59:00Z` | `true` |
| `trades_safe.json` | organic maker flow | `memeradar-trade-flow-v1` | `flow-analysis-fixture-v1` | `2026-08-27T14:59:10Z` | `true` |
| `trades_suspicious.json` | wash-trading heuristics | `memeradar-trade-flow-v1` | `flow-analysis-fixture-v1` | `2026-08-27T14:59:10Z` | `true` |
| `quotes.json` | sellability/impact | `memeradar-quote-flow-v1` | `flow-analysis-fixture-v1` | `2026-08-27T14:59:30Z` | `true` |

The replay contract injects these payloads into provider-independent
`Observation` and `QuoteSnapshot` records. The safe set has diverse makers,
unique sizes, stable liquidity and low impact. The suspicious set has a large
liquidity drop, shallow depth, repeated reciprocal trades, rapid buy/sell
round trips and high quoted impact.
