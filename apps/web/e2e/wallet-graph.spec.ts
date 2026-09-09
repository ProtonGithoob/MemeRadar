import { expect, test } from "@playwright/test";

const authenticatedRead = Boolean(
  (process.env.MEMERADAR_E2E_API_BASE_URL ?? process.env.MEMERADAR_API_BASE_URL)?.trim() &&
  (process.env.MEMERADAR_E2E_VIEWER_API_TOKEN ?? process.env.MEMERADAR_VIEWER_API_TOKEN)?.trim()
);

test("wallet-graph route renders explorer and maintains protected mode boundaries", async ({ page }) => {
  const response = await page.goto("/wallet-graph");
  expect(response?.status()).toBe(200);

  await expect(page.getByRole("heading", { name: "Wallet & Creator Outcome Graph" })).toBeVisible();
  const mode = authenticatedRead ? "ON" : "UNKNOWN";
  await expect(page.getByRole("status", { name: `ANALYSIS ONLY: ${mode}` })).toBeVisible();
  await expect(page.getByRole("status", { name: `PAPER TRADING: ${mode}` })).toBeVisible();

  // Search form controls present
  await expect(page.getByRole("button", { name: "Search Graph" })).toBeVisible();
  await expect(page.getByPlaceholder("Enter address, mint, or cluster ID...")).toBeVisible();

  // No mutation or execution buttons present
  await expect(page.getByRole("button", { name: /execute|sign|submit|save|mutate/i })).toHaveCount(0);
});
