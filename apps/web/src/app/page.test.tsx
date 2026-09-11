import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CommandCenter } from "./components/command-center";
import type { OperationsRecord } from "./lib/read-api";

const unknownOperations: OperationsRecord = {
  schemaVersion: "operations-overview-v1",
  asOf: "2026-09-11T00:00:00.000Z",
  overallState: "UNKNOWN",
  sloState: "UNVERIFIED",
  policyVersion: "test",
  measurementMethod: "fixture",
  providers: [],
  alerts: [],
  metrics: {},
  earlyDetection: {},
  modes: { analysisOnly: true, paperTrading: true, manualExecution: false, autoExecution: false },
  executionEligible: false
};

describe("command center", () => {
  afterEach(() => cleanup());

  it("keeps unavailable evidence explicit and never fabricates candidates", () => {
    render(
      <CommandCenter
        earlyResult={{ ok: false, reason: "NOT_CONFIGURED" }}
        operations={{ ok: false, reason: "NOT_CONFIGURED" }}
        result={{ ok: false, reason: "NOT_CONFIGURED" }}
      />
    );

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getAllByText("READ API NOT CONFIGURED").length).toBeGreaterThan(0);
    expect(screen.getByText("NO LIVE ORDERS")).toBeInTheDocument();
  });

  it("does not render READY for an empty provider projection", () => {
    render(
      <CommandCenter
        earlyResult={{ ok: false, reason: "NOT_CONFIGURED" }}
        operations={{ ok: true, data: unknownOperations }}
        result={{ ok: false, reason: "NOT_CONFIGURED" }}
      />
    );

    expect(screen.getByText("PROVIDERS").parentElement).toHaveTextContent("UNKNOWN");
    expect(screen.queryByText("READY")).not.toBeInTheDocument();
  });
});
