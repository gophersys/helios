// Package update is the UPDATE route of the reference `resource` CRUD: PUT /v1/resources/{id}. One
// of the five 5-file route packages the `resource` resource decomposes into (ADR-0023): route.go /
// parse.go / validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// update sets a resource's name (and bumps updated_at — the query does the bump); a missing row is
// the persistence port's typed KindNotFound, rendered as 404.
package update

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// requiredGrant is the authorization for PUT /v1/resources/{id}: the caller must hold "resource:update".
var requiredGrant = edenhttp.NewGrant("resource", "update")

// Request is the typed input: the resource id from the {id} path segment plus the new name from the
// JSON body. parse reads both; validate checks the name.
type Request struct {
	// ID is the resource id parsed from the path.
	ID uuid.UUID `json:"-"`
	// Name is the new resource name from the body. Required, non-empty (validate enforces it).
	Name string `json:"name"`
}

// Response is the updated resource projection (the contract's `ResourceView`).
type Response = view.Resource

// Updater is the single-method persistence port this route needs. *persistence.Resources satisfies
// it; a fake satisfies it for the unit lane.
type Updater interface {
	Update(ctx context.Context, id uuid.UUID, name string) (persistence.Resource, error)
}

// Register assembles the handler and binds PUT /resources/{id} (mounted under /v1). SuccessStatus
// defaults to 200.
func Register(mux *http.ServeMux, resourceStore Updater, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(resourceStore),
		Action:   effect(provider),
	}
	mux.Handle("PUT /resources/{id}", handler)
}
