# RugCheck fixtures

These are deterministic, redacted report-summary envelopes for the official
read-only RugCheck API. They contain no credentials or session material.

- Summary route: `GET /v1/tokens/{id}/report/summary`
- Health route: `GET /ping`
- Fixture schema: `rugcheck-summary-v1`
- Adapter parser: `rugcheck-summary-v1`

`summary_safe.json` deliberately retains a Token-2022 program and a
verification value. Verification is normalized as informational evidence only;
it is never an endorsement or a risk-gate override.
