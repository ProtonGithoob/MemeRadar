# Early Alpha Intelligence plan: progress and gate ledger (2026-11-25)

**Plan:** [2026-11-25 implementation plan](../superpowers/plans/2026-11-25-memeradar-early-alpha-intelligence.md)

**Branch:** `claude/exciting-brahmagupta-0k7pds`

**Code commits:** `7a1e8eb` (M0), `3db15ca` (M1/M2), `daf629b` (M5/G2)

**Earlier evidence:** [M0 report](M0_RUNTIME_POSTGRES_2026-11-24.md)

Unit suite at `daf629b`: 1,838 passed. mypy is clean on 197 files and ruff is clean.

## Milestones done in this session

### M0: runtime and PostgreSQL

Done for the local scope; see the M0 report. Two items are still open:
- the bounded-traffic worker drill on the Compose host;
- an upgrade run on the operator's deployed database.

### M1: trustworthy historical launch cohort

M1 is done for bounded windows.

**Contract.** `launch_inventory.py` has the frozen eligibility rule `pumpfun-all-observed-launch-v1`. Every successful, finalized `create`/`create_v2` of the verified program in the window is eligible. No trade, liquidity, listing or outcome filter applies, so tokens that never trade or never graduate are included by construction.

**Two retrieval paths** (`pump_fun_inventory.py`):

| Source | How it works |
| --- | --- |
| Block scan (canonical) | `SolanaRpcBackfillAdapter` over finalized blocks, using the same decoder as live ingestion. The window is split into 10-slot chunks with retries, and a failed chunk is marked `UNRESOLVED` with a reason. |
| Address index (independent) | `getSignaturesForAddress` on the global mint-authority PDA `TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM`. The PDA was verified from the account at index 1 in 5/5 mainnet creates. It shares the IDL account order with the canonical path, but not the block fetch or the router. |

**Ledger and manifest:**
- Unresolved slots are kept out of the recall denominator.
- Source disagreement, duplicate mints and failed creates are recorded.
- Overlapping sources add source references without adding rows.
- An import with `UNKNOWN` or `RESTRICTED` data rights cannot be approved.
- The manifest's logical digest excludes run timestamps.

**Live windows** (public keyless RPC):

| Run | Slots | Launches | Agreement | Unresolved | Status | Logical digest | Rebuild |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `2026-11-25-m1-window1` | 473546451–473546570 (120) | 12 | 12/12, recall 1.0 | 0 | APPROVED | `sha256:a9467d08…9790` | identical |
| `2026-11-25-m1-window2` | 473546437–473546836 (400) | 45 | 45/45, recall 1.0 | 0 | APPROVED | `sha256:14b06713…3b99` | identical |

Window 2 contains window 1. The two windows are nested evidence, not two independent samples.

**Window 2 cohort composition:**
- **Assets and creators:** 45 unique assets from 40 unique creators; 8 launches came from creators who launched more than once.
- **Instructions:** all 45 are `create_v2`.
- **Exclusions:** one failed create transaction, seen only by the index and excluded with reason `TRANSACTION_FAILED`.
- **DEX state at capture:** 42 on the curve and 3 on PumpSwap. This is observation only, not an outcome.

**Found and fixed:**
- **Backfill rejected whole ranges on null logs.** Backfill used to reject a whole range when a transaction had null logs. It now skips such a transaction when it cannot reference the Pump program; a Pump transaction without logs still fails closed.
- **Intermittent error.** One backfill run hit "logs were invalid". Chunking now confines such a failure to its own slots.

**Tests:** `test_launch_inventory.py` (10) covers:
- a no-trade launch;
- overlapping sources;
- a disagreement;
- unresolved slots;
- a replayed duplicate mint;
- mismatched decimals, a future-dated record and a bad identity;
- a failed create;
- data rights;
- digest stability.

`test_pump_fun_inventory.py` (5) covers the real-transaction index rule and null-log handling.

