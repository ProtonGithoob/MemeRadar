import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OperationsDashboard } from "./operations";
import type { OperationsRecord, ReadResult } from "../lib/read-api";

const overview: OperationsRecord = {
  schemaVersion: "operations-overview-v1",
  asOf: "2026-09-01T06:00:00.000Z",
  overallState: "DEGRADED",
  sloState: "UNVERIFIED",
  policyVersion: "provider-slo-v1",
  measurementMethod: "synthetic_local",
  providers: [{
    provider: "fixture",
    capability: "market_data",
    state: "DEGRADED",
    sloState: "UNVERIFIED",
    checkedAt: "2026-09-01T06:00:00.000Z",
    latencyMs: null,
    freshnessState: "STALE",
    quotaLimit: 100,
    quotaRemaining: 4,
    quotaResetAt: null,
    costTodayUsd: 10,
    costBudgetUsd: 10,
    errorClass: "rate_limited",
    consecutiveFailures: 2,
    reasonCodes: ["STALE_EVIDENCE"]
  }],
  alerts: [{
    code: "PROVIDER_DEGRADED",
    severity: "WARNING",
    dedupeKey: "operations:provider_degraded:fixture:market_data",
    provider: "fixture",
    capability: "market_data",
    message: "Provider evidence is degraded",
    observedAt: "2026-09-01T06:00:00.000Z",
    reasonCodes: ["STALE_EVIDENCE"]
  }],
  metrics: { counters: { queue_saturations: 0 } },
  modes: {
    analysisOnly: true,
    paperTrading: true,
    manualExecution: false,
    autoExecution: false
  },
  executionEligible: false
};

function result(value: OperationsRecord): ReadResult<OperationsRecord> {
  return { ok: true, data: value };
}

describe("OperationsDashboard", () => {
  afterEach(() => cleanup());

  it("exposes degradation, unverified SLO evidence, quota pressure and alerts", () => {
    render(<OperationsDashboard result={result(overview)} />);

    expect(screen.getByRole("heading", { name: "Operations" })).toBeInTheDocument();
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
    expect(screen.getByText("UNVERIFIED")).toBeInTheDocument();
    expect(screen.getByText("fixture")).toBeInTheDocument();
    expect(screen.getByText("4 remaining / 100 limit")).toBeInTheDocument();
    expect(screen.getByText("$10.00 / $10.00 budget")).toBeInTheDocument();
    expect(screen.getByText("PROVIDER_DEGRADED")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "MODE: ANALYSIS ONLY" })).toBeInTheDocument();
  });

  it("does not infer health from an empty or failed operations read", () => {
    const { rerender } = render(
      <OperationsDashboard result={result({ ...overview, providers: [], alerts: [], overallState: "UNKNOWN" })} />
    );
    expect(screen.getByText("NO OPERATIONAL PROVIDER EVIDENCE")).toBeInTheDocument();
    rerender(<OperationsDashboard result={{ ok: false, reason: "UNAVAILABLE" }} />);
    expect(screen.getByText("OPERATIONS OBSERVABILITY UNAVAILABLE")).toBeInTheDocument();
  });
});
