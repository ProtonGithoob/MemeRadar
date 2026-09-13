import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProvidersDashboard } from "./providers";
import type { ProviderHealthRecord, ReadPage, ReadResult } from "../lib/read-api";

const healthy: ProviderHealthRecord = {
  provider: "fixture-market",
  providerId: "fixture-market",
  displayName: "Fixture Market",
  chains: ["solana"],
  capabilities: ["market_data"],
  required: true,
  enabled: true,
  settingKeys: ["fixture_market_url"],
  capability: "market_data",
  capabilityStatus: "AVAILABLE",
  runtimeHealth: "HEALTHY",
  state: "HEALTHY",
  checkedAt: "2026-08-31T12:00:00.000Z",
  latencyMs: 42,
  quota: { remaining: 90, limit: 100 },
  freshnessState: "FRESH",
  errorClass: null,
  consecutiveFailures: 0
};

const degraded: ProviderHealthRecord = {
  ...healthy,
  provider: "fixture-social",
  capability: "social_data",
  state: "DEGRADED",
  latencyMs: null,
  quota: {},
  freshnessState: "STALE",
  errorClass: "rate_limited",
  consecutiveFailures: 2
};

function result(items: ProviderHealthRecord[]): ReadResult<ReadPage<ProviderHealthRecord>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("ProvidersDashboard", () => {
  afterEach(() => cleanup());

  it("preserves provider health order and exposes degradation honestly", () => {
    render(<ProvidersDashboard result={result([healthy, degraded])} />);

    expect(screen.getByRole("heading", { name: "Provider health" })).toBeInTheDocument();
    expect(screen.getByText("fixture-market")).toBeInTheDocument();
    expect(screen.getByText("fixture-social")).toBeInTheDocument();
    expect(screen.getByText("HEALTHY")).toBeInTheDocument();
    expect(screen.getAllByText(/CAPABILITY\s+AVAILABLE/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/RUNTIME HEALTH\s+HEALTHY/).length).toBeGreaterThan(0);
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.getByText(/ERROR rate_limited/)).toBeInTheDocument();
    expect(screen.getByText("90 remaining / 100 limit")).toBeInTheDocument();
  });

  it("does not infer provider health from an empty or failed read", () => {
    const { rerender } = render(<ProvidersDashboard result={result([])} />);
    expect(screen.getByText("NO PROVIDER HEALTH EVIDENCE")).toBeInTheDocument();
    rerender(<ProvidersDashboard result={{ ok: false, reason: "NOT_CONFIGURED" }} />);
    expect(screen.getByText("PROVIDER HEALTH NOT CONFIGURED")).toBeInTheDocument();
  });

  it("uses canonical setting keys without substring matching or truncation", () => {
    render(<ProvidersDashboard
      result={result([{ ...healthy, settingKeys: ["fixture_market_url", "fixture_market_key"] }])}
      settings={{ ok: true, data: {
        apiVersion: "runtime-settings-v1",
        asOf: "2026-08-31T12:00:00.000Z",
        groups: { providers: [
          { key: "fixture_market_url", value: "https://fixture", state: "CONFIGURED", secret: false },
          { key: "fixture_market_key", value: null, state: "NOT_CONFIGURED", secret: true },
          { key: "fixture_market_url_backup", value: "wrong", state: "CONFIGURED", secret: false }
        ] },
        protectedModes: { analysisOnly: true, paperTrading: true, manualExecution: false, autoExecution: false },
        executionEligible: false
      } }}
    />);

    expect(screen.getByText(/fixture_market_url=https:\/\/fixture/)).toBeInTheDocument();
    expect(screen.getByText(/fixture_market_key=NOT CONFIGURED/)).toBeInTheDocument();
    expect(screen.queryByText(/fixture_market_url_backup/)).not.toBeInTheDocument();
  });
});
