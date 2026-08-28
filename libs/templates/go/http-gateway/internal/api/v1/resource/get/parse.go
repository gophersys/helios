package get

import (
	"net/http"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// parse reads the {id} path segment and parses it into a uuid. The PARSE stage owns ONLY decoding;
// it cites the shared view.ParseID rule (one home for the path-id parse), wrapping its typed 400
// with the route+stage context, before validate or execute run. It touches no port.
func parse(request *http.Request) (Request, error) {
	id, err := view.ParseID(request.PathValue("id"))
	if err != nil {
		return Request{}, errors.Wrap(errors.KindOf(err), "get: parse id", err)
	}
	return Request{ID: id}, nil
}
