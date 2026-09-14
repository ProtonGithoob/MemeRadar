# External Alpha Intelligence Integration — Design Specification

**Date:** 2026-09-14  
**Approved design:** Option A — Conservative High-Signal Integration  
**Baseline:** `Rasman1234/MemeRadar@4ed711ffbd210590d9f1aab41e2446c51317e7c4`

## 1. Objective

Improve MemeRadar's ability to detect high-upside memecoin opportunities early while reducing false positives and rug exposure by adding only high-value external evidence to the existing canonical architecture.

The design integrates:

1. GMGN as an optional read-only, disabled-by-default, LIVE_SHADOW evidence source for SOL/BSC **only when a stable and auditable server-side read contract can be verified**.
2. A factual Helius activity taxonomy inside the existing Helius normalization path.
3. Numi-inspired lifecycle invariants as tests/minimal hardening of the existing lifecycle model.
4. Solbeam as documentation/UI reference only.

This is an evidence-quality project, not an execution-expansion project.

## 2. Non-goals

This design does not authorize:

- a new scoring engine;
- a new risk engine;
- a new wallet graph;
- a second lifecycle engine;
- a second Helius webhook service;
- a separate Telegram alert pipeline;
- private-key or wallet custody;
- GMGN trading, swap, cooking, strategy-order or copy-trading functions;
- Numi/1inch live execution;
- changes to production alpha weights without real-data promotion evidence;
- enabling MANUAL or AUTO execution.

## 3. Existing architecture is canonical

Reuse the current MemeRadar boundaries before adding code:

```text
external provider
    -> provider adapter / canonical request contract
    -> Observation + Provenance + QualityState
    -> existing evidence projections
    -> existing scoring / risk / wallet / lifecycle
    -> Early Alpha projection
    -> existing Telegram/Web delivery
```

Known reusable components at the approved baseline include:

- `packages/application/src/memeradar_application/provider_contracts.py`
- `packages/application/src/memeradar_application/provider_metadata.py`
- `packages/application/src/memeradar_application/launch_lifecycle.py`
- `packages/providers/src/memeradar_providers/helius_stream.py`
- existing provider transport/reliability/composition infrastructure
- existing wallet/caller/security/distribution evidence paths
- existing LIVE_SHADOW/readiness and historical evaluation paths

Do not create a parallel registry or parallel reliability framework.

## 4. Target architecture

```text
GMGN read-only evidence                      Helius stream
        |                                          |
        | candidate / wallet / security            | factual event subtype
        v                                          v
existing provider contracts              existing Helius normalizer
        |                                          |
        +------------------+-----------------------+
                           v
               canonical observations/evidence
                           |
         +-----------------+-------------------+
         |                 |                   |
       Caller          Smart Money        Distribution/Security
         |                 |                   |
         +-----------------+-------------------+
                           v
              existing scoring/risk/lifecycle
                           |
                           v
              Early Alpha / Telegram / Web

All new GMGN evidence: LIVE_SHADOW, weight = 0 until promotion gate passes.
```

## 5. GMGN provider contract

### 5.1 Activation

Initial state must be:

```text
optional = true
enabled_by_default = false
read_only = true
live_shadow = true
scoring_weight = 0
required_for_app_health = false
```

Candidate configuration names, adapted to repository conventions after inspection:

```env
GMGN_ENABLED=false
GMGN_API_KEY=
GMGN_BASE_URL=
```

Do not add `GMGN_BASE_URL` if a stable endpoint is not actually needed or verified. Stable defaults should remain code defaults if that matches repository convention.

### 5.2 Integration precondition

Before writing the adapter, verify the current GMGN upstream contract. A safe integration must use an auditable server-side read interface with explicit request/response semantics.

**Forbidden fallback:** spawning `gmgn-cli` as a subprocess from MemeRadar's Python worker.

If no stable read API/HTTP contract can be verified, the correct behavior is:

- do not invent endpoints;
- do not scrape gmgn.ai;
- do not add a brittle subprocess dependency;
- expose provider readiness as `BLOCKED_EXTERNAL` or equivalent existing canonical state;
- finish the Helius taxonomy, lifecycle hardening, documentation and tests independently.

