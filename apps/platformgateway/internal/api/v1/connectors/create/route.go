// Package create is the CREATE route of the `connectors` resource: POST /v1/connectors. One of the
// five 5-file route packages the resource decomposes into (ADR-0023): route.go / parse.go /
// validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// create is Eden's FIRST authenticated write route (ADR-0029, doc 19). The credential VALUE crosses
// the request body exactly ONCE here; execute seals it via the injected envelope.Sealer and stores
// only the ciphertext + a fingerprint. The 201 Response is the persisted connector projection —
// which carries NO value, ever.
package create

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

// requiredGrant is the authorization for POST /v1/connectors, declared ONCE here. It becomes the
// edenhttp.Handler.Required field — the pipeline's AUTHORIZE stage admits the request iff the caller's
// Identity holds a grant covering "connectors:write".
var requiredGrant = edenhttp.NewGrant("connectors", "write")

// Request is the typed input POST /v1/connectors decodes to: the connector kind, its name, the
// credential VALUE (the plaintext, crossing this seam once), and the scope. It mirrors the contract's
// `CreateConnectorRequest` schema. Value is json-tagged like any field but is NEVER echoed back — the
// Response type has no value field. The scope selector is the shared view.ScopeInput (one home).
type Request struct {
	// Kind is the connector kind ("claude-api"|"github"|"openrouter"). validate checks the enum.
	Kind string `json:"kind"`
	// Name is the connector's human label. Required, non-empty (validate enforces it).
	Name string `json:"name"`
	// Value is the credential plaintext. It crosses ONCE; execute seals it and never returns it.
	Value string `json:"value"`
	// AccountHint is an OPTIONAL non-secret display crumb (an account handle / masked email).
	AccountHint string `json:"accountHint,omitempty"`
	// Scope is the connector's tenancy scope (org default / user).
	Scope view.ScopeInput `json:"scope"`
}

// Response is the typed output the execute stage produces and the pipeline writes as the 201
// Envelope: the persisted connector projection. It mirrors the contract's `ConnectorView` schema and
// carries NO value.
type Response = view.Connector

// Creator is the single-method persistence port this route needs — the SHAPE OF THE NEED (a route
// depends on the one operation it calls). *persistence.Connectors satisfies it; a fake satisfies it
// for the unit lane. It takes the already-sealed material (execute does the sealing) so persistence
// never sees a plaintext.
type Creator interface {
	Create(
		ctx context.Context,
		id, organizationID uuid.UUID,
		userID *uuid.UUID,
		kind, name, accountHint, fingerprint string,
		createdBy uuid.UUID,
		sealed persistence.SealedMaterial,
	) (persistence.Connector, error)
}

// tenantResolver is the port the route resolves the caller's owning organization through (the tenancy
// key every query is scoped by). Declared here as the shape of the need; the aggregate's
// TenantResolver satisfies it.
type tenantResolver interface {
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// Register assembles the edenhttp.Handler from the five stages and binds POST /connectors (mounted
// under /v1 by the server). The Required grant is the AUTHORIZE stage; SuccessStatus is 201 Created.
func Register(mux *http.ServeMux, connectorStore Creator, tenants tenantResolver, sealer envelope.Sealer, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:         parse,
		Validate:      validate,
		Required:      requiredGrant,
		Execute:       execute(connectorStore, tenants, sealer),
		SuccessStatus: http.StatusCreated,
		Action:        effect(provider),
	}
	mux.Handle("POST /connectors", handler)
}
