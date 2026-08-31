# Phase 9 Sprint 9.3 Position UI / Telegram Design

## Goal

Expose paper positions as bounded, explainable read projections and route
position/exit-risk events through the existing alert and notification outbox.
The browser and Telegram adapter remain advisory surfaces; neither can mutate a
position, change a mode, sign, submit or authorize an order.

## Existing seams to extend

- `ReadQueryPort` and `SqlAlchemyReadQueryService` remain the only application
  read boundary for the API.
- Existing `PositionRow` values and normalized `ObservationRow` market events
  are the source of paper position and mark evidence; no duplicate position
  table or provider SDK is introduced.
- The existing `AlertEventProjector`, `AlertDeliveryService`, `alerts` table and
  leased notification outbox remain the Telegram path.
- Existing `OperatorHeader`, protected shell, status badges and server-side
  `read-api.ts` gateway are reused by the new positions page.

## Position read contract

Add bounded `PositionQuery`, `PositionView`, `PositionMarkView`,
`PositionPerformanceView`, `PositionExitRiskView` and
`ClosedTradeExplanationView` contracts. The projection contains:

- immutable position identity, mode and lifecycle state;
- quantity, entry/exit prices and timestamps;
- an explicitly observed current mark with provider/source/parser,
  occurred/observed/ingested timestamps and quality state;
- derived current value, unrealized/realized/total PnL, return, MFE and MAE;
- latest evidence-bearing exit risk action, score, confidence, reason codes and
  evidence references;
- closed-trade reason/evidence/policy/config explanation when available.

All numeric values use `Decimal` in Python and bounded finite numbers in the
web parser. Current PnL is `None` when no usable current mark exists or mark
quality is not `FRESH`; persisted realized PnL/MFE/MAE remain visible with an
explicit quality label. An absent quote is `UNKNOWN`, never a zero or a safe
mark. SQL reads allow-list the normalized market price keys and select the
latest event-time observation at or before the optional `as_of` boundary.

Position list ordering is deterministic: open/exit-signalled positions first,
then latest event time descending, then UUID. Pagination is bounded and
resource-scoped. Every response includes `execution_eligible: false` and the
API exposes GET-only `/v1/positions` and `/v1/positions/{position_id}` routes.

## Telegram projection

Extend `AlertEventProjector` for `ExitSignal`, `ExitEvaluation` and
`PaperExit` event kinds. `EXIT_RISK` is emitted only when the event contains an
actual non-HOLD exit recommendation; a HOLD evaluation remains timeline
evidence and does not create notification noise. A closed paper result may
emit `PAPER_EXIT`. Both payloads are bounded to token/position identity,
action/fraction, PnL if explicitly supplied, reason codes and evidence refs.
External-only exit evidence remains non-triggering, and the existing alert
policy, dedupe, rate limit, retry, redaction and protected modes apply.

## Frontend

Add a server-rendered `/positions` route and typed gateway functions. The page
shows open and closed paper positions, observed mark freshness, derived PnL/MFE/
MAE, latest exit risk and closed-trade explanation. It renders explicit
`UNKNOWN`, `STALE`, `INVALID` and unavailable states, preserves API order, and
contains no forms, mutation controls, wallet material or client-side provider
fetch. The header navigation links to the page. A boundary card labels all
values as paper/advisory and execution as locked.

## Verification

TDD/contract tests cover position validation, deterministic ordering and
pagination, current-mark PnL arithmetic, stale/unknown fail-closed behavior,
closed explanation, SQL projection from positions/observations/exit events,
GET-only API routes, redaction and no execution authority, exit alert
projection/deduplication and frontend parsing/rendering. The existing full
quality gate and opt-in Postgres test remain required. Live quote and Telegram
acceptance are `BLOCKED_EXTERNAL` when credentials/endpoints are absent.
