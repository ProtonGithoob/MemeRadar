# Phase 11 / Sprint 11.3 Security Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible keyless security review that verifies supply-chain, container, secret, authorization and LLM boundaries and records external scan blockers honestly.

**Architecture:** Keep the review in `scripts/security_review.py` as a provider-independent diagnostic over repository files and allow-listed scanner subprocesses. Existing application auth and narrative boundaries remain authoritative; tests inspect their public behavior and safety contracts. Dockerfiles run as non-root users, while CI invokes the deterministic local review and separately makes external scanner availability visible.

**Tech Stack:** Python 3.12 standard library, pytest, Ruff, mypy, Docker Compose, npm audit, optional pip-audit and Trivy/Grype-compatible container scanner.

**Spec:** `docs/superpowers/specs/2026-09-01-phase-11-sprint-11-3-security-review-design.md`

## Global Constraints

- Preserve `ANALYSIS_ONLY=true`, `PAPER_TRADING=true`, `MANUAL_EXECUTION=false`, `AUTO_EXECUTION=false`.
- Never print or persist credentials, private keys, cookies, raw scanner output or provider payloads.
- Local lock/source checks may pass only on concrete evidence; unavailable external vulnerability databases/tools remain `BLOCKED_EXTERNAL`.
- Existing auth, strict read routes, narrative sanitization and advisory-only LLM output remain the source of truth.
- No provider SDK, signer, wallet, transaction submission or live-money capability may enter the review or application domain.

### Task 1: Write security review contracts first

**Files:**
- Create: `tests/unit/test_security_review.py`
- Create: `tests/contract/test_phase11_sprint11_3.py`
- Inspect: `scripts/security_review.py` (created in Task 2)
- Inspect: `apps/api/src/memeradar_api/auth.py`
- Inspect: `packages/application/src/memeradar_application/narrative.py`

**Interfaces:**
- The tests will consume `run_review(root, external=False)`, `SecurityCheck`,
  and `SecurityReviewReport` from `scripts.security_review`.
- The contract suite will assert the current auth/narrative source boundaries,
  protected modes, non-root image requirements and CI/make wiring.

- [x] Add tests proving exact Python/npm lock metadata and versioned Dockerfiles are accepted, while an unpinned requirement or `latest` image is rejected.
- [x] Add tests proving `run_review(..., external=False)` reports local checks separately, keeps external scans `NOT_RUN`, and includes exact protected modes.
- [x] Add tests proving invalid protected modes fail closed and that source contracts contain constant-time bearer comparison, authorization enforcement, prompt delimiters, strict narrative output checks and no execution authority.
- [x] Run `./.venv/bin/pytest tests/unit/test_security_review.py tests/contract/test_phase11_sprint11_3.py -q`; the initial collection failure was the expected missing review module, followed by a green contract run.

### Task 2: Implement the keyless security review diagnostic

**Files:**
- Create: `scripts/security_review.py`
- Modify: `Makefile`
- Test: `tests/unit/test_security_review.py`

**Interfaces:**
- `SecurityCheck(name: str, status: CheckStatus, detail: str)` stores bounded
  safe evidence without command output.
- `SecurityReviewReport.to_dict()` emits `security-review-v1`, check results,
  external scan state and protected modes.
- `run_review(root: Path, *, external: bool = False, environ: Mapping[str,
  str] | None = None) -> SecurityReviewReport` runs deterministic local checks
  and optional allow-listed scanners.

- [x] Implement exact lockfile checks for `requirements.lock`, `pyproject.toml`, `apps/web/package.json` and `apps/web/package-lock.json`, rejecting URLs, editable/path dependencies, missing root lock entries and non-exact declared versions.
- [x] Implement Dockerfile checks rejecting unversioned/`latest` bases, missing `USER` directives and root users; return only bounded check details.
- [x] Reuse `scripts.secret_scan.scan_files` for tracked-file scanning without printing matches or secret-shaped content.
- [x] Implement source boundary checks for auth, control, narrative and operations files using allow-listed file paths and required/forbidden markers; invalid operating-mode settings produce `FAIL`.
- [x] Implement optional scanner execution for `pip-audit`, `npm audit --audit-level=high` and Trivy configuration scanning; classify missing tools, unavailable network/registry and nonzero scanner findings without exposing output.
- [x] Make `security-review` run the deterministic keyless gate and add `security-review-external` as an explicitly external, expected-blockable command.
- [x] Run the focused tests and make the keyless review green.

### Task 3: Harden image runtime users and CI review wiring

**Files:**
- Modify: `infra/docker/api.Dockerfile`
- Modify: `infra/docker/worker.Dockerfile`
- Modify: `infra/docker/web.Dockerfile`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/contract/test_phase11_sprint11_3.py`

**Interfaces:**
- API/worker images run application commands as a named non-root system user.
- Web image owns its worktree for the non-root `node` user and runs the
  existing command unchanged.
- CI runs `make security-review`; optional external scans remain a separate
  visible step and do not turn unavailable public services into fabricated
  success.

- [x] Add non-root image users and preserve existing commands/ports.
- [x] Add a CI security-review step that installs no unreviewed scripts and invokes repository-owned checks.
- [x] Run Compose config, image builds and the contract suite.

### Task 4: Record the review and threat model

**Files:**
- Create: `docs/THREAT_MODEL.md`
- Create: `docs/RUNBOOKS/SECURITY_REVIEW.md`
- Modify: `docs/SECURITY.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/STATUS.md`

**Interfaces:**
- The threat model names assets, trust boundaries, threats, existing controls,
  residual risk and review date/version.
- The runbook gives exact keyless and external commands, safe blocker
  interpretation and incident escalation without secret logging.

- [x] Document supply-chain, secret, RBAC/session, prompt-injection and container review evidence and residual risks.
- [x] Mark all Phase 11.3 roadmap bullets complete only after verification; leave Gate P11 explicit about external blockers and protected modes.
- [x] Record exact test, lint, typecheck, build, scan and Compose evidence in `docs/STATUS.md`.

### Task 5: Quality gate and checkpoint

**Files:**
- Modify: `docs/superpowers/plans/2026-09-01-phase-11-sprint-11-3-security-review.md`

- [x] Run focused tests, `make security-review`, `make verify`, frontend build and Compose/image checks.
- [x] Run optional external scanner commands; record each unavailable tool/network as `BLOCKED_EXTERNAL` without claiming vulnerability-free status.
- [x] Run a final secret scan and inspect `git diff --check`.
- [x] Commit and push one coherent Phase 11.3 checkpoint.
- [x] Reconcile Gate P11 and continue only to independent roadmap work; Phase 12 remains locked pending explicit operator decision and P9-P11 acceptance.
