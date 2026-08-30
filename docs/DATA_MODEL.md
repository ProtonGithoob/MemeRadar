# Data Model

This is the canonical logical model. Physical schemas may evolve through migrations, but names/relationships should remain recognizable.

## Core entities

### tokens
- id (UUID)
- chain (`solana` initially)
- mint_address (unique)
- token_program
- symbol/name/decimals
- created_onchain_at nullable
- first_seen_at
- metadata_uri/status
- creator_wallet nullable
- created_at/updated_at

### pools
- id
- token_id
- venue/program
- pool_address unique
- quote_mint
- created_onchain_at
- first_seen_at
- status

### candidates
- id
- token_id unique active scope
- state
- discovered_at
- discovery_source
- latest_score_id nullable
- latest_risk_id nullable
- state_changed_at
- rejection_reason nullable

### observations
Append-oriented normalized observations.
- id
- candidate_id/token_id nullable
- kind
- provider
- source_id
- occurred_at nullable
- observed_at
- ingested_at
- parser_version
- quality_state
- raw_payload_hash/reference nullable
- normalized_payload JSONB
- unique(provider, kind, source_id) where possible

### feature_snapshots
- id
- candidate_id
- as_of
- expires_at
- feature_version
- completeness/confidence
- values JSONB
- provenance JSONB
- config_hash

### risk_assessments
- id
- candidate_id
- as_of/expires_at
- risk_version
- disposition: PASS/WARN/BLOCK/UNKNOWN
- hard_blocks JSONB
- warnings JSONB
- penalties JSONB
- evidence_refs JSONB
- config_hash

### score_snapshots
- id
- candidate_id
- as_of
- model_version
- strategy_name
- strategy_version
- alpha_score numeric 0..100
- confidence numeric 0..1
- components JSONB
- penalties JSONB
- reason_codes JSONB
- feature_snapshot_id
- risk_assessment_id
- config_hash

`strategy_name` and `strategy_version` identify the deterministic strategy
that produced the score; `model_version` remains for backward compatibility.
Existing rows are backfilled as `legacy` by migration
`0003_score_strategy_identity`. Every new score projection must retain all
three identity/config fields so strategy switching is explicit in replay and
audit records.

### state_transitions
- id
- candidate_id
- from_state/to_state
- reason_codes JSONB
- score_snapshot_id nullable
- risk_assessment_id nullable
- occurred_at
- correlation_id

## Social

### social_authors
- id
- provider
- provider_author_id unique/provider
- handle/display fields
- first_seen_at
- latest_metrics JSONB
- trust_score
- trust_version
- confidence
- labels JSONB

### social_mentions
- id
- token_id/candidate_id
- author_id
- provider_post_id unique/provider
- posted_at/observed_at
- text_fingerprint
- referenced_mint/ticker/canonical_links
- metrics JSONB
- duplicate_cluster nullable
- spam_probability nullable
- source_reference nullable

The Phase 5.1 warm-path `SocialMention` is the provider-independent form of a
read-only post. It preserves the provider post ID, author ID, ordered
`posted_at`/`observed_at`/`ingested_at` timestamps, `Provenance`, quality state,
first referenced mint/ticker and HTTPS-only canonical links. Metrics are
normalized to bounded non-negative integers where present; the deterministic
`text_fingerprint` removes URL and mention presentation differences so
copied-text posts can share a `duplicate_cluster`. Exact duplicate source IDs
are idempotently collapsed and conflicting records are rejected. The
`SocialRestAdapter` performs no persistence, browser scraping or write call;
physical social tables remain the later persistence target.

### author_trust_snapshots
- id
- provider_author_id
- as_of/expires_at
- registry_tier
- trust_score/confidence
- mention_count
- engagement_quality/duplicate_ratio/spam_ratio/coordination_ratio
- components JSONB
- penalties JSONB
- provenance/evidence_refs/reason_codes JSONB
- config_hash/version

The Phase 5.2 warm-path `AuthorTrustScore` uses explicit registry/KOL policy
plus bounded mention evidence. It never promotes an unlisted author, treats
follower count alone as trust, or grants execution authority. Non-fresh,
future, conflicted or invalid evidence produces zero confidence and no fresh
positive score.

### social_velocity_snapshots
- id
- token_id/candidate_id/referenced_mint
- as_of/expires_at
- mention_count
- window_counts JSONB (`1m`, `5m`, `15m`)
- unique_author_counts JSONB (`1m`, `5m`, `15m`)
- engagement_quality
- duplicate_ratio/spam_ratio/coordination_ratio
- coordination_clusters JSONB
- score/confidence
- components JSONB
- penalties JSONB
- provenance/evidence_refs/reason_codes JSONB
- config_hash/version

