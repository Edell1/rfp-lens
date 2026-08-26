import { defineConfig } from "@playwright/test";

const apiPort = 8123;
const webPort = 5173;

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "uv run alembic upgrade head && uv run uvicorn app.main:app --host 127.0.0.1 --port 8123",
      cwd: "../backend",
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        RFP_LENS_ENVIRONMENT: "demo",
        RFP_LENS_AI_PROVIDER: "fake",
        RFP_LENS_JWT_SECRET: "e2e-demo-secret-that-is-long-enough-for-hs256",
        RFP_LENS_CELERY_TASK_ALWAYS_EAGER: "true",
      },
    },
    {
      command: `npm run dev -- --port ${webPort} --strictPort`,
      cwd: "../frontend",
      url: `http://localhost:${webPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}/api`,
      },
    },
  ],
});
