# E6.2 External Wallet Intelligence / Cross Validation

> **Execution note:** follow the repository's autonomous execution contract and
> complete this plan in the current checkout. Keep all external-provider work
> keyless and read-only; fixture success is not live-provider success.

## Objective

Add a provider-independent external wallet intelligence seam that can preserve
GMGN/CabalSpy-style labels and token signals as corroborating evidence without
replacing MemeRadar's internal `SmartWalletScore`, holder graph clustering,
deterministic token-security gates, or execution boundaries.

## Scope and invariants

- Normalize immutable wallet labels and token-level signals with source,
  confidence, timestamps, TTL/expiry, raw source identifiers, provenance and
  quality state.
- Expose an application `ExternalWalletIntelligencePort` and a deterministic
  fixture adapter; do not add brittle scraping or claim a live GMGN adapter
  without a documented/legal operator endpoint.
- Reconcile only fresh external evidence with internal scores. Agreement may
  add a bounded confidence bonus; disagreement is
  `CONFLICTED_EXTERNAL_WALLET_LABEL`; stale evidence cannot add positive
  confidence.
- Collapse externally referenced wallets through the existing internal holder
  graph before counting independent actors. External labels never mutate
  internal scores or independently authorize a decision.
- Map tracked-supply, bundle and side-wallet data to bounded token-level
  corroborating features. Security/rug fields remain warnings/evidence only;
  deterministic hard gates remain authoritative.
- Add a key-safe provider doctor. Missing or unsupported live configuration is
  `BLOCKED_EXTERNAL`; no credential or raw response is emitted.
- Preserve all four protected modes and keep every external result's execution
  predicate permanently false.

## Implementation steps

1. Add `external_wallet.py` application contracts, port, fixture-facing result
   model and deterministic reconciliation policy/snapshot.
2. Add `external_wallet.py` provider fixture adapter and redacted replay
   fixtures for agreement, disagreement, stale evidence and token signals.
3. Add focused unit and E6.2 contract tests covering validation, TTL/freshness,
   agreement/disagreement, graph clustering, feature aggregation, security
   corroboration, provider removal, replay determinism and no execution.
4. Add `scripts/external_wallet_doctor.py`, Makefile/env/smoke coverage and
   document the live-acceptance blocker honestly.
5. Run focused tests, lint/typecheck, full `make verify`, migration/runtime
   smoke where applicable, update all roadmap/provider/data/scoring/security
   docs and `docs/STATUS.md`, then commit and push the checkpoint.

## Acceptance evidence

- Identical fixture inputs and config produce byte-equivalent logical
  reconciliation snapshots regardless of delivery order.
- Removing all external labels/signals leaves internal `SmartWalletScore`,
  graph and `RiskAssessment` values unchanged and only removes the external
  feature/bonus.
- Stale, future, malformed and conflicting external evidence is fail-closed;
  no external-only evidence produces a positive internal wallet agreement.
- The doctor reports only presence/absence and safe status metadata, preserves
  the four protected modes, and returns `BLOCKED_EXTERNAL` without documented
  live adapter configuration.
