import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WalletDetailView } from "./wallet-detail";
import type { ReadResult, WalletRecord } from "../lib/read-api";

const wallet: WalletRecord = {
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

describe("WalletDetailView", () => {
  afterEach(() => cleanup());

  it("renders explainable wallet metrics without execution authority", () => {
    render(<WalletDetailView result={{ ok: true, data: wallet }} />);

    expect(screen.getByRole("heading", { name: "Alpha wallet" })).toBeInTheDocument();
    expect(screen.getByText(wallet.address)).toBeInTheDocument();
    expect(screen.getByText("REALIZED PNL")).toBeInTheDocument();
    expect(screen.getByText("12.50")).toBeInTheDocument();
    expect(screen.getByText("POSITIVE_OUTCOMES")).toBeInTheDocument();
    expect(screen.getByText(/not execution authority/i)).toBeInTheDocument();
  });

  it("keeps not-found and invalid read states explicit", () => {
    const { rerender } = render(<WalletDetailView result={{ ok: true, data: null }} />);
    expect(screen.getByText("WALLET NOT FOUND")).toBeInTheDocument();
    rerender(<WalletDetailView result={{ ok: false, reason: "INVALID_RESPONSE" }} />);
    expect(screen.getByText("INVALID READ RESPONSE")).toBeInTheDocument();
  });
});
