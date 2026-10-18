# Remaining dirty-path audit

Audit date: 2026-10-18. This report resolves the **518 historical UNKNOWN_RETAINED status paths** from the deep-refactor report into explicit file-purpose and retention decisions. It does not claim ownership of inherited edits. No source, test, runtime, credential, report or archive file was deleted, restored, staged or committed by this audit.

## Exact baseline and current delta

The primary baseline is the preserved NUL-delimited recursive porcelain snapshot [deep-refactor worktree](../../artifacts/verification/memeradar-deep-refactor-worktree-2026-10-18.status), not a fresh status count or collapsed directory listing. Its SHA-256 is `ad7fe7c787dac1caf8955cd4f5b74fef4e8630c6e0b434631d04491a7e7854a3`.

**582 = 48 task status paths + 16 retained archive originals + 518 remaining paths**. The 48 paths are listed below and reproduce the previous report's 39 Python/TS + five docs + ignore + two archive files + old API relocation. Their inherited hunks remain outside this audit's ownership.

The first current snapshot taken before this report was written had **587 paths** (SHA-256 `c9f786022a6900fecfaf90227ec318caf1cd12124f24b716375cfaad02b5b161`). All 582 baseline paths remain represented, with exactly these five additions:

- `.codex/logs/codex_validation_20261018_094230.jsonl` — LOCAL_RUNTIME / EXTERNAL_OWNED; metadata only.
- `.codex/logs/codex_validation_20261018_094352.jsonl` — LOCAL_RUNTIME / EXTERNAL_OWNED; metadata only.
- `.codex/runtime/prompt_20261018_094230.txt` — LOCAL_RUNTIME / EXTERNAL_OWNED; metadata only.
- `.codex/runtime/prompt_20261018_094352.txt` — LOCAL_RUNTIME / EXTERNAL_OWNED; metadata only.
- `scripts/MemeRadar.md` — DOC / EXTERNAL_OWNED; operator prompt, outside the historical 518.

The four new runtime paths and operator prompt are a separate current delta; they are not backdated into the 518. Further files written by concurrent work or this report will increase fresh status counts. A status count is not a source identity or a count of changes authored by this audit.

## Classification and disposition

Classes describe purpose, not Git ownership. SOURCE includes executable code and build/configuration inputs; TEST includes test modules, browser harness helpers and fixture/schema inputs; REPORT includes dated audit/acceptance evidence; DOC includes contracts, plans and prototypes. GENERATED lockfiles/type entries remain required build inputs. LOCAL_RUNTIME is host/operator state. UNKNOWN is deliberately content-unread or ownership-uncertain; it is not a deletion candidate.

| Class | Paths |
| --- | ---: |
| SOURCE | 164 |
| TEST | 148 |
| DOC | 29 |
| REPORT | 112 |
| GENERATED | 4 |
| CACHE | 0 |
| ARTIFACT | 2 |
| LOCAL_RUNTIME | 57 |
| UNKNOWN | 2 |
| **Total** | **518** |

| Action | Paths | Meaning |
| --- | ---: | --- |
| KEEP | 457 | Preserve repository code/contracts/evidence and required generated inputs. |
| EXTERNAL_OWNED | 61 | Preserve operator/host runtime, prompts, credential path and backup; no contents or cleanup authority inferred. |
| ARCHIVE | 0 | No additional archival move justified for this historical set. |
| DELETE | 0 | No file passed a complete unused/ownership proof. |
| GENERATED_IGNORE | 0 | No new ignore rule justified. Existing generated lockfiles and tracked Next type entry must remain visible. |

The 57 LOCAL_RUNTIME paths are the historical `.codex` logs/runtime files; only names/status were inspected. `.codex/telegram.env` remains UNKNOWN / EXTERNAL_OWNED, with **no content read, hash, value, credential validation or secret output**. `scripts/run_codex_validation.sh.bak` is the other UNKNOWN: an operator-owned backup whose absence of a runtime import does not authorize deleting it. Two operator prompt files account for the other DOC / EXTERNAL_OWNED entries. The new current operator prompt is separately listed above.

The two wallet seed CSV inputs are retained ARTIFACT, not cache. The three research schema/data fixtures are TEST. Four GENERATED paths are `apps/web/next-env.d.ts`, `apps/web/package-lock.json`, `requirements.lock`, and `uv.lock`; generated origin does not make dependency/type contracts disposable. The absent `provider-actions.tsx` is an inherited deletion, preserved as such; this audit does not recreate it or claim to have deleted it.

## Consumer proof boundary

All **164 SOURCE and 148 TEST** paths receive bounded per-path evidence below. The public corpus contained 1062 UTF-8 files, digest `d7e3e95c30df0a1397a8e00dbc1af9bede33bd4996bc30b26c5eca9e4849a6d1` (sorted path + content SHA-256 pairs). The graph parses Python imports/re-exports (including relative imports), resolves relative TypeScript/JavaScript imports/re-exports, scans exact file/module references in source, build/configuration, tests, migration, replay/serialization-named consumers and documentation, and records source export/definition counts. All Python inputs parsed successfully. `.codex`, actual environment/credential files, dependency/build trees, binary archives/images, and files over 2 MB are excluded from the content scan. The four generated inputs are classified independently of inbound import counts.

In each SOURCE/TEST row, **I** is the number of distinct runtime-source `(path,line)` reference witnesses, **T** tests/fixtures, **C** CLI/build/configuration, **D** documentation, **M** migrations; **R** overlaps references whose consumer path names replay/backfill/historical/forward, and **S** overlaps schema/serialization/models/read/persistence-named consumers. These are static/literal evidence counts, not dynamic call counts or proof that every semantic serialization/replay consumer was executed. Counts can overlap. Up to two concrete witnesses are shown per row. `imports/exports` is Python top-level import-statement count or JS/TS export-token count, not a promise that every import is public.

Registration checks prevent false orphan findings:

- FastAPI `main.py:155–183` includes the control/read/social/services and other routers; API `services.py` and `social.py` have direct main imports. Providers/application/persistence are composed through their existing ports and worker/API owners, not activated by filename alone.
- Worker `main.py:89–94` imports social and wallet-history orchestration; the existing `run_worker` registry schedules them with configuration checks. Existing CLI/script callsites and source/fixture imports remain represented in the graph.
- Pytest `pyproject.toml:31–34` discovers `tests`; test modules do not need production imports. Vitest config discovers `.test` modules while excluding `e2e`. Playwright uses `e2e` plus dedicated social/visual/performance configurations. Standalone root Node tests use `node:test`. Discovery is a KEEP reason even where no literal filename reference exists; it does not establish that an externally gated test ran.
- Next `page.tsx`/`route.ts` files are filesystem entries and deep links. A lack of a component import cannot establish an unused route.
- `source-identity.d.mts` is paired with the imported `.mjs` module through type resolution. `tsconfig.json` is selected by the package's default `tsc --noEmit` command (`package.json:11`). Neither needs an explicit import of its own filename.
- `playwright.visual-fixture.config.ts` has an explicit `testMatch` and fixture-server contract. No literal invocation was found in the bounded corpus, so it remains an optional CLI configuration with usage uncertainty, not proved dead.
- Alembic revisions load through the migration graph. In particular `0022_cross_chain_evidence.py:9` names `0021_operator_memory` as `down_revision`; migrations are retained even where normal Python import fan-in is zero.
- Public exports, JSON/schema contracts, replay/forward/persistence references and dated docs are consumer evidence. No claim of Python pickle compatibility or external-consumer exhaustiveness is made. No absence of a static edge was promoted into “unused”.

The scan is an ownership/retention audit, not a fresh full test execution or library/API usage change. Existing deep-refactor verification remains historical evidence. No dependency, route, serializer, migration, worker registration or scoring behavior changed here.

## Archive verification and duplicate-original review

Independently verified this turn, without extracting or deleting anything:

- Archive SHA-256 `b1591a7b1c77f4e7cb12ec611842e45857424cadb312854a0c7c12ea670dc02d`, **149,020,122 bytes**, matches the retention manifest.
- **1,508 / 1,508** regular-file members: unique names, exact manifest membership, safe relative paths with no traversal, byte size and SHA-256 all match. No symlink or directory entry was accepted as a file.
- Manifest uncompressed total **172,280,982 bytes**. The previous 1,492 archived-original / 16 retained-copy partition is exact.
- **16 / 16** retained originals independently match their manifest size and SHA-256, hence the corresponding archive bytes.
- The runs README and dead-code report both preserve the root restoration command. Historical attachments remain historical; archived screenshots do not establish acceptance of current source.

All 16 loose originals duplicate archive bytes, but they are intentionally retained **acceptance indexes**, not unnecessary copies under the current retention policy. They form eight machine-readable `acceptance.json` / human-readable `acceptance.md` pairs, totaling **338,478 bytes**, so an operator can inspect eight historical run outcomes without unpacking the 149 MB archive or losing the paired index context. The manifest explicitly records `KEEP_REFERENCED_COPY_AND_ARCHIVE`; the runs README and dead-code report document that policy. Two JSON paths also have exact current document references found by scanning full original path or its `runs/...` suffix outside the runs tree and manifest. The other 14 (**333,742 bytes**) need no direct literal document link to justify their index/audit purpose; two are human-readable partners of the directly linked JSON indexes, and twelve preserve six other run-index pairs. These 14 are optional only if the owner changes the documented index-retention policy. No copy is proved unnecessary for that policy, and no deletion is recommended. The two directly linked JSON files additionally require link migration before removal.

| Retained original | Direct current path reference | Recommendation |
| --- | --- | --- |
| `docs/ui-redesign-vnext/visual-evidence/runs/1383044956ca/2026-10-14T10-54-14-239Z-dcb6368b-346e-4a4f-97ca-c4ee526d4cfd/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/1383044956ca/2026-10-14T10-54-14-239Z-dcb6368b-346e-4a4f-97ca-c4ee526d4cfd/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/1a7e37305978/2026-10-14T09-57-04-848Z-8980c69b-16f8-461a-9223-8eb32e652c02/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/1a7e37305978/2026-10-14T09-57-04-848Z-8980c69b-16f8-461a-9223-8eb32e652c02/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/67dcfdc67cfc/2026-10-16T12-15-15-151Z-171dc4ff-53d4-4c00-a7b6-7afa0b10c211/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/67dcfdc67cfc/2026-10-16T12-15-15-151Z-171dc4ff-53d4-4c00-a7b6-7afa0b10c211/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/8db8a68e3157/2026-10-14T09-24-03-972Z-8146e2b8-d208-4bf4-8d43-e3616ddf9f61/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/8db8a68e3157/2026-10-14T09-24-03-972Z-8146e2b8-d208-4bf4-8d43-e3616ddf9f61/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/b772a9690bef/2026-10-14T10-57-29-418Z-715bb559-3362-4ec3-80b4-4d27ee6bcbb2/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/b772a9690bef/2026-10-14T10-57-29-418Z-715bb559-3362-4ec3-80b4-4d27ee6bcbb2/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/c1039dd7e109/2026-10-14T12-48-59-996Z-1af603da-cd74-4835-9a7b-31c814137e5e/host-acceptance/acceptance.json` | `docs/ui-redesign-vnext/PROGRESS.md`, `docs/ui-redesign-vnext/TEST_RESULTS.md` | KEEP: directly linked |
| `docs/ui-redesign-vnext/visual-evidence/runs/c1039dd7e109/2026-10-14T12-48-59-996Z-1af603da-cd74-4835-9a7b-31c814137e5e/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/dfec1845fcf9/2026-10-14T11-09-17-807Z-aa73858d-f0e0-432b-8a12-dbc311afeceb/host-acceptance/acceptance.json` | `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md`, `docs/ui-redesign-vnext/TEST_RESULTS.md` | KEEP: directly linked |
| `docs/ui-redesign-vnext/visual-evidence/runs/dfec1845fcf9/2026-10-14T11-09-17-807Z-aa73858d-f0e0-432b-8a12-dbc311afeceb/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/dfec1845fcf9/2026-10-14T11-21-35-023Z-c74c49e4-f45c-4569-a46f-e1f4276894f8/host-acceptance/acceptance.json` | None in bounded scan | KEEP: intentional paired historical acceptance index |
| `docs/ui-redesign-vnext/visual-evidence/runs/dfec1845fcf9/2026-10-14T11-21-35-023Z-c74c49e4-f45c-4569-a46f-e1f4276894f8/host-acceptance/acceptance.md` | None in bounded scan | KEEP: intentional paired historical acceptance index |

The archive restoration command, from repository root, is:

```bash
tar -xzf docs/history/visual-evidence-2026-10-18.tar.gz -C .
```

The archive contains only historical `docs/.../runs/...` members. For inspection, extracting into a disposable directory with `-C /tmp/<inspection-directory>` also preserves the repository's current layout; original relative attachment links need the complete nested run tree. Do not restore the tree merely to lower or reinterpret a Git status count.

## Archive commit-safety text scan

A separate operator-authorized commit-safety pass inspected the archive contents **in memory**, without extraction, external uploads or reading credential files. Archive SHA-256 remained `b1591a7b1c77f4e7cb12ec611842e45857424cadb312854a0c7c12ea670dc02d`.

| Scope / check | Result |
| --- | ---: |
| Top-level tar regular-file members inspected | 1,508 |
| Nested ZIP containers opened | 32 |
| Nested ZIP file entries inspected | 1,761 |
| Total entries, including containers | 3,269 |
| UTF-8 text entries scanned | 1,226 |
| Text bytes scanned | 250,142,317 |
| Structured JSON documents inspected | 676 |
| JSON-line / trace / network records inspected | 22,429 |
| Binary entries identified | 2,011 |
| High-confidence repository secret findings | 0 |
| Authorization/Bearer/cookie/structured credential findings | 0 |
| Additional project-token/JWT/literal credential findings | 0 |
| Public fixture allowlist matches | 0 |
| Decode/read/size/depth scan failures | 0 |

Every UTF-8 text member was passed to the existing `scripts.secret_scan.scan_text`. Nested ZIP members were read and scanned too, including `.trace`, `.network`, `.json`, `.jsonl`, `.html`, `.md`, `.css`, extensionless resources and other UTF-8 entries. JSON documents and line-delimited trace/network records were walked for nonempty Authorization/proxy-Authorization header pairs or fields, Cookie/Set-Cookie headers, cookie values and credential fields such as access/refresh/session tokens, API keys, passwords and private keys. Additional text patterns checked Bearer literals, cookie assignments, project-style tokens and JWTs. Header names and field names were normalized; no credential value was emitted. The exact known public fixture exception matched **zero** entries, so the result does not depend on a fixture exemption.

ZIP recursion was limited to three nested levels and a 100 MB member cap; no limit or expected-text decode failure was encountered. Independent ZIP metadata totals were **288,018,206 uncompressed bytes**, with largest entry **30,350,846 bytes**. Only safe path/rule/count metadata and aggregate metrics were written to `/tmp/memeradar-archive-secret-audit.json`; the audit did not modify archive bytes or report any credential contents.

**Commit-safety verdict: YES for this archive under the completed bounded text/structured scan.** This is separate from hash integrity and historical acceptance. Binary screenshots/media were not OCR-scanned; the result is not an absolute guarantee against every possible secret encoding or visual disclosure. It provides no live-provider, browser, production or trading acceptance.

## Excluded task-owned status paths (exact 48)

These exclusions are path membership only; they do not attribute every hunk in a path to the earlier task.

