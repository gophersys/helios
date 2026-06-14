import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// The chat slice talks to the agentgateway dev-serve over REST + SSE. The dev-serve sends no
// CORS headers (it is a loopback dev backend, not a public API), so the browser must reach it
// SAME-ORIGIN. We proxy `/gateway/*` through the vite dev server to the dev-serve, stripping the
// `/gateway` prefix — so the UI fetches a relative `/gateway/...` path (no CORS) and vite forwards
// it to the real backend. The proxy target is the dev-serve address; override it with
// EDEN_GATEWAY_TARGET (the E2E points it at the free port it booted the dev-serve on). SSE streams
// pass through unbuffered because the dev-serve sets X-Accel-Buffering: no and the proxy is a raw
// pipe. This keeps the gateway untouched (CORS is a deployment concern, flagged for B8).
const gatewayTarget = process.env.EDEN_GATEWAY_TARGET ?? 'http://127.0.0.1:8080';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/gateway': {
        target: gatewayTarget,
        changeOrigin: true,
        // Long-lived SSE streams must not time out at the proxy.
        timeout: 0,
        proxyTimeout: 0,
        rewrite: (path) => path.replace(/^\/gateway/, ''),
      },
    },
  },
});
