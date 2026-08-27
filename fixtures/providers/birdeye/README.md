# Birdeye market fixtures

These files are synthetic JSON REST responses used by keyless contract tests. They are not live captures and contain no credentials.

| File | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|
| `new_listing.json` | `discovery` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |
| `market_data.json` | `market_data` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |
| `trade_data.json` | `market_data` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |
| `holder.json` | `market_data` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |
| `security.json` | `risk` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |
| `networks.json` | `health` | `birdeye-rest-v1` | `birdeye-market-v1` | `2026-08-27T11:00:00Z` | `true` |

The replay endpoint is the non-credential fixture URL `https://fixture.birdeye.example`. Contract tests inject HTTP responses and assert canonical Solana identities, normalized market observations, freshness and provenance.