- `.gitignore`
- `apps/api/src/memeradar_api/read.py`
- `apps/api/src/memeradar_api/read/__init__.py`
- `apps/api/src/memeradar_api/read/callers.py`
- `apps/api/src/memeradar_api/read/candidates.py`
- `apps/api/src/memeradar_api/read/common.py`
- `apps/api/src/memeradar_api/read/operations.py`
- `apps/api/src/memeradar_api/read/outcomes.py`
- `apps/api/src/memeradar_api/read/research.py`
- `apps/api/src/memeradar_api/read/tokens.py`
- `apps/api/src/memeradar_api/read/wallets.py`
- `apps/web/src/app/components/outcomes.test.tsx`
- `apps/web/src/app/components/outcomes.tsx`
- `apps/web/src/app/components/shell-client.tsx`
- `apps/web/src/app/components/shell.test.tsx`
- `apps/web/src/app/lib/read-api.test.ts`
- `apps/web/src/app/lib/read-api.ts`
- `apps/worker/src/memeradar_worker/early_discovery.py`
- `apps/worker/src/memeradar_worker/forward_evidence.py`
- `apps/worker/src/memeradar_worker/intent_jobs.py`
- `apps/worker/src/memeradar_worker/main.py`
- `apps/worker/src/memeradar_worker/operations_jobs.py`
- `apps/worker/src/memeradar_worker/wallet_jobs.py`
- `docs/ARCHITECTURE.md`
- `docs/STATUS.md`
- `docs/history/visual-evidence-2026-10-18-manifest.json`
- `docs/history/visual-evidence-2026-10-18.tar.gz`
- `docs/reports/memeradar-dead-code-and-archive-report.md`
- `docs/reports/memeradar-deep-refactor.md`
- `docs/ui-redesign-vnext/visual-evidence/runs/README.md`
- `packages/application/src/memeradar_application/pumpfun_forward.py`
- `packages/application/src/memeradar_application/read_api.py`
- `packages/application/src/memeradar_application/read_callers.py`
- `packages/application/src/memeradar_application/read_candidates.py`
- `packages/application/src/memeradar_application/read_common.py`
- `packages/application/src/memeradar_application/read_operations.py`
- `packages/application/src/memeradar_application/read_outcomes.py`
- `packages/application/src/memeradar_application/read_positions.py`
- `packages/application/src/memeradar_application/read_research.py`
- `packages/application/src/memeradar_application/read_tokens.py`
- `packages/application/src/memeradar_application/read_wallets.py`
- `tests/integration/test_madeonsol_runtime_postgres.py`
- `tests/smoke/test_compose_contract.py`
- `tests/unit/test_pumpfun_forward_evidence.py`
- `tests/unit/test_read_api.py`
- `tests/unit/test_read_api_routes.py`
- `tests/unit/test_wallet_history_worker.py`
- `tests/unit/test_worker_entrypoint.py`

## Historical 518-path ledger

Status values are from the preserved baseline: ` M` modified, ` D` absent/deleted, `??` untracked. An action is the audit recommendation, not a mutation performed. Every row is one distinct baseline path; no collapsed directories or current-delta paths are included.

