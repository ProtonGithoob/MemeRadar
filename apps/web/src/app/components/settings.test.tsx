import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SettingsDashboard } from "./settings";
import type {
  ControlConfigRecord,
  ControlStateRecord,
  ReadResult
} from "../lib/read-api";

const state: ControlStateRecord = {
  apiVersion: "control-api-v1",
  analysisPaused: false,
  executionKillSwitch: true,
  version: 2,
  updatedAt: "2026-08-31T12:00:00.000Z",
  updatedBy: "system",
  correlationId: "control-fixture",
  protectedModes: {
    analysisOnly: true,
    paperTrading: true,
    manualExecution: false,
    autoExecution: false
  }
};

const config: ControlConfigRecord = {
  apiVersion: "control-api-v1",
  id: "11111111-1111-4111-8111-111111111111",
  version: "control-config-v1",
  createdAt: "2026-08-31T12:00:00.000Z",
  actor: "system",
  configHash: "sha256:fixture",
  decisionAffecting: true,
  config: {
    alert_max_messages_per_window: 20,
    alert_rate_limit_window_seconds: 60,
    decision_watch_threshold: 40,
    decision_strong_setup_threshold: 75,
    decision_entry_ready_threshold: 85,
    decision_minimum_confidence: 0.6,
    password: "must-not-render"
  }
};

describe("SettingsDashboard", () => {
  afterEach(() => cleanup());

  it("shows protected modes, validated config and explicit role gates", () => {
    render(
      <SettingsDashboard
        stateResult={{ ok: true, data: state }}
        configResult={{ ok: true, data: config }}
      />
    );

    expect(screen.getByRole("heading", { name: "Settings and controls" })).toBeInTheDocument();
    expect(screen.getByText("ANALYSIS ONLY")).toBeInTheDocument();
    expect(screen.getByText("PAPER TRADING")).toBeInTheDocument();
    expect(screen.getByText("MANUAL EXECUTION")).toBeInTheDocument();
    expect(screen.getByText("AUTO EXECUTION")).toBeInTheDocument();
    expect(screen.getByText("EXECUTION KILL SWITCH ACTIVE")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "CONFIGURATION: VALIDATED" })).toBeInTheDocument();
    expect(screen.getByText("VIEWER")).toBeInTheDocument();
    expect(screen.getByText("OPERATOR")).toBeInTheDocument();
    expect(screen.getByText("ADMIN")).toBeInTheDocument();
    expect(screen.getByText("EXECUTION")).toBeInTheDocument();
    expect(screen.getByText("decision_entry_ready_threshold")).toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("keeps state and config failures independently visible", () => {
    render(
      <SettingsDashboard
        stateResult={{ ok: false, reason: "UNAUTHORIZED" }}
        configResult={{ ok: false, reason: "NOT_CONFIGURED" }}
      />
    );
    expect(screen.getByText("CONTROL STATE AUTHORIZATION UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("CONTROL CONFIG NOT CONFIGURED")).toBeInTheDocument();
  });
});
