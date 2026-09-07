# MemeRadar Production Readiness

**Current checkpoint:** Alpha Caller Task 15 complete at `2acf261` before this readiness roadmap.

**Current classification:** `NOT_PRODUCTION_READY` for real-alpha or live-money claims. Engineering verification is strong, but checked-in alpha evidence remains `SYNTHETIC_REDACTED` / `INSUFFICIENT_SAMPLES` and real X/Telegram/provider/live-shadow evidence is still externally incomplete.

Canonical spec: `docs/superpowers/specs/2026-09-07-real-alpha-production-readiness-design.md`

Execution plan: `docs/superpowers/plans/2026-09-07-real-alpha-production-readiness.md`

## Staged target

| Stage | Meaning | Current |
|---|---|---|
| `PROD_READ_ONLY` | Real providers/ingestion/API/dashboard/Telegram, no order creation | NOT ACCEPTED |
| `PROD_PAPER_AUTO` | Real-time fail-closed automated paper positions, no signing/live orders | NOT ACCEPTED |
| `LIVE_MONEY_CANDIDATE` | Evidence package may be reviewed under a separate future design | NOT ELIGIBLE |

Protected modes remain:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

## Acceptance gates

| Gate | Requirement | Initial status | What closes it |
|---|---|---|---|
| PR-1 Engineering/release | Canonical tests, lint/typecheck, migrations, security/SBOM, build, remote CI, release identity, rollback | PARTIAL | Local verification already reported strong; obtain actual remote CI/release-candidate evidence and reproducible rollback metadata |
| PR-2 Provider/evidence | Required real chain/market/social/Telegram capabilities with freshness/provenance and stable doctors | BLOCKED_EXTERNAL/PARTIAL | Configure compliant real provider access; prove bounded live/historical reads and health states without exposing secrets |
| PR-3 Historical-real research | Leakage-safe real positive/negative dataset and real ablation | INSUFFICIENT_SAMPLES | Collect/reconstruct sufficient historical real calls/tokens and rerun canonical research |
| PR-4 Live-shadow | Sustained real observation, replayability, latency/freshness and matured paper outcomes | INSUFFICIENT_SAMPLES | Run durable live-shadow collection and mature enough signals across required capability set |
| PR-5 Operations | Backups/restore, monitoring/alerts, soak/failure tests, deployment/rollback runbooks | PARTIAL/NOT VERIFIED | Execute production-like operational acceptance with recorded evidence |
| PR-6 PROD_READ_ONLY | PR-1 + PR-2 + PR-5 PASS | NOT ACCEPTED | Complete dependencies; PR-3/PR-4 may still be insufficient because read-only prod can collect evidence |
| PR-7 PROD_PAPER_AUTO | PR-1..PR-5 PASS plus real-environment paper-auto fail-closed acceptance | NOT ACCEPTED | Complete evidence and operational gates |
| PR-8 LIVE_MONEY_CANDIDATE | Separate future operator-approved design plus all prior evidence | OUT OF SCOPE | Never auto-enable from this roadmap |

## Minimum evidence targets

These are initial versioned guardrails for sample adequacy, not profitability promises:

- target >=1000 matured historical real calls;
- target >=50 distinct caller/source identities;
- target >=500 matured chain-qualified token outcomes;
- target >=40% negative controls in final evaluation dataset;
- no caller/source >10% of TEST partition;
- target >=14 consecutive calendar days live-shadow;
- target >=200 matured actionable live-shadow signals, otherwise remain `INSUFFICIENT_SAMPLES`;
- chronological/leakage-safe TRAIN/VALIDATION/TEST split;
- executable outcomes after modeled fees/slippage/impact rather than headline ATH;
- no future-label mutation or survivorship test failure;
- promotion requires human review and never changes protected modes automatically.

## Production data capability checklist

Required/expected production capability classes:

- Solana RPC/read stream with gap/freshness handling;
- BNB generic-EVM reads;
- Robinhood generic-EVM reads;
- market/liquidity reference data;
- execution-quote semantics for paper realism;
- compliant historical/live X/social source where configured;
- configured Telegram historical/live source;
- wallet/security enrichment where selected;
- durable PostgreSQL/Redis and queue state;
- Telegram notification delivery.

Each capability must report `READY`, `DEGRADED`, `RATE_LIMITED`, `STALE`, `CONFIGURATION_MISSING`, `BLOCKED_EXTERNAL` or `UNSUPPORTED`. Application health and provider capability health are separate.

## Deployment checklist

Before `PRODUCTION_READY_READ_ONLY`:

- production environment configuration validates and unsafe mode combinations fail startup;
- secrets are environment/secret-manager injected, never repository/image/frontend/log values;
- DB migration path tested on production-like data;
- backup policy configured and restore drill objectively succeeds;
- retention/privacy rules for raw social/provider data reviewed;
- PostgreSQL pool/timeout/index assumptions validated at realistic volume;
- Redis/queue recovery behavior verified;
- live/replay/backfill share canonical normalization/identity semantics;
- observability covers ingestion lag, provider health, queue age, stream gaps, parsing, resolution, quote freshness, decision/alert latency, DB/Redis/API/worker health;
- alerts exist for ingestion stop, stale critical evidence, provider loss, stream gaps, queue growth, DB pressure/migration mismatch and Telegram delivery failure;
- production-like soak and provider/DB/Redis/Telegram failure tests completed;
- remote CI succeeds against exact release candidate;
- release artifact records git SHA, app/schema/migration/config identity and SBOM;
- rollback/forward-fix runbook is tested/documented.

## Alpha acceptance checklist

Before any caller/social/smart-money/opportunity promotion:

- historical real and live-shadow evidence use the same canonical event-time semantics;
- winner-first reverse caller discovery includes negative controls and late/failed calls;
- call timestamp -> decision -> quote -> paper entry timeline is measurable;
- mark-price multiple cannot substitute for executable multiple;
- ablations compare baseline, caller-only, smart-money-only, opportunity-only, caller+smart-money, caller+opportunity and full fusion;
- false-positive costs, precision/recall, confidence intervals, executable expectancy and drawdown are reported;
- chain/caller/archetype/regime segmentation is explicit;
- insufficient confidence remains `INSUFFICIENT_SAMPLES`;
- TEST/live-shadow results are not tuned back into the candidate.

## Release naming rule

Allowed final classifications for this roadmap:

- `PRODUCTION_READY_READ_ONLY`
- `PRODUCTION_READY_PAPER_AUTO`

Forbidden without a separate future approved design/evidence package:

- generic `PRODUCTION_READY` implying live-money readiness;
- `LIVE_TRADING_READY`;
- automatic changes to `MANUAL_EXECUTION` or `AUTO_EXECUTION`.
