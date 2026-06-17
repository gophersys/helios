// Package v1 is the gateway's versioned HTTP API surface (the /v1 prefix). It is the home of the
// RESOURCES, each authored as the 5-files-per-route rule demands: every route is exactly
// route.go / parse.go / validate.go / execute.go / effect.go, and authorization is the declarative
// Required Grant on the route's edenhttp.Handler — NOT a sixth file (ADR-0023). Mount registers
// every resource's routes onto the sub-mux the server mounts behind the spine's authentication
// Middleware.
//
// The `ping` resource below is the ONE worked example shipped with the template — a complete,
// compiling demonstration of the five files. A generated app adds resources by copying its shape
// (the .claude/rules drive that); it is NOT a stub of logic, it is the reference route.
package v1

import (
	"net/http"

	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/ping"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users"
)

// Deps is the injected record of ports every v1 resource may draw from (the persistence store, the
// observability stream). Mount threads it to each resource's route assembly. The persistence store
// is OPTIONAL — a nil Users means persistence is not wired (the probe-only/no-DB boot), so the
// persisted `users` routes are not mounted and only the no-persistence `ping` reference serves.
type Deps struct {
	// Observability is the structured-Event stream a resource's effect stage records on. REQUIRED.
	Observability observability.Provider
	// Users is the typed users store the `users` routes' execute stages call (the consumer-defined
	// users.Store port; *persistence.Users satisfies it). Nil → the users routes are not mounted
	// (no-DB boot).
	Users users.Store
}

// Mount registers every v1 resource's routes onto mux. Each resource owns a Register that mounts its
// five-file routes (with their declarative Required Grants); Mount is the single place the resource
// set is composed, so the route table is auditable in one read. The persisted `users` routes are
// mounted only when a store is wired — the gateway serves the `ping` reference even with no database.
func Mount(mux *http.ServeMux, dependencies Deps) {
	ping.Register(mux, ping.Deps{Observability: dependencies.Observability})
	if dependencies.Users != nil {
		users.Register(mux, dependencies.Users, dependencies.Observability)
	}
}
