# Phase 3 Sprint 3.1 Token Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a provider-independent, fail-closed token-security assessment from on-chain authority evidence and an independent RugCheck risk seam.

**Architecture:** Helius already normalizes Solana mint/freeze authority and token-program observations. A new application evaluator will consume only normalized Observation and provider-neutral RiskFinding values, producing the existing versioned RiskAssessment; it will never import Helius, RugCheck, HTTP or SDK code. A new read-only RugCheck adapter will implement RiskDataPort, validate the official summary shape, preserve provenance/freshness, and treat verification as informational. Fixtures, contract tests, and a key-safe doctor will prove the seam without external credentials.

**Tech Stack:** Python 3.12, dataclasses, existing domain/application provider ports, httpx.AsyncClient, ProviderTransport, pytest/pytest-cov, Make, Docker Compose.

**Spec:** docs/ROADMAP.md Sprint 3.1; docs/SCORING_AND_RISK.md; docs/PROVIDERS.md; docs/SECURITY.md; docs/DATA_MODEL.md.

## Global Constraints

- Preserve ANALYSIS_ONLY=true, PAPER_TRADING=true, MANUAL_EXECUTION=false, and AUTO_EXECUTION=false.
- UNKNOWN, STALE, CONFLICTED, and INVALID critical evidence must never produce an execution-eligible PASS.
- Active mint or freeze authority is a deterministic hard block under the Sprint 3.1 default policy.
- RugCheck and verification evidence are advisory/independent inputs; neither can override missing or unsafe on-chain evidence.
- Domain/application code must not import provider SDKs, FastAPI, SQLAlchemy, or frontend code.
- Provider requests use bounded timeout/retry/rate-limit/circuit behavior and must not log or expose credentials or raw secret-bearing payloads.
- All normalized findings and assessments retain timestamps, provenance, evidence references, reason codes, version, and configuration hash.
- No live-money execution, transaction signing, fund transfer, or permission changes are introduced.

---

### Task 1: Provider-independent authority and token-security evaluator

**Files:**
- Create: packages/application/src/memeradar_application/token_security.py
- Create: tests/unit/test_token_security.py
- Modify: packages/application/src/memeradar_application/__init__.py only if a public export is needed

**Interfaces:**
- Consumes: TokenIdentity, Observation, QualityState, Provenance, ReasonCode, RiskAssessment, RiskFinding, and RiskSeverity.
- Produces: TokenSecurityPolicy, TokenSecurityEvaluator.evaluate(candidate_id, token, observations, security_findings=(), now, config_hash) -> RiskAssessment.

- [ ] **Step 1: Write failing tests for the deterministic authority policy.** Cover revoked mint/freeze authorities producing a fresh PASS, either active authority producing BLOCK with the exact hard-block reason, and a missing/unknown authority observation producing UNKNOWN with no execution eligibility.
- [ ] **Step 2: Run the focused tests and confirm they fail because the evaluator is absent.**

~~~bash
.venv/bin/pytest tests/unit/test_token_security.py -q
~~~

- [ ] **Step 3: Add the minimal evaluator.** Parse only the normalized onchain.token_metadata payload; recognize spl-token-2022, preserve supported extension metadata as explainable values, make malformed or conflicting critical evidence fail closed, and calculate bounded confidence/penalties/reason codes deterministically. Treat third-party BLOCK findings as uncorroborated warnings and provider verification as an informational finding.
- [ ] **Step 4: Add freshness, Token-2022 and verification regression tests.** Assert stale evidence is UNKNOWN and ineligible, Token-2022 is retained without an automatic endorsement or bypass, malformed extension metadata is not silently accepted, severe RugCheck findings do not become sole-authority hard blocks, and verification never changes eligibility.
- [ ] **Step 5: Run the unit suite, Ruff and mypy for the touched packages.**

~~~bash
.venv/bin/pytest tests/unit/test_token_security.py -q
make lint typecheck
~~~

- [ ] **Step 6: Commit the evaluator checkpoint.**

~~~bash
git add packages/application/src/memeradar_application/token_security.py tests/unit/test_token_security.py
git commit -m "feat: add fail-closed token security evaluation"
git push origin main
~~~

### Task 2: Independent RugCheck read-only risk seam

**Files:**
- Create: packages/providers/src/memeradar_providers/rugcheck.py
- Create: tests/unit/test_rugcheck.py
- Create: fixtures/providers/rugcheck/summary_safe.json
- Create: fixtures/providers/rugcheck/summary_risks.json
- Create: fixtures/providers/rugcheck/README.md

**Interfaces:**
- Consumes: RiskDataPort, RiskDataRequest, RiskFinding, RiskSeverity, ProviderRequestContext, TokenIdentity, ProviderTransport, and existing classified provider errors.
- Produces: RugCheckRestAdapter.assess(request) -> tuple[RiskFinding, ...], RugCheckRestAdapter.check_health(context), bounded transport behavior, and deterministic report normalization.

- [ ] **Step 1: Write failing adapter/fixture tests.** Assert the official summary path and correlation header, optional bearer header handling without query credentials, mapping of risks[].level to provider-neutral severities, explicit informational verification, source/provenance timestamps, invalid-schema rejection, and timeout/auth classification.
- [ ] **Step 2: Run the focused tests and confirm the missing adapter/fixtures fail.**
- [ ] **Step 3: Implement the adapter with an injected httpx.AsyncClient, clock, and ProviderTransport.** Validate HTTPS base URLs and token addresses, call /v1/tokens/{mint}/report/summary read-only, preserve safe rate-limit metadata, map danger/critical to BLOCK only at the provider-finding layer, map warn to WARN, and retain verification as INFO. Never include raw report bodies or credential values in errors or representations.
- [ ] **Step 4: Add redacted deterministic fixtures and replay tests.** Include one no-risk Token-2022 summary and one summary with warning/danger risks; reject missing/non-list risks and mismatched mint identity where applicable.
- [ ] **Step 5: Run the adapter suite and touched-package quality checks.**

