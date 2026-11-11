# Directory comparison

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

The [tracked comparison](../../artifacts/audit/MemeRadar-consolidation/tracked-comparison-2026-11-06.json) hashes each snapshot's tracked working files against the **current dirty canonical working tree**, not against a clean commit. “Absent” and “different” counts describe paths/content only; they do not establish that a difference is valuable, obsolete, or safe to merge. Sensitive-looking path names are represented by hashes. Ignored files were counted by category but not fully compared.

Classification: B = unique reachable Git history; D = recovery-critical; E = externally referenced; F = uncertain. Multiple risks can apply; this table gives the primary category. No entry qualified as A for deletion.

| Directory | HEAD | Reachable commits absent from canonical object DB | Dirty/untracked entries | Tracked paths absent in canonical worktree | Tracked paths different | Class | Finding | Action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| `.tmp-memeradar-acbcd35` | `invalid/non-Git` | n/a | n/a | n/a | n/a | F | Empty in scan; host process/mount visibility and removal permission unresolved. | KEEP |
| `MemeRadar-12423c3-exact-20261024` | `12423c382182` | 0 | 0 | 145 | 189 | E | Exited Compose config reference; dangling commit and ignored data. | KEEP |
| `MemeRadar-22686de-exact-20261024` | `57b65b21b51f` | 0 | 0 | 145 | 189 | F | Uncovered dangling commit and ignored data. | KEEP |
| `MemeRadar-40a96c6-exact-20261024` | `b9002ae410cb` | 0 | 0 | 145 | 187 | E | Exited 576 Compose config reference and ignored data. | KEEP |
| `MemeRadar-44764fb-exact-20261023` | `d36d29160ebd` | 0 | 0 | 145 | 187 | F | Tracked differences and ignored data not fully reviewed. | KEEP |
| `MemeRadar-57b65b2-exact-20261024` | `4402fc4ace97` | 3 | 0 | 145 | 188 | B | Three reachable commits absent from canonical objects; incremental bundle verified; dangling 430 variant uncovered. | KEEP |
| `MemeRadar-6de1309-exact-20261024` | `22686dec59ea` | 0 | 0 | 145 | 187 | F | Uncovered dangling commit and ignored/hardlinked data. | KEEP |
| `MemeRadar-71ecba4-exact-20261024` | `40a96c6f8a2c` | 0 | 0 | 145 | 187 | F | Tracked differences and ignored/hardlinked data. | KEEP |
| `MemeRadar-acbcd35-exact-20261023` | `invalid/non-Git` | n/a | n/a | n/a | n/a | F | Incomplete Git skeleton; full provenance unknown. | KEEP |
| `MemeRadar-b9002ae-exact-20261024` | `6de1309a9917` | 0 | 0 | 145 | 187 | F | Uncovered dangling commit and ignored/hardlinked data. | KEEP |
| `MemeRadar-d36d291-exact-20261023` | `71ecba42d03e` | 0 | 0 | 145 | 187 | F | Tracked differences and ignored data. | KEEP |
| `MemeRadar-e252d45-exact-20261023` | `44764fbcd62b` | 0 | 0 | 145 | 183 | F | Tracked differences and ignored data. | KEEP |
| `MemeRadar-e51cf4e-exact-20261024` | `e51cf4e3d0f0` | 0 | 0 | 145 | 187 | F | Tracked differences and ignored/hardlinked data. | KEEP |
| `MemeRadar-exact-ce1831a-20261023` | `e252d4573ab6` | 0 | 0 | 145 | 183 | F | Tracked differences and ignored data. | KEEP |
| `MemeRadar-final-verify-ca79ecf-20261021` | `ce1831abb659` | 0 | 0 | 145 | 183 | F | One dangling blob absent from canonical and existing bundles. | KEEP |
| `MemeRadar-recovery-20261020T070001Z` | `0fe6a3816a7b` | 17 | 3 | 143 | 170 | D | Recovery evidence, 17 absent reachable commits, 117 uncovered dangling blobs and unique untracked files. | KEEP |

Thirteen of the 14 valid snapshot/nested repository HEADs are reachable through canonical local `refs/heads/release/read-only-prod-2026-10-24`; the exception is `4402fc4`, whose three additional reachable commits are in the verified incremental bundle. The recovery repository has 17 commits absent from canonical object storage through other refs; its full bundle advertises those ref tips. [Reachability evidence](../../artifacts/audit/MemeRadar-consolidation/reachability-2026-11-06.json).

The `4402fc4` checkout has **145 tracked paths absent** and **188 different** in dirty `main`. The absent paths include migrations `0013` through `0022`; the canonical local `12423c3` release branch contains `0022`. The three `12423c3..4402fc4` commits touch the persistence control adapter, ORM order index and its test. Corresponding first-write/index semantics are present in the dirty canonical worktree, but no complete lineage merge or clean-source acceptance is claimed. Applying all missing paths to dirty `main` would be a schema/product-lineage change and was not attempted.

A distinct dangling commit `43082632cbc6189ca03ac42af47a3195c5b81485`, present in six snapshots, changes `apps/worker/src/memeradar_worker/forward_evidence.py` and `tests/unit/test_pumpfun_forward_evidence.py`. It has the same parent and subject as reachable `b9002ae`, but their stable patch IDs differ and their trees differ in those two files. The variant is absent from canonical objects and existing bundles. It was not blindly ported into the dirty main lineage; it needs preservation and semantic review.
