package create

import (
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// parse decodes the JSON request body into the typed Request. The PARSE stage owns ONLY decoding —
// edenhttp.DecodeJSONBody bounds the body and rejects unknown fields (a malformed body is a typed
// 400). It does NOT validate the decoded value (that is validate) and touches no port. The decode
// error is wrapped with the route+stage context (Kind preserved) as it crosses the package boundary.
func parse(request *http.Request) (Request, error) {
	var input Request
	if err := edenhttp.DecodeJSONBody(request, &input); err != nil {
		return Request{}, errors.Wrap(errors.KindOf(err), "create: parse body", err)
	}
	return input, nil
}
