import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChainOpportunitiesDashboard } from "./chain-opportunities";
import type { ChainOpportunityRecord } from "../lib/read-api";

const opportunity: ChainOpportunityRecord = {
  chain: "bnb",
  asOf: "2026-09-07T12:00:00.000Z",
  expiresAt: "2026-09-07T12:05:00.000Z",
  newTokenCount5m: 3,
  newTokenCount1h: 8,
  newTokenCount24h: null,
  newPoolCount5m: 2,
  newPoolCount1h: 5,
  newPoolCount24h: null,
  activeWalletCount5m: 10,
  activeWalletAcceleration: 1.2,
  transactionCount5m: 20,
  transactionCount1h: 60,
  transactionAcceleration: null,
  dexVolume5m: 100.5,
  dexVolume1h: 500,
  dexVolumeAcceleration: null,
  liquidityInflow5m: null,
  liquidityInflow1h: null,
  liquidityInflowAcceleration: null,
  launchpadLaunchCount5m: null,
  launchpadGraduationCount5m: null,
  successfulLaunchRatio5m: null,
  provenance: [],
  evidenceRefs: ["fixture:chain"],
  reasonCodes: ["SOURCE_DIVERSITY"],
  sourceIndependenceCount: 2,
  sourceDiversityConfidence: 0.6,
  confidence: 0.6,
  configHash: "sha256:fixture",
  qualityState: "FRESH",
  version: "chain-opportunity-v1"
};

describe("ChainOpportunitiesDashboard", () => {
  afterEach(() => cleanup());

  it("renders chain evidence and keeps missing measurements explicit", () => {
    render(<ChainOpportunitiesDashboard result={{ ok: true, data: {
      items: [opportunity], limit: 50, hasMore: false, nextCursor: null
    } }} />);

    expect(screen.getByRole("heading", { name: "Chain opportunities" })).toBeInTheDocument();
    expect(screen.getByText("BNB")).toBeInTheDocument();
    expect(screen.getByText("100.50")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
    expect(screen.getByText("EXECUTION LOCKED")).toBeInTheDocument();
  });
});
