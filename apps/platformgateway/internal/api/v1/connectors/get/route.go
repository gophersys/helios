// Package get is the GET-by-id route of the `connectors` resource: GET /v1/connectors/{id}. One of
// the five 5-file route packages the resource decomposes into (ADR-0023): route.go / parse.go /
// validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// get reads a single connector's metadata by id, TENANT-SCOPED to the caller's org; a connector owned
// by another org is invisible (rendered as 404, never a cross-tenant leak). The Response carries NO
// credential value.
package get

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// requiredGrant is the authorization for GET /v1/connectors/{id}: the caller must hold "connectors:read".
var requiredGrant = edenhttp.NewGrant("connectors", "read")

// Request is the typed input: the connector id parsed from the {id} path segment. GET carries no body.
type Request struct {
	// ID is the connector id parsed from the path.
	ID uuid.UUID
}

// Response is the persisted connector projection (the contract's `ConnectorView`). No value field.
type Response = view.Connector

// Getter is the single-method persistence port this route needs — TENANT-SCOPED (it takes the
// caller's org id, so a cross-org id resolves to KindNotFound). *persistence.Connectors satisfies it.
type Getter interface {
	Get(ctx context.Context, id, organizationID uuid.UUID) (persistence.Connector, error)
}

// tenantResolver resolves the caller's owning organization (the tenancy key). The aggregate's
// TenantResolver satisfies it.
type tenantResolver interface {
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// Register assembles the handler and binds GET /connectors/{id} (mounted under /v1). The {id} path
// wildcard is read in parse via request.PathValue. SuccessStatus defaults to 200.
func Register(mux *http.ServeMux, connectorStore Getter, tenants tenantResolver, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(connectorStore, tenants),
		Action:   effect(provider),
	}
	mux.Handle("GET /connectors/{id}", handler)
}
