// Package server is the http-gateway's assembled HTTP surface: the pure constructor that builds the
// edenhttp spine (the dev-JWT identity gate) and mounts the health probes + the v1 routes behind its
// authentication Middleware. The composition root (cmd/gateway) wires this; the package owns no I/O
// — New is pure (10 §4), so the server is fakeable and the composition root is the only place wiring
// is chosen.
package server

import (
	"context"
	"net/http"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/secrets"

	apiv1 "github.com/gophersys/eden/apps/platformgateway/internal/api/v1"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/authlogin"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/healthcheck"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/identity"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/login"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/loginbootstrap"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/middleware"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/runtime"
)

// jwtSecretResolveTimeout bounds the one secret resolution New performs at startup.
const jwtSecretResolveTimeout = 10 * time.Second

// Config is the immutable, fully-resolved server input (the configuration pattern). It reads NO env
// and NO clock of its own — every value arrives from the composition root. (Config is the idiomatic
// Go type name HNS-1 rule 11 exempts; a package named `config` would not be.)
type Config struct {
	// JWTSecretRef is the secrets Reference the JWT signing key resolves from at startup.
	JWTSecretRef secrets.Reference
	// HeartbeatInterval is the SSE keepalive cadence the edenhttp spine schedules on (0 → default).
	HeartbeatInterval time.Duration
	// Substrate is the detected deployment substrate, recorded on the server for telemetry/branching.
	Substrate runtime.Substrate
	// RateLimit is the per-client request budget the outer middleware enforces. The zero value (Limit
	// 0) disables limiting, so a server is unlimited unless the composition root opts in.
	RateLimit middleware.RateLimitConfig
	// TokenTTL is the lifetime a /auth/login-minted session JWT is valid for. The zero value defers to
	// the login handler's dev default (24h); the composition root resolves it from EDEN_PLATFORM_TOKEN_TTL.
	TokenTTL time.Duration
}

// Deps is the injected hexagon: the narrow ports the server depends on. New consumes ports; it
// constructs none. (Deps is the idiomatic Go type name HNS-1 rule 11 exempts.)
type Deps struct {
	// Secrets is the redaction port the server resolves the JWT signing key through. REQUIRED.
	Secrets secrets.Provider
	// Observability is the structured-Event stream the server logs on. REQUIRED.
	Observability observability.Provider
	// ReadinessProbes are the dependency probes the readiness handler checks (the Postgres pool, a
	// secrets backend). Empty → the probe-only/no-DB boot: readiness answers 200 with nothing to be
	// unready for. The composition root supplies the real probes once persistence is wired.
	ReadinessProbes []healthcheck.Probe
	// Users is the typed users store the persisted `users` routes call (the consumer-defined
	// users.Store port; *persistence.Users satisfies it). Nil → the users routes are not mounted
	// (the no-DB boot serves only the no-persistence `ping` reference).
	Users users.Store
	// RBAC is the typed RBAC store the `/v1/me` route reads memberships through and the login bootstrap
	// renders the default user's profile from (the me.MembershipReader / loginbootstrap.MembershipProvider
	// port; *persistence.RBAC satisfies it). Nil → the me route + the bootstrap profile fields are not
	// served (the no-DB boot). It is ALSO the grant source the DB-driven verifier resolves the caller's
	// permissions through per request (the IOTEA permission read) — the SAME facade, one home.
	RBAC me.MembershipReader
	// Accounts is the typed linked-identity store the public /auth/login route authenticates credentials
	// against (the login.AccountReader port; *persistence.Accounts satisfies it). Nil → the /auth/login
	// route is not mounted (the no-DB boot has no credentials to verify).
	Accounts login.AccountReader
	// DefaultUser is the pre-identity default-user lookup the public login bootstrap reads (the
	// loginbootstrap.DefaultProvider port; *persistence.Users satisfies it). Nil → the bootstrap route
	// is not mounted (the no-DB boot has no default user to serve).
	DefaultUser loginbootstrap.DefaultProvider
	// DefaultMembership is the pre-identity default-user membership lookup the login bootstrap renders
	// the profile (org/role/permissions) from (the loginbootstrap.MembershipProvider port;
	// *persistence.RBAC satisfies it). Nil → the bootstrap returns the bare user fields only.
	DefaultMembership loginbootstrap.MembershipProvider
	// GrantResolver is the DB-driven authorize source the spine's verifier loads each caller's grants
	// through per request (IGNORING any grants the token carries — the IOTEA permission read). When nil
	// the server derives one from RBAC (identity.NewRBACGrantResolver); when BOTH are nil (the probe-only
	// boot) the spine authenticates but resolves no grants (every grant-bearing route is then 403). A
	// test injects a fake resolver here to drive the DB-driven authz paths without a database.
	GrantResolver identity.GrantResolver
	// Connectors is the typed connector store the `connectors` routes call (connectors.Store port;
	// *persistence.Connectors satisfies it). Nil → the connectors routes are not mounted (ADR-0029).
	Connectors connectors.Store
	// Tenants resolves the caller's owning organization for every connectors query (the tenancy key;
	// connectors.TenantResolver port). Nil → the connectors routes are not mounted.
	Tenants connectors.TenantResolver
	// Sealer is the envelope-encryption port the connectors create/update stages seal credentials with
	// (the KEK resolved from the platform Vault at composition). Nil → the connectors routes are not
	// mounted (a credential cannot be stored without it, ADR-0029).
	Sealer envelope.Sealer
}

