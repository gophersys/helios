package removal

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a VALUE-FREE audit of the revoke (connector id + acting
// subject only). Its error is logged, never surfaced. A revoke is an Info-severity audit line (a
// security-relevant mutation worth recording).
func effect(provider observability.Provider) func(ctx context.Context, identity edenhttp.Identity, in Request, out Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, out Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.connectors.delete",
			Severity: observability.SeverityInfo,
			Fields: []observability.Field{
				observability.String("connector-id", out.ID),
				observability.String("actor", identity.Subject),
			},
		})
		return nil
	}
}
