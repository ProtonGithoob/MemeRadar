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

## 13. Pilot run on real mainnet data (`HISTORICAL_REAL_PILOT_SMALL_SAMPLE`)

**Run:** `artifacts/research/2026-11-25-reverse-wallet-pilot`

**Command:**
```
scripts/reverse_wallet_research.py --cohort artifacts/research/2026-11-25-m1-window2 --max-tx-per-mint 1500 --outcome-horizon 1h
```

**Source:** public publicnode RPC, finalized commitment. Collection exit 0, analysis exit 0.

**Analysis:** 2026-11-25 ≈ 03:30 UTC, about 3 h after the launches.

### Collection and classification

| Metric | Value |
| --- | --- |
| Cohort | 45 all-observed launches (M1 window2, digest `sha256:14b06713…`) |
| Complete histories | 30 / 45 |
| Truncated | 15. Each has more than 1,500 transactions; the launch-forward part was kept and the cutoff recorded. |
| Migrations seen on-chain | 2 |
| Events / verified swaps | 23,457 / 2,811 (1,529 buys, 1,282 sells) |
| Swap reconciliation | 2,789 `MATCHED` (99.2 %), 22 `MISMATCH`, 0 `UNKNOWN` |
| Non-swap kinds | 19,898 `FAILED` transactions, 43 `TRANSFER_IN`, 5 `TRANSFER_OUT`, 654 `UNVERIFIED_VENUE`, 44 `CREATE`, 2 `LIQUIDITY_MIGRATION` |

**Failed transactions.** 85 % of fetched transactions failed. They are mostly failed snipe and bot attempts. None of them was counted as a trade.

**Undecoded venues.** The 654 `UNVERIFIED_VENUE` balance moves are post-migration AMM trades and router legs. They were not counted as buys.

### Registry outcomes, 1h after launch

- 19 `NO_MOVE`
- 6 at 2x, 1 at 5x, 1 at 10x, 1 at 20x
- 17 `CENSORED` (incomplete or truncated history, or the path ended)

Horizons of 6h and longer are `PENDING` for 43 tokens. The other 2 tokens migrated, so their path ended early: one is a 20x lower bound and one a 2x lower bound. Both are censored, not final.

### Wallets

**Profiled:** 395 wallets with point-in-time profiles. The profiles use the 1h outcome horizon because that is the only mature one.

| Category | Wallets |
| --- | --- |
| `LOW_EVIDENCE` | 381 |
| `CREATOR_LINKED` | 36 |
| `POTENTIAL_WASH_TRADER` | 23 |
| `POTENTIAL_MANIPULATION_CLUSTER` | 6 (same-slot co-buying on ≥2 mints) |
| `POTENTIAL_INSIDER` | 2 |
| `MOMENTUM_TRADER` | 1 |
| `UNKNOWN` | 3 |
| `EARLY_SMART_MONEY_CANDIDATE` | **0** |

One cohort window cannot show cross-token repeatability. A candidate needs at least 3 tokens with an observable outcome, and almost every wallet traded one token in this window. That is the expected result, not a defect.

### Copyability backtest (walk-forward)

Assumptions:
- delay: 2 s provider latency + 15 s decision delay;
- size: 0.333 SOL;
- costs: 125 bps fee and 100 bps slippage per side;
- exit: follow the wallet's sell, or after a 30-minute hold;
- assumption hash: `sha256:8594db3a…`.

| Strategy | Signals | Priced fills | No fill | Censored | Mean net × | Median net × | ≥2x | ~Total loss | Net PnL (SOL) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tracked wallets | 0 | 0 | 0 | 0 | — | — | — | — | 0 |
| copy first non-creator buyer | 39 | 32 | 7 | 0 | 0.894 | 0.939 | 0 % | 0 % | −1.13 |
| random at the same moments | 39 | 27 | 10 | 2 | 0.800 | 0.932 | 0 % | 3.7 % | −1.79 |
| momentum (≥10 buys in 60 s) | 24 | 19 | 3 | 2 | 0.575 | 0.564 | 0 % | 15.8 % | −2.69 |

### Interpretation (scope: this pilot only)

- After realistic delay and costs, none of the three naive strategies is profitable on this cohort.
- Momentum, which buys after a visible burst, does worst. That is consistent with late entry into dumps.
- There is no validated wallet signal, so the tracked-wallet strategy produced no trades.

