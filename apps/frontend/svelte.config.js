import adapterStatic from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/**
 * SvelteKit configuration for @eden/frontend — the development spine that hosts the
 * document workspace (ADR-0015).
 *
 * The production deploy serves the UI as a client-rendered SPA behind nginx
 * (apps/frontend/deploy/), which same-origin-proxies /gateway → agentgateway and
 * /platform → platformgateway. adapter-static in SPA mode emits a single static bundle
 * with a fallback document, so any unknown path (a client route, a deep link) is served
 * the app shell and the client router takes over — exactly the SPA the JS-readable cookie
 * + same-origin-proxy topology requires (no SSR, no server runtime in the image). The same
 * static build is what the Tauri shell wraps (ADR-0006).
 *
 * The vite dev server (and the e2e harness's `vite dev`) still serve the +server.ts /
 * +page.server.ts routes — those are a dev-only convenience (the document-workspace
 * projection seam); the deployed agent-web surface reaches the backends through the two
 * proxies, not through in-frontend server endpoints. fallback: 'index.html' is the SPA
 * document; strict:false lets the static build succeed without prerendering every route.
 *
 * @type {import('@sveltejs/kit').Config}
 */
const configuration = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapterStatic({
      fallback: 'index.html',
      strict: false,
    }),
  },
};

export default configuration;
