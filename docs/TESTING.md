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

Sprint 6.3 adds decision-state replay for sequential `WATCH`, `STRONG_SETUP`
and `ENTRY_READY` transitions, fail-closed blocked/unknown/stale risk,
confidence caps, hysteresis floors, cooldown suppression, deterministic
score-delta/risk-escalation events and an event-time timeline projection. The
contract compares repeated fixture replay and reversed timeline delivery,
checks separate occurred/observed/ingested timestamps, provenance and an
`as_of` no-lookahead boundary, and verifies that the application seam has no
provider/persistence/execution imports. The opt-in Postgres suite also
rehydrates a multi-transition candidate with stable decision identity.

Sprint 7.1 adds alert-pipeline contracts for deterministic projection of
meaningful decision/risk/provider-health events, bounded reason/evidence
rendering, secret-shaped text redaction, alert dedupe, suppression and
per-destination rate limiting. Telegram provider tests use an injected HTTP
client and cover `sendMessage`, `getMe`, authentication, rate-limit, timeout,
transport/schema failures and HTTPS/credential boundaries. The fixture replay
exercises the `NotificationPort` without credentials; the opt-in Postgres
suite verifies alert round-trip plus notification outbox delivery/dedupe, and
Compose smoke/runtime checks verify the worker import and health seam. Missing
Telegram configuration is a key-safe `BLOCKED_EXTERNAL` doctor result, not a
fabricated provider PASS.

Sprint 7.2 adds strict TestClient coverage for all nine read routes, response
page envelopes, ranking/filter conversion, cursor traversal, correlation
headers, missing-resource `404`, unconfigured-storage `503`, invalid UUID or
address `422`, extra-query rejection, bounded time windows, unknown provider
health and permanent non-authorizing response fields. Application and
persistence contract tests assert that FastAPI/SQLAlchemy/provider imports do
not cross the application read boundary, all read routes are GET-only, and
secret-shaped values/raw references do not escape. The opt-in Postgres test
round-trips a candidate, latest score/risk, transition, feature, observation
and alert through the read adapter and verifies event-time timeline pagination
and no-lookahead. Replay repeats identical output and cursor traversal.
Keyless focused evidence before the full gate: route regression `29 passed`,
Sprint 7.2 replay/Compose contracts `29 passed`, read application/persistence
unit tests `14 passed`, and the opt-in Postgres read adapter test `1 passed`.

Sprint 7.3 adds role-token/RBAC coverage for viewer, operator, admin and
execution principals, including `503` unconfigured auth, `401` malformed or
wrong bearer values, `403` permission separation, strict mutation bodies,
correlation IDs and secret non-disclosure. Control replay covers safe defaults,
idempotent kill activation, protected clear refusal, allow-listed config
validation, canonical hashes and audit pairing. The opt-in Postgres suite
round-trips the singleton state, immutable config version and audit rows,
rehydrates them through a new adapter and projects them through the read API;
the `0003` to `0004` downgrade/upgrade path is verified. Configured role
credentials also protect existing read routes while keyless local development
remains available. No control test can change the four protected modes or
introduce signing/submission authority.

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
