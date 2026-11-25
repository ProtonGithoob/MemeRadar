# Reverse wallet intelligence: implementation report (2026-11-25)

**Goal:** [REVERSE_WALLET_INTELLIGENCE_GOAL](../goals/REVERSE_WALLET_INTELLIGENCE_GOAL.md).

**Branch:** `claude/exciting-brahmagupta-0k7pds`

**Code commits:** `ead143a` onward

**Evidence classes in this report:**

| Class | Meaning |
| --- | --- |
| `FIXTURE` | Synthetic but internally consistent curve data. |
| `HISTORICAL_REAL_PILOT_SMALL_SAMPLE` | Real finalized mainnet data, but too small and too immature for any performance claim. |

## 1. Existing capability audit (M0)

The read-only audit covered `APP`, `PROV`, `PERS`, the worker, the API and the web app.

| Area | Existing | State before this work |
| --- | --- | --- |
| Wallet trades and FIFO | `wallet_tracking.WalletActivity`/`WalletRoundTrip`/`WalletTrackingAnalyzer` | Unit-tested only. Needs a pre-registered wallet registry. No UNKNOWN cost basis, no transfers, `now` is not a point-in-time cutoff. |
| Wallet scoring | `wallet_scoring.SmartWalletScorer`, `assess_wallet_copyability` | Never instantiated in runtime. Copyability is a heuristic over caller-supplied inputs, not a backtest. |
| Labels and external intel | `wallet_labels`, `external_wallet` | The only adapter is a fixture adapter. Advisory only. |
| Graphs | `wallet_relationship` (API read path), `creator_graph` (live in the worker), `holder_graph` | Built from prior payload fields and holder snapshots. No manipulation categories derived from trades. |
| Trade parsing | `pump_fun_events`, `solana_raw_stream`, `solana_rpc` | Pump curve trades are decoded live. No per-mint or per-wallet history crawler. No Helius history API, no Bitquery or Yellowstone adapter. |
| Research | `early_replay`, `extreme_winner_separability`, `early_failure_analysis` (live missed-winner), `backtesting` | Strategy-level only. No wallet copy backtest. |
| PAPER | `paper_execution` (application, worker, persistence) | Opt-in. No wallet inputs. |
| Persistence | Generic `observations` rows | No wallet tables. |
| API and web | `/wallets`, `/wallet-graph/*` and pages | `/wallets` returned an empty in-memory catalog in production. |
| Alpha scorer | `WalletQuality` 0.20, `SmartMoneyConfluence` 0.05 | Fed only by pre-flagged `smart_wallet` observations, which nothing produced. Effectively UNKNOWN in every live run. |

## 2. Verified missing functionality

- **Swap classification.** Nothing decided from a confirmed transaction whether a wallet event was a real swap rather than a transfer, failure, migration or undecoded venue, and nothing reconciled a swap against balances.
- **On-chain winner registry.** There was no registry built from verified on-chain trades that covers non-movers and censors at migration.
- **Point-in-time profiles.** There were no profiles that hide outcomes until their horizon closes, and UNKNOWN cost basis was not supported.
- **Manipulation categories.** None existed: creator-linked, insider, wash and co-buy cluster evidence were all missing, and none of them was excluded from smart-money status.
- **Copyability backtest.** No backtest modelled delays, curve math, fees, slippage or migration censoring, or compared against baselines.
- **Runtime path.** No path existed from wallet profiles to live decisions, and `/wallets` had no data.

## 3. Implemented changes

| Module | Purpose |
| --- | --- |
| `APP/onchain_wallet_events.py` | `OnChainWalletEvent` classifies each event as `SWAP_BUY`, `SWAP_SELL`, `TRANSFER_IN`, `TRANSFER_OUT`, `UNVERIFIED_VENUE`, `LIQUIDITY_MIGRATION`, `CREATE` or `FAILED`, with a `Reconciliation`. It has a dedup identity and `CurveState` constant-product math. `build_registry_record` assigns an outcome per horizon (1h/6h/24h/7d/30d; 2x–100x+, `NO_MOVE`, `CENSORED`, `PENDING`). |
| `PROV/pump_fun_wallet_activity.py` | Turns a confirmed jsonParsed transaction into events. Only Pump-context `TradeEvent`s become swaps, and each is reconciled against the wallet's token balance delta. The curve's counter-movement is dropped. Residual moves inside undecoded programs become `UNVERIFIED_VENUE`; other residual moves are transfers. |
| `APP/wallet_intelligence.py` | `build_profiles(as_of)`: FIFO lots with UNKNOWN basis and a recorded fee assumption; only outcomes observable at `as_of`. Categories with evidence lists. `co_buy_clusters` finds same-slot co-buying on ≥2 mints and skips busy slots. `signal_features_from_categories` has a coverage gate. |
| `APP/wallet_copyability.py` | Walk-forward copy backtest with latency, delay, fee, slippage, migration censoring and data-end censoring. The tracked-wallet selector is evaluated at signal time. Baselines: copy-all, random at the same time, momentum. |
| `WORKER/wallet_profile_store.py` | Append-only `wallet.profile` observations. Point-in-time lookup by decision time. `wallet.signal_features` observations. |
| `WORKER/early_discovery.py` | Lifecycle reevaluation loads the tape buyers' profiles as of the scheduled checkpoint and records `wallet.signal_features`. It passes counts to the scorer only when `WALLET_INTELLIGENCE_SCORING_ENABLED=true` (default `false`) and at least 50 % of buyers have a profile. |
| `PERS/read_queries.py` | `/wallets` and `/wallets/{address}` serve the latest profiles. Score is `None`, risk wallets are `BLOCKED`, and every view carries `HEURISTIC_CLASSIFICATION_NOT_CALIBRATED`. |
| `scripts/reverse_wallet_research.py` | Resumable collection of an M1 cohort's full histories, then analysis. |

