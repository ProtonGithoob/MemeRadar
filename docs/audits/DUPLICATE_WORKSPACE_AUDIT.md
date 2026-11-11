# Duplicate workspace audit and consolidation

Audited: 2026-10-24T07:37:26Z. Canonical working tree: `/home/ubra/codex/MemeRadar`.

## Result

The audit found **15 sibling MemeRadar directories** totaling **15,258,444 KiB (14.552 GiB)** by `du -sk`. The separate `MemeRadar-before-cleanup.bundle` is a file, not one of those directories. No directory was deleted and **0 bytes were reclaimed**. This is an incomplete cleanup because sibling paths are outside the writable sandbox, Docker bind-mount use could not be ruled out, and snapshots contain ignored runtime and research artifacts.

The canonical checkout remains on `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`. It was not reset, cleaned, replaced, or merged. The staged index is empty; pre-existing untracked prompt and scripts remain. No remote Git command was run. The canonical origin URL remained unchanged. `main` matches the locally cached `origin/main` reference, which is not a fresh remote synchronization check.

## Inventory

The inventory records canonicalized paths, Git root/common-dir, HEAD, branch, sanitized remotes, status counts, ignored-file counts, candidate commits absent from canonical objects, and cleanup decision. All listed entries are ordinary directories, not symlinks.

| Directory | HEAD | `du -sk` size | Worktree | Commit/file evidence | Decision |
| --- | --- | ---: | --- | --- | --- |
| `MemeRadar-12423c3-exact-20261024` | `12423c382182` | 392.8 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-22686de-exact-20261024` | `57b65b21b51f` | 1245.4 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-40a96c6-exact-20261024` | `b9002ae410cb` | 1194.2 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-44764fb-exact-20261023` | `d36d29160ebd` | 1059.5 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-57b65b2-exact-20261024` | `4402fc4ace97` | 1228.8 MiB | clean | 4402fc4ace97, 03e893f3388d, 5c8b66aa8eab | KEEP_TEMPORARILY_UNIQUE_COMMITS_AND_IGNORED_RUNTIME_EVIDENCE |
| `MemeRadar-6de1309-exact-20261024` | `22686dec59ea` | 990.3 MiB | clean | none found | BLOCKED_SANDBOX_AND_CONTAINER_USAGE_UNVERIFIED |
| `MemeRadar-71ecba4-exact-20261024` | `40a96c6f8a2c` | 1194.0 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-acbcd35-exact-20261023` | `—` | 0.0 MiB | non-Git / nested repo | none found | BLOCKED_INCOMPLETE_OR_NON_GIT_CONTENT_AND_SANDBOX |
| `MemeRadar-b9002ae-exact-20261024` | `6de1309a9917` | 1193.2 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-d36d291-exact-20261023` | `71ecba42d03e` | 1020.5 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-e252d45-exact-20261023` | `44764fbcd62b` | 928.4 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-e51cf4e-exact-20261024` | `e51cf4e3d0f0` | 1193.9 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-exact-ce1831a-20261023` | `e252d4573ab6` | 1020.5 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-final-verify-ca79ecf-20261021` | `ce1831abb659` | 1202.3 MiB | clean | none found | KEEP_TEMPORARILY_UNIQUE_OR_IGNORED_DATA |
| `MemeRadar-recovery-20261020T070001Z` | `nested: 0fe6a3816a7b` | 1791.3 MiB | non-Git / nested repo | 17 recovery commits bundled | BLOCKED_INCOMPLETE_OR_NON_GIT_CONTENT_AND_SANDBOX |

There are 13 independent Git snapshot repositories, one incomplete non-Git directory, and one recovery root containing a nested Git repository plus logs, safety material, virtual environments, and untracked recovery files. The snapshot clones contain large ignored dependency/cache trees and individually captured research or verification artifacts. Clean tracked status therefore does not establish that deleting a snapshot is safe.

## History and unique work

The latest snapshot directory, `MemeRadar-57b65b2-exact-20261024`, advanced during the audit to `4402fc4ace97ee34d09c7924ec65ce55eba1e827`. Its three-commit delta over canonical release base `12423c3821828613b8f5dea0ed7a6dace1e24c10` changes the order-claim ORM index contract and serializes concurrent first writes to runtime settings. These semantics and regression coverage have been integrated into the current canonical **working tree** in `packages/persistence/` and `tests/`. They have **not** been committed or imported as refs because canonical `.git` object/ref writes are denied by the host sandbox. The source snapshot’s history is retained in `artifacts/audit/MemeRadar-consolidation/candidate-4402fc4-preservation.bundle` (3,692 bytes; SHA-256 `812fabc717bce2537f16b5339bd2dfffdd4aae38a5c03b06c0c8e29ef79db397`); `git bundle verify` exited 0. Snapshot HEAD `4402fc4…` was identity-computed but its full verification was not run, so it is preserved, not accepted as a release.

