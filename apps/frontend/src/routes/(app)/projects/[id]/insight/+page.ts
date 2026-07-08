// The project INSIGHT route is client-rendered like the rest of the app shell: it reads the gateway
// (GET /projects/{id}/insight) over the browser's same-origin proxy and renders the codeinsight Report
// with @eden/visualization, none of which run server-side. ssr=false keeps gateway URL resolution + the
// insight fetch on the client (mirrors the project-detail/loading + workspace routes and the chat slice).
export const ssr = false;
export const prerender = false;
