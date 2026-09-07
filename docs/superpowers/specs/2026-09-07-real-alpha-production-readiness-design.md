# Real Alpha Evidence & Production Readiness Design

**Date:** 2026-09-07
**Status:** APPROVED BY OPERATOR REQUEST
**Starting checkpoint:** Alpha Caller Task 15 complete at `2acf261`

## Goal

Move MemeRadar from engineering-complete/synthetic-research status to measurable real-world readiness by collecting compliant historical and live-shadow X/Telegram/provider evidence, reconstructing executable event-time outcomes, proving or rejecting incremental alpha out-of-sample, and hardening deployment/operations so production can run safely.

Production is explicitly staged:

1. `PROD_READ_ONLY` — real providers, ingestion, dashboards and Telegram alerts; no order creation.
2. `PROD_PAPER_AUTO` — fail-closed automated paper positions using real-time evidence; no signing or live orders.
3. `LIVE_MONEY_CANDIDATE` — code/ops/research evidence may be reviewed for a future operator-controlled live-money design. Reaching this state does **not** enable live trading.

Current target is stages 1 and 2 only. Protected modes remain unchanged unless a separate future design and explicit operator approval change them.

## Current truth

Alpha Caller Tasks 1-15 are implemented and verified locally, but checked-in alpha evidence remains `SYNTHETIC_REDACTED` / `INSUFFICIENT_SAMPLES`. This means engineering correctness is substantially stronger than real-alpha proof. The next roadmap must prioritize evidence acquisition, provider reliability, outcome reconstruction, live-shadow validation and production operations rather than adding speculative scoring features.

## Production invariants

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

- No private key, seed phrase, signer, swap submission, live copy-trading or sniper path is introduced by this roadmap.
- A production deployment is allowed to be read-only/paper-only.
- Social/KOL/wallet/provider evidence is corroborative, not execution authority.
- Missing critical evidence is `UNKNOWN` and fails closed.
- Event-time features must never contain future outcomes.
- Mark-price multiples without executable liquidity/impact support do not count as validated alpha.

## Workstream A — Real provider and social evidence

### Required capabilities

Implement/finish provider seams and doctors for:

- historical X/social call backfill through a compliant configured provider;
- live X/social observations through a compliant configured provider;
- Telegram historical/live message ingestion for explicitly configured channels/accounts;
- Solana chain/RPC and stream evidence;
- BNB and Robinhood generic-EVM reads;
- market/liquidity/executable quote sources;
- optional wallet/security enrichment.

Every provider must expose operational states such as:

```text
READY
DEGRADED
RATE_LIMITED
STALE
CONFIGURATION_MISSING
BLOCKED_EXTERNAL
UNSUPPORTED
```

Do not make optional social/provider services mandatory for application boot. Production readiness must clearly distinguish application health from evidence-capability readiness.

### Raw evidence requirements

For every external observation retain, subject to existing retention/privacy rules:

- provider/source identity;
- immutable external event/message/post ID where available;
- `occurred_at`, `observed_at`, `ingested_at`;
- edit/delete state where reliably supplied;
- chain-qualified asset/wallet identity when resolved;
- unresolved raw reference separately from canonical identity;
- parser/provider version and config hash;
- provenance and freshness;
- raw payload reference/hash when audit retention permits.

## Workstream B — Historical real dataset

Build a reproducible historical-real dataset, not a hand-curated winner list.

Required cohorts:

- extreme winners (20x/50x/100x where executable);
- moderate winners (5x-20x);
- ordinary winners (2x-5x);
- flat/no-repricing assets;
- severe losers;
- rugs/honeypots/non-sellable launches;
- high-attention false positives;
- late caller/KOL mentions;
- caller calls that failed;
- edited/deleted calls where the provider supplies reliable history.

The dataset must include both caller-discovered and token-discovered samples to avoid winner-only/caller-only selection bias.

### Initial sample adequacy guardrails

These are versioned acceptance guardrails, not claims that the strategy will be profitable:

- target at least `1000` matured historical real calls across at least `50` distinct caller/source identities before considering caller-quality promotion;
- target at least `500` matured chain-qualified token outcomes with negative controls representing at least `40%` of the evaluation set;
- no single caller/source may dominate more than `10%` of the final TEST partition;
- TRAIN/VALIDATION/TEST partitioning must be chronological or otherwise demonstrably leakage-safe;
- sparse chain/caller/archetype slices remain `INSUFFICIENT_SAMPLES` rather than borrowing confidence from unrelated cohorts.