**Still open for M1:**
- Coverage over longer and non-overlapping periods.
- Graduation, outcome and family counts per window. Outcomes mature 1 h to 72 h after each window; cluster families belong to M3.

### M2: Extreme Winner DNA labels

Only the label part is done.

**Labels** (`outcome_labels.py`). Each decision anchor is labelled for every horizon (1h, 6h, 24h, 72h) and multiple (2x–100x) under three independent semantics:
- **`MARKET_MARK`:** the best corroborated mark inside the horizon. A lone, uncorroborated spike does not count.
- **`EXECUTABLE_QUOTE_PEAK`:** a delayed entry (15 s) of USD 50 with fees. The exit quote must be for exactly the tokens bought, after entry and before the horizon closes, with a verified route and units and a quote age within the TTL.
- **`PAPER_REALIZED`:** fills of the named policy only.

**Status rules:**
- An immature horizon is `PENDING`.
- Missing evidence is `CENSORED` with a reason.
- The decision snapshot hash uses decision-time inputs only.

**Tests:** all the plan's cases pass (10): a 100x chart with no sell quote, a 10x exit outside the horizon, an immature label, an entry after the cutoff, a 10x mark against a 2x size-qualified exit, and snapshot-hash invariance.

**Still open for M2:**
- The feature-separability study and baseline results. These need mature cohorts.
- Wiring the labels into the forward collector and lifecycle watch persistence.

### M5: first 120 seconds and the graduation transition

Done in part.

**Verified case.** Mint `2P4qGGkK…Sy32pump`:
- launched at slot 473546798, inside the M1 window 2 cohort;
- `migrate` at slot 473547671, about 6 minutes later, through a Pump CPI into PumpSwap `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`.

The canonical decoder routes the migration by program and discriminator, with the launch mint and finalized commitment. The DexScreener PumpSwap pool `BAkaaTVw…kPBY` is in the migrate transaction's accounts. The case is a fixture with tests.

**Live path:**
- The stream now also fetches Pump-context `Migrate` transactions.
- The early worker stores `migrate` as persist-only evidence.
- The lifecycle watch records an on-chain graduation and promotes the mint to HOT. This fixed a bug where it was scheduled WARM before the first market sample.

**Already done earlier:**
- v3 trade-tape coverage (27/27 on mainnet) and the IDL drift doctor;
- DEX first-seen intervals.

**Still open for M5:**
- Decode PumpSwap trades on-chain. The program ID is now verified by this case; the event layout is not.
- 30/60/120 s cumulative snapshots with buyer/seller diversity and curve progress.
- A Python ingestion benchmark (p50/p95/p99).
- Live/backfill parity fixtures for out-of-order and rollback cases.

### G2: replay and risk independence

The hard-block part is done (`test_g2_hard_block_precedence.py`, 21 tests).

Every `FastSafetyGate` hard block (11) and every missing critical input (7) was run at score 100 and confidence 1.0, with all other gates satisfied. In every case there is no `ENTRY_READY` and no notification eligibility, and the hard block's reason code is present. A provider outage or stream gap blocks entry. Telegram relevance rejects `BLOCK`, `CAUTION` and `UNKNOWN`.

Not yet covered: no-lookahead checks for feature preprocessing. These are part of M7 and M8.

## Forward shadow capture: frozen identities (M9 prerequisite)

The live ingestion and lifecycle watch already write launch, migrate, `lifecycle.signal` and `lifecycle.outcome` rows. A named run must be started on the operator's Compose host, which is the only always-on runtime. Record these values when starting it:

