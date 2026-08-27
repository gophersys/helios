package create

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// execute is the business step: it mints a server-side resource id and inserts the resource through
// the injected Creator port (the ONLY stage that touches persistence), then projects the persisted
// row to the wire Response. It runs only AFTER the pipeline authenticated, parsed, validated, and
// AUTHORIZED the request. A persistence fault is wrapped on the boundary (Kind preserved) so the
// envelope renders the right status; the id is generated here (uuid.New) because the database does
// not default it — an insert is explicit and reproducible.
func execute(resourceStore Creator) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, _ edenhttp.Identity, input Request) (Response, error) {
		row, err := resourceStore.Create(ctx, uuid.New(), input.Name)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "create: insert resource", err)
		}
		return view.NewResource(&row), nil
	}
}
