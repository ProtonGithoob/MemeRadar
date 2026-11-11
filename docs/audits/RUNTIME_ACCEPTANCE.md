# Runtime acceptance

## Host runtime inventory — 2026-10-24 (historical)

This is a historical read-only inventory, not current runtime or production
acceptance. The [2026-11-06 inventory](../repository-consolidation/01_INVENTORY.md)
found these projects exited. Direct `docker ps`,
`docker compose ls`, `docker inspect`, and `docker stats` worked. Container
exec and host-loopback access are denied in this sandbox. Docker Compose is
`5.5.1`; the host has 8 CPUs and 24.4 GiB RAM. Root disk is 95% full (13 GiB
available) and `/tmp` is 67% full (3.9 GiB available).

| Compose project | Services / count | Config provenance | Current observations | Retirement decision |
| --- | --- | --- | --- | --- |
| `memeradar-12423c3-prod` | PostgreSQL, Redis / 2 | `/home/ubra/codex/MemeRadar-12423c3-exact-20261024/infra/compose/` | Both healthy; project-specific named data volumes; no MemeRadar app image. | Owner and DB purpose unknown. Keep running. |
| `memeradar-4402fc4-prod` | API, worker, web, PostgreSQL, Redis / 5 | `/tmp/MemeRadar-4402fc4-exact-20261024/infra/compose/` | All up; API, PostgreSQL and Redis healthy. Worker has no healthcheck and restarted twice. | Active full stack and Compose references its snapshot. Keep running. |
| `memeradar-576200e-shadow-20261023` | API, web, PostgreSQL, Redis / 4 | API/web reference home `MemeRadar-40a96c6`; DB/Redis reference missing `/tmp/MemeRadar-576200e-20261023`. | All up; API, PostgreSQL and Redis healthy; no worker. API health history has 3-second liveness timeouts. | Mixed/missing config provenance. Keep running; do not reconstruct `down` from only the available half. |
| `memeradar-629736f-prod` | API, worker, web, PostgreSQL, Redis / 5 | `/tmp/MemeRadar-629736f-exact-20261024/infra/compose/` | All up; API, PostgreSQL and Redis healthy. Worker has no healthcheck and restarted twice. | Shares app image IDs with `final`, but has separate named DB/cache volumes. Owner unknown. Keep running. |
| `memeradar-629736f-final` | API, worker, web, PostgreSQL, Redis / 5 | Same config path as `prod`. | All up; API, PostgreSQL and Redis healthy. Worker has no healthcheck and restarted twice. | Separate project and volumes from `prod`. Keep running. |

All 21 containers were up at inspection. No application container has a source
bind mount; PostgreSQL and Redis use project-specific named volumes. This does
not make the source snapshots disposable: Compose retains config paths, active
operator ownership is unknown, and one host-reported process has its CWD in a
snapshot.

### Image/source/schema identity

Images have no `org.opencontainers.image.revision` label; the API Dockerfile
also does not set one. Image tags are clues, not proof of build source. The
checked source trees report migration head `0022_cross_chain_evidence` and 40
ORM tables; this is static source evidence, not the migration applied to a
running PostgreSQL volume. `docker exec` could not query `alembic_version`.

