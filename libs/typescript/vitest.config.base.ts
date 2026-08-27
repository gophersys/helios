// libs/typescript/vitest.config.base.ts
//
// Shared vitest base for every @eden/* library (ADR-0024 §Phase-0 @eden/testing analog).
// Per-lib vitest.config.ts merges this via `mergeConfig`. Coverage is v8; the per-package
// FLOOR (80% leaf / 70% substrate, ADR-0020 §cover-floor) is set per-lib, never here.

import { defineConfig } from 'vitest/config';

export const edenVitestBase = defineConfig({
  test: {
    // jsdom is wired per-lib only where a DOM is needed (components); pure-utility leaves
    // stay on the default node-compatible (bun) environment for speed.
    globals: false,
    clearMocks: true,
    coverage: {
      // istanbul (source-instrumentation), NOT v8: bun's `node:inspector` does not implement the
      // V8 coverage profiler API the v8 provider needs ("Coverage APIs are not supported"), and
      // the devcontainer's JS runtime is bun. istanbul instruments the source at transform time,
      // so it is runtime-agnostic and works under bun. (A genuine bun/node gap — see the report.)
      provider: 'istanbul',
      reporter: ['text', 'json-summary'],
      // include/exclude + the FLOOR thresholds are set in the per-lib config, since the floor
      // is a per-package property (leaf vs substrate) — see each lib's vitest.config.ts.
      all: true,
    },
  },
});

export default edenVitestBase;
