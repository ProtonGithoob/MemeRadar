# External Alpha Intelligence — Current-Code Gap Matrix

**Audit baseline:** `b9c46b3fb3c881ca04c76ed9e25872ecc86e5c15`

**Audit date:** 2026-09-14

This matrix records the repository state after synchronizing `origin/main` and
before production-code changes for the approved Option A package.

| requirement | EXISTING | PARTIAL | MISSING | NOT_NEEDED | target files | reason |
|---|---:|---:|---:|---:|---|---|
| Current repository sync and baseline record | yes |  |  |  | `.git`, `docs/STATUS.md` | `main` is fast-forwarded to `origin/main` at the audit baseline. |
| Provider-neutral HTTP transport, typed failures, retry/rate-limit handling | yes |  |  |  | `packages/providers/src/memeradar_providers/transport.py` | Existing transport is the required seam for a direct adapter. |
| Canonical provider request/response ports | yes |  |  |  | `packages/application/src/memeradar_application/provider_contracts.py` | Discovery, market, on-chain observation, risk and provenance contracts already exist. |
| Canonical candidate/observation persistence and redaction | yes |  |  |  | `packages/application/src/memeradar_application/discovery_collection.py`, `packages/domain/src`, `packages/persistence/src` | Existing collector persists provider time, provenance, quality and evidence origin. |
| GMGN upstream read contract and license verification | yes |  |  |  | external audit recorded in `docs/EXTERNAL_ALPHA_INTELLIGENCE_AUDIT_2026-09-14.md` | Current upstream source and docs provide a direct read HTTP contract; root license is MIT. |
| GMGN optional disabled-by-default configuration |  |  | yes |  | `packages/application/src/memeradar_application/config.py`, `.env.example` | No GMGN settings exist; protected mode parsing is reusable. |
| GMGN provider metadata/readiness classification |  | yes |  |  | `packages/application/src/memeradar_application/provider_metadata.py`, `apps/api/src/memeradar_api/read.py` | Registry and provider-health projection exist, but no GMGN entry or runtime override exists. |
| GMGN read-only candidate discovery and normalized evidence |  |  | yes |  | `packages/providers/src/memeradar_providers/gmgn.py` | No GMGN adapter or direct server-side caller exists. |
| GMGN LIVE_SHADOW worker wiring and collection health |  | yes |  |  | `apps/worker/src/memeradar_worker/main.py` | Generic collector and a MadeOnSol shadow loop exist; GMGN-specific wiring is absent. |
| GMGN real-sample accounting |  | yes |  |  | `packages/application/src/memeradar_application/historical_dataset.py`, `packages/persistence/src/memeradar_persistence/read_queries.py` | Explicit real-origin accounting exists, but the report/query is MadeOnSol-specific. |
| Helius factual activity taxonomy |  |  | yes |  | `packages/providers/src/memeradar_providers/helius_stream.py` | Existing normalizer preserves raw facts but has no bounded `activity_kind`. |
| Helius stream reliability, replay identity, provenance and malformed handling | yes |  |  |  | `packages/providers/src/memeradar_providers/helius_stream.py` | Taxonomy can be added without changing the existing stream stack or observation ID. |
| Canonical launch lifecycle and verified-route policy |  | yes |  |  | `packages/application/src/memeradar_application/launch_lifecycle.py` | BONDING/GRADUATING and first-event separation exist; explicit DEX_LIVE/weak-provider regressions are incomplete. |
| Numi lifecycle regression coverage |  |  | yes |  | `tests/unit/test_launch_lifecycle.py` | Required boundary cases are not all tested. |
| Event-time historical replay, ablation, calibration and leakage guards | yes |  |  |  | `packages/application/src/memeradar_application/replay_harness.py`, `calibration.py`, `historical_dataset.py` | Existing research infrastructure already supports later baseline-vs-augmentation analysis. |
| Production scoring weights and protected execution modes | yes |  |  |  | `packages/application/src/memeradar_application/config.py`, scoring/risk modules | Existing defaults are fail-closed; no weight or mode change is authorized. |
| Solbeam runtime integration |  |  |  | yes | none | User scope is documentation/UI reference only. |
| Duplicate scorer/risk/lifecycle/wallet/alert/reliability subsystems |  |  |  | yes | none | Current architecture already has canonical components; reuse them. |
| GMGN execution, wallet custody, private-key or subprocess integration |  |  |  | yes | none | Explicitly forbidden by the approved scope and security policy. |
