// Package list is the LIST route of the `users` resource: GET /v1/users. One of the 5-file route
// packages users decomposes into (ADR-0023): route.go / parse.go / validate.go / execute.go /
// effect.go, authorization the declarative Required Grant.
//
// list returns a paginated page of users oldest-first (the seed default user is the first account).
// Pagination is limit/offset (the query is already LIMIT/OFFSET); the page echoes the resolved
// limit/offset so a client can page deterministically.
package list

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// requiredGrant is the authorization for GET /v1/users: the caller must hold "users:read".
var requiredGrant = edenhttp.NewGrant("users", "read")

// defaultLimit / maxLimit bound the page size: an absent ?limit defaults to defaultLimit, and a
// requested limit is clamped to maxLimit so a client cannot ask for an unbounded page.
const (
	defaultLimit = 50
	maxLimit     = 200
)

// Request is the typed input: the resolved pagination window. parse reads ?limit and ?offset from the
// query (defaulting/clamping), validate checks they are in range.
type Request struct {
	// Limit is the page size (resolved: defaulted and clamped in parse).
	Limit int32
	// Offset is the page offset (0-based).
	Offset int32
}

// Response is the page: the user projections plus the window that produced them, so a client can
// request the next page deterministically. It mirrors the contract's `UserPage` schema.
type Response struct {
	// Items is the page of users (never null — an empty page is []).
	Items []view.User `json:"items"`
	// Limit is the resolved page size.
	Limit int32 `json:"limit"`
	// Offset is the page offset.
	Offset int32 `json:"offset"`
}

// Lister is the single-method persistence port this route needs. *persistence.Users satisfies it; a
// fake satisfies it for the unit lane.
type Lister interface {
	List(ctx context.Context, limit, offset int32) ([]persistence.User, error)
}

// Register assembles the handler and binds GET /users (mounted under /v1). SuccessStatus defaults to
// 200.
func Register(mux *http.ServeMux, userStore Lister, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(userStore),
		Action:   effect(provider),
	}
	mux.Handle("GET /users", handler)
}
