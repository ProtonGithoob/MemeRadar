import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { fireEvent } from "@testing-library/react";

import {
  UltraEarlyPanel,
  UltraEarlyWorkspace,
  alertGate,
  displayLiquiditySource,
  displayTape,
  missingEvidence
} from "./ultra-early";
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
  upsideEvidence: { narrative: "CONVERGENT", smart_wallets: 4 },
  marketIntegrityRisk: "UNKNOWN",
  contractDeployerRisk: "LOW",
  liquidityExitRisk: "PASS",
  executionQuality: 78,
  evidenceConfidence: 0.84,
  evidenceQualityState: "FRESH",
  venue: "PUMPSWAP",
  firstSeenMarketCap: 42000,
  currentMarketCap: 68000,
  buyerAcceleration: 0.72,
  volumeAcceleration: 0.81,
  liquidityAcceleration: 0.34,
  rawSmartWalletCount: 4,
  independentSmartWalletCount: 3,
  organicMomentum: 76,
  liquiditySource: "EXECUTABLE_QUOTE_DEPTH",
  tapeTradeCount: 122,
  tapeUniqueBuyers: 72,
  alerted: true,
  alertLatencyMs: 240,
  multipleSinceDiscovery: 1.62,
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
    expect(screen.getByText("DELIVERED")).toBeInTheDocument();
    expect(screen.getByText("91")).toBeInTheDocument();
    expect(screen.getByText("$12.0K")).toBeInTheDocument();
    expect(screen.getByText("ENTRY_READY")).toBeInTheDocument();
  });

  it("shows liquidity provenance, organic momentum and trade tape in the inspector", () => {
    render(<UltraEarlyPanel result={result([entry])} />);

    expect(screen.getByText("Executable round trip at trade size (within impact limit)")).toBeInTheDocument();
    expect(screen.getAllByText("122 trades · 72 unique buyers").length).toBe(2);
    expect(screen.getByText("Organic momentum")).toBeInTheDocument();
  });

  it("never presents missing liquidity provenance or tape as a value", () => {
    expect(displayLiquiditySource(null)).toBe("UNKNOWN");
    expect(displayLiquiditySource("MARKET_DATA")).toBe("MARKET_DATA");
    expect(displayTape(null, null)).toBe("UNKNOWN");
    expect(displayTape(5, null)).toBe("5 trades · UNKNOWN buyers");
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
    expect(screen.getByRole("combobox", { name: "Sort launches" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "MEME" })).toBeInTheDocument();
    expect(screen.getByText(/Auto execution: LOCKED/)).toBeInTheDocument();
  });

  it("lists every tracked launch and marks only backend-qualified ones alert ready", () => {
    const waiting: EarlyRadarRecord = {
      ...entry,
      candidateId: "33333333-3333-4333-8333-333333333333",
      symbol: "WAIT",
      earlyState: "WATCH",
      reasonCodes: ["SELLABILITY_UNKNOWN", "EARLY_SCORE_BELOW_ENTRY_THRESHOLD"]
    };
    render(<UltraEarlyWorkspace qualified={result([entry])} result={result([entry, waiting])} />);

    expect(screen.getByRole("link", { name: "MEME" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "WAIT" })).toBeInTheDocument();
    expect(screen.getAllByText("ALERT READY").length).toBeGreaterThan(0);
    expect(screen.getAllByText("WAITING").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SELLABILITY UNKNOWN").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Alert ready" }));
    expect(screen.getByRole("link", { name: "MEME" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "WAIT" })).not.toBeInTheDocument();
  });

  it("never infers alert readiness in the browser", () => {
    const strong: EarlyRadarRecord = { ...entry, hardBlockReasons: [], riskDisposition: "PASS" };
    expect(alertGate(strong, new Set())).toBe("WAITING");
    expect(alertGate(strong, null)).toBe("UNKNOWN");
    expect(alertGate(strong, new Set([strong.candidateId]))).toBe("ALERT_READY");
    expect(alertGate({ ...strong, hardBlockReasons: ["SELL_IMPACT_HIGH"] }, new Set())).toBe("BLOCKED");
    expect(missingEvidence({ ...strong, reasonCodes: ["LIQUIDITY_UNKNOWN", "TOKEN_2022_PROGRAM"] }))
      .toEqual(["LIQUIDITY_UNKNOWN"]);
  });
});
