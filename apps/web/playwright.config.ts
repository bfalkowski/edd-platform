import { defineConfig } from "@playwright/test";

const API_PORT = 8091;
const WEB_PORT = 5183;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `uv run --extra dev uvicorn edd_platform_api.main:app --port ${API_PORT}`,
      cwd: "../api",
      port: API_PORT,
      reuseExistingServer: !process.env.CI,
      env: { EDD_PLATFORM_STORAGE_BACKEND: "memory" },
      timeout: 30_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      port: WEB_PORT,
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
      timeout: 30_000,
    },
  ],
});
