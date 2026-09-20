# Early-alpha discovery source matrix

Generated from the repository's protocol registry, adapter contracts, and the
2026-09-20 operational checks. `TODO_VERIFY` and `SUPPORTED_NEEDS_REVERIFY` are deliberately not
authoritative production support.

| Source | Program identity | Discriminator / event identity | Verification | Decoder / normalizer | Worker-connected | Fixture / contract test | Live read-only verification |
|---|---|---|---|---|---|---|---|
| Solana raw transaction/log stream | Provider-specific; must provide program ID and slot | Full `(program_id, discriminator_or_tag)` key | `TODO_VERIFY` until provider payload and protocol identity are verified | `RawChainTransaction` → `CanonicalProtocolDecoder` → `NormalizedChainEvent` | `SUPPORTED_NEEDS_REVERIFY`: `StreamIntegrityCoordinator` → `EarlyRuntimeStreamWorker` | `tests/unit/test_stream_integrity.py`, `tests/unit/test_early_worker_pipeline.py` | `BLOCKED_EXTERNAL`: no verified raw-transaction websocket adapter is configured |
| Pump.fun | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (official public docs; registry provisional) | Anchor `trade` = `b2901ad8f1bbce82` (decoder still provisional) | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` | `PumpFunAdapter`, `CanonicalProtocolDecoder`, launchpad normalizer | Connected through the canonical injected raw-event seam; not authoritative until registry verification | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| PumpSwap | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` (registry provisional) | Anchor `swap` = `f8c69e91e17587c8` (registry provisional) | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` | `PumpSwapAdapter`, `CanonicalProtocolDecoder`, launchpad normalizer | Connected through the canonical injected raw-event seam; not authoritative until registry verification | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Raydium AMM v4 | `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8` (registry provisional) | Native initialize tag `0` (registry provisional) | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` | `RaydiumAdapter`, `CanonicalProtocolDecoder`, launchpad normalizer | Connected through the canonical injected raw-event seam; not authoritative until registry verification | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Raydium CPMM | `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C` (registry provisional) | Anchor `swap` = `f8c69e91e17587c8` (registry provisional) | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` | Shared `RaydiumAdapter`, `CanonicalProtocolDecoder` | Connected through the canonical injected raw-event seam; not authoritative until registry verification | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Raydium CLMM | `CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK` (registry provisional) | Anchor `swap` = `f8c69e91e17587c8` (registry provisional) | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` | Shared `RaydiumAdapter`, `CanonicalProtocolDecoder` | Connected through the canonical injected raw-event seam; not authoritative until registry verification | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Meteora DLMM | `LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo` (official docs; not registered) | Pool/trade instruction identity not registered | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` in coverage audit; no authoritative route | `MeteoraAdapter` exists, but the registry intentionally does not route it | `PRESENT_BUT_NOT_CONNECTED` as an authoritative source; fail-closed | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Meteora DAMM v2 | `cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG` (official docs; not registered) | Pool/trade instruction identity not registered | `TODO_VERIFY` / `SUPPORTED_NEEDS_REVERIFY` in coverage audit; no authoritative route | `MeteoraAdapter` exists, but the registry intentionally does not route it | `PRESENT_BUT_NOT_CONNECTED` as an authoritative source; fail-closed | `tests/unit/test_launchpad_dex.py`, `tests/unit/test_protocol_registry.py` | `BLOCKED_EXTERNAL` |
| Raydium LaunchLab / LetsBonk | No registry entry | Not registered | `NOT_SUPPORTED_PLANNED` | No dedicated verified decoder | Not connected | Registry audit contract | `BLOCKED_EXTERNAL` |
| Meteora DBC / Believe | No registry entry | Not registered | `NOT_SUPPORTED_PLANNED` | No dedicated verified decoder | Not connected | Registry audit contract | `BLOCKED_EXTERNAL` |
| Jupiter-related market discovery | No launch-program identity in this repository | No authoritative launch-event identity | `NOT_SUPPORTED_PLANNED` as a primary launch source | Existing market/quote ports may confirm a market; they do not establish creation-time chain evidence | `PRESENT_BUT_NOT_CONNECTED` for primary discovery | Provider composition and market-data tests | `UNKNOWN` / no historical primary-discovery timestamp |
| DexScreener new-pair / market confirmation | API identity is provider-level, not a chain launch-program identity | New-pair and market observations only | `SUPPORTED` as secondary market evidence; not a creation-time authority | Existing `DexScreenerAdapter` and market-data port | `PRESENT_BUT_NOT_CONNECTED` to the canonical raw stream; remains secondary confirmation | `tests/unit/test_dexscreener.py`, provider contract tests | Provider doctor only; historical Trending/Top Volume timestamps are `UNKNOWN` unless authoritative evidence is supplied |

## Interpretation

The 2026-09-20 read-only smoke check reached
`wss://api.mainnet-beta.solana.com`, obtained a `logsSubscribe` subscription
for the provisional Pump.fun program reference, and unsubscribed successfully.
This verifies WebSocket transport capability only; it does not verify the
program identity, event discriminator, transaction enrichment, or canonical
decoder route. No real launch event was admitted to MemeRadar.

The current Pump.fun program address and Meteora DLMM/DAMM addresses are now
recorded from the respective public protocol documentation. This updates
references only; no venue is promoted to `SUPPORTED_VERIFIED` without a
verified instruction/event payload decoder and live contract evidence.

The new worker connection is real for any source that supplies a validated
`RawChainTransaction`: the existing canonical decoder, cursor/gap store, and
early runtime are one path. The external acceptance blocker is narrower: the
repository does not currently contain a verified websocket adapter that turns a
configured Solana/Helius URL into those raw transactions. A URL, adapter DTO,
or provisional program reference is therefore never promoted to authoritative
launch evidence.
