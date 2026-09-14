# External Repository SWOT — 2026-09-14

## Audit baseline

- MemeRadar repository: `Rasman1234/MemeRadar`
- Baseline branch: `main`
- Baseline HEAD: `4ed711ffbd210590d9f1aab41e2446c51317e7c4`
- Decision: **Option A — Conservative High-Signal Integration**
- Goal: add only evidence that improves early memecoin discovery/risk context without creating parallel scoring, risk, lifecycle, wallet, alert, or execution systems.

## Executive decision

Priority order:

1. **GMGNAI/gmgn-skills — integrate as an optional read-only LIVE_SHADOW evidence provider if a stable, auditable server-side read contract can be verified.**
2. **SoCloseSociety/WhalegodTG — reuse the factual activity-taxonomy concept inside the existing Helius normalization path; do not copy its bot/alert architecture.**
3. **numi-ai/numi-trading-agent — use only as an architectural reference for launch-lifecycle invariants; MemeRadar already has the canonical lifecycle model.**
4. **CodeMuscle/solbeam — documentation/UI/research reference only; no production dependency or source reuse.**

No external repository is allowed to bypass MemeRadar's canonical evidence, risk, readiness, or protected-mode gates.

## Comparative SWOT

| Source | Pinned ref | License status at audit | Strengths | Weaknesses | Opportunity for MemeRadar | Threat / control | Decision |
|---|---|---|---|---|---|---|---|
| `GMGNAI/gmgn-skills` | `4a48b8a31e19b62c96ee57ba76b46310f84043f0` | Root MIT LICENSE verified | Real-time SOL/BSC discovery; Smart Money/KOL; holder/trader; bundler/sniper/insider; security/rug/wash/honeypot; bonding-curve context | Vendor-defined labels and semantics; also exposes execution/wallet/private-key flows that MemeRadar must not inherit | Add a high-signal independent evidence source for discovery, wallet behavior, distribution and security | Vendor labels can be mistaken for ground truth; API/CLI coupling can create operational and secret risk | **9/10 — integrate read-only, disabled by default, weight=0** |
| `SoCloseSociety/WhalegodTG` | `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6` | Root MIT LICENSE verified | Helius webhook experience; factual transaction categories; dedupe; bounded API usage; useful event-flow concepts | Telegram/SQLite-centric; embeds directional labels that do not belong in provider normalization | Improve MemeRadar Helius observations with factual activity kinds such as swap, LP add/remove, bridge and launch | Copying bullish/bearish/degen semantics would contaminate canonical evidence | **7.5/10 — concept-level partial integration** |
| `numi-ai/numi-trading-agent` | `cb460ff96508c8fdae64ac169b4fc6cc2703f4ff` | README/package declare MIT; root LICENSE not found at audit | Robinhood Chain lifecycle thinking; paper-first; fail-closed route/risk concepts; distinction between bonding and DEX execution | Different architecture and execution stack; direct lifecycle duplication would regress MemeRadar | Add regression invariants around bonding, graduation, verified liquidity and first executable swap | License ambiguity for source reuse; live execution code is out of scope | **8/10 architectural reference, 4/10 direct integration — no source copy** |
| `CodeMuscle/solbeam` | `234423a8f0180deffc6b9d83fa84e35687049670` | README declares MIT; root LICENSE not found at audit | Simple Helius-driven UX/pipeline concepts; low-cost dashboard perspective | Principal advertised features were still roadmap-heavy during audit | UI/research inspiration only | Treating roadmap claims as implemented capability would create false confidence | **3/10 — docs/reference only** |

## 1. GMGN — detailed SWOT

### Strengths

GMGN exposes unusually dense early-token evidence relevant to MemeRadar's objective: new/trending token discovery, Smart Money/KOL activity, top holders/traders, smart-degen counts, rat-trader ratio, bundler exposure, sniper count, suspected-insider hold rate, fresh-wallet ratio, developer/creator holdings, wash-trading, honeypot/rug context and bonding-curve state. It spans at least SOL and BSC, which aligns with MemeRadar's current multi-chain scope.

### Weaknesses

The labels are provider opinions, not MemeRadar truth. `smart_money`, `suspected_insider`, `rug_ratio`, or similar values must retain provider provenance and uncertainty. The repository also includes swap/order/private-key workflows; those are explicitly outside this integration.

### Opportunities

Use GMGN as an independent corroborating source for:

- candidate discovery;
- caller/KOL supporting evidence;
- smart-wallet supporting evidence;
- holder/distribution evidence;
- bundler/sniper/fresh-wallet evidence;
- market-integrity/security evidence;
- lifecycle corroboration such as bonding-curve state.

The first phase is **LIVE_SHADOW and unweighted**. The goal is to measure whether the added evidence improves lead time, precision, rug avoidance and extreme-winner capture before any scoring promotion.

### Threats and controls