### 5.3 Transport and correctness requirements

The adapter, if implemented, must follow existing provider conventions:

- server-side API secret only;
- bounded concurrency/semaphore;
- request deadline propagation through existing `ProviderRequestContext` where applicable;
- explicit connect/read timeout;
- canonical authentication, rate-limit, timeout, schema and unavailable exceptions;
- retries only for repository-approved retryable failures;
- no unbounded retry loop;
- valid-empty result distinguished from provider failure;
- absent numeric data remains absent/`UNKNOWN`, never coerced to `0` or `50`;
- event time separated from observed/ingested time;
- UTC normalization and ordered timestamps;
- provider provenance and parser version on every normalized observation;
- deterministic/replay-safe source IDs where upstream IDs permit it;
- canonical chain/address normalization;
- fixture/redaction rules reused rather than reimplemented;
- API keys/tokens never appear in log messages, error strings, reprs, frontend or API projections.

### 5.4 GMGN capability mapping

Use existing provider capabilities whenever possible; do not invent capability enums merely to mirror GMGN vocabulary.

| GMGN evidence | MemeRadar destination |
|---|---|
| new/trending/trenches token data | candidate discovery |
| market/token data | market data enrichment |
| KOL trades/holdings | caller/KOL supporting evidence |
| Smart Money activity | smart-wallet supporting evidence |
| top traders | wallet enrichment |
| top holders | distribution evidence |
| `smart_degen_count` | smart-money supporting evidence |
| `rat_trader_amount_rate` | distribution/security supporting evidence |
| `bundler_trader_amount_rate` | bundler/security evidence |
| `sniper_count` | early-distribution/security evidence |
| `suspected_insider_hold_rate` | insider-pattern supporting evidence |
| `fresh_wallet_rate` | distribution quality evidence |
| dev/creator hold fields | creator/distribution evidence |
| wash-trading signal | market-integrity/security evidence |
| honeypot signal | security evidence |
| rug ratio | provider risk evidence |
| `is_on_curve` | launch-lifecycle corroboration only |

### 5.5 Semantic guardrails

Provider assertions are evidence, not truth:

```text
GMGN smart-money label != verified MemeRadar smart wallet
GMGN KOL label != trusted caller by itself
GMGN suspected insider != CONFIRMED_INSIDER
GMGN rug ratio != deterministic rug verdict
GMGN is_on_curve != authoritative lifecycle transition by itself
```

Preserve upstream field provenance and provider identity so conflicting providers remain distinguishable.

## 6. Helius factual activity taxonomy

### 6.1 Purpose

The current Helius normalizer already handles untrusted payloads, source IDs, event time, provenance, redaction, broad observation kinds, quality, replay-safe IDs and bounded stream consumption. Extend this path rather than adding a new webhook stack.

### 6.2 New normalized field

Add a factual `activity_kind` to normalized Helius transaction-like observations, using a bounded canonical vocabulary:

```text
SWAP
LIQUIDITY_ADD
LIQUIDITY_REMOVE
BRIDGE
TRANSFER
TOKEN_LAUNCH
MEV_ARBITRAGE
UNKNOWN
```

Names may be represented by an enum if an existing domain pattern makes that preferable, but no duplicate event-domain framework should be introduced.

### 6.3 Classification rules

- classify only from explicit/strong payload evidence;
- handle known upstream synonyms deterministically;
- ambiguous payloads -> `UNKNOWN`;
- malformed required structure -> existing schema-error behavior;
- preserve raw/redacted payload evidence needed for replay/debug;
- activity subtype must not change existing observation ID semantics unexpectedly;
- do not infer market direction or risk verdict.

Forbidden examples:

```text
LIQUIDITY_REMOVE => BEARISH
SWAP => BULLISH
MEV_ARBITRAGE => RUG
TOKEN_LAUNCH => BUY
```

## 7. Launch-lifecycle hardening

MemeRadar's current lifecycle model remains authoritative. Validate these invariants with regression tests:

