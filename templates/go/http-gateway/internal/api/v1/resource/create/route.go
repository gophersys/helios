// Package create is the CREATE route of the reference `resource` CRUD: POST /v1/resources. It is one
// of the five 5-file route packages the `resource` resource decomposes into (ADR-0023). Every route
// is exactly route.go / parse.go / validate.go / execute.go / effect.go, and authorization is the
// declarative Required Grant on the assembled edenhttp.Handler — never a sixth file.
//
// create mints the resource id server-side (the database does not default it), so the request body
// carries only the name; the response is the persisted resource at 201 Created.
package create

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// requiredGrant is the authorization for POST /v1/resources, declared ONCE here. It becomes the
// edenhttp.Handler.Required field — the pipeline's AUTHORIZE stage admits the request iff the
// caller's Identity holds a grant covering "resource:create".
var requiredGrant = edenhttp.NewGrant("resource", "create")

// Request is the typed input POST /v1/resources decodes to: the new resource's name (the id is
// server-minted, the timestamps are database-stamped, so the body carries only the name). It mirrors
// the contract's `CreateResourceRequest` schema.
type Request struct {
	// Name is the resource's human label. Required, non-empty (validate enforces it).
	Name string `json:"name"`
}

// Response is the typed output the execute stage produces and the pipeline writes as the 201
// Envelope: the persisted resource projection. It mirrors the contract's `ResourceView` schema.
type Response = view.Resource

// Creator is the single-method persistence port this route needs — the SHAPE OF THE NEED (interface
// -design rule: a route depends on the one operation it calls, not the whole store). *persistence.
// Resources satisfies it; a fake satisfies it for the unit lane.
type Creator interface {
	Create(ctx context.Context, id uuid.UUID, name string) (persistence.Resource, error)
}

// Register assembles the edenhttp.Handler from the five stages and binds POST /resources (mounted
// under /v1 by the server). The Required grant is the AUTHORIZE stage; SuccessStatus is 201 Created
// for the resource-minted-here semantics.
func Register(mux *http.ServeMux, resourceStore Creator, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:         parse,
		Validate:      validate,
		Required:      requiredGrant,
		Execute:       execute(resourceStore),
		SuccessStatus: http.StatusCreated,
		Action:        effect(provider),
	}
	mux.Handle("POST /resources", handler)
}
