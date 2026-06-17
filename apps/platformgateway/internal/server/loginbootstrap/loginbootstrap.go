// Package loginbootstrap serves the PRE-IDENTITY login bootstrap: GET /bootstrap/default-user, the
// one public route the basic login reads to land on the seeded default user. Like the health probes,
// it sits OUTSIDE the /v1 auth spine — login is, by definition, pre-identity — and OUTSIDE the
// OpenAPI contract (which documents the authenticated surface). It renders the default user through
// the SAME me/view projection the authenticated /v1/me route uses, so the login surface and the API
// agree on the profile shape (one concept, one home, 10 §9): the user fields PLUS the IOTEA RBAC
// context (organization, role, permissions) the tokenless frontend shows on login.
//
// The package name is `loginbootstrap`, not `auth` (HNS-1 rule 11 bans `auth`); the bootstrap is the
// pre-identity entry the login flow reads, the seam a real IdP login would later replace.
package loginbootstrap

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"

	meview "github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me/view"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// DefaultProvider is the one-method port the bootstrap needs for the user part: the default-user
// lookup. The concrete *persistence.Users satisfies it; a fake satisfies it for the unit lane.
type DefaultProvider interface {
	Default(ctx context.Context) (persistence.User, error)
}

// MembershipProvider is the one-method RBAC port the bootstrap needs for the profile part: the
// membership lookup by user id. The concrete *persistence.RBAC satisfies it; a fake satisfies it for
// the unit lane. When nil the bootstrap renders the bare user fields only.
type MembershipProvider interface {
	MembershipFor(ctx context.Context, userID uuid.UUID) (persistence.Membership, error)
}

// Deps is the injected record of ports the bootstrap handler draws on. DefaultUser is REQUIRED (the
// handler is mounted only when a default user exists); DefaultMembership and Observability are
// OPTIONAL — a nil DefaultMembership renders the bare user fields (no org/role/permissions), a nil
// Observability skips the audit Event.
type Deps struct {
	// DefaultUser is the default-user lookup. REQUIRED.
	DefaultUser DefaultProvider
	// DefaultMembership is the default user's RBAC membership lookup. Nil → bare user fields only.
	DefaultMembership MembershipProvider
	// Observability is the audit stream the read is emitted on. Nil → no audit Event.
	Observability observability.Provider
}

// Handler builds the public default-user handler. It resolves the default user through the injected
// port and, when the RBAC membership provider is wired, ALSO resolves their organization/role/
// permissions and writes the FULL profile (the SAME meview.Profile shape /v1/me returns) — so the
// tokenless frontend can show the default user's org and permissions on login. The top-level user
// fields (id/email/name/isDefault/timestamps) are present in BOTH shapes (Profile embeds the user
// view), so an existing login client reading those fields keeps working. A missing default (the
// startup seed should have planted it) arrives as the persistence KindNotFound and is rendered as the
// error envelope. The audit Event is emitted after the write (best effort). The id is a redaction-safe
// scalar — no field is a secret.
func Handler(dependencies Deps) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		user, err := dependencies.DefaultUser.Default(request.Context())
		if err != nil {
			edenhttp.WriteError(writer, err)
			return
		}
		payload, err := renderPayload(request.Context(), &user, dependencies.DefaultMembership)
		if err != nil {
			edenhttp.WriteError(writer, err)
			return
		}
		edenhttp.WriteData(writer, http.StatusOK, payload)
		if dependencies.Observability != nil {
			dependencies.Observability.Emit(request.Context(), observability.Event{
				Name:     "bootstrap.default-user",
				Severity: observability.SeverityInfo,
				Fields:   []observability.Field{observability.String("user-id", user.ID.String())},
			})
		}
	})
}

// renderPayload projects the default user (and, when the membership provider is wired, their RBAC
// context) into the wire payload. With a membership provider it returns the full meview.Profile (user
// fields + organization/role/permissions); without one it returns the bare users/view.User. Both
// shapes carry the same top-level user fields, so the login client's existing assertions hold either
// way. A membership-lookup failure (e.g. a missing membership) is surfaced as the error envelope —
// the seed plants the default membership, so its absence is a real fault, not masked.
func renderPayload(ctx context.Context, user *persistence.User, membershipProvider MembershipProvider) (any, error) {
	if membershipProvider == nil {
		return view.NewUser(user), nil
	}
	membership, err := membershipProvider.MembershipFor(ctx, user.ID)
	if err != nil {
		// Preserve the membership lookup's Kind (a missing membership is the facade's KindNotFound) so
		// WriteError renders the right status; the boundary wrap keeps the chain.
		return nil, errors.Wrap(errors.KindOf(err), "loginbootstrap: resolve default-user membership", err)
	}
	return meview.NewProfile(user, &membership), nil
}