// Server is the concrete value New returns (return-concrete): it owns the assembled http.Handler the
// composition root serves. Its zero value is unusable; construct via New. Safe for concurrent use
// (it holds an immutable handler tree).
type Server struct {
	handler http.Handler
}

// New is the pure constructor spine (10 §9): it validates Deps, resolves the JWT signing secret once
// (the ONE blocking step, bounded), builds the edenhttp dev-JWT verifier + spine, and mounts the
// health probes (public) + the v1 routes (behind the spine's authentication Middleware). It returns
// a wrapped error on a missing dependency or an unresolvable secret.
//
//nolint:gocritic // hugeParam: Deps is the by-value injection record New takes by design (the configuration pattern, like every Eden New); a pointer would invite mutation of the shared wiring.
func New(configuration Config, dependencies Deps) (*Server, error) {
	if dependencies.Secrets == nil {
		return nil, errors.New(errors.KindInvalid, "server: New requires Deps.Secrets")
	}
	if dependencies.Observability == nil {
		return nil, errors.New(errors.KindInvalid, "server: New requires Deps.Observability")
	}

	resolveCtx, cancel := context.WithTimeout(context.Background(), jwtSecretResolveTimeout)
	defer cancel()
	// Build the dev-JWT HMAC verifier ONCE. It is wired two ways from this one value: wrapped in the
	// DB-driven verifier as the spine's TokenVerifier (authenticate the subject, then load grants from
	// the DB — NOT from the token), AND handed to the /auth/login handler as the token MINTER (its Sign).
	// One signing key both mints and verifies.
	hmacVerifier, err := identity.NewVerifier(resolveCtx, dependencies.Secrets, configuration.JWTSecretRef)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "server: build identity verifier", err)
	}

	// The DB-driven authorize source: an explicit resolver (a test's fake) wins; else derive one from the
	// RBAC store; else (the probe-only boot) resolve no grants. The verifier loads the caller's grants
	// from here on every request, so a permission change in the DB takes effect on the next request.
	resolver := resolveGrantSource(dependencies)
	spine, err := edenhttp.New(
		edenhttp.Config{HeartbeatInterval: configuration.HeartbeatInterval},
		edenhttp.Deps{
			Verifier: identity.NewDBVerifier(hmacVerifier, resolver),
			Clock:    systemClock{},
			Logger:   middleware.ObservabilityLogger{Provider: dependencies.Observability},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "server: build edenhttp spine", err)
	}

	handler := route(configuration, spine, hmacVerifier, dependencies)
	return &Server{handler: handler}, nil
}

// resolveGrantSource chooses the DB-driven verifier's GrantResolver: an explicitly injected resolver (a
// test's fake) wins; else, when the RBAC store is wired, the persistence-backed RBACGrantResolver (the
// IOTEA permission read); else the no-grants resolver for the probe-only boot (the spine still
// authenticates — every grant-bearing route is then 403, the correct answer with no permission store).
//
//nolint:gocritic,ireturn // hugeParam: Deps is the by-value injection record (the configuration pattern); ireturn: returns the GrantResolver port the spine's verifier consumes (the frozen seam).
func resolveGrantSource(dependencies Deps) identity.GrantResolver {
	if dependencies.GrantResolver != nil {
		return dependencies.GrantResolver
	}
	if dependencies.RBAC != nil {
		return identity.NewRBACGrantResolver(dependencies.RBAC)
	}
	return noGrantsResolver{}
}

// noGrantsResolver is the probe-only boot's GrantResolver: it resolves an empty grant set for any caller,
// so the spine authenticates a valid token but no grant-bearing /v1 route authorizes (403). It is the
// honest answer when no permission store is wired, and it keeps server.New total (never a nil resolver).
type noGrantsResolver struct{}

// ResolveGrants returns the empty grant set — an authenticated-but-unauthorized caller.
func (noGrantsResolver) ResolveGrants(context.Context, uuid.UUID) ([]edenhttp.Grant, error) {
	return nil, nil
}

