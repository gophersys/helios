package update

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// execute is the business step: it updates the resource's name through the injected Updater port
// (the ONLY stage that touches persistence) and projects the updated row to the wire Response. A
// missing row arrives as the persistence facade's typed errors.KindNotFound; execute preserves that
// Kind on the wrap so the envelope renders a 404. It runs only after authenticate/validate/AUTHORIZE.
func execute(resourceStore Updater) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, _ edenhttp.Identity, input Request) (Response, error) {
		row, err := resourceStore.Update(ctx, input.ID, input.Name)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "update: set resource name", err)
		}
		return view.NewResource(&row), nil
	}
}
