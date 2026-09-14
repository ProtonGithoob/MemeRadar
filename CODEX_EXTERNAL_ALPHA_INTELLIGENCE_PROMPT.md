# Codex Prompt — External Alpha Intelligence Integration

Continue from the **CURRENT `origin/main`** of `Rasman1234/MemeRadar`. Implement the approved **Option A — Conservative High-Signal Integration** now. Do not stop after planning.

The historical design baseline was `4ed711ffbd210590d9f1aab41e2446c51317e7c4`, but treat the current synchronized `origin/main` as authoritative when you start.

## Read first

Read and obey current repository instructions and these documents:

- `docs/superpowers/specs/2026-09-14-external-alpha-intelligence-integration.md`
- `docs/superpowers/plans/2026-09-14-external-alpha-intelligence-integration.md`
- `docs/EXTERNAL_REPO_SWOT_2026-09-14.md`
- `docs/RESEARCH_REUSE_REGISTRY.md`
- `docs/UPSTREAM_REPOSITORY_INFLUENCES.md`

Also inspect current status/architecture docs and all current code before changing anything.

## Primary objective

Add only unique, measurable external alpha evidence that MemeRadar does not already provide, while preserving its canonical architecture and fail-closed safety model.

Approved scope:

1. **GMGN** — optional read-only SOL/BSC evidence provider, disabled by default, LIVE_SHADOW and weight 0, but **only if** a stable auditable server-side read API/HTTP contract can be verified.
2. **Helius** — extend the existing stream normalizer with factual activity subtypes; do not create a second webhook stack.
3. **Numi** — use only to test/harden existing launch-lifecycle invariants; no second lifecycle engine.
4. **Solbeam** — documentation/UI reference only; no code/dependency/source reuse.

## Phase 0 — synchronize and prove the gap

1. Fetch/sync current `origin/main`; record baseline HEAD.
2. Inspect `AGENTS.md` or equivalent instructions.
3. Inspect current provider contracts, metadata, config, transport, reliability, composition, worker/bootstrap, Helius stream, lifecycle, wallet/caller/security/distribution evidence, live-shadow/readiness, historical evaluation, Early Alpha and alert paths.
4. Re-verify these upstream refs or record any newer ref you actually audit:
   - `GMGNAI/gmgn-skills` audit pin `4a48b8a31e19b62c96ee57ba76b46310f84043f0`
   - `SoCloseSociety/WhalegodTG` audit pin `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6`
   - `numi-ai/numi-trading-agent` audit pin `cb460ff96508c8fdae64ac169b4fc6cc2703f4ff`
   - `CodeMuscle/solbeam` audit pin `234423a8f0180deffc6b9d83fa84e35687049670`
5. Re-verify current license status before copying any source. GMGN and Whalegod had root MIT LICENSE files at audit time. Numi/Solbeam had MIT declarations in README/package but no root LICENSE was found; do not copy their source/tests/comments/implementation.
6. Before coding, output a compact matrix:

```text
requirement | EXISTING | PARTIAL | MISSING | NOT_NEEDED | target files | reason
```

Delete/shrink planned changes when the current repo already solves the requirement.

## Architecture rules

The canonical flow remains:

```text
provider
-> existing provider contracts/transport/reliability
-> Observation + Provenance + QualityState
-> existing caller/smart-money/distribution/security/lifecycle evidence
-> existing scoring/risk
-> Early Alpha
-> existing Telegram/Web delivery
```

Do **not** create:

- `GMGNScore`
- `GMGNRiskEngine`
- `GMGNWalletScore`
- `NumiRiskManager`
- `RobinhoodLifecycleV2`
- `WhalegodAlertEngine`
- `WhalegodTelegramPipeline`
- another Helius webhook stack
- another wallet graph
- another provider metadata registry
- another provider reliability framework
- GMGN swap/cooking/order/private-key/wallet-management integration
- Numi/1inch live execution

## Workstream A — GMGN read-only intelligence

### Hard integration precondition

Verify a stable, auditable server-side read interface with documented request/response semantics. Prefer direct backend HTTP/API integration consistent with MemeRadar's provider architecture.

