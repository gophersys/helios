// Package connectors is Eden's per-user/org third-party credential domain: the write-once,
// envelope-encrypted connector store the settings UI drives and an agent session resolves (ADR-0029,
// doc 19). It is authored as the 5-files-per-route rule demands (ADR-0023): five routes — create
// (POST /v1/connectors), get (GET /v1/connectors/{id}), list (GET /v1/connectors), update (PUT
// /v1/connectors/{id}), removal (DELETE /v1/connectors/{id}) — each its OWN sub-package of exactly
// route.go / parse.go / validate.go / execute.go / effect.go, with its declarative Required Grant.
// The shared wire projection lives in the leaf `view` package (one concept, one home).
//
// This file is the resource's composition seam: the aggregate Store + TenantResolver ports the
// composition root binds once, the closed v1 Kind enum, and Register (which mounts every route). The
// credential VALUE crosses only the create/update parse seam, is sealed via the injected
// envelope.Sealer at execute, and is NEVER returned, logged, or stored in plaintext.
package connectors

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/create"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/get"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/list"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/removal"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/update"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// Store is the persistence port the `connectors` routes draw on — the write + tenant-scoped read
// surface over the connectors tables. It is the composition of each route's single-method port
// (create.Creator, get.Getter, list.Lister, update.Replacer, removal.Deleter), so a route depends on
// only the operation it calls while the composition root binds one aggregate. It sits at the 5-method
// ceiling exactly (create/get/list/replace/delete); a sixth would split it read/write. The concrete
// *persistence.Connectors satisfies it; a fake satisfies it for the unit lane.
type Store interface {
	create.Creator
	get.Getter
	list.Lister
	update.Replacer
	removal.Deleter
}

// TenantResolver is the port the routes resolve the caller's owning organization through — the
// tenancy key EVERY query is scoped by (WHERE organization_id = $callerOrg, ADR-0029 §2.3). It is the
// shape of the need (one method): map a verified subject (user id) to their organization id. The
// *persistence.RBAC facade's MembershipFor satisfies it via a thin adapter in the composition root; a
// fake satisfies it for the unit lane. Named here because every write/read route needs it.
type TenantResolver interface {
	// OrganizationFor returns the organization the caller (a user id) belongs to. A caller with no
	// membership is a typed errors.KindNotFound the route renders as 404 (they own no connectors).
	OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error)
}

// compile-time assertion: the concrete persistence facade satisfies the aggregate Store (and thereby
// every route's single-method port), so Register hands `connectorStore` to each sub-package without an
// adapter.
var _ Store = (*persistence.Connectors)(nil)

// Register mounts every `connectors` route onto mux behind /v1. It is the ONE place the resource's
// routes are composed — each sub-package owns its 5-file pipeline and declarative Required Grant;
// Register threads the shared Store, the TenantResolver, the envelope.Sealer (the credential-sealing
// port), and Observability into each, so the resource's route table + authz is auditable in a single
// read.
func Register(mux *http.ServeMux, connectorStore Store, tenants TenantResolver, sealer envelope.Sealer, provider observability.Provider) {
	create.Register(mux, connectorStore, tenants, sealer, provider)
	get.Register(mux, connectorStore, tenants, provider)
	list.Register(mux, connectorStore, tenants, provider)
	update.Register(mux, connectorStore, tenants, sealer, provider)
	removal.Register(mux, connectorStore, tenants, provider)
}
