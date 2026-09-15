# Release Candidate and Rollback Runbook

This runbook covers reproducible analysis-only/paper-trading release
candidates. It does not enable live signing, swaps or live-money execution.

## Candidate checklist

From the exact candidate checkout:

```text
make verify
make migration-check
make security-review
make sbom
make release-identity RELEASE_IDENTITY_OUTPUT=artifacts/release-identity.json
git diff --check
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

The release identity records only safe metadata:

- full Git SHA;
- application and API versions;
- Alembic migration heads and metadata table count;
- deterministic runtime configuration hash;
- SBOM schema, component count and digest;
- the exact protected modes.

The GitHub workflow runs the backend, frontend, Compose and secret gates on
pull requests and `main` pushes. Its release-identity job runs only after
those jobs succeed, checks out full history for the history scan, and uploads
`release-candidate-${GITHUB_SHA}` containing `release-identity.json`. A hosted
workflow run must be observed for the exact candidate SHA before claiming
remote-CI acceptance; local `make verify` is not a substitute.

Provider doctors and real historical/live-shadow evidence remain separate
gates. Missing external access is recorded as `BLOCKED_EXTERNAL` or
`INSUFFICIENT_SAMPLES`, never converted into release or alpha success.

The Makefile keeps the existing `verify` target deterministic and exposes the
broader closure boundary separately:

```bash
make deterministic-release-gates
MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_DATABASE_URL" make prod-read-only-verify
```

`prod-read-only-verify` requires an explicit PostgreSQL test URL and runs the
existing integration and Playwright targets. Set
`MEMERADAR_E2E_BASE_URL` to the tested production build for browser acceptance;
without it, Playwright uses its existing local development-server harness.
Provider credentials, hosted CI and managed deployment acceptance remain
separate external gates.

## Rollback and forward fix

1. Keep the execution kill switch active and preserve all four protected modes.
2. Stop the affected API/worker rollout and record the deployed release
   identity without recording credentials or connection strings.
3. If the database head is unchanged, redeploy the previously accepted image
   identified by its full Git SHA and rerun liveness/readiness, migration,
   security and protected-mode checks.
4. If a migration has already been applied, do not downgrade a shared database
   as an incident shortcut. Restore an isolated backup when necessary and
   deploy a reviewed forward-fix migration compatible with the chosen image.
5. Reconcile stream cursor/gap state, outbox leases, paper ledger state and
   audit events before resuming analysis or paper collection.
6. Re-run the relevant provider doctors and bounded smoke/integration tests.
   Keep provider and alpha acceptance blocked until fresh evidence is
   available.

The rollback target, backup timestamp, migration head, release identity,
verification commands and residual blocker belong in the deployment record.
No step changes `MANUAL_EXECUTION` or `AUTO_EXECUTION` automatically.
