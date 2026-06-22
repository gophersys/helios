// The project WORKSPACE route is client-rendered like the rest of the app shell: it reads the
// gateway over the browser's same-origin proxy and uses Svelte 5 runes + a live SSE subscription,
// none of which run server-side. ssr=false keeps gateway URL resolution, the worktree poll, and the
// supervisor SSE stream on the client (mirrors the project-detail/loading route and the chat slice).
export const ssr = false;
export const prerender = false;
