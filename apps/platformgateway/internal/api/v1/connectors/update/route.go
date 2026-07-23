// Package update is the UPDATE route of the `connectors` resource: PUT /v1/connectors/{id}. One of
// the five 5-file route packages the resource decomposes into (ADR-0023): route.go / parse.go /
// validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// update RE-SEALS a connector's credential (rotation/replace): the new credential VALUE crosses the
// body once, execute re-seals it under a fresh DEK and supersedes the stored ciphertext. It is
// TENANT-SCOPED; a connector owned by another org is invisible (404). The Response carries NO value.
package update

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// requiredGrant is the authorization for PUT /v1/connectors/{id}: the caller must hold "connectors:write".
var requiredGrant = edenhttp.NewGrant("connectors", "write")

// Request is the typed input: the connector id from the {id} path segment plus the new credential
// value + optional account hint from the JSON body. parse reads both; validate checks the value.
type Request struct {
	// ID is the connector id parsed from the path (json:"-" so a body cannot set it — id is path-authoritative).
	ID uuid.UUID `json:"-"`
	// Value is the new credential plaintext. It crosses ONCE; execute re-seals it and never returns it.
	Value string `json:"value"`
	// AccountHint is an OPTIONAL non-secret display crumb to update alongside the credential.
	AccountHint string `json:"accountHint,omitempty"`
}

// Response is the updated connector projection (the contract's `ConnectorView`). No value field.
type Response = view.Connector

// Replacer is the single-method persistence port this route needs — TENANT-SCOPED (it takes the
// caller's org id). *persistence.Connectors satisfies it; a fake satisfies it for the unit lane.
type Replacer interface {
	Replace(
		ctx context.Context,
		id, organizationID uuid.UUID,
		accountHint, fingerprint string,
		sealed persistence.SealedMaterial,
	) (persistence.Connector, error)
}

// tenantResolver resolves the caller's owning organization (the tenancy key).
type tenantResolver interface {
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// Register assembles the handler and binds PUT /connectors/{id} (mounted under /v1). SuccessStatus
// defaults to 200.
func Register(mux *http.ServeMux, connectorStore Replacer, tenants tenantResolver, sealer envelope.Sealer, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(connectorStore, tenants, sealer),
		Action:   effect(provider),
	}
	mux.Handle("PUT /connectors/{id}", handler)
}
