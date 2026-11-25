import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WalletResearchDashboard } from "./wallet-research";
import { parseWinnerRegistryRecord } from "../lib/read-api";
import type { ReadPage, ReadResult, WalletRecord, WinnerRegistryRecord } from "../lib/read-api";

const record: WinnerRegistryRecord = {
  mint: "2P4qGGkKRRKJoTyqKfVgNQ4Nkta7ckL7jpq8Sy32pump",
  launchAt: "2026-11-25T00:30:00+00:00",
  migratedAt: "2026-11-25T00:36:00+00:00",
  tradeCount: 559,
  uniqueBuyers: 210,
  initialMarketCapSol: 28,
  peakMarketCapSol: 570,
  historyComplete: true,
  ammTradesDecoded: true,
  outcomes: [
    { horizon: "1h", outcome: "20x", peakMultiple: 20.3, censorReason: null },
    { horizon: "24h", outcome: "PENDING", peakMultiple: null, censorReason: "HORIZON_NOT_MATURE" }
  ],
  asOf: "2026-11-25T03:30:00+00:00"
};

const wallet: WalletRecord = {
  address: "Vote111111111111111111111111111111111111111",
  label: "POTENTIAL_INSIDER",
  registryTier: "CANDIDATE",
  recommendedTier: "BLOCKED",
  asOf: "2026-11-25T03:30:00.000Z",
  expiresAt: "2026-11-26T03:30:00.000Z",
  score: null,
  confidence: null,
  sampleCount: 3,
  knownOutcomeCount: 3,
  winRate: null,
  realizedPnl: null,
  qualityState: "FRESH",
  reasonCodes: ["POTENTIAL_INSIDER", "HEURISTIC_CLASSIFICATION_NOT_CALIBRATED"],
  evidenceRefs: []
};

const wallets: ReadResult<ReadPage<WalletRecord>> = {
  ok: true,
  data: { items: [wallet], limit: 50, nextCursor: null, hasMore: false }
};

afterEach(cleanup);

describe("wallet research dashboard", () => {
  it("separates verified registry outcomes from heuristic wallet classes", () => {
    render(<WalletResearchDashboard registry={{ ok: true, data: [record] }} wallets={wallets} />);
    expect(screen.getByText(/VERIFIED ON-CHAIN TRADES/)).toBeTruthy();
    expect(screen.getByText(/HEURISTIC, NOT CALIBRATED/)).toBeTruthy();
    expect(screen.getByText("20x (20.30x)")).toBeTruthy();
    expect(screen.getByText("PENDING (horizon not mature)")).toBeTruthy();
    expect(screen.getByText("Manipulation-risk wallets (risk evidence only): 1")).toBeTruthy();
    expect(screen.getByText("Early smart-money candidates (unvalidated): 0")).toBeTruthy();
  });

  it("shows read failures explicitly instead of an empty success", () => {
    render(
      <WalletResearchDashboard
        registry={{ ok: false, reason: "UNAVAILABLE" }}
        wallets={{ ok: false, reason: "NOT_CONFIGURED" }}
      />
    );
    expect(screen.getByText("REGISTRY UNAVAILABLE")).toBeTruthy();
    expect(screen.getByText("WALLET READ API NOT CONFIGURED")).toBeTruthy();
  });

  it("rejects malformed registry records", () => {
    expect(parseWinnerRegistryRecord({ mint: "x", outcomes: [] })).toBeNull();
    expect(
      parseWinnerRegistryRecord({
        mint: record.mint, launch_at: record.launchAt, as_of: record.asOf, migrated_at: "garbage",
        trade_count: 1, unique_buyers: 1, outcomes: []
      })
    ).toBeNull();
    expect(
      parseWinnerRegistryRecord({
        mint: record.mint, launch_at: record.launchAt, as_of: record.asOf, migrated_at: null,
        trade_count: 1, unique_buyers: 1,
        outcomes: [{ horizon: "1h", outcome: "NOT_A_CLASS" }]
      })
    ).toBeNull();
  });
});
