import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Edge"], channel: "msedge" } },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium", channel: "msedge" } },
  ],
  webServer: [
    {
      command: "apps\\api\\.venv\\Scripts\\python.exe tests/e2e/serve_api.py",
      url: "http://127.0.0.1:8100/api/v1/health", reuseExistingServer: false,
    },
    {
      command: "corepack pnpm build && corepack pnpm --filter @rule-u/web exec next start --hostname 127.0.0.1 --port 3100",
      env: { API_ORIGIN: "http://127.0.0.1:8100" },
      timeout: 120000,
      url: "http://127.0.0.1:3100", reuseExistingServer: false,
    },
  ],
});
