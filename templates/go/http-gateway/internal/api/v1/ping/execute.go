package ping

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
)

// execute is the business step: it produces the typed Response. The EXECUTE stage is the ONLY one
// that may touch a port (the persistence Querier, an upstream client) — and it runs only AFTER the
// pipeline has authenticated, parsed, validated, and AUTHORIZED the request (the Required grant the
// route declared). It receives the verified Identity, so it echoes the caller's subject; a generated
// resource queries persistence here through the injected Querier and maps a not-found to a typed
// KindNotFound error the envelope renders as 404.
func execute(_ context.Context, identity edenhttp.Identity, _ Request) (Response, error) {
	return Response{
		Subject:    identity.Subject,
		ObservedAt: time.Now().UTC().Format(time.RFC3339),
	}, nil
}
