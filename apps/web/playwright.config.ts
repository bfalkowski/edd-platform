import { defineConfig } from "@playwright/test";

const API_PORT = 8091;
const WEB_PORT = 5183;
const STUB_ANTHROPIC_PORT = 8092;

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
      command: "node tests/e2e/stub-anthropic.mjs",
      port: STUB_ANTHROPIC_PORT,
      reuseExistingServer: !process.env.CI,
      env: { STUB_ANTHROPIC_PORT: String(STUB_ANTHROPIC_PORT) },
      timeout: 30_000,
    },
    {
      command: `uv run --extra dev uvicorn edd_platform_api.main:app --port ${API_PORT}`,
      cwd: "../api",
      port: API_PORT,
      reuseExistingServer: !process.env.CI,
      env: {
        EDD_PLATFORM_STORAGE_BACKEND: "memory",
        // Skip .env files, which from a worktree would be the main checkout's.
        EDD_PLATFORM_E2E: "1",
        // Live runs go to the local stub, never a real provider.
        ANTHROPIC_API_KEY: "e2e-stub-key",
        ANTHROPIC_BASE_URL: `http://127.0.0.1:${STUB_ANTHROPIC_PORT}`,
        LANGFUSE_PUBLIC_KEY: "",
        LANGFUSE_SECRET_KEY: "",
      },
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
