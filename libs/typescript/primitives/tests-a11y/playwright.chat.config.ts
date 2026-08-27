// An ISOLATED Playwright config for the chat group's a11y evidence — a dedicated port (5182) so the
// chat-group lane never contends with the reference Button lane (5180) or the form lane (5181) when
// agents run concurrently. Same three-layer contract: axe on REAL Chromium AND WebKit + Playwright
// keyboard, over the same vite-preview-served multi-page harness (the chat page is /chat.html).
//
// The canonical `./ctl.sh a11y` verb runs the SHARED playwright.config.ts (testDir ./specs picks up
// every *.spec.ts on port 5180). This isolated config exists so the chat lane can be re-run
// independently (e.g. under parallel-agent builds) without a port collision; it is a strict subset
// (only chat.spec.ts) on a non-colliding port.
import { defineConfig, devices } from '@playwright/test';

const PORT = Number(process.env.EDEN_CHAT_A11Y_PORT ?? 5182);

export default defineConfig({
  testDir: './specs',
  testMatch: 'chat.spec.ts',
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
