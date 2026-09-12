import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ReadinessDashboard } from "./readiness";
import type { ReadinessRecord } from "../lib/read-api";

const readiness: ReadinessRecord = {
  asOf: "2026-09-12T12:00:00.000Z",
  classification: "NOT_PRODUCTION_READY",
  gates: [{
    id: "PR-1",
    name: "Engineering/release",
    status: "PARTIAL",
    evidenceCounts: { localQualityGates: 1 },
    blockers: ["HOSTED_CI_BLOCKED_EXTERNAL"],
    nextAction: "Collect hosted evidence"
  }],
  hostedCi: { status: "BLOCKED_EXTERNAL", executed_steps: 0 },
  providerRuntimeBlockers: ["REAL_PROVIDER_ACCESS_UNAVAILABLE"],
  protectedModes: {
    analysisOnly: true,
    paperTrading: true,
    manualExecution: false,
    autoExecution: false
  },
  liveMoney: { status: "OUT_OF_SCOPE", execution_eligible: false },
  alphaValidation: {
    status: "INSUFFICIENT_SAMPLES",
    reasonCodes: ["MADEONSOL_REAL_OBSERVATIONS_REQUIRED"],
    realObservationCount: 0,
    uniqueRobinhoodTokenCount: 0,
    callerKolObservationCount: 0,
    smartWalletObservationCount: 0,
    deployerObservationCount: 0,
    holderDistributionObservationCount: 0,
    bundleLpSecurityObservationCount: 0,
    firstRealObservation: null,
    latestRealObservation: null,
    rateLimitCount: 0,
    errorCount: 0,
    labeledWinnerCount: 0,
    labeledRugCount: 0
  }
};

describe("ReadinessDashboard", () => {
  afterEach(() => cleanup());

  it("separates alpha evidence readiness from engineering and production gates", () => {
    render(<ReadinessDashboard result={{ ok: true, data: readiness }} />);

    expect(screen.getByText("ALPHA VALIDATION / LIVE SHADOW")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alpha evidence readiness" })).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT_SAMPLES")).toBeInTheDocument();
    expect(screen.getByText("REAL OBSERVATIONS")).toBeInTheDocument();
    expect(screen.getByText(/Provider health does not validate alpha or authorize execution\./)).toBeInTheDocument();
    expect(screen.getByText("NOT_PRODUCTION_READY · AS OF 2026-09-12T12:00:00.000Z")).toBeInTheDocument();
  });
});
