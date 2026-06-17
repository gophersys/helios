// Module github.com/gophersys/eden/apps/platformgateway/clients/go — the typed Go
// test/integration client EMITTED from the http-gateway OpenAPI contract (ADR-0023, codegen axis
// #2). It is its OWN module so the regenerated client never breaks the gateway module's build, and
// so the oapi-codegen runtime deps stay out of the gateway's dependency graph.
module github.com/gophersys/eden/apps/platformgateway/clients/go

go 1.26

require github.com/oapi-codegen/runtime v1.4.1

require (
	github.com/apapsch/go-jsonmerge/v2 v2.0.0 // indirect
	github.com/google/uuid v1.6.0 // indirect
)
