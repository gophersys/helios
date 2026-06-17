// The a11y-evidence Playwright config (mirrors @eden/primitives' harness / the OD-1 spike). Runs every
// *.spec.ts on the REAL Chromium AND WebKit engines (both installed in the devcontainer at
// ~/.cache/ms-playwright) against the vite-preview-served harness. This is the browser-level lane of
// the three-layer a11y stack (axe + keyboard); the in-process design-correctness (UI-math) lane is
// vitest (*.design.test.ts).
import { defineConfig, devices } from '@playwright/test';

// The preview port is overridable via EDEN_A11Y_PORT (default 5181, one above primitives' 5180 so the
// two libs' a11y runs can coexist in the same devcontainer). The vite preview server pins a single
// strict port; an env override lets a run isolate onto its own port without editing this shared config.
const PORT = process.env.EDEN_A11Y_PORT ?? '5181';
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
