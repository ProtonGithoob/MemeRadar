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
- alpha_score numeric 0..100
- confidence numeric 0..1
- components JSONB
- penalties JSONB
- reason_codes JSONB
- feature_snapshot_id
- risk_assessment_id
- config_hash

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
- referenced_mint/ticker/url
- metrics JSONB
- duplicate_cluster nullable
- spam_probability nullable
- source_reference nullable

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

## Wallet intelligence

### wallets
- id
- chain
- address unique
- labels JSONB
- creator_relation flags
- first_seen_at

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
