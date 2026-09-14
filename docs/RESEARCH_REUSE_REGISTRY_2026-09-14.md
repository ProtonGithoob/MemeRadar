# Research / Reuse Registry Supplement — 2026-09-14

This supplement records the approved Option A audit without replacing MemeRadar's existing historical `docs/RESEARCH_REUSE_REGISTRY.md` ledger.

| Source | Audit pin | License state at audit | Accepted reuse | Explicitly rejected | Integration mode | Weight / execution status | Revalidation trigger |
|---|---|---|---|---|---|---|---|
| `GMGNAI/gmgn-skills` | `4a48b8a31e19b62c96ee57ba76b46310f84043f0` | Root MIT LICENSE verified | Read-only SOL/BSC discovery, market, KOL/Smart Money, holder/distribution, bundler/sniper/insider and security evidence **if stable server read contract is verified** | CLI subprocess dependency, private key, wallet management, swap, cooking, market/limit/strategy orders, provider-owned final scoring | Optional provider; disabled by default; LIVE_SHADOW | weight=0; no execution | upstream API/schema/auth change; license change; production promotion proposal |
| `SoCloseSociety/WhalegodTG` | `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6` | Root MIT LICENSE verified | Factual transaction activity taxonomy concept; bounded ingestion/dedupe ideas where current MemeRadar lacks them | Telegram/SQLite stack; bullish/bearish/degen conclusions; duplicate alert engine/webhook stack | Independent minimal implementation inside existing Helius normalizer | no score/execution effect | Helius payload contract change; taxonomy expansion |
| `numi-ai/numi-trading-agent` | `cb460ff96508c8fdae64ac169b4fc6cc2703f4ff` | README/package say MIT; root LICENSE not found at audit | Independently reimplemented lifecycle invariants and tests | source/test/comment copying; Numi RiskManager; second Robinhood lifecycle; 1inch/live signer execution | Architectural reference only | no weight/execution effect | root license appears; current MemeRadar lifecycle design materially changes |
| `CodeMuscle/solbeam` | `234423a8f0180deffc6b9d83fa84e35687049670` | README says MIT; root LICENSE not found at audit | UI/research concepts only | source/data-model reuse; duplicate Helius/wallet/alert stack; treating roadmap as implemented | Docs/reference only | none | root license appears and a concrete missing MemeRadar capability is proven |
| `MadeOnSol/robinhood-chain-sdk` | Existing MemeRadar work; use the exact pin already recorded in the historical registry | Existing independent read-only integration track | Existing `madeonsol-robinhood` optional provider direction and canonical Robinhood intelligence evidence | duplicate Robinhood scorer/risk/lifecycle/Telegram systems | Existing optional LIVE_SHADOW integration track | no production promotion without real OOS evidence | any new MadeOnSol capability, API or weight proposal |

## Supplement rules

1. Existing MemeRadar architecture wins; external repositories provide evidence or ideas, not new domain boundaries.
2. License is necessary but not sufficient. Prefer a small independent implementation over importing foreign architecture.
3. No source copy from ambiguous-license entries. README/package license strings are not treated as sufficient for this audit's source-reuse decision when the root license file is absent.
4. Provider labels remain provider labels. `smart_money`, `insider`, `rug`, `KOL`, `alpha` and similar upstream concepts require provenance and must not silently become canonical truth.
5. `UNKNOWN` is preserved. Missing, unsupported or unavailable values do not become zero, false, safe or neutral.
6. Research providers do not receive signing authority. No private key, wallet custody, swap/order or execution capability is added through research reuse.
7. Promotion is empirical. A provider can be available and remain weight 0 indefinitely.
8. Fixtures, mocks, demos, replay-only and synthetic data cannot satisfy real promotion-sample requirements.
9. Revalidate upstream ref, API contract, license, security implications and current MemeRadar overlap before any implementation change.

## Approved semantic boundaries

### GMGN

Accepted as supporting evidence only:

- token discovery/trending;
- KOL and Smart Money observations;
- top trader/holder context;
- bundler, rat-trader, sniper, fresh-wallet and suspected-insider measures;
- creator/dev holding context;
- wash-trading/honeypot/rug context;
- bonding-curve state as lifecycle corroboration.

Not accepted as direct canonical truth or execution authority.

### WhalegodTG

Accepted concept: factual activity type. Directional meaning is deliberately excluded.

### Numi

Accepted concept: route/lifecycle proof must be stronger than a launchpad state label. No second lifecycle engine.

### Solbeam

Reference/UI research only.
