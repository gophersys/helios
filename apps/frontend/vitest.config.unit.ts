// vitest.config.unit.ts — the frontend's UNIT suite (distinct from the Playwright e2e under tests/e2e).
// Scoped to *.unit.test.ts so it never picks up the e2e specs, and run via `bash ./ctl.sh unit`. jsdom
// gives the window/location seam the openEditor branch test mocks. The frontend is a yarn workspace
// member, so `bun x vitest` resolves the workspace-hoisted vitest 3.x (the @eden/* TS-lib pin) + jsdom.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.unit.test.ts', 'tests/unit/**/*.test.ts'],
    clearMocks: true,
    // $lib alias so the unit test imports the same path the app does without the full SvelteKit plugin
    // (the unit suite tests pure TS modules, not Svelte components).
    alias: {
      $lib: new URL('./src/lib', import.meta.url).pathname,
    },
  },
});
