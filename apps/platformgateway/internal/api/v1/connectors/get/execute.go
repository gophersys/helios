package get

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
)

// execute is the business step: it resolves the caller's organization (the tenancy key) and fetches
// the connector by id THROUGH THAT ORG (the ONLY stage that touches persistence). A connector owned
// by another org is invisible — the tenant-scoped query yields the facade's typed KindNotFound, which
// execute preserves so the envelope renders 404 (never a cross-tenant leak). It runs only after
// authenticate/validate/AUTHORIZE. The Response carries no credential value.
func execute(connectorStore Getter, tenants tenantResolver) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, input Request) (Response, error) {
		callerID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "get: parse caller subject", err)
		}
		organizationID, err := tenants.OrganizationFor(ctx, callerID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "get: resolve caller organization", err)
		}
		row, err := connectorStore.Get(ctx, input.ID, organizationID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "get: fetch connector", err)
		}
		return view.NewConnector(&row), nil
	}
}
