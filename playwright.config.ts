import { defineConfig, devices } from "@playwright/test";

// 로컬은 설치된 Edge를, CI(Linux)는 `playwright install`로 받은 Chromium을 사용합니다.
const channel = process.env.CI ? undefined : "msedge";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Edge"], channel } },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium", channel } },
  ],
  webServer: [
    {
      command: "uv run --project apps/api python tests/e2e/serve_api.py",
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
