import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RadarDashboard } from "./radar";
import type { CandidateRecord, ReadPage, ReadResult } from "../lib/read-api";

const first: CandidateRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  tokenId: "22222222-2222-4222-8222-222222222222",
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

describe("RadarDashboard", () => {
  afterEach(() => cleanup());

  it("preserves API ranking and exposes bounded filters and canonical detail links", () => {
    render(
      <RadarDashboard
        filters={{ state: "WATCH", riskDisposition: "PASS", minScore: 70 }}
        result={result([first, second])}
      />
    );

    expect(screen.getByRole("heading", { name: "Radar" })).toBeInTheDocument();
    expect(screen.getByText("MOON")).toBeInTheDocument();
    expect(screen.getByText("WAVE")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /MOON/i })).toHaveAttribute(
      "href",
      "/tokens/22222222-2222-4222-8222-222222222222"
    );
    expect(screen.getByRole("combobox", { name: "State" })).toHaveValue("WATCH");
    expect(screen.getByRole("combobox", { name: "Risk" })).toHaveValue("PASS");
    expect(screen.getByRole("spinbutton", { name: "Minimum score" })).toHaveValue(70);
    expect(screen.getByText("LIVE DATA")).toBeInTheDocument();
    expect(screen.getByText("ADVISORY OUTPUT")).toBeInTheDocument();
    expect(screen.getByText("SCORE 84 / 100")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /Freshness: UNKNOWN/ })).toBeInTheDocument();
  });

  it("does not invent rows for empty or unavailable data", () => {
    const { rerender } = render(
      <RadarDashboard filters={{}} result={result([])} />
    );
    expect(screen.getByText("NO CANDIDATES MATCH FILTERS")).toBeInTheDocument();
    expect(screen.queryByText("MOON")).not.toBeInTheDocument();

    rerender(<RadarDashboard filters={{}} result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("RADAR UNAVAILABLE")).toBeInTheDocument();

    rerender(<RadarDashboard filters={{}} result={{ ok: false, reason: "NOT_CONFIGURED" }} />);
    expect(screen.getByText("READ API NOT CONFIGURED")).toBeInTheDocument();
  });
});
