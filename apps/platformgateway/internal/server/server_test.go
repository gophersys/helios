package server_test

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/identity"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/middleware"
)

// jwtSecretRef is the loggable Reference the test JWT signing key is seeded under; the value never
// appears in a log or an error (the secrets no-leak contract), only the reference.
const jwtSecretRef = "test://gateway-jwt-signing-key"

// testClock is the injected time source for the observability Provider in tests — deterministic, so
// the Provider's New stays pure and the test reads no wall clock of its own.
type testClock struct{}

func (testClock) Now() time.Time { return time.Unix(0, 0).UTC() }

// grantRegistry is the test-wide map from a minted token's SUBJECT (a user uuid) to the grants that
// subject holds — the DB-driven model's stand-in for a real membership row. The `token` helpers register
// a fresh uuid → grant-set here, and grantResolver reads it. This is what makes authorization DB-driven
// in tests: the token carries only the subject, and the grants come from the resolver (the fake DB),
// never from the token. It is package-level + mutex-guarded because tests run in parallel.
var grantRegistry = struct {
	sync.Mutex
	bySubject map[string][]edenhttp.Grant
}{bySubject: map[string][]edenhttp.Grant{}}

// registerGrants records the grants for a subject (a minted token's user id) so the fake resolver returns
// them when the spine resolves that caller. Returns the subject for convenience.
func registerGrants(subject string, grants []edenhttp.Grant) string {
	grantRegistry.Lock()
	defer grantRegistry.Unlock()
	grantRegistry.bySubject[subject] = grants
	return subject
}

// grantResolver is the test's fake identity.GrantResolver: it returns the grants registered for the
// caller's user id (the DB-driven authorize source, mocked). An unregistered subject resolves to the
// empty grant set (an authenticated-but-unauthorized caller). The integration lane proves the SAME
// authorize on a real membership read (ADR-0016 §2).
type grantResolver struct{}

func (grantResolver) ResolveGrants(_ context.Context, userID uuid.UUID) ([]edenhttp.Grant, error) {
	grantRegistry.Lock()
	defer grantRegistry.Unlock()
	return grantRegistry.bySubject[userID.String()], nil
}

// compile-time assertion: grantResolver satisfies the DB-driven verifier's port.
var _ identity.GrantResolver = grantResolver{}

// newDeps builds the server's required ports for a test: a secretstest provider seeded with the JWT
// signing key, a real observability Provider over a discarding slog exporter (the SAME shape the
// composition root wires, so the test exercises the production seams, not stubs), and the fake
// DB-driven GrantResolver (so authorize is the resolver's answer, not the token's). It returns the
// concrete server.Deps record.
func newDeps(t *testing.T) server.Deps {
	t.Helper()
	provider, err := observability.New(
		observability.Config{ServiceName: "platformgateway", MinSeverity: observability.SeverityInfo},
		observability.Deps{Exporter: slogadapter.New(io.Discard), Clock: testClock{}},
	)
	if err != nil {
		t.Fatalf("build observability provider: %v", err)
	}
	return server.Deps{
		Secrets:       secretstest.New(map[string]string{jwtSecretRef: "test-signing-key-32-bytes-minimum!!"}),
		Observability: provider,
		GrantResolver: grantResolver{},
	}
}

// newProbeOnlyServer constructs the gateway server in probe-only mode (no readiness probes, no rate
// limit) through the REAL server.New — the same constructor the composition root calls. It proves
// the assembled handler tree (probes + the auth spine over /v1) boots with no database wired.
func newProbeOnlyServer(t *testing.T, configure func(*server.Config)) *server.Server {
	t.Helper()
	configuration := server.Config{
		JWTSecretRef:      secrets.Ref(jwtSecretRef),
		HeartbeatInterval: time.Second,
	}
	if configure != nil {
		configure(&configuration)
	}
	srv, err := server.New(configuration, newDeps(t))
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// TestNew_BootsProbeOnlyWithoutDatabase is the boot proof the prompt fixes: the server assembled with
// NO persistence wired serves GET /healthz/live with 200 — the binary comes up for the kubelet's
// liveness probe before (or without) a database. It drives the REAL handler tree end to end.
func TestNew_BootsProbeOnlyWithoutDatabase(t *testing.T) {
	t.Parallel()
	srv := newProbeOnlyServer(t, nil)

	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/healthz/live", http.NoBody))

	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /healthz/live status = %d, want 200", recorder.Code)
	}
	if got := recorder.Header().Get("X-Request-Id"); got == "" {
		t.Error("response missing X-Request-Id header (the request-id middleware did not run)")
	}
}

// TestReady_WithoutProbesIsReady asserts the readiness probe answers 200 when no dependency probes
// are wired — the probe-only boot has nothing to be unready for, the correct readiness of a
// dependency-free surface.
func TestReady_WithoutProbesIsReady(t *testing.T) {
	t.Parallel()
	srv := newProbeOnlyServer(t, nil)

	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/healthz/ready", http.NoBody))

	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /healthz/ready status = %d, want 200", recorder.Code)
	}
}

// TestV1_RejectsUnauthenticated proves the v1 surface sits behind the auth spine: a request with no
// bearer token is rejected 401 (the gateway is behind auth even locally), and it never reaches a
// route. The probes, by contrast, are public — this is the public/authenticated split the route tree
// encodes.
func TestV1_RejectsUnauthenticated(t *testing.T) {
	t.Parallel()
	srv := newProbeOnlyServer(t, nil)

	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/v1/ping", http.NoBody))

	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("GET /v1/ping (no token) status = %d, want 401", recorder.Code)
	}
}

// TestRateLimit_RejectsOverBudget proves the outer rate-limit middleware is wired into the assembled
// server: with a budget of one request per long window, a second request from the same client is
// answered 429 — even on a public probe, since the limiter wraps the WHOLE mux.
func TestRateLimit_RejectsOverBudget(t *testing.T) {
	t.Parallel()
	srv := newProbeOnlyServer(t, func(configuration *server.Config) {
		configuration.RateLimit = middleware.RateLimitConfig{Limit: 1, Window: time.Hour}
	})

	first := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/healthz/live", http.NoBody)
	request.RemoteAddr = "203.0.113.7:54321"
	srv.Handler().ServeHTTP(first, request)
	if first.Code != http.StatusOK {
		t.Fatalf("first request status = %d, want 200", first.Code)
	}

	second := httptest.NewRecorder()
	request2 := httptest.NewRequest(http.MethodGet, "/healthz/live", http.NoBody)
	request2.RemoteAddr = "203.0.113.7:54322" // same host, different port → same client bucket.
	srv.Handler().ServeHTTP(second, request2)
	if second.Code != http.StatusTooManyRequests {
		t.Fatalf("second request status = %d, want 429", second.Code)
	}
}

// TestNew_RequiresDependencies asserts the constructor rejects a missing required port with a typed
// validation error (the New-validation contract), never a nil-pointer panic at serve time.
func TestNew_RequiresDependencies(t *testing.T) {
	t.Parallel()
	dependencies := newDeps(t)
	dependencies.Secrets = nil // drop the required Secrets port.
	_, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err == nil {
		t.Fatal("server.New with no Secrets returned nil error, want a validation error")
	}
}