| # | Baseline status | Path | Class | Action | Bounded evidence / retention reason |
| ---: | --- | --- | --- | --- | --- |
| 1 | `??` | `.codex/logs/codex_validation_20260928_154828.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 2 | `??` | `.codex/logs/codex_validation_20260929_151423.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 3 | `??` | `.codex/logs/codex_validation_20260929_190420.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 4 | `??` | `.codex/logs/codex_validation_20260929_212144.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 5 | `??` | `.codex/logs/codex_validation_20261003_132157.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 6 | `??` | `.codex/logs/codex_validation_20261003_211608.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 7 | `??` | `.codex/logs/codex_validation_20261004_182623.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 8 | `??` | `.codex/logs/codex_validation_20261005_153519.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 9 | `??` | `.codex/logs/codex_validation_20261006_104036.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 10 | `??` | `.codex/logs/codex_validation_20261006_112242.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 11 | `??` | `.codex/logs/codex_validation_20261006_224735.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 12 | `??` | `.codex/logs/codex_validation_20261007_013629.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 13 | `??` | `.codex/logs/codex_validation_20261007_081342.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 14 | `??` | `.codex/logs/codex_validation_20261007_174821.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 15 | `??` | `.codex/logs/codex_validation_20261007_224524.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 16 | `??` | `.codex/logs/codex_validation_20261007_232129.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 17 | `??` | `.codex/logs/codex_validation_20261008_072903.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 18 | `??` | `.codex/logs/codex_validation_20261008_101604.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 19 | `??` | `.codex/logs/codex_validation_20261009_005006.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 20 | `??` | `.codex/logs/codex_validation_20261009_155215.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 21 | `??` | `.codex/logs/codex_validation_20261010_215958.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 22 | `??` | `.codex/logs/codex_validation_20261010_220204.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 23 | `??` | `.codex/logs/codex_validation_20261011_130239.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 24 | `??` | `.codex/logs/codex_validation_20261012_012600.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 25 | `??` | `.codex/logs/codex_validation_20261012_160417.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 26 | `??` | `.codex/logs/codex_validation_20261013_222232.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 27 | `??` | `.codex/logs/codex_validation_20261013_234929.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 28 | `??` | `.codex/logs/codex_validation_20261014_004854.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 29 | `??` | `.codex/logs/codex_validation_20261014_110226.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 30 | `??` | `.codex/logs/codex_validation_20261014_122400.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 31 | `??` | `.codex/logs/codex_validation_20261014_130059.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 32 | `??` | `.codex/logs/codex_validation_20261014_144450.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 33 | `??` | `.codex/logs/codex_validation_20261014_154125.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 34 | `??` | `.codex/logs/codex_validation_20261014_172844.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 35 | `??` | `.codex/logs/codex_validation_20261014_201111.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 36 | `??` | `.codex/logs/codex_validation_20261014_213626.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 37 | `??` | `.codex/logs/codex_validation_20261016_153343.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 38 | `??` | `.codex/logs/codex_validation_20261016_211106.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 39 | `??` | `.codex/logs/codex_validation_20261016_223350.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 40 | `??` | `.codex/logs/codex_validation_20261016_231031.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 41 | `??` | `.codex/logs/codex_validation_20261018_000225.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 42 | `??` | `.codex/logs/codex_validation_20261018_003519.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 43 | `??` | `.codex/logs/codex_validation_20261018_004609.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 44 | `??` | `.codex/logs/codex_validation_20261018_012004.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 45 | `??` | `.codex/runtime/latest.jsonl` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 46 | `??` | `.codex/runtime/prompt_20260928_154828.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 47 | `??` | `.codex/runtime/prompt_20260929_190420.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 48 | `??` | `.codex/runtime/prompt_20261006_112242.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 49 | `??` | `.codex/runtime/prompt_20261007_081342.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 50 | `??` | `.codex/runtime/prompt_20261008_072903.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 51 | `??` | `.codex/runtime/prompt_20261008_101604.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 52 | `??` | `.codex/runtime/prompt_20261009_005006.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 53 | `??` | `.codex/runtime/prompt_20261010_215958.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 54 | `??` | `.codex/runtime/prompt_20261016_231031.txt` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 55 | `??` | `.codex/runtime/runner.lock` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 56 | `??` | `.codex/runtime/runner.state` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 57 | `??` | `.codex/runtime/session_id` | LOCAL_RUNTIME | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 58 | `??` | `.codex/telegram.env` | UNKNOWN | EXTERNAL_OWNED | Host/operator runtime metadata; content deliberately unopened |
| 59 | ` M` | `.dockerignore` | SOURCE | KEEP | I1 T0 C0 D4 M0 R0 S0; witness `apps/web/e2e/helpers/source-identity.mjs:20`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:242` |
| 60 | ` M` | `.env.example` | SOURCE | KEEP | I0 T1 C2 D72 M0 R0 S0; witness `.gitignore:3`, `scripts/release_identity.py:67` |
| 61 | ` M` | `.github/workflows/ci.yml` | SOURCE | KEEP | I0 T0 C0 D3 M0 R0 S0; witness `docs/PROD_READ_ONLY_CLOSURE_GAP_MATRIX_2026-09-15.md:86`, `docs/reports/INTERRUPTED_RESUME.md:20` |
| 62 | ` M` | `FRONTEND_EXECUTION_PROMPT.md` | DOC | KEEP | witness `README.md:499`, `docs/DOCS_CLEANUP_REPORT.md:47` |
| 63 | ` M` | `README.md` | DOC | KEEP | witness `packages/providers/src/memeradar_providers/protocol_registry.py:764`, `fixtures/providers/README.md:14` |
| 64 | ` M` | `apps/api/src/memeradar_api/control.py` | SOURCE | KEEP | I1 T3 C1 D3 M0 R0 S0; defs=20, imports/exports=15; witness `apps/api/src/memeradar_api/main.py:45`, `scripts/security_review.py:150` |
| 65 | ` M` | `apps/api/src/memeradar_api/main.py` | SOURCE | KEEP | I0 T21 C1 D4 M0 R0 S3; defs=1, imports/exports=26; witness `scripts/security_review.py:389`, `tests/contract/test_alpha_caller_read_api.py:9` |
| 66 | `??` | `apps/api/src/memeradar_api/services.py` | SOURCE | KEEP | I1 T2 C0 D3 M0 R0 S0; defs=18, imports/exports=27; witness `apps/api/src/memeradar_api/main.py:50`, `tests/contract/test_services_api.py:12` |
| 67 | `??` | `apps/api/src/memeradar_api/social.py` | SOURCE | KEEP | I1 T1 C1 D4 M0 R0 S0; defs=10, imports/exports=17; witness `apps/api/src/memeradar_api/main.py:51`, `scripts/security_review.py:159` |
| 68 | `??` | `apps/web/e2e/accessibility.spec.ts` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=1, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/reports/FRONTEND_VNEXT_RECOVERY.md:40`, `docs/reports/INTERRUPTED_RESUME.md:159` |
| 69 | `??` | `apps/web/e2e/helpers/source-identity.d.mts` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=2; no literal/static inbound hit; not proof of unused; paired .mjs type declaration; consumed through typed import resolution in visual harness, not a textual .d.mts import |
| 70 | `??` | `apps/web/e2e/helpers/source-identity.mjs` | TEST | KEEP | I1 T5 C0 D1 M0 R0 S0; defs=4, imports/exports=1; witness `apps/web/scripts/host-acceptance.mjs:9`, `apps/web/e2e/ui-redesign-vnext.spec.ts:4` |
| 71 | `??` | `apps/web/e2e/helpers/visual-evidence.d.mts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=2; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:461` |
| 72 | `??` | `apps/web/e2e/helpers/visual-evidence.mjs` | TEST | KEEP | I0 T10 C0 D1 M0 R0 S0; defs=3, imports/exports=1; witness `apps/web/e2e/ui-redesign-vnext.spec.ts:5`, `apps/web/e2e/visual-fixtures.spec.ts:4` |
| 73 | ` M` | `apps/web/e2e/operator-dashboard.spec.ts` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=2, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/reports/FRONTEND_VNEXT_RECOVERY.md:40`, `docs/reports/INTERRUPTED_RESUME.md:23` |
| 74 | `??` | `apps/web/e2e/radar-fixture-api.mjs` | TEST | KEEP | I0 T1 C0 D0 M0 R0 S0; defs=3, imports/exports=1; witness `scripts/radar-fixture-api.test.mjs:3` |
| 75 | `??` | `apps/web/e2e/services.spec.ts` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/reports/INTERRUPTED_RESUME.md:160`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:136` |
| 76 | `??` | `apps/web/e2e/social-alpha-api.mjs` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=0; witness `docs/reports/INTERRUPTED_RESUME.md:161`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:137` |
| 77 | `??` | `apps/web/e2e/social-alpha.spec.ts` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=1, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2082`, `docs/reports/FRONTEND_VNEXT_RECOVERY.md:40` |
| 78 | `??` | `apps/web/e2e/ui-redesign-vnext.spec.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:459` |
| 79 | `??` | `apps/web/e2e/visual-fixtures.spec.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:325` |
| 80 | ` M` | `apps/web/e2e/visual-matrix.spec.ts` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=0, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; witness `docs/reports/INTERRUPTED_RESUME.md:24`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:277` |
| 81 | ` M` | `apps/web/e2e/wallet-graph.spec.ts` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=1, imports/exports=0; Playwright testDir=e2e; dedicated config exclusions apply; no literal/static inbound hit; not proof of unused |
| 82 | ` M` | `apps/web/next-env.d.ts` | GENERATED | KEEP | witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:8` |
| 83 | ` M` | `apps/web/next.config.ts` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=1; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:302` |
| 84 | ` M` | `apps/web/package-lock.json` | GENERATED | KEEP | witness `.github/workflows/ci.yml:79`, `scripts/sbom.py:86` |
| 85 | ` M` | `apps/web/package.json` | SOURCE | KEEP | I0 T1 C1 D4 M0 R0 S0; witness `scripts/security_review.py:278`, `tests/unit/test_security_review.py:52` |
| 86 | `??` | `apps/web/perf/runtime.perf.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=0; witness `docs/reports/INTERRUPTED_RESUME.md:163` |
| 87 | ` M` | `apps/web/playwright.config.ts` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=1; witness `docs/reports/INTERRUPTED_RESUME.md:27`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:11` |
| 88 | `??` | `apps/web/playwright.perf.config.ts` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=1; witness `docs/reports/INTERRUPTED_RESUME.md:164`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:140` |
| 89 | `??` | `apps/web/playwright.social-alpha.config.ts` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=1; witness `docs/reports/INTERRUPTED_RESUME.md:165`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:141` |
| 90 | `??` | `apps/web/playwright.visual-fixture.config.ts` | SOURCE | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=0, imports/exports=1; no literal/static inbound hit; not proof of unused; explicit optional CLI config for visual-fixtures.spec.ts; testMatch and fixture servers verified; no literal invocation found in bounded corpus |
| 91 | `??` | `apps/web/scripts/host-acceptance.mjs` | SOURCE | KEEP | I0 T1 C0 D5 M0 R0 S0; defs=18, imports/exports=10; witness `scripts/host-acceptance.test.mjs:3`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:44` |
| 92 | `??` | `apps/web/scripts/route-bundle-report.mjs` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=0; witness `docs/reports/INTERRUPTED_RESUME.md:166` |
| 93 | ` M` | `apps/web/src/app/api/control/runtime-settings/route.test.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:87` |
| 94 | ` M` | `apps/web/src/app/api/control/runtime-settings/route.ts` | SOURCE | KEEP | I0 T1 C0 D2 M0 R0 S0; defs=5, imports/exports=3; Next filesystem entry/deep link; witness `apps/web/src/app/api/control/runtime-settings/route.test.ts:4`, `docs/PROD_READ_ONLY_CLOSURE_GAP_MATRIX_2026-09-15.md:82` |
| 95 | `??` | `apps/web/src/app/api/services/[serviceId]/doctor/route.test.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:167` |
| 96 | `??` | `apps/web/src/app/api/services/[serviceId]/doctor/route.ts` | SOURCE | KEEP | I0 T1 C0 D1 M0 R0 S0; defs=4, imports/exports=2; Next filesystem entry/deep link; witness `apps/web/src/app/api/services/[serviceId]/doctor/route.test.ts:8`, `docs/reports/INTERRUPTED_RESUME.md:168` |
| 97 | `??` | `apps/web/src/app/api/wallet-graph/route.test.ts` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; no literal/static inbound hit; not proof of unused |
| 98 | `??` | `apps/web/src/app/api/wallet-graph/route.ts` | SOURCE | KEEP | I0 T1 C0 D0 M0 R0 S0; defs=8, imports/exports=2; Next filesystem entry/deep link; witness `apps/web/src/app/api/wallet-graph/route.test.ts:3` |
| 99 | `??` | `apps/web/src/app/callers/[sourceId]/page.tsx` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:169`, `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:27` |
| 100 | `??` | `apps/web/src/app/compare/page.tsx` | SOURCE | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=1; Next filesystem entry/deep link; no literal/static inbound hit; not proof of unused |
| 101 | ` M` | `apps/web/src/app/components/audit.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:28`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:12` |
| 102 | ` M` | `apps/web/src/app/components/audit.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=7, imports/exports=1; witness `apps/web/src/app/audit/page.tsx:1`, `apps/web/src/app/components/audit.test.tsx:4` |
| 103 | ` M` | `apps/web/src/app/components/callers.test.tsx` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2056`, `docs/reports/INTERRUPTED_RESUME.md:30` |
| 104 | ` M` | `apps/web/src/app/components/callers.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=14, imports/exports=1; witness `apps/web/src/app/callers/page.tsx:1`, `apps/web/src/app/components/callers.test.tsx:4` |
| 105 | ` M` | `apps/web/src/app/components/chain-opportunities.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:32`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:16` |
| 106 | ` M` | `apps/web/src/app/components/chain-opportunities.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=8, imports/exports=1; witness `apps/web/src/app/opportunities/page.tsx:1`, `apps/web/src/app/components/chain-opportunities.test.tsx:4` |
| 107 | ` M` | `apps/web/src/app/components/command-center.tsx` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S0; defs=13, imports/exports=1; witness `apps/web/src/app/page.tsx:1`, `apps/web/src/app/page.test.tsx:4` |
| 108 | `??` | `apps/web/src/app/components/compare.test.tsx` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=0; Vitest default discovery; e2e excluded; no literal/static inbound hit; not proof of unused |
| 109 | `??` | `apps/web/src/app/components/compare.tsx` | SOURCE | KEEP | I1 T1 C0 D1 M0 R0 S0; defs=5, imports/exports=2; witness `apps/web/src/app/compare/page.tsx:1`, `apps/web/src/app/components/compare.test.tsx:4` |
| 110 | `??` | `apps/web/src/app/components/copy-address-button.tsx` | SOURCE | KEEP | I2 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=1; witness `apps/web/src/app/components/token-detail.tsx:19`, `apps/web/src/app/components/wallet-detail.tsx:4` |
| 111 | `??` | `apps/web/src/app/components/missed-winners.test.tsx` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; no literal/static inbound hit; not proof of unused |
| 112 | `??` | `apps/web/src/app/components/missed-winners.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=1, imports/exports=1; witness `apps/web/src/app/missed-winners/page.tsx:1`, `apps/web/src/app/components/missed-winners.test.tsx:4` |
| 113 | ` M` | `apps/web/src/app/components/operations.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:35`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:19` |
| 114 | ` M` | `apps/web/src/app/components/operations.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=17, imports/exports=1; witness `apps/web/src/app/operations/page.tsx:1`, `apps/web/src/app/components/operations.test.tsx:4` |
| 115 | `??` | `apps/web/src/app/components/pipeline.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:247`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:229` |
| 116 | `??` | `apps/web/src/app/components/pipeline.tsx` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S0; defs=5, imports/exports=1; witness `apps/web/src/app/pipeline/page.tsx:1`, `apps/web/src/app/components/pipeline.test.tsx:4` |
| 117 | ` M` | `apps/web/src/app/components/positions.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:37`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:21` |
| 118 | ` M` | `apps/web/src/app/components/positions.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=13, imports/exports=1; witness `apps/web/src/app/positions/page.tsx:1`, `apps/web/src/app/components/positions.test.tsx:4` |
| 119 | ` D` | `apps/web/src/app/components/provider-actions.tsx` | SOURCE | KEEP | I0 T0 C0 D4 M0 R0 S0; already absent in prior snapshot; preserve inherited deletion; witness `docs/reports/INTERRUPTED_RESUME.md:39`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:23` |
| 120 | ` M` | `apps/web/src/app/components/providers.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:40`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:24` |
| 121 | ` M` | `apps/web/src/app/components/providers.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=7, imports/exports=1; witness `apps/web/src/app/providers/page.tsx:1`, `apps/web/src/app/components/providers.test.tsx:4` |
| 122 | ` M` | `apps/web/src/app/components/radar-table.tsx` | SOURCE | KEEP | I2 T0 C0 D3 M0 R0 S0; defs=9, imports/exports=2; witness `apps/web/src/app/components/radar-workspace.tsx:8`, `apps/web/src/app/components/radar.tsx:12` |
| 123 | `??` | `apps/web/src/app/components/radar-workspace.tsx` | SOURCE | KEEP | I2 T0 C0 D2 M0 R0 S0; defs=13, imports/exports=1; witness `apps/web/src/app/components/command-center.tsx:14`, `apps/web/src/app/components/radar.tsx:11` |
| 124 | ` M` | `apps/web/src/app/components/radar.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:43`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:27` |
| 125 | ` M` | `apps/web/src/app/components/radar.tsx` | SOURCE | KEEP | I2 T1 C0 D2 M0 R0 S0; defs=5, imports/exports=4; witness `apps/web/src/app/components/command-center.tsx:13`, `apps/web/src/app/radar/page.tsx:1` |
| 126 | ` M` | `apps/web/src/app/components/readiness.test.tsx` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:45`, `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:65` |
| 127 | ` M` | `apps/web/src/app/components/readiness.tsx` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=15, imports/exports=1; witness `apps/web/src/app/readiness/page.tsx:1`, `apps/web/src/app/components/readiness.test.tsx:4` |
| 128 | `??` | `apps/web/src/app/components/service-conflicts.test.tsx` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:146` |
| 129 | `??` | `apps/web/src/app/components/service-conflicts.tsx` | SOURCE | KEEP | I3 T1 C0 D1 M0 R0 S0; defs=1, imports/exports=1; witness `apps/web/src/app/components/operations.tsx:12`, `apps/web/src/app/components/services.tsx:13` |
| 130 | `??` | `apps/web/src/app/components/services.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:171`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:148` |
| 131 | `??` | `apps/web/src/app/components/services.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=7, imports/exports=1; witness `apps/web/src/app/services/page.tsx:1`, `apps/web/src/app/components/services.test.tsx:4` |
| 132 | ` M` | `apps/web/src/app/components/settings.test.tsx` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/archive/conflicted/2026-09-07-frontend-backend-parity.conflicted.md:218`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:89` |
| 133 | ` M` | `apps/web/src/app/components/settings.tsx` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S0; defs=18, imports/exports=3; witness `apps/web/src/app/settings/page.tsx:1`, `apps/web/src/app/components/settings.test.tsx:4` |
| 134 | ` M` | `apps/web/src/app/components/shell.tsx` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=10, imports/exports=1; witness `apps/web/src/app/layout.tsx:3`, `apps/web/src/app/components/shell.test.tsx:4` |
| 135 | `??` | `apps/web/src/app/components/social-alpha.test.tsx` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:173`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:150` |
| 136 | `??` | `apps/web/src/app/components/social-alpha.tsx` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=15, imports/exports=1; witness `apps/web/src/app/social-alpha/page.tsx:1`, `apps/web/src/app/components/social-alpha.test.tsx:10` |
| 137 | `??` | `apps/web/src/app/components/subscription-health.tsx` | SOURCE | KEEP | I2 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=1; witness `apps/web/src/app/components/operations.tsx:14`, `apps/web/src/app/components/readiness.tsx:13` |
| 138 | ` M` | `apps/web/src/app/components/token-detail.test.tsx` | TEST | KEEP | I0 T0 C0 D12 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:52`, `docs/reports/agentic-loop/2026-10-07-liquidity-valuation-quality.md:34` |
| 139 | ` M` | `apps/web/src/app/components/token-detail.tsx` | SOURCE | KEEP | I1 T1 C0 D18 M0 R0 S0; defs=60, imports/exports=2; witness `apps/web/src/app/tokens/[tokenId]/page.tsx:3`, `apps/web/src/app/components/token-detail.test.tsx:4` |
| 140 | ` M` | `apps/web/src/app/components/ui.tsx` | SOURCE | KEEP | I19 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=1; witness `apps/web/src/app/components/audit.tsx:7`, `apps/web/src/app/components/callers.tsx:13` |
| 141 | ` M` | `apps/web/src/app/components/ultra-early.test.tsx` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:55`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:39` |
| 142 | ` M` | `apps/web/src/app/components/ultra-early.tsx` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=13, imports/exports=2; witness `apps/web/src/app/ultra-early/page.tsx:1`, `apps/web/src/app/components/ultra-early.test.tsx:4` |
| 143 | ` M` | `apps/web/src/app/components/wallet-detail.test.tsx` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:57`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:58` |
| 144 | ` M` | `apps/web/src/app/components/wallet-detail.tsx` | SOURCE | KEEP | I1 T1 C0 D5 M0 R0 S0; defs=9, imports/exports=1; witness `apps/web/src/app/wallets/[address]/page.tsx:3`, `apps/web/src/app/components/wallet-detail.test.tsx:4` |
| 145 | ` M` | `apps/web/src/app/components/wallet-graph.test.tsx` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=6, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:312`, `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md:27` |
| 146 | ` M` | `apps/web/src/app/components/wallet-graph.tsx` | SOURCE | KEEP | I1 T2 C0 D8 M0 R0 S0; defs=16, imports/exports=1; witness `apps/web/src/app/wallet-graph/page.tsx:2`, `apps/web/src/app/components/wallet-graph.test.tsx:3` |
| 147 | ` M` | `apps/web/src/app/components/wallets.test.tsx` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=2, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:59`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:68` |
| 148 | ` M` | `apps/web/src/app/components/wallets.tsx` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S0; defs=9, imports/exports=1; witness `apps/web/src/app/wallets/page.tsx:1`, `apps/web/src/app/components/wallets.test.tsx:4` |
| 149 | ` M` | `apps/web/src/app/globals.css` | SOURCE | KEEP | I1 T0 C1 D12 M0 R0 S0; witness `apps/web/src/app/layout.tsx:6`, `scripts/check_frontend_css.py:10` |
| 150 | ` M` | `apps/web/src/app/lib/parity-manifest.test.ts` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:62`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:116` |
| 151 | ` M` | `apps/web/src/app/lib/parity-manifest.ts` | SOURCE | KEEP | I0 T2 C0 D6 M0 R0 S0; defs=3, imports/exports=3; witness `apps/web/src/app/lib/parity-manifest.test.ts:3`, `apps/web/src/app/lib/parity-manifest.test.ts:4` |
| 152 | `??` | `apps/web/src/app/lib/read-api-helpers.test.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:22` |
| 153 | `??` | `apps/web/src/app/lib/read-api-helpers.ts` | SOURCE | KEEP | I11 T1 C0 D1 M0 R0 S0; defs=3, imports/exports=4; witness `apps/web/src/app/callers/[sourceId]/page.tsx:10`, `apps/web/src/app/components/pipeline.tsx:6` |
| 154 | `??` | `apps/web/src/app/missed-winners/page.tsx` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=5, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/FRONTEND_VNEXT_RECOVERY.md:38` |
| 155 | ` M` | `apps/web/src/app/operations/page.tsx` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:66`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:50` |
| 156 | `??` | `apps/web/src/app/outcomes/page.tsx` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=5, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/FRONTEND_VNEXT_RECOVERY.md:38` |
| 157 | ` M` | `apps/web/src/app/page.test.tsx` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/INTERRUPTED_RESUME.md:67`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:51` |
| 158 | ` M` | `apps/web/src/app/page.tsx` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=1, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:68`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:52` |
| 159 | `??` | `apps/web/src/app/pipeline/page.tsx` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:247`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:228` |
| 160 | ` M` | `apps/web/src/app/radar/page.tsx` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:69`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:53` |
| 161 | ` M` | `apps/web/src/app/readiness/page.tsx` | SOURCE | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=4, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:70`, `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:65` |
| 162 | `??` | `apps/web/src/app/services/page.tsx` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=2; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:176` |
| 163 | `??` | `apps/web/src/app/social-alpha/actions.test.ts` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:26` |
| 164 | `??` | `apps/web/src/app/social-alpha/actions.ts` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=6, imports/exports=2; witness `apps/web/src/app/components/social-alpha.tsx:17`, `apps/web/src/app/social-alpha/actions.test.ts:8` |
| 165 | `??` | `apps/web/src/app/social-alpha/page.tsx` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=3, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:178` |
| 166 | ` M` | `apps/web/src/app/tokens/[tokenId]/page.tsx` | SOURCE | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=1, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/INTERRUPTED_RESUME.md:72`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:343` |
| 167 | `??` | `apps/web/src/app/wallet-graph/page.test.tsx` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=3, imports/exports=0; Vitest default discovery; e2e excluded; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:281` |
| 168 | ` M` | `apps/web/src/app/wallet-graph/page.tsx` | SOURCE | KEEP | I0 T1 C0 D2 M0 R0 S0; defs=1, imports/exports=2; Next filesystem entry/deep link; witness `apps/web/src/app/wallet-graph/page.test.tsx:4`, `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md:32` |
| 169 | ` M` | `apps/web/src/app/wallets/page.tsx` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=1; Next filesystem entry/deep link; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:57` |
| 170 | ` M` | `apps/web/tsconfig.json` | SOURCE | KEEP | I0 T0 C0 D0 M0 R0 S0; no literal/static inbound hit; not proof of unused; default compiler config for package.json:11 next typegen + tsc --noEmit; include globs cover src and generated Next types |
| 171 | ` M` | `apps/web/vitest.config.ts` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=0, imports/exports=1; witness `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:463` |
| 172 | `??` | `apps/worker/src/memeradar_worker/social_sources.py` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=8, imports/exports=14; witness `apps/worker/src/memeradar_worker/main.py:89`, `tests/unit/test_social_source_worker.py:8` |
| 173 | `??` | `apps/worker/src/memeradar_worker/wallet_history.py` | SOURCE | KEEP | I5 T16 C0 D5 M0 R0 S0; defs=26, imports/exports=22; witness `apps/worker/src/memeradar_worker/main.py:90`, `apps/worker/src/memeradar_worker/main.py:91` |
| 174 | `??` | `data/seeds/solana_wallet_seeds_raw.csv` | ARTIFACT | KEEP | witness `docs/audits/MEMERADAR_V8_MASTER_GAP_MATRIX.md:10`, `docs/audits/WALLET_DATA_MODEL_AUDIT.md:8` |
| 175 | `??` | `data/seeds/solana_wallets.csv` | ARTIFACT | KEEP | witness `docs/reports/MEMERADAR_V8_WALLET_INTELLIGENCE_FINAL.md:36`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:23` |
| 176 | ` M` | `docs/CODEX_FRONTEND_BACKEND_PARITY.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:49`, `docs/archive/frontend/CODEX_FRONTEND_BACKEND_PARITY_2026-09-07_SUPERSEDED.md:9` |
| 177 | ` M` | `docs/DATA_MODEL.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:31`, `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md:20` |
| 178 | `??` | `docs/DOCS_CLEANUP_REPORT.md` | REPORT | KEEP | witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6456`, `docs/ui-redesign/PROGRESS.md:22` |
| 179 | ` M` | `docs/FRONTEND_BACKEND_PARITY.md` | DOC | KEEP | witness `README.md:281`, `docs/DOCS_CLEANUP_REPORT.md:33` |
| 180 | ` M` | `docs/FRONTEND_UI_UX_MODERNIZATION.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:46`, `docs/archive/frontend/FRONTEND_EXECUTION_PROMPT_2026-09-04_REVERTED.md:29` |
| 181 | ` M` | `docs/PRODUCTION_READINESS.md` | DOC | KEEP | witness `tests/contract/test_production_acceptance.py:9`, `docs/CODEX_REAL_ALPHA_PRODUCTION_EXECUTION.md:9` |
| 182 | ` M` | `docs/PROVIDERS.md` | DOC | KEEP | witness `README.md:55`, `docs/CODEX_MULTICHAIN_EXTREME_WINNER_EXECUTION.md:16` |
| 183 | `??` | `docs/README.md` | DOC | KEEP | witness `README.md:489`, `docs/DOCS_CLEANUP_REPORT.md:29` |
| 184 | ` M` | `docs/ROADMAP_RESEARCH_EXTENSIONS.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:30`, `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md:18` |
| 185 | ` M` | `docs/SCORING_AND_RISK.md` | DOC | KEEP | witness `docs/CODEX_MULTICHAIN_EXTREME_WINNER_EXECUTION.md:15`, `docs/DOCS_CLEANUP_REPORT.md:31` |
| 186 | ` M` | `docs/SECURITY.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:129`, `docs/archive/conflicted/2026-09-07-frontend-backend-parity.conflicted.md:187` |
| 187 | ` M` | `docs/STREAM_RELIABILITY_PROTOCOL_VERIFICATION.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:30`, `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md:19` |
| 188 | ` M` | `docs/UPSTREAM_REPOSITORY_INFLUENCES.md` | DOC | KEEP | witness `prompts/MemeRadar.md.new:1520`, `docs/DOCS_CLEANUP_REPORT.md:32` |
| 189 | `??` | `docs/archive/conflicted/2026-09-07-frontend-backend-parity.conflicted.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:48` |
| 190 | `??` | `docs/archive/frontend/2026-09-07-frontend-backend-parity-design_SUPERSEDED.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:50`, `docs/superpowers/specs/2026-09-07-frontend-backend-parity-design.md:4` |
| 191 | `??` | `docs/archive/frontend/CODEX_FRONTEND_BACKEND_PARITY_2026-09-07_SUPERSEDED.md` | DOC | KEEP | witness `docs/CODEX_FRONTEND_BACKEND_PARITY.md:4`, `docs/DOCS_CLEANUP_REPORT.md:49` |
| 192 | `??` | `docs/archive/frontend/FRONTEND_EXECUTION_PROMPT_2026-09-04_REVERTED.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:47` |
| 193 | `??` | `docs/archive/frontend/FRONTEND_UI_UX_MODERNIZATION_2026-09-04_REVERTED.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:46`, `docs/UPSTREAM_REPOSITORY_INFLUENCES.md:436` |
| 194 | `??` | `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:147`, `docs/reports/agentic-loop/2026-10-07-bundle-and-lifecycle-provenance.md:20` |
| 195 | `??` | `docs/audits/EARLY_GEM_V2_BASELINE.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:148`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2626` |
| 196 | `??` | `docs/audits/EXTERNAL_INTELLIGENCE_CAPABILITY_MATRIX.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:149`, `docs/reports/MEMERADAR_V8_1_EVIDENCE_CLOSURE_FINAL.md:47` |
| 197 | `??` | `docs/audits/FRONTEND_BACKEND_PARITY.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:150`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4544` |
| 198 | `??` | `docs/audits/MEMERADAR_V8_MASTER_GAP_MATRIX.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:151`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:5297` |
| 199 | `??` | `docs/audits/PULSE_ARCHITECTURE_COMPARISON.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:152`, `docs/reports/MEMERADAR_V8_1_EVIDENCE_CLOSURE_FINAL.md:49` |
| 200 | `??` | `docs/audits/V8_2_9PLUS_SCORECARD.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:153`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:12` |
| 201 | `??` | `docs/audits/V8_3_9PLUS_SCORECARD.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:154`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6428` |
| 202 | `??` | `docs/audits/WALLET_DATA_MODEL_AUDIT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:155`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:5169` |
| 203 | `??` | `docs/audits/WALLET_SIGNAL_DEPENDENCY_MATRIX.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:156`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:61` |
| 204 | `??` | `docs/case_studies/MUNK_EARLY_DISCOVERY.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:157`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2625` |
| 205 | `??` | `docs/history/PRODUCTION_READINESS-2026-10-18-before-purpose-refactor.md` | REPORT | KEEP | Preserved prior contract/status evidence |
| 206 | `??` | `docs/history/STATUS-2026-10-18-before-purpose-refactor.md` | REPORT | KEEP | Preserved prior contract/status evidence |
| 207 | `??` | `docs/providers/dexscreener-contract.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:158`, `docs/reports/EARLY_ALPHA_V4_FINAL.md:70` |
| 208 | `??` | `docs/providers/pump-fun-contract.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:159`, `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:347` |
| 209 | `??` | `docs/providers/solana-rpc-token-balance-contract.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:160`, `docs/reports/agentic-loop/2026-10-07-canonical-pump-trade-fields.md:27` |
| 210 | `??` | `docs/reports/EARLY_ALPHA_V4_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:161`, `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:66` |
| 211 | `??` | `docs/reports/EARLY_ALPHA_V5_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:162`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:18` |
| 212 | `??` | `docs/reports/EARLY_ALPHA_V6_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:163`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:86` |
| 213 | `??` | `docs/reports/FRONTEND_VNEXT_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:164`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4544` |
| 214 | `??` | `docs/reports/FRONTEND_VNEXT_RECOVERY.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:165`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4544` |
| 215 | `??` | `docs/reports/INTERRUPTED_RESUME.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:166`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:158` |
| 216 | `??` | `docs/reports/MEMERADAR_V8_1_EVIDENCE_CLOSURE_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:167`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:5298` |
| 217 | `??` | `docs/reports/MEMERADAR_V8_2_9PLUS_CLOSURE_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:168`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:309` |
| 218 | `??` | `docs/reports/MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md` | REPORT | KEEP | witness `README.md:492`, `docs/DOCS_CLEANUP_REPORT.md:169` |
| 219 | `??` | `docs/reports/MEMERADAR_V8_WALLET_INTELLIGENCE_FINAL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:170`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:67` |
| 220 | `??` | `docs/reports/agentic-loop/2026-10-07-bundle-and-lifecycle-provenance.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:171`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3320` |
| 221 | `??` | `docs/reports/agentic-loop/2026-10-07-canonical-pump-trade-fields.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:172` |
| 222 | `??` | `docs/reports/agentic-loop/2026-10-07-canonical-token-observation-matching.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:173` |
| 223 | `??` | `docs/reports/agentic-loop/2026-10-07-dexscreener-cohort-coverage.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:174` |
| 224 | `??` | `docs/reports/agentic-loop/2026-10-07-early-feature-event-semantics.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:175`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2595` |
| 225 | `??` | `docs/reports/agentic-loop/2026-10-07-event-time-quality.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:176` |
| 226 | `??` | `docs/reports/agentic-loop/2026-10-07-graduation-trajectory.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:177` |
| 227 | `??` | `docs/reports/agentic-loop/2026-10-07-known-wallet-balance-refresh.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:178` |
| 228 | `??` | `docs/reports/agentic-loop/2026-10-07-liquidity-valuation-quality.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:179`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3147` |
| 229 | `??` | `docs/reports/agentic-loop/2026-10-07-market-behavior-archetypes.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:180`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3130` |
| 230 | `??` | `docs/reports/agentic-loop/2026-10-07-participant-expansion-parity.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:181`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3397` |
| 231 | `??` | `docs/reports/agentic-loop/2026-10-07-participant-price-response.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:182`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3137` |
| 232 | `??` | `docs/reports/agentic-loop/2026-10-07-same-age-failure-controls.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:183` |
| 233 | `??` | `docs/reports/agentic-loop/2026-10-07-sell-response.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:184` |
| 234 | `??` | `docs/reports/agentic-loop/2026-10-07-shutdown-recovery.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:185` |
| 235 | `??` | `docs/reports/agentic-loop/2026-10-07-social-exact-mint-evidence.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:186`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3177` |
| 236 | `??` | `docs/reports/agentic-loop/2026-10-07-verified-pump-trades-early-features.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:187` |
| 237 | `??` | `docs/reports/agentic-loop/2026-10-07-wallet-cluster-evidence-coverage.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:188`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2594` |
| 238 | `??` | `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:189`, `docs/reports/EARLY_ALPHA_V6_FINAL.md:28` |
| 239 | `??` | `docs/reports/agentic-loop/DOCS_CLEANUP_BASELINE.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:190` |
| 240 | `??` | `docs/reports/agentic-loop/DOCS_CLEANUP_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:191`, `docs/ui-redesign/BLOCKERS.md:5` |
| 241 | `??` | `docs/reports/agentic-loop/FRONTEND_VNEXT_SHUTDOWN_RECOVERY.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:192`, `docs/reports/FRONTEND_VNEXT_FINAL.md:101` |
| 242 | `??` | `docs/reports/agentic-loop/FRONTEND_VNEXT_V7_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:193`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:217` |
| 243 | `??` | `docs/reports/agentic-loop/V6_BLOCKER_REGISTRY.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:194`, `docs/reports/agentic-loop/V6_CHECKSUMS.txt:22` |
| 244 | `??` | `docs/reports/agentic-loop/V6_CHECKSUMS.txt` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:195`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:86` |
| 245 | `??` | `docs/reports/agentic-loop/V6_ENV_CONTRACT_AUDIT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:196`, `docs/reports/agentic-loop/V6_CHECKSUMS.txt:23` |
| 246 | `??` | `docs/reports/agentic-loop/V6_REAL_DATA_FUNNEL.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:197`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:86` |
| 247 | `??` | `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:198`, `docs/audits/MEMERADAR_V8_MASTER_GAP_MATRIX.md:31` |
| 248 | `??` | `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:199`, `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:72` |
| 249 | `??` | `docs/reports/agentic-loop/V8_1_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:200`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:5296` |
| 250 | `??` | `docs/reports/agentic-loop/V8_2_BASELINE_MANIFEST.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:201`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:9` |
| 251 | `??` | `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:202` |
| 252 | `??` | `docs/reports/agentic-loop/V8_2_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:203`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:10` |
| 253 | `??` | `docs/reports/agentic-loop/V8_3_BASELINE_MANIFEST.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:204`, `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:31` |
| 254 | `??` | `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:205` |
| 255 | `??` | `docs/reports/agentic-loop/V8_3_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:206`, `docs/reports/MEMERADAR_V8_3_CAUSAL_9PLUS_CLOSURE_FINAL.md:45` |
| 256 | `??` | `docs/reports/agentic-loop/V8_3_VERIFICATION.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:207`, `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:20` |
| 257 | `??` | `docs/reports/agentic-loop/V8_BASELINE_MANIFEST.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:208`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:8` |
| 258 | `??` | `docs/reports/agentic-loop/V8_BLOCKER_REGISTRY.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:209`, `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:21` |
| 259 | `??` | `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:210`, `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:20` |
| 260 | `??` | `docs/reports/agentic-loop/V8_CURRENT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:211`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:5145` |
| 261 | `??` | `docs/reports/agentic-loop/baseline-status-2026-10-07.txt` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:212`, `docs/reports/agentic-loop/2026-10-07-dexscreener-cohort-coverage.md:31` |
| 262 | `??` | `docs/reports/agentic-loop/frontend-vnext-recovery-checkpoint.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:213`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4359` |
| 263 | `??` | `docs/reports/dexscreener-early-market-intelligence-2026-10-07.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:215`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2624` |
| 264 | `??` | `docs/reports/frontend-before-after.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:224`, `docs/reports/INTERRUPTED_RESUME.md:180` |
| 265 | `??` | `docs/reports/frontend-keep-replace-matrix.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:225`, `docs/reports/INTERRUPTED_RESUME.md:181` |
| 266 | `??` | `docs/reports/frontend-live-closure-final.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:226`, `docs/reports/INTERRUPTED_RESUME.md:182` |
| 267 | `??` | `docs/reports/frontend-modernization-audit.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:227`, `docs/reports/INTERRUPTED_RESUME.md:183` |
| 268 | `??` | `docs/reports/frontend-modernization-final.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:228`, `docs/reports/INTERRUPTED_RESUME.md:184` |
| 269 | `??` | `docs/reports/frontend-modernization-progress.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:229`, `docs/reports/INTERRUPTED_RESUME.md:185` |
| 270 | `??` | `docs/reports/frontend-visual-maturity-matrix.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:230`, `docs/reports/INTERRUPTED_RESUME.md:186` |
| 271 | `??` | `docs/reports/fullstack-root-cause-closure-2026-09-30.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:231`, `docs/reports/INTERRUPTED_RESUME.md:187` |
| 272 | `??` | `docs/reports/fullstack-root-cause-gap-matrix.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:232`, `docs/reports/INTERRUPTED_RESUME.md:188` |
| 273 | `??` | `docs/reports/live-readiness-parameter-matrix.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:233`, `docs/reports/INTERRUPTED_RESUME.md:189` |
| 274 | `??` | `docs/reports/memeradar-agentic-root-cause-closure-2026-10-06.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:234`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:170` |
| 275 | `??` | `docs/reports/memeradar-current-authoritative-state-2026-10-06.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:235`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:171` |
| 276 | `??` | `docs/reports/memeradar-purpose-refactor.md` | REPORT | KEEP | witness `README.md:18` |
| 277 | `??` | `docs/reports/memeradar-upstream-intelligence-closure-2026-10-14.md` | REPORT | KEEP | witness `prompts/MemeRadar.md.new:1716`, `docs/UPSTREAM_REPOSITORY_INFLUENCES.md:447` |
| 278 | `??` | `docs/reports/performance-report.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:237`, `docs/reports/INTERRUPTED_RESUME.md:190` |
| 279 | `??` | `docs/reports/services-control-plane-final.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:239`, `docs/reports/INTERRUPTED_RESUME.md:191` |
| 280 | `??` | `docs/reports/social-alpha-caller-intelligence-final.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:240`, `docs/reports/INTERRUPTED_RESUME.md:192` |
| 281 | `??` | `docs/reports/social-alpha-gap-audit.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:241`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2039` |
| 282 | `??` | `docs/reports/upstream-intelligence-integration-matrix-2026-10-14.md` | REPORT | KEEP | witness `prompts/MemeRadar.md.new:367`, `docs/UPSTREAM_REPOSITORY_INFLUENCES.md:445` |
| 283 | `??` | `docs/reports/visual-regression-report.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:243`, `docs/reports/INTERRUPTED_RESUME.md:194` |
| 284 | `??` | `docs/reports/wallet-seed-validation.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:244`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:24` |
| 285 | ` M` | `docs/superpowers/plans/2026-09-07-frontend-backend-parity.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:48`, `docs/archive/frontend/CODEX_FRONTEND_BACKEND_PARITY_2026-09-07_SUPERSEDED.md:11` |
| 286 | `??` | `docs/superpowers/plans/2026-10-14-upstream-intelligence-integration.md` | DOC | KEEP | Documentation/prototype contract; no unused proof |
| 287 | ` M` | `docs/superpowers/specs/2026-09-07-frontend-backend-parity-design.md` | DOC | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:50`, `docs/archive/conflicted/2026-09-07-frontend-backend-parity.conflicted.md:12` |
| 288 | `??` | `docs/ui-redesign-vnext/BASELINE.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 289 | `??` | `docs/ui-redesign-vnext/BEFORE_AFTER.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 290 | `??` | `docs/ui-redesign-vnext/BLOCKERS.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 291 | `??` | `docs/ui-redesign-vnext/CLOSURE_REGISTER.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 292 | `??` | `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md` | REPORT | KEEP | witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6499` |
| 293 | `??` | `docs/ui-redesign-vnext/FINAL_REPORT.md` | REPORT | KEEP | witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6474` |
| 294 | `??` | `docs/ui-redesign-vnext/IMPLEMENTATION_PLAN.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 295 | `??` | `docs/ui-redesign-vnext/INTERACTION_MATRIX.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 296 | `??` | `docs/ui-redesign-vnext/OBSIDIANUI_PROTOTYPES.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 297 | `??` | `docs/ui-redesign-vnext/PAGE_ACCEPTANCE.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 298 | `??` | `docs/ui-redesign-vnext/PROGRESS.md` | REPORT | KEEP | witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6526` |
| 299 | `??` | `docs/ui-redesign-vnext/TEST_RESULTS.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 300 | `??` | `docs/ui-redesign-vnext/VISUAL_BEFORE_AFTER.md` | REPORT | KEEP | Dated audit/evidence; retained, not current acceptance |
| 301 | `??` | `docs/ui-redesign-vnext/obsidianui-prototypes.html` | DOC | KEEP | witness `apps/web/e2e/ui-redesign-vnext.spec.ts:112` |
| 302 | `??` | `docs/ui-redesign/00-repository-inventory.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:264`, `docs/ui-redesign-vnext/BASELINE.md:24` |
| 303 | `??` | `docs/ui-redesign/01-obsidianui-compatibility.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:265` |
| 304 | `??` | `docs/ui-redesign/02-design-system.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:266` |
| 305 | `??` | `docs/ui-redesign/ACCEPTANCE.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:267` |
| 306 | `??` | `docs/ui-redesign/API_MAPPING.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:33` |
| 307 | `??` | `docs/ui-redesign/BEFORE_AFTER.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:269` |
| 308 | `??` | `docs/ui-redesign/BLOCKERS.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:270` |
| 309 | `??` | `docs/ui-redesign/COMPONENT_MAPPING.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:271` |
| 310 | `??` | `docs/ui-redesign/FINAL_REPORT.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:272`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:6456` |
| 311 | `??` | `docs/ui-redesign/PROGRESS.md` | REPORT | KEEP | witness `docs/DOCS_CLEANUP_REPORT.md:273` |
| 312 | `??` | `docs/ui-redesign/README.md` | REPORT | KEEP | witness `README.md:282`, `docs/DOCS_CLEANUP_REPORT.md:54` |
| 313 | ` M` | `fixtures/research/historical_real_dataset.schema.json` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; fixture/schema input; not a discovered test module; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:17` |
| 314 | ` M` | `fixtures/research/historical_real_dataset_validation.json` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; fixture/schema input; not a discovered test module; witness `docs/history/PRODUCTION_READINESS-2026-10-18-before-purpose-refactor.md:314`, `docs/reports/agentic-loop/2026-10-07-same-age-failure-controls.md:34` |
| 315 | ` M` | `fixtures/research/opportunity_research_report.json` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; fixture/schema input; not a discovered test module; witness `docs/API.md:51`, `docs/RESEARCH_GATE_REPORT.md:19` |
| 316 | `??` | `infra/alembic/versions/0013_social_sources.py` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/INTERRUPTED_RESUME.md:195`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:177` |
| 317 | `??` | `infra/alembic/versions/0014_social_call_claims_and_revisions.py` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/INTERRUPTED_RESUME.md:196`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:178` |
| 318 | `??` | `infra/alembic/versions/0015_named_stream_runtime_state.py` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/INTERRUPTED_RESUME.md:197`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:179` |
| 319 | `??` | `infra/alembic/versions/0016_service_conflict_evidence.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:180` |
| 320 | `??` | `infra/alembic/versions/0017_smart_wallet_candidates.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:181` |
| 321 | `??` | `infra/alembic/versions/0018_stream_gap_provider_id.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:182` |
| 322 | `??` | `infra/alembic/versions/0019_wallet_seed_identities.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:38` |
| 323 | `??` | `infra/alembic/versions/0020_wallet_activity_addr_idx.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:159` |
| 324 | `??` | `infra/alembic/versions/0021_operator_memory.py` | SOURCE | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; no literal/static inbound hit; not proof of unused; revision 0021_operator_memory referenced by 0022_cross_chain_evidence.py:9 down_revision; Alembic loader is consumer |
| 325 | `??` | `infra/alembic/versions/0022_cross_chain_evidence.py` | SOURCE | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=2, imports/exports=3; Alembic revision/down_revision graph, not normal import discovery; witness `docs/reports/memeradar-upstream-intelligence-closure-2026-10-14.md:52` |
| 326 | ` M` | `infra/docker/web.Dockerfile` | SOURCE | KEEP | I0 T0 C4 D2 M0 R0 S0; witness `.github/workflows/ci.yml:148`, `Makefile:222` |
| 327 | ` M` | `packages/application/src/memeradar_application/alert_pipeline.py` | SOURCE | KEEP | I3 T10 C0 D5 M0 R0 S1; defs=46, imports/exports=15; witness `apps/worker/src/memeradar_worker/operations_jobs.py:13`, `packages/application/src/memeradar_application/early_alpha_alert.py:14` |
| 328 | ` M` | `packages/application/src/memeradar_application/caller_outcomes.py` | SOURCE | KEEP | I6 T3 C0 D3 M0 R0 S2; defs=51, imports/exports=15; witness `packages/application/src/memeradar_application/opportunity_research.py:26`, `packages/application/src/memeradar_application/read_api.py:33` |
| 329 | ` M` | `packages/application/src/memeradar_application/config.py` | SOURCE | KEEP | I17 T32 C23 D11 M0 R0 S3; defs=25, imports/exports=8; witness `apps/api/src/memeradar_api/auth.py:10`, `apps/api/src/memeradar_api/control.py:16` |
| 330 | ` M` | `packages/application/src/memeradar_application/control.py` | SOURCE | KEEP | I12 T9 C1 D4 M0 R0 S3; defs=30, imports/exports=13; witness `apps/api/src/memeradar_api/auth.py:11`, `apps/api/src/memeradar_api/control.py:26` |
| 331 | ` M` | `packages/application/src/memeradar_application/correlation.py` | SOURCE | KEEP | I4 T9 C0 D4 M0 R1 S0; defs=21, imports/exports=21; witness `packages/application/src/memeradar_application/early_features.py:38`, `packages/application/src/memeradar_application/feature_windows.py:40` |
| 332 | ` M` | `packages/application/src/memeradar_application/creator_graph.py` | SOURCE | KEEP | I6 T6 C0 D3 M0 R1 S4; defs=11, imports/exports=9; witness `apps/worker/src/memeradar_worker/forward_evidence.py:22`, `packages/application/src/memeradar_application/operator_memory.py:20` |
| 333 | ` M` | `packages/application/src/memeradar_application/decision_engine.py` | SOURCE | KEEP | I0 T6 C0 D2 M0 R0 S1; defs=11, imports/exports=13; witness `tests/contract/test_phase6_sprint6_3.py:9`, `tests/integration/test_persistence_postgres.py:18` |
| 334 | ` M` | `packages/application/src/memeradar_application/discovery_collection.py` | SOURCE | KEEP | I1 T3 C0 D3 M0 R0 S0; defs=8, imports/exports=10; witness `apps/worker/src/memeradar_worker/early_discovery.py:19`, `tests/unit/test_discovery_collection.py:7` |
| 335 | ` M` | `packages/application/src/memeradar_application/early_detection.py` | SOURCE | KEEP | I2 T1 C0 D5 M0 R0 S0; defs=12, imports/exports=10; witness `apps/worker/src/memeradar_worker/early_discovery.py:23`, `packages/application/src/memeradar_application/early_runtime.py:45` |
| 336 | ` M` | `packages/application/src/memeradar_application/early_failure_analysis.py` | SOURCE | KEEP | I1 T1 C0 D4 M0 R1 S0; defs=16, imports/exports=8; witness `apps/worker/src/memeradar_worker/forward_evidence.py:30`, `tests/unit/test_early_failure_analysis.py:5` |
| 337 | ` M` | `packages/application/src/memeradar_application/early_features.py` | SOURCE | KEEP | I2 T7 C0 D15 M0 R1 S0; defs=38, imports/exports=19; witness `apps/worker/src/memeradar_worker/early_discovery.py:24`, `packages/application/src/memeradar_application/early_runtime.py:46` |
| 338 | ` M` | `packages/application/src/memeradar_application/early_replay.py` | SOURCE | KEEP | I5 T3 C1 D3 M0 R5 S0; defs=19, imports/exports=15; witness `apps/worker/src/memeradar_worker/forward_evidence.py:34`, `packages/application/src/memeradar_application/calibration.py:39` |
| 339 | ` M` | `packages/application/src/memeradar_application/early_runtime.py` | SOURCE | KEEP | I3 T3 C1 D21 M0 R0 S3; defs=24, imports/exports=21; witness `apps/worker/src/memeradar_worker/early_discovery.py:25`, `packages/application/src/memeradar_application/early_worker.py:12` |
| 340 | ` M` | `packages/application/src/memeradar_application/early_scoring.py` | SOURCE | KEEP | I4 T5 C0 D6 M0 R1 S0; defs=13, imports/exports=13; witness `apps/api/src/memeradar_api/read/__init__.py:40`, `apps/api/src/memeradar_api/read/candidates.py:13` |
| 341 | ` M` | `packages/application/src/memeradar_application/event_time.py` | SOURCE | KEEP | I22 T4 C0 D2 M0 R1 S1; defs=6, imports/exports=5; witness `apps/api/src/memeradar_api/read/__init__.py:43`, `apps/api/src/memeradar_api/read/outcomes.py:12` |
| 342 | ` M` | `packages/application/src/memeradar_application/evidence_helpers.py` | SOURCE | KEEP | I38 T3 C0 D1 M0 R0 S0; defs=4, imports/exports=5; witness `packages/application/src/memeradar_application/alpha_strategy.py:36`, `packages/application/src/memeradar_application/alpha_strategy.py:39` |
| 343 | `??` | `packages/application/src/memeradar_application/execution_mode.py` | SOURCE | KEEP | I3 T1 C0 D3 M0 R0 S0; defs=3, imports/exports=4; witness `apps/api/src/memeradar_api/read/__init__.py:44`, `apps/api/src/memeradar_api/read/__init__.py:45` |
| 344 | ` M` | `packages/application/src/memeradar_application/fast_safety.py` | SOURCE | KEEP | I1 T2 C0 D3 M0 R0 S0; defs=7, imports/exports=10; witness `packages/application/src/memeradar_application/early_runtime.py:57`, `tests/unit/test_early_runtime.py:13` |
| 345 | ` M` | `packages/application/src/memeradar_application/flow_analysis.py` | SOURCE | KEEP | I1 T4 C0 D4 M0 R0 S0; defs=15, imports/exports=16; witness `packages/application/src/memeradar_application/feature_windows.py:54`, `tests/contract/test_phase3_sprint3_3.py:9` |
| 346 | ` M` | `packages/application/src/memeradar_application/historical_dataset.py` | SOURCE | KEEP | I7 T5 C2 D5 M0 R3 S2; defs=15, imports/exports=12; witness `apps/api/src/memeradar_api/read/__init__.py:48`, `apps/api/src/memeradar_api/read/__init__.py:51` |
| 347 | ` M` | `packages/application/src/memeradar_application/holder_graph.py` | SOURCE | KEEP | I4 T13 C0 D3 M0 R0 S1; defs=19, imports/exports=15; witness `packages/application/src/memeradar_application/confluence.py:40`, `packages/application/src/memeradar_application/external_wallet.py:45` |
| 348 | `??` | `packages/application/src/memeradar_application/identity_matching.py` | SOURCE | KEEP | I4 T0 C0 D2 M0 R0 S1; defs=1, imports/exports=1; witness `packages/application/src/memeradar_application/correlation.py:64`, `packages/application/src/memeradar_application/early_features.py:41` |
| 349 | ` M` | `packages/application/src/memeradar_application/launch_lifecycle.py` | SOURCE | KEEP | I1 T2 C0 D4 M0 R0 S1; defs=19, imports/exports=12; witness `packages/persistence/src/memeradar_persistence/read_queries.py:45`, `tests/unit/test_gmgn_shadow_isolation.py:17` |
| 350 | `??` | `packages/application/src/memeradar_application/market_archetypes.py` | SOURCE | KEEP | I1 T1 C0 D2 M0 R0 S0; defs=4, imports/exports=5; witness `packages/application/src/memeradar_application/early_features.py:42`, `tests/unit/test_market_archetypes.py:8` |
| 351 | `??` | `packages/application/src/memeradar_application/operator_memory.py` | SOURCE | KEEP | I6 T7 C0 D1 M0 R2 S4; defs=8, imports/exports=10; witness `apps/worker/src/memeradar_worker/forward_evidence.py:41`, `apps/worker/src/memeradar_worker/wallet_history.py:15` |
| 352 | ` M` | `packages/application/src/memeradar_application/opportunity_research.py` | SOURCE | KEEP | I2 T4 C3 D2 M0 R3 S0; defs=37, imports/exports=17; witness `packages/application/src/memeradar_application/caller_outcomes.py:1161`, `packages/application/src/memeradar_application/historical_dataset.py:25` |
| 353 | `??` | `packages/application/src/memeradar_application/opportunity_window.py` | SOURCE | KEEP | I5 T6 C0 D2 M0 R2 S6; defs=10, imports/exports=11; witness `apps/worker/src/memeradar_worker/forward_evidence.py:42`, `packages/application/src/memeradar_application/read_api.py:37` |
| 354 | ` M` | `packages/application/src/memeradar_application/organic_momentum.py` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=3, imports/exports=8; witness `packages/application/src/memeradar_application/early_runtime.py:58`, `tests/unit/test_organic_momentum.py:5` |
| 355 | ` M` | `packages/application/src/memeradar_application/paper_execution.py` | SOURCE | KEEP | I3 T6 C1 D3 M0 R0 S2; defs=29, imports/exports=16; witness `packages/application/src/memeradar_application/backtesting.py:42`, `packages/application/src/memeradar_application/shadow_entry.py:33` |
| 356 | ` M` | `packages/application/src/memeradar_application/price_semantics.py` | SOURCE | KEEP | I6 T2 C0 D3 M0 R2 S0; defs=7, imports/exports=8; witness `packages/application/src/memeradar_application/caller_outcomes.py:37`, `packages/application/src/memeradar_application/early_features.py:43` |
| 357 | ` M` | `packages/application/src/memeradar_application/provider_contracts.py` | SOURCE | KEEP | I53 T78 C13 D8 M0 R3 S1; defs=50, imports/exports=11; witness `apps/api/src/memeradar_api/manual.py:18`, `apps/api/src/memeradar_api/read/__init__.py:54` |
| 358 | ` M` | `packages/application/src/memeradar_application/provider_metadata.py` | SOURCE | KEEP | I6 T2 C0 D5 M0 R0 S1; defs=4, imports/exports=2; witness `apps/api/src/memeradar_api/operations.py:19`, `apps/api/src/memeradar_api/read/__init__.py:57` |
| 359 | ` M` | `packages/application/src/memeradar_application/provider_routing.py` | SOURCE | KEEP | I1 T2 C0 D3 M0 R0 S0; defs=7, imports/exports=10; witness `packages/providers/src/memeradar_providers/composition.py:32`, `tests/unit/test_provider_routing.py:9` |
| 360 | ` M` | `packages/application/src/memeradar_application/pumpfun_forward_report.py` | SOURCE | KEEP | I0 T1 C1 D3 M0 R2 S0; defs=33, imports/exports=8; witness `scripts/pumpfun_forward_report.py:29`, `tests/unit/test_pumpfun_forward_report.py:1` |
| 361 | `??` | `packages/application/src/memeradar_application/receipt_reconciliation.py` | SOURCE | KEEP | I7 T4 C0 D4 M0 R0 S5; defs=7, imports/exports=8; witness `apps/api/src/memeradar_api/read/__init__.py:135`, `apps/api/src/memeradar_api/read/operations.py:26` |
| 362 | `??` | `packages/application/src/memeradar_application/relay_correlation.py` | SOURCE | KEEP | I6 T3 C0 D2 M0 R0 S5; defs=8, imports/exports=10; witness `apps/api/src/memeradar_api/read/__init__.py:136`, `apps/api/src/memeradar_api/read/__init__.py:137` |
| 363 | `??` | `packages/application/src/memeradar_application/rule_impact.py` | SOURCE | KEEP | I2 T2 C0 D2 M0 R0 S2; defs=3, imports/exports=6; witness `packages/application/src/memeradar_application/rule_outcome_association.py:22`, `packages/persistence/src/memeradar_persistence/read_queries.py:142` |
| 364 | `??` | `packages/application/src/memeradar_application/rule_outcome_association.py` | SOURCE | KEEP | I5 T5 C0 D2 M0 R0 S5; defs=15, imports/exports=12; witness `apps/api/src/memeradar_api/read/__init__.py:138`, `apps/api/src/memeradar_api/read/__init__.py:141` |
| 365 | `??` | `packages/application/src/memeradar_application/service_conflicts.py` | SOURCE | KEEP | I1 T4 C0 D3 M0 R0 S3; defs=5, imports/exports=10; witness `apps/worker/src/memeradar_worker/operations_jobs.py:17`, `tests/integration/test_service_conflict_persistence_postgres.py:14` |
| 366 | `??` | `packages/application/src/memeradar_application/services.py` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=6, imports/exports=8; witness `apps/api/src/memeradar_api/services.py:32`, `tests/contract/test_services_api.py:21` |
| 367 | ` M` | `packages/application/src/memeradar_application/signal_hardening.py` | SOURCE | KEEP | I6 T5 C0 D4 M0 R1 S0; defs=22, imports/exports=13; witness `packages/application/src/memeradar_application/correlation.py:66`, `packages/application/src/memeradar_application/decision_engine.py:44` |
| 368 | `??` | `packages/application/src/memeradar_application/social_sources.py` | SOURCE | KEEP | I2 T0 C0 D3 M0 R0 S0; defs=4, imports/exports=7; witness `apps/api/src/memeradar_api/main.py:25`, `apps/api/src/memeradar_api/social.py:19` |
| 369 | ` M` | `packages/application/src/memeradar_application/stream_integrity.py` | SOURCE | KEEP | I6 T5 C3 D4 M0 R0 S1; defs=34, imports/exports=16; witness `apps/worker/src/memeradar_worker/early_discovery.py:44`, `packages/application/src/memeradar_application/early_worker.py:13` |
| 370 | ` M` | `packages/application/src/memeradar_application/token_security.py` | SOURCE | KEEP | I0 T4 C0 D1 M0 R0 S0; defs=9, imports/exports=10; witness `tests/contract/test_phase3_sprint3_1.py:16`, `tests/smoke/test_compose_contract.py:83` |
| 371 | `??` | `packages/application/src/memeradar_application/wallet_candidate_discovery.py` | SOURCE | KEEP | I5 T3 C0 D6 M0 R0 S3; defs=9, imports/exports=13; witness `apps/worker/src/memeradar_worker/wallet_history.py:18`, `apps/worker/src/memeradar_worker/wallet_jobs.py:15` |
| 372 | ` M` | `packages/application/src/memeradar_application/wallet_relationship.py` | SOURCE | KEEP | I2 T1 C0 D4 M0 R0 S1; defs=12, imports/exports=14; witness `apps/worker/src/memeradar_worker/wallet_history.py:21`, `packages/persistence/src/memeradar_persistence/read_queries.py:153` |
| 373 | ` M` | `packages/application/src/memeradar_application/wallet_scoring.py` | SOURCE | KEEP | I3 T8 C0 D5 M0 R0 S1; defs=11, imports/exports=13; witness `packages/application/src/memeradar_application/confluence.py:41`, `packages/application/src/memeradar_application/external_wallet.py:47` |
| 374 | ` M` | `packages/application/src/memeradar_application/wallet_tracking.py` | SOURCE | KEEP | I9 T16 C0 D5 M0 R0 S1; defs=20, imports/exports=14; witness `apps/api/src/memeradar_api/read/__init__.py:147`, `apps/api/src/memeradar_api/read/wallets.py:28` |
| 375 | ` M` | `packages/domain/src/memeradar_domain/__init__.py` | SOURCE | KEEP | I173 T208 C8 D9 M0 R10 S30; defs=0, imports/exports=11; package/export boundary; witness `apps/api/src/memeradar_api/operations.py:20`, `apps/api/src/memeradar_api/read/__init__.py:148` |
| 376 | ` M` | `packages/domain/src/memeradar_domain/caller.py` | SOURCE | KEEP | I1 T0 C0 D3 M0 R0 S0; defs=18, imports/exports=13; witness `packages/domain/src/memeradar_domain/__init__.py:3`, `docs/reports/INTERRUPTED_RESUME.md:88` |
| 377 | ` M` | `packages/domain/src/memeradar_domain/chain.py` | SOURCE | KEEP | I1 T1 C0 D3 M0 R0 S0; defs=13, imports/exports=11; witness `packages/domain/src/memeradar_domain/__init__.py:22`, `tests/contract/test_extension_e8_4_stream_integrity.py:12` |
| 378 | ` M` | `packages/domain/src/memeradar_domain/lifecycle.py` | SOURCE | KEEP | I1 T0 C0 D3 M0 R0 S0; defs=5, imports/exports=10; witness `packages/domain/src/memeradar_domain/__init__.py:65`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:186` |
| 379 | `??` | `packages/domain/src/memeradar_domain/service_conflict.py` | SOURCE | KEEP | I1 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=9; witness `packages/domain/src/memeradar_domain/__init__.py:91`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:189` |
| 380 | ` M` | `packages/persistence/src/memeradar_persistence/__init__.py` | SOURCE | KEEP | I10 T52 C7 D21 M0 R4 S22; defs=0, imports/exports=10; package/export boundary; witness `apps/api/src/memeradar_api/main.py:27`, `apps/api/src/memeradar_api/services.py:38` |
| 381 | ` M` | `packages/persistence/src/memeradar_persistence/control.py` | SOURCE | KEEP | I1 T0 C0 D3 M0 R0 S1; defs=8, imports/exports=11; witness `packages/persistence/src/memeradar_persistence/__init__.py:3`, `docs/reports/INTERRUPTED_RESUME.md:91` |
| 382 | ` M` | `packages/persistence/src/memeradar_persistence/models.py` | SOURCE | KEEP | I10 T12 C1 D9 M0 R0 S16; defs=42, imports/exports=8; witness `apps/worker/src/memeradar_worker/wallet_history.py:41`, `packages/persistence/src/memeradar_persistence/__init__.py:9` |
| 383 | `??` | `packages/persistence/src/memeradar_persistence/opportunity_window.py` | SOURCE | KEEP | I2 T1 C0 D2 M0 R0 S3; defs=4, imports/exports=10; witness `packages/persistence/src/memeradar_persistence/__init__.py:56`, `packages/persistence/src/memeradar_persistence/read_queries.py:198` |
| 384 | ` M` | `packages/persistence/src/memeradar_persistence/read_queries.py` | SOURCE | KEEP | I1 T6 C0 D17 M0 R0 S4; defs=44, imports/exports=41; witness `packages/persistence/src/memeradar_persistence/__init__.py:58`, `tests/integration/test_operator_memory_graph_projection.py:13` |
| 385 | ` M` | `packages/persistence/src/memeradar_persistence/repositories.py` | SOURCE | KEEP | I4 T6 C0 D12 M0 R0 S8; defs=80, imports/exports=22; witness `packages/persistence/src/memeradar_persistence/__init__.py:59`, `packages/persistence/src/memeradar_persistence/opportunity_window.py:22` |
| 386 | ` M` | `packages/persistence/src/memeradar_persistence/stream.py` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S2; defs=15, imports/exports=10; witness `packages/persistence/src/memeradar_persistence/__init__.py:100`, `tests/unit/test_stream_persistence_contract.py:15` |
| 387 | ` M` | `packages/persistence/src/memeradar_persistence/uow.py` | SOURCE | KEEP | I1 T1 C0 D4 M0 R0 S1; defs=5, imports/exports=13; witness `packages/persistence/src/memeradar_persistence/__init__.py:101`, `tests/unit/test_database_durability.py:5` |
| 388 | ` M` | `packages/providers/src/memeradar_providers/composition.py` | SOURCE | KEEP | I5 T3 C1 D6 M0 R0 S0; defs=13, imports/exports=27; witness `apps/api/src/memeradar_api/main.py:33`, `apps/worker/src/memeradar_worker/early_discovery.py:72` |
| 389 | ` M` | `packages/providers/src/memeradar_providers/dexscreener.py` | SOURCE | KEEP | I1 T7 C3 D4 M0 R0 S0; defs=31, imports/exports=20; witness `packages/providers/src/memeradar_providers/composition.py:40`, `scripts/dexscreener_doctor.py:31` |
| 390 | ` M` | `packages/providers/src/memeradar_providers/evm_protocols.py` | SOURCE | KEEP | I7 T3 C0 D4 M0 R0 S0; defs=19, imports/exports=15; witness `packages/providers/src/memeradar_providers/base.py:4`, `packages/providers/src/memeradar_providers/bnb.py:4` |
| 391 | ` M` | `packages/providers/src/memeradar_providers/evm_rpc.py` | SOURCE | KEEP | I4 T2 C0 D5 M0 R0 S0; defs=16, imports/exports=18; witness `packages/providers/src/memeradar_providers/chainlink.py:16`, `packages/providers/src/memeradar_providers/composition.py:41` |
| 392 | ` M` | `packages/providers/src/memeradar_providers/evm_sellability.py` | SOURCE | KEEP | I0 T1 C0 D3 M0 R0 S0; defs=5, imports/exports=11; witness `tests/unit/test_evm_sellability.py:8`, `docs/reports/INTERRUPTED_RESUME.md:100` |
| 393 | ` M` | `packages/providers/src/memeradar_providers/launchpad_dex.py` | SOURCE | KEEP | I2 T8 C0 D2 M0 R0 S0; defs=26, imports/exports=16; witness `packages/providers/src/memeradar_providers/protocol_registry.py:28`, `packages/providers/src/memeradar_providers/protocol_stream.py:15` |
| 394 | ` M` | `packages/providers/src/memeradar_providers/protocol_registry.py` | SOURCE | KEEP | I2 T3 C1 D5 M0 R0 S0; defs=25, imports/exports=17; witness `apps/worker/src/memeradar_worker/early_discovery.py:73`, `packages/providers/src/memeradar_providers/protocol_verification.py:22` |
| 395 | `??` | `packages/providers/src/memeradar_providers/protocol_verification.py` | SOURCE | KEEP | I0 T1 C0 D3 M0 R0 S0; defs=4, imports/exports=14; witness `tests/unit/test_protocol_verification.py:16`, `docs/reports/INTERRUPTED_RESUME.md:202` |
| 396 | ` M` | `packages/providers/src/memeradar_providers/pump_fun_idl.py` | SOURCE | KEEP | I8 T3 C3 D2 M0 R1 S0; defs=11, imports/exports=5; witness `apps/worker/src/memeradar_worker/forward_evidence.py:82`, `packages/providers/src/memeradar_providers/protocol_registry.py:36` |
| 397 | ` M` | `packages/providers/src/memeradar_providers/robinhood.py` | SOURCE | KEEP | I2 T3 C0 D3 M0 R0 S0; defs=9, imports/exports=14; witness `apps/worker/src/memeradar_worker/intent_jobs.py:24`, `packages/providers/src/memeradar_providers/composition.py:51` |
| 398 | ` M` | `packages/providers/src/memeradar_providers/social.py` | SOURCE | KEEP | I2 T8 C2 D4 M0 R0 S0; defs=38, imports/exports=17; witness `packages/providers/src/memeradar_providers/composition.py:57`, `packages/providers/src/memeradar_providers/telegram.py:26` |
| 399 | ` M` | `packages/providers/src/memeradar_providers/solana_raw_stream.py` | SOURCE | KEEP | I4 T4 C1 D5 M0 R1 S0; defs=19, imports/exports=22; witness `apps/worker/src/memeradar_worker/early_discovery.py:77`, `apps/worker/src/memeradar_worker/operations_jobs.py:38` |
| 400 | ` M` | `packages/providers/src/memeradar_providers/solana_rpc.py` | SOURCE | KEEP | I2 T4 C3 D3 M0 R0 S0; defs=8, imports/exports=21; witness `packages/providers/src/memeradar_providers/composition.py:58`, `packages/providers/src/memeradar_providers/solana_raw_stream.py:49` |
| 401 | ` M` | `packages/providers/src/memeradar_providers/telegram.py` | SOURCE | KEEP | I2 T6 C2 D4 M0 R0 S1; defs=12, imports/exports=14; witness `apps/worker/src/memeradar_worker/operations_jobs.py:41`, `packages/providers/src/memeradar_providers/composition.py:59` |
| 402 | ` M` | `packages/providers/src/memeradar_providers/transport.py` | SOURCE | KEEP | I33 T52 C11 D3 M0 R3 S0; defs=17, imports/exports=12; witness `apps/worker/src/memeradar_worker/early_discovery.py:82`, `apps/worker/src/memeradar_worker/forward_evidence.py:83` |
| 403 | `??` | `prompts/MemeRadar.md` | DOC | EXTERNAL_OWNED | witness `scripts/run_codex_validation.sh:19`, `scripts/run_codex_validation.sh.bak:10` |
| 404 | `??` | `prompts/MemeRadar.md.new` | DOC | EXTERNAL_OWNED | witness `docs/reports/INTERRUPTED_RESUME.md:204` |
| 405 | ` M` | `pyproject.toml` | SOURCE | KEEP | I1 T2 C3 D1 M0 R0 S0; witness `apps/web/e2e/helpers/source-identity.mjs:22`, `scripts/release_identity.py:79` |
| 406 | ` M` | `requirements.lock` | GENERATED | KEEP | witness `.github/workflows/ci.yml:41`, `Makefile:62` |
| 407 | ` M` | `scripts/alpha_readiness.py` | SOURCE | KEEP | I0 T1 C1 D3 M0 R0 S0; defs=10, imports/exports=26; witness `Makefile:90`, `tests/unit/test_alpha_readiness_database.py:9` |
| 408 | ` M` | `scripts/check_migrations.py` | SOURCE | KEEP | I0 T1 C2 D9 M0 R0 S0; defs=1, imports/exports=7; witness `Makefile:231`, `scripts/release_identity.py:50` |
| 409 | ` M` | `scripts/dexscreener_doctor.py` | SOURCE | KEEP | I0 T1 C1 D2 M0 R0 S0; defs=6, imports/exports=14; witness `Makefile:295`, `tests/unit/test_free_provider_doctors.py:10` |
| 410 | `??` | `scripts/host-acceptance.test.mjs` | TEST | KEEP | I1 T0 C0 D3 M0 R0 S0; defs=0, imports/exports=0; node:test standalone test; not pytest; witness `apps/web/e2e/helpers/source-identity.mjs:23`, `docs/ui-redesign-vnext/CLOSURE_REGISTER.md:7` |
| 411 | `??` | `scripts/import_wallet_seeds.py` | SOURCE | KEEP | I0 T1 C1 D5 M0 R0 S1; defs=2, imports/exports=8; witness `scripts/validate_wallet_seeds.py:218`, `tests/unit/test_wallet_seed_persistence.py:163` |
| 412 | `??` | `scripts/radar-fixture-api.test.mjs` | TEST | KEEP | I1 T0 C0 D1 M0 R0 S0; defs=1, imports/exports=0; node:test standalone test; not pytest; witness `apps/web/e2e/helpers/source-identity.mjs:24`, `docs/ui-redesign-vnext/TEST_RESULTS.md:103` |
| 413 | `??` | `scripts/run_codex_validation.sh` | SOURCE | KEEP | I0 T0 C1 D7 M0 R0 S0; witness `.dockerignore:23`, `docs/reports/INTERRUPTED_RESUME.md:206` |
| 414 | `??` | `scripts/run_codex_validation.sh.bak` | UNKNOWN | EXTERNAL_OWNED | witness `docs/reports/INTERRUPTED_RESUME.md:207`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:194` |
| 415 | ` M` | `scripts/security_review.py` | SOURCE | KEEP | I0 T3 C1 D4 M0 R0 S0; defs=21, imports/exports=15; witness `Makefile:205`, `tests/contract/test_phase11_sprint11_3.py:9` |
| 416 | `??` | `scripts/source-identity.test.mjs` | TEST | KEEP | I1 T0 C0 D2 M0 R0 S0; defs=0, imports/exports=2; node:test standalone test; not pytest; witness `apps/web/e2e/helpers/source-identity.mjs:23`, `docs/ui-redesign-vnext/FINAL_CLOSURE_REPORT.md:201` |
| 417 | `??` | `scripts/tailfnohup.sh` | SOURCE | KEEP | I0 T0 C0 D2 M0 R0 S0; witness `docs/reports/INTERRUPTED_RESUME.md:208`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:195` |
| 418 | `??` | `scripts/validate_wallet_seeds.py` | SOURCE | KEEP | I0 T1 C1 D1 M0 R0 S0; defs=8, imports/exports=9; witness `scripts/import_wallet_seeds.py:25`, `tests/unit/test_wallet_seed_validation.py:8` |
| 419 | `??` | `scripts/visual-evidence.test.mjs` | TEST | KEEP | I1 T0 C0 D3 M0 R0 S0; defs=0, imports/exports=0; node:test standalone test; not pytest; witness `apps/web/e2e/helpers/source-identity.mjs:23`, `docs/ui-redesign-vnext/CLOSURE_REGISTER.md:95` |
| 420 | ` M` | `tests/contract/test_alpha_caller_providers.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=9, imports/exports=11; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2059`, `docs/reports/INTERRUPTED_RESUME.md:107` |
| 421 | ` M` | `tests/contract/test_alpha_caller_read_api.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=10, imports/exports=8; pytest testpaths=tests; witness `docs/TESTING.md:407`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2053` |
| 422 | ` M` | `tests/contract/test_alpha_readiness_report.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=4, imports/exports=5; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3929`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:59` |
| 423 | ` M` | `tests/contract/test_api_schema.py` | TEST | KEEP | I0 T0 C0 D8 M0 R0 S0; defs=4, imports/exports=5; pytest testpaths=tests; witness `docs/API.md:15`, `docs/TESTING.md:275` |
| 424 | ` M` | `tests/contract/test_extension_e8_6_creator_graph.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=1, imports/exports=3; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 425 | ` M` | `tests/contract/test_extension_opportunity_research.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=2; pytest testpaths=tests; witness `docs/TESTING.md:430`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:16` |
| 426 | ` M` | `tests/contract/test_extension_task6_chain_opportunity_api.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=5, imports/exports=8; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 427 | ` M` | `tests/contract/test_historical_dataset_contract.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=3, imports/exports=3; pytest testpaths=tests; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:16` |
| 428 | ` M` | `tests/contract/test_phase7_sprint7_2.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=5, imports/exports=10; pytest testpaths=tests; witness `docs/TESTING.md:407`, `docs/reports/INTERRUPTED_RESUME.md:110` |
| 429 | `??` | `tests/contract/test_services_api.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=13, imports/exports=14; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2210`, `docs/reports/INTERRUPTED_RESUME.md:209` |
| 430 | `??` | `tests/contract/test_social_source_api.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=4, imports/exports=5; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2042`, `docs/reports/INTERRUPTED_RESUME.md:210` |
| 431 | `??` | `tests/integration/test_dex_candidate_forward_outcomes_postgres.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=6, imports/exports=14; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4262`, `docs/reports/FRONTEND_VNEXT_RECOVERY.md:40` |
| 432 | ` M` | `tests/integration/test_early_runtime_persistence.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=7, imports/exports=12; pytest testpaths=tests; witness `docs/audits/V8_2_9PLUS_SCORECARD.md:20`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:4496` |
| 433 | `??` | `tests/integration/test_early_social_evidence_postgres.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=11; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 434 | `??` | `tests/integration/test_operator_memory_graph_projection.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=1, imports/exports=9; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 435 | `??` | `tests/integration/test_operator_memory_persistence.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=3, imports/exports=11; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 436 | ` M` | `tests/integration/test_persistence_postgres.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=9, imports/exports=16; pytest testpaths=tests; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:269` |
| 437 | ` M` | `tests/integration/test_read_query_service.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=3, imports/exports=10; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3238`, `docs/reports/agentic-loop/2026-10-07-canonical-token-observation-matching.md:26` |
| 438 | `??` | `tests/integration/test_service_conflict_persistence_postgres.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=12; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2975`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:199` |
| 439 | ` M` | `tests/integration/test_stream_persistence_postgres.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=9; pytest testpaths=tests; witness `docs/reports/INTERRUPTED_RESUME.md:111`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:106` |
| 440 | ` M` | `tests/property/test_invariants.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=4, imports/exports=8; pytest testpaths=tests; witness `docs/TESTING.md:275`, `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:191` |
| 441 | `??` | `tests/unit/test_alert_persistence.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=6; pytest testpaths=tests; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:269`, `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:213` |
| 442 | ` M` | `tests/unit/test_alert_pipeline.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=19, imports/exports=11; pytest testpaths=tests; witness `docs/TESTING.md:458`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:1336` |
| 443 | ` M` | `tests/unit/test_alpha_caller_outcomes.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=10, imports/exports=8; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2066`, `docs/reports/INTERRUPTED_RESUME.md:112` |
| 444 | ` M` | `tests/unit/test_alpha_caller_persistence.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=17, imports/exports=11; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2042`, `docs/reports/INTERRUPTED_RESUME.md:113` |
| 445 | `??` | `tests/unit/test_alpha_readiness_database.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=6, imports/exports=9; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3929`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:61` |
| 446 | `??` | `tests/unit/test_bounded_read_extensions.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=7, imports/exports=7; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2164`, `docs/reports/INTERRUPTED_RESUME.md:211` |
| 447 | ` M` | `tests/unit/test_config.py` | TEST | KEEP | I0 T0 C0 D6 M0 R0 S0; defs=17, imports/exports=2; pytest testpaths=tests; witness `docs/FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md:255`, `docs/PROD_READ_ONLY_CLOSURE_GAP_MATRIX_2026-09-15.md:103` |
| 448 | ` M` | `tests/unit/test_creator_graph.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=9, imports/exports=4; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 449 | `??` | `tests/unit/test_cross_chain_evidence_persistence.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=6, imports/exports=11; pytest testpaths=tests; witness `docs/reports/memeradar-upstream-intelligence-closure-2026-10-14.md:69` |
| 450 | ` M` | `tests/unit/test_dexscreener.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=18, imports/exports=12; pytest testpaths=tests; witness `docs/EARLY_ALPHA_SOURCE_MATRIX.md:20`, `docs/FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md:256` |
| 451 | `??` | `tests/unit/test_dexscreener_discovery.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=3, imports/exports=7; pytest testpaths=tests; witness `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:201` |
| 452 | ` M` | `tests/unit/test_early_detection.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=8, imports/exports=7; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3608`, `docs/reports/agentic-loop/2026-10-07-verified-pump-trades-early-features.md:32` |
| 453 | ` M` | `tests/unit/test_early_failure_analysis.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=5, imports/exports=2; pytest testpaths=tests; witness `docs/reports/agentic-loop/2026-10-07-same-age-failure-controls.md:30`, `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:48` |
| 454 | ` M` | `tests/unit/test_early_features.py` | TEST | KEEP | I0 T0 C0 D14 M0 R0 S0; defs=50, imports/exports=8; pytest testpaths=tests; witness `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:77`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2525` |
| 455 | ` M` | `tests/unit/test_early_read_projection.py` | TEST | KEEP | I0 T0 C0 D9 M0 R0 S0; defs=6, imports/exports=12; pytest testpaths=tests; witness `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:77`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2525` |
| 456 | ` M` | `tests/unit/test_early_replay.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=8, imports/exports=12; pytest testpaths=tests; witness `docs/reports/early-alpha-validation-implementation.md:57` |
| 457 | ` M` | `tests/unit/test_early_runtime.py` | TEST | KEEP | I0 T0 C0 D26 M0 R0 S0; defs=36, imports/exports=11; pytest testpaths=tests; witness `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:77`, `docs/audits/V8_2_9PLUS_SCORECARD.md:20` |
| 458 | ` M` | `tests/unit/test_early_scoring.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=10, imports/exports=6; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:59`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:115` |
| 459 | ` M` | `tests/unit/test_event_time_semantics.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=6, imports/exports=3; pytest testpaths=tests; witness `docs/reports/agentic-loop/2026-10-07-event-time-quality.md:28` |
| 460 | ` M` | `tests/unit/test_evidence_helpers.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=5, imports/exports=4; pytest testpaths=tests; witness `docs/reports/memeradar-purpose-refactor.md:356` |
| 461 | ` M` | `tests/unit/test_evm_protocols.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=9, imports/exports=6; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2154`, `docs/reports/INTERRUPTED_RESUME.md:116` |
| 462 | ` M` | `tests/unit/test_evm_rpc.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=21, imports/exports=12; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2154`, `docs/reports/INTERRUPTED_RESUME.md:117` |
| 463 | ` M` | `tests/unit/test_evm_sellability.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=6, imports/exports=6; pytest testpaths=tests; witness `docs/reports/INTERRUPTED_RESUME.md:118`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:118` |
| 464 | `??` | `tests/unit/test_execution_mode.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=3, imports/exports=1; pytest testpaths=tests; witness `docs/reports/INTERRUPTED_RESUME.md:212`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:202` |
| 465 | `??` | `tests/unit/test_execution_safety_contracts.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=4, imports/exports=7; pytest testpaths=tests; witness `docs/reports/INTERRUPTED_RESUME.md:213`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:203` |
| 466 | ` M` | `tests/unit/test_flow_analysis.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=17, imports/exports=7; pytest testpaths=tests; witness `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:77`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3137` |
| 467 | ` M` | `tests/unit/test_free_provider_doctors.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=6, imports/exports=11; pytest testpaths=tests; witness `docs/FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md:257`, `docs/TESTING.md:27` |
| 468 | ` M` | `tests/unit/test_historical_dataset.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=8, imports/exports=5; pytest testpaths=tests; witness `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:14` |
| 469 | `??` | `tests/unit/test_historical_dataset_ingest.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=7, imports/exports=3; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3929`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:59` |
| 470 | ` M` | `tests/unit/test_holder_graph.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=14, imports/exports=6; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:129`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:428` |
| 471 | ` M` | `tests/unit/test_launch_lifecycle.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=14, imports/exports=4; pytest testpaths=tests; witness `docs/EXTERNAL_ALPHA_INTELLIGENCE_GAP_MATRIX_2026-09-14.md:25`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3298` |
| 472 | ` M` | `tests/unit/test_launchpad_dex.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=12, imports/exports=8; pytest testpaths=tests; witness `docs/EARLY_ALPHA_SOURCE_MATRIX.md:10`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:3608` |
| 473 | `??` | `tests/unit/test_lifecycle_funnel.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=4, imports/exports=8; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:229` |
| 474 | `??` | `tests/unit/test_market_archetypes.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=5, imports/exports=7; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2525`, `docs/reports/agentic-loop/2026-10-07-market-behavior-archetypes.md:26` |
| 475 | ` M` | `tests/unit/test_migration_contract.py` | TEST | KEEP | I0 T0 C0 D7 M0 R0 S0; defs=3, imports/exports=7; pytest testpaths=tests; witness `docs/TESTING.md:167`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2077` |
| 476 | `??` | `tests/unit/test_operator_memory.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=7, imports/exports=6; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 477 | `??` | `tests/unit/test_operator_memory_persistence_contract.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=2, imports/exports=1; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 478 | `??` | `tests/unit/test_operator_memory_worker.py` | TEST | KEEP | I0 T0 C0 D0 M0 R0 S0; defs=4, imports/exports=9; pytest testpaths=tests; no literal/static inbound hit; not proof of unused |
| 479 | ` M` | `tests/unit/test_opportunity_research.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=8, imports/exports=7; pytest testpaths=tests; witness `docs/TESTING.md:430`, `docs/reports/agentic-loop/CURRENT_CHANGE_LEDGER.md:15` |
| 480 | `??` | `tests/unit/test_opportunity_window_policy.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=13, imports/exports=10; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:42`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:140` |
| 481 | ` M` | `tests/unit/test_organic_momentum.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=5, imports/exports=3; pytest testpaths=tests; witness `docs/reports/agentic-loop/2026-10-07-wallet-cluster-evidence-coverage.md:44`, `docs/superpowers/plans/2026-09-19-early-alpha-runtime-integration.md:58` |
| 482 | ` M` | `tests/unit/test_paper_execution.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=15, imports/exports=9; pytest testpaths=tests; witness `docs/TESTING.md:353`, `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2170` |
| 483 | ` M` | `tests/unit/test_position_read.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=10, imports/exports=7; pytest testpaths=tests; witness `docs/TESTING.md:458`, `docs/reports/INTERRUPTED_RESUME.md:121` |
| 484 | ` M` | `tests/unit/test_protocol_registry.py` | TEST | KEEP | I0 T0 C0 D6 M0 R0 S0; defs=18, imports/exports=7; pytest testpaths=tests; witness `docs/EARLY_ALPHA_SOURCE_MATRIX.md:10`, `docs/TESTING.md:167` |
| 485 | `??` | `tests/unit/test_protocol_verification.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=8, imports/exports=9; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2154`, `docs/reports/INTERRUPTED_RESUME.md:214` |
| 486 | ` M` | `tests/unit/test_provider_composition.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=22, imports/exports=10; pytest testpaths=tests; witness `docs/FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md:260`, `docs/TESTING.md:22` |
| 487 | ` M` | `tests/unit/test_provider_contracts.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=11, imports/exports=8; pytest testpaths=tests; witness `docs/reports/agentic-loop/2026-10-07-known-wallet-balance-refresh.md:46` |
| 488 | ` M` | `tests/unit/test_pump_fun_idl.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=19, imports/exports=3; pytest testpaths=tests; witness `docs/superpowers/plans/2026-09-21-pumpfun-launch-decoding.md:34` |
| 489 | ` M` | `tests/unit/test_pumpfun_forward_report.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=8, imports/exports=1; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2495`, `docs/reports/agentic-loop/2026-10-07-same-age-failure-controls.md:6` |
| 490 | ` M` | `tests/unit/test_read_persistence.py` | TEST | KEEP | I0 T0 C0 D22 M0 R0 S0; defs=56, imports/exports=20; pytest testpaths=tests; witness `docs/TESTING.md:458`, `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:106` |
| 491 | ` M` | `tests/unit/test_readiness_api.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=4, imports/exports=7; pytest testpaths=tests; witness `docs/reports/INTERRUPTED_RESUME.md:125`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:126` |
| 492 | `??` | `tests/unit/test_relay_correlation.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=4, imports/exports=5; pytest testpaths=tests; witness `docs/reports/memeradar-upstream-intelligence-closure-2026-10-14.md:76` |
| 493 | ` M` | `tests/unit/test_release_identity.py` | TEST | KEEP | I0 T0 C0 D6 M0 R0 S0; defs=4, imports/exports=4; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2077`, `docs/reports/INTERRUPTED_RESUME.md:126` |
| 494 | ` M` | `tests/unit/test_repository_integrity.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=9, imports/exports=7; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:190` |
| 495 | `??` | `tests/unit/test_robinhood_intent_reconciliation.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=10, imports/exports=11; pytest testpaths=tests; witness `docs/reports/memeradar-upstream-intelligence-closure-2026-10-14.md:77` |
| 496 | `??` | `tests/unit/test_rule_impact.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=5, imports/exports=3; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:227` |
| 497 | `??` | `tests/unit/test_rule_outcome_association.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=9, imports/exports=7; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:90`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:149` |
| 498 | ` M` | `tests/unit/test_runtime_settings_api.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=10, imports/exports=7; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:18` |
| 499 | `??` | `tests/unit/test_service_conflict_persistence.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=11; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2397`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:205` |
| 500 | `??` | `tests/unit/test_service_conflicts.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=5, imports/exports=6; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2397`, `docs/reports/agentic-loop/baseline-status-2026-10-07.txt:206` |
| 501 | ` M` | `tests/unit/test_signal_hardening.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=35, imports/exports=7; pytest testpaths=tests; witness `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:254`, `docs/reports/agentic-loop/2026-10-07-bundle-and-lifecycle-provenance.md:40` |
| 502 | `??` | `tests/unit/test_social_claims.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=3, imports/exports=4; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2051`, `docs/reports/INTERRUPTED_RESUME.md:215` |
| 503 | `??` | `tests/unit/test_social_source_worker.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=4, imports/exports=5; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2059`, `docs/reports/INTERRUPTED_RESUME.md:216` |
| 504 | `??` | `tests/unit/test_social_sources.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=2, imports/exports=4; pytest testpaths=tests; witness `docs/history/STATUS-2026-10-18-before-purpose-refactor.md:2042`, `docs/reports/INTERRUPTED_RESUME.md:217` |
| 505 | ` M` | `tests/unit/test_solana_raw_stream.py` | TEST | KEEP | I0 T0 C0 D8 M0 R0 S0; defs=29, imports/exports=16; pytest testpaths=tests; witness `docs/EARLY_ALPHA_SOURCE_MATRIX.md:9`, `docs/audits/EARLY_ALPHA_V4_CURRENT_STATE.md:316` |
| 506 | ` M` | `tests/unit/test_solana_rpc.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=19, imports/exports=14; pytest testpaths=tests; witness `docs/FREE_FIRST_PROVIDER_MIGRATION_RESULTS.md:261`, `docs/TESTING.md:19` |
| 507 | ` M` | `tests/unit/test_staged_lifecycle.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=8, imports/exports=4; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:189` |
| 508 | ` M` | `tests/unit/test_stream_integrity.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=28, imports/exports=6; pytest testpaths=tests; witness `docs/EARLY_ALPHA_SOURCE_MATRIX.md:9`, `docs/TESTING.md:167` |
| 509 | ` M` | `tests/unit/test_stream_persistence_contract.py` | TEST | KEEP | I0 T0 C0 D4 M0 R0 S0; defs=7, imports/exports=6; pytest testpaths=tests; witness `docs/TESTING.md:167`, `docs/reports/INTERRUPTED_RESUME.md:129` |
| 510 | `??` | `tests/unit/test_wallet_candidate_discovery.py` | TEST | KEEP | I0 T0 C0 D6 M0 R0 S0; defs=10, imports/exports=6; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:33`, `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md:13` |
| 511 | `??` | `tests/unit/test_wallet_candidate_persistence.py` | TEST | KEEP | I0 T0 C0 D5 M0 R0 S0; defs=4, imports/exports=13; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_2_CHANGE_LEDGER.md:216`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:101` |
| 512 | ` M` | `tests/unit/test_wallet_relationship.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=19, imports/exports=8; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:99`, `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md:38` |
| 513 | `??` | `tests/unit/test_wallet_reputation_refresh.py` | TEST | KEEP | I0 T0 C0 D2 M0 R0 S0; defs=2, imports/exports=9; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_3_CHANGE_LEDGER.md:160`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:97` |
| 514 | ` M` | `tests/unit/test_wallet_scoring.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=12, imports/exports=7; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md:42`, `docs/reports/agentic-loop/V8_3_VERIFICATION.md:101` |
| 515 | `??` | `tests/unit/test_wallet_seed_persistence.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=5, imports/exports=10; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:79`, `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md:30` |
| 516 | `??` | `tests/unit/test_wallet_seed_validation.py` | TEST | KEEP | I0 T0 C0 D1 M0 R0 S0; defs=3, imports/exports=4; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_CHANGE_LEDGER.md:25` |
| 517 | ` M` | `tests/unit/test_wallet_tracking.py` | TEST | KEEP | I0 T0 C0 D3 M0 R0 S0; defs=16, imports/exports=6; pytest testpaths=tests; witness `docs/reports/agentic-loop/V8_1_BASELINE_MANIFEST.md:34`, `docs/reports/agentic-loop/V8_1_CHANGE_LEDGER.md:12` |
| 518 | `??` | `uv.lock` | GENERATED | KEEP | witness `apps/web/e2e/helpers/source-identity.mjs:22` |

