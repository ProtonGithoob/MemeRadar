# Launchpad and DEX event fixtures

These files are synthetic protocol event envelopes used by keyless contract tests. They are not live captures and contain no credentials.

| File | Venue | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|---|
| `pump_fun_create.json` | `pump.fun` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `pumpswap_pool_created.json` | `pumpswap` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `raydium_pool_created.json` | `raydium` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `meteora_pool_created.json` | `meteora` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |

The fixtures use the non-credential source boundary `launchpad-dex-fixture`. Contract tests inject each envelope into its venue adapter and assert canonical identity, pool linkage, provenance and deterministic replay.

