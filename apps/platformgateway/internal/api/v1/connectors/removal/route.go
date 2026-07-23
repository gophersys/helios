// Package removal is the DELETE route of the `connectors` resource: DELETE /v1/connectors/{id}. One
// of the five 5-file route packages the resource decomposes into (ADR-0023): route.go / parse.go /
// validate.go / execute.go / effect.go, authorization the declarative Required Grant. The package is
// `removal` (a noun) rather than `delete` because `delete` is a Go predeclared identifier (the
// predeclared linter rejects a package named for one); the route still binds the DELETE method and
// the "connectors:write" grant.
//
// removal REVOKES a connector by id (the ON DELETE CASCADE purges its sealed material atomically). It
// is TENANT-SCOPED; a connector owned by another org (or absent) yields the facade's typed
// KindNotFound → 404 (a delete is never a silent success). It returns 200 with a small {id}
// acknowledgement so the response stays within the uniform edenhttp Envelope, not a bodyless 204.
package removal

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// requiredGrant is the authorization for DELETE /v1/connectors/{id}: the caller must hold "connectors:write".
var requiredGrant = edenhttp.NewGrant("connectors", "write")

// Request is the typed input: the connector id from the {id} path segment. DELETE carries no body.
type Request struct {
	// ID is the connector id parsed from the path.
	ID uuid.UUID
}

// Response is the deletion acknowledgement: the id of the connector removed. It mirrors the contract's
// `DeleteConnectorResponse` schema, keeping delete within the uniform success Envelope.
type Response struct {
	// ID is the (string) id of the connector that was deleted.
	ID string `json:"id"`
}

// Deleter is the single-method persistence port this route needs — TENANT-SCOPED (it takes the
// caller's org id). *persistence.Connectors satisfies it; a fake satisfies it for the unit lane.
type Deleter interface {
	Delete(ctx context.Context, id, organizationID uuid.UUID) error
}

// tenantResolver resolves the caller's owning organization (the tenancy key).
type tenantResolver interface {
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// Register assembles the handler and binds DELETE /connectors/{id} (mounted under /v1). SuccessStatus
// defaults to 200 (a deletion acknowledgement body, not a bodyless 204 — the envelope is uniform).
func Register(mux *http.ServeMux, connectorStore Deleter, tenants tenantResolver, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(connectorStore, tenants),
		Action:   effect(provider),
	}
	mux.Handle("DELETE /connectors/{id}", handler)
}
