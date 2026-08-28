// The a11y-evidence harness vite config (mirrors @eden/primitives' harness / the OD-1 spike). Builds
// the minimal harness app Playwright previews. The svelte plugin compiles the *.svelte under test;
// `@eden/visualization` is aliased to its SOURCE barrel so the harness exercises the live component
// (no dist build needed), and `@eden/theme` resolves through the workspace symlink to its built dist.
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const here = (p: string): string => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  root: here('.'),
  plugins: [svelte({ configFile: here('../svelte.config.js') })],
  // Pin svelte to the workspace copy so the harness compiler + runtime are one instance (the same
  // nested-workspace hygiene the vitest config applies — the superproject's hoisted node_modules
  // can otherwise resolve a second svelte for the runtime).
  resolve: {
    dedupe: ['svelte'],
    alias: {
      '@eden/visualization': here('../src/index.ts'),
    },
  },
  server: { port: 5181, strictPort: true, host: '127.0.0.1' },
  preview: { port: 5181, strictPort: true, host: '127.0.0.1' },
  build: {
    outDir: here('./dist'),
    emptyOutDir: true,
  },
});
