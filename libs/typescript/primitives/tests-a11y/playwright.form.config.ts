// An ISOLATED Playwright config for the form-action group's a11y evidence — a dedicated port (5181)
// so the form-group lane never contends with the reference Button lane (port 5180) when both run
// concurrently. Same three-layer contract: axe on REAL Chromium AND WebKit + Playwright keyboard,
// over the same vite-preview-served multi-page harness (the form page is /form.html).
//
// The canonical `./ctl.sh a11y` verb runs the SHARED playwright.config.ts (testDir ./specs picks up
// BOTH button.spec.ts and form.spec.ts on port 5180). This isolated config exists so the form lane
// can be re-run independently (e.g. under parallel-agent builds) without a port collision; it is a
// strict subset (only form.spec.ts) on a non-colliding port.
import { defineConfig, devices } from '@playwright/test';

const PORT = Number(process.env.EDEN_FORM_A11Y_PORT ?? 5181);

export default defineConfig({
  testDir: './specs',
  testMatch: 'form.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  timeout: 30000,
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    headless: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: `bun x vite preview --config vite.config.ts --port ${String(PORT)} --strictPort --host 127.0.0.1`,
    url: `http://127.0.0.1:${String(PORT)}`,
    reuseExistingServer: false,
    timeout: 120000,
  },
});
