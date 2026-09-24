# Early Alpha Gap Analysis

Audit date: 2026-09-24
Repository: local `main` at `c29b84c` (`fix: report lifecycle cohorts by launch`)

## Scope and evidence posture

This audit started from the repository, not from the requested feature list.
The mandatory architecture, roadmap, research-extension, data-model,
provider, security, testing, and status documents were read before code was
considered. Existing implementations and tests were traced through discovery,
normalization, scoring, risk, stream integrity, persistence, alerts, paper
execution, replay, calibration, and promotion.

The repository is already a provider-independent Solana intelligence and
paper/shadow system. Its current evidence is engineering evidence, not a
profitability claim. The latest bounded Pump.fun forward artifact contains
`1278` launches, `121` MemeRadar-before-Dex leads, and no matured executable
winner labels. The checked-in synthetic winner-vs-rug fixture contains only
three records and is not evidence of real-world performance. The named case
studies (HITBUY, Agrippa, MONITOR, GENIUS, familiars, astro, SPIKE, JEANPHIL,
musebook) are not present as compliant historical replay samples.

No implementation was added before this audit was completed. The first
unresolved acceptance gate is real-data, out-of-sample validation with mature
outcomes; it is blocked by external data/provider access and elapsed outcome
horizons. Adding a second scoring, execution, or state engine before that gate
would duplicate existing owners and risk changing protected behavior.

## Gap matrix

