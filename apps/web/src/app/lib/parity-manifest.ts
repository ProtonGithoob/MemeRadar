export type ParityManifestEntry = {
  apiFields: readonly string[];
  frontendFields: readonly string[];
  omissions: readonly { field: string; reason: string }[];
};

export const PARITY_MANIFEST: Record<string, ParityManifestEntry> = {
  "/": {
    apiFields: ["candidates", "early_radar", "positions", "operations"],
    frontendFields: ["state", "score", "risk", "freshness", "protected_modes", "execution_boundary"],
    omissions: [{ field: "raw_payload", reason: "operator UI uses normalized evidence only" }]
  },
  "/radar": {
    apiFields: ["candidate", "score", "risk", "quality", "reason_codes", "evidence_refs"],
    frontendFields: ["identity", "state", "score", "risk", "freshness", "reasons", "cross_navigation"],
    omissions: [{ field: "raw_provider_payload", reason: "retained for audit/replay, not rendered" }]
  },
  "/ultra-early": {
    apiFields: ["early_state", "early_score", "velocity", "liquidity", "risk", "latency", "asymmetric_alpha"],
    frontendFields: ["state", "score", "velocity", "liquidity", "risk", "latency", "execution_lock"],
    omissions: [{ field: "raw_provider_payload", reason: "bounded normalized projection only" }]
  },
  "/opportunities": {
    apiFields: ["chain", "activity_windows", "acceleration", "launchpad", "provenance", "quality", "confidence", "reason_codes"],
    frontendFields: ["chain", "5m", "1h", "24h", "acceleration", "launchpad", "provenance", "quality", "reasons"],
    omissions: [
      { field: "narrative/pre_token_attention", reason: "not present in ChainOpportunityResponse" },
      { field: "reference_price_integrity", reason: "not present in ChainOpportunityResponse" },
      { field: "risk/security", reason: "not present in ChainOpportunityResponse" }
    ]
  },
  "/positions": {
    apiFields: ["position", "mark", "performance", "exit_risk", "closed_trade", "evidence_refs"],
    frontendFields: ["identity", "mode", "state", "mark", "pnl", "mfe_mae", "exit_risk", "evidence"],
    omissions: [{ field: "live_submission", reason: "execution is protected and read model exposes no submission authority" }]
  },
  "/wallets": {
    apiFields: ["chain", "address", "tiers", "score", "confidence", "samples", "outcomes", "freshness", "reasons"],
    frontendFields: ["chain", "address", "tiers", "score", "confidence", "samples", "outcomes", "freshness"],
    omissions: [{ field: "external_label_authority", reason: "labels remain corroborating evidence" }]
  },
  "/wallets/[address]": {
    apiFields: ["chain", "address", "outcomes", "freshness", "reasons", "evidence_refs"],
    frontendFields: ["chain", "identity", "outcomes", "freshness", "reasons", "evidence_refs"],
    omissions: [{ field: "execution_authority", reason: "wallet evidence cannot authorize execution" }]
  },
  "/wallet-graph": {
    apiFields: ["nodes", "edges", "filters", "quality"],
    frontendFields: ["nodes", "edges", "filters", "quality", "empty", "error"],
    omissions: [{ field: "unsupported graph metrics", reason: "not emitted by the bounded graph read model" }]
  },
  "/callers": {
    apiFields: ["platform", "chain", "evidence_class", "samples", "confidence", "executable_mfe", "early_entry_quality", "kol_bundle", "provenance"],
    frontendFields: ["platform", "chain", "filters", "sorts", "samples", "confidence", "kol_bundle", "provenance"],
    omissions: [{ field: "failure_rate", reason: "no normalized failure-rate field exists; failure count remains displayed" }]
  },
  "/tokens/[tokenId]": {
    apiFields: ["chain", "mint", "pools", "candidate", "launch_lifecycle", "timeline", "quality", "provenance"],
    frontendFields: ["chain", "identity", "pools", "candidate", "launch_lifecycle", "timeline", "quality", "provenance"],
    omissions: [{ field: "provider raw payload", reason: "normalized timeline payload is the operator boundary" }]
  },
  "/providers": {
    apiFields: ["configuration", "health", "latency", "freshness", "quota", "failures", "errors"],
    frontendFields: ["configuration", "credential_state", "mode", "health", "latency", "freshness", "quota", "failures", "doctor"],
    omissions: [
      { field: "external_stream_continuity", reason: "not currently persisted in ProviderHealthResponse" },
      { field: "robinhood_sequencer_rpc_launchpad_state", reason: "not currently present in the read model" },
      { field: "reference_price_integrity", reason: "not currently present in the read model" }
    ]
  },
  "/operations": {
    apiFields: ["overall_state", "slo", "providers", "alerts", "metrics", "early_detection", "modes"],
    frontendFields: ["state", "slo", "providers", "alerts", "counters", "stream_reconnects", "gaps_detected", "backfill_retries", "verification_failures", "early_detection", "modes"],
    omissions: [{ field: "unbounded metrics", reason: "only bounded known counters are rendered" }]
  },
  "/audit": {
    apiFields: ["actor", "action", "target", "occurred_at", "correlation_id", "before", "after"],
    frontendFields: ["actor", "action", "target", "time", "correlation", "safe_before_after"],
    omissions: [{ field: "secret content", reason: "audit contract stores state transitions, never secret values" }]
  },
  "/settings": {
    apiFields: ["key", "category", "type", "effective", "pending", "mutable", "secret", "protected", "mode", "bounds", "configured_state"],
    frontendFields: ["tabs", "typed_controls", "current", "pending", "secret_status", "badges", "reason", "version_conflict", "dirty_state"],
    omissions: [{ field: "secret value", reason: "write-only; browser receives configured state only" }]
  },
  "/readiness": {
    apiFields: ["PR-1..PR-7", "evidence_counts", "blockers", "hosted_ci", "protected_modes", "live_money"],
    frontendFields: ["gate_status", "evidence_counts", "blockers", "next_action", "hosted_ci", "protected_modes", "live_money"],
    omissions: [{ field: "live-money enablement", reason: "explicitly out of scope and backend protected" }]
  }
};
