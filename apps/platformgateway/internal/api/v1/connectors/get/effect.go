package get

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget audit of the read, VALUE-FREE (connector
// id + acting subject only). Its error is logged, never surfaced. A read is audited lightly (Debug)
// so the audit stream is not flooded by list/get traffic while still recording who read what.
func effect(provider observability.Provider) func(ctx context.Context, identity edenhttp.Identity, in Request, out Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, in Request, _ Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.connectors.get",
			Severity: observability.SeverityDebug,
			Fields: []observability.Field{
				observability.String("connector-id", in.ID.String()),
				observability.String("actor", identity.Subject),
			},
		})
		return nil
	}
}