1. `BONDING` does not imply `DEX_ROUTE`.
2. `GRADUATING` / provider `graduated` does not by itself imply verified DEX liquidity.
3. `DEX_LIVE` requires evidence consistent with existing verified-route policy, not merely a vendor string.
4. `first_verified_dex_liquidity_at` and `first_verified_swap_at` remain separate evidence dimensions.
5. lifecycle corroboration from GMGN cannot override higher-quality/reconciled canonical evidence.

If current production code already enforces the invariants, add tests only. Production changes require a failing test that demonstrates a real gap.

## 8. Solbeam handling

Solbeam is documentation/UI inspiration only for this design. Do not:

- import it as a dependency;
- copy source;
- copy its data model;
- create a second Helius ingestion system;
- create a new wallet tracker/alert engine solely to match its README.

## 9. LIVE_SHADOW and readiness evidence

Readiness reporting should reuse the existing readiness/reporting architecture and, where the repository already exposes adjacent counters, add or derive:

- real GMGN observation count;
- unique SOL/BSC tokens observed from GMGN;
- candidate-discovery observations;
- KOL/caller observations;
- smart-wallet observations;
- holder/distribution observations;
- security/risk observations;
- first real observation timestamp;
- last real observation timestamp;
- provider authentication/rate-limit/timeout/unavailable counts or existing summarized status;
- real winner-labeled sample count;
- real rug-labeled sample count;
- sample-sufficiency state.

### Real-sample definition

A promotion-eligible sample must originate from real provider/runtime evidence. The following must not increment real-sample promotion counters:

- fixtures;
- synthetic samples;
- deterministic demos;
- replay-only test data;
- redacted example payloads;
- mocks/stubs.

If sample size is insufficient, report `INSUFFICIENT_SAMPLES`; do not silently substitute neutral confidence.

## 10. Promotion gate

GMGN-derived features remain weight 0 until a reproducible historical/out-of-sample study demonstrates meaningful incremental value without look-ahead or survivorship leakage.

Evaluate at minimum:

- early lead time;
- precision;
- false-positive rate;
- rug avoidance;
- 2x capture;
- 5x capture;
- 10x capture;
- 20x capture;
- 50x capture;
- 100x capture;
- extreme-winner capture;
- calibration where applicable.

Compare baseline versus baseline+GMGN and relevant ablations. Promotion requires measured improvement, not architectural availability.

## 11. Test requirements

### GMGN

If adapter implementation proceeds, cover at least:

- provider disabled by default;
- missing configuration;
- authentication failure;
- HTTP/provider 403 semantics;
- rate limit/429;
- timeout;
- unavailable/5xx;
- malformed schema;
- valid-empty response;
- missing numeric values remain unknown;
- API key is absent from repr/log/error/public projection;
- event-time normalization;
- bounded concurrency;
- canonical chain mapping SOL/BSC;
- canonical evidence mappings;
- LIVE_SHADOW persistence/reporting;
- fixtures/mocks do not increment real-sample counts;
- scoring weights remain unchanged.

### Helius

Cover:

- swap;
- liquidity add;
- liquidity remove;
- bridge;
- transfer;
- token launch;
- MEV/arbitrage where explicit;
- ambiguous -> `UNKNOWN`;
- malformed input retains existing failure behavior;
- duplicate/replay behavior remains stable;
- event time remains correct.

### Lifecycle

Cover all invariants in section 7 and ensure upstream/provider labels cannot manufacture route certainty.

## 12. Protected modes

The integration must preserve:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No implementation in this scope may relax a fail-closed execution gate.

## 13. Acceptance criteria

The design is accepted only when:

- no duplicate scorer/risk/lifecycle/wallet/reliability subsystem exists;
- GMGN is either safely integrated read-only or truthfully `BLOCKED_EXTERNAL`;
- GMGN is disabled by default and unweighted;
- no external execution/private-key path is added;
- Helius factual taxonomy is deterministic and non-directional;
- lifecycle invariants are covered by tests;
- real/synthetic sample separation is explicit;
- full repository verification passes or every environmental blocker is truthfully reported;
- protected modes are unchanged;
- status remains `NOT_PRODUCTION_READY` until real evidence satisfies the existing promotion/readiness criteria.
