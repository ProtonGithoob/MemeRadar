# GMGN root-cause hardening before-gap matrix

Baseline audited on 2026-09-14:

- `HEAD`: `76794f4177a5c0efe5c6f7379d749908f66b344b`
- `origin/main`: `76794f4177a5c0efe5c6f7379d749908f66b344b`
- worktree: clean before this audit document
- `git fetch origin`: attempted first; the host could not update `.git/FETCH_HEAD`, and the no-`FETCH_HEAD` retry was blocked by DNS. The local remote-tracking ref matched `origin/main`.
- current `GMGNAI/gmgn-skills` `main`: `685c46b324f8075b555307a2faa7f7bd54242a5d`; root MIT LICENSE reverified.

The current provider contract remains the previously audited GMGN OpenAPI
market/token read surface. No GMGN implementation change is authorized by this
matrix until the focused regressions below establish the failing behavior.

| Issue | Current behavior | Root cause | Production impact | Correct owner/module | Required change | Regression test |
| --- | --- | --- | --- | --- | --- | --- |
| Signed trader financial values | `packages/providers/src/memeradar_providers/gmgn.py::_decimal` accepts only finite values `>= 0`; `profit` in `wallet.top_traders` uses it. | One non-negative parser is reused for both physical/ratio fields and financial outcomes. | A losing trader can make the whole enrichment batch fail with `ProviderSchemaError`; silently weakening the helper would admit invalid liquidity/ratio values. | GMGN adapter parser helpers and trader mapping. | Keep `_non_negative_decimal`; add the smallest signed helper and use it only for the verified financial field(s). Audit every numeric mapping by domain. | Negative/zero/positive profit accepted; negative liquidity/holder percentage rejected; `None` stays `None`; malformed values stay schema errors. |
| LIVE_SHADOW decision influence | Canonical `Observation` rows retain GMGN kinds, but generic raw-observation analyzers do not apply a promotion/eligibility boundary. The traced consumers include early features, launch risk, holder graph, signal hardening, flow/lifecycle projections when supplied raw observations; replay/research also consumes the same stream. | `collection_mode`/promotion semantics are persisted as metadata but are not a shared provider-neutral production-input policy. | A future caller can accidentally feed unpromoted GMGN evidence into score/risk/lifecycle inputs; candidate collection also follows the normal candidate persistence seam. | Application evidence policy, with explicit production-vs-research call sites. | Add one provider-neutral shadow eligibility boundary; production-facing projections exclude unpromoted `LIVE_SHADOW`, while replay/research explicitly include it. Do not delete observations or add GMGN branches. | Baseline vs baseline plus real-external GMGN `LIVE_SHADOW` yields identical decision outputs; GMGN remains visible to readiness/replay/ablation/diagnostics. |
| Statistical sample accounting | `ExternalProviderReadinessReport` records `real_observation_count` and `unique_token_count`; readiness gating already uses unique tokens, but the report has no explicit independent-unit field and raw polling volume is prominent. SQL/report timestamps use `occurred_at` or `observed_at` for observation inventory. | Raw append-only observation volume and independent alpha-validation units are not named separately in the readiness contract. | Repeated snapshots can be mistaken for independent evidence by operators or future promotion code; 100 polls of one token must never satisfy a token/outcome gate. | `historical_dataset.ExternalProviderReadinessReport` and its API/SQL projections. | Expose a provider-neutral independent sample metric derived from unique token/cohort units; retain raw history; use the independent metric in sufficiency checks; do not create labels. | 100 identical real snapshots for one token => raw 100, unique 1, independent 1 (not 100), `INSUFFICIENT_SAMPLES`; multiple unique tokens count independently; fixtures/replay/redacted rows do not count. |
| GMGN identity and snapshot semantics | `_observation` falls back to collection time in `source_id` when no provider event time exists, while some info/rank mappings pass token creation/open timestamps as `occurred_at`. Aggregate top holders/traders and current-state endpoints have no explicit semantic marker. | Event, snapshot, and aggregate observations are not classified in the adapter contract. | A current-state poll can look like an exact market event or an independent alpha event; event-time replay can be contaminated by provider timestamps with the wrong meaning. | GMGN observation construction and documentation; canonical `Observation` time fields remain authoritative. | Mark endpoint semantics explicitly; keep `occurred_at` null when event time is unknown; use stable provider IDs only for true events; use collection-time identity only for historical snapshots, never as exact event time. | Endpoint classification/source IDs/occurred-at behavior are deterministic across repeated polls and preserve UNKNOWN event-time quality. |
| Runtime GMGN provider state | Registry metadata has `enabled=False` because the provider is optional, while the read API has a partial GMGN settings special case; the generic operations projection still reads static metadata. No explicit `configured` boolean is exposed in the provider-health response. | Static catalog metadata and runtime `Settings` are not resolved through one canonical provider-state projection. | UI/API can report GMGN disabled even when the worker adapter is configured, or cannot distinguish enabled-but-unconfigured from configured-but-unprobed. | Provider metadata/runtime health projection (`provider_metadata`, read API, operations projection if in scope). | Reuse the existing projection; make runtime enabled/configured/health states truthful without exposing credentials. Add proof for disabled, missing key, configured-unprobed, and successful collection. | Four settings/health cases assert enabled, configured/credential state, UNKNOWN/NOT_CONFIGURED, and HEALTHY without secret leakage. |
| Lifecycle regression boundary | Existing `GraduationAwareRouteAnalyzer` hardening separates BONDING/DEX route, rejects raw vendor `DEX_LIVE` authority, and filters weak external evidence when stronger reconciled evidence exists. | No failing gap is established in the current implementation. | Unnecessary lifecycle edits could reintroduce provider authority or route conflation. | Existing canonical launch lifecycle module and tests. | Run regression tests; make zero production lifecycle changes unless a failing test proves a root-cause gap. | BONDING != DEX_ROUTE; provider graduation != verified liquidity; verified liquidity != first verified swap; weak external evidence cannot override stronger canonical evidence. |
| Helius factual taxonomy | Existing `HeliusObservationNormalizer` is the sole webhook/stream normalization path and already maps factual event types with ambiguity handling. | No failing taxonomy case is established in this sprint audit. | Expanding a correct normalizer would create unnecessary provider-specific behavior or directional conclusions. | Existing Helius normalizer/tests. | Preserve the current taxonomy and add only regression protection if needed. | Explicit synonyms map deterministically; conflicting/ambiguous labels remain `UNKNOWN`; no bullish/bearish/buy/sell/rug conclusions. |