The Phase 5.2 warm-path `SocialVelocityScore` counts event-time mentions in
the windows `(now - window, now]`, deduplicates equivalent source deliveries,
excludes future events and keeps missing metric evidence distinct from zero
engagement. Copied-text bursts and the bounded `bot_heuristic_ratio` are
coordination diagnostics, not claims of common control or bot identity. No
physical social migration is required for the keyless application checkpoint.

### narrative_snapshots
- id
- candidate_id
- as_of
- provider/model
- schema_version
- narrative/topic
- novelty/organic/promo/sentiment values
- confidence
- evidence_refs
- prompt/config hash
- cost/usage metadata

The Sprint 5.3 warm-path `NarrativeSnapshot` is the strict advisory form of
this record: bounded narrative/topic text, `0..1` novelty/organic/promotional/
uncertainty/confidence values with the organic+promotional sum capped at one,
strict organic-assessment and sentiment enums, validated token/cost usage, a
deterministic `sha256` cache key over the canonical sanitized input, evidence
references restricted to supplied input IDs, schema/config hashes, quality
state and expiry. The `NarrativeAnalyzer` gateway records deterministic
fallback snapshots with explicit reason codes (`NARRATIVE_TIMEOUT`,
`NARRATIVE_SCHEMA_INVALID`, `NARRATIVE_PROVIDER_UNAVAILABLE`,
`NARRATIVE_EVIDENCE_NOT_FRESH`, `NARRATIVE_UNAVAILABLE`) when the optional LLM
is unavailable; snapshots are always advisory and never execution-eligible.
Physical narrative persistence remains a later roadmap task.

### social_calls
- id/source post IDs
- author_id
- token_id/referenced_mint
- called_at/observed_at/ingested_at
- provenance
- quality_state
- evidence_refs
- config_hash/version

### social_call_outcomes
- social_call_id
- as_of/expires_at
- forward_returns JSONB by fixed horizon
- MFE/MAE JSONB by fixed horizon
- horizon_states JSONB (`COMPLETE`, `PARTIAL`, `UNKNOWN`, `INVALID`)
- rugged/liquidity_collapsed nullable flags
- token_age_at_call_seconds nullable
- quality_state/risk_quality_state
- confidence
- provenance/evidence_refs/reason_codes JSONB
- config_hash/version

### call_performance_snapshots
- id/author_id
- as_of/expires_at
- reference_horizon
- sample_count/known_outcome_count
- hit_rate/median_forward_return/median_mfe/median_mae
- rug_avoidance_rate/median_token_age_at_call_seconds
- score/confidence/uncertainty
- components JSONB
- provenance/evidence_refs/reason_codes JSONB
- config_hash/version

The E5.4 provider-independent warm path models historical author calls as
`SocialCall`, reconstructs only post-call market/risk outcomes, and keeps
missing horizons and missing rug/liquidity evidence nullable. Future-dated
observations are excluded and invalidate the result; equivalent duplicate calls
are collapsed with an explicit reason code and conflicting source IDs fail
closed. `CallPerformanceSnapshot` uses bounded shrinkage toward neutral `50` and
minimum sample/confidence gates. These snapshots are advisory evidence only;
they cannot promote a registry tier, clear a risk gate or authorize execution.
No physical migration is introduced for the keyless checkpoint.

## Wallet intelligence

### wallets
- id
- chain
- address unique
- labels JSONB
- creator_relation flags
- first_seen_at

Sprint 4.1's warm-path registry is represented by provider-independent
`TrackedWallet` entries before persistence. The address is canonical Solana
base58, the label/labels and tier are explicit operator/configuration data,
and inactive or blocked entries cannot contribute activity. Registry entries
are bounded and idempotent; a conflicting duplicate address is rejected.

### wallet_activities
- id
- wallet_id
- token_id
- signature + instruction discriminator unique
- action BUY/SELL/TRANSFER/etc
- occurred_at
- base/quote amounts
- effective_price nullable
- pool/venue
- observation_id

The application `WalletActivity` normalizes allow-listed wallet activity
observations into BUY/SELL records. It preserves `occurred_at`, `observed_at`
and `ingested_at` separately, keeps the source `Provenance` and quality state,
and deduplicates equivalent source deliveries. Quantity is always positive;
quote amount and effective price are nullable rather than defaulted to zero.
Unknown wallets, malformed identities, conflicting source IDs and over-bound
activity batches fail closed.

