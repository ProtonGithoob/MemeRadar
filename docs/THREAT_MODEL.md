# MemeRadar Threat Model

Version: `threat-model-v1`
Reviewed: 2026-09-01
Scope: analysis-only and paper-trading deployment

## Security objective

MemeRadar processes adversarial Solana, market, social, wallet and provider
content to produce explainable research evidence. The system must preserve
evidence provenance and fail closed when identity, freshness, authorization or
provider integrity is unknown. No model output, external label or operational
signal may authorize a live trade.

## Assets and trust boundaries

| Asset | Trust boundary | Required protection |
| --- | --- | --- |
| Normalized token, chain, market and social evidence | untrusted provider/network input to domain | schema validation, provenance, freshness, no-lookahead and conflict states |
| Provider/API credentials | deployment secret boundary | environment/secret manager only, server-side bearer use, redacted errors/logs |
| Role identity and control state | API authentication boundary | constant-time bearer comparison, explicit RBAC, immutable audit/config records |
| Narrative prompts and outputs | untrusted content to optional LLM boundary | delimit/sanitize input, strict bounded output, advisory-only result, no tools |
| Reliability/operations telemetry | application projection to operator UI | bounded allow-list, explicit UNKNOWN/UNVERIFIED/DEGRADED/DOWN, no score/execution path |
| Event log, outbox and paper ledger | application to persistence boundary | append/idempotent semantics, durable replay identity, no invisible correction |
| Protected operating modes | configuration/control boundary | `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false` |

The browser receives server-rendered bounded projections and no provider
credentials, wallet material or raw provider payloads. The application/domain
layers do not import provider SDKs or execution interfaces. The optional
execution boundary is not part of the current deployment.

## Threats and controls

| ID | Threat | Existing control | Residual risk / evidence |
| --- | --- | --- | --- |
| T1 | Secret, cookie or private-key material enters tracked files or logs | high-confidence secret scan, bounded/redacted doctors, source contract checks | scanner patterns are not a substitute for secret-manager audit; `make secret-scan` and `make security-review` pass |
| T2 | Dependency or image supply-chain vulnerability | exact Python/npm lock metadata, versioned image bases, non-root image users, npm advisory scan | pip-audit/Trivy and registry freshness require external access; current local external review is `BLOCKED_EXTERNAL` |
| T3 | Bearer credential bypass or role escalation | constant-time comparison, role-scoped authorization, protected config allow-list and explicit 401/403 contracts | deployment TLS, rotation and rate limiting remain operator responsibilities |
| T4 | Prompt injection or malicious narrative output | untrusted delimiters, secret/instruction/tool sanitization, strict schema/config/evidence validation, `execution_eligible() == false` | optional model/provider behavior still requires operational monitoring |
| T5 | Spoofed mint, protocol or external label | canonical identity validation, full program/discriminator routing, internal wallet/risk authority and corroboration-only external labels | unverified protocol definitions remain non-authoritative |
| T6 | Provider poisoning, outage, stale data or stream gap | provenance/freshness/conflict states, recovery telemetry, operations degradation policy and fail-closed scoring | live provider acceptance remains `BLOCKED_EXTERNAL` |
| T7 | Browser or operational signal gains trade authority | GET-only bounded reads, no frontend mutation/signing path, operational health excluded from AlphaScore and execution | Phase 12 remains locked by protected modes and explicit operator decision |
| T8 | Duplicate/replayed event, order or notification mutates history | idempotency keys, append-oriented evidence, durable outbox leases and replay manifests | persistence/backup operations require the documented runbooks |

## Review evidence

The deterministic local review is reproducible with:

```text
make security-review
make verify
make frontend-build
docker compose -f infra/compose/docker-compose.yml build api worker web
```

The optional external review is:

```text
make security-review-external
```

It returns `BLOCKED_EXTERNAL` when a vulnerability database, scanner or
registry is unavailable and never reports that state as a clean scan. On
2026-09-01, npm advisory access identified and the repository fixed the high
severity Playwright `<1.55.1` issue by pinning `@playwright/test` and its
transitive Playwright packages to `1.62.1`; a subsequent `npm audit` reported
zero vulnerabilities. Pip-audit and Trivy were not installed locally.
