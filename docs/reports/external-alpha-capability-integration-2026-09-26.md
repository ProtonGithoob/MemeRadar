# External alpha capability integration report

Date: 2026-09-26
Repository baseline: `62a44b63aa3c1119ad9c41aecb8785d4f627066aa`
Operating modes: `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`,
`MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`

## Result

The audit found that most requested functionality already belongs to existing
MemeRadar paths.  The local implementation extends those paths with P0
organic-flow evidence and short windows, then adds small provider-neutral
projections for the highest-value P2/P3 gaps.  No external source code was
copied, vendored, or added as a dependency.

Live provider and protocol acceptance is still blocked or insufficient for
Helius webhooks, Robinhood named streams, Par, HoodiePad/Doppler, NOXA,
Odyssey, and mature alpha/OOS claims.  Candidate EVM parsers remain
read-only and refuse unverified deployments.

## External repositories audited

| repository | audited commit | license | candidate use | decision |
|---|---|---|---|---|
| `CodeMuscle/solbeam` | `HEAD_NOT_LOCALLY_VERIFIED` | MIT | Helius push ingestion, watchlists, wallet views, price fallback | Concepts only; extend existing Helius/wallet/price owners |
| `Coinvoro/pumpr-bot` → `nktkass/pumpr-bot` | `HEAD_NOT_LOCALLY_VERIFIED` | MIT | Pump.fun flow, unique buyers, anti-wash, short momentum | Concepts only; reject autonomous execution |
| `SoCloseSociety/WhalegodTG` | `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6` | MIT | taxonomy, labels, duplicate/flood control | Concepts only; extend canonical events/outbox |
| `MadeOnSol/robinhood-chain-sdk` | `241d63978f35458ecac85507098278cdb2f1440d` | MIT | named streams, filters, resume, dedupe, quality | Provider-neutral descriptor only; live contract remains external |
| `pardotfamily/par` | `d2c1f44ce3096d6b80185eeb524c11bedda44e4a` | MIT | immediate Uniswap V4 launch lifecycle | Protocol-specific local parser; deployment verification required |
| `pardotfamily/par-sdk` | `bcbeda5b177e0b764654a663bd9c55f2a40142ba` | MIT | token-to-pool and multi-market mapping | Existing adapter seam retained; no SDK dependency |
| `bitgrass/Launchpad` | `2d3840ccdc86232009ff363f6be481ea7f73887a` | MIT | HoodiePad/Doppler V4, PoolKey/PoolId, limits/locks | Candidate read-only parser; no README address trusted |
| `nirholas/robinhood-trading-bot` | `HEAD_NOT_LOCALLY_VERIFIED` | Apache-2.0 | NOXA/Odyssey observation and quote-based paper concepts | Observation concepts only; no signer/executor copied |
| `nirholas/robinhood-chain-trading-bot` | `HEAD_NOT_LOCALLY_VERIFIED` | Proprietary / All Rights Reserved | lifecycle and kill-switch concepts | Reference only; no source copied |
| `nirholas/robinhood-toolkit` | `HEAD_NOT_LOCALLY_VERIFIED` | All Rights Reserved / proprietary | verified constants, adaptive logs, ticker safety, Multicall, MCP | Reference only; behavior independently implemented |

The exact license and reuse decisions are also recorded in
[`external-repo-license-matrix.md`](external-repo-license-matrix.md).  The
task forbade remote Git operations, so rows without a stable exposed full HEAD
remain explicitly ineligible for source reuse.

## Existing equivalent and integrated functionality

### Integrated into existing owners

- `FlowAnalyzer` now reports raw and organic turnover, suspected wash volume,
  organic-volume ratio, wallet entropy, funded-sibling ratio, repeat and
  round-trip ratios, unique buyers/sellers, and cluster-adjusted buyers.
- Existing early-feature windows now cover 10s, 30s, 1m, and 3m with unique
  buyer velocity, acceleration, organic net volume, and quality fields.
- `OrganicMomentumScorer` consumes the organic-flow evidence and reduces
  confidence when the observed flow is controlled or low quality.  No second
  score engine was created.
