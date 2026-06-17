// libs/typescript/visualization/vitest.config.ts — merges the shared @eden vitest base and adds the
// Svelte component-test substrate (ADR-0024). @eden/visualization ships *.svelte, so the suite needs
// (1) the Svelte 5 compiler (vite-plugin-svelte) and (2) a DOM (jsdom) for the in-process SVG render
// + the *.design.test.ts UI-math assertions. The browser-level a11y evidence (axe on Chromium+WebKit)
// is a SEPARATE Playwright lane (tests-a11y/, driven by the ctl.sh `a11y` verb), not vitest.
//
// Coverage FLOOR (ADR-0020 §cover-floor): the pure scatter math (hotspot-map/scales.ts + tokens.ts —
// the scales/ramp/tick math that turns a Report's entities + an @eden/theme into SVG geometry + CSS
// vars) is the gated public surface and is held to the 80% leaf FLOOR. The *.svelte file is markup
// bound to those derived values; it is exercised by the component + design lanes but excluded from the
// istanbul line floor (a .svelte template is not istanbul-instrumentable the way a .ts module is — the
// SAME reason index.ts is excluded). The Report TS types carry no runtime logic and are likewise out.
import { mergeConfig, defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { svelteTesting } from '@testing-library/svelte/vite';
import { edenVitestBase } from '../vitest.config.base.js';

export default mergeConfig(
  edenVitestBase,
  defineConfig({
    plugins: [svelte(), svelteTesting()],
    // Dedupe svelte to a SINGLE instance so the compiled component and the runtime that mounts it are
    // the same copy (a nested-workspace hygiene guard; the standard Svelte-testing resolution).
    resolve: { dedupe: ['svelte'] },
    test: {
      // jsdom: the DOM the SVG render + the design-math assertions run against. (A pure-math leaf
      // stays on node/bun for speed; a component lib REQUIRES a DOM — ADR-0024.)
      environment: 'jsdom',
      alias: [],
      include: ['src/**/*.{test,property.test,design.test,spec}.ts'],
      setupFiles: ['./vitest.setup.ts'],
      coverage: {
        // The scatter math (the *.ts modules) is the gated surface. The barrel, the *.svelte
        // template, and the pure-type Report modules are excluded from the line FLOOR (see header) —
        // exactly as @eden/theme excludes its pure re-export barrel.
        include: ['src/**/*.ts'],
        exclude: [
          'src/index.ts',
          'src/report/**',
          'src/**/*.{test,property.test,design.test,spec}.ts',
        ],
        thresholds: {
          lines: 80,
          functions: 80,
          branches: 80,
          statements: 80,
        },
      },
    },
  }),
);
