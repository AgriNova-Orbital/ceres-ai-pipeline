import { defineConfig, devices } from "@playwright/test";

const smokePort = 3210;
const baseURL = `http://127.0.0.1:${smokePort}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: {
    command: `HOSTNAME=127.0.0.1 PORT=${smokePort} node .next/standalone/server.js`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "pixel-5",
      use: { ...devices["Pixel 5"] },
    },
  ],
});
