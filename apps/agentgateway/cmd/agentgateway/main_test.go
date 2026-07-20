package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// labelHandler is a stub that writes its own label, so the route-precedence test can assert WHICH
// plane a request landed on without any real substrate.
func labelHandler(label string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(label)) //nolint:errcheck // a stub response writer; a write fault is not a signal for this routing test.
	})
}

// TestComposeMux_RoutesEachPlane proves the combined surface: every pod LIVE-plane pattern routes to
// the bridge handler, and every OTHER path (the REST/record plane) falls through to the rest handler
// via the "/" catch-all. The Go 1.22 ServeMux specific-over-catch-all precedence is the load-bearing
// guarantee; a pattern conflict would panic at composeMux construction, so reaching the assertions at
// all proves the composition is conflict-free.
func TestComposeMux_RoutesEachPlane(t *testing.T) {
	t.Parallel()
	mux := composeMux(labelHandler("bridge"), labelHandler("rest"))
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)

	cases := []struct {
		name   string
		method string
		path   string
		want   string
	}{
		// The pod LIVE plane → the bridge.
		{"events", http.MethodGet, "/sessions/abc/events", "bridge"},
		{"control", http.MethodPost, "/sessions/abc/control", "bridge"},
		{"prompt", http.MethodPost, "/sessions/abc/prompt", "bridge"},
		{"stop", http.MethodPost, "/sessions/abc/stop", "bridge"},
		{"kill", http.MethodPost, "/sessions/abc/kill", "bridge"},
		// The REST/record plane → the full gateway (the catch-all).
		{"propose", http.MethodPost, "/product/propose", "rest"},
		{"projects", http.MethodGet, "/projects", "rest"},
		{"create-session", http.MethodPost, "/sessions", "rest"},
		{"list-sessions", http.MethodGet, "/sessions", "rest"},
		{"get-session", http.MethodGet, "/sessions/abc", "rest"},
		{"transcript", http.MethodGet, "/sessions/abc/transcript", "rest"},
		{"agent-configs", http.MethodGet, "/agent-configs", "rest"},
		{"healthz", http.MethodGet, "/healthz", "rest"},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			request, err := http.NewRequest(testCase.method, server.URL+testCase.path, http.NoBody)
			if err != nil {
				t.Fatalf("new request: %v", err)
			}
			response, err := server.Client().Do(request)
			if err != nil {
				t.Fatalf("do request: %v", err)
			}
			defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a close fault on a drained body is not a signal.
			body, err := io.ReadAll(response.Body)
			if err != nil {
				t.Fatalf("read response body: %v", err)
			}
			if string(body) != testCase.want {
				t.Fatalf("%s %s routed to %q, want %q", testCase.method, testCase.path, string(body), testCase.want)
			}
		})
	}
}
