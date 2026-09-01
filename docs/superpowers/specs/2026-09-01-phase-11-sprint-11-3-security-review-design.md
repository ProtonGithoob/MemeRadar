# Phase 11 / Sprint 11.3 — Security Review Design

## Goal

Produce a repeatable, key-safe security review for the analysis-only MemeRadar
deployment. The review must verify local supply-chain and boundary contracts,
attempt optional dependency/container vulnerability scans without leaking
scanner output, and leave external scan results explicitly
`BLOCKED_EXTERNAL` when the required vulnerability database or tool is not
available.

## Security boundary

The review is a developer/CI diagnostic. It has no provider, database, wallet,
signer, transaction-submission or execution authority. It reads repository
metadata and source contracts, invokes only explicitly allow-listed local
scanner commands, records exit classifications rather than raw command
output, and preserves:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Existing role-token authentication, read/control authorization, narrative
prompt sanitization and strict narrative output validation are the source of
truth. The review adds regression contracts around those seams; it does not
duplicate authorization or narrative business logic.

## Review outputs

`scripts/security_review.py` emits `security-review-v1` JSON with separate
statuses for:

- locked Python and npm dependency metadata;
- Dockerfile base-image/runtime-user checks;
- tracked-file secret scanning;
- RBAC/auth/session boundary contracts;
- LLM prompt/data-handling boundary contracts;
- optional `pip-audit`, `npm audit` and container scanner results.

`--keyless-only` is the deterministic local gate and returns zero only when
all local checks pass. `--external` attempts installed scanners and reports
missing tools, blocked vulnerability databases or blocked Docker access as
`BLOCKED_EXTERNAL`; it never converts a missing scan into `PASS`.

## Non-goals

- no live-provider, live-wallet or live-money action;
- no secret discovery or secret printing;
- no automatic dependency upgrades based on scanner output;
- no assertion that a keyless lockfile review proves absence of vulnerabilities;
- no session-cookie system added to an API that currently uses bearer
  authentication and server-side browser reads.

## Residual risk

The local review can prove pinned metadata, source-boundary invariants,
tracked-file secret absence and hardened image construction. Vulnerability
database freshness, registry image provenance, deployed configuration, TLS,
secret-manager policy and production RBAC remain deployment responsibilities
and are not claimed from a keyless checkout.