None of these numbers is a performance claim. The cohort is a single ~3-minute launch window, and most horizons are immature.

### Before and after

| | Before | After |
| --- | --- | --- |
| Live wallet features | UNKNOWN in 100 % of decisions | Recorded as shadow evidence when profiles exist |
| `/wallets` | Empty | Serves profiles |
| Manipulation-risk wallets | Not detected | Detected; they demote a launch to CAUTION when they are at least 50 % of profiled buyers |
| Wallet precision and coverage | — | Not measurable yet: 0 validated candidates and no mature labels |

### Next steps to reach real evidence

1. Run the collector daily on new M1 windows from the operator host.
2. Persist profiles with `persist_profiles`.
3. Re-run profiles at 24h and 7d maturity.
4. Decode PumpSwap trades so post-graduation paths and exits stop being censored.
5. Only then evaluate `WALLET_INTELLIGENCE_SCORING_ENABLED` by ablation.

### Artifact digests (sha256)

```
    2a1cd7b658ade16da261c7137d8934153c1ddd3a5ec936503999df08cae93d96  summary.json
    3a480358180b71f9e863505b542a07421152404e94bae47b6856a42a52effa6c  registry.json
    2e450033d73e206d5ace70f062bb50d8dc97647ed77952550f032341b25e03ab  profiles.json
    de8ff427263e9d41f847116c85fc36a2c8d3667595e3f09da9ba27fee57c5db3  clusters.json
```

### 13.1 Re-run after PumpSwap decoding (commit `68c77eb`), supersedes the table above

**What changed:** PumpSwap trade decoding was added in `68c77eb`. The two migrated tokens were re-collected with a 3,000-transaction cap. The originals are kept under `pre-pumpswap-decode/`.

**Collection and classification:**

| Metric | Value |
| --- | --- |
| Complete histories | 31 / 45 |
| Verified swaps | 3,018 (1,643 buys, 1,375 sells) |
| Swap reconciliation | 2,987 `MATCHED` (98.97 %), 31 `MISMATCH` |
| `UNVERIFIED_VENUE` | 507 (down from 654) |

**Graduated tokens:**
- **`2P4qGGkK…`**: the history is complete and AMM trades are decoded. The 1h outcome is now **20x (20.30), uncensored**, where before it was a lower bound. The 6h, 24h, 7d and 30d horizons are correctly `PENDING`.
- **`GmRqAzvf…`**: the history is truncated after 3,000 transactions, so its 1h result of 2x (2.78) is still censored as `HISTORY_INCOMPLETE`.

**Wallets:**
- 427 profiled: 412 `LOW_EVIDENCE`, 36 `CREATOR_LINKED`, 30 `POTENTIAL_WASH_TRADER`, 16 `POTENTIAL_MANIPULATION_CLUSTER`, 2 `POTENTIAL_INSIDER`, 1 `MOMENTUM_TRADER`, 2 `UNKNOWN`.
- **0** `EARLY_SMART_MONEY_CANDIDATE`.

**Copyability.** Same assumptions as above. No trade is censored any more, because exits after migration are now priced from pool state.

| Strategy | Signals | Priced | No fill | Mean net × | Median net × | ≥2x | ~Total loss | Net PnL (SOL) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tracked wallets | 0 | 0 | 0 | — | — | — | — | 0 |
| copy first non-creator buyer | 39 | 32 | 7 | 0.894 | 0.939 | 0 % | 0 % | −1.13 |
| random at the same moments | 39 | 29 | 10 | 0.759 | 0.932 | 0 % | 3.4 % | −2.33 |
| momentum (≥10 buys in 60 s) | 24 | 21 | 3 | 0.532 | 0.279 | 0 % | 19.0 % | −3.27 |

Momentum's median net multiple fell from 0.56 to 0.28 once post-migration exits were priced instead of censored. Censoring had hidden part of the loss.

### Digests after the re-run (sha256)

```
    ef97f76f6309af8f1a98ac2b1c20347d1d2dbd34e394d24e8a762f95712798e4  summary.json
    af7b96832b3ad3ac441efedf7d32724969c006ef0aa99b15ce2ecebee711c760  registry.json
    5fd3c824351c3363e5947da129bbdd55eaa35abcdac3ad2312aba34ade571dd3  profiles.json
    d0d2c232f8be3754885f028dcc7658e80b273bdb74519bddb7041f3da85aad5a  clusters.json
```
