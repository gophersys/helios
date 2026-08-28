package list

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// execute is the business step: it reads a page of resources through the injected Lister port (the
// ONLY stage that touches persistence) and projects each row to the wire view. The Items slice is
// always non-nil (initialized to an empty slice) so the success Envelope renders `[]`, never `null`,
// even for an empty page. It runs only after authenticate/validate/AUTHORIZE.
func execute(resourceStore Lister) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, _ edenhttp.Identity, input Request) (Response, error) {
		rows, err := resourceStore.List(ctx, input.Limit, input.Offset)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "list: read resources", err)
		}
		items := make([]view.Resource, 0, len(rows))
		for i := range rows {
			items = append(items, view.NewResource(&rows[i]))
		}
		return Response{Items: items, Limit: input.Limit, Offset: input.Offset}, nil
	}
}
