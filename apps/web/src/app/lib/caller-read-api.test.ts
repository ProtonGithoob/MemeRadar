import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCallerConvergence,
  fetchCallerProfiles,
  fetchSocialCalls
} from "./read-api";

const BNB_ADDRESS = "0x1111111111111111111111111111111111111111";

function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  };
}

const provenance = [{
  provider: "fixture-social",
  source_id: "fixture:1",
  observed_at: "2026-09-07T08:00:00.000Z",
  parser_version: "fixture-v1",
  raw_payload_hash: null
}];

const profile = {
  caller_id: "telegram:alpha",
  platform: "telegram",
  author_id: "alpha",
  as_of: "2026-09-07T08:00:00.000Z",
  expires_at: "2026-09-07T08:15:00.000Z",
  status: "INSUFFICIENT_SAMPLES",
  handle: "alpha",
  display_name: "Alpha Caller",
  sample_count: 1,
  matured_sample_count: 0,
  known_outcome_count: 0,
  evidence_coverage: null,
  early_entry_percentile: null,
  early_entry_quality: null,
  median_call_time_market_cap: null,
  median_token_age_seconds: null,
  executable_win_rates: {},
  median_executable_mfe: null,
  median_executable_mae: null,
  rug_count: 0,
  failure_count: 0,
  rug_avoidance_rate: null,
  consistency_rate: null,
  recency_stability: null,
  specialization: {},
  smart_wallet_confirmation_rate: null,
  early_call_count: 0,
  late_call_count: 0,
  early_call_rate: null,
  late_call_rate: null,
  edited_call_rate: null,
  deleted_call_rate: null,
  paid_promotion_rate: null,
  confidence_intervals: {},
  confidence: "0",
  uncertainty: "1",
  quality_state: "UNKNOWN",
  no_lookahead_verified: true,
  provenance,
  evidence_refs: ["caller-profile:fixture"],
  reason_codes: ["CALLER_HISTORY_UNKNOWN"],
  config_hash: "sha256:caller-profile",
  version: "caller-performance-v1",
  execution_eligible: false
};

const call = {
  id: "telegram:call-1",
  source: "telegram",
  message_id: "call-1",
  caller_id: "telegram:alpha",
  platform: "telegram",
  author_id: "alpha",
  published_at: "2026-09-07T08:00:00.000Z",
  observed_at: "2026-09-07T08:00:00.000Z",
  ingested_at: "2026-09-07T08:00:00.000Z",
  chain: "bnb",
  asset_address: BNB_ADDRESS,
  asset_id: `bnb:${BNB_ADDRESS}`,
  referenced_address: null,
  unresolved_references: [],
  intent: "BULLISH",
  declared_entry: null,
  declared_targets: [],
  disclosure: {},
  edited: null,
  deleted: null,
  handle: "alpha",
  display_name: "Alpha Caller",
  confidence: "0.8",
  quality_state: "FRESH",
  provenance,
  evidence_refs: ["social-call:fixture"],
  execution_eligible: false
};

const convergence = {
  id: `bnb:${BNB_ADDRESS}:2026-09-07T08:00:00+00:00`,
  token_id: `bnb:${BNB_ADDRESS}`,
  chain: "bnb",
  asset_address: BNB_ADDRESS,
  as_of: "2026-09-07T08:00:00.000Z",
  expires_at: "2026-09-07T08:05:00.000Z",
  state: "CALLER_ONLY",
  raw_caller_count: 1,
  independent_caller_count: 1,
  cluster_adjusted_caller_count: 1,
  high_quality_caller_count: null,
  caller_ids: ["telegram:alpha"],
  independent_caller_ids: ["telegram:alpha"],
  earliest_call_at: null,
  latest_call_at: null,
  temporal_dispersion_seconds: null,
  smart_wallet_confirmation: null,
  narrative_alignment: null,
  contradictory_call_count: 0,
  distribution_detected: null,
  risk_disposition: null,
  risk_quality_state: "UNKNOWN",
  risk_blocked: null,
  confidence: "0.5",
  quality_state: "UNKNOWN",
  no_lookahead_verified: true,
  provenance,
  evidence_refs: ["caller-convergence:fixture"],
  reason_codes: ["CALLER_CONVERGENCE_RISK_UNKNOWN"],
  config_hash: "sha256:caller-convergence",
  version: "caller-convergence-v1",
  execution_eligible: false
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("caller read gateway", () => {
  it("fetches validated caller projections through bounded read endpoints", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ items: [profile], limit: 50, has_more: false, next_cursor: null }))
      .mockResolvedValueOnce(response({ items: [call], limit: 50, has_more: false, next_cursor: null }))
      .mockResolvedValueOnce(response({ items: [convergence], limit: 50, has_more: false, next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);

    const profiles = await fetchCallerProfiles({ platform: "telegram" });
    const calls = await fetchSocialCalls({ chain: "bnb" });
    const convergences = await fetchCallerConvergence({ chain: "bnb", qualityState: "UNKNOWN" });

    expect(profiles.ok && profiles.data.items[0]?.callerId).toBe("telegram:alpha");
    expect(calls.ok && calls.data.items[0]?.assetId).toBe(`bnb:${BNB_ADDRESS}`);
    expect(convergences.ok && convergences.data.items[0]?.tokenId).toBe(`bnb:${BNB_ADDRESS}`);
    expect(fetchMock.mock.calls.map((callArgs) => callArgs[0])).toEqual([
      "http://api.internal:8000/v1/caller-profiles?limit=50&platform=telegram",
      "http://api.internal:8000/v1/social-calls?limit=50&chain=bnb",
      "http://api.internal:8000/v1/caller-convergence?limit=50&chain=bnb&quality_state=UNKNOWN"
    ]);
  });

  it("rejects a caller projection that attempts to authorize execution", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({ items: [{ ...profile, execution_eligible: true }], limit: 50, has_more: false, next_cursor: null })
      )
    );

    expect(await fetchCallerProfiles()).toEqual({ ok: false, reason: "INVALID_RESPONSE" });
  });
});
