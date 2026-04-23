// ESLint flat config for the Svelte 5 frontend.
//
// typescript-eslint is resolved from the repo root node_modules.

import tseslint from 'typescript-eslint';
import js from '@eslint/js';

export default tseslint.config(
  {
    ignores: [
      'build/**',
      '.svelte-kit/**',
      'dist/**',
      'node_modules/**',
      'src/lib/types/openapi.ts',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Allow `_` prefix for intentionally-unused identifiers (standard TS convention).
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
    },
  },
  {
    // Svelte 5 reactivity idiom: `this.arr = this.arr` after mutation forces
    // runes to re-run. ESLint's no-self-assign can't see the reactive graph.
    files: ['**/*.svelte.ts', '**/stores/**/*.ts', '**/components/**/*.ts'],
    rules: {
      'no-self-assign': 'off',
    },
  },
  {
    // Parsers/tests that deliberately operate on ANSI escape sequences.
    files: ['**/utils/ansi.ts', '**/utils/formatting.ts', '**/stores/auth.svelte.ts', '**/*.test.ts'],
    rules: {
      'no-control-regex': 'off',
    },
  },
  {
    // Test fixtures deliberately use `any`, `!`, and loose `Function` types.
    files: ['**/*.test.ts', '**/tests/**/*.ts', '**/e2e/**/*.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/no-empty-function': 'off',
      '@typescript-eslint/no-unsafe-function-type': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
);
