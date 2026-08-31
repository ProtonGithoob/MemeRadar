import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCandidates,
  fetchTimeline,
  fetchToken,
  parseRadarFilters,
  type CandidateRecord,
  type ReadPage
} from "./read-api";

const VIEWER_TOKEN = "viewer-server-secret";
const CANDIDATE_ID = "11111111-1111-4111-8111-111111111111";
const TOKEN_ID = "22222222-2222-4222-8222-222222222222";

const candidatePayload: CandidateRecord = {
  id: CANDIDATE_ID,
  tokenId: TOKEN_ID,
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
});
