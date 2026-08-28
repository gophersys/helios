package edenhttp

import (
	"net/http"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// bearerPrefix is the Authorization scheme the Middleware strips before handing the raw token to the
// TokenVerifier (case-insensitive per RFC 7235, but the canonical form is "Bearer ").
const bearerPrefix = "Bearer "

// DefaultHeartbeatInterval is the SSE keepalive cadence when Config.HeartbeatInterval is unset: a
// comment frame every 20s keeps proxies from idling a quiet long-lived stream without flooding it.
const DefaultHeartbeatInterval = 20 * time.Second

// Config is the immutable, fully-resolved spine input (the configuration pattern: parsed at the
// edge, frozen). It reads NO env, NO clock, NO secret value of its own — the JWT secret reaches the
// spine as an already-constructed TokenVerifier on Deps (the composition root resolves
// EDEN_GATEWAY_JWT_SECRET and builds the verifier). (Config is the idiomatic Go type name HNS-1
// rule 11 exempts; a package named `config` would not be.)
type Config struct {
	// HeartbeatInterval is the SSE keepalive cadence a bridge uses (read by the consumer from
	// HeartbeatInterval()). 0 → DefaultHeartbeatInterval.
	HeartbeatInterval time.Duration
}

// Deps is the injected hexagon. New constructs no ports; everything the spine touches arrives here.
// (Deps is the idiomatic Go type name HNS-1 rule 11 exempts.)
type Deps struct {
	// Verifier authenticates each request's bearer token into an Identity (the dev-JWT HMACVerifier
	// in production-local, a real IdP verifier behind the same port elsewhere). REQUIRED.
	Verifier TokenVerifier
	// Clock is the spine's only time source (token-expiry reference + heartbeat scheduling), so New
	// stays pure and tests are deterministic. REQUIRED.
	Clock Clock
	// Logger is the redaction-safe structured-log seam; optional (a nil Logger is a no-op).
	Logger Logger
}

// Spine is the concrete value New returns (return-concrete): the consumer draws its identity
// Middleware, builds pipeline Handlers behind it, and reads the SSE heartbeat cadence from it. Its
// zero value is unusable; construct via New. Safe for concurrent use (it holds immutable
// configuration + immutable ports).
type Spine struct {
	configuration Config
	dependencies  Deps
}

// New is the pure constructor spine (10 §9): no I/O, no clock read, no env read, no goroutine. It
// validates the injected ports + Config and returns the concrete *Spine. It returns a wrapped
// ConfigError (errors.AsType, errors.KindInvalid) on a missing dependency.
//
//nolint:gocritic // contract: Config is the frozen, copyable spine input (the configuration pattern); New takes it by value.
func New(configuration Config, dependencies Deps) (*Spine, error) {
	if dependencies.Verifier == nil {
		return nil, errors.Wrap(errors.KindInvalid, "edenhttp: New",
			ConfigError{Field: "Verifier", Message: "a TokenVerifier is required (the dev-JWT verifier — behind auth even locally)"})
	}
	if dependencies.Clock == nil {
		return nil, errors.Wrap(errors.KindInvalid, "edenhttp: New",
			ConfigError{Field: "Clock", Message: "an injected Clock is required so New stays pure"})
	}
	if configuration.HeartbeatInterval <= 0 {
		configuration.HeartbeatInterval = DefaultHeartbeatInterval
	}
	return &Spine{configuration: configuration, dependencies: dependencies}, nil
}

// HeartbeatInterval returns the resolved SSE keepalive cadence the consumer schedules heartbeats on.
func (s *Spine) HeartbeatInterval() time.Duration { return s.configuration.HeartbeatInterval }

// Clock returns the injected time source, so a consumer (e.g. the SSE bridge's heartbeat ticker)
// shares the spine's single clock rather than reading the wall clock directly.
//
//nolint:ireturn // returns the consumer-defined Clock port the consumer shares (the frozen surface).
func (s *Spine) Clock() Clock { return s.dependencies.Clock }

// Middleware wraps next so every request is authenticated FIRST: it extracts the bearer token,
// verifies it (TokenVerifier), and on success stashes the resulting Identity on the request context
// (IdentityFrom) before calling next. An absent/malformed Authorization header or a token that does
// not verify is rejected with the uniform 401 error Envelope and next is NOT called — the gateway is
// behind auth even locally (ADR-0022 #3). It never logs the token value.
func (s *Spine) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		token, err := bearerToken(request)
		if err != nil {
			s.rejectUnauthenticated(writer, err)
			return
		}
		identity, err := s.dependencies.Verifier.Verify(token, s.dependencies.Clock.Now())
		if err != nil {
			s.rejectUnauthenticated(writer, err)
			return
		}
		next.ServeHTTP(writer, request.WithContext(withIdentity(request.Context(), identity)))
	})
}

// MiddlewareFunc is the http.HandlerFunc-shaped convenience over Middleware, so a consumer wraps a
// bare handler func without an explicit http.Handler conversion.
func (s *Spine) MiddlewareFunc(next http.HandlerFunc) http.Handler { return s.Middleware(next) }

// rejectUnauthenticated writes the uniform 401 Envelope and records a redaction-safe line (never the
// token). The wrapped Kind is forced to KindUnauthenticated so a verifier that returned a bare error
// still yields a 401, never a 500.
func (s *Spine) rejectUnauthenticated(writer http.ResponseWriter, cause error) {
	if errors.KindOf(cause) != errors.KindUnauthenticated {
		cause = errors.Wrap(errors.KindUnauthenticated, "edenhttp: authenticate", cause)
	}
	WriteError(writer, cause)
	if s.dependencies.Logger != nil {
		s.dependencies.Logger.Info("edenhttp: request rejected", "reason", "unauthenticated")
	}
}

// bearerToken extracts the raw token from the Authorization header, requiring the "Bearer " scheme.
// A missing header or wrong scheme is a typed KindUnauthenticated error (never echoing the header).
func bearerToken(request *http.Request) (string, error) {
	header := request.Header.Get("Authorization")
	if header == "" {
		return "", unauthenticated("missing Authorization header")
	}
	if len(header) < len(bearerPrefix) || !strings.EqualFold(header[:len(bearerPrefix)], bearerPrefix) {
		return "", unauthenticated("Authorization header must use the Bearer scheme")
	}
	token := strings.TrimSpace(header[len(bearerPrefix):])
	if token == "" {
		return "", unauthenticated("empty bearer token")
	}
	return token, nil
}
