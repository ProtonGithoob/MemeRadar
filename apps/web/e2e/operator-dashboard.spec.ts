import { expect, test, type Page } from "@playwright/test";

const protectedLabels = [
  "ANALYSIS ONLY",
  "PAPER TRADING",
  "MANUAL EXECUTION",
  "AUTO EXECUTION"
];

async function expectProtectedShell(page: Page) {
  for (const label of protectedLabels) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("ADVISORY OUTPUT", { exact: true })).toBeVisible();
  await expect(page.locator(".status-orb").getByText("NO LIVE ORDERS", { exact: true })).toBeVisible();
}

test("operator shell exposes the read-only sections and protected modes", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "MemeRadar" })).toBeVisible();
  await expectProtectedShell(page);

  const navigation = page.getByRole("navigation", { name: "Operator sections" });
  for (const label of ["Radar", "Wallets", "Providers", "Settings", "Audit"]) {
    await expect(navigation.getByRole("link", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.locator("body")).not.toContainText("MEMERADAR_VIEWER_API_TOKEN");
  await expect(page.locator("body")).not.toContainText("private_key");
});

test("operator intelligence routes render server-side evidence boundaries", async ({ page }) => {
  const routes = [
    ["/wallets", "Smart wallets"],
    ["/providers", "Provider health"],
    ["/settings", "Settings and controls"],
    ["/audit", "Audit explorer"]
  ] as const;

  for (const [path, heading] of routes) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expectProtectedShell(page);
    await expect(page.locator("form")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute|sign|submit|save|mutate/i })).toHaveCount(0);
  }
});

test("invalid wallet boundaries fail closed without inventing a record", async ({ page }) => {
  const response = await page.goto("/wallets/not-a-wallet");
  expect(response?.status()).toBe(200);
  await expect(page.getByText("INVALID READ RESPONSE", { exact: true })).toBeVisible();
  await expectProtectedShell(page);
  await expect(page.locator("body")).not.toContainText("UNLABELED WALLET");
});
