# Dead-code and archive report — current completion checkpoint

2026-10-18. Current disposition is in [remaining-path audit](memeradar-remaining-path-audit.md); this header supersedes the historical bounded report below. No Git-read-only blocker remains.

- Exact prior inventory:518 paths. SOURCE164, TEST148, DOC29, REPORT112, GENERATED4, ARTIFACT2, LOCAL_RUNTIME57, UNKNOWN2, CACHE0. **516 concrete purpose classes;518 explicit dispositions**:457 KEEP +61 EXTERNAL_OWNED. Two UNKNOWN-type paths are the unopened operator credential file and referenced runner backup, neither a deletion candidate. Five later operator/runtime paths were accounted separately.
- Proven unused/deleted source/tests:0. Generated files removed:0. No deletion quota or inference from missing static imports. Current doc/DI/router/worker/CLI/dynamic/config/test/migration/replay/schema references and uncertain ownership are retained in each path's witnesses.
- Archive verified:1,508 unique safe member paths with exact bytes/SHA;1,492 historical originals archived by prior pass;16 intentional index copies retained. Immutable archive is now committed locally with its manifest, restore guide and sixteen indexes. SHA `b1591a7b1c77f4e7cb12ec611842e45857424cadb312854a0c7c12ea670dc02d`,149,020,122 bytes.
- No unnecessary duplicate was deleted:the16 copies form eight machine/human acceptance-index pairs (338,478 bytes).14 are not direct literal references, but carry pair/run audit context under explicit KEEP policy; removing them would reduce convenience for negligible savings. Unique visual/failed-run evidence remains recoverable. Restore from root using `tar -xzf docs/history/visual-evidence-2026-10-18.tar.gz -C .`.
- Archive text commit-safety scan:1,508tar members +1,761nested files in32ZIPs;1,226UTF-8 entries /250,142,317text bytes;676JSON documents and22,429JSONL/trace records. Existing high-confidence scanner plus structured auth/cookie/credential checks:zero findings, exemptions or scan failures. Binary visual content was not OCR-scanned; do not mistake text safety for visual privacy certification.
- Narrow ignores: web playwright-report, web coverage, visual-evidence/tmp, scripts/nohup.out, and exact operator .codex/logs, .codex/runtime, .codex/telegram.env paths. No source/current report/archive ignore; no local state or credential staged. Existing files were preserved.
- Compatibility328 explicit aliases; internal production/script alias imports migrated; tests and unknown external/dynamic users retained. Complete per-alias conditions/consumer ledger in [deep refactor](memeradar-deep-refactor.md).
- Source ownership:coherent commits project existing HEAD behavior, preserving mixed inherited feature work unstaged. Reviewable dependent backend/UI diffs remain verification artifacts pending explicit integration scope. No blanket stage/clean/reset/stash/remote operation. Current verdict LOCAL_COMPLETION_IN_PROGRESS, not repository completion.

[Final verification/source/commit binding](../../artifacts/verification/memeradar-completion-loop-2026-10-18.json). Current SHA/count/verification are read from this final artifact; older results below are historical only.


<!-- HISTORICAL_DEAD_CODE_REPORT -->

# Historical bounded report — superseded by current checkpoint above

# Dead-code proof and artifact retention

Scope: purpose-aligned deep refactor, 2026-10-18. This is a bounded inventory,
not a declaration that every dirty file belongs to this task. See the
[deep refactor report](memeradar-deep-refactor.md) for owners and verification.

## Proof and disposition

