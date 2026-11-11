# Inventory

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

The scan found **16 sibling directories**: the 15 named in the request and `.tmp-memeradar-acbcd35`. Their separately measured `du -sk` sum is **16,063,892 KiB (15.32 GiB)**, across 435,618 file entries. Because 20,617 file entries have multiple hardlinks, the sum is not a measured amount of reclaimable disk. There are 472 nested symlink entries; traversal did not follow them. No listed root is a symlink. All directory walks completed without reported errors.

| Sibling | `du` KiB | Files | HEAD | Status entries | Ignored files | Owner:group / mode | Nested symlinks / hardlinked files |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |
| `.tmp-memeradar-acbcd35` | 4 | 0 | `invalid/non-Git` | n/a | not inventoried as Git | ubra:ubra / `0o775` | 0 / 0 |
| `MemeRadar-12423c3-exact-20261024` | 402,268 | 3,282 | `12423c382182` | 0 | 2311 | ubra:ubra / `0o775` | 1 / 0 |
| `MemeRadar-22686de-exact-20261024` | 1,275,284 | 37,253 | `57b65b21b51f` | 0 | 36292 | ubra:ubra / `0o775` | 37 / 0 |
| `MemeRadar-40a96c6-exact-20261024` | 1,222,836 | 34,653 | `b9002ae410cb` | 0 | 33713 | ubra:ubra / `0o775` | 37 / 3541 |
| `MemeRadar-44764fb-exact-20261023` | 1,084,884 | 30,197 | `d36d29160ebd` | 0 | 29267 | ubra:ubra / `0o775` | 34 / 2 |
| `MemeRadar-57b65b2-exact-20261024` | 1,258,368 | 36,782 | `4402fc4ace97` | 0 | 35789 | ubra:ubra / `0o775` | 37 / 0 |
| `MemeRadar-6de1309-exact-20261024` | 1,014,088 | 29,393 | `22686dec59ea` | 0 | 28444 | ubra:ubra / `0o775` | 37 / 3443 |
| `MemeRadar-71ecba4-exact-20261024` | 1,222,612 | 34,633 | `40a96c6f8a2c` | 0 | 33713 | ubra:ubra / `0o775` | 37 / 3541 |
| `MemeRadar-acbcd35-exact-20261023` | 44 | 19 | `invalid/non-Git` | n/a | not inventoried as Git | ubra:ubra / `0o775` | 0 / 0 |
| `MemeRadar-b9002ae-exact-20261024` | 1,221,888 | 34,558 | `6de1309a9917` | 0 | 33614 | ubra:ubra / `0o775` | 37 / 3443 |
| `MemeRadar-d36d291-exact-20261023` | 1,044,984 | 30,199 | `71ecba42d03e` | 0 | 29262 | ubra:ubra / `0o775` | 34 / 2 |
| `MemeRadar-e252d45-exact-20261023` | 950,700 | 28,025 | `44764fbcd62b` | 0 | 27100 | ubra:ubra / `0o775` | 34 / 2 |
| `MemeRadar-e51cf4e-exact-20261024` | 1,222,544 | 34,628 | `e51cf4e3d0f0` | 0 | 33712 | ubra:ubra / `0o775` | 37 / 3541 |
| `MemeRadar-exact-ce1831a-20261023` | 1,044,952 | 30,187 | `e252d4573ab6` | 0 | 29256 | ubra:ubra / `0o775` | 34 / 2 |
| `MemeRadar-final-verify-ca79ecf-20261021` | 1,231,200 | 34,468 | `ce1831abb659` | 0 | 33430 | ubra:ubra / `0o775` | 37 / 3098 |
| `MemeRadar-recovery-20261020T070001Z` | 1,867,236 | 37,341 | `0fe6a3816a7b` | 3 | 29260 | ubra:ubra / `0o775` | 39 / 2 |

