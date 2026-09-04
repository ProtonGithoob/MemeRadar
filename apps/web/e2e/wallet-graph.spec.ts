import { expect, test } from "@playwright/test";

test("wallet-graph route renders explorer and maintains protected mode boundaries", async ({ page }) => {
  const response = await page.goto("/wallet-graph");
  expect(response?.status()).toBe(200);

  await expect(page.getByRole("heading", { name: "Wallet & Creator Outcome Graph" })).toBeVisible();
  await expect(page.getByText("ANALYSIS ONLY", { exact: true })).toBeVisible();
  await expect(page.getByText("PAPER TRADING", { exact: true })).toBeVisible();
  await expect(page.getByText("ADVISORY OUTPUT", { exact: true })).toBeVisible();

  // Search form controls present
  await expect(page.getByRole("button", { name: "Search Graph" })).toBeVisible();
  await expect(page.getByPlaceholder("Enter address, mint, or cluster ID...")).toBeVisible();

  // No mutation or execution buttons present
  await expect(page.getByRole("button", { name: /execute|sign|submit|save|mutate/i })).toHaveCount(0);
});
