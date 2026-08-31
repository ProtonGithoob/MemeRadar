import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "./theme-toggle";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  localStorage.clear();
});

describe("ThemeToggle", () => {
  it("cycles local system, light and dark preferences without network state", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: /theme: system/i });

    expect(button).toHaveTextContent("THEME SYSTEM");
    fireEvent.click(button);
    expect(screen.getByRole("button", { name: /theme: light/i })).toHaveTextContent("THEME LIGHT");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(localStorage.getItem("memeradar-theme")).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: /theme: light/i }));
    expect(screen.getByRole("button", { name: /theme: dark/i })).toHaveTextContent("THEME DARK");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    fireEvent.click(screen.getByRole("button", { name: /theme: dark/i }));
    expect(screen.getByRole("button", { name: /theme: system/i })).toHaveTextContent("THEME SYSTEM");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(localStorage.getItem("memeradar-theme")).toBeNull();
  });
});