| Image group | Image IDs | Tag/source clue | Compose source tree | Identity conclusion |
| --- | --- | --- | --- | --- |
| `4402fc4` API / worker / web | `sha256:d13c467e907a11967b6a85704ec834e23c46ca23e47f9f2e54ac03b317481833` / `sha256:7556447d6c17ff4ded81539fcc471a8127a070fa50ddf19c4670192253980857` / `sha256:cc574473ed67b535c6f9e983bb0fa5d6053fed0837b8b25a9c548245ea60b66f` | Tags embed full commit `4402fc4ace97ee34d09c7924ec65ce55eba1e827`; that commit exists at home snapshot `MemeRadar-57b65b2`. | Running Compose files are from `/tmp/MemeRadar-4402fc4...`, whose HEAD is `b62d97359be7`. The candidate source and config-tree heads differ. | Candidate source checks are 0022 / 40 tables. Exact image build source is unbound. |
| `576200e` API / web | `sha256:7c4143cbe3e00c9b62df6cd3865b31bb442c9f350bad95bdc3b8f1b41193df96` / `sha256:112b11738e940c86e2d13fd6c4e957e3010f120a71aeb7830b22bba5a8ae64e4` | API/web project tags contain `576200e`; commit `576200e4c436788c2471158649720f5c708ae221` exists in local history. | API/web config source is home snapshot HEAD `b9002ae410cb`; DB/Redis config path is absent. | Available home source checks are 0022 / 40 tables. Exact image build source and applied DB head unknown. |
| `629736f` API / worker / web (`prod` and `final`) | `sha256:8c4df20a84e78c69796fe28ff756f2c1cd728fc969d332049fa2ba4d5ca6f6b5` / `sha256:5a643e7536560517e583b87fa85d13c343039aa41748e04bacfa2a14b57b0791` / `sha256:02c4011cdcd5c9676667a29e88b466b997e72802c214792012d2157eb065ad34` | Tags include `read-only-629736f4`; commit `629736f4d1df661463bed7bb0a635984a8fd2341` exists in `/tmp/MemeRadar-61685c6`. | Running Compose files are from `/tmp/MemeRadar-629736f...`, whose HEAD is `98f1f572cd3a`. | Both checked trees are 0022 / 40 tables. Same image IDs in two projects; exact image source and both DB heads unknown. |
| `12423c3` PostgreSQL / Redis | Upstream `postgres:16-alpine` / `redis:7-alpine` | No MemeRadar app image. | Compose source path is home snapshot HEAD `12423c382182`. | Source release identity reports `0022_cross_chain_evidence`, 40 metadata tables; applied DB migration is unknown. |

These are not images proven to come from canonical dirty `main` at
`c0fbd221…` (local source migration `0012_stream_gap_diagnostics`, 27 ORM
tables). Do not infer source identity from project names or tags.

### API health root cause

The prior report of three unhealthy APIs is not the current state: all four
APIs now report Docker health `healthy`. Recent health history still includes
`/health/live` failures exceeding the configured 3-second timeout on `576200e`,
`4402fc4`, and `629736f-final`; `629736f-prod` had no failure in the inspected
recent sample. A prior in-container readiness probe returned HTTP 200 for all
four APIs with PostgreSQL and Redis reachable at that time.

One `docker stats --no-stream` sample showed three workers at about 88–90% CPU,
`629736f-prod-api` at about 86%, and root disk at 95%. This makes transient
resource contention plausible, but does not prove causation; a timeout also
appeared on the healthy `4402fc4` API. The earlier unhealthy state was not
reproduced, so the root cause is **UNCONFIRMED**. Workers have no healthchecks;
API liveness/readiness does not establish discovery progress, stream recovery,
or paper lifecycle health.

The checked Compose files use the same API liveness probe: `urllib.request`
calls `/health/live` every 5 seconds, with a 3-second timeout, 10 retries and a
10-second start period. The current route returns a constant `alive` response;
it does not probe PostgreSQL, Redis, or external providers. Therefore a logged
timeout means the API process did not answer the liveness request inside 3
seconds; it does not identify why. The separate readiness route performs TCP
dependency probes. Raising the timeout or changing health semantics without a
reproducible cause was not justified by this inventory.

### PostgreSQL options and dry-run boundary

`MEMERADAR_TEST_DATABASE_URL`, `psql`, `postgres`, and `pg_isready` are absent
from this shell. The five running Compose projects use persistent
project-specific PostgreSQL volumes; none is known disposable. Do not use them
for integration tests. `.github/workflows/ci.yml` provides a PostgreSQL 16
service and orders migration upgrade before integration tests, but that hosted
job was not invoked. No new PostgreSQL container was created with the root
filesystem 95% full.

