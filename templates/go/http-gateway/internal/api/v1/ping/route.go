// Package ping is the WORKED EXAMPLE resource that demonstrates the 5-files-per-route rule
// (ADR-0023). A resource's every route is exactly five files, each owning one stage of the edenhttp
// 6-stage pipeline:
//
//	route.go     — ASSEMBLE the edenhttp.Handler: wire parse/validate/execute/effect + declare the
//	               Required Grant (authorization is THIS field, not a sixth file) + register the route.
//	parse.go     — decode the request into the typed input.
//	validate.go  — check the parsed input is well-formed.
//	execute.go   — the business step: produce the typed output (the only stage that may touch a port).
//	effect.go    — the after-respond side effect (audit/telemetry); its error is logged, never surfaced.
//
// `ping` is a read route (GET /v1/ping) requiring the "ping:read" grant, returning the caller's
// subject and a server timestamp — small enough to be the whole reference in one read, real enough
// to compile and serve.
package ping

import (
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// requiredGrant is the authorization for GET /v1/ping, declared ONCE here. It becomes the
// edenhttp.Handler.Required field — the pipeline's AUTHORIZE stage checks the caller's Identity holds
// a grant covering it. This is the 5-file rule's "authz is a field, not a file" in one line.
var requiredGrant = edenhttp.NewGrant("ping", "read")

// Deps is the injected record of ports this resource's route assembly draws from. The worked example
// needs only the observability stream (its effect stage records an audit line); a real resource adds
// the persistence Querier here.
type Deps struct {
	Observability observability.Provider
}

// Register mounts the resource's routes onto mux. It ASSEMBLES the edenhttp.Handler from the five
// stages and binds the route — the one place the resource's pipeline is composed, so the route's
// authz + shape is auditable in a single read.
func Register(mux *http.ServeMux, dependencies Deps) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute,
		Action:   effect(dependencies.Observability),
	}
	mux.Handle("GET /ping", handler)
}
