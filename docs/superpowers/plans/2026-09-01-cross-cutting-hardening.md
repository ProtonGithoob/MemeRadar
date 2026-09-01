# Cross-cutting hardening implementation plan

> Continue only after Gate P11. Phase 12 remains locked by explicit policy.

## Task 1: API version and OpenAPI contract

- [x] Add an API contract test for the generated OpenAPI schema and current
  `/v1` paths.
- [x] Document versioning, authentication, read-only response guarantees and
  operational health endpoints.
- [x] Run the focused API contract tests (`3 passed`).

## Task 2: Deterministic SBOM and dependency evidence

- [x] Add a standard-library CycloneDX exporter for the Python/npm locks and
  container base references.
- [x] Add deterministic tests and `make sbom`/CI wiring.
- [x] Record the generated evidence and npm remediation without claiming that
  unavailable pip-audit/Trivy scans passed.

## Task 3: Data handling and architecture records

- [x] Document retention/partition/minimization and privacy/provider-terms
  rules with safe non-destructive defaults.
- [x] Add ADRs for provider-independent boundaries and protected execution.
- [x] Add contract checks for the policy documents and update roadmap/status
  (`3 passed`).

## Task 4: Deterministic invariants

- [ ] Add fixed-seed property-style tests for score bounds, state transitions
  and stream cursor/gap safety.
- [ ] Include them in the normal test gate without weakening existing tests.

## Task 5: Provider health comparison/routing seam

- [ ] Add normalized provider-health selection/comparison contracts outside the
  domain and without provider SDK imports.
- [ ] Test deterministic healthy preference, degraded/unknown/conflicted
  outcomes and no execution/score authority.
- [ ] Document that routing remains evidence-only until live acceptance.

## Task 6: Checkpoint

- [ ] Run focused checks, full quality gates and final secret/diff checks.
- [ ] Update `docs/STATUS.md`, commit and push.
- [ ] Keep Phase 12, E12.1 and E11.2 locked/conditional.
