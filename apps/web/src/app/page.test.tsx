import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("operator shell", () => {
  it("shows the product identity and protected operating modes", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "MemeRadar" })).toBeInTheDocument();
    expect(screen.getByText("ANALYSIS ONLY")).toBeInTheDocument();
    expect(screen.getByText("PAPER TRADING")).toBeInTheDocument();
    expect(screen.getAllByText("Disabled")).toHaveLength(2);
    expect(screen.getByText("LIVE DATA")).toBeInTheDocument();
    expect(screen.getByText("ADVISORY OUTPUT")).toBeInTheDocument();
    expect(screen.getByText("STREAM DISABLED")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /theme/i })).toBeInTheDocument();
  });
});