~~~bash
.venv/bin/pytest tests/unit/test_rugcheck.py -q
make lint typecheck
~~~

- [ ] **Step 6: Commit the provider checkpoint.**

~~~bash
git add packages/providers/src/memeradar_providers/rugcheck.py tests/unit/test_rugcheck.py fixtures/providers/rugcheck
git commit -m "feat: add RugCheck risk provider seam"
git push origin main
~~~

### Task 3: Key-safe RugCheck doctor and composition contracts

**Files:**
- Create: scripts/rugcheck_doctor.py
- Create: tests/unit/test_rugcheck_doctor.py
- Create: tests/contract/test_rugcheck_provider.py
- Create: tests/contract/test_phase3_sprint3_1.py
- Modify: Makefile
- Modify: .env.example
- Modify: packages/application/src/memeradar_application/config.py only for non-secret provider settings if required

**Interfaces:**
- Consumes: RUGCHECK_API_URL, optional RUGCHECK_API_KEY, safe operating-mode settings, Helius fixture normalization, the evaluator, and RugCheck adapter.
- Produces: make rugcheck-doctor, redacted PASS/FAIL/BLOCKED_EXTERNAL reports, fixture composition from Helius authority evidence plus RugCheck findings, and assertions that execution remains disabled.

- [ ] **Step 1: Write failing doctor and composition contracts.** Cover missing configuration as BLOCKED_EXTERNAL, successful mocked /ping or report health response without secret echo, auth/timeout/schema classifications, and the full keyless authority-plus-RugCheck assessment.
- [ ] **Step 2: Run the focused contracts and confirm the missing script/composition fails.**
- [ ] **Step 3: Implement the doctor.** Use a single bounded read-only GET /ping check from the official API, require only the URL because the report summary is public while supporting an optional bearer token, report configuration presence only, classify unavailable access as BLOCKED_EXTERNAL, and return a nonzero exit code for blocked/failed checks without claiming provider success.
- [ ] **Step 4: Wire Make and safe environment documentation.** Add RUGCHECK_API_URL= and RUGCHECK_API_KEY= to .env.example, add rugcheck-doctor, and document the no-secret keyless path in fixture metadata.
- [ ] **Step 5: Run focused doctor/contracts and Compose import smoke tests.**

~~~bash
.venv/bin/pytest tests/unit/test_rugcheck_doctor.py tests/contract/test_rugcheck_provider.py tests/contract/test_phase3_sprint3_1.py -q
docker compose -f infra/compose/docker-compose.yml config --quiet
~~~

- [ ] **Step 6: Commit the doctor and composition checkpoint.**

~~~bash
git add scripts/rugcheck_doctor.py tests/unit/test_rugcheck_doctor.py tests/contract/test_rugcheck_provider.py tests/contract/test_phase3_sprint3_1.py Makefile .env.example fixtures/providers/rugcheck/README.md
git commit -m "test: add RugCheck doctor and token security contracts"
git push origin main
~~~

### Task 4: Sprint 3.1 gate, documentation and synchronized handoff

**Files:**
- Modify: docs/PROVIDERS.md
- Modify: docs/SCORING_AND_RISK.md
- Modify: docs/SECURITY.md
- Modify: docs/ROADMAP.md
- Modify: docs/STATUS.md
- Modify: tests/smoke/test_compose_contract.py

- [ ] **Step 1: Add the provider and risk-policy documentation.** Record official RugCheck report/health paths, freshness and provenance rules, advisory verification semantics, on-chain authority precedence, and the exact BLOCKED_EXTERNAL live acceptance conditions.
- [ ] **Step 2: Extend the smoke contract.** Assert the provider module imports in API/worker images and all four safe modes remain unchanged.
- [ ] **Step 3: Run the full Sprint 3.1 quality gate.**

~~~bash
make verify
make doctor
make provider-doctor
make birdeye-doctor
make rugcheck-doctor
.venv/bin/pytest tests/unit/test_token_security.py tests/unit/test_rugcheck.py tests/unit/test_rugcheck_doctor.py tests/contract/test_rugcheck_provider.py tests/contract/test_phase3_sprint3_1.py tests/smoke/test_compose_contract.py -q
~~~

Record exact exit codes and pass/skip counts; a missing RugCheck URL must be recorded as BLOCKED_EXTERNAL, never as PASS.
- [ ] **Step 4: Rebuild bounded local Compose services and run runtime import/health probes.** Do not enable live execution or make external calls without configured credentials.
- [ ] **Step 5: Mark Sprint 3.1 complete only after the keyless gate passes, update docs/STATUS.md with completed work, exact verification evidence, blockers, provider acceptance, safety modes, Git sync state, and the exact Sprint 3.2 next task.
- [ ] **Step 6: Commit and push the final sprint checkpoint.**

~~~bash
git add docs/PROVIDERS.md docs/SCORING_AND_RISK.md docs/SECURITY.md docs/ROADMAP.md docs/STATUS.md tests/smoke/test_compose_contract.py
git commit -m "docs: complete Sprint 3.1 token security checkpoint"
git push origin main
~~~
