// Package list is the LIST route of the `connectors` resource: GET /v1/connectors. One of the five
// 5-file route packages the resource decomposes into (ADR-0023): route.go / parse.go / validate.go /
// execute.go / effect.go, authorization the declarative Required Grant.
//
// list returns a paginated page of the CALLER'S ORG connectors oldest-first, TENANT-SCOPED — it never
// lists another org's connectors, and never carries a credential value. Pagination is limit/offset.
package list

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// requiredGrant is the authorization for GET /v1/connectors: the caller must hold "connectors:read".
var requiredGrant = edenhttp.NewGrant("connectors", "read")

// defaultLimit / maxLimit bound the page size: an absent ?limit defaults to defaultLimit, and a
// requested limit is clamped to maxLimit so a client cannot ask for an unbounded page.
const (
	defaultLimit = 50
	maxLimit     = 200
)

// Request is the typed input: the resolved pagination window. parse reads ?limit and ?offset
// (defaulting/clamping), validate checks they are in range.
type Request struct {
	// Limit is the page size (resolved: defaulted and clamped in parse).
	Limit int32
	// Offset is the page offset (0-based).
	Offset int32
}

// Response is the page: the connector projections (never a value) plus the window that produced them.
// It mirrors the contract's `ConnectorPage` schema.
type Response struct {
	// Items is the page of connectors (never null — an empty page is []).
	Items []view.Connector `json:"items"`
	// Limit is the resolved page size.
	Limit int32 `json:"limit"`
	// Offset is the page offset.
	Offset int32 `json:"offset"`
}

// Lister is the single-method persistence port this route needs — TENANT-SCOPED (it takes the
// caller's org id). *persistence.Connectors satisfies it; a fake satisfies it for the unit lane.
type Lister interface {
	List(ctx context.Context, organizationID uuid.UUID, limit, offset int32) ([]persistence.Connector, error)
}

// tenantResolver resolves the caller's owning organization (the tenancy key). The aggregate's
// TenantResolver satisfies it.
type tenantResolver interface {
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// Register assembles the handler and binds GET /connectors (mounted under /v1). SuccessStatus
// defaults to 200.
func Register(mux *http.ServeMux, connectorStore Lister, tenants tenantResolver, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: requiredGrant,
		Execute:  execute(connectorStore, tenants),
		Action:   effect(provider),
	}
	mux.Handle("GET /connectors", handler)
}
