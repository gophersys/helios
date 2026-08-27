package main

import (
	"context"
	"net"
	"net/http"
	"testing"
	"time"
)

// TestServe_DrainsZeroOnSignal is the graceful-drain proof the prompt fixes: the serve loop runs an
// http.Server bound to an ephemeral listener, answers a request, and — when the signal context is
// canceled (the SIGTERM path) — returns nil, the exit-code-0 drain. It exercises the REAL serve
// function the composition root runs, not a stub.
func TestServe_DrainsZeroOnSignal(t *testing.T) {
	t.Parallel()

	// A trivial liveness-shaped handler: enough to prove the loop serves before the drain.
	handler := http.NewServeMux()
	handler.HandleFunc("GET /healthz/live", func(writer http.ResponseWriter, _ *http.Request) {
		writer.WriteHeader(http.StatusOK)
	})

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("bind ephemeral listener: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- serve(ctx, handler, listener) }()

	// Probe /healthz/live and assert 200 — the binary is up far enough to serve liveness.
	client := &http.Client{Timeout: 2 * time.Second}
	response, err := client.Get("http://" + listener.Addr().String() + "/healthz/live")
	if err != nil {
		cancel()
		t.Fatalf("GET /healthz/live: %v", err)
	}
	if closeErr := response.Body.Close(); closeErr != nil {
		t.Errorf("close response body: %v", closeErr)
	}
	if response.StatusCode != http.StatusOK {
		cancel()
		t.Fatalf("GET /healthz/live status = %d, want 200", response.StatusCode)
	}

	// SIGTERM-equivalent: cancel the signal context. serve must drain and return nil (exit 0).
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("serve returned %v on drain, want nil (exit 0)", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("serve did not return within the drain deadline")
	}
}

// TestLoadEnvironment_RequiresJWTSecretRef asserts the composition edge rejects a boot with no JWT
// secret reference — the gateway is behind auth even locally, so the required reference is a typed
// startup error, never a silent default.
func TestLoadEnvironment_RequiresJWTSecretRef(t *testing.T) {
	t.Setenv("EDEN_GATEWAY_JWT_SECRET_REF", "")
	if _, err := loadEnvironment(); err == nil {
		t.Fatal("loadEnvironment with no JWT secret ref returned nil error, want a validation error")
	}
}

// TestLoadEnvironment_ProbeOnlyWithoutDatabase asserts the DSN reference is OPTIONAL: a boot with a
// JWT ref but no database DSN parses cleanly and yields a zero PersistenceDSNRef, the probe-only
// (no-DB) boot the readiness path supports.
func TestLoadEnvironment_ProbeOnlyWithoutDatabase(t *testing.T) {
	t.Setenv("EDEN_GATEWAY_JWT_SECRET_REF", "test://jwt")
	t.Setenv("EDEN_GATEWAY_DATABASE_DSN_REF", "")
	environment, err := loadEnvironment()
	if err != nil {
		t.Fatalf("loadEnvironment: %v", err)
	}
	if !environment.PersistenceDSNRef.IsZero() {
		t.Errorf("PersistenceDSNRef = %q, want zero (probe-only boot)", environment.PersistenceDSNRef.String())
	}
}