- `HeliusWalletWebhookAdapter` uses HMAC authentication, bounded replay
  protection, watched-wallet matching, existing observation normalization,
  provenance, slot/signature timestamps, token identity, USD value, and
  buy/sell classification.  It does not create a second wallet store.
- `SmartWalletLeaderboardProjection` ranks existing wallet scores with sample
  confidence, explainable reasons, copyability, MEV/insider evidence, and
  activity recency.  `estimated_total_pnl` remains observed realized PnL when
  no open-position estimate exists; it is not fabricated or extrapolated.
- `TransactionEventType` and `classify_transaction` add the requested broad
  taxonomy without forcing EVM events into Solana semantics.
- `WalletLabelRegistry` supports multiple evidence-only labels with source,
  confidence, verification time, and evidence references.
- `AlertStormController` extends the existing Telegram outbox with NORMAL,
  BURST, and DIGEST decisions, bounded dedupe, metrics, low-priority digest
  suppression, and priority bypass for actionable alerts.
- `PriceConsensusService` combines eligible observations with median price,
  freshness, source provenance, disagreement, quality, and confidence.  A
  stale or unreliable source is never silently promoted to fresh.
- `SubscriptionDescriptor` adds named Robinhood subscription scope, filters,
  cursor, event identity, health, and gap state.  Provider-level
  `(subscription_id,event_id)` identity remains separate from canonical chain
  identity.
- `AdaptiveEvmLogScanner` provides bounded range shrinking/growth,
  checkpointing, provider error classification, and canonical log dedupe.
- `EvmTokenMetadataRegistry` keys by `(chain_id, contract_address)` and
  requires bytecode, decimals, symbol, and name before accepting metadata;
  ticker collisions remain separate identities.
- Optional chain-configured `Multicall3` support is read-only, bounded, and
  rejects mismatched chain configuration.
- `ParLaunchAdapter`, `HoodiePadLaunchAdapter`, `DopplerV4LaunchAdapter`,
  `NoxaLaunchAdapter`, and `OdysseyLaunchAdapter` are protocol-specific
  read-only parsing contracts.  The existing verified deployment reader
  refuses unverified identities, so these are not claims of live support.
- `StrategyFailureModeRegistry` records hypotheses, required evidence,
  failure modes, minimum quality, hard blocks, and validation state for
  research reports only; it does not alter score decisions.

### Already stronger or equivalent; no parallel implementation

MemeRadar already owns the canonical Pump.fun decoder/replay path, wallet
graph, smart-money convergence, creator graph, supply quality, token security,
provider provenance, stream-gap recovery, decision/refusal evidence,
protected paper execution, execution kill switch, read-only MCP boundary,
copy-observation path, and alert/outbox idempotency.  External execution,
signing, private-key handling, social fabrication, external KOL authority, and
an additional Telegram/MCP/wallet/scoring engine were rejected.

## Before / after matrix