| Field | Value |
| --- | --- |
| Proposed run ID | `shadow-2026-11-25-pumpfun-v1` |
| Source SHA | the commit pulled on the host (≥ `daf629b`) |
| Eligibility | `pumpfun-all-observed-launch-v1` |
| Early score policy | `early-score-v2`, `sha256:52ca31a4…6262` |
| Lifecycle policy | `sha256:ea8388bc…c1af` |
| Label assumptions | `sha256:96e9c7b5…a18d` |
| Manual exit policy | `sha256:f547cf7b…d9ca` |
| Earliest 1h maturity | start + 1 h; 72h labels mature at start + 72 h |
| G5 30-day cohort | earliest mature at start + 30 d + 72 h |

The run has not been started from this sandbox, which has no persistent runtime. G5 stays pending.

## Gate ledger

| Gate | State | Evidence or blocker |
| --- | --- | --- |
| G0 runtime | Local scope PASS | M0 report. Open: worker traffic drill on Compose, upgrade of the operator's database. |
| G1 data coverage | PARTIAL | Two nested bounded windows with 100 % two-source agreement and 0 unresolved slots. A ≥99 % claim needs many non-overlapping normal-operation intervals and live-stream capture of the same intervals. |
| G2 replay/risk | Hard-block part PASS | 21/21 fixtures. The no-lookahead part waits on M7/M8. |
| G3 predictive | NOT STARTED | Needs mature labels. All targets are `INSUFFICIENT_SAMPLES` / `NOT CALIBRATED`. |
| G4 economic | NOT STARTED | Needs `EXECUTABLE_QUOTE_PEAK`/PAPER outcomes from a frozen forward run. |
| G5 operational | PENDING | 7-day and 30-day runs on the host; a real Telegram receipt from an authorized recipient. |
| G6 release | NOT STARTED | Frontend parity for the new evidence (M10), rollback drill. |

## Not started in this session, with reasons

| Milestone | Status |
| --- | --- |
| M3 wallet/creator graph | No external labels yet. Creator counts per cohort are available from M1. |
| M4 narratives | No permitted social feed is configured. The X/Telegram terms need the operator's decision. |
| M6 size buckets USD 250/1,000 | Only the existing USD 50 probe exists. Larger buckets will strain the keyless Jupiter quota. |
| M7, M8, M11 | Need mature, frozen cohorts. |
| M10 UI | No new UI in this session. |
| R1 Robinhood | No verified launchpad or factory addresses yet. |

## Artifact digests (sha256, `artifacts/research/`)

```
    c0f99740db0b476ba4f6a895154d92b37bd51e3ae7058769084c1d1dec3a630d  2026-11-25-m1-window1/cohort-manifest.json
    fafd7ebe349e469d9f62680f0de80047f3a551a46477da6fd31db584eb3c3ec0  2026-11-25-m1-window1/coverage-ledger.json
    d90cc02992beac156a290b705bea10612b1323d54d7fc17d899b8e54a05d0d32  2026-11-25-m1-window1/inventory-independent.json
    b5910a73509a1820da9a178ba2bcf886d346243d03f1af06f6f47df1fae10820  2026-11-25-m1-window1/inventory-primary.json
    cf4a05edb8ccb27be2e00b890410284c2bb9d42cffeb62660a1fecad13f4e1e3  2026-11-25-m1-window2/cohort-manifest.json
    7a8c4dece6478ec14f8d156872dca69dd995b8e8c71d559eba5caf284294aa7f  2026-11-25-m1-window2/cohort-summary.json
    c43177c0a068fcfdb0bb5f81ae9d93cc0210409798a7c7429fc23bdeeac464cd  2026-11-25-m1-window2/coverage-ledger.json
    0e7e984e062eb5f3dc3302a4ce7a6a0801fe9dec5b3ecd17a3095255a495165d  2026-11-25-m1-window2/inventory-independent.json
    44ddeac137dfca869c20e2f8e4300ad4fdaaac04b2a8fa25de5fbb7e2f121b0a  2026-11-25-m1-window2/inventory-primary.json
    84a5e397979d96a594462a6aace2c5ddb5dbfe87900cdb4c25350bd0fd247a43  2026-11-25-m1-window2/migration-case.json
```
