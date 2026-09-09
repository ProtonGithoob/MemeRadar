import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RadarExplorer } from "./radar";
import type {
  CandidateRecord,
  EarlyRadarRecord,
  ReadPage,
  ReadResult
} from "../lib/read-api";

const first: CandidateRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  tokenId: "22222222-2222-4222-8222-222222222222",
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

const second: CandidateRecord = {
  ...first,
  id: "33333333-3333-4333-8333-333333333333",
  tokenId: "44444444-4444-4444-8444-444444444444",
  symbol: "WAVE",
  name: "Wave Fixture",
  state: "ENRICHING",
  score: null,
  scoreConfidence: null,
  riskDisposition: "UNKNOWN",
  riskQualityState: "UNKNOWN",
  riskReasonCodes: [],
  evidenceRefs: []
};

function result(items: CandidateRecord[]): ReadResult<ReadPage<CandidateRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

function earlyResult(items: EarlyRadarRecord[]): ReadResult<ReadPage<EarlyRadarRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("RadarExplorer", () => {
  afterEach(() => cleanup());

  it("preserves API ranking and exposes bounded filters and canonical detail links", () => {
    render(
      <RadarExplorer
        filters={{ state: "WATCH", riskDisposition: "PASS", minScore: 70 }}
        result={result([first, second])}
      />
    );

    expect(screen.getByRole("heading", { name: "Radar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /MOON/i })).toHaveAttribute(
      "href",
      "/tokens/22222222-2222-4222-8222-222222222222"
    );
    expect(screen.getByRole("link", { name: /WAVE/i })).toHaveAttribute(
      "href",
      "/tokens/44444444-4444-4444-8444-444444444444"
    );
    // API order is preserved in the dense table.
    const links = screen.getAllByRole("link", { name: /MOON|WAVE/i });
    expect(links[0]).toHaveTextContent("MOON");
    expect(links[1]).toHaveTextContent("WAVE");
    expect(screen.getByRole("combobox", { name: "State" })).toHaveValue("WATCH");
    expect(screen.getByRole("combobox", { name: "Risk" })).toHaveValue("PASS");
    expect(screen.getByRole("spinbutton", { name: "Minimum score" })).toHaveValue(70);
    expect(screen.getByText("84")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
    expect(screen.getByText("AUTHORITY_CLEAR")).toBeInTheDocument();
  });

  it("does not invent rows for empty or unavailable data", () => {
    const { rerender } = render(
      <RadarExplorer filters={{}} result={result([])} />
    );
    expect(screen.getByText("NO CANDIDATES MATCH FILTERS")).toBeInTheDocument();
    expect(screen.queryByText("MOON")).not.toBeInTheDocument();

    rerender(<RadarExplorer filters={{}} result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("RADAR UNAVAILABLE")).toBeInTheDocument();

    rerender(<RadarExplorer filters={{}} result={{ ok: false, reason: "NOT_CONFIGURED" }} />);
    expect(screen.getByText("READ API NOT CONFIGURED")).toBeInTheDocument();
  });

  it("joins ultra-early liquidity evidence onto radar rows when available", () => {
    const early: EarlyRadarRecord = {
      candidateId: first.id,
      tokenId: first.tokenId,
      mintAddress: first.mintAddress,
      symbol: "MOON",
      name: "Moon Fixture",
      launchAgeSeconds: 45,
      firstSeenAt: "2026-08-31T12:00:00.000Z",
      firstSeenSource: "fixture.discovery",
      firstSeenLatencyMs: 120,
      firstSeenQuality: "FRESH",
      earlyScore: 71,
      earlyScoreConfidence: 0.5,
      earlyState: "WATCH",
      riskDisposition: "PASS",
      buyVelocity: {},
      buyAcceleration: {},
      uniqueBuyers: {},
      quoteInflow: {},
      liquidityUsd: 42000,
      priceImpactBps: 90,
      creatorRisk: "LOW",
      bundleRisk: "LOW",
      holderRisk: "UNKNOWN",
      smartMoneyConfluence: null,
      sellability: "PASS",
      shadowEntryStatus: "NOT_SHADOWED",
      externalCallLeadTimeMs: null,
      hardBlockReasons: [],
      latencyMs: {},
      upsideEvidence: {},
      marketIntegrityRisk: "UNKNOWN",
      contractDeployerRisk: "LOW",
      liquidityExitRisk: "PASS",
      executionQuality: null,
      evidenceConfidence: 0.5,
      evidenceQualityState: "FRESH",
      evidenceRefs: [],
      reasonCodes: []
    };
    render(
      <RadarExplorer filters={{}} result={result([first])} earlyResult={earlyResult([early])} />
    );

    expect(screen.getByText("$42.0K")).toBeInTheDocument();
    expect(screen.getByText("45s")).toBeInTheDocument();
  });
});
