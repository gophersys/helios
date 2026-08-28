// libs/typescript/theme/vitest.config.ts — merges the shared base and sets this lib's
// per-package coverage FLOOR (ADR-0020 §cover-floor: 80% leaf). @eden/theme is a pure-math leaf
// lib (no real substrate): the generative engine + the contrast gate are deterministic functions.
import { mergeConfig, defineConfig } from 'vitest/config';
import { edenVitestBase } from '../vitest.config.base.js';

export default mergeConfig(
  edenVitestBase,
  defineConfig({
    test: {
      include: ['src/**/*.{test,property.test,design.test,spec}.ts'],
      coverage: {
        // Every non-barrel, non-test source module — the public math surface. index.ts is a
        // pure re-export barrel (no logic), excluded so it cannot dilute the floor.
        include: ['src/**/*.ts'],
        exclude: ['src/index.ts', 'src/**/*.{test,property.test,design.test,spec}.ts'],
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
