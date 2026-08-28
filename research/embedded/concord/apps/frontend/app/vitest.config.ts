import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { resolve } from 'path';

export default defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  test: {
    // Use jsdom for DOM testing
    environment: 'jsdom',
    // Include test files
    include: ['src/**/*.{test,spec}.{js,ts}'],
    // Global test utilities
    globals: true,
    // Setup files run before each test file
    setupFiles: ['./src/tests/setup.ts'],
    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/lib/**/*.{ts,svelte}'],
      exclude: [
        'src/lib/**/*.test.ts',
        'src/lib/**/*.spec.ts',
        'src/tests/**'
      ]
    }
  },
  resolve: {
    alias: {
      $lib: resolve('./src/lib'),
      '$app/environment': resolve('./src/tests/mocks/app-environment.ts'),
      '$app/navigation': resolve('./src/tests/mocks/app-navigation.ts'),
      '$app/stores': resolve('./src/tests/mocks/app-stores.ts'),
      '$env/static/public': resolve('./src/tests/mocks/env-static-public.ts')
    }
  }
});
