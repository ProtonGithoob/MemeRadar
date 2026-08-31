import { defineConfig } from "@playwright/test";

const baseURL = process.env.MEMERADAR_E2E_BASE_URL ?? "http://127.0.0.1:13000";
const externalServer = Boolean(process.env.MEMERADAR_E2E_BASE_URL);
const executablePath = process.env.MEMERADAR_E2E_EXECUTABLE_PATH;

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
  ...(externalServer
    ? {}
    : {
        webServer: {
          command: "npm run dev -- --hostname 127.0.0.1 --port 13000",
          url: "http://127.0.0.1:13000/",
          reuseExistingServer: true,
          timeout: 120_000
        }
      })
});
