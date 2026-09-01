# Cross-cutting hardening design

## Goal

Complete the remaining independent keyless backlog after Gate P11 without
unlocking Phase 12. The work makes the existing read API, dependency supply
chain, data handling policy, deterministic scoring/state behavior and provider
health evidence easier to operate and review.

## Non-goals

- no quote endpoint, transaction builder, signer, wallet key or submission path;
- no live-money execution or operating-mode change;
- no provider credential requirement or fabricated live-provider result;
- no Rust/Yellowstone extraction before the measured E11.1 bottleneck gate;
- no provider SDK imports into domain/application contracts.

## Design

1. Treat the existing FastAPI `/v1` route surface and generated OpenAPI schema
   as the versioned API contract. Add a contract test and concise operator
   documentation; health endpoints remain unversioned operational probes.
2. Generate a deterministic CycloneDX JSON SBOM from the pinned Python/npm
   locks and versioned image bases using only the standard library. The review
   command validates the generated component set without contacting providers
   or persisting secrets.
3. Record retention, minimization, privacy and provider-terms operating rules
   in versioned documentation. Automatic destructive retention remains off;
   legal/provider acceptance is explicitly external where applicable.
4. Add deterministic property-style invariant tests over score bounds,
   protected strategy policy, lifecycle transitions and stream cursor progress.
   A fixed seed and bounded case count make failures reproducible in CI.
5. Add a provider-independent health selector over normalized health records.
   It may select only healthy registered providers, reports degraded/unknown/
   conflicted evidence explicitly, and cannot affect AlphaScore or execution.

## Verification

- focused contract/unit/property tests;
- SBOM reproducibility and secret-shaped-field checks;
- Ruff, mypy and full `make verify`;
- frontend lint/typecheck/test/build and OpenAPI route contract;
- protected modes and external blockers recorded in `docs/STATUS.md`.
