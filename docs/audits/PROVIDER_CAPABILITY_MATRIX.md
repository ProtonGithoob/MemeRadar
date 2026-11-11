# Provider capability matrix

Statuses are based on code, deterministic tests and runtime evidence from this
checkout. The doctor ran with `--no-network`; `CONFIGURED` is not provider
health. No live provider was accepted. No provider was added in this task.

| Provider / capability | Implementation and wiring | Deterministic evidence | Live acceptance |
| --- | --- | --- | --- |
| Solana JSON-RPC | `SolanaRpcAdapter`; included by `build_provider_bundle`; worker uses it for raw stream/backfill. | Adapter/composition/doctor contracts; default configured, network not checked. | `BLOCKED_EXTERNAL`, not accepted. |
| Solana raw stream / Pump.fun decoder | `SolanaRawTransactionSource`, `CanonicalProtocolDecoder`, `StreamIntegrityCoordinator`; early-alpha worker path. | Decoder, stream integrity, replay and worker tests. | No live stream/database run. |
| Helius | `HeliusRpcAdapter` and stream adapters; optional when endpoint/key are configured. | Fixture/contract coverage. | Optional, unconfigured; not accepted. |
| DexScreener | `DexScreenerAdapter` for market, pair metadata and reference quote; default route and forward-evidence collector. | Adapter/worker/doctor contracts; configured/defaulted, network not checked. | Not accepted; reference quote is not executable-fill evidence. |
| Birdeye | `BirdeyeRestAdapter`; optional market/discovery fallback. | Adapter contracts. | Optional, unconfigured; not accepted. |
| RugCheck | `RugCheckRestAdapter`; optional advisory risk enrichment. | Adapter and risk contracts. | Optional, unconfigured; not accepted. |
| GoPlus-style token security | `GoPlusTokenSecurityAdapter` exists with tests but is not wired by provider composition. | Unit and contract fixture tests. | `IMPLEMENTED_BUT_UNWIRED`; no operational producer. |
| BNB RPC / DEX | EVM RPC and protocol adapters exist; route is conditional on enabled chain and RPC URL. | Deterministic adapter/identity tests. | No live BNB DEX acceptance established. |
| Robinhood / MadeOnSol | Generic Robinhood EVM RPC plus optional MadeOnSol adapter and shadow worker gate. | Contract and fixture tests. | Optional/config-dependent; no live acceptance. |
| External wallet intelligence | Injected application port, fixture adapter and event-stream seams. | Contract tests. | No credentialed source or live history acceptance. |
| Social analytics | `SocialRestAdapter` is optional for social mentions; DexScreener provides only declared social metadata. | Deterministic parser tests. | No live feed acceptance. |
| Social calls / caller conduct | `SocialRestAdapter.search_calls`, `SocialCallCollector`, `SocialCallObservationRepository`, and bounded social-call read exist; `CallerMarketConductAnalyzer` is a pure analyzer. | `tests/unit/test_social_call_collection.py`, `tests/unit/test_caller_conduct.py`. | Collector is not invoked by worker/provider composition. Social calls can be stored/read, but analyzed caller-conduct results have no production producer, persistence owner or read projection. Not operational. |
| Telegram | Bot API notification/call adapters are optional and downstream. | Fixture/contract tests. | Credentials absent; no notification sent. |
| Jupiter | Optional paper quote adapter. | Quote contracts. | Not accepted; no order path. |
| Ollama / external narrative | Local Ollama or disabled/optional external narrative; advisory only. | Unit/contracts. | No model configured in doctor run. |
| GeckoTerminal, Honeypot.is, Bubblemaps, Cielo, Solscan, Kolscan, Dune | No accepted adapter/wiring found in current composition. | No tests establishing an integration. | Not implemented; deliberately not added during stabilization. |

No environment variable alone establishes an implemented or healthy source.
Third-party risk/wallet evidence remains advisory; deterministic local gates
remain authoritative.
