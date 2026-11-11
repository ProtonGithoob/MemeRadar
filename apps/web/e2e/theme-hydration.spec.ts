import { expect, test } from "@playwright/test";

test("saved theme hydrates and switches without a React mismatch", async ({ page }) => {
  const hydrationMessages: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /hydration|hydrated/i.test(message.text())) {
      hydrationMessages.push(message.text());
    }
  });
  await page.addInitScript(() => localStorage.setItem("memeradar-theme", "light"));
  await page.goto("/");

  const themeToggle = page.getByRole("button", { name: /theme: light/i });
  await expect(themeToggle).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await themeToggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(hydrationMessages).toEqual([]);
});
