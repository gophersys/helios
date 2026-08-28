// Package list is the LIST route of the reference `resource` CRUD: GET /v1/resources. One of the
// five 5-file route packages the `resource` resource decomposes into (ADR-0023): route.go / parse.go
// / validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// list returns a paginated page of resources newest-first. Pagination is limit/offset (OD-16-
// pagination is unruled; the template ships the simplest honest window — the query is already
// LIMIT/OFFSET); the page echoes the resolved limit/offset so a client can page deterministically.
package list

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// requiredGrant is the authorization for GET /v1/resources: the caller must hold "resource:read".
var requiredGrant = edenhttp.NewGrant("resource", "read")

// defaultLimit / maxLimit bound the page size: an absent ?limit defaults to defaultLimit, and a
// requested limit is clamped to maxLimit so a client cannot ask for an unbounded page.
const (
	defaultLimit = 50
	maxLimit     = 200
)

// Request is the typed input: the resolved pagination window. parse reads ?limit and ?offset from
// the query (defaulting/clamping), validate checks they are in range.
type Request struct {
	// Limit is the page size (resolved: defaulted and clamped in parse).
	Limit int32
	// Offset is the page offset (0-based).
	Offset int32
}

// Response is the page: the resource projections plus the window that produced them, so a client can
// request the next page deterministically. It mirrors the contract's `ResourcePage` schema.
type Response struct {
	// Items is the page of resources (never null — an empty page is []).
	Items []view.Resource `json:"items"`
	// Limit is the resolved page size.
	Limit int32 `json:"limit"`
	// Offset is the page offset.
	Offset int32 `json:"offset"`
}

// Lister is the single-method persistence port this route needs. *persistence.Resources satisfies
// it; a fake satisfies it for the unit lane.
type Lister interface {
	List(ctx context.Context, limit, offset int32) ([]persistence.Resource, error)
}

// Register assembles the handler and binds GET /resources (mounted under /v1). SuccessStatus
// defaults to 200.
func Register(mux *http.ServeMux, resourceStore Lister, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(resourceStore),
		Action:   effect(provider),
	}
	mux.Handle("GET /resources", handler)
}
