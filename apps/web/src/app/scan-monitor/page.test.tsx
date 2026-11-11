import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ScanMonitorPage from "./page";
import { fetchCandidates, fetchEarlyRadar, fetchOperations, fetchRuntimeSettings } from "../lib/read-api";

vi.mock("../components/scan-refresh", () => ({ ScanRefresh: () => <button>Refresh now</button> }));
vi.mock("../lib/read-api", () => ({
  fetchCandidates: vi.fn(), fetchEarlyRadar: vi.fn(), fetchOperations: vi.fn(), fetchRuntimeSettings: vi.fn()
}));

describe("scan monitor", () => {
  afterEach(() => { cleanup(); vi.resetAllMocks(); });

  it("shows recorded candidates and rejected decisions with reasons", async () => {
    vi.mocked(fetchCandidates).mockResolvedValue({ ok: true, data: { items: [{
      id: "c1", tokenId: "t1", symbol: "PEPE", mintAddress: "address", chain: "solana",
      discoverySource: "rpc", state: "WATCH", riskDisposition: "WARN", discoveredAt: "2026-11-03",
      riskReasonCodes: ["LOW_LIQUIDITY"]
    } as never], limit: 1, hasMore: true, nextCursor: "next" } });
    vi.mocked(fetchEarlyRadar).mockResolvedValue({ ok: true, data: { items: [{
      candidateId: "c1", tokenId: "t1", symbol: "PEPE", mintAddress: "address", firstSeenSource: "rpc",
      firstSeenAt: "2026-11-03", earlyState: "REJECT/LOW", riskDisposition: "BLOCK",
      hardBlockReasons: ["UNSAFE"], reasonCodes: ["UNSAFE"]
    } as never], limit: 1, hasMore: false, nextCursor: null } });
    vi.mocked(fetchOperations).mockResolvedValue({ ok: true, data: {
      overallState: "DEGRADED", asOf: "2026-11-03", providers: [],
      metrics: {
        notification_delivery: {
          delivered_alerts: 2, delivery_unknown: 1, delivery_unknown_oldest_age_seconds: 45,
          delivery_unknown_reason_counts_sample: { TELEGRAM_ACK_UNKNOWN: 1 }, pending: 1,
          processing: 0, dead_letter: 0, last_delivered_at: "2026-11-03T12:00:00Z"
        },
        stream_coverage: {
          state: "UNKNOWN", unresolved_gap_count: 2, verified_recovery_ranges: 1,
          unresolved_ranges: [{
            gap_id: "gap-open", provider: "solana-public-rpc", stream_id: "early-alpha-v1",
            from_slot: 100, to_slot: 101, status: "OPEN", last_error_class: "BACKFILL_UNAVAILABLE"
          }],
          verification_ranges: [{
            gap_id: "gap-verified", provider: "solana-public-rpc", stream_id: "early-alpha-v1",
            from_slot: 90, to_slot: 90, verification_status: "PASS",
            program_scope: "UNKNOWN", commitment: "UNKNOWN"
          }]
        },
        pre_identity: { recorded_rejections: 3, identity_linked_projections: 1 }
      }
    } as never });
    vi.mocked(fetchRuntimeSettings).mockResolvedValue({ ok: true, data: { settings: [
      { key: "telegram_bot_token", configuredState: "CONFIGURED" },
      { key: "telegram_chat_id", configuredState: "CONFIGURED" }
    ] } as never });
    render(await ScanMonitorPage());
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
    expect(screen.getByText("REJECT/LOW · BLOCK")).toBeInTheDocument();
    expect(screen.getByText("UNSAFE")).toBeInTheDocument();
    expect(screen.getByText("BOT AND CHAT CONFIGURED")).toBeInTheDocument();
    expect(screen.getByText(/Delivered alerts: 2/)).toBeInTheDocument();
    expect(screen.getByText(/Unknown delivery outcomes: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Oldest unknown: 45 seconds · Reasons: TELEGRAM_ACK_UNKNOWN \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("SOURCE COVERAGE")).toBeInTheDocument();
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText(/Known unresolved gaps: 2/)).toBeInTheDocument();
    expect(screen.getByText(/Verified recovery ranges: 1/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Unresolved slot ranges (1)"));
    expect(screen.getByText("solana-public-rpc · early-alpha-v1 · slots 100–101 · OPEN · BACKFILL_UNAVAILABLE")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Recovery verification ranges (1)"));
    expect(screen.getByText(/slots 90–90 · PASS · provider solana-public-rpc · program UNKNOWN · commitment UNKNOWN/)).toBeInTheDocument();
    expect(screen.getByText(/Recorded: 3/)).toBeInTheDocument();
    expect(screen.getByText(/Identity-linked projections: 1/)).toBeInTheDocument();
    expect(screen.getByText(/More records exist/)).toBeInTheDocument();
    expect(screen.getByText(/not a complete ignored-event log/)).toBeInTheDocument();
  });

  it("reports unavailable reads without inventing activity", async () => {
    vi.mocked(fetchCandidates).mockResolvedValue({ ok: false, reason: "UNAVAILABLE" });
    vi.mocked(fetchEarlyRadar).mockResolvedValue({ ok: false, reason: "UNAUTHORIZED" });
    vi.mocked(fetchOperations).mockResolvedValue({ ok: false, reason: "UNAVAILABLE" });
    vi.mocked(fetchRuntimeSettings).mockResolvedValue({ ok: false, reason: "UNAVAILABLE" });
    render(await ScanMonitorPage());
    expect(screen.getByText(/Activity cannot be confirmed/)).toBeInTheDocument();
    expect(screen.getByText(/Candidates unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/Early decisions unavailable/)).toBeInTheDocument();
  });
});
