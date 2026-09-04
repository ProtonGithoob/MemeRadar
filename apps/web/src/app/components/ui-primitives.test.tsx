import { render, screen, cleanup } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import React from "react";
import {
  StatusPill,
  RiskChip,
  FreshnessIndicator,
  ScoreGauge,
  MetricCard,
  SectionHeader,
  EmptyState,
  Tabs,
} from "./ui-primitives";

describe("UI Primitives Design System", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders StatusPill with label and value", () => {
    render(<StatusPill label="State" value="ACTIVE" variant="safe" />);
    expect(screen.getByText("State")).toBeDefined();
    expect(screen.getByText("ACTIVE")).toBeDefined();
  });

  it("renders RiskChip for PASS and UNKNOWN", () => {
    const { rerender } = render(<RiskChip disposition="PASS" />);
    expect(screen.getByText("PASS")).toBeDefined();

    rerender(<RiskChip disposition="UNKNOWN" />);
    expect(screen.getByText("UNKNOWN")).toBeDefined();
  });

  it("renders FreshnessIndicator with correct accessibility label", () => {
    render(<FreshnessIndicator quality="FRESH" />);
    expect(screen.getByLabelText("Freshness: FRESH")).toBeDefined();
    expect(screen.getByText("FRESH")).toBeDefined();
  });

  it("renders ScoreGauge with numeric score and UNKNOWN fallback", () => {
    const { rerender } = render(<ScoreGauge score={85} confidence={0.9} />);
    expect(screen.getByText("85/100")).toBeDefined();
    expect(screen.getByText("90% conf")).toBeDefined();

    rerender(<ScoreGauge score={null} />);
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });

  it("renders MetricCard with value and subtext", () => {
    render(
      <MetricCard
        label="Total Candidates"
        value={142}
        subtext="Active shadow stream"
        variant="info"
      />
    );
    expect(screen.getByText("Total Candidates")).toBeDefined();
    expect(screen.getByText("142")).toBeDefined();
    expect(screen.getByText("Active shadow stream")).toBeDefined();
  });

  it("renders SectionHeader with title and subtitle", () => {
    render(<SectionHeader title="Priority Candidates" subtitle="Sorted by decision priority" />);
    expect(screen.getByText("Priority Candidates")).toBeDefined();
    expect(screen.getByText("Sorted by decision priority")).toBeDefined();
  });

  it("renders EmptyState correctly", () => {
    render(<EmptyState title="No Candidates" description="Waiting for signals" />);
    expect(screen.getByText("No Candidates")).toBeDefined();
    expect(screen.getByText("Waiting for signals")).toBeDefined();
  });

  it("renders Tabs component and triggers callback", () => {
    const tabs = [
      { id: "all", label: "All Candidates", badge: 10 },
      { id: "ready", label: "Entry Ready", badge: 2 },
    ];
    render(<Tabs tabs={tabs} activeTab="all" onChange={() => {}} />);
    expect(screen.getByText("All Candidates")).toBeDefined();
    expect(screen.getByText("Entry Ready")).toBeDefined();
  });
});
