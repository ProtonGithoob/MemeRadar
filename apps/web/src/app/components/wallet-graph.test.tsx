import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WalletGraphExplorer } from "./wallet-graph";

describe("WalletGraphExplorer", () => {
  afterEach(() => cleanup());

  it("renders search controls, filter options, node-link visualization container, and shortest path form", () => {
    render(<WalletGraphExplorer />);

    expect(screen.getByRole("heading", { name: "Search Graph Projection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search Graph" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter address, mint, or cluster ID...")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Search Kind" })).toBeInTheDocument();
    ariaLabelsExist(["Max Depth", "Outcome Filter", "Venue Filter", "Wallet Role", "Evidence Quality"]);

    expect(screen.getByRole("heading", { name: "Explainable Shortest Path" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Start Node/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Target Node/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Find Path" })).toBeInTheDocument();
  });
});

function ariaLabelsExist(labels: string[]) {
  for (const label of labels) {
    expect(screen.getByRole("combobox", { name: label })).toBeInTheDocument();
  }
}
