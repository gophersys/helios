// Package get is the GET-by-id route of the reference `resource` CRUD: GET /v1/resources/{id}. One
// of the five 5-file route packages the `resource` resource decomposes into (ADR-0023): route.go /
// parse.go / validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// get reads a single resource by its path id; a missing row is the persistence port's typed
// KindNotFound, which the pipeline renders as 404.
package get

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// requiredGrant is the authorization for GET /v1/resources/{id}: the caller must hold "resource:read".
var requiredGrant = edenhttp.NewGrant("resource", "read")

// Request is the typed input: the resource id parsed from the {id} path segment. GET carries no
// body; parse reads PathValue, validate (none beyond the parse) accepts.
type Request struct {
	// ID is the resource id parsed from the path.
	ID uuid.UUID
}

// Response is the persisted resource projection (the contract's `ResourceView`).
type Response = view.Resource

// Getter is the single-method persistence port this route needs. *persistence.Resources satisfies
// it; a fake satisfies it for the unit lane.
type Getter interface {
	Get(ctx context.Context, id uuid.UUID) (persistence.Resource, error)
}

// Register assembles the handler and binds GET /resources/{id} (mounted under /v1). The {id} path
// wildcard is read in parse via request.PathValue. SuccessStatus defaults to 200.
func Register(mux *http.ServeMux, resourceStore Getter, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(resourceStore),
		Action:   effect(provider),
	}
	mux.Handle("GET /resources/{id}", handler)
}