`WalletTrackingAnalyzer` reconstructs each watched wallet/token position using
FIFO lots. Only matched slices with known buy cost and sell proceeds produce
realized PnL; open cost basis and aggregate realized PnL remain nullable when
financial evidence is incomplete or an unmatched sell exists. Every matched
slice retains both trade source references, hold seconds and reason codes.
Token age at the first entry is nullable unless a valid token creation
timestamp is supplied. Rug exposure is `true` only for a valid fresh
post-entry rug outcome; missing, stale, conflicted or invalid risk evidence
remains nullable and non-fresh. The warm-path snapshot is explainability data
only and has no execution authority.

### wallet_performance_snapshots
- id
- wallet_id
- window
- as_of
- trades/sample_count
- realized_pnl
- win_rate
- median_return
- early_entry_rate
- rug_exposure_rate
- median_hold_time
- manipulation_penalties
- smart_wallet_score
- tier
- confidence
- scoring_version

The Sprint 4.1 snapshot is a warm-path precursor to this persisted performance
table. It records wallet label/tier, buy/sell and matched counts, open quantity,
unmatched sell quantity, FIFO round trips, realized PnL, median hold duration,
token age, rug exposure, confidence, expiry, quality state, provenance,
reason codes and config/version metadata. Physical wallet migrations remain a
later persistence task; no schema migration is required for this keyless
application checkpoint.

Sprint 4.2's warm-path `SmartWalletScore` aggregates completed round trips
across tokens by wallet inside a bounded rolling window. It stores the raw
sample/known-outcome counts, win rate, aggregate realized PnL, median return,
early-entry rate, rug-avoidance rate, manipulation penalty, normalized
component scores, recommended tier, confidence, expiry, quality state,
provenance, evidence references, reason codes and config/version metadata.
Missing component evidence remains nullable. Duplicate round trips are
deduplicated by immutable token/wallet/timestamps/quantity/source evidence;
future outcomes are excluded and mark the score invalid rather than becoming
look-ahead data. A recommendation never mutates the explicit registry tier.

### smart_money_confluence_snapshots
- id
- token_id
- as_of/expires_at
- confluence_version
- smart_money_score/confidence
- qualified_wallet_count/independent_cluster_count
- entry/exit wallet and cluster counts
- confluence/distribution event counts
- components JSONB (`entry_breadth`, `entry_quality`, `independence`, `exit_pressure`)
- penalties JSONB (`distribution`)
- events JSONB
- provenance/evidence_refs/reason_codes JSONB
- config_hash

Sprint 4.3's warm-path `ConfluenceAnalyzer` consumes fresh `SmartWalletScore`,
`WalletTrackingSnapshot` and the existing bounded `WalletGraphSnapshot`
relationship seam. Completed FIFO slices produce entry/exit event records;
fresh graph edges are unioned transitively so wallets connected through an
observed intermediary count as one independent cluster. Missing or non-fresh
graph evidence for multiple qualified wallets is `UNKNOWN`, not proof of
independence, and confluence is withheld. `TokenSmartMoneyScore` retains all
event timestamps, cluster IDs, member addresses, provenance, evidence,
components, penalties, confidence, quality, reasons and config/version data.
It is advisory only and has no execution authority. No physical migration is
required for this keyless warm-path checkpoint; persistence remains a later
wallet-intelligence task.

### wallet_graph_edges
- id
- from_wallet_id/to_wallet_id
- relation_type (funded_by/transfer/co_buy/etc)
- token_id nullable
- first_seen/last_seen
- weight/confidence
- evidence_refs

The warm-path `HolderGraphAnalyzer` materializes these relationships from
provider-independent transfer/funding observations before persistence. The
bounded analysis defaults to one graph hop, at most 100 holder rows, 500
edges and 500 nodes. Each normalized edge retains the relation type, aggregate
amount/count, first/last event time, confidence, reason codes and every source
ID used to build it. Pool, program and system addresses are classified and
retained for auditability but are not treated as holder ownership; configured
pool addresses and the creator relation are explicit configuration/evidence,
not inferred from an arbitrary string.

## Protocol lifecycle evidence

### protocol_lifecycle_observations

This is a logical view over the append-only `observations` table, not a new
physical migration for the keyless extension.

