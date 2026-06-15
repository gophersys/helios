import { defineConfig, devices } from '@playwright/test';

// Playwright configuration for the chat-slice forced-CRUD E2E. The test drives the production
// build (served by `vite preview`) against a REAL agentgateway dev-serve — no mocked fetch/SSE.
// The runner (tests/e2e/run.sh) boots both substrates on free ports and exports their URLs:
//   E2E_BASE_URL    the vite-preview origin the browser navigates to
//   E2E_GATEWAY_URL the dev-serve origin the UI talks to (passed as ?gateway=…)
// Both default to the conventional dev ports so the suite is runnable standalone too.
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:4174';

export default defineConfig({
  testDir: './tests/e2e',
  // The forced-CRUD flow is one ordered story (create → chat → control → stop); keep it serial
  // and single-worker so the assertions read top-to-bottom against the real backend.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list']],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    headless: true,
  },
  // Chromium is the default lane; WebKit is added so the design-math / a11y dimension is asserted on
  // BOTH engines (the create-product E2E audits the wizard cross-engine). The runner exports
  // E2E_BROWSERS=chromium,webkit; default to chromium so the suite stays fast when run standalone.
  projects: (process.env.E2E_BROWSERS ?? 'chromium')
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean)
    .map((name) =>
      name === 'webkit'
        ? { name: 'webkit', use: { ...devices['Desktop Safari'] } }
        : { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    ),
});
