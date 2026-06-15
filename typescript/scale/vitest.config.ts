// libs/typescript/scale/vitest.config.ts — merges the shared base and sets this lib's
// per-package coverage FLOOR (ADR-0020 §cover-floor: 80% leaf). @eden/scale is a pure leaf lib.
import { mergeConfig, defineConfig } from 'vitest/config';
import { edenVitestBase } from '../vitest.config.base.js';

export default mergeConfig(
  edenVitestBase,
  defineConfig({
    test: {
      include: ['src/**/*.{test,property.test,design.test,spec}.ts'],
      coverage: {
        include: ['src/index.ts'],
        // The per-package FLOOR — a leaf lib is 80% (not a target, a floor). vitest fails the
        // run if any of these dips below threshold.
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
