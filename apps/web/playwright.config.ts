import { defineConfig } from "@playwright/test";

const baseURL = process.env.MEMERADAR_E2E_BASE_URL ?? "http://127.0.0.1:13000";
const externalServer = Boolean(process.env.MEMERADAR_E2E_BASE_URL);
const executablePath = process.env.MEMERADAR_E2E_EXECUTABLE_PATH;
const apiBase = process.env.MEMERADAR_E2E_API_BASE_URL ?? process.env.MEMERADAR_API_BASE_URL ?? "";
const viewerToken = process.env.MEMERADAR_E2E_VIEWER_API_TOKEN ?? process.env.MEMERADAR_VIEWER_API_TOKEN ?? "";
const adminToken = process.env.MEMERADAR_E2E_ADMIN_API_TOKEN ?? process.env.MEMERADAR_ADMIN_API_TOKEN ?? "";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "line",
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
    ...(executablePath ? { launchOptions: { executablePath } } : {})
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "laptop", use: { viewport: { width: 1024, height: 768 } } },
    { name: "tablet", use: { viewport: { width: 768, height: 1024 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } }
  ],
  ...(externalServer
    ? {}
    : {
        webServer: {
          command: "npm run dev -- --hostname 127.0.0.1 --port 13000",
          url: "http://127.0.0.1:13000/",
          reuseExistingServer: false,
          timeout: 120_000,
          env: {
            MEMERADAR_API_BASE_URL: apiBase,
            MEMERADAR_VIEWER_API_TOKEN: viewerToken,
            MEMERADAR_ADMIN_API_TOKEN: adminToken
          }
        }
      })
});
