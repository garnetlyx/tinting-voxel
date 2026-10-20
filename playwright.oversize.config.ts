import { defineConfig, devices } from '@playwright/test';

/**
 * Oversize-cap E2E: runs e2e/oversize-cap.spec.ts against a backend started
 * with a tiny memory budget so the over-budget refusal (and its dialog)
 * actually triggers. The default config cannot host these tests: with the
 * production budget (3072 MB) a seven-layer preview estimates ~105 MB,
 * answers 200, and no dialog ever appears.
 *
 * The hard cap decides which dialog mode is under test:
 * - default (cap 95 MB, below the 105 MB estimate): the dialog must drop
 *   "Run anyway" and only the scale-down may proceed.
 * - E2E_FORCE_ALLOWED=1 (cap 200 MB, above the estimate): "Run anyway"
 *   stays available and forcing must run the job.
 *
 *   npx playwright test --config playwright.oversize.config.ts
 *   E2E_FORCE_ALLOWED=1 npx playwright test --config playwright.oversize.config.ts
 */
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8010);
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 5183);
const FORCE_ALLOWED = process.env.E2E_FORCE_ALLOWED === '1';
const HARD_CAP_MB = FORCE_ALLOWED ? 200 : 95;

export default defineConfig({
  testDir: './e2e',
  testMatch: /oversize-cap\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
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
      command: `cd backend && RATE_LIMIT_ENABLED=false HEAVY_MEMORY_BUDGET_MB=80 HEAVY_MEMORY_HARD_CAP_MB=${HARD_CAP_MB} .venv/bin/python -m uvicorn main:app --port ${BACKEND_PORT}`,
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
