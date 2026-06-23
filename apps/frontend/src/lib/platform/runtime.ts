// runtime — the one place the app learns whether it is running in the WEB browser or the DESKTOP shell
// (the Tauri app, ADR-0006). The two surfaces open external things differently: web opens a new browser
// tab; desktop hands a custom URI (e.g. vscode://…) to the OS so the user's native app launches. SSR-safe.

import { env } from '$env/dynamic/public';

/** isDesktop reports whether the app is running inside the Tauri desktop shell vs a browser. The Tauri
 *  runtime injects `window.__TAURI__`, which is the authoritative signal even if the build env was not
 *  baked; `PUBLIC_EDEN_RUNTIME=desktop` is the predictable build-time default. Web is the fallback. */
export function isDesktop(): boolean {
  if (typeof window !== 'undefined' && '__TAURI__' in window) return true;
  return env.PUBLIC_EDEN_RUNTIME === 'desktop';
}