| PATH | TYPE | CONSUMERS | RUNTIME_REFERENCE | RESEARCH_REFERENCE | TEST_REFERENCE | MIGRATION_REFERENCE | REPLAY_REFERENCE | ACTION | RATIONALE | VERIFICATION |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `apps/api/src/memeradar_api/read.py` → `read/` | API relocation | create_app, existing imports | build_read_router / FastAPI | read projections | API/schema tests | none | JSON projection | MOVE / KEEP | 151 definitions now product-owned; import path retained by package | all 50 paths and existing schemas preserved; default page unchanged |
| application `read_api.py`, 9 `read_*` product files | contracts/facade | API, SQL reader, MCP | ReadQueryPort / DI | as-of/timeline/research | read/persistence contracts | existing consumers unchanged | canonical historical projections | KEEP | 114 relocated symbols, not duplicate implementations | legacy class identity and focused reads |
| worker `main.py`, `early_discovery.py`, `wallet_jobs.py`, `intent_jobs.py`, `operations_jobs.py` | composition | run_worker, scripts | registered existing jobs | shadow/research collectors | entrypoint/checkpoint/reorg | none | existing raw normalization/replay | KEEP | 45 aliases preserve callers; no extra worker owner | worker 33 PASS; combined forward 48 PASS |
| worker `forward_evidence.py` / application `pumpfun_forward.py` | transport vs policy | forward collector | SQL/HTTP orchestration vs pure calculations | horizon outcomes | collector/idempotency tests | no schema change | ReplayEventRecord | KEEP / MOVE | 9 pure helpers moved, private worker aliases retained | missing-data branch/name collision fixed; worker 48 PASS |
| provider composition/adapters | transport/provenance | provider bundle and application ports | configured source adapters | doctor/fixtures | provider/protocol contracts | none changed | canonical decoder registry | KEEP | no scoring/promotion authority violation proved | static boundary audit; full verify separately recorded |
| compatibility exports | import contract | API/MCP/CLI/tests/scripts | facade imports | historical projections | existing import tests | retain migration imports | retain decoder/schema names | KEEP | import absence is insufficient deletion proof | identity tests and API schema equivalence |
| all 22 page routes / exported UI components | primary/detail/research/operations | navigation/deep links | server routes | validation workspaces | UI/gateway contracts | none | as-of links | KEEP | no true product duplication or unused exported component proved | static consumer scan; focused UI tests |
| `provider-actions.tsx` (absent) | inherited deletion | prior tree | not recreated | unknown historical | prior tests | none changed | unknown | PRESERVE INHERITED STATE | not a deletion by this task | git status boundary |
| `docs/history/STATUS-*`, `PRODUCTION_READINESS-*` | prior archived evidence | current docs/reports | none | audit history | prior hash proof | historical migration evidence | historical source IDs | KEEP | no old evidence rewritten | contents not edited this pass |
| `visual-evidence/runs` originals | historical/failed/host-blocked acceptance | prior reports and result attachments | no runtime/DI/CLI route | historical visual/regression evidence | no test fixture dependency | none | preserve source/data labels | ARCHIVE 1,492; KEEP 16 cited/index copies | unique evidence preserved, never counted as current acceptance | 1,508 archive members hash-verified before moving originals |
| `scripts/nohup.out` | generated active transcript | runner/operator | not application source | historical session log | source-ID test excludes it | none | not canonical replay | KEEP / IGNORE FUTURE STATUS NOISE | never remove a possibly active log | narrow ignore only |
| remaining inherited source/reports/artifacts | uncertain ownership | not exhaustively classified | uncertain | uncertain | uncertain | uncertain | uncertain | UNKNOWN_RETAINED | no reset, clean, stash, blanket format or deletion | original dirty work preserved |

No source deletion candidate passed the complete proof gate. Specifically, no
candidate was proved free of static/re-export/DI/CLI/FastAPI/worker/dynamic/test/
migration/replay/serialization/current-document consumers. No source or test was
deleted to reduce counts. The old API file's relocation is not a dead-code removal.

## Archive manifest and restoration

[Per-file manifest](../history/visual-evidence-2026-10-18-manifest.json) records
original path, bytes, SHA-256, class and action for all 1,508 files.
[Archive](../history/visual-evidence-2026-10-18.tar.gz):
SHA-256 `b1591a7b1c77f4e7cb12ec611842e45857424cadb312854a0c7c12ea670dc02d`;
149,020,122 bytes. Every member was read back and matched before moving any
original. Sixteen cited files/acceptance indexes remain in place; the new runs
README explains that nested attachment links need restoration. No historical
report/source label was silently promoted or discarded.

Run classification: these are HISTORICAL_ACCEPTANCE evidence, including
FAIL_OR_PARTIAL and BLOCKED_HOST_RUNTIME results, never current acceptance.
No current-source screenshot existed to archive. No duplicates were assumed
from matching filenames. No generated file was discarded without a recoverable
copy. Restore the complete original paths from the repository root:

```bash
tar -xzf docs/history/visual-evidence-2026-10-18.tar.gz -C .
```

## Bounded counts

- Proven unused source files: **0**.
- DELETED source / tests: **0 / 0**.
- ARCHIVED source / tests: **0 / 0**.
- ARCHIVED historical artifact originals: **1,492**; full archive includes **1,508** members.
- KEEP historical cited/index original copies: **16** (plus one new restoration README).
- GENERATED_REMOVED without preservation: **0**.
- UNKNOWN_RETAINED: **518** other dirty status paths outside the 48 task status paths (47 physical files plus the old API relocation path) and 16 retained artifact copies (final snapshot: 582 total); these are preserved, not proved unused. Ownership of inherited hunks remains separate even inside task-touched paths.

The current source manifest has 39 Python/TS files (only task hunks or relocations
owned), five current documentation files, `.gitignore`, archive and retention
manifest: 47 physical files. Unrelated modifications in these same files remain
inherited. The prior full ownership inventory remains in
[memeradar-purpose-refactor.md](memeradar-purpose-refactor.md).

## Future noise controls

Only narrow `.gitignore` additions: `apps/web/playwright-report/`,
`apps/web/coverage/`, `docs/ui-redesign-vnext/visual-evidence/tmp/`,
`scripts/nohup.out`. Current/retained evidence, source, migrations, fixtures,
reports and archives remain visible. No broad docs or visual-run ignore.

Final aggregate verification and final recursive Git counts are recorded in the
[deep refactor report](memeradar-deep-refactor.md) and [STATUS](../STATUS.md).
