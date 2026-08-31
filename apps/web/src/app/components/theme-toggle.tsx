"use client";

import { useEffect, useSyncExternalStore } from "react";

export const THEME_STORAGE_KEY = "memeradar-theme";
type Theme = "system" | "light" | "dark";

const themes: Theme[] = ["system", "light", "dark"];

function isTheme(value: string | null): value is Theme {
  return value === "system" || value === "light" || value === "dark";
}

function readTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return isTheme(localStorage.getItem(THEME_STORAGE_KEY))
    ? (localStorage.getItem(THEME_STORAGE_KEY) as Theme)
    : "system";
}

function subscribeToTheme(onChange: () => void): () => void {
  window.addEventListener("memeradar-theme-change", onChange);
  return () => window.removeEventListener("memeradar-theme-change", onChange);
}

function applyTheme(theme: Theme): void {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
    return;
  }
  document.documentElement.setAttribute("data-theme", theme);
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, (): Theme => "system");

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function cycleTheme(): void {
    const nextTheme = themes[(themes.indexOf(theme) + 1) % themes.length];
    applyTheme(nextTheme);
    if (nextTheme === "system") {
      localStorage.removeItem(THEME_STORAGE_KEY);
    } else {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    }
    window.dispatchEvent(new Event("memeradar-theme-change"));
  }

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={cycleTheme}
      aria-label={`Theme: ${theme}. Activate to choose the next theme.`}
    >
      <span className="theme-toggle__label">THEME</span>
      {" "}
      <strong>{theme.toUpperCase()}</strong>
    </button>
  );
}
