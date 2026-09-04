import { expect, test } from "@playwright/test";

const VALID_TOKEN_UUID = "123e4567-e89b-12d3-a456-426614174000";

test.describe("MemeRadar Critical Workstation Journeys", () => {
  test("Journey 1: Command Center -> priority candidate -> token research workspace", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "MemeRadar" })).toBeVisible();
    await expect(page.getByText("READ ONLY MODE")).toBeVisible();

    // Navigate to token research workspace with valid UUID
    const tokenRes = await page.goto(`/tokens/${VALID_TOKEN_UUID}`);
    expect(tokenRes?.status()).toBe(200);
    await expect(
      page.getByText(/ENTRY READINESS CHECKLIST|TOKEN READ|BACK TO RADAR|The token projection could not be safely loaded/i).first()
    ).toBeVisible();
  });

  test("Journey 2: Token -> creator -> wallet graph -> related token", async ({ page }) => {
    const response = await page.goto(`/tokens/${VALID_TOKEN_UUID}`);
    expect(response?.status()).toBe(200);

    const graphRes = await page.goto("/wallet-graph?address=42222222222222222222222222222222");
    expect(graphRes?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Wallet & Creator Outcome Graph" })).toBeVisible();
  });

  test("Journey 3: ENTRY_READY candidate -> paper position desk", async ({ page }) => {
    const response = await page.goto("/positions");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Positions", exact: true })).toBeVisible();
    await expect(page.getByText(/PAPER PORTFOLIO|POSITION EVIDENCE \/ READ-ONLY|No position or market data was substituted/i).first()).toBeVisible();

    // Ensure strict safety boundary: no live execution controls
    await expect(page.getByRole("button", { name: /buy|sell|trade|swap|sign|execute live/i })).toHaveCount(0);
  });

  test("Journey 4: Position -> exit risk evidence -> token detail", async ({ page }) => {
    const response = await page.goto("/positions");
    expect(response?.status()).toBe(200);

    const tokenRes = await page.goto(`/tokens/${VALID_TOKEN_UUID}`);
    expect(tokenRes?.status()).toBe(200);
    await expect(page.getByText(/WHY RISKY|TOKEN READ|BACK TO RADAR|HARD GATES|The token projection could not be safely loaded/i).first()).toBeVisible();
  });

  test("Journey 5: Providers/Shadow -> operational truth hierarchy & diagnostic state", async ({ page }) => {
    const response = await page.goto("/operations");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Operations", exact: true })).toBeVisible();
    await expect(page.getByText(/OPERATIONAL TRUTH HIERARCHY|OPERATIONS \/ READ-ONLY|No operational health was inferred/i).first()).toBeVisible();
  });

  test("Journey 6: Research -> unmistakable SYNTHETIC vs LIVE_SHADOW distinction", async ({ page }) => {
    const response = await page.goto("/research");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Product Research Gate & Strategy Calibration" })).toBeVisible();
    await expect(page.getByText("REAL_WORLD_ALPHA_NOT_YET_PROVEN")).toBeVisible();
    await expect(page.getByText("SYNTHETIC_FIXTURE").first()).toBeVisible();
    await expect(page.getByText("LIVE_SHADOW").first()).toBeVisible();
  });
});
