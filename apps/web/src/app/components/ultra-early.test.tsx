import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { UltraEarlyPanel, UltraEarlyWorkspace } from "./ultra-early";
import type { EarlyRadarRecord, ReadPage, ReadResult } from "../lib/read-api";

const entry: EarlyRadarRecord = {
  candidateId: "11111111-1111-4111-8111-111111111111",
  tokenId: "22222222-2222-4222-8222-222222222222",
  mintAddress: "So11111111111111111111111111111111111111112",
  symbol: "MEME",
  name: "Early Meme",
  launchAgeSeconds: 34,
  firstSeenAt: "2026-09-01T12:00:00.000Z",
  firstSeenSource: "direct-chain:fixture",
  firstSeenLatencyMs: 125,
  firstSeenQuality: "FRESH",
  earlyScore: 91,
  earlyScoreConfidence: 0.84,
  earlyState: "ENTRY_READY",
  riskDisposition: "PASS",
  buyVelocity: { "1s": 4 },
  buyAcceleration: { "1s": 1.5 },
  uniqueBuyers: { "1s": 4 },
  quoteInflow: { "1s": 1.2 },
  liquidityUsd: 12000,
  priceImpactBps: 120,
  creatorRisk: "LOW",
  bundleRisk: "MEDIUM",
  holderRisk: "UNKNOWN",
  smartMoneyConfluence: 72,
  sellability: "PASS",
  shadowEntryStatus: "SHADOW_FILLED",
  externalCallLeadTimeMs: 15000,
  hardBlockReasons: [],
  latencyMs: { first_seen_to_entry_ready: 300 },
  evidenceRefs: ["chain:fixture"],
  reasonCodes: ["EARLY_SCORE_V1"]
};

function result(items: EarlyRadarRecord[]): ReadResult<ReadPage<EarlyRadarRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("UltraEarlyPanel", () => {
  afterEach(() => cleanup());

  it("renders bounded launch evidence in a dense table", () => {
    render(<UltraEarlyPanel result={result([entry])} />);

    expect(screen.getByRole("heading", { name: "Ultra-Early Detection" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "MEME" })).toHaveAttribute(
      "href",
      "/tokens/22222222-2222-4222-8222-222222222222"
    );
    expect(screen.getByText("34s")).toBeInTheDocument();
    expect(screen.getByText("91")).toBeInTheDocument();
    expect(screen.getByText("$12.0K")).toBeInTheDocument();
    expect(screen.getByText("125ms")).toBeInTheDocument();
    expect(screen.getByText("ENTRY_READY")).toBeInTheDocument();
  });

  it("keeps unknown and blocked evidence explicit", () => {
    render(
      <UltraEarlyPanel
        result={result([{ ...entry, earlyScore: null, earlyScoreConfidence: null, earlyState: "REJECT/LOW", firstSeenQuality: "UNKNOWN", holderRisk: "UNKNOWN", hardBlockReasons: ["RISK_UNKNOWN"] }])}
      />
    );

    expect(screen.getByText("REJECT/LOW")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });

  it("keeps the unavailable state explicit without substituting data", () => {
    render(<UltraEarlyPanel result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("EARLY RADAR UNAVAILABLE")).toBeInTheDocument();
  });
});

describe("UltraEarlyWorkspace", () => {
  afterEach(() => cleanup());

  it("filters rows through presets without hiding unknown rows by default", () => {
    render(<UltraEarlyWorkspace result={result([entry])} />);

    expect(screen.getByRole("heading", { name: "Ultra-Early Detection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fresh <1m" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entry Ready" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unknown Critical Data" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "MEME" })).toBeInTheDocument();
    expect(screen.getByText(/Auto execution: LOCKED/)).toBeInTheDocument();
  });
});
