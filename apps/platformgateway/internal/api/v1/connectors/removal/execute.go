package removal

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// execute is the business step: it resolves the caller's organization (the tenancy key) and removes
// the connector by id THROUGH THAT ORG (the ONLY stage that touches persistence). A connector owned
// by another org (or absent) is invisible — the tenant-scoped delete matches nothing and yields the
// facade's typed KindNotFound (404); a delete is never a silent success. The CASCADE purges the
// sealed material atomically. It runs only after authenticate/validate/AUTHORIZE.
func execute(connectorStore Deleter, tenants tenantResolver) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, input Request) (Response, error) {
		callerID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "removal: parse caller subject", err)
		}
		organizationID, err := tenants.OrganizationFor(ctx, callerID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "removal: resolve caller organization", err)
		}
		if err := connectorStore.Delete(ctx, input.ID, organizationID); err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "removal: delete connector", err)
		}
		return Response{ID: input.ID.String()}, nil
	}
}
