# Verification and regression tests

Evidence is point-in-time on 2026-11-06. The canonical checkout is dirty `main` at `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; the index is empty. No remote Git operation, project/container stop, volume removal, sibling deletion, or automatic commit occurred. Historical October results are not current acceptance.

| Check | Actual result | Evidence / limits |
| --- | --- | --- |
| Canonical `git fsck --full --no-reflogs` | PASS, exit 0, no output | Does not validate application behavior or independently back up working files. |
| Same fsck on valid sibling/nested repos | 14 / 14 exit 0 | Dangling objects are not corruption; their preservation is separately incomplete. [Results](../../artifacts/audit/MemeRadar-consolidation/fsck-2026-11-06.json). |
| `git bundle verify` | Three exit 0 | Original 15 refs; recovery 13 refs; 4402 incremental requires canonical 12423. |
| Temporary bare bundle restore | PASS, exit 0 | Advertised objects restored, Git fsck exit 0; incremental restored with base. [Log](../../artifacts/audit/MemeRadar-consolidation/bundle-restore-2026-11-06.log). |
| Orphan pack rehearsal | PASS, exit 0 | 128 selected objects / 119 previously uncovered objects restored; fsck exit 0. Temporary packs removed; no durable backup. [Result](../../artifacts/audit/MemeRadar-consolidation/orphan-pack-rehearsal-2026-11-06.json). |
| Inventory/comparison JSON | PASS | JSON parsing succeeded; comparisons are point-in-time and cannot establish value/equivalence. |
| Application suites, build, migrations against DB | NOT RUN | No application code changed in this audit; historical results do not validate today's dirty worktree. |
| Repeated/interrupted/concurrent creator tests | NOT RUN | Legacy scripts are read-only and no creator fix was applied; never run their destructive fixed-path cleanup against real data. |
| Cleanup regression | BLOCKED | No target deletion was eligible or permitted, and no prevention implementation was installed. |

The nine-report validator exited 0: 16 sibling entries, 37 relative links,
14 sibling/nested fsck results and all object-coverage counts matched the
recorded evidence. `git diff --check` and `git diff --cached --check` exited
0; the pre-existing tracked diff outside the intentionally updated
`docs/STATUS.md` retained SHA-256
`bc436cf6e22bce9f0492990842373447699f31ebc4b2c6eab97e45e3a8aec287`.
See the [validation record](../../artifacts/audit/MemeRadar-consolidation/report-validation-2026-11-06-final.json).
