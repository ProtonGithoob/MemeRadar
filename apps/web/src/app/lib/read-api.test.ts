import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCandidates,
  fetchChainOpportunities,
  fetchAuditEvents,
  fetchConfigVersions,
  fetchControlConfig,
  fetchControlState,
  fetchRuntimeSettings,
  fetchOperations,
  fetchProviderHealth,
  fetchPositions,
  fetchPosition,
  fetchReadiness,
  fetchTimeline,
  fetchToken,
  fetchWallet,
  fetchWallets,
  fetchWalletGraph,
  fetchClusterGraph,
  parseRadarFilters,
  type CandidateRecord,
  type ReadPage
} from "./read-api";

const VIEWER_TOKEN = "viewer-server-secret";
const CANDIDATE_ID = "11111111-1111-4111-8111-111111111111";
const TOKEN_ID = "22222222-2222-4222-8222-222222222222";
const PORTFOLIO_ID = "33333333-3333-4333-8333-333333333333";
const POSITION_ID = "44444444-4444-4444-8444-444444444444";

const candidatePayload: CandidateRecord = {
  id: CANDIDATE_ID,
  tokenId: TOKEN_ID,
  chain: "solana",
  mintAddress: "So11111111111111111111111111111111111111112",
  symbol: "MOON",
  name: "Moon Fixture",
  state: "WATCH",
  discoveredAt: "2026-08-31T12:00:00.000Z",
  discoverySource: "fixture.discovery",
  stateChangedAt: "2026-08-31T12:01:00.000Z",
  score: 84,
  scoreConfidence: 0.9,
  riskDisposition: "PASS",
  riskQualityState: "FRESH",
  riskReasonCodes: ["AUTHORITY_CLEAR"],
  evidenceRefs: ["market:1"]
};

const pagePayload: ReadPage<CandidateRecord> = {
  items: [candidatePayload],
  limit: 50,
  hasMore: false,
  nextCursor: null
};

