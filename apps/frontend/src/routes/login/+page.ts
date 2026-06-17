// The login screen is client-rendered: it reads the platform API (the browser's same-origin
// `/platform` proxy) and uses Svelte 5 runes, neither of which run server-side. ssr=false mirrors the
// dashboard + chat routes.
export const ssr = false;
