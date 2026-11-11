# MemeRadar Production Readiness

Updated: 2026-11-11. This checkpoint is bound to the actual dirty local
checkout; it is not a clean release candidate.

## Current classification

- Branch / HEAD: `main` / `c0fbd2217b7e09e9afd93efc1f9ccb54a40e80f5`; dirty worktree preserved. No remote was queried.
- P30 source fingerprint: `97e36f90571212c774b8827a2672a4f1a3137f5c39cdfaf3c12f4a1f2cbfe6e8` (641 files, 8,385,898 bytes); the manifest recheck found zero mismatches or missing files.
- Final local `make verify`: exit 0; backend 1,650 passed / 34 integration deselected / 7 warnings; frontend 86 passed; Ruff, mypy (187 files), CSS, frontend lint/typecheck, Compose, local secret/security review, migration graph and SBOM passed. Exact log, digest and commands are in the verification ledger.
- P30 migration graph head is `0015_stream_verification_provenance` with 27 ORM tables. The graph check passed; the database migration was not executed against PostgreSQL on this source.
- Stream recovery evidence now retains provider, scoped program, commitment, method and recovery attempt. Overall source/subscription coverage remains `UNKNOWN`; these fields make local recovery evidence traceable but do not prove capture completeness.
- PostgreSQL integration, current-source worker recreation, portfolio-concurrency tests and full worker restart remain blocked: `MEMERADAR_TEST_DATABASE_URL` is unset, PostgreSQL binaries are absent, and Docker API access is denied. Earlier PostgreSQL runs are historical, not P30 acceptance.
- Browser E2E could not start because sandbox binding to `127.0.0.1:13000` returned `EPERM`. The production bundle compiled, but Next.js TypeScript config discovery failed because child-process output was unavailable; standalone typecheck passed in `make verify`. No current-source browser/build pass is claimed.
- External container, npm and pip audits were not run. Historical Trivy scans reported 47 HIGH OS findings each for API/worker; they were not rescanned on P30.
- Full-stack runtime, live providers, real Telegram receipt, verified historical inventory, complete launch denominator and independent real alpha remain unaccepted.

| Dimension | Current evidence | Acceptance |
| --- | --- | --- |
| Engineering verification | P30 declared local `make verify` scope passed on the dirty worktree. | PARTIAL; PostgreSQL, browser/build, hosted CI and runtime restart are not accepted. |
| Stream provenance | Local verification rows retain provider/scope/commitment/method/attempt and operations reads project the evidence. | PASS for bounded provenance fields; overall source coverage remains UNKNOWN. |
| Read-only shadow | Social/caller and pre-identity paths are composed; paper entry/exit is opt-in and requires explicit policy plus a matching pre-provisioned PAPER/SOL portfolio. | PARTIAL / NOT OPERATIONALLY ACCEPTED |
| Alpha validation | No independent, mature real chronological cohort or validated copyability evidence. | NOT_PROVEN |
| Live-money execution | No signer or transaction submission; protected modes remain locked. | OUT OF SCOPE |

A deterministic test pass, installed provider configuration or market-price
increase does not establish provider health, executable paper fills or alpha.

## Safety

`ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`,
`AUTO_EXECUTION=false`, `CANARY=false`, `LIVE=false`. No signer, transaction
submission or live-money implementation was introduced. Missing evidence and
costs remain unknown; future observations do not rewrite T0 decisions.

## Acceptance needed

1. Run migration `0015_stream_verification_provenance` and the current-source PostgreSQL integration, recovery-claim, paper-worker and restart suites against an isolated test database.
2. Run current-source browser E2E and production build in an environment where the local web server and TypeScript child-process output work.
3. Re-run external Python, npm and container scans against deployment inputs; resolve or assess the historical API/worker OS findings.
4. Perform bounded, authorized read-only provider recovery and establish only the completeness guarantees the provider contract supports.
5. Run historical launch reconciliation against a verified read-only production history source.
6. Verify delivery with an authorized Telegram test bot/chat; keep ambiguous outcomes durable and do not blindly retry.
7. Collect independently matured real outcomes and evaluate a frozen chronological holdout before any alpha claim.

## Historical acceptance labels

The archived `Task 15 acceptance snapshot` used the classifications
`NOT_PRODUCTION_READY`, `PRODUCTION_READY_READ_ONLY`,
`PRODUCTION_READY_PAPER_AUTO`, and `LIVE_MONEY_CANDIDATE`. These labels are
retained only to interpret that historical report; none is accepted for the
current source. Current read-only, alpha and live-money statuses are listed
separately above.

Historical source identities and runtime results are preserved in
[`history/PRODUCTION_READINESS-2026-10-18-before-purpose-refactor.md`](history/PRODUCTION_READINESS-2026-10-18-before-purpose-refactor.md).
They do not establish current-source acceptance.