The recovery repository has 17 commit objects absent from canonical Git. The retained `recovery-20261020-refs.bundle` was verified and contains its refs. The pre-cleanup bundle at `/home/ubra/codex/MemeRadar-before-cleanup.bundle` was verified (exit 0, 15 refs, complete history; SHA-256 `756c536f5083e0f851f225a72131fd7932bd45ccc0b02e1ae56d6d1790042cfe`). No bundle was removed.

The source integration regression suite passed provider-free checks. The real PostgreSQL first-write race test was skipped because `MEMERADAR_TEST_DATABASE_URL` is unset. The current `make verify` result is for the dirty canonical worktree, not a clean candidate.

## Why duplicates exist and prevention

The recovery script `memeradar_recover_once.sh` creates a timestamped recovery root; later recovery scripts reuse that root and create `verify-vN` clones. Checked-in scripts and docs did not identify a creator for the `MemeRadar-*-exact-*` snapshots. Their independent `.git` directories and chained local `origin` paths are consistent with repeated snapshot verification, but do not prove which process created them.

`AGENTS.md` now documents a bounded temporary-workspace lifecycle: create, validate, preserve evidence, and remove only task-owned inactive workspaces. This is a process instruction, not an enforced cleanup daemon. No unrelated global Codex configuration or operator-owned script was changed.

## Cleanup decision and constraints

All 15 home sibling directories are retained. The initial audit could not inspect Docker mounts; a later read-only host inventory found no source bind mounts, but active Compose config metadata still references snapshot paths and persistent PostgreSQL/Redis volumes remain in use. The recovery root and multiple clean snapshots contain unique ignored files or histories. The incomplete 44 KiB non-Git directory has not been proven disposable. Disk space is limited: 233 GiB total, 209 GiB used, 13 GiB available (95%). No deletion was used as an unverified way to reclaim space.

Durable project-local evidence is in `artifacts/audit/MemeRadar-consolidation/`, including inventory JSON, Git status snapshots, patches, verified bundles, checksums, and verification logs. The requested sibling path `/home/ubra/codex-audit/MemeRadar-consolidation/` is outside the writable sandbox, so no evidence was written there.

## Final state

