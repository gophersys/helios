// Package get is the GET-by-id route of the `users` resource: GET /v1/users/{id}. One of the
// 5-file route packages users decomposes into (ADR-0023): route.go / parse.go / validate.go /
// execute.go / effect.go, authorization the declarative Required Grant.
//
// get reads a single user by its path id; a missing row is the persistence port's typed
// KindNotFound, which the pipeline renders as 404.
package get

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// requiredGrant is the authorization for GET /v1/users/{id}: the caller must hold "users:read".
var requiredGrant = edenhttp.NewGrant("users", "read")

// Request is the typed input: the user id parsed from the {id} path segment. GET carries no body;
// parse reads PathValue, validate accepts.
type Request struct {
	// ID is the user id parsed from the path.
	ID uuid.UUID
}

// Response is the persisted user projection (the contract's `UserView`).
type Response = view.User

// Getter is the single-method persistence port this route needs. *persistence.Users satisfies it; a
// fake satisfies it for the unit lane.
type Getter interface {
	Get(ctx context.Context, id uuid.UUID) (persistence.User, error)
}

// Register assembles the handler and binds GET /users/{id} (mounted under /v1). The {id} path
// wildcard is read in parse via request.PathValue. SuccessStatus defaults to 200.
func Register(mux *http.ServeMux, userStore Getter, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(userStore),
		Action:   effect(provider),
	}
	mux.Handle("GET /users/{id}", handler)
}
