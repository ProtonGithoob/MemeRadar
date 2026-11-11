# Preservation and backup

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

| Artifact | Verification | SHA-256 / constraint |
| --- | --- | --- |
| `/home/ubra/codex/MemeRadar-before-cleanup.bundle` | `git bundle verify` exit 0; 15 advertised refs; complete bundle. Local temporary bare restore verified every advertised object and `git fsck` exited 0. | `756c536f5083e0f851f225a72131fd7932bd45ccc0b02e1ae56d6d1790042cfe`; 153,486,181 bytes. |
| `recovery-20261020-refs.bundle` | Verify exit 0; 13 advertised refs; independently unbundled into temporary bare repo and checked. | `302de970b357ddbdfd0bc7b52e87882ef9200372a3c255442b52d28b027977ab`. |
| `candidate-4402fc4-preservation.bundle` | Verify exit 0; restored `4402fc4` into temporary bare repo using canonical object database as the `12423c3` prerequisite. | `812fabc717bce2537f16b5339bd2dfffdd4aae38a5c03b06c0c8e29ef79db397`; incremental, not standalone. |

The two preservation bundles are in `artifacts/audit/MemeRadar-consolidation/`; the first bundle remains in the parent. All advertised source ref tips absent from canonical objects were present in the appropriate bundle. These bundles do **not** cover every working or unreachable object.

`git fsck --full --no-reflogs` found 121 distinct dangling objects absent from canonical Git. Restore comparison shows 2 commits available from the original/recovery bundles; **119 are missing from the combined bundles and canonical object database: one commit (`43082632...`) and 118 blobs**. No contents were printed. Their byte sizes total about 1.69 MB for the blobs. The [object manifest](../../artifacts/audit/MemeRadar-consolidation/dangling-objects-2026-11-06.json) and [coverage check](../../artifacts/audit/MemeRadar-consolidation/dangling-bundle-coverage-2026-11-06.json) contain hashes, not data.

A temporary pack rehearsal selected 128 objects: the 10-object orphan-commit closure plus 118 blobs. Three local Git packs were indexed, restored alongside the verified bundles and canonical prerequisite, and `git fsck` exited 0 with all 119 previously missing objects present. The temporary packs/repository were removed after the successful test. The [selection manifest](../../artifacts/audit/MemeRadar-consolidation/orphan-pack-selection-2026-11-06.json), [rehearsal result](../../artifacts/audit/MemeRadar-consolidation/orphan-pack-rehearsal-2026-11-06.json), and restricted test scripts are reproducibility evidence, **not a durable backup**. A host-writable external backup destination is still required before deletion.

Recovery `repo` has three untracked files: `prompts/MemeRadar.md.new`, `scripts/run_codex_validation.sh.bak`, and `scripts/tailfnohup.sh`. The first two differ from canonical comparisons and no identical same-path copy was found among top-level sibling checkouts; the third matches canonical. None is contained merely by a Git bundle. All remain in place, and file contents were not copied or disclosed. Ignored artifacts and the recovery root's safety/log directories also remain unreviewed for complete uniqueness.

`/home/ubra/backups` is absent and not writable here; `/home/ubra/codex`, canonical `.git`, and `.codex` are sandbox read-only. No external durable backup or canonical Git ref import was possible.

## Subsequent recovery step — 2026-11-06

Restricted, Git-ignored project-local copies now preserve the three object packs and the two distinct untracked files (plus the matching third file). A standalone bare-repository restore loaded project-local copies of the original, recovery, candidate and newly created prerequisite bundles, checked all 119 previously uncovered objects, and passed `git fsck --full --no-reflogs` with no Git alternates. Bundle and pack SHA-256 values are recorded in `artifacts/audit/MemeRadar-consolidation/restricted-object-backup-4y2ezys3/SHA256-MANIFEST.json`; working-file hashes and original permissions are recorded in `artifacts/audit/MemeRadar-consolidation/restricted-working-file-backup-20261106/manifest.json`. These copies share the canonical filesystem and are **not an independently stored backup**. Ignored data and host activity remain insufficiently audited, so no snapshot is eligible for deletion.
