import { defineConfig, devices } from '@playwright/test';

// Dedicated ports keep E2E runs off the dev servers (8000/5173). The E2E
// backend disables per-client rate limits: one browser drives every test.
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8010);
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 5183);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `cd backend && RATE_LIMIT_ENABLED=false .venv/bin/python -m uvicorn main:app --port ${BACKEND_PORT}`,
      port: BACKEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `API_PROXY_TARGET=http://localhost:${BACKEND_PORT} npx vite --port ${FRONTEND_PORT} --strictPort`,
      port: FRONTEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