// Handler returns the assembled http.Handler the composition root serves. It is the server's only
// exported surface besides New (accept-interfaces, return-concrete — the consumer gets a usable
// http.Handler, not another port).
func (s *Server) Handler() http.Handler { return s.handler }

// route builds the handler tree, layered outside-in:
//
//	requestid+span  ─┐  (every request: correlation id + an observability Scope)
//	rate limit       ├─ the server-wide outer middleware, wrapping BOTH the probes and /v1.
//	mux             ─┘
//	  ├─ GET  /healthz/live   — PUBLIC liveness (the kubelet probes pre-identity).
//	  ├─ GET  /healthz/ready  — PUBLIC readiness (probes the injected dependencies → 503 until up).
//	  ├─ POST /auth/login     — PUBLIC login (pre-identity): credentials → a minted Eden JWT + profile.
//	  └─ /v1/  → spine.Middleware → apiMux  — the authenticated API: the spine authenticates FIRST, then
//	            loads the caller's grants from the DB and each route's declarative Required Grant
//	            authorizes against THAT set (not the token's). The gateway is behind auth even locally
//	            (ADR-0022 #3); authorization is the Required field, not a middleware.
//
// The probes + /auth/login sit OUTSIDE the auth spine (a kubelet has no token; login IS how you get one)
// but INSIDE the request-id/rate-limit outer middleware (so every request is correlated and budgeted).
//
//nolint:gocritic // hugeParam: Deps is the by-value injection record route threads (the configuration pattern); a pointer would invite mutation of the shared wiring.
func route(configuration Config, spine *edenhttp.Spine, minter authlogin.TokenMinter, dependencies Deps) http.Handler {
	mux := http.NewServeMux()

	// Public liveness/readiness probes (no auth — the kubelet probes pre-identity). Readiness checks
	// the injected dependency probes and returns 503 naming any that are down.
	mux.Handle("GET /healthz/live", healthcheck.Live())
	mux.Handle("GET /healthz/ready", healthcheck.Ready(dependencies.ReadinessProbes...))

	// Public login (no auth — login is pre-identity, like the probes): POST credentials, get a minted JWT
	// + the caller's profile. Mounted only when persistence (hence accounts/users/RBAC) is wired. The
	// password Authenticator is the default; an OAuth authenticator drops in behind the same port.
	if dependencies.Accounts != nil && dependencies.Users != nil && dependencies.RBAC != nil {
		mux.Handle("POST /auth/login", authlogin.Handler(authlogin.Deps{
			Authenticator: login.NewPasswordAuthenticator(dependencies.Accounts),
			Minter:        minter,
			Users:         dependencies.Users,
			RBAC:          dependencies.RBAC,
			Clock:         systemClock{},
			TokenTTL:      configuration.TokenTTL,
			Observability: dependencies.Observability,
		}))
	}

	// Public login bootstrap (no auth — login is pre-identity, like the probes): the basic login reads
	// the seeded default user (and, when the RBAC store is wired, their org/role/permissions) here.
	// Mounted only when persistence (hence a default user) is wired.
	if dependencies.DefaultUser != nil {
		mux.Handle("GET /bootstrap/default-user", loginbootstrap.Handler(loginbootstrap.Deps{
			DefaultUser:       dependencies.DefaultUser,
			DefaultMembership: dependencies.DefaultMembership,
			Observability:     dependencies.Observability,
		}))
	}

	// The authenticated v1 API. v1.Mount registers every resource's 5-file routes onto a sub-mux,
	// each carrying its declarative Required Grant; the whole tree sits behind the spine Middleware.
	apiMux := http.NewServeMux()
	apiv1.Mount(apiMux, apiv1.Deps{
		Observability: dependencies.Observability,
		Users:         dependencies.Users,
		RBAC:          dependencies.RBAC,
		Connectors:    dependencies.Connectors,
		Tenants:       dependencies.Tenants,
		Sealer:        dependencies.Sealer,
	})
	mux.Handle("/v1/", http.StripPrefix("/v1", spine.Middleware(apiMux)))

	// Outer, server-wide middleware (applied to the WHOLE mux): request-id + OTel span first so a
	// rejected (rate-limited) request is still correlated, then the per-client rate limit.
	requestID := middleware.RequestID(dependencies.Observability)
	rateLimit := middleware.RateLimit(configuration.RateLimit)
	return requestID(rateLimit(mux))
}

// systemClock is the server's edenhttp.Clock. New stays pure by injecting it rather than reading the
// wall clock inside the libraries; the app is the one place a real clock is read (10 §4).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }
