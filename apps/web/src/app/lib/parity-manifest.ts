export type ParityOmissionStatus =
  | "BACKEND_NOT_EXPOSED"
  | "RAW_EVIDENCE_ONLY"
  | "INTENTIONALLY_OMITTED"
  | "SECRET"
  | "EXECUTION_OUT_OF_SCOPE"
  | "UNSUPPORTED";

export type ParityManifestEntry = {
  backendRoutes: readonly string[];
  owner: string;
  apiFields: readonly string[];
  frontendFields: readonly string[];
  telegramFields?: readonly string[];
  omissions: readonly { field: string; reason: string; status: ParityOmissionStatus }[];
};

export const PARITY_MANIFEST: Record<string, ParityManifestEntry> = {
  "/": {
    backendRoutes: ["/candidates", "/early-radar", "/operations/overview"],
    owner: "CommandCenter",
    apiFields: ["candidates", "early_radar", "positions", "operations"],
    frontendFields: ["state", "score", "risk", "freshness", "protected_modes", "execution_boundary"],
    omissions: [
      { field: "raw_payload", reason: "operator UI uses normalized evidence only", status: "RAW_EVIDENCE_ONLY" },
      { field: "positions", reason: "paper positions have a dedicated read surface", status: "INTENTIONALLY_OMITTED" }
    ]
  },
  "/radar": {
    backendRoutes: ["/candidates", "/early-radar"],
    owner: "RadarExplorer / RadarTable",
    apiFields: ["candidate", "score", "risk", "quality", "reason_codes", "evidence_refs"],
    frontendFields: ["identity", "state", "score", "risk", "freshness", "reasons", "cross_navigation"],
    omissions: [
      { field: "launch_lifecycle", reason: "CandidateView is token-agnostic; authoritative lifecycle is exposed by /tokens/[tokenId]", status: "INTENTIONALLY_OMITTED" },
      { field: "raw_provider_payload", reason: "retained for audit/replay, not rendered", status: "RAW_EVIDENCE_ONLY" },
      { field: "execution_eligible", reason: "candidate read models explicitly reject execution authority at the web boundary", status: "EXECUTION_OUT_OF_SCOPE" }
    ]
  },
  "/ultra-early": {
    backendRoutes: ["/early-radar"],
    owner: "UltraEarlyWorkspace",
    apiFields: ["early_state", "early_score", "velocity", "liquidity", "risk", "latency", "asymmetric_alpha"],
    frontendFields: ["state", "score", "velocity", "liquidity", "risk", "latency", "execution_lock"],
    omissions: [
      { field: "launch_lifecycle", reason: "EarlyRadarView has no authoritative per-token lifecycle projection; use /tokens/[tokenId]", status: "INTENTIONALLY_OMITTED" },
      { field: "raw_provider_payload", reason: "bounded normalized projection only", status: "RAW_EVIDENCE_ONLY" },
      { field: "execution_eligible", reason: "early-radar execution authority is intentionally locked at the backend boundary", status: "EXECUTION_OUT_OF_SCOPE" }
    ]
  },
  "/opportunities": {
    backendRoutes: ["/chain-opportunities"],
    owner: "ChainOpportunitiesDashboard",
    apiFields: ["chain", "activity_windows", "acceleration", "launchpad", "provenance", "quality", "confidence", "reason_codes"],
    frontendFields: ["chain", "5m", "1h", "24h", "acceleration", "launchpad", "provenance", "quality", "reasons"],
    omissions: [
      { field: "narrative/pre_token_attention", reason: "not present in ChainOpportunityResponse", status: "BACKEND_NOT_EXPOSED" },
      { field: "reference_price_integrity", reason: "not present in ChainOpportunityResponse", status: "BACKEND_NOT_EXPOSED" },
      { field: "risk/security", reason: "not present in ChainOpportunityResponse", status: "BACKEND_NOT_EXPOSED" },
      { field: "per_token_launch_lifecycle", reason: "aggregate opportunity response has no bounded token lifecycle projection; use /tokens/[tokenId]", status: "INTENTIONALLY_OMITTED" }
    ]
  },
  "/positions": {
    backendRoutes: ["/positions"],
    owner: "PositionsDashboard",
    apiFields: ["position", "mark", "performance", "exit_risk", "closed_trade", "evidence_refs"],
    frontendFields: ["identity", "mode", "state", "mark", "pnl", "mfe_mae", "exit_risk", "evidence"],
    omissions: [{ field: "live_submission", reason: "execution is protected and read model exposes no submission authority", status: "EXECUTION_OUT_OF_SCOPE" }]
  },
  "/wallets": {
    backendRoutes: ["/wallets"],
    owner: "WalletsDashboard",
    apiFields: ["chain", "address", "tiers", "score", "confidence", "samples", "outcomes", "freshness", "reasons"],
    frontendFields: ["chain", "address", "tiers", "score", "confidence", "samples", "outcomes", "freshness"],
    omissions: [{ field: "external_label_authority", reason: "labels remain corroborating evidence", status: "INTENTIONALLY_OMITTED" }]
  },
  "/wallets/[address]": {
    backendRoutes: ["/wallets/{address}"],
    owner: "WalletDetailView",
    apiFields: ["chain", "address", "outcomes", "freshness", "reasons", "evidence_refs"],
    frontendFields: ["chain", "identity", "outcomes", "freshness", "reasons", "evidence_refs"],
    omissions: [
      { field: "relationship_evidence", reason: "wallet detail remains outcome-focused; candidate-only edges are exposed by /wallet-graph", status: "INTENTIONALLY_OMITTED" },
      { field: "execution_authority", reason: "wallet evidence cannot authorize execution", status: "EXECUTION_OUT_OF_SCOPE" }
    ]
  },
  "/wallet-graph": {
    backendRoutes: ["/wallet-graph/wallets/{address}", "/wallet-graph/tokens/{mint}", "/wallet-graph/clusters/{cluster_id}"],
    owner: "WalletGraphExplorer",
    apiFields: ["nodes", "edges", "relationship_evidence", "relationship_evidence.relationship_type", "relationship_evidence.dimensions", "relationship_evidence.confidence", "relationship_evidence.quality_state", "relationship_evidence.event_count", "relationship_evidence.funding_time_delta_seconds", "relationship_evidence.candidate_only", "relationship_evidence.ownership_asserted", "relationship_evidence.reason_codes", "relationship_evidence.evidence_refs", "relationship_evidence.provenance", "filters", "quality"],
    frontendFields: ["nodes", "edges", "relationship_evidence", "relationship_type", "dimensions", "confidence", "quality", "event_count", "funding_time_delta_seconds", "candidate_only", "ownership_asserted", "reason_codes", "evidence_refs", "provenance", "filters", "empty", "error"],
    omissions: [{ field: "unsupported graph metrics", reason: "not emitted by the bounded graph read model", status: "UNSUPPORTED" }]
  },
  "/callers": {
    backendRoutes: ["/caller-profiles", "/social-calls", "/caller-convergence"],
    owner: "CallersDashboard",
    apiFields: ["platform", "chain", "evidence_class", "samples", "confidence", "executable_mfe", "early_entry_quality", "kol_bundle", "provenance"],
    frontendFields: ["platform", "chain", "filters", "sorts", "samples", "confidence", "kol_bundle", "provenance"],
    omissions: [
      { field: "failure_rate", reason: "no normalized failure-rate field exists; failure count remains displayed", status: "BACKEND_NOT_EXPOSED" },
      { field: "execution_eligible", reason: "caller evidence cannot authorize execution", status: "EXECUTION_OUT_OF_SCOPE" }
    ]
  },
  "/tokens/[tokenId]": {
    backendRoutes: ["/tokens/{tokenId}", "/tokens/{tokenId}/timeline"],
    owner: "TokenDetailView",
    apiFields: ["chain", "mint", "pools", "candidate", "launch_lifecycle.lifecycle_state", "launch_lifecycle.route_state", "launch_lifecycle.route_available", "launch_lifecycle.launchpad", "launch_lifecycle.creator_address", "launch_lifecycle.bonding_curve_progress_bps", "launch_lifecycle.quote_asset", "launch_lifecycle.graduation_threshold_bps", "launch_lifecycle.graduated_at", "launch_lifecycle.first_verified_dex_liquidity_at", "launch_lifecycle.first_verified_swap_at", "launch_lifecycle.liquidity_lock_state", "launch_lifecycle.pool_address", "launch_lifecycle.venue", "launch_lifecycle.as_of", "launch_lifecycle.expires_at", "launch_lifecycle.quality_state", "launch_lifecycle.time_quality", "launch_lifecycle.confidence", "launch_lifecycle.reason_codes", "launch_lifecycle.evidence_refs", "launch_lifecycle.provenance", "launch_lifecycle.config_hash", "launch_lifecycle.version", "insider_evidence.suspicion_state", "insider_evidence.suspicious_holder_count", "insider_evidence.suspicious_supply_pct", "insider_evidence.confidence", "insider_evidence.reason_codes", "insider_evidence.evidence_refs", "insider_evidence.provenance", "insider_evidence.excluded_address_count", "insider_evidence.excluded_address_categories", "insider_evidence.quality_state", "timeline.alert.early_alpha.payload.early_alpha_state", "timeline.alert.early_alpha.payload.early_alpha_snapshot", "timeline.alert.early_alpha.payload.early_alpha_transition", "timeline.alert.early_alpha.payload.risk_gates", "timeline.alert.early_alpha.payload.changes", "timeline.alert.early_alpha.payload.early_alpha_correlation_id", "timeline", "quality", "provenance"],
    frontendFields: ["chain", "identity", "pools", "candidate", "launchLifecycle.lifecycleState", "launchLifecycle.routeState", "launchLifecycle.routeAvailable", "launchLifecycle.launchpad", "launchLifecycle.creatorAddress", "launchLifecycle.bondingCurveProgressBps", "launchLifecycle.quoteAsset", "launchLifecycle.graduatedAt", "launchLifecycle.firstVerifiedDexLiquidityAt", "launchLifecycle.firstVerifiedSwapAt", "launchLifecycle.liquidityLockState", "launchLifecycle.poolAddress", "launchLifecycle.venue", "launchLifecycle.asOf", "launchLifecycle.expiresAt", "launchLifecycle.qualityState", "launchLifecycle.timeQuality", "launchLifecycle.confidence", "launchLifecycle.reasonCodes", "launchLifecycle.evidenceRefs", "launchLifecycle.provenance", "launchLifecycle.configHash", "launchLifecycle.version", "insiderEvidence.suspicionState", "insiderEvidence.suspiciousHolderCount", "insiderEvidence.suspiciousSupplyPct", "insiderEvidence.confidence", "insiderEvidence.reasonCodes", "insiderEvidence.provenance", "insiderEvidence.excludedAddressCount", "insiderEvidence.excludedAddressCategories", "insiderEvidence.qualityState", "earlyAlpha.state", "earlyAlpha.riskGates", "earlyAlpha.beforeNow", "earlyAlpha.transition", "earlyAlpha.correlation", "timeline", "quality", "provenance"],
    omissions: [
      { field: "provider raw payload", reason: "normalized timeline payload is the operator boundary", status: "RAW_EVIDENCE_ONLY" },
      { field: "raw_payload_hash", reason: "audit correlation is retained server-side and is not needed for the bounded evidence view", status: "RAW_EVIDENCE_ONLY" }
    ]
  },
  "/providers": {
    backendRoutes: ["/providers/health", "/config/runtime-settings"],
    owner: "ProvidersDashboard",
    apiFields: ["provider_id", "display_name", "chains", "capabilities", "enabled", "setting_keys", "configuration", "credential_state", "endpoint_state", "capability_status", "health", "latency", "freshness", "quota", "failures", "errors"],
    frontendFields: ["provider_id", "display_name", "chains", "capabilities", "capability_status", "enabled", "setting_keys", "configuration", "credential_state", "endpoint_state", "mode", "health", "latency", "freshness", "quota", "failures", "doctor"],
    omissions: [
      { field: "external_stream_continuity", reason: "not currently persisted in ProviderHealthResponse", status: "BACKEND_NOT_EXPOSED" },
      { field: "robinhood_sequencer_rpc_launchpad_state", reason: "no persisted sequencer/RPC operational counters in ProviderHealthResponse; reconciliation state remains in the read-service seam", status: "BACKEND_NOT_EXPOSED" },
      { field: "reference_price_integrity", reason: "not currently present in the read model", status: "BACKEND_NOT_EXPOSED" }
    ]
  },
  "/operations": {
    backendRoutes: ["/operations/overview"],
    owner: "OperationsDashboard",
    apiFields: ["overall_state", "slo", "providers", "alerts", "metrics", "early_detection", "modes"],
    frontendFields: ["state", "slo", "providers", "alerts", "counters", "stream_reconnects", "gaps_detected", "backfill_retries", "verification_failures", "early_detection", "modes"],
    omissions: [{ field: "unbounded metrics", reason: "only bounded known counters are rendered", status: "UNSUPPORTED" }]
  },
  "/audit": {
    backendRoutes: ["/audit/events", "/config/versions"],
    owner: "AuditDashboard",
    apiFields: ["actor", "action", "target", "occurred_at", "correlation_id", "before", "after"],
    frontendFields: ["actor", "action", "target", "time", "correlation", "safe_before_after"],
    omissions: [{ field: "secret content", reason: "audit contract stores state transitions, never secret values", status: "SECRET" }]
  },
  "/settings": {
    backendRoutes: ["/state", "/config", "/runtime-settings"],
    owner: "SettingsDashboard",
    apiFields: ["key", "category", "type", "effective", "pending", "mutable", "secret", "protected", "mode", "bounds", "configured_state", "madeonsol_enabled", "madeonsol_base_url", "madeonsol_api_key_configured_state"],
    frontendFields: ["tabs", "typed_controls", "current", "pending", "secret_status", "madeonsol_enabled", "madeonsol_base_url", "madeonsol_api_key_configured_state", "badges", "reason", "version_conflict", "dirty_state"],
    omissions: [{ field: "secret value", reason: "write-only; browser receives configured state only", status: "SECRET" }]
  },
  "/readiness": {
    backendRoutes: ["/readiness"],
    owner: "ReadinessDashboard",
    apiFields: ["PR-1..PR-7", "evidence_counts", "blockers", "hosted_ci", "protected_modes", "live_money", "alpha_validation.status", "alpha_validation.real_observation_count", "alpha_validation.unique_robinhood_token_count", "alpha_validation.caller_kol_observation_count", "alpha_validation.smart_wallet_observation_count", "alpha_validation.deployer_observation_count", "alpha_validation.holder_distribution_observation_count", "alpha_validation.bundle_lp_security_observation_count", "alpha_validation.labeled_winner_count", "alpha_validation.labeled_rug_count", "alpha_validation.first_real_observation", "alpha_validation.latest_real_observation", "alpha_validation.rate_limit_count", "alpha_validation.error_count"],
    frontendFields: ["gate_status", "evidence_counts", "blockers", "next_action", "hosted_ci", "protected_modes", "live_money", "alpha_validation.status", "alpha_validation.real_observation_count", "alpha_validation.unique_robinhood_token_count", "alpha_validation.caller_kol_observation_count", "alpha_validation.smart_wallet_observation_count", "alpha_validation.deployer_observation_count", "alpha_validation.holder_distribution_observation_count", "alpha_validation.bundle_lp_security_observation_count", "alpha_validation.labeled_winner_count", "alpha_validation.labeled_rug_count", "alpha_validation.first_real_observation", "alpha_validation.latest_real_observation", "alpha_validation.rate_limit_count", "alpha_validation.error_count"],
    omissions: [{ field: "live-money enablement", reason: "explicitly out of scope and backend protected", status: "EXECUTION_OUT_OF_SCOPE" }]
  },
  "Telegram/EarlyAlpha": {
    backendRoutes: ["/tokens/{tokenId}/timeline"],
    owner: "EarlyAlphaAlertRenderer / AlertDeliveryService",
    apiFields: ["token identity", "chain", "early state", "AlphaScore", "confidence", "risk disposition", "risk quality", "smart-wallet evidence", "holder evidence", "launch lifecycle", "graduation", "volume acceleration", "liquidity", "sellability", "hard blocks", "reason codes", "evidence freshness", "event-time quality", "cohort similarity"],
    frontendFields: ["token identity", "chain", "early state", "AlphaScore", "confidence", "risk disposition", "risk quality", "evidence freshness", "reason codes"],
    telegramFields: ["token identity", "chain", "state", "AlphaScore", "confidence", "risk disposition", "risk quality", "evidence before now", "cohort similarity", "reason codes", "correlation"],
    omissions: [
      { field: "raw provider payload", reason: "bounded normalized evidence only", status: "RAW_EVIDENCE_ONLY" },
      { field: "public web URL", reason: "deployment routing is not configured; no URL is fabricated", status: "UNSUPPORTED" },
      { field: "fields unavailable in the persisted early-alpha projection", reason: "rendered as UNKNOWN or omitted until canonical read-model support exists", status: "BACKEND_NOT_EXPOSED" }
    ]
  }
};
