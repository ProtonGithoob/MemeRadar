import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CommandCenter } from "./components/command-center";

describe("command center", () => {
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
});
