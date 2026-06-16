// The Projects dashboard is a client-rendered surface: it lists projects from the agentgateway over
// REST directly from the browser, so there is nothing to pre-render. ssr=false keeps gateway URL
// resolution + the fetch on the client (mirrors the chat slice).
export const ssr = false;
export const prerender = false;
