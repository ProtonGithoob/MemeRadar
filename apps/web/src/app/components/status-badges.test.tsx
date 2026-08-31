import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ConnectionBadge,
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./status-badges";

describe("dashboard status primitives", () => {
  it("renders a bounded score with a visible numeric meaning", () => {
    render(<ScoreBadge value={84} />);

    expect(screen.getByRole("status", { name: "Score: 84 out of 100" })).toHaveAttribute(
      "data-state",
      "high"
    );
    expect(screen.getByText("SCORE 84 / 100")).toBeInTheDocument();
  });

  it("renders missing scores as unavailable instead of inventing a value", () => {
    render(<ScoreBadge value={null} />);

    expect(screen.getByRole("status", { name: "Score unavailable" })).toHaveAttribute(
      "data-state",
      "unavailable"
    );
    expect(screen.getByText("SCORE UNAVAILABLE")).toBeInTheDocument();
  });

  it("keeps unknown risk and stale freshness visibly non-safe", () => {
    render(
      <div>
        <RiskBadge value="UNKNOWN" />
        <FreshnessBadge value="STALE" />
      </div>
    );

    expect(screen.getByRole("status", { name: "Risk: UNKNOWN (not safe)" })).toHaveAttribute(
      "data-state",
      "unknown"
    );
    expect(screen.getByRole("status", { name: "Freshness: STALE (not current)" })).toHaveAttribute(
      "data-state",
      "stale"
    );
  });

  it("renders paper and realtime states with text independent of color", () => {
    render(
      <div>
        <SafetyBadge label="PAPER TRADING" value="ENABLED" tone="paper" />
        <ConnectionBadge state="CONNECTED" />
      </div>
    );

    expect(screen.getByRole("status", { name: "PAPER TRADING: ENABLED" })).toHaveAttribute(
      "data-state",
      "paper"
    );
    expect(screen.getByRole("status", { name: "Realtime stream: CONNECTED" })).toHaveAttribute(
      "data-state",
      "connected"
    );
  });
});
