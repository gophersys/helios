import { defineConfig, devices } from '@playwright/test';
import { execSync } from 'node:child_process';

// Pull Bitbucket credentials from Docker container if not already set
if (!process.env.BITBUCKET_API_TOKEN || !process.env.BITBUCKET_EMAIL) {
  try {
    const containerEnv = execSync(
      'docker exec development-http-api-1 env',
      { encoding: 'utf-8', timeout: 5_000 },
    );
    for (const key of ['BITBUCKET_API_TOKEN', 'BITBUCKET_EMAIL', 'BITBUCKET_WORKSPACE']) {
      const match = containerEnv.match(new RegExp(`^${key}=(.+)$`, 'm'));
      if (match?.[1] && !process.env[key]) {
        process.env[key] = match[1];
      }
    }
  } catch {
    // Container not running — Bitbucket tests will skip
  }
}

/**
 * Playwright E2E test configuration.
 * Run with: npx playwright test
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use */
  reporter: [
    ['html', { open: 'never' }],
    ['list']
  ],
  /* Shared settings for all projects */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: 'http://localhost:4200',
    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',
    /* Screenshot on failure */
    screenshot: 'only-on-failure',
  },
  /* Configure projects — cleanup runs after all tests */
  projects: [
    {
      name: 'tests',
      testIgnore: /stories\/cleanup\//,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'cleanup',
      testMatch: /stories\/cleanup\//,
      dependencies: ['tests'],
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  /* Run local dev server before starting tests */
  webServer: {
    command: 'npm run dev -- --port 4200',
    url: 'http://localhost:4200',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
