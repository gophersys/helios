package create

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget audit Event recording that a resource
// was created and by whom. It runs AFTER the 201 Envelope is written, so its error is logged, never
// surfaced to the client (the EFFECT stage contract) — it is NOT the primary write (that is
// execute). The fields are redaction-safe scalars (the subject and the new resource id); a field is
// never a secret. nil provider → no Action (the route assembly stays declarative).
func effect(provider observability.Provider) func(context.Context, edenhttp.Identity, Request, Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, output Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.resource.create",
			Severity: observability.SeverityInfo,
			Fields: []observability.Field{
				observability.String("subject", identity.Subject),
				observability.String("resource-id", output.ID),
			},
		})
		return nil
	}
}
