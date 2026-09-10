import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

  it("renders relationship evidence as candidate-only corroboration", async () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        nodes: [
          { id: "cluster:fixture", kind: "ACTOR_CLUSTER", label: "fixture", properties: {}, quality_state: "FRESH", created_at: "2026-09-10T08:00:00.000Z" },
          { id: "wallet:solana:11111111111111111111111111111112", kind: "WALLET", label: "wallet", properties: {}, quality_state: "FRESH", created_at: "2026-09-10T08:00:00.000Z" }
        ],
        edges: [{
          id: "wallet-relationship:fixture",
          from_id: "cluster:fixture",
          to_id: "wallet:solana:11111111111111111111111111111112",
          kind: "RELATIONSHIP_EVIDENCE",
          occurred_at: "2026-09-10T08:00:00.000Z",
          observed_at: "2026-09-10T08:00:00.000Z",
          ingested_at: "2026-09-10T08:00:00.000Z",
          properties: {
            relationship_type: "COMMON_FUNDING",
            dimensions: ["SHARED_FUNDING", "BRIDGE_ORIGIN"],
            confidence: "MEDIUM",
            event_count: 2,
            funding_time_delta_seconds: 3.5,
            candidate_only: true,
            ownership_asserted: false,
            reason_codes: ["RELATIONSHIP_CORROBORATION"],
            evidence_refs: ["funding:1"]
          },
          quality_state: "FRESH",
          reason_codes: []
        }],
        max_depth: 2,
        max_nodes: 50,
        max_edges: 100,
        has_more: false,
        as_of: "2026-09-10T08:00:00.000Z"
      })
    }));
    render(<WalletGraphExplorer />);

    fireEvent.change(screen.getByPlaceholderText("Enter address, mint, or cluster ID..."), {
      target: { value: "11111111111111111111111111111112" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Search Graph" }));

    await waitFor(() => expect(screen.getByLabelText("Relationship evidence details")).toBeInTheDocument());
    expect(screen.getByText("SHARED FUNDING · BRIDGE ORIGIN")).toBeInTheDocument();
    expect(screen.getByText("CANDIDATE ONLY")).toBeInTheDocument();
    expect(screen.getByText("OWNERSHIP ASSERTED: FALSE")).toBeInTheDocument();
    expect(screen.getByText("RELATIONSHIP_CORROBORATION")).toBeInTheDocument();
  });
});

function ariaLabelsExist(labels: string[]) {
  for (const label of labels) {
    expect(screen.getByRole("combobox", { name: label })).toBeInTheDocument();
  }
}
