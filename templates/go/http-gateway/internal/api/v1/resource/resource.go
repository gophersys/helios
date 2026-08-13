// Package resource is the REFERENCE persisted resource: a complete CRUD over the `resource` table,
// authored as the 5-files-per-route rule demands (ADR-0023). Where `ping` is the single-route
// reference (no persistence), `resource` is the full reference — five routes (create/get/list/
// update/delete), each its OWN sub-package of exactly route.go / parse.go / validate.go / execute.go
// / effect.go, with its declarative Required Grant. The shared wire projection + name/id rules live
// in the leaf `view` package (one concept, one home, 10 §9), so no sub-package re-spells them.
//
// This file is the resource's composition seam: the aggregate Persistence port the composition root
// binds once and Register, which mounts every route. The dependency arrow points one way — this
// package imports the route sub-packages (to compose them); a sub-package never imports back.
package resource

import (
	"net/http"

	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/create"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/get"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/list"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/removal"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/update"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// Persistence is the port the `resource` routes draw on — the full CRUD surface over the `resource`
// table, exactly at the 5-method interface ceiling (interface-design rule). It is the composition of
// each route's single-method port (create.Creator, get.Getter, …), so a route depends on only the
// operation it calls while the composition root binds one aggregate. The concrete
// *persistence.Resources satisfies it; a fake satisfies it for the unit lane.
//
// It is named for what it is — the resource's persistence — because `Store` is a banned HNS-1 token
// (rule 11: `db`/`repo`/`store` → `persistence`), and `ResourceStore` in package `resource` would
// stutter. The lowercase package/directory `persistence` is the required slug for the same concept.
type Persistence interface {
	create.Creator
	get.Getter
	list.Lister
	update.Updater
	removal.Deleter
}

// compile-time assertion: the concrete persistence facade satisfies the aggregate Persistence port
// (and thereby every route's single-method port), so Register hands `resources` to each sub-package
// without an adapter.
var _ Persistence = (*persistence.Resources)(nil)

// Register mounts every `resource` route onto mux behind /v1. It is the ONE place the resource's five
// routes are composed — each sub-package owns its 5-file pipeline and declarative Required Grant;
// Register threads the shared Persistence + Observability into each, so the resource's route table +
// authz is auditable in a single read.
func Register(mux *http.ServeMux, resources Persistence, provider observability.Provider) {
	create.Register(mux, resources, provider)
	get.Register(mux, resources, provider)
	list.Register(mux, resources, provider)
	update.Register(mux, resources, provider)
	removal.Register(mux, resources, provider)
}
