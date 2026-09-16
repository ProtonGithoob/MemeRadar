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
- immutable API, worker and web image IDs/digests when images have been built;
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

Build and bind the deployable artifacts before a production-like release:

```bash
make compose-prod-config
make production-images
make release-identity RELEASE_IDENTITY_OUTPUT=artifacts/release-identity.json
```

The image identity is `BOUND` only when all three API/worker/web image
identities are supplied or discovered from Docker; mutable tags alone are not
release identity. Hosted CI performs the same image-build and release-identity
handoff after deterministic backend, frontend, Compose and secret gates.

The Makefile keeps the existing `verify` target deterministic and exposes the
broader closure boundary separately:

```bash
make deterministic-release-gates
MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_DATABASE_URL" \
MEMERADAR_E2E_BASE_URL="https://the-tested-production-build.example" \
  make prod-read-only-verify
```

`make deterministic-release-gates` is keyless/deterministic. The stricter
`prod-read-only-verify` requires both an explicit PostgreSQL test URL and
`MEMERADAR_E2E_BASE_URL` for an already-running production build; it fails
closed instead of starting the development Playwright server. Keep ordinary
`make frontend-e2e` for developer-only browser checks.

## Reproducible local production-read-only acceptance

Run this sequence from the exact candidate checkout with disposable database,
Redis and browser targets. Do not put URLs, tokens or passwords in the
repository or release artifact.

```bash
make compose-prod-config
make production-images

# Start the production Compose contract with the operator's injected values.
docker compose -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.prod.yml up -d --wait

MEMERADAR_TEST_DATABASE_URL="$MEMERADAR_DATABASE_URL" \
MEMERADAR_E2E_BASE_URL="http://127.0.0.1:13000" \
  make prod-read-only-verify

MEMERADAR_STACK_VIEWER_API_TOKEN="$MEMERADAR_VIEWER_API_TOKEN" \
  make production-stack-acceptance \
    STACK_API_BASE_URL=http://127.0.0.1:18000 \
    STACK_CONTAINER_NAMES=compose-api-1,compose-worker-1,compose-postgres-1,compose-redis-1,compose-web-1

make production-dependency-drill
make backup-restore-drill
make release-identity RELEASE_IDENTITY_OUTPUT=artifacts/release-identity.json
```

`production-stack-acceptance` is strict: it requires measured container
liveness, restart counts, memory samples, worker liveness, database/Redis
readiness, exact protected modes and `execution_eligible=false`. Missing
optional-provider observations are reported as truthful unavailable evidence;
they are not converted into synthetic growth. The dependency drill stops and
recovers PostgreSQL and Redis independently and always uses the base plus
production Compose override. Hosted CI, managed deployment/rollback,
credentialed providers, managed backup scheduling and sustained managed soak
remain separate external gates.

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
