import { defineConfig } from '@playwright/test';

/**
 * Playwright config for visual regression tests.
 * Separate from the main E2E config (playwright.config.ts).
 *
 * Run with:
 *   npx playwright test --config=playwright-visual.config.ts
 * Update baselines:
 *   npx playwright test --config=playwright-visual.config.ts --update-snapshots
 */
export default defineConfig({
  testDir: './tests/visual',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: 'http://localhost:4200',
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
  },
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
    },
  },
  /* Assumes dev server is already running (npx nx serve app) */
  webServer: undefined,
});
