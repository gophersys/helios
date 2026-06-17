// The app shell + its pages are client-rendered: they read the gateway/platform APIs (the browser's
// same-origin proxies) and use Svelte 5 runes, neither of which run server-side. ssr=false applies to
// every route in this group (mirrors the chat + login routes).
export const ssr = false;
