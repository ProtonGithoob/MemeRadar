import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PositionsDashboard } from "./positions";
import type { PositionRecord, ReadPage, ReadResult } from "../lib/read-api";

const position: PositionRecord = {
  id: "44444444-4444-4444-8444-444444444444",
  portfolioId: "33333333-3333-4333-8333-333333333333",
  tokenId: "22222222-2222-4222-8222-222222222222",
  mintAddress: "So11111111111111111111111111111111111111112",
  symbol: "MOON",
  name: "Moon Fixture",
  mode: "PAPER",
  state: "OPEN",
  quantity: 100,
  averageEntry: 1,
  openedAt: "2026-08-31T12:00:00.000Z",
  closedAt: null,
  averageExit: null,
  realizedPnl: 0,
  highWatermark: 1.2,
  mfe: 0.2,
  mae: -0.1,
  currentMark: {
    price: 1.1,
    occurredAt: "2026-08-31T12:05:00.000Z",
    observedAt: "2026-08-31T12:05:01.000Z",
    ingestedAt: "2026-08-31T12:05:02.000Z",
    provider: "fixture-market",
    sourceId: "market:position",
    parserVersion: "fixture-v1",
    qualityState: "FRESH",
    evidenceRefs: ["observation:1"]
  },
  performance: {
    asOf: "2026-08-31T12:05:01.000Z",
    qualityState: "FRESH",
    realizedPnl: 0,
    mfe: 0.2,
    mae: -0.1,
    highWatermark: 1.2,
    currentValue: 110,
    unrealizedPnl: 10,
    totalPnl: 10,
    returnRatio: 0.1,
    evidenceRefs: ["observation:1"]
  },
  exitRisk: {
    evaluationId: "55555555-5555-4555-8555-555555555555",
    evaluatedAt: "2026-08-31T12:06:00.000Z",
    action: "REDUCE",
    exitFraction: 0.5,
    score: 72,
    confidence: 0.8,
    qualityState: "FRESH",
    triggeredRules: ["FLOW_REVERSAL"],
    reasonCodes: ["FLOW_REVERSAL"],
    evidenceRefs: ["flow:1"],
    policyVersion: "exit-v1",
    configHash: "sha256:exit"
  },
  closedTrade: null,
  latestActivityAt: "2026-08-31T12:06:00.000Z"
};

function result(items: PositionRecord[]): ReadResult<ReadPage<PositionRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("PositionsDashboard", () => {
  afterEach(() => cleanup());

  it("distinguishes observed marks, derived PnL and advisory exit risk", () => {
    render(<PositionsDashboard result={result([position])} />);

    expect(screen.getByRole("heading", { name: "Positions" })).toBeInTheDocument();
    expect(screen.getByText("MOON")).toBeInTheDocument();
    expect(screen.getByText("fixture-market")).toBeInTheDocument();
    expect(screen.getByText("+10.00 QUOTE PNL")).toBeInTheDocument();
    expect(screen.getByText("REDUCE / 50%")).toBeInTheDocument();
    expect(screen.getAllByText("FLOW_REVERSAL")).not.toHaveLength(0);
    expect(screen.getByText("No execution controls in this view")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute|sell|buy/i })).not.toBeInTheDocument();
  });

  it("keeps unavailable position data explicit and does not invent evidence", () => {
    const unknown = {
      ...position,
      currentMark: null,
      performance: { ...position.performance, qualityState: "UNKNOWN" as const, currentValue: null, unrealizedPnl: null, totalPnl: null, returnRatio: null },
      exitRisk: null
    };
    const { rerender } = render(<PositionsDashboard result={result([unknown])} />);

    expect(screen.getAllByText("UNKNOWN")).not.toHaveLength(0);
    expect(screen.getByText(/No market mark was returned/)).toBeInTheDocument();
    rerender(<PositionsDashboard result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("POSITION DATA UNAVAILABLE")).toBeInTheDocument();
  });
});
