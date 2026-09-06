# MemeRadar API contract

The FastAPI composition root publishes a generated OpenAPI document at
`/openapi.json`, with interactive documentation at `/docs` and `/redoc`.
The current application contract is version `0.1.0`; business routes are
namespaced under `/v1`.

## Compatibility rules

- Additive response fields and new endpoints may be introduced within `/v1`.
- A breaking request, response, authentication or semantic change requires a
  new version namespace such as `/v2` and a migration note.
- `/health/live` and `/health/ready` are operational probes and remain outside
  the business API version namespace.
- The generated OpenAPI document and `tests/contract/test_api_schema.py` are
  the route-surface contract; the test must be updated with any intentional
  endpoint addition or version change.

## Current routes

Read-only routes use GET and preserve explicit empty, unavailable, stale,
unknown and invalid states:

```text
GET  /v1/audit/events
GET  /v1/candidates
GET  /v1/candidates/{candidate_id}
GET  /v1/chain-opportunities
GET  /v1/config/versions
GET  /v1/control/config
GET  /v1/control/state
GET  /v1/operations/overview
GET  /v1/positions
GET  /v1/positions/{position_id}
GET  /v1/providers/health
GET  /v1/tokens/{token_id}
GET  /v1/tokens/{token_id}/timeline
GET  /v1/wallets
GET  /v1/wallets/{address}
```

## Opportunity discovery and research semantics

`GET /v1/chain-opportunities` is the read-only chain-heat projection for the
mandatory `SOLANA`, `BNB` and `ROBINHOOD` discovery chains. It preserves
chain-qualified identities, provenance, timestamps, freshness and explicit
`UNKNOWN`/degraded states; its response is advisory and always has
`execution_eligible: false`.

The opportunity case-study and ablation outputs are cold-path research
artifacts, not API decisions. `fixtures/research/opportunity_research_report.json`
is generated from canonical replay prefixes with TRAIN/VALIDATION/TEST
metadata, no-lookahead verification and independent feature-family metrics.
The checked-in seven-case synthetic/redacted artifact is
`INSUFFICIENT_SAMPLES`, so it cannot change production score weights or pass
the strategy-promotion gate.

Explicitly authenticated mutation routes are limited to the control/manual
surface:

```text
POST /v1/control/analysis-kill-switch
POST /v1/control/config
POST /v1/control/execution-kill-switch
POST /v1/manual/mints
```

These routes do not change the protected operating modes, create an
`ENTRY_READY` decision, sign a transaction or submit live money. The manual
route is an analysis-only validation seam and remains disabled for execution.

## Authentication and data handling

When role tokens are configured, server-side bearer authentication enforces
the required read/operator/admin permission. Viewer credentials are never
sent to the browser. The API returns normalized, bounded projections with
provenance, timestamps, freshness and reason codes; raw provider payloads,
credentials and secret-shaped fields are withheld. LLM narrative data is
advisory and cannot grant execution authority.

The schema describes the API shape, not live-provider availability. Missing
provider credentials, network access or external acceptance remain explicit
`BLOCKED_EXTERNAL` operational conditions.
