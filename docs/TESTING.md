# Testing and Verification Strategy

## Principle

MemeRadar must be testable without external credentials and verifiable against real providers when credentials/network are available. External outages must never be disguised as application success.

## Test layers

### Unit
Cover provider-independent domain/application behavior:
- state transitions;
- scoring and penalties;
- hard risk gates;
- confidence/freshness;
- wallet scoring;
- feature windows;
- sizing/exit policies;
- idempotency/reason codes.

### Property / fuzz
Use where valuable for:
- AlphaScore always 0..100;
- hard blocks cannot be bypassed by score;
- stale critical evidence never becomes execution-eligible;
- duplicate events/orders never duplicate side effects;
- state machine invariants;
- money/quantity arithmetic.

### Integration
Real local dependencies via containers:
- PostgreSQL repositories/UoW;
- migrations;
- outbox/retry/recovery;
- Redis coordination fallback behavior;
- API composition/auth.

### Provider contract
Each provider adapter gets recorded/synthetic fixtures for:
- normal response;
- missing/null fields;
- schema change/error;
- 401/403;
- 429;
- timeout;
- malformed data;
- reconnect for streams.

### Replay
A fixed event dataset must reproduce identical:
- observations/features;
- risk decisions;
- AlphaScores;
- state transitions;
- paper trades/exits,
given identical code/config/model versions.

### End-to-end
Run API + worker + DB + Redis + web using fake providers:
- candidate discovered;
- enrichment;
- score/risk;
- alert;
- dashboard appearance;
- paper entry/exit;
- audit trail.

### Browser
Critical UI flows:
- Radar filtering;
- token detail/timeline;
- wallet/provider pages;
- paper positions;
- auth/RBAC;
- settings validation;
- kill-switch controls.

## Live provider acceptance

Live tests are opt-in and read-only until Phase 12. They must be clearly marked and never make CI depend on paid credentials.

A live provider acceptance report records:
- timestamp;
- provider capability;
- redacted environment;
- request/stream success;
- schema parse;
- latency/freshness;
- rate-limit metadata;
- result PASS / BLOCKED_EXTERNAL / FAIL.

## Execution testing progression

1. fake quote/execution provider;
2. recorded Jupiter quote fixtures;
3. live read-only quotes;
4. transaction simulation/dry run;
5. explicit tiny-size manual acceptance;
6. failure and duplicate-submission tests;
7. auto execution remains locked pending explicit later approval.

## Backtest integrity

- Event-time processing only; no future feature leakage.
- Time-based train/validation/test splits.
- Include failed/dead/rugged tokens, not only survivors.
- Include realistic fees/slippage and liquidity constraints.
- Record dataset manifest, code commit and config hash.
- Report distribution, drawdown and score-bucket calibration, not only total return.

## Quality gates

Phase 0 should expose a single command such as `make verify` that eventually includes:

```text
backend format/lint
backend static typing
backend unit/integration tests
migration validation
frontend lint
frontend typecheck
frontend unit tests
security/secret checks
```

Browser/live-provider/soak tests may be separate commands but must be documented and invoked at relevant phase gates.

## Coverage

Do not chase a vanity global percentage. Require strong coverage around high-risk deterministic domain code and regression tests for every production bug. Critical risk/execution modules should have branch/edge-case coverage materially higher than presentation code.

## Performance verification

Measure:
- event ingestion throughput/lag;
- score computation latency;
- provider fan-out latency;
- DB query p95 for Radar/timeline;
- replay throughput;
- queue/outbox backlog recovery.

Sprint 6.1 adds credential-free feature-window replay and persistence checks:
the fixture must reproduce identical `1m`/`5m`/`15m` snapshot IDs, values,
provenance, quality and config identity regardless of delivery order; future
evidence must produce `INVALID`/zero-confidence snapshots; and the opt-in
Postgres repository test must round-trip JSON-safe values and provenance while
accepting an equivalent duplicate and rejecting conflicting snapshot reuse.

Sprint 6.2 adds golden score replay for correlated, sparse/unknown,
penalty-clamp and blocked-risk inputs. It verifies stable score identity under
reversed component/penalty delivery, exact weighted arithmetic, bounded
penalties, strategy/model/config identity, hard-risk reason preservation and
pre-boundary rejection. The opt-in Postgres path persists feature, risk and
score rows together and verifies duplicate acceptance plus JSON-safe
round-trips.

Add regression thresholds only after a stable baseline exists.

## Failure tests

Before production analysis acceptance test:
- provider 429/outage;
- websocket disconnect/reconnect;
- DB restart;
- Redis outage;
- Telegram outage;
- malformed provider payload;
- duplicate/reordered events;
- LLM outage/malformed structured result;
- stale risk evidence.

Before any live trading acceptance additionally test:
- stale/changed quote;
- insufficient balance;
- slippage/impact breach;
- duplicate order request;
- submission timeout with unknown chain status;
- transaction failure;
- reconciliation after restart;
- kill switch during active monitoring.

## Completion evidence

`docs/STATUS.md` must state exact commands and results. Never write “all tests pass” unless they were actually run in the current relevant environment.