**Never** add a `gmgn-cli` subprocess, shell-out, browser scraping, private key, signing, wallet management or order execution to MemeRadar.

If a stable safe read contract cannot be verified:

- do not guess endpoints;
- do not create a fake adapter;
- record GMGN as `BLOCKED_EXTERNAL` using existing readiness semantics;
- complete Helius, lifecycle, readiness/docs work;
- report the blocker precisely in the final report.

`BLOCKED_EXTERNAL` is a correct outcome, not a reason to weaken architecture.

### If the contract is verified

Implement the smallest provider adapter under current repository conventions. A likely path is `packages/providers/src/memeradar_providers/gmgn.py`, but use the actual current layout after inspection.

Reuse existing:

- provider request/result contracts;
- transport/errors;
- deadlines/timeouts;
- reliability telemetry;
- composition/bootstrap;
- canonical chain/address validation;
- fixture/redaction logic;
- provider metadata/readiness.

Initial state:

```text
optional=true
enabled_by_default=false
required_for_health=false
read_only=true
live_shadow=true
scoring_weight=0
```

Potential config names, only if they match current conventions and actual needs:

```env
GMGN_ENABLED=false
GMGN_API_KEY=
GMGN_BASE_URL=
```

Do not add a configurable base URL when no verified runtime need exists.

### Normalize into existing evidence

Map verified upstream fields/capabilities to existing MemeRadar concepts:

- new/trending/trenches -> candidate discovery
- market/token data -> market enrichment
- KOL activity -> caller/KOL supporting evidence
- Smart Money activity -> smart-wallet supporting evidence
- top traders -> wallet enrichment
- top holders -> distribution evidence
- `smart_degen_count` -> smart-money supporting evidence
- `rat_trader_amount_rate` -> distribution/security supporting evidence
- `bundler_trader_amount_rate` -> bundler/security evidence
- `sniper_count` -> early-distribution/security evidence
- `suspected_insider_hold_rate` -> insider-pattern supporting evidence
- `fresh_wallet_rate` -> distribution quality
- dev/creator holding fields -> creator/distribution evidence
- wash-trading -> market-integrity/security evidence
- honeypot -> security evidence
- rug ratio -> provider risk evidence
- `is_on_curve` -> lifecycle corroboration only

Semantic invariants:

```text
GMGN smart_money != verified MemeRadar smart wallet
GMGN KOL != trusted caller by itself
GMGN suspected_insider != CONFIRMED_INSIDER
GMGN rug ratio != deterministic rug verdict
GMGN is_on_curve != authoritative lifecycle transition
```

### Provider correctness

Test first, then implement:

- disabled/missing config;
- auth/403;
- 429/rate limit;
- timeout/deadline;
- unavailable/5xx;
- malformed schema;
- valid-empty response;
- missing numeric stays UNKNOWN/None, not zero/50;
- missing boolean stays UNKNOWN, not safe false;
- API key redaction from repr/log/error/public projections;
- event_time vs observed_at/ingested_at;
- bounded concurrency;
- SOL/BSC normalization;
- provenance/parser version;
- replay/determinism where source IDs permit.

## Workstream B — Helius factual activity taxonomy

Extend the **existing** `HeliusObservationNormalizer`. Do not replace it and do not add another webhook pipeline.

Add a factual normalized `activity_kind` (or equivalent existing-domain representation) for:

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

Requirements:

- use explicit/strong payload evidence only;
- known synonyms may normalize deterministically;
- ambiguous -> `UNKNOWN`;
- preserve current source-ID/provenance/event-time/replay semantics;
- preserve current malformed-message behavior;
- do not infer bullish/bearish/degen/rug/buy/sell recommendations from activity type.

Write failing focused tests first, then minimal implementation, then rerun the complete Helius suite.

## Workstream C — Numi lifecycle invariants

Do **not** create a new lifecycle model. MemeRadar's existing `launch_lifecycle.py` remains canonical.

Add regression tests proving:

1. `BONDING` does not imply `DEX_ROUTE`.
2. `GRADUATING` or provider `graduated` does not imply verified DEX liquidity.
3. `DEX_LIVE` requires evidence compatible with current verified-route policy, not a vendor label alone.
4. `first_verified_dex_liquidity_at` and `first_verified_swap_at` are distinct.
5. weak GMGN lifecycle corroboration cannot override stronger canonical/reconciled evidence.

