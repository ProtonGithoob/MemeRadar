# Root cause analysis

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

## Confirmed recovery creator

`/home/ubra/codex/memeradar_recover_once.sh:22-31` computes a UTC-second timestamp, creates `MemeRadar-recovery-$STAMP` in the project parent, and prepares `repo`, `verify`, safety and log paths. Lines 190 and 425 use `git clone --no-hardlinks` to create separate recovery and verification repositories. `logs/recovery.log` identifies the observed `MemeRadar-recovery-20261020T070001Z` and records the reconstruction phase. Each later run with a different timestamp can create another root. The `fail()` path explicitly retains the workspace, and no `trap` cleanup or `flock` was found in these four scripts; retention on interruption is possible and useful recovery evidence remains.

`memeradar_recover_v2.sh:21-24,510-512`, `memeradar_recover_continue_v3.sh:7-10,380-382`, and `memeradar_recover_continue_v4.sh:7-10,499-501` use separate fixed `verify-v2`, `verify-v3`, and `verify-v4` clone paths. Before cloning they run unconditional `rm -rf` of their fixed verification path, without a dirty-worktree or active-process check. The scripts have no identified shared lock or exit cleanup. Their same-path concurrent execution is a **risk**, not an observed race. V4 also creates an ordinary `mktemp -d` at line 263 and removes it on normal branches at 278/283; interruption between those statements can leave it behind. The scripts contain prohibited remote-Git commands for this task and were inspected only.

## SHA-named verification clones

The actual creator of `MemeRadar-<SHA>-exact-*`, `MemeRadar-exact-<SHA>-*`, and `MemeRadar-final-verify-*` was **not identified**. The four recovery scripts and checked-in repository scripts contain no matching creator. Recovery logs show validation commands running from these paths, which establishes use, not creation. The inspected Codex session matches were later inventory outputs, not creator commands; the available shell history did not identify one. Chained local Git origins and dates are consistent with repeated verification clones, but do not prove who created them.

System and user systemd bus inspection was blocked by the sandbox; cron could not be distinguished from unavailable or empty; sandbox `/proc` is not a host-wide process audit. The scripts and their parent directory are read-only here, so the confirmed unsafe lifecycle was **not fixed** and rerun/interruption/concurrency behavior was not tested. Existing `AGENTS.md` guidance is a policy, not enforced prevention.
