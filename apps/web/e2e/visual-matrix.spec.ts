import { expect, test } from "@playwright/test";

const ROUTES = [
  "/",
  "/radar",
  "/ultra-early",
  "/opportunities",
  "/positions",
  "/wallets",
  "/wallets/not-a-wallet",
  "/wallet-graph",
  "/callers",
  "/providers",
  "/operations",
  "/audit",
  "/settings",
  "/readiness",
  "/tokens/22222222-2222-4222-8222-222222222222"
] as const;

test("responsive visual matrix keeps every operator surface bounded", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  for (const theme of ["dark", "light"] as const) {
    await page.goto("/");
    await page.evaluate((nextTheme) => {
      localStorage.setItem("memeradar-theme", nextTheme);
      document.documentElement.setAttribute("data-theme", nextTheme);
      window.dispatchEvent(new Event("memeradar-theme-change"));
    }, theme);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

    for (const route of ROUTES) {
      const response = await page.goto(route, { waitUntil: "domcontentloaded" });
      expect(response?.status(), `${theme} ${route}`).toBe(200);
      await expect(page.locator(".ws-main")).toBeVisible();

      const layout = await page.evaluate(() => {
        const topbar = document.querySelector(".ws-topbar")?.getBoundingClientRect();
        const main = document.querySelector(".ws-main")?.getBoundingClientRect();
        return {
          viewport: window.innerWidth,
          globalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          topbarOverlap: topbar !== undefined && main !== undefined && main.top < topbar.bottom - 1
        };
      });
      expect(layout.globalOverflow, `${theme} ${route} has global horizontal overflow`).toBe(false);
      expect(layout.topbarOverlap, `${theme} ${route} overlaps the topbar`).toBe(false);

      if (layout.viewport <= 768) {
        const openNavigation = page.getByRole("button", { name: "Open navigation" });
        await expect(openNavigation).toBeVisible();
        await openNavigation.click({ force: true });
        await expect(page.getByRole("button", { name: "Close navigation" })).toBeVisible();
        await page.getByRole("button", { name: "Close navigation" }).click({ force: true });
      }

      if (testInfo.project.name === "desktop" && route === "/") {
        await testInfo.attach(`${theme}-overview`, {
          body: await page.screenshot({ fullPage: true }),
          contentType: "image/png"
        });
      }
    }
  }
});
