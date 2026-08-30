# Launchpad and DEX event fixtures

These files are synthetic protocol event envelopes used by keyless contract tests. They are not live captures and contain no credentials.

| File | Venue | Capability | Schema | Parser | Captured at | Redacted |
|---|---|---|---|---|---|---|
| `pump_fun_create.json` | `pump.fun` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `pumpswap_pool_created.json` | `pumpswap` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `raydium_pool_created.json` | `raydium` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `meteora_pool_created.json` | `meteora` | `discovery` | `launchpad-dex-v1` | `launchpad-dex-v1` | `2026-08-27T11:00:00Z` | `true` |
| `rich_pumpfun_replay.json` | `pump.fun`/`pumpswap` | `protocol.lifecycle` replay | `2` | `launchpad-dex-v2` | `2026-08-27T11:00:00Z` | `true` |

The fixtures use the non-credential source boundary `launchpad-dex-fixture`. Contract tests inject each envelope into its venue adapter and assert canonical identity, pool linkage, provenance and deterministic replay.

`rich_pumpfun_replay.json` is a synthetic, keyless E2.5 replay. It includes
launch, trade, bonding-curve progress, graduation, migration, pool creation,
creator-fee and fee-recipient events, plus a PumpSwap trade, an intentional
duplicate delivery and one malformed envelope. Schema v2 preserves the raw
event alias while adding a canonical `ProtocolEventType`; `WHALE_TRADE` is
marked `DERIVED` when a deterministic trade flag is present, and all other
protocol facts remain `NATIVE`. This is not a live capture and it is not a
claim that any provider endpoint is configured or healthy.
