// The a11y-evidence harness vite config (mirrors the OD-1 spike). Builds the minimal harness app
// Playwright previews. The svelte plugin compiles the *.svelte under test; `@eden/primitives` is
// aliased to its SOURCE barrel so the harness exercises the live component (no dist build needed),
// and `@eden/theme` resolves through the workspace symlink to its built dist.
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const here = (p: string): string => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  root: here('.'),
  plugins: [svelte({ configFile: here('../svelte.config.js') })],
  resolve: {
    alias: {
      '@eden/primitives': here('../src/index.ts'),
    },
  },
  server: { port: 5180, strictPort: true, host: '127.0.0.1' },
  preview: { port: 5180, strictPort: true, host: '127.0.0.1' },
  build: {
    outDir: here('./dist'),
    emptyOutDir: true,
    // Multi-page: each component group has its OWN harness page so the per-group specs stay isolated
    // (the form-action group lives at /form.html; the reference Button harness stays at /).
    rollupOptions: {
      input: {
        index: here('./index.html'),
        form: here('./form.html'),
        chat: here('./chat.html'),
        wave1: here('./wave1.html'),
      },
    },
  },
});