If these targets cannot be reached, collect as much real evidence as available and retain `INSUFFICIENT_SAMPLES`; do not fabricate readiness.

## Workstream C — Winner-first reverse caller discovery

For every matured winner and negative control:

```text
asset outcome
-> search only observations published before the relevant move
-> identify earliest resolved callers
-> reconstruct event-time market/wallet/security state
-> backfill that caller's prior calls
-> compute caller history using only information available before each subsequent call
-> place eligible caller into a research cohort
-> evaluate future calls out-of-sample
```

The system must retain failures, rugs, late calls and contradictory evidence. Deleted content is only used when supplied by a trustworthy configured source; absence of deletion history is `UNKNOWN`.

## Workstream D — Executable outcome reconstruction

Each call/signal must be evaluated at realistic executable semantics, not headline ATH.

Capture/derive where available:

- first actionable decision timestamp;
- signal-to-decision latency;
- decision-to-quote latency;
- quote age/freshness;
- decision market cap and token age;
- liquidity available at entry;
- price impact for configured paper notional;
- estimated fees/slippage/priority cost;
- executable entry price;
- partial-fill assumption/coverage;
- 5m/15m/1h/6h/24h/7d MFE and MAE;
- executable 2x/5x/10x/20x/50x/100x labels;
- executable exit under candidate policies;
- drawdown, exit capture and giveback.

For Solana, measure MEV/priority-fee exposure where the available evidence permits it. Missing execution evidence remains `UNKNOWN` and cannot be silently replaced by mark price.

## Workstream E — Live-shadow acceptance

Run the same canonical ingestion/normalization/decision path against current market data with execution disabled.

Initial acceptance guardrails before any research promotion:

- at least `14` consecutive calendar days of live-shadow collection;
- at least `200` matured actionable signals across the enabled production chains, or remain `INSUFFICIENT_SAMPLES`;
- provider uptime and freshness measured rather than assumed;
- no unresolved critical stream gap treated as contiguous data;
- all decisions and alerts replayable from stored normalized evidence;
- measured alert latency, decision latency and provider lag distributions;
- paper outcomes calculated with the same executable semantics used by historical replay.

A longer window is required when market activity is too low or regime concentration makes the sample unrepresentative.

## Workstream F — Alpha promotion gate

No caller/social/smart-money/opportunity feature or production weight is promoted solely because a backtest looks strong.

Required evidence:

- baseline versus caller-only;
- baseline versus smart-money-only;
- baseline versus opportunity-only;
- caller + smart-money;
- caller + opportunity;
- full fusion;
- feature-family ablation;
- false-positive cost;
- precision/recall and calibration;
- Wilson/confidence intervals;
- chain/caller/archetype/regime segmentation;
- executable expectancy after modeled costs;
- maximum drawdown/risk bounds;
- survivorship/no-lookahead mutation tests.

For a strategy candidate to be eligible for human review, the TEST/live-shadow evidence should, at minimum, demonstrate positive net paper expectancy after modeled costs and no material regression in hard-risk false negatives. Prefer a lower confidence bound above zero; if uncertainty remains high, classify `INSUFFICIENT_SAMPLES` rather than promoting.

Promotion remains human-reviewed and does not change protected modes automatically.

## Workstream G — Production deployment architecture

### Services

Production deployment must explicitly account for:

- API service;
- worker/ingestion processes;
- PostgreSQL;
- Redis/queue/cache where required;
- web frontend;
- scheduler/background collectors;
- provider adapters;
- Telegram notification worker/path;
- replay/research jobs isolated from latency-sensitive live ingestion.

### Configuration

- production configuration is environment-driven and validated at startup;
- no secret in repository, image, logs or frontend bundle;
- secret values are injected through the deployment environment/secret manager;
- all enabled chains/providers have explicit capability config and timeouts;
- unsafe mode combinations fail startup;
- environment/config hash is recorded in runtime provenance.

### Database

Before `PROD_READ_ONLY`:

- migration upgrade and downgrade/recovery strategy tested on a production-like copy;
- automated backups configured and restore procedure exercised;
- retention policy for raw social/provider evidence reviewed;
- critical tables/indexes assessed using realistic volumes;
- long-running research jobs cannot starve live ingestion/API transactions;
- connection pool limits and statement timeouts explicitly configured.

## Workstream H — Reliability, observability and SLOs

Expose metrics/logging sufficient to diagnose:

