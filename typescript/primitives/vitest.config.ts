// libs/typescript/primitives/vitest.config.ts — merges the shared @eden vitest base and adds the
// Svelte component-test substrate (ADR-0024). @eden/primitives is the FIRST component lib: it ships
// *.svelte, so the suite needs (1) the Svelte 5 compiler (vite-plugin-svelte) and (2) a DOM
// (jsdom) for the in-process component render + the *.design.test.ts UI-math assertions. The
// browser-level a11y evidence (axe on Chromium+WebKit) is a SEPARATE Playwright lane (tests-a11y/,
// driven by the ctl.sh `a11y` verb), not vitest — see _ctl/lib.sh cmd_a11y.
//
// Coverage FLOOR (ADR-0020 §cover-floor): the token-DERIVATION logic (button/tokens.ts — the math
// that turns @eden/theme into this component's CSS vars) is the gated public surface and is held to
// the 80% leaf FLOOR. The *.svelte files are markup bound to those derived vars; they are exercised
// by the component + design lanes but excluded from the istanbul line floor (a .svelte template is
// not istanbul-instrumentable the way a .ts module is — the SAME reason index.ts is excluded).
import { mergeConfig, defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { svelteTesting } from '@testing-library/svelte/vite';
import { edenVitestBase } from '../vitest.config.base.js';

export default mergeConfig(
  edenVitestBase,
  defineConfig({
    plugins: [svelte(), svelteTesting()],
    test: {
      // jsdom: the DOM the component render + the design-math assertions run against. (A pure-math
      // leaf stays on node/bun for speed; a component lib REQUIRES a DOM — ADR-0024.)
      environment: 'jsdom',
      // The Svelte browser condition resolves the *.svelte runtime entry of svelte + bits-ui.
      alias: [],
      include: ['src/**/*.{test,property.test,design.test,spec}.ts'],
      setupFiles: ['./vitest.setup.ts'],
      coverage: {
        // The token-derivation math (the *.ts modules) is the gated surface. The barrel and the
        // *.svelte templates are excluded from the line FLOOR (see header) — exactly as @eden/theme
        // excludes its pure re-export barrel.
        include: ['src/**/*.ts'],
        exclude: ['src/index.ts', 'src/**/*.{test,property.test,design.test,spec}.ts'],
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