- Canonical HEAD: `main` / `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; unchanged.
- Canonical worktree: intentionally dirty, index empty; task fixes are not committed.
- Snapshot history: latest 3-commit bundle verified; recovery bundle verified.
- Sibling directories removed: 0 of 15.
- Disk reclaimed: 0 bytes.
- Remote operations: none.
- Consolidation verdict: **PARTIAL — useful code is present in the canonical working tree, but durable canonical refs and safe cleanup require host-level write/mount access.**

## Host runtime and `/tmp` recheck — 2026-10-24 (historical)

This historical section supersedes only the earlier statement that Docker mount inspection
was unavailable. Direct read-only Docker inspection is now available. It found
five running Compose projects (21 containers), no source bind mounts, and
project-specific persistent PostgreSQL/Redis volumes. No project was stopped,
restarted, or modified; no volume or snapshot was removed.
The [2026-11-06 inventory](../repository-consolidation/01_INVENTORY.md) found
the projects exited and no `/tmp/MemeRadar-*` directories at that later scan.

### `/tmp` snapshot inventory

`find` and `du -sk` found nine ordinary directories totaling **6,314,644 KiB
(about 6.02 GiB)**. Each resolved to itself under `/tmp`; none was a symlink.
Tracked status and ignored-file counts were read from each Git repository.

| Directory | Size (KiB) | HEAD | Tracked state | Ignored files | Runtime/process evidence | Decision |
| --- | ---: | --- | --- | ---: | --- | --- |
| `/tmp/MemeRadar-03e893f-exact-20261024` | 889,232 | `03e893f3388d` | clean | 29,465 | No active Compose config path found. | KEEP_TEMPORARILY; ignored state not preserved. |
| `/tmp/MemeRadar-33c6748-exact-20261024` | 791,532 | `3ce35530c4a3` | clean | 27,221 | Operator reports a live recovery/verification process CWD here. Its latest commit is `3ce35530` at 2026-10-24 14:32:57 +0400. Sandbox `/proc` could not see the host process. | KEEP_ACTIVE. Do not inspect by killing/restarting it. |
| `/tmp/MemeRadar-4402fc4-exact-20261024` | 878,720 | `b62d97359be7` | clean | 29,292 | Config path is recorded by the active five-service `4402fc4-prod` project. | KEEP_ACTIVE. |
| `/tmp/MemeRadar-5c8b66a-exact-20261024` | 250,396 | `5c8b66aa8eab` | two modified tracked tests | 2,311 | No active Compose config path found. | KEEP_DIRTY; preserve both test changes. |
| `/tmp/MemeRadar-61685c6-exact-20261024` | 790,956 | `629736f4d1df` | clean | 27,220 | Contains the exact commit suggested by the `629736f` image tags; not the Compose config path. | KEEP_TEMPORARILY; image build source is not proven. |
| `/tmp/MemeRadar-629736f-exact-20261024` | 878,700 | `98f1f572cd3a` | clean | 29,293 | Config path is recorded by both active `629736f-prod` and `629736f-final` projects. | KEEP_ACTIVE. |
| `/tmp/MemeRadar-98f1f57-exact-20261024` | 791,320 | `33c6748d151f` | clean | 27,222 | No active Compose config path found. | KEEP_TEMPORARILY; ignored state not preserved. |
| `/tmp/MemeRadar-b62d973-exact-20261024` | 884,024 | `61685c6e2914` | clean | 29,382 | No active Compose config path found. | KEEP_TEMPORARILY; ignored state not preserved. |
| `/tmp/MemeRadar-3ce3553-fresh-20261024` | 159,764 | `3ce35530c4a3` | clean | 2,298 | Same HEAD as the operator-reported active `33c6748` process path; not a recorded Compose config path. | KEEP_TEMPORARILY; possible concurrent verification copy, ownership unresolved. |

The Compose metadata for `memeradar-576200e-shadow-20261023` refers to
`/tmp/MemeRadar-576200e-20261023` for PostgreSQL/Redis, but that directory is
absent. API/web metadata points to the home `MemeRadar-40a96c6` snapshot. This
mixed provenance blocks a reliable Compose dry-run and retirement plan for the
project.

None of the nine `/tmp` directories meets `SAFE_TO_DELETE`: one has modified
tests, one is host-reported active, two are referenced by active Compose
projects, the `629736f` candidate source is not image-bound, and every clean
snapshot still contains thousands of ignored files. All nine remain. Reclaimed
space is **0 bytes**. A lack of Docker source bind mounts does not prove ignored
files, histories, or active process use are recoverable elsewhere.

### Project retirement decisions and guarded commands

All project owners and operator/test purposes remain unknown. Therefore every
project is **KEEP / NOT AUTHORIZED TO STOP**:

- `memeradar-12423c3-prod`: PostgreSQL and Redis only, persistent named volumes;
  keep until the owner confirms the database is retired.
- `memeradar-4402fc4-prod`: active API/worker/web stack and its config snapshot;
  keep.
- `memeradar-576200e-shadow-20261023`: mixed config labels and missing recorded
  config path; keep until the exact compose files are recovered.
- `memeradar-629736f-prod` and `memeradar-629736f-final`: same API/worker/web
  image IDs but separate database/cache volumes; keep both until owners confirm
  their data is no longer needed.

Docker Compose `5.5.1` supports `--dry-run`. Dry-run attempts were made for the
four projects with extant config paths. They exited 1 before planning because
the current shell does not have required production environment variables; no
secret values were emitted. The `576200e` attempt exited 1 because its recorded
config file path is absent. Thus no successful dry-run plan was produced.

In a later operator shell that already has the approved Compose environment
loaded (do not enable shell tracing or print values), these are the exact
non-mutating commands to run first:

```sh
docker compose --dry-run -p memeradar-12423c3-prod -f /home/ubra/codex/MemeRadar-12423c3-exact-20261024/infra/compose/docker-compose.yml -f /home/ubra/codex/MemeRadar-12423c3-exact-20261024/infra/compose/docker-compose.prod.yml down
docker compose --dry-run -p memeradar-4402fc4-prod -f /tmp/MemeRadar-4402fc4-exact-20261024/infra/compose/docker-compose.yml -f /tmp/MemeRadar-4402fc4-exact-20261024/infra/compose/docker-compose.prod.yml down
docker compose --dry-run -p memeradar-629736f-prod -f /tmp/MemeRadar-629736f-exact-20261024/infra/compose/docker-compose.yml -f /tmp/MemeRadar-629736f-exact-20261024/infra/compose/docker-compose.prod.yml down
docker compose --dry-run -p memeradar-629736f-final -f /tmp/MemeRadar-629736f-exact-20261024/infra/compose/docker-compose.yml -f /tmp/MemeRadar-629736f-exact-20261024/infra/compose/docker-compose.prod.yml down
```

Compare each planned container set with the captured inventory. **Only after
per-project owner approval**, run the identical command without `--dry-run`.
Do not pass `-v`, `--rmi`, or `--remove-orphans`; named data volumes must remain.
Do not issue a `576200e` command until its exact missing Compose files are
recovered and their rendered services match the running project. These
commands have not been executed against the host.

### Snapshot creation and PostgreSQL test path

The checked-in `scripts/run_codex_validation.sh` uses the canonical repository
path and contains no clone/worktree/snapshot creation. The only matching
`mktemp -d` in the checked-in Makefile is the production dependency drill's
short-lived result directory with an exit trap; it does not create
`MemeRadar-*` repositories. `AGENTS.md` already describes a task-scoped bounded
workspace lifecycle. No responsible repository-owned snapshot creator was
found, so no speculative cleanup code or global Codex configuration was
changed. The host-reported active process and the new `3ce3553-fresh` directory
show that snapshot creation may continue outside those repository scripts.

`MEMERADAR_TEST_DATABASE_URL`, `psql`, `postgres`, and `pg_isready` are absent.
The existing named-volume databases are not verified disposable and must not be
used for tests. The local test option is an explicitly provisioned isolated
database; the repository CI option is its ephemeral PostgreSQL 16 service
followed by migration upgrade and integration tests. CI was not invoked. With
the root filesystem 95% full, no additional container/database was created.