If all tests pass before production changes, **do not change production lifecycle code**. If one fails, make the smallest root-cause fix.

## Workstream D — LIVE_SHADOW / readiness / real samples

Reuse current readiness/reporting. Do not make a new readiness system.

Where current architecture supports it, expose/derive:

- real GMGN observation count;
- unique real SOL/BSC token count;
- candidate count;
- KOL/caller observation count;
- smart-wallet observation count;
- holder/distribution observation count;
- security/risk observation count;
- first/last real observation timestamps;
- provider errors/rate limits/status;
- real winner count;
- real rug count;
- sample sufficiency.

Strictly exclude from real promotion samples:

- fixtures;
- mocks;
- synthetic samples;
- demos;
- replay-only samples;
- redacted examples.

Insufficient evidence must report `INSUFFICIENT_SAMPLES`.

## Workstream E — promotion analysis only

Do not change production weights. Keep new GMGN features at weight 0.

Reuse current event-time historical/ablation infrastructure so future baseline vs baseline+GMGN analysis can measure:

- lead time;
- precision;
- false-positive rate;
- rug avoidance;
- 2x, 5x, 10x, 20x, 50x, 100x capture;
- extreme-winner capture;
- calibration.

No look-ahead or survivorship leakage. Availability of an adapter is not evidence for promotion.

## Protected-mode invariants

Do not change:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

No new integration may relax fail-closed execution requirements.

## TDD and verification

Use test-driven development for every production behavior change:

```text
failing focused test
-> minimal implementation
-> focused green
-> related-suite green
-> refactor only while green
```

After implementation, run the repository's **current native commands** for all applicable gates:

- focused GMGN tests if adapter exists;
- Helius tests;
- lifecycle/readiness tests;
- full Python suite;
- Telegram/alert tests;
- frontend tests;
- lint;
- typecheck;
- frontend build;
- migrations;
- security scan/checks;
- SBOM/dependency checks;
- `git diff --check`;
- `make verify` or current equivalent;
- browser journeys where runnable.

Do not call blocked or skipped external checks PASS. Report exact pass/skip/fail counts and environmental blockers.

## Final diff audit

Before commit/push, explicitly prove:

- no secrets/private keys in diff/logs;
- no GMGN execution/trading code;
- no duplicate scorer/risk/lifecycle/wallet/alert/reliability subsystem;
- no production weight promotion;
- protected modes unchanged;
- `UNKNOWN` semantics preserved;
- fixtures/mocks excluded from real-sample counters;
- docs match implementation.

## Required final report — exactly cover these 27 items

1. baseline HEAD;
2. audited upstream refs and license state;
3. before gap matrix;
4. canonical functionality reused;
5. GMGN implementation state or exact `BLOCKED_EXTERNAL` reason;
6. rejected GMGN execution/private-key surface;
7. Helius activity taxonomy implementation;
8. lifecycle invariants/results;
9. changed files;
10. config/secrets model;
11. provider-to-canonical mapping;
12. LIVE_SHADOW state;
13. real-data counts;
14. sample-sufficiency/calibration state;
15. confirmation that scoring weights are unchanged;
16. protected-mode values;
17. focused test results;
18. full test results;
19. lint/typecheck/build results;
20. migration result;
21. security result;
22. SBOM/dependency result;
23. browser result;
24. all `BLOCKED_EXTERNAL`/environmental blockers;
25. final readiness classification;
26. implementation commit SHA(s);
27. final HEAD and whether `HEAD == origin/main`.

Unless sufficient **real** out-of-sample evidence now exists, the expected truthful classification is:

```text
ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION
NOT_PRODUCTION_READY
```

## Required execution order

```text
sync
-> gap analysis
-> reuse mapping
-> failing tests
-> GMGN contract decision
-> minimal GMGN implementation only if verified
-> Helius taxonomy
-> lifecycle regression/hardening
-> live-shadow/readiness accounting
-> full verification
-> diff/security audit
-> status/doc sync
-> commit/push
```

Implement now. Do not stop after writing or repeating a plan.
