import adapterAuto from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/**
 * SvelteKit configuration for @eden/frontend — the development spine that hosts the
 * document workspace (ADR-0015). adapter-auto is the v0 default; the static-adapter
 * build that the Tauri shell wraps (ADR-0006) is selected later when that surface is
 * pulled into existence.
 *
 * @type {import('@sveltejs/kit').Config}
 */
const configuration = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapterAuto(),
  },
};

export default configuration;