| CURRENT CAPABILITY | EXISTING REUSABLE COMPONENT | GAP | PROPOSED CHANGE | RISK | VALIDATION METHOD |
|---|---|---|---|---|---|
| Canonical token identity is keyed by chain and address; lifecycle transitions are persisted and idempotent. | `identities.py`, `lifecycle.py`, `early.py`, `early_detection.py`, `early_runtime.py` | The requested names (`SHADOW_CANDIDATE`, `EARLY_ALPHA`, `AUTO_ELIGIBLE`, etc.) are not one public enum. Existing `EARLY_WATCH`, `ENTRY_READY`, and paper gates already express most of the behavior. | Add a thin versioned projection only if an external contract requires the requested labels; do not create a second state machine. | Divergent states could authorize or hide candidates incorrectly. | Transition/property tests, replay equivalence, and hard-gate tests for UNKNOWN and blocked evidence. |
| Provider-independent application ports exist for discovery, market data, on-chain data, risk, social, narrative, quotes, execution, and notifications. | `provider_contracts.py`, `composition.py`, `identities.py`, provider adapters | There is no exact common `ChainAdapter`/`LaunchpadAdapter` family, and Base plus unverified BNB/Base launchpad integrations are not enabled. | Extend existing ports only when a provider contract is verified and all discovery, security, liquidity, quote, and execution seams are available. Keep unsupported protocols disabled. | Guessed protocol IDs or incomplete security could create false-safe evidence. | Provider contract tests, decoder identity verification, fixture replay, and keyless doctor checks. |
| Ultra-early detection consumes raw protocol events, normalizes them, preserves provenance, and supports direct-chain versus fallback evidence. | `UltraEarlyDetector`, `early_runtime.py`, stream/replay infrastructure, Pump.fun adapters | A generic cross-chain snapshot scheduler with the full requested T+0 through T+24h schedule is not a single reusable component. Current bounded real collection is Pump.fun/Solana. | Reuse the existing scheduler/observation repository when a compliant feed exists; add no generic scheduler ahead of a real source. | Sparse or delayed data can look like early alpha and create look-ahead bias. | Event-time replay, snapshot timestamp tests, and real read-only bounded collection. |
| Event-time microfeatures calculate rates and accelerations for buys, sells, buyers, holders/flow proxies, price, liquidity, market cap, trade sizes, smart-wallet and cluster diagnostics. | `early_features.py`, feature snapshots, `FlowAnalyzer` | There is no explicit unified turnover/effective-liquidity feature family, age-cohort percentile normalizer, or complete 30m/1h fast-window set. | Extend the existing feature snapshot contract with configuration-driven diagnostics only after executable-liquidity and historical cohort data are available. | TVL, provider marks, and sparse windows can produce false momentum. | No-lookahead replay, fixture/property tests, quote-depth comparison, and OOS cohort calibration. |
| Flow, liquidity, impact, and sellability are already used by safety and early scoring. | `fast_safety.py`, `early_scoring.py`, `paper_execution.py`, quote ports | Requested turnover hypotheses are not validated and reported liquidity is not always executable liquidity. | Treat turnover as advisory evidence; require fresh route/quote depth for paper eligibility and never promote shadow thresholds directly. | High activity in a shallow or wash-traded pool can be mistaken for demand. | Sell simulation, slippage/impact tests, negative controls, and mature paper replay. |
| Wallet tracking, scoring, graph relationships, confluence, external-wallet evidence, and smart-money convergence exist. | `wallet_tracking.py`, `wallet_scoring.py`, `wallet_relationship.py`, `smart_money_convergence.py`, `confluence.py`, creator/holder graph | There is no autonomous historical wallet-discovery pipeline with measured copyability and a fully separated MEV/insider performance sample. | Build the research projection on top of existing wallet evidence only after compliant historical wallet and outcome data arrive; third-party labels remain corroboration. | PnL-only ranking, cabals, MEV timing, and survivorship can inflate alpha. | Time-split attribution, cluster-independence tests, copy-impact simulation, and LIVE_SHADOW promotion gates. |
| Wallet funding/relationship and creator/deployer evidence already support cluster and coordination diagnostics. | `wallet_relationship.py`, `creator_graph.py`, `signal_hardening.py`, holder graph | The requested full funding-hop/bridge/CEX fingerprint set is not uniformly available across chains. | Add fields to existing graph evidence only when provenance and chain-specific source contracts are known. | Missing evidence must remain UNKNOWN; inferred independence can be unsafe. | Same-parent cabal fixture, unrelated-wallet convergence fixture, and provider disagreement tests. |
| Supply, concentration, authority, sellability, creator, bundle/sniper, lock, and token security evidence are already represented across risk and hardening paths. | `holder_graph.py`, `creator_graph.py`, `token_security.py`, `fast_safety.py`, `signal_hardening.py`, GoPlus adapter | There is not one cross-chain `SecurityEvidence` projection with every requested field; BNB/Base coverage is incomplete and optional external evidence is blocked. | Normalize missing fields into the existing risk/evidence model; keep unknown distinct from PASS and preserve chain-specific checks. | A partial projection can accidentally turn unavailable evidence into safe evidence. | Security contract tests, failed sell simulation, authority/concentration fixtures, and fail-closed paper tests. |
| Social attention, social calls, narrative matching, catalyst evidence, and freshness/quality fields exist as provider-independent seams. | `social_intelligence.py`, `narrative.py`, `narrative_matcher.py`, `narrative_catalyst.py`, social ports | Compliant X/Telegram data and a validated cross-token narrative-cluster/re-entry sample are unavailable. | Reuse existing social/catalyst projections when credentials and provenance are available; do not let ticker-only or LLM output authorize execution. | Bot/duplicate content and ticker collisions can contaminate a candidate. | Address-attribution tests, age normalization replay, provider disagreement fixtures, and social-off tests. |
| AlphaScore, early scoring, confidence, risk, and decision policy are deterministic, versioned, explainable, and separated from execution. | `alpha_strategy.py`, `early_scoring.py`, `decision_engine.py`, `fast_safety.py`, `strategy_promotion.py` | The requested `AIS`, `SafetyConfidence`, and `OpportunityConfidence` labels are not one canonical projection; overlapping score systems already exist. | Prefer a reporting/projection layer over a new scorer, and only consolidate after OOS evidence identifies one source of truth. | Weight drift or two scores disagreeing could alter alerts or gates silently. | Config-hash persistence, score-component snapshots, ablation, OOS calibration, and promotion-gate tests. |
| Evidence provenance, timestamps, stream cursor/gap/recovery, protocol identity verification, replay, and commitment state are implemented. | `stream_integrity.py`, chain events, protocol registry, evidence models | A general multi-provider consensus projector is not complete; live provider disagreement data are unavailable. | Extend the existing evidence records with explicit disagreement only when two trusted sources are present. | Treating disagreement as a vote can hide a bad source; unresolved gaps must remain fail-closed. | Synthetic gaps, replay equivalence, provider conflict fixtures, and real shadow health counters. |
| Alerts are outboxed, deduplicated, rendered from early-alpha evidence, and separated from market-data processing. | `alert_pipeline.py`, `early_alpha_alert.py`, notification ports, Telegram adapter | Requested emoji/classes and transition wording are not a single public taxonomy; Telegram credentials/acceptance are unavailable. | Extend the existing renderer and allowlist, preserving outbox idempotency and secret-free content. | Alert spam or leaking raw provider data could harm operations. | Renderer snapshots, dedupe tests, queue non-blocking tests, and credentialed external acceptance when available. |
| Paper sizing, quote freshness, sellability, impact, idempotency, restart recovery, shadow entry, and exit evidence share deterministic gates. | `paper_execution.py`, `shadow_entry.py`, `exit_engine.py`, `PaperAutoExecutionGate` | Live signing/auto execution is intentionally absent; the requested `AUTO_ELIGIBLE` path is not enabled. | Keep PAPER_AUTO and LIVE_SHADOW bounded; do not implement Phase 12/13 authority without explicit protected acceptance. | Any default change could enable live money or bypass risk. | Existing paper/idempotency/recovery tests, protected-mode assertions, and real read-only paper acceptance. |
| Replay, backtest, calibration, ablation, missed-winner/false-positive analysis, and `StrategyPromotionGate` exist. | `replay_harness.py`, `early_replay.py`, `early_benchmark.py`, `winner_vs_rug.py`, `calibration.py`, `early_failure_analysis.py`, `strategy_promotion.py` | There is no compliant historical sample for the named winners or matched controls; the current fixtures are synthetic and below promotion minimums. | Acquire/ingest compliant historical data through existing seams, then run time-split OOS evaluation without changing protected weights or modes. | Winner-only analysis, outcome leakage, and survivorship bias would invalidate the result. | Dataset provenance, no-lookahead tests, matched controls, sample gates, ablation, and `INSUFFICIENT_SAMPLES` when needed. |
| Observability and operational health cover provider latency, stream gaps, dedupe, shadow counters, API/worker health, and forward reports. | telemetry package, health/doctor scripts, stream health, Pump.fun forward artifacts, Compose stack | Live external SLOs and mature false-positive/negative rates are not available; current bounded collection is operational evidence, not statistical evidence. | Continue reporting operational counters and keep statistical fields unavailable rather than zero-filled. | Zero-filled missing metrics can be read as success. | `make verify`, provider doctors, bounded stack checks, and real-data monitoring with explicit freshness. |
| Identity, unknown-state, risk, cabal, convergence, stream, replay, and paper regressions have broad coverage. | `tests/unit`, `tests/contract`, `tests/integration`, `tests/property`, `tests/smoke` | The exact requested 15-same-ticker regression and exact alert/state names are not necessarily represented as one test contract. | Add focused tests only alongside a justified projection or provider extension; do not add tests for a duplicate architecture. | Test names can imply support that implementation/evidence does not provide. | Canonical identity isolation, UNKNOWN high-AIS blocking, cabal discount, independent convergence, and renderer snapshots. |

