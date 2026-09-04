import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AuditDashboard } from "./audit";
import type {
  AuditEventRecord,
  ConfigVersionRecord,
  ReadPage,
  ReadResult
} from "../lib/read-api";

const audit: AuditEventRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  actor: "operator",
  action: "control.analysis_pause",
  target: "analysis",
  occurredAt: "2026-08-31T12:00:00.000Z",
  correlationId: "corr-fixture",
  before: { analysis_paused: false },
  after: { analysis_paused: true, password: "must-not-render" }
};

const config: ConfigVersionRecord = {
  id: "22222222-2222-4222-8222-222222222222",
  version: "control-config-v1",
  createdAt: "2026-08-31T12:01:00.000Z",
  actor: "admin",
  configHash: "sha256:fixture",
  decisionAffecting: true,
  config: { decision_entry_ready_threshold: 85, api_key: "must-not-render" }
};

function page<T>(items: T[]): ReadResult<ReadPage<T>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("AuditDashboard", () => {
  afterEach(() => cleanup());

  it("preserves audit/config order and renders only allow-listed values", () => {
    render(<AuditDashboard auditResult={page([audit])} configResult={page([config])} />);

    expect(screen.getByRole("heading", { name: /Audit Explorer/i })).toBeInTheDocument();
    expect(screen.getByText("control.analysis_pause")).toBeInTheDocument();
    expect(screen.getByText(/ACTOR operator/)).toBeInTheDocument();
    expect(screen.getByText("decision_entry_ready_threshold")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
  });

  it("keeps audit and config failures separate", () => {
    render(
      <AuditDashboard
        auditResult={{ ok: false, reason: "UNAVAILABLE" }}
        configResult={page([])}
      />
    );
    expect(screen.getByText("AUDIT EVENTS UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("NO CONFIGURATION HISTORY")).toBeInTheDocument();
  });
});