The first 13 valid snapshot checkouts are standalone repositories with separate `.git` directories. The recovery root contains one nested valid repository. `MemeRadar-acbcd35-exact-20261023` contains an incomplete Git skeleton; the hidden sibling was empty at scan. See [machine inventory](../../artifacts/audit/MemeRadar-consolidation/inventory-2026-11-06.json) for full real paths, device IDs, UTC mtime/ctime, mode, Git common directories, nested entries and counts. Birth time was not available through the Python filesystem interface. The root filesystem appears as `/dev/nvme0n1p2` ext4 `ro` in this sandbox; no nested mount was found in its mount namespace, which cannot prove host-wide mount absence.

| Other MemeRadar-related parent file | Bytes | Mode | Owner:group | Modified UTC |
| --- | ---: | --- | --- | --- |
| `MemeRadar-before-cleanup.bundle` | 153,486,181 | `0o664` | ubra:ubra | 2026-10-23T19:28:29.488717+00:00 |
| `memeradar-final-ca79ecf-frontend-build.log` | 1,293 | `0o664` | ubra:ubra | 2026-10-21T08:16:27.958634+00:00 |
| `memeradar-final-ca79ecf-make-verify.log` | 71,294 | `0o664` | ubra:ubra | 2026-10-21T08:12:32.053311+00:00 |
| `memeradar-final-npm-ci.log` | 913 | `0o664` | ubra:ubra | 2026-10-21T07:13:08.409005+00:00 |
| `memeradar-final-uv-sync.log` | 1,221 | `0o664` | ubra:ubra | 2026-10-21T07:12:18.282654+00:00 |
| `memeradar-pg-fresh-migrate.log` | 22 | `0o664` | ubra:ubra | 2026-10-21T08:29:05.644158+00:00 |
| `memeradar-pg-integration.log` | 18,583 | `0o664` | ubra:ubra | 2026-10-21T08:29:56.458511+00:00 |
| `memeradar-pg-targeted-2.log` | 8,632 | `0o664` | ubra:ubra | 2026-10-21T08:37:12.988432+00:00 |
| `memeradar-pg-targeted-3.log` | 8,123 | `0o664` | ubra:ubra | 2026-10-21T08:38:08.529789+00:00 |
| `memeradar-pg-targeted-4.log` | 7,931 | `0o664` | ubra:ubra | 2026-10-21T08:42:07.460514+00:00 |
| `memeradar-pg-targeted.log` | 27,635 | `0o664` | ubra:ubra | 2026-10-21T08:34:35.803839+00:00 |
| `memeradar_recover_continue_v3.sh` | 17,208 | `0o775` | ubra:ubra | 2026-10-20T07:05:12.987270+00:00 |
| `memeradar_recover_continue_v4.sh` | 20,266 | `0o775` | ubra:ubra | 2026-10-20T07:07:13.133391+00:00 |
| `memeradar_recover_once.sh` | 20,169 | `0o775` | ubra:ubra | 2026-10-20T07:00:01.825199+00:00 |
| `memeradar_recover_v2.sh` | 18,767 | `0o775` | ubra:ubra | 2026-10-20T07:02:34.389300+00:00 |

`git worktree list --porcelain` lists only the canonical checkout. The canonical stash contains one entry; its contents were not modified. [Git metadata inventory](../../artifacts/audit/MemeRadar-consolidation/git-metadata-2026-11-06.json) contains sanitized remotes, refs and local-upstream counts. No submodule entries or tracked `filter=lfs` attributes were found in the current checked trees; `git-lfs` is unavailable, and historical LFS content was not fully assessed.

Six MemeRadar Compose projects are currently exited, including `memeradar-local`; 23 exited containers and their named PostgreSQL/Redis volumes remain. Two home snapshots are still referenced by exited container Compose labels. No source bind mounts appeared in the 23 container inspections. No matching snapshot CWD was visible in this sandbox's `/proc`; systemd bus access was denied and the user crontab was unavailable or empty, so host-wide process/timer activity is unknown.
