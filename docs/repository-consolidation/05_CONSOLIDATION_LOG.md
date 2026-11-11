# Consolidation log

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

- Existing canonical local branch `release/read-only-prod-2026-10-24` points to `12423c3821828613b8f5dea0ed7a6dace1e24c10`; `git cat-file -e` confirmed its `0022_cross_chain_evidence` migration exists. Thirteen snapshot/nested HEADs are reachable from that local ref.
- The three `12423c3..4402fc4` commits are preserved in the verified incremental bundle, and the dirty canonical source already contains the previously reviewed order-claim index and runtime-settings first-write seams. Their full integration on a clean current-lineage branch is **not** verified. No ref was imported or commit created in this run.
- The distinct dangling `43082632...` forward-collector variant was compared with reachable `b9002ae`: both have parent `40a96c6`, but patch IDs differ (`e5e76e8f...` versus `aacff4cc...`) and the two affected source/test files differ. Its object is not covered by current durable bundles. It remains in the six source repositories pending external preservation and semantic review.
- The recovery repository's two differing untracked files were compared by SHA-256 without printing their contents. They remain at source. No snapshot file, ignored data, secret, or migration was copied over canonical work.
- The 145 absent / 188 different tracked paths in the `4402fc4` snapshot include ten migrations and many application/test files. This is a genuine 0012-versus-0022 lineage conflict, not a safe bulk-copy operation. Preserve the current dirty main and the local release branch until an explicitly reviewed integration can be tested.

Application code was not changed in this cleanup audit.
