import { defineConfig, devices } from '@playwright/test';

/**
 * Parallel E2E story suite configuration.
 *
 * Tests are organized into domain-based projects that run IN PARALLEL,
 * while tests WITHIN each domain run serially (they build on state from
 * previous tests via `test.describe.configure({ mode: 'serial' })`).
 *
 * Domain groups:
 *   1. auth        — login, route guards, sidebar, view-as-role (independent)
 *   2. products    — creation wizard, detail tabs, edit, delete, boards, recipes
 *   3. bitbucket   — sync, branch/PR lifecycle
 *   4. builds      — auto-trigger, monitoring, artifacts
 *   5. validation  — queue CRUD, execution, realtime, results
 *   6. fixtures    — designs, instances, slots, deployment, deletion
 *   7. manufacturing — setup, fixtures, sessions, results
 *   8. users       — CRUD, permissions, API keys, roles
 *   9. roles       — role-based permission stories
 *  10. cleanup     — database, bitbucket, corecloud, minio zero-state
 *
 * Run with: npx playwright test --config e2e.config.ts
 * Run one domain: npx playwright test --config e2e.config.ts --project=auth
 * Run serial (old behavior): npx playwright test --config e2e.config.ts --workers=1
 */

const sharedUse = {
  ...devices['Desktop Chrome'],
  baseURL: process.env.E2E_BASE_URL || 'http://localhost:4200',
  trace: 'retain-on-failure' as const,
  screenshot: 'only-on-failure' as const,
  video: 'retain-on-failure' as const,
};

export default defineConfig({
  testDir: './e2e/stories',
  fullyParallel: false, // serial within each project
  workers: parseInt(process.env.E2E_WORKERS || '5', 10),
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['html', { open: 'never', outputFolder: 'e2e-report' }],
    ['list'],
  ],
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  projects: [
    {
      name: 'auth',
      testDir: './e2e/stories/auth',
      use: sharedUse,
    },
    {
      name: 'products',
      testDir: './e2e/stories/products',
      use: sharedUse,
    },
    {
      name: 'bitbucket',
      testDir: './e2e/stories/bitbucket',
      use: sharedUse,
    },
    {
      name: 'builds',
      testDir: './e2e/stories/builds',
      use: sharedUse,
    },
    {
      name: 'validation',
      testDir: './e2e/stories/validation',
      use: sharedUse,
    },
    {
      name: 'fixtures',
      testDir: './e2e/stories/fixtures',
      use: sharedUse,
    },
    {
      name: 'manufacturing',
      testDir: './e2e/stories/manufacturing',
      use: sharedUse,
    },
    {
      name: 'users',
      testDir: './e2e/stories/users',
      use: sharedUse,
    },
    {
      name: 'roles',
      testDir: './e2e/stories/roles',
      use: sharedUse,
    },
    {
      name: 'cleanup',
      testDir: './e2e/stories/cleanup',
      use: sharedUse,
    },
  ],
});