### Reuse decision

`wallet_tracking.WalletRoundTrip` and `SmartWalletScorer` are not replaced. They take already-classified trades of registered wallets, and the new module sits before them. They were not reused for profiles because the goal requires two things they cannot do: UNKNOWN cost basis for transferred lots, and an as-of filter on both events and outcomes.

## 4. Data source contracts

| Source | Used for | Contract |
| --- | --- | --- |
| Solana RPC `getSignaturesForAddress(mint, finalized)` | History index per token | Paged oldest-ward until the launch signature appears. A history is `history_complete` only when the launch signature was reached and every transaction was fetched. |
| Solana RPC `getTransaction(jsonParsed, finalized)` | Transaction body | `meta.err`, Pump-context logs and `pre/postTokenBalances`. A missing body is counted, and the history is then not complete. |
| Pump.fun `TradeEvent` (verified discriminator `bddb7fd34ee661ee`) | Swap side, user, SOL and token amounts, post-trade virtual reserves | Fee fields are not decoded (unverified), so fees are a recorded assumption. `real_*` reserves are not used. |
| DexScreener | Discovery and enrichment only | Not used for historical trades or OHLC. |
| Helius history, Bitquery, Yellowstone | Not added | Public RPC already covers the pilot. No incremental value has been measured (see §12). |

Price semantics: `reference_price` is virtual SOL over virtual tokens after a trade. Market cap uses Pump.fun's fixed 1e9 × 1e6 raw supply and is expressed in SOL. Hypothetical fills come from `CurveState.buy`/`sell` on the state that existed before the simulated action.

## 5. Database and migration changes

None. Profiles and signal features are `observations` rows (`wallet.profile`, `wallet.signal_features`), with deterministic UUIDv5 identities, so duplicate deliveries are idempotent. Migration head stays `0015`.

## 6. Runtime wiring proof

- **Reevaluation loop.** `early_discovery._run_early_lifecycle_reevaluation` calls `_wallet_signal_features` on every reevaluation and writes `wallet.signal_features`.
- **Scorer gate.** Counts enter `safety_evidence` → `FastSafetyGate` → `early_runtime._components` → `WalletQuality`/`SmartMoneyConfluence` only when the flag is enabled.
- **Read path.** `SqlAlchemyReadQueryService.list_wallets` and `get_wallet` serve the profiles.
- **Tests:** `tests/unit/test_wallet_profile_store.py` and `tests/integration/test_wallet_profiles_postgres.py`. The PostgreSQL test covers duplicate delivery, point-in-time lookup, the read API and restart through a new engine.

## 7. Historical evaluation methodology

1. **Cohort.** The M1 all-observed-launch cohort, which includes non-movers by construction. This is a bounded finalized window with a two-source-verified inventory (window2: 45 launches, digest `sha256:14b06713…`).
2. **Collection.** The full finalized history of each token is reconstructed and classified as above.
3. **Registry.** Outcome per horizon is anchored at the first verified trade's reference cap. The path is censored at migration, because PumpSwap events are not decoded, or when the history is incomplete. Horizons that are not yet mature are `PENDING`.
4. **Profiles and categories.** Computed at `as_of`. A token's outcome counts only after `launch + horizon ≤ as_of`.
5. **Copyability.** Walk-forward. At each signal time *t* the tracked set is recomputed from data up to the 10-minute bucket of *t*.
   - Entry: *t* + 2 s provider latency + 15 s decision delay, into the curve state before that moment, with 125 bps fee + 100 bps slippage, about 0.333 SOL.
   - Exit: when the wallet's next sell becomes observable, or after a 30-minute hold.
   - Censoring: unpriced after migration, or beyond the observed data.

   All are compared against copy-all, random-at-the-same-time and momentum (≥10 buys in 60 s) baselines.

## 8–10. Before/after metrics, wallet signal precision and coverage, realistic PAPER outcomes

See §13 for the pilot run. Before this work, live wallet features were UNKNOWN in 100 % of decisions. After it, features are recorded as shadow evidence whenever profiles exist for at least one buyer. Scoring influence stays off until an ablation over a matured cohort supports it.

No PAPER fills were produced from wallet signals, because no candidate qualifies under the default policy. Wallet-derived PAPER results therefore remain `NOT_AVAILABLE`.

## 11. Test results

| Suite | Result |
| --- | --- |
| Unit tests | 1,858 passed |
| PostgreSQL integration (isolated local 16.15) | 35/35 passed |
| Reverse-wallet unit tests | 12 synthetic curve tests; 4 tests on real mainnet transactions (buy and sell `MATCHED`, tampered balance gives `MISMATCH`, failed transaction, migration produces no buys); 4 store/read tests |

## 12. Remaining blockers

- **Cohort maturity and size.** 24h/7d/30d outcomes for the pilot cohort mature from 2026-11-26 to 2026-12-25. Statistically meaningful wallet precision needs many more cohorts. An M9-style forward run on the operator host should collect histories daily.
- **PumpSwap trade decoding.** It is not implemented. Post-graduation paths, and therefore most 10x+ moves, are censored, and copy exits after migration are unpriced.
- **Funding graph.** Collecting a wallet's funding history needs a per-wallet history crawl. On public RPC this is rate-limited, so it is not collected yet. `co_buy_clusters` is the only coordination evidence so far.
- **Helius, Bitquery, Yellowstone.** Not added. There is no measured incremental value yet, and Bitquery and Helius history need keys.
- **Dashboard.** The existing `/wallets` pages now have data. A registry page and copyability reports in the web app are not built.
- **Robinhood Chain.** No verified launchpad or factory addresses exist yet.
