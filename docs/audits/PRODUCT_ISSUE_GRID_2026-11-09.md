# Product issue grid — 2026-11-09

Scope: current dirty checkout against the discovery → risk → decision → paper → outcome research purpose and current roadmap. This is an evidence-led inventory, not a claim that every defect has been found. Existing changes are preserved. External acceptance and unimplemented capabilities are distinguished from reproduced bugs.

| Priority | Finding | Evidence / impact | State |
| --- | --- | --- | --- |
| High | Pump.fun launch consumers match generic event names without checking program identity | `forward_evidence.is_pumpfun_launch` and `early_discovery._pumpfun_launch_row` can select another protocol's create/launch event, contaminating research and reevaluation. | Fixed locally; regression failed before the fix and the focused worker suite passed (18 tests). Existing contaminated data has not been reconciled. |
| High | Stream and read-only shadow acceptance incomplete | `docs/STATUS.md` records unresolved gaps and rate-limited RPC; chronological provider recovery and durable progress are not accepted. | External/runtime validation outstanding. |
| High | Paper entry is not operationally wired | `docs/audits/RECURSIVE_ACCEPTANCE_REPORT.md` identifies no worker composition for `ShadowEntryService`; market reference alone cannot certify execution. | Capability gap; requires bounded portfolio and executable quote policy. |
| High | Social collection and caller conduct are not operationally wired | Existing collector/analyzer have no worker production call path. | Capability gap; bounded query, quota, cursor and persistence contracts needed. |
| High | Pre-identity rejections are not durably reconciled | No producer/read path for raw events discarded before identity; missed-winner coverage is incomplete. | Capability gap; event identity, retention and bounds needed. |
| High | Real alpha and executable performance are unproven | No accepted matured, independent real-world cohort; synthetic replay does not prove expectancy. | Evidence/time dependent. |
| Medium | PostgreSQL and restart recovery unaccepted | Isolated test database unavailable per status; integration tests need dedicated URL. | Environment dependent. |
| Medium | Browser, provider, external security and hosted CI acceptance incomplete | Current status records missing or partial checks. | Verification gaps; not proof of failures. |
| Medium | Working tree contains substantial prior changes and unprotected recovery material | Current git status is dirty; status records unbacked dangling objects and external backup requirement. | Preserve data; cleanup blocked on safe durable backup. |

See the implementation plan for ordering and acceptance. Findings from older reports must be revalidated before being treated as current failures.
