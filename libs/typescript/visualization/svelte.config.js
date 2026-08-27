// libs/typescript/visualization/svelte.config.js — the Svelte 5 compiler config for @eden/visualization.
//
// Consumed by svelte-check (the typecheck lane for *.svelte) and by the vitest-plugin-svelte
// (the component test lane). vitePreprocess lets a <script lang="ts"> block be type-checked and
// transpiled. Svelte 5 runes mode is the default in svelte@5 — no compilerOptions override needed.
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
};
