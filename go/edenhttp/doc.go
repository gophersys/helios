// Package edenhttp is the Eden HTTP spine — the reusable, harness-shaped building blocks an
// Eden HTTP service composes its surface from (ADR-0022 #3). It is NOT a server and owns no
// routes of its own: it is a small kit of composable pieces a consumer (the agentgateway,
// B5) wires behind net/http.
//
// It owns four concepts, each with one home (10 §9):
//
//   - The 6-stage handler PIPELINE (parse → validate → authorize → execute → respond → action),
//     adopted from the IOTEA prior art and adapted to Eden + the frozen errors taxonomy. A
//     Handler[I, O] is a typed, composable value: a request is decoded into the typed input I,
//     validated, authorized against a required grant, executed into the typed output O, and
//     written as a uniform Envelope; an optional after-respond Action runs last. Every stage
//     surfaces a typed *errors.Error whose Kind maps to an HTTP status (one mapping, one home).
//
//   - The uniform response ENVELOPE — every Eden HTTP body is {data, errors} (a list of
//     operator-safe error strings), so the browser branches on one shape across every route.
//
//   - The SSE writer/STREAM helper — event framing (id:/event:/data:), an explicit Flush, a
//     heartbeat/keepalive comment cadence, and Last-Event-ID/from-seq cursor parsing. This is
//     the half IOTEA never had (it has no streaming); it is Eden-new and is the spine of the
//     B5 NATS→SSE bridge (the gateway frames each agentruntime.EventEnvelope through it).
//
//   - IDENTITY + authz — a dev-JWT (HMAC-SHA256) verifier and the namespace:action grant
//     grammar (IOTEA RBAC). A Middleware verifies the bearer token, extracts the caller's
//     Identity (subject + granted namespace:action set), and stashes it on the request context
//     so a pipeline's authorize stage admits or denies a required Grant. The gateway is behind
//     auth EVEN LOCALLY: a dev JWT signed with the secret named by EDEN_GATEWAY_JWT_SECRET.
//     The lib's auth CONCEPT is "identity" (HNS-1 rule 11: never a package/concept named
//     `auth`); idiomatic token/JWT type names are fine.
//
// It does NOT own: a router/mux (net/http is the consumer's; this kit returns http.Handler /
// http.HandlerFunc the consumer mounts), the NATS bus (the gateway injects a consumer-defined
// publisher/subscriber — agentruntime owns the bus protocol; edenhttp never imports nats.go),
// the agentsession Event taxonomy (transported, never redefined — the gateway projects it), or
// credential storage (the JWT secret is a value the consumer resolves from secrets/env and
// hands to New; edenhttp never reads the environment).
//
// Construction spine: New(Config, Deps) is PURE (10 §9): no I/O, no clock read, no env read.
// It validates the injected ports + Config and returns the concrete *Spine the consumer draws
// its Middleware and SSE writers from. The ports are consumer-defined and ≤5 methods each.
//
// Module: github.com/gophersys/libs/go/edenhttp (go 1.26).
package edenhttp
