// The a11y-evidence Playwright config (mirrors the OD-1 spike). Runs every *.spec.ts on the REAL
// Chromium AND WebKit engines (both installed in the devcontainer at ~/.cache/ms-playwright) against
// the vite-preview-served harness. This is the browser-level lane of the three-layer a11y stack
// (axe + keyboard); the in-process design-correctness (UI-math) lane is vitest (*.design.test.ts).
import { defineConfig, devices } from '@playwright/test';

// The preview port is overridable via EDEN_A11Y_PORT (default 5180). The vite preview server pins a
// single strict port, so two a11y runs in the same devcontainer (e.g. two Build agents running their
// per-component spec concurrently) would collide on it. An env override lets a run isolate onto its
// own port without editing this shared config — the default keeps the canonical single-run behavior.
const PORT = process.env.EDEN_A11Y_PORT ?? '5180';
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: './specs',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  timeout: 30000,
  use: {
    baseURL: BASE_URL,
    headless: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: `bun x vite preview --config vite.config.ts --port ${PORT} --strictPort --host 127.0.0.1`,
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 120000,
  },
});
