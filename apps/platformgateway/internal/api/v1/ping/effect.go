package ping

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget side effect that runs AFTER the success
// Envelope is written, so its error is logged, never surfaced to the client (the EFFECT stage's
// contract). It is where an audit line, a metric, or a domain event is emitted — never the primary
// write (that is execute). The ping example records a redaction-safe audit Event naming the caller;
// a field is never a secret (the observability Field constructors keep it so by construction).
//
// effect returns the edenhttp Action closure (or nil when no observability stream is wired), so the
// route assembly stays declarative: route.go reads `Action: effect(deps.Observability)`.
func effect(provider observability.Provider) func(ctx context.Context, identity edenhttp.Identity, in Request, out Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, _ Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.ping",
			Severity: observability.SeverityInfo,
			Fields:   []observability.Field{observability.String("subject", identity.Subject)},
		})
		return nil
	}
}
