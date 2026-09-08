import { expect, test, type Page } from "@playwright/test";

const protectedLabels = ["ANALYSIS ONLY", "PAPER TRADING", "EXECUTION LOCKED"];

async function expectProtectedShell(page: Page) {
  for (const label of protectedLabels) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByRole("link", { name: "MemeRadar" })).toBeVisible();
}

test("workstation shell exposes navigation, search and protected modes", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expectProtectedShell(page);
  await expect(page.getByText("NO LIVE ORDERS", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Search by token UUID or wallet address")).toBeVisible();

  const navigation = page.getByRole("navigation", { name: "Operator sections" });
  for (const label of ["Overview", "Radar", "Ultra Early", "Positions", "Opportunities", "Wallets", "Graph", "Providers", "Operations", "Settings", "Audit"]) {
    await expect(navigation.getByRole("link", { name: label, exact: true })).toBeAttached();
  }
  await expect(page.locator("body")).not.toContainText("MEMERADAR_VIEWER_API_TOKEN");
  await expect(page.locator("body")).not.toContainText("private_key");
});

test("settings and chain opportunity surfaces preserve read-only evidence boundaries", async ({ page }) => {
  const settings = await page.goto("/settings");
  expect(settings?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible();
  for (const label of ["PROVIDERS", "CHAINS", "TELEGRAM", "X", "SOCIAL", "WEBSITE", "WALLET", "SECURITY", "LLM"]) {
    await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.getByText("SECRET VALUE HIDDEN").first()).toBeVisible();
  await expect(page.locator("body")).not.toContainText("runtime-provider-secret");

  const opportunities = await page.goto("/opportunities");
  expect(opportunities?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Chain opportunities" })).toBeVisible();
  await expect(page.getByText("EXECUTION LOCKED", { exact: true }).first()).toBeVisible();
});

test("radar and ultra-early routes render read-only discovery workspaces", async ({ page }) => {
  const radar = await page.goto("/radar");
  expect(radar?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Radar" })).toBeVisible();
  await expectProtectedShell(page);

  const ultraEarly = await page.goto("/ultra-early");
  expect(ultraEarly?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Ultra-Early Detection" })).toBeVisible();
  await expect(
    page.getByText(/Auto execution: LOCKED|NO ULTRA-EARLY CANDIDATES|EARLY RADAR/i).first()
  ).toBeVisible();
  await expectProtectedShell(page);
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

test("settings route renders protected modes without control authority", async ({ page }) => {
  const response = await page.goto("/settings");
  expect(response?.status()).toBe(200);
  for (const label of ["ANALYSIS ONLY", "PAPER TRADING", "MANUAL EXECUTION", "AUTO EXECUTION"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
});

test("invalid wallet boundaries fail closed without inventing a record", async ({ page }) => {
  const response = await page.goto("/wallets/not-a-wallet");
  expect(response?.status()).toBe(200);
  await expect(page.getByText("INVALID READ RESPONSE", { exact: true })).toBeVisible();
  await expectProtectedShell(page);
  await expect(page.locator("body")).not.toContainText("UNLABELED WALLET");
});
