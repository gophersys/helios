// Package removal is the DELETE route of the reference `resource` CRUD: DELETE /v1/resources/{id}.
// One of the five 5-file route packages the `resource` resource decomposes into (ADR-0023): route.go
// / parse.go / validate.go / execute.go / effect.go, authorization the declarative Required Grant.
// The package is `removal` (a noun) rather than `delete` because `delete` is a Go predeclared
// identifier (the predeclared linter rejects a package named for one); the route still binds the
// DELETE method and the "resource:delete" grant.
//
// removal deletes a resource by id; a delete of an absent resource is the persistence port's typed
// KindNotFound (the DELETE ... RETURNING yields no row), rendered as 404 — a delete is never a
// silent success. It returns 200 with a small {id} acknowledgement so the response stays within the
// uniform edenhttp Envelope (every route returns {data, errors}), not a bodyless 204.
package removal

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// requiredGrant is the authorization for DELETE /v1/resources/{id}: the caller must hold
// "resource:delete".
var requiredGrant = edenhttp.NewGrant("resource", "delete")

// Request is the typed input: the resource id from the {id} path segment. DELETE carries no body.
type Request struct {
	// ID is the resource id parsed from the path.
	ID uuid.UUID
}

// Response is the deletion acknowledgement: the id of the resource removed. It mirrors the contract's
// `DeleteResourceResponse` schema, keeping delete within the uniform success Envelope.
type Response struct {
	// ID is the (string) id of the resource that was deleted.
	ID string `json:"id"`
}

// Deleter is the single-method persistence port this route needs. *persistence.Resources satisfies
// it; a fake satisfies it for the unit lane.
type Deleter interface {
	Delete(ctx context.Context, id uuid.UUID) error
}

// Register assembles the handler and binds DELETE /resources/{id} (mounted under /v1). SuccessStatus
// defaults to 200 (a deletion acknowledgement body, not a bodyless 204 — the envelope is uniform).
func Register(mux *http.ServeMux, resourceStore Deleter, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(resourceStore),
		Action:   effect(provider),
	}
	mux.Handle("DELETE /resources/{id}", handler)
}
