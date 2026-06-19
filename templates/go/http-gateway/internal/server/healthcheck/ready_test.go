package healthcheck_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/healthcheck"
)

// TestReady_NoProbesIsReady asserts a readiness handler with no dependency probes answers 200 — the
// probe-only surface is ready by definition.
func TestReady_NoProbesIsReady(t *testing.T) {
	t.Parallel()
	recorder := serveReady(healthcheck.Ready())
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", recorder.Code)
	}
}

// TestReady_AllUpIsReady asserts that when every probe reports reachable, readiness is 200.
func TestReady_AllUpIsReady(t *testing.T) {
	t.Parallel()
	recorder := serveReady(healthcheck.Ready(
		healthcheck.NamedProbe{Label: "postgres", CheckFunc: func(context.Context) error { return nil }},
		healthcheck.NamedProbe{Label: "vault", CheckFunc: func(context.Context) error { return nil }},
	))
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", recorder.Code)
	}
}

// TestReady_DownDependencyIs503 asserts that a single unreachable dependency drops readiness to 503
// and the response names the failing dependency — the signal an operator reads off the probe.
func TestReady_DownDependencyIs503(t *testing.T) {
	t.Parallel()
	down := errors.New(errors.KindUnavailable, "postgres unreachable")
	recorder := serveReady(healthcheck.Ready(
		healthcheck.NamedProbe{Label: "postgres", CheckFunc: func(context.Context) error { return down }},
		healthcheck.NamedProbe{Label: "vault", CheckFunc: func(context.Context) error { return nil }},
	))
	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", recorder.Code)
	}
	if body := recorder.Body.String(); !contains(body, "postgres") {
		t.Errorf("503 body %q does not name the failing dependency", body)
	}
}

// serveReady drives one GET against a readiness handler and returns the recorder.
func serveReady(handler http.Handler) *httptest.ResponseRecorder {
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/healthz/ready", http.NoBody))
	return recorder
}

// contains is a tiny substring check kept local so the test pulls no extra dependency.
func contains(haystack, needle string) bool {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return true
		}
	}
	return false
}