- kind: `protocol.lifecycle`
- token_id (canonical UUID)
- venue and source_id
- raw event_type and canonical protocol_event_type
- event_origin (`NATIVE` or `DERIVED`)
- schema_version and parser_version
- occurred_at/observed_at/ingested_at
- pool_id/pool address and quote mint when present
- normalized_payload JSONB with safe protocol fields
- quality_state and provenance

Schema-v2 lifecycle events cover launch, trade, bonding-curve progress,
graduation, migration, pool creation, creator-fee claims and fee-recipient
changes. A reliable `bonding_curve_progress_bps` value is retained only in the
inclusive `0..10000` range. `WHALE_TRADE` is a derived classification and must
never be stored or explained as a native protocol fact. Duplicate source
deliveries retain the same deterministic observation identity so persistence
can apply its idempotency policy without losing replay evidence; event-time
ordering is independent of delivery order.

Graduation/migration and creator-fee/recipient observations are timeline,
risk and exit evidence only. They do not have an intrinsic positive or
negative score, and missing or non-fresh critical evidence remains
`UNKNOWN`. Phase 6 correlation consumes these observations alongside social,
wallet and market evidence; no lifecycle observation can authorize execution
or clear a deterministic hard risk gate. No physical protocol migration is
introduced for this warm-path checkpoint.

## Correlation and launch micro-features

### correlation_window_snapshots (logical E6.0 view)

E6.0 emits immutable application snapshots over the existing append-only
observations and application contracts. This is a logical replay view; it
does not add a physical table or migration.

- token identity/mint
- as_of/expires_at
- required windows: `5s`, `15s`, `30s`, `60s`, `1m`, `5m`, `15m`
- event/source counts and source-diversity confidence
- unique buyers/sellers and buyer arrival rate
- buy/sell quote volumes, ratio, net flow and net-flow acceleration
- transaction/maker ratio and repeated-size/circular/rapid-round-trip ratios
- liquidity, liquidity delta/acceleration and nullable tracked-supply percentage
- protocol lifecycle counts and nullable bonding-curve progress basis points
- independent smart-money entry clusters and weighted entry quality
- creator/related-wallet sell pressure
- risk disposition and critical evidence quality
- feature/snapshot confidence, quality state, reason codes and version
- provenance, evidence references and configuration hash

Window membership is inclusive of the end and exclusive of the start:
`(as_of - duration, as_of]`. Event time is authoritative, with observed,
ingested, provider and source tie-breakers. Equivalent duplicate deliveries
are idempotently collapsed; conflicting reuse is invalid. Future event,
observed or ingested timestamps are excluded and invalidate confidence.
Missing critical risk evidence, insufficient samples and fewer than the
configured independent source categories remain `UNKNOWN`/low confidence.
Correlation is advisory and has no execution authority; persistence and
final score/decision snapshots remain later Phase 6 work.

## AlphaStrategy and AlphaScore v1

Research extension E6.1 emits an immutable logical `StrategySnapshot` from a
`FeatureSnapshot`, matching `RiskAssessment` and an explicit mode-safe
`StrategyPolicy`. The snapshot retains:

- strategy name/version and configuration hash;
- candidate, feature-snapshot and risk-assessment references;
- the seven normalized components: `SmartMoney`, `OnChainSafety`,
  `LiquidityQuality`, `OrganicFlow`, `SocialVelocity`, `HolderQuality` and
  `Momentum`;
- weighted components, pre-penalty raw score, post-penalty score suggestion,
  bounded penalties, confidence and confidence adjustment;
- risk disposition/hard blocks, quality, reason codes, evidence references and
  provenance.

The initial weights are 25%/20%/15%/15%/10%/10%/5% in the order above. Missing
components use an explicit neutral value only with a confidence reduction;
malformed values fail closed. Risk `BLOCK`, `UNKNOWN`, stale and conflicted
evidence remain visible and cannot be cleared by the strategy. The result is
always advisory and `execution_eligible()` is permanently false. Physical score
rows carry explicit strategy identity through migration
`0003_score_strategy_identity`; final candidate recomputation and decision
state orchestration remain later Phase 6 work.

## Market / holder data

### market_snapshots
- id
- token_id/pool_id
- as_of
- price/liquidity/market_cap nullable
- buy/sell volume windows
- unique buyer/seller windows
- trade counts
- price impact metrics nullable
- provider

### holder_snapshots
- id
- token_id
- as_of
- total_holder_count nullable
- top1/top5/top10 concentration
- clustered_top concentration nullable
- provider
- data JSONB for bounded top holders

