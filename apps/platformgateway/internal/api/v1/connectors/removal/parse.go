package removal

import (
	"net/http"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
)

// parse reads the {id} path segment into the typed Request via the shared view.ParseID rule. The
// PARSE stage owns ONLY decoding; it touches no port. A malformed id is wrapped as a typed 400.
func parse(request *http.Request) (Request, error) {
	id, err := view.ParseID(request.PathValue("id"))
	if err != nil {
		return Request{}, errors.Wrap(errors.KindOf(err), "removal: parse id", err)
	}
	return Request{ID: id}, nil
}
