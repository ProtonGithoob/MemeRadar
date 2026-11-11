# Final executive report

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

**FINAL STATUS: PARTIALLY COMPLETED / BLOCKED.** The inventory, Git checks and restore rehearsals are complete. No target directory was deleted. The host permissions and preservation/ownership gates prevent safe consolidation and cleanup.

| Metric | Before | After | Result |
| --- | --- | --- | --- |
| Canonical project directories | 1 observed | 1 | PASS |
| Duplicate project directories | 15 requested plus 1 hidden | 16 remain | FAIL: zero target not reached |
| Unique Git history | 3 reachable commits in one snapshot and 17 through recovery refs absent from canonical object DB; 119 further dangling objects uncovered | Ref tips backed by verified bundles; 119 objects only rehearsed, originals retained | PARTIAL / BLOCKED |
| Valuable uncommitted changes | Canonical dirty; recovery has three untracked entries | Retained in place; no destructive edits | PARTIAL |
| Valuable untracked files | Two recovery files differ from same-path copies | Retained in source only; external backup unavailable | BLOCKED |
| Git integrity | Unknown at start of this run | Canonical and 14 valid sibling/nested fsck exits 0 | PASS with dangling-object caveat |
| Root causes | Recovery creators and exact-clone creator unverified | Recovery creators established; exact-clone creator unknown; scripts unmodified | PARTIAL / FAIL |
| Recovery capability | Three existing bundles | Advertised refs restore in isolated bare repo; 119 uncovered objects restored only in pack rehearsal | PARTIAL |
| Regression tests | Prior historical application evidence | Git/bundle/pack tests passed; creator/cleanup/app suites not run | PARTIAL |
| Duplicate creation on rerun | 16 directories present | Not tested; one-shot creator makes a timestamped root by construction | FAIL / UNKNOWN |
| Reclaimable disk space | Separate `du` sum 16,063,892 KiB; root 96% full / 9.1 GiB available | 0 bytes reclaimed; root 97% full / 8.7 GiB available at final scan | ACTUAL: 0; filesystem change not attributed |
| Remaining risks | Unknown | Listed in [remaining risks](08_REMAINING_RISKS.md) | DOCUMENTED |

## Directory-by-directory disposition

| Original directory | Unique or unresolved content | Preservation method | Final disposition | Evidence |
| --- | --- | --- | --- | --- |
| `.tmp-memeradar-acbcd35` | Empty in scan; host process/mount visibility and removal permission unresolved. | retained in place; no independent recovery claim | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-12423c3-exact-20261024` | Exited Compose config reference; dangling commit and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-22686de-exact-20261024` | Uncovered dangling commit and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-40a96c6-exact-20261024` | Exited 576 Compose config reference and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-44764fb-exact-20261023` | Tracked differences and ignored data not fully reviewed. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-57b65b2-exact-20261024` | Three reachable commits absent from canonical objects; incremental bundle verified; dangling 430 variant uncovered. | 4402 incremental bundle restored with canonical 12423 base; 430 remains uncovered | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-6de1309-exact-20261024` | Uncovered dangling commit and ignored/hardlinked data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-71ecba4-exact-20261024` | Tracked differences and ignored/hardlinked data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-acbcd35-exact-20261023` | Incomplete Git skeleton; full provenance unknown. | retained in place; no independent recovery claim | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-b9002ae-exact-20261024` | Uncovered dangling commit and ignored/hardlinked data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-d36d291-exact-20261023` | Tracked differences and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-e252d45-exact-20261023` | Tracked differences and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-e51cf4e-exact-20261024` | Tracked differences and ignored/hardlinked data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-exact-ce1831a-20261023` | Tracked differences and ignored data. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-final-verify-ca79ecf-20261021` | One dangling blob absent from canonical and existing bundles. | HEAD reachable via canonical local release ref; ignored/dangling data remains in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |
| `MemeRadar-recovery-20261020T070001Z` | Recovery evidence, 17 absent reachable commits, 117 uncovered dangling blobs and unique untracked files. | recovery bundle restored for refs; uncovered blobs and distinct untracked files remain in place | RETAINED | [inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) |

The detailed [inventory](01_INVENTORY.md), [root causes](02_ROOT_CAUSE_ANALYSIS.md), [comparison](03_DIRECTORY_COMPARISON.md), [backup evidence](04_PRESERVATION_AND_BACKUP.md), [consolidation](05_CONSOLIDATION_LOG.md), [cleanup](06_CLEANUP_EXECUTION.md), and [verification](07_REGRESSION_TESTS.md) describe the remaining gates.

## Subsequent recovery step — 2026-11-06

Restricted, Git-ignored project-local copies now preserve the three object packs and the two distinct untracked files (plus the matching third file). A standalone bare-repository restore loaded project-local copies of the original, recovery, candidate and newly created prerequisite bundles, checked all 119 previously uncovered objects, and passed `git fsck --full --no-reflogs` with no Git alternates. Bundle and pack SHA-256 values are recorded in `artifacts/audit/MemeRadar-consolidation/restricted-object-backup-4y2ezys3/SHA256-MANIFEST.json`; working-file hashes and original permissions are recorded in `artifacts/audit/MemeRadar-consolidation/restricted-working-file-backup-20261106/manifest.json`. These copies share the canonical filesystem and are **not an independently stored backup**. Ignored data and host activity remain insufficiently audited, so no snapshot is eligible for deletion.
