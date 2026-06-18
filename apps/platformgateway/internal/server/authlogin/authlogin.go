// Package authlogin serves the PUBLIC, PRE-IDENTITY login endpoint: POST /auth/login, the one route a
// tokenless caller hits to exchange credentials for an Eden JWT. Like the health probes and the login
// bootstrap it sits OUTSIDE the /v1 auth spine (login is, by definition, pre-identity) and OUTSIDE the
// OpenAPI contract (which documents only the authenticated /v1 surface). It is the REAL authentication
// entry the basic-login flow reads.
//
// The flow is the IOTEA shape (PERMISSION_SYSTEM_GUIDE): authenticate the credentials through the
// login.Authenticator (today password; a Google/GitHub authenticator drops in behind the SAME port),
// MINT a JWT that carries ONLY the user id (no grants — the DB-driven verifier loads grants per request),
// then render the caller's profile (the SAME meview.Profile shape /v1/me returns) so the frontend has the
// user's org/role/permissions immediately on login. On a bad credential the handler answers 401 WITHOUT
// revealing which of email/password was wrong (the Authenticator collapses both to KindUnauthenticated).
//
// The package name is `authlogin` — the login ENDPOINT (distinct from the `login` package that owns the
// authentication PORT, and from `loginbootstrap` that owns the default-user bootstrap); `auth` alone is
// banned (rule 11), so the concept is spelled in the compound.
package authlogin

