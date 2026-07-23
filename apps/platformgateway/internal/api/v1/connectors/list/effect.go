package list

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget audit of the list read, VALUE-FREE (the
// acting subject + the page size returned). Its error is logged, never surfaced. Debug severity so the
// audit stream is not flooded by list traffic.
func effect(provider observability.Provider) func(ctx context.Context, identity edenhttp.Identity, in Request, out Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, out Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.connectors.list",
			Severity: observability.SeverityDebug,
			Fields: []observability.Field{
				observability.String("actor", identity.Subject),
				observability.Int64("count", int64(len(out.Items))),
			},
		})
		return nil
	}
}
