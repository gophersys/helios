package get

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget read-audit Event naming the caller and
// the resource read. It runs AFTER the 200 Envelope is written, so its error is logged, never
// surfaced (the EFFECT stage contract). The fields are redaction-safe scalars (subject + resource
// id); a field is never a secret. nil provider → no Action.
func effect(provider observability.Provider) func(context.Context, edenhttp.Identity, Request, Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, output Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.resource.get",
			Severity: observability.SeverityInfo,
			Fields: []observability.Field{
				observability.String("subject", identity.Subject),
				observability.String("resource-id", output.ID),
			},
		})
		return nil
	}
}