## Reproduction

1. Preserve recursive Git status **before** creating audit output: `git status --porcelain=v1 -z --untracked-files=all > /tmp/memeradar-path-audit-status.z`. Do not split a NUL-delimited snapshot into lines. Parse Git rename/copy records with their extra path field.
2. Save the reference Python procedure below as `/tmp/memeradar_path_audit.py` and run `python3 /tmp/memeradar_path_audit.py` from this repository. It makes no repository mutations, does not read `.codex` contents, and writes its evidence JSON only to `/tmp`. Its assertions enforce the historical 582/48/16/518 partition, all archive sizes/hashes and retained-copy equality. Its current delta intentionally changes if the runtime creates more files.
3. The procedure scans current public contents rather than reconstructing historical bytes. Re-running after concurrent code/report edits can change reference counts, line numbers and corpus digest; primary baseline path membership remains deterministic. This report adds four manually inspected registration witnesses for the type declaration, optional Playwright config, compiler config and migration revision, described above and in their table rows.
4. Reconcile all baseline ledger paths against the set difference; verify the row count and class/action totals. Never treat no import hit as deletion proof. No source/test removal or new ignore rule is part of the procedure.

<details>
<summary>Read-only reference procedure</summary>

```python
import ast,collections,hashlib,json,pathlib,re,subprocess,tarfile
ROOT=pathlib.Path('/home/ubra/codex/MemeRadar')
def status(data):
    out=[]; xs=data.split(b'\0');i=0
    while i<len(xs) and xs[i]:
        s=xs[i].decode();i+=1;out.append((s[:2],s[3:]))
        if any(x in s[:2] for x in 'RC'): i+=1
    return out
baseline_path='artifacts/verification/memeradar-deep-refactor-worktree-2026-10-18.status'
prior=status((ROOT/baseline_path).read_bytes())
now=status(pathlib.Path('/tmp/memeradar-path-audit-status.z').read_bytes())
manifest=json.loads((ROOT/'docs/history/visual-evidence-2026-10-18-manifest.json').read_text())
retained={r['path'] for r in manifest['rows'] if r['action']=='KEEP_REFERENCED_COPY_AND_ARCHIVE'}
task=set()
for x in ['__init__','common','candidates','tokens','wallets','callers','outcomes','operations','research']:task.add(f'apps/api/src/memeradar_api/read/{x}.py')
for x in ['read_api','read_common','read_candidates','read_tokens','read_wallets','read_callers','read_outcomes','read_positions','read_operations','read_research','pumpfun_forward']:task.add(f'packages/application/src/memeradar_application/{x}.py')
for x in ['main','early_discovery','wallet_jobs','intent_jobs','operations_jobs','forward_evidence']:task.add(f'apps/worker/src/memeradar_worker/{x}.py')
for p in ['tests/unit/test_read_api.py','tests/unit/test_read_api_routes.py','tests/unit/test_worker_entrypoint.py','tests/unit/test_pumpfun_forward_evidence.py','tests/unit/test_wallet_history_worker.py','tests/smoke/test_compose_contract.py','tests/integration/test_madeonsol_runtime_postgres.py']:task.add(p)
for p in ['lib/read-api.ts','lib/read-api.test.ts','components/outcomes.tsx','components/shell-client.tsx','components/outcomes.test.tsx','components/shell.test.tsx']:task.add('apps/web/src/app/'+p)
assert len(task)==39
for p in ['docs/STATUS.md','docs/ARCHITECTURE.md','docs/reports/memeradar-deep-refactor.md','docs/reports/memeradar-dead-code-and-archive-report.md','docs/ui-redesign-vnext/visual-evidence/runs/README.md','.gitignore','docs/history/visual-evidence-2026-10-18.tar.gz','docs/history/visual-evidence-2026-10-18-manifest.json','apps/api/src/memeradar_api/read.py']:task.add(p)
assert len(task)==48
assert task|retained <= {p for _,p in prior}
remaining=sorted((s,p) for s,p in prior if p not in task|retained)
assert len(prior)==582 and len(remaining)==518 and len(retained)==16
# Only public repository source/config/test/docs inputs. Never open .codex or actual environment/credential files.
paths=subprocess.check_output(['rg','--files','apps','packages','tests','scripts','infra','docs','fixtures','data','prompts'],cwd=ROOT,text=True).splitlines()
paths += ['README.md','Makefile','pyproject.toml','.gitignore','.dockerignore','.env.example','.github/workflows/ci.yml','requirements.lock','uv.lock']
allowed={'.py','.ts','.tsx','.mjs','.mts','.json','.md','.yaml','.yml','.toml','.sh','.css','.html','.txt','.csv','.lock','.bak','.new'}
texts={}
for p in sorted(set(paths)):
    if p.startswith('.codex/') or '/node_modules/' in p or '/.next/' in p:continue
    f=ROOT/p
    if not f.is_file() or (f.suffix not in allowed and f.name not in ['Makefile','.gitignore','.dockerignore','.env.example']):continue
    if f.stat().st_size>2_000_000:continue
    try: texts[p]=f.read_text()
    except UnicodeError:pass
# Module identities and exact static import/re-export graph, including relative imports.
modules={}
for p in texts:
    if not p.endswith('.py'):continue
    if '/src/' in p:m=p.split('/src/',1)[1][:-3].replace('/','.')
    else:m=p[:-3].replace('/','.')
    if m.endswith('.__init__'):m=m[:-9]
    modules[m]=p
refs=collections.defaultdict(set); definitions={};exports={};parse_errors=[]
for p,t in texts.items():
    if p.endswith('.py'):
        try:tree=ast.parse(t)
        except SyntaxError:parse_errors.append(p);continue
        definitions[p]=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) for n in tree.body)
        exports[p]=sum(isinstance(n,(ast.Import,ast.ImportFrom)) for n in tree.body)
        m=next((m for m,q in modules.items() if q==p),'');package=m if p.endswith('/__init__.py') else m.rpartition('.')[0]
        for n in ast.walk(tree):
            targets=[]
            if isinstance(n,ast.Import):targets=[a.name for a in n.names]
            elif isinstance(n,ast.ImportFrom):
                if n.level:
                    bits=package.split('.');base='.'.join(bits[:len(bits)-n.level+1]);base+='.'+n.module if n.module else ''
                else:base=n.module or ''
                targets=[base]+[base+'.'+a.name for a in n.names]
            for q in targets:
                if q in modules and modules[q]!=p:refs[modules[q]].add((p,n.lineno))
    elif p.endswith(('.ts','.tsx','.mjs','.mts')):
        definitions[p]=len(re.findall(r'\b(?:function|class|interface|type)\s+\w+',t));exports[p]=len(re.findall(r'\bexport\s',t))
        for mat in re.finditer(r'''(?:from\s*|import\s*\(\s*|import\s*)["']([^"']+)["']''',t):
            spec=mat.group(1)
            if spec.startswith('.') : base=(ROOT/p).parent/spec
            elif spec.startswith('@/'):base=ROOT/'apps/web/src'/spec[2:]
            else:continue
            base=pathlib.Path(str(base)).resolve()
            variants=[base]+[pathlib.Path(str(base)+s) for s in ['.ts','.tsx','.mjs','.mts','.d.mts']]+[base/('index'+s) for s in ['.ts','.tsx','.mjs']]
            for v in variants:
                try:q=str(v.relative_to(ROOT))
                except ValueError:continue
                if q in texts and q!=p:refs[q].add((p,t.count('\n',0,mat.start())+1));break

def bucket(p):
    if p.startswith('docs/') or p=='README.md':return 'D'
    if p.startswith('infra/alembic/versions/'):return 'M'
    if p.startswith(('tests/','fixtures/')) or '.test.' in p or '.spec.' in p:return 'T'
    if p.startswith(('scripts/','infra/','.github/')) or p.endswith(('.json','.toml','.yaml','.yml','.lock')) or p in ['Makefile','.env.example','.gitignore','.dockerignore']:return 'C'
    return 'I'

def classification(p):
    if p.startswith('.codex/'):
        return ('LOCAL_RUNTIME' if p!='.codex/telegram.env' else 'UNKNOWN','EXTERNAL_OWNED','Host/operator runtime metadata; content deliberately unopened')
    if p.startswith(('tests/','apps/web/e2e/','apps/web/perf/')) or '.test.' in p or p.startswith('fixtures/'):return 'TEST','KEEP','Test/fixture contract'
    if p=='apps/web/next-env.d.ts':return 'GENERATED','KEEP','Framework-generated tracked type entry; preserve tool contract'
    if p in ['apps/web/package-lock.json','requirements.lock','uv.lock']:return 'GENERATED','KEEP','Dependency lock input; do not delete/ignore tracked reproducibility contract'
    if p.startswith(('prompts/','scripts/MemeRadar')) or p=='scripts/run_codex_validation.sh.bak':return 'DOC' if not p.endswith('.bak') else 'UNKNOWN','EXTERNAL_OWNED','Operator prompt/backup; ownership outside product code'
    if p.startswith('data/'):return 'ARTIFACT','KEEP','Wallet seed input consumed by importer/validator; not disposable output'
    if p.startswith('docs/reports/') or p.startswith(('docs/audits/','docs/ui-redesign/','docs/ui-redesign-vnext/')) and p.endswith('.md') or 'CLEANUP_REPORT' in p:return 'REPORT','KEEP','Dated audit/evidence; retained, not current acceptance'
    if p.startswith('docs/history/'):return 'REPORT','KEEP','Preserved prior contract/status evidence'
    if p.endswith(('.md','.html','.new')):return 'DOC','KEEP','Documentation/prototype contract; no unused proof'
    return 'SOURCE','KEEP','Runtime/build/tool contract; no unused proof'
records=[]
for st,p in sorted(remaining,key=lambda x:x[1]):
    cat,action,reason=classification(p)
    counts=collections.Counter();found=set(refs[p]);mod=next((m for m,q in modules.items() if q==p),'')
    needles=[p]
    if mod:needles.append(mod)
    if p.startswith('scripts/'):needles.append(pathlib.Path(p).name)
    for q,t in texts.items():
        if q==p:continue
        for needle in needles:
            pos=t.find(needle)
            if pos>=0:
                found.add((q,t.count('\n',0,pos)+1));break
    for q,line in found:
        counts[bucket(q)]+=1
        if re.search('replay|backfill|historical|forward',q,re.I):counts['R']+=1
        if re.search('serial|schema|models|read_queries|read_api|persistence',q,re.I):counts['S']+=1
    facts=[]
    if cat in ['SOURCE','TEST']:
        facts.append(' '.join(f'{k}{counts[k]}' for k in ['I','T','C','D','M','R','S']))
        if p in definitions:facts.append(f'defs={definitions[p]}, imports/exports={exports[p]}')
        if p.startswith('tests/'):facts.append('pytest testpaths=tests')
        elif '.test.' in p and p.startswith('apps/web/'):facts.append('Vitest default discovery; e2e excluded')
        elif '.spec.' in p and '/e2e/' in p:facts.append('Playwright testDir=e2e; dedicated config exclusions apply')
        elif p.startswith('scripts/') and '.test.' in p:facts.append('node:test standalone test; not pytest')
        if p.startswith('fixtures/'):facts.append('fixture/schema input; not a discovered test module')
        if p.startswith('infra/alembic/versions/'):facts.append('Alembic revision/down_revision graph, not normal import discovery')
        if p.startswith('apps/web/src/app/') and pathlib.Path(p).name in ['page.tsx','route.ts']:facts.append('Next filesystem entry/deep link')
        if p.endswith('/__init__.py'):facts.append('package/export boundary')
        if st.strip()=='D':facts.append('already absent in prior snapshot; preserve inherited deletion')
        if not found:facts.append('no literal/static inbound hit; not proof of unused')
    if found and not p.startswith('.codex/'):
        # Prefer runtime and configuration over generic docs, then concrete test witness.
        witnesses=sorted(found,key=lambda x:({'I':0,'C':1,'T':2,'M':3,'D':4}[bucket(x[0])],x))[:2]
        facts.append('witness '+', '.join(f'`{q}:{line}`' for q,line in witnesses))
    if not facts:facts=[reason]
    records.append({'status':st,'path':p,'class':cat,'action':action,'reason':reason,'evidence':'; '.join(facts),'counts':dict(counts)})
# Independently verify archive bytes, names, counts, per-member size+SHA, and retained copies.
archive=ROOT/manifest['archive']; archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_sha==manifest['archive_sha256']
expected={r['path']:r for r in manifest['rows']}; assert len(expected)==1508
with tarfile.open(archive,'r:gz') as tf:
    members=tf.getmembers(); assert len(members)==1508
    assert len({m.name for m in members})==1508
    assert {m.name for m in members}==set(expected)
    for m in members:
        assert m.isfile() and not m.name.startswith('/') and '..' not in pathlib.PurePosixPath(m.name).parts
        b=tf.extractfile(m).read();r=expected[m.name]
        assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
retention=[]
for p in sorted(retained):
    r=expected[p];b=(ROOT/p).read_bytes()
    assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
    suffix=p.split('visual-evidence/',1)[1]
    direct=[]
    for q,t in texts.items():
        if q==p or '/visual-evidence/runs/' in q or q.endswith('-manifest.json'):continue
        if p in t or suffix in t:direct.append(q)
    retention.append({'path':p,'bytes':len(b),'direct_refs':direct})
counts=collections.Counter(r['class'] for r in records);actions=collections.Counter(r['action'] for r in records)
summary={'baseline_entries':len(prior),'baseline_sha256':hashlib.sha256((ROOT/baseline_path).read_bytes()).hexdigest(),'current_entries':len(now),'current_snapshot_sha256':hashlib.sha256(pathlib.Path('/tmp/memeradar-path-audit-status.z').read_bytes()).hexdigest(),'remaining':len(records),'classes':dict(counts),'actions':dict(actions),'archive_sha256':archive_sha,'archive_bytes':archive.stat().st_size,'retained':retention,'added':sorted(set(p for _,p in now)-set(p for _,p in prior)),'removed':sorted(set(p for _,p in prior)-set(p for _,p in now)),'parse_errors':parse_errors,'corpus_files':len(texts),'corpus_digest':hashlib.sha256('\n'.join(f'{p}\0{hashlib.sha256(t.encode()).hexdigest()}' for p,t in sorted(texts.items())).encode()).hexdigest()}
pathlib.Path('/tmp/memeradar-path-audit-result.json').write_text(json.dumps({'summary':summary,'task':sorted(task),'records':records},indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='retained'},indent=2))
print('retained direct refs',sum(bool(x['direct_refs']) for x in retention),'/16')
print('source/test without inbound:',[r['path'] for r in records if r['class'] in ['SOURCE','TEST'] and not r['counts']])
```

</details>

## Result and limits

The earlier undifferentiated 518-path bucket is now fully enumerated with purpose, action and bounded consumer evidence. Keep 457 repository paths and preserve 61 externally owned paths. No additional source/test/cache deletion or ignore is justified by this evidence. Archive integrity is independently confirmed; the 14 originals without direct literal links are justified as intentional paired historical indexes, not classified as unnecessary under the documented retention policy.

Not checked: credential-file contents, image OCR, external processes, live providers, PostgreSQL/browser acceptance, dynamic external consumers or a new full test run. Historical archive text/trace credentials were checked solely for commit safety as recorded above. Static reference absence and dated reports do not establish unused code, current acceptance or production readiness.