import (
	"context"
	"net/http"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"

	meview "github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me/view"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/login"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// defaultTokenTTL is the lifetime a minted login token is valid for when no override is configured. It is
// a DEV default (24h) — long enough that a local session does not expire mid-work; a deployment overrides
// it via EDEN_PLATFORM_TOKEN_TTL at the composition root.
const defaultTokenTTL = 24 * time.Hour

// TokenMinter is the one-method port the handler mints the session JWT through: subject + grants +
// expiry → a signed token. The concrete *edenhttp.HMACVerifier satisfies it (its Sign method), so the
// SAME verifier the spine authenticates with also mints here — one signing key, both directions. The
// handler passes NO grants (the empty slice): grants live in the DB now and the DB-driven verifier loads
// them per request, so the token is a pure identity assertion.
type TokenMinter interface {
	Sign(subject string, grants []edenhttp.Grant, expiresAt time.Time) (string, error)
}

// UserReader is the one-method users port the handler renders the profile's user fields through (the
// authenticated user's record by id). The concrete *persistence.Users satisfies it.
type UserReader interface {
	Get(ctx context.Context, id uuid.UUID) (persistence.User, error)
}

// MembershipReader is the one-method RBAC port the handler renders the profile's org/role/permissions
// through (the user's first/default membership). The concrete *persistence.RBAC satisfies it.
type MembershipReader interface {
	MembershipFor(ctx context.Context, userID uuid.UUID) (persistence.Membership, error)
}

// Clock is the minimal injected time port the handler stamps token expiry from (now + TTL). The
// composition root injects the real wall clock; a test injects a deterministic one. New stays pure.
type Clock interface{ Now() time.Time }

// Deps is the injected record the login handler draws on. Every field is REQUIRED — the route is mounted
// only when persistence (hence accounts/users/RBAC) is wired, so the handler always has a real
// Authenticator, minter, stores, and clock. Observability is optional (a nil skips the audit Event).
type Deps struct {
	// Authenticator resolves the posted credentials to a user id (today password; OAuth drops in here).
	Authenticator login.Authenticator
	// Minter signs the session JWT (the SAME *edenhttp.HMACVerifier the spine verifies with).
	Minter TokenMinter
	// Users renders the profile's user fields. REQUIRED.
	Users UserReader
	// RBAC renders the profile's org/role/permissions. REQUIRED.
	RBAC MembershipReader
	// Clock stamps token expiry (now + TokenTTL). REQUIRED.
	Clock Clock
	// TokenTTL is the minted token's lifetime; <= 0 → defaultTokenTTL (the dev 24h default).
	TokenTTL time.Duration
	// Observability is the audit stream the login is emitted on. Nil → no audit Event.
	Observability observability.Provider
}

// request is the POST /auth/login body: the email + plaintext password. The Password is a credential
// value — it is decoded, handed to the Authenticator, and NEVER logged or put on an error.
type request struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// response is the success payload (wrapped by edenhttp.WriteData in the `{ "data": ... }` Envelope): the
// minted session token plus the caller's profile (the SAME meview.Profile /v1/me returns), so the
// frontend lands on login with both the bearer token and the user's org/role/permissions.
type response struct {
	// Token is the signed Eden JWT the caller sends as the Bearer credential on /v1 requests.
	Token string `json:"token"`
	// Profile is the authenticated caller's profile (user fields + organization/role/permissions).
	Profile meview.Profile `json:"profile"`
}

// Handler builds the public POST /auth/login handler. It decodes the credentials, authenticates them
// through the injected Authenticator (a bad credential → a typed 401 the error Envelope renders, never
// revealing which factor was wrong), mints a JWT carrying ONLY the user id, renders the caller's profile,
// and writes the `{ "data": { token, profile } }` Envelope. A malformed body is a 400; an authentication
// failure is a 401; a missing user/membership after a successful auth is the persistence Kind (a real
// fault, surfaced honestly). The audit Event is emitted after the write (best effort) and carries only
// the user id — never the email or the password.
//
//nolint:gocritic // hugeParam: Deps is the by-value injection record Handler takes (the configuration pattern, like every Eden handler builder); a pointer would invite mutation of the shared wiring.
func Handler(dependencies Deps) http.Handler {
	ttl := dependencies.TokenTTL
	if ttl <= 0 {
		ttl = defaultTokenTTL
	}
	return http.HandlerFunc(func(writer http.ResponseWriter, httpRequest *http.Request) {
		var body request
		if err := edenhttp.DecodeJSONBody(httpRequest, &body); err != nil {
			edenhttp.WriteError(writer, err)
			return
		}

		ctx := httpRequest.Context()
		userID, err := dependencies.Authenticator.Authenticate(ctx, login.Credentials{
			Email:    body.Email,
			Password: body.Password,
		})
		if err != nil {
			// The Authenticator returns KindUnauthenticated on a bad credential → a 401 Envelope. The cause
			// (which never carries the email/password) rides for the server log; the client sees only 401.
			edenhttp.WriteError(writer, err)
			return
		}

		token, err := dependencies.Minter.Sign(userID.String(), nil, dependencies.Clock.Now().Add(ttl))
		if err != nil {
			edenhttp.WriteError(writer, errors.Wrap(errors.KindInternal, "authlogin: mint token", err))
			return
		}

		profile, err := renderProfile(ctx, userID, dependencies.Users, dependencies.RBAC)
		if err != nil {
			edenhttp.WriteError(writer, err)
			return
		}

		edenhttp.WriteData(writer, http.StatusOK, response{Token: token, Profile: profile})
		if dependencies.Observability != nil {
			dependencies.Observability.Emit(ctx, observability.Event{
				Name:     "auth.login",
				Severity: observability.SeverityInfo,
				Fields:   []observability.Field{observability.String("user-id", userID.String())},
			})
		}
	})
}

// renderProfile loads the authenticated user + their membership and projects them into the wire Profile
// through the SAME meview.NewProfile /v1/me and the bootstrap use (one concept, one home). A missing user
// or membership after a successful authentication is a real fault (the account linked to a user that
// should exist) — surfaced with its persistence Kind, not masked.
func renderProfile(ctx context.Context, userID uuid.UUID, users UserReader, rbac MembershipReader) (meview.Profile, error) {
	user, err := users.Get(ctx, userID)
	if err != nil {
		return meview.Profile{}, errors.Wrap(errors.KindOf(err), "authlogin: load user for profile", err)
	}
	membership, err := rbac.MembershipFor(ctx, userID)
	if err != nil {
		return meview.Profile{}, errors.Wrap(errors.KindOf(err), "authlogin: load membership for profile", err)
	}
	return meview.NewProfile(&user, &membership), nil
}
