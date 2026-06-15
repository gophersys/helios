// libs/typescript/eslint.config.base.mjs
//
// Shared ESLint flat config for every @eden/* library (ADR-0024 §Phase-0 @eden/lint-config
// analog; the .golangci.yml counterpart for the UI track). Each per-lib eslint.config.mjs
// re-exports this so the strict rule set lives in ONE home (10 §9, one concept one home).
//
// Carries the HNS-1 name lint (the "maintainability" dimension's name check, ADR-0024 §3):
// the banned identifiers `util`/`utils`/`common`/`core`/`misc` and the BANNED `helios` token
// (invariant E7) are rejected mechanically here, mirroring golangci forbidigo for the Go track.

import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';

/** The HNS-1 banned-identifier set — rejected as identifiers anywhere in @eden source. */
const HNS1_BANNED_IDENTIFIER = '^(util|utils|common|core|misc|helios)$';

export default tseslint.config(
  {
    ignores: ['**/dist/**', '**/coverage/**', '**/node_modules/**', '**/.svelte-kit/**'],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        // The tooling config files (eslint.config.mjs, *.config.ts) live outside any tsconfig
        // `include`; allowDefaultProject type-checks them under an inferred default program so
        // the type-checked rules do not error on the config surface itself.
        projectService: {
          allowDefaultProject: ['eslint.config.mjs', '*.config.ts', '*.config.mjs'],
        },
      },
      globals: { ...globals.node, ...globals.browser },
    },
    rules: {
      // HNS-1 (rule 11): `util`/`common`/`core`/`misc` banned outright; `helios` banned (E7).
      // The name lint is part of the ADR-0024 "maintainability" test dimension.
      'id-denylist': ['error', 'util', 'utils', 'common', 'core', 'misc', 'helios'],
      'no-restricted-syntax': [
        'error',
        {
          selector: `Identifier[name=/${HNS1_BANNED_IDENTIFIER}/]`,
          message:
            'HNS-1: util/utils/common/core/misc are banned (name the real concept); `helios` is banned (invariant E7 — the system is Eden).',
        },
      ],
      // Interface-design rule 10 + error-handling rule 12 analogs for TS.
      '@typescript-eslint/explicit-module-boundary-types': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      'no-console': ['error', { allow: ['warn', 'error'] }],
      // `unified-signatures` (a stylistic overload-merge rule from strictTypeChecked) crashes in
      // typescript-eslint 8.46.4 with `TypeError: undefined is not an object (typeParameters.params)`
      // when it walks an interface whose member is an inline object type — a tool defect unrelated
      // to its purpose (merging function overloads). Disabled until the upstream fix lands; the gate
      // keeps all correctness + HNS-1 teeth (this rule never had any). FLAG for Mateo on the next
      // typescript-eslint bump: re-enable and remove this line if the crash is resolved.
      '@typescript-eslint/unified-signatures': 'off',
    },
  },
  ...svelte.configs.recommended,
  {
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        // svelte-eslint-parser delegates the `<script lang="ts">` block to a sub-parser; without
        // this the TS in a component (e.g. `interface Props {`) is parsed as plain JS and throws
        // "Unexpected token {". Point it at the typescript-eslint parser and enable the project
        // service so the typed-linting rules have type information for component scripts too.
        parser: tseslint.parser,
        projectService: true,
        extraFileExtensions: ['.svelte'],
      },
    },
  },
  {
    // Test files relax the boundary-type and floating-promise strictness that suits library
    // surfaces but not arrange-act-assert test bodies.
    files: ['**/*.test.ts', '**/*.spec.ts'],
    rules: {
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },
);