function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("server-side read gateway", () => {
  it("accepts only bounded Radar filter values", () => {
    expect(
      parseRadarFilters({
        state: "WATCH",
        risk_disposition: "WARN",
        min_score: "70",
        ignored: "do-not-forward"
      })
    ).toEqual({ state: "WATCH", riskDisposition: "WARN", minScore: 70 });
    expect(parseRadarFilters({ state: ["WATCH", "BLOCK"], min_score: "101" })).toEqual({});
    expect(parseRadarFilters({ state: "NOT_A_STATE", risk_disposition: "PASS" })).toEqual({
      riskDisposition: "PASS"
    });
  });

  it("builds a bounded candidate request and keeps the viewer token server-side", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubEnv("MEMERADAR_VIEWER_API_TOKEN", VIEWER_TOKEN);
    const fetchMock = vi.fn().mockResolvedValue(response({
      items: [
        {
          id: CANDIDATE_ID,
          token_id: TOKEN_ID,
          mint_address: candidatePayload.mintAddress,
          symbol: candidatePayload.symbol,
          name: candidatePayload.name,
          state: candidatePayload.state,
          discovered_at: candidatePayload.discoveredAt,
          discovery_source: candidatePayload.discoverySource,
          state_changed_at: candidatePayload.stateChangedAt,
          score: "84.5",
          score_confidence: "0.9",
          risk_disposition: "PASS",
          risk_quality_state: "FRESH",
          risk_reason_codes: ["AUTHORITY_CLEAR"],
          evidence_refs: ["market:1"]
        }
      ],
      limit: 50,
      has_more: false,
      next_cursor: null
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchCandidates({ state: "WATCH", riskDisposition: "WARN", minScore: 70 });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [requestUrl, requestOptions] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(requestUrl).toBe(
      "http://api.internal:8000/v1/candidates?limit=50&state=WATCH&min_score=70&risk_disposition=WARN"
    );
    expect(requestOptions.headers).toEqual({ Authorization: `Bearer ${VIEWER_TOKEN}` });
    expect(requestOptions.cache).toBe("no-store");
    expect(JSON.stringify(result)).not.toContain(VIEWER_TOKEN);
    if (result.ok) expect(result.data.items[0]?.score).toBe(84.5);
  });

  it("fails explicitly when the server read base is not configured", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchCandidates({});

    expect(result).toEqual({ ok: false, reason: "NOT_CONFIGURED" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps authorization, transport and malformed responses without response-body leakage", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    fetchMock.mockResolvedValueOnce(response({ detail: "Bearer provider-secret" }, 401));
    expect(await fetchCandidates({})).toEqual({ ok: false, reason: "UNAUTHORIZED", status: 401 });

    fetchMock.mockRejectedValueOnce(new Error("database-password should not escape"));
    expect(await fetchCandidates({})).toEqual({ ok: false, reason: "UNAVAILABLE" });

    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => { throw new Error("bad json"); } });
    const malformed = await fetchCandidates({});
    expect(malformed).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
    expect(JSON.stringify(malformed)).not.toContain("database-password");
  });

  it("keeps graph query ordering and cluster outcome omission", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn().mockResolvedValue(response({ nodes: [], edges: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const filters = {
      maxDepth: 3,
      maxNodes: 20,
      maxEdges: 40,
      outcomeFilter: "WINNER / RUG",
      dateFrom: "2026-01-01",
      dateTo: "2026-01-02",
      venue: "raydium/amm",
      walletRole: "creator",
      riskOutcomeClass: "LOW_RISK",
      evidenceQuality: "FRESH"
    };

    expect((await fetchWalletGraph("So11111111111111111111111111111111111111112", filters)).ok).toBe(true);
    expect((await fetchClusterGraph("cluster/one", filters)).ok).toBe(true);
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://api.internal:8000/v1/wallet-graph/wallets/So11111111111111111111111111111111111111112?limit=50&max_depth=3&max_nodes=20&max_edges=40&outcome_filter=WINNER+%2F+RUG&date_from=2026-01-01&date_to=2026-01-02&venue=raydium%2Famm&wallet_role=creator&risk_outcome_class=LOW_RISK&evidence_quality=FRESH",
      "http://api.internal:8000/v1/wallet-graph/clusters/cluster%2Fone?limit=50&max_depth=3&max_nodes=20&max_edges=40&date_from=2026-01-01&date_to=2026-01-02&venue=raydium%2Famm&wallet_role=creator&risk_outcome_class=LOW_RISK&evidence_quality=FRESH"
    ]);
  });

  it("fetches operations observability as a bounded read-only projection", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn().mockResolvedValue(response({
      schema_version: "operations-overview-v1",
      as_of: "2026-09-01T06:00:00.000Z",
      overall_state: "UNKNOWN",
      slo_state: "UNVERIFIED",
      policy_version: "provider-slo-v1",
      measurement_method: "synthetic_local",
      providers: [],
      alerts: [],
      metrics: { counters: { queue_saturations: 0 } },
      modes: {
        analysis_only: true,
        paper_trading: true,
        manual_execution: false,
        auto_execution: false
      },
      execution_eligible: false
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchOperations();

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.internal:8000/v1/operations/overview",
      expect.objectContaining({ cache: "no-store" })
    );
    if (result.ok) {
      expect(result.data.overallState).toBe("UNKNOWN");
      expect(result.data.sloState).toBe("UNVERIFIED");
      expect(result.data.executionEligible).toBe(false);
    }
  });

  it("parses grouped runtime settings without allowing secret values into the web projection", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn().mockResolvedValue(response({
      api_version: "runtime-settings-v1",
      as_of: "2026-09-07T12:00:00.000Z",
      groups: {
        providers: [{ key: "helius_api_key", value: null, state: "CONFIGURED", secret: true }],
        chains: [{ key: "enabled_chains", value: "solana,bnb,robinhood", state: "CONFIGURED", secret: false }],
        telegram: [],
        x: [{ key: "enabled", value: false, state: "DEFAULTED", secret: false }],
        social: [],
        website: [],
        wallet: [],
        security: [],
        llm: []
      },
      protected_modes: {
        analysis_only: true,
        paper_trading: true,
        manual_execution: false,
        auto_execution: false
      },
      execution_eligible: false
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchRuntimeSettings();

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.internal:8000/v1/control/runtime-settings",
      expect.objectContaining({ cache: "no-store" })
    );
    if (result.ok) {
      expect(result.data.groups.providers[0]?.value).toBeNull();
      expect(result.data.groups.chains[0]?.value).toBe("solana,bnb,robinhood");
    }
  });

  it("keeps canonical alpha validation zeros and unknown timestamps intact", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      as_of: "2026-09-12T12:00:00.000Z",
      classification: "NOT_PRODUCTION_READY",
      gates: [{
        id: "alpha",
        name: "Alpha evidence",
        status: "INSUFFICIENT_SAMPLES",
        evidence_counts: { real: 0 },
        blockers: ["REAL_PROVIDER_ACCESS_UNAVAILABLE"],
        next_action: "Collect real evidence"
      }],
      hosted_ci: {},
      provider_runtime_blockers: ["MADEONSOL_CREDENTIALS_UNAVAILABLE"],
      protected_modes: {
        analysis_only: true,
        paper_trading: true,
        manual_execution: false,
        auto_execution: false
      },
      live_money: { execution_eligible: false },
      alpha_validation: {
        status: "INSUFFICIENT_SAMPLES",
        reason_codes: ["MADEONSOL_REAL_OBSERVATIONS_REQUIRED"],
        real_observation_count: 0,
        unique_robinhood_token_count: 0,
        caller_kol_observation_count: 0,
        smart_wallet_observation_count: 0,
        deployer_observation_count: 0,
        holder_distribution_observation_count: 0,
        bundle_lp_security_observation_count: 0,
        first_real_observation: null,
        latest_real_observation: null,
        rate_limit_count: 0,
        error_count: 0,
        labeled_winner_count: 0,
        labeled_rug_count: 0
      }
    })));

    const result = await fetchReadiness();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.alphaValidation.realObservationCount).toBe(0);
      expect(result.data.alphaValidation.uniqueRobinhoodTokenCount).toBe(0);
      expect(result.data.alphaValidation.firstRealObservation).toBeNull();
      expect(result.data.alphaValidation.status).toBe("INSUFFICIENT_SAMPLES");
    }
  });

  it("preserves unavailable alpha counters as null instead of measured zero", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      as_of: "2026-09-12T12:00:00.000Z",
      classification: "NOT_PRODUCTION_READY",
      gates: [],
      hosted_ci: {},
      provider_runtime_blockers: [],
      protected_modes: {
        analysis_only: true,
        paper_trading: true,
        manual_execution: false,
        auto_execution: false
      },
      live_money: { execution_eligible: false },
      alpha_validation: {
        status: "INSUFFICIENT_SAMPLES",
        reason_codes: ["MADEONSOL_LABELED_OUTCOMES_UNAVAILABLE"],
        real_observation_count: 0,
        unique_robinhood_token_count: 0,
        caller_kol_observation_count: 0,
        smart_wallet_observation_count: 0,
        deployer_observation_count: 0,
        holder_distribution_observation_count: 0,
        bundle_lp_security_observation_count: 0,
        first_real_observation: null,
        latest_real_observation: null,
        rate_limit_count: null,
        error_count: null,
        labeled_winner_count: null,
        labeled_rug_count: null
      }
    })));

    const result = await fetchReadiness();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.alphaValidation.rateLimitCount).toBeNull();
      expect(result.data.alphaValidation.errorCount).toBeNull();
      expect(result.data.alphaValidation.labeledWinnerCount).toBeNull();
      expect(result.data.alphaValidation.labeledRugCount).toBeNull();
    }
  });

  it("parses backend insider evidence without allowing frontend inference", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      id: TOKEN_ID,
      chain: "solana",
      mint_address: "So11111111111111111111111111111111111111112",
      token_program: "spl-token",
      symbol: "MOON",
      name: "Moon Fixture",
      decimals: 6,
      status: "ACTIVE",
      creator_wallet: null,
      pools: [],
      candidate: null,
      launch_lifecycle: {},
      insider_evidence: {
        suspicion_state: "UNKNOWN",
        suspicious_holder_count: null,
        suspicious_supply_pct: null,
        confidence: null,
        reason_codes: ["HOLDER_EVIDENCE_MISSING"],
        evidence_refs: [],
        provenance: [],
        excluded_address_count: 0,
        excluded_address_categories: [],
        top_suspicious_wallets: [],
        quality_state: "UNKNOWN",
        as_of: null
      }
    })));

    const result = await fetchToken(TOKEN_ID);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.insiderEvidence?.suspicionState).toBe("UNKNOWN");
      expect(result.data.insiderEvidence?.suspiciousSupplyPct).toBeNull();
      expect(result.data.insiderEvidence?.excludedAddressCount).toBe(0);
    }
  });

  it("fetches chain opportunity evidence through the existing bounded read route", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn().mockResolvedValue(response({
      items: [{
        chain: "bnb",
        as_of: "2026-09-07T12:00:00.000Z",
        expires_at: "2026-09-07T12:05:00.000Z",
        new_token_count_5m: 3,
        new_token_count_1h: 8,
        new_token_count_24h: null,
        new_pool_count_5m: 2,
        new_pool_count_1h: 5,
        new_pool_count_24h: null,
        active_wallet_count_5m: 10,
        active_wallet_acceleration: "1.2",
        transaction_count_5m: 20,
        transaction_count_1h: 60,
        transaction_acceleration: null,
        dex_volume_5m: "100.5",
        dex_volume_1h: "500.0",
        dex_volume_acceleration: null,
        liquidity_inflow_5m: null,
        liquidity_inflow_1h: null,
        liquidity_inflow_acceleration: null,
        launchpad_launch_count_5m: null,
        launchpad_graduation_count_5m: null,
        successful_launch_ratio_5m: null,
        provenance: [],
        evidence_refs: ["fixture:chain"],
        reason_codes: ["SOURCE_DIVERSITY"],
        source_independence_count: 2,
        source_diversity_confidence: "0.6",
        confidence: "0.6",
        config_hash: "sha256:fixture",
        quality_state: "FRESH",
        version: "chain-opportunity-v1",
        execution_eligible: false
      }],
      limit: 50,
      has_more: false,
      next_cursor: null
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchChainOpportunities({ chain: "bnb", qualityState: "FRESH" });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.internal:8000/v1/chain-opportunities?limit=50&chain=bnb&quality_state=FRESH",
      expect.objectContaining({ cache: "no-store" })
    );
    if (result.ok) expect(result.data.items[0]?.dexVolume5m).toBe(100.5);
  });

  it("rejects operations responses that attempt to enable execution or modes", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      schema_version: "operations-overview-v1",
      as_of: "2026-09-01T06:00:00.000Z",
      overall_state: "HEALTHY",
      slo_state: "MEASURED",
      policy_version: "provider-slo-v1",
      measurement_method: "runtime",
      providers: [],
      alerts: [],
      metrics: {},
      modes: {
        analysis_only: true,
        paper_trading: true,
        manual_execution: false,
        auto_execution: false
      },
      execution_eligible: true
    })));

    expect(await fetchOperations()).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });

  it("rejects malformed records instead of partially rendering them", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({ items: [{ id: "not-a-candidate" }], limit: 50, has_more: false, next_cursor: null })
      )
    );

    expect(await fetchCandidates({})).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });

  it("fetches token and timeline through validated UUID paths", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({
        id: TOKEN_ID,
        chain: "solana",
        mint_address: candidatePayload.mintAddress,
        token_program: "spl-token",
        symbol: "MOON",
        name: "Moon Fixture",
        decimals: 6,
        status: "ACTIVE",
        creator_wallet: null,
        pools: [],
        candidate: null
      }))
      .mockResolvedValueOnce(response({ items: [], limit: 50, has_more: false, next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);

    const token = await fetchToken(TOKEN_ID);
    const timeline = await fetchTimeline(TOKEN_ID);

    expect(token.ok).toBe(true);
    expect(timeline.ok).toBe(true);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`http://api.internal:8000/v1/tokens/${TOKEN_ID}`);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `http://api.internal:8000/v1/tokens/${TOKEN_ID}/timeline?limit=50`
    );
    expect(await fetchToken("not-a-uuid")).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });

  it("strictly parses lifecycle projections and rejects malformed lifecycle payloads", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const lifecycle = {
      lifecycle_state: "BONDING",
      route_state: "BONDING_ROUTE",
      route_available: null,
      launchpad: "fixturepad",
      creator_address: null,
      bonding_curve_progress_bps: 4200,
      quote_asset: "USDC",
      graduation_threshold_bps: 8000,
      graduated_at: null,
      first_verified_dex_liquidity_at: null,
      first_verified_swap_at: null,
      liquidity_lock_state: null,
      pool_address: null,
      venue: null,
      as_of: "2026-08-31T12:00:00.000Z",
      expires_at: "2026-08-31T12:05:00.000Z",
      quality_state: "FRESH",
      time_quality: "EXACT",
      confidence: "0.7",
      reason_codes: ["BONDING_ROUTE"],
      evidence_refs: ["observation:1"],
      provenance: [{
        provider: "fixture-launchpad",
        source_id: "launch:1",
        observed_at: "2026-08-31T12:00:00.000Z",
        parser_version: "fixture-v1"
      }],
      config_hash: "launch-lifecycle-read-v2",
      version: "launch-lifecycle-v2"
    };
    const tokenPayload = {
      id: TOKEN_ID,
      chain: "solana",
      mint_address: candidatePayload.mintAddress,
      token_program: "spl-token",
      symbol: "MOON",
      name: "Moon Fixture",
      decimals: 6,
      status: "ACTIVE",
      creator_wallet: null,
      pools: [],
      candidate: null,
      launch_lifecycle: lifecycle
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(tokenPayload))
      .mockResolvedValueOnce(response({ ...tokenPayload, launch_lifecycle: { lifecycle_state: "BONDING" } }));
    vi.stubGlobal("fetch", fetchMock);

    const parsed = await fetchToken(TOKEN_ID);
    const malformed = await fetchToken(TOKEN_ID);

    expect(parsed.ok && parsed.data.launchLifecycle?.bondingCurveProgressBps).toBe(4200);
    expect(malformed).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });

  it("keeps unknown occurrence time distinct from observed time", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      items: [{
        id: "66666666-6666-4666-8666-666666666666",
        token_id: TOKEN_ID,
        kind: "chain.launchpad",
        source_id: "launch:unknown-time",
        occurred_at: null,
        observed_at: "2026-08-31T12:03:00.000Z",
        ingested_at: "2026-08-31T12:03:01.000Z",
        quality_state: "UNKNOWN",
        time_quality: "UNKNOWN",
        reason_codes: ["EVENT_TIME_UNKNOWN"],
        evidence_refs: [],
        payload: {},
        provenance: []
      }],
      limit: 50,
      has_more: false,
      next_cursor: null
    })));

    const result = await fetchTimeline(TOKEN_ID);

    expect(result.ok && result.data.items[0]?.occurredAt).toBeNull();
    expect(result.ok && result.data.items[0]?.timeQuality).toBe("UNKNOWN");
  });

  it("rejects timeline entries whose event timestamps are not ordered", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          items: [{
            id: "66666666-6666-4666-8666-666666666666",
            token_id: TOKEN_ID,
            kind: "market.snapshot",
            source_id: "market:fixture",
            occurred_at: "2026-08-31T12:03:02.000Z",
            observed_at: "2026-08-31T12:03:01.000Z",
            ingested_at: "2026-08-31T12:03:03.000Z",
            quality_state: "FRESH",
            reason_codes: [],
            evidence_refs: [],
            payload: {},
            provenance: []
          }],
          limit: 50,
          has_more: false,
          next_cursor: null
        })
      )
    );

    expect(await fetchTimeline(TOKEN_ID)).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });

  it("fetches and validates read-only position projections", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const position = {
      id: POSITION_ID,
      portfolio_id: PORTFOLIO_ID,
      token_id: TOKEN_ID,
      mint_address: candidatePayload.mintAddress,
      symbol: "MOON",
      name: "Moon Fixture",
      mode: "PAPER",
      state: "OPEN",
      quantity: "100",
      average_entry: "1",
      opened_at: "2026-08-31T12:00:00.000Z",
      closed_at: null,
      average_exit: null,
      realized_pnl: "0",
      high_watermark: "1.2",
      mfe: "0.2",
      mae: "-0.1",
      current_mark: {
        price: "1.1",
        occurred_at: "2026-08-31T12:05:00.000Z",
        observed_at: "2026-08-31T12:05:01.000Z",
        ingested_at: "2026-08-31T12:05:02.000Z",
        provider: "fixture-market",
        source_id: "market:position",
        parser_version: "fixture-v1",
        quality_state: "FRESH",
        evidence_refs: ["observation:1"]
      },
      performance: {
        as_of: "2026-08-31T12:05:01.000Z",
        quality_state: "FRESH",
        realized_pnl: "0",
        mfe: "0.2",
        mae: "-0.1",
        high_watermark: "1.2",
        current_value: "110",
        unrealized_pnl: "10",
        total_pnl: "10",
        return_ratio: "0.1",
        evidence_refs: ["observation:1"]
      },
      exit_risk: null,
      closed_trade: null,
      latest_activity_at: "2026-08-31T12:05:01.000Z",
      execution_eligible: false
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ items: [position], limit: 50, has_more: false, next_cursor: null }))
      .mockResolvedValueOnce(response(position));
    vi.stubGlobal("fetch", fetchMock);

    const page = await fetchPositions({ portfolioId: PORTFOLIO_ID, mode: "PAPER", state: "OPEN" });
    const detail = await fetchPosition(POSITION_ID);

    expect(page.ok && page.data.items[0]?.performance.unrealizedPnl).toBe(10);
    expect(detail.ok && detail.data.currentMark?.qualityState).toBe("FRESH");
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      `http://api.internal:8000/v1/positions?limit=50&portfolio_id=${PORTFOLIO_ID}&mode=PAPER&state=OPEN`,
      `http://api.internal:8000/v1/positions/${POSITION_ID}`
    ]);
  });

  it("reads the remaining bounded operator catalogs and control projections", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const walletAddress = "Vote111111111111111111111111111111111111111";
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({
        items: [{
          address: walletAddress,
          label: "Fixture smart wallet",
          registry_tier: "TIER_A",
          recommended_tier: "TIER_A",
          as_of: "2026-08-31T12:00:00.000Z",
          expires_at: "2026-08-31T13:00:00.000Z",
          score: "91",
          confidence: "0.88",
          sample_count: 12,
          known_outcome_count: 8,
          win_rate: "0.75",
          realized_pnl: "12.5",
          quality_state: "FRESH",
          reason_codes: ["POSITIVE_OUTCOMES"],
          evidence_refs: ["wallet:fixture"],
          execution_eligible: false
        }],
        limit: 50,
        has_more: false,
        next_cursor: null
      }))
      .mockResolvedValueOnce(response({
        items: [{
          provider: "fixture-market",
          capability: "market_data",
          state: "DEGRADED",
          checked_at: "2026-08-31T12:01:00.000Z",
          latency_ms: 125,
          quota: { remaining: 4, limit: 10 },
          freshness_state: "STALE",
          error_class: "rate_limited",
          consecutive_failures: 2
        }],
        limit: 50,
        has_more: false,
        next_cursor: null
      }))
      .mockResolvedValueOnce(response({
        items: [{
          id: CANDIDATE_ID,
          actor: "operator",
          action: "control.analysis_pause",
          target: "analysis",
          occurred_at: "2026-08-31T12:02:00.000Z",
          correlation_id: "corr-fixture",
          before: {},
          after: { analysis_paused: true, authorization: "Bearer hidden" }
        }],
        limit: 50,
        has_more: false,
        next_cursor: null
      }))
      .mockResolvedValueOnce(response({
        items: [{
          id: CANDIDATE_ID,
          version: "control-config-v1",
          created_at: "2026-08-31T12:03:00.000Z",
          actor: "admin",
          config_hash: "sha256:fixture",
          decision_affecting: true,
          config: {
            decision_entry_ready_threshold: 85,
            password: "should-not-render"
          }
        }],
        limit: 50,
        has_more: false,
        next_cursor: null
      }))
      .mockResolvedValueOnce(response({
        api_version: "control-api-v1",
        analysis_paused: false,
        execution_kill_switch: true,
        version: 2,
        updated_at: "2026-08-31T12:04:00.000Z",
        updated_by: "system",
        correlation_id: "control-fixture",
        protected_modes: {
          analysis_only: true,
          paper_trading: true,
          manual_execution: false,
          auto_execution: false
        }
      }))
      .mockResolvedValueOnce(response({
        api_version: "control-api-v1",
        id: CANDIDATE_ID,
        version: "control-config-v1",
        created_at: "2026-08-31T12:03:00.000Z",
        actor: "admin",
        config_hash: "sha256:fixture",
        decision_affecting: true,
        config: {
          alert_max_messages_per_window: 20,
          alert_rate_limit_window_seconds: 60,
          decision_watch_threshold: 40,
          decision_strong_setup_threshold: 75,
          decision_entry_ready_threshold: 85,
          decision_minimum_confidence: 0.6
        }
      }));
    vi.stubGlobal("fetch", fetchMock);

    const wallets = await fetchWallets({ tier: "TIER_A", minScore: 80 });
    const health = await fetchProviderHealth({ state: "DEGRADED" });
    const audits = await fetchAuditEvents({ action: "control.analysis_pause" });
    const configs = await fetchConfigVersions({ decisionAffecting: true });
    const state = await fetchControlState();
    const config = await fetchControlConfig();

    expect(wallets.ok && wallets.data.items[0]?.score).toBe(91);
    expect(health.ok && health.data.items[0]?.state).toBe("DEGRADED");
    expect(audits.ok && audits.data.items[0]?.action).toBe("control.analysis_pause");
    expect(configs.ok && configs.data.items[0]?.configHash).toBe("sha256:fixture");
    expect(state.ok && state.data.executionKillSwitch).toBe(true);
    expect(config.ok && config.data.config.decision_entry_ready_threshold).toBe(85);
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://api.internal:8000/v1/wallets?limit=50&tier=TIER_A&min_score=80",
      "http://api.internal:8000/v1/providers/health?limit=50&state=DEGRADED",
      "http://api.internal:8000/v1/audit/events?limit=50&action=control.analysis_pause",
      "http://api.internal:8000/v1/config/versions?limit=50&decision_affecting=true",
      "http://api.internal:8000/v1/control/state",
      "http://api.internal:8000/v1/control/config"
    ]);
    expect(JSON.stringify(audits)).not.toContain("should-not-render");
    expect(await fetchWallet("not-a-solana-address")).toEqual({
      ok: false,
      reason: "INVALID_RESPONSE"
    });
  });
});
