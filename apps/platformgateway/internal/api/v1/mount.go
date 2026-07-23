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

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/ping"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users"
)

// Deps is the injected record of ports every v1 resource may draw from (the persistence stores, the
// observability stream). Mount threads it to each resource's route assembly. The persistence stores
// are OPTIONAL — a nil Users means persistence is not wired (the probe-only/no-DB boot), so the
// persisted `users`/`me` routes are not mounted and only the no-persistence `ping` reference serves.
type Deps struct {
	// Observability is the structured-Event stream a resource's effect stage records on. REQUIRED.
	Observability observability.Provider
	// Users is the typed users store the `users` routes' execute stages call (the consumer-defined
	// users.Store port; *persistence.Users satisfies it). Nil → the users/me routes are not mounted
	// (no-DB boot).
	Users users.Store
	// RBAC is the typed RBAC store the `me` route reads memberships through (the me.MembershipReader
	// port; *persistence.RBAC satisfies it). Nil → the me route is not mounted (no-DB boot).
	RBAC me.MembershipReader
	// Connectors is the typed connector store the `connectors` routes' execute stages call (the
	// consumer-defined connectors.Store port; *persistence.Connectors satisfies it). Nil → the
	// connectors routes are not mounted (no-DB boot, or no envelope Sealer wired — ADR-0029).
	Connectors connectors.Store
	// Tenants resolves the caller's owning organization for every connectors query (the tenancy key;
	// connectors.TenantResolver port). Nil → the connectors routes are not mounted.
	Tenants connectors.TenantResolver
	// Sealer is the envelope-encryption port the connectors create/update stages seal a credential
	// with (the KEK resolved from the platform Vault at composition). Nil → the connectors routes are
	// not mounted (there is nothing to seal credentials with — a hard requirement, ADR-0029).
	Sealer envelope.Sealer
}

// Mount registers every v1 resource's routes onto mux. Each resource owns a Register that mounts its
// five-file routes (with their declarative Required Grants); Mount is the single place the resource
// set is composed, so the route table is auditable in one read. The persisted `users`/`me` routes are
// mounted only when a store is wired — the gateway serves the `ping` reference even with no database.
func Mount(mux *http.ServeMux, dependencies Deps) {
	ping.Register(mux, ping.Deps{Observability: dependencies.Observability})
	if dependencies.Users != nil {
		users.Register(mux, dependencies.Users, dependencies.Observability)
		// /v1/me reads the caller's user record + their RBAC membership. The users.Store satisfies the
		// route's UserGetter (it embeds get.Getter), so Mount threads it alongside the RBAC store.
		if dependencies.RBAC != nil {
			me.Register(mux, dependencies.Users, dependencies.RBAC, dependencies.Observability)
		}
	}
	// The connectors routes mount only when the store, the tenant resolver, AND the envelope Sealer
	// are all wired — a connector cannot be sealed without the Sealer, so the resource is absent
	// rather than half-wired (ADR-0029).
	if dependencies.Connectors != nil && dependencies.Tenants != nil && dependencies.Sealer != nil {
		connectors.Register(mux, dependencies.Connectors, dependencies.Tenants, dependencies.Sealer, dependencies.Observability)
	}
}
