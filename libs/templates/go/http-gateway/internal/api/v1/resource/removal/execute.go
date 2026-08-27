package removal

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// execute is the business step: it removes the resource by id through the injected Deleter port (the
// ONLY stage that touches persistence) and returns the deletion acknowledgement. A delete of an
// absent resource arrives as the persistence facade's typed errors.KindNotFound; execute preserves
// that Kind on the wrap so the envelope renders a 404 — a delete is never a silent success. It runs
// only after authenticate/validate/AUTHORIZE.
func execute(resourceStore Deleter) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, _ edenhttp.Identity, input Request) (Response, error) {
		if err := resourceStore.Delete(ctx, input.ID); err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "delete: remove resource", err)
		}
		return Response{ID: input.ID.String()}, nil
	}
}
