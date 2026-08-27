# Helius read fixtures

These files are synthetic JSON-RPC responses used by keyless contract tests. They are not live captures and contain no credentials.

| File | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|
| `get_asset_token.json` | `on_chain` | `helius-json-rpc-v1` | `helius-read-v1` | `2026-08-27T06:00:00Z` | `true` |
| `get_account_info.json` | `on_chain` | `solana-json-rpc-v1` | `helius-read-v1` | `2026-08-27T06:00:00Z` | `true` |
| `get_transaction.json` | `on_chain` | `solana-json-rpc-v1` | `helius-read-v1` | `2026-08-27T06:00:00Z` | `true` |

The replay endpoint is the non-credential fixture URL `https://fixture.helius.example/rpc`. The contract tests inject the HTTP response and assert normalized identities, authorities, timestamps, quality and provenance.
