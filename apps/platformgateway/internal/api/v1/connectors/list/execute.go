package list

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
)

// execute is the business step: it resolves the caller's organization (the tenancy key) and lists
// THAT ORG'S connectors through the Lister port (the ONLY stage that touches persistence), projecting
// each row to the wire Response (never a value). The list is scoped to the caller's org, so it can
// never surface another org's connectors. It runs only after authenticate/validate/AUTHORIZE. The
// Items slice is never nil (an empty page renders `[]`).
func execute(connectorStore Lister, tenants tenantResolver) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, input Request) (Response, error) {
		callerID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "list: parse caller subject", err)
		}
		organizationID, err := tenants.OrganizationFor(ctx, callerID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "list: resolve caller organization", err)
		}
		rows, err := connectorStore.List(ctx, organizationID, input.Limit, input.Offset)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "list: fetch connectors", err)
		}
		items := make([]view.Connector, len(rows))
		for i := range rows {
			items[i] = view.NewConnector(&rows[i])
		}
		return Response{Items: items, Limit: input.Limit, Offset: input.Offset}, nil
	}
}
