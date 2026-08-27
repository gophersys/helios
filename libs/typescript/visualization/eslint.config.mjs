// libs/typescript/visualization/eslint.config.mjs — the shared strict flat config (ONE home,
// ../eslint.config.base.mjs) plus the per-lib ignore for the a11y-evidence harness sub-project.
//
// `tests-a11y/` is a SEPARATE vite + Playwright sub-project (its own vite.config.ts / svelte.config
// resolution, its own dist), not part of the library's typed program (tsconfig.json includes only
// `src/**`). The base config's typed-linting rules need a tsconfig project for every file; the
// harness files have none, so they are linted by their own toolchain (svelte-check via the build,
// tsc-of-the-spec via Playwright's transform), and excluded here. The library SURFACE (`src/**`,
// the gated code) is fully linted by the strict base. This is the only deviation, and it is scoped.
import base from '../eslint.config.base.mjs';

export default [
  // The a11y-evidence harness sub-project + build output (see header) and the pure tooling/test-infra
  // config files (svelte.config.js: the compiler config consumed by the build/svelte-check; the
  // vitest setup) are out of the library's typed program; they are not gated library surface.
  { ignores: ['tests-a11y/**', 'dist/**', 'svelte.config.js', 'vitest.setup.ts'] },
  ...base,
];