## Traced GMGN observation consumers

The audit traced these canonical kinds before implementation:

| Kind | Existing persistence/readiness use | Raw decision/research consumers found | Shadow handling target |
| --- | --- | --- | --- |
| `candidate.discovery` | Discovery collector, candidate persistence, readiness counts, timeline/read views. | Candidate discovery is an application input seam; no scorer directly reads the row. | Preserve canonical observation persistence; prevent unpromoted evidence from becoming production decision input/state where the existing policy boundary requires it. |
| `market.snapshot` | Observation persistence/read views, readiness, price-role resolution. | Early features, signal hardening, flow analysis, launch/replay research, opportunity research. | Production analyzers use the shared eligibility policy; replay/research explicitly retain shadow rows. |
| `creator.profile` | Readiness counts and canonical observation persistence. | Launch-risk/signal-hardening generic payload scans when supplied. | Exclude unpromoted shadow rows from production projections; keep research visibility. |
| `wallet.top_traders` | Readiness counts and canonical observation persistence. | Launch-risk generic actor scans and research inputs when supplied. | Do not equate provider labels with internal smart-wallet authority; exclude unpromoted shadow rows from production projections. |
| `social.caller_consensus` | Readiness counts and canonical observation persistence. | No direct typed `SocialCallObservation` conversion; caller research remains separate. | Keep as supporting shadow evidence only until promotion. |
| `market.holder_data` | Readiness counts and canonical observation persistence. | `HolderGraphAnalyzer` holder concentration/graph inputs. | Exclude from production holder/security projections while preserving research/readiness. |
| `security.provider_risk` | Readiness counts and canonical observation persistence. | Provider risk is explicitly marked supporting evidence; deterministic token-security authority remains `onchain.token_metadata`. | No direct deterministic verdict; exclude unpromoted rows from production raw-evidence projections. |

