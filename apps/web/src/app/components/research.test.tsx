import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ResearchDashboard, DEFAULT_RESEARCH_GATE } from "./research";

describe("ResearchDashboard", () => {
  afterEach(() => cleanup());

  it("renders product research gate and unmistakably marks synthetic vs live alpha status", () => {
    render(<ResearchDashboard data={DEFAULT_RESEARCH_GATE} />);

    expect(screen.getByRole("heading", { name: "Product Research Gate & Strategy Calibration" })).toBeInTheDocument();
    expect(screen.getByText("REAL_WORLD_ALPHA_NOT_YET_PROVEN")).toBeInTheDocument();
    expect(screen.getByText("EVIDENCE CLASS TAXONOMY")).toBeInTheDocument();
    expect(screen.getAllByText("SYNTHETIC_FIXTURE")).not.toHaveLength(0);
    expect(screen.getByText("11 Product Research Gate Questions")).toBeInTheDocument();
    expect(screen.getByText(/Can future 20x\/50x\/100x winners be detected/)).toBeInTheDocument();
  });
});