- provider success/error/rate-limit/staleness by capability;
- ingestion lag;
- queue depth/oldest age;
- duplicate/idempotency rate;
- unresolved stream gaps;
- parser/normalization failures;
- social call resolution rate;
- market/execution quote freshness;
- decision latency;
- alert delivery latency/failure;
- paper-order gate allowed/blocked reason codes;
- database/Redis health;
- API latency/error rate;
- worker restart/crash rate.

Initial production SLO targets should be configuration/documentation, then measured in soak tests. Do not claim SLO PASS without evidence. Suggested initial service targets for `PROD_READ_ONLY` are 99.5% application availability over the measurement window and explicit freshness SLOs per provider capability; provider outages must be shown separately from application availability.

Alerts must exist for sustained ingestion stoppage, stale market evidence, critical provider loss, unresolved stream gaps, queue growth, DB storage pressure, migration mismatch and Telegram delivery failure.

## Workstream I — Security and release engineering

Before production deployment:

- secrets scan passes;
- dependency/SBOM and known-vulnerability review passes according to repository policy;
- auth/RBAC for non-public operator/control endpoints verified;
- rate limits/input bounds for externally reachable endpoints verified;
- logs are checked for secret/token/session leakage;
- container images run without unnecessary privileges where feasible;
- dependency versions/build artifacts are reproducible/pinned enough for rollback;
- CI runs the canonical verify gates on push/PR or release candidate;
- release artifact is tied to exact git SHA and config/schema versions;
- rollback procedure is documented and tested;
- production migrations are not coupled to an irreversible application start.

The current absence of a visible remote CI run for the Alpha Caller checkpoint must be closed before claiming release-grade CI evidence. Local `make verify` is necessary but not sufficient as the sole production release proof.

## Workstream J — Soak, load and failure testing

Before `PROD_READ_ONLY` acceptance:

- run a production-like soak long enough to exercise provider refresh/retry/token rotation paths;
- test provider timeout/rate-limit/recovery;
- test Redis restart and queue recovery;
- test database connection interruption/recovery;
- test duplicate social/chain events;
- test delayed/out-of-order events;
- test stale quotes and unresolved gaps fail closed;
- test Telegram outage/retry/dedupe;
- benchmark API and ingestion throughput at expected load with headroom;
- document bottlenecks and capacity assumptions.

Do not use synthetic throughput as proof of real provider alpha quality; performance and alpha evidence are separate gates.

## Production acceptance matrix

### Gate PR-1 — Engineering/release

PASS requires canonical tests/lint/typecheck/security/SBOM/migrations/builds, remote CI evidence, reproducible release artifact and rollback instructions.

### Gate PR-2 — Provider/evidence readiness

PASS requires configured required production providers to return real observations with freshness/provenance and stable doctor evidence. Optional providers may remain degraded if the documented production capability set does not require them.

### Gate PR-3 — Historical-real research

PASS requires a leakage-safe real dataset and completed replay/ablation. If sample targets or confidence are inadequate, result is `INSUFFICIENT_SAMPLES`, not PASS.

### Gate PR-4 — Live-shadow

PASS requires sustained real live-shadow evidence, replayability, measured latency/freshness, no unsafe data-gap behavior and matured paper outcomes.

### Gate PR-5 — Operations

PASS requires backups/restore test, observability/alerts, soak/failure tests, deployment/rollback runbook and production configuration validation.

### Gate PR-6 — PROD_READ_ONLY

Allowed only when PR-1, PR-2 and PR-5 pass. PR-3/PR-4 may still be insufficient because read-only production can be used to collect real evidence. Protected modes remain unchanged.

### Gate PR-7 — PROD_PAPER_AUTO

Allowed only when PR-1 through PR-5 pass and paper-auto fail-closed behavior is verified in the real deployment environment. This still does not enable live money.

### Gate PR-8 — LIVE_MONEY_CANDIDATE

Requires a separate future operator-approved design. At minimum PR-1 through PR-7 must pass plus sufficient out-of-sample alpha/risk evidence. This gate records candidacy only; no mode is automatically changed.

## Definition of production ready for this roadmap

MemeRadar may be called production-ready only with a qualifier:

- `PRODUCTION_READY_READ_ONLY`, or
- `PRODUCTION_READY_PAPER_AUTO`.

Do not report generic `PRODUCTION_READY` or live-trading readiness while `AUTO_EXECUTION=false` and real-alpha evidence remains unpromoted.