| capability | before | after | status | evidence |
|---|---|---|---|---|
| Helius push wallet tracking | Helius normalization seam; no push adapter | Authenticated, replay-safe watched-wallet adapter mapped to existing observations | `IMPLEMENTED_LOCAL` / live `BLOCKED_EXTERNAL` | `helius_stream.py`, focused tests |
| Smart-wallet leaderboard | Wallet scores existed; no ranked projection | Confidence-adjusted explainable leaderboard | `IMPLEMENTED_LOCAL` | `wallet_scoring.py`, focused tests |
| Unique buyer velocity | Existing windows and buyer counts | 10s/30s/1m/3m velocity, acceleration and cluster-adjusted buyers | `IMPLEMENTED_LOCAL` | `early_features.py`, focused tests |
| Wash trading detection | Existing repeated/circular/rapid heuristics | Funded siblings, entropy, repeats, round trips, explicit suspected volume | `IMPLEMENTED_LOCAL` | `flow_analysis.py`, `organic_momentum.py`, tests |
| Organic volume | No explicit raw/organic turnover pair | `gross_volume`, `organic_volume_estimate`, `wash_suspected_volume`, raw/organic turnover | `IMPLEMENTED_LOCAL` | `FlowMetrics`, tests |
| Transaction taxonomy | Normalized events without one broad category enum | Provider-neutral canonical taxonomy | `IMPLEMENTED_LOCAL` | `event_taxonomy.py`, tests |
| Wallet labels | Provider labels were evidence but not registry-backed | Multi-label source/confidence/verification registry | `IMPLEMENTED_LOCAL` | `wallet_labels.py`, tests |
| Alert flood control | Durable outbox and dedupe | NORMAL/BURST/DIGEST with priority bypass and metrics | `IMPLEMENTED_LOCAL` | `alert_pipeline.py`, tests |
| Price fallback/consensus | Quality-aware source seams | Freshness-aware median consensus and disagreement | `IMPLEMENTED_LOCAL` | `price_consensus.py`, tests |
| Robinhood named subscriptions | Shared stream/gap abstractions | Independent descriptor/filter/cursor/health/gap contract | `IMPLEMENTED_LOCAL` / live `BLOCKED_EXTERNAL` | `provider_contracts.py`, tests |
| Robinhood token-price quality | Existing quality states and price semantics | Consensus preserves FRESH/STALE/UNRELIABLE/UNKNOWN and disagreement | `EXTEND_EXISTING` | `price_consensus.py`, existing quality tests |
| Par launch support | Generic EVM lifecycle seam | Immediate TOKEN_CREATED → POOL_CREATED → DEX_ACTIVE parser | `IMPLEMENTED_LOCAL` / live `BLOCKED_EXTERNAL` | `evm_protocols.py`, parser tests |
| HoodiePad/Doppler support | No candidate parser | Read-only candidate fields for PoolKey/PoolId/hook/limits/locks/fees | `IMPLEMENTED_LOCAL_CONTRACT` / `BLOCKED_EXTERNAL` | `evm_protocols.py`; deployment remains TODO_VERIFY |
| NOXA support | No verified adapter | Read-only launch/pool/holder/dev/flow parser contract | `IMPLEMENTED_LOCAL_CONTRACT` / `BLOCKED_EXTERNAL` | `evm_protocols.py`; identity remains TODO_VERIFY |
| Odyssey support | No protocol-specific lifecycle | Separate curve, trade and graduation parser contract | `IMPLEMENTED_LOCAL_CONTRACT` / `BLOCKED_EXTERNAL` | `evm_protocols.py`; identity remains TODO_VERIFY |
| Real-quote paper fills | Protected provider-neutral paper path already existed | Reused existing quote/liquidity/fee/slippage/impact semantics | `ALREADY_EQUIVALENT` | Existing paper execution and quote tests |
| Decision/refusal journal | Existing replayable reason/evidence journal | No duplicate journal; rejected candidates remain outcome-trackable | `ALREADY_EQUIVALENT` | Existing decision evidence tests |
| Strategy failure-mode metadata | Research metadata was implicit | Versioned report-only registry | `IMPLEMENTED_LOCAL` | `strategy_promotion.py`, tests |
| Kill switch | Protected new-entry kill control existed | No copied execution code; existing control retained | `ALREADY_EQUIVALENT` | Existing control/security tests |
| Adaptive `eth_getLogs` | Generic EVM log reader; no adaptive window policy | Bounded adaptive scanner with checkpoint and dedupe | `IMPLEMENTED_LOCAL` | `evm_rpc.py`, tests |
| Ticker collision protection | Token identity primitives existed; ticker guard was implicit | Required metadata and address-keyed registry | `IMPLEMENTED_LOCAL` | `evm_rpc.py`, collision tests |
| Multicall | No optional batch-read port | Chain-configured read-only Multicall3 aggregate3 contract | `IMPLEMENTED_LOCAL` | `evm_rpc.py`, encoding/decoding tests |

## Copy and adaptation ledger

Copied source: none.  Adapted source: none.  No external dependency was
added.  All changed production behavior was independently implemented against
MemeRadar-owned domain/provider contracts.  Therefore there is no copied-file
attribution block beyond the audit/license records.

Independent implementation destinations:

- `packages/application/src/memeradar_application/flow_analysis.py`
- `packages/application/src/memeradar_application/early_features.py`
- `packages/application/src/memeradar_application/organic_momentum.py`
- `packages/application/src/memeradar_application/correlation.py`
- `packages/application/src/memeradar_application/wallet_scoring.py`
- `packages/application/src/memeradar_application/wallet_labels.py`
- `packages/application/src/memeradar_application/event_taxonomy.py`
- `packages/application/src/memeradar_application/price_consensus.py`
- `packages/application/src/memeradar_application/alert_pipeline.py`
- `packages/application/src/memeradar_application/provider_contracts.py`
- `packages/application/src/memeradar_application/strategy_promotion.py`
- `packages/providers/src/memeradar_providers/helius_stream.py`
- `packages/providers/src/memeradar_providers/evm_rpc.py`
- `packages/providers/src/memeradar_providers/evm_protocols.py`

Security treatment: no signing, private keys, credential reads, remote
binary loaders, arbitrary shell, transaction submission, or live-execution
path was imported.  Webhook authentication, replay bounds, timeouts,
provenance, raw decimal handling, address identity, and explicit unknown
states remain at the trust boundaries.

## Tests and verification

Focused slices passed during implementation, including P0 flow/windows and
the new wallet, labels, alerts, price, provider, EVM and protocol contracts.
The full Python test run reached **1507 passed, 21 skipped, 7 warnings** and
three security-review assertions failed only because the pre-existing dirty
`.env.example` contains a value matching the repository's high-confidence
Telegram-token pattern.  The value is intentionally not reproduced here and
the user-owned file was not changed.  Scanning `HEAD:.env.example` produced no
finding; all other local security checks passed.

`make lint` and `make typecheck` passed after the implementation.  The final
frontend CSS contract, frontend lint/typecheck/tests, Compose configuration,
migration check, and SBOM subtargets also passed (`83` frontend tests and
`582` SBOM components).  `make verify` stopped at its Python-test prerequisite
because of the same three security assertions; `secret-scan` independently
reported the same pre-existing `.env.example` finding.  Coverage from the
full Python run was 79% total; no claim is made that this is a mature
alpha-validation metric.

## Latency and performance

No representative live event benchmark was available, so no latency
improvement claim is made.  The synchronous path uses bounded windows and
bounded trade inspection; slower graph/provider analysis remains outside the
critical discovery path.  The organic-flow comparison is explicitly bounded
to the existing 500-trade policy window, with a recorded upgrade path if
replay profiling demonstrates a need.

## Provider dependencies and real-data acceptance

The new seams add no mandatory provider dependency.  Real acceptance still
requires configured Helius, Robinhood Chain, verified EVM deployment data and
read-only RPC/indexer access.  The intended order remains Solana Pump.fun,
Solana wallet webhook, Robinhood protocols, BNB Four.meme, Base, and
Ethereum.  Missing credentials, unverified protocol addresses, and absent
mature outcome samples remain `BLOCKED_EXTERNAL` or `INSUFFICIENT_SAMPLES`;
they are not converted into synthetic success.

The Pumpr-style `>=5 buys`, `>=2 SOL`, `30 seconds` hypothesis was not made a
production rule.  It is represented by the short-window evidence and must be
compared against raw, cluster-adjusted, and age-cohort-normalized variants in
LIVE_SHADOW before promotion.

## Remaining blockers

- `.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` are host-mounted
  read-only in this runtime; durable checkpoint evidence is stored in
  `docs/reports/` instead.
- The pre-existing `.env.example` edit causes the repository secret scan to
  fail; it was preserved as unrelated user work and its value was not exposed.
- No authenticated external provider samples or sufficient matured OOS data
  were available for real-data acceptance or an alpha claim.
- Exact stable full HEAD hashes for some public external repositories were not
  exposed by the allowed browser audit, and remote Git was prohibited.
- Par, HoodiePad/Doppler, NOXA and Odyssey deployment identities remain
  `TODO_VERIFY`; the existing log reader fail-closes on unverified identities.

## Next safe step

Resolve the pre-existing environment-file secret finding outside this change,
then run external scanners with configured access and begin read-only Solana
Pump.fun / Helius acceptance.  Keep the new evidence in LIVE_SHADOW and do not
promote heuristics or enable live execution without replay and OOS evidence.
