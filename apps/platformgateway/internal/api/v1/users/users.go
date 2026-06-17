// Package users is Eden's first persisted domain resource: the read slice over the `users` table,
// authored as the 5-files-per-route rule demands (ADR-0023). Two routes — get (GET /v1/users/{id})
// and list (GET /v1/users) — each its OWN sub-package of exactly route.go / parse.go / validate.go /
// execute.go / effect.go, with its declarative Required Grant. The shared wire projection lives in the
// leaf `view` package (one concept, one home, 10 §9), which the pre-identity login bootstrap also
// renders the default user through, so the login surface and the authenticated API agree on the
// user shape.
//
// This file is the resource's composition seam: the aggregate Store port the composition root binds
// once and Register, which mounts every route. The dependency arrow points one way — this package
// imports the route sub-packages (to compose them); a sub-package never imports back. Create/update/
// delete are deferred to a later backend piece (the backend grows piece by piece).
package users

import (
	"net/http"

	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/get"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/list"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// Store is the persistence port the `users` routes draw on — the read surface over the `users`
// table. It is the composition of each route's single-method port (get.Getter, list.Lister), so a
// route depends on only the operation it calls while the composition root binds one aggregate. The
// concrete *persistence.Users satisfies it; a fake satisfies it for the unit lane.
type Store interface {
	get.Getter
	list.Lister
}

// compile-time assertion: the concrete persistence facade satisfies the aggregate Store (and thereby
// every route's single-method port), so Register hands `userStore` to each sub-package without an adapter.
var _ Store = (*persistence.Users)(nil)

// Register mounts every `users` route onto mux behind /v1. It is the ONE place the resource's routes
// are composed — each sub-package owns its 5-file pipeline and declarative Required Grant; Register
// threads the shared Store + Observability into each, so the resource's route table + authz is
// auditable in a single read.
func Register(mux *http.ServeMux, userStore Store, provider observability.Provider) {
	get.Register(mux, userStore, provider)
	list.Register(mux, userStore, provider)
}