Compose `--dry-run` was attempted for `12423c3`, `4402fc4`, and both `629736f`
projects. Each exited 1 before planning because required production environment
variables were absent in this shell; no values were printed and no containers
changed. The `576200e` attempt exited 1 because its recorded `/tmp` Compose
files are missing. No actual `down`, restart, or volume action was run. A
future owner-approved dry-run must run in the same approved secret-bearing
shell, with the project `-p` name and exact config paths below; compare planned
container names to this inventory before separate explicit authorization for
the actual `down` command. Do not pass `-v`, `--rmi`, or `--remove-orphans`.
Compose preserves named volumes by default unless `-v` is specified ([official
`down` reference](https://docs.docker.com/reference/cli/docker/compose/down/)).

The nine `/tmp` snapshot entries, preservation decisions, and per-project
commands are recorded in the [duplicate-workspace audit](DUPLICATE_WORKSPACE_AUDIT.md).

| Gate | Result | Evidence / limit |
| --- | --- | --- |
| Python / frontend deterministic suite | PASS | Final `make verify` exit 0: 1,529 Python passed, 21 integration tests deselected, 83 Vitest passed / 24 files. |
| Lint and static checks | PASS | Ruff, mypy (182 source files), CSS contract, frontend lint/typecheck. |
| Compose configuration | PASS | Included in aggregate; configuration validation does not start a stack. |
| Migration graph / metadata | PASS | One head `0012_stream_gap_diagnostics`; 27 ORM tables. Static only. |
| Production build | BLOCKED_HOST | Next compiled, then failed parsing TypeScript `--showConfig`; direct TypeScript works, but child output capture is restricted by host. |
| Route budgets | NOT_CONFIGURED | No current package, Makefile or workflow target. |
| PostgreSQL | BLOCKED_ISOLATED_RUNTIME | No `MEMERADAR_TEST_DATABASE_URL` or local PostgreSQL binaries. Existing project volumes are persistent and not classified disposable; container exec is denied. The runtime-settings first-write concurrency test is skipped. CI defines an isolated PostgreSQL 16 service, but hosted CI was not invoked. |
| API / worker / web stack | NOT_ACCEPTED | Six MemeRadar Compose projects are exited as of 2026-11-06. The October inventory observed API readiness, but discovery, worker progress, paper lifecycle, and restart acceptance were not established. |
| Browser E2E | NOT_RUN | No final-source endpoint; Settings secret journey, axe, screenshots and timings were not measured. |
| Provider doctor | CONFIGURATION_ONLY | `.venv/bin/python -m scripts.free_provider_doctor --no-network` exit 0; network/auth/schema/latency `not_checked`. Endpoints are configured, not healthy. |
| Live providers | NOT_ACCEPTED | No bounded live Solana RPC, DexScreener or optional-provider acceptance. |
| Security | PARTIAL | Local secret scan/security review passed. npm audit found 1 critical and 2 high production advisories; external pip/npm/container scans were not run. |
| Release identity / SBOM | PARTIAL | Release identity tests passed; SBOM passed (582 components). No clean release binding or immutable images were produced. |

The aggregate deselected 21 PostgreSQL integration tests. No live chain event
was followed through persistence, risk, scoring, notification and paper position
in this environment. No new discovery counts, latency percentiles, gap recovery
rates, provider metrics, paper PnL or missed-winner performance were measured.

`ANALYSIS_ONLY=true` and `PAPER_TRADING=true` remain enforced; manual and
automatic execution remain false. No signer or transaction submission was
introduced.

The checked production Compose overlays for `12423c3`, `4402fc4`, and the
available `576200e`/`629736f` source trees explicitly set
`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
`AUTO_EXECUTION=false`, `CANARY=false`, and `LIVE=false` for API and worker.
The running container environment could not be queried through the sandbox's
safe-filter path, and image revisions are not bound to those source trees, so
this is configuration evidence, not a runtime flag acceptance result.

Related: [CI causes](CI_ROOT_CAUSE_ANALYSIS.md),
[provider matrix](PROVIDER_CAPABILITY_MATRIX.md), and
[remaining blockers](REMAINING_BLOCKERS.md).

## Dependency remediation — 2026-11-03

Updated Next.js and `eslint-config-next` to `16.4.4`, `sharp` to `0.35.5`,
`source-map-js` to `1.2.2`, and Vitest to `5.1.0`. The current production
dependency audit reports zero vulnerabilities. The full audit reports 16
moderate `minimatch` advisories in the ESLint development dependency tree; npm's
forced remediation would downgrade ESLint to `4.0.0` and was not applied.
Frontend tests, lint, typecheck, and production build passed with these updates.
