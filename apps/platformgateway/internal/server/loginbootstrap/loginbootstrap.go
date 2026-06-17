// Package loginbootstrap serves the PRE-IDENTITY login bootstrap: GET /bootstrap/default-user, the
// one public route the basic login reads to land on the seeded default user. Like the health probes,
// it sits OUTSIDE the /v1 auth spine — login is, by definition, pre-identity — and OUTSIDE the
// OpenAPI contract (which documents the authenticated surface). It renders the default user through
// the SAME users/view projection the authenticated routes use, so the login surface and the API agree
// on the user shape (one concept, one home, 10 §9).
//
// The package name is `loginbootstrap`, not `auth` (HNS-1 rule 11 bans `auth`); the bootstrap is the
// pre-identity entry the login flow reads, the seam a real IdP login would later replace.
package loginbootstrap

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// DefaultProvider is the one-method port the bootstrap needs: the default-user lookup. The concrete
// *persistence.Users satisfies it; a fake satisfies it for the unit lane.
type DefaultProvider interface {
	Default(ctx context.Context) (persistence.User, error)
}

// Handler builds the public default-user handler. It resolves the default user through the injected
// port and writes it as the uniform edenhttp data envelope ({ "data": <user> }); a missing default
// (the startup seed should have planted it) arrives as the persistence KindNotFound and is rendered
// as the error envelope with the mapped status. The audit Event is emitted after the write (best
// effort, never blocking the response). The id is a redaction-safe scalar — no field is a secret.
func Handler(provider DefaultProvider, observabilityProvider observability.Provider) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		user, err := provider.Default(request.Context())
		if err != nil {
			edenhttp.WriteError(writer, err)
			return
		}
		edenhttp.WriteData(writer, http.StatusOK, view.NewUser(&user))
		if observabilityProvider != nil {
			observabilityProvider.Emit(request.Context(), observability.Event{
				Name:     "bootstrap.default-user",
				Severity: observability.SeverityInfo,
				Fields:   []observability.Field{observability.String("user-id", user.ID.String())},
			})
		}
	})
}
