import { expect, test, type Page } from "@playwright/test";

async function expectProtectedShell(page: Page) {
  await expect(page.getByText(/READ ONLY MODE|ANALYSIS_ONLY=true/i).first()).toBeVisible();
}

test("operator shell exposes the read-only sections and protected modes", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "MemeRadar" })).toBeVisible();
  await expectProtectedShell(page);

  // Check top workstation navigation links inside nav bar
  const nav = page.locator("header nav");
  await expect(nav.getByRole("link", { name: "Radar" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Ultra Early" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Positions" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Wallet Graph" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Providers & Shadow" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Research" })).toBeVisible();

  await expect(page.locator("body")).not.toContainText("MEMERADAR_VIEWER_API_TOKEN");
  await expect(page.locator("body")).not.toContainText("private_key");
});

test("operator intelligence routes render server-side evidence boundaries", async ({ page }) => {
  test.setTimeout(60_000);
  const routes = [
    "/operations",
    "/providers",
    "/positions",
    "/wallet-graph",
    "/research",
    "/audit"
  ];

  for (const path of routes) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expectProtectedShell(page);
    await expect(page.getByRole("button", { name: /execute live|sign transaction|swap live/i })).toHaveCount(0);
  }
});
