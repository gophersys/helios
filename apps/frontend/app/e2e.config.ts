import { defineConfig, devices } from '@playwright/test';

/**
 * Separate Playwright config for the full end-to-end story suite.
 *
 * These tests exercise the complete stack (UI + API + docker-compose services +
 * external integrations) and run sequentially because each test builds on the
 * state left by the previous one.
 *
 * Run with: npx playwright test --config e2e.config.ts
 */
export default defineConfig({
  testDir: './e2e/stories',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 600_000,
  expect: { timeout: 30_000 },
  reporter: [
    ['html', { open: 'never', outputFolder: 'e2e-report' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:4200',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
