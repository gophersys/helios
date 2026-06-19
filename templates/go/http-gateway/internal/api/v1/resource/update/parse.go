package update

import (
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// parse reads BOTH inputs PUT /v1/resources/{id} carries: the {id} path segment (via the shared
// view.ParseID rule) and the new name from the JSON body (via DecodeJSONBody, which rejects unknown
// fields — the body's `id` is json:"-", so a body that tries to set it is rejected, keeping the id
// path-authoritative). The PARSE stage owns ONLY decoding; it touches no port. A malformed id or
// body is wrapped as a typed 400 with the route+stage context.
func parse(request *http.Request) (Request, error) {
	id, err := view.ParseID(request.PathValue("id"))
	if err != nil {
		return Request{}, errors.Wrap(errors.KindOf(err), "update: parse id", err)
	}
	var input Request
	if err := edenhttp.DecodeJSONBody(request, &input); err != nil {
		return Request{}, errors.Wrap(errors.KindOf(err), "update: parse body", err)
	}
	input.ID = id
	return input, nil
}
