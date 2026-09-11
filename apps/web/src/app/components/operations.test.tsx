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
  metrics: { counters: {
    queue_saturations: 0,
    gaps_detected: 2,
    backfill_retries: 3,
    verification_failures: 1
  } },
  earlyDetection: {
    measurement_method: "synthetic_local",
    evidence_class: "SYNTHETIC",
    counters: { candidates_detected: 3, entry_ready: 1, shadow_fills: 1 },
    rates: { entry_ready_rate: 0.333333, shadow_fill_rate: 0.333333 },
    latencies: {
      first_seen_to_decision_ms: {
        SYNTHETIC: { p50_ms: 42, p95_ms: 48, p99_ms: 48 }
      }
    },
    modes: {
      analysis_only: true,
      paper_trading: true,
      manual_execution: false,
      auto_execution: false
    }
  },
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
    expect(screen.getByText("Ultra-early detection")).toBeInTheDocument();
    expect(screen.getByText("SYNTHETIC / synthetic_local")).toBeInTheDocument();
    expect(screen.getByText("42 ms p50 / 48 ms p95")).toBeInTheDocument();
    expect(screen.getByText("STREAM GAPS").parentElement).toHaveTextContent("2");
    expect(screen.getByText("BACKFILL RETRIES").parentElement).toHaveTextContent("3");
    expect(screen.getByText("VERIFICATION FAILURES").parentElement).toHaveTextContent("1");
    expect(screen.getByText("AUTO EXECUTION: LOCKED")).toBeInTheDocument();
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

  it("keeps missing counters UNKNOWN while preserving explicit zero", () => {
    render(
      <OperationsDashboard result={result({
        ...overview,
        metrics: { counters: { queue_saturations: 0 } },
        earlyDetection: {}
      })} />
    );

    expect(screen.getByText("QUEUE SATURATION").parentElement).toHaveTextContent("0");
    expect(screen.getByText("OUTBOX DEAD LETTERS").parentElement).toHaveTextContent("UNKNOWN");
    expect(screen.getByText("CANDIDATES / ENTRY READY").parentElement).toHaveTextContent("UNKNOWN / UNKNOWN");
  });
});
