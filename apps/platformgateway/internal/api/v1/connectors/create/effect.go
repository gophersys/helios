package create

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
)

// effect builds the after-respond Action: a fire-and-forget audit that runs AFTER the 201 Envelope is
// written, so its error is logged, never surfaced (the EFFECT stage's contract). It emits a
// VALUE-FREE audit Event — the connector id, kind, and the acting subject ONLY. It NEVER carries the
// credential value, and NEVER the fingerprint's preimage (ADR-0029 §2.5). The observability Field
// constructors keep every field a safe scalar by construction.
//
// effect returns the edenhttp Action closure (or nil when no observability stream is wired), so the
// route assembly stays declarative: route.go reads `Action: effect(deps.Observability)`.
func effect(provider observability.Provider) func(ctx context.Context, identity edenhttp.Identity, in Request, out Response) error {
	if provider == nil {
		return nil
	}
	return func(ctx context.Context, identity edenhttp.Identity, _ Request, out Response) error {
		provider.Emit(ctx, observability.Event{
			Name:     "api.v1.connectors.create",
			Severity: observability.SeverityInfo,
			Fields: []observability.Field{
				observability.String("connector-id", out.ID),
				observability.String("connector-kind", out.Kind),
				observability.String("actor", identity.Subject),
			},
		})
		return nil
	}
}
