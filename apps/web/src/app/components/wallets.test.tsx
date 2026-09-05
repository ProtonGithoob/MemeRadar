import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WalletsDashboard } from "./wallets";
import type { ReadPage, ReadResult, WalletRecord } from "../lib/read-api";

const walletA: WalletRecord = {
  address: "Vote111111111111111111111111111111111111111",
  label: "Alpha wallet",
  registryTier: "TIER_A",
  recommendedTier: "TIER_A",
  asOf: "2026-08-31T12:00:00.000Z",
  expiresAt: "2026-08-31T13:00:00.000Z",
  score: 91,
  confidence: 0.88,
  sampleCount: 12,
  knownOutcomeCount: 8,
  winRate: 0.75,
  realizedPnl: 12.5,
  qualityState: "FRESH",
  reasonCodes: ["POSITIVE_OUTCOMES"],
  evidenceRefs: ["wallet:alpha"]
};

const walletB: WalletRecord = {
  ...walletA,
  address: "SysvarRent111111111111111111111111111111111",
  label: "Beta wallet",
  registryTier: "CANDIDATE",
  recommendedTier: "UNKNOWN",
  score: null,
  confidence: null,
  qualityState: "UNKNOWN",
  sampleCount: 0,
  knownOutcomeCount: 0,
  winRate: null,
  realizedPnl: null,
  reasonCodes: [],
  evidenceRefs: []
};

function result(items: WalletRecord[]): ReadResult<ReadPage<WalletRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("WalletsDashboard", () => {
  afterEach(() => cleanup());

  it("preserves API leaderboard order and shows bounded wallet evidence", () => {
    render(<WalletsDashboard result={result([walletA, walletB])} />);

    expect(screen.getByRole("heading", { name: "Smart wallets" })).toBeInTheDocument();
    expect(screen.getByText("Alpha wallet")).toBeInTheDocument();
    expect(screen.getByText("Beta wallet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Alpha wallet/i })).toHaveAttribute(
      "href",
      "/wallets/Vote111111111111111111111111111111111111111"
    );
    expect(screen.getByText("SCORE 91 / 100")).toBeInTheDocument();
    expect(screen.getByText("75% WIN RATE")).toBeInTheDocument();
    expect(screen.getByText("FRESH")).toBeInTheDocument();
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "EXECUTION: LOCKED" })).toBeInTheDocument();
  });

  it("does not invent wallet evidence for empty or unavailable catalogs", () => {
    const { rerender } = render(
      <WalletsDashboard result={result([])} />
    );
    expect(screen.getByText("NO WALLET CATALOG AVAILABLE")).toBeInTheDocument();
    expect(screen.queryByText("Alpha wallet")).not.toBeInTheDocument();

    rerender(<WalletsDashboard result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("WALLET INTELLIGENCE UNAVAILABLE")).toBeInTheDocument();
  });
});
