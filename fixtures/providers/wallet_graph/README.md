# Wallet graph fixtures

These files are synthetic, redacted normalized observations for the Phase 3
Sprint 3.2 holder concentration and wallet graph contracts. They are not live
captures and contain no credentials, private keys, session material or
execution instructions.

| File | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|
| `holder_data.json` | holder concentration | `memeradar-holder-v1` | `wallet-graph-fixture-v1` | `2026-08-27T12:59:00Z` | `true` |
| `transfers.json` | bounded wallet graph | `memeradar-transfer-v1` | `wallet-graph-fixture-v1` | `2026-08-27T12:59:30Z` | `true` |

The contract tests inject these normalized payloads into provider-independent
`Observation` records. The graph policy traverses one edge from creator/top
holder seeds, excludes known system and program addresses, aggregates repeated
funding evidence, and retains source IDs for replay and explanation.