- **Vendor semantic leakage:** preserve provider-native labels as evidence, never as final canonical truth.
- **Execution creep:** no GMGN swap, cooking, order, wallet-management, signing, private-key or copy-trading surface.
- **CLI dependency risk:** do not introduce a `gmgn-cli` subprocess in the Python worker. Prefer a stable documented read API/HTTP contract. If none can be safely verified, expose the integration as `BLOCKED_EXTERNAL` instead of inventing an endpoint.
- **Secret exposure:** API keys remain server-side only; never render them in frontend projections, logs or reprs.
- **Availability bias:** valid-empty responses are not transport failures; missing data remains `UNKNOWN` rather than neutral zero.

## 2. WhalegodTG — detailed SWOT

### Strengths

Its most reusable concept is a factual activity taxonomy around on-chain events: swaps, liquidity additions/removals, bridges, transfers, launches and MEV-like activity. It also demonstrates practical deduplication and bounded provider use.

### Weaknesses

Its Telegram-first alert architecture, SQLite persistence and directional labels do not match MemeRadar's layered canonical architecture.

### Opportunity

Extend the existing `HeliusObservationNormalizer` so `normalized_payload` includes a factual `activity_kind` while preserving the existing broad observation kind and provenance. Recommended vocabulary:

- `SWAP`
- `LIQUIDITY_ADD`
- `LIQUIDITY_REMOVE`
- `BRIDGE`
- `TRANSFER`
- `TOKEN_LAUNCH`
- `MEV_ARBITRAGE`
- `UNKNOWN`

Ambiguous or incomplete input must map to `UNKNOWN` rather than a guess.

### Threat and control

Provider normalization must never encode `LP_REMOVE = bearish`, `SWAP = bullish`, `MEV = rug`, or equivalent conclusions. Interpretation belongs to existing canonical risk/evidence layers.

## 3. Numi — detailed SWOT

### Strengths

Numi's Robinhood Chain design makes useful distinctions between bonding-curve state, graduation, post-graduation routing, verified liquidity and executable trading.

### Weaknesses

MemeRadar already has a provider-neutral lifecycle projection with `CREATED`, `BONDING`, `GRADUATING`, `DEX_LIVE`, route state, verified liquidity and first-swap evidence. A second lifecycle engine would be duplication.

### Opportunity

Use Numi only to strengthen regression tests for these invariants:

1. `BONDING` does not imply `DEX_ROUTE`.
2. `GRADUATING` or upstream `graduated` does not imply verified DEX liquidity.
3. `DEX_LIVE` must require evidence consistent with MemeRadar's verified-route policy rather than a vendor label alone.
4. First verified DEX liquidity and first verified executable swap are distinct evidence points.

If current code already satisfies all four, no production-code change is required; regression tests are the correct result.

### Threat and control

Because a root LICENSE was not found during this audit, do not copy source, comments, tests, function names or implementation details. Independently implement only the architectural invariants above.

## 4. Solbeam — detailed SWOT

### Strengths

Solbeam gives useful product/UI ideas around live token feeds, wallet pages, risk panels and Helius-driven updates.

### Weaknesses

At audit time several principal README features remained roadmap items, so advertised capability must not be interpreted as proven implementation.

### Opportunity

Retain only as research and UI inspiration. MemeRadar already has provider, wallet graph, alert and frontend architecture that should remain canonical.

### Threat and control

A root LICENSE was not found during this audit. No source reuse or dependency is permitted from this decision; any future use requires a fresh license and implementation audit.

## Accepted concepts

- GMGN read-only evidence acquisition for SOL/BSC when a safe read contract is verifiable.
- Provider-native Smart Money/KOL/holder/bundler/sniper/insider/rug data as **supporting evidence with provenance**.
- Helius factual activity subtyping inside the existing normalizer.
- Numi lifecycle regression invariants.
- Solbeam as docs/UI reference only.

## Explicitly rejected concepts

Do not create or import:

- `GMGNScore`
- `GMGNRiskEngine`
- `GMGNWalletScore`
- `NumiRiskManager`
- `RobinhoodLifecycleV2`
- `WhalegodAlertEngine`
- `WhalegodTelegramPipeline`
- a second Helius webhook stack
- a second wallet graph
- a second provider reliability registry
- GMGN swap/cooking/order execution
- external wallet/private-key management
- 1inch live execution from Numi
- provider-layer bullish/bearish/rug decisions

## Promotion gate

New GMGN-derived evidence starts at **weight 0** and LIVE_SHADOW only. Promotion requires reproducible, event-time-correct, out-of-sample evidence of meaningful improvement in one or more of:

- earlier lead time;
- precision;
- false-positive rate;
- rug avoidance;
- 2x / 5x / 10x / 20x / 50x / 100x capture;
- extreme-winner capture;
- calibration.

Synthetic, fixture, replay-only or redacted samples must never increment real-sample promotion counters.

## Safety/readiness invariant

This work must not change the protected operating posture:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Absent sufficient real out-of-sample samples, the truthful status remains:

```text
ENGINEERING_READY_FOR_REAL_DATA_ALPHA_VALIDATION
NOT_PRODUCTION_READY
```
