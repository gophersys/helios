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
// platformgateway (Eden's platform HTTP API: users + login) is a SECOND backend the UI reaches
// same-origin through a `/platform/*` proxy, the same shape as `/gateway`. The login screen fetches
// `/platform/bootstrap/default-user`. Override the target with EDEN_PLATFORM_TARGET (the demo points
// it at the in-container platformgateway-live; the E2E at the free port it booted it on).
const platformTarget = process.env.EDEN_PLATFORM_TARGET ?? 'http://127.0.0.1:8081';

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
      '/platform': {
        target: platformTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/platform/, ''),
      },
    },
  },
});
