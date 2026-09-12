import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SettingsDashboard, validateRuntimeSettingDraft } from "./settings";
import type {
  ControlConfigRecord,
  ControlStateRecord,
  RuntimeSettingsRecord,
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

const runtimeSettings: RuntimeSettingsRecord = {
  apiVersion: "runtime-settings-v1",
  asOf: "2026-09-07T12:00:00.000Z",
  groups: {
    providers: [
      { key: "market_data_provider", value: "dexscreener", state: "CONFIGURED", secret: false },
      { key: "decision_entry_ready_threshold", value: 85, state: "CONFIGURED", secret: false, decisionAffecting: true },
      { key: "madeonsol_enabled", value: false, state: "DEFAULTED", secret: false },
      { key: "madeonsol_api_key", value: null, state: "UNCONFIGURED_OPTIONAL", configuredState: "NOT_CONFIGURED", secret: true },
      { key: "madeonsol_base_url", value: "https://madeonsol.com/api/v1", state: "DEFAULTED", secret: false }
    ],
    chains: [{ key: "enabled_chains", value: "solana,bnb,robinhood", state: "CONFIGURED", secret: false }],
    telegram: [{ key: "bot_token", value: null, state: "UNCONFIGURED_OPTIONAL", secret: true }],
    x: [{ key: "enabled", value: false, state: "DEFAULTED", secret: false }],
    social: [],
    website: [{ key: "url", value: "https://memeradar.example", state: "CONFIGURED", secret: false }],
    wallet: [],
    security: [],
    llm: [{ key: "provider", value: "ollama", state: "DEFAULTED", secret: false }]
  },
  protectedModes: state.protectedModes,
  executionEligible: false
};

describe("SettingsDashboard", () => {
  afterEach(() => cleanup());

  it("shows protected modes, validated config and explicit role gates", () => {
    render(
      <SettingsDashboard
        stateResult={{ ok: true, data: state }}
        configResult={{ ok: true, data: config }}
        runtimeSettingsResult={{ ok: true, data: runtimeSettings }}
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
    expect(screen.getByText("MADEONSOL ENABLED")).toBeInTheDocument();
    expect(screen.getByText("MADEONSOL BASE URL")).toBeInTheDocument();
    expect(screen.getByText("MADEONSOL API KEY")).toBeInTheDocument();
    expect(screen.getByText("NOT_CONFIGURED")).toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("renders dynamic runtime categories without displaying secret values", () => {
    render(
      <SettingsDashboard
        stateResult={{ ok: true, data: state }}
        configResult={{ ok: true, data: config }}
        runtimeSettingsResult={{ ok: true, data: runtimeSettings }}
      />
    );

    expect(screen.getByRole("heading", { name: "Runtime configuration" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "PROVIDERS" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "CHAINS" }));
    expect(screen.getByText("solana,bnb,robinhood")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "TELEGRAM" }));
    expect(screen.getByText("NOT CONFIGURED")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "WEBSITE" }));
    expect(screen.getByText("https://memeradar.example")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "LLM" }));
    expect(screen.getByText("ollama")).toBeInTheDocument();
  });

  it("keeps state and config failures independently visible", () => {
    render(
      <SettingsDashboard
        stateResult={{ ok: false, reason: "UNAUTHORIZED" }}
        configResult={{ ok: false, reason: "NOT_CONFIGURED" }}
        runtimeSettingsResult={{ ok: false, reason: "UNAVAILABLE" }}
      />
    );
    expect(screen.getByText("CONTROL STATE AUTHORIZATION UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("CONTROL CONFIG NOT CONFIGURED")).toBeInTheDocument();
    expect(screen.getByText("RUNTIME SETTINGS UNAVAILABLE")).toBeInTheDocument();
  });

  it("validates numeric drafts before parsing and preserves explicit zero", () => {
    const item = {
      key: "decision_threshold",
      type: "integer",
      value: 5,
      state: "CONFIGURED" as const,
      secret: false,
      minimum: 0,
      maximum: 10
    };
    expect(validateRuntimeSettingDraft(item, "")).toEqual({ ok: false, reason: "REQUIRED" });
    expect(validateRuntimeSettingDraft(item, "nope")).toEqual({ ok: false, reason: "INVALID_NUMBER" });
    expect(validateRuntimeSettingDraft(item, "11")).toEqual({ ok: false, reason: "ABOVE_MAXIMUM" });
    expect(validateRuntimeSettingDraft(item, "0")).toEqual({ ok: true, value: 0 });
  });
});
