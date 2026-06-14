// Runtime resolution of the gateway base URL the chat slice talks to. The dev-serve sends no CORS
// headers (it is a loopback dev backend), so the browser reaches it SAME-ORIGIN through the vite
// dev proxy: a relative `/gateway` path that vite forwards to the real dev-serve (see
// vite.config.ts; the proxy target is the dev-serve, overridable via EDEN_GATEWAY_TARGET). The URL
// is resolvable three ways, in precedence order, so the same UI runs against any dev-serve:
//
//   1. a `?gateway=<url>` query parameter (point directly at a CORS-enabled gateway, or another
//      proxy origin — the E2E uses this only when it runs against an absolute, same-origin proxy),
//   2. the PUBLIC_GATEWAY_URL build/runtime env (a deployed config),
//   3. the default `/gateway` — the same-origin vite proxy path (the local dev + E2E default).
//
// It is browser-safe: the query/window read is guarded for SSR so the page server-renders.

import { env } from '$env/dynamic/public';

/** The default gateway base: the same-origin vite proxy path that forwards to the dev-serve. */
export const DEFAULT_GATEWAY_URL = '/gateway';

/** resolveGatewayUrl picks the gateway base URL by the precedence above. */
export function resolveGatewayUrl(): string {
  if (typeof window !== 'undefined') {
    const fromQuery = new URLSearchParams(window.location.search).get('gateway');
    if (fromQuery) return fromQuery;
  }
  if (env.PUBLIC_GATEWAY_URL) return env.PUBLIC_GATEWAY_URL;
  return DEFAULT_GATEWAY_URL;
}
