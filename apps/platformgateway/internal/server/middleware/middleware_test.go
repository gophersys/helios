package middleware_test

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/middleware"
)

// okHandler is a trivial 200 handler the middleware wraps in tests.
var okHandler = http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
	writer.WriteHeader(http.StatusOK)
})

// TestRateLimit_Disabled asserts a non-positive Limit is a pass-through: every request is admitted,
// so the policy is opt-in (a server with no configured budget is unlimited).
func TestRateLimit_Disabled(t *testing.T) {
	t.Parallel()
	handler := middleware.RateLimit(middleware.RateLimitConfig{})(okHandler)
	for i := 0; i < 5; i++ {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, request("198.51.100.1:5000"))
		if recorder.Code != http.StatusOK {
			t.Fatalf("request %d under disabled limiter status = %d, want 200", i, recorder.Code)
		}
	}
}

// TestRateLimit_BudgetThen429 asserts the per-client sliding window admits up to Limit then rejects,
// and that a DIFFERENT client has its own budget (the bucket is per-client IP).
func TestRateLimit_BudgetThen429(t *testing.T) {
	t.Parallel()
	handler := middleware.RateLimit(middleware.RateLimitConfig{Limit: 2, Window: time.Hour})(okHandler)

	// Client A: two admitted, the third rejected.
	assertStatus(t, handler, "192.0.2.10:1", http.StatusOK)
	assertStatus(t, handler, "192.0.2.10:2", http.StatusOK)
	assertStatus(t, handler, "192.0.2.10:3", http.StatusTooManyRequests)

	// Client B: its own fresh budget, unaffected by A.
	assertStatus(t, handler, "192.0.2.20:1", http.StatusOK)
}

// TestRequestID_PropagatesInbound asserts an inbound X-Request-Id is propagated (not overwritten) so
// an ingress-minted correlation id flows through unchanged, and a request without one is minted.
func TestRequestID_PropagatesInbound(t *testing.T) {
	t.Parallel()
	handler := middleware.RequestID(nil)(okHandler) // nil provider → id propagation without a span.

	const inbound = "ingress-correlation-1234"
	recorder := httptest.NewRecorder()
	req := request("203.0.113.1:9")
	req.Header.Set("X-Request-Id", inbound)
	handler.ServeHTTP(recorder, req)
	if got := recorder.Header().Get("X-Request-Id"); got != inbound {
		t.Errorf("propagated request id = %q, want %q", got, inbound)
	}

	minted := httptest.NewRecorder()
	handler.ServeHTTP(minted, request("203.0.113.1:10"))
	if got := minted.Header().Get("X-Request-Id"); got == "" {
		t.Error("a request without an inbound id was not assigned one")
	}
}

// request builds a GET with the given client remote address.
func request(remoteAddr string) *http.Request {
	req := httptest.NewRequest(http.MethodGet, "/healthz/live", http.NoBody)
	req.RemoteAddr = remoteAddr
	return req
}

// assertStatus drives one request through handler and asserts the status.
func assertStatus(t *testing.T, handler http.Handler, remoteAddr string, want int) {
	t.Helper()
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request(remoteAddr))
	if recorder.Code != want {
		t.Fatalf("client %s status = %d, want %d", remoteAddr, recorder.Code, want)
	}
}
