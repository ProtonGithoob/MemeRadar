# PROD_READ_ONLY Root-Cause Hardening Plan

> Execute this plan in the current repository without enabling live-money execution.

## Goal

Close repository-controlled production-read-only correctness and release gaps while preserving the canonical evidence, provider, readiness, lifecycle and protected-mode boundaries. External credentials, hosting, GitHub billing/permissions and managed operations remain explicit acceptance inputs.

## Constraints

- Reuse existing Settings, evidence policy, provider metadata/composition, persistence/readiness, Makefile, Dockerfiles and release tooling.
- Keep `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Keep GMGN `LIVE_SHADOW` and weight zero; no provider-specific scorer, risk engine, lifecycle or execution path.
- Use TDD for production behavior: failing focused regression, smallest fix, focused/related/full verification.

## Tasks

1. Harden web control trust: viewer-only GET, production mutation deny-by-default, no browser-to-admin proxy, and adversarial route tests.
2. Add explicit `APP_ENV` allow-list and service-specific runtime validators; remove API role/execution credentials from the worker contract and test API/worker least privilege.
3. Separate local and production Compose contracts; require production secrets/configuration, validate enabled-chain transport, and align Helius/GMGN/Robinhood metadata with runtime capabilities.
4. Make evidence isolation fail closed for recognized modes, provider payload promotion claims and newly written missing-mode observations while preserving an audited pre-boundary legacy read path; add full decision-chain equality coverage.
5. Extend CI with PostgreSQL16 integration, runtime dependency audit, deterministic security/build/image gates and release identity dependencies.
6. Add reusable production-stack smoke/soak and backup/restore/release-image targets by reusing existing tooling; keep the synthetic benchmark explicitly synthetic.
7. Add release-image identity fields and documentation/status evidence; run focused, full, database, frontend, browser, security, SBOM, Compose, doctor and release checks.
8. Audit final diff for duplication, secret leakage, protected-mode/weight changes, document every external blocker, commit logical changes and synchronize `main`.

## Verification order

Run focused regression tests first and prove pre-fix failures where behavior is currently wrong. Then run related Python/frontend/Compose checks, PostgreSQL integration, production build/browser checks, security/audit/SBOM checks, provider doctors, stack smoke/soak and release identity. Finish with `git diff --check`, full repository-native gates, final status/matrix synchronization and clean push verification.
