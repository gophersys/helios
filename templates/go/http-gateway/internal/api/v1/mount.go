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

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/ping"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource"
)

// Deps is the injected record of ports every v1 resource may draw from (the persistence store, the
// observability stream). Mount threads it to each resource's route assembly. The persistence store
// is OPTIONAL — a nil Resources means persistence is not wired (the probe-only/no-DB boot), so the
// persisted `resource` routes are not mounted and only the no-persistence `ping` reference serves.
type Deps struct {
	// Observability is the structured-Event stream a resource's effect stage records on. REQUIRED.
	Observability observability.Provider
	// Resources is the typed CRUD store the `resource` routes' execute stages call (the consumer-
	// defined resource.Store port; *persistence.Resources satisfies it). Nil → the resource routes
	// are not mounted (no-DB boot).
	Resources resource.Store
}

// Mount registers every v1 resource's routes onto mux. Each resource owns a Register that mounts its
// five-file routes (with their declarative Required Grants); Mount is the single place the resource
// set is composed, so the route table is auditable in one read. The persisted `resource` routes are
// mounted only when a store is wired — the gateway serves the `ping` reference even with no database.
func Mount(mux *http.ServeMux, dependencies Deps) {
	ping.Register(mux, ping.Deps{Observability: dependencies.Observability})
	if dependencies.Resources != nil {
		resource.Register(mux, dependencies.Resources, dependencies.Observability)
	}
}