This matrix is the pre-implementation record. Subsequent changes must be
small, test-led, and limited to the owners above.

## GMGN numeric-domain audit

The adapter keeps the non-negative parser for physical quantities and provider
ratios. Only the documented trader `profit` mapping uses the signed parser.
Unmapped provider fields such as `pnl`, `realized_pnl`, `unrealized_pnl`,
`profit_usd`, and `profit_pct` are retained only in the redacted raw payload;
they are not assigned an invented domain.

| Domain | Normalized fields |
| --- | --- |
| `NON_NEGATIVE` | `price`, `liquidity`, `market_cap`, `volume_1h`, `buy_volume`, `sell_volume`, `creator_token_balance` |
| `SIGNED` | trader `profit` |
| `BOUNDED_RATIO` | `fresh_wallet_rate`, `top_10_holder_rate`, `creator_hold_rate`, `amount_percentage`, `buy_tax`, `sell_tax`, `dev_team_hold_rate`, `creator_balance_rate`, `suspected_insider_hold_rate`, `rat_trader_amount_rate`, `bundler_trader_amount_rate`, `rug_ratio`, `launchpad_progress` |
| `COUNT` | `holder_count`, `buys_1h`, `sells_1h`, `swaps_1h`, `smart_degen_count`, `renowned_count`, `smart_money_wallet_count`, `kol_count`, `sniper_count`, and derived `trader_count` |
| `UNKNOWN_DOMAIN` | Unmapped numeric provider fields and scalar status fields; raw redacted payload only, with no signed/non-negative inference |

Ratio values remain provider values; this sprint does not coerce units or
promote provider classifications into canonical verdicts.

## Post-implementation result

- `_non_negative_decimal` remains the canonical parser for non-negative
  quantities; `_signed_decimal` is used only for trader `profit`. The focused
  adapter regressions cover negative, zero, positive, missing and malformed
  financial values plus rejected negative liquidity and holder percentages.
- `evidence_policy.production_observations` is the shared provider-neutral
  boundary. Production-facing early, risk, holder, flow, signal, correlation,
  price and lifecycle projections exclude unpromoted `LIVE_SHADOW`; replay and
  research callers explicitly opt in. Persisted observations and readiness
  inventory are unchanged and remain available for later ablation.
- A lifecycle regression initially failed when a GMGN shadow market snapshot
  changed the lifecycle projection. The smallest root-cause fix was applying
  the same shared policy at `GraduationAwareRouteAnalyzer`; existing canonical
  lifecycle invariants remain intact.
- Enrichment endpoints are classified as `SNAPSHOT` or `AGGREGATE` and leave
  `occurred_at` null when no provider event time is supplied. Collection time is
  used only in the deterministic observation identity, not asserted as event
  time. Rank discovery retains the provider's token-open timestamp because the
  canonical discovery port requires a candidate time; it is not a market-event
  claim.
- Readiness now exposes `independent_sample_count`, derived from unique
  provider token identities. One hundred retained polls of one token remain
  one independent unit and `INSUFFICIENT_SAMPLES`; no labels or neutral scores
  are manufactured.
- Read and operations provider projections derive GMGN runtime configuration
  from `Settings`, expose `enabled`/`configured` and fail closed to `UNKNOWN`
  when disabled, incomplete or unprobed. Secrets remain server-only.
