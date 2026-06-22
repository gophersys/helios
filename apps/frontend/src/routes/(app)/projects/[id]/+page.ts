// The project-detail / loading route is client-rendered like the rest of the app shell: it reads the
// gateway over the browser's same-origin proxy and uses Svelte 5 runes + polling, neither of which run
// server-side. ssr=false keeps gateway URL resolution + the status poll on the client (mirrors the
// projects dashboard and the chat slice).
export const ssr = false;
export const prerender = false;
