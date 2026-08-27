package get

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// execute is the business step: it fetches the resource by id through the injected Getter port (the
// ONLY stage that touches persistence) and projects it to the wire Response. A missing row arrives
// as the persistence facade's typed errors.KindNotFound; execute preserves that Kind on the wrap, so
// the envelope renders a 404 (not a 500). It runs only after authenticate/validate/AUTHORIZE.
func execute(resourceStore Getter) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, _ edenhttp.Identity, input Request) (Response, error) {
		row, err := resourceStore.Get(ctx, input.ID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "get: fetch resource", err)
		}
		return view.NewResource(&row), nil
	}
}