## Audit decision

The minimum safe change at this checkpoint is documentation and durable
recovery state, not another parallel engine. The repository already has the
owners needed for the locally complete portions of the roadmap. The remaining
high-value claims require external authority or time: compliant historical
chain/social/wallet data, mature outcomes, multi-provider acceptance, and
credentialed Telegram/production-like read-only validation.

Protected modes remain unchanged:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

The next implementation checkpoint is therefore verification of the existing
HEAD and continued external-data readiness. If new data makes a gap measurable,
the smallest change should extend the existing feature/evidence/replay owner;
it should not introduce a second score, lifecycle, execution, or provider
framework.

## Verification checkpoint

The audited tree passed the local quality gates:

- `git diff --check`: PASS
- `make lint`: PASS
- `make typecheck`: PASS (`146` source files)
- `make test`: PASS (`1444 passed, 21 skipped, 7 warnings`; coverage report
  total `79%`)
- `make verify`: PASS; it repeated the Python gates, then passed the frontend
  CSS contract (`290` classes / `59` files), frontend lint, TypeScript,
  frontend tests (`24` files / `83` tests), Compose config, secret scan,
  migration check (`0011_collection_checkpoints`, `27` tables), security
  review, and SBOM (`582` components)

The security review correctly reports external container/npm/pip scans as
`NOT_RUN` and external acceptance as `BLOCKED_EXTERNAL`. No integration or
production read-only gate was claimed because the required external database
and deployment credentials are not present.

The host exposes `.codex/` as read-only. Attempts to create the requested
`.codex/CURRENT_TASK.md` and `.codex/VERIFICATION.md` were denied with a
read-only filesystem error. The audit report and this verification record are
therefore durable under `docs/reports/`; this filesystem limitation is an
environment blocker, not an application failure.
