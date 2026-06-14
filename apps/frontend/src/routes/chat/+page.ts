// The chat slice is a client-rendered surface: it talks to the agentgateway dev-serve directly
// from the browser over REST + SSE, so there is nothing for the server to pre-render. Disabling
// SSR keeps the gateway URL resolution (window/query) and the live EventSource purely on the
// client. ssr=false (not prerender) because the page is dynamic, not static.
export const ssr = false;
export const prerender = false;
