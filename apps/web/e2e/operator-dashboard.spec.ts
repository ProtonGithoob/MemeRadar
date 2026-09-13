import { expect, test, type Page } from "@playwright/test";

const hasApi = Boolean(
  (process.env.MEMERADAR_E2E_API_BASE_URL ?? process.env.MEMERADAR_API_BASE_URL)?.trim()
);
const hasViewerAuth = Boolean(
  (process.env.MEMERADAR_E2E_VIEWER_API_TOKEN ?? process.env.MEMERADAR_VIEWER_API_TOKEN)?.trim()
);
const hasAdminAuth = Boolean(
  (process.env.MEMERADAR_E2E_ADMIN_API_TOKEN ?? process.env.MEMERADAR_ADMIN_API_TOKEN)?.trim()
);
const authenticatedRead = hasApi && hasViewerAuth;

async function expectProtectedShell(page: Page) {
  const expected = authenticatedRead
    ? ["ANALYSIS ONLY: ON", "PAPER TRADING: ON", "EXECUTION: LOCKED"]
    : ["ANALYSIS ONLY: UNKNOWN", "PAPER TRADING: UNKNOWN", "EXECUTION: UNKNOWN"];
  const shellModes = page.locator(".ws-topbar__actions");
  for (const label of expected) await expect(shellModes.getByRole("status", { name: label })).toBeVisible();
  await expect(page.getByRole("link", { name: "MemeRadar" })).toBeVisible();
}

test("workstation shell exposes navigation, search and protected modes", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expectProtectedShell(page);
  await expect(page.getByText("NO LIVE ORDERS", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Search token, wallet, caller, or chain-qualified address")).toBeVisible();

  const navigation = page.getByRole("navigation", { name: "Operator sections" });
  for (const label of ["Overview", "Radar", "Ultra Early", "Positions", "Opportunities", "Wallets", "Callers", "Graph", "Providers", "Operations", "Readiness", "Settings", "Audit"]) {
    await expect(navigation.getByRole("link", { name: label, exact: true })).toBeAttached();
  }
  await expect(page.locator("body")).not.toContainText("MEMERADAR_VIEWER_API_TOKEN");
  await expect(page.locator("body")).not.toContainText("private_key");
});

test("settings and chain opportunity surfaces preserve evidence boundaries", async ({ page }) => {
  const settings = await page.goto("/settings");
  expect(settings?.status()).toBe(200);
  if (authenticatedRead) {
    await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible();
    await expect(page.getByRole("tablist", { name: "Runtime setting categories" })).toBeVisible();
    await expect(page.getByRole("tab").first()).toBeVisible();
    if (hasAdminAuth) {
      await expect(page.getByRole("button", { name: "SAVE CHANGED SETTINGS" })).toBeVisible();
    } else {
      await expect(page.getByRole("button", { name: "SAVE CHANGED SETTINGS" })).toHaveCount(0);
    }
  } else {
    await expect(page.getByText(/RUNTIME SETTINGS (NOT CONFIGURED|AUTHORIZATION UNAVAILABLE|UNAVAILABLE)/)).toBeVisible();
    await expect(page.getByRole("button", { name: "SAVE CHANGED SETTINGS" })).toHaveCount(0);
  }
  await expect(page.locator("body")).not.toContainText("runtime-provider-secret");

  const opportunities = await page.goto("/opportunities");
  expect(opportunities?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Chain opportunities" })).toBeVisible();
  await expect(page.getByRole("status", { name: /EXECUTION: (LOCKED|UNKNOWN)/ })).toBeVisible();
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
    ["/readiness", "Production readiness"],
    ["/audit", "Audit explorer"]
  ] as const;

  for (const [path, heading] of routes) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    if (path === "/readiness" && !authenticatedRead) {
      await expect(page.getByText(/READINESS (NOT CONFIGURED|AUTHORIZATION UNAVAILABLE|UNAVAILABLE)/).first()).toBeVisible();
    } else {
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    }
    await expectProtectedShell(page);
    await expect(page.getByRole("button", { name: /execute|sign|submit|mutate/i })).toHaveCount(0);
  }
});

test("settings route renders protected modes without browser control authority", async ({ page }) => {
  const response = await page.goto("/settings");
  expect(response?.status()).toBe(200);
  for (const label of ["ANALYSIS ONLY", "PAPER TRADING", "MANUAL EXECUTION", "AUTO EXECUTION"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
});

test("missing server credentials remain an explicit acceptance failure state", async ({ page }) => {
  test.skip(authenticatedRead, "authenticated server gateway is configured");
  const response = await page.goto("/settings");
  expect(response?.status()).toBe(200);
  await expect(page.getByText(/RUNTIME SETTINGS (NOT CONFIGURED|AUTHORIZATION UNAVAILABLE|UNAVAILABLE)/)).toBeVisible();
  await expect(page.getByRole("button", { name: "SAVE CHANGED SETTINGS" })).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/MEMERADAR_[A-Z_]+TOKEN|private_key|runtime-provider-secret/i);
});

test("authenticated admin settings mutation journey is available through server configuration", async ({ page }, testInfo) => {
  test.skip(!hasAdminAuth || !authenticatedRead, "test-only admin and viewer credentials are not configured");
  test.skip(testInfo.project.name !== "desktop", "run the stateful mutation once; other viewports cover the form");
  const response = await page.goto("/settings");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("button", { name: "SAVE CHANGED SETTINGS" })).toBeVisible();
  await expect(page.getByLabel("Audit reason")).toBeVisible();
  await page.getByRole("tab", { name: "ALERTS" }).click();
  const alertLimit = page.getByLabel("ALERT MAX MESSAGES PER WINDOW");
  const current = Number(await alertLimit.inputValue());
  const updated = String(current >= 1000 ? current - 1 : current + 1);
  await alertLimit.fill(updated);
  await page.getByLabel("Audit reason").fill("browser acceptance runtime settings");
  const mutation = page.waitForResponse((result) =>
    result.url().endsWith("/api/control/runtime-settings") && result.request().method() === "POST"
  );
  await page.getByRole("button", { name: "SAVE CHANGED SETTINGS" }).click();
  expect((await mutation).status()).toBe(200);
  await expect(page.getByLabel("ALERT MAX MESSAGES PER WINDOW")).toHaveValue(updated);
  await expect(page.locator("body")).not.toContainText(/MEMERADAR_[A-Z_]+TOKEN|private_key|runtime-provider-secret/i);
});

test("invalid wallet boundaries fail closed without inventing a record", async ({ page }) => {
  const response = await page.goto("/wallets/not-a-wallet");
  expect(response?.status()).toBe(200);
  await expect(page.getByText("INVALID READ RESPONSE", { exact: true })).toBeVisible();
  await expectProtectedShell(page);
  await expect(page.locator("body")).not.toContainText("UNLABELED WALLET");
});
