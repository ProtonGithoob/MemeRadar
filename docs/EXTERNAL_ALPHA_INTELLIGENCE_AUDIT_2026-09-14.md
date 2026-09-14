# External Alpha Intelligence — Implementation Audit

Audit date: 2026-09-14
Repository baseline: `b9c46b3fb3c881ca04c76ed9e25872ecc86e5c15`
Audit scope: the approved Option A package, before production-code changes.

## Upstream refs and reuse decisions

| Repository | Audited ref | License state | Decision |
|---|---|---|---|
| [`GMGNAI/gmgn-skills`](https://github.com/GMGNAI/gmgn-skills) | `4a48b8a31e19b62c96ee57ba76b46310f84043f0` | Root `LICENSE` is MIT | Direct read contract verified; behavior independently implemented in the existing Python provider seams. |
| `SoCloseSociety/WhalegodTG` | `3b0733ceb8d0bd10f52d21e86ae97ca0aa9f49a6` | Root `LICENSE` is MIT | Factual taxonomy concept only; no Telegram, SQLite, webhook or alert code copied. |
| `numi-ai/numi-trading-agent` | `cb460ff96508c8fdae64ac169b4fc6cc2703f4ff` | README/package declare MIT; root `LICENSE` not found | Lifecycle invariants only; no source, tests, comments, signer or 1inch path copied. |
| `CodeMuscle/solbeam` | `234423a8f0180deffc6b9d83fa84e35687049670` | README declares MIT; root `LICENSE` not found | Documentation/UI research only; no dependency, model or runtime copied. |

The upstream refs and license findings agree with the dated reuse registry and
influence register. No restricted or ambiguous source was copied.

## GMGN contract decision

The current GMGN implementation exposes an auditable server-side HTTP client:

- Base host: `https://openapi.gmgn.ai`.
- Read routes audited in [`OpenApiClient.ts`](https://raw.githubusercontent.com/GMGNAI/gmgn-skills/main/src/client/OpenApiClient.ts): `GET /v1/market/rank`, `POST /v1/trenches`, `GET /v1/token/info`, `GET /v1/token/security`, `GET /v1/token/pool_info`, top holders, top traders, KOL and Smart Money routes.
- Read authentication is explicit `X-APIKEY`, Unix-second `timestamp` and UUID
  `client_id`; the signed `X-Signature` path is used by upstream swap/order
  functions and is deliberately excluded.
- The upstream skill docs define rank/trenches envelopes and token/security
  fields; response `code == 0`, HTTP status, rate-limit reset and bounded list
  handling are treated as contract conditions.

This is sufficient for a bounded, read-only backend adapter. MemeRadar uses the
rank, token info, security, top-holder and top-trader read routes only. No
`gmgn-cli` subprocess, browser scraping, private key, wallet custody, swap,
order, cooking, copy-trading or provider-owned scorer/risk engine is present.

Runtime activation remains `optional=true`, disabled by default, not required
for application health, read-only, `LIVE_SHADOW`, and score weight `0`. A
missing API key or unavailable external service is reported as configuration or
external evidence absence; no live sample is fabricated.

## Implementation audit result

- GMGN is independently implemented as a provider adapter using existing
  transport, exception, provenance, UTC timestamp, chain/address, redaction,
  candidate collector, persistence and readiness seams.
- Helius receives one factual `activity_kind` field in the existing normalizer;
  ambiguous or weak evidence is `UNKNOWN`, and no directional conclusion is
  added.
- The canonical launch lifecycle remains the only lifecycle. Regression tests
  cover bonding versus DEX route, graduation versus verified liquidity,
  first-liquidity versus first-swap timestamps, and weak GMGN corroboration.
- Existing event-time replay/ablation infrastructure remains the future
  baseline-versus-GMGN measurement path. Production scoring weights and all
  execution modes are unchanged.
- Real readiness counts accept only provider-owned `REAL_EXTERNAL` observations
  and explicitly exclude fixtures, synthetic data, demos, replay-only data and
  redacted examples. Missing labels remain `UNKNOWN`/`INSUFFICIENT_SAMPLES`.
