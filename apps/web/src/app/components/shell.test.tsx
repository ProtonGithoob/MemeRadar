import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkstationShell } from "./shell";
import type { OperationsRecord } from "../lib/read-api";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/radar",
  useRouter: () => ({ push })
}));

const operations: OperationsRecord = {
  schemaVersion: "operations-overview-v1",
  asOf: "2026-09-05T12:00:00.000Z",
  overallState: "DEGRADED",
  sloState: "UNVERIFIED",
  policyVersion: "ops-v1",
  measurementMethod: "synthetic",
  providers: [
    {
      provider: "birdeye",
      capability: "market",
      state: "DEGRADED",
      sloState: "UNVERIFIED",
      checkedAt: "2026-09-05T12:00:00.000Z",
      latencyMs: null,
      freshnessState: null,
      quotaLimit: null,
      quotaRemaining: null,
      quotaResetAt: null,
      costTodayUsd: null,
      costBudgetUsd: null,
      errorClass: null,
      consecutiveFailures: 0,
      reasonCodes: []
    }
  ],
  alerts: [],
  metrics: {},
  earlyDetection: {},
  modes: { analysisOnly: true, paperTrading: true, manualExecution: false, autoExecution: false },
  executionEligible: false
};

describe("WorkstationShell", () => {
  afterEach(() => {
    cleanup();
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("renders the brand, system status, protected modes and navigation", () => {
    render(<WorkstationShell operations={{ ok: true, data: operations }}><div /></WorkstationShell>);

    expect(screen.getByRole("link", { name: "MemeRadar" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("status", { name: "STACK: DEGRADED" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "PROVIDERS: 1 DEGRADED" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "ANALYSIS ONLY: ON" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "PAPER TRADING: ON" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "EXECUTION: LOCKED" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Operator sections" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Radar" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });

  it("keeps unknown system status explicit when operations are unavailable", () => {
    render(<WorkstationShell operations={{ ok: false, reason: "UNAVAILABLE" }}><div /></WorkstationShell>);
    expect(screen.getByRole("status", { name: "STACK: UNKNOWN" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "PROVIDERS: UNKNOWN" })).toBeInTheDocument();
  });

  it("routes search through the backend resolver and rejects unknown shapes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("22222222")) {
        return { ok: true, json: async () => ({ kind: "TOKEN", route: "/tokens/22222222-2222-4222-8222-222222222222", reason_codes: [] }) };
      }
      if (url.includes("Vote111")) {
        return { ok: true, json: async () => ({ kind: "WALLET", route: "/wallets/Vote111111111111111111111111111111111111111", reason_codes: [] }) };
      }
      return { ok: true, json: async () => ({ kind: "NOT_FOUND", route: null, reason_codes: ["NOT_FOUND"] }) };
    }));
    render(<WorkstationShell operations={{ ok: false, reason: "UNAVAILABLE" }}><div /></WorkstationShell>);
    const input = screen.getByLabelText("Search token, wallet, caller, or chain-qualified address");
    const go = screen.getByRole("button", { name: "GO" });

    fireEvent.change(input, { target: { value: "22222222-2222-4222-8222-222222222222" } });
    fireEvent.click(go);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/tokens/22222222-2222-4222-8222-222222222222"));

    fireEvent.change(input, { target: { value: "Vote111111111111111111111111111111111111111" } });
    fireEvent.click(go);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/wallets/Vote111111111111111111111111111111111111111"));

    fireEvent.change(input, { target: { value: "not-a-target" } });
    fireEvent.click(go);
    await waitFor(() => expect(push).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
