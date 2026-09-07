# Security Review Runbook

This runbook is for the analysis-only/paper-trading deployment. Do not print
credentials, cookies, provider payloads, private keys, scanner output that may
contain environment data, or database connection strings.

## Routine review

Run the repository-owned deterministic review from the repository root:

```text
make security-review
make sbom
```

Expected keyless result: exit `0`, JSON schema `security-review-v1`, local
checks `PASS`, exact protected modes, and `external_acceptance:
BLOCKED_EXTERNAL` because external vulnerability scans are not run by the
keyless gate.

Run the complete local quality gate and frontend build:

```text
make verify
make frontend-build
docker compose -f infra/compose/docker-compose.yml build api worker web
```

The security review checks exact Python/npm declarations against their lock
files, versioned Docker base images, non-root runtime users, tracked-file
secrets, bearer/RBAC and narrative boundaries, and protected modes.

## Optional external scans

```text
make security-review-external
```

The command attempts `pip-audit`, `npm audit --audit-level=high --omit=dev`
and a Trivy configuration scan with fixed arguments. Interpret results as:

- exit `0`: all local and requested external checks passed;
- exit `1`: a local check or external scanner reported a finding/failure;
- exit `2`: external access/tooling is unavailable and is
  `BLOCKED_EXTERNAL`.

Never change dependencies with `--force` or suppress a scanner finding. Record
the package/image, advisory, affected range, remediation and verification in a
review commit. The 2026-09-01 review upgraded `@playwright/test` from 1.51.1
to 1.62.1 after npm reported a high-severity Playwright advisory; the next
advisory scan reported zero vulnerabilities. Local pip-audit and Trivy were
unavailable, so their acceptance remains blocked.

`make sbom` builds `security-sbom-v1`, a deterministic CycloneDX document from
`requirements.lock`, `apps/web/package-lock.json` and the versioned Docker
base images. Use `make sbom SBOM_OUTPUT=/secure/operator/path/memeradar.json`
when an artifact is needed. The default check prints only a component count
and digest, and never includes credentials, raw provider data or scanner
output.

Release candidates also run `make release-identity`, which binds the full Git
SHA, migration head/table count, app/API versions, configuration hash and SBOM
digest into a keyless JSON artifact. The release identity contains no provider
or Telegram credentials.

## Credential or authorization incident

1. Keep the execution kill switch active and preserve all four protected modes.
2. Revoke/rotate the affected secret through the deployment secret manager;
   do not paste it into an issue, shell history, test, or log.
3. Preserve redacted audit and review evidence.
4. Run `make secret-scan`, `make security-review`, `make verify` and the
   relevant provider doctor after remediation.
5. Review bearer role assignments and immutable control audit records.
6. Document the incident, affected boundary, rotation evidence and residual
   risk without recording secret values.

## Prompt-injection or narrative incident

Treat all post/metadata text as hostile data. Disable optional narrative calls
if the provider returns malformed or suspicious output; deterministic risk and
score paths remain authoritative. Verify strict schema/config/evidence checks,
bounded prompt sanitization and `execution_eligible() == false`. Do not add
tools, config mutation, wallet access or execution permissions to a narrative
provider.

## Container finding

Stop promotion of the affected image, record the image digest and scanner
advisory, rebuild from the reviewed lockfiles/base image, and rerun the image
build plus the keyless/full gates. Do not solve a finding by disabling the
scanner or running the image as root.