Holder concentration values are Decimal ratios in the inclusive `0..1` range.
`top1`, `top5` and `top10` are nullable when valid percentage evidence is
missing or incomplete; `top10` may use a provider-supplied normalized summary
only when fewer than ten valid holder rows are available. The bounded data
payload records holder ranks, amounts/percentages, address classifications,
excluded pool/program/system addresses, graph clusters and source evidence
references. Every snapshot also preserves quality state (`FRESH`, `STALE`,
`UNKNOWN`, `CONFLICTED` or `INVALID`), expiry and config/version metadata;
non-fresh states never become safe complete evidence.

### organic_flow_snapshots
- id
- token_id
- as_of/expires_at
- flow_version
- organic_flow_score 0..100 nullable when critical evidence is unknown
- confidence 0..1
- liquidity/depth/change metrics nullable
- unique maker, transaction/maker, repeated-size, circular-flow and rapid-round-trip metrics
- sellability and price-impact quote metrics nullable
- penalties JSONB
- reason_codes/evidence_refs
- provider/config metadata

The warm-path Sprint 3.3 `FlowAnalyzer` derives this record from bounded
normalized market/trade observations and optional application `QuoteSnapshot`
values. `transaction_maker_ratio` is a non-negative transaction-to-maker
ratio; the other proportion metrics are inclusive `0..1` Decimal values.
Summary trade observations may supply counts and volumes, but repeated-size,
circular-flow and rapid-round-trip fields remain nullable until row-level
maker evidence exists. Quote freshness is retained separately from overall
flow quality so unsupported sellability is never treated as a successful
sellability check. Organic-flow snapshots are advisory evidence and do not
authorize orders.

## Trading

### portfolios
- id
- mode PAPER/LIVE
- currency
- initial_balance
- current_balance derived/reconciled

### orders
- id
- portfolio_id
- candidate/token_id
- mode PAPER/LIVE
- side
- state
- idempotency_key unique
- requested_amount
- requested_at
- quote_snapshot JSONB
- risk_snapshot JSONB
- provider_order/signature nullable
- reject/failure reason nullable

### fills
- id
- order_id
- occurred_at
- qty
- price
- fee breakdown JSONB
- slippage
- source

### positions
- id
- portfolio_id
- token_id
- mode
- state
- opened_at/closed_at
- quantity
- average_entry/average_exit
- realized_pnl
- high_watermark
- mfe/mae
- entry_decision_ref
- exit_decision_ref nullable

### exit_signals
- id
- position_id
- occurred_at
- severity
- action recommendation
- reason_codes/evidence
- score_before/after nullable

## Operations

### alerts
- id
- type
- candidate/position nullable
- severity
- payload JSONB
- dedupe_key
- state
- requested_at/delivered_at
- attempts

### provider_health
- provider + capability key
- checked_at
- state HEALTHY/DEGRADED/DOWN/UNKNOWN
- latency/rate-limit/quota/freshness metadata
- error_class redacted

### audit_events
Immutable operator/system-sensitive audit log.
- id
- actor
- action
- target
- before/after JSONB redacted
- occurred_at
- correlation_id

### config_versions
- id/version
- created_at
- actor
- config_hash unique
- decision_affecting flag
- config JSONB with secrets excluded

### domain_events
- event envelope fields from ARCHITECTURE
- payload JSONB
- processing state where needed

### outbox
- id
- event/side_effect kind
- payload
- idempotency/dedupe key
- created_at
- available_at
- delivered_at nullable
- attempts/error metadata

## Research

### replay_runs
- id
- dataset/config/model versions
- start/end event time
- state
- metrics/results JSONB
- code commit SHA

### outcome_labels
- candidate/token
- reference timestamp
- horizons
- forward returns
- MFE/MAE
- liquidity/rug/failure labels
- methodology version

## Indexing baseline

At minimum index:
- mint/pool/wallet addresses;
- candidate state + score ordering;
- all event-time columns used for window queries;
- observations `(kind, occurred_at)` and `(token_id, kind, occurred_at)`;
- wallet activities `(wallet_id, occurred_at)` and `(token_id, occurred_at)`;
- alerts state/available time;
- outbox delivery state/available time;
- audit occurred_at;
- GIN only where justified for JSONB queries.

Use BRIN/partitioning later only after measured volume justifies it.

## Retention principle

Do not delete the evidence required to reproduce decisions. High-volume raw payloads may be tiered/compacted while retaining hashes, normalized observations and research manifests.
